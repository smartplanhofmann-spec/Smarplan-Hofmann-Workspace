# Lieferantenkataloge im Browser – Umsetzung und Nachweise

Stand: 4. November 2026. Isolierter Arbeitsbaum `/workspace/smartplan-catalog-browser-20261104`, Ausgangsstand `2fdfa9f`. Dieses Paket erfüllt den lokalen Browser-Dateiimport des Gesamtziels. Es ist keine Fertigmeldung für die gesamte CRM-/ERP-Software und keine Lieferanten- oder Produktivfreigabe.

## Bestandsaufnahme und verbindlicher Umfang

Das Gesamtziel und `CRM_ERP_GESAMTZIEL_GEGENPRUEFUNG_2026-11-04.md` wurden zugrunde gelegt. Der Bestand hatte einen tatsächlich arbeitenden CSV-/DATANORM-Import im Backend und im nativen Client. Im Browser zeigte der Einstellungsdialog ausschließlich Adapterstatus. Es gab keinen öffentlichen Abruf früherer Katalogimporte und keine dauerhafte Speicherung der hochgeladenen Katalogoriginale.

Weiterhin gelten ausschließlich die vorhandenen Formate:

- `catalog_csv_v1`: UTF-8 mit optionalem BOM, Semikolon, exakte Kopfzeile `code;name;unit;cost_price_net;unit_price_net;tax_rate`, Dezimalpunkt und höchstens vier Nachkommastellen.
- `datanorm_a14_cp850_v1`: CP850, ausschließlich A/N-Neuanlagen mit genau 14 Feldern. Rohpreisskalierung, Nettopreisziel und Umsatzsteuersatz sind ausdrückliche Eingaben. Rabatt-/Langtextverweise werden blockiert. Dies ist keine vollständige DATANORM-Zertifizierung.
- Maximal 2 MiB Originalbytes und 2.000 Artikel. Die bestehenden fachlichen Artikelgrenzen bleiben zusätzlich verbindlich; ein syntaktisch lesbarer Katalog kann deshalb in der Übernahmevorschau fachlich abgelehnt werden.

CSV v2, zeitliche Preisgültigkeit, automatische Lieferantenkontakte, Lieferantenbestellungen und neue steuerliche Annahmen gehören nicht zu diesem Paket. Unsichere Browseraufträge bleiben nur in der laufenden RAM-Sitzung; Logout und Seitenneuladen verwerfen diese lokale Warteschlange. Bereits gespeicherte Vorgänge bleiben über die geschützte Historie überprüfbar. Es wird kein automatischer Ersatzauftrag mit neuer ID erzeugt.

## Umsetzung und Anforderungsabgleich

| Anforderung | Umsetzung | Nachweis |
| --- | --- | --- |
| Lokale Datei auswählen | Eigene Katalogquelle mit festem Format; echte Dateiauswahl, Größenprüfung und unveränderte Bytes | Chromium: CSV und DATANORM, Originaldownload |
| Vorschau vor Artikeländerung | Speicherung als `staged`; rein lesende serverseitige Übernahmevorschau; explizite Checkbox vor Annahme | Backend: keine Artikel-/Quittungs-/Audit-Schreibvorgänge bei Vorschau; Browser: keine Artikel vor Annahme |
| Unterschiede und Fehler sehen | Gebundene Artikelrevisionen, neue/geänderte/unveränderte Artikel, Einheit und beide Preise, Artikelart/Aktivstatus/Kostenkennzeichnung/Kalkulation; fachliche Fehler bleiben sichtbar | Nodefixtures aus echtem Backend; Chromium: Einheit-/Preiswechsel und Doppelnummerfehler |
| Tatsächliche Bestandsentscheidung | Gemeinsame unveränderte V1-Zeilenentscheidung für Vorschau und Annahme, einschließlich `noop` bei identischem Quellhash | Reproduzierter Fall `cost_known=false`: Vorschau und Annahme lassen die manuelle Metainformation unverändert |
| Historie und Originale | Begrenzte Historienseiten, einzelner Import mit vollständigen Positionen, Originaldownload mit erneuter Rechte- und Hashprüfung | SQLite-/PostgreSQL-Wiederöffnung, Chromium-Download bytegleich |
| Wiederholung nach verlorener Antwort | Ursprüngliche Datei, Werte und `request_id` bleiben in der RAM-Auftragsverwaltung; vor Wiederholung aktuelle Rechte | Tatsächlich verlorene Import-/Annahme-ACKs, identische erneute HTTP-Aufträge und keine doppelten Effekte |
| Rechte und Ansichtswechsel | Einstellungen- und Finanzrechte; Schreibrecht/Modulstatus vor Annahme; Kontext-/Sitzungsstempel und Editor-Epochen; Schließen bei Background | Unabhängige UI-Callback-Gegenfälle sowie echter MFA-/HTTP-Rechteentzug |
| Mobile Bedienung und große Dateien | Scrollbarer Dialog, seitenweise Positionen, 390-Pixel-Ansicht; eigene begrenzte JSON-Antwortgröße für Unicode und Vorher-/Nachher-Snapshots | Chromium mit genau 2 MiB, 2.000 Unicode-Artikeln, Seitenwechsel und Originaldownload |

## Additiver Backendvertrag

Das neue Modul `business_catalog_imports` enthält ausschließlich zusätzliche Original-/Legacy-/Annahmetabellen. Vorhandene Adaptertabellen, deren Schemachecksummen, bereits gespeicherte Runs und Requestquittungen werden nicht umgeschrieben. Die explizite Migration kennzeichnet vorhandene Imports als Altbestand. Für diese wird `original.available=false` mit Grund `legacy_original_not_stored` geliefert; Originalbytes werden niemals aus Positionen erfunden.

Neue Imports speichern tatsächliche Bytes, Dateiname, Quell-/Positionshash, ursprünglichen Auftrag und ursprüngliche Artikelrevisionen atomar. Die spätere Annahme speichert einen eigenen unveränderlichen Beleg mit Quellhash, Auftrag, Preiszuordnung und tatsächlich verwendeten Artikelversionen. Trigger und getrennte PostgreSQL-Runtime-Rechte verhindern Änderungen und Löschungen. Die Integritätsprüfung bindet Original, V1-Quittung, Positionen und historische Artikelversionen zusammen. Die neuen Tabellen sind im portablen Unternehmensexport berücksichtigt.

Neue Routen:

- `GET /business/adapters/:id/imports?offset=0&limit=20` – Historie mit höchstens 50 Einträgen je Seite.
- `GET /business/adapters/imports/:id` – bestehender vollständiger Run plus Original- und Annahmeinformationen.
- `GET /business/adapters/imports/:id/original` – tatsächliche Originalbytes; alte Imports liefern ausdrücklich 404.
- `POST /business/adapters/imports/:id/catalog-preview` – reine Leseoperation mit `{}` bei CSV beziehungsweise genau `price_scale`, `target_price`, `tax_rate` bei DATANORM. Antwort bindet Run, Originalhash, Preiszuordnung und vollständige Vorher-/Nachher-Snapshots an die tatsächliche `create`-/`update`-/`noop`-Entscheidung. Sie erzeugt keine Request-ID, Quittung oder Fachmutation und bleibt in fachlich deaktiviertem/globalem Lesemodus lesbar.

Der vorhandene Dateiimport akzeptiert zusätzlich optional `filename`. Seine 2-MiB-Rohdateigrenze bleibt bestehen. Beide HTTP-Transporte erlauben nur für die konkrete Import-Route einen begrenzten JSON-Envelope von 2.850.000 Bytes. Die Browserobergrenze von 32 MiB betrifft ausschließlich einzelne Katalog-Run-, Vorschau- und Annahmeantworten: Unicode-Escaping und Vorher-/Nachher-Snapshots können größer als die Originaldatei werden. Andere JSON-Routen behalten ihre bisherigen Grenzen.

## Prüfungen

- 99 Backendtests grün: 17 neue Fälle plus bestehende Adapter-, Schema-, API-, Organisations- und Exportregression.
- 2 echte lokale HTTP-Grenztests grün: genau 2 MiB, unveränderte Wiederholung/Originalbytes, 2 MiB + 1 Byte, Envelopegrenzen, doppelte Queryfelder und zusätzlicher Anfragekörper.
- 2 PostgreSQL-/MFA-/HTTP-Fälle grün mit vorhandener ausschließlich auf Loopback/Testdatenbank begrenzter Fixture: BLOB, Annahme, exakter Replay, Wiederöffnung, Runtime-ACL, Unveränderlichkeitstrigger und aktueller Rechteentzug. Kein bestehendes Restore-Ziel wurde verändert; dieser Lauf behauptet keinen zusätzlichen vollständigen Restoretest.
- 427 vollständige Node-Regressionsfälle grün, darunter 29 neue gezielte Katalogfälle. Davon sind 10 unabhängige Lifecyclefälle mit tatsächlichen UI-Callbacks und `OfficeApi`. Zwei Fälle wurden zusätzlich ohne den Schutz gegen Schreibrechte-/Modulverlust zuverlässig rot reproduziert. Fünf Fixtures stammen aus dem echten Backend.
- Ein vollständiger realer Chromium-/MFA-/HTTP-Ablauf grün: CSV-Fehler, unveränderte Lost-ACK-Wiederholung für Import und Annahme, Originaldownload, Einheit-/Preiswechsel, tatsächlicher V1-No-op, DATANORM-Zuordnung, Hintergrund mit später Antwort, frischer Schreibrechteentzug, 390-Pixel-Ansicht sowie genau 2 MiB mit 2.000 Unicode-Artikeln und Seitenwechsel.
- Der tatsächliche Chromiumlauf verwendet Passwort/MFA, einen temporären lokalen HTTP-Server und aktive Namespace-/PID-/Netzwerk-/Seccomp-Sandbox. Es wurden keine Tokens injiziert und keine externen Anbieter kontaktiert.

Evidenz: [Backendregression](evidence/catalog-originals-backend-2026-11-04.txt), [Browser/Node/HTTP/PG und Screenshots](evidence/catalog-browser-2026-11-04/). Die Browserquittungen enthalten synthetische IDs und Hashes der ursprünglichen Base64-Aufträge, keine Sitzungsgeheimnisse und keine großen Originaldateikopien.

## Integration

Die Änderungen sind uncommitted und unstaged. Beim Zusammenführen müssen die aktuellen Source4-/Opening-Erweiterungen im Hauptrepository erhalten bleiben, insbesondere die asynchrone `OfficeApi`-Receiptvalidierung samt erneuter Sitzungsprüfung.

Global gemeinsam berührte Dateien: `backend/business_api.py`, `backend/business_schema.py`, `backend/company_export_catalog.py`, `backend/online/web.py`, `backend/server.py`, `web/office/office.js`, `web/office/tests/e2e.cjs`, `.github/workflows/checks.yml`. Die Katalog-Ergänzungen müssen gezielt übernommen werden; diese Dateien dürfen nicht vollständig über jüngere Hauptrepositoryfassungen kopiert werden.

Die bereits durch Root in diesen Baum kopierten Änderungen an `backend/test_business_assistant.py` und `backend/test_business_assistant_speech_transport.py` gehören zu dessen unabhängiger Datumsfixturekorrektur, nicht zu diesem Katalogpaket. Es wurden keine zusätzlichen Abhängigkeiten oder Lockfileänderungen eingeführt.
