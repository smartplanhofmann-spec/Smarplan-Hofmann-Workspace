# Vorhandenen Bot mit Smartplan verbinden

Dieses Paket ergänzt den bereits eingerichteten Mailbot um **lesende Metadaten
aus Google Kalender und OneDrive**. Es richtet keinen neuen Bot ein. Die dort
bereits verbundenen Konten werden verwendet; neue Google-/Microsoft-Apps,
Passwörter oder OAuth-Clientschlüssel sind für diesen Weg nicht erforderlich.
Ob die konkrete Botplattform diese Lese- und HTTPS-Funktionen freigibt, muss der
Bot tatsächlich prüfen. Das Paket behauptet keine bestehende Verbindung.

1. In Smartplan unter **Integrationen → Vorhandenen Bot weiterverwenden →
   Integrationszugang bereitstellen** den neuen Integrationsschlüssel erstellen.
   Smartplan benötigt mindestens Server 0.11, Schema 6 und die Fähigkeit
   `business_integrations`.
2. Den Schlüssel ausschließlich im geschützten Credentialfeld des Bots als
   `SMARTPLAN_INTEGRATION_TOKEN` für `office.smartplan-hofmann.de` hinterlegen.
   Den bestehenden `SMARTPLAN_INTAKE_TOKEN` für Mails unverändert lassen.
3. Dem Bot dieses Paket und [BOT_AUFTRAG.md](BOT_AUFTRAG.md) geben. Er soll den
   bestehenden Fünf-Minuten-Job erweitern und die erste bestätigte Zustellung
   melden. Keine zweite Automation anlegen.

Der Schlüssel gehört weder in Chat, Prompt, JSON-Beispiele noch Protokolle.
Eine maskierte Anzeige oder die Länge eines Platzhalters belegt keine korrekte
Credentialbindung. Bei geschützten Handles die native authentifizierte
HTTPS-Action der Plattform verwenden. Der mitgelieferte Pythonclient löst
Platzhalter nicht selbst in echte Schlüssel auf; erst die Serverquittung belegt
eine Zustellung. Der echte SPIX-Schlüssel wird ausschließlich vom Server geprüft.

## Technischer Vertrag für den Bot

`openapi.json` beschreibt genau zwei Routen auf dem festen Smartplan-Host:

- `GET /api/v1/intake/integrations/jobs`: begrenzte Auftragsliste.
- `POST /api/v1/intake/integrations/jobs/{id}/result`: Ergebnis oder fester Fehler.

Autorisierung: `Authorization: Bearer <geschützt gebundener Integrationszugang>`.
SPIX ist vom bisherigen SPIN-Mailzugang getrennt und berechtigt weder zur
allgemeinen Fach-API noch zu Kunden-, Finanz- oder Benutzerverwaltung.

`client.py` benötigt nur Python 3.11 oder neuer. Der Bot nutzt seine vorhandenen
Provider-Lesewerkzeuge selbst; der Helper öffnet keine Providerkonten und lädt
keine Originaldateien herunter. Geschützte lokale Dateien müssen unter POSIX
dem aktuellen Benutzer gehören und dürfen keine Gruppen-/Fremdrechte haben
(Dateien 0600, Arbeitsverzeichnis 0700). Keine Symlinks oder FIFOs verwenden.

```bash
python3 client.py --list-jobs --output private-jobs.json --send
python3 client.py --result private-result.json --check
python3 client.py --result private-result.json --send
```

Alternativ zum bereits sicher gesetzten `SMARTPLAN_INTEGRATION_TOKEN` ist
`--token-file /geschuetzter/pfad` erlaubt. Keine Schlüssel als Kommandoargument.
Die Ausgabedatei wird neu angelegt und nicht überschrieben. Stdout enthält nur
Anzahl, feste Fehlercodes und minimale Quittungen, keine Kalender-/Dateiinhalte.

Die Resultdatei enthält `job_id` und den unveränderten API-Body daneben, etwa im
synthetischen [Katalogbeispiel](examples/catalog_result.json). `job_id` bestimmt
den festen POST-Pfad und wird nicht in den Body kopiert. Erfolgsantworten sind
nur **HTTP 201 + `status:"received"` + passende `job_id` + boolesches
`idempotent`**. Ein bestätigter Fehler bedeutet lediglich, dass der Fehler beim
Server angekommen ist; er bedeutet keine erfolgreiche Datensynchronisation.

Alle Providerdaten werden **normalisiert** geliefert, keine Google-/Graph-
Rohobjekte. Die vollständigen synthetischen Formen stehen in
[Google-Ressource](examples/google_resource_result.json),
[OneDrive-Katalog](examples/onedrive_catalog_result.json) und
[OneDrive-Ordner](examples/onedrive_resource_result.json). Ein Google-Snapshot
muss exakt alle ausgewählten Termin-IDs liefern (höchstens 50), auch entfernte
Termine als explizite `cancelled`-Tombstones mit `start/end/all_day:null`.
Ressourcenvorschauen enthalten höchstens 500 Termine. Aktive Termine verwenden
`start/end` als RFC3339 mit UTC-Abstand oder als `YYYY-MM-DD` bei `all_day:true`.
OneDrive-Dateien liegen direkt unter `folder.path`; `rev` bleibt der echte
eTag/cTag einschließlich vorhandener Anführungszeichen.

Vor dem Senden das vollständige Ergebnis privat und dauerhaft speichern.
`source_id` ist eine stabile echte Quellrevision oder der SHA256-Wert des
kanonischen vollständigen Payloads (`client.stable_source_id(payload)`), niemals
eine neue Retry-Uhrzeit. Nach Timeout oder unbestätigter Antwort denselben Body
und dieselbe `source_id` beim nächsten bestehenden Joblauf erneut senden. Kein
automatischer Schnellretry. HTTP 429/`Retry-After` respektieren; bei 401 die
geschützte Bindung, Ablauf oder Widerruf prüfen. 404 kann einen noch nicht
aktualisierten Server bedeuten; nichts als verarbeitet melden. 409/410 wegen
alter Auswahl/Generation nicht durch neue IDs umgehen, sondern aktuellen
Auftrag laden und den Konflikt melden.

Nur echte Kalender-/Ordnerkataloge und ausdrücklich beauftragte Ressourcen
lesen. Providerkennungen, OneDrive-Laufwerk/Elternordner, Revisionen, Zeitzonen,
UTC-Abstände und das exklusive Ende ganztägiger Termine erhalten. Höchstens
1000 Metadateneinträge und 2 MiB pro Ergebnis. Unvollständige Seitenlisten sind
kein vollständiger Erfolg. OneDrive-URLs müssen vorhandene private
First-Party-`webUrl`-Werte sein; keine temporären Download-URLs und keine neu
angelegten Freigaben. Keine Datei-Originale, Zugangsdaten, Anhänge, Skripte oder
KI-Auswertungen an diese Metadatenrouten senden.

Fehlen Werkzeuge, Berechtigungen oder vollständige Ergebnisse, einen festen
Fehlercode senden (Beispiel: [error_result.json](examples/error_result.json)) und
die fehlende Fähigkeit konkret nennen. Keine leeren Erfolgskataloge erfinden.
Das lokale `--check` prüft Struktur und Grenzen; der Server prüft zusätzlich
aktuelle Konto-, Projekt-, Generations- und Auswahlbindungen.
