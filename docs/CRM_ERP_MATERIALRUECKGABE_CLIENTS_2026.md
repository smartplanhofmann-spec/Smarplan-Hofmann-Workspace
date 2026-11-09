# Materialrückgabe zur Originalentnahme

Gesamtziel §6/7, R07.01, Abnahmen B/C: Browser und native App bieten jetzt den vollständigen Weg **Material zurückgeben**. Der vorhandene Serververtrag bleibt erhalten. Eine Rückgabe ist eine neue unveränderliche Lagerbewegung; die ursprüngliche Entnahme wird nicht überschrieben.

## Bedienung und Bindung

Der Nutzer wählt eine noch offene Originalentnahme. Artikel und Projekt stammen fest aus diesem Original; eine freie Umbuchung auf ein anderes Projekt oder einen anderen Artikel ist hier ausgeschlossen. Die tatsächlich zurückgegebene Menge bleibt zunächst leer. Ziellager und tatsächliche Rückgabe werden ausdrücklich bestätigt. Das Journal bestimmt die bereits zurückgegebene und die noch zulässige Menge mit genau vier Dezimalstellen; dafür werden keine Gleitkommazahlen verwendet.

Der Auftrag enthält `kind: return`, die Originalentnahme als `reversal_of`, deren Artikel und Projekt, Ziellager, Menge und Notiz. Quelllager und neuer Einstandspreis werden nicht gesendet. Der Server übernimmt den historischen Entnahmewert einschließlich des verbleibenden Rundungsrests bei der letzten Vollrückgabe. Eine spätere Artikelpreisänderung bewertet die alte Entnahme nicht neu.

Berechtigte Lagerrollen benötigen kein Finanzleserecht. Ihre Quellen und Quittungen bleiben operativ; Artikelpreisendpunkte werden dafür nicht geladen. Einstandskosten werden nur angezeigt, wenn sie im erlaubten Original geliefert werden. Aktuelle Projekt-/Lagerrechte und das aktive Ziellager werden vor neuen Schreibversuchen geprüft.

Eine verlorene Antwort hält denselben ursprünglichen Auftrag mit derselben Request-ID fest. Die Wiederholung prüft aktuelle Rechte; sie behandelt eine durch die bereits angenommene Rückgabe verringerte Restmenge nicht als neue Rückgabe. Die Bestätigung muss zu Artikel, Projekt, Originalentnahme, Ziellager, Menge und Urheber passen und wird aus dem Lagerjournal zurückgelesen. Bei fehlender eindeutiger Bestätigung bleibt der Auftrag offen.

Im ursprünglichen Stand dieses Abschnitts bleiben offene Aufträge nur im Arbeitsspeicher derselben angemeldeten Sitzung erhalten. Die native App ergänzt inzwischen ein [verschlüsseltes Originaljournal](CRM_ERP_ONLINEAUFTRAEGE_NEUSTART_2026-11-09.md) für gebundene Server. Nach vollständigem App-Neustart wird derselbe Auftrag frisch berechtigt wiederaufgenommen; ein Ersatzauftrag bleibt gesperrt. Der Browser bleibt sitzungsgebunden. Der separat nachgewiesene Backend-Neustart erhält die bereits angenommenen Quittungen und erlaubt die unveränderte Wiederholung.

## Tatsächliche Nachweise

- **3 SQLite-/HTTP-Fälle** und **4 echte PostgreSQL-Fälle** bestehen. PostgreSQL läuft mit eingeschränkter Runtime-Rolle; Neustart, echter Dump/Restore, entzogene Rechte und zwei konkurrierende Rückgaben mit Ergebnis 201/409 sind geprüft.
- Die echte Kette erhält 10 Einheiten zu 10 EUR, entnimmt 6 und gibt 2 zurück: Lagerbestand 6, Projektmaterialkosten 40 EUR. Weitere Rückgaben von 1 und 3 stellen den Bestand 10 wieder her und heben genau die ursprünglichen Projektmaterialkosten auf. Übermengen werden abgewiesen.
- Die gesonderte Rundungskette liefert Rückgabewerte von 0,3333 / 0,3333 / 0,3334. Die letzte Rückgabe übernimmt den Originalrest; die ursprünglichen Bewegungen bleiben unverändert.
- **8 neue Browser-Vertragsfälle**, **7 betroffene Browser-Testdateien** und **36 native Tests**, darunter 11 neue Fälle, sind grün. Die Analyse der drei betroffenen Dartdateien meldet keine Probleme. Der native HTTP-Test bricht die Verbindung nach angenommener Rückgabe ab und prüft die gleiche Request-ID und denselben Body bei der Wiederholung.
- Der echte Chromium-/MFA-/HTTP-Ablauf besteht einschließlich Originalauswahl, Preisänderung nach Entnahme, lokaler Mengenbegrenzung ohne POST, verlorener Antwort, Teil-/Vollrückgaben, unveränderter Originale, Projektkosten, Lagerrolle ohne Finanzrechte und 390-Pixel-Ansicht. Namespace-/PID-/Netzwerk-/Seccomp-Sandbox bleiben aktiv.
- Ein unabhängiger Reviewpunkt wurde echt reproduziert: Eine verspätete Bewegungsantwort öffnete den bereits geschlossenen Wizard erneut und ersetzte einen anderen Dialog. Der vorhandene Lade-Stamp berücksichtigt nun auch die Dialoggeneration; dieselbe Gegenprobe besteht im abschließenden Browserlauf.

Die echte Fixture entsteht durch `scripts/generate-material-return-fixture.py`; ihre Originale und Hashes werden nicht von Hand nachgebaut. Frühere Test-/Umgebungsfehler und der rote Dialognachweis bleiben erhalten. CI führt die neue Browserkette und den PostgreSQL-Test zusätzlich zu den vorhandenen automatischen Modul-/Appprüfungen aus.

Genaue Datei-/Fixturehashes und Prüfzahlen: [verification.json](evidence/material-return-clients-2026-11-09/verification.json). Die Nachweise gelten für kontrollierte Testdaten und die Cloud-Testumgebung; eine Liveinstallation oder reale Geräteabnahme wurde damit nicht ausgeführt.
