# Lokaler Foto-/PDF-Importkern

Ausführbarer Linux-CLI-Pilot für den vereinbarten
[Planimport auf Hetzner](../../PLANIMPORT_UND_DIGITALISIERUNG.md). JPEG, PNG und
eine ausgewählte PDF-Seite ergeben ein unverändertes Original mit SHA-256,
eine aufrechte Vorschau, lokale Linien-/Drucktextkandidaten und eine eigenständig
offline öffnende HTML-Prüfansicht. Ergebnisse haben immer `needs_review`.

Dieser Kern ist noch nicht mit Kamera, nativer App, Offline-Medienspeicher,
Uploadrouten, Office-Datenbank oder einem produktiven Hetzner-Dienst verbunden.
Er ändert weder die produktive Version 0.7 noch deren Datenbankschema. Wände,
Türen, Räume, Handschrift und durchgestrichene Maße werden nicht semantisch
erkannt. Perspektivkorrektur und Maßkalibrierung sind noch offen. HEIC, DXF,
DWG, animierte Bilder und verschlüsselte PDFs werden ausdrücklich abgewiesen.

## Lokal entwickeln und ausprobieren

Voraussetzung: Linux, Python 3.12, eine eigene Venv und lokal installiertes
Tesseract mit `eng`. Die Entwicklungsumgebung wurde mit Tesseract 5.5 geprüft;
der Testcontainer verwendet die Debian-Pakete. Die Befehle gelten ab Repository-
Wurzel und sind keine Installationsanweisung für den produktiven Server.

```bash
python3 -m venv /tmp/smartplan-import-venv
/tmp/smartplan-import-venv/bin/python -m pip install --only-binary=:all: -r backend/plan_import/requirements-test.lock
export PYTHONPATH=backend
/tmp/smartplan-import-venv/bin/python -m plan_import doctor

/tmp/smartplan-import-venv/bin/python examples/plan_import/generate_samples.py --output /tmp/smartplan-musterplaene
/tmp/smartplan-import-venv/bin/python -m plan_import --store /tmp/smartplan-import-demo run /tmp/smartplan-musterplaene/hausplan-foto.jpg --request-id muster-foto-1
/tmp/smartplan-import-venv/bin/python -m plan_import --store /tmp/smartplan-import-demo run /tmp/smartplan-musterplaene/hausplan.pdf --page 2 --request-id muster-scan-1
```

Der Generator erzeugt ausschließlich synthetische Pläne. JPEG/PNG zeigen denselben
Grundriss mit roten Strichen und Pfeilen; PDF-Seite 1 enthält Vektoren und echten
PDF-Text, Seite 2 einen Bildscan. Vorhandene Dateien werden nicht überschrieben.
Die Beispiele belegen keine Qualität bei realen Handyfotos oder Handschrift.

Die CLI liefert JSON mit `job_id`, Status, Quellhash und bei erfolgreicher
Verarbeitung `review_path`, `preview_path` und `result_path`. `review.html` direkt
im Browser öffnen: Linien-/Textschicht einblenden, zoomen und Textstellen anklicken.
Die Ansicht enthält alle Ressourcen selbst und lädt nichts aus dem Netz.

Für getrennte Erfassung und Verarbeitung:

```bash
python -m plan_import --store /tmp/smartplan-import-demo submit /tmp/smartplan-musterplaene/hausplan.pdf --page 1 --request-id muster-pdf-1
python -m plan_import --store /tmp/smartplan-import-demo work --watch
python -m plan_import --store /tmp/smartplan-import-demo status JOB_ID
```

Dabei `python` aus der Import-Venv verwenden und `JOB_ID` durch die gelieferte ID
ersetzen. `--store` steht vor dem Unterbefehl. Der Elternordner muss vorhanden
sein; ein neuer Store wird privat mit Modus `0700` angelegt. Einen vorhandenen
Store mit anderen Rechten weist die CLI ab. PDF-Seiten zählen in der CLI ab 1,
in gespeicherten Daten ab 0. Fotos besitzen nur die erste Seite.

`doctor` legt keinen Store an. `--ocr-languages deu+eng` ist bei `run` und `work`
möglich, sobald die Sprachdaten lokal installiert sind. Fehlende Sprachen werden
ausdrücklich im Ergebnis gemeldet; gegebenenfalls wird `eng` als Ersatz gemeldet.
Ohne nutzbare Sprache schlägt die Verarbeitung fehl. Deutschqualität und der
optionale Container-Build `SMARTPLAN_OCR_DEU=1` sind noch nicht abgenommen.

## Dauerhafte Quellen und Aufträge

Der Pilot verwendet einen eigenen lokalen Store, getrennt von Office:

| Bestandteil | Inhalt |
| --- | --- |
| `originals/` | Unveränderte Quellbytes, private unveränderliche Dateien und SHA-256-Prüfung. |
| `imports.sqlite3` | Quellen, Aufträge, Seitenwahl, Versuche, Leases und Ergebnismanifeste; WAL und `synchronous=FULL`. |
| `derived/` | PNG-Vorschau und eigenständige HTML-Prüfansicht je abgeschlossenem Versuch. |
| `recognition/` | Begrenztes JSON mit Herkunft, Transformation, Kandidaten und Warnungen. |

`submit` bestätigt erst nach dauerhafter Quellenablage und Metadaten-Commit.
Dieselbe `request-id` mit denselben Bytes und derselben Seite liefert denselben
Auftrag; eine andere Eingabe unter derselben ID wird abgewiesen. Ohne explizite
ID entsteht bei jedem Aufruf ein neuer Auftrag. Es gibt keine globale
Duplikatbereinigung oder automatische Löschung von Originalen.

Ein Worker beansprucht den Auftrag mit einer 90-Sekunden-Lease. Die Verarbeitung
läuft außerhalb der SQLite-Transaktion in einem eigenen Prozess. Nur ein noch
berechtigter Versuch darf sein dauerhaft abgelegtes Ergebnis veröffentlichen;
verspätete Versuche können neuere Ergebnisse nicht überschreiben.
Nach einem Abbruch bleibt ein Auftrag bis zum Lease-Ablauf `running` und kann
danach erneut beansprucht werden. Nach drei abgebrochenen Versuchen wird er
`failed`. Auch ein regulärer Parserfehler beendet den Auftrag mit `failed` und
erhält das Original. Ein bewusster neuer Versuch benötigt eine neue Anfrage-ID.

Verzeichnisse und Dateien sind privat; Symlinks, Pfadwechsel, Fremddatenbanken
und veränderte Quellen werden abgewiesen. Fehlende Store-Metadaten werden nicht
still durch eine neue leere Datenbank ersetzt. Unterbrochene Veröffentlichungen
können unreferenzierte Dateien hinterlassen; sie werden nicht automatisch gelöscht.

Dieser Entwicklungsstore verschlüsselt die Dateien nicht selbst und hat keinen
Sicherungs-/Wiederherstellungsvertrag mit Office. Vor einer Serverintegration
sind Rechte, Speicherbegrenzung sowie gemeinsame Sicherung und Wiederherstellung
von Metadaten und Dateien zu implementieren und zu prüfen. Die geplanten
verschlüsselten Offline-Dateien auf Handy/iPad sind eine separate nächste Aufgabe.

## Ergebnis und Grenzen

PDFium rendert nur die gewählte statische Seite einschließlich vorhandener
Anmerkungen; Formularfunktionen, JavaScript, Links und Anhänge werden nicht
ausgeführt oder abgerufen. Eingebetteter PDF-Text bleibt von Tesseract-OCR
unterscheidbar. Ein Scan liefert keinen erfundenen eingebetteten Text.
JPEG-/PNG-Vorschauen berücksichtigen EXIF-Ausrichtung und übernehmen keine
EXIF-/GPS-Metadaten; das unveränderte Original behält seine ursprünglichen Daten.

OpenCV liefert Linienkandidaten, Tesseract Kandidaten für Drucktext. Auch ein
roter Pfeil kann als Linie und ein Kritzel als Text erscheinen. Kandidaten sind
keine bestätigten Wände, gültigen Maße oder verstandenen Handnotizen. Die
Tesseract-Konfidenz ist ein Wortscore, keine kalibrierte Wahrscheinlichkeit.

Koordinaten der Kandidaten liegen normiert zwischen 0 und 1, Ursprung links
oben in der aufrechten Vorschau. `source_to_preview` beschreibt die affine
Abbildung `x'=a*x+b*y+c`, `y'=d*x+e*y+f` aus Originalpixeln beziehungsweise
PDF-Punkten. PDF-CropBox und Drehung bleiben nachvollziehbar. Kalibrierung ist
`unknown`, Einheit `unitless`; PDF-Seitenpunkte sind keine Gebäudemaße.

| Grenze | Wert |
| --- | --- |
| Original | 1 Byte bis 20 MiB; Inhaltssignatur entscheidet über das Format. |
| Bild / PDF | Bis 40 Mio. Quell-/eingebettete Rasterpixel; bis 50 PDF-Seiten. |
| Vorschau | Lange Kante höchstens 2200 Pixel. |
| Erkennung | Interne Linienanalyse höchstens 2048 Pixel; je höchstens 2000 Linien-/OCR-Kandidaten. |
| Ergebnis | JSON höchstens 1 MiB; abgeleitete Dateien zusammen höchstens 40 MiB. |
| Parserprozess | 55 Sekunden Wandzeit, 40/45 Sekunden CPU, 1 GiB virtueller Adressraum, 32 MiB pro geschriebener Datei. |
| OCR | Begrenzte Laufzeit und Ausgaben; standardmäßig 15 Sekunden pro Aufruf. |

Der Controller beendet bei Timeout, normalem Ende, Strg+C und SIGTERM die eigene
Worker-Prozessgruppe einschließlich OCR-Nachfahren. Ein SIGKILL des Controllers
ist dadurch nicht abgesichert; die Lease erlaubt spätere Wiederaufnahme. Diese
Prozesslimits sind kein vollständiger Sicherheitscontainer. Ein produktiver
Worker benötigt eine eigene eingeschränkte Laufzeit ohne Netzwerk und Zugriff
auf Office-Geheimnisse. Es gibt keinen externen OCR-/KI-Dienst oder automatischen
externen Ersatzdienst.

## Prüfung und Abhängigkeiten

```bash
PYTHONPATH=backend /tmp/smartplan-import-venv/bin/python -m unittest discover -s backend/plan_import/tests -v
bash backend/plan_import/test-docker.sh
```

67 Tests prüfen echte JPEG-/PNG-/PDF-Verarbeitung, Drucktext-OCR,
Seiten-/Drehungskoordinaten, Limits, Hash-/Dateischutz, Idempotenz, Lease-Verlust,
Prozessabbruch samt OCR-Kindprozess und HTML-Escaping. Der Container baut nur
Werkzeuge aus den separaten Locks und verarbeitet anschließend ausschließlich
synthetische Daten mit `--network none`, schreibgeschütztem Root-/Quell-Dateisystem,
privatem temporärem Speicher und CPU-/RAM-/Prozesslimits. Der Docker-Buildkontext
enthält nur Dockerfile und Locks. Paketbezug beim Build benötigt Internet;
Planverarbeitung im Test benötigt es nicht.

Der eigene [Workflow](../../.github/workflows/plan-import.yml) führt diesen
Containerlauf aus. Die reguläre Backend-Venv und deren Lockdatei bleiben
unverändert; die Worker-Tests werden dort nicht versehentlich mitentdeckt.

Produktive Python-Werkzeuge sind separat versioniert: Pillow 12.3.0
(HPND), NumPy 2.3.5 (BSD), OpenCV headless 4.13.0.92 (Apache/BSD einschließlich
mitgelieferter Drittkomponenten) und pypdfium2 5.14.0 (Apache-2.0/BSD-3-Clause mit
PDFium-Drittkomponenten). Tesseract steht unter Apache-2.0. ReportLab und
charset-normalizer werden nur für synthetische Testdateien benötigt. Die
Lizenzdateien und Drittanbieterhinweise der ausgelieferten Wheels/Systempakete
müssen bei einer späteren Distribution mitgeführt und geprüft werden. PyMuPDF
aus der früheren Machbarkeitsprobe ist keine Abhängigkeit dieses Kerns.

Als Nächstes folgt der native Durchstich: Original auf dem Gerät verschlüsselt
sichern, berechtigt und fortsetzbar auf Hetzner hochladen, Workerauftrag auslösen
und die prüfbare Quelle samt Ergebnis in der App anzeigen. Erst danach lässt
sich die Erkennungsqualität mit realen, direkt auf Hetzner bereitgestellten
Planunterlagen bewerten.
