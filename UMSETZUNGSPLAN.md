# Smartplan Office – konkreter Umsetzungsplan

Aktualisiert: 23. Oktober 2026. Die ursprüngliche Planung vom 14. Oktober bleibt
als Rahmen erhalten; der aktuelle Abnahmestand steht unmittelbar darunter.
Kontoverbindungen, Hosting-Buchungen und Apple-Mitgliedschaften erfordern jeweils
einen konkreten Auftrag. Die laufende Entwicklung im freigegebenen GitHub-Branch
ist bereits beauftragt.

## Aktueller Abnahmestand

Die lokale Windows-Stufe mit GUI 0.3.0 wurde vom Nutzer bestätigt: Anmeldung,
Projektanlage, Servicebericht, Unterschrift, PDF-Ausgabe, Benutzerverwaltung,
Technikerzuweisung und Entzug des Projektzugriffs. Auch die neue Oberfläche,
der gemeinsame Start per `Starten.cmd`, die manuelle Sicherung und die
Wiederherstellung einschließlich erneutem Öffnen der vorhandenen Daten/PDFs
wurden im Gespräch erfolgreich zurückgemeldet. Die neuen Prüfabläufe müssen
nicht erneut von Anfang an durchlaufen werden.

Die technische Grundlage ist vorhanden: Backend mit 24 Testfällen (unter Linux
wird der eine Windows-spezifische Fall übersprungen), 18 erfolgreiche App-Tests
einschließlich echtem Python-Backend sowie erfolgreiche Windows-Release- und
iOS-Simulator-Builds im GitHub-Lauf `39416338557`. Für die Rolle Buchhaltung,
Sitzungssperren und unveränderliche Signaturdaten liegen automatisierte
Prüfungen vor; eine gesonderte manuelle Buchhaltungs-Abnahme wurde nicht behauptet.

Inzwischen ist auch der Online-Pilot mit PostgreSQL, MFA und HTTPS auf dem
Hetzner-CAX11 in Nürnberg eingerichtet. Windows und die über TestFlight
installierte iPhone-App arbeiten nach Nutzerbestätigung auf demselben Projekt.
Der am iPhone unterschriebene Bericht wird unter Windows als PDF geöffnet.
Das separate Signaturfenster im Querformat (0.5.1) ist ebenfalls vom Nutzer
abgenommen. Die Rechteprüfungen sollen laut Nutzer nicht erneut durchgeführt
werden: Sie seien bereits getestet. Einzelbelege:
[Pilot- und Geräteabnahme](deploy/hetzner/ABNAHME.md).
Die nächste Stufe und ihre Voraussetzungen stehen in
[BETRIEB_UND_IPHONE.md](BETRIEB_UND_IPHONE.md).

**Aktuelle Architekturentscheidung vom 23. Oktober:** Projektmanagement,
Benutzer, Datenbank und die ursprünglichen signierten PDFs bleiben auf Hetzner.
Unterschriebene PDFs werden auf Wunsch zusätzlich in einer wählbaren
Dokumentablage gespeichert, beispielsweise in je einem Projektordner auf
OneDrive. OneDrive ist optional; Speicheradapter erlauben auch Serververzeichnisse
und HTTPS-WebDAV-Ziele (Cloud/NAS). Der Betriebsort der Datenbank und die
zusätzliche Dokumentablage sind getrennte Entscheidungen. Ein NAS als PDF-Ablage
bedeutet nicht, dass die gesamten Smartplan-Daten beim Nutzer vor Ort liegen.

**Aktuelle Reihenfolge nach Nutzerkorrektur vom 23. Oktober:**
Planimport und Digitalisierung haben Vorrang vor dem weiteren Ausbau des freien
Wandeditors. Der Nutzer kann in 0.7 zeichnen, lehnt diesen Hauptablauf aber ab.
Zuerst abfotografierte Papierpläne mit handschriftlichen Ergänzungen sowie PDF,
danach DXF und lokal konvertierbares DWG. **Die Erkennung bleibt auf Hetzner;
die vorher kurz erwogene Nutzung externer KI-Dienste wurde zurückgenommen.**
Das Ziel umfasst Originalerhalt und verschlüsselte Aufnahmen auf Handy/iPad
ohne Empfang. Ablauf, Datenvertrag und erste Qualitätsabnahme:
[Planimport und Digitalisierung](PLANIMPORT_UND_DIGITALISIERUNG.md).

Neu implementiert ist der getrennte
[Linux-CLI-Importkern](backend/plan_import/README.md) für JPEG/PNG/PDF:
Original mit Prüfsumme, PDF-Seitenwahl, Vorschau, lokale Linienkandidaten und
Tesseract-Drucktext sowie eine HTML-Prüfansicht mit Status `needs_review`.
67 Tests bestanden im netzlosen Docker-Lauf. Kamera, Offline-Medien, Upload,
Office-API/-Datenbank-Anbindung, Wand-/Handschriftsemantik und DXF/DWG bleiben
offen. Der Kern ist nicht auf Hetzner bereitgestellt; der produktive Stand 0.7
bleibt unverändert.

Die bereits vorbereiteten optionalen Speicheranschlüsse bleiben bestehen;
eine echte Kontoverbindung ist weiterhin ein gesonderter Schritt.
Die Bestellübersicht des vorhandenen Servers lag bei 9,15 Euro brutto monatlich
inklusive Hetzner-Backups und IPv4. Für den bisherigen Onlinebetrieb war kein
weiterer Server erforderlich. Der Ressourcenbedarf lokaler Planerkennung wird
vor Auswahl größerer Modelle gesondert geprüft; eine Aufrüstung ist nicht bestellt.
Echte OneDrive-Zustimmung, getrennte Sicherungswiederherstellung, Betriebsbetreuung
und die übrigen Fachmodule bleiben offen. Version 0.4.0 enthält die erste lokale
Kundenstufe aus Etappe 3, noch keine vollständige CRM-/Angebotslösung.
Details und Geräteabnahme stehen in [KUNDENVERWALTUNG.md](KUNDENVERWALTUNG.md).
Die übrigen Fachmodule bleiben offen.

## Zielbild und Rahmen

**Früherer Rahmen vom 23. Oktober, für Planimporte inzwischen konkretisiert:**
Der Nutzer möchte größere gemeinsame Updates
und mehrere KI-Assistenten, darunter eigene vorhandene Bots und Anbieter wie
OpenAI, Anthropic und xAI. Konkret gewählt sind Sprache/Fotos/Videos für Aufmaß,
bearbeitbare Pläne aus Skizzen und vorhandenen Unterlagen sowie das Positionieren
von Geräten und Notizen durch Antippen und Sprache. Routinearbeiten sollen
automatisch nach Regeln laufen, wichtige Aktionen mit Freigabe. Genannte
Assistenten: Grok-Bot, „ChatGPT Work“ und Codex. iPhone: 17; die Grundfunktionen
setzen LiDAR nicht voraus. Erste Ausgaben: DXF und PDF, DWG optional über einen
geeigneten Anschluss. Konzepte: [KI_AGENTEN.md](KI_AGENTEN.md) und
[AUFMASS_UND_PLAENE.md](AUFMASS_UND_PLAENE.md). Diese früher genannten externen
Anbieter sind keine Freigabe für Planfotos und -unterlagen: Für den jetzigen
Import-/Digitalisierungsablauf gilt ausschließlich Hetzner-Verarbeitung.
Das Serverupdate 0.7 wurde inzwischen vom Nutzer ausgeführt und öffentlich
mit Schema 2, Plan- und Offline-Fähigkeiten bestätigt. Echte Kontoverbindungen
zu optionalen Ablagen bleiben davon getrennt zu prüfen.

Smartplan Office wird die gemeinsame Arbeitsoberfläche für Büro und Baustelle: Windows im Büro, iPhone unterwegs. Kunden, Projekte, Aufgaben, Zeiten, Materialien und Dokumente bilden eine zusammenhängende Datenbasis. Funktionen und Datenzugriff hängen von Rolle, Projektzuordnung und später Einzelrechten ab.

Festgehaltene Vorgaben aus dem gelieferten Projekt: Windows und iPhone zuerst; OneDrive Personal/Family zunächst als Dokumentablage; Business und NAS später; keine Ablösung von ETS, DDS-CAD oder DIALux. Diese Vorgaben sind die Planungsbasis und bei Bedarf mit dem Nutzer zu bestätigen. sevdesk ist ein Vorschlag, keine festgelegte Anbieterentscheidung.

Die vollständige Software entsteht in abnehmbaren Etappen. Der erste interne Einsatz umfasst Projekte und Berichte. Der volle Funktionsumfang ist erst erreicht, wenn auch die benötigten realen Integrationen und Offline-Abläufe abgenommen sind. Ein interner Pilot, eine veröffentlichte App und ein produktiver Mehrbenutzerbetrieb sind unterschiedliche Meilensteine.

## Ursprünglicher Ausgangsstand vom 14. Oktober 2026

Vorhanden sind Python/SQLite, REST-Endpunkte, Passwortanmeldung, vier feste Rollen, Projektzuweisungen, Berichts- und Lieferscheinentwürfe, Unterschrift und PDF-Erzeugung sowie ein vorbereiteter OneDrive-Adapter. Neun Backend-Tests bestanden in der Cloud. OneDrive-Antworten sind simuliert. Der lokale Server beantwortet den Gesundheitscheck und weist unberechtigte Projektzugriffe zurück.

Flutter-Quellcode ist vorhanden, aber nicht kompiliert oder auf Geräten geprüft. Plattformgerüste, Windows-Installer und iPhone-Paket fehlen. Die Oberfläche bietet noch keine vollständige Benutzerverwaltung, Projektzuweisung oder PDF-Anzeige. Es gibt keine produktive Bereitstellung, Live-Integrationen oder Offline-Synchronisierung.

Das ausgewählte GitHub-Repository ist leer. Die gelieferten Quellen liegen derzeit unter `/workspace/local-setup/smartplan-office`. Vor Entwicklungsbeginn werden diese Quellen kontrolliert in das bestehende Repository übernommen, Setup-Pfade angepasst und überprüft. Die ursprüngliche ZIP-Datei bleibt als Referenz erhalten. Git-Push oder Veröffentlichung erfolgt erst auf ausdrücklichen Auftrag.

## Vorgeschlagene Architektur

- Oberfläche: Flutter für Windows und iOS; getrennte Plattformpakete, gemeinsame Fachlogik. Eine Browser-App ist zunächst kein Pflichtziel.
- Backend: Python mit einem produktionsgeeigneten API-Framework und dokumentierten Endpunkten. Der vorhandene Standardbibliothek-HTTP-Server bleibt ausschließlich Entwicklungsprototyp.
- Datenbank: PostgreSQL für zentralen Mehrbenutzerbetrieb, versionierte Migrationen; SQLite für lokale mobile Offline-Daten und gegebenenfalls den frühen Pilot.
- Dateien: austauschbarer Ablageadapter. OneDrive Personal zuerst, Business/NAS später. Die Datenbank wird nicht über OneDrive synchronisiert. Dateiversionen, Berechtigungen und Integritätswerte verwaltet das Backend.
- Betrieb: HTTPS, zentrale Konfiguration, Hintergrundjobs für Imports/Uploads, Protokollierung ohne Geheimnisse, gesicherte Backups und Wiederherstellung. Hosting-Anbieter und Betriebskosten werden vor Bestellung entschieden.
- Anmeldung: für den produktiven Betrieb zentrale Identität mit MFA und kontrollierbaren Sitzungen. Anbieterwahl nach Nutzerkreis und Microsoft-Zugang; keine pauschale Festlegung auf einen kostenpflichtigen Dienst.
- Integrationen: getrennte Adapter mit begrenzten Berechtigungen, nachvollziehbaren Wiederholungsregeln und Testumgebungen. Externe Ausfälle dürfen lokale Arbeitsdaten nicht verlieren.

Vor dieser Architekturentscheidung wird eine kurze technische Prüfung durchgeführt: Flutter-Windows-Build, iOS-Build auf macOS, Hintergrundsynchronisierung, PDF-Anzeige und sichere Gerätespeicherung. Versionen werden auf tatsächlich verfügbare, kompatible Releases festgelegt; die im README genannte Flutter-Version ist noch nicht verifiziert.

## Fachmodule und Abnahme

| Modul | Geplanter Umfang | Konkrete Abnahme |
| --- | --- | --- |
| Anmeldung und Rechte | Benutzer einladen/anlegen, deaktivieren, Rollen und Projektzuordnung; später Einzelrechte je Modul/Aktion und externe Partner | Ein Techniker erhält nur zugewiesene Projekte. Deaktivierung sperrt bestehende Sitzungen. Ein externer Partner sieht ausschließlich freigegebene Inhalte; Download und API beachten dieselben Rechte. |
| CRM | Kunden, Ansprechpartner, Adressen, Anfragen, Notizen, Aktivitäten, Suche, Dublettenbehandlung | Eine Anfrage wird einem Kunden zugeordnet und ohne doppelte Stammdaten in ein Angebot und Projekt überführt. |
| Angebote | Positionen, Mengen, Einheiten, Preise, Steuern, Versionen, Status und PDF; Übernahme angenommener Angebote | Eine Angebotsversion bleibt nachvollziehbar; Annahme übernimmt Positionen und Kalkulationsgrundlage in das Projekt. Nummern- und Steuerregeln werden mit dem Buchhaltungssystem abgestimmt. |
| Projekte und Planung | Status, Verantwortliche, Aufgaben, Termine, Meilensteine, Partner, Dokumente, Tages-/Wochenansicht | Eine zugewiesene Aufgabe erscheint beim richtigen Benutzer; Terminänderungen werden konsistent auf beiden Geräten sichtbar. |
| Dokumente und Fachdateien | Upload, Versionen, Zuordnung, Suche; ETS/DDS-CAD/DIALux-Dateien als Dateien und Bearbeitungsstände | Eine neue Dateiversion ersetzt nicht unbemerkt die alte. Herunterladen ist nur mit Projektberechtigung möglich. Keine Bearbeitungsfunktion dieser Fremdprogramme wird versprochen. |
| Serviceberichte und Lieferscheine | Listen vorhandener Berichte, Entwürfe, Prüfung, Unterschrift, Name/Zeit, PDF-Vorschau und Download | Bericht am iPhone erstellen und unterschreiben; dasselbe unveränderte PDF unter Windows öffnen. Eine Korrektur erzeugt eine neue nachvollziehbare Fassung. |
| Zeit und Material | Zeiterfassung je Projekt/Aufgabe, manuelle Korrektur mit Historie, Materialpositionen, Verbrauch, Freigabe | Erfasste Zeiten und Materialien fließen ohne Doppelzählung in Projektübersicht und Nachkalkulation ein. Arbeitszeitregeln und Bewertungsgrundlagen sind festgelegt. |
| Finanzen | Belege, Rechnungs-/Zahlungsstatus, offene Posten, Zuordnung, Kosten und Nachkalkulation; abgestimmte Buchhaltungsanbindung | Ein Beleg ist einem Projekt zugeordnet; Rechnung und Zahlung sind abgestimmt. Es gibt eine festgelegte führende Quelle für Rechnungsnummern, Steuerlogik und Buchungsdaten. |
| Banken | Zunächst lesender Abruf von Qonto, AMEX und passender Sparkasse; Konten, Transaktionen, Zuordnung und Importhistorie | Reale freigegebene Transaktionen werden importiert; erneuter Import erzeugt keine Duplikate. Fehlende Anbieterabdeckung wird sichtbar ausgewiesen. |
| OneDrive und spätere Ablagen | Personal-OAuth, Verbindungsstatus, erneute Anmeldung, Upload-/Fehlerstatus; austauschbarer Speicher | Ein echter Bericht wird nach Zustimmung im eigenen Microsoft-App-Ordner gefunden. Abgelaufene Anmeldung und fehlgeschlagener Upload werden korrekt behandelt. Bestehende Ordner benötigen einen eigenen Importentscheid. |
| WhatsApp Business | Autorisierte Eingangsnachrichten, Bilder, Dateien, Sprachnachrichten; Vorschläge zur Projektzuordnung und Bearbeitung | Eine echte freigegebene Nachricht wird genau einmal übernommen; ein Mitarbeiter bestätigt die Zuordnung. Umfang hängt von Nummer, Anbieter und Coexistence-Unterstützung ab. |
| Kalender | Projekttermine, persönliche Zuordnung, Erinnerungen; externe Synchronisierung nach Anbieterentscheidung | Eine Änderung wird ohne Endlosschleife synchronisiert; Konflikte und Zeitzonen werden nachvollziehbar behandelt. |
| KI und Grok Bots | Projektbezogene Assistenz, Dokument-/Sprachauswertung, kontrollierte Werkzeugaufrufe; zunächst MCP-Anbindung vorhandener Bots, falls unterstützt | Der Assistent kann keine fremden Projekte lesen. Vorschläge sind prüfbar; Änderungen mit relevanten Auswirkungen benötigen Bestätigung. Fehler dürfen keine erfundenen Live-Ergebnisse anzeigen. |
| MCP | Client für ausgewählte externe Werkzeuge und eigener Server für freigegebene Office-Funktionen | Erste Werkzeuge: zugewiesene Projekte lesen und Berichtentwürfe erstellen. Rechte gelten pro Aufruf; Agenten können keine Kundenunterschrift erzeugen. |
| Offline | Lokale freigegebene Daten, Entwürfe, Zeiten, Fotos und Sprachnotizen; Warteschlange und Konfliktanzeige | Ein Auftrag wird ohne Netz bearbeitet und nach Wiederverbindung ohne Verlust oder Duplikate synchronisiert. Rechteentzug wird bei Verbindung durchgesetzt; zulässige Offline-Dauer ist vorher festgelegt. |

## Umsetzung in Etappen

### 0 – belastbare Entwicklungsbasis

Quellen in das Repository übernehmen, README und Setup-Pfade konsolidieren, Werkzeugversionen festlegen, CI für Backend und Flutter einrichten, native Gerüste ohne Verlust eigener Dateien erstellen. Authentifizierung, Rechte, Dateipfade und API-Methoden gezielt prüfen. Plattformvoraussetzungen und gewünschte Verteilung klären.

Abnahme: Backend-Tests laufen im Repository; Flutter-Analyse und relevante UI-Tests laufen; eine Windows-Entwicklungsapp startet. Ein erster iOS-Build auf macOS beweist die Plattformgrundlage. Fehlende Buildmaschinen werden als konkrete Voraussetzung ausgewiesen.

### 1 – erste nutzbare Version: Projekte und Berichte

Benutzerverwaltung und Projektzuweisung in der Oberfläche; Berichtslisten, erneut öffnbare Entwürfe, Unterschrift, PDF-Anzeige/Download; klare Lade-/Fehlerzustände; OneDrive-Verbindungsstatus. Sichere Ersteinrichtung ohne Standardpasswort. Wiederherstellbare Datensicherung für den Pilot.

Abnahme: Geschäftsführung legt Projekt und Techniker an, weist das Projekt zu; Techniker erstellt einen Bericht; Kunde unterschreibt; das PDF ist unter Windows wieder abrufbar. Buchhaltung liest Dokumente, kann sie nicht unterschreiben. Eine fremde Projekt-ID bleibt auch über direkte API-Aufrufe gesperrt.

### 2 – zentraler Mehrbenutzerbetrieb und echte OneDrive-Anbindung

Produktions-API, PostgreSQL/Migrationen, HTTPS-Testbereitstellung, produktive Anmeldung/MFA, Sitzungskontrolle, Jobverarbeitung, Backups. Microsoft-Appregistrierung und unterstützte sichere Laufzeitbereitstellung der Schlüssel; OneDrive Personal live verbinden. Die lokale Callback-Adresse aus dem Prototyp wird für den geplanten Betrieb passend ersetzt.

Abnahme: Windows und iPhone arbeiten auf denselben Projektdaten. Echte Dateiablage, erneute Anmeldung und fehlgeschlagene Uploads sind getestet. Ein Backup wird in einer getrennten Testinstanz erfolgreich wiederhergestellt. Der App-Ordner ist keine Sicherung der gesamten Datenbank.

### 3 – CRM, Angebote und Projektplanung

Kunden/Ansprechpartner/Anfragen, Angebote, Aufgaben, Termine, Partner und Fachdateien. Zusammenhängender Ablauf von Anfrage bis Auftrag. Rechte und Suchergebnisse gelten durchgängig über alle neuen Module.

Abnahme: Ein realistischer Musterauftrag durchläuft Anfrage, Angebot, Annahme, Planung und Dokumentablage. Unberechtigte Benutzer erhalten keine Ergebnisse aus gesperrten Projekten.

### 4 – Zeiten, Material, Offline und mobile Erfassung

Zeiterfassung und Materialverbrauch, Freigaben, Fotos/Sprachnotizen; lokale verschlüsselte Speicherung, Synchronisierung und Konfliktbehandlung. Ein Offline-Signaturablauf benötigt eine gesonderte Festlegung zu Version, Gerätezeit, Serverempfang und endgültiger Ablage. Bis zur Abnahme bleiben verbindliche Signaturen online.

Abnahme: Flugmodus, App-Neustart, abgebrochener Upload, parallele Änderungen und Rechteentzug werden auf einem echten iPhone geprüft. Synchronisierung verliert keine bestätigten Eingaben und kennzeichnet ungelöste Konflikte.

### 5 – Finanzen, Buchhaltung und Banken

Buchhaltungsanbieter und führende Datenquelle festlegen, Belege/Rechnungen/offene Posten integrieren; Qonto, AMEX und konkrete Sparkasse auf verfügbare Zugänge prüfen. Unterstützte API oder Anbieter verwenden. Ein kontrollierter CSV-Import kann eine Übergangslösung sein und wird entsprechend bezeichnet. Zunächst keine Zahlungsauslösung.

Abnahme: Musterrechnung, Teilzahlung und Projektkosten stimmen mit dem führenden Buchhaltungssystem überein. Wiederholte Imports sind idempotent. Mindestens ein realer freigegebener Kontoabruf je geforderter Anbindung ist nachgewiesen oder die konkrete Anbietergrenze dokumentiert und entschieden.

### 6 – Kommunikation, Kalender, MCP und KI

WhatsApp-Zugang/Coexistence, Kalenderanbieter und Bot-Zugänge prüfen; Webhooks und Zuordnungsoberfläche umsetzen. MCP-Funktionen mit denselben Rechten wie die App; KI-Vorschläge und kontrollierte Schreibaktionen. Gesprächsinhalte, Transkripte und KI-Kosten erhalten definierte Aufbewahrungs- und Nutzungsregeln.

Abnahme: Reale autorisierte Nachrichten und Termine erreichen das richtige Projekt; wiederholte Webhooks erzeugen keine Duplikate. Bots sehen ausschließlich freigegebene Daten. Externe Dokumenttexte können keine Rechte oder Bestätigungspflichten außer Kraft setzen.

### 7 – Betrieb und vollständige Freigabe

**Für das nächste Windows-Update nach Teststand 0.7.0 fest eingeplant
(Nutzerwunsch vom 22. Oktober, erneut bestätigt am 23. Oktober 2026):**
Die SmartScreen-Warnung des heruntergeladenen Online-Testpakets bearbeiten.
Vertrauenswürdige Authenticode-Signierung der EXE und eines Installationspakets
mit festem Herausgeber und Zeitstempel vorbereiten; Signatur im Release prüfen
und das tatsächlich heruntergeladene Paket auf einem Windows-PC abnehmen.
Zertifikats-/Signierdienst, Herausgebernachweis, Kosten und sichere Bereitstellung
der Signierzugänge sind vor einer Buchung konkret zu klären. Eine gültige
Signatur garantiert keine sofortige SmartScreen-Reputation. Die Warnung durch
Abschalten von SmartScreen oder Entfernen der Downloadmarkierung zu umgehen
gilt nicht als Lösung. Der Nutzer hat das damalige Paket am 22. Oktober manuell gestartet;
die Behebung ist noch offen.

Am 23. Oktober zeigt auch das Online-Paket 0.7.0 aus dem geprüften Build
`39977162879` weiterhin „Unbekannter Herausgeber“. Der Nutzer verlangt erneut:
„bitte beim nächsten Update berücksichtigen“. Die Signierung ist damit ein
offener Abnahmepunkt für das nächste Windows-Update; das aktuelle Paket ist
keine Behebung dieser Rückmeldung.

Für den Abschluss dieser Aufgabe müssen folgende Nachweise vorliegen:

- App-EXE und Installationspaket besitzen gültige, öffentlich vertrauenswürdige
  Authenticode-Signaturen mit dem vereinbarten Herausgeber und Zeitstempel.
- Die Releaseprüfung bestätigt Signaturstatus, Herausgeber und unveränderte
  Paketdateien. Ein bloßer Firmenname in den EXE-Eigenschaften reicht nicht aus.
- Das tatsächlich neu heruntergeladene Paket wird auf dem Windows-Rechner des
  Nutzers geprüft. Ein trotz gültiger Signatur verbleibender SmartScreen-Hinweis
  wird ausdrücklich dokumentiert; die Warnung gilt dann weiterhin nicht als behoben.

Die Umsetzung beginnt mit einem konkreten Vorschlag für Signierdienst,
Identitätsnachweis, sichere CI-Anbindung und Kosten. Eine kostenpflichtige
Bestellung ist damit noch nicht beauftragt.

Installer/Updates für Windows, iPhone-Verteilung zunächst über geeigneten Testweg und anschließend den gewählten regulären Weg; Dokumentation, Datenübernahme, Supportabläufe, Last-/Rechtetests, Backup/Restore und Pilot mit echten Anwendern. Business/NAS wird als spätere Erweiterung separat abgenommen.

Abnahme: Die tatsächlich benötigten Funktionen jeder vorigen Etappe bestehen ihre Abnahme; bekannte Einschränkungen sind entschieden; Wiederherstellung und Updates sind erprobt; Pilotanwender können die vereinbarten Alltagsabläufe ohne Entwicklerhilfe durchführen. Keine Behauptung rechtlicher Konformität allein aufgrund technischer Tests.

## Reihenfolge und Abhängigkeiten

0 → 1 → 2 bilden den Weg zum gemeinsamen internen Einsatz. Darauf bauen 3 und 4 auf. 5 benötigt die Anbieterentscheidungen und Stammdaten aus 3; 6 benötigt Zugänge und das durchgängige Rechtemodell. 7 begleitet alle Etappen und schließt die Freigabe ab.

Integrationsprüfung beginnt früh, damit nicht erst am Ende auffällt, dass eine gewünschte Bank oder bestehende WhatsApp-Nummer keinen geeigneten Zugang bietet. NAS/Business bleiben außerhalb der ersten Gesamtfreigabe, solange diese spätere Erweiterung nicht zusätzlich beauftragt wird.

## Wichtige technische Entscheidungen

1. Rechte: vier vorhandene Rollen dienen als Ausgangspunkt. Vor Einzelrechten wird eine Matrix pro Modul, Aktion, Projekt und externem Partner beschlossen. Die API ist die maßgebliche Prüfung, nicht allein die Sichtbarkeit eines Buttons.
2. Datenverantwortung: Smartplan führt Projektarbeit; ein gewähltes Buchhaltungssystem kann Rechnungen/Buchungen führen. Schreibrechte und Konfliktregeln werden pro Datentyp festgelegt.
3. Unterschriften: zeichnerische Signatur mit gebundener Dokumentversion und Historie. Eine qualifizierte elektronische Signatur ist ein anderes Produkt und bei Bedarf separat zu integrieren.
4. Offline: sofortiger Fernwiderruf kann ein Gerät ohne Verbindung nicht erreichen. Begrenzte Offline-Freigabe, lokale Datensicherung und Verhalten bei Ablauf werden vor Umsetzung entschieden.
5. Dateiimport: OneDrive-App-Ordnerzugriff gewährt keinen vollständigen Zugriff auf bestehende Firmenordner. Import und weitergehende Berechtigungen benötigen einen eigenen vereinbarten Umfang.
6. Geheimnisse: nur über unterstützte sichere Konfiguration; nicht im Chat, Repository oder Setup-Skript. Lokale Verschlüsselungsschlüssel benötigen geeignete sichere Bereitstellung und Sicherung, keine erfundenen Platzhalter als produktive Lösung.

## Noch benötigte Entscheidungen – zum passenden Zeitpunkt

| Zeitpunkt | Benötigte Angabe | Warum |
| --- | --- | --- |
| Vor Etappe 0/1 | Windows-Version, vorhandener Mac-/Xcode-Zugang, iPhone-Testgerät; Anzahl interner Nutzer und erste Rollen | Build- und Testweg sowie Pilotumfang festlegen |
| Vor Etappe 1 | Firmen-/Briefkopfdaten und gewünschte Berichts-/Lieferscheinvorlage | Nutzbare Dokumente statt einer Muster-PDF |
| Vor Etappe 2 | Hosting/Budget/Datenschutzvorgaben, Microsoft-Appregistrierung, gewünschte Anmeldung, Apple-Verteilung | Gemeinsamer Betrieb und sichere reale Zugänge |
| Vor Etappe 3 | Aktuelle Kunden-/Projektlisten, Angebotsablauf, Nummern-/Preis-/Steuerregeln | Stammdaten und Arbeitsablauf passend abbilden |
| Vor Etappe 4 | Zeit-/Materialregeln, benötigte Offline-Dauer und Freigabeverfahren | Kalkulation und Konfliktregeln verbindlich machen |
| Vor Etappe 5 | Tatsächlich verwendete Buchhaltungssoftware, Sparkasseninstitut, AMEX-Produkt, Qonto-Zugangsmöglichkeiten | Machbarkeit und verfügbare APIs feststellen |
| Vor Etappe 6 | WhatsApp-Nummer/Kontostatus und Gruppenbedarf, Kalenderanbieter, Namen/Funktionen/Zugänge bestehender Grok Bots | Unterstützten Integrationsumfang bestimmen |

Passwörter, Tokens und Schlüssel werden ausschließlich über sichere Einstellungen eingegeben. Diese offenen Angaben blockieren die Planung nicht; sie blockieren erst ihre jeweilige Umsetzung oder Live-Abnahme.

## Aufwand und Arbeitsmodus

Eine seriöse Termin- und Kostenzusage ist mit dem vorhandenen Prototyp und ungeprüften externen Zugängen noch nicht möglich. Der gesamte Umfang ist ein Entwicklungsprojekt über mehrere Monate; dieser Größenrahmen ist keine zugesagte Lieferzeit. Besonders Offline, Bankabdeckung, WhatsApp und native Verteilung bestimmen den Aufwand.

Nach Etappe 0 und der Integrationsprüfung wird jede Etappe in kleine Arbeitspakete mit Aufwand, Abhängigkeiten und Verantwortlichen zerlegt. Pro Paket: konkrete Änderung, automatisierte Tests soweit sinnvoll, relevanter Geräte-/Integrationstest und nachvollziehbares Ergebnis. Fehlende Zugänge werden früh gemeldet; unabhängige Arbeiten gehen weiter. Keine Funktion wird durch Demo-Daten als live fertig ausgewiesen.

Etappe 2 besitzt inzwischen einen auf Windows und iPhone bestätigten gemeinsamen
Online-Piloten. Domain, Tarif und TestFlight-Zugang sind eingerichtet. Die erste
lokale Kundenstufe aus Etappe 3 ist bereits umgesetzt. Weitere Angaben werden
gezielt für die nächste Integration eingeholt; reale Speicherverbindungen,
Betriebsverantwortung und die Abnahme der übrigen Fachmodule bleiben offen.
