# Einmalbezüge v6: PostgreSQL-Prüfung am 04.11.2026

Drei echte Prüfungen in `backend/online/test_business_payroll_oneoff_pg.py` bestehen auf der isolierten PostgreSQL-Testdatenbank. Der vorhandene erste Lauf bestand in 32,190 Sekunden; der getrennte Lauf nach Wiederaufnahme in 27,372 Sekunden. Beide Protokolle bleiben unverändert erhalten. Es sind drei verschiedene Prüfungen, nicht sechs.

## Geprüfte Abläufe

- Zwei getrennte Datenbankverbindungen bestätigen denselben Lohnauftrag parallel. Es entsteht genau eine unveränderte Lohnrevision mit genau einer Anspruchszuordnung.
- Zwei verschiedene Erstanfragen zum selben Einmalanspruch ergeben genau eine Annahme und einen Konflikt 409. Die angenommene Anfrage bleibt unverändert wiederholbar.
- Echte Anmeldung mit MFA und HTTP prüfen private Zugriffsrechte, gesperrten Offlinezugang und die strikten Transportregeln. Datenbankrollen und Unveränderlichkeitstrigger verhindern nachträgliches Umschreiben oder Löschen.
- Nach tatsächlicher Sicherung und Wiederherstellung bleiben Fall, Lohnlauf, Zahlungsnachweis, Anspruchsverbrauch, Steueraufzeichnung, Personaloriginal, Jahreskonto sowie beide PDF-Dateien identisch. Die ursprünglichen angenommenen Aufträge bleiben auch nach Restore wiederholbar.

## Abgrenzung und Protokolle

Die PostgreSQL-Fälle erfassen einen tatsächlichen Nettozahlungsnachweis. Sie buchen in diesem Paket keinen Cash-Import und keine EÜR; diese Geldkette besitzt eigene Domänentests. Spätere Source4-Jahresvorträge, mehrere Boni und abweichende Zuflusstage sind ebenfalls kein Bestandteil dieses Nachweises.

Der erste Wrapperstart dieser Wiederaufnahme wurde ohne Datenbankwirkung durch den bereits vorhandenen Protokollnamen abgewiesen. Der anschließende separate Lauf begann, bevor die Anweisung eintraf, den vorhandenen Nachweis ohne Wiederholung zu sichern; er wurde geordnet beendet. Es wurden keine neuen Tests oder Produktänderungen vorgenommen.

Dauerhafter maschinenlesbarer Nachweis: [payroll-oneoff-postgres-2026-11-04.json](evidence/payroll-oneoff-postgres-2026-11-04.json). Darin stehen Prüfsummen beider Originalprotokolle sowie nach dem zweiten Lauf gelesene Quellprüfsummen. Die Quellprüfsummen sind ausdrücklich kein eingefrorenes Dateimanifest des ersten Laufs.

## Ergänzung: bezahlter Einmalbezug in späterer Jahresbasis

Die gezielte Integration vom 04.11.2026 umfasst jetzt vier PostgreSQL-Fälle
(44,607 Sekunden, alle bestanden). Der zusätzliche Fall erzeugt eine
Jahresbasis aus einem tatsächlich abgeschlossenen und mit Original belegten
Source4-Zahlungsnachweis über die echte HTTP-API. Er prüft den früheren Bonus,
die vier getrennten SV-Basen, die kompakte Originalreferenz und die verweigerte
Einsicht durch einen Techniker. Nach tatsächlichem Backup/Restore bleiben
angenommener Jahresauftrag, Originalauflösung, Lohnlauf, Zahlungsnachweis,
Anspruchsverbrauch und PDFs identisch.

Der neue Nachweis ergänzt die vorstehenden historischen Dreierläufe:
[`payroll-oneoff-pg-annual-integration-2026-11-04.json`](evidence/payroll-oneoff-pg-annual-integration-2026-11-04.json).
Er prüft synthetische Daten in der entbehrlichen lokalen Datenbank und erklärt
keine vollständige fachliche Freigabe aller Einmalbezugsfälle.

Nach der zusätzlichen Korrektur des bereits verbrauchten eigenen
Märzklauselanspruchs wurde diese Viererprüfung auf dem finalen Backendstand
wiederholt: **4/4 bestanden, 46,480 Sekunden**. Neue Quellprüfsummen und das
unveränderte neue Protokoll stehen in
[`payroll-oneoff-pg-annual-final-2026-11-04.json`](evidence/payroll-oneoff-pg-annual-final-2026-11-04.json).
Der vorherige Nachweis bleibt als Beleg seines damaligen Stands erhalten.

