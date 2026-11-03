# Teilmonatsabrechnung 2026 – implementierter P3a-Stand

Stand: 03.11.2026. Die neue Rechenversion `de_2026_periods_pap_v4` berechnet belegte Ein- und Austrittsmonate für regulär Beschäftigte, Midijobs und gewerbliche pauschal versteuerte Minijobs. Sie verwendet eine inländische Beschäftigungsepisode, eine im Monat wirksame Entgeltvereinbarung und ein unverändertes Steuer-/Versicherungsprofil. Die historische v1-/v2-/v3-Rechnung bleibt unverändert erreichbar. Der vollständige Lohnumfang ist damit noch nicht abgeschlossen; die konkreten folgenden Pakete stehen unten.

Der [frühere Entwurf](CRM_ERP_LOHN_ZEITACHSEN_TEILMONATE_ENTWURF.md), die [unabhängige Quellen- und Zahlengegenprüfung](CRM_ERP_LOHN_TEILMONATE_GEGENPRUEFUNG_2026.md), der [Faktenvertrag](CRM_ERP_LOHN_ZEITACHSEN_API.md) und die [P2-Abnahme](CRM_ERP_LOHN_FAKTEN_2026.md) dokumentieren Herkunft und Abgrenzung. Der aktuelle Nachweis ist [maschinenlesbar](CRM_ERP_LOHN_TEILMONATE_PRUEFUNG_2026-11-03.json).

## Berechnung und Quellen

Der reine Rechner in `backend/payroll_periods_2026.py` liest ausschließlich das unveränderliche P2-Quellenbild. `build_period_plan` erzeugt Beschäftigungstage, belegten Entgeltquotienten, tatsächliches Brutto, Steuer-Lohnzahlungszeitraum, SV-Tage, Teil-BBG und Minijob-Mindestbasis. `calculate_period_source` ergänzt die Steuer, getrennte AN-/AG-Beiträge, Umlagen und das Netto. Weder Datenbank, aktuelle Personalstämme, Systemzeit noch Provider werden für die historische Rechnung konsultiert.

- Monatliche Entgeltansprüche werden nach der ausdrücklich belegten Vertragsmethode berechnet: tatsächliche Kalendertage, vertragliche 30-Tage-Methode, Soll-Arbeitstage oder Soll-Sekunden. Die beiden letzten Methoden benötigen den vollständigen belegten Monatsarbeitsplan. Stundenentgelt verwendet freigegebene tatsächliche Arbeitssekunden.
- Vollmonat, tatsächliche Beschäftigungstage, SV-Tage und Steuer-Tage bleiben getrennt. Ein voller Februar hat 28 Kalendertage und 30 SV-Tage. Der einzige Beschäftigungstag am 31. eines Monats zählt als ein Tag. Eine Abwesenheit wird nicht zu einem erfundenen Austritt.
- Der eigene Tages-PAP-Wrapper `backend/payroll_pap_periods_2026.py` ruft den unveränderten Jahreskern auf. Er rechnet die ganzzahligen täglichen Cent-Eingaben mit 360 hoch und die amtlichen Jahresausgaben mit Centabrundung zurück. Tatsächliches Brutto und Divisionrest bleiben separat nachweisbar. Monatliche Freibeträge/Hinzurechnungsbeträge werden für den Tagesfall nach R39a.1/R39b.5 auf den nächsten durch fünf teilbaren Centbetrag aufgerundet.
- Kirchensteuer wird vom gesamten BK des tatsächlichen Lohnzahlungszeitraums berechnet und erst dann auf Cent abgerundet. 17 Tage in der belegten bayerischen Klasse-VI-Referenz ergeben 101,53 EUR statt 101,49 EUR aus falscher täglicher Kirchensteuerrundung.
- Teil-BBG und anteilige Minijob-Mindestbasis werden eigenständig auf Cent gerundet. Beitragssätze und AN-/AG-Verteilung folgen anschließend; Sachsen und Pflege-Kinderabschläge bleiben getrennt. Die Minijob-Quellenabweichung im gedruckten 27-Tage-Beispiel ist ausdrücklich dokumentiert, keine vermeintliche amtliche Korrektur wird behauptet.
- Der Midijobstatus folgt der belegten Jahresprognose. Ein niedriges tatsächliches Teilentgelt macht eine reguläre Beschäftigung nicht automatisch zum Midijob. Die Midijob-Basis verwendet den exakten Vertragsquotienten und rundet erst die endgültige Teilbasis; vorgerundete Vollmonatsbasen würden nachgewiesene Centfehler verursachen.

Fehlende Identität, widersprüchliche Quellen, nicht belegte Vertragsmethode und noch nicht implementierte fachliche Fälle erzeugen präzise Blocker. Es gibt dann kein scheinbar fertiges Netto. Eine Bestätigung der Fakten kann einen fachlichen Blocker nicht aufheben.

## Integrierter Arbeitsablauf und Historie

Die alternative Payroll-Eingabe lautet exakt `source_schema_version: 2`, `employee_id`, `period_case_ref`. Eine frei eingegebene Bruttosumme gehört nicht zu diesem Pfad. Der Server löst die bestätigte Faktenrevision auf und prüft ihre aktuelle Verwendbarkeit vor einer neuen Vorschau. Die Laufquelle bindet den vollständigen historischen Fall, seine Originalrevisionen und den identischen nachgerechneten Plan.

`business_payroll.py` bindet Vorschau, Abschluss, Korrektur, Originalquittung, JSON/PDF und Integritätsprüfung. Die unveränderten Summenfelder werden um `period_details` ergänzt. Jahresauswertungen in `payroll_ledger.py` zählen nur die wirksame Monatsrevision, zeigen Perioden- und Quellenhashes und behandeln pauschal versteuerte Minijobs korrekt mit null individueller Lohnsteuer.

`business_payroll_accounts.py` prüft für v4 den tatsächlichen Beschäftigungszeitraum und die exakt gewählte Identitätsrevision. Die Vollmonatsprüfung historischer Quellen bleibt erhalten. Tatsächliche Zahlungen müssen weiterhin gesondert belegt werden. Korrigiertes Netto erzeugt weder rückwirkend eine Zahlung noch automatisch einen neuen Geldfluss. Der getestete Weg führt über bestehendes PayrollCash und tatsächliche Netto-/Abführungsteile in die EÜR sowie einen ausdrücklich zugeordneten Bankabschluss. Private Anspruchs- und Originaldaten erscheinen nicht in der öffentlichen Buchhaltungsquelle.

Alte Quittungen, Laufrevisionen und Originaldateien bleiben nach Profiländerung, Fallarchivierung und Modulpausierung exakt lesbar beziehungsweise wiederholbar. Neue Verarbeitung einer veralteten Quelle wird zurückgewiesen. Aktuelle Rechte werden auch vor der Wiederholung geprüft. Offline-Zugriffe auf den neuen Verarbeitungspfad bleiben gesperrt.

Die eingebetteten vollständigen v4-Quellen enthalten private Personalakten. Deshalb benötigen Rohbelege und Jahresquellen `personnel.read`; bestehende eingeschränkte Selbstleserechte dürfen diese Akten nicht indirekt öffnen. Eine eigene schmale Mitarbeiteransicht für Abrechnung und Zahlung ohne private Anspruchs-/Originalakten ist ein **noch zu entwickelnder Produktbestandteil**, keine dauerhafte Einschränkung des Gesamtziels.

## Verifikation und Freeze

Die Tests verwenden ausschließlich synthetische Daten. Die 15 eigenen Kernfälle enthalten sämtliche 18 unabhängig aus der amtlichen Jahrestabelle hergeleiteten Tageswerte, vier Mehrtagesfälle, veröffentlichte Teil-BBG, Monats-/Vertragsquotienten, Einzeltag und Februar, getrennte hohe SV-Basen mit Sachsen, Quellenvollständigkeit und fachliche Sperren. Weitere zwölf unabhängig geschriebene Gegenfälle prüfen insbesondere Centgrenzen, Midijob-Endrundung, Mindest-RV und Kirchensteuer. Diese Sollwerte stammen nicht aus dem neuen Produktrechner.

Fünf neue integrierte Domänenfälle prüfen tatsächliche Fakten bis Lauf, Identität, Korrektur, Jahresausgabe, Originalquittung, Cash/EÜR/Bank und private Rechte. Drei echte PostgreSQL-Fälle prüfen MFA/HTTP und Neustart, frischen Rechteentzug, unabhängige konkurrierende Verbindungen sowie Dump/Restore des tatsächlichen Midijob-Teilmonats mit Geldfluss und Bankabschluss. Rechenquittungen und Originaldateien bleiben nach Restore gleich; neue finanzielle Verarbeitung bleibt bis zum bestehenden Betreiberabgleich gesperrt.

Die zusammenhängende Lohnregression und historische PostgreSQL-Abnahme werden mit Anzahl, Laufzeit und Dateihashes im maschinenlesbaren Nachweis festgehalten. Die 258 amtlichen Jahres-PAP-Referenzen bleiben Teil der alten Regressionsfälle. Die Clientabnahme gehört zur gesonderten P2/P3-Clientstrecke; dieser Backendnachweis behauptet keinen nicht ausgeführten Browserlauf.

Die v4-Kernmodule und ihr Quellenvertrag sind nach diesem Nachweis eingefroren. Weitere Fachregeln erhalten einen eigenen Regelstand; historische v4-Quellen werden nicht durch späteres Wissen umgedeutet.

## Konkrete weitere Entwicklung

1. **P3b:** mehrere wirksame Entgeltvereinbarungen, untermonatige Kassen-/Beitrags-/Profilwechsel und Wiederaufnahme. Echte Beitragsgruppenwechsel können in einem 31-Tage-Monat 15+16 SV-Tage und damit eine zusätzliche Teil-BBG von 1/30 erzeugen; beliebige Entgeltzeilen dürfen dies nicht. Eine allgemeine Deckelung aller fachlichen Segmente auf 30 wäre ebenso falsch. Die Ereignis- und Rundungsregeln werden separat belegt und implementiert.
2. **P4:** bezahlte/unbezahlte Abwesenheiten, tatsächliche Urlaub-/Feiertags-/EFZ-Ansprüche für Stundenlohn, Krankheitsvorzeiten und SV-Fortbestand. P2 kann den belegten Fall bereits speichern, v4 kann ihn noch nicht vollständig berechnen.
3. **P5 und Lebenszyklus:** Einmalbezüge, Vorjahres-/Nachzahlungsfälle, unterjährige Übernahmen und entsprechende externe Teilmonatsvorträge. Die vorhandenen Vollmonatsvorträge ersetzen diese fehlende Periodenimplementierung nicht. Weitere Minijob-Statusfälle benötigen ihre eigenen Regeln.
4. **Mitarbeiterbeleg und Meldungen:** schmale private Selbstansicht; echte Meldeverfahren, Zugänge und gegebenenfalls Systemzulassung. `not_transmitted` und `official_system_approval: false` bleiben korrekt. Reisepauschalen werden parallel als eigener Entgelt-/Erstattungsbereich entwickelt.

Diese offenen Rechen- und Produktfälle bleiben echte Entwicklungsarbeit. Weder ein Quellencheck noch eine dokumentierte Sperre erklärt sie für erledigt.
