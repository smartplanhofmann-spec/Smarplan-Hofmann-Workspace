# Unternehmenswechsel, Assistent und Sprache – integrierte Prüfung

Auf dem Jahresvortragsstand `657e565` schließen zwei native Produktdateien sechs
unabhängig belegte Fehlerabläufe: alte Firmendaten und verspätete Antworten nach
Sitzungswechsel, zurückbleibende private Dialoge nach Wechsel oder Seitenabbau,
eine weiterlaufende Aufnahme nach Kontextwechsel sowie Fachabfragen nach einer
Hintergrundunterbrechung während des ersten Rechteabrufs. Die alten roten
Teststände und Originalquellen bleiben unverändert erhalten.

Eigene private Dialogrouten werden gezielt entfernt; eine fremde darüberliegende
Route bleibt erhalten. Unbestätigte Aufträge bleiben an ihre ursprüngliche
Sitzung gebunden. Es wurde keine serverseitige Freigabe fremder Firmendaten oder
Anbieterübertragung aus diesen lokalen Darstellungsfehlern behauptet.

## Abschließende Prüfungen auf dem gemeinsamen Stand

- 91 betroffene native Assistenten-, Sprach- und Ereignisfälle bestanden
  einschließlich tatsächlicher lokaler HTTP-Strecken (25,930 Sekunden).
- Sieben tatsächliche Zwei-Prozess-HTTP-Fälle und ein CI-Konfigurationsfall
  bestanden (25,849 Sekunden Testlauf; 26,830 einschließlich Start). Getrennte
  Firmen, Originale, Suchquellen, Archive, Ereignisse, private Rechte und echte
  lokale Parserworker wurden mit synthetischen Daten geprüft.
- Alle 848 Browsermodulfälle bestanden (6,748 Sekunden); App-Analyse ohne
  Befund (15,195 Sekunden); 16 Paketprüfungen bestanden (12,346 Sekunden).

Der [Gesamtnachweis](evidence/company-isolation-integrated-regression-2026-11-04.json)
bindet Protokolle und endgültige Quellen. Kein erfasster Quelltext änderte sich
während oder nach diesen Abschlussprüfungen. Der erste eingeschränkte Node-Lauf
lieferte nur 98 Dateisummen und einen unaufgelösten Unterprozessfehler. Er wird
nicht als erfolgreiche Testabdeckung gezählt. Der unveränderte Teststand bestand
mit den erforderlichen lokalen Prozessrechten alle 848 Einzeltests.

Vier echte PostgreSQL-Fälle mit getrennten Firmenrollen/Datenbanken und ein
Linux-UID-Dateirechtefall waren bereits im isolierten Ausgangsbaum auf `2e2ed5c`
bestanden. Ihre Logs bleiben als frühere Nachweise erhalten; sie werden nicht
als erneute PostgreSQL-Abnahme dieses Integrationsstands ausgegeben. Diese
Integration ändert keine Backend-Produktdatei, Datenbankstruktur oder Finanzregel.
Finanzhorizont 15 und Restorebericht 16 bleiben erhalten. Die umfassende
Finanzprüfung des direkten Vorgängers bleibt ihrem eigenen Quellstand zugeordnet.

## CI und Beweissicherung

Der bestehende Schutz erlaubt Wegwerf-Provisionierung nur auf Port 55433. Die
CI verwies fälschlich auf 5432 und scheiterte am unveränderten Schutz. Serviceport
und Test-DSN stimmen jetzt überein. Die neuen Isolationstests und der tatsächliche
getrennte Parserablauf sind registriert. Ein GitHub-Lauf wurde nicht ausgelöst.
Beide Quellpakete und Windows-CI enthalten identische 144 Backend- und 213
Betreiberpfade; sämtliche Jahresvortragsregistrierungen bleiben erhalten.

Die parallelen Bearbeiter erreichten nach ihren finalen Logs das Nutzungslimit,
bevor die Übergabemanifeste fertig waren. Root prüfte den hinterlassenen
20-Dateien-Snapshot und die grünen Originalprotokolle, archivierte sie unverändert
und kennzeichnete die ergänzten Manifeste ausdrücklich als von Root zusammengestellt.
Die unabhängigen Aussagen werden nicht um nachträglich erfundene Testläufe ergänzt.

R03.04 und Gesamtabnahme A bleiben offen: produktive Host-/Systemd-/TLS-Grenzen,
reale Geräte und externe unabhängige Sicherheitsprüfung sind damit nicht vollständig
abgenommen. Kontrollierter Recorder und lokale Anbieter-Testdoubles ersetzen keine
Mikrofon- oder Liveanbieterabnahme. Keine Produktivmigration, Zahlung, Meldung,
Bereitstellung oder externe Nachricht wurde ausgeführt.
