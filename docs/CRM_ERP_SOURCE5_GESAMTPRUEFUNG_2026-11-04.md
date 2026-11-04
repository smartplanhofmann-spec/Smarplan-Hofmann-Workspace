# Integrierte Source5-Lohnabläufe

Stand: 04.11.2026. Auf Basis `4c2f008` sind der private Source5-Fachkern,
Browser und native App sowie die reduzierten eigenen Mitarbeiterbelege
zusammengeführt. Anfangssalden und Katalogoriginale bleiben erhalten.

Ein vollständiger ursprünglicher Einmalanspruch lässt sich mit unterschiedlichen
tatsächlichen Zahlungstagen für laufenden Lohn und Bonus abrechnen. Bereits
bezahlte laufende Teile bleiben unverändert gebunden, auch nach mehreren noch
unbezahlten Korrekturfassungen. Neue Zahlungsteile verlangen ihre ausdrückliche
Zuordnung zum ursprünglichen Ereignis. Ein Zahlungsnachweis löst keine
Banküberweisung aus. Eigene Mitarbeiterbelege enthalten keine privaten
Jahresquellen oder internen Anspruchs-/Ereigniskennungen.

## Vollständige Prüfungen des zusammengeführten Standes

| Prüfung | Ergebnis |
| --- | --- |
| Backend | 1.627 ausgeführt, 1.626 bestanden; ein vorhandener Windows-spezifischer Test unter Linux ausgelassen; 762,619 s |
| Browsermodule | 555/555 bestanden; 9,649 s |
| Flutter | 1.208/1.208 bestanden; 450,177 s |
| Flutteranalyse | Keine Befunde; 17,900 s |
| Quell-/Installationspakete | 16/16 bestanden; 12,465 s |
| Tatsächliche Browserabläufe | Source5 einschließlich eigener PDF-/JSON-Belege, bestehendes Source4 und Anfangssalden jeweils über Chromium/MFA/lokales HTTP bestanden |
| PostgreSQL | Drei bereits ausgeführte Source5-/Own-Integrationsfälle einschließlich tatsächlicher Wiederherstellung; alle dort gebundenen Quellhashes unverändert |

Die drei Browserabläufe dauern 56,562, 46,868 und 25,288 Sekunden. Chromium
bestätigte Namespace-, PID-, Netzwerk- und Seccomp-Isolation vor dem Zugriff.
Die App-Prüfung läuft in der Flutter-Testumgebung; eine installierte Windows-
oder iPhone-App wird damit nicht behauptet.

Alle jeweiligen Testeingaben blieben während des Laufs und bis zum finalen
Hashvergleich unverändert. Der [Gesamtnachweis](evidence/source5-integrated-regression-2026-11-04.json)
bindet die Protokolle und [1.138 Eingabedateien](evidence/source5-integrated-source-snapshot-2026-11-04.json).
Die ursprüngliche Zieldatei bleibt bytegleich. Der PostgreSQL-Nachweis wurde
vor der letzten statischen Browserdatei-Registrierung ausgeführt; diese ist
durch die aktuelle Backend- und echte Browserprüfung abgedeckt. Es werden keine
nicht ausgeführten zusätzlichen PostgreSQL-Fälle behauptet.

## Tatsächlich gefundene und korrigierte Fehler

- Eine wiederholte unbezahlte Korrektur konnte einen bereits bezahlten
  laufenden Vorlauf verlieren. Die Zahlungskette prüft nun alle relevanten
  früheren Fassungen und erhält den tatsächlichen Ursprung.
- Ein später Browser-Vorschauabschluss konnte einen geschlossenen privaten
  Dialog erneut öffnen. Lokale Ansichtskennungen verhindern das.
- Fehlende oder herabgesetzte Versionsmarker konnten neue Zahlungsfelder
  an der speziellen Leserprüfung vorbeiführen. Browser und App verlangen
  bei jedem neuen Formatmerkmal die vollständige passende Lohnquelle.
- Ein entfernter App-Bildschirm ließ seinen privaten Dialog im erhaltenen
  Navigator stehen. Nur seine eigenen Dialogrouten werden jetzt nach dem
  aktuellen Aufbau geschlossen; ein Sitzungswechsel wird ebenso behandelt.

Die unveränderten unabhängigen Gegenfälle, ursprünglichen Fehlprotokolle und
Nachträge bleiben im Repository. Frühere erfolgreiche Teilprüfungen werden
nicht nachträglich als Prüfung der späteren Korrekturen ausgegeben.

## Verbleibender Umfang

Mehrere tatsächliche Bonus-Steuergruppen, finanzielle Folgekorrekturen bereits
bezahlter Source5-Läufe und Rückzahlungen bleiben gesperrt und erhalten eigene
weiterzuführende Verträge. Historische Anlagen, datierte Katalogpreise und
unternehmensweite Ereignisregeln sind separate laufende Pakete. Ein im
Anlagenablauf reproduzierter gleichzeitiger Sitzungsabruf wird dort mit einer
gemeinsam abgewarteten Antwort korrigiert; dieser Fix gehört noch nicht zu
diesem Zwischenstand. Der bisherige Pfad lehnt konservativ ab.

Dieser Stand ist ein geprüfter lokaler Entwicklungsabschnitt. Das Gesamtziel,
die vollständige Buchhaltung, Fach-/Geräteabnahmen und produktive Freigaben
sind damit nicht abgeschlossen.
