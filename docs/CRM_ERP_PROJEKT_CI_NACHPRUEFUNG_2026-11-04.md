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
