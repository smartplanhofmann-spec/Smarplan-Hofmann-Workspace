# Lohn-Zeitachsen und Teilmonate 2026 – P2/P3-Entwurf

Stand des ursprünglichen Entwurfs: 03.11.2026. **Historischer Planungsstand. P2 und P3a sind inzwischen implementiert; der aktuelle Umfang und Nachweis stehen in [P3a-Abnahme](CRM_ERP_LOHN_TEILMONATE_2026.md) und [P2-Abnahme](CRM_ERP_LOHN_FAKTEN_2026.md).** Die folgenden Zukunftsaussagen beschreiben den damaligen Planungsstand; der verbindliche implementierte DTO steht im [API-Vertrag](CRM_ERP_LOHN_ZEITACHSEN_API.md). Midijob-Vollmonate einschließlich Clients sind abgeschlossen und eingefroren; siehe [Kernelabnahme](CRM_ERP_LOHN_MIDIJOB_2026.md) und [Clientabnahme](CRM_ERP_LOHN_MIDIJOB_CLIENTS.md). Der Auftrag bleibt das vollständige Lohnprodukt für reguläre Mitarbeiter und gewerbliche Minijobs. Die folgenden Pakete beseitigen tatsächliche Code-Lücken; eine derzeitige Sperre erklärt einen Standardfall nicht zum dauerhaft ausgeschlossenen Gesamtziel.

## Fachentscheidung und Reihenfolge

P2 ergänzt eine private, unveränderliche Fallhistorie und einen nachprüfbaren Periodenplan. P3 verwendet diesen Plan für Eintritt/Austritt, Teilentgelt, Tages-PAP, Teil-BBG, anteilige Minijob-Mindestbasis und Midijob-Teilmonate. Abwesenheitsansprüche werden als belegte eigene Entscheidung modelliert, anschließend in P4 vollständig berechnet. P5 ergänzt Einmalzahlungen/Jahresvorträge; Reisepauschalen bleiben ein unabhängiger Folgepunkt.

Vorgeschlagene Lieferfolge:

| Paket | Tatsächliches Ergebnis | Abschlusskriterium |
|---|---|---|
| P2 | Fakten, Originalbindung, Beschäftigungs-/Entgelt-/Steuer-/SV-Plan, Historie und Korrekturen; beide Clients | Kein neuer Steuerbetrag nötig; fehlende/überlappende Quellen ergeben präzise offene Punkte |
| P3a | Eintritt/Austritt mit einer inländischen Beschäftigung und unverändertem Versicherungsstatus; Monats- und Stundenentgelt; regulär/Minijob/Midijob | Neue Rechenversion, vollständiges Netto/Lohnkonto/Exporte, effektive Jahresfassung, bestehendes PayrollCash |
| P3b | Mehrere Entgeltvereinbarungen, untermonatiger Kassen-/Beitrags-/Profilwechsel, Wiederaufnahme innerhalb des Monats | Belegte Zuordnung und ereignistypische Rundung aller Segmente, keine durch beliebige Entgeltzeilen erzeugte BBG, Steuermerkmale am Ende des tatsächlichen LZZ |
| P4/P5 | Anspruchsberechnung/Unterbrechungen bzw. Einmalbezüge samt Vorjahresfällen | Eigene fachliche Referenzen und End-to-End-Abnahme; bleiben offen, bis implementiert |

P3a darf keine unbezahlte Abwesenheit als Austritt interpretieren. Ein P4-Fall kann in P2 gespeichert und beurteilt werden; solange sein Anspruchs-/SV-/Steuerzweig fehlt, bleibt die neue Berechnung mit genau diesem Grund unvollständig. Ein pauschaler Bestätigungs-Bool darf die Sperre nicht übergehen.

## Erhobener Quellenstand

| Kennung | Gelesene Quelle und genaue Verwendung |
|---|---|
| Q1 | [BMF PAP 2026, endgültig 12.11.2025, Anlage 1 bei IHK München](https://www.ihk-muenchen.de/ihk/documents/Recht-Steuern/Steuerrecht/Einkommensteuer/2025-11-12-PAP-2026-anlage-1.pdf): S.2 tägliche Berechnung bei abweichendem LZZ; S.3 Rundung nur an bezeichneten Feldern; S.5/6 LZZ/RE4/Freibeträge; S.15 MRE4JL; S.31 Soli/BK; S.32 UPANTEIL; S.39 veröffentlichte Jahres-Prüftabelle. |
| Q2 | Vollständige R39b.5 Abs.1–5, endgültige Veröffentlichung BStBl 2022 Sondernummer 2 vom 05.12.2022: [öffentliche Wiedergabe des endgültigen Hefts](https://media.frag-den-staat.de/files/docs/58/87/65/588765db0e33433fa82243330f2e0feb/bstbl_2022_s2.pdf), PDF-Seite 42. Gegenquelle: [Bundesratsvorlage 455/22](https://dserver.bundestag.de/brd/2022/0455-22.pdf) und [unveränderte Zustimmung 28.10.2022](https://dserver.bundestag.de/brd/2022/0455-22B.pdf). Volltextauszug im Repository, siehe unten. |
| Q3 | [Aktueller LStH-2026-Eintrag R39b.5](https://ao.bundesfinanzministerium.de/lsth/2026/A-Einkommensteuergesetz/VI-Steuererhebung-36-47/2-Steuerabzug-vom-Arbeitslohn-Lohnsteuer-38-42g/Paragraf-39b/r-39b-5.html), [Einführung](https://usth.bundesfinanzministerium.de/lsth/2026/A-Einkommensteuergesetz/Einfuehrung/inhalt.html): indexierter aktueller Richtlinienstand gegengeprüft; direkte HTML-Abfrage weiterhin 503. Q2 ist vollständig gelesen, ein erfolgreicher Vollabruf von Q3 wird nicht behauptet. |
| Q4 | [DRV Beiträge 2026](https://www.deutsche-rentenversicherung.de/SharedDocs/Downloads/DE/Fachliteratur_Kommentare_Gesetzestexte/summa_summarum/e_paper_und_broschueren/broschueren/beitraege.pdf?__blob=publicationFile&v=10), Abschnitte 1.3–1.4, S.12–14: 30 Tage bei Vollmonat, tatsächliche Teilmonatstage, Teil-BBG und Unterbrechung. |
| Q5 | [Gemeinsames Übergangsbereichs-Rundschreiben 20.12.2022](https://www.kbs.de/SharedDocs/Downloads/DE/VersicherungsrechtBeitraegeMeldungen/Downloads/Uebergangsbereich_idF_20_12_2022.pdf?__blob=publicationFile&v=2), 4.3.2.5 S.23/24, 4.3.3.5 S.28, Beispiele 6/7b S.42/43: Teilentgelt-Hochrechnung, ausdrücklich abweichende Vertragsquotienten, unbezahlter Urlaub ohne SV-Tagekürzung. Historische Grenzen/F/PV-Sätze werden nicht übernommen. |
| Q6 | [Minijob-Richtlinien 2026](https://www.minijob-zentrale.de/SharedDocs/Downloads/DE/Rundschreiben/Geringfuegigkeitsrichtlinien-2026.pdf?__blob=publicationFile), C3.2.1 S.71/72, Beispiele 29/30 S.117: anteilige Mindestbasis, Fortbestand und Nullentgelt. Beispiel 30 enthält die unten dokumentierte numerische Abweichung. |
| Q7 | [BVV §1](https://rvrecht.deutsche-rentenversicherung.de/SharedDocs/rvRecht/05_Normen_und_Vertraege/02_A-B/BVV/0001/0001_2006_07_01.html) und [BVV §2, geltende Fassung ab 01.01.2025](https://rvrecht.deutsche-rentenversicherung.de/SharedDocs/rvRecht/05_Normen_und_Vertraege/02_A-B/BVV/0002/0002_2025_01_01.html): Rundung und Mindestbeitrags-/Beitragsanteilsfolge. |
| Q8 | [EntgFG §§2–4](https://www.gesetze-im-internet.de/entgfg/BJNR106500994.html), [BUrlG §11](https://www.gesetze-im-internet.de/burlg/__11.html), [SGB IV §7 Abs.3](https://www.gesetze-im-internet.de/sgb_4/__7.html): Grundlage künftiger Anspruchsentscheidungen, nicht bereits implementierte EFZ-/Urlaubsberechnung. |

[R39b.5-Volltextauszug](CRM_ERP_LOHN_R39B5_QUELLENAUSZUG_2026-11-03.txt) ist eine gekennzeichnete Textextraktion mit Herkunft. Es wurde kein Original-PDF im Repository vorgetäuscht. [Numerische Referenzen](CRM_ERP_LOHN_TEILMONATE_REFERENZEN_2026-11-03.json) trennen veröffentlichte Zahlen, aus ihnen unabhängig abgeleitete Werte und eine entdeckte Quellenabweichung.

## Sechs getrennte Zeitachsen

| Achse | Belegte Eingabe | Vom System abgeleitete Ausgabe |
|---|---|---|
| Beschäftigung | tatsächlicher Beginn/Ende, gegebenenfalls mehrere belegte Episoden | inklusive Kalendertagsintervalle; Grenzen gegen Personalstamm und Original geprüft |
| Entgeltanspruch | gültige Vereinbarung, Teilentgeltmethode, Arbeitsplan, Arbeits-/Ausfallzeit und Anspruchsnachweis | laufendes Entgelt je Position, exakter Quotient und Cent-Rundung; keine erfundenen Projektstunden |
| Steuer-LZZ | Zeitraum, für den laufender Lohn gezahlt wird; Dienstverhältnisfortbestand; tatsächlich einschlägige steuerliche Ereignisse | Monat oder einzelne Tage; Kalendertagsanzahl, PAP-Eingaben und zugehörige Steuermerkmale |
| SV | beitragsrechtlicher Status und belegte Unterbrechungsgründe je KV/PV/RV/AV | SV-Tage, Teil-BBG und Beitragsbasen je Zweig; kein Rückschluss allein aus Arbeitsstunden |
| Merkmalgültigkeit | ELStAM-/Bescheinigungs-, Kassen-/Beitrags-/PV- und Minijob-RV-Fassungen | Steuerfassung grundsätzlich zum Ende des LZZ; beitragsrechtliche zeitliche Gültigkeit separat |
| Zahlung/Meldung | tatsächliche Zahlungsteile, Zahlungstag, Abrechnungsabschluss; später echte Meldeereignisse | Lohnkonto, Zahlungsnachweise, Geldfluss/EÜR und tatsächlicher Meldezustand; Berechnung erzeugt keine Zahlung |

Konsequenzen aus der vollständig gelesenen R39b.5:

- Abs.1: Maßgeblich sind grundsätzlich die Steuermerkmale am Ende des LZZ. Ein Profilwechsel erzeugt daher nicht automatisch zwei steuerliche Teilmonate. Vorzeitige Zahlungen und später rückwirkend bekannt gewordene Merkmale brauchen einen belegten Korrekturfall.
- Abs.2: Fortbestehendes Dienstverhältnis mit unbezahlten Arbeitstagen verkürzt den Steuer-LZZ nicht automatisch. Ist der LZZ nicht feststellbar, sind die tatsächlichen Arbeitstage/-wochen die eigenständige Ersatzgrundlage. Nicht inländisch besteuerter Arbeitslohn benötigt seinen eigenen noch offenen DBA-Zweig.
- Abs.3: Ein nicht direkt bereitgestellter Freibetrag wird vom bereits aufgerundeten monatlichen Merkmal abgeleitet; keine erneute freie Jahresverteilung.
- Abs.4: Laufende Nach-/Vorauszahlungen sind grundsätzlich den zugehörigen LZZ zuzuordnen. Sie sind keine zusätzliche gewöhnliche Monatsposition ohne Herkunft.
- Abs.5: Abschläge und endgültige Abrechnung haben eigene Fünf-/Dreiwochenbedingungen; bei Jahreswechsel können Lohnkonto-Zuordnungsjahr und Anmeldungsmonat auseinanderfallen. P3a verarbeitet diese Fälle nicht stillschweigend als normale Zahlung im aktuellen Monat; ihre eigene Umsetzung bleibt erforderlich.

## Fachregeln für den neuen Periodenplan

**Arbeitsentgelt:** Die bestehende Personalvereinbarung liefert Monatsbetrag beziehungsweise Stundensatz. Ein zusätzlicher Originalnachweis bestätigt die Teilentgeltmethode: `calendar_days_actual`, `contractual_30_days`, `scheduled_workdays` oder `scheduled_seconds`. Es gibt keinen Standardquotienten. Kalender-/Arbeitszeit-Zähler und Nenner werden aus Beschäftigung und belegtem Arbeitsplan hergeleitet; der Benutzer bestätigt die Vereinbarung, nicht eine beliebige gewünschte Centzahl. Für eine abweichende individuelle Vertragsformel ist ein eigener prüfbarer Methodenzweig erforderlich. Freigegebene Arbeitszeit bleibt tatsächliche Projektarbeit; bezahlter Feiertag, Urlaub und Krankheit werden separate Entgeltpositionen.

**SV-Tage und BBG:** Bei einem vollständigen Beitragsmonat 30 Tage, sonst die einschlägigen tatsächlichen Kalendertage. KV/PV-BBG 2026: 6.975.000 Cent jährlich; RV/AV: 10.140.000 Cent. Teil-BBG = Jahres-BBG × Tage /360 mit Rundung erst nach der vollständigen Multiplikation. Ein Tag am 31. ist bei einem echten eintägigen Beschäftigungsverhältnis ein SV-Tag. Bei Unterbrechungen wird Fortbestand nach §7 Abs.3 geprüft; ein unbezahlter Arbeitstag darf nicht automatisch einen SV-Tag entfernen. Bloße Entgeltzeilen erzeugen keine zusätzliche BBG. Sachlich notwendige beitragsrechtliche Aufteilungen können dagegen im 31-Tage-Monat insgesamt 31 SV-Tage und entsprechend erhöhte Teil-BBG ergeben. P3b braucht einen typisierten belegten Aufteilungsanlass und dessen eigene Segment-/Rundungsregel; siehe die [unabhängige Gegenprüfung](CRM_ERP_LOHN_TEILMONATE_GEGENPRUEFUNG_2026.md). Eine Februar-Meldeprüfungstoleranz wird nicht als fiktive Abrechnungs-BBG verwendet.

**Tages-PAP:** Ein neuer, ausdrücklich versionierter PAP-Zweig unterstützt `LZZ=4`; die heutige Funktion mit ausschließlich Jahr/Monat und deren Hash bleibt unverändert. Q1 bezeichnet RE4, LZZFREIB und LZZHINZU als ganze Cent. Nach Q1 Abschnitt 3 wird erst bei Übergabe an das entsprechende PAP-Eingabefeld abgeschnitten; unbenannte Zwischenfelder bleiben ungerundet. Der Periodenplan speichert deshalb beim Brutto den exakten rationalen Durchschnitt, den ganzzahligen PAP-Eingabewert und den Rest gesondert. Freibetrag und Hinzurechnungsbetrag haben eine andere Regel: R39b.5 Absatz 3 in Verbindung mit R39a.1 Absatz 7 führt vom bereits aufgerundeten Monatsmerkmal durch Division durch 30 und Aufrundung auf den nächsten durch fünf teilbaren Centbetrag zum hergeleiteten Tagesmerkmal. Dieser Wert wird nicht als unmittelbar vom Finanzamt abgerufen ausgegeben. Das steuerliche Tages-Rechenbrutto ersetzt nicht das tatsächliche auszuzahlende Brutto.

Bei einheitlichem laufendem Entgelt des Teil-LZZ ist die Tagesbasis dessen Gesamtbrutto geteilt durch die steuerlich maßgebenden Tage. Jahreshochrechnung ×360; Rückverteilung der jeweiligen Jahressteuer nach unten auf Cent. Anschließend werden die bereits centgenauen Tagesergebnisse summiert. Einmal `Jahressteuer × Tage /360` zu runden ist nicht gleichwertig. Bei sich unterscheidenden Fällen/steuerlichen Zuordnungen ist kein blindes Zusammenfassen zulässig. Wochen-LZZ bleibt als eigener noch zu prüfender Zweig dokumentiert; er wird nicht durch `Tag ×7` ersetzt.

Die tatsächliche Kirchensteuer bleibt von der PAP-Maßstabsteuer BK getrennt. Für P3 ist die dokumentierte länderrechtliche Rundung auf den tatsächlichen LZZ zu übertragen und mit Fällen zu prüfen, die sich bei täglicher gegenüber abschließender Rundung unterscheiden. Die hier hinterlegten Tagesfälle prüfen BK, nicht eine ungeprüft angenommene Kirchensteuer-Summenrundung.

**Minijob:** RV-Mindestbasis 17.500 Cent × relevante SV-Tage /30; ohne tatsächliches Entgelt im gesamten Monat kein Mindestbeitrag. Der AG trägt 15 % des tatsächlichen Entgelts im gewerblichen Fall; der AN ergänzt den nach BVV ermittelten Mindestbeitrag. RV-Befreiung/Aufhebung wird ab P2 als datierter belegter Lebenslauf vorbereitet; die einmalige Aufhebung ab Juli 2026 mit Folgemonatswirkung darf nicht durch einen beliebigen Profil-Bool simuliert werden.

**Midijob:** Die prognostische Statusentscheidung bleibt vom tatsächlichen Teilentgelt getrennt. Im 30-Tage-Verfahren zunächst Teilentgelt ×30/SV-Tage, daraus beide 2026-Basen, anschließend mit SV-Tagen/30 auf den Teilmonat reduzieren. Q5 Beispiel 7b verlangt bei einer belegten anderen Vertragsaufteilung auch für die reduzierten Basen deren Quotienten: dort 6/19 Arbeitstage, nicht 9/30 Kalendertage. Bei voller SV-Tagezahl und nur unbezahltem Urlaub findet keine fiktive Hochrechnung des Restentgelts statt. Kassenumlagen verwenden die passende reduzierte Gesamt-RV-Basis. Der gesamte Rechenweg einschließlich Zwischenrundungen wird in der neuen Regelversion und Ausgabe festgeschrieben; die bisherige v3-Vollmonatsquelle bleibt identisch.

## Additive Tabellen und unveränderliche Fakten

Vorgeschlagene neue Datei `backend/business_payroll_facts.py`, genau zwei neue Tabellen. Die Originale bleiben in den bereits privaten Personalakten; keine zusätzliche ungeschützte Kopie.

```text
business_payroll_fact_events
  fact_id TEXT, revision INTEGER, employee_id TEXT, kind TEXT,
  effective_from TEXT, effective_to TEXT NULL,
  status TEXT, payload_json TEXT, sources_json TEXT, source_hash TEXT,
  previous_hash TEXT NULL, content_hash TEXT, actor_id TEXT, created_at TEXT
  PRIMARY KEY(fact_id, revision)

business_payroll_fact_requests
  actor_id TEXT, request_id TEXT, operation TEXT, payload_hash TEXT,
  fact_id TEXT, fact_revision INTEGER, fact_content_hash TEXT, created_at TEXT
  PRIMARY KEY(actor_id, request_id)
```

Alle Fachfassungen append-only mit DB-Guards und begründetem Vorgänger. Technische Quittungen speichern nur Referenzen/Hashes; keine zweite vollständige private Fallkopie. Neue Identität `payfact_…`; alle Referenzen enthalten mindestens `id,revision,content_hash`, bei Personalakten zusätzlich `employee_id,sha256`. Ein Ereignis bindet seine vollständigen kanonischen Quellen; aktuelle Quellen werden vor Bestätigung erneut gelesen. Historische Integritätsprüfung verwendet die damaligen Fassungen, niemals heutige Stammdaten.

Drei eng typisierte Arten für P2:

1. `employment_terms`: belegter tatsächlicher Beschäftigungszeitraum, Referenzen auf gültige Entgeltvereinbarungen, Teilentgeltmethode und Vertragsgrund. Kein Überschreiben des Personalstamms; Widerspruch zum aktuellen Stamm muss vor einer neuen Berechnung mit dessen normalem Änderungsweg aufgeklärt werden.
2. `work_schedule`: datierter Sollarbeitsplan mit Datum, Sollsekunden, Arbeitsort/Feiertagsregion, Original und belegten Abweichungen. Für die Teilentgeltquote erforderlich, wenn die gewählte Methode auf Arbeitstagen/-zeit beruht; noch kein automatischer Urlaubs-/EFZ-Anspruch.
3. `period_case`: Monat, Referenzen auf obige Fakten und die bestehende Monatsvorbereitung, Profile/Identitätsbelege, belegte LZZ-Einordnung sowie tatsächlich vorhandene Unterbrechungs-/Anspruchsentscheidungen. Speichert den bestätigten Periodenplan und dessen Quellenhash atomar. Gesetzliche Steuer-/SV-Tage sind berechnete Ergebnisse, keine frei editierbaren Eingabefelder.

Die typisierte Anspruchsentscheidung enthält `kind`, von/bis, Arbeitsplan-/Abwesenheitsreferenz, Rechts-/Vertragsgrund, bezahlte Sollzeit, Vorzeiten-/Fallreferenzen und Original. Zulässige Anfänge: `ordinary_work, public_holiday, vacation, sickness_continued_pay, unpaid_leave, sickness_after_entitlement`. Ein unbekannter oder noch nicht berechenbarer Fall wird fachlich erfasst und als offener Punkt ausgegeben. Diagnosen sind nicht nötig; eine private und vom Verantwortlichen bestätigte Fortsetzungsfallreferenz reicht für spätere Anspruchsprüfung. Widersprüchliche oder doppelt als Arbeits-/Ausfallzeit belegte Stunden werden abgewiesen.

**Datenschutz/Export/Restore:** Sämtliche Fakten sind sensible Personaldaten, geschützt wie Payroll. Kein allgemeiner Assistenz-/Finanzkontext erhält die privaten Zeitachsen oder Krankheitsbelege. Unternehmensexport inventarisiert Fachfassungen; technische Quittungen bleiben technische Daten. Personeninventar bindet Mitarbeiter und Originale, Historie wird nicht still gelöscht. Restore-Horizont bindet beide Tabellen, fachliche Quellenhashes und alle referenzierten Originalhashes. Root registriert Schema/API/Paketlisten/Restore erst nach bestätigtem finalem Vertrag.

## Vorgeschlagene API und Berechnungsintegration

| Route | Verhalten/Recht |
|---|---|
| GET `/business/payroll/facts?employee_id=…&kind=…` | aktuelle Fassungen, `items`, oben `can_write`, `can_approve`; frisches `personnel.read` |
| GET `/business/payroll/facts/{id}` und `/{id}/history` | konkrete Fassung/Historie; keine indirekte Selbstlesefreigabe medizinischer Anspruchsgründe |
| POST `/business/payroll/facts` | `employment_terms/work_schedule`: read+write; `period_case`: read+approve; aktuelle Personalzuordnung, MFA/Onlinegate wie Payroll |
| POST `/business/payroll/periods/preview` | aus ausdrücklich gewählten aktuellen Quellen berechneter Plan; speichert nichts, löst keine Zahlung aus |
| Bestehende Payroll-Vorschau/Finalisierung | zusätzliches vollständig alternatives `source_schema_version=2` mit expliziter `period_case_ref`; bisheriger vollständiger v1-Eingabesatz unverändert |

Mutationsumschlag: `request_id, employee_id, kind, revision, id?, status, details, source_file_ids, confirmed, correction_reason?`. Bei Änderung müssen Vorgänger, Grund und aktuelle Quellen passen; `void` archiviert fachlich, entfernt keine Revision. Die genaue Quellenliste wird serverseitig auf geschützte Originale derselben Person aufgelöst. ACK liefert die unveränderliche bestätigte Fassung; gleiches Nonce+gleicher Inhalt ergibt dieselbe Fassung, anderes Payload bei gleichem Nonce 409. Rechte/MFA/Zuordnung werden **vor** Lesen einer gespeicherten Quittung neu geprüft. Client-Wiederholung prüft per frischem GET die obersten Fähigkeiten; verlorene/ungewisse Antworten bleiben bis zur tatsächlichen Klärung erhalten.

Vorschauausgabe:

```text
{
  schema_version: 1, employee_id, month,
  sources: [{kind,id,revision,content_hash}],
  employment_intervals: [{from,to,calendar_days}],
  earnings: [{kind,agreement_ref,from,to,quantity,ratio,
              gross_minor,tax_classification,social_classification,evidence_refs}],
  tax_periods: [{from,to,lzz,tax_days,profile_ref,tax_evidence_ref,
                gross_minor,daily_input_minor,daily_input_remainder,
                allowance_input_minor,addition_input_minor}],
  social_periods: [{from,to,reason,profile_ref,
                   branches:{health:{days,cap_minor},care:{…},pension:{…},unemployment:{…}},
                   transition_basis,minimum_pension_basis_minor}],
  entitlement_decisions: […],
  blockers: [{code,source_ref,from,to,explanation}],
  plan_hash, can_confirm, can_calculate
}
```

`plan_hash` = SHA256 über kanonischen fachlichen Plan einschließlich Quellreferenzen, ohne Fähigkeiten und ohne eigenen Hash. Fachliche Blocker gehören in den Hash; rollenabhängige Fähigkeiten nicht. Bestätigung schreibt exakt den geprüften Plan. Neue Payrollquelle bindet diesen Plan, seine Faktenfassung und alle historischen Originale. Eine spätere Änderung erfordert neue Fall- und Laufrevision; sie verändert alte PDF/JSON/CSV, Quittungen oder PayrollCash nicht.

Für neue unterstützte Rechnungen eigener Regelname, beispielsweise `de_2026_periods_pap_v4`; genauer Name wird vor Implementierung eingefroren. Existierende v1/v2/v3-Läufe bleiben historisch lesbar und nachrechenbar. Die bekannten Summenfelder für Brutto, LSt, Soli, KiSt, AN-/AG-SV, Umlagen und Netto bleiben erhalten; zusätzliche `period_details` zeigen Teilrechnungen/Rundungen. Korrekturdifferenzen verwenden nur die effektive Vorgängerfassung. Jeder Mitarbeiter/Monat hat weiterhin genau einen wirksamen Lauf; neue Teilsegmente erzeugen keine zusätzlichen parallel gezählten Monatsläufe.

Lohnkontoidentität muss künftig genau den tatsächlichen Beschäftigungs-/Steuerzeitraum decken. Die heutige Vollmonatsprüfung in `business_payroll_accounts._identity` bleibt für alte Quellen erhalten; neuer v2-Quellenzweig validiert die Perioden. Zahlungen referenzieren weiterhin die exakte Laufrevision. Vorträge brauchen denselben Perioden-/Quellenvertrag und nachweisbare Beträge; freie Jahres-Summeneingaben ersetzen keine SV-Historie. Jahresausgabe zählt allein wirksame Revisionen und weist unvollständige Steuer-/Zahlungs-/Anspruchsnachweise sichtbar aus.

## Unabhängige Zahlen und entdeckte Abweichung

Die folgenden Tageswerte sind **aus der amtlichen Jahres-Prüftabelle und der vorgeschriebenen täglichen Verteilung hergeleitet**. Es handelt sich weder um eine vom BMF veröffentlichte gesonderte Tagestabelle noch um Ergebnisse des vorhandenen Produktrechners. Annahmen wie Q1 S.39: gesetzliche Zweige, KVZ 2,90 %, PVZ bei Klasse II 0, sonst 1, keine Freibeträge/Kinderfreibeträge/Sachsen.

| Tagesbrutto EUR | Genau zugehöriges Jahresbrutto EUR | Tages-LSt I / II / III / IV / V / VI, Cent |
|---:|---:|---|
| 125,00 | 45.000 | 1547 / 1224 / 513 / 1547 / 2870 / 3018 |
| 187,50 | 67.500 | 3190 / 2811 / 1778 / 3190 / 4966 / 5113 |
| 250,00 | 90.000 | 5399 / 4951 / 3383 / 5399 / 7318 / 7466 |

17 Tage mit 250 EUR Tagesbrutto ergeben bei Klasse I 917,83 EUR LSt, nicht 917,90 EUR bei verspäteter Gesamtrundung. Klasse VI ergibt 1.269,22 EUR LSt und 36,55 EUR Soli; bei Kirchenmitgliedschaft ist BK 1.269,22 EUR, die Kirchensteuer bleibt eine eigene Berechnung. Zwölf Tage mit 125 EUR in Klasse III ergeben 61,56 EUR LSt. Diese Fälle stehen maschinenlesbar mit 18 Einzel- und vier Mehrtages-/Datumsreferenzen bereit; sie sind noch **nicht** gegen einen neu implementierten Tageskern gelaufen.

DRV-Teil-BBG: 17.–28.02.2026 = zwölf Tage, KV/PV 2.325,00 EUR, RV/AV 3.380,00 EUR. 01.–16.03.2026 = 16 Tage, KV/PV 3.100,00 EUR, RV/AV 4.506,67 EUR.

Minijob Q6 Beispiel 29: 20 Tage, Mindestbasis 116,67 EUR, RV gesamt 21,70 EUR. Das veröffentlichte Beispiel betrifft einen Privathaushalt mit AG 5,00/AN 16,70 EUR; eine gewerbliche Variante muss AG 15,00/AN 6,70 EUR verwenden und wird ausdrücklich als abgeleitete Variante bezeichnet.

**Q6 Beispiel 30 enthält einen Rechenwiderspruch:** Bei 27 SV-Tagen druckt es die zutreffende Basis 157,50 EUR, aber 29,31 EUR RV und 21,81 EUR AN bei 7,50 EUR AG. Exakte Multiplikation 157,50 ×18,6 %=29,295 EUR führt nach BVV-Rundung zu 29,30 EUR bzw. 21,80 EUR AN. Die Zeitachsenreferenz (01.–18. und 23.–31.08., insgesamt 27 Tage) bleibt verwendbar; der gedruckte Betrag darf nicht unbemerkt als korrekte numerische Sollvorgabe übernommen werden. P3 dokumentiert die gesetzliche Herleitung und prüft den Cent-Grenzfall ausdrücklich. Es wurde keine amtliche Korrekturbestätigung eingeholt.

## Verbindliche Abnahmematrix vor Freigabe von P3

| Gruppe | Erforderliche echte Fälle |
|---|---|
| Entgelt/Zeiten | Eintritt/Austritt jeweils Monatsanfang/-ende und eintägig am 31.; Februar; mehrere Vertragsmethoden; exakt ein Cent Rest bei Division; Arbeitsplanänderung; keine Doppelvergütung von Arbeits-/Ausfallzeit |
| Steuer | 18+4 Referenzen oben; Monat bleibt Monat bei fortbestehendem Dienstverhältnis; Tages-Freibetrag vom monatlichen Merkmal; Klassen I–VI; Soli-Milderung; BK mit Kindern; Kirchensteuer-Rundung; Merkmale am LZZ-Ende; fehlender Nachweis sperrt |
| Reguläre SV | beide veröffentlichten Teil-BBG, Sätze/Kassenzusatz, Sachsen, kinderlos/mehrere Kinder, einzelne Tage und hohe Teilentgelte; Zweige getrennt |
| Minijob | Mindestbasis 20/27/30 Tage, Mindestbeitrag-Centgrenze, Nullentgeltmonat, RV-Befreiungswirkung; unbezahlter Urlaub unter/über einen Monat bleibt ausdrücklich eigener Fall |
| Midijob | Teilentgelt unter 603 trotz Midijobstatus; 30-Tage- und dokumentierte Arbeitstagsquote; Grenze nach Hochrechnung; niedriger Restmonat ohne SV-Tagekürzung; reduzierte U1/U2-/Insolvenz-Basis |
| Historie | alte v1/v2/v3-Quellenhashes und Exporte unverändert; rückwirkendes Eintrittsdatum, Profil-/Originaländerung, neuer Fall und eine Laufkorrektur; keine doppelte Jahreszählung |
| Geldfluss | tatsächliche frühere Zahlung bleibt unverändert, Differenzzahlung erfordert eigenen Beleg; PayrollCash/Bank/EÜR ohne künstlichen oder doppelten Geldfluss |
| Rechte/Technik | echte MFA/HTTP, frischer Rechteentzug vor Erst- und Wiederholungsaufruf, zwei PG-Verbindungen, Lost-ACK in beiden Clients, offline gesperrt, echte Dump/Restore-Fachprüfung |
| P3b zusätzlich | mehrere Kassen-/Beitragssegmente, 28/30/31 Tage, ereignistypische Teil-BBG ohne frei erfundene Verdoppelung, aktuelle und historische ELStAM-Wirkung; vor Codefreigabe konkrete Segmentreferenzen ergänzen |

Die vorhandenen 67 Fachtests, 3 neuen und 9 historischen PostgreSQL-Fälle sowie beide Midijob-Clientstrecken werden nach Implementierung als Regression erneut ausgeführt. Quellen- und Referenzprüfung dieses Entwurfs ist kein Ersatz dafür.

Entwurfsprüfung durchgeführt: 18 Tagesreferenzen, vier Mehrtages-/Datumsfälle, zwei Teil-BBG-Paare, die dokumentierte Minijob-Zahlenabweichung, Vollständigkeit aller fünf Richtlinienabsätze und lokale Dokumentlinks. Der Prüfer importiert keinen Produktrechner. Aufruf: `backend/.venv/bin/python work/verification/check-payroll-partial-references.py`; [Prüfstand und Dateihashes](CRM_ERP_LOHN_TEILMONATE_ENTWURF_PRUEFUNG_2026-11-03.json). PostgreSQL wurde dafür nicht verwendet; `git diff --check` ist fehlerfrei.

## Noch zu erledigen, vor neuen Produktbehauptungen

- P2-API/Schemas abstimmen, danach additive Umsetzung und Clientvertrag. Aktuell sind keine neuen Tabellen/Routen/Rechenregeln registriert.
- Tages-PAP und Periodenrechner implementieren; Referenzen gegen den neuen Kern prüfen, PAP-Eingangsrundung mit nicht exakt teilbaren Entgelten und länderrechtliche Kirchensteuer-Verteilung vollständig abnehmen.
- P3b-Segmentregeln/Kassenwechsel numerisch gesondert belegen. Keine künstlichen Profil-Teilmonate in der Steuerrechnung.
- Tatsächliche EFZ-/Urlaubs-/Feiertagsansprüche, Einmalbezüge/Vorjahr und Reisepauschalen entsprechend dem [Lückenplan](CRM_ERP_LOHN_LUECKENPLAN_2026.md) fertigstellen.
- Amtliche Meldung, Zugang und gegebenenfalls Systemzulassung sind zusätzlich erforderliche externe Schritte; bis zu echten Nachweisen bleiben Übermittlung und Zulassung false. Sie erklären die oben genannten fehlenden Rechenfunktionen nicht für erledigt.
