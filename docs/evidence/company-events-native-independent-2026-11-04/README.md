# Unabhängiger Native-Review: Unternehmensereignisse

Stand: 4. November 2026. Arbeitsbaum `/workspace/smartplan-company-events-20261104`. Geprüft wurde der [native Ereignisvertrag](../../CRM_ERP_UNTERNEHMENSEREIGNISSE_NATIVE_2026-11-04.md) anhand der tatsächlich erzeugten `app/test/fixtures/company_events_2026.json`, echter BusinessSession-Instanzen und zusätzlicher eigener Gegenfälle. Keine eigenen Produktänderungen, keine Commits.

Ein konkreter Vertragsfehler wurde reproduziert und durch den Runtimeowner eng korrigiert: Die tatsächliche `external_unconfirmed.plan_after` mit bestehendem Ausführungsclaim und `outcome: null` wurde angenommen, wenn ausschließlich das abgeleitete `status` auf `succeeded` geändert war. Der unabhängige Widgettest zeigte bei 390 Pixeln ausdrücklich „Status: Erfolgreich ausgeführt“. Es gab dabei keinen tatsächlichen Erfolgsnachweis.

Der gezielte Ownerfix in `business_company_event_contract.dart` verlangt bei `status == succeeded` eine Ausführung und ein tatsächliches Ergebnis mit `outcome.status == succeeded`. Der unveränderte Vertragsgegenfall sowie der tatsächliche Widgetgegenfall bestehen anschließend. Bereits erfolgreiche historische Ausführungen bleiben auch bei späteren Statuswerten `stale` oder `suspended_after_restore` nachprüfbar; dafür besteht ein eigener positiver Grenzfall. Der Review behauptet keinen solchen Fehler in einer tatsächlichen Serverantwort; geprüft wurde die erforderliche Zurückweisung einer widersprüchlichen Antwort.

Die neue unabhängige Datei `app/test/business_company_events_independent_review_test.dart` enthält 14 Tests:

- Falsche Erfolgsbehauptung ohne Ergebnis wird sowohl im Vertragsprüfer als auch in der schmalen nativen Übersicht abgewiesen.
- Tatsächliches historisches erfolgreiches Ergebnis bleibt bei veralteten Quellen beziehungsweise Wiederherstellungssperre erhalten.
- Ausschließlich im Projekt entzogene Quellen- oder Freigaberechte löschen den privaten Prüfvermerk, während beide globalen Rechte ausdrücklich erhalten bleiben.
- Während einer ausstehenden Akteursprüfung verlorenes Projekt-Schreibrecht verhindert einen neuen POST; die globale Schreibberechtigung bleibt vorhanden.
- Verspätete erfolgreiche und fehlerhafte Planantworten können einen danach neu eingegebenen Regelentwurf weder ersetzen noch löschen.
- Verspätete erfolgreiche und fehlerhafte Freigabeantworten gehören zum ursprünglichen offenen Auftrag. Ein neuerer Regelentwurf bleibt bestehen; nur eine gültige Originalannahme löst den alten Auftrag auf.
- Sitzungswechsel, Hintergrundwechsel und alleiniger Entzug der Verwaltungsberechtigung löschen private Regelentwürfe. Eine Änderung der abgelösten Sitzung beeinflusst die neue Ansicht nicht.
- Drei gleichzeitig offen gehaltene Vorgangsarten — Regel, Scan und konkrete Freigabe — bewahren drei verschiedene ursprüngliche Bodies und Kennungen. Eine über Kreuz zugeordnete Scanquittung kann keinen Freigabeauftrag auflösen. Gezielte Wiederholungen erhalten jeweils den exakten Originalbody und erzeugen insgesamt nur die drei ursprünglichen Effekte.

## Tatsächliche Ergebnisse

| Lauf | Ergebnis | Nachweis |
| --- | --- | --- |
| Erste unabhängige Prüfung auf eingefrorenem Produktstand | 11 bestanden, ein Vertragsgegenfall rot | `before-status-outcome-fix.txt` |
| Getrennter echter Widgetgegenfall vor Fix | rot; falsche Erfolgsanzeige bei 390px | `widget-before-status-outcome-fix.txt` |
| Erste unabhängige Nachprüfung nach Ownerfix | 13/13 bestanden | `first-independent-after-fix.txt` |
| Abschließende gemeinsame Suite | 74/74 bestanden: 14 unabhängige + 60 Ownerfälle | `combined-final.txt` |
| Analyse der neuen unabhängigen Datei | 0 Befunde | `analyze-final.txt` |

Die 60 Ownerfälle enthalten den erneut tatsächlich ausgeführten lokalen HTTP-Ablauf mit verlorener erfolgreicher Antwort auf `POST /rules`, `POST /scan` und `POST /plans/:id/execute`. Jeder Auftrag wird mit derselben ursprünglichen Kennung und demselben vollständigen Body erneut gesendet. Dabei entsteht genau eine tatsächliche Testaufgabe. Weitere Fälle sichern `external_unconfirmed` mit angenommener ursprünglicher Quittung, fehlendem Ergebnis und ohne neue Ausführungsaktion sowie Sitzungs-/Generations-/Rechte-/Hintergrundwechsel.

Die anfängliche Teststeuerung enthielt vier zusätzliche Zeitüberschreitungen, weil ein Hilfsaufruf vor der Navigation eine absichtlich offene Fortschrittsanzeige abwartete. Nach Korrektur ausschließlich dieser eigenen Testnavigation bleiben im archivierten roten Lauf genau der Vertragsfehler und separat der Widgetbeleg. Diese Hilfsfehler werden nicht als Produktbefunde gezählt. Die abschließende Analyse erforderte lediglich das Entfernen eines ungenutzten Imports in der eigenen Testdatei.

## Hashbindung und Übergabe

Ursprünglicher Ownerfreeze: `9b737c632ad28623372a6b6d0d48c99247697239598e6460d54c94d2a6bff58f`. Nach dem engen Fix: `fa00c556a991bee7395ff458ce49a1af9e56a5f48fda4bd636dd4c4d54e3459c`. Vertrag vorher `8909b2f77f5674ff97ca1a58eb3a10d39b0db9ea1fae609f8cee92b69165b7ad`, danach `977def401a70c4a11f240f6c2c8a15ce0b81756288b580e9bb16ca45f9b1c2e6`. Alle anderen Owner-Runtime-, Test- und Fixturedateien bleiben unverändert; die Endprüfung gleicht sie mit dem aktualisierten Ownermanifest ab.

`before-hashes.json`, `contract-before-fix.txt` und `status-outcome-owner-fix.diff` erhalten den tatsächlichen ursprünglichen Stand. Das eigene `manifest.json` bindet die abschließenden Nachweise und die geprüften Runtimehashes. In das Gesamtpaket kommen zusätzlich zum aktualisierten Ownerpaket nur die neue unabhängige Testdatei und dieses Evidenzverzeichnis. Es wurde keine erneute Gesamtprüfung aller älteren Appmodule behauptet; deren bisherige 89 Ownerregressionsfälle sind separat dokumentiert. Root führt die Integration durch.

Reproduktion aus `app/` mit vorhandener Flutter-Toolchain:

```sh
SMARTPLAN_TEST_PYTHON=/tmp/smartplan-backend-verified/bin/python flutter test --no-pub test/business_company_events_independent_review_test.dart test/business_company_event_contract_test.dart test/business_company_events_test.dart test/business_company_events_http_test.dart --reporter expanded
flutter analyze --no-pub test/business_company_events_independent_review_test.dart
```

Alle verwendeten Unternehmen, Projekte, Personen, Aufträge und Nachrichten sind synthetische lokale Testdaten. Der HTTP-Ablauf erzeugt keine produktiven Kontakte oder Zahlungen. Dieser Review bestätigt den beschriebenen Clientumfang und behauptet weder vollständige ERP-Abdeckung noch eine allgemeine Produktionsfreigabe.
