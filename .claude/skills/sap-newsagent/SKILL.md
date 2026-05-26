---
name: sap-newsagent
description: Arbeiten am SAP-Newsagent-Projekt — Architektur, Pipeline, Anpassungen, häufige Aufgaben und Fallstricke. Beim Editieren der Recherche-/Render-/Parser-Logik oder beim Hinzufügen von Items hier zuerst nachlesen.
---

# SAP-Newsagent — Arbeits-Skill

Dieses Skill hält das Arbeitswissen zum Projekt zusammen: was die Pipeline tut,
welche Invarianten gelten, wo häufige Probleme auftauchen und wie man typische
Aufgaben durchführt.

## Architektur (kurz)

```
Workflow (Mo 06:00 UTC) ─► research.py ─► Markdown vom Modell
                              │
                              ├─► parse.py extrahiert Items
                              │
                              └─► database.py: append in data/news.jsonl (URL-Dedup)

render.py liest news.jsonl ─► für jeden Edition-Termin Items in [date-7d, date] ─► docs/archive/*.html + docs/index.html
```

**Source of Truth: `data/news.jsonl`** — eine Zeile pro Item. Markdown-Dateien
in `data/markdown/` sind nur Audit-Log. HTML in `docs/` ist generierter Output.

### Item-Schema (eine JSONL-Zeile)

```json
{
  "id": "12-stelliger sha1 der URL",
  "title": "Titel auf Deutsch",
  "summary": "2–3 Sätze: Kernaussage + Relevanz für SAP-Beratung",
  "url": "https://...",
  "source": "news.sap.com",
  "published_date": "2026-05-21",
  "first_seen_run": "2026-05-26"
}
```

**Natürlicher Schlüssel ist `url`** (nicht `id`). Dedup in `parse.upsert_items`
erfolgt nach URL.

### Edition-Konzept

Eine "Edition" = ein Datum. Die Edition zeigt Items mit `published_date` in
`[edition_date - 7d, edition_date]`. Edition-Daten werden in
`render._collect_edition_dates` aus drei Quellen gemerged:

1. Allen `data/markdown/sap_news_YYYY-MM-DD.md` (= echte Workflow-Läufe)
2. Jeder Montag im Bereich `[earliest_item_pub, max(today, latest_item_pub)]`
3. Plus `today` (für die laufende Woche)

Editionen ohne Items werden vom Index ausgeblendet — außer der heutigen
(zeigt dann den Empty-State "Du bist auf dem aktuellen Stand").

## Setup-Befehle

```powershell
# Erstes Setup
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Render-only (kostet nichts)
.\.venv\Scripts\Activate.ps1
python scripts/render.py

# Volle Pipeline (kostet API-Tokens)
$env:ANTHROPIC_API_KEY = "sk-ant-..."
python scripts/main.py
```

## Häufige Aufgaben

### Items manuell hinzufügen (kein API-Verbrauch)

Vorlage: `scripts/seed_may_2026.py`. Pattern:

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

Danach `python scripts/render.py`.

### Themen / Quellenpriorität ändern

→ `prompts/research_prompt.md` editieren. Schritt 4 (Themen-Filter) und
Schritt 3b (Quellenpriorität) sind die relevanten Abschnitte. Kein Code-Anfassen
nötig.

### Modell wechseln

→ `scripts/research.py` Konstante `MODEL` ändern. Wenn auf Sonnet 4.6 hoch:
`allowed_callers=["direct"]` aus den Tools entfernen, damit Dynamic Filtering
greift; `MAX_TOOL_USES` auf 25 und `MAX_TOKENS` auf 16000. Vorsicht: Anthropic
Tier 1 erlaubt nur 30k Input-TPM bei Sonnet — eventuell Rate-Limit-Fehler bei
hoher Tool-Nutzung.

### Zeitfenster ändern (aktuell 7 Tage)

Zwei Stellen:
1. `scripts/research.py` → `cutoff_date = today_date - timedelta(days=N)` und
   `WINDOW_DAYS` (falls existent).
2. `prompts/research_prompt.md` → alle Erwähnungen von "7 Tage" / "VOR_7_TAGEN" anpassen.
3. `scripts/render.py` → `WINDOW_DAYS` Konstante.

### Lokale Vorschau prüfen

`docs/index.html` im Browser öffnen. Bei Bedarf `python scripts/render.py` für
Re-Render.

## Bekannte Fallstricke

### Anthropic-API: 30k Input-TPM auf Tier 1

Sonnet 4.6 reißt das Limit schnell bei vielen `web_fetch`-Aufrufen. Symptom:
HTTP 429 nach ein paar Minuten. Lösung: Modell auf Haiku 4.5 oder Tier 2
kaufen.

### Haiku unterstützt kein Programmatic Tool Calling

Symptom: `'does not support programmatic tool calling. ... allowed_callers
require it'`. Lösung: `allowed_callers=["direct"]` in der Tool-Definition
in `research.py`.

### Code-Execution-Container bei web_search_20260209/web_fetch_20260209

Bei `pause_turn` muss `container_id` im Folge-Request mitgegeben werden.
Bereits in `research.py` umgesetzt. Bei Modellwechsel zurück auf Sonnet daran
denken.

### Modell-Vorrede ("Schritt 0: …", "Jetzt suche ich…")

Haiku ignoriert die Anweisung "keine Vorrede" manchmal. Der Wrapper-Cleanup
in `research._clean_markdown` schneidet alles vor `# Stand:` ab. Nicht aus
Versehen entfernen.

### Datum-K.O.-Filter

Doppelter Schutz:
1. Prompt-Regel "Datum ≥ VOR_7_TAGEN sonst ausschließen" (Schritt 5).
2. Programmatischer Filter `research._filter_by_date`. Funktioniert auch wenn
   das Modell Items in einem Block ohne `---`-Trenner ausgibt — splittet nach
   Titel-Pattern, prüft `Datum: YYYY-MM-DD` pro Item.

### Item-Zähler verzählt sich

`render._count_items` ist eine eigene Funktion. Bei Änderungen am Markdown-Format
muss die Item-Zähl-Logik mitwandern. Sicherer wäre, Counts aus der JSONL zu
berechnen (TODO).

### Git: erst pullen, dann pushen

Der Workflow committet automatisch. Vor dem manuellen Commit/Push immer
`git pull --rebase`. Bei "cannot pull with rebase: unstaged changes" erst
`git add -A; git commit`, dann pull --rebase.

## Was NICHT tun

- **Markdown-Dateien als Source of Truth behandeln** — die sind nur Audit-Log.
  Items kommen aus `data/news.jsonl`.
- **JSONL-Datei aufräumen / löschen** — die wächst absichtlich kontinuierlich,
  weil sie auch alte Editionen rendert.
- **`docs/archive/*.html` von Hand editieren** — wird beim nächsten Render
  überschrieben.
- **API-Key in Code committen** — nur als `ANTHROPIC_API_KEY` env var / Secret.
- **GitHub Pages-Source umstellen** — bleibt auf `main` / `/docs`.

## Pfade

| Pfad | Zweck |
|---|---|
| `scripts/main.py` | Orchestriert research → render → cleanup |
| `scripts/research.py` | API-Call, Datums-Filter, JSONL-Append |
| `scripts/parse.py` | Markdown-Block → Item-Dict |
| `scripts/database.py` | JSONL lesen/schreiben |
| `scripts/render.py` | JSONL → HTML |
| `scripts/cleanup.py` | Alte Dateien löschen (>90 Tage) |
| `scripts/import_markdown.py` | Bestehende Markdowns in DB (einmalig) |
| `scripts/seed_may_2026.py` | Vorlage für manuelle Item-Insertion |
| `prompts/research_prompt.md` | Recherche-Prompt (frei editierbar) |
| `data/news.jsonl` | Item-Datenbank |
| `data/markdown/sap_news_*.md` | Audit-Log der Modell-Antworten |
| `docs/index.html` | Startseite (generiert) |
| `docs/archive/*.html` | Wochenausgaben (generiert) |
| `docs/style.css` | Site-Styling |
| `.github/workflows/daily-news.yml` | Cron-Workflow (Mo 06:00 UTC) |
