# SAP-Newsagent

Automatisierte tägliche SAP-News-Übersicht. Ein GitHub-Actions-Workflow ruft einmal pro Tag
die Anthropic API (Claude mit `web_search` + `web_fetch`) auf, recherchiert neue SAP-News
der letzten 24 Stunden, dedupliziert gegen den Vortag, rendert das Ergebnis als HTML und
veröffentlicht es über **GitHub Pages**.

## Projektstruktur

```
.github/workflows/daily-news.yml   # Cron 06:00 UTC + workflow_dispatch
docs/                              # GitHub Pages Root
  index.html                       # Übersicht der letzten 30 Tage (generiert)
  style.css
  archive/YYYY-MM-DD.html          # Eine Seite pro Tag (generiert)
data/markdown/sap_news_*.md        # Roh-Markdown der Recherchen
prompts/research_prompt.md         # Recherche-Prompt (frei anpassbar)
scripts/
  research.py                      # Anthropic API + Tools
  render.py                        # Markdown → HTML + Index
  cleanup.py                       # Löscht Einträge > 30 Tage
  main.py                          # Orchestrierung
requirements.txt
```

## Lokales Setup

```powershell
# Virtuelle Umgebung anlegen
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Abhängigkeiten installieren
pip install -r requirements.txt

# API-Key setzen (für die aktuelle Shell)
$env:ANTHROPIC_API_KEY = "sk-ant-..."

# Pipeline lokal ausführen
python scripts/main.py
```

Das erzeugt eine neue Markdown-Datei in `data/markdown/` und aktualisiert `docs/`.
Lokale Vorschau: `docs/index.html` im Browser öffnen.

## Kosten

Pro Lauf wenige US-Cent (abhängig von Anzahl Web-Suchen und web_fetch-Aufrufen).

## Modell und Tools

- **Modell**: `claude-sonnet-4-6` (in `scripts/research.py`, Konstante `MODEL`).
- **Server-Tools**: `web_search_20260209`, `web_fetch_20260209` (GA-Versionen mit dynamischem
  Filter; kein Beta-Header nötig).
- **Tool-Limit**: `max_uses=40` pro Tool und Lauf.

## GitHub-Einrichtung (einmalig)

1. **Repository-Secret anlegen**: `Settings → Secrets and variables → Actions →
   New repository secret`
   - Name: `ANTHROPIC_API_KEY`
   - Wert: dein Anthropic API-Key (`sk-ant-...`)

2. **Workflow-Permissions auf "Read and write" setzen**:
   `Settings → Actions → General → Workflow permissions →
   "Read and write permissions"` aktivieren.

3. **GitHub Pages aktivieren**: `Settings → Pages`
   - Source: **Deploy from a branch**
   - Branch: `main`, Ordner `/docs`
   - Speichern. Die Seite ist dann unter
     `https://<dein-user>.github.io/SAP-Newsagent/` erreichbar.

4. **Workflow erstmalig manuell starten**: `Actions → Daily SAP News → Run workflow`.
   Der erste Lauf erzeugt `data/markdown/sap_news_<HEUTE>.md` und committet die HTML-Dateien.

Danach läuft der Job täglich um **06:00 UTC** automatisch.

## Recherche-Prompt anpassen

Der gesamte Recherche-Prompt liegt in `prompts/research_prompt.md`. Hier kannst du
Suchanfragen, Themen-Filter oder Ausgabeformat ändern, ohne den Python-Code anzufassen.

Der Wrapper hängt automatisch die autoritativen Datumsangaben (HEUTE/GESTERN/JETZT) und
die Vortagesdatei als Vergleichsbasis an, damit das Modell nicht selbst raten muss.

## Robustheit

- Bei API-Fehlern oder leerer Antwort wird **keine** Markdown-Datei geschrieben (Exit-Code
  ≠ 0), damit der Auto-Commit nichts kaputtes pusht.
- `cleanup.py` löscht Einträge älter als 30 Tage anhand des Datums im Dateinamen.
- Logging mit Zeitstempel via `logging`-Modul.
