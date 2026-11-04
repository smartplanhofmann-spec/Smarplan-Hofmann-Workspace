# Aktueller Buildstatus: Veröffentlichung autorisiert, CI-Nachprüfung läuft

**Aktuell nach ausdrücklicher Zustimmung:** Upload erfolgreich. Der neue
Branch `codex/testupdate-0.7-projects-20261104` enthält den Quellstand 0.13.0
und nachfolgende gezielte CI-Korrekturen. Der tatsächliche Windows-Job auf
`70b5cb28d2afa43e37715222e34ab62abd55db82` ist vollständig erfolgreich:
1.593 App-Tests, drei echte PDF-Engine-Tests, 79 lokale Backendfälle ohne Skip,
beide Releasepakete und deren natives Quell-/Dateimanifest geprüft.

**[Windows-Online-Paket 0.13.0 herunterladen](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/41929317907/artifacts/13372157359)**
(21.831.095 Byte; GitHub-Artefakt 13372157359). Vollständig entpacken und
smartplan_office.exe öffnen. Dieses Paket enthält keinen lokalen Pythonserver.
[Metadaten und Digests beider Programme](evidence/project-native-ci-2026-11-04/windows-artifacts.json)
und der [tatsächliche Windows-Lauf](evidence/project-native-ci-2026-11-04/current-windows.log)
sind erhalten. Die ZIP-Inhaltsprüfung erfolgte im Windows-CI; die ZIP wurde in
dieser Cloud nicht zusätzlich lokal entpackt. Die spätere lokale Geräteabnahme
und der gemeinsame Serverabgleich sind weiterhin offen.

Linux-App-/Backend-Gesamtlauf und echter Simulatorbuild sind erfolgreich.
Der vollständige iPhone-Prüflauf fand drei Temp-Pfadfehler; die vier betroffenen
Fixturestellen bestehen nach Korrektur unter einer reproduzierten Symlink-
Tempumgebung. Der Browser-Einkaufsfallback ist gezielt nachgeprüft. Beide
vollständigen Remote-Nachprüfungen stehen noch aus. 367 App-/Backend-Paketquellen
sind bytegleich mit dem tatsächlichen Windows-Build; neuere Änderungen betreffen
Tests und Nachweise. Ein installierbarer aktueller iPhone-Build ist noch offen.
[Fortlaufender CI-Nachweis](CRM_ERP_PROJEKT_CI_NACHPRUEFUNG_2026-11-04.md).

**Erste Veröffentlichung:** GitHub hat für `8e320bd` die
[Development checks](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/41915157732)
und den [iPhone-Prüfbuild](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/41915157953)
automatisch gestartet. Die nachstehende Ablehnung ist der erhaltene Verlauf
vor dieser Zustimmung. Zu diesem ersten Zeitpunkt waren aktuelle Binärartefakte
noch nicht belegt.

## Verlauf vor der Zustimmung

Der geprüfte lokale Produktstand ist **0.13.0+130**, Commit
`35c572781731e93689628ad0b88c5d71e07ab012`, im Hauptprojekt
`/workspace/Smarplan-Hofmann-Workspace`. Der [Integrationsbericht](CRM_ERP_PROJEKTBETRIEB_INTEGRATION_2026-11-04.md)
enthält Änderungen, Nachläufe und Grenzen. 260 geänderte Pfade sind nach der
Zusammenführung bytegleich mit dem Kandidaten; 3.130 unveränderte getrackte
Pfade und 1.237 Quellbindungen sind geprüft.

Der normale Git-Dry-Run für einen neuen Branch war erfolgreich. Der danach
angeforderte tatsächliche Push wurde von der automatischen Freigabeprüfung
**vor der Ausführung abgelehnt**. Begründung: Die bisherige Entwicklung im
Repository autorisiert nicht ausdrücklich die externe Veröffentlichung des
vollständigen lokalen Quellstands und der Nachweise auf GitHub.

Angefragte Aktion nach ausdrücklicher Zustimmung:

- Ziel: öffentliches Repository
  `https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace`.
- Neuer Branch: `codex/testupdate-0.7-projects-20261104`.
- Inhalt: geprüfter Quellstand 0.13.0 einschließlich bisheriger lokaler
  Entwicklung und archivierter Prüfnachweise; keine bloße Binärdatei.
- Zweck: vorhandene GitHub-Actions für Windows und unsignierte iPhone-
  Prüfbuilds starten und deren tatsächliche Ergebnisse prüfen.

Der Defaultbranch wird bei dieser vorgeschlagenen Aktion nicht aktualisiert.
Signierter TestFlight-Upload und Änderung des laufenden Servers sind weitere
Schritte mit eigener konkreter Bereitstellung. Die bestehenden älteren
Windows-/iPhone-Artefakte werden nicht als aktuelle Version ausgegeben.

**Tatsächlich ausgeführt:** lokale Entwicklung, Prüfungen, Commit und
Fast-Forward im Cloud-Hauptrepository sowie ein Git-Dry-Run. **Nicht
stattgefunden:** tatsächlicher GitHub-Push, neue Remote-Builds,
Produktivmigration, Serverupdate oder TestFlight-Upload. Es wurde keine
Alternative zum Umgehen der automatischen Ablehnung versucht.
