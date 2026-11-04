# Gemeinsame Prüfung: Anfangsbestände, Katalogoriginale und Source4

Stand: 04.11.2026. Der neue eingefrorene Entwicklungsstand baut auf `5d9e7fd` auf.
Er ergänzt belegte Geldkonto-Anfangsbestände in Backend, Browser und Flutter
sowie den vollständigen Browserimport bestehender CSV-v1-/begrenzter DATANORM-
Kataloge mit unveränderlichen Originalen, serverseitiger Vorschau und Historie.
Die bestehende Source4-Lohnkette bleibt Bestandteil der gemeinsamen Prüfung.

| Prüfung | Tatsächlich ausgeführtes Ergebnis |
| --- | --- |
| Backend vollständig | 1.566 ausgeführt, 1.565 bestanden, ein Windows-spezifischer Skip unter Linux; 537,315 s Testlauf |
| Browserverträge vollständig | 522/522 benannte Nodefälle; keine Auslassung |
| Flutter vollständig | 1.118/1.118, einschließlich tatsächlicher HTTP-Widgetabläufe |
| Flutter-Analyse | Keine Befunde |
| Native-/Windows-Paketprüfung | 16/16 |
| PostgreSQL mit getrennten Rollen | Zehn bestehende Source4-/Opening-/Katalogfälle grün; zusätzlicher gemeinsamer befüllter Katalog-/Opening-Restore grün |
| Echter Chromium | Beide zusammengeführten Workflows für Anfangssalden und Katalogimport grün; aktive Namespace-/PID-/Netzwerk-/Seccomp-Sandbox |

Alle 1.626 im [Quellmanifest](evidence/opening-catalog-integrated-source-snapshot-2026-11-04.json)
erfassten Dateien waren nach diesen Prüfungen unverändert. Erst danach wurden
dieser Ergebnisbericht, die Rohprotokolle und die globalen Fortschrittsdokumente
ergänzt. [Maschinenlesbarer Nachweis](evidence/opening-catalog-integrated-regression-2026-11-04.json).

## Fachliche Ergebnisse

Anfangssalden binden tatsächliches Original, Konto, bestätigten Buchführungsbeginn
und ausdrückliche Annahme. Sie erzeugen keine neue Zahlung, EÜR-Einnahme oder
Vorsteuer. Fehlende Bestände bleiben unbekannt. Beide Oberflächen zeigen belegte
Teilbestände getrennt vom vollständigen Kontenumfang, bieten Korrektur/Aufhebung
und wiederholen unklare Annahmen mit unveränderter Vorgangskennung. Ein tatsächlich
reproduzierter Summenfehler wurde behoben: zulässiger Anfangsbestand plus Zahlung
darf als abgeleitete Summe mehr Stellen besitzen als eine Einzeleingabe. Positive
und negative echte Grenzfixtures werden im Backend und beiden Clients geprüft.

Katalogimporte bewahren tatsächliche Bytes und Annahmen; alte v1-Imports ohne
Original sind ausdrücklich als solche gekennzeichnet. Eine rein lesende
Servervorschau bildet dieselbe Neuanlage/Änderung/No-op-Entscheidung wie die
Annahme ab. Der echte Browserlauf umfasst verlorene Antworten, DATANORM-
Preiszuordnung, Rechteentzug, Hintergrundwechsel, 390 Pixel und eine genau
2 MiB große Unicode-Datei mit 2.000 Artikeln. Neue Runtime-Dateien sind in
beiden Paketlisten und in der tatsächlichen Windows-CI-Kopierliste enthalten.

Die neue gemeinsame PostgreSQL-Gegenprobe stellt Originale, Artikelstände und
Annahmen sowie Anfangssalden aus einem tatsächlichen Dump wieder her. Ihr erster
Lauf hatte eine falsche Testannahme: ein unveränderter, lesender Katalog-v1-Replay
sollte pauschal an der Finanzfreigabe scheitern. Der korrigierte Test beweist dessen
unveränderte Antwort und unveränderten Datenbankfingerprint; der Anfangssalden-
Schreibpfad bleibt bis zur gesonderten Finanzfreigabe gesperrt. Keine Produktsperre
wurde für diesen Test entfernt. Das Erstprotokoll bleibt erhalten.

## Fortlaufende Arbeit

Source5 für einen Bonus mit unterschiedlichen tatsächlichen Zahlungstagen,
historische lineare Anlagen, datierte Katalogpreise v2 und die native Ergänzung
der Kataloghistorie entstehen in getrennten Arbeitsständen. Ihre eigenen
Nachweise werden nicht in die obigen Gesamtzahlen eingerechnet. Weitere Lohn-,
Steuer-, Melde- und Unternehmensregelfälle sowie echte Geräte-/Betriebsabnahmen
bleiben Teil des Gesamtziels. Dieser Checkpoint ist keine Fertigmeldung der
vollständigen Software und keine produktive Bereitstellung.
