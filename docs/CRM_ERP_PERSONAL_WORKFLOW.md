# Personalakten, belegte Reisekosten und monatliche Lohnvorbereitung

Stand: 3. November 2026. Backend-Modul: `business_personnel_workflow`; Feature: `personnel_preparation`. Der Ablauf ergänzt die vorhandenen Mitarbeiter-, Zeit- und Abwesenheitsdaten. Er führt keine Brutto-Netto-, Steuer-, Sozialversicherungs- oder Pauschalenberechnung aus.

## Abgeschlossener Ablauf

1. Berechtigte Personen archivieren ein Personaloriginal für einen vorhandenen Mitarbeiter. PDF-, PNG- und JPEG-Dateien bis 600.000 Bytes werden unverändert einschließlich SHA-256 gespeichert. Dateimetadaten sind ebenfalls gehasht. Nachfolger verweisen auf das Original; es wird nicht überschrieben.
2. Eine ausdrücklich dokumentierte Entgeltvereinbarung nennt Beschäftigungsart, Beginn, Monats- oder Stundenbasis, ganzzahligen EUR-Centbetrag und Personalaktenoriginal. Spätere Gültigkeitsbeginne sind neue Vereinbarungen; Korrekturen bestehender Vereinbarungen benötigen einen Grund und behalten die Historie. Projektkostensätze werden nicht übernommen.
3. Mitarbeiter erfassen eigene Reisen und tatsächlich belegte EUR-Auslagen. Jeder Posten verweist auf ein Original. Vor Reisebeginn gekaufte Fahrkarten sind zulässig. Gleiches Original mit neuer Upload-ID kann keinen zweiten gleichzeitig eingereichten/erstatteten Antrag begründen.
4. Entwurf → Einreichung → Freigabe oder Zurückweisung. Eine andere berechtigte Person prüft; eigene und selbst eingereichte Anträge dürfen nicht selbst genehmigt werden. Korrekturen erhalten neue Versionen und benötigen eine neue Prüfung.
5. Eine Erstattung wird erst als bestätigt geführt, wenn die prüfberechtigte Person den vollständigen tatsächlichen Betrag, Zahlungstag und eine eindeutige Referenz ausdrücklich bestätigt. Dies ist eine dokumentierte Anwenderbestätigung; es wird keine Banküberweisung ausgeführt. Ein erstatteter Antrag benötigt vor einer Korrektur eine entsprechend bestätigte vollständige Rückzahlung. Frühere Zahlungsnachweise bleiben erhalten.
6. Die Monatsvorschau übernimmt belegte Entgeltvereinbarungen, freigegebene erfasste Arbeitstage mit Korrekturen, genehmigte Abwesenheiten ohne medizinischen Freitext und geprüfte Reisen. Laufende/ungeprüfte Zeiterfassungen und offene Abwesenheits-/Reisekostenanträge verhindern den Abschluss.
7. Die zuständige Person bestätigt die Vollständigkeit der erfassten Quellen. Der Abschluss prüft den Vorschauhash erneut und archiviert einen unveränderlichen Monatsstand mit PDF. CSV, vollständiges JSON, PDF und historische Revisionen sind abrufbar. Spätere Quellenänderungen verändern abgeschlossene Monate nicht; eine begründete neue Abschlussversion übernimmt die geänderten Quellen.

Reisen werden anhand ihres Endmonats zugeordnet; die Zahlungsnachweise haben jeweils ihre eigenen tatsächlichen Zahlungstage. Ein später ergänzter Zahlungsnachweis kann über eine Korrekturversion in den betreffenden Vorbereitungsmonat übernommen werden. Daraus werden keine EÜR-Buchungen oder Steuerperioden abgeleitet. Für nicht erfasste Arbeitszeit wird keine Nullbeschäftigung oder vollständige Abrechnung unterstellt.

## Rechte und dauerhafte Nachweise

- `personnel.read`: Personalinformationen anderer Mitarbeiter; `personnel.write`: Personalakten und Entgeltvereinbarungen verwalten.
- `time.own`: eigene Reisekosten und sichtbare eigene Unterlagen. Interne Personaloriginale bleiben ohne `personnel.read` unzugänglich.
- `personnel.approve`: Reiseprüfungen, tatsächliche Zahlungsbestätigungen und Monatsabschluss. Der Monatsabschluss benötigt zusätzlich Leserechte.
- `personnel.export` zusammen mit `personnel.read`: Monatsunterlagen herunterladen. Eine Finanzrolle oder eine Projektfreigabe gewährt keine Personalrechte.
- Alle Zugänge und Berechtigungen werden vor jedem Aufruf und jeder Wiederholung frisch aus dem aktuellen Benutzerbestand gelesen. Baustellen-Gerätetoken dürfen die HR-Endpunkte nicht nutzen.
- Originale, Ereignisse und Empfangsbelege sind append-only. SQLite-Trigger schützen auch `INSERT OR REPLACE` über eindeutige Monats-/Vertragsidentitäten. PostgreSQL-Laufzeitrechte verweigern UPDATE/DELETE/TRUNCATE; Migratortrigger schützen UPDATE/DELETE zusätzlich.
- Jede Änderung erhält `request_id`, Inhaltshash und Empfangsbeleg. Gleiche Wiederholungen liefern dieselbe bestätigte Antwort; veränderte Inhalte unter derselben ID sind Konflikte. `request_resolution=not_accepted` wird nur nach gesicherter Prüfung einer noch nicht angenommenen Anfrage zurückgegeben.

Das PDF wird bei Abschluss außerhalb des globalen Anwendungsschlosses gerendert. Der anschließende Commit vergleicht die Quellen erneut. Der Download prüft die archivierten Bytes gegen den gespeicherten PDF-Hash. Dieser Nachweis beweist Archivintegrität, keine unabhängige fachliche Lohnberechnung oder amtliche Zulassung.

## Bedienung im Browser und in Flutter

Unter **Personal → Personalakte, Reisen und Lohnvorbereitung** wird der
gewünschte Mitarbeiter gewählt. Die bestehenden Zeit- und Abwesenheitsseiten
bleiben erreichbar. Die neue Ansicht bietet den gesamten oben beschriebenen
Ablauf: Originale, Vereinbarungen, Reiseanträge, Einreichung, unabhängige Prüfung,
Erstattungs-/Rückzahlungsnachweise sowie Monatsvorschau, Abschluss und Historie.

Im Browser lassen sich weitere Auslagenpositionen unmittelbar hinzufügen oder
entfernen. Flutter fragt zunächst die Zahl der Belege ab und erfasst dann jede
Position mit eigenem Datum, Betrag, Original und optionalem Projekt. Eine Reise
kann bis zu 100 Positionen enthalten. Vorab bezahlte Fahrkarten dürfen ein
Belegdatum vor dem Reisebeginn haben. Geldbeträge werden vor der Übertragung
exakt in Cent umgewandelt; zusätzliche Dezimalstellen werden abgewiesen.

Eine verlorene Erfolgsantwort bleibt an die ursprüngliche Anfrage-ID und deren
Inhalt gebunden. Im Browser führt **Antworten offen → Unverändert erneut senden**
zur gesicherten Wiederholung. Flutter zeigt im Personalbereich **Antwort offen**
mit **Unverändert wiederholen**; dieselbe Anfrage bleibt auch nach Schließen des
Editors und einem Wechsel der Servergeneration erhalten. Aktuelle Rechte und
Modulaktivierung werden vor dem Wiederholungsversuch erneut geprüft. Das ist
ein Puffer der laufenden Sitzung, kein dauerhaftes Offline-Personaljournal.

Bekannter Rechteentzug entfernt fremde Mitarbeiter-/Aktendaten aus den
Flutter-Ansichten und schließt die betroffenen Browserdialoge. Datei- und
Monatsexporte prüfen die Berechtigung auch nach dem asynchronen Abruf;
ein privates Original wird bei zwischenzeitlich entzogenem Personal-Leserecht
nicht ausgegeben, auch wenn eigene Zeitrechte erhalten bleiben. Native
Originalvorschauen sind widerrufbar. Originaldateien und Monats-PDFs werden
zusätzlich gegen die gebundenen SHA-256-Werte geprüft.

Historien zeigen jede Fassung einschließlich der damals bestätigten Quellen.
Die Schaltflächen **PDF / CSV / JSON · Fassung N** adressieren genau diese
Revision. Eine nachträgliche Vertragsänderung, Rückzahlung oder Antragskorrektur
verändert einen vorherigen Monatsabschluss nicht.

## HTTP-Vertrag

Alle folgenden Pfade liegen unter `/business/personnel` und benötigen die bestehende angemeldete Sitzung:

| Pfad | Methoden / Zweck |
|---|---|
| `/files` | GET Mitarbeiterdateien; POST Original archivieren |
| `/files/{id}/content` | GET berechtigtes Original als Anhang |
| `/agreements` | GET Vereinbarungen; POST neue Vereinbarung/Korrektur |
| `/expenses` | GET Reisen; POST Entwurf/Korrektur |
| `/expenses/{id}/submit` | POST einreichen |
| `/expenses/{id}/approve` oder `/reject` | POST begründete Prüfung |
| `/expenses/{id}/reimburse` oder `/reverse-reimbursement` | POST tatsächliche vollständige Erstattung/Rückzahlung bestätigen |
| `/payroll-preparations/preview` | GET Vorschau mit `employee_id` und `month=JJJJ-MM` |
| `/payroll-preparations` | GET Monatsstände; POST geprüften Monat abschließen/korrigieren |
| `/{agreements,expenses,payroll-preparations}/{id}` | GET aktueller Vorgang |
| `/{agreements,expenses,payroll-preparations}/{id}/history` | GET sämtliche Revisionen |
| `/payroll-preparations/{id}/{pdf,csv,json}` | GET Export; optional `revision` für historischen Stand |

Listen filtern über `employee_id`; ohne diesen Filter wird ausschließlich das eigene Mitarbeiterprofil verwendet. Unbekannte Felder, doppelte Suchfilter und vermischte GET-/POST-Eingabekanäle werden abgewiesen. Geldbeträge sind ganzzahlige Centwerte, keine Gleitkommazahlen.

## Ausgeführte Prüfungen

Am 3. November 2026 erfolgreich:

- `python -m unittest discover -s backend -p test_business_personnel_workflow.py -q`: **14 Tests bestanden**, 2,382 Sekunden. Belegte Gesamtkette, Rechte/Altrolle, frische Wiederholungsprüfung, Korrektur/Rückzahlung, Quellenänderung, Archivschutz und Rollback, SQLite-REPLACE, fremde rehashte Restore-Quellen, PDF-Manipulation, Originalduplikate, offene Zeiten, Moduldeaktivierung, eindeutige Konfliktbeweise und vorgebuchte Reisekosten.
- `backend/.venv/bin/python -m unittest discover -s backend/online -p test_business_personnel_workflow_pg.py -v`: **2 Tests bestanden**, 6,058 Sekunden. Ausschließlich die bestehende geprüfte lokale PostgreSQL-Testdatenbank: reale MFA-/HTTP-Kette, Neustart/Retry, Rechte-/Gerätetokenbegrenzung, echte Laufzeit-ACLs und Migratortrigger sowie tatsächliche Migration, `pg_dump`/Restore und Erhalt der Originale, Monats-PDFs und Empfangsbelege. Ergebnisprotokoll: `work/verification/pg-personnel-workflow.log`.

Der erste PostgreSQL-Aufruf scheiterte bereits am Loopback-Socket der Sandbox. Die tatsächlich ausgeführte Prüfung erfolgte danach mit dem zugelassenen lokalen Netzwerkzugriff; die beiden oben genannten Fälle wurden nicht übersprungen. Es wurden keine externen Dienste, echten Personaldaten oder Produktivmeldungen verwendet.

### Clientnachweise

- `flutter test --no-pub --reporter expanded test/business_personnel_workflow_test.dart`:
  **9/9 bestanden**. Exakte Centbeträge, mehrere Originalpositionen, begründete
  Korrekturen, Mitarbeiter-/Monatsbindung, 600-kB-Grenze, verlorene
  Upload-Erfolgsantwort, Editor schließen, Rechteentzug, Servergenerationswechsel
  und identischer Wiederholungsbefehl mit genau einem archivierten Original.
- `flutter analyze --no-pub lib/business_personnel_workflow.dart test/business_personnel_workflow_test.dart`:
  **keine Befunde**. Der erste Gesamtanalyselauf enthielt ausschließlich sechs
  Warnungen aus dem gleichzeitig bearbeiteten EÜR-Modul; die HR-Dateien waren
  ohne Analysebefund.
- `node --test --test-isolation=none --test-reporter=tap web/office/tests/personnel-workflow.test.mjs`:
  **7/7 bestanden**, einschließlich eines bereits laufenden privaten
  Originaldownloads, der nach Entzug von `personnel.read` trotz erhaltenem
  `time.own` nicht mehr ausgegeben wird.
- `SMARTPLAN_BROWSER_WORKFLOW=personnel-workflow node web/office/tests/e2e.cjs`:
  **1 vollständiger Chromium-Ablauf bestanden**. Zwei echte synthetische
  MFA-Anmeldungen; private Entgeltakte, eigener Original-Reisebeleg, Einreichung,
  Fremdprüfung, volle Erstattung, Vorschau und Monatsabschluss, verlorene
  Erfolgsantwort, identische Wiederholung nach zwischenzeitlich geänderter
  Entgeltquelle, historische PDF-/CSV-/JSON-Ausgaben, neue Monatsfassung,
  Rückzahlung und erneuter Antragsentwurf. Das alte PDF blieb bytegleich.
  Freigegebene Arbeitszeit wurde zur Vorbereitung über die echte HTTP-API
  erzeugt. Dokumente, Reise- und Monatsvorgänge sowie Exporte wurden geklickt.
  Namespace-, PID-, Netzwerk- und Seccomp-Sandbox wurden vor Zugriff geprüft.

Desktop und 390-Pixel-Ansicht sind geprüft. Die Nachweise verwenden ausschließlich
synthetische lokale Daten; sie belegen keine reale Android-/Windows-Geräteabnahme.
Ein erster Client-Grenzwerttest fand die Eingabeprüfung am zulässigen Höchstbetrag
zu eng; beide Clients wurden vor dem erfolgreichen Abschlusstest korrigiert.
Der erste Browserlauf stoppte nach erfolgreichen historischen Exporten an einem
Testnavigator; die erneute Öffnung der Personalübersicht ist im Test nun korrekt.

Code und Tests: `app/lib/business_personnel_workflow.dart`,
`app/test/business_personnel_workflow_test.dart`,
`web/office/personnel-workflow.js`,
`web/office/tests/personnel-workflow.test.mjs` und
`web/office/tests/personnel-workflow-flow.cjs`.
Lokale Protokolle/Screenshots liegen unter
`work/verification/personnel-*`; der Arbeitsordner wird nicht ausgeliefert.

## Noch offen im Gesamtziel

Fremdwährungsumrechnung, automatische Reise-/Verpflegungspauschalen, steuerliche Einstufung der Auslagen, Brutto-Netto-Rechenwerk, Lohnkonto/gesetzliche Abrechnungsfälle und amtliche Meldeverfahren sind nicht Bestandteil dieses Vorbereitungsmoduls. Tatsächliche ELSTER-/Sozialversicherungszulassungen werden durch diese Tests nicht belegt. Maßgebliche 2026-Quellen und der verbleibende Umsetzungsplan stehen in [CRM_ERP_LOHN_QUELLEN.md](CRM_ERP_LOHN_QUELLEN.md).
