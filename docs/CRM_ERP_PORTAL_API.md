# Angebotsportal: Schnittstellenvertrag der ersten Implementierung

Stand: 02.11.2026, Ausgangsbasis `54b08c2`. Konkretisierung des
[Portalplans](CRM_ERP_PORTAL_PLAN.md). Die folgenden Schnittstellen beschreiben
den [ersten entwickelten Umfang](CRM_ERP_PORTAL.md); diese Datei allein ist
kein Funktions- oder Abnahmenachweis.

## Gemeinsame Grenzen

- Neues additives Modul `business_portal`, Feature `offer_portal`, Fachrecht
  `portal.manage` ohne zusätzliche Standardfreigaben für interne Mitarbeiter.
- Der Online-Adapter setzt ausschließlich aus dem bereits geprüften Host
  `office.portal_origin = "https://…"`. Lokale Backendprozesse setzen dies nicht.
  Das Modul meldet sein Feature über `runtime_features(office)` nur bei gültigem
  Online-Origin. Es erzeugt ohne diesen Kontext keine Kundenfreigabe.
- Geschäftliche Schreibvorgänge benötigen aktiven Businessmodus, aktivierte
  Dokumente und den vorhandenen Restore-/Finanzabgleich. Widerruf und Logout
  bleiben Sicherheitsaktionen. Kunden werden nie zu internen Office-Benutzern.
- Kein E-Mail-Versand. Keine automatische Rechnung, Zahlung, Terminbuchung oder
  Bestellung. Annahme und interne Auftragsübernahme sind getrennte Vorgänge.
- Ablaufdaten betreffen den Zugang; sie ändern keine Bedingungen des finalen
  Angebotstexts. Linkbesitz und erklärte Namen sind keine extern verifizierte
  Vertretungsberechtigung oder QES.

## Interne HTTP-Schnittstelle

Basis `/api/v1/business`, bestehender interner Bearer und aktuelle Projektrechte.
Alle IDs sind 32 Hexzeichen. Unbekannte Felder/Methoden werden abgewiesen.

| Methode/Pfad | Eingabe | Antwort |
| --- | --- | --- |
| `GET /portal/grants?offer_id=…` | Nur `offer_id` | `{source,items,decision,adoption}` |
| `POST /portal/grants` | `request_id`, `offer_id`, `source_revision`, `content_hash`, `pdf_hash`, `recipient_name`, `recipient_email`, `expires_in_days` (1–30), `confirmation:true` | `{grant,link_available,portal_url?}`, 201 |
| `POST /portal/grants/{id}/revoke` | `request_id`, `reason`, `confirmation:true` | Grant, 200 |
| `POST /portal/offers/{id}/adopt` | `request_id`, `decision_id`, `source_revision`, `content_hash`, `pdf_hash`, `confirmation:true` | Adoption, 201 |

Lesen, Freigabe und Widerruf benötigen `portal.manage` und `finance.read` im
Quellprojekt. Übernahme zusätzlich `finance.write` und `projects.manage`.
Alle Rechte werden vor Wiederholungsantworten erneut geprüft.

`source` enthält `offer_id`, `number`, `project_id`, `customer_id`,
`source_revision`, `content_hash` und `pdf_hash`. Nur ein finales, unverändert
archiviertes Angebot mit aktivem, nicht gelöschtem Kunden kann freigegeben werden.

Ein Grant enthält `id`, dieselben Quellbindungen, `principal:{id,name,email,active}`,
`created_by`, `created_at`, `expires_at`, `status` (`active`, `expired`, `revoked`)
und gegebenenfalls `revocation`. Es enthält kein Geheimnis. Entscheidung und
Übernahme liegen separat in der Antwort der Angebotsübersicht.

Die URL lautet `https://HOST/office/portal.html#grant=ID&key=GEHEIMNIS`.
Sie wird ausschließlich bei erfolgreicher Ersterstellung zurückgegeben.
Gespeicherte Wiederholungsbelege enthalten nur Referenzen und Hashes. Eine
identische Wiederholung liefert denselben Grant mit `link_available:false` und
ohne URL. Bei verlorener Antwort zeigt der Client die bestehende Freigabe an;
ein neuer Link verlangt ausdrücklich Widerruf und neue Freigabe.
Eine bereits dokumentierte Entscheidung verhindert nach Widerruf oder Ablauf
keinen neuen ausdrücklich erstellten Zugang zum historischen Angebot. Dieser
zeigt die vorhandene Erklärung; eine zweite Entscheidung bleibt ausgeschlossen.

Eine Adoption enthält `id`, `offer_id`, `decision_id`, `document_id`,
`project_id`, `created_by`, `created_at`. Sie entsteht atomar mit genau einem
Auftragsbestätigungsentwurf durch den tatsächlich berechtigten internen Akteur.
Eine bereits vorhandene manuelle Auftragsbestätigung aus derselben Quelle wird
nicht automatisch übernommen und verhindert einen weiteren Entwurf.

## Getrennte Kundenschnittstelle

Basis `/api/v1/portal`. Keine Office-Sitzung und keine Cookies. Kundentokens
haben den eigenen Präfix `SPPT_`, Einladungsgeheimnisse `SPPI_`; beide verwenden
mindestens 32 zufällige Bytes und werden nur als Hash gespeichert. Der
Authorization-Header einer Kundensitzung lautet `Bearer SPPT_…`.

Alle öffentlichen POST-Routen verlangen JSON und den exakten konfigurierten
HTTPS-Origin. Nicht benötigte Query-/Bodyparameter werden abgewiesen. Der
Online-Adapter begrenzt Eingaben und zählt Fehlversuche unabhängig von der
anschließenden Authentifizierung. Die bestehenden Host-/TLS-/CSP-/No-store-
Grenzen bleiben aktiv. Kein Fetch fremder URLs und kein offenes CORS.

| Methode/Pfad | Eingabe | Antwort |
| --- | --- | --- |
| `POST /sessions` | `grant_id`, `key` | `{token,expires_at}`, 201 |
| `POST /logout` | leeres Objekt, Kundentoken | `{logged_out:true}` |
| `GET /offer` | Kundentoken, keine weiteren Parameter | `{offer,expires_at,decision,actions_allowed,statements}` |
| `GET /offer/pdf` | Kundentoken | Bytegleiches Original-PDF als Download |
| `POST /offer/decision` | `request_id`, `content_hash`, `pdf_hash`, `decision` (`accepted`/`declined`), `declared_name`, `statement_version`, `confirmation:true` | Decision, 201 |

Eine Sitzung gilt höchstens 30 Minuten und nie länger als ihre Freigabe. Eine
Freigabe erlaubt höchstens fünf gleichzeitig aktive Sitzungen. Derselbe
Einladungslink kann bis Ablauf/Widerruf erneut eine Sitzung öffnen; er ist kein
einmaliger Aktivierungscode. Fehlversuche und Sitzungsmenge sind begrenzt.

`offer` enthält `id`, `number`, `revision`, `content_hash`, `pdf_hash`, `title`,
`issue_date`, `due_date`, `currency`, `intro`, `notes`, `buyer`, `issuer`,
`positions`, `totals`. Aussteller/Kunde und Positionen werden ausdrücklich
projiziert. Erlaubt sind gedruckte Anschrifts-/Kontaktangaben, Beschreibungen,
Mengen, Einheiten, Verkaufspreise, Rabatte, Steuern und Netto-/Bruttobeträge.
Keine Artikel-, Aufmaß-, Zeit-, Kalkulations- oder Personalsnapshots, Kosten,
Margen, Vorlagenquellen oder internen Ausstellereinstellungen. Folgende
Unterfelder sind zulässig, soweit sie im archivierten Angebot vorhanden sind:

- `buyer`: `name`, `contact_name`, `address_line`, `postal_code`, `city`,
  `country`, `email`, `vat_id`.
- `issuer`: `company_name`, `address_line`, `postal_code`, `city`, `country`,
  `email`, `phone`, `website`, `vat_id`, `tax_number`, `iban`, `bic`,
  `payment_terms`, `footer`.
- `positions[]`: `index`, `description`, `quantity`, `unit`, `unit_price_net`,
  `price_base_quantity`, `discount_percent`, `tax_rate`, `tax_category`,
  `tax_exemption_reason`, `net`.
- `totals`: `net`, `tax`, `gross`, `payable`, `labor_net`, `labor_tax`,
  `labor_gross`, `material_net`, `material_tax`, `material_gross`,
  `tax_breakdown[]` mit `rate`, `category`, `reason`, `net`, `tax`.

Die Darstellung berücksichtigt Preisbasismengen und erfindet keine fehlenden
Vertragsdaten. Das archivierte Original-PDF bleibt bytegleich abrufbar.

`statements` enthält `version`, `accepted`, `declined`. Die Oberfläche zeigt
den passenden Wortlaut vor dem ausdrücklichen Senden an. Der Server speichert
Version und tatsächlichen Wortlaut zusammen mit der Entscheidung.

Eine Decision enthält `id`, `offer_id`, `grant_id`, `principal_id`, `decision`,
`declared_name`, `statement_version`, `statement_text`, `content_hash`,
`pdf_hash`, `created_at`. Höchstens eine abschließende Erklärung je Angebot.
Gleiche Anfrage-ID/Inhalte liefern nach erneuter Zugangsprüfung denselben
Beleg. Andere Inhalte oder eine neue konkurrierende Entscheidung ergeben 409;
der Client lädt die tatsächliche Entscheidung neu. Archiv und Belegstatus
bleiben unverändert. Keine erfundene interne Benutzeridentität für Kundenaudit.

## Domänen-/Adaptervertrag und Restore

`Portal(office, clock=…)` erstellt keine Tabellen. Interne Methoden heißen
`list_grants(actor,offer_id)`, `create_grant(actor,data)`,
`revoke_grant(actor,grant_id,data)`, `adopt(actor,offer_id,data)`.
Kundenmethoden heißen `open_session(grant_id,key)`, `logout(token)`,
`view(token)`, `pdf(token)` (Bytes und Dateiname), `decide(token,data)`.
Der Online-Adapter verwendet diese Methoden und synthetisiert keinen Owner.
Der organisationsbezogene Schreibschutz wird nach eigener Authentifizierung
über `business_organization.module_enabled(office,'documents')` geprüft; diese
Hilfsfunktion vergibt selbst keine Identität oder Objektberechtigung.

Das Modul stellt außerdem `count_attempt(office,key,limit,window_seconds)` für
kurzlebige gehashte Ratenzähler bereit. Die Zähltransaktion wird auch bei
nachfolgendem Fehler abgeschlossen. Der Online-Adapter bildet den Schlüssel
aus dem vertrauenswürdigen Proxy-Client und einer HMAC mit dem Server-Vault-Key;
rohe IPs, Geheimnisse und vollständige Bodies werden nicht protokolliert.

`sanitize_after_restore(db)` arbeitet innerhalb der Transaktion des Aufrufers:
alle vorhandenen Grants erhalten, soweit nicht schon widerrufen, einen
unveränderlichen Restore-Widerruf ohne erfundenen internen Benutzer. Principals
werden deaktiviert, Sitzungen/Ratenzähler gelöscht. Entscheidungen, Übernahmen
und Originalarchive bleiben erhalten. Hook in PostgreSQL- und SQLite-Restore;
keine Anwendung bei normaler additiver Softwaremigration.

Die Integritätsprüfung unterscheidet historische Bindungen von aktuellem
Zugriff: Eine spätere legitime Kundenneuzuordnung oder Löschung kann den
Portalzugriff sperren, ohne deshalb die gesamte historische Datenbank als
beschädigt zu verwerfen. Manipulierte Beleg-/PDF-Hashes und widersprüchliche
historische Beziehungen werden dagegen abgewiesen.
