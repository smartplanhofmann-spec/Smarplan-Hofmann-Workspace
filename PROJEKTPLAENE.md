# Projektpläne – erste Entwicklungsstufe

**Neue Priorität vom 23. Oktober 2026:** Der Nutzer kann den Wandeditor bedienen,
möchte aber vorhandene Pläne importieren und Papierpläne mit Handnotizen
fotografieren. Kamera/Foto und PDF stehen vor DXF/DWG und weiterem manuellen
Zeichenausbau. Digitalisierung ausschließlich auf Hetzner; Originale und
verschlüsselte Offline-Speicherung bleiben erhalten. Die neue Spezifikation
steht in [Planimport und Digitalisierung](PLANIMPORT_UND_DIGITALISIERUNG.md).
Dieser Import ist noch nicht in der App implementiert. Der folgende Abschnitt
beschreibt den bereits vorhandenen Stand 0.7.

Die Projektansicht enthält den Einstieg **Projektpläne** (Grundriss-Symbol).
Ein Plan steht für einen benannten Grundriss, beispielsweise ein Geschoss.
Die erste Stufe kann leere Pläne anlegen, Wände durch Antippen von Start- und
Endpunkt zeichnen, Zeichenschritte rückgängig machen und Pläne speichern/öffnen.
Die neue App speichert Projektpläne zunächst verschlüsselt auf dem Gerät und
synchronisiert sie über eine dauerhafte Warteschlange; siehe
[Offline-Nutzung](OFFLINE_UND_SYNCHRONISIERUNG.md).
Die Zeichenfläche verwendet feste Entwurfskoordinaten, unabhängig von der
Bildschirmgröße. Das Raster ist eine Zeichenhilfe und kein Längenmaß.
Alle Pläne sind ausdrücklich **Entwurf – nicht maßstäblich**.

## Speicherung und Zugriffe

Lokales Backend und Online-API bieten dieselben Operationen:

- `GET /api/projects/{project_id}/plans`: neueste Stände auflisten.
- `POST /api/projects/{project_id}/plans`: `{title, walls}` anlegen.
- `GET /api/projects/{project_id}/plans/{plan_id}`: aktuellen Stand öffnen.
- `POST /api/projects/{project_id}/plans/{plan_id}`:
  `{title, walls, revision}` als Folgestand speichern.

Online verwendet die App wie bisher das Präfix `/api/v1/` und MFA-Sitzungen.
Eine Wand besteht aus einer eindeutigen `id` und zwei kartesischen `points`.
Die Y-Achse zeigt nach oben. Höchstens 2000 Wände, endliche Koordinaten im
Bereich ±10000 und unterschiedliche Endpunkte werden geprüft.
Für zuverlässige Wiederholung nach Verbindungsabbrüchen akzeptieren
Speicheraufrufe zusätzlich eine stabile `request_id`; siehe
[Offline-Vertrag](OFFLINE_UND_SYNCHRONISIERUNG.md).

Ein Plan führt ID, Projekt, Titel, Revision, Entwurfsstatus, Einheit,
Wände, Bearbeitungszeit und Benutzer. Alte Stände bleiben in `plan_versions`
erhalten; eine Oberfläche zum Anzeigen alter Stände folgt später.

Projektzugriff wird für jeden Abruf und jede Speicherung geprüft.
Geschäftsführung, Projektleitung und Technik können im erlaubten Projekt
schreiben; Buchhaltung kann lesen. Bei einer veralteten Ausgangsversion
antwortet der Server mit 409 und überschreibt keinen Stand. Die App behält
den ungespeicherten Entwurf geöffnet. Zum Laden des aktuellen Stands die
Planliste öffnen und „Konflikt klären“ wählen. Die lokale Fassung kann als
zusätzlicher Plan erhalten oder ausdrücklich verworfen werden. Bestätigte
lokale Änderungen überstehen einen App-Neustart. Automatisches Zusammenführen
und eine Oberfläche für die gesamte Versionshistorie folgen später.
Nach einem erfolgreichen Speichern öffnet ein anderes Gerät denselben Stand;
es gibt noch keine automatische Live-Aktualisierung.

## Datenbank und Bereitstellung

SQLite ergänzt beim Öffnen additiv die Tabelle `plan_versions`.
Bestehende Berichte, PDF-Dateien und Kunden werden nicht umgeschrieben.
PostgreSQL benötigt eine **explizite Migration von Schema 1 auf 2** über
`PYTHONPATH=backend python -m online.manage migrate` mit der vorgesehenen
`SMARTPLAN_DATABASE_DSN`. Die Migration legt `plan_versions`, `plan_requests` und `plan_sessions` an und
läuft transaktional und wiederholbar.
Sie wird niemals durch einen API-Aufruf ausgelöst.

**Auf Hetzner bereitgestellt und öffentlich bestätigt:** Der Nutzer führte
das Update des geprüften Quellstands `95fc88c` am 23. Oktober aus. `/ready`
meldet Version `0.7.0-online-pilot`, Schema 2 und Plan-/Offline-Fähigkeiten.
Windows-Start, Anmeldung und Zeichnen wurden anschließend bestätigt; der Nutzer
möchte nun den oben beschriebenen Importablauf. Der neue
[Updateablauf](deploy/hetzner/online/UPDATE_0_7.md) bereitet eine separate,
vollständig rückgesicherte und geprüfte Kandidaten-Datenbank vor. Öffentliche
Schreibzugriffe bleiben bis nach der Prüfung gesperrt. Die bisherige Datenbank
bleibt erhalten. Ab öffentlicher Freigabe gibt es keine automatische Rückkehr,
damit neu angenommene Eingaben nicht verloren gehen. Native Prüfpakete und
Geräteabnahme sind im [Testupdateplan](TESTUPDATE_0_7.md) beschrieben.

## Prüfungen

- `backend/.venv/bin/python -m unittest discover -s backend -v`
- Mit entbehrlicher PostgreSQL-Datenbank `smartplan_check`,
  `PYTHONPATH=backend` und `SMARTPLAN_TEST_DSN`:
  `backend/.venv/bin/python -m unittest discover -s backend/online -p test_plans_online.py -v`
- In `app`: `flutter analyze` und `flutter test`.

Die neuen HTTP-Tests prüfen Speicherung, Wiederöffnen mit neuer
Datenbankverbindung, Zugriffsentzug, Lesezugriff und fehlerhafte Geometrie.
PostgreSQL-Tests prüfen zusätzlich echte konkurrierende Speicherungen aus
zwei Verbindungen und die Migration vorhandener Daten.
Flutter-Analyse und sämtliche 52 App-Tests bestanden, einschließlich Zeichnen,
Rückgängig, Wiederöffnen, Konflikterhalt, Offline-Speicherung und tatsächlicher
Übertragung nach einem simulierten Client-Neustart. Die Cloud-Freigabe für
`storage.googleapis.com` ist wirksam; Flutter/Dart konnten installiert werden.
Native Windows-, iOS-Simulator- und unsignierte iOS-Gerätebuilds des Quellstands
`95fc88c` bestanden in den CI-Läufen `39977162879` und `39977162745`.
Echte iPhone-/iPad-Tests von Schlüsselablage, Geräteentsperrung und Offline-
Synchronisierung dieser Erweiterung stehen weiterhin aus.

Maße, Räume, Türen/Fenster, Gerätesymbole, PDF/DXF-Export, Quellenimport und KI
sind weitere Schritte. Der separate HTML-Prototyp bleibt davon unabhängig;
seine umfangreicheren Modelle können noch nicht in die native Ansicht importiert werden.

Ausgeführt in dieser Entwicklungsumgebung: lokale Backend-Suite mit 39 Fällen
(38 bestanden, ein Windows-Fall übersprungen), vorhandene Online-Suite mit
19 bestandenen Fällen und drei bestandene PostgreSQL-Planfälle. PostgreSQL 16
lief dafür in einem separaten, entbehrlichen Container; Dump/Restore nutzten
die echten PostgreSQL-Werkzeuge dieses Containers. Keine Produktivdaten oder
externen Konten wurden für die Prüfungen verwendet.
