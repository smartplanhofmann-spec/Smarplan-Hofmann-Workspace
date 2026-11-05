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
iPhone-Artefakt liegt daraus nicht vor. Keine aktuelle Windows-/iPhone-
Auslieferung wird behauptet.

Die nachfolgend gelesenen echten [GitHub-Annotations](evidence/project-native-ci-2026-11-04/mac-runner-annotations.json)
benennen mehrfach ARM64-Kapazitätsengpässe und einen nicht zugeteilten Hosted
Runner. Simulator und unsignierter iPhone-Prüfjob verwenden deshalb den in der
[offiziellen Runnerliste](evidence/project-native-ci-2026-11-04/runner-images-available.md)
ausgewiesenen Standardrunner `macos-26-intel`. Der signierte Uploadjob und seine
ausdrückliche Freigabebedingung sind unverändert. Die tatsächliche Zuteilung
und der Build müssen in der nächsten Runde bestätigt werden.

Der vollständige Abgleich aller App-Prozessstarts fand zusätzlich zwei reine
HTTP-Bibliotheken für Altposten und Altanlagen, die die POSIX-Fixture lediglich
importieren. Auch sie tragen nun denselben Tag: insgesamt 25 Bibliotheken plus
ein Einzelfall. Ihre beiden unveränderten echten HTTP-Abläufe bestehen unter
Linux; portable lokale Backendtests bleiben ausdrücklich unmarkiert.

## Gemeinsame PostgreSQL-Projektkette am aktuellen Quellstand

Auf `112bc91` bestehen beide vorhandenen vollständigen Kundenabläufe erneut
gegen PostgreSQL 16.15: Anfrage/Katalog/Portal, Projektdurchführung mit Zeit und
Bericht, tatsächliche Rechnungsausstellung und Zahlung über Dienstneustart;
außerdem derselbe Auftrag mit Liefer-/Geräte-/Servicebezug und erhaltenen
Originalen über echten Dump/Restore. Die bestehende Finanzzuordnung wird hier
als Regression mitgeprüft; das hebt die zurückgestellte Buchhaltungsabnahme
nicht auf. Die Fälle laufen unter der geschützten Laufzeitrolle und mit MFA.

Der eigene lokale Testcontainer ist anschließend entfernt. Gebundene
Backendquellen blieben über den Lauf unverändert. [Treiber, vollständiges Log,
Quellhashes und Bereinigung](evidence/project-native-ci-2026-11-04/current-project-journeys/postgres-result.json)
sind erhalten. Diese Server-/HTTP-Nachweise ersetzen weiterhin keine
Offline-Neustart- oder Geräteabnahme und keine Bereitstellung auf dem Kundensystem.

## Python-Prüfprofil des portablen Windows-Dienstes

Nach den erfolgreichen Windows-App-Tests lädt der bisher als Start-/Sicherungs-
prüfung benannte Python-Helfer tatsächlich die gesamte Backend-Discovery.
Diese enthält inzwischen zahlreiche POSIX-Online-Fixtures. Der Helfer wählt
auf Windows nun ausdrücklich zehn vorhandene lokale Testmodule: Office,
Administration, Sicherung, Windows-Launcher, Berichtsoriginale, Kunden, Pläne,
Gerätefreigaben, Arbeitsbereichsrechte und Projektmappe. Jede Auswahl muss
tatsächlich Fälle enthalten. Die vorhandenen Assertions bleiben unverändert.
Unter Linux bleibt die vollständige Discovery erhalten; beide Profile sind
zusätzlich über --scope ausdrücklich auswählbar.

Der lokale portable Lauf umfasst 79 Fälle: 78 bestanden, eine reine Windows-
Jobobjektprüfung auf Linux erwartungsgemäß übersprungen. Diese bleibt für den
echten Windows-Lauf ausgewählt. [Ursprung, Profil, Quellen und vollständiger Lauf](evidence/project-native-ci-2026-11-04/portable-local-backend/result.json)
sind erhalten. Die bereits erfolgreichen 1.621 Linux-App-Tests und der echte
iOS-Simulatorbuild auf `112bc91` bleiben getrennt nachgewiesen. App-/Backend-
Fachruntime ist durch diese reine CI-Helferänderung unverändert; der laufende
iPhone-Prüfjob wird von diesem geänderten Skriptpfad nicht neu ausgelöst.

## macOS: temporäre Elternpfade der drei gebundenen Testinstanzen

Der vollständige Intel-macOS-App-Lauf auf `112bc91` endet mit drei Fehlern
bei der Instanzbindung: macOS stellt den temporären Elternpfad unter dem
System-Symlink /var bereit. Der geschützte Serveradapter verweigert diesen
Symlink wie vorgesehen mit O_NOFOLLOW. Betroffen sind der Ereignis-HTTP-Fall
und beide Jahresnachweis-HTTP-Fälle; bei letzterem liegt eine erste Bindung
bereits in der verwendeten Python-Testfixture.

Vier reine Fixture-Pfadstellen verwenden jetzt den kanonischen, bereits
vorhandenen temporären Elternpfad mit resolve(strict=True), bevor sie das
neue private Ablageverzeichnis anhängen. Der Produktionsadapter, die
Instanzprüfung und sämtliche Verhaltensassertionen sind unverändert.

Eine eigene lokale Symlink-Tempumgebung reproduziert genau alle drei Fehler
vor der Korrektur. Anschließend bestehen dort alle drei vollständigen echten
HTTP-Abläufe; Flutter analyze meldet keine Befunde. Die eigene Tempumgebung
ist jeweils entfernt. [Vorher-/Nachher-Läufe und Quellbindungen](evidence/project-native-ci-2026-11-04/mac-temp-canonical/after-result.json)
und der vollständige ursprüngliche [macOS-Fehlerlauf](evidence/project-native-ci-2026-11-04/current-ios-failed.log)
sind erhalten. Die tatsächliche macOS-Nachprüfung und der unsignierte
Gerätebuild stehen noch aus.

## Einkauf: neue preisfreie Auswahl und vollständiger Legacy-Fallback

Der vollständige Browserlauf auf `70b5cb2` besteht die vorher korrigierte
Komponentenprüfung und die anschließenden Finanzabläufe. Er stoppt später
an einer veralteten Erwartung im Einkaufstest: Das simulierte Legacy-Angebot
entfernt purchasing_catalog, lässt aber die neue inventory_article_refs-
Fähigkeit aktiv und erwartet trotzdem keine unbestückten Artikel.

Der Test prüft jetzt beide tatsächlich unterschiedlichen Verträge. Ohne
Einkaufssuche, aber mit preisfreien Referenzen bleiben unbestückte Artikel
auswählbar und der Referenzendpunkt wird benutzt. Fehlen beide Fähigkeiten,
bleibt die Bestandsauswahl erhalten und keiner der beiden nicht angebotenen
Endpunkte wird aufgerufen. Die Schranke gegen finanzielle Katalogabfragen
sowie alle bestehenden Pagination-, Projekt-, Speicher-, Bearbeitungs- und
390px-Prüfungen bleiben erhalten.

Der gleiche bestehende Ablauf ist zusätzlich gezielt als purchasing-catalog
ausführbar und besteht mit echtem Testbackend und sandboxiertem Chromium.
Produktcode wurde dafür nicht geändert. [Lauf, Screenshots und Quellen](evidence/project-native-ci-2026-11-04/purchasing-fallback/result.json)
und der ursprüngliche [vollständige CI-Fehlerlauf](evidence/project-native-ci-2026-11-04/browser-70b5-failed.log)
sind erhalten. Der vollständige nachfolgende CI-Browserlauf steht noch aus.

## 05.11.2026 – Tatsächliche Windows-/iPhone-Builds und vollständige Browserauswahl

Auf `bd8caef` bestehen Windows, Linux-App, Linux-Backend und iOS-Simulator.
Windows: 1.593 App-Fälle, drei native PDF-Fälle und 79 portable Backendfälle
ohne Skip; beide Releasepakete sind veröffentlicht. iPhone: 1.616 bestandene
App-Fälle, fünf ausgewiesene Plattform-Skips, drei native PDF-Fälle und Analyse
ohne Befund; tatsächlicher unsignierter Gerätebuild 0.13.0 Build 167 erfolgreich.
[Metadaten, Job-IDs, Digests und Downloadziele](evidence/project-native-ci-2026-11-04/final/delivery-status.json)
sind erhalten. Das iPhone-Artefakt ist nicht installierbar; Signierung,
TestFlight, gemeinsame Geräteabnahme und laufender Serverabgleich fehlen.

Der Linux-Backendlauf enthält 1.924 Fälle: 1.921 bestanden und drei erläuterte
Skips. Linux-Flutter besteht 1.621 Fälle sowie drei separate echte PDF-Fälle;
Analyse ohne Befund. Die neuen späteren Server-Guard-Tests gehören nicht zu
diesen historischen Zahlen. Die sechs vollständigen CI-Logs unter
`evidence/project-native-ci-2026-11-04/final/` bleiben unverändert erhalten,
einschließlich beider roten Gesamtjobs.

Der ursprüngliche Browserjob besteht Hauptablauf und Altposten, stoppt dann
an einer veralteten Kundenfeldbezeichnung im Wirtschaftlichkeitstest. Dieser
verwendet jetzt den bestehenden neuen Kundenauswahlvertrag und besteht mit
allen Original-, Antwortverlust-, Korrektur-, Historien- und Budgetprüfungen.
Die übrigen 45 bestehenden Browserabläufe wurden mit drei unabhängigen lokalen
Fixtures und vollständig sandboxiertem Chromium ausgeführt: 44 bestanden,
Unternehmensübersicht zunächst wegen einer nach Navigation verlorenen CDP-
Antwort. Deren Beobachter liest jetzt die echte API-Antwort vor unverändertem
Weiterreichen; der ganze bestehende Übersichtsablauf besteht anschließend.
Damit sind die **48 verschiedenen CI-Browserabläufe aufgeteilt nachgewiesen**;
das ist kein einzelner grüner Remote-Gesamtlauf. Die 856 Node-Fälle bestehen
vollständig mit der für ihre Kindprozesse nötigen lokalen Ausführungsberechtigung.
Der erste eingeschränkte EPERM-Lauf bleibt als Umgebungsfehler erhalten.

[45er-Lauf und Bildhashes](evidence/project-native-ci-2026-11-04/remaining-browser/result.json),
[Wirtschaftlichkeit](evidence/project-native-ci-2026-11-04/project-economics-recheck/browser.txt),
[Unternehmensübersicht](evidence/project-native-ci-2026-11-04/company-overview-recheck/browser.txt)
und [Node-Gesamtlauf](evidence/project-native-ci-2026-11-04/remaining-browser/node-tests-permitted.txt)
sind archiviert. Die Bilder der 45er-Auswahl liegen im ignorierten Arbeitsordner
und sind im Ergebnis durch SHA-256 gebunden; die gezielten Nachprüfungsbilder
liegen direkt bei den Repository-Nachweisen.

## Kalenderdatum, Restore-Stichtag und kurz nachlaufende PostgreSQL-Verbindungen

Die Berechtigungs-Kalenderfixture verwendete UTC, während die Kalenderansicht
Arbeitstage in Europe/Berlin abgrenzt. Kurz vor UTC-Mitternacht suchte sie den
Termin dadurch am falschen Tag. Die Fixture verwendet jetzt dieselbe Zeitzone.
Die bestehende echte HTTP-/ACL-Prüfung scheitert vor der Korrektur gezielt bei
23:30 UTC und besteht danach bei 12:30, 22:30 und 23:30 UTC. Alle elf Fälle des
Moduls bestehen. Die Kalender-/Berechtigungsruntime ist unverändert.
[Vorher/Nachher und vollständiges Modul](evidence/project-native-ci-2026-11-04/calendar-date-boundary/after-result.json).

Der vorhandene vollständige Finanz-Restorefall fragte die Liquidität fest zum
04.11. ab, obwohl seine synthetischen Zahlungen inzwischen am 05.11. erstellt
wurden. Seine drei Abfragen verwenden jetzt denselben tatsächlichen Zahltag.
Beträge, gebundene Originale und Restore-/Reconciliation-Assertions bleiben
unverändert; der ganze PostgreSQL-Fall besteht nach Korrektur.
Buchhaltung bleibt fachlich zurückgestellt; dies sind Bestandserhalt-Prüfungen.

Die Nachprüfung aller nach dem Kalenderfehler in CI ausgelassenen Online-
Befehle besteht zunächst elf von 13 Gruppen, darunter beide vollständigen
Projekt-/Kundenketten mit PostgreSQL, MFA, Rechnung und Dienstneustart bzw.
Dump/Restore. Die zwei übrigen Gruppen sind separat nachgeprüft. Der erste
Versuch einer Namespace-Beobachtung scheiterte vor Testausführung an einer
OS-Berechtigung; Originalquittung und korrigierte Einordnung bleiben erhalten.
Danach laufen die Prüfungen ausschließlich über Docker in eigenen privaten
Offline-Netzen ohne veröffentlichten Hostport 55433 und als unprivilegierter
Benutzer. Kein bestehender Hostcluster wurde berührt.

Dabei reproduzierte sich ein echter Betreiber-Guard-Fehler: Eine gerade
ordnungsgemäß geschlossene Migrationsverbindung war für einen kurzen Moment
noch in pg_stat_activity sichtbar. Ein rein lesender Diagnoselauf zeigt nach
der Ablehnung bereits keine fremde Verbindung mehr. `no_other_clients`
prüft jetzt frische Snapshots bis höchstens 250 ms nach; aktive Verbindungen
sperren weiterhin, keine Verbindung wird beendet. Zwei neue reale PostgreSQL-
Fälle belegen natürliches Abmelden und fortbestehende Sperre samt weiter
benutzbarer fremder Verbindung. Die vollständige Releasegruppe besteht mit
23 Fällen. Dies ist die einzige spätere Änderung der Server-Fachquellen;
der bereits gebaute native Quellstand enthält diese Serveränderung noch nicht.

Eine Provisionierungsfixture verlangte außerdem eine zuvor von anderen
Suites angelegte Altsystemrolle. Sie legt diese ausschließlich bei Fehlen im
bereits geschützten synthetischen Cluster selbst an und entfernt nur ihre
eigene Rolle am Ende. Alle negativen Rollen-/Fremddatenbankprüfungen bleiben
erhalten. Die unabhängige tatsächliche UID-Isolation bleibt separat und wird
hier ausdrücklich nicht als durchgeführt ausgegeben.

Der [gezielte vollständige Release-Lauf](evidence/project-native-ci-2026-11-04/online-final/1-tests.txt)
besteht alle 23 Fälle. Die [korrigierte Provisionierungssuite](evidence/project-native-ci-2026-11-04/provisioning-final/result.json)
besteht 22 Fälle mit einem ausdrücklichen UID-Akzeptanz-Skip; echte HTTP-Prozesse,
MFA, Rollenabweichung, gebundene Ablage und Dump/Restore sind enthalten. Der
längere vollständige Online-Business-Nachlauf läuft zum Zeitpunkt dieser
Veröffentlichung noch und wird mit eigener Abschlussquittung ergänzt.
