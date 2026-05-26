"""Einmalig: liest alle bestehenden sap_news_*.md ein und befüllt die JSONL-DB."""
from __future__ import annotations

import logging
import re
import sys
from pathlib import Path

from database import DB_FILE, load_items, save_items
from parse import parse_items, upsert_items

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
MARKDOWN_DIR = ROOT / "data" / "markdown"
DATE_RE = re.compile(r"^sap_news_(\d{4}-\d{2}-\d{2})\.md$")


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    existing = load_items()
    logger.info("DB bisher: %d Items", len(existing))

    files = sorted(MARKDOWN_DIR.glob("sap_news_*.md")) if MARKDOWN_DIR.exists() else []
    if not files:
        logger.warning("Keine Markdown-Dateien gefunden — nichts zu importieren.")
        return 0

    total_added = 0
    for path in files:
        match = DATE_RE.match(path.name)
        if not match:
            continue
        run_date = match.group(1)
        text = path.read_text(encoding="utf-8")
        items = parse_items(text, run_date=run_date)
        added, updated = upsert_items(existing, items)
        logger.info(
            "Import %s: %d Items geparst, +%d neu, %d aktualisiert",
            path.name, len(items), added, updated,
        )
        total_added += added

    save_items(existing.values())
    logger.info("Import fertig — DB enthält jetzt %d Items (+%d neu)", len(existing), total_added)
    return 0


if __name__ == "__main__":
    sys.exit(main())
