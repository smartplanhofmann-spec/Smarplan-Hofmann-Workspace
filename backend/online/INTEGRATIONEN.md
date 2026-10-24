# Online-Integrationsvertrag 0.11 / Schema 6

Provider IDs: sevdesk, google_calendar, onedrive. Nur der Online-Adapter bietet
business_integrations; lokale und Offline-/SPIN-Zugänge erhalten diese Rechte nicht.
Normale App-APIs verwenden einen aktuellen Office-Bearer. Die neue SPIX-Bindung
hat ausschließlich die unten genannten Bot-Eingänge.

## App-Endpunkte unter /api/v1

- GET /integrations: sichere Verbindungszustände; keine Schlüssel/Ciphertexte.
- POST /integrations/sevdesk/connect: api_token, request_id; echte lesende
  Prüfung vor verschlüsselter Speicherung. Schlechter Ersatz erhält die alte Verbindung.
- POST /integrations/bot/connect: request_id; stellt einen gemeinsamen SPIX-Zugang
  für Google/OneDrive aus. Ausgabe nur in der privaten Antwort; exakte aktuelle
  Wiederholung kann den verschlüsselten Bootstrap fünf Minuten wiederholen.
  Dauerhafte referenzierende Receipts verhindern spätere X/Y/X-Schlüsselrotation.
- POST /integrations/bot/sync: leerer Auftrag für aktuelle Kontokataloge.
- POST /integrations/{provider}/catalog: optionale query; liefert items und pending.
- POST /integrations/{provider}/disconnect: request_id; lokale Trennung.
- GET /projects/{project}/integrations: aktuelle freigegebene Metadaten; bei
  fehlender Finanzrolle wird Sevdesk gar nicht serialisiert.
- POST /projects/{project}/integrations/{provider}/preview: generation sowie
  contact_id, calendar_id oder drive_id+folder_id; gegebenenfalls pending mit Job-ID.
- POST /projects/{project}/integrations/{provider}/link: generation, revision,
  request_id und ausdrückliche Auswahl. Sevdesk zusätzlich offer_ids/invoice_ids;
  Google event_ids; OneDrive drive_id+folder_id.
- POST /projects/{project}/integrations/{provider}/sync: generation+revision.
- POST /projects/{project}/integrations/{provider}/unlink:
  generation+revision+request_id.

Alle Provider-/Projektaktionen prüfen Berechtigung und Konto-/Zuordnungsgeneration
vor I/O und erneut vor Speicherung. Bestätigte Link-Wiederholungen lesen heutige
Daten, auch unter konkurrierender Verarbeitung, und überschreiben keine neueren
Snapshots. Quelle und Status bleiben getrennt; ein pending-Job ist kein neuer Abruf.

## Projektbot

Das vollständige maschinenlesbare Schema und portable Hilfsprogramm stehen in
integrations/project_bot. Feste Endpunkte:

    GET /api/v1/intake/integrations/jobs
    POST /api/v1/intake/integrations/jobs/{32hex}/result

Authorization wird über SMARTPLAN_INTEGRATION_TOKEN gebunden. Ein gültiger SPIX
ist kein SPIN und keine normale Office-Sitzung. Jobs enthalten nur Provider,
Art, tatsächliche Ressourcenkennungen, ausdrückliche Auswahl und Epochdaten.
Metadaten bis 2 MiB, begrenzte Datensätze; keine Datei-/Bas64- oder Providersecrets.

Ergebnis: source_id und complete:true/payload oder ein fester error_code. Erst
HTTP201 mit status:received, passender job_id und idempotent bestätigt die
Lieferquittung. Eine Fehlerquittung bestätigt ausschließlich den Fehlerbericht.
Exakte Wiederholung ist idempotent, veränderte Wiederholung409. Stale/revokte
Aufträge werden nicht angewendet. Authentifizierte ungültige Abrufe verbrauchen
vor dem späteren Parse-/Lookupfehler den eigenen300/min-Ratenzähler.

Kataloge bestätigen eine stabile Kontoidentität. Ressourcen dienen ausschließlich
zur Owner-Auswahl; nur selektierte Projekt-Snapshots werden Teammitgliedern
sichtbar. Kalender behalten RFC3339-Offsets und exklusive Ganztags-Enddaten.
OneDrive bindet Datei-ID mit Drive-ID und direktem Parent, erlaubt nur tatsächliche
Microsoft-Browseradressen und verwirft unauthentifizierte Download-/Freigabetokenlinks.
Der vorhandene Bot erweitert seinen Job; Kalender/Dateien werden nicht verändert.

## Datenbank und Wiederherstellung

external_connections, external_project_links, external_snapshots, external_requests,
external_oauth_states, external_bridge_jobs, external_bridge_limits. Zwei reine
Domainmodule erzeugen SQLite-/PostgreSQL-kompatible Schemata und gemeinsame
Integritätsprüfungen. Normaler Kandidatenklon erhält gültige Credentials.
Disaster-Restore prüft zuerst Snapshots/Receipts/FKs, leert dann Bridge-/OAuthdaten,
trennt neue Konfiguration/Credentials und erhöht Generationen. Bestehende Legacy-
OneDrive-AppFolder-Secrets sind ein gesonderter unveränderter Bereich.

## Alternative Google-Direktverbindung

POST /integrations/google_calendar/configure mit client_id/client_secret/request_id;
POST /integrations/google_calendar/connect mit leerem Objekt; öffentlicher
GET /integrations/google_calendar/callback mit einmaligem PKCE-State. Webanwendungs-
Client und Kalenderfreigaben sind erforderlich. Standard bleibt nach Nutzerwahl
jedoch die bereits bestehende Botverbindung. Keine Microsoft-/Dropbox-App wird
für die OneDrive-Metadatenbridge registriert.
