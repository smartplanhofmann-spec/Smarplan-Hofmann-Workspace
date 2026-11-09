# Offene native Material- und Kilometeraufträge nach Neustart

Gesamtziel §7/9/11, R07.01/R09.02: Auf gebundenen Onlineservern speichert die
native App den vollständigen bestätigten Originalauftrag verschlüsselt, bevor
sie ihn sendet. Ein verlorener Antwortweg und ein vollständiger Neustart von
Controller und angemeldeter Appansicht erzeugen dadurch keine Ersatzkennung.
Es entsteht keine neue Offlineberechtigung und keine automatische Buchung beim
Öffnen der Ansicht.

## Nachgewiesene Ausgangslücke

Mit dem unveränderten Materialcontroller aus 49b73d9 konnte ein neuer Auftrag
nach angenommener, verlorener Antwort und vollständiger Sitzungsneuerstellung
tatsächlich eine zweite Rückgabe buchen. Die unabhängige HTTP-Gegenprobe
erwartet eine Sperre mit 409 und erhielt stattdessen eine weitere angenommene
Lagerbewegung. Der rote Rohbeleg bleibt erhalten. Die temporäre Reproduktion
hat den neuen Controller danach im `finally` unverändert wiederhergestellt.

## Speicherung und Wiederaufnahme

`OnlineCommandJournal` nutzt den bestehenden AES-GCM-Vault und gerätegeschützten
Schlüssel. API-Adresse, API-Version und Konto bilden getrennte Speicherbereiche.
Projekt beziehungsweise Mitarbeiter und Auftragsart besitzen eigene Slots.
Die Instanzbindung bleibt im verschlüsselten Zustand: Eine neue Firma mit
denselben Konto- und Projektkennungen auf demselben Host darf ein offenes altes
Original weder lesen noch durch einen neuen Speicherbereich umgehen. Erst ein
bestätigt leerer Journalzustand darf an die neue Firma gebunden werden.

Das Journal erhält Werte, Unicode, Nullwerte und die ursprüngliche Request-ID.
JSON-Schlüsselreihenfolge ist kein fachlicher Unterschied. Je Snapshot gilt
eine Grenze von 1 MiB. Fehlender Schlüssel, kaputter jüngster Snapshot,
unaufgelöste Dateien, geänderte Anmeldung und konkurrierende Fenster führen
zu einer Sperre; es gibt keinen stillen Rückfall auf ältere Inhalte. Fehler
beim dauerhaften Vorbereiten verhindern den POST. Fehler beim lokalen
Bestätigungsabschluss erhalten das bereits angenommene Original.

Frische Identität, Firma und Fachrechte werden vor dem Entschlüsseln und erneut
vor jedem POST oder privaten Statusabruf geprüft. Die App speichert keine
Zugangsdaten in diesem Journal. Beim Verlassen einer privaten Ansicht werden
die Daten im Arbeitsspeicher weiterhin gewischt; das verschlüsselte Original
wird dadurch nicht gelöscht. Ein anderes Fenster, das denselben Auftrag
bereits vollständig geklärt hat, wird beim erneuten Öffnen erkannt.

Bei Materialrückgaben erfolgt eine identische Wiederholung des vorhandenen
idempotenten Lagervertrags, danach der Abgleich mit der gespeicherten Bewegung.
Die historische Bewertung und die Lager-/Projektkostenarithmetik sind unverändert.
Bei Kilometern wird zuerst ausschließlich die ursprüngliche private Quittung
gelesen. Nur wenn sie tatsächlich fehlt, kann ausdrücklich derselbe Auftrag
wiederholt werden. Fahrt, Einreichung, unabhängige Freigabe und tatsächlicher
Erstattungsnachweis bleiben an Person, Handlung, Fassung und beide Auftragshashes
gebunden. Der ursprüngliche Fahrtstand für Einreichung/Zurückweisung wird
ebenfalls verschlüsselt erhalten und beim Ergebnis erneut verglichen.

Eine ausdrückliche Serverantwort `409 / not_accepted` erlaubt den lokalen
Abschluss eines nachweislich nicht angenommenen Auftrags und anschließend
eine neue bewusste Eingabe. Für neue Materialrückgaben wird diese Antwort nur
innerhalb des bereits gegen Originalquittung geprüften, gesperrten Schreibwegs
erteilt. Eine Kollision mit einer schon angenommenen Request-ID wird niemals
so bezeichnet. Unklare Antworten und Fehler ohne diese Aussage erhalten das
Original; die App leitet aus einem beliebigen Fehler keine Nichtannahme ab.

## Prüfungen und Grenzen

Der gemeinsame native Nachweis umfasst Journalfehler, Firmen-/Konto-/Projekt-/
Mitarbeitertrennung, verlorene angenommene und nicht angenommene Antworten,
andere Fenster, explizite Ablehnung, Rechteentzug sowie zwei 390-Pixel-Ansichten.
Fünf tatsächliche lokale MFA-/TCP-/HTTP-Fälle verwenden den vollständigen
Server für Materialrückgabe, Fahrt, Einreichung, Freigabe und Zahlung.
Materialkonkurrenz, eingeschränkte PostgreSQL-Rolle und ein tatsächlicher
Dump/Restore sind gesonderte Backendnachweise.

| Prüfung | Tatsächliches Endergebnis |
| --- | --- |
| Neun betroffene native Journal-/Reise-/Material-/Service-Suiten | 89 bestanden, kein Fehler/Skip, 44 Sekunden im Fortschrittslog |
| Gesamte Appanalyse | Kein Befund, 24,0 Sekunden |
| Lager-/Inventur-/Artikel-/MFA-/HTTP-Backend | 42 bestanden, 24,157 Sekunden |
| Eingeschränkte PostgreSQL-Rolle, Konkurrenz, Ablehnung und Dump/Restore | 5 bestanden, 62,419 Sekunden |
| Tatsächlicher Materialbrowser mit MFA, verlorener Antwort und Lagerrolle | Ein vollständiger Ablauf bestanden |

Vor Wiederanzeige einer Rückgabenotiz prüft zusätzlich der ursprüngliche
Bewegungsendpunkt das aktuelle Projektleserecht. Ein globales Lagerleserecht
ohne dieses Projektrecht reicht nicht. Bis zur frischen Prüfung zeigt der
Dialog keinen gespeicherten privaten Auftrag an.

Die 32 historischen Rechenmodule, das vollständige ursprüngliche Modul
`payroll_multiple_payments.py` und die Gesamtzieldatei sind erneut bytegleich.

Die ersten laufenden App-/PostgreSQL-/Browserprüfungen wurden bei einer
Umgebungsaktualisierung beendet und gelten als unvollständig. Der erste
PG-Nachlauf verweigerte korrekt das vom Abbruch erhaltene Restore-Ziel.
Dieses synthetische Ziel wurde geprüft und gesichert; der vollständige
Nachweis verwendet einen frischen eigenen Testcontainer. Der Schutz vor
Überschreiben vorhandener Ziele wurde nicht geändert.

[Rohprotokolle, Ergebnisse und Quellhashes](evidence/online-command-restart-2026-11-09/verification.json).
Die auf 19ec4e9 vollständig grüne Windows-/iPhone-CI bleibt ihrem eigenen
Quellstand zugeordnet. Eine neue Serverinstallation oder echte Geräteabnahme
wird durch die lokalen Prüfungen nicht ersetzt.

Browseraufträge und alte Server ohne bestätigte Firmenbindung bleiben bisher
sitzungsgebunden. Die Kilometeransicht zeigt diesen Unterschied ausdrücklich.
Offline-Materialrückgaben, weitere Reisearten und die übrigen Gesamtzielpunkte
sind damit nicht geschlossen. Ein dauerhaft zurückgewiesenes Original ohne
eindeutigen Nichtannahmenachweis bleibt geschützt zur Klärung erhalten; es
existiert keine pauschale Lösch- oder Neuverbuchungsaktion.
