# Einmalbezüge 2026: Quellen, Jahresvorträge und geplanter v6-Vertrag

Stand: 03.11.2026. P5 ist laufende Implementierungsarbeit. Die folgenden
Anforderungen beschreiben die eigene neue Regelversion; gespeicherte v1–v5
werden nicht geändert. Die endgültige v6-Kennung und Registrierung vergibt
die Integration. Ein vorbereitetes Referenzpaket bedeutet noch keine fertige
Abrechnung, API oder Meldeanbindung.

## Quellen und Zugriff

| Kürzel | Originalquelle | Gelesener Umfang / Verwendung |
|---|---|---|
| T1 | [BMF PAP 2026, endgültig 12.11.2025, Anlage 1](https://www.ihk-muenchen.de/ihk/documents/Recht-Steuern/Steuerrecht/Einkommensteuer/2025-11-12-PAP-2026-anlage-1.pdf) | Amtliches Dokument auf IHK-Host; Eingaben S. 3–5, Sonderzweige S. 33–37, allgemeine Jahrestabelle S. 39 |
| T2 | [§ 39b Abs. 3 EStG](https://www.gesetze-im-internet.de/estg/__39b.html) | Jahreslohnschätzung und sonstiger Bezug; vollständiger Webtext gelesen, späterer Abruf zeitweise Timeout |
| T3 | [§ 3 SolzG 1995](https://www.gesetze-im-internet.de/solzg_1995/__3.html) | Jahresfreigrenzen und Bemessungsgrundlage |
| S1 | [§ 23a SGB IV](https://www.gesetze-im-internet.de/sgb_4/__23a.html) | Volltext über Suchindex; direkter Abruf wiederholt Timeout |
| S2 | [DRV GRA zu § 23a SGB IV](https://rvrecht.deutsche-rentenversicherung.de/SharedDocs/rvRecht/01_GRA_SGB/04_SGB_IV/pp_0001_25/gra_sgb004_p_0023a.html) | Abschnitte 2–4: Begriff, Zuordnung, Märzklausel, Statuswechsel, SV-Tage und bereits verbeitragtes Entgelt |
| S3 | [DRV Beiträge 2026](https://www.deutsche-rentenversicherung.de/SharedDocs/Downloads/DE/Fachliteratur_Kommentare_Gesetzestexte/summa_summarum/e_paper_und_broschueren/broschueren/beitraege.pdf?__blob=publicationFile&v=10) | S. 14–20: Unterbrechung, Zuordnung und amtliches Zahlenbeispiel; S. 35–36: Umlagen |
| Y1 | [Sozialversicherungsrechengrößen-Verordnung 2025](https://www.gesetze-im-internet.de/svbezgrv_2025/BJNR16D0A0024.html) | §§ 2, 4 und 5: echte 2025-Werte und Wirksamkeit |
| Y2 | [PBAV 2025](https://www.gesetze-im-internet.de/pbav_2025/BJNR1BE0A0024.html) | § 1: Pflegebeitrag 3,6 % ab 01.01.2025 |
| Y3 | [DRV Zahlen und Tabellen, Stand 17.06.2025](https://www.deutsche-rentenversicherung.de/SharedDocs/Newsletter/DE/Rheinland/Fachinfos/25-03-nl-fachinfo-pdf.pdf?__blob=publicationFile&v=2) | S. 2–3 und 5: Beitragssätze, 2025-BBG, Minijobgrenze |
| Y4 | [BMG Finanzierung der Pflegeversicherung](https://www.bundesgesundheitsministerium.de/themen/pflege/online-ratgeber-pflege/die-pflegeversicherung/finanzierung) | Arbeitnehmer-/Arbeitgeberanteile, Sachsen und Kinderabschläge seit 2025 |

PDF-Inhalte wurden über den Web-Textauszug geprüft. Original-PDF oder amtliches
XML wurden in diesem Arbeitsschritt nicht heruntergeladen. Der direkte
Download des PAP vom IHK-Host lieferte HTTP 403; PDF-Screenshotzugriff war nicht
verfügbar. Die Referenzen sind daher keine behauptete Prüfung von Originalbytes
oder Softwarezertifizierung. Gesetzestexte und Tabellen werden mit Datum und
Fundstelle gebunden. Eine später geänderte Webdatei ersetzt keinen gespeicherten
Regelstand.

## Steuerliche Eingaben und Rechnung

Steuerlicher sonstiger Bezug und sozialversicherungsrechtliches einmaliges
Arbeitsentgelt sind getrennte Einstufungen. Eine verspätete Monatsvergütung
wird nicht allein wegen des Zahlungsabstands zum SV-Einmalbezug. Der Fall muss
beide Einstufungen und die zugehörigen Anspruchsquellen enthalten.

Der steuerliche Berechner benötigt folgende hergeleitete Größen:

| Größe | Herkunft / Prüfung |
|---|---|
| `JRE4` | Tatsächlicher bisheriger laufender Jahreslohn, belegte Vorschau des restlichen laufenden Jahreslohns und bereits erhaltene sonstige Bezüge; aktueller sonstiger Bezug ausgeschlossen |
| `SONSTB` | Konkret bewilligter Bezug mit Zuflussdatum, Brutto und Anspruchsoriginal |
| `JFREIB`, `JHINZU` | Ausdrückliche Jahreswerte der gültigen Steuermerkmale; keine unbelegte Multiplikation eines Monatswerts |
| `KVZ` | Tatsächlicher Zusatzbeitrag der maßgebenden Krankenkasse zum Ende des Zuflussmonats, kein durchschnittlicher Ersatzwert |
| Steuer-/Kinder-/PV-Merkmale | Exakte gültige Identitäts-/Profilfassung; Kinderfreibetrag und Pflegekinderabschlag getrennt |
| Frühere Arbeitgeber | Belegte Vorbezüge oder ausdrücklich dokumentierte gesetzliche Schätzung nach § 39b Abs. 3; fehlender Nachweis ist keine Null |

MSONST ermittelt `STS` aus der Jahressteuer vor und nach dem aktuellen Bezug.
`BKS` folgt im allgemeinen Zweig mit Kirchensteuerpflicht dem `STS`. `SOLZS`
verwendet dagegen die eigene Jahresfreigrenzenprüfung des MSOLZSTS und danach
5,5 % von `STS`, auf Cent abgeschnitten. Es ist keine Differenz zweier jährlicher
Solidaritätszuschläge. Kindermerkmale können die Freigrenzenprüfung ändern.
Die kirchliche Maßstabsteuer ist noch nicht der landesspezifische Zahlbetrag.

Der erste isolierte Teilzweig soll die bereits vorhandenen allgemeinen
PAP-Voraussetzungen verwenden: gesetzliche KV/RV/AV, Steuerklassen I–VI,
kein Faktor, Altersentlastungsbetrag, Versorgungsbezug oder Auslandsbezug.
`MBV`, `JRE4ENT`, `SONSTENT`, `JVBEZ`, `VBS` sind ausdrücklich null. Diese
Einschränkung ist eine Implementierungsgrenze dieses Teilzweigs; die übrigen
Fälle bleiben im Gesamtziel offen und werden nicht durch einen Standardwert
als unterstützt ausgegeben.

## Quellenvertrag für Jahres- und Periodenfakten

Der neue Lohnlauf bleibt ein kanonischer Abrechnungsfall. Clients liefern keine
gewünschten Steuern, freie Jahressummen oder fertige SV-Luft. Der Fall bindet
neue unveränderliche Fakten mit `id`, `revision`, `content_hash`, Vorgänger,
Originalbelegen, Personenfassung und rechtlicher Arbeitgeberidentität.

```text
one_off_earning
  employee_ref, employer_legal_identity_ref, employment_terms_refs[]
  entitlement_kind, entitlement_periods[], entitlement_source_refs[]
  gross_minor, tax_classification, social_classification
  planned_receipt_date, actual_receipt_ref|null
  origin_allocations[]  # konkrete Anspruchsanteile bei Statuswechsel
  source_file_ids[], verification_note

annual_history
  employee_ref, employer_legal_identity_ref, year, coverage_to
  employment_episodes[], covered_intervals[], explicit_gap_facts[]
  payroll_period_refs[], imported_period_fact_refs[]
  earlier_one_off_allocation_refs[], corrections_superseding_refs[]
  completeness_assertion, source_file_ids[]

imported_period_fact
  period_from, period_to, actual_employment_episode_ref
  original_payroll_document_refs[], original_report_refs[]
  tax_year, social_year, original_rule_version, original_rule_hash
  earnings[]             # laufend / sonstig; Steuer-/SV-Einstufung getrennt
  social_assessments[]    # je tatsächlichem Statusintervall und Zweig
  tax_periods[]           # LZZ und tatsächlich verwendete Steuermerkmale
  status_refs[], fund_rate_refs[], source_file_ids[]

annual_tax_forecast
  employee_ref, receipt_date, annual_history_ref
  previous_employer_certificate_refs[] | statutory_estimation_fact_ref
  remaining_running_earnings[]  # Intervall, Vertrag, Art, Betrag, Herleitung
  annual_allowance_identity_ref, month_end_fund_rate_ref
  source_file_ids[], verification_note
```

Die Namen sind ein abgestimmter fachlicher Entwurf, noch kein registriertes
HTTP-Schema. Die konkrete strikte JSON-Form wird vor Clientintegration fixiert.
`source_file_ids` allein sind keine Inhaltsprüfung: interne Quellen werden
gegen ihre kanonischen unveränderlichen Aufträge/Läufe rekonstruiert; importierte
Vorträge benötigen Originaldatei, geprüfte strukturierte Werte und eine eigene
angenommene Revision. Ein selbstkonsistenter Fremdhash genügt nicht.

V5 liefert laut Berechnervertrag `earnings`, `social_assessments` und
`tax_periods`. P5 übernimmt diese über genaue historische Laufrevisionen,
nicht über den jeweils neuesten Lauf. Externe 2025-Vorträge verwenden denselben
fachlichen Inhalt, aber ausdrücklich eigene Originalbelege und 2025-Regeln.
Interne und importierte Abschnitte dürfen sich nicht doppeln. Fehlende Monate,
ungeklärte Beschäftigungslücken und widersprüchliche Summen sperren die neue
Verwendung. Eine bestätigte Nichtbeschäftigung ist ein Fakt und keine implizite
Null, die durch eine leere Liste entsteht.

`social_assessments` muss je Zweig die SV-Tage, tatsächliche beitragspflichtige
Basis, ausgeschöpfte BBG, Beitragsgruppe, Kasse und Beitragsfaktoren enthalten.
Oberhalb der BBG liegendes Brutto wird nicht als verbrauchte SV-Luft gezählt.
Bereits zugeordnete Einmalbezüge werden genau einmal verbraucht. Der laufende
Anteil des aktuellen Monats ist vor der neuen Einmalzahlung einzubeziehen und
darf nicht zugleich über einen alten wirksamen Monatslauf doppelt eingehen.

## Sozialversicherungsjahr, SV-Luft und Märzklausel

Aus S1/S2 folgen verbindliche Prüfschritte:

1. Anspruchsart und Beschäftigungsabschnitt bestimmen. Ein Wechsel von regulär
   zu geringfügig kann eine belegte Aufteilung nach Anspruchsursprung erfordern.
2. Zahlungsdatum und gesetzliche Zuordnung bestimmen, einschließlich letzter
   Periode nach Ende/Ruhen. Vereinfachte Zuordnung zur noch nicht abgerechneten
   Vorperiode benötigt eine ausdrückliche, belegte Entscheidung.
3. Zweigweise SV-Luft aus der anteiligen Jahres-BBG und bereits tatsächlich
   verbeitragten laufenden und einmaligen Entgelten ermitteln.
4. Bei tatsächlicher Zahlung Januar–März den Vorjahresbezug prüfen. Besteht
   gesetzliche KV-Pflicht, entscheidet deren Grenze; sonst die RV-Grenze.
5. Bei ausgelöster Märzklausel den ganzen Bezug einheitlich dem letzten
   Vorjahreszeitraum zuordnen. Kein Wahlrecht nach günstigerem Ergebnis.
6. Tatsächliche Vorjahresbeiträge mit den damaligen Faktoren berechnen. Der
   Steuerzufluss bleibt davon unabhängig 2026.

Volle Monate zählen 30 SV-Tage, Teilmonate ihre maßgebenden tatsächlichen Tage.
Die Jahres-BBG wird zuerst mit den Tagen multipliziert und dann durch 360
geteilt. Die endgültige Cent-Rundung benötigt einen gesonderten Grenzfall.
Zeiten nach § 7 Abs. 3 sowie beitragspflichtige § 23c-Leistungen dürfen nicht
wegen fehlenden normalen Monatslohns pauschal entfernt werden. Beitragsfreie
Unterbrechungen müssen dagegen mit ihrem tatsächlichen Rechtsgrund vorliegen.

Eine Aprilzahlung nach Austritt im Februar wird dem letzten laufenden
Jahreszeitraum zugeordnet; sie löst dadurch keine Märzklausel aus. Beschäftigung
im Vorjahr ohne dortiges beitragspflichtiges Entgelt kann zur Vorjahreszuordnung
mit fehlender SV-Luft führen. Fehlende Vorjahresquellen dürfen niemals durch
2026-Werte oder die Annahme einer beitragsfreien Zahlung ersetzt werden.

Die Umlagen U1/U2 erfassen echte Einmalbezüge nicht. Insolvenzgeldumlage wird
aus ihrer einschlägigen RV-Basis und dem zeitlich richtigen Satz hergeleitet.
Laufende Nachzahlungen, die ausnahmsweise wie ein Einmalbezug bemessen werden,
behalten ihre eigene Umlagenbehandlung und brauchen eine eigene Fallart.

## Tatsächliche 2025-Parameter

| Parameter | 2025 | 2026 zum Vergleich |
|---|---:|---:|
| KV/PV Jahres-BBG | 66.150,00 EUR | 69.750,00 EUR |
| Allgemeine RV/AV Jahres-BBG | 96.600,00 EUR | 101.400,00 EUR |
| KV/PV Monats-BBG | 5.512,50 EUR | 5.812,50 EUR |
| Allgemeine RV/AV Monats-BBG | 8.050,00 EUR | 8.450,00 EUR |
| RV gesamt | 18,6 % | 18,6 % |
| AV gesamt | 2,6 % | 2,6 % |
| KV allgemein, ohne individuellen Zusatz | 14,6 % | 14,6 % |
| PV allgemein | 3,6 % | 3,6 % |
| Minijob Monatsgrenze | 556,00 EUR | 603,00 EUR |

Der tatsächliche Kassen-Zusatzbeitrag wird als historische Quelle gebunden;
der durchschnittliche 2025-Wert ist kein Ersatz. PBAV 2025 ist für den Satz
3,6 % erforderlich: der Gesetzesgrundtext § 55 Abs. 1 allein nennt weiterhin
3,4 %. Die Sonderabführung für Renten im Juli 2025 gilt nicht pauschal für
Arbeitnehmerlohn. Sachsen, Kinderlosenzuschlag und Kinderabschläge brauchen die
für die zugeordnete Periode gültige Personenfassung.

## Zahlenreferenzen und Gegenfälle

`docs/evidence/payroll-oneoff-2026-derived-pap-references.json` enthält die 43
unabhängig gelesenen allgemeinen BMF-Jahrestabellenzeilen und 252 daraus nach
MSONST abgeleitete Sonderbezugsfälle über alle sechs Steuerklassen. Die
Sonderbezugsfälle sind eigene Ableitungen; BMF hat diese 252 Kombinationen
nicht als Bonustabelle veröffentlicht. Die besondere Jahrestabelle auf S. 40
ist eine andere Versicherungsannahme und keine Einmalbezugstabelle.

Ein wichtiger Gegenfall ist JRE4 90.000 EUR, SONSTB 2.500 EUR, Klasse I nach
den allgemeinen Tabellenbedingungen: Jahressteuer 19.438 → 20.390 EUR;
STS 952 EUR, SOLZS 52,36 EUR. Die Differenz der jährlichen Soliwerte würde
hier fälschlich nur 4,76 EUR liefern. Der nächste Schritt 92.500 → 95.000 EUR
ergibt STS 953 EUR und SOLZS 52,41 EUR; die halbe Centstelle wird abgeschnitten.

S3 veröffentlicht das eigenständige Zahlenbeispiel: Eintritt 01.02.2026,
laufend 5.600 EUR monatlich, Urlaubsgeld Juni 1.500 EUR. Bei 150 SV-Tagen und
28.000 EUR bereits beitragspflichtigem Lohn beträgt die KV/PV-Teil-BBG
29.062,50 EUR und die RV/AV-Teil-BBG 42.250 EUR. Vom Urlaubsgeld sind somit
1.062,50 EUR in KV/PV und 1.500 EUR in RV/AV beitragspflichtig.

Zusätzliche notwendige Gegenproben: genau erreichte versus einen Cent
überschrittene Märzklauselgrenze; keine Vorjahresbeschäftigung; Zahlung am
31.03. versus 01.04.; frühere Einmalzahlung; unterschiedliche Kassen-/PV-Fakten
2025 und 2026; Vorjahres-BBG vollständig ausgeschöpft; § 7 Abs. 3-Fortbestand;
echter Statuswechsel; zwei Zahlungen am selben Tag; Korrektur einer bereits
verbrauchten Vortragsquelle; alte Regeln nach Restore unverändert.

## Auszahlung, Korrektur und Fortschritt

Geplanter Zufluss reicht für eine Vorschau. Die tatsächliche Auszahlung muss
den angenommenen Zuflussfall bestätigen. Abweichung von Datum, Jahr oder
Betrag verlangt einen neuen nachvollziehbaren Fall; die Cash-/Bankspur darf
nicht rückdatiert werden. Anspruch, Brutto, Steuer, SV, Netto und tatsächliche
Zahlung bleiben getrennt. Eine Einmalzahlung darf nicht zugleich über einen
eigenen Zahlungsweg und das Lohnnetto ausgezahlt werden.

Die Annahme reserviert konkrete Einmalbezugs- und Vortragsrevisionen. Korrekturen
zeigen betroffene spätere SV-Luft-Verwendungen und Jahresfassungen an und
erfordern deren nachvollziehbare Neubewertung. Historische Läufe, Belege und
Zahlungen bleiben erhalten. Neue Verwendung verlangt frische Rechte, aktuelle
kanonische Quellen und einen eindeutigen Journalstand; Replay verwendet den
ursprünglich angenommenen Zustand mit frischen Rechten.

| Teil | Stand |
|---|---|
| Amtliche PAP-/SV-/2025-Quellen | gelesen, Zugriffsbeschränkungen dokumentiert |
| 252 abgeleitete PAP-Referenzen | gegen eigenen isolierten Sondersteuerkern grün |
| Amtliches SV-Luft-Zahlenbeispiel | unabhängig festgehalten |
| Jahres-/Periodenvertrag | Striktes Schema implementiert und global registriert: [Jahresbasis-Vertrag](CRM_ERP_LOHN_JAHRESBASIS_VERTRAG_2026.md) |
| Allgemeiner Sondersteuerkern | `payroll_pap_oneoff_2026.py`: 8 eigene Tests plus 4 unabhängige Gegenfälle grün |
| SV-Luft/Märzklausel/2025-Rechnung | Isolierter Kern implementiert; 23 Tests einschließlich tatsächlicher Beitragsanteile grün, vollständige Quellenkomposition noch offen |
| Minijobprognose / Midijob-Einmalbezüge | Isolierte Prognose, unvorhersehbare Überschreitung, RV-Mindestbasis und Beitragsdifferenzen implementiert; eigene private Statusquellen und v6-Verknüpfung offen |
| Private Jahresfakten | 15 Domain- und 2 Jahreswechseltests grün; tatsächliche v5-Quellen und konkrete Lohnkontozuflüsse gebunden |
| HTTP / PostgreSQL / Restore | 2 HTTP- und 3 PG-Fälle global registriert grün; additive Migration, parallele Annahme, echte Sicherung/Wiederherstellung und Originalbytes geprüft |
| v6, Clients, Lohnkonto, Cash/EÜR | Neue Gesamtintegration offen; vorbereitete Jahresquellen sind noch keine vollständige Einmalabrechnung |

Der isolierte Lauf mit den 8 neuen und 3 unveränderten bestehenden PAP-Tests
ist grün (11/11; darunter 252 abgeleitete Sonderbezüge und 258 amtliche
Jahreswerte). Protokoll und Dateihashes stehen in
`docs/evidence/payroll-oneoff-pap-2026-11-03.txt` und `.json`. Zusätzliche eigene
Fälle sichern die Soli-Freigrenze einschließlich Gleichheit, Kinderwirkung,
Mitgliedschaft, Nullbezug und Centabschneiden. Die unabhängige PAP-Gegenprüfung
ergänzt Jahresfreibetrag/Hinzurechnung, einen Cent an der Steuerstufe,
Klasse-III-Rundung und die RV-Jahres-BBG. Die vollständige
SV-/Fakten-/Zahlungskette ist damit noch nicht abgeschlossen.

Die unabhängige Jahresquellenprüfung fand einen konkreten Vollständigkeitsfehler:
Ein 2026 zugeflossener, der SV-Periode Dezember 2025 zugeordneter Einmalbezug
konnte in der Jahressteuerprognose fehlen. Die neue Prüfung verlangt nun alle
bekannten tatsächlichen Steuerzuflüsse außerhalb der gewählten SV-Jahresbasis.
Sie werden nicht still ergänzt; fehlende Originalreferenzen sperren die
Bestätigung. Der unabhängige Gegenfall und das ursprüngliche Ergebnis bleiben
als Prüfnachweis erhalten. Die globale Registrierung ist abgeschlossen; der
finale Lauf mit 56 Kern-/Domänen-/Gegentests, zwei HTTP- und drei PG-Fällen
bestand nach dem Fix. Der letzte PG-Lauf setzt echte globale Registrierung
voraus. Nachweis: `docs/evidence/payroll-annual-integrated-2026-11-03.json`.

Einzelne noch offene Rechenfälle sind eigene Softwarearbeit innerhalb des
Gesamtziels. Sie werden nicht als externe Anbindung umbenannt.
