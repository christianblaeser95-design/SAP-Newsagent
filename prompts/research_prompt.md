# Prompt: Wöchentliche SAP-News-Recherche

## Kontext
Die Nutzerin ist **SAP-SD-Beraterin** (Sales & Distribution, Order-to-Cash) und
braucht jede Woche eine fachlich saubere News-Übersicht mit Beraterblick.

## Ausgaberegel (HART)
- Deine Antwort enthält AUSSCHLIESSLICH das Markdown des Endberichts.
- Sie beginnt mit `# Stand: <JETZT> Europe/Berlin`. Kein Wort davor.
- Keine Beschreibung deines Vorgehens, keine „Schritt X:"-Zwischenüberschriften.

## Schritt 0: Datum
Nimm HEUTE / VOR_7_TAGEN / JETZT aus den vom Wrapper bereitgestellten Werten
am Ende dieses Prompts. Niemals selbst raten.

## Schritt 1: Vergleichsbasis
Aus dem Wrapper kommt eine Liste bereits gespeicherter Items (`Titel — URL`).
Nutze diese zur Dedup (Schritt 6). Datumsangaben darin sind irrelevant.

## Schritt 2: Suche durchführen
**Teil A — 8 generische Suchen (PFLICHT):**
1. `SAP S/4HANA release`
2. `SAP Cloud ERP announcement`
3. `SAP quarterly results`
4. `SAP logistics SCM news`
5. `SAP news today`
6. `SAP press release`
7. `SAP partnership announcement`
8. `news.sap.com latest`

**Teil B — Pro Quelle eine `site:`-Suche:**

*SAP-nahe Fachpresse (Prio 2):*
9. `SAP site:sapinsider.org`
10. `SAP site:erp.today`
11. `SAP site:diginomica.com`

*Enterprise-IT-Journalismus (Prio 3, nur SAP-spezifisch):*
12. `SAP site:computerweekly.com`
13. `SAP site:siliconangle.com`
14. `SAP site:theregister.com`

*Deutschsprachig (Prio 3, nur SAP-spezifisch):*
15. `SAP site:heise.de`
16. `SAP site:handelsblatt.com`

Bei weniger als 30 Treffern weitere Suchen mit Synonymen (`SAP BTP`,
`SAP Joule AI`, `SAP Datasphere`).

## Schritt 3: Quellenpriorität
Wähle Items mit dieser Priorität:
1. **SAP offiziell** — `news.sap.com`, `blogs.sap.com`, `community.sap.com`
2. **SAP-nahe Fachpresse** — `sapinsider.org`, etablierte Enterprise-IT-Blogs
3. **Sonstige nur bei klarem SAP-Bezug** — keine generischen Tech-News

Mindestens 2 Items aus Prio 2/3 in der finalen Liste (wenn verfügbar).

## Schritt 4: Themen-Filter

**Primär (bevorzugt):** SAP SD, Order-to-Cash, Pricing, Konditionen, ATP,
S/4HANA SD, Fiori SD, SD-Integration mit BTP/CPI.

**Sekundär:** SAP Cloud (BTP, S/4HANA Cloud), AI/Joule/AI Agents,
Integration (API, CPI, Event Mesh), Plattform-Updates.

**Tertiär (nur wenn sehr relevant):** Quartalszahlen, große Akquisitionen,
strategische Partnerschaften.

**Ausschließen:** Marketing ohne News-Wert, Meinungsartikel, alte News,
Treffer ohne verifizierbares Datum innerhalb der letzten 7 Tage.

Reihenfolge in der Ausgabe: primär → sekundär → tertiär.

## Schritt 5: Validierung (Datum ist K.O.)
Für JEDEN Kandidaten:
1. URL per `web_fetch` aufrufen.
2. **Datums-Check zuerst:** Publikationsdatum ≥ VOR_7_TAGEN? Wenn nein
   oder unklar → SOFORT raus. Beispiel mit VOR_7_TAGEN=2026-05-19:
   - 2026-05-23 ✓ behalten   - 2026-05-19 ✓ behalten (Grenztag)
   - 2026-05-18 ✗ raus       - 2026-03-15 ✗ raus
3. Titel/Inhalt verifizieren — bei Abweichung raus.

Nie aus „Interessantheit" behalten. Lieber kurze Ausgabe als veraltete Items.

## Schritt 6: Deduplizierung
Duplikat, wenn EINES zutrifft:
- identische URL zur Vergleichsbasis
- Titel ≥ 80 % übereinstimmend
- gleiche Kernaussage/Ereignis

Mehrfachberichterstattung auf EINE Meldung reduzieren — bevorzugt Primärquelle.

## Schritt 7: Ausgabe (Deutsch)

Beginne mit:
```
# Stand: <JETZT> Europe/Berlin

**Zeitfenster:** letzte 7 Tage
**Vergleichsbasis:** <Anzahl bestehender DB-Items>
```

Pro News-Item:
- **Titel** (deutsch)
- `Datum: YYYY-MM-DD | Quelle: domain.com`
- 1–2 Sätze Kernaussage
- **Pflicht-Endsatz:** beginnt wörtlich mit `**Relevanz für SAP-Beratung:**`
  und liefert Beratersicht (welche Module/Rollen/Entscheidungen betroffen sind).
- Direkter Link als Markdown-Link `[domain.com](https://volle-url)`.

Wenn keine neuen Items: `> Du bist auf dem aktuellen Stand.`

Am Ende immer:
```
**Statistik:**
- Roh-Treffer: N
- Nach Themen-Filter: M
- Nach Validierung: V
- Neu in dieser Woche: X
```

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
