# Belegte offene Altposten – additiver Vertrag 1

Stand: 04.11.2026. Arbeitsbaum: `/workspace/smartplan-opening-items-20261104`.
Dieser Kandidat ergänzt den vorhandenen Geld-/EÜR-Weg. Sein Backend ist mit SQLite,
echten lokalen/MFA-HTTP-Routen und PostgreSQL samt tatsächlichem Dump/Restore geprüft.
Die gemeinsame Abnahme beider Clients und die Integration in den Hauptbaum laufen noch.

## Bestandsaufnahme und abgegrenzter Umfang

Die drei ausführbaren Bestandsfälle in `test_accounting_opening_items_inventory.py`
zeigen: Eine vorhandene archivierte lokale Rechnung lässt sich nach dem Softwarebeginn
weiter bezahlen. Sie braucht keine Ersatzrechnung. Eine externe alte Lieferantenrechnung
kann zwar erfasst werden; der normale EÜR-Weg darf ihren alten Vorsteuerabzug aber
nicht auf einen neuen Anspruchstag verschieben. Eine unzugeordnete Zahlung besitzt
noch keine dokumentierte ursprüngliche Rechnungs-/Steuerbasis.

Der neue Import betrifft deshalb **externe, hier noch nicht erfasste offene Rechnungen**
eines fortgeführten Einzelunternehmens mit unveränderter EÜR, Regel- und Istbesteuerung.
Die amtlichen Grundlagen und unabhängig gerechneten Referenzen stehen in
[der Quellengegenprüfung](CRM_ERP_ALTPOSTEN_QUELLEN_GEGENPRUEFUNG_2026-11-04.md).

Unterstützt sind vollständig betriebliche, gewöhnliche inländische EUR-Rechnungen
mit genau einer 19- oder 7-Prozent-Gruppe. Die Originalsteuer entspricht der auf Cent
gerundeten Steuer auf das Gesamtnetto. Leistung, Rechnung und Rechnungseingang liegen
vor dem bestätigten `bookkeeping_start`, innerhalb von `vat_effective_from`.
`bookkeeping_start` ist hier der Softwarebeginn, kein fingierter Unternehmensbeginn.

- **Forderung:** Nur spätere tatsächliche Eingänge erzeugen Nettoerlös, vereinnahmte
  Umsatzsteuer und Ist-Umsatzsteuer auf den neu vereinnahmten Anteil.
- **Verbindlichkeit:** Der vollständige rechtmäßige Vorsteuerabzug muss bereits in
  einer Vorperiode vor dem Startmonat belegt sein. Spätere Lieferantenzahlungen
  erzeugen Nettoaufwand und gezahlte Vorsteuer in der EÜR; neue VAT-input-Buchung: null.
- **Noch nicht oder nur teilweise ausgeübter Alt-Vorsteueranspruch:** bewusst
  nicht freigegeben. Kein Rückfall auf einen geratenen neuen Abzug.
- **Übernahme:** Keine neue Rechnung, Zahlung, Einnahme, Ausgabe oder steuerliche
  Anmeldung. Bankanfangssalden bleiben eigene Bestände.

Unterjährige Umstiege behalten `partial_period_profile_coverage` im Jahresbericht.
Offene Altposten ersetzen keine bereits bezahlten Altjahresvorgänge. Die Referenzen
begründen keine ELSTER-Formularzuordnung 2026; diese bleibt gesondert offen.

## Identität, Originale und Beträge

`entity_key` ist eine unveränderliche, NFKC-normalisierte, kleingeschriebene externe
Kennung mit zusammengefassten Leerzeichen (maximal 200 Zeichen). Eine Zahlung benutzt
eine eigene 32-stellige Hexkennung. Die gesamte Folge hat einen globalen `sequence`,
einen Hashvorgänger und je Kennung eine lückenlose `revision`. Übernahmen und Zahlungen
belegen unterschiedliche Vorgänge; Kennungen können ihre Art nicht wechseln.

Zusätzlich werden System/externe Dokumentkennung, Richtung/Gegenpartei/Rechnungsnummer/
Rechnungsdatum sowie der Originalhash dauerhaft auf doppelte Übernahme geprüft.
Rechnung, Stichtagsaufstellung, alte Teilzahlungen und früherer Vorsteuerabzug sind
jeweils an akzeptierte Originale gebunden. Ein Dokument darf mehrere dieser
Nachweise enthalten; eine **neue Zahlung** benötigt einen eigenen Zahlungsnachweis.
Der Erstvertrag übernimmt vorhandene normale Finance-Belege oder lokale Rechnungen
nicht ein zweites Mal. Bereits gebundene Importoriginale können auch nicht später
als gewöhnlicher neuer Finance-Beleg oder als historische Anlage wiederverwendet werden.

Jeder alte Zahlungsanteil enthält Datum, Referenz, Brutto, Netto, Steuer und Original.
Die ursprünglichen Centwerte sind unveränderliche Eingaben. Die erste technische
Aufteilung benutzt das vorhandene kumulative Gesamtgruppenverfahren:
Steuerverbrauch bis zum kumulierten Brutto wird halbauf auf Cent gerundet; neue Teile
sind Differenzen der kumulierten Werte. Das ist ein ausdrücklicher Softwarevertrag,
keine behauptete gesetzliche Rundungspflicht. Widersprechende Altcentwerte führen
zur Klärungssperre. Keine stille Umrechnung, keine pauschale Mischung mehrerer Steuersätze.

Beispiel: Original 100/19/119; alt bezahlt 33,34/6,33/39,67. Neu 39,67 verbraucht
33,33/6,34; abschließend 39,66 verbraucht 33,33/6,33. Der neue Restverbrauch ist
66,66/12,67/79,33. Restnetto, Reststeuer und Restbrutto bleiben getrennt sichtbar.

## HTTP-Vertrag

Basis: `/business/accounting/open-items` (lokal `/api` davor, online `/api/v1`).
Alle Routen verlangen aktuelle globale `accounting.read`- und `finance.read`-Rechte.
Schreiben verlangt zusätzlich `accounting.admin`, `accounting.prepare`, `finance.write`
und die aktuelle Finanz-/Restorefreigabe. Offline-Schreiben bleibt gesperrt.

| Methode / Route | Inhalt |
| --- | --- |
| GET Basis | `schema_version=1`, Regelversion, Revision/Statehash, aktuelles Profil, aktuelle Altposten mit `remaining`, `remaining_net`, `remaining_tax`, aktuelle Zahlungen, Originalmetadaten, `can_prepare` |
| GET `/history?entity_key=…` | Unveränderliche Fassungen genau dieser Kennung |
| GET `/payments/{32hex}?revision={positiv}` | Originalgebundene Geld-/EÜR-Quelle genau dieser Zahlungsfassung |
| POST `/originals` | `request_id, entity_key, filename, media_type, content_base64`; PDF/PNG/JPEG bis 5 MiB; Originalbytes werden unverändert gespeichert |
| GET `/originals/{id}` | Geschützter Download, `no-store`, ursprünglicher Medien-/Dateiname und exakte Originalbytes |
| POST `/preview` | Genau `expected_revision, state_hash, entity_key, profile_ref, operation, payload, reason` |
| POST `/confirm` | Dieselben Felder plus `request_id, preview_hash, confirmation:true` |

`profile_ref` enthält `id, revision, entry_sha256`. `operation` ist `item` oder
`payment`. Zusätzliche Felder, doppelte JSON-Schlüssel, unerwartete Queryparameter
und GET-Bodies werden abgewiesen. Originalupload ist separat, keine implizite Annahme.
Bestätigung prüft Vorschau, aktuelle Rechte, Profil, Konto und Perioden erneut unter
dem gemeinsamen Finanzlock. Späte Fehler rollen Ereignis und Annahmequittung zurück.
Eine exakte Wiederholung liefert die **ursprüngliche** Annahme; geänderte Nutzlast
mit gleicher Vorgangskennung wird abgewiesen. Auch Wiederholung benötigt aktuelle
Rechte und Restorefreigabe, aber kein nachträgliches Umschreiben des alten Profils.

### Payload `item`

Genau folgende Felder:

`status, external_system, external_id, direction, counterparty_key, counterparty_name,
invoice_number, invoice_date, service_date, invoice_received_date, currency, rate,
category, net, tax, gross, prior_payments, invoice_proof, cutover_proof, history_through,
prior_input_vat, scope_confirmed`.

`status`: `active`/`void`; `direction`: `receivable`/`payable`; `currency`: `EUR`;
`rate`: `19`/`7`; sämtliche Geldwerte kanonische Zeichenfolgen mit zwei Nachkommastellen.
`category`: Forderung `sales`, Verbindlichkeit `materials`, `external_services`, `rent`,
`insurance`, `software` oder `other_expense`. `scope_confirmed:true` bestätigt die
oben genannten gewöhnlichen Fälle und unveränderte historische Methode; eine UI
muss diese Erklärung sichtbar nennen, nicht still vorbelegen.

Originalreferenz: `{original_id, sha256}`. `history_through` ist der Tag unmittelbar
vor dem Buchführungsbeginn. `prior_payments` ist eine chronologische Liste mit
`date, reference, gross, net, tax, proof`. Leere Liste bedeutet ausdrücklich nach
Stichtagsoriginal ungezahlter Ursprung, nicht unbekannte Zahlungen als Null.

`prior_input_vat`: bei Forderungen `null`, bei Verbindlichkeiten genau
`{amount, entitlement_date, declared_period, deducted_on, proof}`. Der vollständige Betrag muss
der Originalsteuer entsprechen, der Anspruchstag dem späteren Leistungs-/Eingangstag,
der erklärte Monat diesem Anspruchstag und einer Vorperiode vor dem Startmonat.
`deducted_on` belegt die tatsächliche frühere Ausübung vor dem Softwarebeginn;
der alte Erklärungszeitraum allein genügt nicht.
Strittige, korrigierte oder fehlende Anspruchsnachweise bleiben außerhalb.

### Payload `payment`

Genau `status, item_key, item_id, item_hash, date, amount, account_id, account_revision,
evidence_reference, proof`. Der unveränderte Altposten wird über ID/Hash gebunden.
`amount` ist positiv, Datum tatsächlich ab Beginn, nicht künftig und chronologisch
gegenüber früheren aktiven Teilzahlungen. Betrag überschreitet keinen Rest. Das
aktuelle aktive EUR-Konto wird geprüft. Originalhash und normalisierte Kontoreferenz
bleiben über alte Fassungen hinweg reserviert; gemeinsame Geldquellen können den
gleichen Nachweis nicht noch einmal verwenden.

`void` bezeichnet ausdrücklich die Aufhebung eines **falsch erfassten Nachweises**,
keine wirtschaftliche Rückzahlung. Aktive EÜR-Buchungen müssen zuerst gegengebucht,
aktive Bankzuordnungen aufgehoben werden. Spätere Teilzahlungen müssen vor Korrektur
einer früheren Centaufteilung korrigiert werden. Alte Ereignisse, Originale und
Quittungen bleiben erhalten. Neue korrekte Fassung benutzt dieselbe Zahlungskennung.
Ein Altposten mit aktiven Zahlungen kann keine geänderten Finanzwerte annehmen;
eine erneute Prüfung unveränderter Werte unter aktuellem Profil bleibt möglich.

## Tatsächliche Weiterverarbeitung

Die Quelle `opening_item_cash` enthält Zahlungskennung/-revision/-hash, Altpostenbezug,
Original, Datum, Netto/Steuer/Brutto, Richtung und genau eine aktive Geldbewegung
(bei aufgehobenem Nachweis keine). Sie fließt in den bestehenden EÜR-Quellenkatalog,
Bankkandidaten und die Liquidität mit den separat belegten Anfangssalden.

EÜR-Vorgang `opening_item_cash` erwartet genau
`payment_id, revision, source_hash, net_account, tax_account`. Die erste Bestätigung
bindet die Originalquelle; Gegenbuchung und Korrektur benutzen das vorhandene EÜR-Journal.
Nicht klassifizierte aktive Zahlungen bleiben sichtbar als
`opening_item_cash_classification_missing`. Geld verschwindet nicht nur deshalb,
weil die steuerliche Zuordnung noch fehlt. Geänderte Profile werden als offene
Prüfung gemeldet. Bestehende Export-/Periodenberichte werden nicht neu berechnet.

## Speicherung und Restore

Neue Familie (nur SELECT/INSERT, Update/Delete/Replace gesperrt):

- `business_accounting_open_item_originals`: `id, entity_key, filename, media_type,
  size, sha256, original, created_by, created_at`.
- `business_accounting_open_item_events`: `id, sequence, entity_key, revision,
  previous_hash, payload_json, content_hash, created_by, created_at`.
- `business_accounting_open_item_requests`: `user_id, request_id, operation,
  request_json, request_hash, result_json`.

Die vollständige Ereignisfolge wird aus Originalen und ursprünglichen Annahmebefehlen
reproduziert. Der Unternehmenexport enthält die Originaldateien und Ereignisse;
technische Annahmequittungen bleiben vom fachlichen Export ausgeschlossen. Vollständige
Backups behalten diese Quittungen für Wiederholung und Integritätsprüfung.

Finanzhorizont **14** ergänzt `opening_items` mit exakten Tabellenzahlen und Hash;
neuer Restorebericht **15** verlangt diesen Umfang. Historische Horizonte/Berichte
und bereits erteilte alte Freigabequittungen bleiben unverändert überprüfbar.

## Noch offene Teilanforderungen

Browser-/Native-Integration und gemeinsame Endabnahme dieses Kandidaten;
Überleitung schon vorhandener normaler Finance-Originale; nicht ausgeübte Altvorsteuer;
gemischte Steuergruppen oder andere nachgewiesene Rundungsverfahren; wirtschaftliche
Rückzahlungen/Gutschriften/Skonti, Aufrechnung, Anlagen, Privatanteile, Auslandsfälle,
§15a-/Methodenwechsel, Zehntagesfälle und vollständige Altjahreswerte. Diese Grenzen
dürfen weder die UI noch einen vollständigen Gesamtsoftware-Abschluss behaupten.
