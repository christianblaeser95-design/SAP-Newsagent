"""Löscht Markdown- und HTML-Einträge älter als 30 Tage."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
MARKDOWN_DIR = ROOT / "data" / "markdown"
ARCHIVE_DIR = ROOT / "docs" / "archive"

RETENTION_DAYS = 30
MD_RE = re.compile(r"^sap_news_(\d{4}-\d{2}-\d{2})\.md$")
HTML_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.html$")


def _cutoff_date() -> datetime:
    return datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)


def _purge(directory: Path, pattern: re.Pattern[str]) -> int:
    if not directory.exists():
        return 0
    cutoff = _cutoff_date().date()
    removed = 0
    for path in directory.iterdir():
        match = pattern.match(path.name)
        if not match:
            continue
        try:
            file_date = datetime.strptime(match.group(1), "%Y-%m-%d").date()
        except ValueError:
            continue
        if file_date < cutoff:
            try:
                path.unlink()
                logger.info("Gelöscht: %s", path.relative_to(ROOT))
                removed += 1
            except OSError as exc:
                logger.warning("Konnte %s nicht löschen: %s", path, exc)
    return removed


def cleanup() -> None:
    md_removed = _purge(MARKDOWN_DIR, MD_RE)
    html_removed = _purge(ARCHIVE_DIR, HTML_RE)
    logger.info("Cleanup fertig: %d Markdown, %d HTML entfernt.", md_removed, html_removed)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    try:
        cleanup()
    except Exception as exc:
        logging.exception("Cleanup fehlgeschlagen: %s", exc)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
