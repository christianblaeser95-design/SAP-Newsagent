"""Einmaliges Seeding: SAP-News aus Mai 2026 (recherchiert via WebSearch).

Dieses Skript wird einmal lokal ausgeführt, um die JSONL-Datenbank rückwirkend
mit verifizierten Items aus dem Mai 2026 zu befüllen. Danach kann es im Repo
verbleiben (oder gelöscht werden) — bei wiederholten Läufen werden Items per
URL-Dedup nicht doppelt eingefügt.
"""
from __future__ import annotations

import logging
import sys

from database import load_items, save_items
from parse import _stable_id, upsert_items

logger = logging.getLogger(__name__)


def _item(title: str, published: str, url: str, summary: str, source: str = "news.sap.com") -> dict:
    return {
        "id": _stable_id(url),
        "title": title,
        "summary": summary,
        "url": url,
        "source": source,
        "published_date": published,
        "first_seen_run": "2026-05-26",
    }


SEED_ITEMS: list[dict] = [
    # === Anfang Mai: Akquisitionen ===
    _item(
        "SAP schließt Übernahme von Reltio ab",
        "2026-05-04",
        "https://news.sap.com/2026/05/sap-completes-acquisition-of-reltio/",
        "SAP hat die Akquisition von Reltio, einem führenden Anbieter von Master-Data-Management-Software, "
        "abgeschlossen. Reltio wird in SAP Business Data Cloud integriert und stärkt damit SAPs Position "
        "im Bereich Stammdatenmanagement — relevant für Beratungsprojekte mit komplexen Datenlandschaften "
        "und MDM-Anforderungen.",
    ),
    _item(
        "SAP übernimmt Dremio für agentische KI-Daten",
        "2026-05-04",
        "https://news.sap.com/2026/05/sap-to-acquire-dremio-unify-sap-and-non-sap-data-power-agentic-ai/",
        "SAP hat die Übernahme von Dremio vereinbart, einer offenen Data-Lakehouse-Plattform. Damit erweitert "
        "SAP Business Data Cloud um eine Apache-Iceberg-native Architektur, die SAP- und Non-SAP-Daten ohne "
        "Datenbewegung kombiniert. Für Beratungsprojekte zentral bei hybriden Datenlandschaften und KI-Readiness.",
    ),
    _item(
        "SAP übernimmt Prior Labs — Frontier AI Lab in Europa",
        "2026-05-04",
        "https://news.sap.com/2026/05/sap-to-acquire-prior-labs-establish-frontier-ai-lab-europe/",
        "SAP hat die Übernahme von Prior Labs angekündigt, dem Pionier für Tabular Foundation Models. "
        "Über vier Jahre investiert SAP mehr als 1 Mrd. € in den Aufbau eines globalen Frontier-AI-Labs in "
        "Europa. Strategisches Signal für eigene KI-Kompetenz und souveräne Modelle.",
    ),

    # === Sapphire 2026 (12.-13. Mai) ===
    _item(
        "SAP präsentiert die Autonomous Enterprise auf Sapphire 2026",
        "2026-05-12",
        "https://news.sap.com/2026/05/sap-sapphire-sap-unveils-autonomous-enterprise/",
        "Auf der SAP Sapphire 2026 in Orlando hat SAP die Vision der Autonomous Enterprise vorgestellt: "
        "eine vereinheitlichte SAP Business AI Platform plus eine Autonomous Suite mit über 50 "
        "domänenspezifischen Joule-Assistenten, die mehr als 200 spezialisierte Agenten in Finanzen, "
        "Supply Chain, Beschaffung, HCM und CX orchestrieren. Vertiefte Partnerschaften u. a. mit "
        "Anthropic, AWS, Google Cloud, Microsoft, NVIDIA und Palantir.",
    ),
    _item(
        "SAP und Palantir erweitern Partnerschaft für KI-gestützte Datenmigration",
        "2026-05-12",
        "https://news.sap.com/2026/05/sap-palantir-enhance-partnership-ai-supported-data-migration-tooling/",
        "SAP und Palantir bauen ihre strategische Partnerschaft aus: neue KI-gestützte Datenmigrations-"
        "Tools auf Basis von Palantir AIP werden ab Q3 2026 als SAP Solution Extension verfügbar. "
        "Accenture ist erster globaler Service-Partner. Beschleunigung von ECC-zu-Cloud-Migrationen, "
        "wichtig für komplexe Transformationsprojekte.",
    ),
    _item(
        "Joule Studio: Enterprise-Scale Agentic Development",
        "2026-05-12",
        "https://news.sap.com/2026/05/new-joule-studio-enterprise-scale-agentic-development/",
        "SAP führt Joule Studio ein — eine managed Plattform für Entwicklung und Betrieb von KI-Agenten, "
        "die nativ auf Live-Geschäftsdaten, End-to-End-Prozesse und Business-Semantik der SAP-Landschaft "
        "zugreifen. Kostenloser Design-Time-Zugang bis Ende 2026. Eingebettete Partnerschaften mit Vercel "
        "und n8n für Workflow-Orchestrierung und UX.",
    ),
    _item(
        "SAP Security Patch Day Mai 2026",
        "2026-05-12",
        "https://erp.today/sap-security-patch-day-may-2026-risk/",
        "15 neue Security Notes, davon zwei kritische Schwachstellen in SAP S/4HANA Enterprise Search "
        "für ABAP und SAP Commerce Cloud. Für Beratungsprojekte mit Cloud-Produkten: Patch-Status "
        "prüfen und Update-Roadmap mit Kunden besprechen.",
        source="erp.today",
    ),
    _item(
        "Sapphire-Keynote: Powering the Autonomous Enterprise",
        "2026-05-13",
        "https://news.sap.com/2026/05/sap-sapphire-keynote-business-ai-platform-power-autonomous-enterprise/",
        "Die Eröffnungs-Keynote von SAP CEO Christian Klein gab den Startschuss für die Autonomous "
        "Enterprise: agentengesteuerte KI sicher und im Maßstab eingesetzt, getragen von der neuen SAP "
        "Business AI Platform als Fundament für SAPs Vision agentenbasierter Geschäftsprozesse.",
    ),
    _item(
        "Sapphire-Keynote: Making AI Value Real Today",
        "2026-05-13",
        "https://news.sap.com/2026/05/sap-sapphire-keynote-customers-making-ai-value-real-today/",
        "Thomas Saueressig und Jan Gilg präsentierten konkrete Kundenbeispiele, die zeigen, wie sich "
        "die Vision der Autonomous Enterprise bereits heute realisieren lässt. Fokus: skalierbare "
        "KI-Use-Cases mit messbarem Geschäftsergebnis.",
    ),
    _item(
        "A Symphony of Partnership: Partner-Summit auf Sapphire 2026",
        "2026-05-13",
        "https://news.sap.com/2026/05/partner-summit-sap-sapphire-autonomous-enterprise-era/",
        "SAP verstärkt sein Partner-Ökosystem mit 100 Mio. € Investitionen, um KI-Adoption und den "
        "Weg zur Autonomous Enterprise zu beschleunigen. Implementation Partners wie Accenture und "
        "Palantir spielen Schlüsselrollen bei komplexen Datenmigrationen.",
    ),
    _item(
        "The Future of the Enterprise Is Autonomous",
        "2026-05-13",
        "https://news.sap.com/2026/05/future-enterprise-autonomous/",
        "Konzeptionelle Einordnung der Autonomous Enterprise: Wie agentengesteuerte KI Geschäftsprozesse "
        "neu gestaltet — von Finanzen über Supply Chain bis HR — und welche Implikationen das für "
        "SAP-Implementierungsmethoden und Beratungsansätze hat.",
    ),

    # === Mitte/Ende Mai: Kundenprojekte ===
    _item(
        "Ericsson skaliert KI mit Business Data Fabric von SAP",
        "2026-05-15",
        "https://news.sap.com/2026/05/ericsson-scales-ai-across-enterprise-business-data-fabric-sap/",
        "Ericsson nutzt eine Business Data Fabric auf Basis von SAP, um KI-Anwendungen unternehmensweit "
        "zu skalieren. Referenzimplementierung für Datenarchitekturen, die Analytics und KI-Workloads "
        "über SAP- und Non-SAP-Quellen hinweg ermöglichen.",
    ),
    _item(
        "Madrid: Stadtverwaltung modernisiert Finanz- und Steuermanagement mit SAP",
        "2026-05-21",
        "https://news.sap.com/2026/05/madrid-city-council-modernization-internal-tax-management-sap/",
        "Der Stadtrat von Madrid digitalisiert mit SAP interne Verfahren in Finanzen, Steuern und HR. "
        "Bereits zwei Drittel der städtischen Steuereinnahmen werden auf der SAP-Plattform verwaltet. "
        "Ausweitung auf Kfz- und Gewerbesteuer geplant. Public-Sector-Referenz für integrierte Tax- "
        "und Revenue-Management-Lösungen.",
    ),
]


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    existing = load_items()
    logger.info("DB bisher: %d Items", len(existing))

    added, updated = upsert_items(existing, SEED_ITEMS)
    save_items(existing.values())
    logger.info("Seed fertig — +%d neu, %d aktualisiert, gesamt %d Items.", added, updated, len(existing))
    return 0


if __name__ == "__main__":
    sys.exit(main())
