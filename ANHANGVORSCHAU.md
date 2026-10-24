# Anhangvorschau – App 0.10.1

Der Nutzer hat die tatsächliche Übernahme eines Mailanhangs in Smartplan
bestätigt. Bisher kann die Datei nur gespeichert beziehungsweise geteilt
werden. Die App-Erweiterung öffnet PDF- und Bildanhänge direkt innerhalb der
Anfrage oder der Projektdokumente.

## Bedienung

- Eine verfügbare Datei über ihren Namen oder die Aktion **Vorschau** öffnen.
- PDF-Seiten innerhalb der App ansehen; Bilder vergrößern und verschieben.
- Über Zurück beziehungsweise Schließen wieder zur Anfrage oder zum Projekt.
- Originaldateien weiterhin ausdrücklich speichern beziehungsweise teilen.
- Für nicht unterstützte Dateiformate oder beschädigte Dateien eine klare
  Meldung mit der vorhandenen Dateiausgabe erhalten.

Die Vorschau verändert weder den Originalanhang noch eine bereits angelegte
Planquelle. DWG/DXF und Office-Dokumente erhalten durch diese Erweiterung keine
eingebaute CAD- oder Office-Konvertierung.

## Daten und Zugriff

Die App lädt dieselben geschützten Originalbytes wie beim bisherigen Download.
Größe und SHA-256 werden vor der Anzeige geprüft. Die Vorschau verwendet den
Arbeitsspeicher der App und keinen externen Viewer, Browser- oder Konvertierungsdienst.
Für die Vorschau werden keine unverschlüsselten temporären Dateien angelegt.
Abmeldung oder der Verlust des lokalen Zugriffs beendet die Anzeige. Eine
serverseitige Rechteänderung wird wie bisher bei der nächsten Onlineprüfung
erkannt; ein bereits geladenes Dokument ist keine laufende Serververbindung.

Anfragen und ihre Anhänge benötigen weiterhin Verbindung. Die bestehenden
verschlüsselten Offline-Projektmappen und Planquellen haben ihren eigenen Ablauf.

## Bereitstellung

Nur die App wird auf **0.10.1** aktualisiert. Der vorhandene Backendstand
**0.10 / Schema 5** mit `mail_attachments` und der bereits eingerichtete Bot
liefern alle benötigten Daten. Es gibt keine neue Datenbankmigration, keinen
zusätzlichen Dienst und keinen weiteren Botauftrag für diese Vorschau.

Unter Windows die alte App schließen, das neue Online-ZIP vollständig in einen
neuen Ordner entpacken und daraus starten. App-Daten und ausstehende
Offline-Eingaben erhalten. Mobile Vorschau und Dateiausgabe benötigen zusätzlich
die tatsächliche Geräteabnahme; ein erfolgreicher Build ersetzt diese nicht.

Die Prüfungen verwenden ausschließlich synthetische PDF-/Bilddateien. Zu den
Abnahmen gehören mehrseitiges PDF, Bildzoom, ungültige Dateien, nicht unterstützte
Dateitypen, Größen-/Hashfehler sowie Abmeldung während des Ladens und einer
bereits geöffneten Vorschau.
