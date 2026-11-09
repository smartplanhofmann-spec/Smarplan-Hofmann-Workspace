# Materialrückgabe im gemeinsamen Produktstand

Die Browser- und App-Erweiterung ist mit Offline V2, Service-Journal,
Wartungsverträgen, Projektmeilensteinen, V10/V11-Lohnfällen und
Browserzeitabrechnung zusammengeführt. Die fünf Produktionsdateien und der
tatsächliche Browserworkflow sind bytegleich zum eigenständig geprüften
Materialcommit 564fc7d. Produktstand der zusätzlichen gemeinsamen Tests: 4c72f08.

Der [Einzelnachweis](CRM_ERP_MATERIALRUECKGABE_CLIENTS_2026.md) enthält vier
tatsächliche PostgreSQL- und drei SQLite-/MFA-/HTTP-Fälle, vollständigen
Chromiumablauf, historische Preise, Teil-/Vollrückgabe, Rundungsrest,
Bestand/Projektkosten, Rechte, Konkurrenz und echten Dump/Restore. Eine
Lagerrolle ohne Finanzleserecht kann zurückgeben, ohne Preise nachzuladen.

Der zusätzliche Review reproduziert einen echten Dialogfehler: Eine verspätete
GET-Antwort ersetzt nach Schließen den neu geöffneten Lagerortdialog durch die
alte Materialrückgabe. Die bestehende Kontextprüfung berücksichtigt jetzt auch
die Dialoggeneration. Dieselbe tatsächliche Gegenprobe besteht danach; der
Fehlnachweis bleibt erhalten.

## Gemeinsame Ergebnisse

| Prüfung | Ergebnis |
| --- | --- |
| Alle Browsermodultests | 980 bestanden, kein Fehler/Skip, 13,607 Sekunden |
| Material-, Bestands-, Preis-/Belegzugriff, Offline- und Service-HTTP-Fälle | 41 bestanden, kein Fehler/Skip, 1:05 Minuten im Fortschrittslog |
| Gesamte Appanalyse | Kein Befund, 26,9 Sekunden |
| Ursprüngliche Finanz-/Lohnquellen | 32 alte Rechenmodule und ursprüngliche Zahlungsarithmetik unverändert |
| Ursprüngliches Gesamtziel | Unverändert, 23.863 Bytes, ursprünglicher SHA-256 bestätigt |

[Rohlogs und Quellbindung](evidence/material-return-integration-2026-11-09/verification.json).
Die CI ruft sowohl die neue tatsächliche PostgreSQL-Suite als auch die
SQLite-/HTTP-Suite und den vollständigen Browserworkflow ausdrücklich auf.

Der vorherige vollständige App-Lauf auf 8273852 besteht 1.770 Fälle und separat
drei native PDF-Fälle. Er wird nicht zu einem neuen vollständigen Lauf auf dem
Materialstand umgedeutet. Die drei neuen CI-Testaufbaukorrekturen sind ebenfalls
integriert; [Nachweis](CRM_ERP_CI_OFFLINE_FIXTURES_2026-11-09.md).
Eine neue Remoteprüfung, Serverinstallation oder reale Geräteabnahme wird
durch die lokalen Ergebnisse nicht ersetzt.

Die neue Rückgabe verwendet den vorhandenen Online-Lagervertrag. Offene
Clientaufträge bleiben innerhalb der aktuellen Sitzung im RAM erhalten;
Prozessneustartpersistenz und Offline-Materialrückgaben sind damit nicht
implementiert. Für die ursprünglich entnommenen Mengen bleiben serverseitiger
Wiederholungsschutz, Restmengengrenze und historische Bewertung verbindlich.
