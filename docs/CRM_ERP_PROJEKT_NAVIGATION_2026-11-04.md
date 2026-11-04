# Projektregister und Rücknavigation – 04.11.2026

Die native Projektmappe wurde auf Basis `c875ea5` korrigiert. Löhne und
Buchhaltung werden entsprechend der neuen Nutzerpriorität zurückgestellt.
Diese Änderung betrifft den Projektzugang und schützt vorhandene Planentwürfe.

## Behobene Fehler

- Beim Öffnen von Arbeitszeit oder einem anderen Fachregister griffen die
  gleichzeitig aufgebauten Grundlisten mit dem Fachregisterindex auf nur sieben
  Grundregister zu. Ein tatsächlicher Widgetlauf gegen die unveränderte
  Projektdatei reproduziert `RangeError`, Index 9 bei zulässigem Bereich 0–6.
  Die Grundlisten erhalten ihren Titel nun aus ihrer eigenen Art.
- Auswahl und bereits geöffnete Fachregister bleiben an ihre Identität gebunden.
  Änderungen an Rechten oder verfügbaren Modulen verschieben eine geöffnete
  Arbeitszeitseite nicht in einen anderen Bereich. Entfernte Register werden
  geschlossen; alte Auswahlcallbacks prüfen die noch vorhandene Identität.
  Alle sieben Grund- und vierzehn aktuellen Fachregister bleiben berücksichtigt.
- Ein ungesicherter Plan schützt jetzt auch die äußere Projektroute, einschließlich
  eines im Hintergrund geöffneten Plans. Laufende lokale Schreibvorgänge und
  Serverantworten müssen abgewartet werden; Verwerfen verlangt eine frische
  Bestätigung. Der Rücksprung nach Planimport darf den Editor nicht umgehen.
- Die weitere Verwaltung besitzt einen sichtbaren Rückpfeil „Zum Arbeitsbereich“.
  Er schließt ausschließlich seine aktuelle Verwaltungsroute; ein verspäteter
  Callback kann keine später geöffnete Route schließen.

Die Korrektur übernimmt einzeln geprüfte Plan-/Registeransätze aus dem noch
separaten [PR 8](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/pull/8)
und ergänzt sie für den aktuellen Stand mit Zusatzfeldern, Kundenservice,
Assistent und Kundenportal. Der Verwaltungsrückweg wurde anhand des PR-7-
Basisbefunds neu mit einer Prüfung der eigenen Route umgesetzt. Andere PR-
Änderungen, Versionen und Releasekonfigurationen wurden nicht übernommen.

## Prüfung

- **20/20 neue Navigationsfälle bestanden**: sämtliche 21 Projektregister mit
  tatsächlichen Fachwidgets bei 1200 und 390 Pixeln; Hin- und Rückweg;
  entfernte/wiederkehrende Module; Rechteänderungen; verspätete Auswahl;
  Arbeitszeitaktionen; ungespeicherte, speichernde und lokal fehlgeschlagene
  Planänderungen; Import-Rücksprung; Verwaltungsrückkehr und alte Callbacks.
- **22/22 bestehende Fälle bestanden**: Planbearbeitung, Offline-Pläne,
  Projektmappe, Workspace und Login/Rollen.
- **Vollständige Flutter-Analyse ohne Befund.**
- Hashes der 13 vor dem Schlusslauf erfassten Quellen sind danach unverändert.

Der Rotnachweis und sämtliche Zwischenläufe bleiben im
[Prüfverzeichnis](evidence/project-navigation-2026-11-04/manifest.json).
Die ersten neuen Testläufe enthielten noch alte synthetische Projekt-IDs,
unpassende Widgetfinder und fehlende Appschriften; dies wurde in den Fixtures
korrigiert. Eine konstante Testmap mit überschriebenem Schlüssel löste einen
Dart-Laufzeitassert aus und wurde durch eine explizite Map ersetzt. Der mobile
48-Pixel-Überlauf lag bereits am Testlogin mit Ersatzschrift Ahem; mit der
mitgelieferten Inter-Schrift besteht der tatsächliche Navigationslauf.
Pub-/Compiler-/PDFium-Cache-/Loopback-Probleme sind gesonderte Umgebungslogs,
keine Produktbefunde. Geprüft wurde mit vorhandenem PDFium-Cache, ohne neue
Netzwerkdownloads, mit erlaubten lokalen Testsockets.

## Grenzen

Die Läufe verwenden Linux-Flutterwidgets und synthetische API-Antworten.
Offline-Planfälle verwenden die echte OfflinePlans-Transaktion mit kontrollierter
Geräteschreibgrenze. Sie sind kein Nachweis für einen aktuellen Windows-Build,
eine iPhone-Installation, produktiven Serverbetrieb oder die Gesamtfertigstellung.
Es wurden keine Bestandsdaten migriert, keine Dateien des Nutzers verworfen und
keine Releases gebaut, veröffentlicht oder bereitgestellt. Der Stand liegt bis
zur Gesamtintegration im separaten Worktree.
