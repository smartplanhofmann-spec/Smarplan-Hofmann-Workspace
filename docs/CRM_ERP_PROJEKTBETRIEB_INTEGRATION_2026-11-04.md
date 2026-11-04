# Gemeinsamer Projektstand 0.13.0

Ausgangspunkt: `cf5e50b` / unveränderter Produktcode von `c875ea5`.
Der Nutzer priorisiert Projektbetrieb, Angebote, Rechnungen und Stunden in
Browser, Windows und iPhone. Neue Lohn- und Buchhaltungsentwicklung bleibt
zurückgestellt. Das ursprüngliche Gesamtziel ist unverändert.

## Integrierte Änderungen

- [Kunde, Projekt und Rechnungsanschrift](CRM_ERP_PROJEKT_KUNDENFLUSS_2026-11-04.md):
  vorhandene Kunden eindeutig wählen, aus der Kundenkarte ein Projekt beginnen,
  strukturierte Rechnungsadresse erhalten und im Beleg vollständig anzeigen.
- [Projektregister und Rückwege](CRM_ERP_PROJEKT_NAVIGATION_2026-11-04.md):
  alle 21 aktuellen Register öffnen, stabile Auswahl bei Modul-/Rechtewechsel,
  Rückkehr aus weiterer Verwaltung und Schutz ungespeicherter Pläne.
- [Zeiten](CRM_ERP_PROJEKTZEITEN_2026-11-04.md): vollständige gemischte
  Server-/Offline-Ereigniskette, Projektbezug, exakte Arbeitstage, begründete
  Korrekturen mit Historie in beiden Clients und passende Exportrechte.
- [Material und Belegrechte](CRM_ERP_PROJEKT_MATERIAL_BELEGRECHTE_2026-11-04.md):
  preisfreie Artikelreferenzen für Lagerrollen, passende Positionsrechte und
  gebundene Stornoentwürfe. Der
  [Browseranschluss](CRM_ERP_MATERIAL_ARTIKELAUSWAHL_BROWSER_2026-11-04.md)
  verwendet denselben Artikelvertrag.
- [Wiederholbare Projektanlage](CRM_ERP_PROJEKTANLAGE_WIEDERHOLUNG_2026-11-04.md):
  Originalauftrag, frische Rechte und atomare Quittung verhindern Doppelprojekte
  bei identischer Wiederholung nach verlorener Antwort. Die native App erhält
  den offenen Auftrag beim Schließen und erneuten Öffnen des Dialogs.
- Eindeutige Releasekennung **0.13.0+130**. Die automatische iPhone-Buildnummer
  berücksichtigt die Quellbuildnummer und wächst mit jedem Workflowlauf.
  Die bestehende getrennte Freigabe für Signierung/TestFlight bleibt erhalten.

Alle produktiven Änderungen wurden aus den vorhandenen aktuellen Dateien
übernommen. Die alten PR-7/8-Dateien wurden nicht über den heutigen Katalog-,
Kontext- und Offlinecode geschrieben. Überlappende Stunden-/Kundenänderungen
in `office.js` wurden zusammengeführt; der Browserrunner enthält alle drei
neuen Abläufe. Die CI führt diese Abläufe sowie die neuen HTTP- und
PostgreSQL-Prüfungen ausdrücklich aus.

## Gemeinsame Prüfungen und Nachläufe

| Prüfung | Tatsächlicher Befund |
| --- | --- |
| Vollständiger Backendlauf | 1.920 gemeldete Ausgänge: 1.918 bestanden, ein Windows-Skip, ein Fehler beim Import der neuen Gegenprüfungsdatei |
| Korrigierter normaler Backend-Testimport | 14 Fälle: zwölf bestanden, zwei bedingt ausgelassene PG-Fälle; enthält neun bereits im Gesamtlauf bestandene Ownerfälle |
| Tatsächliches PostgreSQL nach Importkorrektur | Zwei Fälle bestanden auf eigener PostgreSQL-16.15-Instanz; unabhängige Verbindungen, Originalquittung und Rollback; Container anschließend entfernt |
| Neues Inventar über MFA/HTTP | Sechs Fälle bestanden am gemeinsamen Stand |
| Vollständige Flutterprüfung mit gezieltem Nachlauf | 1.621 unterschiedliche Testfälle besitzen zuletzt erfolgreiche Ergebnisse; sieben erste Fehlschläge wurden über 13 gezielte Fälle nachgeprüft |
| Flutteranalyse | Ohne Befund; abschließend zehn App-Start-/Oberflächenfälle mit sichtbarer Version 0.13.0 bestanden |
| Gesamte Node-Suite | 856 Einzelfälle bestanden |
| Paketprüfung | 16 Fälle bestanden, nach Versionswechsel erneut bestanden |
| Tatsächlicher Chromium | Drei Abläufe bestanden: Kunden-/Belegkette mit verlorener Projektantwort, preisfreie Materialbuchung und Stundenkorrektur; aktiver Namespace-/Seccomp-Sandbox |
| Automatische iPhone-Buildnummer | Sechs Prüfungen des tatsächlichen Workflow-Pythoncodes bestanden |

Der Backend-Importfehler betraf ausschließlich den Prüfcode: der PG-Helfer
wird jetzt über `online.test_online` und nur bei gesetzter Test-DSN importiert.
Der Flask-Dispatchtest bleibt im reinen Backendpaket optional und läuft
ausdrücklich im Online-CI-Job. Die Produktdateien wurden dafür nicht verändert.

Fünf erste Appfehler betrafen eine unvollständige lokale Python-Verknüpfung;
die tatsächlich vollständige geprüfte Pythonumgebung wird nun verwendet.
Zwei alte Appfixtures mussten an den aktuellen Vertrag angeschlossen werden:
eine gültige Projektkennung und die Antwort auf die zusätzlich gelesenen
Zeitnachweise. Bestehende Verhaltensassertionen bleiben erhalten. Erstläufe,
Originalfixtures und erfolgreiche Nachläufe sind archiviert. Lade- und
Setup-/Teardown-Ereignisse werden nicht als Fluttertestfälle gezählt.

Der bereits zuvor ausgeführte zweifache Main-PG-Rechnungskettennachweis bleibt
mit seinem ursprünglichen Quellstand erhalten. Er belegt tatsächliche
Rechnungsausstellung und PDF-Originale am damaligen Mainstand; er wird nicht
als erneut ausgeführter gemeinsamer Lauf nach dem neuen Projektquittungsfix
ausgegeben. Die neue gemeinsame PG-Prüfung betrifft die Projektanlage.

Der [Gesamtnachweis](evidence/project-integrated-2026-11-04/manifest.json)
bindet 1.237 Quellen und die Grenzen. Die
[Versionsprüfung](evidence/project-release-version-2026-11-04/manifest.json)
bindet die nach dem funktionalen Gesamtlauf geänderten Versionsmetadaten.
Eine erneute vollständige Steuer-/Lohnentwicklung wurde damit nicht begonnen.

## Nächster Auslieferungsschritt und verbleibende Grenzen

Der lokale Quell- und Prüfblock ist abgeschlossen. Aktuelle Windows-/iPhone-
Binärdateien müssen aus genau diesem Stand gebaut werden. Die
[Bereitstellungsprüfung](CRM_ERP_PROJEKT_AUSLIEFERUNG_2026-11-04.md) und der
[PR-Abgleich](CRM_ERP_PROJEKT_NAVIGATION_PR8_ABGLEICH_2026-11-04.md) benennen
die vorhandenen älteren Artefakte und den geeigneten Buildweg.

Ein normaler Git-Dry-Run für einen neuen Testbranch war erfolgreich. Dabei
wurde weder ein Branch angelegt noch Quellcode hochgeladen. Die vorherige
CLI-Tokenwarnung bedeutet daher keine generelle Sperre des Git-Transports.
Eine Änderung des Defaultbranches oder des laufenden Kundensystems ist kein
Teil dieser lokalen Zusammenführung.

Offen bleiben aktuelle native Builds, kompatibler Serverstand, Installation
und gemeinsamer Ablauf auf tatsächlichem Windows-/iPhone-Gerät sowie die
betriebliche Abnahme. Native offene Projektaufträge überleben derzeit das
Schließen des Dialogs, aber keinen vollständigen App-Neustart. Die dauerhafte
Offline-Zeiterfassung ist separat vorhanden und geprüft. Der Browser besitzt
keine gleichwertige Offlinewarteschlange. Diese Teilprüfung erklärt weder die
gesamte Projektphase noch das vollständige CRM-/ERP-Ziel für fertig oder
produktiv freigegeben.
