# E1b-4a1: ausdrücklich gespeichertes Vorbereitungsprofil

Stand: 03.11.2026. **Implementierungsvertrag mit gesondertem
[Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_E1B4A1.json).** Eigenständiger Abschnitt
nach E1b-3c. Tatsächlich ausgeführte Prüfungen und offene Grenzen werden im
Nachweis getrennt vom Vertrag festgehalten. Basis ist dessen
Nachweispin `91304fc9eb5cf8c42caa1c75c6b1d5c16ea2a612`, Implementierung
`bef8ec23adbddcde0b619f41b5df88db7d481d59`. Grundlagen:
[EÜR-Plan](CRM_ERP_EUER_PLAN.md) und
[nächster Schritt](CRM_ERP_EUER_NAECHSTER_SCHRITT.md).
Sachliche CashEvent-Einordnung gehört erst zu E1b-4a2.

## Umfang, Namen und Rechte

Additives Modul `business_accounting_profile`, Klasse
`AccountingPreparationProfile(office,clock=None)`, Feature
`accounting_preparation_profile`. Die vollständige bisherige Installation
einschließlich E1b-3c ist Voraussetzung. Der eigene Profilvalidator liest nur
seine zwei Tabellen und benötigt keinen CashEvent-/C2-/R2-Ledgeraufruf.

Pro Office-Datenbank gibt es eine fortlaufende Folge ausdrücklich bestätigter
Vorbereitungsstände. Weder Migration, GET, Anmeldung noch Öffnen des Editors
legt einen Profilstand an. Einzelunternehmen/EÜR darf im leeren Editor als
noch ungespeicherter Vorschlag erscheinen. Umsatzsteuer, Soll/Ist, deren
Beginn und Buchhaltungsbeginn bleiben leer. Ihre Beantwortung ist keine
Voraussetzung für das Speichern eines begründeten Vorbereitungsstands.

Das Profil dokumentiert Angaben, keine fachliche Freigabe. Alle bestehenden
Geldflüsse, Zuordnungen, Komponenten, Rücknahmen, Originale und Antworten
bleiben unverändert; auch `Accounting.status` behält seinen bisherigen
`profile_status:'unconfigured'`. Der neue Status heißt `preparation_status`.
Gespeicherte Angaben aktivieren keine Steuerregel und sperren keine bisher
zulässige Finanzoperation wegen fehlender Profilvollständigkeit.

Lesen verlangt global `accounting.read` und `finance.read`; Vorschau und
Bestätigung zusätzlich global `accounting.admin`. Keine neue Berechtigung,
kein `accounting.prepare` oder `finance.write` als Ersatz. Projektgrants
reichen nicht. Profilangaben haben keine Projekt-/CashEventquelle; deshalb
keine zusätzliche Quellenhülle oder Originaldownloadberechtigung erfinden.
Bestehende Sitzung/MFA-, Businessmodus-, Financeaktivierungs-, Runtime- und
Restoregrenzen gelten. Autorisierte Historie bleibt bei Schreibsperre lesbar.

## Profil und feste DTOs

Profile enthält exakt:

```text
{legal_form:'sole_proprietorship',accounting_method:'euer',
 vat_regime:null|'small_business'|'regular',
 vat_timing:null|'accrual'|'cash',
 vat_effective_from:null|YYYY-MM-DD,bookkeeping_start:null|YYYY-MM-DD}
```

`accrual` bezeichnet erklärte Soll-, `cash` erklärte Istbesteuerung.
vat_timing darf nur bei vat_regime regular nicht null sein;
vat_effective_from nur bei bekanntem vat_regime. Ansonsten sind alle vier
optionalen Angaben unabhängig leer speicherbar; regular verlangt noch keine
Timing-/Datumsantwort. Daten sind gültige kanonische ISO-Kalendertage im
vorhandenen Bereich 1900–2200. Kein Datum wird aus Erfassungszeit, erster
Zahlung oder Belegen abgeleitet. Die beiden Datumsfelder sind erklärte Fakten,
keine implementierte Perioden-/Profilgültigkeitssteuerung. Zwischen ihnen
wird keine erfundene Reihenfolgebedingung geprüft.

Andere Unternehmens-/Buchführungsformen sind in diesem Abschnitt nicht
unterstützt. Leere UI-Felder werden zu JSON null, nicht zu Leerstring,
`unknown`, false oder einem Standardwert. Auch künftig ausdrücklich
eingetragene Steuermerkmale bleiben bloße Angaben ohne Berechnung/Freigabe.

Gemeinsame Flags exakt:
`scope:'organization_profile',tax_status:'unconfigured',tax_result_available:false`.
Diese Sicht beschreibt das Office-Profil, keine vollständige Finanzsicht.

State exakt:

```text
{revision,state_hash,preparation_status:'unrecorded'|'recorded',
 current:null|Entry,writes_allowed,scope,tax_status,tax_result_available}
```

revision ist die Anzahl gespeicherter Versionen. Bei 0: current null und
unrecorded; sonst current die letzte Version und recorded. Es gibt keinen
Status configured/approved/complete. writes_allowed prüft frische Adminrechte
und die bestehenden Schreibgates; es behauptet keine steuerliche Zulässigkeit.

Previewbody exakt:

```text
{expected_revision,state_hash,profile:Profile,reason,evidence_reference}
```

expected_revision ist ein strikter Integer ab 0, kein bool. reason 1–1000,
evidence_reference 1–200 Zeichen; beide Strings einzeilig, nicht nur Leerraum,
ohne Steuerzeichen/DEL/Surrogates. Keine stille Normalisierung gespeicherter
Werte. Die Referenz darf etwa eine ausdrücklich bestätigte Inhaberangabe oder
einen eigenen Nachweis benennen. Sie behauptet keinen geprüften Behördenbeleg;
kein Abruf, Upload, Versand oder automatische Dokumentzuordnung.

Preview exakt Previewbody plus preview_hash und gemeinsame Flags.
preview_hash = SHA-256 des vollständigen kanonischen Preview ohne preview_hash.
Confirmbody exakt Previewbody plus `{request_id,preview_hash,confirmation:true}`.

Entry exakt Preview ohne expected_revision/state_hash, dafür
`{id,revision,previous_state_hash,created_by,created_at}`.
previous_state_hash ist der damals bestätigte state_hash; revision die neue
positive Profilrevision. IDs/Request-/Akteur-IDs: 32 Kleinhexzeichen, Hashes:
64 Kleinhexzeichen. created_at wird serverseitig als kanonischer UTC-Zeitpunkt
erzeugt und bleibt unverändert.

## Routen, Vorschau und Quittung

Basis `/api/v1/business/accounting/profile`:

| Methode/Pfad | Ergebnis |
| --- | --- |
| GET Basis | State, 200 |
| GET /history?limit=50&offset=0 | `{items:[Entry],total,next_offset,scope:'organization_profile'}`, 200 |
| POST /preview | Preview, 200; keinerlei DB-/Auditwirkung |
| POST /confirm | Entry, 201; identischer erfolgreicher Replay ebenfalls 201 |

History nach revision DESC,id; limit 1–100, offset 0–100000. Keine weiteren
Filter, GET-Bodies, POST-Queries, unbekannten Felder oder doppelten Parameter.
Eine identische fachliche Angabe darf mit neuem Grund/Bezug und eigener
ausdrücklicher Bestätigung erneut versioniert werden; keine automatische
Zusammenführung. Es gibt keinen UPDATE-/DELETE-/Aktivierungsendpunkt.

Bestätigung innerhalb der bestehenden SQLite-IMMEDIATE-/PG-Advisory-
Transaktion: frische Rechte und Schreibgates, vollständige eigene Integrität,
Lookup der eigenen Benutzer-/Requestquittung. Identischer Request liefert den
unveränderten alten Entry, auch nach späteren Profilversionen. Gleiche ID mit
anderem Body liefert unmarkierten409. Erst bei fehlender Quittung aktuellen
Revisions-/State-/Previewhash prüfen, dann Version, Quittung und Audit atomar
schreiben. Keine Prüfung heutiger Revision vor erfolgreichem Replay.

Nur nach sicher fehlendem Receipt, vor jeglichem Insert/Audit, darf ein
aktueller409-Konflikt `{error,request_resolution:'not_accepted'}` tragen.
Sicherheits-/Restore-/Integritätsgates vor Lookup bleiben unmarkiert.
400 gilt für falsche Eingaben,403 für fehlende globale Rechte,409 für Stand/
Quittung/Integrität,423 für Financepause,405 für falsche Methode.

Beide Clients führen einen eigenen logischen Pendingkey für den Profilconfirm.
Sie bewahren exakten ursprünglichen Pfad, Body und request_id. Vor Retry
Metadaten/Rechte und eigenen Profil-State frisch lesen; keine heutige Revision
oder Vollständigkeit als Replaygate. Pending neutral anzeigen. Erfolg oder
markierter409 lösen den unklaren Auftrag; erster wie späterer403/404,
unmarkierter409,423,5xx und Netzfehler erhalten ihn. Die begrenzte bestehende
Clientregel wird nur um diesen Confirmpfad erweitert; andere Vorgänge bleiben
unverändert. Logout/Identitätswechsel und verspätete ACKs behalten die
vorhandenen Sitzungs-/Generationsgrenzen.

## Zwei Tabellen und vollständige Rekonstruktion

`business_accounting_profile_versions`:
`id TEXT PK`, `revision INTEGER NOT NULL UNIQUE CHECK(revision>0)`,
`previous_state_hash TEXT NOT NULL`, `entry_json TEXT NOT NULL`,
`entry_sha256 TEXT NOT NULL`, `created_by TEXT NOT NULL FK users(id)`,
`created_at TEXT NOT NULL`. Hashspalten haben CHECK length=64.

`business_accounting_profile_requests`:
`user_id TEXT FK users(id)`, `request_id TEXT`, PK(user_id,request_id),
`request_json TEXT NOT NULL`, `request_hash TEXT NOT NULL CHECK(length=64)`,
`entry_id TEXT NOT NULL UNIQUE FK profile_versions(id)`; PK-Felder NOT NULL.
Requesthash = SHA-256 des kanonischen
`['profile.confirm',null,<ganzer ursprünglicher Confirmbody>]`.

Statehash = SHA-256 des kanonischen
`{schema_version:1,revision,head:null|{id,entry_sha256}}`.
Bei revision0 ist head null; sonst der zuletzt vollständig geprüfte Entry.
Jeder Entry.previous_state_hash muss zum tatsächlich rekonstruierten vorigen
Präfix passen. IDs, exakte DTO-/JSON-Formen, Werte, Flags, Zeitpunkte, lückenlose
Revisionen1..N, Previewhash und ursprünglicher Request werden geprüft.
Jede Version besitzt genau eine passende Quittung; Akteur, erwartete Revision,
Hash, Felder und Bestätigung stimmen exakt überein. Orphans, Zweige, Lücken,
veränderte Spalten und inkonsistente neu gehashte Daten scheitern geschlossen.
Keine alternative steuerliche Ableitung aus heutigen Einstellungen.

Beide Tabellen erhalten vorhandenen UPDATE-/DELETE-Schutz, SQLite zusätzlich
REPLACE-Konfliktschutz für alle Unique-Grenzen, PG Runtime nur SELECT/INSERT.
Eigene Integrität und Horizont sind nebenwirkungsfrei. Vollständig nicht
installiert bedeutet beide Tabellen und Migrationsmarker fehlen; Teilbestand
oder fehlende Abhängigkeit ergibt Fehler. Alte Modul-DDL/Checksummen bleiben.

## Restore und Abnahmegrenze

Eigener P1-Horizont exakt:

```text
{schema_version:1,table_counts:{business_accounting_profile_versions:<int>,
 business_accounting_profile_requests:<int>},sha256}
```

Hash wie bestehende Module über kanonisches
`{schema_version:1,tables:{<Tabellenname>:[vollständige geprüfte DB-Zeilen]}}`,
je Tabelle nach kanonischer Zeilenrepräsentation sortiert. Installiert und
leer ergibt beide Counts0, nicht null. Neuer H7 enthält exakt die bisherigen
H6-Felder plus profile:P1 und schema_version:7. Neue Betreiberfreigabe verlangt
Berichtschema8, auch bei leerem installiertem Profilmodul. Sonstige äußere
Betreiberfelder bleiben gleich. Historische H6/Berichtschema7 und ältere
Inventare bleiben fest; erfolgreiche alte identische Quittungen nur ohne neue
Entsperrwirkung replayen, keine neue Rücksicherung damit freigeben.

Gezielte Abnahme: (1) leere Migration/GET/Preview ohne Profilzeile; null bleibt
null, keine Istannahme; (2) explizite erste/zweite Version, History und exakter
alter Replay; (3) echte PG-Revisionskonkurrenz und vollständiger Rollback;
(4) Rechte-/Modus-/Restorewechsel einschließlich Pending-Erst403/404;
(5) Lücken/Orphans/Neu-Hash-Tamper und SQLite-/PG-Guards; (6) bytegleicher
3c-Altbestand, H7/schema8 und genuine alte Freigabegrenzen; (7) Browser und
Flutter über echte API mit leerem Profil, ausdrücklicher Vorschau/Bestätigung,
weiter leerer Umsatzsteuer, Historie und Antwortverlust. Kein ausgeführter
Nachweis wird durch diesen Vertrag behauptet.
