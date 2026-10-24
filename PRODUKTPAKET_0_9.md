# Smartplan Office 0.9 – zusammenhängendes Arbeitspaket

## Arbeitsgrundlage vom 24. Oktober 2026

Thomas möchte eine schnell nutzbare gemeinsame Arbeitsoberfläche statt einzelner
kleiner Funktionsupdates. Bosch Professional, HERO und jetzt auch Capmo sind
fachliche Referenzen. Die Projektübersicht bleibt erhalten; ein geöffnetes
Projekt beginnt mit einem Dashboard und verständlich benannten Bereichen.

Die genannten Arbeitsschritte sind **keine Pflichtreihenfolge**. Service,
Beratung, Montage und größere Aufträge brauchen unterschiedliche Abläufe.
Aufgaben, Termine, Projektphase, Anzahlung und Material werden unabhängig
voneinander gepflegt. Auch eine Erstklärung oder ein Aufmaß kann bereits ein
Projekt sein. Eine tatsächlich erteilte Zusage wird ausdrücklich erfasst;
eine Projektanlage erfindet weder eine Zusage noch einen Zahlungseingang.

Bestätigte heutige Werkzeuge:

| Bereich | Führende Quelle und Übergang |
| --- | --- |
| Neue Anfragen | Gmail und WhatsApp-Business-App |
| Angebote und Rechnungen | **Sevdesk bleibt führend** |
| Kalender | Google Kalender; zunächst ausdrücklicher Kalenderexport und Übergabe |
| Vorhandene Dateiablage | Dropbox; vorhandene Struktur zunächst erhalten |
| App, Projektinformationen, Pläne und Verarbeitung | Eigener Hetzner-Server |

Häufige Bausteine: Rückruf, Unterlagen sichten, Aufmaß vor Ort oder Zoom,
Angebot in Sevdesk, telefonische oder schriftliche Zusage, Terminabstimmung,
Anzahlung, Materialbestellung, Ausführung und Schlussrechnung. Diese Aufzählung
bestimmt keine automatische Reihenfolge oder Vertragsannahme.

## Inhalt des gebündelten Entwicklungsstands

1. **Anfragen:** Gemeinsamer Eingang mit Quelle, nächstem Schritt, Fälligkeit,
   Status und passenden bestehenden Kunden. Manuelle Nachrichten, WhatsApp-Text
   und EML-Dateien sind unmittelbar erfassbar. Die bestätigte Übernahme in Kunde
   und Projekt erfolgt atomar und erzeugt bei Wiederholung keine Duplikate.
2. **Projektmappe:** Übersicht, Aufgaben, Termine, Bautagebuch, Pläne,
   Dokumentverweise und vorhandene unterschriebene Berichte. Alle Register sind
   frei erreichbar; es gibt keinen erzwungenen Ablaufassistenten.
3. **Dashboard:** Echte Projektbeschreibung, Baustelle, manuell gepflegte Phase,
   offene/überfällige Aufgaben, nächste Termine und letzter Tagebucheintrag.
   Unbekannte Anzahlung oder Materiallage erscheinen nicht als bestätigt.
4. **Aufgaben und Bautagebuch:** Zuständigkeit, Fälligkeit und Bearbeitungsstand;
   Tagesarbeiten, Probleme und nächste Schritte. Änderungen besitzen Revisionen
   und nachvollziehbare Wiederholungsregeln. Es wird keine rechtliche
   Gleichstellung mit unterschriebenen Berichten behauptet.
5. **Bestehende Werkzeuge:** Benannte Dropbox-/Sevdesk-/Vertragsverweise und echte
   Kalenderdateien. Ein gespeicherter Link ist keine aktive Datenabgleichung.
   Angebote, Rechnungsnummern, Zahlungen und Steuerlogik werden nicht parallel zu
   Sevdesk neu erfunden.
6. **Planunterlagen:** Ruhige Ansicht mit Drehen, Vergrößern und Einpassen;
   Linien- und Texterkennung optional und erklärt. Eine Erkennungsvorschau ist
   weiterhin kein automatisch bearbeitbarer Wandplan.
7. **Löschen:** Bestätigtes Entfernen von importierten und gezeichneten Plänen,
   auch offline. Dauerhafte Löschmarkierungen verhindern spätere Wiederbelebung.
   Aktive Original-/Ergebnisbytes werden gezielt entfernt; historische
   Betriebssicherungen werden dadurch nicht nachträglich umgeschrieben.
8. **Offline-Projektarbeit:** Verschlüsselte vorbereitete Projektmappen,
   Aufgaben, Termine, Tagebucheinträge und Pläne mit sieben Tagen Freigabe,
   dauerhafter Warteschlange und sichtbaren Konflikten. Anfragen, externe
   Anbieter und unterschriebene Berichte bleiben verbindungsabhängig.
9. **Gmail-Vorbereitung:** Ein auf ein ausgewähltes Label begrenztes Apps-Script
   kann Nachrichten über einen widerrufbaren Einlieferungsschlüssel übernehmen.
   Der Schlüssel erlaubt keine Projekt-/Kunden-/Finanzabrufe. Echte Google-
   Autorisierung, Trigger und erste Liveübernahme müssen gesondert nachgewiesen
   werden; ein Konfigurationsdialog behauptet keine aktive Verbindung.

## Zusammenhängende Abnahme

Ein synthetischer Beispielvorgang durchläuft Eingang, Kundenvorschlag und
Projektübernahme; danach Aufgaben, Termin, Tagebuch, Dropbox-/Sevdesk-Verweis,
Planimport und unverändertes unterschriebenes PDF. Ein zweiter Vorgang überspringt
Angebot/Zusage und legt direkt ein Klärungsprojekt an. Offline-Neustart,
Wiederverbindung, zweites Gerät, Konflikt und Rechteentzug gehören zur Abnahme.

Tests müssen echte Speicherung, API-Aufrufe, Migration von Schema 3 auf 4,
Backup/Wiederherstellung und Paketinhalt prüfen. Stubtests externer Anbieter
beweisen deren echte Verbindung nicht. Der erste große Teststand und eine
Produktivfreigabe bleiben unterscheidbar. Windows-Signierung/SmartScreen sowie
die tatsächliche mobile Geräteprüfung sind weiterhin eigene Freigabepunkte.

## Recherche und noch nicht verbundene Dienste

Die Cloud hat die offiziellen Seiten von Capmo, HERO und Bosch beim Abruf mit
HTTP-CONNECT 403 blockiert. Ein gezielter Netzwerkentwurf für Anbieter- und
Dokumentationsseiten ist gespeichert, aber seine Veröffentlichung ist noch nicht
nachgewiesen. Bis ein tatsächlicher Abruf gelingt, werden daraus keine aktuellen
Produkteigenschaften, Preise oder verfügbaren Schnittstellen behauptet.

Anschließend zu prüfen: Capmo/Bautagebuch und Aufgaben, Bosch Professional
(konkretes Produkt OfficeOn/MeasureOn abgrenzen), HERO/Handwerksabläufe sowie
PlanRadar, 123erfasst, Craftnote, Meisterwerk und WinWorker als Vergleich.
Offizielle Quellen und verifizierte Aussagen gehören in den anschließenden
Marktvergleich, nicht unbestätigte Marketingannahmen.

Die vorhandene WhatsApp-Business-App ist keine bereits eingerichtete API.
Offizielle Business-Platform-Anbindung, Nummern-Coexistence und tatsächlicher
Nachrichtenumfang müssen für das Nutzerkonto geprüft werden. Bestehende Nutzung
und Nummer werden nicht automatisch umgestellt. Für die erste Arbeitsgrundlage
ist eine ausdrücklich zugeordnete Nachrichtenerfassung verfügbar.

Der optionale [Dropbox-Prozessprompt](DROPBOX_PROZESSPROMPT.md) dient nur der
anonymisierten Beschreibung vorhandener Arbeitsweisen; er ist keine Erlaubnis,
Dateien zu verschieben, echte Kundenpläne extern zu verarbeiten oder Dienste zu
bestellen.
