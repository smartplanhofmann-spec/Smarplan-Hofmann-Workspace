# Smartplan Office – Entwicklungsstand 0.9.0

Gemeinsamer Arbeitsbereich für Büro und Baustelle: Anfragen, Kunden,
Projektmappen, Aufgaben, Termine, Bautagebuch, Pläne und unterschriebene Berichte.
Windows und iPhone/iPad verwenden denselben Hetzner-Server. Der aktuelle große
Entwicklungsstand wird als zusammenhängendes Paket geprüft und verteilt.

Die fachliche Grundlage und Abnahme stehen in
[Produktpaket 0.9](PRODUKTPAKET_0_9.md). Arbeitsabläufe sind flexibel: Ein Projekt
kann zur Klärung, zum Aufmaß oder als Serviceeinsatz beginnen. Angebot, Zusage,
Anzahlung und Material sind keine erzwungene Pflichtreihenfolge.

## Bestätigte Betriebsentscheidungen

- Eingang über **Gmail und die WhatsApp-Business-App**.
- **Sevdesk bleibt führend für Angebote und Rechnungen**. Smartplan verknüpft
  passende Vorgänge; es erzeugt keine zweite Buchhaltung.
- **Google Kalender** bleibt für Termine vorgesehen. Das Paket bietet eigene
  Projekttermine und ausdrücklichen Kalenderexport, keine bereits laufende
  bidirektionale Google-Synchronisierung.
- Die vorhandene **Dropbox-Struktur** bleibt bestehen. Ordner und Dokumente sind
  benannt verknüpfbar; das ist keine bereits verbundene Dropbox-API.
- Datenbank und Planverarbeitung bleiben auf dem eigenen **Hetzner-Server**.
  Kein externer KI-/OCR-Ausweichdienst. Cloudtests verwenden synthetische Daten.

## Inhalt des Pakets

**Anfragen und Kunden:** Eingang mit Quelle, Suche, Fälligkeit und nächstem
Schritt; manuelle/WhatsApp-Nachrichten und EML-Dateien; bestehende Kunden als
Vorschlag. Die bestätigte Übernahme in Kunde und Projekt ist atomar und
retryfest. Eine Projektanlage erfindet keine Angebotszusage.

**Projektmappe:** Übersicht als Einstieg, vollständig benannte Register für
Aufgaben, Termine, Bautagebuch, Pläne, Dokumentverweise und Berichte. Tatsächliche
Projektdaten und offene Arbeit statt Demozahlen; Zuständigkeiten, Fälligkeiten
und manuelle Anzahlung-/Materialmeilensteine sind unabhängig änderbar.
Revisionen schützen vor stillen Überschreibungen.

**Offline:** Vorbereitete Projektmappen, Aufgaben, Termine, Tagebuch und Pläne
werden verschlüsselt gespeichert und mit dauerhafter Warteschlange abgeglichen.
Freigabe bis zu sieben Tage, keine automatische Löschfrist. Anfragen, externe
Dienste und unterschriebene Berichte benötigen Verbindung. Alte Plantokens
bekommen nicht stillschweigend erweiterte Rechte.

**Planunterlagen:** JPEG/PNG/PDF und iOS-Kamera; Originale, fortsetzbare Uploads
und lokale Servererkennung. Ruhige Ansicht mit Drehen/Zoom/Einpassen und
optionalen Erkennungsdetails. Bestätigtes Löschen auch offline, ohne spätere
Wiederbelebung. Linien und Drucktext sind Prüfvorschläge; automatisch bearbeitbare
Wand-/Raumpläne, Handschriftsemantik, Perspektivkorrektur, Maßstab und DXF/DWG sind
weiterhin eigene Entwicklungsaufgaben.

**Gmail-Vorbereitung:** Labelbegrenzte lesende Apps-Script-Brücke mit widerrufbarem,
engem Einlieferungsschlüssel. Einrichtung und belegter Empfang sind getrennt.
[Google/Gmail einrichten](integrations/google_apps_script/SETUP.md): echte
Google-Autorisierung, Trigger und erste Übernahme gesondert abnehmen. WhatsApp-
API/Nummern-Coexistence sind nicht bereits eingerichtet.

## Tatsächlicher Nutzer-Server

Am **24. Oktober 2026** bestätigte Thomas **0.8.0 / Schema 3**, Commit
`c58b6094f4278318bdec82322dd6e9a3fc389561`, auf Hetzner. Die synthetische ARM64-
Abnahme für lokale deutsche/englische OCR, Isolation, Stopp/Wiederaufnahme und
Bereinigung war erfolgreich. API, HTTPS und Importdienst meldeten `active`;
Foto-/PDF-Import in der Windows-App ist bestätigt.

**0.9.0 / Schema 4 ist der neue Entwicklungsstand, noch nicht auf dieser VM
installiert.** Der [gebündelte Updateablauf](deploy/hetzner/online/UPDATE_0_9.md)
verwendet den vorhandenen Datenbankkopie-/Wartungsablauf.

Windows-Pakete sind **unsignierte interne Prüfpakete**. Authenticode-/Installer-/
SmartScreen-Abnahme bleiben offen. Neue Apple-/Provider-Abos oder kostenpflichtige
Signierdienste werden nicht bestellt. Vorhandene Apple-Zugänge dienen der
bestehenden TestFlight-Verteilung; ein unsignierter Gerätebuild ist keine Installation.

## Entwicklung und Nachweise

- [Entwicklung und bisherige Abnahmen](ENTWICKLUNG.md)
- [Kundenverwaltung](KUNDENVERWALTUNG.md), [Projektpläne](PROJEKTPLAENE.md)
- [Offline-Grundlagen](OFFLINE_UND_SYNCHRONISIERUNG.md)
- [Planimport und Digitalisierung](PLANIMPORT_UND_DIGITALISIERUNG.md)
- [API-Vertrag Planquellen](backend/online/PLANIMPORT.md)
- [Geschützter Importdienst](deploy/hetzner/online/PLANIMPORT_DIENST.md)
- [Optionaler Dropbox-Prozessprompt](DROPBOX_PROZESSPROMPT.md)

`scripts/setup-cloud.sh` bereitet die vorhandene Cloudentwicklung mit festem
Flutter-SDK und getrennten Backendabhängigkeiten vor. Tests benutzen eigene
entbehrliche Datenbanken und synthetische Dateien. PostgreSQL-Migration und
Restore sind ausdrücklich und nie Nebeneffekt einer HTTP-Anfrage. Native
Paketprüfung kontrolliert Version, API-Ziel, Quellcommit, Plugins und Backenddateien.

Bosch Professional, HERO und Capmo dienen als fachliche Referenzen. Der aktuelle
Status der angeforderten Anbieterrecherche ist im Produktpaket offengelegt;
blockierte Webseiten werden nicht als gelesene Quellen ausgegeben.
