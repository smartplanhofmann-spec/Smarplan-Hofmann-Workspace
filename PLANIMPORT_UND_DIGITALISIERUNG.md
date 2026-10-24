# Planimport und Digitalisierung auf Hetzner

Nutzerentscheidung vom 23. Oktober 2026: Der freie Wandeditor aus Version 0.7
ist nicht der gewünschte Hauptablauf. Vorrang haben vorhandene Pläne und
abfotografierte Papierpläne, besonders Hausgrundrisse mit handschriftlichen
Ergänzungen. Aus diesen Quellen soll im Hintergrund ein überprüfbarer,
bearbeitbarer Plan entstehen. Das Original muss daneben erhalten bleiben.

Diese Spezifikation beschreibt das Ziel und den unten abgegrenzten aktuellen
Durchstich. Dateiauswahl, iOS-Kamera, verschlüsselte Originale, Upload und
Serveraufträge und ein standardmäßig geschützter Linux-Worker sind verbunden.
Version 0.8 mit Schema 3 ist auf Hetzner bereitgestellt; die synthetische
systemd-/ARM64-Dienstabnahme ist bestanden. Das vorbereitete Paket 0.9 mit
Schema 4 ist noch nicht auf dem Nutzer-Server bereitgestellt.

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

## Nutzerablauf als Zielbild

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
gegebenenfalls PDF-Seite. PostgreSQL-Schema 3 hält unveränderliche Originalchunks
und getrennte Vorschau-/Erkennungsergebnisse in der Datenbank. Die bestehende
gemeinsame Sicherung erfasst damit auch Planquellen; Release und Restore prüfen
Hashes, partielle Uploads und veröffentlichte Ergebnisse im getrennten Kandidaten.

**Offline-Speicherung:** große Quellen als unveränderliche, verschlüsselte
Binärdateien im vorhandenen Konto-/Serverscope. Keine Base64-Bilder im gesamten
JSON-Snapshot. Zuerst die Quelldatei dauerhaft veröffentlichen, danach ihre
Referenz samt Uploadauftrag über den vorhandenen einzigen Metadaten-Schreiber
committen. Das ist im Entwicklungscode umgesetzt. Abgebrochene Uploads und
abgelaufene Freigaben löschen keine Originale. Die Dateien werden vor dem
Metadatencommit verschlüsselt geschrieben und geflusht; Dart bietet hier keinen
Verzeichnis-fsync. Eine garantierte Stromausfallsicherheit ist deshalb nicht
nachgewiesen. App-Neustart und Wiederaufnahme gehören zur Integrationsprüfung.

**Übertragung und Rechte:** eigene begrenzte, fortsetzbare Binärrouten mit
Chunk- und Gesamtprüfsumme. Neue Routen übertragen Abschnitte mit 256 KiB;
die bisherige JSON-Grenze von 1 MB bleibt bestehen. Wiederholte Anfrage-ID und
bereits bestätigte Abschnitte verhindern doppelte beziehungsweise ersetzte
Originale. Projektprüfung und der eng begrenzte Siebentage-Zugang gelten auch für
Quellen, Vorschauen und Aufträge. Importdaten stehen getrennt vom bisherigen
`title/walls`-Vertrag, damit alte Planclients sie nicht entfernen.

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

## Bestätigter Stand 0.8 und vorbereitetes Paket 0.9

Unter [`backend/plan_import`](backend/plan_import/README.md) ist jetzt ein
Linux-Importkern implementiert: JPEG/PNG und PDF werden nach
Dateiinhalt erkannt, das Original samt Prüfsumme erhalten und die gewählte
PDF-Seite als Vorschau gerendert. PDFium liefert zusätzlich vorhandenen
PDF-Text mit Positionsbezug; OpenCV erzeugt Linienkandidaten, Tesseract erkennt
Drucktext. Erfolgreich verarbeitete Aufträge stehen zur fachlichen Prüfung in
`needs_review`; PNG-Vorschau, JSON-Ergebnis und eine eigenständige
HTML-Prüfansicht gehören dazu. Für die App verbindet der neue
[API-/Worker-Durchstich](backend/online/PLANIMPORT.md) diesen Kern mit den
projektgebundenen Quellen und Ergebnissen in PostgreSQL.

Die App im Online-Modus (API v1) enthält Dateiauswahl für JPEG/PNG/PDF und Kameraaufnahme auf iOS,
verschlüsselte Binärdateien sowie eine fortsetzbare Uploadwarteschlange.
Das lokale Windows-Paket blendet den neuen Import aus. Der Online-Modus erlaubt
die vorbereitete Offline-Nutzung auch ohne aktuelle Internetverbindung.
Quellkopien und heruntergeladene Ergebnisse bleiben im Konto-/Serverscope.
Für iOS sind Kameraerlaubnis, `NSFileProtectionComplete` und Ausschluss des
Offline-Ordners aus Systemsicherungen implementiert. Die Kamera-Tempdatei wird
nach bestätigter verschlüsselter Übernahme bereinigt; keine Aufnahme wird durch
die App in die Fotomediathek exportiert. Diese nativen Eigenschaften benötigen
noch die reale iPhone-/iPad-Abnahme; CI-Kompilierung allein belegt sie nicht.

Der Nutzer hat den Hetzner-Server auf **0.8 / Commit `c58b609` / Schema 3**
aktualisiert. Die synthetische Abnahme unter der tatsächlichen systemd-Unit auf
Ubuntu 24.04 ARM64 ist bestanden; API, HTTPS und Importdienst wurden gemeinsam
als `active` bestätigt. Der geschützte Importdienst ist aktiviert. Einrichtung
und Abnahme müssen bei diesem bestehenden Stand nicht erneut als Erstinstallation
ausgeführt werden.

**0.9 / Schema 4 ist vorbereitet, noch nicht bereitgestellt.** Die Planansicht
öffnet ohne voreingeblendete Erkennungslinien. Drehen, Zoomen und Einpassen
erleichtern die Prüfung; die gespeicherte Drehung betrifft nur die lokale Ansicht,
das Original bleibt unverändert. Linien- und Textvorschläge sind optional unter
Details erreichbar. Importquellen und gezeichnete Pläne können mit Berechtigungs-
und Bestätigungsprüfung aus dem Projekt entfernt werden; Geräte gleichen dies
bei Verbindung ab. Fehler dürfen keine unbestätigte Löschung vortäuschen.
Diese Änderungen gehören zum [gebündelten Update 0.9](deploy/hetzner/online/UPDATE_0_9.md)
und sind keine bereits auf dem Nutzer-Server aktivierten Funktionen.

Der Online-Worker startet standardmäßig in einer unprivilegierten bubblewrap-
Sandbox. Eigene Mount-, PID- und Netzwerk-Namespaces trennen Parser/OCR von
Datenbank, Hostnetz und privaten Serverdateien. Quelle, Code und Runtime sind
schreibgeschützt. Nur zwei begrenzte Exportdateien sind auf dem Host beschreibbar;
temporäre Dateien bleiben in privaten tmpfs-Bereichen mit 128 beziehungsweise
96 MiB. Die bereinigte Umgebung enthält keine DSN-/Vault-/OAuth-Geheimnisse.
`--doctor` prüft vor dem ersten Datenbankzugriff echte Isolation, exakt versionierte
Abhängigkeiten und lokale OCR-Sprachen. Ein fehlgeschlagener Aufbau führt zu
keinem ungeschützten Ersatzlauf. Der ausdrücklich ungeschützte Entwicklungsmodus
bleibt synthetischen Tests vorbehalten.

Die optionale [Dienstvorbereitung](deploy/hetzner/online/PLANIMPORT_DIENST.md)
bereitet Runtime und systemd-Unit unter der gemeinsamen Updatesperre vor,
ohne den Dienst zu starten, zu aktivieren oder Daten zu ändern. Der Dienst
begrenzt Controller und Nachfahren gemeinsam und beendet die gesamte Kontrollgruppe
beim Stopp. Native Parserabstürze werden von Infrastrukturfehlern unterschieden;
Originale bleiben erhalten und geordnet unterbrochene gültige Versuche werden
zurückgegeben. Lokale echte Namespace- und Datenbanktests sind bestanden.
Die obligatorische Namespace-CI prüft auch dieselbe Unit unter Ubuntu-24.04-
systemd mit eigenen synthetischen PostgreSQL-Aufträgen. Die zusätzliche
synthetische Abnahme auf dem tatsächlichen ARM64-Hetzner-Server ist ebenfalls
bestanden. Deutsche OCR benötigt lokale Sprachdaten; ihre fachliche Qualität
bei realen Plänen ist dadurch nicht abgenommen.
Wandsemantik, Handschriftauswertung, Perspektivkorrektur, Maßkalibrierung und
DXF/DWG-Import stehen aus; Linien werden nicht automatisch als Wände übernommen.

Die frühere Machbarkeitsprobe in der Cloud verwendete PyMuPDF für PDF und ezdxf
für DXF sowie synthetischen Tesseract-Drucktext. Sie war eine getrennte Probe;
der neue Importkern verwendet PDFium, OpenCV und Tesseract. Diese historische
Cloud-Probe war kein Server- oder Gerätenachweis; inzwischen ist der isolierte
Dienst auf ARM64 abgenommen. Es wurde kein Plan an einen
externen Auswertungsdienst gesendet. Ein Linienkandidat ist noch keine bestätigte
Wand und interpretiert keine handschriftliche Änderung.

Der nächste konkrete Qualitätsnachweis verwendet einen repräsentativen
abfotografierten Plan mit Handnotizen und möglichst die dazugehörige PDF-/DXF-
Vorlage. Diese Testdateien werden direkt auf dem eigenen Hetzner-System
bereitgestellt; reale Planunterlagen werden dafür nicht im Chat hochgeladen.
Die Entwicklung verwendet synthetische Beispiele. Nach der bestandenen
Dienstabnahme können vom Nutzer gewählte reale Testunterlagen direkt auf dem
eigenen Hetzner-System fachlich verglichen werden.
Zuerst Original und digitale Kopie vergleichen; danach Geometrie,
Handnotizen und Maße einzeln bewerten. Daraus werden die lokal geeigneten
Verfahren und der nächste native Durchstich ausgewählt.

Die vollständige Abnahme verlangt zusätzlich: offline aufnehmen, App neu öffnen,
später unterbrochenen Upload fortsetzen, Serverauftrag nach Worker-Neustart
beenden und dieselbe Quelle samt prüfbarem Ergebnis auf dem zweiten Gerät öffnen.
Die SmartScreen-/Signierungsaufgabe des nächsten Windows-Updates bleibt offen.
Die bestandene synthetische Serverabnahme ersetzt weder die reale iPhone-/iPad-
Prüfung noch einen Nachweis vollständiger bearbeitbarer CAD-Erkennung. Handschrift,
Wandsemantik, Perspektivkorrektur, Maßkalibrierung sowie DXF/DWG bleiben weitere
Ausbauschritte.
