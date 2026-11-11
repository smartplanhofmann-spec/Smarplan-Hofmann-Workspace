# Auslagenkorrektur erhält installierte Migrationsverträge

Stand: 11.11.2026. Der erste Auslagenkandidat 3c824c1 ist nicht zur Installation
freigegeben. Seine bisherigen lokalen und gemeinsamen Einzelprüfungen bleiben
mit ihrer tatsächlich geprüften Quelle erhalten. Ein zusätzlicher echter
Altbestandscheck findet eine zuvor nicht abgedeckte Updategrenze.

## Tatsächlicher Gegenfall

Das unveränderte Commitarchiv ab6b615 erstellt eine tatsächliche SQLite-
Datenbank mit Mitarbeiter, Original, unabhängiger Freigabe und bestätigter
Erstattung. Das Öffnen dieses Bestands mit 3c824c1 scheitert mit
`Nicht unterstützte Business-Migrationsänderung.` Ursache ist der zusätzlich
eingefügte Suchindex in einem bereits registrierten Migrationsvertrag, Version 1.
Die Schutzprüfung weist die geänderte Vertragsprüfsumme korrekt ab.

Der zusätzliche Index ist entfernt. Bestehende Tabellen, Indizes, Guards,
Versionsnummern und gespeicherte Journalprüfsummen bleiben exakt erhalten.
Die Originalsperre verwendet die vorhandenen Tabellen und Transaktionssperren.
Es werden weder alte Migrationseinträge überschrieben noch Schutzprüfungen
abgeschaltet. Ein fester Test prüft die tatsächlich aus dem alten Archiv
ermittelten Vertragsprüfsummen für SQLite und PostgreSQL.

Das gleiche alte SQLite-Original öffnet jetzt erfolgreich. Die ursprüngliche
Zahlungsquittung wird unverändert wiederholt. Ein weiterer tatsächlicher
PostgreSQL-Gegenlauf erzeugt den alten Bestand mit ab6b615, echter MFA,
Originalakten, Zahlung und Monatsabschluss. Die neue Migration erhält den
gesamten Datenfingerabdruck; anschließend bleiben alte Zahlungs- und
Monatsquittung, Originaldatei und Monats-PDF exakt erhalten. Die alte Anmeldung
funktioniert weiter, die neue Serverfähigkeit ist vorhanden. Keine Produktiv-
datenbank und kein externer Geldfluss sind beteiligt.

## Nachweise und neuer gemeinsamer Lauf

48 betroffene Auslagen-/Schema-/CI-Fälle bestehen in 10,107 Sekunden.
Vier tatsächliche PostgreSQL-Fälle einschließlich Altbestandsmigration und
vollständigem Restore bestehen in 31,890 Sekunden. Der eigene Container
`smartplan-expense-index-pg-20261111`, vollständige ID
`8ec93b99a74c44025ee891fe2fdb1704fff09c9be755586d55538d54d454ce15`,
verwendete ausschließlich Loopback-Port 32830 und ist nach ID-/Labelprüfung
entfernt. Die abschließende betroffene Reise-/Backend-/CI-Prüfung besteht
81 Fälle in 60,654 Sekunden.

Der PostgreSQL-Gegenfall ist bereits durch die vorhandene verpflichtende
CI-Discovery enthalten. Der unnötige zusätzliche identische Einzelaufruf aus
3c824c1 ist entfernt. Derselbe Fall wird nicht als zwei verschiedene Fälle
gezählt. Browser- und App-Produktcode bleiben bytegleich zu 3c824c1; die
Schemaerhaltung und der neue feste Gegenfall erhalten dennoch einen eigenen
vollständigen gemeinsamen Quell-/Paketnachlauf.

Ein zusätzlicher tatsächlicher Chromiumlauf am eingefrorenen Produktarchiv
4bb5071 besteht auch die sichtbare Mitarbeitergrenze: Ein zweiter Mitarbeiter
lädt dasselbe ganze Original unter neuer Datei-ID hoch, erhält beim Einreichen
409 mit `request_resolution=not_accepted` und eine lesbare Meldung auf Desktop
und Mobilansicht. Nach unabhängiger Freigaberücknahme wird die erneute
Einreichung mit 200 angenommen. Der vollständige ursprüngliche Ablauf mit
Freigabe, Zahlung/Rückzahlung, Monats-PDF und verlorener Antwort besteht danach
weiter. Alle 1.045 übrigen Archivdateien sind gegen 4bb5071 bytegleich geprüft;
nur der externe Testtreiber ist erweitert. Produktcode und laufende CI bleiben
unverändert. HTTP-Belege und Screenshots sind archiviert.

Die eigene alte signierte Vorbereitung 42966356463 wurde während der
unsignierten Vorprüfung geordnet abgebrochen. Der danach als abgebrochen
aufgeführte Signierjob besitzt keine Schritte; kein Apple-Schritt war gestartet.
Die ersten Development-/iPhone-Läufe werden mit ihren tatsächlichen Ergebnissen
bewahrt und nicht auf den korrigierten Quellstand übertragen.

Die Rohbelege liegen unter
[`evidence/expense-migration-preservation-2026-11-11/`](evidence/expense-migration-preservation-2026-11-11/).
TestFlight bleibt ohne ausdrückliche passende Uploadfreigabe ausgeschaltet.
Der vollständige Gesamtauftrag und die offenen Betriebs-/Fach-/Geräteabnahmen
bleiben aktiv.
