# Arbeitsauftrag für die Fortsetzung in Codex

## Ziel und verbindliche Nutzerentscheidungen

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

## Erster vorhandener Stand

Siehe README. Backend mit Anmeldung, festen Rollen und Projektzuweisung; erste
Dokumentkette bis unterschriebenem PDF; Flutter-Oberfläche als unkompilierter
Quellcode; vorbereiteter OneDrive-OAuth-Adapter. Neun Backend-Tests bestanden.
Keine echten Kunden-, Bank- oder Microsoft-Daten eingefügt. Keine nativen Builds.
Kein Betriebssystemfenster oder lokaler Ordner auf Thomas' PC wurde hier eingerichtet.

## Nächster konkreter Arbeitsauftrag

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

## Noch offene Angaben - erst erfragen, wenn der jeweilige Schritt sie benötigt

- Anzahl und Namen der ersten Benutzer, Aufgaben und gewünschte Einzelrechte.
- Namen, Aufgaben und Zugangsmöglichkeiten der bestehenden Grok Bots.
- Sparkasseninstitut und AMEX-Kartenprodukt.
- Zugang zu Microsoft-Appregistrierung und späterer Hosting-/Apple-Buildumgebung.
- Nummer und Kontostatus für WhatsApp sowie Einzelchat-/Gruppenbedarf.
- Dokumentvorlagen, Briefkopf, Firmenadresse, Steuerdaten und Abrechnungsabläufe.

Grundlegende Entscheidungen sind Vorschläge, wo der Nutzer keine Vorgabe gemacht
hat: Flutter für beide Apps und Python/SQLite für den lokalen ersten Prototyp.
Die spätere Backend-Technologie darf nach Prüfung angepasst werden.
