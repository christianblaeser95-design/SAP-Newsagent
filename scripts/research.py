"""Ruft die Anthropic API mit web_search + web_fetch auf und speichert das Ergebnis."""
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
PROMPT_FILE = ROOT / "prompts" / "research_prompt.md"
MARKDOWN_DIR = ROOT / "data" / "markdown"

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 16000
MAX_TOOL_USES = 40


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


def _build_system_prompt(prompt_body: str, today: str, yesterday: str, now: str) -> str:
    """Hängt verlässliche Datumsangaben an den Recherche-Prompt an."""
    return (
        f"{prompt_body}\n\n"
        "## Vom Wrapper bereitgestellte Datumsangaben (AUTORITATIV)\n"
        f"- HEUTE = {today}\n"
        f"- GESTERN = {yesterday}\n"
        f"- JETZT = {now} Europe/Berlin\n"
        "Verwende diese Werte für Schritt 0 anstelle eigener Datumsermittlung."
    )


def _extract_text(content_blocks) -> str:
    parts: list[str] = []
    for block in content_blocks:
        if getattr(block, "type", None) == "text":
            text = getattr(block, "text", "") or ""
            if text.strip():
                parts.append(text)
    return "\n\n".join(parts).strip()


def run_research() -> Path:
    """Führt die Recherche aus und speichert die Markdown-Datei. Gibt den Pfad zurück."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY ist nicht gesetzt.")

    now_dt = _berlin_now()
    today_iso = now_dt.strftime("%Y-%m-%d")
    yesterday_iso = (now_dt - timedelta(days=1)).strftime("%Y-%m-%d")
    now_str = now_dt.strftime("%Y-%m-%d %H:%M")

    prompt_body = PROMPT_FILE.read_text(encoding="utf-8")
    system_prompt = _build_system_prompt(prompt_body, today_iso, yesterday_iso, now_str)

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

    tools = [
        {"type": "web_search_20260209", "name": "web_search", "max_uses": MAX_TOOL_USES},
        {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": MAX_TOOL_USES},
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
