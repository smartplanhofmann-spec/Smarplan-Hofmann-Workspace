# Verbindlicher aktueller Arbeitsstand

Stand: 11.11.2026. Der aktive Auftrag bleibt die gesamte CRM-/ERP-Software nach
Nutzerauftrag und unveränderter `CRM_ERP_Gesamtziel.txt`. Ein abgeschlossener
Lieferabschnitt verkleinert das Gesamtziel nicht und beendet den Auftrag nicht.

## Projekt und tatsächlich veröffentlichte Quelle

Hauptprojekt `/workspace/Smarplan-Hofmann-Workspace`, lokaler Branch
`codex/factor-transition-periods-20261110`. Einziger autorisierter Testbranch:
`codex/testupdate-0.7-projects-20261104` im bestehenden GitHub-Repository.
Kein Force-Push und kein Wechsel des Standardbranches daraus ableiten.

Aktuelle Produktquelle: `4bb5071891344a38f640d8ae43ec240c1f95e61e`.
Originalziel: 23.863 Bytes, SHA256
`a4dea28f6de4afd3e36d1549441aad91ce16dad374f56097979cc2d79b07fbf5`.
Alle 64 bisherigen Lohnmodule bleiben zu ab6b615 bytegleich.
Ältere eigene Arbeitskopien bleiben erhalten; die unter
`/tmp/smartplan-expense-originals-20261111` enthält den zurückgezogenen ersten
Auslagenkandidaten. Weitere Entwicklung auf dem aktuellen Hauptprojekt fortsetzen.

## Neue Auslagenkorrektur und tatsächlicher Altbestand

Die [unternehmensweite Originalsperre](CRM_ERP_AUSLAGEN_ORIGINALSPERRE_2026-11-11.md)
schließt die tatsächlich reproduzierte zweite Einreichung desselben schon
vollständig erstatteten Belegs durch einen anderen Mitarbeiter. Neue
Einreichung, Freigabe, Erstattung und zusätzliche Reiseabrechnung prüfen die
Bindung innerhalb derselben Unternehmensdatenbank. Browser und App ergänzen
mit eigener Serverfähigkeit die begründete Rücknahme unbezahlter Freigaben.
Alte Originale, Geldflüsse, Monatsunterlagen und angenommene Quittungen bleiben erhalten.

**Erster Kandidat 3c824c1 ist nicht zur Installation freigegeben.** Ein echter
Altbestandsgegenfall erkennt dessen zusätzlich eingefügten Index als Änderung
an einem alten Version-1-Migrationsvertrag. Der Index ist entfernt; weder
Journalwerte noch Schutzprüfungen werden überschrieben. Die [Korrektur](CRM_ERP_AUSLAGEN_MIGRATIONSERHALT_2026-11-11.md)
erhält alle 59 registrierten Modulverträge in beiden Datenbankdialekten exakt
zu ab6b615. Ein fester Regressionstest bindet die alten Personalprüfsummen.

Tatsächlich erfolgreich auf den korrigierten Dateien: 81 betroffene Backend-/
Reise-/CI-Fälle in 60,654 Sekunden; 48 Auslagen-/Schema-/CI-Fälle in 10,107 Sekunden; vier echte
PostgreSQL-/MFA-/Altbestands-/Komplettrestorefälle in 31,890 Sekunden. Die aus dem alten
Commitarchiv erzeugten SQLite- und PostgreSQL-Bestände behalten ursprüngliche
Zahlungsquittungen. Bei PostgreSQL sind außerdem gesamter Datenfingerabdruck,
Originaldatei, Monatsquittung und Monats-PDF exakt erhalten.

Am tatsächlichen korrigierten Commitarchiv bestehen zwei Paket-/MFA-/
Browserdateifälle in 2,634 Sekunden und ein weiterer Zwei-Firmen-MFA-Fall: gleiches
Original unabhängig zulässig, zweite Einreichung innerhalb der Firma gesperrt,
fremder Firmentoken abgewiesen und exakt passende Browserdateien ausgeliefert.
Alle eigenen Testcontainer sind nach vollständiger ID-/Label-/Portprüfung entfernt.

Browser-/App-Produktcode sind bytegleich zum ersten Auslagenkandidaten, dessen
1.120 Browsermodulfälle, zwölf native Personalprüfungen, vollständige Appanalyse
und tatsächlicher Browserablauf erfolgreich waren. Diese Komponentennachweise
werden nicht als neuer gemeinsamer Gesamtquelllauf ausgegeben. Der neue eigene
Gesamtnachlauf auf genau 4bb5071:

- Development 42968922844 vollständig erfolgreich: 2.236 Backendfälle mit drei
  ausgewiesenen Auslassungen, 2.036 Linux-Appfälle plus drei PDF-Fälle,
  1.120 Browsermodulfälle, sechs Browser-/sechs PG-Gruppen, Runtime/MFA/HTTPS/
  Update/Restore. Windows: 1.991 Appfälle, drei PDF-Fälle, 81 portable
  Backendfälle, tatsächliche Komplett-/Onlinepakete und Start/Sicherung/Restore.
- Automatisches iPhone 42968922850 erfolgreich: 2.031 Appfälle plus drei
  native PDF-Fälle mit fünf Linux-Auslassungen; unsigniertes Paket 219 vorhanden.
- Signierte Vorbereitung 42968958373 läuft weiter: `prepare_signed_ipa=true`,
  `upload_to_testflight=false`.

Alte Läufe 42966124379/42966124295/42966356463 behalten ihre tatsächlichen
Ergebnisse. Die alte manuelle Vorbereitung wurde vor dem ersten Apple-Schritt
abgebrochen; ihr Signierjob besitzt keine Schritte. Neue Paketkennungen und
endgültige Ergebnisse werden im [Lieferstand](CRM_ERP_LIEFERSTAND_AKTUELL.md) ergänzt.
Rohbelege liegen in den getrennten Auslagen- und Migrationsnachweisverzeichnissen.

## Betrieb, Uploadfreigabe und vollständiges Gesamtziel

Letzter vom Nutzer bestätigter Serverstand: a93cb4d02eab610e5f2a8b07fbd1ee51ae99c3e5,
05.11. Hier fehlen SSH-Schlüssel/Agent/Remoteidentität und freigegebener Serverhost;
kein neuer Serverupdate wurde ausgeführt. Konkrete Windows-SSH-Verbindung und
festgelegter Updateweg bleiben vorbereitet. Die Anleitung für 3c824c1 ist
zurückgezogen und ihr Ausführungsblock gesperrt.

Die automatische Freigabeprüfung hat den aus „Ok. Mach fertig“ abgeleiteten
TestFlight-Start abgelehnt, weil die Übermittlung des konkreten signierten
App-Pakets an Apple darin nicht ausdrücklich genug freigegeben ist. Der ganze
abgelehnte Start wurde nicht ausgeführt. Die neu konkret gestellte Frage zu
ab6b615 ist weiterhin unbeantwortet und deckt den neuen Funktionsstand nicht
ab. Signierte Vorbereitung ist kein Upload; Upload bleibt false. Nur eine
passende ausdrückliche Freigabe des konkreten Pakets/Ziels ermöglicht Verteilung.

Deutschland/EUR, Einzelunternehmen/EÜR, Regelbesteuerung/Ist, 19 %, SKR04,
Nettopreise; reguläre Mitarbeiter und gewerbliche Minijobs. Die frühere
Priorisierung des Projektbetriebs streicht Lohn/Buchhaltung nicht aus dem Ziel.
Banken: Qonto, Kreissparkasse Rottweil, Amex Business. Lieferanten: Granzow,
Alexander Bürkle, Loxone, Voltus. Echte Zugänge und Anbieterdateien fehlen;
Loxones Hostfreigabe ist ausdrücklich auf später verschoben. Nicht erneut als
unbeantwortete Frage behandeln; keine fertige echte Anbieteranbindung behaupten.

34 echte Gerätefälle und Gesamtabnahmen A–G bleiben offen. Eigene synthetische
Prüfungen sind keine unabhängige Fach-/Sicherheitsabnahme. Weitere Code-/Fachfälle,
insbesondere Source5-Gruppen, alte Offlinebestände und weitere Lohnfälle, bleiben
im [Plan](CRM_ERP_UMSETZUNGSPLAN.md) und in der [Matrix](CRM_ERP_ANFORDERUNGEN.md).
Für zusätzliche gleichzeitige Source5-Gruppen fehlt die verifizierte fachliche
Gruppierungsgrundlage; weitere amtliche Ansichten liefern 503. Keine Regel raten
und fehlende Codefälle nicht pauschal extern erledigt nennen.

Keine echten Nachrichten, Zahlungen, Meldungen oder produktiven Migrationen
aus dem Entwicklungsauftrag ableiten. Historische Quellen/Quittungen erhalten.
Der [vorherige Arbeitsstand](CRM_ERP_ARBEITSSTAND_AUSLAGEN_ERSTKANDIDAT_2026-11-11.md)
und die vorherigen RV-/V16-Lieferstände bleiben als zeitgebundene Nachweise
archiviert. Die gesamte Software ist weiterhin nicht vollständig produktiv freigegeben.
