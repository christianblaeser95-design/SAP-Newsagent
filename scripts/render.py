"""Rendert HTML-Seiten aus der JSONL-Datenbank.

Architektur:
- `data/news.jsonl` ist die Quelle der Wahrheit für alle Items.
- Jede `data/markdown/sap_news_YYYY-MM-DD.md` markiert ein "Edition-Datum"
  (ein Lauf des Recherche-Workflows).
- Pro Edition zeigt die HTML-Seite Items mit `published_date` in den 7 Tagen
  vor dem Edition-Datum.
- Existieren noch keine Markdown-Dateien, gibt es nur die "Heute"-Edition.
"""
from __future__ import annotations

import html
import logging
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from database import load_items

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = ROOT / "docs"
ARCHIVE_DIR = DOCS_DIR / "archive"

MONTHS_DE = {
    1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni",
    7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember",
}
WEEKDAYS_DE = ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"]

INDEX_LIMIT = 30
WINDOW_DAYS = 7

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


def _format_date_de(date_iso: str | date, *, with_weekday: bool = False) -> str:
    if isinstance(date_iso, date):
        dt = date_iso
    else:
        dt = datetime.strptime(date_iso, "%Y-%m-%d").date()
    base = f"{dt.day}. {MONTHS_DE[dt.month]} {dt.year}"
    if with_weekday:
        return f"{WEEKDAYS_DE[dt.weekday()]}, {base}"
    return base


def _collect_edition_dates(items: list[dict]) -> list[str]:
    """Generiert Edition-Daten: jeden Montag im Item-Datumsbereich + heute."""
    dates: set[str] = {date.today().isoformat()}

    if items:
        pub_dates: list[date] = []
        for item in items:
            try:
                pub_dates.append(datetime.strptime(item["published_date"], "%Y-%m-%d").date())
            except (KeyError, ValueError):
                continue
        if pub_dates:
            earliest = min(pub_dates)
            latest = max(date.today(), max(pub_dates))
            first_monday = earliest + timedelta(days=(7 - earliest.weekday()) % 7)
            cur = first_monday
            while cur <= latest:
                dates.add(cur.isoformat())
                cur += timedelta(days=7)

    return sorted(dates)


def _items_for_edition(items: list[dict], edition_date: str) -> list[dict]:
    """Items, deren Publikationsdatum in den 7 Tagen VOR edition_date liegt."""
    end_dt = datetime.strptime(edition_date, "%Y-%m-%d").date()
    start_dt = end_dt - timedelta(days=WINDOW_DAYS)
    result: list[dict] = []
    for item in items:
        try:
            pub = datetime.strptime(item["published_date"], "%Y-%m-%d").date()
        except (KeyError, ValueError):
            continue
        if start_dt <= pub <= end_dt:
            result.append(item)
    # Neueste zuerst
    result.sort(key=lambda i: i.get("published_date", ""), reverse=True)
    return result


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


def _format_inline_markdown(text: str) -> str:
    """Konvertiert Inline-Markdown zu HTML (escapet zuerst alle HTML-Sonderzeichen).

    Unterstützt: **bold** → <strong>, *italic* → <em>, `code` → <code>.
    """
    escaped = html.escape(text)
    # **bold** (vor *italic* anwenden, weil ** ein Subset von * ist)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    # *italic*
    escaped = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", escaped)
    # `code`
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    return escaped


def _split_summary_and_relevance(summary_raw: str) -> tuple[str, str]:
    """Trennt den Kernaussage-Teil von der "Relevanz für SAP-Beratung:" Sektion.

    Gibt (kernaussage, relevanz) zurück. Wenn keine Relevanz-Sektion gefunden:
    (summary_raw, "").
    """
    match = re.search(
        r"\*\*\s*Relevanz für SAP[-\s]Beratung\s*:?\s*\*\*",
        summary_raw,
        flags=re.IGNORECASE,
    )
    if not match:
        return summary_raw.strip(), ""
    core = summary_raw[: match.start()].rstrip().rstrip(".").rstrip()
    # Punkt am Ende der Kernaussage wiederherstellen, falls vorhanden gewesen.
    if core and core[-1] not in ".!?":
        core += "."
    relevance_body = summary_raw[match.end():].strip()
    return core, relevance_body


def _render_item_html(item: dict) -> str:
    """Rendert ein einzelnes News-Item als HTML-Karte."""
    title = html.escape(item.get("title", "(ohne Titel)"))
    core_raw, relevance_raw = _split_summary_and_relevance(item.get("summary", ""))
    summary_html = _format_inline_markdown(core_raw)
    relevance_html = _format_inline_markdown(relevance_raw) if relevance_raw else ""
    url = item.get("url", "")
    source = item.get("source", "") or _domain_from_url(url)
    pub = item.get("published_date", "")
    pub_pretty = _format_date_de(pub) if pub else ""

    meta_parts = []
    if pub_pretty:
        meta_parts.append(f'<time datetime="{html.escape(pub)}">{html.escape(pub_pretty)}</time>')
    if source:
        meta_parts.append(f'<span class="item-source">{html.escape(source)}</span>')
    meta_html = " · ".join(meta_parts)

    link_html = (
        f'<a class="item-link" href="{html.escape(url)}" target="_blank" rel="noopener">'
        f'Originalartikel öffnen →</a>'
    ) if url else ""

    relevance_block = (
        f'<p class="item-relevance"><strong>Relevanz für SAP-Beratung:</strong> {relevance_html}</p>'
        if relevance_html else ""
    )

    return f"""<article class="news-item">
  <h2 class="item-title">{title}</h2>
  <p class="item-meta">{meta_html}</p>
  <p class="item-summary">{summary_html}</p>
  {relevance_block}
  {link_html}
</article>"""


def _domain_from_url(url: str) -> str:
    match = re.match(r"https?://([^/]+)", url or "")
    if not match:
        return ""
    host = match.group(1).lower()
    return host[4:] if host.startswith("www.") else host


def _render_day_page(edition_date: str, all_dates: list[str], items: list[dict], is_latest: bool) -> Path:
    nav_html = _build_nav(edition_date, all_dates)
    date_pretty = _format_date_de(edition_date, with_weekday=True)
    item_count = len(items)
    latest_badge = '<span class="badge">Aktuelle Ausgabe</span>' if is_latest else ""

    if items:
        items_html = "\n".join(_render_item_html(it) for it in items)
        body_html = items_html
    else:
        body_html = (
            '<div class="empty-state">'
            '<p class="empty-headline">Keine neuen Meldungen in diesem Zeitraum.</p>'
            '<p class="empty-text">Der Recherche-Agent hat in den 7 Tagen vor diesem '
            'Datum keine relevanten SAP-Meldungen gefunden, die alle Qualitätskriterien '
            '(Aktualität, Themenfilter, Validierung) erfüllen.</p>'
            '</div>'
        )

    page = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(date_pretty)} – {SITE_TITLE}</title>
<meta name="description" content="SAP-News-Übersicht vom {html.escape(date_pretty)}.">
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
    out_path = ARCHIVE_DIR / f"{edition_date}.html"
    out_path.write_text(page, encoding="utf-8")
    return out_path


def _render_index(all_dates: list[str], items_per_date: dict[str, list[dict]]) -> Path:
    DOCS_DIR.mkdir(parents=True, exist_ok=True)
    recent = list(reversed(all_dates))[:INDEX_LIMIT]

    # --- Featured edition ---
    if recent:
        latest_date = recent[0]
        latest_items = items_per_date.get(latest_date, [])
        latest_count = len(latest_items)
        latest_pretty = _format_date_de(latest_date, with_weekday=True)
        if latest_items:
            top_title = latest_items[0].get("title", "")
            teaser_html = (
                f'<p class="featured-teaser">Top-Meldung: „{html.escape(top_title)}“</p>'
                if top_title else ""
            )
        else:
            teaser_html = (
                '<p class="featured-teaser">Du bist auf dem aktuellen Stand — '
                'keine neuen Meldungen in den letzten 7 Tagen.</p>'
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
  <p class="featured-teaser">Sobald der wöchentliche Workflow gelaufen ist, erscheint hier die aktuelle Ausgabe.</p>
</section>"""
        archive_dates = []

    # --- So funktioniert's ---
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
    archive_items_html: list[str] = []
    for date_iso in archive_dates:
        items = items_per_date.get(date_iso, [])
        count = len(items)
        teaser = items[0].get("title", "") if items else ""
        teaser_html = f'<p class="archive-teaser">{html.escape(teaser)}</p>' if teaser else ""
        count_html = (
            f'<span class="archive-count">{count} {"Meldung" if count == 1 else "Meldungen"}</span>'
        )
        archive_items_html.append(
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
        '<ul class="archive-list">\n' + "\n".join(archive_items_html) + "\n</ul>"
        if archive_items_html
        else '<p class="archive-empty">Noch keine älteren Ausgaben vorhanden.</p>'
    )

    page = f"""<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{SITE_TITLE} – Wöchentliche KI-kuratierte SAP-News</title>
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
    all_items = list(load_items().values())
    all_edition_dates = _collect_edition_dates(all_items)

    items_per_date: dict[str, list[dict]] = {
        ed: _items_for_edition(all_items, ed) for ed in all_edition_dates
    }

    # Tagesseiten: für jede Edition mit Items ODER für die heutige Edition
    # (auch wenn leer — Empty-State zeigt "Du bist auf dem aktuellen Stand").
    today_iso = date.today().isoformat()
    edition_dates = [
        ed for ed in all_edition_dates
        if items_per_date[ed] or ed == today_iso
    ]
    if not edition_dates:
        edition_dates = [today_iso]

    logger.info(
        "Datenbank: %d Items, %d Edition(en) mit Inhalt (von %d insgesamt geprüft)",
        len(all_items), len(edition_dates), len(all_edition_dates),
    )

    latest = edition_dates[-1]
    for ed in edition_dates:
        path = _render_day_page(ed, edition_dates, items_per_date[ed], is_latest=(ed == latest))
        logger.info(
            "Edition %s: %d Item(s) → %s",
            ed, len(items_per_date[ed]), path.relative_to(ROOT),
        )
    index_path = _render_index(edition_dates, items_per_date)
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
