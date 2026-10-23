# Smartplan Office – Aufmaß, Planerfassung und Geräteplatzierung

Stand: 23. Oktober 2026. Diese Spezifikation beschreibt den gewünschten Ausbau.
Aufnahme, KI-Auswertung, Planeditor und CAD-Export sind noch nicht implementiert.
Die vorhandenen Projekte, Berichte und Ablageanschlüsse bilden die Grundlage.

## Auftrag und Arbeitsweise

Der Nutzer möchte unterwegs frei sprechen, Fotos und kurze Videos ergänzen und
daraus eine prüfbare Aufmaß-Zusammenfassung sowie einen bearbeitbaren Plan erhalten.
Handskizzen, vorhandene Pläne und verfügbare Karten-/Luftbilder sollen als Quellen
einbezogen werden. Ein gefilmter Raumbegang soll die Planerfassung unterstützen.
Meist liegen keine Maße vor; eine bekannte Maßreferenz kann bei Bedarf ergänzt werden.
DWG, DXF oder PDF sind dem Nutzer als Zielformat grundsätzlich recht; vorgesehen
sind zunächst ein bearbeitbarer DXF-Plan und ein PDF aus demselben Planstand.
Routinearbeiten dürfen automatisch erfolgen, wichtige Änderungen brauchen Freigabe.
Genanntes Testgerät ist ein iPhone 17; eine Pro-Ausführung wurde nicht angegeben.
Die grundlegende Erfassung setzt deshalb weder LiDAR noch RoomPlan voraus.

Aufmaß ist ein eigenes Erfassungsergebnis mit Originalaufnahme, Transkript, Maßen,
Beobachtungen und gegebenenfalls geprüften Mengen. Es wird nicht in einen
Servicebericht umbenannt; eine spätere Übernahme in Berichte ist eine eigene Aktion.

## Ablauf auf dem iPhone

1. Im Projekt „Aufmaß“ öffnen, Raum auswählen oder einen neuen Raum benennen.
2. Aufnahme starten und Tätigkeiten, Maße und Beobachtungen in Fließtext sprechen.
3. Fotos oder einen kurzen Raumbegang ergänzen; Aufnahmen bleiben dem Raum zugeordnet.
4. Die Verarbeitung zeigt ihren Fortschritt und erstellt eine Zusammenfassung.
5. Maße, Beobachtungen und offene Fragen einzeln prüfen; ein Eintrag öffnet seine Quelle.
6. Angaben berichtigen und die geprüfte Zusammenfassung als Aufmaßstand übernehmen.

Die Originalaufnahme bleibt neben Transkript und Zusammenfassung erhalten.
Unverständliche Zahlen, Einheiten oder Raumzuordnungen werden als offen angezeigt.
Eine KI ergänzt keine fehlenden Maße durch scheinbar gemessene Werte.
Eine Unterbrechung darf bestätigte Eingaben nicht verlieren; Uploads brauchen einen
sichtbaren Wiederholungsstatus. KI-Verarbeitung beginnt erst nach erfolgreichem Upload.

## Quellen zum Plan übernehmen

- **Handskizze:** fotografieren, Ausschnitt und Perspektive prüfen, erkannte Wände,
  Räume und Öffnungen als Vorschlag anzeigen. Die ursprüngliche Skizze bleibt sichtbar.
- **Vorhandener Plan:** Datei importieren und Einheit, Orientierung sowie Planstand
  prüfen. Vektorinformationen können übernommen werden; Bild-PDFs benötigen Erkennung.
- **Normaler Raumbegang:** Video liefert Beobachtungen, Bildausschnitte und mögliche
  Raumzusammenhänge. Es garantiert keinen vollständigen, maßhaltigen Grundriss.
- **RoomPlan:** optionaler geführter Live-Scan auf einem unterstützten LiDAR-iPhone
  ab iOS 16. OS-Verfügbarkeit und `isSupported` werden zur Laufzeit geprüft;
  für das genannte iPhone 17 wird die Unterstützung nicht vorausgesetzt.
  Ein gewöhnliches vorhandenes Video wird dadurch nicht nachträglich zum RoomPlan-Scan.
- **Karten/Luftbilder:** berechtigt bereitgestellte Bilder oder Exporte können Lage,
  Gebäudeumriss und Außenbezüge liefern. Daraus werden keine Innenwände abgeleitet.

Für jede Quelle werden Herkunft, Projekt, Raum und gegebenenfalls Videoposition
gespeichert. Importierte Originale bleiben erhalten; Korrekturen betreffen eine
abgeleitete Planfassung. Anbieterzugang oder Nutzungsrechte werden beim konkreten
Kartenimport geklärt; ein automatischer Google-Maps-Import ist damit nicht zugesagt.

## Maße und Planprüfung

Ohne Maße beginnt der Plan als Entwurf mit unbestimmtem Maßstab. Er bleibt zum
Ordnen von Räumen, Geräten und Notizen nutzbar. Die App behauptet keine realen Längen.
Der Nutzer kann eine bekannte Strecke im Bild oder Plan markieren und ihr Maß angeben.
Eine einzelne Referenz skaliert den Entwurf näherungsweise; sie beseitigt weder
Ungenauigkeiten einer freien Handskizze noch perspektivische oder räumliche Fehler.
Für verlässliche Abmessungen werden die maßgeblichen Wandlängen und Zusammenhänge
zusätzlich geprüft. Widersprüchliche Angaben werden vor der Übernahme aufgelöst.

Die Prüfansicht zeigt offene Maße, vermutete Öffnungen und unklare Wandverbindungen.
Maße tragen eine Herkunft: eingegeben, aus Quelle erkannt oder vom Scan geschätzt.
Der Prüfstatus wird pro Angabe geführt; eine bestätigte Referenz bestätigt nicht
automatisch sämtliche anderen Maße. Flächen und Mengen bleiben entsprechend vorläufig.
Einheiten werden ausdrücklich erfasst und geprüft. Aus „vier zwanzig“ entsteht
ohne eindeutigen Zusammenhang keine automatische Umrechnung in 4,20 Meter.

## Auf dem Plan arbeiten und sprechen

Die App zeigt die ausgewählte Wand deutlich an. Danach kann der Nutzer sprechen:
„Hier zwei Steckdosen“ oder „Hier eine Zweifachsteckdose, 30 Zentimeter über Boden“.
Die Erkennung erzeugt echte Geräteobjekte an der ausgewählten Wand, keine bloße
Textmarkierung im Foto. Anzahl, Kombination und Montagehöhe werden getrennt geführt.
Eine bekannte Projektvorgabe kann eine Routineanordnung bestimmen; sonst bleiben
fehlende Angaben offen oder die App stellt eine konkrete Rückfrage.

Der erkannte Auftrag erscheint kurz mit den gesetzten Symbolen und „Rückgängig“.
Eine direkte, eindeutige Geräteplatzierung wird sofort in der Arbeitsfassung gespeichert.
„Hier zwei Steckdosen hin“ legt Geräte mit Status „geplant“ an. Erfasster Bestand
hat einen eigenen Status und Prüfstand. Aus Fotos erkannte Geräte bleiben Vorschläge;
Planung und automatische Erkennung ergeben keine bestätigten oder abrechenbaren Mengen.
Notizen und zugehörige Sprachstellen bleiben mit Raum, Wand und Position verbunden.
Wird eine Wand später verändert, muss ihre Gerätezuordnung erneut geprüft werden.
Ein unsicherer Bezug wird angezeigt, statt das Gerät still auf eine andere Wand zu setzen.

## Windows, Freigaben und Export

Unter Windows stehen derselbe Planstand, eine größere Zeichenfläche, Maß- und
Gerätelisten sowie die Quellen nebeneinander bereit. Korrekturen sind auf beiden
Geräten nachvollziehbar. Freigaben erzeugen einen benannten, versionierten Planstand.
Maßänderungen, Verschieben/Löschen bestätigter Wände und Änderungen freigegebener
Planstände werden zunächst als Vorschlag mit Vorher-/Nachher-Ansicht vorgelegt.
Der Assistent darf Routineentwürfe vorbereiten und ergänzen; seine Befugnisse und
Projektzugriffe stammen aus dem freigegebenen Assistentenauftrag.

DXF enthält getrennt bearbeitbare Wände, Öffnungen, Geräte und Beschriftungen.
Ein Rasterbild als Hintergrund ersetzt diese Planobjekte nicht. PDF und DXF
entstehen aus derselben Version, mit passender Legende und erkennbarem Prüfstatus.
Bei bestätigter Skalierung sind Zeichnungseinheiten ausdrücklich Millimeter.
Ein unskalierter Export bleibt einheitenlos und als nicht maßstäblich gekennzeichnet;
aus Bildkoordinaten werden keine scheinbar gültigen Millimetermaße erzeugt.
DWG kann später über einen geprüften Konverter hinzukommen. Ein kostenpflichtiger
Konverter oder eine bestimmte CAD-Kompatibilität wird vor Prüfung nicht zugesagt.

## Vertrag für Daten und Verarbeitung

- Jedes Projekt, jeder Raum, jede Wand, Öffnung, Geräteposition und Quelle besitzt
  eine stabile ID. Ein Planstand nennt seine Vorgängerversion und seinen Prüfstatus.
- Geometrie vor Skalierung verwendet ein ausdrücklich benanntes Bild-/Entwurfs-
  Koordinatensystem. Metrische Geometrie führt Längen in Millimetern und speichert
  die Transformation zur Quelle; unbekannte Maße bleiben unbekannt.
- Geräte referenzieren Raum, Wand und Position entlang der Wand; Montagehöhe ist
  ein eigenes optionales Maß. Gerätestatus und Prüfstatus werden getrennt geführt.
  Notizen referenzieren Objekt und Quelle unabhängig vom Zoom.
- Aufnahmen enthalten Originaldatei, Aufnahmedatum, Raumbezug und bei Video/Audio
  Zeitmarken. Transkript, Vorschläge und manuelle Korrekturen bleiben unterscheidbar.
- Verarbeitungsaufträge besitzen Status und eine eindeutige Auftrags-ID. Wiederholung
  nach Verbindungsabbruch darf weder Geräte noch Planstände doppelt anlegen.
- Jeder Änderungsauftrag bezieht sich auf eine konkrete Ausgangsversion. Bei
  zwischenzeitlichen Änderungen wird der Vorschlag erneut abgeglichen und geprüft.
- Beim derzeitigen Betriebsmodell liegen Projekt-/Planstände und Quellmedien auf
  dem Hetzner-System. Die Ablageadapter aus Version 0.6 bilden die Grundlage für
  optionale zusätzliche Plan-PDFs; dafür ist die Dokumentanbindung noch zu erweitern.
- Medien und Plandaten gehen nur an den gewählten, freigegebenen KI-Anschluss und
  innerhalb der Projektberechtigung. Importierte Inhalte erteilen keine Werkzeugrechte.

Vorgesehene KI-Anschlüsse sind unter anderem OpenAI, Claude, Grok, vorhandene
Grok-Bots und eigene Assistenten. Welches Produkt mit „ChatGPT Work“ gemeint ist
und welche API-Anbindung dafür verfügbar ist, ist noch offen; ebenso die genaue
Rolle von Codex. Verfügbarkeit und Berechtigungen werden je Anschluss nachgewiesen.

## Erste durchgehende Abnahme

1. **Aufmaß:** Gesprochener Raumtext, Foto und Video erscheinen korrekt zugeordnet.
   Eindeutige Maße stimmen; eine unklare Zahl wird zur Prüfung gestellt. Einträge
   öffnen die betreffende Quelle; ein Upload-Neustart verliert keine bestätigten Daten.
2. **Skizze zum CAD-Plan:** Ein mit 4,20 × 3,30 Metern bestätigter Rechteckraum misst
   im DXF 4.200 × 3.300 Millimeter. Wände und Geräte sind einzeln bearbeitbar;
   PDF und DXF zeigen dieselbe Version. Ohne Referenz bleibt der Maßstab offen.
3. **Raumbegang und Quellen:** Ein normales Video führt zu einem prüfbaren Entwurf
   mit Quellenstellen und offenen Angaben. Ein optionaler RoomPlan-Scan wird nur
   auf tatsächlich unterstütztem Gerät angeboten. Ein Luftbild erzeugt keine Innenräume.
4. **Wandbefehl und Freigabe:** Eine Zweifachsteckdose mit Höhe und Notiz erscheint
   als „geplant“ an der gewählten Wand auf iPhone und Windows, ohne den bestätigten
   Bestand zu erhöhen. Ein wiederholter Auftrag erzeugt kein Duplikat. Die Änderung
   einer bestätigten Wand wartet auf Freigabe.
