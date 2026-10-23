# Planimport und Digitalisierung auf Hetzner

Nutzerentscheidung vom 23. Oktober 2026: Der freie Wandeditor aus Version 0.7
ist nicht der gewünschte Hauptablauf. Vorrang haben vorhandene Pläne und
abfotografierte Papierpläne, besonders Hausgrundrisse mit handschriftlichen
Ergänzungen. Aus diesen Quellen soll im Hintergrund ein überprüfbarer,
bearbeitbarer Plan entstehen. Das Original muss daneben erhalten bleiben.

Diese Spezifikation beschreibt den nächsten Ausbau. Kamera, Quellenimport und
automatische Digitalisierung sind in der nativen App noch nicht implementiert.

## Verbindlicher Verarbeitungsort

Die letzte Nutzerentscheidung lautet: **„es soll auf dem Hetznerserver bleiben“**.
Sie ersetzt die zuvor kurz erwogene Nutzung externer KI-Dienste.

- Originalfotos, Planunterlagen und daraus abgeleitete Erkennungsdaten werden
  für diese Verarbeitung an keinen externen KI-, OCR- oder CAD-Webdienst gesendet.
- Erkennung, OCR und gegebenenfalls CAD-Konvertierung laufen auf dem eigenen
  Hetzner-System. Es gibt keinen automatischen externen Ausweichdienst.
- Ohne Empfang bleiben neue Originale verschlüsselt auf dem Handy/iPad. Bei
  Verbindung werden sie zum eigenen Server übertragen. Die bereits gewählten
  sieben Tage Offline-Zugriff bleiben bestehen; sie sind keine Löschfrist.
- Neue Kameraaufnahmen werden nicht automatisch in die Systemfotomediathek
  oder einen Cloudspeicher exportiert. Die nativen Sicherungs-/Ausschlussregeln
  für die lokalen App-Dateien sind bei der Geräteabnahme zu prüfen.
- Erforderliche lokale Werkzeuge und Modelle werden vor Einsatz hinsichtlich
  Ressourcenbedarf, Lizenz und unterstützter Eingaben geprüft. Ein größerer
  Server oder ein kostenpflichtiger Konverter ist nicht bestellt.

## Nutzerablauf

1. Im Projekt **Plan hinzufügen** öffnen: **Plan fotografieren** auf iPhone/iPad
   oder **Datei importieren** auf Handy, Tablet und Windows.
2. Papierplan einschließlich handschriftlicher Änderungen aufnehmen. Original
   zuerst dauerhaft sichern; danach Ausschnitt, Drehung und Entzerrung anzeigen.
3. Ohne Verbindung **Lokal gespeichert – wartet auf Verbindung** anzeigen. Ein
   bestätigtes Original übersteht App-Wechsel und Neustart.
4. Bei Verbindung die Datei fortsetzbar und mit Prüfsumme zum Hetzner-Server
   übertragen. Erst vollständige, berechtigte Uploads zur Erkennung freigeben.
5. Der tatsächliche Serverauftrag läuft unabhängig von der geöffneten App weiter.
   Nach Wiederöffnung werden Status und Ergebnis abgeholt. iOS garantiert keine
   sofortige Übertragung einer beendeten App; ein noch lokales Foto ist daher
   nicht bereits ein laufender Serverauftrag.
6. Original, aufbereitete Ansicht und automatisch abgeleiteten Entwurf gemeinsam
   zeigen. Wände, Öffnungen, Texte und Handnotizen mit unklaren Stellen kenntlich
   machen. Freie Zeichenwerkzeuge dienen anschließend der Korrektur.
7. Maßstab beziehungsweise Referenzmaß prüfen und die gewünschte Fassung
   übernehmen. Erneute Erkennung oder Korrektur erzeugt einen neuen Stand.

## Formate und Reihenfolge

| Quelle | Ausbau | Nachweis vor Freigabe |
| --- | --- | --- |
| Kamerafoto, JPEG/PNG | Erste Priorität: Original, Vorschau, Perspektive, lokale Erkennung und Ergebnisvergleich. | Gedruckter Hausplan mit Handschrift, schräger Aufnahme und uneinheitlichem Licht. |
| PDF | Erste Importstufe: Seitenwahl, Original und Vorschau; Vektor-PDF und gescannte Seite unterscheiden. | Ein mehrseitiges Vektor-PDF und ein Bild-PDF; Seiten-/Text-/Geometriebezug erhalten. |
| DXF | Danach: Einheiten, Layer und unterstützte Elemente übernehmen; unbekannte Inhalte ausdrücklich melden. | Linien, Texte, Blöcke, Bögen und Bemaßungen bleiben entweder erhalten oder als nicht übernommene Inhalte erkennbar. |
| DWG | Lokaler Import mit separat geprüftem Konverter und geklärten Nutzungsbedingungen. | Unterstützte DWG-Versionen und Vergleich vor/nach Konvertierung; kein externer Konvertierungsdienst. |

Die Kameraausgabe kann HEIC sein. Originalerhalt, native Vorschau und eine
lokale Konvertierung müssen auf dem tatsächlichen iPhone/iPad nachgewiesen
werden. Eine Dateiendung im Auswahlfenster belegt keine Formatunterstützung.
Ein bloß abgelegtes Foto oder DWG ist noch kein automatisch digitalisierter Plan.

## Original, Notizen und Maße

- Originaldateien bleiben unverändert. Zuschnitt und Entzerrung erzeugen eigene
  Ableitungen mit nachvollziehbarer Transformation zur jeweiligen Quellseite.
- Gedruckte Geometrie, handschriftliche Ergänzungen, Durchstreichungen, Pfeile
  und Farben bleiben unterscheidbar. Ein Pfeil ist nicht ohne Weiteres eine
  Wand und eine durchgestrichene Zahl kein gültiges Maß.
- Unsichere Erkennung bleibt ein Vorschlag. Fehlende Maße, Anschlüsse oder
  verdeckte Wandstücke werden nicht als gemessener Bestand ergänzt.
- Ein Foto hat zunächst keinen verlässlichen Maßstab. Eine Referenzstrecke wird
  nach Klärung der Perspektive gesetzt; sie bestätigt nicht sämtliche Maße.
- Quellen- und Erkennungsebene bleiben neben übernommenen Planobjekten erhalten.
  Eine erneute Erkennung darf Nutzerkorrekturen nicht still überschreiben.

## Technischer Durchstich

**Originalquelle:** stabile ID, Projekt, Quellhash, MIME-Typ, Byteanzahl und
gegebenenfalls PDF-Seite. Original und Vorschau getrennt speichern. Für den
ersten begrenzten Serverausbau kommen DB-BLOBs/Chunks infrage, damit die Quelle
mit der bestehenden Datenbanksicherung konsistent wiederherstellbar bleibt.
Dateien außerhalb der Datenbank auf demselben Server brauchen einen eigenen
geprüften Sicherungsvertrag.

**Offline-Speicherung:** große Quellen als unveränderliche, verschlüsselte
Binärdateien im vorhandenen Konto-/Serverscope. Keine Base64-Bilder im gesamten
JSON-Snapshot. Zuerst die Quelldatei dauerhaft veröffentlichen, danach ihre
Referenz samt Uploadauftrag über den vorhandenen einzigen Metadaten-Schreiber
committen. Abgebrochene Uploads und abgelaufene Freigaben löschen keine Originale.

**Übertragung und Rechte:** eigene begrenzte, fortsetzbare Binärrouten mit
Chunk- und Gesamtprüfsumme. Die aktuelle JSON-Grenze von 1 MB reicht für Fotos
nicht. Projektprüfung und der eng begrenzte Siebentage-Zugang gelten auch für
Quellen, Vorschauen und Aufträge. Ältere Planclients dürfen Quellenreferenzen
beim Speichern nicht entfernen.

**Aufträge:** Uploadstatus von Erkennungsstatus trennen. Dauerhafte Auftrags-ID,
Ausgangsversion, Versuchszähler, Lease und begrenzte Wiederholungen vorsehen.
Ein Neustart setzt unterbrochene Arbeit fort, ohne Planstände zu duplizieren.
Ohne tatsächlich eingerichtetes Erkennungsverfahren keine laufende KI-Auswertung
oder fertige Digitalisierung vortäuschen.

**Worker:** Erkennung außerhalb der heutigen globalen Office-Transaktion und
außerhalb der HTTP-Worker ausführen. Dateigröße, aufgelöste Pixel, Seitenzahl,
Parserlaufzeit und Arbeitsspeicher begrenzen. Das vorhandene ARM-System vor
Auswahl größerer lokaler Modelle prüfen; Bildverarbeitung darf Anmeldung und
Berichte nicht durch Speicher- oder CPU-Überlastung blockieren.

**Planrevision:** Referenz auf Originalhash/Seite, Koordinatensystem,
Transformation, Kalibrierung und Erkennungslauf. Übernahme als neue Revision mit
stabiler Anfrage-ID und Prüfung der Ausgangsversion. Der bestehende reine
`title/walls`-Vertrag muss dafür ausdrücklich erweitert werden.

## Belegter Stand: isolierter Importkern

Unter [`backend/plan_import`](backend/plan_import/README.md) ist jetzt ein
isolierter Linux-CLI-Importkern implementiert: JPEG/PNG und PDF werden nach
Dateiinhalt erkannt, das Original samt Prüfsumme erhalten und die gewählte
PDF-Seite als Vorschau gerendert. PDFium liefert zusätzlich vorhandenen
PDF-Text mit Positionsbezug; OpenCV erzeugt Linienkandidaten, Tesseract erkennt
Drucktext. Erfolgreich verarbeitete Aufträge stehen zur fachlichen Prüfung in
`needs_review`; PNG-Vorschau, JSON-Ergebnis und eine eigenständige
HTML-Prüfansicht gehören dazu.
**67 Tests bestanden im Docker-Lauf ohne Netzwerkzugang.**

Kameraaufnahme, verschlüsselte Offline-Medien, Upload und die Anbindung an
Office-API/-Datenbank sind damit noch nicht umgesetzt. Wandsemantik,
Handschriftauswertung und DXF/DWG-Import stehen ebenfalls aus. Dieser Kern wurde
nicht auf Hetzner bereitgestellt; der produktive Stand 0.7 bleibt unverändert.

Die frühere Machbarkeitsprobe in der Cloud verwendete PyMuPDF für PDF und ezdxf
für DXF sowie synthetischen Tesseract-Drucktext. Sie war eine getrennte Probe;
der neue Importkern verwendet PDFium, OpenCV und Tesseract. Daraus folgt weiterhin
kein Nachweis auf dem Nutzer-Server oder Handy. Es wurde kein Plan an einen
externen Auswertungsdienst gesendet. Ein Linienkandidat ist noch keine bestätigte
Wand und interpretiert keine handschriftliche Änderung.

Der nächste konkrete Qualitätsnachweis verwendet einen repräsentativen
abfotografierten Plan mit Handnotizen und möglichst die dazugehörige PDF-/DXF-
Vorlage. Diese Testdateien werden direkt auf dem eigenen Hetzner-System
bereitgestellt; reale Planunterlagen werden dafür nicht im Chat hochgeladen.
Die Entwicklung verwendet zunächst synthetische Beispiele.
Zuerst Original und digitale Kopie vergleichen; danach Geometrie,
Handnotizen und Maße einzeln bewerten. Daraus werden die lokal geeigneten
Verfahren und der nächste native Durchstich ausgewählt.

Die vollständige Abnahme verlangt zusätzlich: offline aufnehmen, App neu öffnen,
später unterbrochenen Upload fortsetzen, Serverauftrag nach Worker-Neustart
beenden und dieselbe Quelle samt prüfbarem Ergebnis auf dem zweiten Gerät öffnen.
Die SmartScreen-/Signierungsaufgabe des nächsten Windows-Updates bleibt offen.
