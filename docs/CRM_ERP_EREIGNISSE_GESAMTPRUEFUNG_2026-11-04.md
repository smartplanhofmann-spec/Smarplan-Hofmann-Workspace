# Gemeinsame Ereignisintegration – 04.11.2026

Basis ist `b0b96024f0a7cf2c7097fb3b77c64032265850a5`, einschließlich
Source5, Anfangssalden, historischer linearer Anlagen und datierter Katalogpreise.
Die gemeinsame Abnahme ist im isolierten Arbeitsbaum abgeschlossen:
`/workspace/smartplan-company-events-integration-20261104`.

## Umfang und Erhalt

Der final eingefrorene Ownerhandoff umfasst 116 Dateien auf Basis `4c2f008`.
Acht bereits integrierte Kostenfixdateien waren identisch. Die gemeinsamen
Registrierungen, Client-Sessions und Dialoge wurden additiv zusammengeführt.
Finanzhorizont13 und Wiederherstellungsbericht14 bleiben unverändert.
Der [unabhängige Merge-Review](CRM_ERP_UNTERNEHMENSEREIGNISSE_MERGE_GEGENPRUEFUNG_2026-11-04.md)
prüft alle 116 Ownerpfade und die drei ausdrücklich nachträglich korrigierten
Runtimepfade; kein bestätigter Befund bleibt offen.
Die Quellpaketlisten enthalten übereinstimmend 134 Backend- und 150 Betreiberpfade.

Die neuen Regeln verwenden tatsächliche Aufgaben, Rechnungen, Kostenstände,
Anfragen, finale Dokumente und freigegebene Mahnungen. Automatik, konkrete
Freigabe und Verbot respektieren bestehende Projektregeln und aktuelle Rechte.
Eine gestartete Aktion wird nach Antwortverlust oder Restore nicht doppelt
begonnen. Unbestätigte externe Wirkung wird nicht als Erfolg ausgegeben.
Der bestehende Instanzguard gilt auch für den begrenzten CLI-Einstieg.

## Konkrete gemeinsame Preisgrenze

Ein tatsächlicher V2-Katalogartikel ohne ausdrückliche datierte Preiswahl
lieferte zunächst einen vorbereiteten ausführbaren Plan. Die Dokumentdomäne
verhinderte zwar bereits den falschen Angebotsentwurf, die Vorbereitung war
jedoch irreführend. Der erhaltene Rotbeleg zeigt diesen Gegenfall.
`company_event_sources.action_context` verwendet jetzt zusätzlich die kanonische
Dokumentpositionsprüfung mit `persist=False`. Die Vorbereitung enthält409,
keine Aktionsparameter und `can_execute=false`; kein Dokument, Ausführungsclaim
oder Versand entsteht. Ein normaler unverändert bepreister Artikel erzeugt
weiterhin genau einen richtigen Entwurf. Beide echten Gegenfälle bestehen.
Die Vorlage erfindet weder ein Preisdatum noch einen Ersatzpreis.

## Zusätzliche unabhängige Browserbefunde

Die unabhängige gemeinsame Prüfung reproduzierte zwei konkrete weitere Fehler:
Eine gehaltene erste Ereignisabfrage öffnete nach Hintergrundwechsel einen
privaten Dialog, weil noch kein bestehendes Modal geschlossen werden konnte.
Der Visibilityhandler invalidiert jetzt auch dann den Ereigniskontext; offene
Originalaufträge werden nicht gelöscht. Außerdem akzeptierte der Browserreader
`status=succeeded` bei unverändertem Ausführungsclaim und fehlendem Ergebnis
und zeigte fälschlich Erfolg. Er verlangt jetzt dieselbe bestätigte
Erfolgsquittung wie der native Reader. Historische veraltete oder nach Restore
gesperrte Pläne mit früherem Erfolg bleiben lesbar. Originale Rotbelege und
unveränderte Gegenprüfungen werden im unabhängigen Merge-Nachweis erhalten.

## Prüfungen

| Prüfung | Tatsächliches Ergebnis | Dauer |
| --- | --- | --- |
| Backend vollständig | 1.779 ausgeführt, 1.778 bestanden, 1 Windows-Skip unter Linux | 812,590 s |
| Flutter vollständig | 1.386 bestanden | 517,579 s |
| Flutteranalyse | Kein Befund | 9,891 s |
| Node vollständig, nach Browserreview | 647 bestanden | 7,393 s |
| Gezielte Domain-/HTTP-/Workerprüfung | 64 bestanden, Überlappung mit Gesamtlauf | 20,369 s |
| Quellpakete | 16 bestanden; kein Windows-Binärbuild behauptet | 13,030 s |
| Tatsächliches PostgreSQL | Vier Fälle bestanden | 64,387 s |

Die PostgreSQLprüfung umfasst parallele Ausführung, geschützte Laufzeitrollen,
Ereignisrestore und zusätzlich einen gemeinsamen gefüllten Restore mit
Source5-Lohnlauf, V1-/V2-Katalogoriginalen, datiertem Angebot, Anfangssaldo,
historischer Anlage, EÜR-Export und Ereignisfreigaben. Historische Bytes und
Quittungen bleiben erhalten, offene Ereignispläne bleiben nach Restore gesperrt.
Der Testdienst hat nach Abschluss keine weiteren Verbindungen oder Restoreziele.

Echte Chromium-/MFA-/HTTP-Abläufe bestehen für Unternehmensereignisse
(21,206 s nach den letzten Korrekturen), bisherigen Assistenten (43,748 s),
datierte Katalogpreise (23,868 s), Source5 einschließlich eigener geschützter
Mitarbeiterbelege (55,434 s) und historische Anlagen (31,540 s). Die unabhängige
Prüfung verspäteter Dialogantworten besteht zusätzlich; nach dem letzten Fix
bestehen alle vier tatsächlichen Hintergrund-/Rückkehr-/Erfolg-/Fehlervarianten.
Die Sandbox blieb in allen Chromiumläufen aktiviert.
Die letzten zwei Browserkorrekturen wurden nach dem ursprünglichen 645er-Node-
Lauf durch 647 Fälle, den erneuten tatsächlichen Ereignisflow und unabhängige
Gegenläufe geprüft. Frühere Logs bleiben erhalten. Testgruppen überlappen.

Der maschinenlesbare [Gesamtnachweis](evidence/events-integrated-regression-2026-11-04.json)
bindet die Befehle, tatsächlichen Ergebnisse, Logs und endgültigen Quelldateien.
Die einzige während eines vollständigen Laufs geänderte erfasste Datei war
die unten beschriebene zusätzliche, von Flutter nicht verwendete PG-Fixture.
Die vollständige App-/Backendruntime blieb unverändert; die endgültige PG-Fixture
ist durch den tatsächlichen erfolgreichen gemeinsamen Restore separat geprüft.

## Erhaltene fehlgeschlagene Erstläufe

- Der neue Preisgegenfall war vor der Produktkorrektur tatsächlich rot.
- Die zusätzliche gemeinsame PG-Fixture ließ zuerst die erforderliche echte
  Instanzbindung aus; der Regelaufruf wurde korrekt mit409 gesperrt. Die
  Fixture verwendet jetzt dieselbe ausdrückliche Bindung wie die vorhandenen
  Ereignistests und die bestehende `decide`-API. Alle vier Fälle bestehen
  danach. Originaltesttext, Erstlog und Vorher-/Nachherhash sind archiviert.
  Diese einzelne reine Online-PG-Testdatei wurde während der Flutterprüfung
  korrigiert; sie wird von keinem Fluttertest importiert. Produktdateien
  änderten sich während der vollständigen Prüfungen nicht.
- Ein falsch benannter Browserworkflow wurde vor Start zurückgewiesen.
  Der registrierte Source5-Workflow bestand anschließend; kein
  Anwendungserfolg wird aus dem abgewiesenen Aufruf abgeleitet.

## Weiter offener Zielumfang

Die Ereignisintegration ersetzt keine vollständige Software-/Fachabnahme.
Historische offene Posten sind separat umgesetzt und werden als nächstes
integriert. Unterjährige Jahresvorträge, ein ergänzendes Original-/Journalpaket,
weitere Lohn-/Steuerkorrekturen und die vollständigen Abnahmen A–G bleiben
Arbeit. Keine Produktivmigration, echte Nachricht, Zahlung, Behördenmeldung,
Veröffentlichung oder Remoteübertragung wurde vorgenommen.
