"""Ergänzt jede bestehende DB-Eintrag um einen expliziten
`**Relevanz für SAP-Beratung:**`-Satz am Ende.

Strategie:
1. Lade alle Items.
2. Falls die Summary bereits "Relevanz für SAP-Beratung:" enthält, lasse sie
   unangetastet (idempotent).
3. Andernfalls hänge einen item-spezifischen Relevanz-Satz an. Die Sätze sind
   pro URL kuratiert; für unbekannte URLs gibt es eine generische Fallback-
   Formulierung.
"""
from __future__ import annotations

import logging
import re
import sys

from database import load_items, save_items

logger = logging.getLogger(__name__)

# URL → Relevanzsatz (ohne führendes "**Relevanz für SAP-Beratung:**", das
# wird automatisch ergänzt).
RELEVANCE_BY_URL: dict[str, str] = {
    "https://news.sap.com/2026/05/sap-completes-acquisition-of-reltio/":
        "Stärkt SAP-MDM-Story; relevant für Projekte mit komplexen "
        "Stammdaten- und Datenmigrationsanforderungen.",
    "https://news.sap.com/2026/05/sap-to-acquire-dremio-unify-sap-and-non-sap-data-power-agentic-ai/":
        "Beeinflusst Datenstrategie-Entscheidungen bei hybriden Landschaften "
        "und macht offene Lakehouse-Formate (Iceberg) zur strategischen Option "
        "in Business Data Cloud.",
    "https://news.sap.com/2026/05/sap-to-acquire-prior-labs-establish-frontier-ai-lab-europe/":
        "Strategisches Signal: SAP investiert in eigene Foundation Models. "
        "Mittelfristige Implikation für Architektur-Entscheidungen rund um KI "
        "und Souveränität (DSGVO/EU AI Act).",
    "https://news.sap.com/2026/05/sap-sapphire-sap-unveils-autonomous-enterprise/":
        "Verschiebt die Implementierungsmethodik in Richtung agentenbasierter "
        "Prozesse — neue Bewertungsfragen für Cloud-ERP-Roadmaps und "
        "Change-Management bei Kunden.",
    "https://news.sap.com/2026/05/sap-palantir-enhance-partnership-ai-supported-data-migration-tooling/":
        "Direkter Hebel bei ECC→Cloud-ERP-Migrationen: KI-gestütztes Tooling "
        "verkürzt typische Datenmigrationsphasen und ändert das Skill-Mix in "
        "Migrationsteams.",
    "https://news.sap.com/2026/05/new-joule-studio-enterprise-scale-agentic-development/":
        "Erweiterungs- und Extensibility-Projekte sollten Joule Studio als "
        "Plattform-Option in Betracht ziehen — auch für SD-spezifische "
        "Agenten in Pricing, ATP und Auftragserfassung.",
    "https://erp.today/sap-security-patch-day-may-2026-risk/":
        "Patch-Status in S/4HANA- und Commerce-Cloud-Projekten zeitnah prüfen "
        "und in Kundenkommunikation aufnehmen.",
    "https://news.sap.com/2026/05/sap-sapphire-keynote-business-ai-platform-power-autonomous-enterprise/":
        "Strategische Einordnung der Business AI Platform — Basis für "
        "Architektur-Diskussionen mit Kunden, die BTP und KI-Use-Cases verbinden.",
    "https://news.sap.com/2026/05/sap-sapphire-keynote-customers-making-ai-value-real-today/":
        "Konkrete Referenzkunden und Use-Cases als Argumentationsbasis "
        "für KI-Initiativen in laufenden Beratungsprojekten.",
    "https://news.sap.com/2026/05/partner-summit-sap-sapphire-autonomous-enterprise-era/":
        "Partner-Ökosystem wird neu sortiert: Co-Innovation und SI-Rollen "
        "ändern sich. Für Beratungshäuser relevant bei der Positionierung "
        "in Cloud-ERP-Transformationen.",
    "https://news.sap.com/2026/05/future-enterprise-autonomous/":
        "Hilfsmittel zur Kommunikation der Autonomous-Enterprise-Vision an "
        "Kundenstakeholder; ordnet ein, was kurz- vs. mittelfristig realistisch ist.",
    "https://news.sap.com/2026/05/ericsson-scales-ai-across-enterprise-business-data-fabric-sap/":
        "Praxisbeispiel als Referenzarchitektur für Kunden mit gemischten "
        "Datenlandschaften — KI-Workloads über SAP- und Non-SAP-Quellen.",
    "https://news.sap.com/2026/05/madrid-city-council-modernization-internal-tax-management-sap/":
        "Public-Sector-Referenz für integrierte Tax- und Revenue-Management-"
        "Lösungen auf S/4HANA — argumentativ nutzbar bei Verwaltungs-Kunden.",
    "https://news.sap.com/2026/05/martur-fompak-international-throughput-efficiency-intelligent-robotics-joule-embodied-ai/":
        "Konkretes Beispiel für EWM + Robotik im Fulfillment — direkt relevant "
        "für SD-Beratung bei Order-to-Cash-Projekten mit Lagerlogistik-Bezug.",
    "https://news.sap.com/2026/04/sap-business-ai-release-highlights-q1-2026/":
        "AI-Email-to-Order, Predictive Close Dates, Deal Risk Scoring — direkt "
        "in SD/O2C-Beratungsprojekten einsetzbar. Pilot-Use-Cases identifizieren.",
    "https://community.sap.com/t5/crm-and-cx-blog-posts-by-sap/sap-sales-cloud-q1-2026-innovation-overview/ba-p/14377174":
        "Wichtig bei Migration von klassischem CRM auf Sales Cloud V2 und für "
        "die Integration in S/4HANA-O2C-Prozesse.",
    "https://news.sap.com/2026/05/more-autonomous-supply-chain/":
        "ATP wird Teil agentengetriebener Fulfillment-Entscheidungen — wichtig "
        "für SD-Logistik-Schnittstellen und neue Order-Promising-Konzepte.",
    "https://www.theregister.com/saas/2026/05/19/saps-ai-strategy-come-for-the-openness-stay-because-you-have-to/5241109":
        "Kritischer Blick aufs Lock-in-Risiko der Business AI Platform — wichtig "
        "für Vertragsverhandlungen und Multi-Vendor-Strategien.",
    "https://sapinsider.org/articles/sap-sapphire-2026-autonomous-enterprise-erp-business-ai/":
        "Strukturierte Übersicht der Konsolidierungs-Roadmap (BTP + BDC + AI). "
        "Hilft bei Architektur-Entscheidungen in laufenden BTP-Projekten.",
    "https://sapinsider.org/articles/sapphire-2026-your-sap-erp-just-got-an-ai-brain-now-what-seven-questions-every-leader-must-answer/":
        "Checkliste organisatorischer und vertraglicher Fragen — als "
        "Vorbereitung auf Kundenworkshops zur KI-Strategie nutzbar.",
    "https://sapinsider.org/articles/sap-sapphire-2026-the-autonomous-enterprise-and-the-rise-of-the-partnership-economy/":
        "Veränderte Partner-Dynamik: Co-Innovation statt linearer "
        "Implementierung — Folgen für Beratungs-Engagement-Modelle.",
    "https://erp.today/how-sap-is-using-anthropic-nvidia-and-palantir-to-shape-its-autonomous-enterprise-stack/":
        "Technische Architektur der Autonomous-Stack-Bausteine — Grundlage "
        "für Architekturdiskussionen in BTP- und KI-Projekten.",
    "https://erp.today/sap-sapphire-2026-autonomous-enterprise-ai-governance-trust/":
        "Governance-Fragen direkt für Kundenkommunikation und "
        "Risiko-Workshops nutzbar; wichtig bei produktiven Agenten-Rollouts.",
    "https://diginomica.com/sap-sapphire-2026-sap-cto-philipp-herzig-saps-api-policy-changes-and-why-organizational-memory":
        "API-Policy-Änderungen direkt relevant für Integrations- und "
        "Extensibility-Projekte; Organizational Memory als neues Konzept "
        "in Architektur-Designs einplanen.",
    "https://diginomica.com/sap-sapphire-2026-why-sap-ceo-christian-klein-sees-need-speed-when-it-comes-ai-value-realization":
        "Argumentationshilfe gegenüber Kunden, die wegen Modernisierung mit "
        "KI-Initiativen warten — SAP positioniert sich für hybride Pfade.",
    "https://www.handelsblatt.com/technik/it-internet/kuenstliche-intelligenz-sap-stellt-vision-fuer-autonome-unternehmen-vor/100223581.html":
        "Deutsche Wirtschaftspresse-Sicht; nützlich für Stakeholder-"
        "Kommunikation auf Vorstandsebene.",
    "https://www.heise.de/en/news/Old-Knowledge-New-AI-SAP-s-Strategy-for-the-Autonomous-Enterprise-11292276.html":
        "Deutsche IT-Sicht auf SAPs Strategie — hilfreich bei der "
        "Bewertung lokaler Implikationen (Datensouveränität, EU AI Act).",
    "https://www.heise.de/en/news/SAP-Patchday-Critical-vulnerabilities-allow-unauthorized-login-11291681.html":
        "Patch-Status in produktiven S/4HANA- und Commerce-Cloud-"
        "Installationen prompt prüfen und Kunden informieren.",
    "https://www.theregister.com/2026/03/19/sap_2b_off_target/":
        "Kritische RISE-Bestandsaufnahme — wichtig für ehrliche "
        "Kundenkommunikation zu Migrationsrisiken und realistische "
        "Projekt-Roadmaps.",
    "https://www.theregister.com/software/2026/04/10/sellafield-starts-sap-migration-with-33m-award/5221588":
        "Public-Sector-/Regulated-Industries-Referenz für die "
        "Argumentationskette in hochregulierten Migrationen.",
    "https://www.theregister.com/security/2026/05/01/ongoing-supply-chain-attacks-worm-into-sap-npm-packages/5228837":
        "Supply-Chain-Risiko in CAP- und BTP-basierten Erweiterungen — "
        "Build-Pipelines und Lockfiles in laufenden Projekten prüfen.",
}

FALLBACK_RELEVANCE = (
    "Im Beratungskontext relevant für SAP-Cloud-/AI-Strategie-Diskussionen — "
    "bei Bedarf vertiefen."
)


def _has_relevance(text: str) -> bool:
    return bool(re.search(r"Relevanz für SAP[-\s]Beratung\s*:", text, re.IGNORECASE))


def _strip_inline_relevance(text: str) -> str:
    """Entfernt eingebettete '**Relevanz für Beratung:** ...' Floskeln,
    damit am Ende ein sauberer separater Satz steht."""
    pattern = re.compile(r"\*\*Relevanz für (SAP-?\s?)?Beratung\*\*:?", re.IGNORECASE)
    return pattern.sub("", text)


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    items_map = load_items()
    logger.info("Geladen: %d Items.", len(items_map))

    updated = 0
    untouched = 0
    for url, item in items_map.items():
        summary = item.get("summary", "").strip()
        if _has_relevance(summary):
            untouched += 1
            continue

        # Eingebettete Floskeln entfernen, damit der neue Satz alleinsteht.
        cleaned = _strip_inline_relevance(summary).strip()
        # Doppelte Leerzeichen normalisieren
        cleaned = re.sub(r"\s{2,}", " ", cleaned)
        # Endsatzzeichen sicherstellen
        if cleaned and cleaned[-1] not in ".!?":
            cleaned += "."

        relevance = RELEVANCE_BY_URL.get(url, FALLBACK_RELEVANCE)
        new_summary = f"{cleaned} **Relevanz für SAP-Beratung:** {relevance}"
        item["summary"] = new_summary
        updated += 1

    save_items(items_map.values())
    logger.info(
        "Fertig: %d aktualisiert, %d bereits gut, gesamt %d Items.",
        updated, untouched, len(items_map),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
