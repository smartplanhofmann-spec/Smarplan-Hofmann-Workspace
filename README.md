# Smartplan Office – Entwicklungsstand 0.13.0

Aktuelle Fortsetzung vom 08.11.2026: [Arbeitsstand und nächste Schritte](docs/CRM_ERP_ARBEITSSTAND.md).
Das unveränderte Gesamtziel bleibt maßgeblich. Die erneut beauftragte gesamte
Software umfasst auch Buchhaltung und Lohn; die frühere Projektphase hat nur
die Reihenfolge geändert. Vor einer Fortsetzung den tatsächlichen Quellstand
mit dem autorisierten Testbranch abgleichen.

## Aktuelles Gesamtziel – 04.11.2026

Für die weitere Entwicklung gilt
[CRM_ERP_Gesamtziel.txt](CRM_ERP_Gesamtziel.txt). Es erweitert den bisherigen
Projektumfang zur branchenübergreifenden CRM-/ERP-Software einschließlich eigener
Buchhaltung, optionaler deutscher Lohnabrechnung, Kundenportal, KI-Assistent,
Browser, Windows und iPhone. HERO und sevDesk sollen langfristig ersetzt werden.
Frühere Aussagen, dass eine Ablösung nicht beauftragt sei, begrenzen diesen
aktuellen Entwicklungsauftrag nicht. Ein produktiver Ausstellerwechsel oder
eine Übernahme echter Daten wird dadurch nicht automatisch freigegeben.

Der vorhandene Businessstand `420c4c7` wird weiterentwickelt. Einstieg:
[Bestandsaufnahme](docs/CRM_ERP_BESTANDSAUFNAHME.md),
[Anforderungen und Abnahme A–G](docs/CRM_ERP_ANFORDERUNGEN.md),
[Umsetzungsplan](docs/CRM_ERP_UMSETZUNGSPLAN.md) und
[aktueller Fortschritt mit Testergebnissen](docs/CRM_ERP_FORTSCHRITT.md).

Der [aktuelle Integrationsstand](docs/CRM_ERP_INTEGRATIONSSTAND_2026-11-03.md)
fasst die tatsächlich geprüften Abläufe zusammen: Kundenauftrag und Portal,
Projektwirtschaftlichkeit, Einkauf/Geräte/Inventur, eigene EÜR mit
Rechnungsketten, Personal und begrenzte deutsche Lohnfälle, Assistent/Regeln,
Sprachentwürfe, Dateiimport, Unternehmensarchiv, freie Zusatzfelder,
Datenschutzfälle, belegte Lohnzahlungen zur EÜR, Bankabgleich, Kundenservice und
Betriebsmittel. Midijob-Vollmonate sind in beiden Oberflächen geprüft;
Lieferantenretouren und die zusätzliche Unternehmensprovisionierung haben ihre
Fach-/Gegenprüfungen bestanden. Der Source4-Integrationsstand ist lokal als `5d9e7fd` gesichert;
der nachfolgende geprüfte Checkpoint ergänzt Anfangssalden und Katalogoriginale.
Belegte Lohnzeitachsen und einfache Teilmonate sind
inzwischen im Backend, PostgreSQL und beiden Clients geprüft
([Teilmonate](docs/CRM_ERP_LOHN_TEILMONATE_2026.md),
[Oberflächen](docs/CRM_ERP_LOHN_ZEITACHSEN_CLIENTS.md)). Die
[eigene Mitarbeiter-Belegansicht](docs/CRM_ERP_LOHN_MITARBEITERBELEG.md) ist
für v1–v5 geprüft. Reisepauschalen besitzen eine tatsächliche
Zahlungs-/EÜR-/Bankkette. Die v5 verbindet mehrteilige Lohnfälle, belegte
Ansprüche und Reise-Lohnwerte; Reise-v3 ergänzt Mischreisen und Boden-Zeitzonen.
Jahresquellen, Unterbrechungen, Nullnetto und die reguläre Source4-Kette für
Einmalbezüge sind inzwischen gemeinsam geprüft:
[1.508 Backend-, 473 JavaScript- und 1.103 Fluttertests sowie 16 Paketprüfungen](docs/CRM_ERP_SOURCE4_GESAMTPRUEFUNG_2026-11-04.md).
Ein Windows-spezifischer Backendtest blieb unter Linux ausgelassen.
Belegte Konto-Anfangssalden in beiden Oberflächen und der vollständige Browser-
Katalogimport sind jetzt gemeinsam geprüft: [1.565 bestandene Backendtests,
522 Node- und 1.118 Fluttertests, 16 Paketprüfungen sowie tatsächliche
PostgreSQL-/Restore- und Browserabläufe](docs/CRM_ERP_ANFANGSSALDEN_KATALOG_GESAMTPRUEFUNG_2026-11-04.md).
Aktiv entstehen Source5-Lohn-/Zahlungsfälle, historische Anlagen, datierte
Katalogpreise. Die native Kataloghistorie ist inzwischen integriert und durch
eine [weitere vollständige App-Prüfung mit 1.163 Tests](docs/CRM_ERP_KATALOG_NATIVE_2026-11-04.md) abgesichert.
Die noch laufenden fachlichen Erweiterungen
liegen außerhalb des neuen eingefrorenen Gesamtnachweises.
Das Gesamtziel ist noch nicht erreicht.

Verbindlicher Unternehmensrahmen: Einzelunternehmen mit EÜR, Regelbesteuerung,
Ist-Versteuerung, 19 % Standard-Umsatzsteuer, SKR04 und Nettopreise. Der
Personalumfang umfasst reguläre Mitarbeiter und Minijobs; tatsächlich
unterstützte Rechenfälle und verbleibende Zulassungen stehen in der
[Lohndokumentation](docs/CRM_ERP_LOHN_RECHENWERK_2026.md). Echte Anfangsbestände,
Gültigkeitsdaten und Betriebsfreigaben werden nicht erfunden.

Das [Benutzerhandbuch](docs/CRM_ERP_BENUTZERHANDBUCH.md) verbindet die
Arbeitsabläufe und verweist auf die detaillierten Fachanleitungen.

Die [Komponenten-/Sicherheitsprüfung](docs/CRM_ERP_ABHAENGIGKEITEN_SICHERHEIT.md)
und [fachliche Nachweisliste](docs/CRM_ERP_KONFORMITAET_QUELLEN.md) unterscheiden
reproduzierbare Entwicklungsbelege, tatsächliche Anbieter-/Geräteprüfungen und
noch erforderliche unabhängige Freigaben. Historische Zwischenstände bleiben
im Fortschrittsbericht erhalten.

**Aktuelle Nutzerabnahme laut Gesamtziel:** Bisher wurde nur ein digital
unterschreibbares Protokoll geprüft. Weitergehende Test-/Betriebsbestätigungen
in den nachfolgenden älteren Abschnitten bleiben historische Aufzeichnungen;
sie ersetzen weder die erneute Prüfung noch die Abnahme des neuen Gesamtziels.
Die gezeichnete Unterschrift ist ohne gesonderten Nachweis keine qualifizierte
elektronische Signatur.

## Vorhandenes Paket und historische Betriebsangaben

Das Projektpaket 0.12 ergänzt CRM und Projektstatus, eigene Belege und Finanzen,
Einsatzplanung, Zeiten, Baustellendokumentation, Material und Wartung. Die
responsive Browseroberfläche liegt unter `/office/`; die native App ergänzt
verschlüsselte Warteschlangen für eigene Zeiten und Baustellenfotos.
Strukturierte Rechnungskontakte, Decimal-Preiskalkulation, quellengebundene
Aufmaßübernahme und die Jahresplanung ergänzen den durchgängigen Ablauf.
Funktionsumfang, offene Punkte und Abnahmen stehen im
[Umsetzungsbericht](docs/BERICHT_HERO_UMSETZUNG.md), die technischen
Voraussetzungen und der sichere Umstieg im
[Betriebsleitfaden](docs/BETRIEB_BUSINESS_UPDATE.md).

Die folgenden Abschnitte beschreiben auch den weiterhin bestehenden 0.11-Kern.
Das neue Paket ist kein Nachweis einer bereits ausgeführten Serverinstallation.

Gemeinsamer Arbeitsbereich für Büro und Baustelle: Anfragen, Kunden,
Projektmappen, Aufgaben, Termine, Bautagebuch, Pläne und unterschriebene Berichte.
Windows und iPhone/iPad verwenden denselben Hetzner-Server. Der aktuelle große
Entwicklungsstand wird als zusammenhängendes Paket geprüft und verteilt.

Die fachliche Grundlage und Abnahme stehen im
[Integrationspaket 0.11](INTEGRATIONSPAKET_0_11.md),
[Produktpaket 0.10](PRODUKTPAKET_0_10.md) und seiner
[Projektgrundlage 0.9](PRODUKTPAKET_0_9.md). Arbeitsabläufe sind flexibel: Ein Projekt
kann zur Klärung, zum Aufmaß oder als Serviceeinsatz beginnen. Angebot, Zusage,
Anzahlung und Material sind keine erzwungene Pflichtreihenfolge.

Das [App-Update 0.10.1](APP_UPDATE_0_10_1.md) verbindet eine direkte Vorschau
für PDF- und Bildanhänge mit einer klareren, an Apple angelehnten Oberfläche.
Dieser Stand wurde vom Nutzer als funktionierend bestätigt. Das anschließende
Paket 0.11 ergänzt nun die Bürointegrationen mit geschütztem Serverupdate.

## Bestätigte Betriebsentscheidungen

- Eingang über **Gmail und die WhatsApp-Business-App**.
- **Sevdesk bleibt bis zum dokumentierten Ausstellerwechsel führend**.
  Eigene Rechnungsstellung und externer Versand sind zunächst gesperrt.
  Derselbe Auftrag wird nicht parallel in beiden Systemen abgerechnet.
- **Google Kalender und OneDrive** sind laut Nutzer bereits mit dem vorhandenen
  Bot verbunden. **OneDrive ersetzt die zuvor irrtümliche Dropbox-Annahme.**
  Paket 0.11 nutzt diese Verbindungen für ausdrücklich gewählte Projektmetadaten.
  Ein neuer SPIX-Projektbotzugang ergänzt denselben Fünfminutenjob; der bestehende
  SPIN-Maileingang bleibt erhalten. Es gibt keinen Kalender-Schreibabgleich.
- Datenbank und Planverarbeitung bleiben auf dem eigenen **Hetzner-Server**.
  Kein externer KI-/OCR-Ausweichdienst. Cloudtests verwenden synthetische Daten.
- Großhändler: **Granzow und Alexander Bürkle**. Lieferantenprofile sind
  vorbereitet; echte Preise und Bestellungen benötigen verifizierte
  Partnerprotokolle und eine ausdrückliche technische Freischaltung.

## Inhalt des Pakets

**Bürointegrationen 0.11:** Sevdesk-Kontakt und einzelne Angebote/Rechnungen
ausdrücklich zuordnen, gewählte Google-Termine anzeigen und OneDrive-Ordner samt
Originalverweisen im Projekt finden. Status, letzte bestätigte Aktualisierung
und ausstehende Botaufträge bleiben erkennbar. OneDrive-Dateien öffnen bewusst
im Microsoft-Browserkonto; die Mailanhangvorschau bleibt innerhalb der App.
Einrichtung unter Integrationen, geschützte Schlüssel ausschließlich auf
Hetzner beziehungsweise im Credential-Feld des vorhandenen Bots. Der
[Projektbot-Vertrag](integrations/project_bot/README.md) enthält Ablauf und Grenzen.

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
enthält Werkzeugbeschreibung, Text- und Anhanghelfer. Der Nutzer hat inzwischen
bestätigt, dass ein tatsächlicher Mailanhang in Smartplan angekommen ist.
Apps Script ist eine frühere Alternative,
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

**Die tatsächliche Anhangübernahme nach dem Paket 0.10 ist vom Nutzer bestätigt.**
Der letzte ausdrücklich ausgelesene Server-Quellcommit bleibt der oben genannte
0.9-Stand; die funktionierende neue Anhangroute belegt die aktive Erweiterung.
Der gebündelte Ablauf dafür steht unter
[Update 0.10](deploy/hetzner/online/UPDATE_0_10.md).
Gültige vorhandene Eingangsschlüssel und die bisherige Liste bestätigter Mails
werden weiterverwendet. Die Originaldateien werden nachgereicht; Mailtexte
müssen dafür nicht erneut gepostet werden.

**App 0.10.1 mit Vorschau und Design wurde im Praxistest bestätigt.**
**Paket 0.11 / Schema 6 ist vorbereitet und noch nicht auf dem Nutzer-Server
installiert.** Der [gebündelte Updateablauf](deploy/hetzner/online/UPDATE_0_11.md)
verwendet weiterhin Sicherung, Datenbankkopie und Kandidatenprüfung. Für echte
Sevdesk-/Botverbindungen folgt anschließend die Einrichtung in der aktualisierten App.

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
- [Integrationsvertrag und Rechte](backend/online/INTEGRATIONEN.md)
- [Tatsächlich geprüfte Anbieterquellen](backend/online/INTEGRATIONEN_QUELLEN.md)

`scripts/setup-cloud.sh` bereitet die vorhandene Cloudentwicklung mit festem
Flutter-SDK und getrennten Backendabhängigkeiten vor. Tests benutzen eigene
entbehrliche Datenbanken und synthetische Dateien. PostgreSQL-Migration und
Restore sind ausdrücklich und nie Nebeneffekt einer HTTP-Anfrage. Native
Paketprüfung kontrolliert Version, API-Ziel, Quellcommit, Plugins und Backenddateien.

Bosch Professional, HERO und Capmo dienen als fachliche Referenzen. Der aktuelle
Status der angeforderten Anbieterrecherche ist im Produktpaket offengelegt;
blockierte Webseiten werden nicht als gelesene Quellen ausgegeben.
