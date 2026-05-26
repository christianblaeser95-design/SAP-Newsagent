"""Wöchentlicher Recherche-Lauf: Anthropic API → strukturierte Items → JSONL-DB."""
from __future__ import annotations

import logging
import os
import re
import sys
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
PROMPT_FILE = ROOT / "prompts" / "research_prompt.md"

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 8000
# 12 erlaubt 16 Suchen ist nicht möglich — Anthropic teilt max_uses pro Tool.
# 12 web_search + 12 web_fetch reicht für die 16 Pflicht-Suchen aus dem Prompt
# (das Modell darf priorisieren). Budget pro Lauf: ~$0.25 = ~$1/Monat.
MAX_TOOL_USES = 12
# Maximale Anzahl Items, die als Dedup-Basis ans Modell gehen (neueste zuerst).
DEDUP_CONTEXT_LIMIT = 40


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


def _build_system_prompt(prompt_body: str, today: str, cutoff: str, now: str) -> str:
    return (
        f"{prompt_body}\n\n"
        "## Vom Wrapper bereitgestellte Datumsangaben (AUTORITATIV)\n"
        f"- HEUTE = {today}\n"
        f"- VOR_7_TAGEN = {cutoff} (harter Cutoff — Artikel davor AUSSCHLIESSEN)\n"
        f"- JETZT = {now} Europe/Berlin\n\n"
        "Pro Item IMMER `Datum: YYYY-MM-DD` ausgeben — ein nachgelagerter Filter "
        "wirft alles raus, was vor VOR_7_TAGEN liegt."
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


def _filter_by_date(text: str, cutoff: date, today: date) -> tuple[str, int]:
    """Entfernt Item-Blöcke außerhalb des 7-Tage-Fensters.

    Splittet anhand der Titel-Pattern und schließt Items aus, deren `Datum:`
    vor `cutoff` oder mehr als 1 Tag in der Zukunft liegt.
    """
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
            logger.info("Filter: Item mit Datum %s entfernt (Cutoff %s).", item_date, cutoff)
            removed += 1
            continue
        out_frames.append((kind, lines))

    result_lines: list[str] = []
    for _, fl in out_frames:
        result_lines.extend(fl)
    return "\n".join(result_lines), removed


def _call_api(client: anthropic.Anthropic, system_prompt: str, user_message: str) -> anthropic.types.Message:
    """API-Aufruf mit pause_turn-Handling für interne Code-Execution-Iteration."""
    tools = [
        {
            "type": "web_search_20260209", "name": "web_search",
            "max_uses": MAX_TOOL_USES, "allowed_callers": ["direct"],
        },
        {
            "type": "web_fetch_20260209", "name": "web_fetch",
            "max_uses": MAX_TOOL_USES, "allowed_callers": ["direct"],
        },
    ]
    messages = [{"role": "user", "content": user_message}]
    container_id: str | None = None

    for iteration in range(5):
        kwargs = {
            "model": MODEL, "max_tokens": MAX_TOKENS,
            "system": system_prompt, "tools": tools, "messages": messages,
        }
        if container_id is not None:
            kwargs["container"] = container_id

        with client.messages.stream(**kwargs) as stream:
            response = stream.get_final_message()

        logger.info(
            "API-Iteration %d: stop=%s, output_tokens=%d",
            iteration + 1, response.stop_reason, response.usage.output_tokens,
        )
        if getattr(response, "container", None) is not None:
            container_id = response.container.id

        if response.stop_reason == "pause_turn":
            messages.append({"role": "assistant", "content": response.content})
            continue
        return response

    raise RuntimeError("API endete nicht in einem terminalen Zustand nach 5 Iterationen.")


def run_research() -> int:
    """Führt die Recherche aus, parsed Items und ergänzt die JSONL-DB. Gibt Anzahl neuer Items zurück."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY ist nicht gesetzt.")

    now_dt = _berlin_now()
    today_date = now_dt.date()
    cutoff_date = today_date - timedelta(days=7)
    today_iso, cutoff_iso = today_date.isoformat(), cutoff_date.isoformat()
    now_str = now_dt.strftime("%Y-%m-%d %H:%M")

    # Dedup-Kontext aus JSONL — umfasst alle bisherigen Items.
    db_items = list(load_items().values())
    dedup_context = _build_dedup_context(db_items)

    prompt_body = PROMPT_FILE.read_text(encoding="utf-8")
    system_prompt = _build_system_prompt(prompt_body, today_iso, cutoff_iso, now_str)
    user_message = (
        f"Bitte führe die wöchentliche SAP-News-Recherche für {today_iso} (Europe/Berlin) aus.\n"
        f"Folge dem System-Prompt strikt. Gib am Ende NUR das fertige Markdown aus.\n\n"
        f"{dedup_context}"
    )

    logger.info("Starte Recherche (Modell %s, %d Items in DB)…", MODEL, len(db_items))
    client = anthropic.Anthropic(api_key=api_key)
    try:
        response = _call_api(client, system_prompt, user_message)
    except anthropic.APIError as exc:
        logger.error("Anthropic API-Fehler: %s", exc)
        raise

    if response.stop_reason == "refusal":
        raise RuntimeError(f"Modell hat abgelehnt: {getattr(response, 'stop_details', None)}")

    markdown = _clean_markdown(_extract_text(response.content))
    if not markdown:
        raise RuntimeError("Leere Antwort — kein Update der DB.")

    markdown, removed = _filter_by_date(markdown, cutoff_date, today_date)
    if removed:
        logger.warning("Datums-Filter hat %d Item(s) entfernt.", removed)

    # Parse + Upsert in JSONL.
    new_items = parse_items(markdown, run_date=today_iso)
    db_map = {i["url"]: i for i in db_items}
    added, updated = upsert_items(db_map, new_items)
    save_items(db_map.values())
    logger.info(
        "DB-Update: %d Items geparst, +%d neu, %d aktualisiert, gesamt %d.",
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
