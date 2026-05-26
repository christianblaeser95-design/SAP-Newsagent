"""Parst Markdown-Reports in strukturierte News-Items.

Erwartetes Item-Format (durch `---` getrennt):

    **Titel des Items**

    Datum: 2026-05-23 | Quelle: news.sap.com

    Zwei bis drei Sätze Zusammenfassung. **Relevanz für Beratung:** ...

    [domain.com](https://...)

Der Parser ist tolerant gegen kleine Format-Abweichungen.
"""
from __future__ import annotations

import hashlib
import logging
import re
from datetime import date
from typing import Iterable

logger = logging.getLogger(__name__)

# Bekannte Metadaten-Labels, die optisch wie News-Titel aussehen können.
LABEL_BLACKLIST = {
    "statistik", "zeitfenster", "vergleichsbasis", "stand",
    "quelle", "datum", "relevanz für beratung", "relevanz",
    "neue sap-news (gestern + heute)", "neue sap-news",
}

DATE_RE = re.compile(r"\b(20\d{2})-(\d{2})-(\d{2})\b")
DATE_LABEL_RE = re.compile(r"Datum[:\s]+\**\s*(\d{4})-(\d{2})-(\d{2})", re.IGNORECASE)
SOURCE_LABEL_RE = re.compile(r"Quelle[:\s]+\**\s*([A-Za-z0-9\.\-]+)", re.IGNORECASE)
MD_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
TITLE_LINE_RE = re.compile(r"^[-*]?\s*\*\*(.+?)\*\*\s*:?\s*$")


def _stable_id(url: str) -> str:
    """Eindeutige ID = SHA1 der URL, ersten 12 Hex-Stellen."""
    return hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]


def _extract_title(chunk: str) -> str | None:
    """Erster eigenständiger **Titel** im Block, der kein Label ist."""
    for raw_line in chunk.splitlines():
        line = raw_line.strip()
        match = TITLE_LINE_RE.match(line)
        if not match:
            continue
        candidate = match.group(1).strip().rstrip(":")
        if candidate.lower() in LABEL_BLACKLIST:
            continue
        # Führende Numerierung "1. " / "2. " entfernen
        cleaned = re.sub(r"^\d+[\.\)]\s*", "", candidate).strip()
        return cleaned or None
    return None


def _extract_source_and_url(chunk: str) -> tuple[str | None, str | None]:
    """Markdown-Link finden und Domain als Quelle ableiten."""
    link_match = MD_LINK_RE.search(chunk)
    if not link_match:
        return None, None
    url = link_match.group(2).strip()
    # Domain aus URL extrahieren
    domain_match = re.match(r"https?://([^/]+)", url)
    domain = domain_match.group(1).lower() if domain_match else None
    if domain and domain.startswith("www."):
        domain = domain[4:]
    return domain, url


def _extract_summary(chunk: str, title: str | None) -> str:
    """Sammelt freien Fließtext zwischen Titel und Link.

    Heuristik: alle Zeilen, die nicht Titel, nicht Datum/Quelle-Label und
    kein Markdown-Link sind.
    """
    lines: list[str] = []
    for raw_line in chunk.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if TITLE_LINE_RE.match(line):
            continue
        if DATE_LABEL_RE.search(line) and SOURCE_LABEL_RE.search(line):
            continue
        if DATE_LABEL_RE.match(line) or SOURCE_LABEL_RE.match(line):
            continue
        if MD_LINK_RE.fullmatch(line):
            continue
        # Reine URL-Zeile?
        if re.fullmatch(r"https?://\S+", line):
            continue
        lines.append(line)
    summary = " ".join(lines).strip()
    # Mehrfache Leerzeichen einsparen
    summary = re.sub(r"\s+", " ", summary)
    return summary


def _split_into_item_blocks(text: str) -> list[str]:
    """Zerlegt das Markdown in News-Item-Blöcke.

    Ein Item beginnt mit einer Zeile, die wie `**1. Titel**` oder allgemein
    `**<nicht-Label-Titel>**` aussieht. Der Block endet vor dem nächsten Titel
    oder vor einer Label-Sektion (`**Zusammenfassung:**` etc.) oder bei `---`.
    """
    lines = text.splitlines()
    blocks: list[list[str]] = []
    current: list[str] | None = None

    def is_item_title(line: str) -> bool:
        stripped = line.strip()
        m = TITLE_LINE_RE.match(stripped)
        if not m:
            return False
        inner = m.group(1).strip()
        if inner.endswith(":"):
            return False  # Label
        if inner.lower().rstrip(":") in LABEL_BLACKLIST:
            return False
        # Items haben typisch eine führende Nummer, sind aber nicht zwingend numeriert.
        # Pragmatisch: wenn die nächsten paar Zeilen ein Datum: enthalten, ist es ein Item.
        return True

    def is_section_end(line: str) -> bool:
        stripped = line.strip()
        if stripped == "---":
            return True
        m = TITLE_LINE_RE.match(stripped)
        if m:
            inner = m.group(1).strip()
            if inner.endswith(":"):
                return True  # Label wie **Zusammenfassung:**
            if inner.lower().rstrip(":") in LABEL_BLACKLIST:
                return True
        if stripped.startswith("## "):
            heading = stripped[3:].strip().lower().rstrip(":")
            if heading in LABEL_BLACKLIST:
                return True
        return False

    for line in lines:
        if is_item_title(line):
            if current is not None:
                blocks.append(current)
            current = [line]
        elif current is not None:
            if is_section_end(line):
                blocks.append(current)
                current = None
            else:
                current.append(line)
    if current is not None:
        blocks.append(current)

    # Nur Blöcke behalten, die ein Datum enthalten (= echte News-Items).
    return [
        "\n".join(block)
        for block in blocks
        if DATE_LABEL_RE.search("\n".join(block))
    ]


def parse_items(markdown_text: str, *, run_date: str) -> list[dict]:
    """Extrahiert strukturierte News-Items aus einem Markdown-Report.

    `run_date` ist das ISO-Datum (YYYY-MM-DD) des Recherche-Laufs.
    """
    blocks = _split_into_item_blocks(markdown_text)
    items: list[dict] = []
    for chunk in blocks:
        date_match = DATE_LABEL_RE.search(chunk)
        if not date_match:
            continue
        title = _extract_title(chunk)
        if not title:
            continue
        try:
            published_date = date(
                int(date_match.group(1)),
                int(date_match.group(2)),
                int(date_match.group(3)),
            )
        except ValueError:
            continue
        source_label_match = SOURCE_LABEL_RE.search(chunk)
        source_from_label = (
            source_label_match.group(1).lower().strip() if source_label_match else None
        )
        source_from_link, url = _extract_source_and_url(chunk)
        source = source_from_label or source_from_link
        if not url:
            continue
        summary = _extract_summary(chunk, title)
        items.append(
            {
                "id": _stable_id(url),
                "title": title,
                "summary": summary,
                "url": url,
                "source": source or "",
                "published_date": published_date.isoformat(),
                "first_seen_run": run_date,
            }
        )
    return items


def upsert_items(existing: dict[str, dict], new_items: Iterable[dict]) -> tuple[int, int]:
    """Fügt neue Items in `existing` (Map url → item) ein. Gibt (added, updated) zurück."""
    added = 0
    updated = 0
    for item in new_items:
        key = item["url"]
        if key in existing:
            # Bekannt — keep first_seen_run aus dem Original.
            prev = existing[key]
            if not prev.get("summary") and item.get("summary"):
                prev["summary"] = item["summary"]
                updated += 1
            if not prev.get("source") and item.get("source"):
                prev["source"] = item["source"]
                updated += 1
        else:
            existing[key] = dict(item)
            added += 1
    return added, updated
