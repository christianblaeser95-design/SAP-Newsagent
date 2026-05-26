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

### Teil A — 8 generische Suchen (PFLICHT, nicht weniger):
1. `SAP S/4HANA release`
2. `SAP Cloud ERP announcement`
3. `SAP quarterly results`
4. `SAP logistics SCM news`
5. `SAP news today`
6. `SAP press release`
7. `SAP partnership announcement`
8. `news.sap.com latest`

### Teil B — Pro Quelle eine `site:`-Suche (PFLICHT, eine Suche je Quelle):

Diese kuratierten Quellen liefern den Mix aus SAP-eigenen und unabhängigen
Perspektiven. Führe für JEDE eine gezielte Suche aus:

**SAP-nahe Fachpresse (Prio 2):**
9. `SAP site:sapinsider.org`
10. `SAP site:erp.today`
11. `SAP site:diginomica.com`

**Etablierte Enterprise-IT-Journalismus (Prio 3, nur SAP-spezifische Artikel):**
12. `SAP site:computerweekly.com`
13. `SAP site:siliconangle.com`
14. `SAP site:theregister.com`

**Deutschsprachige Tech-/Wirtschaftspresse (Prio 3, nur SAP-spezifisch):**
15. `SAP site:heise.de`
16. `SAP site:handelsblatt.com`

Erwartete Rohtrefferzahl gesamt: **50–100 Treffer**. Wenn weniger als 30,
weitere Suchen mit Synonymen (`SAP BTP`, `SAP Joule AI`, `SAP Datasphere`).

### Verbindlich:
- Aus den Treffern müssen am Ende **mindestens 2 Items aus Prio-2- oder
  Prio-3-Quellen** in die finale Liste kommen, sofern verfügbar.
- Wenn eine Quelle in der Woche keinen relevanten Artikel hat: kein Zwang,
  einen mittelmäßigen aufzunehmen — Qualität geht vor Quote.

Themen-Priorität für Auswahl / Reihenfolge in der Ausgabe siehe Schritt 4
(SD / Order-to-Cash zuerst, dann Cloud/AI/Integration, dann Sonstiges).

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

Pro News-Item — VERBINDLICHES Format:
- **Titel** (deutsch)
- Datum (verifiziert) & Quelle (Domain)
- 1–2 Sätze Kernaussage (was passiert ist, worum geht es)
- **PFLICHT:** Ein separater letzter Satz, der wörtlich mit
  `**Relevanz für SAP-Beratung:**` beginnt und eine Beratersicht liefert:
  Was bedeutet diese News konkret für laufende oder geplante SAP-Projekte?
  Welche Module, Rollen, Entscheidungen sind betroffen?
- Direkter Link (validiert) — IMMER als Markdown-Link formatieren:
  `[domain.com](https://volle-url)` (NICHT die nackte URL ausgeben)

Beispiel-Item:

> **SAP übernimmt Dremio**
>
> Datum: 2026-05-04 | Quelle: news.sap.com
>
> SAP hat die Übernahme von Dremio vereinbart, einer offenen
> Data-Lakehouse-Plattform auf Basis von Apache Iceberg.
>
> **Relevanz für SAP-Beratung:** Beeinflusst Datenstrategie-Entscheidungen
> bei hybriden Landschaften (SAP + Non-SAP) und macht offene Lakehouse-Formate
> zur strategischen Option für Business Data Cloud.
>
> [news.sap.com](https://news.sap.com/2026/05/sap-to-acquire-dremio-...)

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
