# Unternehmensübersicht: gemeinsame EÜR-Quellen lesen

Stand: 09.11.2026. Zuordnung: R04.02, R08.05 und Browser-Gesamtlauf.

Die vollständige lokale Browserfolge zeigte nach den C1/R1/C2/R2-
Geldflussketten einen echten Engpass beim erneuten Anmelden und Öffnen der
Einsatzplanung. Die Anmeldung war erfolgreich. Die Übersicht hielt während
`/business/overview/metrics` länger als 15 Sekunden die Transaktion; auch die
folgenden Metadatenabrufe warteten darauf. Der erste Fehler auf die erwartete
Übersichtsüberschrift und der zweite Fehler mit offenen API-Pfaden und
[Screenshot](evidence/completion-followup-2026-11-09/browser-failure-before.png)
bleiben als getrennte ursprüngliche Befunde erhalten.

`EuerAccounting._cash_source` rekonstruierte für jede Geldquelle erneut die
vollständigen gemeinsamen C2/R2-Journale. Der neue Leseabschnitt verwendet deren
vollständig geprüfte Rekonstruktion innerhalb genau eines serialisierten
öffentlichen EÜR-Aufrufs erneut. Er entfernt seinen Zwischenspeicher bei Erfolg
und Fehler. Es gibt keinen Cache zwischen Aufrufen und keine Änderung an
Originalen, Quellenhashes, Beträgen, Steuerregeln oder Rechteprüfungen.

Die drei neuen Prüfungen vergleichen den vollständigen Bericht und
Quellenkatalog mit dem bisherigen Pfad ohne Wiederverwendung. Sie bestätigen
identische kanonische Inhalte und genau eine vollständige Rekonstruktion je
Aufruf. Neue Geldflüsse, manipulierte Originalquellen und entzogene Rechte
werden mit derselben Serviceinstanz wieder frisch geprüft. Der Fehlerpfad
hinterlässt keinen Cache. Die Manipulation erfolgt ausschließlich in einer
wegwerfbaren synthetischen SQLite-Testdatenbank nach ausdrücklich entferntem
Schreibschutz; die produktiven Schutzregeln werden nicht verändert.

Der Browser-Anmeldehelfer wartet auf den tatsächlichen Abmeldeknopf und die
exakte, vom Server gelesene Benutzeridentität. Ansichts- und Datenladeprüfungen
bleiben bei der jeweiligen Seite. Keine Frist oder Authentifizierungsprüfung
ist gelockert. Der gemeinsame Kalenderablauf ist extrahiert und zusätzlich als
`SMARTPLAN_BROWSER_WORKFLOW=planning-relogin` mit echtem Profil-/MFA-/
Recoverycode-Ablauf prüfbar. Weitere Browserfehler speichern aktive Ansicht,
offene API-Pfade ohne Tokens und einen synthetischen Screenshot.

Die lokalen 29 Fach-/Übersichts-/HTTP-Prüfungen bestehen ohne Skip. Zusätzlich
bestehen alle vier bestehenden tatsächlichen EÜR-PostgreSQL-Fälle in 93,676
Sekunden: echte Rechnung und Quellen, MFA/Rechte, konkurrierende Annahme,
Perioden, Korrektur, unverändertes Exportoriginal, Neustart und tatsächlicher
Dump/Restore. Die eigene kurzlebige PostgreSQL16.15-Instanz ist anschließend
entfernt. Die ersten beiden Fehler des neuen Testaufbaus betreffen ein falsch
gewähltes Snapshotfeld und die absichtlich unveränderliche Zahlungszeile; die
beiden ursprünglichen Protokolle und die korrigierte Prüfung bleiben erhalten.

Eine zusätzliche Kopie genau des zuvor fehlgeschlagenen synthetischen
Browserstands enthält 34 Geldflüsse, 18 C1-, sechs R1-, fünf C2- und zwei
R2-Einträge. Die unveränderte vollständige Unternehmensübersicht stimmt darin
zwischen beiden Lesepfaden kanonisch exakt überein. Der ursprüngliche Pfad
benötigt hier 18,406 Sekunden; der neue 1,863 Sekunden ohne Profiler bzw.
3,219 Sekunden mit Profiler. Dies ist eine einzelne lokale Vergleichsmessung,
keine zugesicherte Produktionslaufzeit. [Vergleich und Quellbindung](evidence/completion-followup-2026-11-09/overview-prefix-comparison.json),
[Profil](evidence/completion-followup-2026-11-09/overview-prefix-profile.txt).

Alle 17 Abläufe der vollständigen lokalen Browserfolge bestehen jetzt ohne
Änderung einer Frist. Der gezielte Profil-/Kalender-/Recovery-Ablauf besteht
ebenfalls. [Gemeinsamer Prüfnachweis](evidence/completion-followup-2026-11-09/overview-verification.json),
[vollständiges Browserprotokoll](evidence/completion-followup-2026-11-09/full-browser-scoped.txt).
Die Produktkorrektur ist als 4b8ec08 und gemeinsam mit 894ecdd auf dem autorisierten
Testbranch veröffentlicht. Die eigene Remote-CI läuft; eine neue Installation
auf dem Kundentestserver ist nicht bestätigt. Der
bereits veröffentlichte Stand ef1259c besteht unabhängig davon alle acht
Development-Jobs und den unsignierten iPhone-Build; siehe
[CI-Nachweis](evidence/completion-followup-2026-11-09/ci-after.json).

Alle Nachweise stehen unter
`docs/evidence/completion-followup-2026-11-09/`. Eine Gesamtabnahme A–G,
signierte iPhone-Auslieferung oder neue Serverrevision folgt daraus nicht.
