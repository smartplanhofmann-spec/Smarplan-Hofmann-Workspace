# Smartplan Office – Entwicklungsstand 0.10.0

Gemeinsamer Arbeitsbereich für Büro und Baustelle: Anfragen, Kunden,
Projektmappen, Aufgaben, Termine, Bautagebuch, Pläne und unterschriebene Berichte.
Windows und iPhone/iPad verwenden denselben Hetzner-Server. Der aktuelle große
Entwicklungsstand wird als zusammenhängendes Paket geprüft und verteilt.

Die fachliche Grundlage und Abnahme stehen in
[Produktpaket 0.10](PRODUKTPAKET_0_10.md) und seiner
[Projektgrundlage 0.9](PRODUKTPAKET_0_9.md). Arbeitsabläufe sind flexibel: Ein Projekt
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

**Mailbot-Anschluss:** Nach der letzten Nutzerentscheidung verarbeitet der
vorhandene Bot die Mails und liefert die Anfragen direkt an Smartplan.
[Anschlusspaket und Bot-Auftrag](integrations/mail_bot/README.md) verwenden den
Eingang mit eng begrenztem, widerrufbarem Schlüssel. Die Textübernahme mit dem
vorhandenen Bot wurde vom Nutzer bestätigt. 0.10 ergänzt Originalanhänge:
fortsetzbare Abschnitte, SHA-Prüfung, vollständige Quittung und Nachträge zu
bereits übernommenen Mails. Anfrage und Projektmappe zeigen die Dateien;
PDF/JPEG/PNG lassen sich gezielt als Planquelle übernehmen. Windows verwendet
den Speicherdialog, iPhone/iPad die native Teilen-/Speichern-Ausgabe. Das Paket
enthält Werkzeugbeschreibung, Text- und Anhanghelfer; der tatsächliche Anhangabruf
des externen Bots muss gesondert abgenommen werden. Apps Script ist eine frühere Alternative,
deren manuelle Einrichtung der Nutzer als zu aufwendig verworfen hat.
WhatsApp-API/Nummern-Coexistence sind nicht bereits eingerichtet.

## Tatsächlicher Nutzer-Server

Am **24. Oktober 2026** bestätigte Thomas das Update auf **0.9.0 / Schema 4**,
Commit `822fe58be148f5df52ab14d6ff8a9267c696932e`, auf Hetzner. Die Abschlussprüfung
meldete Datenbank und Status `ok` sowie alle drei API-/HTTPS-/Importdienste
`active`. Manuelle Anfrageerfassung in der neuen Windows-App ist bestätigt.
Die synthetische ARM64-Dienstabnahme und der Foto-/PDF-Import wurden bereits mit
0.8 erfolgreich geprüft. Weitere reale Workflow- und Geräteprüfungen bleiben offen.
Der [gebündelte Updateablauf](deploy/hetzner/online/UPDATE_0_9.md) verwendet den
vorhandenen Datenbankkopie-/Wartungsablauf.

**0.10 / Schema 5 ist vorbereitet und noch nicht auf dieser VM installiert.**
Für Anhänge werden Server, Windows-App und der Auftrag des vorhandenen Bots
gemeinsam aktualisiert; siehe [Update 0.10](deploy/hetzner/online/UPDATE_0_10.md).
Gültige vorhandene Eingangsschlüssel und die bisherige Liste bestätigter Mails
werden weiterverwendet. Die Originaldateien werden nachgereicht; Mailtexte
müssen dafür nicht erneut gepostet werden.

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
