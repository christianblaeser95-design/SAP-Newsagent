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
WEEKDAYS_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

DATE_RE = re.compile(r"^sap_news_(\d{4}-\d{2}-\d{2})\.md$")
INDEX_LIMIT = 30
SITE_TITLE = "SAP Newsagent"
INTRO_HEADLINE = "Die wichtigsten SAP-News der Woche."
INTRO_SUBLINE = (
    "Ein KI-Agent recherchiert jeden Montagmorgen automatisch das Web, validiert die "
    "Quellen und fasst die Meldungen der letzten 7 Tage für SAP-Beraterinnen "
    "und SAP-Berater zusammen."
)
HOW_STEPS = [
    (
        "Montags um 8 Uhr",
        "Eine neue Wochenausgabe wird automatisch erstellt — kein manuelles Anstoßen nötig.",
    ),
    (
        "Web-Recherche & Validierung",
        "Acht thematische Suchen, jede Quelle vor Aufnahme auf Aktualität und Inhalt geprüft.",
    ),
    (
        "Dedupliziert & gefiltert",
        "Nur Meldungen mit konkretem News-Wert (Releases, Produkte, Zahlen, Partnerschaften).",
    ),
]
USAGE_NOTE = (
    "Klicke auf eine Ausgabe, um die Meldungen der jeweiligen Woche zu lesen. "
    "Innerhalb einer Ausgabe kannst du per Pfeil-Links zur Vor- oder Folgewoche wechseln."
)


def _format_date_de(date_iso: str, *, with_weekday: bool = False) -> str:
    dt = datetime.strptime(date_iso, "%Y-%m-%d")
    base = f"{dt.day}. {MONTHS_DE[dt.month]} {dt.year}"
    if with_weekday:
        return f"{WEEKDAYS_DE[dt.weekday()]}, {base}"
    return base


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


def _count_items(markdown_text: str) -> int:
    """Zählt die News-Items im Markdown (basiert auf **Titel**-Zeilen).

    Schließt Label-Zeilen aus, die mit ':' enden (z.B. **Statistik:**) sowie
    bekannte Metadaten-Labels.
    """
    # Bekannte Metadaten-Labels, die optisch wie News-Titel aussehen können.
    skip_labels = {
        "statistik", "zeitfenster", "vergleichsbasis", "stand",
        "quelle", "datum", "relevanz für beratung", "relevanz",
    }
    count = 0
    for line in markdown_text.splitlines():
        stripped = line.strip()
        m = re.match(r"^[-*]?\s*\*\*(.+?)\*\*\s*:?\s*$", stripped)
        if m:
            label = m.group(1).strip().rstrip(":").lower()
            # Bold-Zeile, die mit ':' endet → fast immer ein Label, kein Titel.
            if stripped.rstrip().endswith(":"):
                continue
            if label in skip_labels:
                continue
            count += 1
        elif stripped.startswith("## ") and len(stripped) > 3:
            heading = stripped[3:].strip().lower().rstrip(":")
            if heading in skip_labels:
                continue
            count += 1
    return count


def _build_nav(date_iso: str, all_dates: list[str]) -> str:
    idx = all_dates.index(date_iso)
    prev_date = all_dates[idx - 1] if idx > 0 else None
    next_date = all_dates[idx + 1] if idx < len(all_dates) - 1 else None

    parts: list[str] = []
    if prev_date:
        parts.append(f'<a class="nav-link" href="{prev_date}.html">← {_format_date_de(prev_date)}</a>')
    else:
        parts.append('<span class="nav-link disabled">←</span>')
    parts.append('<a class="nav-link nav-home" href="../index.html">Alle Ausgaben</a>')
    if next_date:
        parts.append(f'<a class="nav-link" href="{next_date}.html">{_format_date_de(next_date)} →</a>')
    else:
        parts.append('<span class="nav-link disabled">→</span>')
    return "\n".join(parts)


def _site_header(home_href: str) -> str:
    return f"""<header class="site-header">
  <a class="site-brand" href="{home_href}" title="Zur Startseite">
    <span class="brand-mark">SAP</span>
    <span class="brand-name">Newsagent</span>
  </a>
  <p class="site-tagline">Wöchentliche KI-kuratierte SAP-News</p>
</header>"""


def _site_footer() -> str:
    return """<footer class="site-footer">
  <p>Automatisch erstellt mit <a href="https://www.anthropic.com/claude" rel="noopener">Anthropic Claude</a>.
  Quellen werden vor der Aufnahme validiert; trotzdem ohne Gewähr.</p>
</footer>"""


def _render_day_page(date_iso: str, all_dates: list[str], is_latest: bool) -> Path:
    md_path = MARKDOWN_DIR / f"sap_news_{date_iso}.md"
    text = md_path.read_text(encoding="utf-8")
    body_html = md.markdown(text, extensions=["extra", "sane_lists"])
    nav_html = _build_nav(date_iso, all_dates)
    date_pretty = _format_date_de(date_iso, with_weekday=True)
    item_count = _count_items(text)
    latest_badge = '<span class="badge">Aktuelle Ausgabe</span>' if is_latest else ""

    page = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(date_pretty)} – {SITE_TITLE}</title>
<meta name="description" content="SAP-News vom {html.escape(date_pretty)} — automatisch recherchiert und zusammengefasst.">
<link rel="stylesheet" href="../style.css">
</head>
<body>
{_site_header("../index.html")}
<main class="day-page">
  <nav class="day-nav top">{nav_html}</nav>
  <article class="edition">
    <header class="edition-header">
      {latest_badge}
      <p class="edition-kicker">SAP-News der letzten 7 Tage</p>
      <h1 class="edition-date">{html.escape(date_pretty)}</h1>
      <p class="edition-meta">{item_count} {"Meldung" if item_count == 1 else "Meldungen"}</p>
    </header>
    <div class="edition-body">
{body_html}
    </div>
  </article>
  <nav class="day-nav bottom">{nav_html}</nav>
</main>
{_site_footer()}
</body>
</html>
"""

    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    out_path = ARCHIVE_DIR / f"{date_iso}.html"
    out_path.write_text(page, encoding="utf-8")
    return out_path


def _render_index(all_dates: list[str]) -> Path:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    recent = list(reversed(all_dates))[:INDEX_LIMIT]

    # --- Featured edition (oben groß) ---
    if recent:
        latest_date = recent[0]
        latest_md = MARKDOWN_DIR / f"sap_news_{latest_date}.md"
        try:
            latest_text = latest_md.read_text(encoding="utf-8")
        except OSError:
            latest_text = ""
        latest_teaser = _extract_first_title(latest_text)
        latest_count = _count_items(latest_text)
        latest_pretty = _format_date_de(latest_date, with_weekday=True)
        teaser_html = (
            f'<p class="featured-teaser">Top-Meldung: „{html.escape(latest_teaser)}“</p>'
            if latest_teaser else ""
        )
        meldung_label = "Meldung" if latest_count == 1 else "Meldungen"
        featured_html = f"""<section class="featured" aria-labelledby="featured-heading">
  <div class="featured-tag">Aktuelle Ausgabe</div>
  <h2 id="featured-heading" class="featured-date">{html.escape(latest_pretty)}</h2>
  <p class="featured-meta">{latest_count} {meldung_label} · automatisch erstellt</p>
  {teaser_html}
  <a class="featured-cta" href="archive/{latest_date}.html">Ausgabe lesen →</a>
</section>"""
        archive_dates = recent[1:]
    else:
        featured_html = """<section class="featured featured-empty">
  <div class="featured-tag">Noch keine Ausgabe</div>
  <h2 class="featured-date">Die erste Recherche läuft …</h2>
  <p class="featured-teaser">Sobald der tägliche Workflow gelaufen ist, erscheint hier die aktuelle Ausgabe.</p>
</section>"""
        archive_dates = []

    # --- "So funktioniert's" — 3 Spalten ---
    steps_html = "\n".join(
        f"""<li class="how-step">
  <span class="how-num">{i + 1}</span>
  <div>
    <h3 class="how-title">{html.escape(title)}</h3>
    <p class="how-desc">{html.escape(desc)}</p>
  </div>
</li>"""
        for i, (title, desc) in enumerate(HOW_STEPS)
    )

    # --- Archivliste ---
    archive_items: list[str] = []
    for date_iso in archive_dates:
        md_path = MARKDOWN_DIR / f"sap_news_{date_iso}.md"
        try:
            text = md_path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        teaser = _extract_first_title(text)
        count = _count_items(text)
        teaser_html = f'<p class="archive-teaser">{html.escape(teaser)}</p>' if teaser else ""
        count_html = (
            f'<span class="archive-count">{count} {"Meldung" if count == 1 else "Meldungen"}</span>'
            if count else ""
        )
        archive_items.append(
            f"""<li class="archive-item">
  <a class="archive-link" href="archive/{date_iso}.html">
    <div class="archive-head">
      <span class="archive-date">{_format_date_de(date_iso, with_weekday=True)}</span>
      {count_html}
    </div>
    {teaser_html}
  </a>
</li>"""
        )

    archive_html = (
        '<ul class="archive-list">\n' + "\n".join(archive_items) + "\n</ul>"
        if archive_items
        else '<p class="archive-empty">Noch keine älteren Ausgaben vorhanden.</p>'
    )

    page = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{SITE_TITLE} – Tägliche KI-kuratierte SAP-News</title>
<meta name="description" content="{html.escape(INTRO_SUBLINE)}">
<link rel="stylesheet" href="style.css">
</head>
<body>
{_site_header("index.html")}
<main class="index-page">

  <section class="intro">
    <p class="intro-eyebrow">Für SAP-Beraterinnen und SAP-Berater</p>
    <h1 class="intro-headline">{html.escape(INTRO_HEADLINE)}</h1>
    <p class="intro-subline">{html.escape(INTRO_SUBLINE)}</p>
  </section>

  {featured_html}

  <section class="how" aria-labelledby="how-heading">
    <h2 id="how-heading" class="section-title">So funktioniert's</h2>
    <ol class="how-list">
{steps_html}
    </ol>
    <p class="how-usage">{html.escape(USAGE_NOTE)}</p>
  </section>

  <section class="archive" aria-labelledby="archive-heading">
    <h2 id="archive-heading" class="section-title">Frühere Ausgaben</h2>
    {archive_html}
  </section>

</main>
{_site_footer()}
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
    latest = dates[-1] if dates else None
    for date_iso in dates:
        path = _render_day_page(date_iso, dates, is_latest=(date_iso == latest))
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
