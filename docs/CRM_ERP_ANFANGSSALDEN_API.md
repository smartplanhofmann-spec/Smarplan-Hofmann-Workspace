# Belegte Geldkonto-Anfangsbestände – API und Rechenvertrag v1

Stand 04.11.2026. Additives Modul `business_accounting_openings`, Feature
`accounting_opening_balances`, Regel `account_opening_balances_v1`.
Implementierung im isolierten Entwicklungsbaum
`/workspace/smartplan-financial-opening-20261104`; Basis `2fdfa9f`.
Der Vertrag führt keine Zahlung, Buchung, Übermittlung oder Kontoeinlage aus.

## Bedeutung des Stichtags

Der Anfangsbestand gilt **unmittelbar vor der ersten Geldbewegung am bestätigten
`profile.bookkeeping_start`, 00:00 Uhr Europe/Berlin**. Alle tatsächlichen
Geldbewegungen dieses Kalendertags sind anschließend enthalten. Ein früherer
Geldfluss wird nicht nochmals addiert. Der angezeigte Bestandsstichtag `as_of`
ist ausdrücklich zu wählen und schließt die Bewegungen dieses Tages ein;
zukünftige Stichtage werden nicht als tatsächlicher Bestand ausgegeben.

Konten verwenden EUR. Beträge sind Zeichenketten mit exakt zwei Nachkommastellen,
optional negativ, ohne Plus-/Tausenderzeichen oder führende Nullen; `-0.00` ist
ungültig. Ein Bank-/Zahlungsdienstsaldo kann negativ sein. Ein gezählter
Kassenbestand darf nicht negativ sein. `0.00` ist nur mit derselben ausdrücklichen
Originalprüfung wie jeder andere Betrag zulässig. Ein fehlender Anfangsbestand
bleibt `null`, niemals automatisch null Euro.

Die gesetzlichen Bezugspunkte wurden am 04.11.2026 auf den offiziellen
Gesetze-im-Internet-Seiten gelesen: [EStG §11](https://www.gesetze-im-internet.de/estg/__11.html)
ordnet Einnahmen/Ausgaben ihrem tatsächlichen Zufluss/Abfluss zu;
[AO §146 Abs.1 und4](https://www.gesetze-im-internet.de/ao_1977/__146.html)
verlangt geordnete richtige Aufzeichnungen und erkennbare ursprüngliche Inhalte.
Der technische Übertrag eines vorhandenen Bestands wird deshalb als eigene
belegte Zustandsinformation gespeichert, ohne neue Einnahme, Ausgabe,
Umsatzsteuer, Vorsteuer oder Bankbewegung. Das ist kein vollständiger
steuerlicher Übernahmevertrag für alte Forderungen oder Anlagen.

## Rechte und Tabellen

Lesen benötigt die vorhandenen Rechte `accounting.read`, `finance.read` und
`bank.read`. Schreiben zusätzlich `accounting.admin`, `accounting.prepare`
und `finance.write`, aktiven Finanzbereich, aktuelle Runtime-/Restorefreigabe
und schreibfähigen Businessmodus. `can_prepare` aus dem Zustand ist zusätzlich
zu lokalen Rechteprüfungen zu beachten. Offline-Gerätescopes erhalten keinen
Zugang. Originale und Quittungen werden nicht bei einem Mitarbeiter oder
Projekt mit geringeren Rechten veröffentlicht.

Drei neue Tabellen speichern unveränderliche Originale, Ereignisse und
Annahmequittungen: `business_accounting_opening_originals`,
`business_accounting_opening_events`, `business_accounting_opening_requests`.
Kontoidentität, ursprüngliches Profil, Quellenbeleg, Vorschau und ursprünglicher
Befehl bleiben gebunden. Der Finanzhorizont erhält Version12 mit
`opening_balances`; die zugehörige Restore-Abnahme verwendet Version13.
Alte Horizonte/Berichte bleiben unter ihrer damaligen Version prüfbar.

## Routen

Alle folgenden Pfade hängen unter `/business/accounting/opening-balances`;
die native BusinessSession verwendet den relativen Teil ab `/accounting`.

| Methode/Pfad | Ergebnis |
| --- | --- |
| GET Basis | Zustand mit `schema_version`, `rule_version`, globaler `revision`/`state_hash`, `profile`, `profile_ref`, `accounts`, aktuellen `items`, `can_prepare`, `max_original_bytes`, `liquidity_path` und den beiden false-Wirkungsflags |
| GET `/sources?account_id=ID` | Exakte Kontofassung, aktueller Profilbezug, `opening_date`, passende `bank_statements`, gespeicherte `originals` und erforderlicher `original_evidence_type` |
| POST `/originals` | Original aufnehmen; Ergebnis enthält ID, Kontobindung, Dateimetadaten, SHA-256 und Downloadpfad |
| GET `/originals/ID` | Unveränderte Originalbytes als Attachment mit gespeichertem Dateinamen und Medientyp |
| POST `/preview` | Berechnete, quellengebundene Vorschau ohne Schreibwirkung |
| POST `/confirm` | Genau diese Vorschau annehmen und unveränderliche Fassung zurückgeben |
| GET `/accounts/ID/history` | `{schema_version:1, account_id, items:[...]}` mit allen Fassungen einschließlich Aufhebung |
| GET `/liquidity?as_of=YYYY-MM-DD` | Versionierte Sicht aus Anfangsbeständen und bereits vorhandenen tatsächlichen Geldquellen |

Die GET-Parameter und JSON-Felder sind exakt; unbekannte Felder, doppelte
JSON-Schlüssel, GET-Körper und zusätzliche POST-Queryparameter werden
abgewiesen. 201 gilt für Originalannahme und Bestätigung, 200 für Vorschau und
Lesen. Ein ungültiger Eingabevertrag liefert400, fehlende Rechte403,
unverfügbare Quellen404, Quellen-/Fassungs-/Restorekonflikte409,
deaktivierte Finanzen423. Nur ein nach fehlender Annahmequittung sicher nicht
angenommener Bestätigungskonflikt trägt `request_resolution: not_accepted`.

## Originale und Quellen

Originalannahme verlangt exakt:

```json
{
  "request_id": "32 lowercase hex",
  "account_id": "32 lowercase hex",
  "filename": "anfangsbestand.pdf",
  "media_type": "application/pdf",
  "content_base64": "..."
}
```

Zulässig sind PDF/PNG/JPEG mit 1 Byte bis einschließlich5MiB, einfachem
Dateinamen und vorhandener Format-/Größenprüfung. Die Uploadquittung bindet
unveränderte Bytes über SHA-256. Wiederholung desselben Originals pro Konto
liefert dieselbe Original-ID. Abweichende Metadaten desselben Originals
benötigen eine bewusste Klärung. Das Original wird nicht als Eingangsrechnung
angelegt und erzeugt keinen Vorsteuerklärfall.

`source` besitzt genau eine der folgenden Formen:

```json
{
  "kind": "bank_statement",
  "statement_id": "32 lowercase hex",
  "content_hash": "64 lowercase hex",
  "balance_side": "opening"
}
```

`balance_side: opening` verlangt `statement.period_from == opening_date`;
`closing` verlangt `statement.period_to + 1 Kalendertag == opening_date`.
Betrag und Konto müssen dem originalen Auszug exakt entsprechen. Die API
leitet Kandidaten und Betrag aus dem bestehenden Bankauszug ab. Die
Auszugsbewegungen werden dabei nicht erneut importiert.

```json
{
  "kind": "original",
  "original_id": "32 lowercase hex",
  "sha256": "64 lowercase hex",
  "evidence_type": "account_statement",
  "at_start_of_day": true
}
```

Für ein Kassenkonto lautet `evidence_type: cash_count`, sonst
`account_statement`. Betrag und Beginn werden anhand dieses Originals
ausdrücklich fachlich bestätigt. Das System behauptet keine OCR-Erkennung.
Ein vorhandener Bankauszugsanfang oder Vorperioden-Endsaldo am selben Stichtag
darf dem bestätigten Betrag nicht widersprechen.

## Vorschau, Bestätigung und Korrektur

Der Vorschauauftrag enthält exakt:

```text
expected_revision: aktuelle globale Journalrevision (int)
state_hash: aktueller globaler Journalzustand (SHA-256)
account_id: unveränderliche Geldkonto-ID
account_revision: ausdrücklich gewählte aktuelle Kontofassung (int)
profile_ref: {id, revision, entry_sha256}
status: active | void
opening_date: genau profile.bookkeeping_start
amount: signierter kanonischer EUR-Centtext
source: eine der beiden oben beschriebenen Quellen
reason: verpflichtender einzeiliger Prüf-/Korrekturgrund
```

`profile_ref` wird vom Zustand/Sources übernommen, nicht im Client geraten.
Die Vorschau wiederholt den Auftrag und ergänzt `schema_version:1`,
`rule_version`, vollständige bestätigte `account`-/`profile`-Snapshots,
`source_proof`, `previous_ref` (oder null), `preview_hash`,
`cash_flow_created:false`, `tax_postings_created:false`,
`balance_timing:start_of_day` und `timezone:Europe/Berlin`.

Die Bestätigung ergänzt denselben Auftrag um `request_id`, `preview_hash` und
`confirmation:true`. Sie erzeugt eine Fassung mit `id`, globaler `sequence`,
Kontofassung `revision`, globalem `previous_hash`, Ersteller/Zeitpunkt sowie
`content_hash`. Eine aktive Korrektur verwendet denselben Kontobezug mit
frisch geprüfter Quelle/Betrag und begründetem neuen Auftrag. Eine Aufhebung
verwendet `status:void` und muss `account_revision`, `profile_ref`,
`opening_date`, `amount` und `source` des zuvor aktiven Ereignisses unverändert
übernehmen. Nur Journalrevision/-hash und Grund ändern sich. Reaktivierung
benötigt wieder eine frische aktive Bestätigung.

Geschlossene EÜR-Perioden ab dem früheren oder neuen Anfangsdatum verhindern
eine neue Anfangsfassung. Ihre begründete Wiederöffnung erfolgt im bestehenden
EÜR-Verfahren. Eine bereits angenommene identische Anfrage bleibt bei
unverändert vorhandenen Originalen und frischen Rechten lesbar; Restore-/Modul-
und Runtimegates gelten weiterhin. Antwortverlust ist kein Anlass, Betrag,
Vorschau oder Request-ID automatisch zu ersetzen. Ein Profilwechsel lässt
alte Belege unverändert, macht den derzeitigen Bestand aber bis zu einer
ausdrücklichen neuen Bestätigung unbestätigt.

## Liquidität und EÜR-Anbindung

Die neue Antwort enthält `schema_version:1`, Regel, `as_of`, EUR,
`scope:recorded_movements`, Journalrevision/-hash, `accounts`,
`unresolved_cash_sources`, globale `issues`,
`complete_for_recorded_accounts`, `known_account_count`, `account_count`,
`known_balance_sum` und `balance_total`. Beide Kontenzahlen sind ganze Zahlen;
`known_balance_sum` bleibt bei null bestätigten Konten ebenfalls `null`.
`balance_total` bleibt bei fehlenden Anfangsbeständen, ungelösten tatsächlichen
Zahlungsquellen, Restoreprüfung oder widersprechenden Auszügen null.
Eine leere Kontomenge ist kein belegter Nullbestand.

Abgeleitete Summen (`inflows`, `outflows`, `calculated_balance`, `balance`,
`recorded_balance`, `known_balance_sum`, `balance_total`) sind kanonische
signierte Centtexte ohne die elfstellige Grenze einzelner Anfangseingaben.
Gültige Einzelbeträge können zusammen größere Beträge ergeben. Clients lesen
diese Summen exakt mit Ganzzahlen beliebiger Länge; sie kürzen sie weder auf
das Eingabelimit noch auf Fließkommagenauigkeit. Die gesonderten echten Fixtures
`accounting_openings_large_balances_2026.json` belegen positive und negative
zwölfstellige Bestände aus angenommenem Anfangswert und tatsächlichem Geldfluss.

Jede Kontozeile enthält `account`, `opening_ref`, `opening_date`,
`opening_balance`, `inflows`, `outflows`, `calculated_balance`, `balance`,
verwendete `movements`, `bank_connections` und `issues`. Ein diagnostisch
berechenbarer Betrag kann in `calculated_balance` stehen, obwohl `balance`
wegen einer widersprechenden Quelle null bleibt. Die getrennten Namen dürfen
im Client nicht als gleichwertige bestätigte Werte behandelt werden.

Die vier vorhandenen Geldklassen werden aus derselben EÜR-Quellensicht
übernommen: `cash_event`, `reviewed_external_cash`, `payroll_cash`, `travel_cash`.
Eine bloß hochgeladene Rechnung, ein Anlagebeleg oder ein neuer Anfangsbestand
erzeugen keine zusätzliche Bewegung. Noch nicht einem Geldkonto zugeordnete
tatsächliche Zahlungen bleiben in `unresolved_cash_sources` sichtbar.
Steuerliche Klassifizierung und tatsächlicher Geldfluss bleiben getrennt.

Bekannte Problemschlüssel sind `opening_balance_missing`,
`opening_profile_changed`, `as_of_before_opening`,
`bank_statement_connection_mismatch`, `cash_balance_negative`,
`cash_import_missing` und global
`restore_reconciliation_pending`. Der Client verwendet verständliche Texte.

Die bestehenden EÜR-Zustands- und Quellenrouten erhalten nur den additiven
Einstieg `opening_balances_path`, sofern die erforderlichen Rechte vorliegen.
Gespeicherte EÜR-Berichte/Exporte und deren frühere Summen bleiben unverändert.
Der alte Bewegungsbericht bleibt eine Bewegungssicht; die neue bestätigte
Bestandssicht wird separat geöffnet. Auch der bisherige CompanyOverview-Vertrag
mit `balance:null` bleibt unverändert; er darf einen berechtigten Einstieg zur
neuen Sicht zeigen. Eine vollständige bankfachliche Abstimmung oder
Vollständigkeit aller realen Konten wird aus `recorded_movements` nicht abgeleitet.

## Tatsächliche Fixtures und Prüfstand

`scripts/generate-accounting-opening-fixture.py` erzeugt beide identischen
Dateien `docs/fixtures/accounting_openings_2026.json` und
`app/test/fixtures/accounting_openings_2026.json` durch wirkliche isolierte
Domänenbefehle. Enthalten sind Originalannahme, Zustand/Quellen, Vorschau,
Bestätigung, Korrektur, Aufhebung, Historie, Liquidität/EÜR und ein gesonderter
Bankauszugsfall. Es sind ausschließlich synthetische Konten und Originale.

Erster korrigierter eigener Domänenlauf:16/16 Fälle,10,947s. Der erste Lauf
enthielt eine ungültige Testannahme zum Entzug von Ownerrechten; der korrigierte
Test nutzt einen tatsächlichen delegierten Benutzer. Zusätzlich prüfte der
erste Lauf wegen eines importierten Testklassennamens unbeabsichtigt18 bestehende
EÜR-Fälle, alle grün. Unabhängiger Review:7/7 nach zwei Produktkorrekturen
(Restorestatus und fehlende Originalannahmequittung). Vollständige Transport-,
PostgreSQL-, Client- und Gesamtregression werden gesondert protokolliert.

Der abschließende gemeinsame Domain-/Review-/EÜR-Lauf besteht aus 18 eigenen,
7 unabhängigen und 18 bestehenden EÜR-Fällen: **43/43 grün in19,374s**. Er prüft
zusätzlich einen erst später aufgenommenen widersprechenden Vorperioden-Endsaldo
und einen durch reale Auszahlungen rechnerisch negativen Kassenbestand. Der
vorherige Lauf enthielt einen Fehler im synthetischen Privatentnahme-Testbeleg;
dieser wurde ohne Produktänderung auf einen steuerneutralen Beleg korrigiert.
