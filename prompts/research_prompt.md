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

Themen- UND quellenorientierte Suchen. Mindestens diese 8:

**Primärer Themenfokus (SD / Order-to-Cash):**
1. `SAP Sales Distribution SD news` (offen)
2. `S/4HANA Order-to-Cash OR pricing OR ATP` (offen)
3. `SAP Fiori SD apps update` (offen)
4. `SAP BTP CPI SD integration` (offen)

**Sekundärer Themenfokus (Cloud, AI, Integration, Plattform):**
5. `SAP Cloud BTP Joule news` (SAP-Quellen erwartet)
6. `SAP AI agents OR Joule Studio` (SAP-Quellen erwartet)

**SAP-eigene Pressestelle und SAP-nahe Fachpresse:**
7. `news.sap.com latest` (SAP News Center)
8. `SAP site:blogs.sap.com OR site:community.sap.com OR site:sapinsider.org` (SAP-nahe Quellen)

Erwartete Rohtrefferzahl: 40–80 Treffer. Wenn weniger als 30, weitere Suchen
(`SAP Event Mesh`, `SAP Datasphere`, `S/4HANA Cloud SD Fiori update`).

## Schritt 3: Roh-Inventur
Erstelle eine interne Tabelle ALLER gefundenen Treffer mit Titel, URL, Datum (falls genannt),
Quelle (Domain). Zähle: Anzahl Roh-Treffer = N.

## Schritt 3b: Quellenpriorität (PFLICHT)

Bei der Auswahl der finalen Items bevorzuge Quellen in dieser Reihenfolge:

**Priorität 1 — SAP offizielle Quellen:**
- `news.sap.com` (SAP News Center)
- `blogs.sap.com` (SAP Blogs)
- `community.sap.com` (SAP Community)
- `sap.com` (Produktseiten, Whitepapers)

**Priorität 2 — SAP-nahe Analysten- und Fachquellen:**
- `sapinsider.org`
- etablierte Enterprise-IT-Blogs mit SAP-Spezialisierung

**Priorität 3 — Sonstige technische Quellen NUR wenn SAP-bezogen:**
- `erp.today`, `computerweekly.com`, `heise.de`, `siliconangle.com` etc.
- Aufnahme nur, wenn der Artikel substantielle SAP-spezifische Information liefert
  (nicht: allgemeine Tech-News, in denen SAP nur kurz erwähnt wird)

## Schritt 4: Themen-Filter (mit Themen-Priorität)

**Primärer Themenfokus (SEHR WICHTIG — bevorzugt aufnehmen):**
- SAP Sales & Distribution (SD)
- Order-to-Cash Prozesse
- Pricing / Konditionen / ATP (Available-to-Promise)
- S/4HANA SD Funktionen
- Fiori SD Apps
- Integration SD mit BTP / CPI

**Sekundärer Themenfokus (wichtig):**
- SAP Cloud (BTP, S/4HANA Cloud)
- SAP AI / Joule / AI Agents
- Integration (API, CPI, Event Mesh)
- SAP Platform Updates

**Tertiär (nur wenn sehr relevant):**
- Umsatzzahlen, Quartalsberichte, strategische Partnerschaften
- Generelle SAP-Produktankündigungen außerhalb der oben genannten Bereiche

**Ausschließen:**
- Themen ohne klare SD- oder Plattform-Relevanz
- reine Meinungsartikel, Marketing-Blogposts ohne News-Wert
- ältere News, die nur neu indexiert wurden
- Treffer ohne verifizierbares Datum innerhalb der letzten 7 Tage

Reihenfolge in der Ausgabe: Primäre Items oben, sekundäre danach, tertiäre zuletzt.

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
Die Nutzerin ist **SAP-SD-Beraterin** (Sales & Distribution, Order-to-Cash) und
nutzt diese Übersicht zur wöchentlichen Marktbeobachtung. Sie braucht
**fachliche Tiefe in ihren Kernthemen** (SD, Pricing, ATP, Fiori SD, BTP/CPI)
und einen breiten Blick auf SAPs Cloud-, AI- und Plattformstrategie. Kritische
Migrationskommentare oder Konkurrenzanalysen sind explizit NICHT der Fokus.
