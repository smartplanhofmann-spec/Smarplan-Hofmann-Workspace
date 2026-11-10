# Lohnberechnung in Browser und Flutter

Stand: 03.11.2026. Diese Oberflächen verwenden den begrenzten, quellengebundenen
[Rechenumfang 2026](CRM_ERP_LOHN_RECHENWERK_2026.md). Sie ersetzen weder eine
Systemzulassung noch tatsächlich erfolgte gesetzliche Meldungen.

Aktueller Zusatzstand10.11.: Neben den historischen Abläufen dieses Dokuments
sind [Faktor mit P4-Ansprüchen V12](CRM_ERP_FAKTOR_ANSPRUECHE_V12_2026-11-10.md)
und [Faktor mit P4 und bereits bezahlten Reisen V13](CRM_ERP_FAKTOR_ANSPRUECHE_BEZAHLTE_REISEN_V13_2026-11-10.md)
in Browser und App integriert und durchgängig technisch geprüft. Die aktuelle
[Bedienfolge](CRM_ERP_BENUTZERHANDBUCH.md#faktor-monat-mit-ansprüchen-und-bereits-bezahlten-reisen)
beschreibt Auswahl, Quellen, getrennte Bestätigungen und unveränderte
Wiederholung. Bereits verwendete Altfall-Ergänzung und weitere Fallgruppen
bleiben nach dem [aktuellen Lückenplan](CRM_ERP_LOHN_LUECKENPLAN_2026.md) offen.

Der zusätzlich belegte Übergangsbereich mit ausdrücklicher Zwölfmonatsprognose ist
in [CRM_ERP_LOHN_MIDIJOB_CLIENTS.md](CRM_ERP_LOHN_MIDIJOB_CLIENTS.md) einschließlich
separater Browser-/Flutterabnahme dokumentiert. Bestehende Profile werden nicht
automatisch auf diesen Umfang umgestellt.

## Erreichbarer Ablauf

Im Bereich Personal einen Mitarbeiter und dessen **Personalakte, Reisen und
Lohnvorbereitung** öffnen. **Lohnberechnung 2026** führt zu:

1. Einem Lohnprofil mit tatsächlich gültigem Beginn, persönlicher Steuer- und
   Versicherungskonstellation und unverändertem geschütztem Originalnachweis.
   Die erste Erfassung gibt keine unbekannten persönlichen Werte vor.
2. Einer ausdrücklich gewählten Berechnungsart. Reguläre Standardabrechnung
   benötigt zusätzlich die tatsächlichen monatlichen ELStAM-Frei- und
   Hinzurechnungsbeträge; bekannte Nullwerte werden ausdrücklich eingetragen.
   Die wählbare reine Sozialversicherungsberechnung hält Netto und Steuern
   weiterhin unbekannt. Für Minijobs ist das unterstützte Arbeitgeber-
   Pauschsteuerverfahren separat erkennbar.
3. Der Auswahl des gültigen Profils und einer bereits abgeschlossenen
   HR-Monatsvorbereitung. Das Brutto wird aus dem belegten Arbeitsentgelt
   geprüft; Projektkostensätze werden nicht übernommen.
4. Einer Vorschau mit Beiträgen, Umlagen, Steuern, Netto, berechnetem
   Auszahlungsbetrag, Grenzen und eingefrorenen Quellen. Nicht unterstützte
   Fälle können nicht als abgeschlossene Berechnung bestätigt werden.
5. Ausdrücklicher Bestätigung des angezeigten Umfangs, begründeter
   Profil-/Monatskorrektur und unveränderlicher Historie mit PDF und JSON.
   Eine Korrektur zeigt die Differenz zur vorherigen Berechnung. Frühere
   Dateien bleiben verfügbar; keine Bankzahlung wird ausgelöst.

Das Bundesland muss für die Beitrags- und reguläre Kirchensteuerkonstellation
geprüft sein. Kirchensteuer-Sonderfälle werden gekennzeichnet und bleiben
außerhalb dieses Standardumfangs. Es gibt keinen automatischen ELStAM-Abruf.

## Rechte und unklare Antworten

- Eigene Mitarbeiter können ihre freigegebenen Berechnungen lesen. Globale
  Personalverwaltung benötigt `personnel.read`, die Profilpflege zusätzlich
  `personnel.write`, die Bestätigung `personnel.approve`, Exporte
  `personnel.export`. Ein privates Original wird nicht über die eigene
  Zeitberechtigung zugänglich.
- Vor Wiederholung werden aktuelle globale Berechtigungen und die konkrete
  Mitarbeiterzuordnung erneut geprüft. Navigationswechsel erzeugt keinen
  neuen Schreibauftrag. Eine verlorene Erfolgsantwort behält ihre ursprüngliche
  Kennung, Eingaben und Empfangsprüfung.
- Eine erfolgreiche Antwort muss mit Mitarbeiter, Quellrevisionen,
  Berechnungsumfang, Beträgen und Korrekturdifferenz übereinstimmen.
  Fremde oder widersprüchliche Antworten lösen den offenen Auftrag nicht auf.
- Exporte werden vor dem Speichern erneut autorisiert. PDF-Prüfsumme und
  JSON-Archivhülle werden geprüft. Während des Downloads entzogene Rechte
  verhindern die Ausgabe. Historische Lese-/Exportfunktionen bleiben bei
  fachlich pausiertem Personalbereich verfügbar, sofern ihre Rechte bestehen.

## Testnachweise

Reproduzierbare Tests:

- `app/test/business_payroll_test.dart`: Betragspräzision, ausdrückliche
  Merkmalswahl, Minijob und regulärer PAP-Umfang, Quellenbindung, exakte
  Korrekturdifferenz, Archivhash, verlorene Antwort, neue Generation,
  Rechteentzug, falscher Mitarbeiter, Seitenwechsel und eigene Lesesicht.
- `web/office/tests/payroll.test.mjs`: entsprechende Clientprüfungen,
  insbesondere globale Wiederholung und Rechteentzug während eines
  Original-/Historienexports.
- `SMARTPLAN_BROWSER_WORKFLOW=payroll node web/office/tests/e2e.cjs`:
  tatsächlicher Chromium-Browser gegen einen wegwerfbaren lokalen Server,
  echte MFA-Anmeldungen zweier synthetischer Benutzer, Profilpflege und
  Vorschau über UI, verlorene Antwort und identische Wiederholung,
  Profilkorrektur und neue Monatsfassung, alte PDF-/JSON-Ausgaben,
  Desktop-/Mobilansicht und Mitarbeiterzugang.

Der Browserlauf prüft Minijob 603,00 EUR → 581,29 EUR Netto, danach eine
nachgewiesene RV-Befreiung → 603,00 EUR mit Differenz 21,71 EUR. Zusätzlich
prüft er einen regulären Standardfall mit 5.000,00 EUR Brutto, 2,90 %
KV-Zusatzbeitrag, Steuerklasse I, Kinderlosenzuschlag und ausdrücklich 0 EUR
ELStAM-Beträgen: 782,41 EUR Lohnsteuer und 3.130,09 EUR Netto.

Die gemeinsamen JSON-Fälle unter `app/test/fixtures/payroll_workflow.json`
sind synthetische echte Backend-Archivantworten. Ihre Verwendung prüft den
Clientvertrag; die unabhängige fachliche Referenzprüfung des Rechenwerks ist
separat dokumentiert. Die Browser-HR-Ausgangsbelege und Monatsquellen werden
per authentifizierter Test-API vorbereitet. Es findet keine externe Meldung,
Nachricht oder Zahlung statt.

Aktuelle Rohlogs liegen unter `work/verification/payroll-{node,flutter,browser}.log`;
Screenshots und synthetische HTTP-Nachweise unter
`work/verification/payroll-browser/`. Die abschließenden ausgeführten
Testzahlen werden im Integrationsstand festgehalten. Flutter-Tests in Linux
und responsive Browserprüfungen ersetzen keine reale Windows-/iPhone-Abnahme.

## Jahresübersicht und Exporte

**Jahresübersicht öffnen** zeigt alle zwölf Kalendermonate. Nicht erfasste Monate
bleiben ausdrücklich fehlend. Summen enthalten je Monat nur die wirksame letzte
Berechnung, nicht zusätzlich die Korrekturdifferenz. Bei einer erfassten reinen
Sozialversicherungsberechnung bleiben Steuer-/Nettosummen unbekannt. Bei einem
leeren Jahr sind Beträge unbekannt statt null Euro. Die Arbeitgeber-Pauschsteuer
bleibt von individueller Arbeitnehmersteuer getrennt.

Beide Clients prüfen Monatszuordnung, Vollständigkeitsmerkmale, Betrags- und
Beitragssummen, kanonische Snapshot-Prüfsumme und die Exportmanifeste. PDF, CSV
und JSON werden mit dem ausdrücklich angezeigten Snapshot angefordert und nach
Größe und SHA-256 geprüft. Bei einer zwischenzeitlichen Korrektur muss die
Jahresübersicht vor dem Export erneut geladen werden. Die reine Jahressummen-
übersicht wird durch die nachfolgend beschriebenen privaten Stamm- und
Zahlungsnachweise ergänzt. Fehlende Pflichtangaben bleiben erkennbar.

## Stammnachweise, Zahlungstage und belegte Vorträge

**Lohnkonto-Nachweise öffnen** ergänzt in beiden Clients die fehlenden privaten
Angaben: Name, Geburtsdatum, deutsche Anschrift, persönliche Steuer-ID,
Arbeitgeber und Steuernummer, tatsächlicher Beschäftigungszeitraum, Herkunft
und Gültigkeit der Steuermerkmale, jährliche Frei-/Hinzurechnungsbeträge sowie
das Religionsmerkmal. Die ausgewählte Profilrevision und ein geschützter
Originalnachweis werden fest gebunden. Ein Wechsel von Minijob zu regulärer
Beschäftigung ist nicht automatisch ein neues Arbeitsverhältnis; widersprüchliche
Beschäftigungszeiträume werden in der Jahresübersicht benannt.

Zahlungsnachweise erfassen ein bis zwanzig tatsächliche Zahlungsteile mit Datum,
Centbetrag und eigener Referenz. Negative Beträge sind tatsächliche Arbeitnehmer-
Nachzahlungen, etwa beim Mindest-RV-Beitrag eines sehr kleinen Minijobs. Ein
Nullbetrag wird nicht als tatsächliche Zahlung ausgegeben. Steuerfreie Bezüge
und ihre Nachweisgrundlage werden ausdrücklich getrennt erfasst. Es erfolgt
keine Banküberweisung. Für einen Monatslauf muss die wirksame Berechnungs- und
Identitätsrevision ausgewählt werden.

Belegte Monatsvorträge erfassen frühere Standardabrechnungen mit Original,
Profil-/Identitätsrevision, Brutto, Netto, Steuern, Beiträgen, Arbeitgeberaufwand
und tatsächlich belegten Zahlungen. Der Server rechnet den Standardfall erneut
und gleicht die Centbeträge ab. Ein aktiver Vortrag und eine lokale Abrechnung
für denselben Monat schließen sich aus. Eine begründete Aufhebung ist eine
Änderung der Jahreszuordnung, keine Rückzahlung. Die UI bietet für jede
Nachweisart begründete Korrekturen und die unveränderliche Historie.

Ein Lohnkonto kann für die belegten Beschäftigungsmonate im unterstützten
Standardfall vollständige Pflichtangaben und Zahlungsnachweise aufweisen,
obwohl nicht alle zwölf Monate Beschäftigung bestanden. Die Clients unterscheiden
diesen Status von vollständigen Kalenderjahressummen, DLS-Prüfexportkonformität,
Systemzulassung und tatsächlich erfolgter Meldung. Unbelegte Zeiträume werden
nicht erfunden.

Auch diese Aufträge behalten bei unklarer Antwort ihren ursprünglichen Inhalt
und ihre Kennung. Vor Wiederholung werden die konkrete Mitarbeiterbindung,
die installierte Funktion und aktuelle Personalrechte geprüft. Die Nachweisart
bestimmt das erforderliche Schreib-/Freigaberecht. Die Bestätigung muss nicht
nur auf dieselben IDs und Revisionen, sondern auch auf den tatsächlich geprüften
Quelleninhalt passen.

Zusätzliche Tests stehen in `app/test/business_payroll_accounts_test.dart` und
`web/office/tests/payroll-accounts.test.mjs`; die Fälle unter
`app/test/fixtures/payroll_accounts.json` sind tatsächliche synthetische
Backend-Archivantworten. Sie prüfen auch widersprüchliche Quellen,
Rechteentzug, unveränderten Wiederholungsauftrag, eigene Lesesicht,
Arbeitnehmer-Nachzahlung und den vollständig belegten Standardfall.

Abschließend bestanden **35 Node-Tests** (16 Payroll, 7 Lohnkonto, 7 Personal,
5 unveränderte Wiederholungen), **34 Flutter-Tests** (16 Payroll, 9 Lohnkonto,
9 Personal), Flutter-Analyse ohne Beanstandung und **ein vollständiger realer
Chromium-Ablauf** mit allen oben beschriebenen Schritten. Dieser prüft zusätzlich
einen im selben Formular korrigierten definitiven Eingabefehler, die unveränderte
Wiederholung nach verlorenem Erfolgsbescheid und einen belegten Septembervortrag.
Mit Septembervortrag, korrigiertem Oktober-Minijob und regulärem November ergeben
sich genau 4.336,09 EUR Netto in den erfassten wirksamen Monaten. Die Stamm- und
Zahlungsnachweise decken den tatsächlich belegten Beschäftigungszeitraum
September bis November ab; Kalenderjahressummen und amtliche Meldestatus bleiben
davon getrennt.

Der Browser wurde mit Namespace-, PID-, Netzwerk- und Seccomp-Sandbox geprüft.
Alle Daten sind synthetisch; keine externe Nachricht, Zahlung, Meldung oder
produktive Arbeitgeber-/Mitarbeiterdatenübertragung wurde ausgelöst.
