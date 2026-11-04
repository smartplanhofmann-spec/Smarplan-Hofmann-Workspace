# Aktueller Buildstatus: Veröffentlichung benötigt Freigabe

**Aktuell nach ausdrücklicher Zustimmung:** Upload erfolgreich. Der neue
Branch `codex/testupdate-0.7-projects-20261104` steht auf dem unveränderten
Commit `8e320bd60671fb7e95c95a197ee34dd3e078bd66`. GitHub hat die
[Development checks](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/41915157732)
und den [iPhone-Prüfbuild](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/41915157953)
automatisch gestartet. Die nachstehende Ablehnung ist der erhaltene Verlauf
vor dieser Zustimmung. Fertige aktuelle Binärartefakte sind noch nicht belegt.

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
