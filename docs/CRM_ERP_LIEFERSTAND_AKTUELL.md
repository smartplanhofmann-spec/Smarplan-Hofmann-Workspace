# Aktueller Lieferstand

Stand 10.11.2026. Projekt: `/workspace/Smarplan-Hofmann-Workspace`.
Maßgeblicher geprüfter Produktcode:
`29b02c82a12d4aa1dfc97eaa84638d840882612d` auf dem autorisierten Testbranch
`codex/testupdate-0.7-projects-20261104`. Nachfolgende reine Dokumentationsbelege
ändern diesen Produktcode nicht. Das unveränderte Gesamtziel bleibt gültig;
eine abgeschlossene technische Lieferung ist keine vollständige Produktivfreigabe.

## Geprüfter Umfang

CRM, Projekte, Angebote/Rechnungen, Zeiten, Material, Service und die ausdrücklich
abgegrenzten Finanz-/Personalabläufe verwenden den gemeinsamen Kern. Enthalten
sind jetzt auch die native Offline-Berichtsklärung, der CAMT.053.001.08-
Originalimport in Browser und App und die Personalprofilpflege ohne Zugriff
auf die vollständige Inhaber-Benutzerverwaltung. Ein vorhandenes Personalprofil
kann auch nach Sperrung seines Logins korrekt beendet werden.

Die [eigene Development-Prüfung](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42872855464)
besteht alle 20 Gruppen einschließlich tatsächlicher Windowsbauten, Browser,
PostgreSQL, MFA, Isolation, Update und Wiederherstellung. Der Backendjob
bestätigt 2.186 Fälle in 1.565,117s mit drei ausgewiesenen Auslassungen.
Der Flutterjob bestätigt drei separate native PDF-Fälle und 2.001 Hauptfälle,
zusammen 2.004 erfolgreiche Appfälle. Die ausgewiesenen Auslassungen des
allgemeinen Backendjobs werden nicht als bestandene Einzeltests ausgegeben;
eigene PostgreSQL-/Windowsgruppen liefern zusätzliche getrennte Nachweise.
[Unveränderte Rohlogs und Prüfsummen](evidence/employee-account-selection-2026-11-10/manifest.json).

Der zusätzliche lokale App-Gesamtlauf wurde beim Cloud-Ausfall unterbrochen;
sein Teilprotokoll endet bei 1.229 sichtbaren Erfolgen ohne Abschluss-/Exitstatus.
Er zählt ausdrücklich nicht als vollständiger Erfolg. Der eigene vollständige
CI-Lauf ist davon unabhängig erfolgreich. Der ältere Bankstand 4f67bf8 besitzt
seinen getrennten vollständigen lokalen Nachlauf mit 1.997 Fällen.

## Tatsächliche Pakete

| Paket für Produktquelle 29b02c8 | Tatsächlicher Nachweis |
|---|---|
| [Windows mit lokalem Backend](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42872855464/artifacts/13791891675) | 40.634.172 Bytes; tatsächlicher Windowsbau einschließlich XML-Parser/Schema |
| [Windows für den Onlineserver](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42872855464/artifacts/13791089491) | 22.260.434 Bytes; getrenntes Onlinepaket |
| [Unsignierter iPhone-/iPad-Release 209](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42872855484/artifacts/13791784869) | 15.076.475 Bytes; automatischer Push-Lauf erfolgreich; noch keine installierbare Verteilung |
| [Signiertes iPhone-/iPad-Paket 210](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42873343567/artifacts/13794053691) | 29.959.338 Bytes; tatsächlicher manueller Apple-Export, Signatur-/Team-/Keychain-Prüfung und Schlüsselbereinigung erfolgreich; TestFlight-Upload ausgelassen |

SHA-256 der Windows-Komplettdatei:
`8975bb7e72e3da837bd506f9496f4b8ca8959689d54020aeda65371fbbc9900c`.
Windows-Online:
`7e0a706ff1ad07f5f6fb4a3c0414d44a677247a17620359e4ac47a5a98a7e91b`.
Unsigniertes iOS 209:
`ec5eb82b834f7b6556deea614e879b5744c834ecef457ecdb9e16d666cbb0599`.
Die GitHub-Artefakte sind derzeit bis 24.11.2026 befristet und benötigen
Repositoryzugriff. Ein Prüfsummenabgleich ersetzt keine Geräteabnahme.
Die obigen Prüfsummen stammen aus den tatsächlichen GitHub-Artefaktmetadaten.
Eine zusätzliche unabhängige ZIP-Prüfung in dieser Cloud scheitert vor Empfang
der Dateibytes an HTTP403 des ausgehenden Proxys, auch über den vom Connector
bereitgestellten Dateilink. Sie wird nicht als lokal bestanden ausgegeben;
die eigenen tatsächlichen CI-Bau-/Paketprüfungen bleiben getrennt erfolgreich.

Die manuell ausgelöste [signierte Vorbereitung 42873343567](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42873343567)
besteht vollständig auf derselben Produktquelle. Tatsächliches signiertes
Paket 210: Artefakt 13794053691, SHA-256
`bd556ca8b5464b6436ebbd9544831d8013a6e766adf41e838de4d8ee06be4e06`.
Der tatsächliche macOS-Job 130058782187 bestätigt endgültige Apple-
Distributionssignatur, richtiges Team, eigene Keychain-Berechtigung und
Schlüsselbereinigung. Der TestFlight-Schritt ist ausdrücklich ausgelassen;
ein Upload ist weder ausgeführt noch aus der Vorbereitung autorisiert.

Die tatsächliche macOS-Vorprüfung zu Build 210 besteht 1.996 Hauptfälle plus
drei native PDF-Fälle. Fünf ausdrücklich auf Linux begrenzte Integrationsfälle
sind dort übersprungen und im getrennten vollständigen Linux-Lauf enthalten.
Das ältere signierte Paket 208 aus 42864950880 gehört weiterhin zu 4f67bf8
und enthält die spätere Personal-Korrektur noch nicht. Eine signierte App-Store-
IPA allein ist keine TestFlight-Verteilung oder tatsächliche Geräteinstallation.

Die älteren Startnotizen im Windows-Online-ZIP beschreiben Berichte noch
pauschal als onlinepflichtig. Für den inzwischen ausdrücklich freigegebenen
Offline-Serviceberichtweg gelten die aktuellen
[Handbuchschritte](CRM_ERP_BENUTZERHANDBUCH.md#verbindungsabbruch-und-offlinearbeit)
und die [Konfliktklärung](CRM_ERP_OFFLINE_KONFLIKTKLAERUNG_2026-11-10.md);
daraus folgt keine allgemeine Offlinefreigabe aller Dokumentarten.

## Server und erste Geräteprüfung

Die [konkrete Serveranleitung](CRM_ERP_SERVERUPDATE_29B02C8_2026-11-10.md)
enthält zuerst die bekannte Windows-SSH-Verbindung und anschließend den auf
29b02c8 festgelegten kontrollierten Updatebefehl. Aus dieser Cloud ist dieser
Schritt mangels SSH-Schlüssel/Agent nicht am Server ausgeführt. Der letzte vom
Nutzer bestätigte Live-Stand bleibt a93cb4d vom 05.11. Die Veröffentlichung
eines Quellbranches verändert diese Installation nicht automatisch.

Das [Geräteprotokoll](CRM_ERP_KUNDENTEST_PROTOKOLL_0_13.csv) enthält 28 noch
ungeprüfte Fälle. Zusätzliche Personal-, XML-Bank- und native Konfliktfälle
ergänzen die unveränderten ursprünglichen 20 Fälle. Das
[Prüfpaket](CRM_ERP_EXTERNER_ABNAHMEAUFTRAG_2026-11-10.md) beschreibt die
Fach-, Zugriffs- und Betriebsprüfung anhand kontrollierter Daten.

## Verbleibendes Gesamtziel

Die [Anforderungsmatrix](CRM_ERP_ANFORDERUNGEN.md) und der
[Arbeitsstand](CRM_ERP_ARBEITSSTAND.md) benennen weiterhin offene Codefälle,
direkte Anbieterzugänge und echte Bank-/Lieferantendaten, noch nicht
unterstützte Lohnfälle und Meldeverfahren, zusätzliche Offline-/Altbestandsfälle,
aktuelle Server-/Geräteprüfung sowie unabhängige Fach-, Sicherheits- und
Datenschutznachweise. Die spätere Loxone-Einrichtung bleibt wie vom Nutzer
festgelegt zurückgestellt. Keine Zahlung, Meldung, Bestellung, echte Nachricht
oder TestFlight-Veröffentlichung wurde aus diesem Entwicklungsauftrag ausgelöst.
Die ganze Software ist noch nicht als vollständig produktiv freigegeben belegt.
