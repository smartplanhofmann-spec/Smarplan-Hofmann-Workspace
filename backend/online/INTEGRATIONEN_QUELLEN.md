# Tatsächlich geprüfte Quellen und Grenzen – 0.11

Alle Provider-I/O-Funktionstests verwenden synthetische Antworten. Keine echten Benutzerkonten oder Dateien wurden im Cloudworkspace verwendet.


## Sevdesk / Transport

# Sevdesk-Adapter: Quellen und tatsächliche Prüfgrenzen

Stand: 24.10.2026. Keine Zugangsschlüssel oder Kundenkonten verwendet; keine
Sevdesk-Datenoperation gegen ein echtes Konto ausgeführt.

## Abrufbare und gesperrte Quellen

Die Root-Recherche hat normale HTTPS-Aufrufe von `https://api.sevdesk.de/`
(HTTP403) und `https://my.sevdesk.de/api/v1/` (CONNECT403 Forbidden) versucht.
Diese Ziele wurden nicht erneut oder über einen anderen Weg abgefragt.

`https://api.github.com/users/sevdesk` war über `gh api` erfolgreich erreichbar
(HTTP200): Organisation „sevdesk“, Firma „sevDesk GmbH“, **0 öffentliche
Repositories**. Ein offizieller öffentlicher SDK lässt sich dort daher nicht
belegen. Die folgenden GitHub-Ressourcen waren regulär über die GitHub-API
erreichbar (HTTP200), sind aber **Sekundärquellen eines unabhängigen Autors**:

- SDK: <https://github.com/j-mastr/sevdesk-php-sdk>, geprüfter Commit
  `c3c32e5322af0db4ebf3230227f37f689531db87` vom 16.10.2026.
  Der README nennt das Projekt ausdrücklich „unofficial“, automatisch generiert
  und auf Anpassungen des folgenden OpenAPI-Projekts beruhend.
- Spezifikationsmirror:
  <https://github.com/j-mastr/sevdesk-api/blob/f72d04598a146aa9081a97d9cdfb7883d38fcba0/external/openapi.yaml>.
  Geprüfter Git-Blob `c947f46c3a3d54afb11c8c1e43610f90c8f28d70`, 671.199 Bytes.
  Das dortige `scripts/update.sh` nennt `https://api.sevdesk.de/openapi.yaml`
  als Quelle. **Die Übereinstimmung mit der momentan beim Anbieter ausgelieferten
  Spezifikation konnte wegen der Sperre nicht unabhängig bestätigt werden.**
- Lokale gelesene Kopien: `/tmp/smartplan-sevdesk-source/`.

## Daraus abgeleiteter enger Vertrag

Der Mirror und die generierten SDK-Dokumente nennen
`https://my.sevdesk.de/api/v1` als API-Basis und den unveränderten API-Schlüssel
im Header `Authorization` (ohne erfundenes Bearer-Präfix). Implementiert sind nur
GET-Aufrufe für `/SevUser`, `/Contact`, `/Contact/{id}`, `/Order`, `/Order/{id}`,
`/Invoice`, `/Invoice/{id}`. Die Identität wird an `sevClient.id` aus der
Benutzerantwort gebunden; der erste Benutzer wird nicht als aktuell angemeldeter
Benutzer ausgegeben.

Kontaktlisten verwenden die belegten Parameter `depth`, `limit`, `offset` und
gegebenenfalls `customerNumber`. Namenssuche erfolgt innerhalb eines auf 500
Kontakte begrenzten Katalogs; größere Ergebnisse werden ausdrücklich abgewiesen.
Dokumentlisten verwenden `contact[id]` und `contact[objectName]=Contact`.
Jeder zurückgegebene Dokumentbezug wird zusätzlich geprüft. Ein Projektsnapshot
ruft ausschließlich explizit ausgewählte Dokument-IDs erneut ab.

Angebote sind `Order.orderType=AN`; Auftragsbestätigungen `AB` und Lieferscheine
`LI` werden nicht als Angebote angezeigt. Belegte Order-Statuscodes sind
100 Entwurf, 200 versendet, 300 abgelehnt/storniert, 500 angenommen, 750 teilweise
berechnet, 1000 berechnet. Invoice-Status: 50 deaktivierte wiederkehrende Rechnung,
100 Entwurf, 200 offen, 750 teilweise bezahlt, 1000 bezahlt. Insbesondere wird aus 200
keine Aussage über Fälligkeit oder eine früher erfolgte Teilzahlung abgeleitet.
Unbekannte Codes bleiben sichtbar unbekannt.

`sumGross` ist im Antwortmodell ein Dezimalstring und `currency` ein
ISO-4217-Code. Der Adapter erhält Dezimalstrings unverändert, rechnet nicht mit
Fließkommazahlen und erfindet weder fehlende Beträge noch EUR als Ersatz.
Fehlende Werte bleiben `null`; falsche Zahlenformate werden abgewiesen.
Ein dokumentierter stabiler UI-Deeplink ist in den geprüften Quellen nicht
belegt: `document.url` bleibt `null`.

Die SDK-Dokumente führen an `/Invoice/{id}/getPdf` und `/Order/{id}/getPdf` einen
Parameter `preventSendBy` auf („Defines if u want to send ...“). Diese GET-Routen
werden deshalb ebenso wie Render-, Sende-, Buchungs- und Statusänderungsrouten
vom Transport vollständig ausgeschlossen. Die Implementierung lädt nur
Metadaten; sie erzeugt und versendet keine Angebote/Rechnungen.

## Lokale Prüfung

`PYTHONPATH=backend backend/.venv/bin/python -m unittest discover -s backend/online -p 'test_integration_*.py' -v`
prüft 24 eigene Fälle: feste Ziele/Pfade und Methoden, Rohheader, getrennte OAuth-POSTs,
keine Redirects (einschließlich echter lokaler HTTP-Antwort), Größen/Framing,
gemeinsame Deadline einschließlich echter langsam gelieferter HTTP-Header,
echte TLS-Loopback-Kommunikation mit überprüfter Test-CA/Hostnamen und Chunked-Body,
sichere Fehlerklassifikation, JSON-Grenzen,
Kontakt-/Dokumentbindung, gezielte Auswahl, Paging/Duplikate, Status und genaue
Dezimalwerte. Alle 24 eigenen Fälle sind grün; zusammen mit den inzwischen
vorhandenen Google-/Dropbox-Tests liefen 58 Integrationsfälle grün.
Dies ist keine Live-Kontoabnahme und ersetzt
die spätere ausdrücklich autorisierte Verbindungsprüfung mit dem Anbieter nicht.


## Google Kalender

# Google Calendar adapter: primary-source research

Reviewed 2026-10-24 for Smartplan 0.11. No real account credentials, OAuth grants,
calendar records or customer documents were used. Documentation downloads used
ordinary HTTPS; no proxy or policy bypass.

## Successfully read Google sources

- [Web-server OAuth](https://developers.google.com/identity/protocols/oauth2/web-server):
  registered web-application client ID/secret, exact registered redirect URI,
  authorization-code exchange, `access_type=offline`, `prompt=consent`, scope
  validation and refresh token handling. Authorize endpoint is
  `https://accounts.google.com/o/oauth2/v2/auth`; token endpoint is
  `https://oauth2.googleapis.com/token`.
- [Google's PKCE documentation](https://developers.google.com/identity/protocols/oauth2/native-app):
  Google documents verifier length 43–128, unreserved ASCII characters,
  S256 = unpadded base64url SHA256 of the verifier, and the corresponding
  `code_challenge`, `code_challenge_method`, `code_verifier` parameters on the
  same Google OAuth endpoints. This page describes installed applications;
  the actual configured confidential web-client consent remains a real-account
  acceptance step. We do not claim that the synthetic tests complete Google consent.
- [OAuth token expiration](https://developers.google.com/identity/protocols/oauth2#expiration):
  an External application in Testing gets refresh tokens expiring after seven
  days unless only basic identity scopes are requested. Calendar scopes do not
  meet that exception. Production/Internal application configuration and,
  where applicable, Google's verification are operator prerequisites for
  enduring use. This has no relationship to Smartplan's seven-day offline grant.
- [Calendar authorization scopes](https://developers.google.com/workspace/calendar/api/auth):
  `calendar.calendarlist.readonly` reads subscribed calendars;
  `calendar.events.readonly` reads events. The adapter requests these exact two
  scopes, no profile/email, writes, invitations or broader calendar scope.
  Public applications using user-data scopes may need Google's verification.
- [CalendarList.get](https://developers.google.com/workspace/calendar/api/v3/reference/calendarList/get):
  `primary` identifies the current user's primary calendar, and the calendar-list
  read scope suffices. Identity uses its canonical ID and title, avoiding extra
  identity scopes. No separate `calendars.get` permission is necessary.
- [CalendarList.list](https://developers.google.com/workspace/calendar/api/v3/reference/calendarList/list):
  opaque `nextPageToken`, page size at most 250, `minAccessRole=reader`, and
  omitted deleted/hidden calendars. The adapter requests 100 per page.
- [Events.list](https://developers.google.com/workspace/calendar/api/v3/reference/events/list):
  `singleEvents=true` expands recurring instances; `showDeleted=true` includes
  cancellations. With both true the recurring master is not returned.
  `timeMin` bounds event ends, `timeMax` bounds starts, both exclusive RFC3339
  timestamps with offsets. `orderBy=startTime` requires expanded single events.
  Pages can be empty while still having a next token. The endpoint supports
  `calendar.events.readonly`.
- [Events.get](https://developers.google.com/workspace/calendar/api/v3/reference/events/get)
  and [Events resource](https://developers.google.com/workspace/calendar/api/v3/reference/events):
  `end` is exclusive, including all-day dates; `dateTime` needs an offset unless
  `timeZone` is supplied. Recurring cancelled exceptions may have only ID,
  recurringEventId and originalStartTime; other deleted events may retain only
  their ID. Cancelled events are available through get until removed entirely.
  Descriptions can contain HTML and must remain ordinary text in the app.

Raw sources and extracted text are in this scratch directory (`google-*.html`,
`google-*.txt`). Events.list was reused from Root's successful
`/tmp/smartplan-integrations-source-2.html`; extracted text is
`google-events-list.txt`.

## Delivery contract and practical limits

The authorization code is exchanged with the server-held PKCE verifier and
web-client secret. Refresh responses are validated for bearer token type,
positive expiry, bounded tokens and exact read scopes; an omitted unchanged
scope/refresh token on refresh retains the original grant/token. A new OAuth
grant must provide both required scopes and a refresh token. Tokens are returned
only to the owning server service, which encrypts them and adds expires_at.

The owner selection preview is explicitly the previous 31 / next 366 days,
at most 5 × 100 events. Infinite recurrences cannot create an unbounded list;
excess pages or aggregate JSON cause a clear error instead of partial success.
Only explicitly selected event IDs (at most 50) are fetched for a project,
including selected dates outside the preview window. No list-wide contents are
automatically assigned to a project. All-day end dates stay exclusive;
timezone offsets and cancellation tombstones stay explicit.

The common transport permits only fixed Google API GET paths and the exact
OAuth form POST. Pagination tokens remain query values, never URLs to follow.
Every operation has the common 18-second total deadline. Upstream 401/known
invalid OAuth grants require reauthorization; resource-specific 403 remains a
separate permission error. 404/410 for a selected event becomes a cancellation
tombstone only after fresh access to the chosen calendar succeeds.

One optional public metadata source,
`https://accounts.google.com/.well-known/openid-configuration`, was attempted
once and blocked by the environment tunnel with HTTP403. It was not retried or
bypassed, and the adapter does not depend on runtime discovery.


## OneDrive

# OneDrive bridge: primary-source facts and local source contract

Date: 2026-10-24. User correction supersedes the earlier Dropbox implementation.
Only the existing mailbot's already connected OneDrive tools supply account,
folder and file metadata. No new Microsoft OAuth application, provider password,
direct Graph request, binary transfer or created sharing link is implemented.

## Official Microsoft source actually read

The following documentation source files were fetched normally from the official
Microsoft Graph documentation repository over allowed HTTPS:

- https://github.com/microsoftgraph/microsoft-graph-docs-contrib/blob/main/api-reference/v1.0/resources/driveitem.md
- https://github.com/microsoftgraph/microsoft-graph-docs-contrib/blob/main/api-reference/v1.0/resources/itemreference.md
- https://github.com/microsoftgraph/microsoft-graph-docs-contrib/blob/main/api-reference/v1.0/api/driveitem-list-children.md
- https://github.com/microsoftgraph/microsoft-graph-docs-contrib/blob/main/api-reference/v1.0/api/driveitem-get.md
- https://github.com/microsoftgraph/microsoft-graph-docs-contrib/blob/main/api-reference/v1.0/resources/user.md

No blocked host was bypassed. No real provider account, customer folder, document
or credential was accessed. Fixtures and tests are entirely synthetic.

Verified facts:

1. `driveItem.id` uniquely identifies the item **within its drive**. Therefore
   catalog identity is the pair `(drive_id, item_id)`; equal item IDs in different
   drives are not automatically duplicates.
2. `itemReference.driveId` is the drive identifier and `itemReference.id` is the
   item identifier. A file's `parentReference` identifies its actual parent;
   names alone do not establish project-folder membership.
3. `driveItem.eTag` describes metadata and content; `cTag` describes content and
   may be absent on folders. The bridge stores an actual supplied eTag or cTag
   unchanged in `rev`, including any quote characters.
4. `driveItem.webUrl` is the browser URL for the resource. The official get-item
   example uses an ordinary `https://contoso-my.sharepoint.com/personal/...`
   browser URL.
5. `@microsoft.graph.downloadUrl` is a different, unauthenticated, short-lived
   download URL. Documentation explicitly says it must not be cached. It is not
   accepted as a persistent project link and is not part of bridge payloads.
6. The children relationship returns direct DriveItems of the requested folder.
   List-children responses may contain `@odata.nextLink` when more pages exist;
   a partial page cannot truthfully be marked as a completed catalog/snapshot.
7. `itemReference.path` is a percent-encoded Graph API path, e.g.
   `/drive/root:/Documents/my%20file.docx`. The source protocol below deliberately
   uses an already normalized, decoded drive-relative path, e.g.
   `/Documents/my file.docx`; raw Graph objects or raw API URLs are not the input.
8. `user.id` is a unique opaque user identifier. The bot must supply the actual
   connected-account identity from its tool/connection metadata, rather than
   guessing identity from a folder name or a document's unrelated owner.

The normalizer's browser-host allowlist is an **application restriction**, not a
claim that Microsoft documents an exhaustive host list: `onedrive.live.com` and
tenant subdomains of `sharepoint.com`. It excludes generic `1drv.ms` short links
because no actual original-driveItem example for that shortener was established
in the sources read. Userinfo, fragments, control characters, preauthenticated
query parameters, direct-download actions and SharePoint sharing shortcuts are
also rejected. No link is generated or followed by this module.

## Exact normalized source input

`normalize_bridge_catalog(payload)`:

```json
{
  "complete": true,
  "identity": {"id": "actual-account-id", "label": "Actual account label"},
  "folders": [
    {
      "id": "actual-folder-id",
      "drive_id": "actual-drive-id",
      "name": "Projekt",
      "path": "/Projekt",
      "parent_id": "actual-parent-id",
      "url": "https://tenant.sharepoint.com/sites/site/Shared%20Documents/Projekt"
    }
  ]
}
```

`parent_id` and `url` are optional only on catalog folder entries. Identity has
exactly `id` and `label`; its serialized size is at most 8192 bytes. The catalog is
flat; it may contain actual folders from multiple drives. There is no recursive
fetch or Dropbox-style navigation protocol in Smartplan.

`normalize_bridge_resource(payload, selection)` and
`normalize_bridge_snapshot(payload, selection)` use the same source contract:

```json
{
  "complete": true,
  "folder": {
    "id": "actual-folder-id",
    "drive_id": "actual-drive-id",
    "name": "Projekt",
    "path": "/Projekt",
    "url": "https://tenant.sharepoint.com/sites/site/Shared%20Documents/Projekt"
  },
  "files": [
    {
      "id": "actual-file-id",
      "drive_id": "actual-drive-id",
      "parent_id": "actual-folder-id",
      "name": "Plan.pdf",
      "path": "/Projekt/Plan.pdf",
      "rev": "\"{actual-etag},1\"",
      "size": 12000,
      "media_type": "application/pdf",
      "url": "https://tenant.sharepoint.com/sites/site/Shared%20Documents/Projekt/Plan.pdf"
    }
  ]
}
```

Selection is exactly `{drive_id, folder_id}`. Folder `url` is optional; every file
requires its original browser URL and all listed fields. The selected drive and
folder must match, every file must have that direct parent and drive, its path
must represent a direct child, and file IDs must be unique. Root folder paths use
`/`. File sizes are metadata, so a valid large original link is not falsely given
the separate Gmail attachment-preview transfer limit.

Both protocols require `complete:true`; optional `has_more` is accepted only when
strictly false. Unknown fields, raw Graph objects, tokens, raw download URLs,
bytes, incomplete pages, control-bearing paths/names, invalid MIME types and
ambiguous duplicate identifiers fail without creating a successful snapshot.
Output preserves the verified fields and removes the transport completeness
flags. Genuine complete empty lists remain valid only with actual account or
selected-folder metadata.

Limits: 1000 folders/files per delivered result; complete serialized input at
most 2 MiB. No success, identity, name, revision or project association is guessed.
If the existing bot cannot obtain complete actual metadata, it must report a
fixed job error through the service rather than fabricate an empty success.

## Validation and preserved work

`backend/online/test_integration_onedrive.py`: 12 focused synthetic tests passed.
Log: `/tmp/smartplan-onedrive-bridge-tests.log`. Python compilation and targeted
diff checks passed. No live user/provider calls or shared PostgreSQL tests ran.

The earlier untracked Dropbox adapter/test were moved, not deleted, to
`/workspace/scratch/unused-dropbox-011/`. They are absent from the shipping tree.
