# Kontrollierte Dateiübernahme

Stand: 03.11.2026. Implementierter lokaler Dateiworkflow für Kontakte, Projekte
und historische Dokumente. Quellenprüfung und Anbietergrenzen stehen im
[Architekturbericht](CRM_ERP_MIGRATION_ENTWURF.md).

## Was dieser Import übernimmt

**Smartplan-Dateiimport v1** ist ein eigenes, dokumentiertes Zuordnungsformat.
Die Auswahl „HERO“ oder „sevdesk“ vermerkt die vom Anwender erklärte Herkunft;
sie bestätigt weder einen API-Zugang noch die Kompatibilität mit sämtlichen
Exportversionen des Anbieters. Automatische Anbieterabrufe sind nicht enthalten.

Der Ablauf erhält hochgeladene Originaldateien bytegenau, ordnet Tabellenfelder
ausdrücklich zu und zeigt vor jeder Übernahme Fehler, Dublettenkandidaten,
Kunden-/Projektbeziehungen und deklarierte Beträge. Nach Bestätigung entstehen
kanonische Kontakte und Projekte sowie getrennte historische Dokumentarchive.
Bestehende Kontakte/Projekte werden beim Verknüpfen nicht überschrieben.

Eine historische Rechnung erhält **keine** neue Rechnungsnummer und erzeugt
keine Zahlungs-, offene-Posten-, Umsatzsteuer- oder EÜR-Buchung. Insbesondere
ist ihr deklarierter Bruttobetrag kein nachgewiesener offener Saldo und eine
Datei mit dem Namen „bezahlt“ kein Zahlungsnachweis. Finanzielle Eröffnung und
Übernahme offener Einzelposten benötigen einen gesonderten fachlichen Ablauf.

## Bedienablauf

1. Unter den Unternehmenseinstellungen die Dateiübernahme öffnen und ein Paket
   mit Quelle, eindeutigem Quellkonto, Bezeichnung, Umfang und optionalem
   vollständigem Exportzeitraum anlegen. Das Quellkonto ist eine bewusst
   gewählte Herkunftskennung, kein geprüftes Zugangskonto.
2. Originale hochladen. Dateiname, Dateityp, Byteanzahl und SHA-256 bleiben
   erhalten. Ein bestehender Name kann innerhalb des Pakets nicht überschrieben
   werden. Auch nicht interpretierte ZIP- oder andere Originaldateien lassen
   sich aufbewahren; sie werden nicht automatisch entpackt oder ausgeführt.
3. Für jede Datentabelle CSV oder JSON, Zeichensatz, Trennzeichen, Dezimalzeichen
   und Zielart wählen. Pflichtfelder müssen vorhandenen Quellspalten zugeordnet
   werden. Vorschau und Beispieldaten erleichtern diese Wahl. Eine geänderte
   Zuordnung erzeugt eine neue Version; Originaldateien bleiben unverändert.
4. Vorschau prüfen. Bei Dubletten ausdrücklich mit einem vorhandenen Kontakt/
   Projekt verknüpfen, bewusst neu anlegen oder mit Begründung ausschließen.
   Ein Kontakt mit identischem normalisierten Namen und identischer Adresse
   kann wegen des kanonischen Eindeutigkeitsschutzes nicht doppelt angelegt
   werden. Dokumente lassen sich ausschließen oder bewusst archivieren, nicht
   als fremde native Rechnung verknüpfen.
5. Fehler in einer ausgeschlossenen Zeile bleiben im Bericht sichtbar. Fehler
   anderer Zeilen, unaufgelöste Kunden-/Projektbezüge oder ungeprüfte Dubletten
   sperren die Übernahme. Fehlende Quellkennungen lassen sich nicht erraten;
   eine korrigierte Arbeitsdatei kann als weiteres Original mit anderer
   Bezeichnung hochgeladen und anstelle der bisherigen Tabelle zugeordnet werden.
6. Die gesamte gewählte Übernahme bestätigen. Sie bindet die konkrete
   Zuordnungsversion, Originalhashes, Dublettenkandidaten und heutigen Zielstände.
   Änderungen seit der Vorschau verlangen eine neue Prüfung. Bei einem Fehler
   wird die gesamte Transaktion zurückgerollt, einschließlich bereits angelegter
   Kontakte, Projekte, Archive, Verknüpfungen und Ergebnisquittung.
7. Ergebnisbericht gegen die Originale prüfen: Quellanzahl, Neuanlagen,
   Verknüpfungen, bereits übernommene Quellen, Ausschlüsse, Beziehungen und
   Summen. Anschließend den **deklarierten Umfang** mit einer Abgleichnotiz
   bestätigen. Das bestätigt keinen ungeprüften Gesamtbestand im Fremdsystem.

Eine verlorene Antwort wird mit dem unveränderten ursprünglichen Auftrag und
derselben Vorgangs-ID wiederholt. Eine bestätigte Übernahme wird dadurch nicht
erneut ausgeführt. Der Client prüft vorher heutige Sitzung, Eigentümerrolle und
Rechte. Unverändert übernommene Quellen späterer Pakete werden über System,
Quellkonto, Zielart und Quellkennung wiedererkannt. Geänderte Quellinhalte
überschreiben keinen früheren Import; sie erscheinen als Konflikt.

## Tabellenvertrag

CSV unterstützt explizit UTF-8 mit optionaler BOM oder Windows-1252 sowie
Semikolon, Komma oder Tabulator. Spaltennamen müssen eindeutig sein, jede Zeile
die gleiche Anzahl Spalten haben. JSON ist ein Array gleichförmiger Objekte mit
Textwerten oder `null`. JSON-Zahlen, verschachtelte Werte, doppelte Schlüssel
und wechselnde Spalten werden abgewiesen, damit insbesondere Geldwerte keine
Fließkommapräzision verlieren. Es werden keine Tabellenformeln ausgeführt.

| Zielart | Pflichtfelder | Weitere Felder |
|---|---|---|
| `contact` | `source_id`, `name` | `contact`, `email`, `phone`, `address`, `notes`, `person_name`, `person_email`, `person_phone` |
| `project` | `source_id`, `customer_source_id`, `name` | keine |
| `document` | `source_id`, `customer_source_id`, `kind`, `number`, `issue_date`, `original_filename` | `project_source_id`, `net`, `tax`, `gross`, `currency` |

Diese Namen sind **Smartplan-Zielfelder**, keine behaupteten Originalspalten von
HERO oder sevdesk. Quellspalten dürfen anders heißen und werden in der Oberfläche
explizit zugeordnet. Ansprechpartner werden als echter Kontaktuntereintrag
angelegt; ohne Namen lassen sich keine Kontaktdaten einer Person erfinden.
Dieses erste Tabellenprofil unterstützt einen Ansprechpartner pro Kontaktzeile.
Weitere Strukturen bleiben im Original erhalten und können später mit einem
erweiterten, überprüften Profil übernommen werden.

Dokumentarten: `invoice`, `credit_note`, `offer`, `order`, `delivery_note`, `other`.
Das Datum muss ISO `YYYY-MM-DD` sein. Beträge sind vorzeichenbehaftete
Dezimaltexte mit maximal zwei Nachkommastellen, dem ausdrücklich gewählten
Dezimalzeichen und ohne Tausendertrennzeichen. Währungen benötigen drei
Großbuchstaben; eine fehlende Währung wird nicht durch EUR ersetzt. Sind alle
drei Beträge vorhanden, müssen Netto plus Steuer genau Brutto ergeben.

Summen im API-Bericht sind ganze **Hundertstel der deklarierten Währung**;
`11900` bedeutet also beispielsweise `119,00 EUR`. Währungen werden getrennt
summiert, ohne Umrechnung. Zusätzlich liefern `net_exact`, `tax_exact` und
`gross_exact` feste Dezimaltexte wie `119.00`, damit auch Summen über der
Ganzzahlpräzision von JavaScript unverändert angezeigt werden können.
`missing` zählt Dokumentzeilen mit mindestens einem
fehlenden oder ungültigen Betrag. Die Summen sind ein Quellabgleich, keine
Buchhaltung. Für Fehlerzeilen bleiben Originalwerte und Fehlermeldungen erhalten.

`original_filename` muss genau eine hochgeladene PDF-/XML-/PNG-/JPEG-Datei
bezeichnen. PDF-Originale benötigen einen PDF-Dateikopf; ihre fachliche
Richtigkeit oder rechtliche Archivqualität wird damit nicht bescheinigt.
Downloads erfolgen als Anhang und werden nicht als aktive Inhalte ausgeführt.
Eine allgemeine Schadsoftwareprüfung oder OCR wird nicht behauptet.

Grenzen: maximal 2 MiB je Datei, 20 Dateien und 20 MiB je Paket, 1000 Zeilen über
alle zugeordneten Tabellen, höchstens 50 Quellspalten. Größere Exporte benötigen
kontrolliert getrennte Pakete mit stabilen Quellkennungen. Eine spätere Tabelle
darf auf bereits übernommene Kunden/Projekte desselben Quellkontos verweisen.

## API und Rechte

Alle Pfade stehen unter `/business` (online unter `/api/v1`, lokal unter `/api`).

| Pfad | Methode | Zweck |
|---|---|---|
| `/migrations` | GET, POST | Pakete lesen oder Herkunft/Umfang anlegen |
| `/migrations/options` | GET | Felder, Pflichtfelder und verfügbare Ziele |
| `/migrations/{id}` | GET | Originale, aktuelle Mappingversion, Status, Bericht |
| `/migrations/{id}/files` | POST | Originaldatei mit Dateiname, Typ und Base64-Bytes |
| `/migrations/{id}/files/{file}/inspect` | GET | Gewähltes Format/Encoding/Trennzeichen prüfen |
| `/migrations/{id}/files/{file}/original` | GET | Bytegenaues Original herunterladen |
| `/migrations/{id}/mapping` | POST | Neue explizite Tabellen-/Feld-/Dublettenentscheidung |
| `/migrations/{id}/preview` | GET | Aktuelle Prüfung ohne Anlage von Fachobjekten |
| `/migrations/{id}/apply` | POST | Gebundene Vorschau atomar übernehmen |
| `/migrations/{id}/report` | GET | Unveränderlichen Ergebnisbericht lesen |
| `/migrations/{id}/reconcile` | POST | Genau diesen Bericht mit Notiz bestätigen |

Sämtliche Importansichten sind wegen unzerlegter unternehmensweiter Originale
der aktuellen `owner`-Rolle vorbehalten und verlangen zusätzlich
`settings.manage`, `contacts.read`, `finance.read`, `documents.read`.
Schreiben benötigt aktives `business_migrations` und keinen Nur-Lese-Modus;
Übernahme zusätzlich `contacts.write` und `projects.manage`. Ausgewählte
Dokumente benötigen das aktive Dokumentmodul. Bereits quittierte Übernahmen
bleiben bei archivierten Kontakten lesbar; neue Verknüpfungen zu archivierten
Kontakten sind gesperrt. Offline-/Projektgerätetokens öffnen diesen Bereich nicht.

Uploadanfragen besitzen einen eigenen HTTP-Bodydeckel von 2.850.000 Bytes;
die Grenze anderer normaler Businessbefehle bleibt 1.000.000 Bytes. Auf beiden
Transporten werden zusätzliche GET-Bodies und POST-Querywerte abgewiesen.
Nachweislich nicht angenommene Konflikte besitzen `request_resolution=not_accepted`;
Kollisionen bereits belegter Vorgangs-IDs erhalten diese Aussage nicht.

## Persistenz, Datenschutz und Wiederherstellung

Die acht additiven Tabellen `business_migration_packages`, `files`, `mappings`,
`bindings`, `documents`, `applications`, `reconciliations` und `requests`
verwenden überall den Präfix `business_migration_`. Fachoriginale, Mappingversionen,
Herkunftsverknüpfungen und Ergebnisbelege sind nur einfügbar. SQLite-Guards
schützen auch vor ersetzenden Inserts; PostgreSQL-Runtime erhält ausschließlich
SELECT/INSERT, zusätzliche Trigger schützen migratorseitige Änderungen.

Der Integritätscheck bindet Originalbytes, Beziehungen, Archive, Berichtsanzahlen,
Quellsummen und Quittungen an ihre unveränderlichen Originalnachweise.
Backup/Restore erhält diese Daten. Es gibt keine automatisch weiterlaufenden
Provideraufträge und keine Wiederholung finanzieller Vorgänge.

Der Unternehmensexport erfasst Originale und sämtliche fachlichen Nachweise;
technische Requestquittungen sind ausgeschlossen. Originaldateien können
personenbezogene Daten auch bisher unzugeordneter Kunden enthalten. Deshalb
blockiert die automatische Kontaktlöschung bei vorhandenen unzerlegten
Importoriginalen bis zur gesonderten Vollständigkeits-/Bereinigungsprüfung.
Ein automatischer sicherer Löschprozess für beliebige Fremdexporte ist offen.

## Tatsächliche Prüfungen

| Prüfung | Ergebnis | Nachweis |
|---|---|---|
| Domäne + echter lokaler HTTP-Transport | 16/16 bestanden (14 Domäne, 2 Transport), 4,377 s | `backend/test_business_migrations.py`, `backend/test_business_migrations_transport.py`; `work/verification/migrations-domain-http.log` |
| PostgreSQL/MFA/HTTP, Runtime-/Migratorrechte, Konkurrenz, echter Backup/Restore | 2/2 bestanden, 8,279 s, keine Skips | `backend/online/test_business_migrations_pg.py`; `work/verification/migrations-pg.log` |

Der lokale HTTP-Test überträgt exakt 2 MiB als Original und prüft Downloadbytes,
Nonce-Wiederholung, dekodierte Größenüberschreitung und getrennte Bodygrenzen.
Der Online-Test überträgt ein Original größer als 1 MB durch die realen
Flask-/MFA-/PostgreSQL-Routen. Zwei getrennte Laufzeitverbindungen übernehmen
denselben Auftrag konkurrierend genau einmal. Der Restoretest stellt einen
echten Dump in eine getrennte Datenbank wieder her und vergleicht die acht
Tabellen einschließlich Originalen und Empfangsbelegen.

Alle Prüfungen verwenden synthetische Daten. Die ersten PG-Versuche deckten
falsche Testfixture-Zugriffe auf (`body` statt `data`, nicht vorhandene Hilfsnamen);
die korrigierten Tests liefen vollständig erfolgreich. Sie sind keine
Bestätigung eines produktiven Fremdexports oder Zugangs. Client-/Browsernachweise
stehen im ergänzenden [Clientbericht](CRM_ERP_DATEIIMPORT.md). Der letzte
zusätzliche Domänenfall prüft exakte Dezimaltexte auch oberhalb der
JavaScript-Ganzzahlpräzision; die PostgreSQL-Tabellenstruktur blieb dabei unverändert.
