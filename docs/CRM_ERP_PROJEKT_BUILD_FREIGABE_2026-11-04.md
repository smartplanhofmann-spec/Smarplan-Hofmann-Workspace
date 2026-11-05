# Aktueller Buildstatus: Windows gebaut, iPhone-Prüfbuild erfolgreich

Stand 05.11.2026: Der ausdrücklich freigegebene Branch
`codex/testupdate-0.7-projects-20261104` enthält Version **0.13.0+130**.
Auf dem Quellstand `bd8caef6ffcfa0cdf6bbd4314ddb393ad49dd806` sind beide
Windows-Pakete, der iOS-Simulator und der unsignierte iPhone-Gerätebuild
nachweislich erfolgreich gebaut.

**[Windows-Online-Paket 0.13.0 herunterladen](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/41932861640/artifacts/13373951873)**

Das ZIP vollständig entpacken und **smartplan_office.exe** öffnen. Das
Online-Paket enthält keinen lokalen Pythonserver. Größe: 21.831.091 Byte;
SHA-256: `a91aaed307be58a22d4fc06272c662c68632346627b1221d15b84b1b32999f7f`.
Das getrennte lokale Windows-Paket ist im selben Lauf als Artefakt
13374016008 vorhanden; es ersetzt keinen gemeinsamen Online-Server.

Der tatsächliche Windows-Job 126934277996 besteht 1.593 App-Tests, drei
native PDF-Engine-Fälle und 79 portable Backendfälle ohne Skip. Beide
Releasepakete und ihre nativen Quell-/Dateimanifeste sind im Windows-CI
geprüft. Die ZIP wurde in dieser Cloud nicht zusätzlich lokal entpackt
oder als Windowsprogramm ausgeführt.

Der tatsächliche iPhone-Job 126933889419 besteht die Analyse, 1.616 App-Fälle
mit fünf ausgewiesenen Plattform-Skips und drei native PDF-Fälle. Der
Gerätebuild **0.13.0, Build 167** und sein iPhone-/iPad-Manifest sind erfolgreich.
[Unsigniertes Prüfartefakt](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/41932861659/artifacts/13373843589):
14.666.907 Byte, SHA-256
`bfa2706b0bc7578dfc23457db29505451d8e5c2b10493eb2eadb0e4e843cb6ac`.
**Dieses Artefakt ist nicht auf dem iPhone installierbar.** Die Signierung und
der TestFlight-Upload sind noch offen; der geschützte Uploadjob blieb
übersprungen. Die tatsächliche Geräteabnahme ist nicht durchgeführt.

[GitHub-Jobstatus und Artefaktmetadaten](evidence/project-native-ci-2026-11-04/final/delivery-status.json)
sowie die vollständigen [Windows-](evidence/project-native-ci-2026-11-04/final/windows-bd8caef.log)
und [iPhone-Logs](evidence/project-native-ci-2026-11-04/final/ios-bd8caef.log)
sind archiviert. Der Gesamt-CI-Lauf auf diesem Commit war wegen zweier
nachfolgend korrigierter Testannahmen nicht vollständig grün; erfolgreiche
native Teiljobs werden deshalb getrennt ausgewiesen. Die aktuellen
[Nachprüfungen](CRM_ERP_PROJEKT_CI_NACHPRUEFUNG_2026-11-04.md) dokumentieren auch
die späteren Testkorrekturen und den Server-Guard gegen kurz nachlaufende
PostgreSQL-Verbindungen. Diese spätere Serveränderung ist kein Bestandteil
des bereits gebauten Serverstands.

Für den gemeinsamen Kundentest fehlen der nachgewiesene installierte
Serverstand, der installierbare iPhone-Build und die 20 tatsächlichen
Geräte-/Bedienprüfungen. Die [Testanleitung](CRM_ERP_KUNDENTEST_PROJEKTBETRIEB_0_13.md)
enthält die vorbereiteten Schritte und lesenden Serverbefehle. In der
Cloud ist kein Zugang zum laufenden Office-Server eingerichtet; ein
Serverupdate wurde nicht ausgeführt. Löhne und Buchhaltung bleiben
entsprechend der Nutzerentscheidung zurückgestellt.

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
