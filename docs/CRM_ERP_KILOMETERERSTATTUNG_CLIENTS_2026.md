# Kilometererstattung im Browser und in der nativen App

Gesamtziel §9 / R09.02: Der ausdrückliche Einstieg **Private Pkw-Kilometererstattung** ergänzt die vorhandenen Reiseoberflächen. Der fachliche Vertrag, die Grenzen und die amtlichen Quellen stehen im [Kilometervertrag](CRM_ERP_KILOMETERERSTATTUNG_VERTRAG_2026.md). Dieser Abschnitt ersetzt weder den bisherigen Reisestandard noch die Auszahlung durch eine neue Geldstrecke.

## Zusammenhängender Ablauf

Die Person wählt ihre unveränderten Wohn-/Stättennachweise, privaten Fahrzeug- und Erklärungsoriginale sowie jeden Streckennachweis. Gefahrene Teilstrecken werden in ganzen Metern mit tatsächlicher Ortsfolge und Berliner Zeitlage erfasst. Die sechs Voraussetzungen stehen bei Neuanlage und Korrektur ausdrücklich unbestätigt. Fehlende Erklärungen bleiben im Entwurf sichtbar und verhindern eine Freigabe. Erst ein anderer Berechtigter prüft und bestätigt die eingereichte Fahrt.

Dieser enge Ablauf gilt für einen Mitarbeiter, einen inländischen Fahrtag im Jahr 2026 und einen privat gestellten Pkw mit selbst getragenen Fahrzeugkosten. Pendel-/Familienheimfahrten, Unternehmerfahrten, Dienstwagen, Mitfahrt ohne eigene Kosten, Mischfahrten, andere Gebiete, Ausland, Unterkunft, Verpflegung und zusätzliche Auslagen gehören nicht dazu. Die Berechnung verwendet die belegten Originalmeter und rundet die vollständige Fahrt genau einmal. Es wird kein weiterer Betrag zum Lohnnetto addiert.

Die tatsächliche Erstattung und eine spätere tatsächliche Rückzahlung verwenden den bestehenden TravelCash-Weg, seine Kontofassungen und privaten Zahlungsoriginale. Eine geänderte Anspruchshöhe verändert keinen früheren Geldnachweis. Die ursprünglichen Fahrt-, Abrechnungs- und Zahlungsfassungen bleiben in der Historie und in ihren Originalexporten erhalten.

## Private Pfade und unbestätigte Antworten

Neue private Fahrten, Quellen, Abrechnungen, Zahlungsnachweise und Auftragsquittungen bleiben vollständig unter `/personnel/travel/mileage`. Die allgemeine reine Zeitauflösung wird für die bereits vorhandene Berliner DST-Auswahl genutzt. Sie ist kein Rückfallweg für private Mileage-Daten. Alte Reise-Schreibpfade können keine Mileage-Aufträge übernehmen. Der Lesemarker `travel_private_car_mileage_read` macht historische Kilometeroriginale erreichbar; neue Schreibaktionen verlangen zusätzlich das Schreibmerkmal, aktiven Bereich, Schreibmodus und frische Personenrechte.

Nach verlorener Antwort wird zuerst die genaue ursprüngliche private Quittung geprüft. Ein bereits angenommener Auftrag benötigt keinen zweiten POST. Request-ID, unveränderter Body, Akteur, innerer Auftragshash, Ergebnishash, Originalreferenzen und Fassungen werden geprüft. Ein Entzug des Schreibmerkmals verhindert neue Schreibversuche, verhindert aber nicht das lesende Bestätigen einer bereits angenommenen Originalquittung bei fortbestehendem Leserecht.

Die private Ansicht hält unbestätigte Eingaben im Arbeitsspeicher. Schließen, Verlassen oder Entzug des privaten Lesekontexts verwirft private Eingaben entsprechend dem bestehenden Reiseverfahren. Es wurde keine neue dauerhafte Speicherung oder Wiederherstellung nach Prozessneustart eingeführt. Ein nativer State-Wechsel auf eine andere Sitzung, Person oder einen anderen Reisemodus wischt die ursprünglichen privaten Daten und bindet keine alte Vorgangskennung an den neuen Kontext.

## Tatsächliche Prüfungen

- **12 neue Browser-Vertragsfälle** und **6 betroffene Browser-Testdateien** bestehen. Sie verwenden die echte Backendfixture mit ursprünglichen Fahrt-/Freigabe-/Zahlungsquittungen und ihren unveränderten Hashes.
- **36 native Fälle**, davon 12 neue und 24 bestehende Reise-/v3-/Geld-/Provenancefälle, sind grün. Die drei betroffenen Dartdateien sind fehlerfrei analysiert. Der State-Wechselbefund wurde zuerst rot reproduziert und anschließend für Sitzung, Person und Modus grün nachgeprüft; alte Fehlerprotokolle bleiben erhalten.
- Der echte Chromium-/MFA-/HTTP-Ablauf verwendet getrennte Antragsteller- und Prüferkonten. Er prüft 100 km / 30 EUR, drei verlorene angenommene Antworten mit reiner Statusbestätigung, die unabhängige Korrektur auf 50 km, das unveränderte 30-EUR-Zahlungsoriginal und eine gesondert belegte 15-EUR-Rückzahlung.
- Die tatsächlichen Zahlungen werden über die vorhandenen EÜR-Vorschau-/Bestätigungsendpunkte übernommen: 30 EUR Aufwand, nach belegter Rückzahlung netto 15 EUR. Öffentliche Geldquellen enthalten weder Fahrzeugkennzeichen noch private Streckendateinamen. Die allgemeinen alten Reiselisten übernehmen V4 nicht.
- Alte Originalfassungen, ihr PDF-Download und die 390-Pixel-Ansicht bestehen im echten Browser. Chromium behält die überprüfte Namespace-/PID-/Netzwerk-/Seccomp-Sandbox. Die temporäre POSIX-Testwurzel wird vor Storagebindung kanonisiert.

[Maschineller Nachweis](evidence/private-car-mileage-clients-2026-11-09/verification.json). Die abschließende gemeinsame Prüfung nach dem separat koordinierten Backendfix zur Überlappung einzelner Streckenoriginale wird hier vor Übergabe ergänzt. Die beschriebenen Nachweise sind lokale Test-/Cloudnachweise; Liveinstallation und reale Geräteabnahme sind nicht damit durchgeführt.
