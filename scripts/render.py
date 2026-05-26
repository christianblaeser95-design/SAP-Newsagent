"""Konvertiert Markdown-Dateien in HTML-Tagesseiten und aktualisiert den Index."""
from __future__ import annotations

import html
import logging
import re
from datetime import datetime
from pathlib import Path

import markdown as md

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
MARKDOWN_DIR = ROOT / "data" / "markdown"
DOCS_DIR = ROOT / "docs"
ARCHIVE_DIR = DOCS_DIR / "archive"

MONTHS_DE = {
    1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni",
    7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember",
}

DATE_RE = re.compile(r"^sap_news_(\d{4}-\d{2}-\d{2})\.md$")
INDEX_LIMIT = 30


def _format_date_de(date_iso: str) -> str:
    dt = datetime.strptime(date_iso, "%Y-%m-%d")
    return f"{dt.day}. {MONTHS_DE[dt.month]} {dt.year}"


def _collect_dates() -> list[str]:
    if not MARKDOWN_DIR.exists():
        return []
    dates: list[str] = []
    for path in MARKDOWN_DIR.glob("sap_news_*.md"):
        match = DATE_RE.match(path.name)
        if match:
            dates.append(match.group(1))
    return sorted(dates)


def _extract_first_title(markdown_text: str) -> str:
    """Extrahiert den ersten **Titel** aus dem Markdown als Teaser."""
    for line in markdown_text.splitlines():
        stripped = line.strip()
        m = re.match(r"^[-*]?\s*\*\*(.+?)\*\*\s*$", stripped)
        if m:
            return m.group(1).strip()
        if stripped.startswith("## ") and len(stripped) > 3:
            return stripped[3:].strip()
    return ""


def _page_template(title: str, body_html: str, nav_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} – SAP Newsagent</title>
<link rel="stylesheet" href="../style.css">
</head>
<body>
<main>
<header class="page-nav">{nav_html}</header>
<h1>{html.escape(title)}</h1>
<article class="news">
{body_html}
</article>
<footer class="page-nav">{nav_html}</footer>
</main>
</body>
</html>
"""


def _build_nav(date_iso: str, all_dates: list[str]) -> str:
    idx = all_dates.index(date_iso)
    prev_date = all_dates[idx - 1] if idx > 0 else None
    next_date = all_dates[idx + 1] if idx < len(all_dates) - 1 else None

    parts: list[str] = []
    if prev_date:
        parts.append(f'<a href="{prev_date}.html">← {_format_date_de(prev_date)}</a>')
    else:
        parts.append('<span class="disabled">←</span>')
    parts.append('<a href="../index.html">Übersicht</a>')
    if next_date:
        parts.append(f'<a href="{next_date}.html">{_format_date_de(next_date)} →</a>')
    else:
        parts.append('<span class="disabled">→</span>')
    return " · ".join(parts)


def _render_day_page(date_iso: str, all_dates: list[str]) -> Path:
    md_path = MARKDOWN_DIR / f"sap_news_{date_iso}.md"
    text = md_path.read_text(encoding="utf-8")
    body_html = md.markdown(text, extensions=["extra", "sane_lists"])
    nav_html = _build_nav(date_iso, all_dates)
    page = _page_template(_format_date_de(date_iso), body_html, nav_html)

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ARCHIVE_DIR / f"{date_iso}.html"
    out_path.write_text(page, encoding="utf-8")
    return out_path


def _render_index(all_dates: list[str]) -> Path:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    recent = list(reversed(all_dates))[:INDEX_LIMIT]

    items: list[str] = []
    for date_iso in recent:
        md_path = MARKDOWN_DIR / f"sap_news_{date_iso}.md"
        try:
            teaser = _extract_first_title(md_path.read_text(encoding="utf-8"))
        except OSError:
            teaser = ""
        teaser_html = f' <span class="teaser">– {html.escape(teaser)}</span>' if teaser else ""
        items.append(
            f'<li><a href="archive/{date_iso}.html">{_format_date_de(date_iso)}</a>{teaser_html}</li>'
        )

    items_html = "\n".join(items) if items else "<li>Noch keine Einträge vorhanden.</li>"

    page = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SAP Newsagent</title>
<link rel="stylesheet" href="style.css">
</head>
<body>
<main>
<h1>SAP Newsagent</h1>
<p class="intro">Tägliche, automatisierte SAP-News-Übersicht. Die letzten {INDEX_LIMIT} Tage:</p>
<ul class="archive-list">
{items_html}
</ul>
</main>
</body>
</html>
"""
    out_path = DOCS_DIR / "index.html"
    out_path.write_text(page, encoding="utf-8")
    return out_path


def render_all() -> None:
    dates = _collect_dates()
    if not dates:
        logger.warning("Keine Markdown-Dateien gefunden — Index wird trotzdem erzeugt.")
    for date_iso in dates:
        path = _render_day_page(date_iso, dates)
        logger.info("Tagesseite gerendert: %s", path.relative_to(ROOT))
    index_path = _render_index(dates)
    logger.info("Index aktualisiert: %s", index_path.relative_to(ROOT))


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        render_all()
    except Exception as exc:
        logging.exception("Rendering fehlgeschlagen: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
