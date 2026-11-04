# Projektbuilds: Nachprüfung der Update- und Migrationsfixtures

Die erste veröffentlichte Prüfrunde auf `8e320bd` fand zwei bislang nicht im
lokalen Projekt-Gesamtlauf enthaltene Fehler. Die Update-Simulation hatte den
stdlib-only Rollenhelfer von `online.release` nicht in ihr isoliertes Paket
aufgenommen. Der Einkaufs-Migrationstest entfernte lediglich das Einkaufsmodul,
behielt aber davon abhängige spätere Tabellen. Eine gezielte verwandte Prüfung
fand denselben falschen Aufbau im Portal-Migrationstest.

Die Simulation lädt nun neben dem echten Releaseprüfer auch den echten
Rollenhelfer. Datenbank-/Dienstgrenzen bleiben simuliert und gesperrt. Die beiden
Migrationsfixtures verwenden einen geschlossenen Modulpräfix und dazu passende
Modulnamen. Die bisherigen Prüfungen auf Original-PDF, Nummern, Zahlungen und
Audit wurden erhalten. Keine fachliche App-/Backendruntime wurde dafür geändert.

Ergebnis: **60/60** Update-/Rollback-/Dienstfälle im entbehrlichen Container
bestanden. **Fünf tatsächliche PostgreSQL-Migrationsfälle** bestanden: Einkauf,
Portal, bisherige Rechnung/Zahlung/Bericht sowie zwei Finanzmigrationen.
PostgreSQL 16.15, tatsächlich ausgeführte pg_dump/pg_restore-Programme für die
Restoreprobe. Alle eigenen Testcontainer sind entfernt. Die erste verwandte
Viererprüfung hatte einen Portalfehler und einen lokalen fehlenden pg_dump;
der vollständige erfolgreiche Vierer-Nachlauf ist separat erhalten.

Die iPhone-Prüfrunden auf dem Testbranch werden bei einer neueren Prüffassung
abgelöst. Für den bestehenden Releasebranch bleibt das vorherige Verhalten
erhalten; die ausdrückliche Signier-/Uploadschranke bleibt unverändert.
Damit blockiert ein überholter unsignierter Testlauf nicht die nächste Fassung.

[Gebundene Quellen, Erstfehler und Nachläufe](evidence/project-native-ci-2026-11-04/ci-fixes.json)
liegen im Repository. Die neuen GitHub-Läufe müssen diesen Stand noch bestätigen.
Keine produktive Migration, Serveränderung oder TestFlight-Veröffentlichung.

## Eindeutige Sicherungsimporte im Online-Testmodus

Die nachfolgende echte GitHub-Runde `9c9742e` deckte eine Namenskollision
auf: unittest-Discovery priorisiert backend/online; gleichnamige unqualifizierte
backup-/restore-Importe verwendeten die PostgreSQL-Helfer in SQLite-Restoretests.
Zwölf Online-Testdateien importieren jetzt ausdrücklich die SQLite-Funktionen
aus backend. Der paketweise geladene SQLite-Restore bindet auch seinen
untergeordneten Sicherungshelfer relativ; Skript-/Top-Level-Modus behalten
den bisherigen Import. Alle bestehenden Testkörper und Assertions bleiben
erhalten. 89 Fälle in zwölf separat gestarteten Online-Modulen sowie
die beiden bisherigen Sicherungsfälle bestehen.

[Importbindung, Quellhashes und Nachläufe](evidence/project-native-ci-2026-11-04/import-binding.json).
Frühere Fehlerlogs bleiben separat erhalten; App-Fachlogik und Datenbankschema
wurden nicht geändert.

## Portable Python-Auswahl der App-Prüfungen

Die echte Flutter-Runde auf `9e5bd30` fand in sieben Testdateien einen
Entwicklerpfad unter /tmp. Diese Dateien verwenden jetzt wie die übrigen
Integrationstests die eingerichtete Projekt-venv und den passenden Windows-/
Unix-Interpreter. Eine ausdrückliche SMARTPLAN_TEST_PYTHON-Angabe hat weiter
Vorrang. Acht tatsächliche App-/HTTP-Fälle bestehen ohne diese
Umgebungsüberschreibung; Testlogik und Assertions sind unverändert.
[Quellbindungen und Log](evidence/project-native-ci-2026-11-04/portable-python.json).

## Windows-Testgrenze und vollständige Backend-Testabhängigkeiten

Auf `c437ddc` bestehen der vollständige Linux-Flutter-Lauf, die Updateprüfung
und HTTPS-Einrichtung in GitHub. Windows besteht die eigene echte PDF-Prüfung,
stoppt danach aber an Testservern: Der geschützte Online-Dateispeicher benötigt
POSIX (`fcntl`), und ältere Tests verwenden ohne Überschreibung Unix-venv-Pfade.

Der Windows-Job setzt deshalb den eingerichteten Scripts/python.exe ausdrücklich
für seine Testprozesse. 23 reine Online-HTTP-Testbibliotheken und genau ein
Online-HTTP-Fall innerhalb einer gemischten Katalogbibliothek tragen nun
`posix_backend`. Nur der Windows-Job schließt diesen Tag aus. GUI-, Validierungs-
und portable lokale Backendtests bleiben erhalten; Linux und der unsignierte
iPhone-Prüfjob führen die POSIX-Fälle weiterhin aus. Die Server-Dateischutzlogik
ist unverändert. Das ersetzt keinen Windows-Clienttest gegen den gemeinsamen
Linux-Server und keine Geräteabnahme.

Die lokale Prüfung dieser Auswahl besteht mit **51 Fällen**. Ein ausdrücklich
nicht ausgeschlossener POSIX-App-/HTTP-Fall besteht ebenfalls; Flutter analyze
meldet keine Befunde. Die Tags sind in dart_test.yaml deklariert.

Der vollständige Backend-Job fand außerdem 59 Fehler durch den fehlenden
PostgreSQL-Treiber in seiner bisherigen reinen SQLite-Abhängigkeitsinstallation.
Er installiert nun den vorhandenen fest gepinnten Online-Lock, der auch die
bisherigen Basisabhängigkeiten enthält. 18 gezielte vorhandene Fälle einschließlich
Archiv, Reisequellen und Worker bestehen mit diesen Abhängigkeiten. Eine neue
vollständige Remoteprüfung steht aus; keine fachliche Lohnentwicklung wurde
aufgenommen.

## Verzögerte Browserantwort tatsächlich im Client nachweisen

Der Browser-Komponententest wartete auf response.finished(), obwohl die echte
zurückgehaltene Antwort bereits zum Client unterwegs war. Wie die vorhandenen
Erstattungs-/Kapazitätsprüfungen beobachtet er jetzt das originale OfficeApi-
Promise transparent: Ergebnis und Fehler werden unverändert weitergegeben;
das vollständig geparste Ergebnis muss dem echten Backend-DTO entsprechen.
Das geschlossene Fenster darf nach der späten Antwort weiterhin nicht aufgehen.
Alle anschließenden Rechte-, Wiederholungs- und schmalen Bildschirmprüfungen
bleiben erhalten. Der vollständige Komponentenablauf besteht mit tatsächlich
sandboxiertem Chromium und Testbackend.

[Quellhashes, Erstfehler und tatsächliche Nachläufe](evidence/project-native-ci-2026-11-04/platform-ci-preparation.json)
liegen im Repository. Der macOS-Simulatorjob und der unsignierte iPhone-Job der
fünften Runde wurden vor Zuteilung eines Runners abgebrochen; ein aktuelles
iPhone-Artefakt liegt daraus nicht vor. Die Ursache der Runner-Abbrüche ist noch
nicht belegt. Keine aktuelle Windows-/iPhone-Auslieferung wird behauptet.
