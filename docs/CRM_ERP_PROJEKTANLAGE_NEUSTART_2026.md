# Projektanlage nach verlorener Antwort und App-Neustart

Stand: 09.11.2026. Eigener Entwicklungsabschnitt ab `51786b1` für R01.02,
R06.04, R11 und die Abnahmefälle B/F/G des unveränderten Gesamtziels.
Die bisherige Grenze steht im Projekt-Integrationsstand vom 04.11.: Ein
unbestätigter Projektauftrag überlebte nur das Schließen des Dialogs.

## Verhalten

Bei einem Server mit `project_creation_journal` wird die exakt eingegebene
Projektanlage vor dem ersten POST verschlüsselt auf dem Gerät gesichert.
Ein lokaler Schreibfehler verhindert den POST und lässt die Eingaben korrigierbar.
Bei verlorener Serverantwort bleiben Auftragskennung, Projektname und gewählter
Kunde unverändert. Erneutes Öffnen nach einer neuen Anmeldung und vollständigem
Neuaufbau der App setzt genau diesen Auftrag fort; es wird keine neue Kennung
erzeugt. Der Nutzer löst die Wiederholung ausdrücklich aus.

Die App verlangt vor der Anzeige eine frische Online-Anmeldung, denselben
Benutzer, die Geschäftsführungsrolle und die bestätigte Unternehmensinstanz.
Ein inzwischen entzogenes Recht, andere Instanz oder fehlender Scope gibt
gesicherte Kundendaten nicht frei. Ein bloß zurückgesetzter alter Tokenstring
reaktiviert keinen bereits verworfenen Anwendungskontext.

Erst die vollständige Annahmeprüfung entfernt den offenen Auftrag. Eine
fehlgeschlagene Quittungsabfrage nach angenommenem POST — auch HTTP403/404 —
oder ein Fehler beim lokalen Abschluss lässt denselben Auftrag erhalten.
Abmelden entfernt den sichtbaren Zustand, aber nicht den verschlüsselten
unbestätigten Auftrag. Die getrennte Offline-Planschlüsselverwaltung löscht
den Schlüssel dieses Journals nicht.

## Speicher- und API-Vertrag

Der bestehende `OfflineVault` speichert AES-GCM-verschlüsselte, atomar umbenannte
Zustände mit Versionsprüfung und Schreibsperre. `OfflineDevice` verwendet den
bestehenden Betriebssystem-Schlüsselspeicher. Es entsteht keine neue
Kryptografie oder Abhängigkeit. Das Journal hat einen getrennten Namensraum
aus Server, API-Version und Benutzer; der verschlüsselte Zustand bindet die
unveränderliche Instanzkennung. Token und Passwörter werden nicht gespeichert.
Vom ausgewählten Kunden werden nur die zur unveränderten Anzeige benötigten
Kennung, Name und Adresse gesichert.

Die Schlüssel-Erstanlage besitzt zusätzlich eine Sperre im laufenden Prozess
und eine Dateisperre. Zwei erstmalige Fenster dürfen den gemeinsamen Schlüssel
nicht gegenseitig ersetzen. Vorhandene Schlüssel und verschlüsselte
Bestandsdateien werden nicht neu erzeugt. Ein beschädigter oder ausdrücklich
quarantänisierter neuester Journalstand sperrt die Anlage; es erfolgt keine
stille Rückkehr zum vorigen Auftrag.

Der Server kündigt das Feature nur mit einer tatsächlich gespeicherten
Unternehmensbindung an. Die Fähigkeiten enthalten:

```json
{"project_creation_scope":{"schema_version":1,"instance_id":"…","account_id":"…"}}
```

`GET /business/project-creations/{request_id}` liest die eigene gespeicherte
Annahmequittung nach frischer Geschäftsführungsprüfung. Das Ergebnis enthält
Instanz, Konto, Auftragskennung, gespeicherten Auftragshash und Projektkennung.
Zusätzliche Queryparameter und andere Methoden sind unzulässig. Gerätezugänge
für Offlinearbeiten bekommen weder Scope noch Quittungszugriff.

Der Client prüft die Projektkennung gegen die POST-Antwort und SHA-256 über die
ursprüngliche kanonische Servereingabe:

```text
{"data":{"customer":…,"customer_id":…,"name":…,"request_id":…},
 "operation":"core.project.create:v1"}
```

Nicht vorhandene Kundenfelder sind dabei ausdrücklich `null`. Der Hash wird
nicht aus heutigen editierbaren Projekt-/Kundendaten neu erzeugt. Das bestehende
Quittungsformat und die Datenbank bleiben unverändert; der neue GET liest es.
Die Registrierung erfolgt im vorhandenen Foundation-Routenvertrag. Es gibt
keine neuen Tabellen, Exportspalten oder Operator-Schreibpfade.

## Altserver und Grenzen

Ohne neues Feature bleibt der ausdrücklich begrenzte bisherige Dialog-/Replay-
Modus erhalten. Das bloße Prüfen auf ein vorhandenes Journal erzeugt dann weder
einen Schlüssel noch eine verschlüsselte Datei. Ein bereits vorhandener offener
Journalauftrag kann jedoch nicht durch ein Server-Downgrade umgangen werden;
er benötigt weiterhin den ursprünglichen bestätigten Scope. Es wird keine
Neustartbeständigkeit des Altservermodus behauptet.

Dies ist keine Freigabe zur Offline-Projektanlage. Das Journal bewahrt die
Identität einer Onlineanfrage; jeder Versand benötigt erneut aktuelle
Serverrechte. Ein Geräteverlust oder das Löschen von Daten/OS-Schlüsseln wird
nicht durch lokale Persistenz aufgehoben. Ein tatsächlicher Windows-/iPhone-
Prozessabbruch, Geräteschlüsselspeicher und Geräteinstallation bleiben gesonderte
Abnahmen. Vollständiger App-Neuaufbau mit echter Datei und echtem HTTP wird
als Neustartsimulation ausgewiesen.

## Prüfstand

Die [Quellhashes und Ergebnisse](evidence/project-creation-journal-2026-11-09/verification.json)
und [unveränderten Rohprotokolle](evidence/project-creation-journal-2026-11-09/raw-logs.json)
sind im Repository festgehalten. Die Gruppen überschneiden sich und werden
nicht zu einer scheinbaren Zahl verschiedener Gesamtabnahmen addiert.

| Prüfung | Ergebnis |
| --- | --- |
| Gemeinsame native Journal-, HTTP-, Alt-Replay- und Offlineprüfung | 94 bestanden, keine Skips, 64 Sekunden |
| Aktuelle Backend-Scope-/Quittungs-/Originalprüfungen | 11 bestanden, keine Skips, 10,538 Sekunden |
| Zusätzlich betroffene Backend-Replay-/Feature-/Routergruppe | 23 bestanden, keine Skips, 9,498 Sekunden |
| Paketprüfung einschließlich tatsächlichem Import des gepackten Backends | 16 bestanden |
| Flutter-Analyse | Kein Befund, 27,1 Sekunden |

Der tatsächliche HTTP-Fall nutzt zwei frische MFA-Anmeldungen über synthetische
Wiederherstellungscodes, eine echte lokale Unternehmensbindung und eine lokale
temporäre Datenbank. Nach angenommener, aber im Client verworfener POST-Antwort
werden App, API und flüchtiger Zustand vollständig neu aufgebaut. Die identische
Wiederholung ergibt genau ein Projekt und einen Kunden mit ursprünglicher
Zuordnung. Die Quittung wird tatsächlich über den neuen geschützten GET geprüft.

Unabhängige Nachprüfung fand zwei Fehler der ersten Fassung: Ein nachgelagerter
Quittungsfehler durfte nicht als Ablehnung des vorherigen POST gelten; außerdem
fehlte die frische Rollenprüfung vor Anzeige der gespeicherten Kundendaten.
Beides ist korrigiert und ausdrücklich getestet. Die zusätzliche Prüfung der
Schlüssel-Erstanlage fand das parallele Initialisierungsrennen; der Prozess-/
Dateisperrenfix ist mit zwei gleichzeitigen Öffnungen und anschließendem Lesen
des ursprünglichen verschlüsselten Zustands geprüft.

Fehlgeschlagene Erstläufe bleiben erhalten: Ein alter Widgettest erwartete nach
manuellem Zurücksetzen eines verworfenen Sitzungstokens eine neue Anlage; der
neue Ablauf verlangt dort eine echte Anmeldung. Der HTTP-Testaufbau wurde an
normalisierte Wiederherstellungscodes und die tatsächliche scrollbare Navigation
angepasst. Diese Fehlläufe werden durch die späteren Erfolge nicht umgedeutet.
