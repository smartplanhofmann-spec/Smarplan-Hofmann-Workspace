# Aktueller Lieferstand

Stand: 11.11.2026. Aktuelle veröffentlichte Produktquelle:
`ab6b61535a35f8306bbf04ebe6557acdb2ac3f41`, ausschließlich auf
`codex/testupdate-0.7-projects-20261104`. Hauptprojekt:
`/workspace/Smarplan-Hofmann-Workspace`.

Die gemeinsame Developmentprüfung und beide Windows-Pakete sind erfolgreich.
Die beiden eigenen iPhone-Läufe sind noch nicht abgeschlossen. Der gesamte
Produktivabschluss wird deshalb nicht behauptet. Der
[vorherige vollständig abgeschlossene V16-Paketstand](CRM_ERP_LIEFERSTAND_V16_VOR_RV_2026-11-10.md)
bleibt unverändert archiviert; seine Pakete enthalten den neuen RV-Umfang nicht.

## Tatsächlich abgeschlossene gemeinsame Prüfung

[Development 42923602362](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42923602362)
besteht alle 20 eigenen Gruppen: 2.225 Backendfälle in 1.023,039 Sekunden mit
drei ausgewiesenen Auslassungen, 2.033 Linux-Apphauptfälle plus drei native
PDF-Fälle, 1.119 Browsermodulfälle, sechs tatsächliche Browsergruppen, sechs
PostgreSQL-/API-Gruppen, Runtime/MFA, Isolation, HTTPS, Update und Restore.
Windows besteht mit 1.988 Apphauptfällen, drei nativen PDF-Fällen und 81
portablen Backendfällen, tatsächlichem Bau, Paketierung, Start/Sicherung/Restore
und getrenntem Onlinepaket. Die im allgemeinen Backendlauf ausgelassenen beiden
PG-Gegenfälle und der Windows-Prozessfall sind dort tatsächlich separat geprüft.

Enthalten sind die bisherigen CRM-, Projekt-, Angebots-/Rechnungs-, Zeit-,
Material-, Einkaufs-, Service-, Finanz-, Personal- und abgegrenzten Lohnabläufe.
Der neue [belegte Minijob-RV-Verlauf](CRM_ERP_MINIJOB_RV_INTEGRATION_2026-11-10.md)
verbindet private Originale und vollständige Fassungsgeschichte mit genauer
Profilfassung, tatsächlichem Abrechnungsmonat und beiden Clients. Ein offenes
Verfahren erzeugt keine scheinbare Entscheidung. Neue Lohnschritte verwenden
den aktuell geprüften Status; historische Belege und Quittungen bleiben erhalten.

22 zusätzliche Paket-/Archivfälle bestehen in 17,556 Sekunden, darunter das
wirkliche festgelegte Commitarchiv nach MFA mit eigenem Quellmarker und neuen
RV-/Browserdateien. Eine weitere tatsächliche PG-/MFA-/Konkurrenz-/Geld-/EÜR-/
Export-/Komplettrestore-Gegenprüfung besteht in 44,962 Sekunden am unveränderten
Produktcode: 581,29 EUR Netto plus 209,66 EUR Abführung ergeben 790,95 EUR
EÜR-Aufwand, Vorsteuer 0,00 EUR. Eigener Testcontainer ist entfernt.

Der erste Kandidat 51c404b bleibt nicht freigegeben: Sein eigener Lauf besitzt
17 erfolgreiche und drei rote Gruppen. Die Altbelegregression und eine
Nullsekunden-Browsertesteingabe sind getrennt behoben und im aktuellen
Gesamtlauf nachgeprüft. Ursprüngliche Fehl- und Nachläufe bleiben mit ihren
jeweiligen Quellen unverändert unter
[evidence/minijob-rv-lifecycle-2026-11-10](evidence/minijob-rv-lifecycle-2026-11-10/)
erhalten. Frühere Erfolge werden nicht als neuer Lauf ausgegeben.

## Tatsächliche Windows-Pakete des aktuellen Quellstands

| Paket | Tatsächlicher Nachweis |
|---|---|
| [Windows mit lokalem Backend](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42923602362/artifacts/13814036629) | 40.712.595 Bytes; Quelle ab6b615; Metadatenablauf 2026-11-24T23:45:58Z |
| [Windows für den Onlineserver](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42923602362/artifacts/13813403219) | 22.319.641 Bytes; Quelle ab6b615; Metadatenablauf 2026-11-24T23:47:13Z |
| [Windows Start und Sicherung](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42923602362/artifacts/13812318527) | 19.624.557 Bytes; Quelle ab6b615; Metadatenablauf 2026-11-24T23:29:01Z |

SHA256 aus den tatsächlichen GitHub-Artefaktmetadaten:

- Windows vollständig: `f3ec25258853df97efdaed400ccdb8ddc136a33b3bc26bcb84ece48e0a66a480`.
- Windows online: `7ca912aed728d678b5b0ad0a3ede159bfeba19fe97f84e6a0aa1a41a256e9da9`.
- Start/Sicherung: `772dbe7241e15b6a8d353a0183109a404d806a52faaa1c2287fa7b0c1ec3ea0d`.

Dies sind Metadatendigests. Die ZIP-Bytes wurden hier nicht zusätzlich lokal
heruntergeladen und geprüft; ein früherer Archivabruf war bereits vor Empfang
von ZIP-Bytes mit HTTP403 blockiert. Die tatsächlichen CI-Bau-/Paket-/Import-/
Start-/Restoreprüfungen sind davon unabhängig erfolgreich. Die Downloads
benötigen GitHub-Zugriff und sind befristet.

## Eigene iPhone-Auslieferung: noch in Prüfung

- [Automatischer unsignierter Release 42923602365](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42923602365).
- [Signierte Vorbereitung 42924966961](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42924966961).

Beide sind nach beobachteter Laufkennung an genau ab6b615 gebunden. Endgültige
Pakete, Signatur-/Team-/Keychain-Prüfung und Schlüsselbereinigung werden erst
nach tatsächlichem Abschluss ergänzt. `prepare_signed_ipa=true`,
`upload_to_testflight=false`. Ein signiertes IPA ist keine TestFlight-Verteilung
oder reale Installation. Die überholte Vorbereitung 42918342817 zu 51c404b ist
vor dem ersten Apple-Export bewusst beendet; die tatsächliche Schlüsselbereinigung
ist erfolgreich bestätigt. Sie ist kein Paketnachweis des aktuellen Standes.

## Server und tatsächliche Abnahme

Die [konkrete Serveranleitung für ab6b615](CRM_ERP_SERVERUPDATE_AB6B615_2026-11-10.md)
beginnt mit der bekannten Windows-SSH-Verbindung, erhält den bisherigen
Quellcommit und verwendet das kontrollierte Update auf den festen geprüften
Stand. Die Bash-Syntax ist geprüft; aus dieser Cloud ist kein Serverbefehl
ausgeführt. Hier fehlen geschützter SSH-Zugang und Hostfreigabe. Der letzte
vom Nutzer bestätigte Server bleibt a93cb4d vom 05.11. Ein alter Cloudabruf
mit HTTP403 ist kein Beweis eines Serverausfalls oder einer neuen Installation.

[34 reale Gerätefälle](CRM_ERP_KUNDENTEST_PROTOKOLL_0_13.csv) bleiben ungeprüft;
die ursprünglichen 31 Zeilen sind bytegleich erhalten. Vor realen Tests passende
Client-/Serverstände abgleichen. Die älteren Windows-Online-Startnotizen
beschreiben Berichte noch pauschal als onlinepflichtig; für den ausdrücklich
freigegebenen Offline-Serviceberichtweg gelten die aktuellen
[Handbuchschritte](CRM_ERP_BENUTZERHANDBUCH.md#verbindungsabbruch-und-offlinearbeit)
und die [Konfliktklärung](CRM_ERP_OFFLINE_KONFLIKTKLAERUNG_2026-11-10.md).
Dies ist keine allgemeine Offlinefreigabe beliebiger Dokumentarten.

## Gesamtziel und konkrete verbleibende Grenzen

Die [Anforderungsmatrix](CRM_ERP_ANFORDERUNGEN.md) und Gesamtabnahmen A–G bleiben
maßgeblich. Technische Paketprüfungen ersetzen weder tatsächliche Geräte-,
Fach-, Rechts-, Sicherheits- noch Produktivnachweise. Weitere ausdrücklich
beschriebene Lohn-, Reise-, Offline-Altbestands- und Schnittstellenfälle sind
nicht pauschal geschlossen. Direkte produktive Meldewege und unabhängige
Fach-/Sicherheitsprüfungen fehlen. Die zusätzliche gleichzeitige Source5-Gruppe
bleibt ohne verifizierte fachliche Gruppierungsgrundlage gesperrt.

Qonto, Kreissparkasse Rottweil und Amex Business sind gewählt; echte Zugänge,
Anbieterdateien und Abnahmen fehlen. Dasselbe gilt für die festgelegten
Lieferanten. Loxones Hosteinrichtung ist ausdrücklich auf später verschoben.
Keine echte Zahlung, Meldung, Nachricht, Anbieteranbindung, neue Liveinstallation
oder TestFlight-Veröffentlichung wurde aus dem Entwicklungsauftrag ausgeführt.
Das Gesamtziel ist noch nicht vollständig erreicht.
