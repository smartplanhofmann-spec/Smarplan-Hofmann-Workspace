# Kunden, Projekte und Rechnungsentwürfe: Browseranschluss

Stand: 4. November 2026. Arbeitsbasis `c875ea5a221e5d38533bb7d50a1d96b9c455d22f`; isolierter Arbeitsbaum `/workspace/smartplan-project-flow-20261104`. Die neue Nutzerpriorität stellt Lohn und Buchhaltung zurück. Dieser Abschnitt betrifft Kunden, Projektarbeit und Ausgangsbelege.

## Bestandsbefund und Umsetzung

Die Originaldatei `CRM_ERP_Gesamtziel.txt` wurde vollständig gelesen und unverändert belassen. Ihre Abschnitte 5, 6, 11 und 14 verlangen wiederverwendete Kunden-/Projektdaten und einen zusammenhängenden Ablauf in den Anwendungen.

Der Bestand hat bereits echte Kunden- und Projektdatensätze, versionierte Belege, Angebotsportal, Belegumwandlung und einen gesondert abgesicherten PostgreSQL-Rechnungsaussteller. Die Projektmappe entsteht in dieser Architektur vor dem Angebot und ist dessen gemeinsamer Datenbezug. Eine Projektanlage erklärt noch keine Angebotsannahme oder Auftragszusage.

Zwei konkrete Browserlücken unterbrachen den einfachen Kundeneinstieg:

1. Die direkte Projektanlage übergab nur einen freien Kundennamen. Der Server unterstützt bereits `customer_id`. Bei einem vorhandenen Kunden mit gespeicherter Adresse führte der Freitextvertrag tatsächlich zu einem zweiten Kundendatensatz ohne Anschrift. Der Nachweis steht in `existing-customer-repro.json`.
2. Das Browserkontaktformular bot ausschließlich ein unstrukturiertes Adressfeld. Der Server rät ausdrücklich keine Postleitzahl oder Stadt daraus; solche neu erfassten Kunden lieferten daher keine vollständige Rechnungsanschrift.

`web/office/office.js` verbindet jetzt die vorhandenen Schnittstellen:

- Auswahl eines aktiven vorhandenen Kunden bei direkter Projektanlage; Name, Adresse und E-Mail unterscheiden die Auswahlmöglichkeiten.
- Ein vorausgewählter Projekteinstieg aus der Kundenkarte.
- Eindeutiger Wechsel zwischen vorhandenem Kunden und neuem freien Kundennamen.
- Vollständige Anzeige der gespeicherten Empfängeranschrift einschließlich Postleitzahl, Ort und Land im Belegdetail.
- Strukturierte Kontaktadressen mit Zweck, Bezeichnung, Straße, Postleitzahl, Stadt und Land. Vorhandene Adress-IDs bleiben erhalten; Personen und andere nicht bearbeitete Kontaktdaten werden weiter vom Server bewahrt.

Der Flutter-Bestand besitzt Kundenauswahl und strukturierte Kontaktadressen bereits (`main.dart: ProjectDialog`, `business_contacts.dart`). Diese App-Dateien wurden hier nicht geändert. Das ist ein Quellcodebefund, kein Nachweis einer auf Geräten installierten aktuellen Version.

## Nachweise

Der echte Chromium-Ablauf benutzt die normale Anmeldung mit MFA, reale HTTP-Aufrufe und eine wegwerfbare SQLite-Testfirma. Er legt den Kunden vollständig über das Formular an, ergänzt eine Lieferadresse, erzeugt über beide Projekteinstiege Projekte mit derselben Kunden-ID und prüft, dass nur ein Kunde vorhanden bleibt. Anschließend erzeugt er Angebot, Auftragsbestätigungsentwurf und Rechnungsentwurf mit identischer Anschrift und identischen Positionen: 100,00 EUR netto, 19,00 EUR Steuer, 119,00 EUR brutto. Die Darstellung wurde mit 1440 und 390 Pixeln Breite geprüft. Nachweis: `final-customer.txt`, `final-customer/` und `final-browser-runs.json`. Die vollständige Empfängeranzeige im Rechnungsdetail wird zusätzlich gegen Straße, Postleitzahl, Ort und Land geprüft.

Die zwölf bestehenden Backendtests in `test_business_contact_snapshot` sind grün. Sie prüfen unter anderem Berechtigungen, Mehrdeutigkeit und die unveränderte Anschrift bereits erstellter Belege. Die gezielten Browser-Modultests werden mit deaktivierter Prozessisolation des Node-Testrunners ausgeführt, damit alle einzelnen Testfälle im Protokoll sichtbar sind; Chromium selbst behält Namespace-, PID-, Netzwerk- und Seccomp-Sandboxing bei.

Die SQLite-Browserfirma stellt keine neue Rechnung aus. Der zusätzliche unveränderte Main-Wrapper `run-invoice-chain-pg.py` prüfte den wirklichen Rechnungsaussteller auf der exklusiv reservierten lokalen PostgreSQL-Testdatenbank: **2/2 Tests, 220,563 Sekunden, Exit-Code 0**. Dazu gehören Originalarchiv, getrennte Laufzeitrolle, Konkurrenz-/Berechtigungsfälle und Dump/Wiederherstellung. Der Lauf startete auf `c875ea5`; währenddessen entstand auf Main `cf5e50b` mit ausschließlich Dokumentationsänderungen. Die relevanten Projekt-, Kontakt- und Rechnungsquellen stimmen byteweise überein; siehe `main-backend-bindings.json`. Diese Prüfung ersetzt keinen Browserlauf auf einem produktiven Server.

Der neue Entwurf `backend/online/test_project_customer_journey_pg.py` bleibt separat und wurde hier **nicht ausgeführt**. Er wird nicht als bestandener Nachweis gezählt.

Alle Nachweise liegen unter `docs/evidence/project-customer-flow-2026-11-04/`. Frühere Startfehler des Testaufbaus und zwischenzeitliche Fehler bleiben dort erhalten: zunächst gesperrte lokale Sockets, danach die äußere Chromium-Sandboxumgebung; anschließend ein behobener Sichtbarkeitsfehler des Neukundenfelds und zwei korrigierte Testannahmen zur vorhandenen Belegposition beziehungsweise zum asynchronen Laden des Dialogs. Sie werden nicht als fachliche Rotproben ausgegeben.

## Offen und nächster Anschluss

- Direkte Projektanlage benötigt noch serverseitige Wiederholsicherheit bei verlorenem Antwortpaket. Root bearbeitet diesen getrennten Backendanschluss; `POST /projects` wird in diesem Paket nicht geändert.
- Angebotsannahme im Kundenportal ist ein eigener bereits vorhandener Pfad. Dieser Browsernachweis wandelt Entwürfe um und behauptet keine neue Portalabnahme.
- Aktuelle installierbare Windows-/iPhone-Versionen und gemeinsame Serverbereitstellung werden separat zusammengeführt und auf Geräten geprüft.
- Mehrere Rechnungsadressen bleiben echte separate Adressen; die Auswahl für einen konkreten Beleg ist fachlich von der Kontaktpflege zu unterscheiden. Die hier geprüfte Kundenstrecke verwendet eine Rechnungsadresse und eine Lieferadresse.

Dieser Abschnitt ist implementiert und gezielt getestet, nicht als vollständige oder produktiv freigegebene Gesamtsoftware deklariert.
