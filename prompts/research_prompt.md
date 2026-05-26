# Prompt: Tägliche SAP-News-Recherche (mit Deduplizierung)

## Schritt 0: Datum ermitteln (HARTE REGEL — VOR ALLEM ANDEREN)
Ermittle das HEUTIGE Datum AUSSCHLIESSLICH aus einer dieser Quellen, in dieser Reihenfolge:
1. Systemzeit / Tool zum Abrufen der aktuellen Zeit (Zeitzone: Europe/Berlin)
2. Falls kein Tool verfügbar: explizit beim User nachfragen — NICHT raten

VERBOTEN als Datumsquelle:
- Dateinamen aus dem Output-Ordner (auch wenn `sap_news_YYYY-MM-DD.md` darin enthalten ist)
- Inhalte aus gestriger Markdown-Datei
- "Stand:"-Zeilen aus alten Reports
- Datumsangaben aus Suchergebnissen
- Datumsangaben aus deinem Trainingswissen

Gib das ermittelte Datum sofort aus:
- HEUTE = YYYY-MM-DD (Quelle: <Tool/User-Angabe>)
- GESTERN = HEUTE minus 1 Tag = YYYY-MM-DD
- JETZT = YYYY-MM-DD HH:MM Europe/Berlin

Verwende von hier an NUR noch diese drei Werte.

## Schritt 1: Vorherige Datei einlesen (Inhalt OK, Datum IGNORIEREN)
- Versuche, die Datei `sap_news_<GESTERN>.md` zu lesen.
- Falls nicht vorhanden, suche zusätzlich die neueste vorhandene `sap_news_*.md`-Datei als Fallback.
- Aus der gefundenen Datei extrahierst du AUSSCHLIESSLICH: Titel + URLs für die Deduplizierungsliste.
- IGNORIERE alle Datumsangaben in der Datei.
- Notiere: "Vergleichsbasis: <gefundener_dateiname> (Inhalt übernommen, Datum ignoriert)"

## Schritt 2: Suche durchführen
Führe MINDESTENS folgende 8 Suchen aus:
1. `SAP S/4HANA release`
2. `SAP Cloud ERP announcement`
3. `SAP quarterly results`
4. `SAP logistics SCM news`
5. `SAP news today`
6. `SAP press release`
7. `SAP partnership announcement`
8. `news.sap.com latest`
Erwartete Rohtrefferzahl: 40–80 Treffer. Wenn weniger als 30, weitere Suchen
(`SAP BTP`, `SAP Joule AI`, `SAP Datasphere`).

## Schritt 3: Roh-Inventur
Erstelle eine interne Tabelle ALLER gefundenen Treffer mit Titel, URL, Datum (falls genannt),
Quelle (Domain). Zähle: Anzahl Roh-Treffer = N.

## Schritt 4: Themen-Filter
Behalten:
- Neue Releases & Produktankündigungen
- Neue Funktionalitäten / Features
- SAP Cloud (Public/Private), Cloud ERP, S/4HANA
- Logistik / SCM / TM / EWM
- Umsatzzahlen, Quartalsberichte, Geschäftserfolge, strategische Partnerschaften
Ausschließen:
- reine Meinungsartikel, Marketing-Blogposts ohne News-Wert
- ältere News, die nur neu indexiert wurden
- Treffer ohne verifizierbares Datum innerhalb der letzten 24 h

## Schritt 5: Validierung (PFLICHT)
Für JEDEN verbleibenden Treffer:
1. URL per web_fetch aufrufen.
2. Datum verifizieren (letzte 24 h, Referenz JETZT).
3. Titel und Inhalt verifizieren.
4. Bei Abweichung → ausschließen.

## Schritt 6: Deduplizierung
Duplikat, wenn EINES zutrifft:
- identische URL zu Vergleichsliste
- Titel ≥80 % übereinstimmend
- gleiche Kernaussage/Ereignis
Mehrfachberichterstattung auf EINE Meldung reduzieren — bevorzugt Primärquelle.

## Schritt 7: Ausgabe (Deutsch)
Beginne mit:
- "Stand: <JETZT> Europe/Berlin"
- "Zeitfenster: letzte 24 Stunden"
- "Vergleichsbasis: <Dateiname> (gefunden / nicht gefunden)"

Pro News-Item:
- **Titel** (deutsch)
- Datum (verifiziert) & Quelle (Domain)
- 2–3 Sätze: Kernaussage + Relevanz für SAP-Beratung
- Direkter Link (validiert)

Wenn keine neuen News: "> Du bist auf dem aktuellen Stand."

Am Ende IMMER:
- Roh-Treffer gesamt: N
- Nach Themen-Filter: M
- Nach Validierung: V
- Nach Deduplizierung (= neu): X

## Schritt 8: Speichern
Der Speichern-Schritt wird vom Python-Wrapper übernommen.
Gib einfach das vollständige Markdown als deine finale Antwort aus.

## Kontext
Die Nutzerin ist SAP-Beraterin und nutzt diese Übersicht zur täglichen Marktbeobachtung.
