"""Ruft die Anthropic API mit web_search + web_fetch auf und speichert das Ergebnis."""
from __future__ import annotations

import logging
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
PROMPT_FILE = ROOT / "prompts" / "research_prompt.md"
MARKDOWN_DIR = ROOT / "data" / "markdown"

MODEL = "claude-haiku-4-5"
MAX_TOKENS = 8000
MAX_TOOL_USES = 12


def _berlin_now() -> datetime:
    return datetime.now(ZoneInfo("Europe/Berlin"))


def _find_previous_markdown(today_iso: str) -> tuple[str, str] | None:
    """Sucht Vortagesdatei oder die zuletzt vorhandene Datei. Gibt (Dateiname, Inhalt) zurück."""
    if not MARKDOWN_DIR.exists():
        return None
    candidates = sorted(
        [p for p in MARKDOWN_DIR.glob("sap_news_*.md") if p.stem != f"sap_news_{today_iso}"],
        reverse=True,
    )
    if not candidates:
        return None
    latest = candidates[0]
    try:
        return latest.name, latest.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("Konnte Vergleichsdatei nicht lesen: %s", exc)
        return None


def _build_system_prompt(prompt_body: str, today: str, cutoff: str, now: str) -> str:
    """Hängt verlässliche Datumsangaben an den Recherche-Prompt an."""
    return (
        f"{prompt_body}\n\n"
        "## Vom Wrapper bereitgestellte Datumsangaben (AUTORITATIV)\n"
        f"- HEUTE = {today}\n"
        f"- VOR_7_TAGEN = {cutoff} (= harter Cutoff: Artikel älter als dieses Datum AUSSCHLIESSEN)\n"
        f"- JETZT = {now} Europe/Berlin\n"
        "Verwende diese Werte für Schritt 0 anstelle eigener Datumsermittlung.\n"
        "Hinweis: Ein nachgelagerter Wrapper filtert technisch noch einmal nach diesem "
        "Cutoff — gib also IMMER `Datum: YYYY-MM-DD` pro News-Item aus, damit der "
        "Filter die Items eindeutig zuordnen kann."
    )


def _extract_text(content_blocks) -> str:
    parts: list[str] = []
    for block in content_blocks:
        if getattr(block, "type", None) == "text":
            text = getattr(block, "text", "") or ""
            if text.strip():
                parts.append(text)
    return "\n\n".join(parts).strip()


def _clean_markdown(text: str) -> str:
    """Schneidet Prozess-Vorrede ab und normalisiert Leerzeilen.

    Falls das Modell trotz Prompt-Regel Schritt-Geplauder ausgibt, behalten wir
    nur den Teil ab `# Stand:` / `Stand:` — also den eigentlichen Report.
    """
    import re

    # Suche den Beginn des eigentlichen Reports.
    match = re.search(r"^#{0,3}\s*\**\s*Stand:\s*", text, flags=re.MULTILINE | re.IGNORECASE)
    if match:
        text = text[match.start():]
        # Sicherstellen, dass der Bericht mit "# Stand:" beginnt (normalisiert).
        text = re.sub(
            r"^#{0,3}\s*\**\s*Stand:\s*",
            "# Stand: ",
            text,
            count=1,
            flags=re.IGNORECASE,
        )

    # Mehr als zwei aufeinanderfolgende Leerzeilen auf zwei reduzieren.
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Bloße URLs in Markdown-Links umwandeln — Anzeige: Domain.
    # Greift NUR auf URLs, die NICHT bereits Teil eines Markdown-Links sind.
    bare_url_re = re.compile(
        r"(?<![\(\[<\"'=])https?://([^\s<>\"']+?)(?=[\s\.,;:!?\)\]]*(?:$|\n))",
        flags=re.MULTILINE,
    )

    def _to_link(match: "re.Match[str]") -> str:
        url = match.group(0)
        # Domain extrahieren (host + ggf. erstes Pfadsegment unterdrücken).
        host = match.group(1).split("/", 1)[0]
        if host.startswith("www."):
            host = host[4:]
        return f"[{host}]({url})"

    text = bare_url_re.sub(_to_link, text)
    return text.strip()


def _filter_by_date(text: str, cutoff: date, today: date) -> tuple[str, int]:
    """Entfernt News-Items, deren Publikationsdatum vor `cutoff` liegt.

    Nutzt den strukturierten Parser aus `parse.py`. Strategie:
    1. Parse alle Items aus dem Markdown.
    2. Erkenne pro Item dessen Position im Text anhand des Titels.
    3. Schneide Items raus, deren Datum außerhalb des Zeitfensters liegt.
    4. Header / Statistik bleiben unangetastet.

    Items in der Zukunft (> today + 1 Tag) werden ebenfalls verworfen
    (typischerweise halluzinierte Daten).
    """
    import re

    from parse import (
        LABEL_BLACKLIST,
        TITLE_LINE_RE,
        DATE_LABEL_RE,
    )

    future_cutoff = today + timedelta(days=1)
    lines = text.splitlines()

    # Zerlege das Markdown in "Frames": Header / Item / Item / ... / Footer
    # Ein Item beginnt bei einem **Titel**-Header (nicht Label) und endet
    # vor dem nächsten Titel ODER vor einer Label-Sektion ODER bei `---`.
    def line_is_item_title(line: str) -> bool:
        m = TITLE_LINE_RE.match(line.strip())
        if not m:
            return False
        inner = m.group(1).strip()
        if inner.endswith(":"):
            return False
        if inner.lower().rstrip(":") in LABEL_BLACKLIST:
            return False
        return True

    def line_is_section_end(line: str) -> bool:
        stripped = line.strip()
        if stripped == "---":
            return True
        m = TITLE_LINE_RE.match(stripped)
        if m:
            inner = m.group(1).strip()
            if inner.endswith(":"):
                return True
            if inner.lower().rstrip(":") in LABEL_BLACKLIST:
                return True
        if stripped.startswith("## "):
            heading = stripped[3:].strip().lower().rstrip(":")
            if heading in LABEL_BLACKLIST:
                return True
        return False

    # Frames sammeln: jeder Frame ist (kind, lines) mit kind in {"header","item","footer","sep"}
    frames: list[tuple[str, list[str]]] = []
    current_kind = "header"
    current_lines: list[str] = []

    for line in lines:
        if line_is_item_title(line):
            # Vorigen Frame abschließen
            if current_lines:
                frames.append((current_kind, current_lines))
            current_kind = "item"
            current_lines = [line]
        elif current_kind == "item" and line_is_section_end(line):
            # Item-Sequenz endet hier
            frames.append((current_kind, current_lines))
            current_lines = [line]
            current_kind = "footer"
        else:
            current_lines.append(line)

    if current_lines:
        frames.append((current_kind, current_lines))

    # Filter pro Item
    removed = 0
    out_frames: list[tuple[str, list[str]]] = []
    for kind, frame_lines in frames:
        if kind != "item":
            out_frames.append((kind, frame_lines))
            continue
        chunk_text = "\n".join(frame_lines)
        m = DATE_LABEL_RE.search(chunk_text)
        if not m:
            out_frames.append((kind, frame_lines))
            continue
        try:
            item_date = date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            out_frames.append((kind, frame_lines))
            continue
        if item_date < cutoff:
            logger.info("Filter: Item mit Datum %s < cutoff %s entfernt.", item_date, cutoff)
            removed += 1
            continue
        if item_date > future_cutoff:
            logger.info("Filter: Item mit Zukunfts-Datum %s entfernt.", item_date)
            removed += 1
            continue
        out_frames.append((kind, frame_lines))

    result_lines: list[str] = []
    for _, fl in out_frames:
        result_lines.extend(fl)
    return "\n".join(result_lines), removed


def run_research() -> Path:
    """Führt die Recherche aus und speichert die Markdown-Datei. Gibt den Pfad zurück."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY ist nicht gesetzt.")

    now_dt = _berlin_now()
    today_date = now_dt.date()
    cutoff_date = today_date - timedelta(days=7)
    today_iso = today_date.strftime("%Y-%m-%d")
    cutoff_iso = cutoff_date.strftime("%Y-%m-%d")
    now_str = now_dt.strftime("%Y-%m-%d %H:%M")

    prompt_body = PROMPT_FILE.read_text(encoding="utf-8")
    system_prompt = _build_system_prompt(prompt_body, today_iso, cutoff_iso, now_str)

    # Vergleichsbasis als Kontext anhängen.
    prev = _find_previous_markdown(today_iso)
    user_lines = [
        f"Bitte führe die tägliche SAP-News-Recherche für {today_iso} (Europe/Berlin) aus.",
        "Folge dem System-Prompt strikt. Gib am Ende NUR das fertige Markdown aus.",
    ]
    if prev:
        prev_name, prev_content = prev
        user_lines.append(
            f"\n--- VERGLEICHSBASIS: {prev_name} (Inhalt zur Deduplizierung, Datum ignorieren) ---\n"
            f"{prev_content}\n--- ENDE VERGLEICHSBASIS ---"
        )
    else:
        user_lines.append("\nVERGLEICHSBASIS: keine Vortagesdatei vorhanden.")

    user_message = "\n".join(user_lines)

    # allowed_callers=["direct"] schaltet Dynamic Filtering ab — nötig für Haiku 4.5,
    # spart Tokens und macht die container_id-Logik überflüssig.
    tools = [
        {
            "type": "web_search_20260209",
            "name": "web_search",
            "max_uses": MAX_TOOL_USES,
            "allowed_callers": ["direct"],
        },
        {
            "type": "web_fetch_20260209",
            "name": "web_fetch",
            "max_uses": MAX_TOOL_USES,
            "allowed_callers": ["direct"],
        },
    ]

    client = anthropic.Anthropic(api_key=api_key)

    messages = [{"role": "user", "content": user_message}]

    logger.info("Starte Recherche mit Modell %s ...", MODEL)

    # Agentic loop: pause_turn behandeln, falls server-side Tools die interne Iteration ausschöpfen.
    # web_search_20260209 / web_fetch_20260209 nutzen intern Code Execution für Dynamic Filtering;
    # bei pause_turn muss die container_id aus der Antwort im Folge-Request mitgegeben werden.
    final_response = None
    container_id: str | None = None
    for iteration in range(5):
        request_kwargs = {
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
            "system": system_prompt,
            "tools": tools,
            "messages": messages,
        }
        if container_id is not None:
            request_kwargs["container"] = container_id

        try:
            with client.messages.stream(**request_kwargs) as stream:
                response = stream.get_final_message()
        except anthropic.APIError as exc:
            logger.error("Anthropic API-Fehler: %s", exc)
            raise

        logger.info(
            "Iteration %d abgeschlossen (stop_reason=%s, output_tokens=%d)",
            iteration + 1,
            response.stop_reason,
            response.usage.output_tokens,
        )

        # Container-ID für mögliche Folge-Iterationen merken.
        if getattr(response, "container", None) is not None:
            container_id = response.container.id

        if response.stop_reason == "pause_turn":
            # Server pausiert — Antwort anhängen und mit container_id nochmal aufrufen.
            messages.append({"role": "assistant", "content": response.content})
            continue

        final_response = response
        break

    if final_response is None:
        raise RuntimeError("Recherche endete nicht in einem terminalen Zustand.")

    if final_response.stop_reason == "refusal":
        raise RuntimeError(
            f"Modell hat abgelehnt: {getattr(final_response, 'stop_details', None)}"
        )

    markdown = _extract_text(final_response.content)
    if not markdown:
        raise RuntimeError("Antwort enthält keinen Text — Datei wird NICHT geschrieben.")
    markdown = _clean_markdown(markdown)
    if not markdown:
        raise RuntimeError("Antwort enthält nach Cleanup keinen Text — Datei wird NICHT geschrieben.")

    markdown, removed_count = _filter_by_date(markdown, cutoff_date, today_date)
    if removed_count:
        logger.warning(
            "Post-Filter hat %d Item(s) außerhalb des 7-Tage-Fensters entfernt.",
            removed_count,
        )

    MARKDOWN_DIR.mkdir(parents=True, exist_ok=True)
    out_path = MARKDOWN_DIR / f"sap_news_{today_iso}.md"
    out_path.write_text(markdown, encoding="utf-8")
    logger.info("Recherche gespeichert: %s (%d Zeichen)", out_path, len(markdown))
    return out_path


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
