# Aktueller Lieferstand

Stand: 11.11.2026. Veröffentlichte Produktquelle:
`4bb5071891344a38f640d8ae43ec240c1f95e61e`, ausschließlich auf
`codex/testupdate-0.7-projects-20261104`. Hauptprojekt:
`/workspace/Smarplan-Hofmann-Workspace`.

Die [Auslagenoriginalsperre](CRM_ERP_AUSLAGEN_ORIGINALSPERRE_2026-11-11.md)
verhindert die doppelte Einreichung identischer ganzer Belege auch zwischen
Mitarbeitern. Neue Einreichung, Freigabe, Erstattung und zusätzliche
Reiseabrechnung prüfen die Unternehmensbindung. Browser und App ergänzen
mit eigener Serverfähigkeit die begründete Rücknahme unbezahlter Freigaben.
Originale, frühere Entscheidungen, Geldflüsse und angenommene Quittungen bleiben erhalten.

## Korrigierter Updatevertrag und tatsächlich geprüfter Altbestand

Der erste Kandidat 3c824c1 ist zurückgezogen: Sein zusätzlicher Suchindex
verändert einen alten Migrationsvertrag. Die [Korrektur](CRM_ERP_AUSLAGEN_MIGRATIONSERHALT_2026-11-11.md)
erhält alle 59 Modulverträge für beide Datenbankdialekte exakt zu ab6b615.
Weder gespeicherte Journalwerte noch Schutzprüfungen werden überschrieben.
Der alte Serverbefehlsblock ist gesperrt. Die alte signierte Vorbereitung wurde
noch vor dem ersten Apple-Schritt gestoppt; ihr Signierjob besitzt keine Schritte.

Korrigierte Dateien: 81 betroffene Backend-/Reise-/CI-Fälle in 60,654 Sekunden,
48 Auslagen-/Schema-/CI-Fälle in 10,107 Sekunden und vier tatsächliche
PostgreSQL-/MFA-/Altbestands-/Komplettrestorefälle in 31,890 Sekunden erfolgreich.
Aus dem alten Archiv erzeugte SQLite- und PostgreSQL-Bestände behalten ihre
Zahlungsquittungen. Bei PostgreSQL bleiben zudem der gesamte Datenfingerabdruck,
Originaldatei, Monatsquittung und Monats-PDF exakt erhalten.

Am tatsächlichen 4bb5071-Commitarchiv bestehen zwei Paket-/MFA-/Browserdateifälle
in 2,634 Sekunden und ein weiterer Zwei-Firmen-MFA-Fall: Gleiches Original ist
unabhängig pro Firma zulässig, innerhalb einer Firma wird die zweite Einreichung
gesperrt. Fremder Firmentoken wird abgewiesen; Browserdateien sind bytegleich.
Originalziel und 64 bisherige Lohnmodule sind unverändert. Browser-/App-
Produktcode sind bytegleich zu 3c824c1; dessen eigene Komponentennachweise
werden nicht als neuer gemeinsamer Gesamtquelllauf ausgegeben.

## Gemeinsame Developmentprüfung vollständig erfolgreich

[Development 42968922844](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42968922844)
besteht alle 20 eigenen Gruppen auf exakt 4bb5071: 2.236 Backendfälle in
1.040,812 Sekunden mit drei ausgewiesenen Auslassungen, 2.036 Linux-Appfälle
plus drei native PDF-Fälle, 1.120 Browsermodulfälle, alle sechs tatsächlichen
Browser- und sechs PostgreSQL-/API-Gruppen sowie Runtime, MFA, HTTPS, Update
und Restore. Die zwei ausgelassenen PostgreSQL-Gegenfälle laufen tatsächlich
in der eigenen PG-Auswahl; der Windows-Prozessfall gehört zum Windowsprüfumfang.

Windows besteht mit 1.991 Apphauptfällen, drei nativen PDF-Fällen und 81
portablen Backendfällen. Tatsächlicher Releasebau, Paketierung, Start,
Sicherung/Wiederherstellung und getrenntes Onlinepaket sind erfolgreich.
Die Downloadkennungen und SHA256 stammen aus tatsächlichen GitHub-Metadaten;
die äußeren Artefakt-ZIPs wurden hier nicht erneut lokal heruntergeladen.

| Paket | Tatsächliche Quelle und Metadaten |
|---|---|
| [Windows mit lokalem Backend](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42968922844/artifacts/13833098535) | 4bb5071; 40.713.207 Bytes; SHA256 `c34887ee16df78485ee176d08a613686686053ee8ac4c297477ae0a8217b05f0` |
| [Windows für den Onlineserver](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42968922844/artifacts/13832954008) | 4bb5071; 22.319.969 Bytes; SHA256 `c7a4e496a66a93e626fd7fdfc722d25c514a4e3d8210e02b792fea2a5446227c` |
| [Windows Start und Sicherung](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42968922844/artifacts/13833135094) | 4bb5071; 19.625.436 Bytes; SHA256 `d4da0c743719978b5267ffdd0e8728092353ebda4db3c59bb5314534dda2e1a7` |

## Eigene iPhone-Auslieferung

Der [automatische Lauf 42968922850](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42968922850)
ist erfolgreich: tatsächliche 2.031 Apphauptfälle plus drei native PDF-Fälle,
fünf ausgewiesene Linux-Auslassungen, Gerätebau, Konfiguration und Paketprüfung.
Der automatische Signierschritt ist ausgelassen; kein Upload.

[Unsigniertes Prüfartefakt 219](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42968922850/artifacts/13834280596):
15.123.896 Bytes, Quelle 4bb5071, GitHub-Metadaten-SHA256
`c248cf23fa856deb2657c7e20985159a2ec24e0a87f62c3d2bff34325599210a`.
Dieses unsignierte Prüfartefakt ist kein bereits verteiltes iPhone-Paket.

Die [signierte Vorbereitung 42968958373](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42968958373)
besteht mit beiden Jobs auf exakt 4bb5071. Auch ihre eigene Vorprüfung besteht
2.031 Apphauptfälle plus drei native PDF-Fälle mit fünf ausgewiesenen
Linux-Auslassungen. Beide Apple-Exporte, endgültige Signatur-/Team-/Keychain-
Prüfung und Schlüsselbereinigung sind erfolgreich. Der TestFlight-Schritt
ist tatsächlich ausgelassen.

[Signiertes iPhone-Paket 220](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42968958373/artifacts/13834509998):
30.029.207 Bytes, Quelle 4bb5071, Bundle-ID `de.smartplanhofmann.office`,
GitHub-Metadaten-SHA256
`f7da31a9314c1ebf702ab013d9f46414154ed75fa94387f927c77f75d566877b`.
Die signierte Vorbereitung ist vollständig technisch geprüft; eine tatsächliche
TestFlight-Übermittlung, Verarbeitung bei Apple oder Geräteinstallation liegt
noch nicht vor.

Das getrennte unsignierte Vorprüfpaket 220 hat Artefaktkennung 13834413616,
15.123.860 Bytes und GitHub-Metadaten-SHA256
`699a20089717b9ab2a32438a459c9f5fd39448fa55829c2d7ac4ea72364147eb`.
Alle Pakete und die drei eigenen Läufe sind derselben Produktquelle zugeordnet.

Der [erste Auslagenlieferstand](CRM_ERP_LIEFERSTAND_AUSLAGEN_ERSTKANDIDAT_2026-11-11.md)
und der [vorherige RV-Lieferstand](CRM_ERP_LIEFERSTAND_RV_VOR_AUSLAGEN_2026-11-11.md)
bleiben mit ihren eigenen Quellen und Ergebnissen archiviert. Der erste
Auslagen-Developmentlauf endet abgebrochen mit 19 erfolgreichen Jobs und einem
abgebrochenen Backendjob; beide alten iPhone-Läufe enden abgebrochen. Der
rote Altbestandsgegenfall bleibt der Grund für den Rückzug von 3c824c1.

## Betrieb und notwendige Freigaben

Die [konkrete Serveranleitung für 4bb5071](CRM_ERP_SERVERUPDATE_4BB5071_2026-11-11.md)
ist auf genau diesen erfolgreich geprüften Commit festgelegt und syntaktisch
geprüft. Ein zusätzlicher tatsächlicher Operatorgegenlauf vom letzten
bestätigten a93cb4d erhält alte Daten/Quittungen bei Sicherung, Kandidatenkopie,
Migration der drei zusätzlichen Module und Rechtevergabe. Aus dieser Cloud wurde kein Serverupdate
ausgeführt. Letzte Nutzerbestätigung bleibt a93cb4d vom 05.11.; geschützter
Serverzugang und freigegebener Host fehlen hier.

Die automatische Freigabeprüfung hat den aus „Ok. Mach fertig“ abgeleiteten
TestFlight-Start abgelehnt: Eine eindeutige Freigabe des konkreten signierten
App-Pakets an Apple fehlte. Der abgelehnte Start wurde nicht ausgeführt.
Die frühere Frage zu ab6b615 ist durch die neue konkrete Frage zu Smartplan
Office, Bundle-ID `de.smartplanhofmann.office`, Funktionsstand 4bb5071 und
geprüfter Vorbereitung 220 ersetzt. Diese Frage ist ausdrücklich mit „Ja, diesen Funktionsstand an Apple TestFlight
hochladen“ beantwortet. Der freigegebene Uploadlauf wird separat dokumentiert. Der aktuelle manuelle Lauf hat ausschließlich das signierte Paket vorbereitet.
Ein TestFlight-Upload hat nicht stattgefunden. Der vorhandene Uploadweg würde
einen neuen Build mit identischem Programmcode erstellen; dafür ist eine
ausdrückliche passende Freigabe des aktuellen Funktionsstands/Ziels erforderlich;
diese liegt nun vor. Der bisherige Vorbereitungsnachweis bleibt unverändert.

Die drei zusätzlichen Gerätefälle zur Originalsperre/Freigaberücknahme sind
vorbereitet; alle bisherigen 34 Zeilen bleiben bytegleich. Alle 37 realen
Gerätefälle, Fach-/Sicherheitsprüfung und Gesamtabnahme A–G
bleiben offen. Anbieterzugänge und weitere benannte Code-/Fachfälle sind damit
nicht erledigt. Der vollständige Gesamtauftrag bleibt aktiv; eine produktive
Gesamtfreigabe liegt noch nicht vor.
