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
läuft weiterhin auf derselben Quelle: `prepare_signed_ipa=true`,
`upload_to_testflight=false`. Ihre Appvorprüfung hat den Gerätebau erreicht.
Eine tatsächlich abgeschlossene neue Signatur samt Paketkennung wird erst
nach Abschluss bestätigt. Frühere Pakete 215/216 oder erste Auslagenpakete
werden nicht als signierte Pakete der korrigierten Quelle ausgegeben.

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
Die neu konkrete Uploadfrage zu ab6b615 ist unbeantwortet und deckt diesen
neuen Funktionsstand nicht ab. Der aktuelle manuelle Lauf bereitet nur das
signierte Paket vor. Ein TestFlight-Upload hat nicht stattgefunden.

Alle 34 realen Gerätefälle, Fach-/Sicherheitsprüfung und Gesamtabnahme A–G
bleiben offen. Anbieterzugänge und weitere benannte Code-/Fachfälle sind damit
nicht erledigt. Der vollständige Gesamtauftrag bleibt aktiv; eine produktive
Gesamtfreigabe liegt noch nicht vor.
