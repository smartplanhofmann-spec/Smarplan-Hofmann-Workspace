# Planimport: App, API und lokaler Worker

Entwicklungsstand 0.8.0 im Online-Modus (API v1) verbindet JPEG-/PNG-/PDF-Dateiauswahl und die
iOS-Kamera mit verschlüsselten lokalen Quellen, fortsetzbarem Upload und
projektgebundenen PostgreSQL-Aufträgen. Parser und Drucktext-OCR laufen über
den [lokalen Importkern](../plan_import/README.md), ohne externen Auswertungsdienst.
Die Integrationsprüfungen laufen noch; dieser Stand ist nicht auf dem bestehenden
Hetzner-Server bereitgestellt. Dort läuft weiterhin Version 0.7 mit Schema 2.
Das lokale Windows-Paket enthält diese Importoberfläche nicht. Online-Modus
bezeichnet die Serverkonfiguration; eine vorbereitete Offline-Nutzung bleibt
auch ohne momentane Internetverbindung möglich.

## App und Offline-Speicherung

Die App übernimmt das Original vor der Erfolgsbestätigung in eine unveränderliche
AES-GCM-Binärdatei im bestehenden Konto-/Serverscope. Erst danach schreibt der
einzige Metadaten-Schreiber die Referenz und den Uploadauftrag. Große Bilder
werden nicht als Base64 in den gesamten JSON-Snapshot eingebaut. Referenz,
Prüfsumme und verschlüsselte Bytes werden beim Lesen gemeinsam geprüft.

Die sieben Tage nach einer Online-Anmeldung begrenzen den Offline-Zugriff;
sie sind keine Löschfrist. App-Wechsel, Rechteentzug oder Uploadfehler löschen
keine bestätigten Originale. Bei fehlenden neuen Routen auf einem alten Server
bleibt die Quelle lokal. Die Anmeldung meldet die unterstützten Funktionen;
nur bei unbekannter Importfunktion gilt eine 404-Antwort als fehlendes
Serverupdate. Bei bekannter Importfunktion sperrt ein nicht mehr verfügbares
Projekt den Zugriff auf die behaltenen Originale. Ein noch lokaler Upload ist
kein bereits laufender Erkennungsauftrag.
Eine beendete iOS-App garantiert keine sofortige Hintergrundübertragung.

Für iOS sind Kameraerlaubnis, `NSFileProtectionComplete` und
`isExcludedFromBackup` für den eigenen Offline-Ordner implementiert; der native
Aufruf prüft Pfade und verweigert unbestätigten Schutz. Schlüssel bleiben im
gerätegebundenen Keychain-Zugang. Die Kamera-Tempdatei wird nach bestätigter
verschlüsselter Übernahme bereinigt. Die App exportiert die Aufnahme nicht in die
Fotomediathek. Kamera, Sperrverhalten und tatsächlicher Backup-Ausschluss sind
noch auf iPhone/iPad abzunehmen; ein CI-Build ist kein Gerätenachweis.

Der iOS-Prozess setzt vor Flutter-/Plugin-Initialisierung `umask 0077`, damit
auch neu angelegte Binärordner privat sind. POSIX-Entwicklungs-/Testbefehle laufen
ebenfalls unter `umask 0077`; die Prüfung tatsächlich privater Ordner bleibt aktiv.

Dateiflush und Umbenennung kommen vor dem Metadatencommit. Dart bietet hier
keinen Verzeichnis-fsync; garantierte Stromausfallsicherheit ist nicht belegt.
App-Neustart- und Übertragungstests sind Teil der laufenden Integrationsprüfung.

## API-Vertrag

Alle Routen liegen unter `/api/v1/projects/PROJEKT_ID/plan-imports` und benötigen
einen gültigen Bearer-Zugang sowie die frische Projektberechtigung. Der eng
begrenzte Siebentage-Planzugang darf auch diese Projektquellen abrufen und
hochladen. Schreibrechte besitzen Geschäftsführung, Projektleitung und Technik;
der vorhandene Projekt-/Rollenvertrag bleibt maßgeblich.

| Methode / relativer Pfad | Zweck |
| --- | --- |
| `GET` Basisroute | Projektimporte, zuletzt angelegte zuerst. |
| `POST` Basisroute | Manifest anlegen oder mit derselben Anfrage-ID wieder aufnehmen. |
| `GET /IMPORT_ID` | Status, Prüfsummen und bestätigte Abschnittsindizes. |
| `PUT /IMPORT_ID/chunks/INDEX` | Genau einen Binärabschnitt übertragen. |
| `POST /IMPORT_ID/complete` | Vollständige Quelle prüfen und Auftrag einreihen. |
| `GET /IMPORT_ID/source` | Bestätigtes Original einschließlich fehlgeschlagener Erkennung. |
| `GET /IMPORT_ID/preview` bzw. `/result` | Veröffentlichtes PNG beziehungsweise Erkennungs-JSON. |

Das Manifest enthält `request_id` (32 Hex-Zeichen), `filename`, `media_type`,
`size`, `sha256`, `page` und `title`. Quellen sind auf 20 MiB begrenzt;
JPEG/PNG verwenden Seite 0, PDF-Seiten zählen in der API ab 0 und in der App ab 1.
Eine bestimmte PDF-Seite und ihr Originalhash gehören zusammen zum Auftrag.
HEIC, DXF/DWG und verschlüsselte PDFs sind nicht unterstützt.

Ein Abschnitt umfasst 262144 Bytes (256 KiB), der letzte die verbleibenden Bytes.
Die Antwort nennt vorhandene `uploaded_chunks`. Dieselbe Anfrage-ID und dieselben
Originalabschnitte lassen sich wiederholen; abweichende Inhalte werden abgewiesen.
Erst Gesamtgröße und Gesamt-SHA-256 bestätigen den vollständigen Upload.
Die bisherige JSON-Grenze von 1 MB bleibt bestehen; Binärdaten haben eigene Grenzen.

Statusfolge: `uploading` → `queued` → `running` → `needs_review` oder `failed`.
Ein vorhandener Upload bleibt über Unterbrechungen erhalten. Ein abgebrochener
Workerauftrag kann nach Ablauf seiner Lease erneut beansprucht werden; ein
verspäteter Versuch darf das Ergebnis eines neueren Versuchs nicht überschreiben.
Nach begrenzten Wiederholungen bleibt ein fehlgeschlagener Auftrag samt Quelle
erhalten. Ein Parserfehler erzeugt keinen scheinbar fertigen leeren Plan.

## Kanonische Daten und Wiederherstellung

Schema 3 enthält `plan_imports` und `plan_import_chunks`. Originalchunks bleiben
auch nach Uploadabschluss unverändert. Vorschau, Erkennungs-JSON, Hashes,
Seitenbezug und Auftragszustand liegen ebenfalls in PostgreSQL. Der eigenständige
SQLite-Dateistore des Kernel-CLI wird hierfür nicht verwendet.

Die vorhandene gemeinsame PostgreSQL-Sicherung umfasst dadurch Quellen und
Ergebnisse. Release/Restore prüfen Chunkhashes und -längen, vollständige Quellen,
PNG-/JSON-Hashes und den Bezug des Ergebnisses auf Originalhash und PDF-Seite.
Partielle Uploads bleiben zulässig. Unterstützte alte Schemas werden nur im
getrennten Kandidaten migriert; das aktive System wird nicht überschrieben.

Der Updateablauf erwartet Schema 3 und die Capability `plan_imports`. Ein bereits
aktiver `smartplan-plan-import.service` wird vor dem Datenbankklon angehalten und
erst passend zu Rollback beziehungsweise bestätigter Aktivierungsgrenze wieder
gestartet. Ein vorher inaktiver Worker wird nicht automatisch aktiviert. Es wird
keine neue Workerunit angelegt und kein Importdienst automatisch bereitgestellt.

## Worker-CLI für synthetische Entwicklungstests

Der Controller benötigt den Online-Lock; der beaufsichtigte Parser benötigt eine
eigene Linux-/Python-3.12-Umgebung mit `backend/plan_import/requirements.lock`
und lokalem Tesseract samt `eng`. Schwere Bildverarbeitung wird nicht in die
HTTP-Worker geladen. Einrichtung und Kernel-Testbefehle stehen im
[Kernel-README](../plan_import/README.md). Die folgenden Befehle setzen eine
bereits vorbereitete lokale Einweg-Testdatenbank und beide Venvs voraus; sie
sind keine Aufforderung zur Installation auf dem Nutzer-Server.

```bash
PYTHONPATH=backend SMARTPLAN_DATABASE_DSN="${SMARTPLAN_TEST_DSN:?Lokale Einweg-Testdatenbank fehlt}" \
  /tmp/smartplan-online-test/bin/python -m online.import_worker \
  --worker-python /tmp/smartplan-import-test/bin/python --once
```

`--watch` arbeitet die Warteschlange fortlaufend ab. Alternativ benennt
`SMARTPLAN_IMPORT_WORKER_PYTHON` den Parser-Pythonpfad. `--ocr-languages deu+eng`
verwendet lokal installierte Sprachdaten; fehlende Sprachen und gegebenenfalls
englischer Ersatz werden im Ergebnis gemeldet. Eine Deutsch- oder
Handschriftqualität ist nicht abgenommen.

Der Parser erhält nur erlaubte Umgebungsvariablen, keine Datenbank-DSN,
Vault-/OAuth-Geheimnisse oder geerbten Proxy-Zugänge. Er läuft außerhalb der
Office-Transaktion mit Laufzeit-/Speicherlimits und bereinigter Prozessgruppe.
Das ist **keine vollständige Netzwerk-/Dateisystem-Sandbox**: der CLI-Pilot
besitzt noch keinen umfassend isolierten produktiven Ausführungsvertrag.
Vor Sandbox- und Serverabnahme werden keine ungeprüften echten Planunterlagen
verarbeitet. Die Entwicklung nutzt synthetische Beispiele; reale Unterlagen
werden später direkt auf dem eigenen Hetzner-System bereitgestellt.

## Fachliche und Freigabegrenzen

Die App zeigt Original und verfügbare Vorschau mit Kandidaten zur Prüfung.
Linien und Drucktexte sind keine bestätigten Wände, Türen, Räume oder gültigen
Maße. Handschrift, Durchstreichungen und Pfeile werden nicht fachlich verstanden;
Linien werden nicht automatisch in den bisherigen Wandplan übernommen.
Perspektivkorrektur, Maßkalibrierung, DXF und DWG folgen später.

Die App-/HTTP-, Neustart-, Upload- und Rechteprüfungen laufen. Native CI-Builds
folgen nach dem Push; iPhone-/iPad- und Serverabnahme bleiben erforderlich.
Vor einer neuen Windows-Veröffentlichung ist außerdem die bestehende
Authenticode-/SmartScreen-Signierungsaufgabe abzuschließen. Dieser Durchstich
behauptet keine Behebung der Warnung des bisherigen unsignierten Testpakets.
