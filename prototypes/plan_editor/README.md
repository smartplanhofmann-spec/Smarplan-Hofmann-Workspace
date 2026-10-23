# Lokaler Planeditor-Prototyp

Erster ausführbarer Baustein für das Planmodul aus
[AUFMASS_UND_PLAENE.md](../../AUFMASS_UND_PLAENE.md). Dieser Prototyp zeigt
Vektorpläne, Wandpositionen, geplante Geräte, Notizen und CAD-Exporte.
Er ist noch kein Bestandteil der nativen Smartplan-App oder der Online-API.
Die Eingabe „hier 2 Steckdosen“ wird durch eine begrenzte lokale Befehlsregel
verarbeitet. Es findet keine KI-, Sprach- oder Bilderkennung statt.

## Lokal starten

Python 3.12 und eine eigene virtuelle Umgebung verwenden:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r prototypes/plan_editor/requirements.txt
.venv/bin/python -m unittest discover -s prototypes/plan_editor -p 'test_*.py' -v
```

Das Modell wird als JSON übergeben. `build_editor.py` erstellt daraus eine
einzelne HTML-Datei, die ohne Internetverbindung im Browser geöffnet werden kann.
`plan_tools.py` erzeugt PDF und DXF aus demselben Modellstand.
Die Python-Funktionen sind auch unabhängig vom HTML-Editor verwendbar.

```sh
.venv/bin/python prototypes/plan_editor/build_editor.py /privat/plan.json /privat/planeditor.html
.venv/bin/python prototypes/plan_editor/plan_tools.py /privat/plan.json --out-dir /privat/export
```

`editor.html` ohne eingebettetes Modell enthält einen synthetischen Übungsplan.
Für echte Projektpläne eine eigene HTML-Datei mit `build_editor.py` erstellen.

## Modell und Bearbeitung

- `schema_version: 1`, stabile Objekt-IDs, `revision`, `status: "draft"`.
- Kartesische Koordinaten mit Y nach oben; Winkel in Grad.
- `walls`: Polylinien mit `points`, getrennt von `fixtures` wie Küchenzeilen.
- `doors`: Drehpunkt `hinge`, Radius und Winkel für Türblatt und Öffnungsbogen.
- `regions`: Raumbezeichnungen und ihre Position; keine daraus erfundenen Flächen.
- `opening_candidates`: ungeklärte Öffnungsmarkierungen aus einer Quelle.
- `devices`: `wall_id` und `along` zwischen 0 und 1 entlang der gesamten
  Wand-Polylinie; `quantity` ist die Anzahl an dieser Position. Ein Symbol mit
  Anzahl 2 wird nicht zusätzlich als zwei weitere Geräte gezählt.
- `notes`, `issues`: örtliche Notizen und offene Prüfpunkte.

Eine Geräteplatzierung im Python-Modul verwendet eine `request_id`. Wiederholung
mit demselben Inhalt erzeugt weder eine neue Revision noch ein zweites Objekt;
abweichender Inhalt mit derselben ID wird zurückgewiesen. Eingabemodelle werden
dabei nicht verändert. Geräte sind geplant; eine Platzierung bestätigt keinen Bestand.

Im Browser eine Wand an der gewünschten Stelle anklicken, dann den unterstützten
Steckdosenbefehl eingeben oder eine Notiz ergänzen. „Rückgängig“ verwirft die letzte
lokale Änderung. „Stand speichern“ lädt den JSON-Stand herunter; „Plan laden“
öffnet ihn später wieder.
Die lokale Datei besitzt keine Projektanmeldung oder Synchronisierung mit Hetzner.

## Maßstab und Export

Ohne zugeordnete Referenz gilt `units: "unitless"`, `source.scale: "unknown"`.
Eine bekannte Länge mit noch offenen Endpunkten kann unter `scale_reference`
stehen, skaliert den Plan aber nicht automatisch.

`calibrate_plan` benötigt zwei ausdrücklich zugeordnete unterschiedliche Punkte
und eine positive Referenzlänge in Millimetern. Koordinaten und Radien werden
gleichmäßig umgerechnet. Die Referenz und die Transformation bleiben erhalten;
andere Wände, Öffnungen und Proportionen werden dadurch nicht bestätigt.
Eine einzelne Strecke korrigiert keine Verzerrungen einer freien Handskizze.

DXF enthält echte Vektorelemente und getrennte Layer für Wände, Türen,
Einrichtung, Geräte, Beschriftungen und offene Stellen. Einheitenlose Pläne setzen
`$INSUNITS=0`, metrische Pläne `$INSUNITS=4` für Millimeter. PDF kennzeichnet
den Entwurfs- und Maßstabsstatus. DWG und der Import beliebiger Fremdpläne sind
noch nicht umgesetzt.

## Datenschutz und nächste Integration

Die Tests verwenden ausschließlich synthetische Modelle. Nutzerfotos, daraus
abgeleitete Geometrie und private Exporte gehören außerhalb des öffentlichen
Repositories. Die HTML-Datei enthält das gesamte eingebettete Planmodell;
wer die Datei erhält, kann es lesen.

Für den produktiven Einbau fehlen unter anderem Planversionen und Projektzugriffe
in der Online-API, die native Bearbeitungsoberfläche, Medienaufnahme/-Upload,
freigegebene KI-Anschlüsse und der zugehörige Auftragsablauf. Diese Funktionen
werden nicht durch den lokalen Prototyp ersetzt.
