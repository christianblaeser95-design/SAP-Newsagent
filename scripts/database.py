"""Persistente JSONL-Datenbank aller jemals gefetchten SAP-News-Items."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Iterable

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
DB_FILE = ROOT / "data" / "news.jsonl"


def load_items() -> dict[str, dict]:
    """Lädt alle Items als Map url → item."""
    items: dict[str, dict] = {}
    if not DB_FILE.exists():
        return items
    with DB_FILE.open("r", encoding="utf-8") as fh:
        for line_no, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("DB-Zeile %d übersprungen (JSON-Fehler): %s", line_no, exc)
                continue
            url = obj.get("url")
            if url:
                items[url] = obj
    return items


def save_items(items: Iterable[dict]) -> None:
    """Schreibt alle Items zurück (kompletter Rewrite, sortiert nach Datum)."""
    DB_FILE.parent.mkdir(parents=True, exist_ok=True)
    items_list = sorted(
        items,
        key=lambda i: (i.get("published_date", ""), i.get("title", "")),
        reverse=True,
    )
    with DB_FILE.open("w", encoding="utf-8") as fh:
        for item in items_list:
            fh.write(json.dumps(item, ensure_ascii=False) + "\n")
    logger.info("Datenbank gespeichert: %d Items in %s", len(items_list), DB_FILE)
