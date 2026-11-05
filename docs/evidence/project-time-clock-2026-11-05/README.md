# Exakte Offline-Assertions und die Testuhr

Der Remote-Job auf e7089a6 besteht Browser/Business vollständig, alle Server-,
Windows-, Simulator-, Update- und HTTPS-Jobs. Ein Linux-App-Fall scheitert an
7199 statt der erwarteten 7200 Sekunden. Alle übrigen 1620 App-Fälle bestehen.
Die Testsuite verwendet DateTime.now mit Mikrosekunden. Ein von diesem
Zeitpunkt relativ angelegtes einstündiges Teilintervall kann über Berliner
Mitternacht laufen. Die bestehende _split-Berechnung schneidet jeden
Kalendertagesabschnitt getrennt auf ganze Sekunden ab. Zwei fractional
Tagesanteile ergeben dadurch in diesem Fall zusammen 3599 statt 3600 Sekunden.

Der konkrete Integrationstest prüft dauerhafte Offline-Ereignisse, die
Übernahme bereits auf dem Server begonnener Schichten, exakte Wiederholung,
Vermeidung doppelter Starts sowie Fotooriginale, Belege und Scoped-Grant-
Grenzen. Seine exakten Ganzsekunden-Erwartungen verwenden nun ausdrücklich
eine ganzsekündige Testuhr. Die Assertions 7200/3600, die tatsächliche API,
Warteschlange, Neustarts, Originale und Rechte bleiben erhalten.

Der unveränderte vollständige HTTP-Fall reproduziert vor der Korrektur mit
2026-11-04T05:30:00.123456Z exakt den CI-Befund. Mit der korrigierten Testuhr
besteht er mit 01:30, 05:30 und 12:30 UTC, darunter derselbe Tageswechsel.
Die ersten fehlgeschlagenen Aufrufe hatten den vorhandenen clang-19 nicht im
PATH und erreichten keine Produktfälle; ihre Logs bleiben getrennt erhalten.
Die temporären Testdateien werden nach jedem tatsächlichen Lauf entfernt.

Das ist ausdrücklich keine Änderung der produktiven Subsekunden-Rundung.
Bestehende gespeicherte und freigegebene Tageswerte werden nicht neu berechnet.
Eine künftig summenerhaltende Aufteilung von Sekundenbruchteilen müsste mit
expliziter Berechnungsversion und bestandserhaltender Migration erfolgen;
dieser Nachweis behauptet eine solche Funktion nicht. Der aktuelle
Produktstand rechnet die einzelnen Tagesabschnitte in ganzen Sekunden.
