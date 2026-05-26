"""Einmaliges Seeding: SAP-News aus seriösen Drittquellen (Mai 2026).

Ergänzt die Datenbank um SAPinsider, erp.today, diginomica, The Register,
Heise und Handelsblatt. Bei wiederholten Läufen verhindert URL-Dedup, dass
Items doppelt landen.
"""
from __future__ import annotations

import logging
import sys

from database import load_items, save_items
from parse import _stable_id, upsert_items

logger = logging.getLogger(__name__)


def _item(title: str, published: str, url: str, summary: str, source: str) -> dict:
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
    # === Aktuelle Woche (≥ 2026-05-19) ===
    _item(
        "The Register: SAPs KI-Strategie — Offenheit als Türöffner, Lock-in als Konsequenz",
        "2026-05-19",
        "https://www.theregister.com/saas/2026/05/19/saps-ai-strategy-come-for-the-openness-stay-because-you-have-to/5241109",
        "Kritische Analyse der SAP-KI-Strategie: Die Anthropic-Partnerschaft und das offene Foundation-Model-"
        "Konzept locken Kunden an, aber die Bindung an die Business AI Platform erschwert spätere "
        "Anbieterwechsel. Eine 2028-Vertragsverhandlung, die bereits heute entschieden wird.",
        source="theregister.com",
    ),

    # === Sapphire-Woche (Mai 12–13) — externe Stimmen ===
    _item(
        "SAPinsider: Sapphire 2026 — Autonomous Enterprise und neuer ERP-Stack",
        "2026-05-13",
        "https://sapinsider.org/articles/sap-sapphire-2026-autonomous-enterprise-erp-business-ai/",
        "Analyse der Sapphire-2026-Strategieumstellung: Konsolidierung von BTP, Business Data Cloud und "
        "Business AI in eine vereinheitlichte Plattform plus Autonomous Suite. AI Agent Hub kommt Q3 2026, "
        "Joule Studio 2.0 ab Juni. Was Beratungsprojekte jetzt mitberücksichtigen müssen.",
        source="sapinsider.org",
    ),
    _item(
        "SAPinsider: Sapphire 2026 — Sieben Fragen jeder Entscheider beantworten muss",
        "2026-05-13",
        "https://sapinsider.org/articles/sapphire-2026-your-sap-erp-just-got-an-ai-brain-now-what-seven-questions-every-leader-must-answer/",
        "Pragmatische Checkliste für IT-Verantwortliche: Welche organisatorischen, technischen und "
        "vertraglichen Fragen die neue Autonomous-Enterprise-Architektur aufwirft — von "
        "Datenklassifizierung bis zu Vertragsklauseln für agentengesteuerte Prozesse.",
        source="sapinsider.org",
    ),
    _item(
        "SAPinsider: Sapphire 2026 — Autonomous Enterprise und die Partnership Economy",
        "2026-05-13",
        "https://sapinsider.org/articles/sap-sapphire-2026-the-autonomous-enterprise-and-the-rise-of-the-partnership-economy/",
        "SAP setzt verstärkt auf ein Partnernetzwerk: 100 Mio. € Investment, neue Rolle für SI-Partner "
        "(Accenture, Palantir) bei komplexen Migrationen. Implikation für SD-Beratungsprojekte: Mehr "
        "Co-Innovation, weniger linearer Implementierungspfad.",
        source="sapinsider.org",
    ),
    _item(
        "erp.today: Wie SAP Anthropic, NVIDIA und Palantir in den Autonomous Stack einbaut",
        "2026-05-13",
        "https://erp.today/how-sap-is-using-anthropic-nvidia-and-palantir-to-shape-its-autonomous-enterprise-stack/",
        "Technische Einordnung: Anthropics Claude liefert die Reasoning-Schicht hinter Joule, NVIDIA "
        "stellt die sichere Runtime-Infrastruktur, Palantir AIP übernimmt KI-gestützte Datenmigration. "
        "Konkrete Architektur-Bausteine, die in Cloud-ERP-Transformationen sichtbar werden.",
        source="erp.today",
    ),
    _item(
        "erp.today: Können SAPs KI-Agenten produktiven ERP-Umgebungen vertraut werden?",
        "2026-05-14",
        "https://erp.today/sap-sapphire-2026-autonomous-enterprise-ai-governance-trust/",
        "Q&A-Format zur Governance-Frage: Wie validieren, auditieren und kontrollieren Unternehmen "
        "agentengetriebene Entscheidungen in produktivem S/4HANA? Welche Guardrails SAP eingebaut hat "
        "und wo Kunden eigene Kontrollmechanismen brauchen.",
        source="erp.today",
    ),
    _item(
        "diginomica: SAP-CTO Philipp Herzig zu API-Policy und 'Organizational Memory'",
        "2026-05-13",
        "https://diginomica.com/sap-sapphire-2026-sap-cto-philipp-herzig-saps-api-policy-changes-and-why-organizational-memory",
        "Interview mit SAP-CTO Philipp Herzig über grundlegende API-Policy-Änderungen und das Konzept "
        "des 'Organizational Memory' für agentengetriebene KI. Was Beratungsprojekte mit "
        "Integrations- und Extension-Anteil ab sofort einplanen müssen.",
        source="diginomica.com",
    ),
    _item(
        "diginomica: SAP-CEO Klein zur Geschwindigkeit der KI-Wertrealisierung",
        "2026-05-13",
        "https://diginomica.com/sap-sapphire-2026-why-sap-ceo-christian-klein-sees-need-speed-when-it-comes-ai-value-realization",
        "Christian Kleins Botschaft auf Sapphire 2026: Kunden sollen nicht drei Jahre auf "
        "System-Modernisierung warten, bevor sie KI nutzen. Klein räumt Joule-Genauigkeitsprobleme "
        "ein und beschreibt, wie SAP mit selektiven KI-Szenarien Brücken bauen will.",
        source="diginomica.com",
    ),
    _item(
        "Handelsblatt: SAP stellt Vision für autonome Unternehmen vor",
        "2026-05-12",
        "https://www.handelsblatt.com/technik/it-internet/kuenstliche-intelligenz-sap-stellt-vision-fuer-autonome-unternehmen-vor/100223581.html",
        "Deutsche Wirtschaftspresse zur Sapphire-Keynote: SAP-Anwendungen sollen Aufgaben in Finanzen, "
        "Logistik und HR weitgehend autonom übernehmen. 100 Mio. € Förderprogramm für Kunden, die "
        "diese Vision umsetzen wollen.",
        source="handelsblatt.com",
    ),
    _item(
        "Heise: SAP-Strategie für die Autonomous Enterprise — Altes Wissen, neue KI",
        "2026-05-13",
        "https://www.heise.de/en/news/Old-Knowledge-New-AI-SAP-s-Strategy-for-the-Autonomous-Enterprise-11292276.html",
        "Heise ordnet SAPs Autonomous-Enterprise-Vision ein: Die jahrzehntelange ERP-Expertise wird mit "
        "neuer Agenten-Technologie kombiniert. Komplementiert durch Investitionen in Startups wie n8n "
        "und Parloa. Bewertung aus deutscher IT-Sicht.",
        source="heise.de",
    ),
    _item(
        "Heise: SAP-Patchday Mai — kritische Login-Lücken",
        "2026-05-13",
        "https://www.heise.de/en/news/SAP-Patchday-Critical-vulnerabilities-allow-unauthorized-login-11291681.html",
        "Mai-Patchday: 15 neue Security Notes, zwei davon kritisch — erlauben unautorisierten Login bzw. "
        "SQL-Injection. Patch-Stand sollte zeitnah geprüft werden, besonders in produktiven "
        "S/4HANA- und Commerce-Cloud-Installationen.",
        source="heise.de",
    ),

    # === Frühere Wochen (zur Anreicherung historischer Editionen) ===
    _item(
        "The Register: Cloud-Pläne von SAP 2 Milliarden Euro unter Plan",
        "2026-03-19",
        "https://www.theregister.com/2026/03/19/sap_2b_off_target/",
        "Fünf Jahre nach Start des Cloud-Migrationsplans liegt SAP rund 2 Mrd. € unter dem ursprünglichen "
        "Ziel. Kritische Bestandsaufnahme der RISE-Strategie und der Hürden bei der ECC-Ablösung.",
        source="theregister.com",
    ),
    _item(
        "The Register: Sellafield startet SAP-Migration mit 33-Mio.-£-Auftrag",
        "2026-04-10",
        "https://www.theregister.com/software/2026/04/10/sellafield-starts-sap-migration-with-33m-award/5221588",
        "Das britische Atomstandort-Unternehmen Sellafield vergibt ohne Wettbewerb einen "
        "33-Mio.-Pfund-Auftrag an SAP zur Ablösung des Legacy-ERP. Beispielhaft für die hochregulierten "
        "Migrationsprojekte, die SAP in Public Sector / kritischer Infrastruktur aktuell gewinnt.",
        source="theregister.com",
    ),
    _item(
        "The Register: Supply-Chain-Angriff auf SAP-npm-Pakete",
        "2026-05-01",
        "https://www.theregister.com/security/2026/05/01/ongoing-supply-chain-attacks-worm-into-sap-npm-packages/5228837",
        "TeamPCP kompromittiert am 29. April vier offizielle npm-Pakete aus dem SAP-JavaScript- und "
        "Cloud-Application-Development-Ökosystem. Vergiftete Releases zwischen 09:55 und 12:14 UTC "
        "publiziert. Auswirkungen auf CAP- und BTP-basierte Erweiterungsprojekte prüfen.",
        source="theregister.com",
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
    logger.info(
        "Seed fertig — +%d neu, %d aktualisiert, gesamt %d Items.",
        added, updated, len(existing),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
