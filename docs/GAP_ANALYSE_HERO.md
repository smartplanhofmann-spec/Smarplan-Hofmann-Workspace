# Gap-Analyse: Smartplan Office und projektzentrierter Zielumfang

Diese Phase-0-Analyse dokumentiert den Zustand **vor** der Umsetzung. Den aktuellen Implementierungs- und Prüfstand enthält [BERICHT_HERO_UMSETZUNG.md](BERICHT_HERO_UMSETZUNG.md).

Stand: **25.10.2026**. Analysierter Quellcommit: **`f2e729486edc2652f466e21c30d25b6e710b199f`**; App **0.11.0+15**, PostgreSQL-Schema **6**. Dies ist die Pflichtanalyse der **Phase 0**. Produktivcode, Tests, API und Deploymentkonfiguration werden in diesem PR nicht geändert. Die vorgeschlagene Umsetzung steht in [ZIELARCHITEKTUR.md](ZIELARCHITEKTUR.md).

## 1. Umfang, Methode und Recherchegrenze

Die vollständige vom Nutzer gelieferte Checkliste A1–O4 mit **98 einzeln bewerteten IDs** ist der Anforderungskatalog. Der hier beschriebene Funktionsvergleich bezieht sich auf diesen Katalog und den tatsächlich geprüften Smartplan-Code, nicht auf eine behauptete Zertifizierung oder vollständige neue Marktstudie.

Ein regulärer HTTPS-Abruf von [hero-software.de](https://hero-software.de/) am 25.10.2026 wurde von der Cloudzugriffspolitik mit **HTTP 403** blockiert. Keine Umgehung, keine dortigen Texte/Assets übernommen; aktuelle Herstellerbehauptungen konnten nicht unabhängig nachgelesen werden. Die Nutzercheckliste bleibt deshalb ausdrücklich eine vorgegebene Anforderung. HERO ist ausschließlich fachliche Referenz, kein Name für eigene Module. Bestehende Anbietergrenzen zu Sevdesk/Google/OneDrive sind in [INTEGRATIONEN_QUELLEN.md](../backend/online/INTEGRATIONEN_QUELLEN.md) dokumentiert.

Die offiziellen GitHub-Projekte [KoSIT-Validator](https://github.com/itplr-kosit/validator) und [XRechnung-Konfiguration](https://github.com/itplr-kosit/validator-configuration-xrechnung) wurden am 25.10.2026 anhand öffentlicher Repositorymetadaten bestätigt. Das belegt ihre Rolle als spätere Validatorquellen, noch keine ausgeführte XRechnungsprüfung. Format-/Profilversionen werden im Umsetzungs-PR festgehalten.

Die Analyse umfasst statische Quellprüfung von `app/lib`, `backend`, `backend/online`, `backend/plan_import`, `integrations`, `deploy`, `scripts` und CI. Es wurden keine echten Kundendaten, Mails, Pläne, Credentials oder Nutzer-Server abgefragt. Repo-/Buildstand ist nicht gleich Livestand: Die App 0.10.1 und echte Mailanhänge wurden zuvor vom Nutzer bestätigt; das Paket 0.11 wurde vorbereitet. Ob der Nutzer es inzwischen installiert hat, wurde hier nicht überprüft.

**Bewertung:** `vorhanden` erfüllt den genannten fachlichen Punkt im beschriebenen Bestand; `teilweise` bedeutet ausdrücklich benannte Teilfunktion oder wiederverwendbare Basis, nicht volle Nutzbarkeit der Gesamtanforderung; `fehlt` bedeutet kein entsprechender funktionsfähiger Fachablauf in den untersuchten Modulen. Ein externer Link, PDF oder Auditdatensatz zählt nicht als Rechnungseditor, Mailversand, Plantafel oder Messenger.

**Aufwand = verbleibender Restumfang**, keine Kalenderzusage: **S** überschaubare Ergänzung/Absicherung, **M** begrenztes Fachmodul, **L** mehrere Schichten/Teil-PRs oder wesentliche Fach-/Integrationsrisiken. Nicht vorhandene Providerunterlagen, Rechts-/Betriebsentscheidungen und reale Geräteabnahmen bleiben zusätzliche Abhängigkeiten. Phasen sind Zielreihenfolge und Teilfreigaben, keine Behauptung bereits umgesetzter Funktionen.

## 2. Ergebnis und wichtigste Risiken

Die Matrix enthält **3 vorhandene, 27 teilweise vorhandene und 68 fehlende Anforderungen**. Diese Zahl misst keine Prozent-Fertigstellung: etwa „teilweise E-Rechnungseingang“ kann nur vorhandenen Originaltransport bedeuten, während der Fachablauf noch fehlt.

Wiederverwendbar sind insbesondere reale Anfragen mit fortsetzbaren Originalanhängen, atomare bestätigte Kunde-/Projektanlage, Projektzuordnung und Aufgaben, native Projektmappe, sichere Offline-Warteschlange für vorbereitete Projektarbeit, Planimport sowie unterschriebene Serviceberichte/Lieferscheine.

Prioritäten vor dem Ausbau:

1. **Intake stabil halten:** Bodyquittung, Originalanhänge, SPIN-Scope und Wiederholungen sind produktrelevante Verträge. Ein `received` bedeutet keine vollständige Dateilieferung und keinen Auftrag.
2. **Finanzrechte durchgängig:** Sevdesk-Metadaten sind geschützt; generische Angebots-/Rechnungslinks und übernommene Mailoriginale sind hingegen allgemein projektlesbar. Phase 1 benötigt Rechte/Klassifikation auch für Dateiinhalte, Vorschauen, Suche und Exporte.
3. **Eigene kaufmännische Kernmodule fehlen:** Kein eigener Angebots-/AB-/Rechnungsfluss, Nummern-/Festschreibungsledger, OP-/Mahnprozess, Artikel-/Lager-/Zeitkern. Das neue Ziel autorisiert diesen Ausbau; der bisherige Sevdesk-Betrieb bleibt bis zum kontrollierten Umstieg führend.
4. **Web/Android/Echtzeit sind Lücken:** Native Flutterbasis und REST/Polling sind vorhanden; Website ist eine Einrichtungsseite. Kein vorhandenes Web-/PWA-/Androidziel und kein belegter SSE-/Pushkanal.
5. **Migrationen:** Exakter Schema-6-Vertrag und vollständige Legacy-Fingerprints schützen den Istbestand, sind aber noch kein allgemeines datenbewahrendes Down-System. Ein getesteter Kompatibilitäts-/Rückkehr-Build kommt vor neuen Fachmigrationen.
6. **DSGVO/GoBD:** Kontaktarchivierung ist keine Löschung, DB-Dump kein Betroffenenexport, Berichtshash keine GoBD-Abnahme. Receipts, Versionen, Backups und Offlinekopien gehören ins Dateninventar. Native Finanzfunktionen benötigen technische Festschreibung und betriebliche/steuerliche Prüfung.
7. **Eigene Betriebsgrenzen beachten:** Kein Mandantenmodell im Bestand; eine Installation für diesen Betrieb ist nicht bereits SaaS-Mandantentrennung. Unternehmensbindung von Nummern, Rechten und späteren Daten wird explizit vorgesehen, ohne fremde Mandanten ungeprüft mitzuführen.

## 3. Tech-Stack, Struktur und Betrieb


- **App:** Flutter/Dart, `app/pubspec.yaml:1–33`: Version **0.11.0+15**, Dart
  `>=3.13.0 <4.0.0`, Flutter `>=3.47.7`. CI/Setup pinnen Flutter3.47.7
  (`checks.yml:113`, `ios-testflight.yml:55`, `scripts/setup-cloud.sh:30–33`).
  Sichtbare Version separat `app/lib/app_version.dart`; Manifest prüft beide.
- Flutter Material3/eigenes Design+Interfont (`app/lib/main.dart:20–38`,
  `app/lib/design.dart`). Native Windows C++/CMake, iOS Swift/Xcode, iOS15
  und Bundle-ID `de.smartplanhofmann.office`
  (`app/ios/Runner.xcodeproj/project.pbxproj:363,386`).
- App-Abhängigkeiten: `pdfrx2.10.1`, `share_plus13.3.1`, `image_picker1.2.4`,
  `url_launcher6.3.2`, `flutter_secure_storage11.2.0`, `local_auth3.0.2`,
  `cryptography2.9.0`, `path_provider2.1.6`, `qr_flutter4.1.0`, file_selector
  und printing (genaue Auflösung in `app/pubspec.lock`; pubspec enthält teils
  Versionsbereiche). Native PDFium-Rasterprüfung erforderlich.
- **Backend:** Python3.11+ laut Setup, CI3.12. Lokaler Kern `backend/core.py`
  und `server.py`; gemeinsame Domänenmodule direkt in `backend/`.
  `backend/requirements.lock`: cryptography46.0.7, ReportLab4.5.1,
  Pillow12.3.0 plus transitive Pakete.
- **Online:** `backend/online/requirements.lock`: Flask3.1.3,
  Gunicorn26.2.0, Werkzeug3.1.9, psycopg/psycopg-binary3.3.6;
  PostgreSQL16 wird durch Installer/CI bereitgestellt
  (`deploy/hetzner/online/install-online.sh:30`, `checks.yml:19–30`).
- **Importworker:** eigener Pythonruntime und lokale PDF/OCR-Verarbeitung:
  `backend/plan_import/requirements.lock` numpy2.3.5,
  opencv-python-headless4.13.0.92, Pillow12.3.0, pypdfium2 5.14.0;
  systemisches Tesseract, bubblewrap und Linuxsystemd. Keine externe KI/OCR.
- `app/lib`: Anmeldung/Navigation, Kunden, Anfragen, Projektmappe, Pläne,
  Import, Report/Unterschrift, Anhänge, Offlinevault, Integrationsansichten.
- `backend/online`: Flaskauth/Adapter, PostgreSQL, Release/Backup/Restore,
  Storage, Integrationorchestrierung und Importcontroller/-sandbox.
- `backend/plan_import`: eigenständiger Importkern/CLI und Store;
  `backend/plan_import/tests`: schwere isolierte Workerfälle.
- `integrations/google_apps_script`: bestehende Gmail-Brücke;
  `integrations/mail_bot`: Mail-/Anhangskit;
  `integrations/project_bot`: separates lesendes SPIX-Metadatenkit.
- `deploy/hetzner/{https,online}`: Caddy, systemd, Install-/Update-/Recovery- und
  Abnahmeabläufe; `windows/` + `backend/windows_office.py`: lokaler Launcher;
  `scripts/`: Paketvertrag, Windows-Supportarchiv, Setup-/CI-Helfer.
- Keine React-/Next-/Node-Webapp. Node wird für synthetische Apps-Script-Tests
  benutzt, nicht als Produktbackend (`checks.yml:88–89`). Kein ORM, keine
  Alembic-/Prisma-/Django-Migrationen.

### Betrieb: lokaler Client, Online und Import getrennt

| Bereich | Tatsächliche Quellkonfiguration |
|---|---|
| Lokales Windows | Flutter-Windows-App + mitgelieferter Python-Loopbackserver/SQLite; Standardclient `http://127.0.0.1:8765`, API `/api/*`, `API_VERSION=''` (`app/lib/api.dart:19–26`, `backend/server.py:200ff`, `windows_office.py`). Kein öffentliches lokales HTTP. Lokale `/health`-Versionszeichenfolge ist historisch `0.2.0-development` (`backend/server.py:91`), daher nicht mit App0.11-Semver verwechseln. |
| Gemeinsamer Onlinepilot | `https://office.smartplan-hofmann.de/api/v1`, PostgreSQL16, Gunicorn hinter Caddy. `deploy/hetzner/online/Caddyfile:8–27` leitet nur `/api/v1/*`, `/health`, `/ready` nach127.0.0.1:8766. Caddy2.11.7 wird gepinnt geladen (`deploy/hetzner/https/fetch-caddy.sh:13`). |
| Serverprozess | `smartplan-online.service`: Unixuser smartplan-online, `/opt/smartplan-online/app/backend`, EnvironmentFile `/etc/smartplan-online/service.env`, zwei gthread-Worker×vier Threads, bind127.0.0.1:8766,30s Timeout, UMask0077, Hardening. DB-DSN verwendet Unixsocket/Peer (`install-online.sh:51`). |
| Geschützter Import | Separater `smartplan-plan-import.service`, Runtime `/opt/smartplan-plan-import/venv/bin/python`, `--doctor` vor `--watch`,3Maximalversuche/Leases im Jobmodell, bubblewrap-Sandbox, AF_UNIX/AF_NETLINK, kein Parsernetzwerk, begrenzte tmpfs/CPU/RAM, KillModecontrol-group (`smartplan-plan-import.service`, `import_sandbox.py`). |
| Website | Caddy liefert `/`, index.html, style.css aus `/usr/share/smartplan-setup`; übrige `/api`-/Authaltpfade bekommen503 (`Caddyfile:30–44`). Das ist eine Einrichtungsseite, keine Browser-Fachapp/PWA. |
| Historie / Produktiv | `deploy/hetzner/ABNAHME.md:12` nennt historischen CAX11ARM64/Ubuntu24.04-Nürnberg-Stand. `deploy/hetzner/online/UPDATE_0_11.md:3–7` dokumentiert bestätigte App0.10.1/Mailanhänge und ausdrücklich, dass0.11 vor manueller Ausführung noch nicht auf dem Nutzerserver installiert ist. **Aktueller Livestand in Phase0 ungeprüft**; weder neuer Installationsstand noch echte Providerverbindung behaupten. |

### Datenzugriff und Aktualisierung

- Online-Schema **6**: `backend/online/store.py:9,74–79,87–132`.
  `migrate(dsn)` ist expliziter transaktionaler Pfad1→2→3→4→5→6; Requeststartup
  verweigert abweichende Version, migriert nicht still. Neues6 ergänzt reine
  Module nach dem alten5, bestehende Normalclones/Receipts bleiben erhalten.
- SQLite: `Office.__init__`, `backend/core.py:134–184`; Kundenmigration `198–212`,
  additive `schema_statements()`-Aufrufe für gemeinsame Domänen. Lokaler
  SQLite-`PRAGMA user_version=1` ist **nicht** PG-Schemaversion6.
- RawSQL mit Parametern, `sqlite3.Row` bzw. kleiner psycopg-Rowwrapper;
  `store.Database.execute:46–49` adaptiert `?` zu`%s`. `Office.lock` ist RLock;
  jede äußerste Online-Transaktion nutzt global
  `pg_advisory_xact_lock(741290518)` (`store.py:51–64`). Pilotzugriffe dadurch
  über Prozesse serialisiert, keine unbewiesene Hochlastskalierung.
- Provideraufrufe außerhalb des Office-Transaktionslocks; separate per-provider
  Locks plus erneute Session-/Generation-/Linkprüfung vor Publikation
  (`backend/online/integrations_service.py:183–210,395–460`).
- **Kein echter Push-/Realtimekanal**: App`HttpClient` REST, kein WebSocket/SSE
  in inventarisierten Produktdateien. Offline-Sync20s (`app/lib/offline_plans.dart:194`),
  Integrationsstatus30s (`app/lib/integration_pages.dart:112`,
  `app/lib/project_integration_widgets.dart:83–85`). Bot ergänzt extern bestehenden
  Fünfminutenjob (`integrations/project_bot/BOT_AUFTRAG.md:3ff`), ohne neue
  Automation auf Hetzner. Importwatcher pollt bei Leerlauf2s
  (`online/import_worker.py:238–241`). Normale GET-Statusabfragen rufen keine
  Anbieter ab. Dashboard/Listen laden bei Öffnen/Aktualisieren; keine implizite
  sofortige Pushverteilung für alle fachlichen Daten.
- Mutationsergebnisse nutzen request_id+Hash-Receipts sowie Revisionen/
  Konflikt409 (`plans.py`, `project_workspace.py`, `inquiries.py`,
  `external_integrations.py`, `integration_bridge.py`). Das ist fachliche
  Idempotenz, kein Ersatz für einen Nachrichtendienst/Enterprise-Eventbus.

### Authentifizierung und Berechtigungen

- Onlineentrypoints `POST /api/v1/login` und `/login/verify`
  (`online/web.py:203–211`, `online/auth.py:45,80`). PasswortPBKDF2-HMAC-SHA256,
 310000Runden/Salt (`backend/core.py:41–42`), Mindestlänge12 (`48–50`). Online verlangt
  TOTP/Recovery mit fünfminütiger einmaliger Challenge und DB-Ratelimits,
  TOTP-Zähler gegen Replay; Sessions8h als SHA256-Hash (`backend/online/auth.py:71,88,119–125`).
  Enrollment und zehn Recoverycodes werden einmalig zurückgegeben; deren
  Speicherung/Fernet-MFA liegt in DB, nicht im Browser.
- Lokaler `POST /api/login`: Office.login nur Passwort,8hBearer
  (`backend/server.py:94–95`, `backend/core.py:366–385`). Keine belegte lokale MFA.
- `GET /me`, `POST /logout`; Token nur AuthorizationBearer, kein Cookie- oder
  JWT-SSO-Vertrag. `app/lib/api.dart:27,54–62` hält normales Token im Speicher,
  HTTPS für Remote erforderlich und Redirects deaktiviert. Host/TLS prüft
  Onlineweb zusätzlich (`backend/online/web.py:132–154`).
- Rollen owner/manager/technician/accountant (`backend/core.py:45`). Frischer Userstatus
  vor Zugriff und `Office.project` prüft Projektzuordnung für alle Nichtowner
  (`backend/core.py:384–406`). Owner kann sämtliche Projekte sehen. Selbstschutz gegen
  letzten Owner und Session-/Offlinewiderruf bei Rollen-/Passwortänderung
  (`backend/core.py:335–340`). Keine Firma/Mandanten-FK in diesen Regeln.
- Projektmappe: owner/manager/technician schreiben; Profil nur owner/manager
  (`backend/project_workspace.py:17,178–186`). Finanzintegration nur owner/accountant;
  andere Rollen erhalten Sevdesk nicht serialisiert
  (`backend/external_integrations.py:315–321`, `backend/online/integrations_service.py:266–273`).
- Offline-Gerätezugang separat `offline_` und `offline_workspace_`, sieben Tage,
  Hash/Fingerprint gebunden an aktuelle Rolle/Passwort/Aktivstatus
  (`backend/plan_access.py:11–49`). Online-Routenallowlist `backend/online/web.py:325–332` erlaubt nur
  zugewiesene Pläne, Planquellen, Löschfeed und expliziten Workspacebereich.
  Inbox, Finanzintegrationen, Admin und Reporte bleiben außerhalb.
- Lokaler Offlinecache: AES256GCM-Snapshots/Assets, Konten-/Serverscope,
  Schlüssel und Gerätetoken im OS-SecureStorage, biometrischer/Device-Unlock
  (`app/lib/offline_vault.dart:18–45,137–207`, `app/lib/offline_assets.dart:30,253–275`).
  iOS-Verzeichnisschutz/Backupausschluss wird per Nativechannel aufgerufen
  (`app/lib/offline_vault.dart:190–193`, `ios/Runner/AppDelegate.swift`). Kein SQLite-
  Appcache und keine belegte Web-IndexedDB-/Serviceworker-Offlineschicht.
- Gmail-Intake **SPIN** und Projektbot **SPIX** sind andere Rechtebereiche,
  keine normalen Appbearer. SPIN nur Mail-/Anhangseingang; SPIX nur Jobs lesen/
  Ergebnisse zustellen. Beide Hash/Expiry/freshactiveowner; keine Fach-API-
  Rechte aus dem Präfix ableiten (`backend/inbound_connectors.py:144–183`,
  `online/integration_bot_service.py:310–362`, `online/web.py:226–282`).


## 4. Ist-Datenmodell: Tabellen und Beziehungen

Statische DDL-Erfassung ergibt **38 unterschiedliche Tabellennamen**:
**36 im Online-Office-Schema**, davon **30 auch im regulären lokalen Office-
Start**, sowie **2 nur im eigenständigen Import-CLI-Store**. PostgreSQL-only
gegenüber lokalemOffice: `smartplan_schema`, `mfa`, `auth_challenges`,
`login_limits`, `plan_imports`, `plan_import_chunks`. Der Online-Testadapter kann
einzelne SQLitezusätze anlegen; das macht lokalen Windows-Office nicht zur
produktiven PostgreSQL-/Importinstallation.

Alle fachlichen JSON-Payloads sind TEXT-Spalten plus Anwendungsvalidatoren;
kein implizites ORM-Schema für Rechnungen, Zeit, Lieferanten, Artikel oder
Mandanten. UUIDähnliche IDs sind überwiegend32hexTEXT. In SQLite/PG sind
Payload-/Receipt-Hashes und Fremdschlüssel zusätzlich zu Rollenprüfung vorhanden.
`audit.user_id/object_id` sind ohne SQL-FK, `plan_deletions.object_id` ist
polymorph, Workspaceversionen haben keinen direkten SQL-FK zur aktuellen
Itemversion; dies sind bewusst als solche zu benennende logische Beziehungen.

Die folgende Tabelle und die DDL-Blöcke werden unmittelbar aus statischem
Quelltext erfasst; kein Schema wurde zur Analyse ausgeführt.

| Tabelle / Geltung | Spalten | Primärschlüssel | SQL-Fremdschlüssel | DDL-Beleg |
|---|---|---|---|---|
| `assignments` (Office shared) | `user_id`, `project_id` | user_id, project_id | user_id → users(id); project_id → projects(id) | `backend/online/store.py:146` |
| `audit` (Office shared) | `id`, `user_id`, `action`, `object_id`, `at` | id | keine SQL-FK | `backend/online/store.py:152` |
| `auth_challenges` (nur Online-Office) | `token`, `user_id`, `credential`, `secret`, `expiry`, `failures` | token | user_id → users(id) | `backend/online/store.py:157` |
| `customers` (Office shared) | `id`, `name`, `contact`, `email`, `phone`, `address`, `notes`, `active`, `dedupe_key`, `created_at`, `updated_at` | id | keine SQL-FK | `backend/online/store.py:139` |
| `external_bridge_jobs` (Office shared) | `id`, `provider`, `owner_id`, `kind`, `generation`, `requested_generation`, `resource`, `project_id`, `revision`, `selection_json`, `request_hash`, `status`, `payload_json`, `payload_sha256`, `source_id`, `error_code`, `created_at`, `expires_at`, `completed_at` | id | provider → external_connections(provider); owner_id → users(id); project_id → projects(id) | `backend/integration_bridge.py:31` |
| `external_bridge_limits` (Office shared) | `provider`, `token_hash`, `window_start`, `request_count` | provider, token_hash | provider → external_connections(provider) | `backend/integration_bridge.py:56` |
| `external_connections` (Office shared) | `provider`, `id`, `owner_id`, `config_cipher`, `credential_cipher`, `identity_json`, `generation`, `state`, `created_at`, `updated_at` | provider | owner_id → users(id) | `backend/external_integrations.py:38` |
| `external_oauth_states` (Office shared) | `state_hash`, `provider`, `owner_id`, `session_hash`, `config_hash`, `generation`, `payload_cipher`, `expires_at`, `created_at` | state_hash | provider → external_connections(provider); owner_id → users(id) | `backend/external_integrations.py:68` |
| `external_project_links` (Office shared) | `project_id`, `provider`, `remote`, `selection_json`, `active`, `revision`, `generation`, `updated_by`, `updated_at`, `error_code` | project_id, provider | project_id → projects(id); provider → external_connections(provider); updated_by → users(id) | `backend/external_integrations.py:47` |
| `external_requests` (Office shared) | `user_id`, `request_id`, `provider`, `operation`, `project_id`, `request_hash`, `result_json`, `created_at` | user_id, request_id | user_id → users(id); provider → external_connections(provider); project_id → projects(id) | `backend/external_integrations.py:61` |
| `external_snapshots` (Office shared) | `project_id`, `provider`, `generation`, `revision`, `payload_json`, `payload_sha256`, `synced_at` | project_id, provider | (project_id,provider) → external_project_links(project_id,provider) | `backend/external_integrations.py:55` |
| `inbound_import_tokens` (Office shared) | `id`, `owner_id`, `name`, `source_account`, `token_hash`, `created_at`, `expires_at`, `revoked_at`, `last_used_at`, `window_started_at`, `window_count` | id | owner_id → users(id) | `backend/inbound_connectors.py:27` |
| `inquiries` (Office shared) | `id`, `source`, `source_account`, `source_id`, `source_fingerprint`, `subject`, `message`, `sender_name`, `sender_email`, `sender_phone`, `received_at`, `status`, `review_method`, `acceptance_channel`, `customer_id`, `project_id`, `next_action`, `due_date`, `sevdesk_url`, `provenance`, `revision`, `created_by`, `created_at`, `updated_at` | id | customer_id → customers(id); project_id → projects(id); created_by → users(id) | `backend/inquiries.py:36` |
| `inquiry_attachment_chunks` (Office shared) | `attachment_id`, `chunk_index`, `data`, `sha256`, `size` | attachment_id, chunk_index | attachment_id → inquiry_attachments(id) | `backend/inquiry_attachments.py:56` |
| `inquiry_attachment_limits` (Office shared) | `token_id`, `window_started_at`, `window_count` | token_id | token_id → inbound_import_tokens(id) | `backend/inquiry_attachments.py:62` |
| `inquiry_attachment_sets` (Office shared) | `inquiry_id`, `manifest_hash`, `expected_count`, `total_bytes`, `created_at` | inquiry_id | inquiry_id → inquiries(id) | `backend/inquiry_attachments.py:40` |
| `inquiry_attachments` (Office shared) | `id`, `inquiry_id`, `source_attachment_id`, `filename`, `media_type`, `size`, `sha256`, `status`, `created_at`, `updated_at`, `deleted_at` | id | inquiry_id → inquiries(id) | `backend/inquiry_attachments.py:46` |
| `inquiry_requests` (Office shared) | `user_id`, `request_id`, `request_hash`, `result` | user_id, request_id | user_id → users(id) | `backend/inquiries.py:52` |
| `jobs` (CLI separat) | `job_id`, `request_id`, `source_id`, `page`, `status`, `created_at`, `updated_at`, `attempts`, `worker_id`, `lease_token`, `lease_until`, `result_token`, `result_hash`, `manifest`, `error_code`, `error_message` | job_id | source_id → sources(source_id) | `backend/plan_import/store.py:207` |
| `login_limits` (nur Online-Office) | `key`, `failures`, `reset_at` | key | keine SQL-FK | `backend/online/store.py:160` |
| `mfa` (nur Online-Office) | `user_id`, `secret`, `last_step`, `recovery` | user_id | user_id → users(id) | `backend/online/store.py:155` |
| `plan_deletions` (Office shared) | `deletion_id`, `kind`, `object_id`, `project_id`, `created_by`, `create_request_id`, `deleted_by`, `deleted_at`, `revision` | deletion_id | project_id → projects(id); created_by → users(id); deleted_by → users(id) | `backend/plan_deletions.py:14` |
| `plan_import_chunks` (nur Online-Office) | `import_id`, `chunk_index`, `data`, `sha256`, `size` | import_id, chunk_index | import_id → plan_imports(id) | `backend/online/plan_imports.py:46` |
| `plan_imports` (nur Online-Office) | `id`, `project_id`, `user_id`, `request_id`, `manifest_hash`, `filename`, `media_type`, `size`, `sha256`, `page`, `title`, `status`, `created_at`, `updated_at`, `attempts`, `lease_token`, `lease_until`, `error_code`, `preview`, `preview_sha256`, `result`, `result_sha256` | id | project_id → projects(id); user_id → users(id) | `backend/online/plan_imports.py:35` |
| `plan_requests` (Office shared) | `user_id`, `request_id`, `project_id`, `request_hash`, `result` | user_id, request_id | user_id → users(id); project_id → projects(id) | `backend/online/store.py:98` |
| `plan_sessions` (Office shared) | `token`, `user_id`, `expiry`, `credential` | token | user_id → users(id) | `backend/online/store.py:102` |
| `plan_versions` (Office shared) | `id`, `revision`, `project_id`, `payload` | id, revision | project_id → projects(id) | `backend/online/store.py:95` |
| `project_profiles` (Office shared) | `project_id`, `payload`, `revision`, `updated_by`, `updated_at` | project_id | project_id → projects(id); updated_by → users(id) | `backend/project_workspace.py:31` |
| `projects` (Office shared) | `id`, `name`, `customer`, `customer_id` | id | customer_id → customers(id) | `backend/online/store.py:143` |
| `reports` (Office shared) | `id`, `project_id`, `payload`, `pdf`, `pdf_hash`, `onedrive_id`, `rowid` | id | project_id → projects(id) | `backend/online/store.py:148` |
| `secrets` (Office shared) | `name`, `value` | name | keine SQL-FK | `backend/online/store.py:154` |
| `sessions` (Office shared) | `token`, `user_id`, `expiry` | token | user_id → users(id) | `backend/online/store.py:138` |
| `smartplan_schema` (nur Online-Office) | `version` | kein PK deklariert | keine SQL-FK | `backend/online/store.py:91` |
| `sources` (CLI separat) | `source_id`, `sha256`, `size`, `media_type`, `source_filename`, `created_at` | source_id | keine SQL-FK | `backend/plan_import/store.py:204` |
| `users` (Office shared) | `id`, `email`, `salt`, `password`, `role`, `active` | id | keine SQL-FK | `backend/online/store.py:135` |
| `workspace_items` (Office shared) | `id`, `project_id`, `kind`, `payload`, `revision`, `created_by`, `created_at`, `updated_by`, `updated_at` | id | project_id → projects(id); created_by → users(id); updated_by → users(id) | `backend/project_workspace.py:35` |
| `workspace_requests` (Office shared) | `user_id`, `request_id`, `project_id`, `request_hash`, `result` | user_id, request_id | user_id → users(id); project_id → projects(id) | `backend/project_workspace.py:46` |
| `workspace_versions` (Office shared) | `kind`, `object_id`, `revision`, `project_id`, `payload` | kind, object_id, revision | project_id → projects(id) | `backend/project_workspace.py:42` |


## 5. Bestehende API-Endpunkte


Außer den Rootpfaden `/health` und `/ready` sowie dem ausdrücklich lokalen `/oauth/callback` gilt der unten genannte API-Prefix.

Notation: `P`=32hexProjekt, `I`=32hexObjekt, `provider`=sevdesk/google_calendar/onedrive.
Im Onlinebetrieb ist der Prefix `/api/v1`; lokale gemeinsame Fachpfade heißen
`/api`. Ein aufgeführtes `GET,POST` bei Collection+Item beschreibt jeweils
beide Routenversionen; unerlaubte HTTPMethoden ergeben405. Der Flaskcatch-all
nennt PUT/PATCH/DELETE nur für kontrollierte Methodenablehnung, nicht als
universelle freie CRUD-Unterstützung (`backend/online/web.py:299–311`).

| Methoden | Relativer Pfad | Geltung / Auth / Beleg |
|---|---|---|
| GET | `/health`; online zusätzlich `/ready` | Öffentlich, DB/Sourcemetadaten; `backend/online/web.py:191–201`, `backend/server.py:90`. |
| POST | `/login` | Lokal Passwort; online Passwort→MFAchallenge; `backend/online/web.py:203`, `backend/server.py:94`. |
| POST | `/login/verify` | Nur online MFA/Recovery; `backend/online/web.py:208`. |
| GET | `/me` | Normaler Sessionbearer; `backend/online/web.py:20,63`. |
| POST | `/logout` | Sessionwiderruf; `backend/online/web.py:65`. |
| POST | `/offline/access`, `/offline/logout` | Normale Sitzung stellt eingeschränkten Devicegrant aus / Devicegrant widerrufen; `backend/online/web.py:55–62`, `backend/server.py:113ff`. |
| GET, POST | `/users` | Ownerverwaltung; `backend/online/web.py:20,68`, Corecreate_user/users. |
| POST | `/users/I` | Owner, aktuelle Rollen/Passwort/Aktivierung; `backend/online/web.py:34,80`. |
| GET, POST | `/customers`, `/customers/I` | Owner-CRM; `backend/online/web.py:21,35,71,82`, Corecustomer-Methoden. |
| GET, POST | `/projects` | Projektliste nach Rolle/Assignment; ErstellungOwner; `backend/online/web.py:21,74`. |
| POST | `/projects/P/customer` | Explizite Kundenzuordnung; `backend/online/web.py:36,114`. |
| POST | `/assignments` | Ownerzuweisung/-entzug; `backend/online/web.py:21,76`. |
| GET | `/projects/P/assignments` | Projektteam; `backend/online/web.py:37,118`. |
| GET, POST | `/projects/P/plans`, `/projects/P/plans/I` | Versionierte manuelle Pläne; Sharedlocal+online, begrenzter Offlinegrant; `backend/online/web.py:33,107–113`. |
| POST | `/projects/P/plans/delete` | Bestätigte Tombstone-Löschung; `backend/online/web.py:26,108`; lokal ebenfalls. |
| GET | `/projects/P/plan-deletions` | Projektbezogener Löschfeed; `backend/online/web.py:27,85`. |
| GET, POST | `/projects/P/plan-imports` | Nur online, binärer Quellenimport anlegen/listen; `backend/online/web.py:28,87–93`. |
| GET | `/projects/P/plan-imports/I` | Online, aktuelle Metadaten; `backend/online/web.py:29,95`. |
| PUT | `/projects/P/plan-imports/I/chunks/N` | Online octetstream256KiB; `backend/online/web.py:30,97,312–319`. |
| POST | `/projects/P/plan-imports/I/complete` | Online, Uploadprüfung/Queue; `backend/online/web.py:31,99–102`. |
| GET | `/projects/P/plan-imports/I/source`, `/preview`, `/result` | Online, nur zugewiesener Scope; `backend/online/web.py:32,103–106`. |
| POST | `/projects/P/plan-imports/delete` | Online bestätigte Quellenlöschung; `backend/online/web.py:26,90`. |
| GET, POST | `/projects/P/reports` | Projektberichtsliste / Servicebericht oder Lieferschein; `backend/online/web.py:38,120`; lokal ebenfalls. |
| GET | `/reports/I`, `/reports/I/pdf` | Report/PDF nur Projektzugriff; `backend/online/web.py:39,124–127`. |
| POST | `/reports/I/sign` | Revision/Hash und Unterschriftsstriche; `backend/online/web.py:40,122–123`. |
| POST | `/reports/I/storage`, `/reports/I/onedrive` | Online expliziter unterschriebener PDF-Upload; lokal nur `/onedrive`; `backend/online/web.py:41,351–356`, `server.py`. |
| GET | `/storage/status` | Online auswählbare Storageadapter; lokal derselbe Pfad für den persönlichen OneDrive-Adapter; `backend/online/web.py:22,340`. |
| POST | `/storage/connect`, `/storage/provider`, `/storage/disconnect` | Online Owner; `backend/online/web.py:22–23,342–350`. |
| POST | `/storage/callback` | Online öffentlicher Microsoftform_post mit gebundenem State/Owner; `backend/online/web.py:213–225`. Lokal dagegen GET `/oauth/callback` außerhalb `/api` (`backend/server.py:96–100`). |
| GET, POST | `/inquiries`, `/inquiries/I` | Sharedowner-Inbox; `backend/workspace_api.py:24,27,139–148`. |
| GET | `/inquiries/connections` | Ownerquellenstatus; `backend/workspace_api.py:25,126`. |
| POST | `/inquiries/import-eml` | Expliziter gebundener EML-Import; `backend/workspace_api.py:26,128–138`. |
| POST | `/inquiries/I/convert` | Explizite Kunde/Projektübernahme, kein automatischer Auftrag; `backend/workspace_api.py:28,145`. |
| GET | `/inquiries/I/attachments`, `/inquiries/I/attachments/I/content` | Sharedowner-Anhangsliste/Original; `backend/workspace_api.py:29–30,105–115`. |
| POST | `/inquiries/I/attachments/I/delete` | Ownerdelete, kein leerer Erfolg nach Fehler; `backend/workspace_api.py:31,111–114`. |
| GET, POST | `/inbound/gmail/tokens` | Owner enge SPIN-Lieferkeys listen/erzeugen; `backend/workspace_api.py:32,150–152`. |
| POST | `/inbound/gmail/tokens/I/revoke` | Ownerwiderruf; `backend/workspace_api.py:33,153–157`. |
| GET, POST | `/projects/P/workspace` | Dashboard/Profilrevision; `backend/workspace_api.py:34,161–163`. |
| GET, POST | `/projects/P/tasks[/I]`, `/diary[/I]`, `/appointments[/I]`, `/links[/I]` | Sharedprojektbezogene versionierte Items; `backend/workspace_api.py:35,164–170`. |
| GET | `/projects/P/appointments/I/calendar` | Expliziter ICSDownload, kein CalDAVSync; `backend/workspace_api.py:36,166`. |
| GET | `/projects/P/mail-attachments`, `/projects/P/mail-attachments/I/content` | Nur dem zugeordneten Projekt sichtbar; `backend/workspace_api.py:37–38,116–124`. |
| POST | `/projects/P/mail-attachments/I/plan-import` | Onlinekopie in vorhandene Importqueue; lokaler Helper behandelt fehlendes Onlinemodul als409, keine vorgetäuschte lokale Workerfunktion; `backend/workspace_api.py:39,122–123`, `inquiry_attachments.py:copy_to_plan`. |
| GET | `/integrations`, `/projects/P/integrations` | OnlineSession; globalOwner, projektspezifisch Need-to-know/Finanzrolle; `backend/online/integrations_service.py:46–60,633–667`. |
| POST | `/integrations/sevdesk/connect`, `/disconnect`, `/catalog` | OnlineOwner, direkter lesender Provider; gleicher Beleg. |
| POST | `/integrations/google_calendar/configure`, `/connect`, `/disconnect`, `/catalog` | OnlineOwner, alternative OAuthkonfiguration bzw. ausgewählter Botmodus; gleicher Beleg. |
| GET | `/integrations/google_calendar/callback` | Online öffentlicher einmaliger OAuthstate; `backend/online/web.py:284–297`. Andere Provider in Callbackroute werden fachlich abgewiesen. |
| POST | `/integrations/bot/connect`, `/integrations/bot/sync` | OnlineOwner, SPIXBootstrap bzw. Katalogqueue; `backend/online/integrations_service.py:52–55,638–641`. |
| POST | `/integrations/onedrive/catalog`, `/disconnect` | OnlineOwner, Bot-Metadaten; `backend/online/integrations_service.py:55–56`. |
| POST | `/projects/P/integrations/provider/preview`, `/link`, `/sync`, `/unlink` | Online, frische Generation/Revision/Session; Owner schreibt Zuordnung, Team liest freigegebene Snapshots; `backend/online/integrations_service.py:57–58,487ff`. |
| POST | `/intake/gmail` | Nur onlineöffentlicher enger SPIN-Eingang, keine Appsession; `backend/online/web.py:226–233`. |
| POST | `/intake/gmail/attachments` | SPINManifest; `backend/online/web.py:240–244`. |
| PUT | `/intake/gmail/attachments/I/chunks/N` | SPIN Binär256KiB; `backend/online/web.py:246–256`. |
| POST | `/intake/gmail/attachments/I/complete` | SPIN hashgeprüfter Abschluss; `backend/online/web.py:258–264`. |
| GET | `/intake/integrations/jobs` | Nur onlineöffentlicher enger SPIX-Eingang; `backend/online/web.py:272–274`. |
| POST | `/intake/integrations/jobs/I/result` | SPIX, Auth/Rate vor Parse, atomare Publication+Receipt; `backend/online/web.py:276–282`, `integration_bot_service.py:deliver`. |

Lokale Storagepfade sind GET `/api/storage/status` und POST `/api/storage/connect`;
Online ergänzt Providerwahl/Disconnect. Weitere exakte lokale Routinganker folgen unten; gemeinsame Workspacepfade besitzen zwar lokalen
Dispatcher, zentrale externe Intakes/Integrationsorchestrierung aber nicht.


## 6. Anfragen, Gmail und Originalanhänge: verbindlicher Ist-Vertrag

### Gmail-Eingang


#### Routen, Authentifizierung und HTTP-Grundregeln

| Route | Request | Erfolg | Autorisierung / Beleg |
| --- | --- | --- | --- |
| `POST /api/v1/intake/gmail` | JSON-Mailtext-Envelope | HTTP 201, `{id,status:"received",ingested_at}`; auch bei identischer Wiederholung | Ausschließlich `Authorization: Bearer SPIN_…`, nicht normale Sitzung/Offlinezugang; `backend/online/web.py:226`, `backend/inbound_connectors.py:155` |
| `POST /api/v1/intake/gmail/attachments` | JSON-Gesamtmanifest | HTTP 201, Upload-/Gesamtstand mit `chunk_size`; auch beim Fortsetzen | Derselbe SPIN-Typ, zusätzlich exakt ursprüngliches Postfach + ursprünglicher Owner; `backend/online/web.py:240`, `backend/inquiry_attachments.py:244` |
| `PUT /api/v1/intake/gmail/attachments/{id}/chunks/{index}` | Binär, `application/octet-stream` | HTTP 200, Dateimetadaten + `received_chunks` | Keine Login-/Leserechte; `backend/online/web.py:246`, `backend/inquiry_attachments.py:294` |
| `POST /api/v1/intake/gmail/attachments/{id}/complete` | JSON `{}` | HTTP 200, Datei `status:"ready"` bei geprüftem vollständigem Original | `backend/online/web.py:258`, `backend/inquiry_attachments.py:339` |

Gemeinsame Regeln: HTTPS und exakt konfigurierter öffentlicher Host erforderlich (`backend/online/web.py:151`); Header `Cache-Control: no-store`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer`, CSP ohne aktive Inhalte (`backend/online/web.py:156`). Normales globales HTTP-Bodylimit 1.000.000 Bytes (`backend/online/web.py:147`), für Binärchunk individuell 262.144 Bytes (`backend/online/web.py:250`). Binärupload lehnt andere MIME-Typen mit 415 und Content-Encoding außer `identity` mit 400 ab (`backend/online/web.py:251`).

Fehler: JSON `{error: <deutsche feste/validierte Meldung>}`. Problem-429 setzt aktuell `Retry-After: 300`; tatsächliche Ratefenster sind 60 Sekunden. Ungültiges JSON 400, falscher Content-Type 415, HTTP-Übergröße 413, Methode 405, unbekannte Funktion 404; unerwartete Fehler generisch 500 ohne Request-/Credential-/SQL-Logging (`backend/online/web.py:164`, `:172`). Keine Annahme, jeder Proxyfehler sei JSON: Mailbot behandelt unbestätigte Antworten ausdrücklich als unbestätigt (`integrations/mail_bot/send_inquiry.py:178`).

#### Erlaubte Body-Felder des Mailtexteingangs

Empfänger akzeptiert genau sieben mögliche Felder; die ersten vier sind erforderlich (`backend/inbound_connectors.py:156`). Zusätzliche Felder wie `source`, `request_id`, `status`, `customer_id` oder `attachments` werden mit 400 abgelehnt. Kein Freitext-POST mit integrierten Dateien, kein Datei-URL-Fetch.

| Feld | Ist-Vertrag |
| --- | --- |
| `source_account` | Erforderliche Postfachadresse, max. 254 Zeichen, getrimmt und kleingeschrieben; einfache Mail-Syntax; muss exakt zur Tokenbindung passen. Es ist das Empfängerpostfach, NICHT die Kundenadresse (`backend/inbound_connectors.py:69`, `:165`, `:172`). |
| `source_id` | Erforderliche stabile native Gmail-Nachrichten-ID, Regex `[A-Za-z0-9_-]{1,128}`. Keine vom Bot wechselnd generierte neue ID bei Konflikt (`backend/inbound_connectors.py:166`). |
| `subject` | Erforderlich, getrimmt, nicht leer, max. 300 Unicode-Zeichen; keine Steuerzeichen (`backend/inquiries.py:86`, `:406`). |
| `message` | Erforderlich, lesbarer Text, max. 40.000 Zeichen; CRLF/CR werden zu LF normalisiert, LF/Tab sind erlaubt, andere C0-Steuerzeichen nicht; außen getrimmt (`backend/inquiries.py:86`, `:407`). |
| `sender_name` | Optional, Standard leer, max. 200 Zeichen (`backend/inquiries.py:408`). |
| `sender_email` | Optional, Standard leer, max. 254 Zeichen; falls gesetzt einfache syntaktische Prüfung; gespeicherte Originalschreibweise bleibt, Matching normalisiert (`backend/inquiries.py:104`, `:409`). |
| `received_at` | Optional; ISO-Zeitstempel MIT Zeitzone, max. 64 Zeichen; Speicherung UTC sekundengenau. Ohne Feld initiale Serverzeit. Wiederholungen müssen das Feld unverändert mitsenden oder stets weglassen (`backend/inquiries.py:135`, `:412`). |

Zusätzlich wird das Envelope durch serverseitige JSON-Serialisierung (`ensure_ascii=False`, `allow_nan=False`) in UTF-8 auf 200.000 Bytes begrenzt; dies ist nicht einfach die Länge des eingehenden HTTP-Strings (`backend/inbound_connectors.py:160`). JSON-Array wird abgelehnt. Die Flask-Standard-JSONverarbeitung und der CLI-Parser sind nicht vollständig identisch: Der CLI erkennt doppelte JSON-Schlüssel explizit, die Flask-`body()`-Funktion verwendet `request.get_json()` ohne eigenen Duplicate-Key-Hook (`integrations/mail_bot/send_inquiry.py:37`, `backend/online/web.py:185`). Dies ist eine zu dokumentierende Vertragsecke; eine spätere Verschärfung nicht beiläufig als scheinbar unverändertes Verhalten einführen.

Response ist bewusst exakt schmal: interne Anfrage-ID (32 kleine Hexzeichen), `status:"received"`, `ingested_at` als UTC-Zeit dieser erfolgreichen Bestätigung. `ingested_at` darf bei Replay variieren und ist kein Datum der Originalmail. Keine Kunden-/Kandidaten-/Mailtexte-/Finanzfelder und keine Tokenmetadaten (`backend/inbound_connectors.py:184`, Test `backend/test_inbound_connectors.py:62`).

#### SPIN-Zugang – Lebenszyklus und Scope

Owner erstellt/listet/widerruft Tokens über normale nach MFA erhaltene App-Sitzung:

- `GET/POST /api/v1/inbound/gmail/tokens`, Ausgabe bei Erstellung HTTP 201; Request `{name,source_account,expires_days?}`. Namen max. 100, Laufzeit Standard 90, zulässig ganzzahlig 1–365 Tage. Maximal 20 aktive Tokens pro ausstellendem Owner (`backend/workspace_api.py:32`, `:149`, `backend/inbound_connectors.py:99`).
- `POST /api/v1/inbound/gmail/tokens/{id}/revoke` mit `{}`, idempotent HTTP 200; nur ausstellender Owner darf dieses Token verwalten (`backend/inbound_connectors.py:130`). Ein anderer Owner sieht nicht dessen Tokenliste (`:124`).
- Neue Rohcredentials `SPIN_` + 43 URL-sichere Zeichen, kryptografisch erzeugt; nur beim Erstellen ausgegeben, serverseitig nur SHA-256 gespeichert. Metadaten `id,name,source_account,created_at,expires_at,revoked_at,last_used_at`; kein Hash im Listenresponse (`backend/inbound_connectors.py:94`, `:114`).
- Jede Lieferung prüft Tokenformat, Hash, aktuellen Ablauf/Widerruf UND aktive aktuelle Ownerrolle des Ausstellers. Rollenänderung/Deaktivierung sperrt auch bereits ausgegebene Importtokens sofort (`backend/inbound_connectors.py:144`).
- Kein Office-Login, keine Sessions, keine allgemeine Inbox-/Kunden-/Projekt-/Finanz-Leseberechtigung. Normale App-/MFA-Challenge-/Offline-Tokens ersetzen den Importtoken nicht (`backend/online/web.py:226`, `backend/core.py:387`, `backend/online/test_workspace_api.py:357`, `backend/online/test_inquiry_attachments_api.py:218`).
- `last_used_at` wird nur nach erfolgreichem Mailtext-Create/Replay gesetzt; eine Anhangsvollständigkeit oder reale fortlaufende Gmail-Synchronisation lässt sich daraus NICHT ableiten (`backend/inbound_connectors.py:181`).

Online-App-MFA erzeugt erst nach erfolgreicher Prüfung eine Sitzung (`online/auth.py:125`). Neue API-Sitzung ist acht Stunden gültig; die sieben Tage Offlinezugang betreffen die bestehenden Projektfunktionen, nicht die Inbox (`backend/online/auth.py:125`, `backend/online/web.py:325`, `app/lib/main.dart:372`). Inbox/Kundenbearbeitung bleibt online.

#### Idempotenz, Transaktion und Rate Mailtext

Kanonische Eindeutigkeit ist `(source='gmail', source_account, source_id)` über DB-UNIQUE (`backend/inquiries.py:48`), zusätzlich abgeleitete Mutations-ID `sha256('gmail\n'+account+'\n'+source_id)[:32]` (`backend/inbound_connectors.py:177`). Anfrage-Receipts sind pro `(user_id,request_id)` gespeichert (`backend/inquiries.py:52`, `:307`).

- Identischer Retry nach verlorener Antwort, Neustart oder Tokenrotation erzeugt keine weitere Anfrage. Derselbe Postfach-/Mail-ID-Inhalt wird auch bei einem anderen Owner als bestehende Anfrage bestätigt (Test `backend/online/test_inquiry_attachments_api.py:262`).
- Geänderter normalisierter Inhalt bei derselben Source-Identität führt 409; keinesfalls mit neuer erfundener ID umgehen. Request-Replay mit verändertem explizitem Zeitstempel führt ebenfalls 409. Source-Fingerprint enthält den Mailinhalt und Provenienz, aber nicht `received_at`; bei anderem Owner kann daher nur ein expliziter Zeitstempelunterschied über die source-dedup-Ebene toleriert werden. Den dokumentierten konservativen Vertrag (Zeitstempel konstant) beibehalten (`backend/inquiries.py:413`, `:423`).
- Replay auf Mutations-ID gibt das gespeicherte historische Ergebnis zurück. Der minimale öffentliche Receiverresponse bleibt trotzdem nur received/id/aktueller Bestätigungszeitpunkt, auch wenn die Anfrage inzwischen fachlich weiterbearbeitet wurde.
- Eine Transaktion umfasst frische Tokenprüfung, Erstellen/Replay der Anfrage, Audit/Receipt und `last_used_at`+Ratezähler. Später Fehler rollt alles zurück. SQLite SAVEPOINT wahrt äußere Transaktionen; PostgreSQL nutzt verschachtelte Transaktionen plus globalen Advisory-Lock (`backend/inbound_connectors.py:43`, `backend/inquiries.py:66`, `online/store.py:51`). Kein Netzaufruf innerhalb dieses Empfangspfads.
- Max. 60 ERFOLGREICHE Mailtext-Übernahmen inkl. Replay pro Minute und Token; persistierter Zähler im Tokendatensatz. Fehlgeschlagene Mailtextlieferungen zählen nach aktuellem Vertrag nicht mit (`backend/inbound_connectors.py:174`, `openapi.json:109`). Ein pauschaler Wechsel auf IP-/Account-/Fehlversuchszählung wäre keine unveränderte Fortschreibung dieses Vertrags.

### Originalanhänge – genauer Ist-Vertrag

#### Manifest und Limits

`POST /attachments` erwartet exakt `{source_account,source_id,attachments}`. Ursprünglicher Mailtext muss bereits existieren und dem gleichen gebundenen Postfach UND ausstellenden Owner gehören. Tokenrotation mit gleichem Owner/Postfach ist möglich; anderer Owner kann den deduplizierten Body sehen lassen, aber die ursprünglichen Dateien nicht hochladen/verändern (`backend/inquiry_attachments.py:265`, `:168`, API-Test `backend/online/test_inquiry_attachments_api.py:249`). Das ist eine bestehende bewusst getestete Asymmetrie zwischen Mailtext-Dedupe und Dateiupload-Scope.

Jede Beschreibung enthält exakt `{source_attachment_id,filename,media_type,size,sha256}` (`backend/inquiry_attachments.py:114`):

- Original-Anhang-ID ist opaquer druckbarer String mit 1–2048 Zeichen; NICHT auf Gmail-Body-ID-Regex reduzieren. Slash/`=` dürfen in dieser Provider-ID vorkommen.
- Dateiname 1–200 Zeichen, druckbar, keine Slash-/Backslash-Pfade, nicht `.`/`..`, getrimmt; kein Server-Dateipfad.
- MIME-Type ohne Parameter, syntaktische `type/subtype`-Prüfung, Speicherung kleingeschrieben. Für Originalspeicherung keine pauschale PDF/Bild-Allowlist.
- Positive ganzzahlige Originalgröße max. 20 MiB pro Datei; SHA-256 des vollständigen Originals als 64 kleine Hexzeichen.
- Max. 30 Dateien; max. 60 MiB je Mail; max. 2 GiB global reservierte Dateigrößen. Hochzuladende und fertige Dateien zählen zur globalen Quota, gelöschte nicht. Quota wird nicht anhand bereits eingegangener Chunkbytes kleingerechnet (`backend/inquiry_attachments.py:22`, `:256`, `:278`).

Manifest ist nach erster Bestätigung unveränderlich, reihenfolgeunabhängig gehasht, ursprüngliche IDs eindeutig; identisches Reannounce zeigt denselben Dateistand/IDs. Unterschiedlicher Inhalt führt 409, nicht Merge/Ersetzen. `attachments: []` ist eine explizite verifizierte Aussage: null Anhänge. Kein Manifest bedeutet `status:not_announced, expected_count:null` und darf NICHT in anhanglos umgedeutet werden (`backend/inquiry_attachments.py:228`, `:272`).

Manifestresponse: `status` (`uploading|complete`), `expected_count`, `ready_count`, `deleted_count`, `total_bytes`, `files`, zusätzlich `chunk_size:262144`. Jede Datei hat `id`, ursprüngliche fünf Descriptorfelder, `status` (`uploading|ready|deleted`) und bei Botresponses `received_chunks`. Gelöschte Dateien bleiben in Botresponses als Tombstones, werden in normalen UI-Dateilisten ausgefiltert (`backend/inquiry_attachments.py:221`, `:239`, `:290`). `total_bytes` ist das ursprüngliche Gesamtmanifest einschließlich gelöschter Originalgrößen; nicht verbleibende Livebytes.

#### Chunkupload, Abschluss, Bestätigung

- 256 KiB Chunks; sämtliche Zwischenchunks exakt 262.144 Bytes, letzter exakt Restgröße. Index im erwarteten Bereich, beliebige Reihenfolge möglich (`backend/inquiry_attachments.py:294`).
- Identischer bereits gespeicherter Chunk ist wiederholbar, auch wenn Datei bereits fertig ist; abweichende Bytes für denselben Index 409. Ready-Datei nimmt keine neuen fehlenden Abschnitte an. Deleted-Datei 410, kein Wiederbeleben (`:303`, `:174`).
- `complete` liest und prüft gespeicherte Abschnitte (Index, Abschnittgröße, Abschnittsha), Gesamtlänge und Originalsha. Fehlende/falsche Gesamtdatei 409. Erst dann Status ready; Wiederholung stabil (`:316`, `:339`). Speicher-/Integritätsfehler außerhalb erwarteter Problems ergeben generische 500 ohne Bytes-/Dateinamensleck (API-Test `backend/online/test_inquiry_attachments_api.py:333`).
- Upload-Operationen haben eigenen persistenten Tokenzähler max. 600 pro Minute, unabhängig von 60 Body-Quittungen. Authentifizierte fachliche Fehler (z. B. unbekannte/fremde/gelöschte ID oder falscher Gesamthash) zählen bei Domain-Aufrufen ebenfalls, Dateiänderungen werden dabei zurückgerollt. Ungültige Tokens erhalten keinen Zähler (`backend/inquiry_attachments.py:178`, `:191`). HTTP-Vorprüfungen, die die Domain gar nicht erreichen (z. B. Content-Type/HTTP-Bodylimit), sind davon ausgenommen; daher nicht behaupten, ausnahmslos jeder HTTP-Fehler zähle.
- Body, Manifest und jeder Upload/Abschluss sind einzelne Transaktionen. SQLite startet standalone `BEGIN IMMEDIATE` vor Quota-Prüfung und verwendet Savepoints; dies verhindert parallele Überreservierung. PostgreSQL nutzt Office-Transaktion/Advisory-Lock (`backend/inquiry_attachments.py:78`, Test `backend/test_inquiry_attachments.py:291`).
- Dateiinhalt liegt in `inquiry_attachment_chunks.data` (SQLite BLOB/PostgreSQL BYTEA), nicht im Dateisystem oder auf Dropbox/OneDrive. Gesamte Originaldatei wird zum Prüfen/Download im RAM zusammengefügt; maximal 20 MiB (`backend/inquiry_attachments.py:36`, `:316`). Keine Dateiausführung, MIME-Konvertierung, OCR oder Providerdownload durch das Backendmodul.
- Eine Mail ist nach Botvertrag vollständig erst, wenn nach allen Dateiabschlüssen das unveränderte Gesamtmanifest erneut abgefragt und die complete-Quittung mit IDs, vollständigen Metadaten/Hashes/Größen und Zählern validiert wurde. `ready_count+deleted_count==expected_count`. Absichtlich gelöschte Originale sind gültige terminale Tombstones (`integrations/mail_bot/send_attachments.py:209`, `:237`). `received` allein bleibt Teilerfolg.

#### Lesen, Projektübergabe, Planübernahme, Löschen

Private App-Routen unter `/api/v1`:

- `GET /inquiries/{iid}/attachments`, `GET /inquiries/{iid}/attachments/{aid}/content`, `POST /inquiries/{iid}/attachments/{aid}/delete {}`: Owner-only, aktuelle Rolle/Aktivierung wird neu gelesen (`backend/workspace_api.py:29`, `:105`, `backend/inquiry_attachments.py:144`, `:152`).
- `GET /projects/{pid}/mail-attachments`, `GET /projects/{pid}/mail-attachments/{aid}/content`: Owner oder aktuell zugewiesener aktiver Nutzer; Datei nur wenn Anfrage tatsächlich converted UND genau mit diesem Projekt verknüpft (`backend/workspace_api.py:37`, `backend/inquiry_attachments.py:158`, `:211`). Im aktuellen Modell können auch zugewiesene Buchhaltung/Techniker sämtliche so verknüpften Originale lesen. Es existiert keine dokumentweise Vertraulichkeitsklassifikation. Das genügt einem differenzierten neuen Need-to-know-Modell noch nicht.
- Downloads mit normaler App-Sitzung, `application/octet-stream`, attachment-Disposition mit RFC5987-Dateinamen, `no-store/nosniff`; kein öffentlicher/Bot-Download und kein Inline-Originalrendern (`backend/workspace_api.py:43`, `:108`, `online/web.py:45`). Offlinezugänge werden auf diesen Routen ausdrücklich ausgeschlossen (`backend/online/web.py:325`, API-Test `backend/online/test_inquiry_attachments_api.py:218`).
- `POST /projects/{pid}/mail-attachments/{aid}/plan-import` mit exakt `{request_id,page,title}`: Owner/zugewiesener Manager/Techniker; Accountant darf lesen, nicht kopieren. Nur PDF/JPEG/PNG als Planquelle, separate PlanImports-Validierung/Queue. Wiederholung an dieselbe Original-ID gebunden, auch bei bytegleichen anderen Dateien (`backend/inquiry_attachments.py:410`). Quelle wird explizit kopiert, nicht im Hintergrund digitalisiert; Inquiries.create/convert startet keinen Planimport.
- Original löschen: Owner bestätigt, Chunks werden physisch aus aktiver DB gelöscht, Metadaten/Manifest/Dateiname/Hashes/Tombstone bleiben, Audit genau einmal. Wiedereinlieferung kann Datei nicht wiederherstellen. Bereits angelegte Planimportkopie bleibt unabhängig erhalten; Löschen eines Planimports lässt das Original ebenso bestehen (`backend/inquiry_attachments.py:398`, Tests `backend/test_inquiry_attachments.py:317`, `:411`).

Projektaggregation meldet `pending_count` und `unannounced_count`. Bei unbekanntem Manifest bleibt `expected_count:null`; bei Uploads Status uploading. Beide Aspekte können gleichzeitig vorkommen; aktuelle Aggregation priorisiert bei Statusstring uploading, separate Zähler bleiben maßgeblich (`backend/inquiry_attachments.py:357`). Conversion selbst prüft die Dateivollständigkeit nicht und legt auch keinen Kopierjob an.

### Anfragen → Kontakt/Kunde → Projekt

#### Eingang und Bearbeitung

Neue Anfrage speichert Quelle/Account/native ID, Betreff, Nachricht, Sender, Datum, Provenienz, Revision 1 und Creator; Status new, noch ohne Kunde/Projekt (`backend/inquiries.py:390`, `:430`). Keine automatische Kontakterstellung anhand jeder Mail, kein Newsletter/Sig-Mining, keine automatische Auftragserkennung. Inbox und Kandidaten nur Owner (`backend/inquiries.py:294`).

Exakte Kandidaten aus aktiven Kunden: E-Mail NFKC+casefold, Telefon konservativ Ziffern/+ bzw.00-Normalisierung; mehrere Treffer bleiben explizit. Kein probabilistischer Merge, keine automatische Zuordnung. `+49…` wird nicht automatisch mit nationalem `0…` gleichgesetzt, keine automatische Länderannahme (`backend/inquiries.py:111`, `:321`).

Private API-Routen und Erfolgscodes: `/inquiries` GET 200/POST 201; `/inquiries/{id}` GET/POST 200; `/inquiries/import-eml` POST 201; `/inquiries/{id}/convert` POST 200 (`backend/workspace_api.py:24`, `:125`). Listen-Domain Standard max.200, max.500 möglich; HTTP-Dispatch ruft derzeit ohne Pagination-/Statusparameter auf, Oberfläche filtert lokal. Kein vollwertiger serverseitiger CRM-Suchindex/Pagination (`backend/inquiries.py:361`, `backend/workspace_api.py:139`).

Mutable Bearbeitungsfelder: status, review_method, acceptance_channel, customer_id, next_action, due_date, sevdesk_url; `request_id`+positive `revision` erforderlich. Betreff/Nachricht/Originalsender bleiben als Provenienz unverändert. Wiedervorlagedatum echtes Kalenderdatum. Nur HTTPS-Links zu sevdesk.de/subdomains, keine URLs mit Credentials (`backend/inquiries.py:441`, `:147`).

Statusmenge: new/callback/review/offer/awaiting_acceptance/accepted/qualified/declined/converted. Keine zwingende Reihenfolge. `accepted` ist optional, ausdrücklich erfasste Zusage braucht Kanal phone/email/other. `converted` darf nur durch tatsächliche Projektübernahme gesetzt werden. Declined muss vor Übernahme bewusst reaktiviert werden (`backend/inquiries.py:27`, `:451`, `:481`, `:513`).

#### Atomare Projektanlage

Convert-Request: `{request_id,revision,project_name,customer_id}` ODER `{request_id,revision,project_name,customer:{name,contact?,email?,phone?,address?,notes?,active?}}`. Genau bestehender ODER bestätigter neuer Kunde; aktive Kunden erforderlich (`backend/inquiries.py:491`). Übernahme direkt aus new zulässig, ohne Zusage/Finanzzustände zu erfinden.

Transaktion beinhaltet Kundenneuanlage falls explizit angefordert, Projektneuanlage, Anfrage→Kunde/Projekt-Verknüpfung, status converted, Revision/Audits/gespeicherte Quittung. Derselbe Request erzeugt keine weiteren Projekte/Kunden. Späte Fehler rollen alles zurück. Die Domain verwendet bewusst niedrigstufiges `insert_customer`+validierten Projektinsert innerhalb EINER Transaktion, nicht verschachtelte früh commitende SQLite-Kernmethoden (`backend/inquiries.py:505`, `:520`, `:523`, `:532`; Tests `backend/test_inquiries.py:167`, `:185`).

Kundendubletten werden über NFKC/casefold/Whitespace-normalisierten NAMEN+ADRESSE abgewiesen (409), nicht automatisch vorhandener Kunde übernommen. Ein gleicher Name an anderer Adresse ist erlaubt; gleiche E-Mail bei mehreren Kunden führt explizit mehrere Vorschläge (`backend/core.py:108`, `:128`, `:213`).

Übernahme erzeugt KEINE Mitarbeiterzuordnung. Mitarbeiterzuordnung über separaten Owner-POST `/assignments` (`backend/core.py:352`). Für A4 wären Zuweisungsregeln, deren Berechtigungen/Atomarität und fehlende Mitarbeiter ausdrücklich neu zu definieren.

Aktuelle UI: Owner öffnet Anfragen aus Projekt-/Workspace-Navigation, Formular „Manuell / Telefon“, „WhatsApp-Nachricht einfügen“, „E-Mail manuell erfassen“. Subject+Message Pflicht, Name/E-Mail/Telefon optional; ein anonymer Rückruf ohne Kontaktdaten ist technisch möglich. Telefonische Erfassung ist kein automatischer Telefon-/WhatsApp-Connector (`app/lib/main.dart:401`, `app/lib/inquiry_pages.dart:602`, `:646`). Dirty-Notizen werden vor Projektanlage gespeichert; Datenverlust-/Retryfälle sind berücksichtigt (`app/lib/inquiry_pages.dart:1033`). Nach Übernahme lädt App Projekte und Offlineberechtigung vor Öffnen des neuen Projekts frisch (`app/lib/main.dart:409`).

#### EML und ältere Apps-Script-Bridge sauber abgrenzen

Manueller EML-Import max.512 KiB, base64 JSON; stdlib-MIME-Parser extrahiert Text/HTML als reinen Text und AnhangMETADATEN, KEINE Originalbytes. Das ist trotz vorhandener separater Gmail-Originalupload-API weiterhin die EML-Funktion (`backend/workspace_api.py:128`, `backend/inquiries.py:197`, `:270`, `:534`). Kein stilles Gleichsetzen dieser Importwege.

Vorbereitete Google-Apps-Script-Bridge: Gmail Advanced Service readonly + external_request; labelbasiert, max.20/Lauf, 240s Deadline, Cursor/Lock/Receiptprüfung, keine Mailveränderung/kein Versand. Lädt/überträgt ausdrücklich keine Anhänge (`integrations/google_apps_script/appsscript.json:10`, `integrations/google_apps_script/SmartplanGmail.gs:4`, `:36`, `:75`, `integrations/google_apps_script/SETUP.md:41`). Der neuere vorhandene Mailbot kann dagegen mit `send_attachments.py`/nativem API-Tool Originale separat übertragen (`integrations/mail_bot/README.md:79`). Kein unbekannter Bot wird durch diese Dateien bereits als angeschlossen bestätigt.

### CRM, Datenschutz, Aufbewahrung, Rollen

#### Heutige Kundenkartei

`customers` enthält id, name, contact, email, phone, address, notes, active, dedupe_key, created_at/updated_at. Genau ein Hauptansprechpartner, keine getrennten Privat-/Firmenkontakte, keine zusätzlichen Lieferanten-/Lead-Typen, keine Kommunikationshistorie oder DSAR-Verarbeitung (`backend/core.py:198`, `:105`).

API GET/POST Kunden + Kundendetail/-änderung ist Owner-only (`backend/core.py:224`, `:233`, `:241`, `:249`). App bietet Suche, Anlage/Bearbeitung, Archivieren/Reaktivieren, Projektzähler und Projektstart mit gewähltem Kunden, responsive auch am Telefon (`app/lib/customer_pages.dart:13`, `:58`, `:126`, `:138`). Nicht-Owner sehen in zugewiesenen Projekten nur bisherigen Kundennamen; neue granulare CRM-Rechte existieren nicht. Archivieren ändert nur active, löscht keine personenbezogenen Daten (`KUNDENVERWALTUNG.md:23`, `:40`).

Projekte tragen customer_id und redundanten Kundennamen. Änderung des Kundennamens aktualisiert Projektstamm; bereits erstellte Berichte/PDF behalten alte Snapshotdaten. `draft` übernimmt nur Kundennamen, nicht kompletten Kontakt-/Adressblock (`backend/core.py:260`, `:511`). sevdesk-Integration kann explizit ausgewählten Remote-Kontakt sowie ausgewählte Angebote/Rechnungen lesen/verknüpfen; keine automatische lokale Kontaktübertragung in neu erstellte Rechnungen/Briefköpfe (`online/integrations_service.py:104`, `:462`, `:487`, `backend/external_integrations.py:221`).

#### Datenorte und bestehende Schutzmaßnahmen

| Daten | Ort / Verhalten | Offene Grenze |
| --- | --- | --- |
| Normalisierter Mailtext/Personendaten | inquiries inkl. unveränderlicher Originalsender/-text/-provenienz (`backend/inquiries.py:36`) | Kein Anfrage-Lösch-/Anonymisierungs-/Retentiondatum/-export-Endpunkt. declined ist kein Löschen. |
| Historische Mutationsantworten | inquiry_requests.result enthält vollständige JSON-Ergebnis-Snapshots, inkl. personenbezogener Felder/Kandidaten/Metadaten (`backend/inquiries.py:52`, `:316`) | Kontaktänderung oder künftige Haupttabellenlöschung beseitigt diese Kopien nicht. Zwingend im Lösch-/Exportkonzept berücksichtigen; kein Replay darf gelöschte Daten neu offenlegen. |
| Kontakte | customers, Projekte: Name und ID (`backend/core.py:198`, `:261`) | active=false nur Archivierung; kein Betroffenenexport/-löschauftrag. |
| Originalanhänge | DB-BLOB/BYTEA-Abschnitte; Originalmetadata im unveränderlichen Manifest (`backend/inquiry_attachments.py:36`) | Owner-Löschung entfernt aktive Chunkbytes, behält Filename/hash/Metadaten/Tombstone. Diese Metadaten können selbst personenbezogen sein. |
| Plan-/Berichtskopien und Versionen | Getrennte kanonische PlanImports/plan_versions, reports/pdfs (`backend/core.py:148`, `backend/inquiry_attachments.py:410`) | Löschen des Anhangs entfernt bewusst KEINE Planquelle/Version/Berichtkopie; Fallprüfung/Aufbewahrungspflicht nötig. |
| Importzugänge | Hash + Owner/Postfach/Zeiten/Rate; Rohwert nur Erstellung (`backend/inbound_connectors.py:26`) | Widerruf löscht keine vorher gespeicherten Mail-/Datei-/Kontaktinformationen. |
| Audit | user_id, action, object_id, timestamp (`backend/core.py:150`, `:279`) | Mutationen nachvollziehbar, aber keine eigenständige fälschungssichere/DSGVO-Fallakte, kein fachlicher Löschgrund/Freigabe/Legal Hold/Leselog. |
| Datenbanksicherung | PostgreSQL pg_dump aller Tabellen, Zieldatei0600/Verzeichnis0700 + SHA256 (`online/backup.py:9`) | Backup ist kein Betroffenenexport, keine automatische kundenspezifische Löschung. Aufbewahrungsdauer/physische DB-Reclamation hier nicht geregelt. |

PostgreSQL-Disaster-Restore validiert kanonische Daten, löscht Sitzungen/Challenges/Trafficlimits und widerruft alte SPIN-Tokens; Originale/Anfragen/Kunden bleiben erhalten (`online/restore.py:40`). Es existiert eine Regression für unveränderte Original-/Plan-/Dateitombstone-Daten nach Restore (`online/test_release_attachments.py:200`). Ein neuer DSGVO-Löschprozess braucht einen dauerhaften datensparsamen Lösch-/Sperrvermerk und ein definiertes Wiederanwendungskonzept bei Restore, damit Backups gelöschte Personendaten nicht unkontrolliert reaktivieren. Die neuesten datensparsamen Lösch-/Sperrmarkierungen müssen dafür unabhängig vom rückzusichernden Snapshot gesichert und vor Wiederfreigabe abgeglichen werden; fehlt der aktuelle Nachweis, bleibt die Wiederherstellung gesperrt. Dabei gesetzlich aufzubewahrende signierte Rechnungs-/Berichtsdaten nicht pauschal zerstören.

Gmail-Quelle bleibt außerhalb Smartplan beim Nutzer/Bot/Google. Smartplan-Anhanglöschung löscht diese Mail/Originale nicht. Apps-Script hat readonly-Berechtigung und kann das auch nicht. Externe Mailbotwarteschlange, private JSON-/Dateimanifeste und Originale sind zusätzliche Datenorte außerhalb dieser Backendtransaktion (`integrations/mail_bot/send_inquiry.py:4`, `integrations/mail_bot/send_attachments.py:237`, `integrations/mail_bot/README.md:136`). Datenschutzexport-/Löschanzeige muss Scope/weitere Verantwortlichkeiten sichtbar machen; keine Vollständigkeitsbehauptung über unbekannte fremde Systeme.

#### Was für die DSGVO-/Need-to-know-Anforderung fehlt

1. Owner-initiierter, wiederholbarer datensparsamer Datenschutzfall: Betroffenenidentifikation, Umfang/Vorschau, gesetzliche Aufbewahrung/Legal Hold, nachvollziehbarer Lösch-/Anonymisierungsgrund, Ergebnis/Fehler/ausgenommene Belege. Nicht nur SQL-DELETE customers.
2. Maschinenlesbarer kontaktbezogener Export (Kontakt, Anfragen/Notizen, Projektbezüge, Metadaten/Originale nach Berechtigung, sensible Drittpersonen redigieren, Schema-/Zeitangabe) mit begrenztem authentifiziertem Download. Kein kompletter Datenbankdump/Tokenexport.
3. Dateninventar/Abhängigkeitsstrategie inklusive inquiry_requests, historische Namen/Provenienz, Originaldateinamen, Planquellen/Versionen, Berichte, externe Snapshots, bestehende sichere Offlinekopien und Backups.
4. Dokument-/Kontaktsicht je Zweck/Projektzuweisung statt globaler Adressbuchfreigabe. Gegenwärtig sind Inbox+Kunden sehr eng Owner-only, verknüpfte Projektanhänge dagegen für JEDE zugewiesene Rolle lesbar (auch Accountant/Techniker). Eine neue Einschränkung/Erweiterung braucht klare Rollentabelle und Tests. Finanzoriginale/Preisinhalte dürfen nicht nur wegen Dateiverknüpfung ungeprüft beim gesamten Projektteam landen.
5. Tests für Revocation/Disable auch während Export/Download, keine Datenlecks aus historischen Replayantworten, identische Wiederholung, Löschsperren, fehlerhafte Teillöschung/Timeout, Restore mit Löschentscheidungen. Im Ist fehlen entsprechende Funktionen, daher fehlen hierfür naturgemäß erfolgreiche Fachtests.


## 7. Build und CI


| Workflow / Jobs | Umfang / Quelle |
|---|---|
| Development checks / update-flow | Ubuntu24.04, isolierter Docker-Update-/Recoveryablauf (`checks.yml:9–14`). |
| Development checks / online-api | PostgreSQL16-Service, Python3.12, Online-/Import-/Lösch-/Workspace-/Anhang-/Integrations-/Release-/Storagefälle; systemd/bash-Verträge, echtes Caddy/Gunicorn mit geprüfter Test-TLS (`checks.yml:15–62`). |
| Development checks / https-setup | Isoliertes HTTPS-/DNS-/Caddy-Paket (`checks.yml:63–75`). |
| Development checks / backend | SharedSQLite-Backenddiscovery und Apps-Script-Nodevertragsfälle (`76–89`). |
| Development checks / flutter | Flutter3.47.7, lockfile, Analyse, native Releasequell-/Pakettests, echter PDFium-Raster-Smoke, übrige Fluttertests inklusive echter Backendintegration und echte Widgetscreenshots (`90–167`). Keine Web-/Browserprüfung. |
| Development checks / native-build | Windows Release+gesonderter Onlineflavor, reale Windows-Backend-/Client-/PDFtests, Backendkopierwhitelist/DLL- und Manifestprüfung; macOS baut iOS-Simulator (`168–450`). Liefert portable unsigned Prüfpakete, keinen Authenticode-/Trustnachweis. |
| iPhone TestFlight / unsigned | macOS, Analyzer, echter PDF-/App-Test, `flutter build ios --release --no-codesign`, iPhone/iPad-/Manifestprüfung, unsigniertes Artefakt (`ios-testflight.yml:31–170`). Branchguards auf bestehende Codexbranches. |
| iPhone TestFlight / testflight | Nur ausdrücklicher workflow_dispatch+upload_to_testflight und Releasebranch, Applecredentials/Signierung/Upload; normales Pushen lädt nicht hoch (`172–184,242–295`). Geräteinstallation/Storefreigabe bleibt eigene Abnahme. |
| Local plan import worker / local-worker | Ubuntu24.04, Docker, synthetische PDF/Bild/OCR-/CLI-/SIGTERM-Fälle ohne Testnetz (`plan-import.yml:36–42`). |
| Local plan import worker / parser-isolation | Ubuntu24.04, echte Linuxnamespaces/Netz-/Filesystemlimits, gezieltes offizielles AppArmorprofil, exakte systemd-Produktionsunit gegen synthetische PG-Jobs samt Stop/Restart (`44–77`). Kein Cloudtail-PID1-Test als systemd-Abnahme ausgeben. |
| Mail bot connection | Linux/Windows, portable Helper und POSIX reale synthetische Intake-/Anhangsannahme, enger ZIP-Packager (`mail-bot.yml:27–75`). |
| Project bot connection | Linux/Windows, stdlib-/Privatdatei-/Transport-/Receipt-/Whitelist-ZIP-Verträge; keine echten Google-/Microsoftkonten (`project-bot.yml:23–65`). |

Die Worker-/Bot-/iOS-Workflows sind teilweise pfad-/branchgefiltert; ein beliebiger
Docs-Push startet nicht automatisch jede Plattformprüfung. Technische grüne
Vorläufe separat auf exakten SHA prüfen, nicht aus einem Workflowtext ableiten.


## 8. Vollständige Funktions-Gap-Matrix

Jede vorgegebene ID steht genau einmal in der folgenden Matrix. Bei fehlenden Funktionen verweist die Fundstelle auf die untersuchte Modell-/Routengrenze; sie behauptet keinen vorhandenen Implementierungscode. Phasenverweise richten sich nach dem neuen Auftrag, auch wenn frühere Betriebsdokumente einen kleineren Scope nennen.

### A. Anfragen und Leads

| ID | Funktion | Status (vorhanden / teilweise / fehlt) | Fundstelle im Code | Aufwand (S/M/L) | Abhängigkeiten | Phase |
| --- | --- | --- | --- | --- | --- | --- |
| A1 | Lead-API bzw. eigenes Website-Kontaktformular; Anfragen direkt in der Projektoberfläche | teilweise | Reale Owner-Inbox/privates Erfassungs-API und narrow Gmail-Liefer-API vorhanden (`backend/workspace_api.py:24`, `backend/inbound_connectors.py:155`, `app/lib/main.dart:401`). Kein generisches öffentliches Lead-/Webformular, keine Website-Leadidentität/Antispam-/Formularintegration. Eingang liegt neben Projekten, nicht als allgemeiner Projekt-Leadkanal. | M | P1 Anfrage-/Kontaktkern; P8 eigener öffentlicher Vertrag, Source-Dedupe, Spam-/Ratelimits; SPIN nie in Browser-JavaScript | 1 Basis; 8 Formular |
| A2 | Automatische Antwort an den Anfragenden mit nächsten Schritten | fehlt | Kein Mailversand im Inquiries-/Inboundmodul, Apps-Script ausschließlich gmail.readonly (`backend/inquiries.py:1`, `integrations/google_apps_script/appsscript.json:10`). Kein Outbox-/Template-/Versandstatus-/Dedupe-Vertrag. | L | P8 freigegebene Vorlage/Absender und Versandadapter, idempotente Outbox; keine Werbeeinwilligung unterstellen | 8 |
| A3 | Anfrage mit Kontaktdaten, Ausgangssituation und Anliegen ohne manuelle Eingabe | teilweise | Gmail übernimmt Sendername/-mail, Subject, Text und Zeit ohne manuelle Abtipparbeit (`backend/inbound_connectors.py:155`, `backend/inquiries.py:402`). Exakte Kontaktvorschläge (`:321`). Ausgangssituation/Anliegen nur unstrukturierter Nachrichtentext; Telefon/Adresse nicht automatisch extrahiert; keine belastbare Zusammenfassung/strukturierte Pflichtfelder/Confidence-/Reviewanzeige. | M | Kontakt-/Anfragenmodell, strukturierte Felder und geprüfte Vorschläge; weitergehende Erkennung nur auf freigegebenem Hetznerpfad | 1; 8 Erweiterung |
| A4 | Lead-Portale Aroundhome/TapTapHome: Projekt/Kontakt automatisch anlegen und Mitarbeiter zuweisen | fehlt | Sources nur manual/gmail/whatsapp/import (`backend/inquiries.py:26`), Connector nur Gmail (`backend/inbound_connectors.py:155`); Übernahme ausdrücklich Owner-bestätigt, keine Portalroute/Autofreigabe; Zuweisung separater Owner-Endpunkt (`backend/inquiries.py:491`, `backend/core.py:352`). Repositorysuche nach Aroundhome/TapTapHome ohne Implementierungstreffer. | L | P8 Partnerverträge/Testpayloads, Herkunft/Auth/Dedupe, explizit freigeschaltete Anlage-/Zuweisungsregeln; Gmail-Standard nicht ändern | 8 |
| A5 | Telefonische Aufträge mit wenigen Klicks erfassen | teilweise | Nutzbarer manueller Telefon-Inboxdialog, Subject+Gesprächsnotiz+optionale Kontaktdaten, danach bewusstes Verknüpfen mit neuem Projekt (`app/lib/inquiry_pages.dart:602`, `:646`, `:1033`). Kein eigener kompakter Telefon-Schnellauftrag mit Kontaktwahl, Verantwortlichem/Termin und sofortiger konfigurierbarer Projektübernahme. „Wenige Klicks“ noch kein gemessener Abnahmepfad. | M | P1 vorhandene Convert-Domäne, Kontaktwahl, definierter Schnellpfad; keine automatisch erfundene Zusage | 1 |
| A6 | Bestehender Gmail-Intake inklusive Anhängen muss erhalten bleiben | vorhanden | Vier reale Public-Routen, schmale Tokens, unveränderte Bodyquittung, kanonische fortsetzbare Originaluploads (`backend/online/web.py:226`, `:240`, `:246`, `:258`, `backend/inquiry_attachments.py:244`). Existierender veröffentlichter OpenAPI-/Mailbotvertrag (`openapi.json:19`, `:141`). 111 einschlägige lokale Bestandsregressionen am Basisstand bestanden, siehe unten. Reale Nutzerbot-/Hetznerabnahme daraus nicht ableitbar. | S | Veröffentlichter Altvertrag, neue Regressionen vor jeder Änderung, HTTP-/PG-/Release- und Altclient-Gates | 1–10 Erhaltung |

### B. Projekte und Auftragsabwicklung

| ID | Funktion | Status (vorhanden / teilweise / fehlt) | Fundstelle im Code | Aufwand (S/M/L) | Abhängigkeiten | Phase |
| --- | --- | --- | --- | --- | --- | --- |
| B1 | Projekt als zentrale Einheit mit allen projektbezogenen Dokumenten | teilweise | Projekt-FK verbindet Aufgaben/Termine/Tagebuch/Links, Berichte, Planrevisionen und konvertierte Mailanhänge. Sieben Register oben. Verträge/Angebote/Rechnungen sind überwiegend Links bzw. explizite externe Leseansichten; kein einheitliches versioniertes Dokumentenobjekt für alle Dokumentarten. `backend/core.py:145`, `backend/project_workspace.py:29`, `inquiry_attachments.py`, `app/lib/project_workspace_page.dart:1425`. | L |  gemeinsame Dokumentenreferenzen, Kategorie-/Dateirechte, Ursprung und Versionen festlegen; vorhandene Originale/Hashes erhalten | 1; 2/5 Ausbau |
| B2 | Projektübersicht und Suche; individuelle Projektpipelines bzw. Projektstatus | teilweise | Suche und A–Z real (`app/lib/home_views.dart:875`), acht feste frei änderbare Profilphasen (`app/lib/project_workspace_forms.dart:7`; Server `backend/project_workspace.py:247`). Keine individuell definierten Pipelines/Stages, keine Statusfilter im Projektindex. | M |  konfigurierbare Statusdefinitionen mit stabilen IDs, Migration der bisherigen Codes und frei wechselbarem Status. Keine Pflichtreihenfolge zwischen Anzahlung/Material/Ausführung einführen | 1 |
| B3 | Statusbenachrichtigungen im Unternehmensfeed und per Push | fehlt | `audit` und `workspace_versions` speichern Ereignis-/Versionsnachweise (`backend/core.py:150`, `backend/project_workspace.py:42`, `:388`), aber es gibt keinen Unternehmensfeed, Empfängerzustand, Push-Token oder Benachrichtigungsendpunkt in den tatsächlichen Routen. Audit ist kein angezeigter Nachrichtenfeed. | L |  Push separat mit Betrieb/Einwilligung/Empfänger-/Duplikatregeln abnehmen. Automatisierungen aus P10 davon abgrenzen | 1 Feed; 3 Push |
| B4 | Aufgaben erstellen, verteilen, abarbeiten; Fortschritt offen/erledigt | vorhanden | Aufgaben wirklich erstellen/zuweisen/bearbeiten/erledigen, Status+Frist+Priorität; aktive Teamzuweisung validiert. `backend/project_workspace.py:315`, `:360`; `app/lib/project_workspace_page.dart:549`, `:1257`; `app/lib/project_workspace_forms.dart:523`. | S |  Wunsch nach mehreren Bearbeitern, Checklisten, Kommentaren etc. wäre zusätzlicher Scope | 1 Erhaltung |
| B5 | Auftragsbestätigung aus Angebot erstellen | fehlt | sevdesk wird ausschließlich über GET gelesen (`online/integration_sevdesk.py:61`), zeigt Angebote vom Typ AN und Rechnungen (`:170`); keine AB-Erzeugung. `Office.draft` akzeptiert nur Servicebericht/Lieferschein (`backend/core.py:514`). Eine Anfragezusage ist keine Auftragsbestätigung. | L | L, P2, abhängig von fachlich führendem Angebot/Dokumentvorlagen/Nummerierung/Versionierung und Entscheidung sevdesk vs. Smartplan. Keine automatischen Finanzschreibvorgänge unter bestehendem Read-only-Adapter verstecken | 2 |
| B6 | Mitarbeiter Projekten zuordnen | vorhanden | Owner ordnet Benutzerkonten Projekten zu und entfernt sie; echte `assignments`-Tabelle, API und UI. `backend/core.py:344`, `:352`, `:399`; `app/lib/admin_pages.dart:331`, `:381`; Projektmappe `:1579`. | S |  vorhandene Berechtigungen erhalten, Personalverfügbarkeit dadurch nicht als umgesetzt zählen | 1 Erhaltung |
| B7 | Projekt-Messenger mit Notizen, Nachrichten und Bildern | fehlt | Kein Nachrichten-/Kommentar-/Konversationsmodell oder Messenger-Route; Arbeits-/Probleme-/Nächste-Schritte-Freitexte sind Tagebucheinträge, keine Chatnachrichten mit Empfängern/Bildern/Lesestatus. Aktuelle Artenliste `backend/project_workspace.py:18` und Routen `backend/workspace_api.py:23`. | L |  Dokument-/Medienmodell, Empfänger+Rechte, Aufbewahrung/Export, Offlinekonflikte und Ereigniszustellung. Keine fremden Chatdienste voraussetzen | 5 |

### C. Kontakte / CRM

| ID | Funktion | Status (vorhanden / teilweise / fehlt) | Fundstelle im Code | Aufwand (S/M/L) | Abhängigkeiten | Phase |
| --- | --- | --- | --- | --- | --- | --- |
| C1 | Kundenkartei; Kontaktdaten automatisch in Projekt, Rechnung und Briefkopf | teilweise | Kundenkartei mit Hauptkontakt/Adresse/Notiz, customer_id+Kundenname im Projekt (`backend/core.py:198`, `:233`, `:261`); Berichtsnamen als Snapshot (`:516`). sevdesk Remote-Referenz/Read-Snapshot, keine automatische Rechnungserstellung/Adressübertragung (`backend/online/integrations_service.py:104`, `:505`). Voller Kontakt-/Adressblock/Briefkopf-/mehrere Ansprechpartner fehlt. | L | P1 Kontakt-/Adressmodell, Rechte, Export/Löschung; P2 eigene Belegsnapshots und kontrollierter Sevdesk-Übergang | 1; 2 Belegsnapshot |
| C2 | Mobiles CRM in der App | teilweise | Flutter-Kundenliste/-editor responsive; Suche, Archivierung und Projektstart vorhanden (`app/lib/customer_pages.dart:13`, `:138`, `:190`; Test `app/test/customer_test.dart:276`). Owner-only, ein Hauptkontakt, keine Kontakt-/Kommunikationschronik/Verantwortlichkeit/CRM-Offlinequeue. Inbox erfordert Verbindung (`app/lib/main.dart:372`). | M | P1 mobiles Kontaktmodell, Feldrechte; selektive Offlinefreigabe benötigt eigenes Cache-/Löschkonzept | 1; später selektiv offline |
| C3 | Lieferantenverwaltung | fehlt | Kein Lieferantenmodell/-typ/-API/-UI; customers-Felder kennen keinen supplier-Typ (`backend/core.py:105`, `:198`), Connectorprovider sevdesk/google_calendar/onedrive sind keine Lieferantenkartei (`backend/external_integrations.py:23`). Implementierungssuche supplier/suppliers/Lieferant/lieferant ohne passende Treffer. | M | P1 gemeinsame Parteirollen und Ansprechpartner; P7 Bestellungen/Wareneingang/Konditionen | 1 Basis; 7 Einkauf |

### D. Angebote, Dokumente, Vorlagen

| ID | Funktion | Status (vorhanden / teilweise / fehlt) | Fundstelle im Code | Aufwand (S/M/L) | Abhängigkeiten | Phase |
| --- | --- | --- | --- | --- | --- | --- |
| D1 | Angebote aus Vorlagen; Artikel/Leistungen per Drag & Drop; Summen/Steuern automatisch | fehlt | `backend/core.py:511` (`draft`) erlaubt nur Servicebericht/Lieferschein und Freitext; `backend/online/integration_sevdesk.py:119` (`_document`) liest nur externe Angebotskopfdaten. Keine Angebotspositionen, Drag & Drop, Preis-/Steuerberechnung oder eigene Vorlage. | L | P1 CRM/RBAC, E1/E3, versionierte Positionen/Decimal-Rundungsregel, D2/D3, F8 | 2 |
| D2 | Eigene Vorlagen für Angebote, Rechnungen, Mahnungen, Kostenvoranschläge, Lieferscheine; Textbausteine und Vorlagenpool | fehlt | `backend/core.py:74` (`make_pdf`) hat eine feste Berichtsvorlage; `Office.draft:511` nur zwei fest verdrahtete Dokumenttypen. Keine editierbaren Angebots-/Rechnungs-/Mahn-/KV-/LS-Vorlagen, Textbausteine oder Poolversionen. | L | unveränderliche Templateversion, Variablenschema/Escaping, Rollen, D1; Mahntexte G2 | 2; 5/6 Vorlagen |
| D3 | Eigenes Briefpapier, Logo und Dokumentbranding | teilweise | `backend/core.py:80` (`make_pdf`) druckt fest „SMARTPLAN HOFMANN“. Firmen-/Steuer-/Bank-/Adresssnapshot, frei gewähltes Logo/Briefpapier und versionierbare Brandingkonfiguration fehlen. | M | P1 Firmendaten, sichere Medienablage, D2; Finanzpflichtfelder separat prüfen | 2 |
| D4 | Aufmaßdokumente, Lieferscheine und Zahlungserinnerungen auch mobil | teilweise | Mobiler Lieferschein/Servicebericht über `app/lib/project_page.dart:66,152,466` und `Office.draft:511` vorhanden. Kein strukturiertes Aufmaßdokument und keine Zahlungserinnerung. Bestehende Berichte sind verbindungsabhängig. | L | P2 Dokumentmodell, K1/K2, P5 Aufmaß, P6 OP/Erinnerung, separater Offlineentwurfvertrag | 2; 5/6 |
| D5 | E-Mail-Versand aus Software und PDF-Download | teilweise | `backend/core.py:566` (`pdf`), `backend/online/web.py:124` und `app/lib/pdf_page.dart:44` (`save`) liefern Berichts-PDF/Download bzw. Betriebssystem-Teilen. Kein integrierter Mailversand, Empfänger-/Anhangssnapshot, Versandnachweis oder Zustell-Outbox. Teilen ist kein bestätigter Softwareversand. | L | D2/F8, geschützte Versand-Credentials, Voransicht/Freigabe, idempotente Outbox; G4 für Mahnung | 2; 5/6 |
| D6 | Digitale Unterschrift in App für Angebot, Lieferschein, Aufmaß und Bericht; eIDAS-Stufen | teilweise | `Office.sign` (`backend/core.py:537`) bindet Zeichenstriche, Namenseingabe, Bearbeiter und UTC-Zeit an erwarteten Inhaltshash und erzeugt ein festes PDF; `app/lib/signature_editor.dart:31` ist eine echte mobile Zeichenfläche. Nur Servicebericht/Lieferschein, keine Angebots-/Aufmaßsignatur. Keine attestierte Identitätsprüfung, fortgeschrittene oder qualifizierte Signatur / qualifizierter Zeitstempel. | L | D1/K1, signierbarer unveränderlicher Snapshot, Widerruf/Version, Beweisexport; eIDAS-Zielniveau je Dokument entscheiden | 2 Angebot; 5 Ausbau |
| D7 | Dokumentenmanagement: Speichern, Änderungen, Archiv, Suche und Export | teilweise | `Office.reports:532`, `Office.pdf:566`, `backend/project_workspace.py:232` (`_version`), `backend/online/plan_imports.py:302` und `backend/inquiry_attachments.py:357,388` speichern/prüfen bestimmte Dokumente und Historien. Allgemeines DMS mit beliebigen Uploads, Versionen, Metadaten-/Volltextsuche, Aufbewahrungs-/Sperrregeln, nachvollziehbarem Archiv-/Paketexport fehlt. OneDrive-Metadaten sind kein eigenes Originalarchiv. | L | P1 RBAC, eigenständige Assets/Retention, F8 bereits in P2, P5 Rechte/Suche/Export | 2 Finanzarchiv; 5 DMS |

### E. Kalkulation

| ID | Funktion | Status (vorhanden / teilweise / fehlt) | Fundstelle im Code | Aufwand (S/M/L) | Abhängigkeiten | Phase |
| --- | --- | --- | --- | --- | --- | --- |
| E1 | Artikel, Leistungen und Preise pflegen und aktualisieren | fehlt | Kein Artikel-/Leistungs-/Preisbestand im Schema `backend/online/store.py:134`; `Office.draft:516` enthält allein einen Beschreibungstext. Keine Preisgültigkeit/Revision/Einheit. | M | Stammdaten/RBAC, Einheiten, Preisversionen, Lieferantenbezug optional; bestehende Rechnungspositionen dürfen Preisupdates nicht übernehmen | 2 Basis; 7 Ausbau |
| E2 | Gewerkspezifisches Leistungsverzeichnis; Material-, Lohn- und Maschinenkosten | fehlt | `backend/project_workspace.py:18,302` kennt Aufgaben/Tagebuch/Termine/Links, keine Leistungsverzeichnisse oder Material-/Lohn-/Maschinenkomponenten. | L | E1, Einheiten/Kostengruppen, zusammengesetzte Leistungspositionen, Importquellen | 2 Leistungsbasis; 7 Ausbau |
| E3 | EK plus Aufschlag in Prozent/Euro, Stundensätze, Gemeinkosten, Zuschläge, netto/brutto | fehlt | `backend/online/integration_sevdesk.py:40,139` validiert fremde Bruttobeträge als Dezimalstrings, kalkuliert aber nichts. Keine EK-/VK-, Prozent-/Euroaufschläge, Stundensätze, Gemeinkosten, Zuschläge oder eigene Netto-/Bruttologik. | L | E1, Decimal-Festkomma/Rundung, Preis-/Steuer-/Lohnsatz-Snapshots, Rabatte/Einheiten; keine IEEE-Float-Geldbeträge | 2 Rechnen; 7 Kalkulation |
| E4 | Marge/Gewinn und Angebotskalkulation | fehlt | Weder eigene Angebotspositionen noch EK/VK im Schema; Sevdesk-Metadaten `backend/online/integration_sevdesk.py:139` liefern nur Gesamtbrutto/Status. Keine definierte Marge/Deckungsbeitrag/Gewinnberechnung. | M | E2/E3, klare Kennzahlformeln/Finanzrechte, Angebotsversion | 7 |
| E5 | Nachkalkulation und Soll-Ist je Projektverlauf | fehlt | `backend/project_workspace.py:392` (`dashboard`) zählt Aufgaben/Termine/Berichte/Pläne; es bilanziert keine Istzeit/-kosten. Manuelles `materials_status` ist kein Materialverbrauch. | L | genehmigte Zeiten aus P4 × historischer Satz, bewertete Lager-/Materialbewegungen L1, Baseline aus E4, Umgang mit Nachträgen | 7 |
| E6 | Nachtragskalkulation | fehlt | `backend/core.py:456` (`save_plan`) versioniert Zeichnungen, nicht Nachträge. Kein Nachtragsdokument mit Referenz auf den angenommenen Auftrag, separater Freigabe und Preiswirkung. | L | D1/F1, E2/E3, Vertrags-/Auftragsversion, genehmigte Nachträge; keine Änderung festgeschriebener Rechnung | 7 |
| E7 | Budgetplanung | fehlt | `backend/project_workspace.py:19,247` (`PROFILE_FIELDS`/`save_profile`) hat Beschreibung/Phase/Status/Termine, kein Budget oder Budgetversionen. | M | E3/E5, Projekt/Kostengruppen, Freigabe/Finanzrechte, Warnschwellen ohne erfundene Istkosten | 7 |

### F. Rechnungen

| ID | Funktion | Status (vorhanden / teilweise / fehlt) | Fundstelle im Code | Aufwand (S/M/L) | Abhängigkeiten | Phase |
| --- | --- | --- | --- | --- | --- | --- |
| F1 | Angebot, Auftrag oder AB per Knopfdruck in Rechnung umwandeln | fehlt | `backend/online/integration_sevdesk.py:170,187` liest getrennte fremde Order/Invoice-Metadaten; `Office.draft:511` erstellt keine Rechnung. Keine eigene Angebot→Auftrag/AB→Rechnung-Übernahme mit Kontakt-/Positions-/Preis-/Steuersnapshot. | L | D1, E1/E3, CRM, Annahme/AB, F8, exklusiver Issuer/Cutover | 2 |
| F2 | XRechnung und ZUGFeRD erstellen | fehlt | `backend/core.py:74` erzeugt normales ReportLab-Berichts-PDF; kein UBL/CII, kein EN16931-Profil/Validator, kein hybrides PDF/A mit eingebettetem XML. Ein PDF ist keine XRechnung/ZUGFeRD. | L | F1/F4/F8, Pflicht-/Steuerfelder, festgelegte Format-/Profilversionen, offizielle Validatorartefakte und Positiv-/Negativfixtures, XML/PDF-Bindung | 2 |
| F3 | E-Rechnung empfangen: Upload und Datenerfassung; angekündigtes automatisches Auslesen getrennt bewerten | teilweise | `backend/inquiry_attachments.py:23,36,388` bewahrt allgemeine Gmail-Anhänge mit Größe/Hash/Chunks; `backend/workspace_api.py:104,128` bietet authentifizierten Abruf bzw. EML-Eingang. Keine fachliche E-Rechnungseingangsmaske, strukturierte Datenerfassung, Profil-/Steuerprüfung, XML-/ZUGFeRD-Extraktion oder Rechnungsfreigabe. Automatisches Auslesen ist nicht vorhanden und muss getrennt von sicherem Upload gekennzeichnet bleiben. | L | F2 Formatschema/Parser ohne externe Auflösung, Originalarchiv F8, D7, Lieferanten/Zuweisung, P6 Eingangsbelege | 2 Eingang/Erfassung; 6 Ausbau |
| F4 | Material und Lohn inklusive Umsatzsteuer getrennt ausweisen | fehlt | `Office.draft:516` hat keine Positionen/Beträge; `backend/online/integration_sevdesk.py:145` enthält nur fremdes Gesamtbrutto. Keine getrennte Material-/Lohnsumme oder Umsatzsteueraufteilung. | M | E1/E3, Positionstypen, Steuersätze/Regelwerk je Betrieb, Summen-/Rundungsabnahme | 2 |
| F5 | Zeiteinträge direkt in Rechnung übernehmen | fehlt | Keine Zeiteintragsdomain im Schema/Routen; `backend/project_workspace.py:305` (`crew_count`) ist nur Tagebuch-Kopfzahl, kein abrechenbarer Zeitbeleg. | M | genehmigte P4-Zeiten, E3 Satzsnapshot, F1 Positionen; Teilmengen/Mehrfachabrechnung verhindern | 4 nach 2 |
| F6 | Abschlags-, Schluss- und kumulierte Rechnung | fehlt | `backend/project_workspace.py:249` (`deposit_status`) ist manuell und enthält weder Zahlungsbetrag noch Abschlags-/Schlussrechnung. Keine kumulierten Bemessungsgrundlagen/Steuern, Abzüge oder verknüpfte Rechnungskette. | L | F1/F4/F8, Vertrags-/Nachtragswerte, referenzierte Abschläge, Soll/Ist-Zahlungszuordnung, Steuerberater-Abnahme | 2 |
| F7 | QR-Code für Zahlung auf Rechnung | fehlt | `backend/core.py:74` (`make_pdf`) rendert keinen Zahlungs-QR; vorhandene TOTP-Einrichtung `backend/online/auth.py:74` ist sachlich unabhängig. | M | F1/F8, geprüfte IBAN/BIC/Name/Währung/Betrag/Verwendungszweck, EPC/Girocode-Format und Scannertest; QR ist kein Zahlungsnachweis | 2 |
| F8 | GoBD-Speicherung: Festschreibung, Korrektur/Storno, lückenlose Nummern, Hash/Zeitstempel/Versionen, rechtliche Prüfung durch Betrieb/Steuerberater | fehlt | `Office.sign:553` verhindert erneut signiertes Berichtpayload über die API und `Office.pdf:571` prüft PDF-SHA. `backend/online/store.py:152`/`Office.audit:278` sind ein gewöhnliches beschreibbares Auditlog ohne Hashkette/Belegnummern/Festschreibungsledger. Keine eigenen finalen Rechnungen, Nummernregister, Storno-/Korrekturkette oder rechtliche Verfahrensdokumentation. | L | P1 unveränderliches Audit/RBAC/Betriebsdoku, F1, atomare Nummern/Festschreibung/Archiv, Export, Restore-/Down-Vertrag; Betrieb/Steuerberater-Freigabe | 2 Pflicht |
| F9 | Rechnungsdaten und Belege an Steuerberater übergeben | fehlt | `app/lib/pdf_page.dart:44` kann Einzel-PDF teilen/speichern, `backend/online/backup.py:9` sichert DB-Betrieb. Beides ersetzt keine abgestimmte, reproduzierbare Übergabe von Rechnungsdaten/Originalbelegen/Steuercodes/Korrekturen mit Manifest und Importprotokoll. | L | F1/F8/F3, Konten-/Steuer-/Mandantmapping, Berater-Zielformat, N7 und ggf. N8 | 6; 8 Transport |

### G. Finanzen und Mahnwesen

| ID | Funktion | Status (vorhanden / teilweise / fehlt) | Fundstelle im Code | Aufwand (S/M/L) | Abhängigkeiten | Phase |
| --- | --- | --- | --- | --- | --- | --- |
| G1 | Sortierbare OP-Liste mit offen/Teilzahlung, Mahnstufe, Tagen bis zur nächsten Stufe, letzter Erinnerung und letzter Notiz | teilweise | `backend/online/integration_sevdesk.py:16,139` kennt offen/teilbezahlt/bezahlt als Providerstatus; `app/lib/project_integration_widgets.dart:366` listet nur gewählte Projektbelege. Keine sortierbare vollständige OP-Liste, Zahlungsbeträge/-zuordnung, Mahnstufe, nächste Fälligkeit oder letzte Erinnerung/Notiz. | L | F1/F8, freigegebene Zahlungs-/OP-Quelle, Teilzahlungen/Restforderung/Strittigkeit, Finanz-RBAC | 6 |
| G2 | Bis zu sechs Mahnstufen: drei Erinnerungen plus drei Mahnungen, je Name, E-Mail-Vorlage, Intervall in Tagen und Karenztag | fehlt | Kein Mahnmodell in `backend/online/store.py:134` / `backend/workspace_api.py:23`; keine Stufenkonfiguration. Ziel: Ausgangsstufe0 plus bis zu sechs individuell benannte Stufen, Vorlagen/Intervall/Karenztag versioniert. | M | G1/D2, Kalender-/Fälligkeitsregel, Berechtigungen/Freeze der verwendeten Regelversion | 6 |
| G3 | Mahnstufe nach Mahnungserstellung automatisch erhöhen | fehlt | Audit `backend/core.py:278` dokumentiert vorhandene Aktionen, enthält aber keinen Mahn-/Versandübergang. Nur die freigegebene endgültige Erstellung darf im Ziel eine Stufe weiterführen; Vorschau/Entwurf/Retry nicht. Versandstatus bleibt getrennt. | M | G2/G4, atomarer Freigabe-/Beleg-/Outbox-Eintrag, Request-ID/Empfangsquittung | 6 |
| G4 | Mahnlauf: Vorschlagsliste, Empfänger prüfen, Versand manuell freigeben | fehlt | `backend/online/web.py:299` / `backend/workspace_api.py:23` haben keinen Mahnlauf oder Sendekanal. Zwingendes Ziel: Vorschlagsliste, Empfänger-/Betrags-/Belegprüfung, ausdrückliche manuelle Freigabe; ohne Freigabe weder Versand noch Stufenerhöhung. | L | G1/G2/D5, freigegebener Inhalts-/Empfängerhash, letzte Rechte-/Zahlungsprüfung, Outbox/Unknown-Outcome-Behandlung; kein P10-Autoversand | 6 |
| G5 | Zahlungseingang/Zahlungsabgleich und Online-Zahlung durch Kunden | fehlt | `backend/online/integration_sevdesk.py:145` enthält keine einzelnen Bank-/Zahlungstransaktionen; `backend/project_workspace.py:249` ist keine Zahlungsbuchung. Keine Zahlungseingangserfassung/Zuordnung, kein Bankabgleich oder Kundenzahlungsdienst. | L | F1/G1, Providerzugang/Consent hinter Flag, unveränderliche Transaktions-ID, Zuordnungen/Teilzahlungen/Erstattung; Onlinezahlung gesonderter freigegebener Provider | 6 Zahlung/Onlinezahlung; 8 Providertransport |
| G6 | Belege in der App erfassen | teilweise | `backend/inquiry_attachments.py:36,388` und `app/lib/mail_attachment_widgets.dart` ermöglichen Maileingangsanhänge; Kamera/Foto in `app/lib/plan_import_page.dart` erfasst Planquellen. Keine eigenständige Belegfoto-/Eingangsrechnungsmaske mit Betrag/Steuer/Lieferant/Projekt/Freigabe. Planfoto darf nicht als fertige Belegerfassung gelten. | M | F3/D7, Lieferanten-/Projektbezug, Originalhash, Retention/Offline-Entwurf, Finanz-RBAC | 6 |
| G7 | Finanzübersicht | teilweise | `app/lib/project_integration_widgets.dart:366` zeigt gewählte Sevdesk-Belege mit Status/Brutto, keine Gesamtfinanzsicht. `backend/project_workspace.py:392` ist ein Arbeitsdashboard, keine Umsatz-/Kosten-/Liquiditätsübersicht. | L | G1/G5, F8, E5, korrekte Quellen-/Währungs-/Stichtagsabgrenzung; fehlende Daten explizit unbekannt | 6; 7 Kosten |

### H. Plantafel und Einsatzplanung

| ID | Funktion | Status (vorhanden / teilweise / fehlt) | Fundstelle im Code | Aufwand (S/M/L) | Abhängigkeiten | Phase |
| --- | --- | --- | --- | --- | --- | --- |
| H1 | Projekttermine einzeln/als Serie mit Mitarbeiterzuweisung | teilweise | Einzeltermine mit Zeitzonenprüfung vorhanden, aber Payload hat nur title/details/start_at/end_at/status (`backend/project_workspace.py:24`, `:335`; Formular `app/lib/project_workspace_forms.dart:550`). Weder Mitarbeiterzuweisung noch Serien/RRULE. Google-Leselinks sind keine lokal editierbare Serie. | L |  Termin/Serie/Ausnahme, mehrere Mitarbeiter, Zeitzone Europe/Berlin, Konflikte und Rechte. Offlineausbau auf Grundlage der vorhandenen Outbox | 3 |
| H2 | Digitale Plantafel Woche/Monat/gefilterte Tage/individuelle Ansicht | fehlt | Termine erscheinen als sortierte Liste (`backend/project_workspace.py:289`, `app/lib/project_workspace_page.dart:1341`), nicht als Wochen-/Monats-/Tage- oder individuelle Plantafel. | L |  H1-Zielmodell, Ressourcen/Abwesenheiten, Bereichsabfragen und performante mobile Darstellung | 3 |
| H3 | Planänderungen per Drag & Drop | fehlt | Kein Drag-&-Drop für Termine/Ressourcen. Zeichengesten im Planeditor sind dafür kein Beleg. Termine werden über Formulare geändert (`app/lib/project_workspace_forms.dart:550`). | M |  genau ein revisionsgesicherter Umplanungsvorgang, Konfliktrückmeldung und gleichwertiger Touch-/Tastatur-/Formularweg | 3 |
| H4 | Fahrzeuge, Maschinen und Werkzeuge planen | fehlt | Keine Fahrzeug-/Maschinen-/Werkzeugressourcen oder Reservierungen in Schema/Artenliste/Routen; Projektteam sind ausschließlich Benutzer (`backend/project_workspace.py:189`). | L |  Resource, Booking/Allocation, Verfügbarkeit, Sperrung/Wartung und Überschneidungen | 3; 7 Inventar |
| H5 | Urlaub und Abwesenheiten in Plantafel | fehlt | Kein Abwesenheits-/Urlaubsobjekt, keine Planungsüberlagerung. Nicht aus fehlenden Terminen als Urlaub ableiten. | L |  Datenschutz: Planer braucht Verfügbarkeit, nicht Krankheitsgründe | 3 Sicht; 4 Prozess |
| H6 | Grafische Projektplanung über ein Jahr oder länger | fehlt | Profil besitzt nur optionales Start-/Enddatum (`backend/project_workspace.py:19`, `:253`; UI `:929`), keine grafische Langfristplanung, Abhängigkeiten oder Meilensteinachse. | L |  belastbare Auftrags-/Phasentermine, Zeitachsenabfragen und optional Abhängigkeiten. Ein langfristiger Balken darf keine gefertigte Detailplanung vortäuschen | 3 |
| H7 | Mobile Plantafel mit Echtzeitsynchronisation | teilweise | Mobile Terminbearbeitung plus verschlüsselte Offline-Warteschlange sind real (`app/lib/offline_workspace.dart:29`, `:325`, `:704`). Keine mobile Plantafel; Sync ist Foreground-Polling alle 20 s (`app/lib/offline_plans.dart:192`) + App-Resume (`app/lib/main.dart:83`), kein Push/WebSocket/Echtzeitversprechen. Externe Botmetadaten kommen beim nächsten Fünfminutenlauf. | L |  H1/H2, Delta-/Konfliktmodell, nachvollziehbarer letzter Datenstand; Betriebssystem-Backgroundgrenzen explizit | 3 |
| H8 | Werkzeugverwaltung: Verfügbarkeit, QR/NFC optional | fehlt | Keine Werkzeugverwaltung, Verfügbarkeitsdaten, QR-/NFC-Zuordnung. Ressourcen- und Inventarbestand fehlen; aktuelle Projektfelder siehe `backend/project_workspace.py:19`. | L |  QR/NFC separat optional hinter Flag und erst nach Stammdatenmodell | 3 Basis; 7 Verwaltung |

### I. Zeiterfassung und Personal

| ID | Funktion | Status (vorhanden / teilweise / fehlt) | Fundstelle im Code | Aufwand (S/M/L) | Abhängigkeiten | Phase |
| --- | --- | --- | --- | --- | --- | --- |
| I1 | Projektbezogene Stempeluhr Beginn/Pause/Ende | fehlt | Kein Beginn/Pause/Ende-Event oder laufende Zeitsitzung; Termine enthalten keinen Ist-Zeitstatus (`backend/project_workspace.py:24`). | L |  eigene Stempelereignisse/Zeitsitzungen und Mitarbeiter-/Projektberechtigung | 4 |
| I2 | Push-Erinnerung zu definierter Uhrzeit | fehlt | Keine lokale/Push-Erinnerungsplanung oder Geräte-Pushregistrierung. Timer in `app/lib/offline_plans.dart:194` synchronisiert Daten und ist keine Erinnerung. | M |  I1, Firmenzeitzone, Opt-in, zuverlässige Geräte-/Betriebssystemregeln; keine heimliche Zeiterfassung | 4 |
| I3 | Zeiten online/offline, Überstunden und automatischer Pausenabzug | fehlt | Es existieren keine Zeiten, Überstundenregeln oder automatischen Pausenabzüge. Offlinebasis ist wiederverwendbar, erfüllt aber diese Fachfunktion nicht (`app/lib/offline_workspace.dart:3`). | L |  idempotente Offline-Stempelevents, Mehrgeräte-/Überschneidungskonflikte, versionierte Pausen-/Sollzeitregeln und Korrekturen | 4 |
| I4 | Zeitenauswertung täglich/wöchentlich/monatlich/jährlich | fehlt | Keine Tages-/Wochen-/Monats-/Jahresauswertung. Dashboardzähler zählen Aufgaben/Termine/Tagebuch (`backend/project_workspace.py:409`). | L |  zeitzonen- und freigabekonsistente Auswertungen | 4 |
| I5 | Optionaler Standort nur beim Ein-/Ausstempeln, Freischaltung pro Firma, Löschung nach Genehmigung, kein Tracking | fehlt | Keine Standortaufnahme bei Zeitereignissen, keine Firmenfreigabe, keine Löschung nach Genehmigung. Heutige App enthält keinen entsprechenden Zeit-/Geoablauf. | L |  standardmäßig aus; explizite Firmenfreigabe; nur Start/Stop, niemals Pause-/Hintergrundtracking. Separate kurzlebige Geodaten mit nachgewiesener Löschung nach Freigabe, inklusive Offlineausgang und Backup-/Aufbewahrungsentscheidung | 4 |
| I6 | Arbeitstag genehmigen/freigeben | fehlt | Keine Tagesfreigabe, Sperrung, Rückfrage oder Korrekturhistorie für Arbeitszeiten. Berichtsunterschrift gibt kein Arbeitszeitkonto frei. | L |  Vorgesetzten-/Personalrechte, Abschlusszustände und nachvollziehbare Korrektur statt stiller Änderung | 4 |
| I7 | Eigene Zeitkategorien und Zuschläge | fehlt | Keine Zeitkategorien/Zuschläge. Priorität und Dokumentkategorie sind andere Fachfelder (`backend/project_workspace.py:21`). | M |  konfigurierbare Regeln mit Wirksamkeitsdatum, keine Lohnabrechnung implementieren | 4 |
| I8 | Arbeitszeitkonto | fehlt | Kein Sollstunden-/Saldo-/Übertrags-/Arbeitszeitkonto. | L |  Arbeitszeitmodell, I3/I6, Periodenabschluss/Korrektur, Rechte | 4 |
| I9 | Abwesenheitsmanagement und Urlaubsanträge | fehlt | Keine Urlaubsanträge/Abwesenheitsgenehmigungen. Benutzeraktivität ist ein Zugriffsstatus, kein Urlaub (`backend/core.py:311`). | L |  Personalkalender, Antrag/Freigabe/Vertretung, getrennte private Gründe und frei sichtbare Verfügbarkeit | 4 |
| I10 | Dienstpläne | fehlt | Keine Dienstpläne oder Schichtdefinitionen/-zuweisungen. Projektzuweisung ist keine zeitliche Schicht (`backend/core.py:146`). | L |  Personalverfügbarkeit, Regeln, Serien/Ausnahmen und Planungsrechte | 4 |
| I11 | Mitarbeiterverwaltung und Stundenlisten-Export zur Lohnvorbereitung; keine Lohnabrechnung | teilweise | Benutzerkonten mit E-Mail/Rolle/aktiv sowie Projektzuweisung funktionieren (`backend/core.py:298`, `:304`, `:352`; `app/lib/admin_pages.dart:331`). Keine Mitarbeiterstammdaten/Arbeitsmodelle oder Stundenlisten-/Lohnvorbereitungs-Exporte. | L |  Personalprofil getrennt vom Login, Export freigegebener Zeiten und strenge Feldrechte. Keine Lohnabrechnung und keine sensiblen HR-Daten in allgemeine Projektpayloads | 4 |
| I12 | Mitarbeiterverfügbarkeiten | fehlt | Projektteam kennt nur aktive Benutzer und Zuordnung, keine zeitabhängige Verfügbarkeit (`backend/project_workspace.py:189`). | L |  H4/H5/I9/I10 und datensparsame Verfügbarkeitsansicht | 3 Verfügbarkeit; 4 Personal |

### J. Baudokumentation

| ID | Funktion | Status (vorhanden / teilweise / fehlt) | Fundstelle im Code | Aufwand (S/M/L) | Abhängigkeiten | Phase |
| --- | --- | --- | --- | --- | --- | --- |
| J1 | Fotodokumentation mit Upload, Notizen und Markierungen | teilweise | Planfotoaufnahme/Dateiauswahl und Mailbild-Originale funktionieren, inkl. lokalem Original und Vorschau (`app/lib/plan_import_page.dart:201`, `:220`, `:481`; `app/lib/project_workspace_page.dart:1425`). Keine allgemeine Baustellen-Fotodoku mit Bildnotizen/Markierungsebenen. Linienvorschläge aus Erkennung sind keine vom Benutzer erzeugten Fotoannotationen. Android-Kameragate siehe oben. | L |  gemeinsame Medien-/Dokumentobjekte, Original unverändert + getrennte Annotationen, Aufnahme-/Bearbeitungsrechte, Upload-/Offline-/Löschmodell | 5 |
| J2 | Projektbezogene Bildergalerie | fehlt | Keine eigenständige Projektbildergalerie. Planquellenliste und Mailanhangsliste mit Einzelvorschau sind keine komplette projektbezogene Fotoverwaltung. Aktuelle Dokumentenkomposition `app/lib/project_workspace_page.dart:1425` und Registerliste `:20`. | M |  echte Bildfilter/Thumbnails/Datum/Zuordnung, Datenschutz und projektweite Suche | 5 |
| J3 | Bautagesbericht mit Vorlagen, Artikeln und Leistungen per Drag & Drop sowie Dauerimport aus Zeiterfassung | teilweise | Tagesbericht als Freitext mit Datum/Wetter/Personenzahl vorhanden (`app/lib/project_workspace_forms.dart:531`; `backend/project_workspace.py:327`). Keine Vorlagen, Artikel-/Leistungspositionen oder importierten Ist-Zeiten. Servicebericht-Freitext ist separater Ablauf. | L |  Übernahmen müssen Originalreferenzen und Versionsstand tragen | 5 |
| J4 | Bautagebuch und Projektlogbuch mit Export | teilweise | Tatsächliches Bautagebuch und interne Versions-/Auditprotokolle (`backend/project_workspace.py:42`, `:288`, `:388`). Kein nutzerseitiger Projektlogbuch-Feed und kein Tagebuch-/Gesamtexport. `calendar()` ist nur ICS (`:416`); `Office.pdf()` nur unterzeichnete Berichte. | L |  exportierbare versionierte Tagesberichte/Logereignisse, Medienreferenzen und Berechtigungen. Kein Audit-Export als fertiges Bautagebuch ausgeben | 5 |
| J5 | Mängelmanagement | fehlt | Keine Mangelentität, Orts-/Planmarkierung, Foto-/Frist-/Verantwortlichkeits-/Abnahmehistorie; „Probleme/Besonderheiten“ ist Freitext (`app/lib/project_workspace_forms.dart:540`). | L |  Aufgaben/Medien/Planreferenzen wiederverwenden, eigener Status-/Beweis-/Abschlussablauf mit Revisionsschutz | 5 |
| J6 | Dokumentation per Mail versenden bzw. herunterladen | teilweise | Geschützter PDF-Download für unterschriebene Serviceberichte/Lieferscheine existiert (`online/web.py:39`, `backend/core.py:568`, `app/lib/pdf_page.dart:44`). Windows speichert per Dateidialog; andere Plattformen nutzen `Printing.sharePdf`, womit der Nutzer selbst eine Mail-App wählen kann. Signierte Berichte können in konfigurierte Ablage übertragen werden. Kein eigener Versanddienst mit Empfängern/Versandbeleg und kein Export aller neuen Dokuarten. | M |  Dokumentenrendering/Download, separat freigegebener Mailversand, Empfängerprüfung und Sendequittung. Bestehender Gmail-Empfang ist kein Versandkanal | 5 |

### K. Aufmaß

| ID | Funktion | Status (vorhanden / teilweise / fehlt) | Fundstelle im Code | Aufwand (S/M/L) | Abhängigkeiten | Phase |
| --- | --- | --- | --- | --- | --- | --- |
| K1 | Mobiles digitales Aufmaß | fehlt | Planzeichnung ist ausdrücklich `units='unitless'` (`backend/core.py:492`), UI „Entwürfe ohne Maßstab“ (`app/lib/plan_pages.dart:355`), Erkennung übernimmt keine bestätigten Maße (`app/lib/plan_import_page.dart:481`, `:937`). Keine aufmaßfähigen Mengen/Einheiten/Formeln/Positionen. | L |  manuelle metrische Erfassung zuerst definieren, Planmaßstab/Kalibrierung und Genauigkeits-/Freigaberegeln separat. Kein Auto-Aufmaß aus Foto versprechen | 5 |
| K2 | Aufmaß in Kalkulation übernehmen | fehlt | Kein digitales Aufmaß, kein Artikel-/Leistungs-/Kalkulationsmodell und kein Übergabepfad. `Office.draft` verwendet nur Freitext (`backend/core.py:516`). | L |  Mengen-/Einheiten-/Rundungs-/Positionsreferenzen und reproduzierbare Übernahme/Korrektur | 7 nach 5 |
| K3 | Aufmaß digital unterschreiben | fehlt | Handschriftliche Signatur nur für Servicebericht/Lieferschein (`backend/core.py:511`, `:537`; `app/lib/project_page.dart:66`), nicht für Aufmaßdokumente. | M |  eingefrorener Aufmaßstand+Signer/Zeit/Hash und konkrete Beweis-/eIDAS-Anforderungen; vorhandene Canvas-Signatur nicht als qualifizierte Signatur bezeichnen | 5 |

### L. Lager und Material

| ID | Funktion | Status (vorhanden / teilweise / fehlt) | Fundstelle im Code | Aufwand (S/M/L) | Abhängigkeiten | Phase |
| --- | --- | --- | --- | --- | --- | --- |
| L1 | Bestände, Entnahmen und Lagerbewegungen | fehlt | `backend/project_workspace.py:251` speichert nur einen Bestellstatus; kein Bestands-/Bewegungsledger im Schema. Keine Lagerorte, Zugänge, Entnahmen, Umbuchungen, Rückgaben/Inventur oder Kostenbewertung. | L | E1/E3, Projekt-/Lagerrechte, append-only Bewegungen, Mengen-/Einheitsregeln, Offline-Idempotenz und Konflikte | 7 |
| L2 | Lagerartikel mit Dokumenten | fehlt | Keine Lagerartikel im Schema; `backend/project_workspace.py:342` sind Projektlinks, keine artikelbezogenen Dokumente. | M | E1/L1, D7 Dokumentrechte/-versionen und sichere Objektbindung | 7 |
| L3 | Lieferantenmanagement | fehlt | `backend/core.py:105,198,224` modelliert Kunden, nicht Lieferanten. Eine umbenannte Kundenzeile ersetzt keine Lieferantenstammdaten/-rollen, Artikelzuordnung, Bezugsnummer oder Einkaufskonditionen. | M | P1 Kontaktmodell/RBAC, E1, eindeutige Parteirollen; bestehende Kundenbezüge unverändert lassen | 1 Kontakt; 7 Einkauf |
| L4 | QR-/Barcode-Scan mit Abhaken in App | fehlt | Keine Lager-Scanroute/-UI; `app/lib/plan_import_page.dart` verwendet Kamera für Planfotos, nicht QR-/Barcode-Suche/Quittierung. | M | E1/L1, Codeformat/Dublettenbindung, Kameraberechtigung, Scanbestätigung und Offline-Request-ID; kein NFC-Zwang | 7 |
| L5 | Kommissionierung für Aufträge | fehlt | Aufgaben `backend/project_workspace.py:304` sind keine Kommissionierung; keine Reservierungs-/Entnahme-/Fehlmengenpositionen pro Auftrag. | L | F1 Auftragspositionen, L1, Freigabe/Teil-/Rückmengen und konkurrierende Bestandsvergabe | 7 |
| L6 | Nachbestellung über Großhändler und tagesaktuelle Preise | fehlt | `backend/online/integration_http.py:29,193` hat keinen Großhändleradapter; Materialstatus `backend/project_workspace.py:251` verschickt keine Bestellung. Weder Nachbestellung noch Tagespreisabruf/Preisgültigkeit. | L | L3/E1/L1, N1..N5, Händlervertrag/Sandbox/Flags/SecretStore; Preiszeitpunkt/Quelle, Bestellung nur ausdrücklich bestätigt | 8 nach 7 |

### M. Außendienst und Wartung

| ID | Funktion | Status (vorhanden / teilweise / fehlt) | Fundstelle im Code | Aufwand (S/M/L) | Abhängigkeiten | Phase |
| --- | --- | --- | --- | --- | --- | --- |
| M1 | Auftrags-/Technikerchecklisten auch für Einarbeitung; in Servicebericht überführen | fehlt | Keine Checklisten-/Vorlagen-/Run-/Antwortentitäten oder Überführung in Servicebericht. Aufgabenliste/Checkbox „Bestätigen“ vor Unterschrift sind keine Technikercheckliste. Servicebericht bleibt Freitext (`backend/core.py:514`, `:516`). | L |  versionierte Checklisten, Pflicht-/optionale Antworten und nachvollziehbare Übernahme in eingefrorenen Servicebericht | 3 Checklisten; 5 Bericht |
| M2 | Wartung/Wartungsvertrag, Erinnerung, Vertragsanhang und Wartungshistorie je Anlage | fehlt | Keine Anlagen-, Wartungsplan-, Vertrags-, Fälligkeits-/Erinnerungs- oder Anlagenhistorienobjekte. Freie „Serviceprojekte möglich“-Formulierung (`app/lib/project_workspace_forms.dart:512`) schafft keinen Wartungsablauf. Allgemeiner Vertragslink (`:44`) ist kein Wartungsvertrag. | L |  Anlage/Kunde/Standort, Vertrag/Anhänge, wiederkehrender Plan, Auftragseinsatz, Historie, Erinnerungen und M1. Bestehende allgemeine Termine ersetzen keine Wartungsserie | 9 |

### N. Schnittstellen

| ID | Funktion | Status (vorhanden / teilweise / fehlt) | Fundstelle im Code | Aufwand (S/M/L) | Abhängigkeiten | Phase |
| --- | --- | --- | --- | --- | --- | --- |
| N1 | Datanorm | fehlt | Kein Datanorm-Parser/-Schema; produktive Adapterliste `backend/external_integrations.py:23` und feste URL-Abgrenzung `backend/online/integration_http.py:29` enthalten keinen Handelsdatenimport. | L | E1/E3/L3, zugesicherte Datanorm-Versionen/Encoding/Änderungsarten, Importjournal/Preisgültigkeit, Beispieldateien | 8 |
| N2 | IDS Connect | fehlt | Kein IDS-Connect-Adapter in `backend/online/integration_http.py:193` oder Produktmodulen. | L | L3/E1/L6, Händlervertrag/Session-/Warenkorbvertrag, Testzugang, Handoff-/Retourparameter prüfen | 8 |
| N3 | UGL | fehlt | Keine UGL-Ein-/Ausgabe; Schema/Routen `backend/online/store.py:87` / `backend/workspace_api.py:23` enthalten keine Handelsdokumente. | L | E1/L3, Auftrag/Bestellmodell, vereinbarte UGL-Version/Zeichensatz/Positionsmapping, kein automatischer Einkauf | 8 |
| N4 | OCI | fehlt | Kein OCI-Punchout oder Einkaufsrücklauf in `backend/online/web.py:299` / `backend/online/integration_http.py:193`. | L | E1/L3/L6, authentisierter Session-/Warenkorbrücklauf, Zielallowlist, Anbieter-/Betriebsflag, sichere Formularrückgabe | 8 |
| N5 | SHK Connect | fehlt | Kein SHK-Connect-Verzeichnis-/Dienstadapter; vorhandene Integrationen sind Sevdesk/Google/OneDrive (`backend/external_integrations.py:23`). | M | L3, offiziell bestätigter Endpunkt-/Versionsvertrag, Händlerzuordnung/Serviceentdeckung und Flags | 8 |
| N6 | GAEB-Import und -Export für Ausschreibung/Angebot/Nachträge/Rechnung | fehlt | Keine GAEB-Import-/Exportformate; Planformat-/PDF-Funktionen sind keine GAEB-Datenphasen (`backend/core.py:456,74`). | L | D1/F1/E2/E6, konkret unterstützte GAEB-Versionen und Austauschphasen (Ausschreibung/Angebot/Nachtrag/Rechnung), Mengeneinheiten/Ordnungszahlen, Roundtripvalidator | 8 |
| N7 | DATEV-Export bzw. -Synchronisation | fehlt | `backend/online/backup.py:9` ist ein Betriebssicherungsdump; `app/lib/pdf_page.dart:44` ein Einzel-PDF-Export. Kein DATEV-Daten-/Belegexport, keine Synchronisation. | L | F9/P6, Beratermandant/Konten-/Steuerschlüssel/Zeichenkonvention, Exportmanifest/Berichtigungen, offizielle Importabnahme; Synchronisation separater Vertrag | 6 Export; 8 Transport |
| N8 | Lexware Office: Rechnungen übergeben und Zahlungen überwachen | fehlt | Sevdesk-GET-Adapter `backend/online/integration_sevdesk.py:61` ist keine Lexware-Office-Anbindung. Keine Rechnungsübergabe/Zahlungsüberwachung. | L | F1/F8/G1/G5, exklusiver Issuer, Mapping und Wiederholungs-/Webhookvertrag, OAuth/API-Zugang ausschließlich SecretStore | 6 Vertrag; 8 Adapter |
| N9 | Aroundhome | fehlt | `backend/inbound_connectors.py:155` (`receive_gmail`) ist Gmail-/SPIN-spezifisch; keine Aroundhome-Signaturprüfung, Leadzuordnung oder Portalfreigabe. | M | A1/A4, offizieller Partnervertrag/Beispielpayload, Inbox-Dedupe/Consent/Rate, P1 Mitarbeiterzuweisung | 8 |
| N10 | TapTapHome | fehlt | Derselbe tatsächliche Eingang `backend/inbound_connectors.py:155` ersetzt keinen TapTapHome-Connector. | M | A1/A4, bestätigte API/Partnerrechte, Auth-/Replay-/Duplikatregeln, Inbox/CRM-Zuordnung | 8 |
| N11 | Lead-API | teilweise | `backend/inbound_connectors.py:155` nimmt echte Gmail-Envelopes idempotent entgegen; `backend/workspace_api.py:139` erlaubt authentifiziertes manuelles Inquiry-POST. Keine allgemeine Website-/Portal-Lead-API mit eigenem Scope, Schema, Einwilligungs-/Quellnachweis und Webhook-Replayschutz. SPIN nicht stillschweigend verbreitern. | M | P1 Inquiry/CRM/Pipeline, A1, dedizierter Einlieferungsschlüssel und minimale öffentliche Antwort, Absenderprüfung/Rate/Dedupe | 1 Basis; 8 Adapter |

### O. Plattform

| ID | Funktion | Status (vorhanden / teilweise / fehlt) | Fundstelle im Code | Aufwand (S/M/L) | Abhängigkeiten | Phase |
| --- | --- | --- | --- | --- | --- | --- |
| O1 | Cloud mit Echtzeitsync, PC/Smartphone/Tablet, Web und iOS-/Android-App | teilweise | Native Flutter-Windows-/iOS-App und HTTPS-API: `app/lib/api.dart:19`, `.github/workflows/checks.yml:168`. Kein versioniertes Web-/PWA-/Androidziel; `dart:io`, Polling 20/30 s statt Push-Echtzeit. | L | Plattformadapter, Rechte/Datenschutz, fachliche Module und nachgewiesene Geräteziel-/Syncfreigabe | 1 Web; 3 Live; 4 Offline; mobile Freigaben fortlaufend |
| O2 | Datenschutz, Sicherheit und Zugriffsrechte | teilweise | Rollen/Projektzugriff `backend/core.py:395`, Online-MFA `backend/online/auth.py:45`, Offlinevault `app/lib/offline_vault.dart:18`; Export/Löschung, durchgängige Dateiklassifikation, feine Rechte und Secret-Store-Umstieg fehlen. | L | P1 RBAC/Audit/Datenschutz-/Migrationsbasis; laufende Dateninventar-, Secret-, Lösch-/Restore- und Betriebsabnahme; keine pauschale DSGVO-Zusage | 1–9 Querschnitt |
| O3 | Mobile App: Aufträge, Dokumentation, Zeit, Unterschrift, Kunden | teilweise | Projekt-/Kunden-/Doku-/Signatur-UI `app/lib/project_workspace_page.dart:20`, `app/lib/customer_pages.dart:13`, `app/lib/signature_editor.dart:31`; Zeiten, kompletter Auftragsfluss und Android/Web fehlen. | L | Plattformadapter, Rechte/Datenschutz, fachliche Module und nachgewiesene Geräteziel-/Syncfreigabe | 1–5; 7 mobil |
| O4 | Optionale Automationen: Kunden-Terminerinnerung, Rechnung nach Abschluss, KI-Telefonannahme; zuletzt | fehlt | `backend/workspace_api.py:23` und `backend/online/integrations_service.py:46`: keine Telefon-, automatische Rechnungsausgabe- oder allgemeine Koordinationsautomation. Bestehende Bot-/Backuptimer erfüllen das nicht. | L | Stabile P1–9, getrennte Flags/Adapter/Freigaben, Zustell-/Datenrechte; keine Vorverlagerung optionaler KI-Automation | 10 optional zuletzt |

## 9. Teststand und vorgelagerte Regressionen


### Ausgeführte sichere Bestandsbasis

Am 25.10.2026 ausschließlich bestehende Tests ausgeführt, keine Tests geschrieben/geändert. Bytecode bewusst deaktiviert, Test-DSN explizit leer, SQLite/Flask-Testclients/Monkeypatch-Provider, künstliche example.test-Daten. Keine Nutzerpostfächer, externen Services oder produktiven Datenbanken angesprochen. Ergebnis: **111 Tests, 14,607 s, OK**.

```text
PYTHONDONTWRITEBYTECODE=1 SMARTPLAN_TEST_DSN='' PYTHONPATH=backend:backend/online:scripts \
 /workspace/Smarplan-Hofmann-Workspace/backend/.venv/bin/python -B -m unittest \
 test_inquiries test_inbound_connectors test_inquiry_attachments \
 test_workspace_api.WorkspaceApiTests \
 test_inquiry_attachments_api.InquiryAttachmentApiTests \
 test_customers test_mail_bot test_mail_bot_attachments -q
```

Die Baseline belegt den unveränderten Stand dieses Worktrees. Kein Frontend-/PG-/Deploy-/Live-Gmaillauf wurde von diesem Analyseauftrag ausgeführt. Insbesondere keine Testdatenbank per Environment übernommen. Nach Testlauf Worktree weiterhin clean.

### Inhaltsabdeckung mit präzisen Symbolbelegen

| Testquelle | Vorhandene relevante Abdeckung |
| --- | --- |
| `backend/test_inbound_connectors.py:44` | Einmaliger Rohwert, hash-only DB/list/audit; Tokenlaufzeit/-limit; Replay nach Clockadvance/Rotation, owner mailbox scope; keine impliziten Kunden/Projekte; off-purpose tokens, fehlerhafte Felder/40k/200k-Guard; Konflikt ohne success timestamp; 60/min+Reset (`:139`); spätes Create-Failure rollt Inquiry/Receipt/last_used/rate gemeinsam zurück (`:148`). |
| `backend/test_inquiries.py:50` | Durable Inbox/kein stiller Kunde; aktuelle Ownerrolle, exaktes mehrdeutiges Matching (`:87`), source retry ownerübergreifend (`:100`), Revision/Statusfreiheit (`:116`), optionale explizite Zusage (`:131`), new→project ohne Zusage (`:140`), bestätigter neuer Kunde/Dublettenschutz (`:155`), spätes Convert-Rollback (`:167`), äußere Transaktion (`:185`), declined-Reaktivierung, EML Plain/HTML/Metadaten/Bereiche. |
| `backend/test_inquiry_attachments.py:90` | not_announced versus [] terminal; opake Original-IDs/unveränderliches reihenfolgeunabhängiges Manifest; out-of-order/resume/Reopen/complete idempotent (`:114`); Indizes/Längen/Gesamthash; Descriptorbounds/Quoten/Tokenrotation/Owner-Aktivierung; getrennte 600/min-Rate und Fehler zählen (`:206`, `:217`, `:227`); parallele Quotareservation (`:291`); byte purge/tombstone (`:317`); Rollen/Frischzuordnung (`:333`); Partial-/Unknownaggregation (`:355`); späte Rollbacks/äußere Transaktion (`:375`, `:403`); echte idempotente unabhängige Plankopie (`:411`, `:431`), Integritäts-/Schemafälle. |
| `backend/online/test_workspace_api.py:357` | Echte Flask-/normale-MFA-/Public-Scope-Grenzen, minimale received-Antwort, input injection, Tokenwiderruf; Pending-MFA/nonowners denied (`:384`); Ablauf/Rolechange/Envelope-HTTP (`:405`); wahrheitsgemäßer Verbindungstatus (`:425`); EML Base64/Metadaten-only (`:441`); Methoden/JSON/HTTPS/Header (`:467`). Voller Anfrage→Kunde→Projektpfad (`:239`), aber zusätzlicher HTTP-Atomikfall `:329` betrifft Workspace-Aufgabe/Tagebuch und NICHT neue-Kunde-Convert. |
| `backend/online/test_inquiry_attachments_api.py:202` | Vollständiger MFA→Body→zwei Originale→Resume/Reopen→Projekt→Download→Planimport→getrennte Löschung→Revoke. []/Altbody-Kompatibilität (`:205`); Sitzung/Offline/SPIN-Scope (`:218`); Tokenrotation vs anderer Owner/Postfach (`:249`); Accountant/Unassigned/Rolechange (`:277`); HTTP binary/MIME/encoding/JSON/method/length (`:306`); korrupte Storedchunks generisches500 (`:333`); Rate bei falschem Hash (`:349`). |
| `scripts/test_mail_bot.py:100` | Envelope-CLI/echtes veröffentlichtes synthetisches Beispiel lokal, sichere Authbinding/Argumente/Keyfiles/NoRedirect, keine unerlaubten fields, Parser-Duplicates/Nan/Size, nur valide minimal receipts; echter Flaskreceiver und verlorenes Ack (`:324`, `:351`), geänderter Originaltext/wrong mailbox/revoke (`:392`); Paketwhitelist/hashes, keine Secrets/DB-Dateien (`:407`). |
| `scripts/test_mail_bot_attachments.py:136` | Reale private synthetische Dateien hashen, tatsächliche Chunks/final complete, lost chunk receipt resume (`:156`), ready/tombstones nicht reuploaden; fehlerhafte fremde IDs/Metadaten/Zähler/Chunkclaims nie bestätigen (`:188`); Auth-/Netz-/404/-Rate/Redirect/no content leaks (`:237`); tatsächliche20/60MiB-Grenzen (`:285`); symlink/FIFO/publicfiles (`:300`); echter Flask-/DB-Reopen (`:369`), fehlender Parent wird nicht neu erfunden (`:395`). |
| `backend/test_customers.py:37` | Kunde bearbeiten/Projektname und altes signiertes PDF, Archivierung/Reaktivierung, Owner-only Kontakte/Notizen (`:77`), Dubletten/Validation, Backup-Restore und IDs/Legacy-Migration. |

Zusätzlich vorhanden, NUR gelesen / hier nicht ausgeführt:

- Reale separate PostgreSQL-HTTP-Abnahme, `backend/online/test_inquiry_attachments_api.py:378` (`PostgresInquiryAttachmentApiTests.test_real_postgres_two_file_mail_project_and_plan_source_survive_reconnect`), benötigt ausdrücklich disposable loopback `smartplan_check`-DB; `backend/online/test_workspace_api.py:504` für ursprünglichen Anfrage-/Projektpfad.
- Release-/Migrations-/Restore-Abnahmen `backend/online/test_release_attachments.py:151`, `:186`, `:200`, `:226`, `:234`: schema4→aktuell, Erhalt ready/partial/deleted-Originale, unabhängige Planquellen, Restore mit Tokenwiderruf, korruptes Original wird abgelehnt.
- Frontend `app/test/inquiry_widget_test.dart:206` ff.: Ownerguards, Filter, older server, lost response, EML-bounds, flexible Conversion, dirtysave, Tokenanzeige/revoke/auth loss/mobile390px.
- `app/test/mail_attachment_widget_test.dart`, `mail_attachment_integration_widget_test.dart:155`/`:216`/`:278`/`:317`/`:358`, `mail_attachment_preview_widget_test.dart`: Anhänge vor Mailtext, dirty note erhalten bei refresh/delete, korrekter Projekttab/Reload nach Planübernahme, Offlinehinweis ohne Anhangrequest, Vorschauguards.
- `app/test/customer_test.dart:139` ff. inkl. phone-width-editor `:276`.
- Apps-Script-Harness wird durch `backend/test_inbound_connectors.py:172` in obiger Basis ausgeführt (6 synthetische Scriptchecks). Kein Google-Login oder Zeittrigger dadurch abgenommen.

### Zusätzliche Vertragstests VOR späterer Gmail-/API-Arbeit

Die breite bestehende Abdeckung wiederverwenden, nicht ersatzlos neu schreiben. Zuerst folgende fehlende/noch nicht explizit konsolidierte Abnahmefälle ergänzen, dann erst relevante Produktionsänderung. Alle Tests ausschließlich synthetisch; APIvertrag vor Testszenarien festhalten. Dies ist ein Folgeplan, keine in Phase0 ausgeführten Änderungen.

1. **Ein einziger veröffentlichter Contract als Driftwächter:** Existierendes `openapi.json` maschinell gegen reale Flask-Responses/Requests validieren (alle vier Publicrouten, zulässige sieben Envelopefelder, Statuscodes/Headers, receipt exakt id/status/ingested_at, manifeste Descriptoren). CLI-/Apps-Script-/native Bots als Altclient-Fälle durchlaufen lassen. Aktuelle Tests prüfen viele Einzelfälle; ein parametrischer Schema-Conformance-/Diffgate für OpenAPI↔Backend ist noch nicht nachgewiesen.
2. **Altclient-Neue-CRM-Interoperabilität:** Vor CRMmigration fest erzeugte IDs/source_fingerprints/legacybody Requests ohne Anhänge sichern; nach Migration/Neustart identisch liefern, dieselbe Anfrage und keinerlei neue Customer-/Project-/Message-Sideeffects. Tokenrotation und Originalmanifest-Neunachtrag erhalten, old Bodyquittung bleibt201+minimal. Bereits fachlich converted/declined/accepted/überarbeitetes Inquiry nochmals per Legacy-Bot senden: kein Reset von Revision/Kunde/Projekt/Notiz, gleiche ID, originales received-Signal. Während Featureflag optionaler Lead-Automation weiterhin unkonfigurierte Standardsemantik ohne Autokunde/Projekt/Antwort.
3. **Durchgehende AK Anfrage→Kontakt+Projekt+Anhänge mit ausdrücklich NEUEM Kontakt:** HTTP-Conversion mit bestätigten neuen Kundendaten UND bereits fertigen Originaldateien. Wiederholung nach verlorener Conversionantwort/reopen liefert dieselben customer/project/attachment IDs und Bytehashes. Ein zusätzlicher frischer Request nach erfolgter Convert darf nicht duplizieren. HTTP-später Fehler (z. B. Audit/Receipt nach Projektinsert) rollt Kunden/Projekt/Status/Receipts vollständig zurück; Originalbytes/Manifest unangetastet. Domain-Atomik existiert bereits, HTTPanhangsworkflow verwendet bislang vorab separat erzeugten BESTEHENDEN Kunden.
4. **Übergabe bei partiellen oder noch nicht angekündigten Originalen:** Aus new zum Projekt konvertieren, während ein File uploading / Manifest noch not_announced ist. Keine erfundene Vollständigkeit, klare pending/unannounced UI; danach spätes Manifest/fehlende Chunks mit rotiertem zulässigem Token liefern und dieselben Dateien im bereits bestehenden Projekt sehen. Keine zweite Anfrage/Datei/Projektanlage, kein Pflichtphasen-Gate, kein späterer Autofinanzstatus. Verhalten ist nach aktuellem Code grundsätzlich möglich, aber nicht als End-to-end-Gate vollständig abgedeckt.
5. **Echte gleichzeitige Lieferung/Conversion/Tokenwechsel auf disposable PostgreSQL:** Zwei Prozesse liefern dieselbe Mail / dasselbe Manifest / dieselbe Convert-ID; keine500 durch unique race, genau einmal Businessstate/Quotenreservation/receipt. SQLite-Concurrency für Quota existiert; PostgreSQL-End-to-end ist bislang vorwiegend sequenziell. Respektive Cross-owner-Body-Dedupe vs ursprünglicher Upload-Owner explizit als bestehende Grenze beibehalten; Adminübernahme falls gewünscht als NEUEN bestätigten Vorgang planen.
6. **Werte-/Grenzmatrix am HTTP-Vertrag:** Exakte Unicode-/Bytesgrenzen 300/40k/200k/1M, CRLF und whitespace-normalisierte Replayinhalte, timestamp omitted/explicit Z/offset/UTCseconds; Body61+Retry-After und Clockfenster/Tokenrotation; Descriptoropaque-ID2048 und Filenames200; Chunk1..80; MIME-/Contentencoding+emptycomplete. Bestehende Domain-/CLIgrenzen decken vieles ab, aber OpenAPI-konsolidierte End-to-end-Boundarymatrix verhindert Abweichungen zwischen Code, Pluginen und Bots. Doppelte JSONkeys nach gesonderter Entscheidung als dokumentiertes Verhalten einfrieren oder versionieren.
7. **Rechte-/Need-to-know-Matrix VOR neuer Kontakt-/Dokumentfreigabe:** Owner/Manager/Techniker/Buchhaltung/Unassigned/Disabled/PendingMFA, jedes neue Contact-/Project-/Export-/Doc-Feld. Alte SPIN bleibt reines Einliefern, keine neuen Leserechte/Selfconvert/Autoreply. Neue notwendige Kontaktfelder nur bewusst freigegeben, historische Replayantworten dürfen Revocations nicht umgehen. Aktuelle permissive Projektoriginal-Lesbarkeit explizit als Ist dokumentieren; neue Klassifikation mit Abnahmegespräch definieren.
8. **DSGVO-Export-/Lösch-/Restore-Verträge vor deren Implementierung:** Export nur betroffener zulässiger Daten, keine Tokens/andere Kunden/Sicherheitsgeheimnisse, sauberes Manifest/hash/verknüpfte Originale; wiederholbarer Löschauftrag, gesetzlich geschützte Dokumente erklären, Kontakt-/Anfrage-/Receipt-/Dateiname-/Anhang-/Plan-/Snapshotkopien/Offline-/Backupumfang nach definiertem Konzept; neuer Botretry nach Löschung darf keinen personenbezogenen Datensatz still reanimieren; Disaster-Restore muss Löschentscheidungen wahren. Diese Funktionen fehlen heute; entsprechend neue Tests zuerst mit erwarteten AKs anlegen und Änderungen danach.
9. **Frontend durchgehender Abnahmepfad:** frische Gmail-Anfrage inkl. zwei Originalen → Kontakt bestätigen/neu → Projekt öffnen → Dokumente mit gleichen Hashes → optional Plankopie → Rückkehr ohne Datenverlust; Smartphoneansicht; Refresh/LostACK/Authverlust/Dokumentklassifikation; Vorhandene Widget-Fakes allein ersetzen den realen HTTP+SQL-Vertrag nicht.

Gatereihenfolge für jede spätere betroffene Änderung: (a) gewünschte additive Semantik und unveränderliche Altvertragteile benennen, (b) Bestandsbasis + neue spezifische Contracttests zuerst ausführen/erfassen, (c) kleinste passende Implementierung, (d) alle betroffenen Tests plus disposable PostgreSQL/Restore-/Releaseprüfungen bei Persistenzänderung, (e) vollständige synthetische Abnahmekette, (f) separat konfigurierter echter Anbieterpilot. Phase0 stoppt davor beim Docs-PR und der Nutzerprüfung.


## 10. Übergabe an die Umsetzung und Abnahmegrenze

Die verbindlichen Phasen und Haupt-AK stehen in [ZIELARCHITEKTUR.md, Abschnitt 13](ZIELARCHITEKTUR.md#13-meilensteine-prs-und-verbindliche-abnahme). Abhängigkeiten sind absichtlich gestaffelt: Artikel-/Leistungsbasis und Finanzarchiv schon in Phase 2, Checklisten in Phase 3, Zeiterfassungsübernahme erst mit Phase 4, Finanzexportkern in Phase 6, weitergehende Adapter in Phase 8. Aufmaßdaten kommen nicht allein durch die vorhandene maßstabslose Planzeichnung zustande.

Vor der ersten Produktänderung: Docs-PR reviewen, Intake-Regressionsfälle zuerst ergänzen, Migrations-/Down-Vertrag nachweisen und dann mit kleinen Conventional-Commit-PRs je Teilfunktion beginnen. Mehrere freigegebene PRs können in einem größeren getesteten Updatepaket ausgerollt werden. Bestehende Daten und Offlineeingaben werden nicht zur Vereinfachung verworfen.

Der Phase-0-PR enthält nur diese Gap-Analyse und die Zielarchitektur. Es gibt hier **keine neue Fachfunktion, keine neue Migration und keine Breaking Change**. Die künftige Berechtigungsmigration und jede unvermeidbare Inkompatibilität werden im jeweiligen Teil-PR unter `BREAKING` mit Migrationspfad offengelegt. Keine produktive Installation oder echte Providerabnahme wurde durch diese Analyse ausgelöst.

Der verpflichtende `docs/BERICHT_HERO_UMSETZUNG.md` wird ab der ersten Implementierungsphase fortgeschrieben und am Gesamtabschluss mit umgesetzten/offenen IDs, sämtlichen PRs/Migrationen, BREAKING-Pfaden, Testnachweisen, DSGVO-/GoBD-Betriebscheckliste und nächsten Schritten finalisiert. Phase 0 ist die Planungsübergabe, nicht der Abschluss des gesamten Ausbaus.
