# Arbeitsauftrag für die Fortsetzung in Codex

## Verbindliche aktuelle Nutzerentscheidungen – 25. Oktober 2026

Dieser Abschnitt hat Vorrang vor dem unten erhaltenen historischen Auftrag.

- Gmail und WhatsApp Business sind die gewünschten Eingangskanäle. Der vorbereitete
  Gmail-Eingang nutzt eine gesondert einzurichtende, begrenzte Übergabe; eine
  WhatsApp-Business-Platform-Verbindung und Zugriff auf bestehende Chats sind
  damit nicht bereits eingerichtet.
- **Letzte Entscheidung zum Maileingang:** Der vorhandene Bot soll seine
  bestehende Mailanbindung verwenden und Anfragen selbstständig in Smartplan
  einliefern. Der manuelle Apps-Script-Aufbau wurde als zu kompliziert verworfen.
  Die Textübernahme in Smartplan wurde im echten Test bestätigt. Der Bot meldet
  einen aktiven Fünfminutenjob; eine zweite Mail wurde übernommen, ihre Anhänge
  fehlten jedoch im textbeschränkten 0.9-Eingang. Das zusammenhängende Paket
  0.10/Schema5 wurde ausgeliefert. Es enthält Blob-Upload,
  verifizierten Download, Projektablage, Plankopie und gezielten Altmailnachtrag.
  Server/App/Botauftrag gemeinsam aktualisieren; vorhandenen Job, gültigen
  Schlüssel und bestätigte Mail-IDs erhalten. Produktidentität ist nicht
  abschließend verifiziert, aber die vorhandene HTTP-Textanbindung ist belegt.
  Der Nutzer hat anschließend ausdrücklich bestätigt: Der Anhang ist jetzt in
  der Software vorhanden. Die mobile Geräteausgabe bleibt gesondert zu prüfen.
  Eine beiläufige Nennung von Salesforce ist keine beauftragte CRM-Umstellung.
- **Abgenommener App-Auftrag 0.10.1:** PDF- und Bildanhänge direkt in der Software ansehen
  können. Zugleich das unübersichtliche, als nicht zeitgemäß empfundene Design
  überarbeiten: stark an Apple angelehnt, intuitiver, etwas lebendig, aber mit
  zurückhaltenden Farben. Vorschau und neue Navigation/Gestaltung gemeinsam als
  App 0.10.1 wurden geliefert und vom Nutzer als passend und funktionierend
  bestätigt. Der bestehende Anhangserver und Bot genügten dafür.
- **sevdesk bleibt** das bestehende System für Angebote und Rechnungen. Die App
  ordnet Vorgänge und Links dem Projekt zu; eine Ablösung ist nicht beauftragt.
- **Aktueller autorisierter Auftrag: Integrationspaket 0.11** für Sevdesk,
  Google Kalender und die vorhandene Dokumentablage. Nutzerkorrektur ausdrücklich:
  **kein Dropbox, sondern OneDrive**; Google Kalender und OneDrive sind bereits
  im vorhandenen Mailbot verbunden. Die neue Metadatenbridge nutzt diese
  Verbindungen im selben Fünfminutenjob. Keine zweite Automatik oder zusätzlichen
  Google-/Microsoft-Appregistrierungen für den Standardweg verlangen.
- Neuer enger SPIX-Projektbotzugang ist vom vorhandenen SPIN-Maileingang getrennt.
  Geschäftsführung wählt Kalendertermine und OneDrive-Laufwerk/Ordner ausdrücklich;
  echte Datenlieferung bestätigt erst die Verbindung, wartende Daten nicht als
  erfolgreich leer darstellen. OneDrive öffnet Original-webUrl nach Nutzerklick;
  kein zusätzlicher Originalbytecache/-download oder externer Plananalysedienst.
- Sevdesk wird direkt lesend verbunden und bleibt führend. Einzelne Belege
  ausdrücklich je Projekt wählen; keine automatische Zuordnung aller
  Kundenvorgänge, kein Erstellen/Versenden/Bezahlen von Dokumenten.
- **Abläufe sind unterschiedlich und bleiben frei.** Anfrage, Kunde, Projekt,
  Aufmaß, Angebot, Zusage, Anzahlung und Material haben keine erzwungene
  Reihenfolge. Ein Projekt kann früh zur Klärung oder für einen Serviceeinsatz
  entstehen. Phase, Anzahlung und Materialstatus sind unabhängig pflegbar.
- Größere zusammenhängende und überprüfbare Pakete liefern, statt den Nutzer
  mit vielen kleinen manuellen Updates zu beschäftigen. Capmo, Bosch und HERO
  dienen als Orientierung für eine verständliche Projektarbeit.
- Bei **jeder Serveranleitung zuerst die SSH-Verbindung und das richtige Fenster
  erklären**: Verbindung aus Windows PowerShell, Linux-Befehle danach im
  verbundenen Serverfenster. Die bekannte Verbindung lautet:

  ```powershell
  ssh -i "$env:USERPROFILE\.ssh\smartplan_hetzner" root@office.smartplan-hofmann.de
  ```

- Planerkennung bleibt auf dem eigenen Hetzner-System, ohne externen KI-/OCR-
  Ausweichdienst. Neue Planquellen werden auf Handy/iPad zunächst verschlüsselt
  gespeichert und bei Verbindung synchronisiert. Sieben Tage Offline-Freigabe
  sind keine Löschfrist für bereits gespeicherte Eingaben.

## Bestätigter Betrieb und vorbereitetes Paket

Auf Hetzner läuft inzwischen bestätigt **0.9 / Commit `822fe58` / PostgreSQL-Schema 4**.
Die abschließende HTTPS-Prüfung zeigte Version 0.9.0-online-pilot, Datenbank
und Status ok; alle drei Dienste waren active. Die manuelle Anfrageerfassung
in der aktualisierten Windows-App funktioniert laut Nutzer.
Die synthetische Abnahme des geschützten Importdienstes unter der tatsächlichen
systemd-Unit auf Ubuntu 24.04 ARM64 ist bestanden. API, HTTPS und Importdienst
(`smartplan-online`, `smartplan-https`, `smartplan-plan-import`) wurden vom Nutzer
gemeinsam als `active` bestätigt; der Importdienst ist aktiviert.

**0.9 / Schema 4 wurde auf dem Nutzer-Server aktiviert.**
Das größere Paket verbindet Anfrageeingang, Projektmappe, Aufgaben, Termine,
Bautagebuch, Dokumentverweise und vorbereitete Offline-Projektarbeit. Die
Planansicht ist ruhiger, drehbar und löschbar; daraus wird noch keine vollständige
bearbeitbare CAD-Zeichnung. Der verwendete gebündelte Serverablauf steht unter
[UPDATE_0_9.md](deploy/hetzner/online/UPDATE_0_9.md). Bestehende App-Daten und
ausstehende Offline-Eingaben dürfen dafür nicht durch Neuinstallation oder
manuelles Löschen beseitigt werden.

**Die tatsächliche Anhangübernahme aus Paket 0.10 ist vom Nutzer bestätigt.**
Ein neuer HTTPS-Readiness-Auszug/Quellcommit wurde danach nicht separat gezeigt;
den alten ausgelesenen 0.9-Stand deshalb als historische Evidenz erhalten.
Maßgeblich für die Anhanggrundlage sind
[Produktpaket 0.10](PRODUKTPAKET_0_10.md) und
[Update 0.10](deploy/hetzner/online/UPDATE_0_10.md).
Mailanhänge werden als unveränderte Bytes auf Hetzner gespeichert; der externe
Bot verwendet dafür seine bereits vorhandene Gmail-Anbindung und führt keine
externe Plan-/Dokumentanalyse aus. Die Beschränkung der Planverarbeitung auf
den eigenen Hetzner-Server bleibt verbindlich.

Die anschließende [App-Erweiterung 0.10.1](ANHANGVORSCHAU.md) verwendet dieselben
geschützten Downloads für die Vorschau. Anfragen und ihre Originalanhänge
bleiben online; vorhandene Offline-Projektmappen und Planquellen unverändert.

**0.10.1 wurde anschließend als passend und funktionierend bestätigt.**
Das nun vorbereitete [Integrationspaket 0.11](INTEGRATIONSPAKET_0_11.md) benötigt
Schema 6 und einen gebündelten geschützten Server-/Appwechsel. Noch kein
Produktivupdate, keine echten Sevdesk-/Google-/Microsoftzugänge in der Cloud
verwendet. [Updateanleitung](deploy/hetzner/online/UPDATE_0_11.md) und
[Projektbotpaket](integrations/project_bot/README.md) gehören dazu. Die bestehende
Legacy-OneDrive-AppFolder-Berichtsablage bleibt ein gesonderter erhaltener Bereich.

Reale iPhone-/iPad-Abnahme und Windows-Herausgebersignierung bleiben offen.
Eine erfolgreiche Serverabnahme belegt weder Handschrift-/Wandsemantik noch
DXF-/DWG-Import oder einen bereits verbundenen externen Anbieter.

## Historischer Ausgangsauftrag – durch den aktuellen Abschnitt ergänzt

Die folgenden Abschnitte dokumentieren den frühen Ausgangsstand. Aussagen über
fehlende Builds, noch einzurichtendes Hosting, die damalige Ablagepriorität und
den „nächsten“ Arbeitsschritt sind **historisch**, keine aktuellen Anweisungen.

Thomas Hofmann möchte eine individuelle Unternehmenssoftware für Smartplan Hofmann,
ähnlich im Funktionsumfang wie HERO. Desktop zunächst ausschließlich Windows,
mobile App zunächst iPhone. Mehrere Benutzer mit individuell eingeschränkter Sicht
und Bearbeitungsrechten. OneDrive wird derzeit über Microsoft 365 Family genutzt.
Family jetzt anbinden; Business-Wechsel ausdrücklich später. Es gibt noch keine NAS;
eine NAS soll später als zusätzlicher Speicher angeschlossen werden können.

Gewünschte Gesamtfunktionen:

1. CRM mit Kunden, Kontakten, Anfragen, Angeboten und Projektkommunikation.
2. Projektmanagement und Ablaufplanung: Aufgaben, Termine, Meilensteine, Partner,
   Dokumente, Material, Zeiterfassung und Nachkalkulation. Keine Ablösung von
   ETS, DDS-CAD oder DIALux; deren Dateien/Bearbeitungsstände zuordnen.
3. Buchhaltung und Finanzen mit Belegen, Rechnungen und offenen Posten.
   sevdesk-Anbindung ist ein Architekturvorschlag, noch keine bestätigte endgültige Wahl.
4. Kontenanbindungen Qonto, AMEX und Sparkasse. Zunächst lesender Abruf und
   Zuordnung. Sparkasseninstitut, AMEX-Produkt und verfügbare Zugänge noch unbekannt.
5. Serviceberichte und Lieferscheine am iPhone mit zeichnerischer Unterschrift,
   Name, Zeit, bindender Dokumentversion und projektbezogener PDF-Ablage.
6. Mehrbenutzerrechte nach Modul, Aktion und Projekt; auch für Externe und Bots.
7. MCP-Client für externe Werkzeuge sowie eigener MCP-Server für kontrollierte
   Zugriffe auf Office. Grok Bots sollen integriert werden. Bestehende Bots
   zunächst über MCP anbinden, eingebettete native Bot-Chats nicht versprechen.
   Eigene Grok/OpenAI-Assistenten über APIs sind eine zusätzliche Möglichkeit.
8. WhatsApp Business: Text, Bilder, Dokumente und Sprachnachrichten auswerten und
   Projekten zuordnen. Bestehende Nummer mit Coexistence prüfen. Bedarf an bestehenden
   Gruppen noch klären; keinen vollständigen Zugriff auf alle alten Chats zusagen.
9. Mobile Offline-Nutzung mit Konflikterkennung und kontrolliertem Widerruf von
   Berechtigungen, Fotos und Sprachnotizen.
10. Austauschbare Dateiablage, zunächst OneDrive Personal, später NAS/Business.

## Historisch: erster vorhandener Stand

Siehe README. Backend mit Anmeldung, festen Rollen und Projektzuweisung; erste
Dokumentkette bis unterschriebenem PDF; Flutter-Oberfläche als unkompilierter
Quellcode; vorbereiteter OneDrive-OAuth-Adapter. Neun Backend-Tests bestanden.
Keine echten Kunden-, Bank- oder Microsoft-Daten eingefügt. Keine nativen Builds.
Kein Betriebssystemfenster oder lokaler Ordner auf Thomas' PC wurde hier eingerichtet.

## Historisch: damaliger nächster Arbeitsauftrag

Öffne dieses Projekt in Codex lokal. Lies README und diesen Auftrag. Prüfe die
Umgebung, richte Flutter-Platformgerüste ein und bringe `flutter analyze` sowie
einen Windows-Entwicklungsbuild zum Erfolg. Teste Anmeldung, Projektanlage,
Berichtsvorschau und Signatur auf Windows. Ergänze Benutzerverwaltung und
Projektzuweisung in der Oberfläche sowie PDF-Vorschau/Download.

Danach Microsoft-Appregistrierung und sichere Geheimniseingabe vorbereiten.
OneDrive Personal mit Thomas' Zustimmung verbinden und einen Bericht in den
eigenen App-Ordner hochladen; Ergebnis tatsächlich in OneDrive nachweisen.
Nicht unbemerkt auf Business umstellen. Für iPhone zunächst das Backend per
HTTPS in einer geeigneten Testumgebung bereitstellen; anschließend auf macOS
mit Xcode bauen und echte Unterschriftengesten testen.

Entwickle in überprüfbaren Etappen. Keine UI mit simulierten Live-Verbindungen
als fertig darstellen. Datenbank und Kontozugänge nicht in OneDrive synchronisieren.
MCP-Zugriffe müssen dieselben Backend-Rechte wie App-Benutzer respektieren.
Erste MCP-Funktionen: zugewiesene Projekte lesen und Berichtentwürfe erstellen;
für autonome Agenten keine Unterschriften im Namen eines Kunden erzeugen.

## Historisch: damals noch offene Angaben

- Anzahl und Namen der ersten Benutzer, Aufgaben und gewünschte Einzelrechte.
- Namen, Aufgaben und Zugangsmöglichkeiten der bestehenden Grok Bots.
- Sparkasseninstitut und AMEX-Kartenprodukt.
- Zugang zu Microsoft-Appregistrierung und späterer Hosting-/Apple-Buildumgebung.
- Nummer und Kontostatus für WhatsApp sowie Einzelchat-/Gruppenbedarf.
- Dokumentvorlagen, Briefkopf, Firmenadresse, Steuerdaten und Abrechnungsabläufe.

Grundlegende Entscheidungen sind Vorschläge, wo der Nutzer keine Vorgabe gemacht
hat: Flutter für beide Apps und Python/SQLite für den lokalen ersten Prototyp.
Die spätere Backend-Technologie darf nach Prüfung angepasst werden.
