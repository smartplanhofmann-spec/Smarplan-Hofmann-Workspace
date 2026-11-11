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

## Gemeinsame Plattform- und Paketprüfung läuft auf 4bb5071

| Lauf | Tatsächlich beobachteter Stand |
|---|---|
| [Development 42968922844](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42968922844) | Neuer vollständiger Lauf mit 20 eigenen Gruppen |
| [Automatisches iPhone 42968922850](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42968922850) | Neuer unsignierter Gerätebuild |
| [Signierte Vorbereitung 42968958373](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42968958373) | `prepare_signed_ipa=true`, `upload_to_testflight=false` |

Endgültige Ergebnisse, Paketkennungen und Digests werden nach tatsächlichem
Abschluss ergänzt. Frühere Auslagen- oder RV-Pakete werden nicht als Pakete der
korrigierten Quelle ausgegeben. Der [erste Auslagenlieferstand](CRM_ERP_LIEFERSTAND_AUSLAGEN_ERSTKANDIDAT_2026-11-11.md)
und der [vorherige RV-Lieferstand](CRM_ERP_LIEFERSTAND_RV_VOR_AUSLAGEN_2026-11-11.md)
bleiben mit ihren damaligen Quellen und Ergebnissen archiviert.

## Betrieb und notwendige Freigaben

Die [konkrete Serveranleitung für 4bb5071](CRM_ERP_SERVERUPDATE_4BB5071_2026-11-11.md)
ist vorbereitet und syntaktisch geprüft; erst nach erfolgreichem gemeinsamem
Developmentabschluss verwenden. Aus dieser Cloud wurde kein Serverupdate
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
