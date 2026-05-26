# Prompt: Wöchentliche SAP-News-Recherche (mit Deduplizierung)

## Ausgaberegel (HARTE REGEL — ÜBER ALLEM)
Die Schritte 0–6 sind **interne Arbeitsschritte**. Führe sie still aus.
Deine ANTWORT enthält AUSSCHLIESSLICH das Markdown aus Schritt 7 — sonst nichts.

VERBOTEN in deiner Antwort:
- Sätze wie "Ich führe jetzt die Recherche durch", "Schritt X:", "Jetzt validiere ich..."
- Zwischenüberschriften wie "**Schritt 0**", "**Schritt 1**" etc.
- Aufzählung der durchgeführten Suchen
- Jegliche Beschreibung deines Vorgehens

Deine Antwort MUSS mit der Zeile `# Stand: <JETZT> Europe/Berlin` beginnen. Kein Wort davor.

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
- VOR_7_TAGEN = HEUTE minus 7 Tage = YYYY-MM-DD
- JETZT = YYYY-MM-DD HH:MM Europe/Berlin

Verwende von hier an NUR noch diese drei Werte.

## Schritt 1: Vorherige Datei einlesen (Inhalt OK, Datum IGNORIEREN)
- Suche die neueste vorhandene `sap_news_*.md`-Datei (= letzte wöchentliche Ausgabe).
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
- Treffer ohne verifizierbares Datum innerhalb der letzten 7 Tage

## Schritt 5: Validierung — DATUM IST K.O.-KRITERIUM

Für JEDEN verbleibenden Treffer:
1. URL per web_fetch aufrufen.
2. **DATUMS-PRÜFUNG (zuerst, hart):**
   - Lies das Publikationsdatum vom Artikel.
   - **Vergleich:** Publikationsdatum ≥ VOR_7_TAGEN ?
   - **Wenn JA:** behalten.
   - **Wenn NEIN oder Datum nicht eindeutig erkennbar:** SOFORT ausschließen, KEINE Diskussion.
   - Beispiel mit VOR_7_TAGEN = 2026-05-19:
     - Artikel vom 2026-05-23 → behalten (23 ≥ 19)
     - Artikel vom 2026-05-19 → behalten (Grenztag, 19 ≥ 19)
     - Artikel vom 2026-05-18 → ausschließen (18 < 19)
     - Artikel vom 2026-05-12 → ausschließen
     - Artikel vom 2026-03-15 → ausschließen
3. Titel und Inhalt verifizieren.
4. Bei Abweichung → ausschließen.

NIEMALS einen Treffer behalten, nur weil er "interessant" oder "wichtig" ist.
Wenn das Datum älter als VOR_7_TAGEN ist → raus.

## Schritt 5b: ABSCHLUSSPRÜFUNG (vor Ausgabe)

Bevor du Schritt 7 ausführst, gehe deine finale Liste DURCH und prüfe für JEDES Item:
- Ist das Datum ≥ VOR_7_TAGEN? Wenn nicht: streichen.

Diese Prüfung ist nicht optional. Lieber eine kurze Ausgabe ("Du bist auf dem
aktuellen Stand.") als eine lange Ausgabe mit veralteten Treffern.

## Schritt 6: Deduplizierung
Duplikat, wenn EINES zutrifft:
- identische URL zu Vergleichsliste
- Titel ≥80 % übereinstimmend
- gleiche Kernaussage/Ereignis
Mehrfachberichterstattung auf EINE Meldung reduzieren — bevorzugt Primärquelle.

## Schritt 7: Ausgabe (Deutsch)
Beginne mit:
- "Stand: <JETZT> Europe/Berlin"
- "Zeitfenster: letzte 7 Tage"
- "Vergleichsbasis: <Dateiname> (gefunden / nicht gefunden)"

Pro News-Item:
- **Titel** (deutsch)
- Datum (verifiziert) & Quelle (Domain)
- 2–3 Sätze: Kernaussage + Relevanz für SAP-Beratung
- Direkter Link (validiert) — IMMER als Markdown-Link formatieren:
  `[domain.com](https://volle-url)` (NICHT die nackte URL ausgeben)

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
Die Nutzerin ist SAP-Beraterin und nutzt diese Übersicht zur wöchentlichen Marktbeobachtung.
