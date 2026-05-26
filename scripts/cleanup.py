"""Löscht alte HTML-Wochenausgaben. Die JSONL-Datenbank wird NICHT angetastet."""
from __future__ import annotations

import logging
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE_DIR = ROOT / "docs" / "archive"

# 90 Tage ≈ 12 Wochenausgaben.
RETENTION_DAYS = 90
HTML_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.html$")


def cleanup() -> int:
    """Entfernt HTML-Archive älter als RETENTION_DAYS. Gibt Anzahl gelöschter Dateien zurück."""
    if not ARCHIVE_DIR.exists():
        return 0
    cutoff = (datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)).date()
    removed = 0
    for path in ARCHIVE_DIR.iterdir():
        match = HTML_RE.match(path.name)
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
    logger.info("Cleanup fertig: %d HTML-Archiv(e) entfernt (>%d Tage).", removed, RETENTION_DAYS)
    return removed


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
