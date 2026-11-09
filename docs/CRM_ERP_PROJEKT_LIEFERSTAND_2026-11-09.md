# Gemeinsamer Projekt- und Korrekturstand vom 09.11.2026

Die drei neuen Abschnitte sind zusammengeführt und lokal geprüft:

1. [Projektanlage nach App-Neustart](CRM_ERP_PROJEKTANLAGE_NEUSTART_2026.md):
   Der verschlüsselte offene Auftrag wird nach frischer Anmeldung mit derselben
   Kennung wiederholt. Eine angenommene Anlage mit verlorener Antwort erzeugt
   kein zweites Projekt. Neue Schlüssel entstehen unter einer gemeinsamen
   Sperre; Quittungsfehler und beschädigte Zustände löschen keinen offenen Auftrag.
2. [Browser-Projektaufgaben](CRM_ERP_PROJEKTAUFGABEN_BROWSER_2026.md):
   Bearbeiten, Zuständigkeit, Erledigen, Abbrechen, Wiederöffnen und unveränderte
   Fassungen. Ungültige Prioritäten sind entfernt; Konflikte und verlorene
   Antworten behalten den ursprünglichen Auftrag.
3. [Begrenzte positive Lohnkorrektur](CRM_ERP_SOURCE5_POSITIVE_KORREKTUR_2026.md):
   Alte tatsächliche Zahlungsteile bleiben unverändert, zusätzliches Netto
   erhält einen eigenen Nachweis. Brutto/Ereignis/Zuflusstag bleiben gleich;
   Abführungsgrenzen und belegte Vollständigkeit sind verbindlich.

## Gemeinsame Prüfung

| Prüfung | Ergebnis |
| --- | --- |
| Breiter Lohn-/Reisesammellauf | 713 bestanden, kein Skip, 1519,359 s |
| Browsermodule einschließlich neuer Projektaufgaben | 912 bestanden, kein Skip |
| Gemeinsame native Journal-/Offline-/Lohn-/Dateifälle | 183 bestanden, kein Skip |
| Unternehmensgrundlage, Projektanlage und echte HTTP-Quittungen | 45 bestanden, kein Skip |
| Tatsächliche PostgreSQL-Integration | 4 bestanden, kein Skip; darunter Originalquittung, Konkurrenz und echter Dump/Restore |
| Tatsächlicher Paketimport und Paketverträge | 16 bestanden, kein Skip |
| Erneuter echter Browserablauf auf gemeinsamem Servercode | bestanden; MFA, sieben Aufgabenfassungen, verlorene Antworten, Konkurrenz, Rechteentzug und 390px |

Die Prüfgruppen überlappen; ihre Zahlen sind keine summierte Anzahl unabhängiger
Gesamtabnahmen. Der 713er Lauf prüfte die unveränderten Lohn-/Reisequellen vor
der danach integrierten Projektjournal-Erweiterung. Die 183 nativen Fälle und
die vier PostgreSQLfälle prüfen anschließend den gemeinsamen Stand. Browser-
JavaScript blieb seit dem 912er Lauf unverändert. Die ursprünglichen 32
Rechenmodule, die alte v1-Zahlungsdatei und das Originalziel sind bytegleich.

[Quellbindungen, Rohprotokolle und genaue Ergebnisse](evidence/project-delivery-2026-11-09/verification.json)
sowie die verlinkten Einzelabschnitte erhalten auch frühere Fehlversuche.
Der vorher übersprungene PostgreSQL-Workspacefall wurde in der echten
Datenbankgruppe ausgeführt; Historien bleiben über erneute Verbindung erhalten.
Beide eigenen Datenbankcontainer sind nach den Prüfungen entfernt.

## Auslieferungsgrenze

Der vorige veröffentlichte Stand 894ecdd hatte zwei bestätigte CI-Testfehler.
Die mobile Anmeldung und die echte native Dateischreibsynchronisierung sind
behoben und gezielt geprüft. Der iPhone-Job verwendet jetzt ebenfalls den
vorhandenen maschinenlesbaren Fehlerbericht. Der Stand `3859a1cb223f134e1eec14d4978e13be1ca8b039` ist veröffentlicht.
[Development42634757414](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42634757414)
und [iPhone42634757313](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42634757313)
laufen auf genau diesem Commit; signierter Upload nicht angefordert.
[Veröffentlichungsnachweis](evidence/project-delivery-2026-11-09/publication.json).
Ein vollständig grünes Remote-Ergebnis wird noch nicht behauptet.

Eine Installation auf dem Kundenserver und reale Windows-/iPhone-Geräteabnahmen
sind nicht erfolgt. Der zuletzt bestätigte Serverstand bleibt a93cb4d.
Der nächste eigenständige Codeabschnitt sind explizite Projektmeilensteine;
weitere Lohn-/EÜR-Fälle, Integrationen und Abnahmen A–G bleiben im Gesamtplan.
Diese Lieferung ist kein Abschluss der gesamten Software.
