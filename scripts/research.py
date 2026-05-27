"""Zweistufige Recherche-Pipeline:

1. **Sammel-Stufe** (Tools an): Haiku mit web_search + web_fetch sammelt
   möglichst viele Roh-Items im 7-Tage-Fenster und gibt sie als kompakte,
   parsbare Blöcke aus. Kein Ranking, keine Beratersicht.
2. **Kurations-Stufe** (Tools aus): Haiku ohne Tools wählt aus der Rohliste
   die 5–7 relevantesten Items, dedupliziert gegen die DB und schreibt das
   finale Markdown mit Relevanz-Sätzen.

Die Trennung spart Kosten (Tool-freier Curate-Call ist günstig) und verbessert
die Auswahl-Qualität (eigener Pass nur für Ranking/Dedup).
"""
from __future__ import annotations

import logging
import os
import re
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic

from database import load_items, save_items
from parse import (
    DATE_LABEL_RE,
    LABEL_BLACKLIST,
    TITLE_LINE_RE,
    parse_items,
    upsert_items,
)

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
COLLECT_PROMPT_FILE = ROOT / "prompts" / "collect_prompt.md"
CURATE_PROMPT_FILE = ROOT / "prompts" / "curate_prompt.md"

MODEL = "claude-haiku-4-5"
COLLECT_MAX_TOKENS = 8000
CURATE_MAX_TOKENS = 4000
# Tool-Budget für die Sammel-Stufe. Getrennt pro Tool:
# - web_search: 32, deckt die 28 Pflicht-Suchen (Teil A+B+C) mit Puffer ab.
# - web_fetch: 8, hält Input-Tokens unter Haikus 200k-Kontext-Limit.
#   Jeder Fetch bringt 10–30k Tokens Webseiten-Inhalt; bei 28+ Suchen
#   (je ~3–5k Tokens) bleiben nach Fetches ~50–70k Puffer für System-
#   Prompt + Modell-Output. Erhöhen erst, wenn Tier-2-Limits gekauft.
MAX_WEB_SEARCH_USES = 32
MAX_WEB_FETCH_USES = 8
# Maximale Anzahl Items, die als Dedup-Basis an die Kurations-Stufe gehen
# (neueste zuerst).
DEDUP_CONTEXT_LIMIT = 40
# Harter Cap auf Roh-Items, die an Stage 2 weitergereicht werden — schützt
# Stage-2-Input-Kosten, falls der Sammel-Agent das Prompt-Limit ignoriert.
MAX_RAW_ITEMS = 100

# Pause zwischen Stage 1 und Stage 2 in Sekunden. Stage 1 verbraucht typisch
# 200–300k Input-Tokens (web_fetch zählt voll), Tier-1-Limit ist 50k/min.
# Ohne Pause schlägt Stage 2 mit HTTP 429 fehl. Testlauf 2026-05-27: 90s
# reichten nicht, 120s-Fallback-Retry war nötig — daher direkt 150s als
# Default. Bei Stage 1 mit ~230k Input dauert das Token-Bucket-Recovery
# rechnerisch ~4.6min, aber Stage 2 braucht nur ~10k Tokens, daher genügen
# ~2.5min Pause in der Praxis.
INTER_STAGE_SLEEP_SECONDS = 150

# Hartes Kosten-Budget pro Pipeline-Lauf (USD). Bei Überschreitung wird der
# Lauf abgebrochen statt weiterzulaufen. Haiku 4.5: $1/MTok input, $5/MTok output.
# Achtung: web_search ($10/1000 Suchen) und web_fetch (Input-Tokens) sind im
# Modell-Usage enthalten bzw. wird die Such-Komponente nicht separat gezählt —
# Schätzung ist konservativ für Tokens, eventuelle Such-Gebühren obendrauf.
BUDGET_USD = 2.00
HAIKU_INPUT_USD_PER_MTOK = 1.0
HAIKU_OUTPUT_USD_PER_MTOK = 5.0


class BudgetExceededError(RuntimeError):
    """Wird ausgelöst, wenn das Pipeline-Budget überschritten wird."""


def _estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        (input_tokens / 1_000_000) * HAIKU_INPUT_USD_PER_MTOK
        + (output_tokens / 1_000_000) * HAIKU_OUTPUT_USD_PER_MTOK
    )


def _berlin_now() -> datetime:
    return datetime.now(ZoneInfo("Europe/Berlin"))


def _build_dedup_context(items: list[dict], limit: int = DEDUP_CONTEXT_LIMIT) -> str:
    """Kurze Liste 'Titel — URL' für die Dedup-Vergleichsbasis."""
    if not items:
        return "VERGLEICHSBASIS: leere Datenbank — alle Treffer sind potenziell neu."
    recent = sorted(
        items,
        key=lambda i: i.get("published_date", ""),
        reverse=True,
    )[:limit]
    lines = [f"- {i.get('title','')} — {i.get('url','')}" for i in recent]
    return (
        f"VERGLEICHSBASIS — bereits in der Datenbank "
        f"({len(recent)} jüngste von {len(items)} Items):\n"
        + "\n".join(lines)
    )


def _build_collect_system(prompt_body: str, today: str, cutoff: str, now: str) -> str:
    return (
        f"{prompt_body}\n\n"
        "## Vom Wrapper bereitgestellte Datumsangaben (AUTORITATIV)\n"
        f"- HEUTE = {today}\n"
        f"- VOR_7_TAGEN = {cutoff} (harter Cutoff)\n"
        f"- JETZT = {now} Europe/Berlin\n"
    )


def _build_curate_system(prompt_body: str, today: str, cutoff: str, now: str) -> str:
    return (
        f"{prompt_body}\n\n"
        "## Vom Wrapper bereitgestellte Datumsangaben (AUTORITATIV)\n"
        f"- HEUTE = {today}\n"
        f"- VOR_7_TAGEN = {cutoff}\n"
        f"- JETZT = {now} Europe/Berlin\n"
    )


def _extract_text(content_blocks) -> str:
    parts = [
        getattr(b, "text", "") for b in content_blocks
        if getattr(b, "type", None) == "text" and getattr(b, "text", "").strip()
    ]
    return "\n\n".join(parts).strip()


def _clean_markdown(text: str) -> str:
    """Schneidet Prozess-Vorrede ab, normalisiert Leerzeilen, wandelt bloße URLs in Markdown-Links."""
    match = re.search(r"^#{0,3}\s*\**\s*Stand:\s*", text, flags=re.MULTILINE | re.IGNORECASE)
    if match:
        text = text[match.start():]
        text = re.sub(
            r"^#{0,3}\s*\**\s*Stand:\s*", "# Stand: ", text,
            count=1, flags=re.IGNORECASE,
        )
    text = re.sub(r"\n{3,}", "\n\n", text)

    bare_url_re = re.compile(
        r"(?<![\(\[<\"'=])https?://([^\s<>\"']+?)(?=[\s\.,;:!?\)\]]*(?:$|\n))",
        flags=re.MULTILINE,
    )

    def _to_link(m: "re.Match[str]") -> str:
        url = m.group(0)
        host = m.group(1).split("/", 1)[0]
        if host.startswith("www."):
            host = host[4:]
        return f"[{host}]({url})"

    return bare_url_re.sub(_to_link, text).strip()


def _filter_raw_by_date(raw_text: str, cutoff: date, today: date) -> tuple[str, int]:
    """Filtert Sammel-Stufe-Output: behält nur `## TITEL`-Blöcke mit Datum im Fenster.

    Erwartet das Roh-Format aus `collect_prompt.md`: Blöcke beginnen mit
    `## TITEL`, enthalten eine `Datum: YYYY-MM-DD`-Zeile, sind durch `---`
    getrennt.
    """
    future_cutoff = today + timedelta(days=1)
    blocks = re.split(r"\n---\s*\n", raw_text.strip())
    kept: list[str] = []
    removed = 0
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        m = DATE_LABEL_RE.search(block)
        if not m:
            removed += 1
            continue
        try:
            item_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            removed += 1
            continue
        if item_date < cutoff or item_date > future_cutoff:
            logger.info("Sammel-Filter: Item mit Datum %s entfernt.", item_date)
            removed += 1
            continue
        kept.append(block)
    return "\n\n---\n\n".join(kept), removed


def _count_raw_items(raw_text: str) -> int:
    return sum(
        1 for block in re.split(r"\n---\s*\n", raw_text.strip())
        if block.strip() and DATE_LABEL_RE.search(block)
    )


def _filter_by_date(text: str, cutoff: date, today: date) -> tuple[str, int]:
    """Entfernt finale Item-Blöcke außerhalb des 7-Tage-Fensters (Sicherheitsnetz)."""
    future_cutoff = today + timedelta(days=1)

    def is_item_title(line: str) -> bool:
        m = TITLE_LINE_RE.match(line.strip())
        if not m:
            return False
        inner = m.group(1).strip()
        if inner.endswith(":"):
            return False
        return inner.lower().rstrip(":") not in LABEL_BLACKLIST

    def is_section_end(line: str) -> bool:
        s = line.strip()
        if s == "---":
            return True
        m = TITLE_LINE_RE.match(s)
        if m:
            inner = m.group(1).strip()
            if inner.endswith(":"):
                return True
            if inner.lower().rstrip(":") in LABEL_BLACKLIST:
                return True
        if s.startswith("## "):
            heading = s[3:].strip().lower().rstrip(":")
            if heading in LABEL_BLACKLIST:
                return True
        return False

    frames: list[tuple[str, list[str]]] = []
    current_kind, current_lines = "header", []
    for line in text.splitlines():
        if is_item_title(line):
            if current_lines:
                frames.append((current_kind, current_lines))
            current_kind, current_lines = "item", [line]
        elif current_kind == "item" and is_section_end(line):
            frames.append((current_kind, current_lines))
            current_kind, current_lines = "footer", [line]
        else:
            current_lines.append(line)
    if current_lines:
        frames.append((current_kind, current_lines))

    out_frames: list[tuple[str, list[str]]] = []
    removed = 0
    for kind, lines in frames:
        if kind != "item":
            out_frames.append((kind, lines))
            continue
        m = DATE_LABEL_RE.search("\n".join(lines))
        if not m:
            out_frames.append((kind, lines))
            continue
        try:
            item_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            out_frames.append((kind, lines))
            continue
        if item_date < cutoff or item_date > future_cutoff:
            logger.info("Curate-Filter: Item mit Datum %s entfernt (Cutoff %s).", item_date, cutoff)
            removed += 1
            continue
        out_frames.append((kind, lines))

    result_lines: list[str] = []
    for _, fl in out_frames:
        result_lines.extend(fl)
    return "\n".join(result_lines), removed


def _log_usage(stage: str, response: anthropic.types.Message) -> float:
    """Loggt Token-Verbrauch und grobe Kostenschätzung pro Stage. Gibt Kosten zurück."""
    u = response.usage
    cost = _estimate_cost(u.input_tokens, u.output_tokens)
    logger.info(
        "[%s] usage: input=%d, output=%d, ~$%.4f",
        stage, u.input_tokens, u.output_tokens, cost,
    )
    return cost


def _call_collect(
    client: anthropic.Anthropic,
    system_prompt: str,
    user_message: str,
    budget_remaining_usd: float,
) -> tuple[str, float]:
    """Sammel-Stufe mit web_search + web_fetch.

    Bricht ab, sobald der laufende Stage-Verbrauch `budget_remaining_usd`
    überschreitet. Gibt (Roh-Markdown, verbrauchte_kosten_usd) zurück.
    """
    tools = [
        {
            "type": "web_search_20260209", "name": "web_search",
            "max_uses": MAX_WEB_SEARCH_USES, "allowed_callers": ["direct"],
        },
        {
            "type": "web_fetch_20260209", "name": "web_fetch",
            "max_uses": MAX_WEB_FETCH_USES, "allowed_callers": ["direct"],
        },
    ]
    messages = [{"role": "user", "content": user_message}]
    container_id: str | None = None
    total_input = 0
    total_output = 0

    for iteration in range(5):
        kwargs = {
            "model": MODEL, "max_tokens": COLLECT_MAX_TOKENS,
            "system": system_prompt, "tools": tools, "messages": messages,
        }
        if container_id is not None:
            kwargs["container"] = container_id

        with client.messages.stream(**kwargs) as stream:
            response = stream.get_final_message()

        total_input += response.usage.input_tokens
        total_output += response.usage.output_tokens
        running_cost = _estimate_cost(total_input, total_output)
        logger.info(
            "[collect] iter %d: stop=%s, output_tokens=%d, kumuliert ~$%.4f / $%.2f",
            iteration + 1, response.stop_reason, response.usage.output_tokens,
            running_cost, budget_remaining_usd,
        )
        if getattr(response, "container", None) is not None:
            container_id = response.container.id

        if running_cost > budget_remaining_usd:
            raise BudgetExceededError(
                f"Sammel-Stufe: kumulierte Kosten ~${running_cost:.4f} "
                f"überschreiten verfügbares Budget ${budget_remaining_usd:.2f} "
                f"nach Iteration {iteration + 1}."
            )

        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue

        if response.stop_reason == "refusal":
            raise RuntimeError(f"Sammel-Stufe abgelehnt: {getattr(response, 'stop_details', None)}")

        logger.info(
            "[collect] gesamt: input=%d, output=%d, ~$%.4f",
            total_input, total_output, running_cost,
        )
        return _extract_text(response.content), running_cost

    raise RuntimeError("Sammel-Stufe endete nicht in einem terminalen Zustand nach 5 Iterationen.")


def _call_curate(
    client: anthropic.Anthropic,
    system_prompt: str,
    user_message: str,
) -> tuple[str, float]:
    """Kurations-Stufe ohne Tools — billig, weil kein web_fetch."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=CURATE_MAX_TOKENS,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    cost = _log_usage("curate", response)
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Kurations-Stufe abgelehnt: {getattr(response, 'stop_details', None)}")
    return _extract_text(response.content), cost


def run_research() -> int:
    """Zweistufige Recherche → JSONL-DB. Gibt Anzahl neuer Items zurück."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY ist nicht gesetzt.")

    now_dt = _berlin_now()
    today_date = now_dt.date()
    cutoff_date = today_date - timedelta(days=7)
    today_iso, cutoff_iso = today_date.isoformat(), cutoff_date.isoformat()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M")

    db_items = list(load_items().values())
    dedup_context = _build_dedup_context(db_items)

    client = anthropic.Anthropic(api_key=api_key)

    # ----- Stage 1: Sammeln -----
    collect_body = COLLECT_PROMPT_FILE.read_text(encoding="utf-8")
    collect_system = _build_collect_system(collect_body, today_iso, cutoff_iso, now_str)
    collect_user = (
        f"Sammle SAP-News-Roh-Items für {today_iso} (Europe/Berlin). "
        f"Folge dem System-Prompt strikt. Gib NUR die Item-Blöcke aus."
    )
    logger.info("Stage 1: Sammeln (Modell %s, Budget $%.2f)…", MODEL, BUDGET_USD)
    raw_output, collect_cost = _call_collect(
        client, collect_system, collect_user, budget_remaining_usd=BUDGET_USD,
    )
    if not raw_output:
        raise RuntimeError("Sammel-Stufe lieferte leere Antwort.")

    raw_filtered, raw_removed = _filter_raw_by_date(raw_output, cutoff_date, today_date)
    raw_count = _count_raw_items(raw_filtered)
    logger.info(
        "Sammel-Stufe: %d Roh-Items (Datums-Filter entfernte %d).",
        raw_count, raw_removed,
    )
    if raw_count > MAX_RAW_ITEMS:
        blocks = re.split(r"\n---\s*\n", raw_filtered.strip())
        kept = [b for b in blocks if b.strip() and DATE_LABEL_RE.search(b)][:MAX_RAW_ITEMS]
        raw_filtered = "\n\n---\n\n".join(kept)
        logger.warning(
            "Sammel-Stufe lieferte %d Items, kappe auf MAX_RAW_ITEMS=%d.",
            raw_count, MAX_RAW_ITEMS,
        )
        raw_count = MAX_RAW_ITEMS
    if raw_count == 0:
        logger.warning("Keine Roh-Items übrig — überspringe Kuration.")
        return 0

    # ----- Stage 2: Kuratieren -----
    curate_body = CURATE_PROMPT_FILE.read_text(encoding="utf-8")
    curate_system = _build_curate_system(curate_body, today_iso, cutoff_iso, now_str)
    curate_user = (
        f"Kuratiere die folgende Rohliste für {today_iso} (Europe/Berlin). "
        f"Folge dem System-Prompt strikt. Gib NUR das fertige Markdown aus.\n\n"
        f"{dedup_context}\n\n"
        f"ROHLISTE ({raw_count} Items vom Sammel-Agent):\n\n{raw_filtered}"
    )
    budget_remaining = BUDGET_USD - collect_cost
    if budget_remaining <= 0:
        raise BudgetExceededError(
            f"Nach Sammel-Stufe kein Budget mehr übrig (verbraucht ${collect_cost:.4f} / ${BUDGET_USD:.2f})."
        )
    logger.info(
        "Pause %ds vor Stage 2 (Rate-Limit-Recovery)…",
        INTER_STAGE_SLEEP_SECONDS,
    )
    time.sleep(INTER_STAGE_SLEEP_SECONDS)

    logger.info(
        "Stage 2: Kuratieren (Modell %s, ohne Tools, Restbudget $%.4f)…",
        MODEL, budget_remaining,
    )
    try:
        curated_raw, curate_cost = _call_curate(client, curate_system, curate_user)
    except anthropic.RateLimitError as exc:
        logger.warning("Stage 2 trotz Pause rate-limited, warte 120s und versuche es nochmal: %s", exc)
        time.sleep(120)
        curated_raw, curate_cost = _call_curate(client, curate_system, curate_user)
    except anthropic.APIError as exc:
        logger.error("Kurations-Stufe API-Fehler: %s", exc)
        raise
    total_cost = collect_cost + curate_cost
    logger.info(
        "Pipeline-Kosten: collect ~$%.4f + curate ~$%.4f = ~$%.4f / Budget $%.2f",
        collect_cost, curate_cost, total_cost, BUDGET_USD,
    )
    if total_cost > BUDGET_USD:
        logger.warning(
            "Gesamtkosten ~$%.4f überschreiten Budget $%.2f (Kuration lief trotzdem durch).",
            total_cost, BUDGET_USD,
        )

    markdown = _clean_markdown(curated_raw)
    if not markdown:
        raise RuntimeError("Kurations-Stufe lieferte leere Antwort.")

    markdown, removed = _filter_by_date(markdown, cutoff_date, today_date)
    if removed:
        logger.warning("Curate-Datums-Filter hat %d Item(s) entfernt.", removed)

    # ----- Persist -----
    new_items = parse_items(markdown, run_date=today_iso)
    db_map = {i["url"]: i for i in db_items}
    added, updated = upsert_items(db_map, new_items)
    save_items(db_map.values())
    logger.info(
        "DB-Update: %d kuratierte Items, +%d neu, %d aktualisiert, gesamt %d.",
        len(new_items), added, updated, len(db_map),
    )
    return added


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        run_research()
    except Exception as exc:
        logger.exception("Recherche fehlgeschlagen: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
