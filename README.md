# SAP-Newsagent

Automatisierte **wöchentliche SAP-News-Übersicht** für SAP-SD-Beraterinnen und -Berater.

Ein GitHub-Actions-Workflow ruft jeden Montagmorgen die Anthropic API (Claude mit
`web_search` + `web_fetch`) auf, recherchiert SAP-News der letzten 7 Tage,
extrahiert sie als strukturierte Items in eine JSONL-Datenbank, dedupliziert
gegen alle bisherigen Einträge, rendert das Ergebnis als HTML und veröffentlicht
es über **GitHub Pages**.

Live: https://christianblaeser95-design.github.io/SAP-Newsagent/

## Architektur in 30 Sekunden

```
   ┌── Workflow (Mo 06:00 UTC) ────────────────┐
   │                                            │
   │  research.py  ──Claude API+web_search──>  Markdown-Antwort
   │     │                                      │
   │     └── parse.py: Items extrahieren ──>   data/news.jsonl
   │                                            │      (Source of Truth)
   │                                            ▼
   │  render.py ── liest JSONL, filtert ──> docs/archive/*.html
   │              pro Wochenausgabe              docs/index.html
   │                                            │
   └────────────────────────────────────────────┘
                                                │
                                                ▼
                              git commit + push → GitHub Pages
```

**Schlüsselidee:** `data/news.jsonl` ist die persistente Datenbank aller jemals
gefetchten Items. Jede Wochenausgabe ist nur ein **Datumsfilter** (`published_date`
in den 7 Tagen vor dem Edition-Datum) über diese DB. Neue Läufe legen Items hinzu
(URL-Dedup), löschen nie. So sind auch **rückwirkende Wochenausgaben** möglich,
sobald genug Daten in der DB sind.

## Projektstruktur

```
.github/workflows/daily-news.yml   # Cron Mo 06:00 UTC + workflow_dispatch
docs/                              # GitHub Pages Root
  index.html                       # Startseite (generiert)
  style.css
  archive/YYYY-MM-DD.html          # Pro Wochenausgabe eine Seite (generiert)
data/news.jsonl                    # Persistente Item-Datenbank (Source of Truth)
prompts/research_prompt.md         # Recherche-Prompt
scripts/
  main.py                          # Orchestrierung: research → render → cleanup
  research.py                      # API-Call → Datums-Filter → JSONL-Append
  parse.py                         # Markdown → strukturierte Items
  database.py                      # JSONL-Lesen/Schreiben (Dedup nach URL)
  render.py                        # JSONL → HTML (Editionen + Index)
  cleanup.py                       # Löscht HTML-Archive >90 Tage
requirements.txt
```

## Modell, Quellen, Themen

- **Modell:** `claude-haiku-4-5` (kostengünstig, eigener Rate-Limit-Pool).
  Für höhere Qualität auf `claude-sonnet-4-6` umstellen (`scripts/research.py`,
  Konstante `MODEL`) — benötigt Anthropic-API-Tier 2.
- **Tools:** `web_search_20260209` + `web_fetch_20260209` (GA), beide mit
  `allowed_callers=["direct"]` (Haiku unterstützt kein Programmatic Tool Calling).
- **Tool-Limit:** `max_uses=12` pro Tool und Lauf. Budget ~$0,25 pro Lauf = **~$1/Monat**.
- **Zeitfenster:** Letzte 7 Tage (`scripts/research.py`, `cutoff_date`).
- **Themenfokus** (in `prompts/research_prompt.md` definiert):
  - Primär: SAP SD, Order-to-Cash, Pricing, ATP, Fiori SD, BTP/CPI-Integration
  - Sekundär: SAP Cloud (BTP, S/4HANA Cloud), AI / Joule, Integration, Plattform
- **Quellenpriorität:**
  1. SAP-offiziell (news.sap.com, blogs.sap.com, community.sap.com)
  2. SAP-nahe Fachpresse (sapinsider.org)
  3. Sonstige nur bei klarem SAP-Bezug

## Lokales Setup

```powershell
# Virtuelle Umgebung
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Abhängigkeiten
pip install -r requirements.txt

# API-Key setzen (nur für API-Lauf nötig — Render/Cleanup laufen ohne)
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# Vollständige Pipeline (kostet API-Tokens)
python scripts/main.py

# Nur HTML neu rendern (ohne API)
python scripts/render.py

# Nur alte Einträge aufräumen
python scripts/cleanup.py
```

Lokale Vorschau: `docs/index.html` im Browser öffnen.

## Robustheit & Garantien

- **Datums-Garantie:** Selbst wenn das Modell den 7-Tage-Cutoff ignoriert, wirft
  der Wrapper (`research.py:_filter_by_date`) Items mit Publikationsdatum vor
  Cutoff oder mehr als 1 Tag in der Zukunft programmatisch raus.
- **Fail-Safe:** Bei API-Fehlern oder leerer Antwort wird **keine** Datei
  geschrieben (Exit-Code ≠ 0), damit der Auto-Commit nichts Kaputtes pusht.
- **URL-Dedup:** Items werden in der DB nach URL eindeutig gehalten. Erneutes
  Auffinden eines Items aktualisiert es höchstens (Summary, Source).
- **Aufbewahrung:** `cleanup.py` löscht HTML-Archive älter als 90 Tage.
  Die **JSONL-Datenbank wird nie automatisch gekürzt** — sie wächst kontinuierlich.

## Kosten

- Haiku 4.5, wöchentlich, mit 16 Suchen + ~12 fetches: ~$0,25 pro Lauf → **~$1/Monat**.
- Sonnet 4.6 (falls upgegradet): ~$0,40 pro Lauf → ~$1,60/Monat.

## GitHub-Einrichtung (einmalig)

1. **Repository-Secret:** `Settings → Secrets and variables → Actions →
   New repository secret`
   - Name: `ANTHROPIC_API_KEY`
   - Wert: dein Anthropic-API-Key (`sk-ant-...`)
2. **Workflow-Permissions:** `Settings → Actions → General → Workflow permissions
   → Read and write permissions`
3. **GitHub Pages:** `Settings → Pages → Deploy from a branch → main → /docs`
4. **Workflow erstmalig manuell:** `Actions → Weekly SAP News → Run workflow`

Danach läuft der Workflow automatisch jeden **Montag um 06:00 UTC**
(07:00 Berlin im Winter, 08:00 Berlin im Sommer).

## Anpassungen

| Möchte ich… | …ändere ich… |
|---|---|
| anderes Modell | `scripts/research.py` → `MODEL` |
| anderes Zeitfenster | `scripts/research.py` → `cutoff_date = today_date - timedelta(days=N)` und im Prompt `VOR_7_TAGEN`-Text |
| anderen Themenfokus / Quellen | `prompts/research_prompt.md` |
| anderen Zeitplan | `.github/workflows/daily-news.yml` → `cron` |
| längere Aufbewahrung | `scripts/cleanup.py` → `RETENTION_DAYS` |
| Site-Design | `docs/style.css` |
| Site-Texte (Headline, "So funktioniert's") | `scripts/render.py` → Konstanten oben im File |

## Items manuell hinzufügen

Items lassen sich ohne API-Aufruf in die DB einpflegen. Vorlage:
`scripts/seed_may_2026.py`. Pattern:

```python
from database import load_items, save_items
from parse import _stable_id, upsert_items

existing = load_items()
upsert_items(existing, [
    {
        "id": _stable_id(url),
        "title": "...",
        "summary": "...",
        "url": "https://...",
        "source": "news.sap.com",
        "published_date": "2026-05-21",
        "first_seen_run": "2026-05-26",
    }
])
save_items(existing.values())
```

Danach `python scripts/render.py` zum Neu-Rendern.
