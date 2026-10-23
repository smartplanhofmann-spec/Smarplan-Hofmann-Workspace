# Offline-Nutzung und Synchronisierung

Verbindlicher Nutzerwunsch vom 23. Oktober 2026: Die App auf iPhone und iPad
muss bei fehlendem Empfang weiterarbeiten, Eingaben dauerhaft lokal speichern
und bei wieder verfügbarer Verbindung synchronisieren. Bestätigte Dauer:
**bis zu sieben Tage nach erfolgreicher Online-Anmeldung**.
Die erste Umsetzung für Projektpläne ist automatisiert geprüft und mit Version
0.7 auf Hetzner bereitgestellt. Windows-Start und Anmeldung sind bestätigt;
die Offline-Geräteabnahme auf iPhone/iPad bleibt offen. Die übrigen Fachmodule
bleiben zunächst online.

**Neue Priorität:** Auch fotografierte oder importierte Originalpläne müssen
ohne Empfang zunächst dauerhaft und verschlüsselt erhalten bleiben. Dieser
Medienpfad ist noch nicht implementiert. Erkennung und Konvertierung laufen
nach Upload ausschließlich auf Hetzner, ohne externe Auswertungsdienste.
Siehe [Planimport und Digitalisierung](PLANIMPORT_UND_DIGITALISIERUNG.md).

## Verhalten für den Nutzer

- Bereits geladene beziehungsweise ausdrücklich offline bereitgestellte Projekte
  und zugehörige Inhalte sind vor Ort nutzbar. Noch nie geladene Serverdaten
  lassen sich ohne Verbindung nicht abrufen.
- Jede bestätigte Eingabe wird zuerst dauerhaft auf dem Gerät gespeichert.
  Das gilt auch bei schlechtem Empfang, App-Wechsel und einem Neustart der App.
  Eine nicht auf das Gerät geschriebene Eingabe darf nicht als gespeichert gelten.
- Sichtbare Zustände: **Lokal gespeichert**, **Wartet auf Verbindung**,
  **Wird synchronisiert**, **Synchronisiert**, **Konflikt** und gegebenenfalls
  **Anmeldung erforderlich**. Die Zahl ausstehender Änderungen bleibt sichtbar.
- Sobald Verbindung und gültige Anmeldung vorhanden sind, werden ausstehende
  Änderungen automatisch übertragen, auch beim erneuten Öffnen der App.
  iOS/iPadOS garantieren bei einer beendeten App keine sofortige Ausführung im
  Hintergrund; beim nächsten Öffnen muss die Übertragung zuverlässig fortsetzen.
- Die siebentägige Berechtigung wird nicht durch bloßes Offline-Öffnen verlängert.
  Nach ihrem Ablauf ist erneute Online-Anmeldung nötig. Lokale unübertragene
  Eingaben bleiben erhalten. Sitzungsablauf, Passwortwechsel oder Zugriffsentzug
  dürfen sie nicht stillschweigend löschen.
- Ein Geräte- oder Kontowechsel darf keine Warteschlange einem anderen Benutzer
  zuordnen. Abmeldung und Entfernen lokaler Daten müssen auf unübertragene
  Eingaben hinweisen. Ein Deinstallieren kann den lokalen App-Speicher löschen;
  es ist kein synchronisierender Vorgang.

## Geltungsbereich und Etappen

Der Wunsch betrifft die Arbeitsdaten der App, nicht nur den neuen Planeditor.
Der erste durchgehende Ausbau beginnt mit Projektplänen, danach folgen
Aufmaß, Berichts-/Lieferscheinentwürfe, Medien und weitere Fachmodule.
Nicht verfügbare Offline-Funktionen müssen ausdrücklich gekennzeichnet sein.
Online-Kontoverbindungen, Freigabe neuer Benutzer und Änderungen von
Berechtigungen benötigen weiterhin Serverkontakt.

Signierte Berichte werden nicht nachträglich bearbeitet. Eine Offline-Unterschrift
braucht einen eigenen Vertrag: lokale Erfassungszeit und tatsächliche spätere
Serverannahme sind verschieden. Es darf kein angeblich serverbestätigter
Unterschriftszeitpunkt erzeugt werden, solange der Server unerreichbar ist.
Diese Erweiterung ist separat zu implementieren und zu prüfen.

## Technischer Vertrag

1. Geschützter, konten- und servergetrennter lokaler Datenspeicher mit
   transaktionaler Warteschlange. Kein temporäres Verzeichnis und keine bloße
   Speicherung im Widget-Zustand. Geräteschutz und sicher gespeicherte
   Anmeldung/Offline-Freigabe gehören vor die Gerätefreigabe.
2. Jeder Auftrag erhält vor dem ersten Sendeversuch eine zufällige, stabile ID.
   Wiederholungen verwenden dieselbe ID und exakt denselben Inhalt. Server
   speichern Ergebnis und Auftrags-ID in derselben Transaktion wie die Änderung.
3. Synchronisierung erfolgt geordnet pro Objekt und mit begrenzten Wiederholungen.
   Ein Abbruch nach Serverannahme wird durch erneute Übertragung derselben ID
   geklärt. Änderungen während eines laufenden Uploads dürfen nicht als bereits
   übertragen markiert oder aus der Warteschlange entfernt werden.
4. Änderungen beziehen sich auf den geladenen Ausgangsstand. Ein neuerer
   Serverstand erzeugt einen Konflikt; lokale und serverseitige Fassungen bleiben
   erhalten. Kein stilles Überschreiben nach dem Prinzip „letztes Gerät gewinnt“.
5. Daten werden erst nach bestätigter Serverannahme als synchronisiert markiert.
   Netzwerkfehler sind von Validierungsfehlern, Konflikten, fehlender Anmeldung
   und entzogenem Projektzugriff zu unterscheiden. Bei den letzten Fällen sind
   unendliche automatische Wiederholungen zu vermeiden.
6. Projekt- und Benutzerrechte werden bei jeder Serverannahme erneut geprüft.
   Ein Gerät ohne Verbindung erfährt einen Fernwiderruf erst beim nächsten
   Kontakt beziehungsweise Ablauf der Offline-Freigabe. Die sieben Tage sind
   die gewählte maximale Offline-Dauer, keine Zusage sofortigen Fernwiderrufs.
7. Fotos, Audio und Video behalten lokale Originale bis zum bestätigten Upload.
   Prüfsummen, fortsetzbare Übertragung, Speicherplatzprüfung und erkennbare
   Fehler sind erforderlich. KI-Verarbeitung beginnt erst nach vollständigem
   Upload und erneuter Berechtigungsprüfung.

## Bereits implementierte Grundlage

Planstände sind serverseitig versioniert. Veraltete Änderungen erhalten 409.
Plan-Speicheraufrufe unterstützen eine optionale `request_id` aus 32 kleinen
Hexadezimalzeichen. Pro Benutzer werden Anfrageinhalt und Antwort atomar in
`plan_requests` festgehalten. Dieselbe ID mit gleichem Inhalt gibt die ursprüngliche
Antwort zurück, auch wenn die ursprüngliche Antwort das Gerät nicht erreicht hat.
Eine andere Verwendung derselben ID erzeugt 409. Projektzugriff und Schreibrecht
werden vor jeder Wiederholung geprüft. Für neue Offline-Clients ist die ID
verpflichtend; bestehende Clients ohne ID behalten ihr bisheriges Verhalten.

## Implementierte App-Stufe für Pläne

- Nach vollständiger Online-Anmeldung werden Benutzer und Projektübersicht
  für dieses Gerät gespeichert. Pläne werden beim Öffnen der Projektplanliste
  heruntergeladen. Noch nicht geladene Serverpläne sind entsprechend bezeichnet.
- Neue Pläne und jede abgeschlossene Wand-/Titeländerung werden zuerst lokal
  gespeichert. Währenddessen zeigt die App den laufenden Schreibvorgang; bei
  fehlendem Speicherplatz bleibt die Änderung als ungesichert erkennbar.
- AES-256-GCM schützt Inhalt und Integrität des lokalen Speichers. Der Schlüssel
  bleibt im Betriebssystem-Schlüsselspeicher, unter iOS nur auf diesem Gerät
  und nur im entsperrten Zustand. Unveränderliche, verschlüsselte Dateistände
  werden über temporäre Dateien veröffentlicht; der bisherige Stand bleibt
  bei Schreibfehlern erhalten. Fehlerhafte neueste Stände werden nicht still
  durch alte Daten oder einen leeren Speicher ersetzt.
- Der Einstieg **Offline-Pläne entsperren** verwendet Geräteauthentifizierung
  (Face ID, Touch ID beziehungsweise unterstützte Geräteanmeldung). Ohne
  erfolgreiches Entsperren oder nach sieben Tagen öffnet sich kein Offline-Bereich.
- Server und Konten besitzen getrennte Speicher und Warteschlangen. Abmeldung
  warnt bei ausstehenden Änderungen, sperrt den lokalen Einstieg und entfernt
  den Gerätezugang. Die Daten bleiben für erneute Online-Anmeldung erhalten.
- Nach erfolgreicher Online-Anmeldung gibt `POST /api/v1/offline/access` einen
  gesonderten siebentägigen Zugang aus. Er erlaubt ausschließlich das Lesen der
  erlaubten Projektübersicht und Planoperationen, keine Kundenverwaltung,
  Berichte, Benutzerverwaltung oder Erteilung weiterer Zugänge. Sein Wert liegt
  im geschützten Betriebssystem-Speicher; normale Sitzungstokens, Passwörter
  und MFA-Codes werden nicht in den Offline-Dateien gespeichert.
- Der Server speichert nur den Hash des Gerätezugangs in `plan_sessions`.
  Aktuelle Projektzuweisungen werden weiterhin geprüft. Passwort-/Rollenwechsel,
  Sperrung, MFA-Zurücksetzung und Datenbankwiederherstellung widerrufen die
  betreffenden Zugänge. Abmeldung widerruft den aktuellen Gerätezugang nach
  Möglichkeit auch serverseitig; ohne Empfang gilt die lokale Sperre sofort.
- Die Warteschlange friert Inhalt und Auftrags-ID vor dem ersten Sendeversuch
  dauerhaft ein. Spätere Änderungen werden getrennt angehängt. Automatische
  Versuche erfolgen beim Öffnen/Fortsetzen und alle 20 Sekunden bei laufender
  App; fehlende Anmeldung, Validierungsfehler und Konflikte werden unterschieden.
- Bei Konflikten bleiben lokale Zeichnung und Serverfassung erhalten. Die
  Planliste bietet einen Vergleich beider Zeichnungen und die Wahl, den
  Serverstand zu übernehmen oder den lokalen Entwurf als zusätzlichen Plan
  zu erhalten. Es gibt kein automatisches Überschreiben.

Die Uhrzeit wird auf Rücksprünge gegenüber dem zuletzt gespeicherten Zugriff
geprüft; ein Offline-Öffnen verlängert die Freigabe nicht. Server und Gerät
prüfen den Ablauf unabhängig. Ein verlorenes Gerät, eine Deinstallation oder
verlorene Geräteschlüssel ersetzen keine erfolgreiche Synchronisierung.

**Noch offen:** Geräteabnahme der neuen Plugins, Face ID/Gerätecode und
Schlüsselablage auf iPhone/iPad, Offline-Berichte, Aufmaß und Medien. Native
Builds bestanden; das Serverupdate wurde vom Nutzer ausgeführt und öffentlich
geprüft. iOS garantiert keine sofortige
Synchronisierung einer beendeten App. Ein erneut geöffnetes, berechtigtes Gerät
setzt die Warteschlange fort.

## Automatisierte Nachweise

Die App-Suite enthält Prüfungen mit echten verschlüsselten Dateien für Neustart,
verlorene Antworten, Änderungen während eines Uploads, Konflikte, Ablauf,
Kontowechsel, Uhrzeitrücksprung, beschädigte Dateien, Schreibfehler und bekannten
Zugriffsentzug. Ein Widgettest prüft automatische Speicherung von Titel und Wand;
ein separater Integrationstest überträgt nach einem simulierten Client-Neustart
einen Offline-Entwurf an einen echten Python-HTTP-Server. Der Schlüsselspeicher
und die Geräteauthentifizierung sind in diesen Cloud-Tests ersetzt; sie gelten
nicht als native Geräteabnahme.

## Erforderliche Abnahme

Auf iPhone und iPad mit fiktiven Daten: Projekt laden, Flugmodus aktivieren,
Plan bearbeiten, App beenden und neu öffnen, unveränderte lokale Daten prüfen,
Verbindung wiederherstellen und unter Windows denselben Stand öffnen.
Zusätzlich: Verbindungsabbruch nach Serverannahme, parallele Bearbeitung,
Sitzungsablauf, sieben Tage abgelaufene Offline-Freigabe, Zugriffsentzug,
Kontowechsel und voller Gerätespeicher. Kein Fall darf unübertragene Eingaben
verlieren oder fremde Daten freigeben. Automatisierte Tests ergänzen diese
Geräteabnahme; sie ersetzen sie nicht.
