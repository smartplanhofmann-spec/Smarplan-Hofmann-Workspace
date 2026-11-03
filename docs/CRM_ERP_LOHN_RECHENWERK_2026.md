# Lohn-Rechenwerk 2026: Umfang und Nachweise

Stand: 3. November 2026. Die Implementierung erweitert die geschützte Personalakte
und Monatsvorbereitung. Sie führt keine Zahlungen, ELStAM-Abrufe oder amtlichen
Meldungen aus. `statutory_report_status` und `transmission_status` bleiben
`not_transmitted`; `official_system_approval` bleibt `false`.

## Durchgehender Ablauf

1. Personalaktennachweis speichern und tatsächliche Entgeltvereinbarung erfassen.
2. Steuer-/SV-Profil mit Gültigkeitsbeginn und Originalnachweis bestätigen.
3. Zeiten, Abwesenheiten und belegte Reisen prüfen und Monatsvorbereitung schließen.
4. Brutto aus der freigegebenen Entgeltquelle berechnen, Vorschau prüfen und den
   tatsächlich verfügbaren Berechnungsumfang ausdrücklich bestätigen.
5. Unveränderlichen Berechnungsbeleg mit Quellen, Regeln, Centbeträgen und PDF
   speichern. Korrekturen benötigen neue Quellenrevisionen und einen Grund;
   ursprüngliche Ergebnisse und PDFs bleiben abrufbar.

Ein interner Projektkostensatz wird niemals als Lohn verwendet. Auslagen bleiben
separat; ihre Erstattung wird nicht nochmals ins Lohnnetto addiert. Einmalige
Vorgangs-IDs verhindern doppelte Profile/Läufe auch nach verlorener Antwort.
Vor jeder Wiederholung prüft der Server die aktuellen Personalrechte.

## Unterstützte Fälle

| Fall | Ergebnis |
|---|---|
| Gewerblicher Minijob 2026, vollständiger Monat, ausdrücklich Arbeitgeber-Pauschsteuer 2 % | Netto, RV-Mindestbeitrag oder belegte Befreiung, Arbeitgeberbeiträge und Umlagen |
| Reguläres laufendes Monatsentgelt 2026, gesetzliche Pflichtversicherung, außerhalb des Übergangsbereichs, ohne Sonderfall | Einzelbeiträge, PAP-Lohnsteuer, Soli, Standard-Kirchenlohnsteuer, Netto |
| Reguläres Profil ohne ausdrücklich erfassten Monatsfreibetrag/Hinzurechnungsbetrag | Nur SV-Berechnung; Steuer und Netto bleiben `null` |
| Nicht unterstützter Fall | Ausdrückliche Sperrgründe; kein fiktives Nullnetto |

Für den vollständigen Standardfall sind beide Profilfelder
`tax_allowance_monthly_minor` und `tax_addition_monthly_minor` erforderlich. Null
ist ein ausdrücklich belegter Wert, kein automatischer Vorgabewert. Die Felder
werden als Paar gespeichert. Der tatsächliche Kassenzusatzbeitrag darf im PAP
höchstens zwei Nachkommastellen haben. Steuerklasse V/VI mit Kinderfreibeträgen,
Klasse VI mit Hinzurechnungsbetrag und Klasse II ohne Elternmerkmal werden abgewiesen.

Der bestätigte Landescode beschreibt den für den Standardfall geprüften
Beitrags-/Kirchensteuerbereich. Länder-/Konfessionssonderfälle sind gesondert
zu prüfen und als Sonderfall zu sperren. Die Standard-Kirchensteuer beträgt
8 % in BW/BY und 9 % in den übrigen Ländern; Centbruchteile werden abgeschnitten.
Quellen: [Bundesportal](https://verwaltung.bund.de/leistungsverzeichnis/DE/leistung/99102035002000/herausgeber/HH-S1000020010000006138/region/020000000000),
[Bayerische Rundungsregel](https://www.gesetze-bayern.de/Content/Document/BayAVKirchStG-9).

Nicht abgedeckt sind unter anderem Übergangsbereich, Ein-/Austritt im Monat,
Einmalentgelt, Sachbezüge, KUG/Krankengeld, Mehrfachbeschäftigung, private/freiwillige
KV im regulären Fall, Faktorverfahren, Altersentlastung und ausländische
Steuerfälle. Ein vor Jahresbeginn vollendetes 64. Lebensjahr löst bereits eine
gesonderte PAP-Prüfung aus; die Sperre wartet nicht bis zum 65. Geburtstag.

## Rechen- und Versionsnachweise

- `payroll_de_2026.py`: einzelne gesetzliche Beitragskomponenten werden mit
  Dezimalarithmetik und vorgeschriebener Cent-Rundung berechnet. Minijob-RV von
  150 EUR und 25 EUR ist gegen die veröffentlichten Beispiele der Minijob-Zentrale geprüft.
- `payroll_pap_2026.py`: eigenständig implementierter, begrenzter Ablauf anhand
  der amtlichen BMF-Anlage 1 vom 12. November 2025, gelesen über die
  [IHK-München-Veröffentlichung](https://www.ihk-muenchen.de/ihk/documents/Recht-Steuern/Steuerrecht/Einkommensteuer/2025-11-12-PAP-2026-anlage-1.pdf).
  Die allgemeine Prüftabelle auf Seite 39 enthält 43 Bruttowerte × 6 Steuerklassen;
  alle 258 Erwartungsbeträge sind unabhängig aus dem PDF übertragen.
- Monatsreferenz: 5.000 EUR Brutto, Klasse I, KVZ 2,90 %, kinderlos,
  keine Kirchensteuer/Freibeträge: Lohnsteuer 782,41 EUR, Arbeitnehmer-SV
  1.087,50 EUR, Netto 3.130,09 EUR. Die Lohnsteuer folgt aus dem amtlichen
  Jahresreferenzbetrag 9.389 EUR; Beiträge sind separat aus den Regeln berechnet.
- `pap_provenance_sha256` hasht die ausgewiesenen Quellenmetadaten. Es ist keine
  Prüfsumme des nicht heruntergeladenen amtlichen XML. Es wird kein Drittanbieter-
  Downloadcode und keine abgeschaltete TLS-Prüfung verwendet.
- V1 (`de_2026_standard_contributions_v1`) bleibt für historische Minijob- und
  Teilberechnungen reproduzierbar. Neue reguläre Ergebnisse verwenden V2
  (`de_2026_standard_monthly_pap_v2`). Restore berechnet jeden archivierten Lauf
  mit seiner gespeicherten Regelversion erneut; unbekannte Versionen scheitern.
  Eine V1-Teilberechnung wird niemals nachträglich in ein Netto umgedeutet.

## API und Berechtigungen

`/payroll/profiles`, `/payroll/preview`, `/payroll/runs`, jeweilige Einzelansichten
und Historien sowie `/payroll/runs/{id}/{pdf|json}?revision=N` und `/payroll/rules`.
Profiländerungen benötigen `personnel.read` + `personnel.write`; Monatsläufe
`personnel.read` + `personnel.approve`; Exporte zusätzlich `personnel.export`.
Eigenansichten erlauben nur den tatsächlich zugeordneten Mitarbeiter. Die
Unternehmens-/Modul- und frischen Berechtigungsprüfungen greifen auch beim Retry.
Alle Quellenreferenzen bleiben an denselben Mitarbeiter gebunden.

## Lohnkonto, tatsächliche Zahlungstage und belegte Monatsvorträge

Die Jahresübersicht `/payroll/ledger?employee_id=…&year=2026` zeigt zwölf Monate
und zählt ausschließlich die jeweils wirksame Revision. Noch fehlende Monate
bleiben sichtbar. `totals_scope=recorded_effective_months_only` bezeichnet die
Summe der aufgeführten Monate; Teilberechnungen machen betroffene Steuer-/Netto-
Summen unbekannt (`null`). Bei pauschal besteuerten Minijobs ist die individuelle
Arbeitnehmersteuer dagegen ausdrücklich nicht anwendbar und trägt null Euro zur
Summe bei; die Arbeitgeber-Pauschsteuer steht gesondert daneben.

Das additive Modul `business_payroll_accounts.py` erfasst folgende private,
unveränderliche Nachweise über `/payroll/account-records`:

- **Identität und Steuermerkmale:** getrennte Vor-/Familiennamen, Geburtsdatum,
  deutsche Anschrift, elfstellige Steuer-ID, Arbeitgeber/Anschrift/Steuernummer,
  Beschäftigungszeitraum, tatsächliche ELStAM-Import-/Finanzamtsbescheinigungs-
  oder Minijob-Nachweisquelle, Datum, Gültigkeit, Jahresfreibetrag/-hinzurechnung
  und Religionsmerkmal. Die exakte Payroll-Profilrevision liefert monatliche
  Steuermerkmale. Es gibt keine erfundenen Vorgabewerte und keinen behaupteten
  Live-ELStAM-Abruf. Die Steuer-ID-Prüfung ist eine Formatprüfung, keine
  Bestätigung einer amtlichen Vergabe.
- **Zahlungsnachweis:** tatsächliche Zahlungstage, signierte Centbeträge und
  Referenzen, gebunden an eine exakte Lauf- und Identitätsrevision. Mehrere
  Zahlungsteile müssen zusammen dem Netto entsprechen. Negative Beträge
  dokumentieren tatsächliche Arbeitnehmer-Nachzahlungen, etwa beim Minijob-
  Mindestbeitrag. Zukünftige Ist-Zahlungen werden abgewiesen. Ein geschützter
  Originalbeleg und ausdrückliche Standardfall-Bestätigung sind erforderlich.
  Zusätzliche steuerfreie Bezüge werden mit ausdrücklich angegebenem Betrag
  und Begründung separat erfasst; sie erhöhen nicht erneut das Lohnnetto.
- **Monatsvortrag:** ein nachgewiesener externer Standardmonat 2026 wird mit
  Original, Identitäts-/Steuerprofil, tatsächlichen Zahlungsteilen und den
  Vergleichswerten für Netto, Steuer, Arbeitnehmer-/Arbeitgeber-SV und gesamten
  Arbeitgeberbetrag erfasst. Der lokale 2026-Rechenlauf muss alle Vergleichswerte
  centgenau reproduzieren. Summarische unbelegte Anfangssalden werden nicht
  angelegt. Ein aktiver Vortrag und ein lokaler Lauf desselben Monats schließen
  sich gegenseitig aus. Eine begründete Aufhebung lässt den ursprünglichen
  Nachweis erhalten; sie führt keine Geldrückzahlung aus.

Jeder Nachweis hat Korrekturversionen, Quellen-/Inhaltshashes und geschützte
Vorgangsbelege. Eine korrigierte Identität muss ausdrücklich in den aktuellen
Zahlungsnachweis übernommen werden. Derselbe Zahlungstag mit derselben
Referenz darf beim Mitarbeiter nicht in zwei wirksamen Monaten wiederverwendet
werden; auch Unicode-/Großschreibungsvarianten umgehen die Prüfung nicht.
Private Lese-/Schreib-/Freigaberechte werden vor jedem Replay erneut geprüft.
Der eigene Mitarbeiter darf seine Nachweise mit `time.own` lesen; dies gibt
keinen Zugriff auf fremde Mitarbeiter oder nicht freigegebene Originaldateien.

`supported_wage_account_fields_complete` bedeutet: alle vorhandenen wirksamen
Monate haben vollständige Nachweise. `statutory_wage_account_complete` wird erst
wahr, wenn zusätzlich alle ausdrücklich belegten Beschäftigungsmonate des Jahres
abgedeckt sind und keine widersprüchlichen Beschäftigungszeiträume bestehen.
Ein beendetes einmonatiges Beschäftigungsverhältnis verlangt keine erfundenen
elf weiteren Lohnmonate. Diese technische Feldprüfung bedeutet keine externe
Fachabnahme. `digital_audit_export_compliant` und `official_system_approval`
bleiben ausdrücklich falsch; ein PDF/CSV ist kein amtlicher DLS-Export.

Die Exporte `/payroll/ledger/{pdf|csv|json}` verlangen den zuvor geprüften
`snapshot_hash`. Änderungen vor dem Export liefern 409. Die Vorschau enthält
Größe und SHA256 jedes deterministisch erzeugten Exports; Clients prüfen diese
vor der Dateiübergabe. JSON enthält die vollständige Jahresprojektion, CSV/PDF
auch Identitäts-, Zahlungs-, Original- und Korrekturbezüge. Korrekturdifferenzen
werden nie zusätzlich zu den wirksamen Monatsbeträgen summiert.

Amtliche Rechtsgrundlage, am 3. November 2026 vollständig gelesen:
[§ 4 LStDV](https://www.gesetze-im-internet.de/lstdv/__4.html),
[§ 41 EStG](https://www.gesetze-im-internet.de/estg/__41.html) und der
[Anwendungszeitraum in den LStH 2026](https://esth.bundesfinanzministerium.de/lsth/2026/B-Anhaenge/Anhang-22/anhang-22.html).
§ 4 Abs. 2a in der Ende 2025 geänderten Fassung gilt für die ab 2027
aufzuzeichnenden Daten; für 2026 gilt die dort bezeichnete Vorfassung.
Der fachlich begrenzte Fall bestätigt ausdrücklich laufenden Barlohn ohne
weitere Sach-/Sonderbezüge, U-/S-Fälle oder Drittlohn. Entsprechende Sonderfälle,
abweichende Beitrags-/Steuerfälle und hier nicht unterstützte Zahlungen über
die Jahresgrenze bleiben gesperrt und benötigen eigene Implementierung.

Nach § 41 Abs. 1 Satz 9 EStG reicht die Lohnkonto-Aufbewahrung bis zum Ende des
sechsten Kalenderjahrs nach der letzten eingetragenen Lohnzahlung, beispielsweise
bis 31. Dezember 2032 bei letzter Zahlung 2026. Maßgeblich ist der tatsächliche
Zahlungstag, nicht das Import-/Änderungsdatum. Das betrifft die zugehörige
Lohnkonto-Fachhistorie und ihre nötigen Berechnungs-/Originalnachweise; daraus
folgt keine pauschale Sechsjahresfrist für sämtliche Personaldateien oder rein
technischen Vorgänge. Weitere gesetzliche Pflichten und Sperren bleiben gesondert
zu prüfen. Die Umsetzung löscht diese Belege nicht automatisch.

## Ausgeführte technische Prüfungen

`PYTHONPATH=backend backend/.venv/bin/python -m unittest
backend.test_payroll_de_2026 backend.test_payroll_pap_2026
backend.test_business_payroll backend.test_business_payroll_ledger
backend.test_business_payroll_accounts -v`: **43 Tests bestanden** in 5,104 Sekunden, darunter 258 amtliche
Tabellenwerte als Unterfälle, sechs monatliche Brutto-Netto-Referenzen, Minijob-
Mindestbeiträge, Sachsen/Kinder/Rundung, explizite Freibeträge, Korrekturen,
verlorene Antwort/Wiederholung, Rechteentzug, Original-PDF und historische V1-
Wiederherstellung. Hinzu kommen zwölfmonatige Summen, Teilmonatslücken,
unvollständige Steuer-/Nettosummen, Pflichtfeld-/Quellen-/Gültigkeitsprüfung,
Identitätskorrekturen, belegte Vorträge, Zahlungsreferenz-Doppelschutz, signierte
Zahlungsteile, nachträglich neu gehashte Manipulationen und deterministische
CSV-/PDF-/JSON-Exporte. Log: `work/verification/payroll-complete-domain.log`.

Die **sechs PostgreSQL-Tests** in `online.test_business_payroll_pg` und
`online.test_business_payroll_accounts_pg` bestanden in **21,864 Sekunden**
gegen die reservierte lokale synthetische Datenbank. Minijob und
regulärer PAP-Lauf sind über MFA/HTTP, Quellenkorrektur, Neustart, alte PDFs und
tatsächliches Dump/Restore geprüft. Die Laufzeitrolle kann die geschützten
Tabellen nicht überschreiben/löschen/leeren; Datenbankwächter blockieren
Überschreiben/Löschen auch für den Migrator. Log:
`work/verification/payroll-final-postgres.log`. Die zusätzliche Jahreskette verbindet
einen belegten Oktober-Vortrag mit einer lokalen November-Abrechnung, vollständigen
Steuer-/Identitätsnachweisen und tatsächlichen Zahlungsteilen. Jahresbeträge,
Originalreferenzen und alle drei identischen Jahres-Exportdateien überstehen den
tatsächlichen Restore. Es wurden ausschließlich synthetische Daten verwendet.

Der [maschinenlesbare Nachweis](CRM_ERP_LOHN_PRUEFUNG_2026-11-03.json) hält
Datei-/Log-Prüfsummen, tatsächlich ausgeführte Fälle und Grenzen fest. Interne
Tests ersetzen keine externe fachliche Abnahme oder Systemuntersuchung.
