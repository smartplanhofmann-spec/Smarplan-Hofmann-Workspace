# R08.03 – belegter Bankabgleich: Bestandsaufnahme und additiver Entwurf

Historischer Architekturentwurf vom 03.11.2026. Der Entwurf wurde bestätigt und umgesetzt; den aktuellen Umfang und die Entwicklungsabnahmen beschreibt [CRM_ERP_BANKABGLEICH.md](CRM_ERP_BANKABGLEICH.md). Keine Produktivabnahme. Das Gesamtziel wurde vollständig erneut gelesen; maßgeblich sind Abschnitte 8, 12, 13 und 15. Qonto ist als bestehendes Umfeld genannt, aber nicht verbindlich als Erstintegration ausgewählt. Dieser Entwurf behauptet deshalb weder ein Qonto-Dateiformat noch eine Bank-API oder bestehende Zugangsdaten.

## Tatsächlicher Bestand

`business_accounting.py` verwaltet versionierte EUR-Geldkonten (`bank`, `cash`, `payment_service`), belegte Zahlungseingänge/Erstattungen und tatsächliche Auszahlungen zu geprüften Eingangsbelegen. Die Originalquellen und Geldflüsse sind unveränderlich. Konten besitzen bisher keine Bankverbindung/IBAN.

`EuerAccounting.sources()['cash_movements']` ist die gemeinsame, nach tatsächlichen Quellenrechten geprüfte Geldflussprojektion. Sie enthält vorhandene `cash_event`-Bewegungen, aktuell wirksame `reviewed_external_cash`-Bewegungen und die gerade ergänzten öffentlichen `payroll_cash`-Bewegungen. Die reine Accounting-Eventliste wäre als Bankquelle unvollständig. Anfangssaldo und tatsächlicher Bankkontostand werden bisher ausdrücklich nicht behauptet.

Die EÜR-Periodenbestätigung besitzt bisher nur die ausdrückliche Benutzeraussage `attestation.bank_reconciled`; dahinter existiert noch kein eigener Bankabgleichnachweis. Bankdateien, unveränderliche Banktransaktionen, Zeilenzuordnungen und Saldoprüfungen fehlen.

Die abgestimmte Lohnzahlungsprojektion liefert je Batch/Geldkonto/Zahltag/Richtung aggregierte Bewegungen mit `id,date,account,direction,amount,categories`, öffentlichem `source_hash` und `source_path`. Sie enthält keine Namen, Steuer-IDs, Mitarbeiter-IDs oder privaten Originale. Der Bankabgleich greift ausschließlich auf diese öffentliche Projektion zu und erzeugt keine zweite Lohnzahlung.

## Verbindlich abgegrenzter erster Dateiweg

Ein explizit dokumentierter neutraler UTF-8-CSV-Vertrag `smartplan_bank_csv_v1` ermöglicht Entwicklung und Einsatz ohne erfundene Anbieteranbindung. Eine herunterladbare Vorlage und die Anzeige der erwarteten Spalten gehören dazu. Unterstützt werden EUR-Buchungen auf ausdrücklich zugeordneten Bankkonten; andere Währungen, Vormerkungen, aggregierte Fremdwährungszeilen und fehlende stabile Transaktions-IDs werden als nicht importierbar angezeigt.

Die Datei hat genau diese Spalten: `transaction_id,booking_date,value_date,amount,currency,counterparty,reference`. Trennzeichen wird ausdrücklich gewählt (Semikolon oder Komma); UTF-8-BOM ist zulässig. Datum ist ISO `YYYY-MM-DD`, Betrag ein vorzeichenbehafteter Cent-Dezimaltext ohne Exponent oder Tausenderseparator. Positive Beträge sind Eingänge, negative Ausgänge, Nullbuchungen werden abgewiesen. `transaction_id` stammt aus dem ursprünglichen Export bzw. einer dokumentierten Zuordnung und bleibt innerhalb des Geldkontos stabil. Die Anwendung erfindet sie nicht aus Betrag/Datum/Name, da zwei echte gleiche Zahlungen sonst unzulässig zusammenfallen könnten.

Der Benutzer ergänzt ausdrücklich: bereits vorhandenes EUR-Bankkonto, aktuelle Kontofassung, Bankidentität/IBAN, Auszugsreferenz, Zeitraum, Anfangs- und Endsaldo sowie Bestätigung, dass die Datei den erklärten Auszug vollständig wiedergibt. Anfänglicher sinnvoller Dateirahmen: höchstens 5 MiB/10.000 Zeilen. 0-Byte-Dateien, ungültige Zeilen, mehrdeutige Datums-/Betragsformate, doppelte IDs innerhalb der Datei, falsche Währung und `Anfangssaldo + Summe = Endsaldo`-Abweichungen verhindern den Abschluss. Fehlerbericht enthält Zeilennummer und fachlichen Grund; keine stillen ausgelassenen Buchungen.

Ein bestätigter Nullaktivitätsauszug darf nur den vollständigen CSV-Kopf enthalten, wenn Anfangs- und Endsaldo gleich sind. Er erzeugt keine künstliche Nullbuchung.

Originalbytes werden nach geprüfter Importbestätigung unverändert mit SHA-256 und Metadaten gespeichert. Eine Vorschau hat keine Geld- oder Steuerwirkung. Wiederholter Import derselben Datei/Referenz liefert einen nachvollziehbaren Dublettenbefund. Bereits bekannte kontogebundene Transaktions-IDs mit identischem normierten Inhalt werden nur erneut mit dem Auszug verknüpft; abweichender Inhalt derselben ID bleibt ein expliziter Konflikt. Überlappende Auszüge sind deshalb nachweisbar, ohne doppelte Banktransaktionen zu erzeugen.

Ein konkreter Bankexport kann später durch einen offiziell belegten Parser in denselben internen Vertrag übersetzt werden. CSV aus einem genannten Produkt wird ohne verifizierte Formatdokumentation nicht still als kompatibel erklärt.

## Konto und Rechte

Bankidentität wird additiv an ein vorhandenes `Accounting`-Geldkonto der Art `bank` und Währung EUR gebunden. Ein Konto mit importierten Auszügen wird nicht nachträglich auf eine andere IBAN umgebogen; für eine andere Bankverbindung wird ein neues Geldkonto angelegt. IBAN-Prüfung ist strukturelle Prüfziffernvalidierung, keine Kontoinhaber- oder Bankbestätigung.

Vorgeschlagene zusätzliche globale Fachrechte: `bank.read`, `bank.prepare`, `bank.admin`, ohne automatische Standardfreigabe für Nicht-Inhaber. Bankoriginale können in Klartext auch Gehaltszahlungen enthalten; dies ist bei der Rechtevergabe ausdrücklich sichtbar. `bank.read` allein erweitert keine Personalakten-/Lohnquellenrechte. Zusätzlich gelten vorhandene globale `accounting.read` und `finance.read`, für Mutationen `accounting.prepare`/`finance.write`, für Bankkontobindung `accounting.admin`/`bank.admin`. Zugeordnete kaufmännische Quellen verlangen weiterhin ihre tatsächlichen Projekt-/Belegrechte. Die Geschäftsführung erhält die Rechte nach dem bestehenden Eigentümermodell; delegierte Benutzer benötigen eine ausdrückliche Freigabe.

Schreiben benötigt aktives Finanzmodul, Schreibmodus und bestehende Financial-Release-/Runtime-Prüfung. Lesen/Export bleibt im Kompatibilitätsmodus nach aktuellen Rechten möglich. Rechte und tatsächliche Quellzugriffe werden bei Vorschau, Bestätigung, Download und jeder Wiederholung frisch geprüft; keine privaten Bankzeilen in globalen Übersichten ohne `bank.read`.

## Fachlicher Abgleich

Eine Banktransaktion wird ausdrücklich mit Teilbeträgen vorhandener Geldbewegungen verbunden. Eine Transaktion darf mehrere Geldbewegungen und eine Geldbewegung mehrere Transaktionen abdecken. Damit bleiben Teilzahlungen, Sammelzahlungen sowie die öffentliche Lohnaggregation darstellbar.

Es müssen dasselbe Geldkonto, dieselbe Währung und dieselbe Richtung gelten. Die Summe aktiver Zuordnungen überschreitet weder den absoluten Bankbetrag noch die aktuelle belegte Geldbewegung. Kandidaten sind Vorschläge nach belegbaren Kriterien, keine automatischen Bestätigungen. Gegenparteinamen oder Verwendungszwecke sind nicht vertrauenswürdige Eingaben und lösen keine Aktion aus.

Jede Zuordnung bindet genaue Bankzeile, ursprünglichen Dateinachweis und den aktuellen vollständigen öffentlichen Geldquellensnapshot inklusive Hash. Wurde eine Quelle korrigiert oder zurückgenommen, wird der Abgleich als veraltet ausgewiesen; alte Zuordnungen reservieren ihren Bezug bis zur ausdrücklichen Aufhebung/Korrektur. Geänderte Hashes werden nicht automatisch bestätigt und frühere Quittungen bleiben unverändert lesbar.

Bankbuchungstag, Wertstellung und bereits belegter Geldflusstag werden getrennt dargestellt. Abweichungen benötigen einen ausdrücklich begründeten zeitlichen Abgleich; die Bankzuordnung ändert niemals EÜR-Datum oder Zehntagesregel. Rücklastschriften und Erstattungen sind eigene entgegengesetzte Bewegungen mit vorhandenen Quellen, keine stillen negativen Änderungen an früheren Zahlungen.

Fehlende Buchungsquellen (z. B. noch nicht belegte Bankgebühren), Überzahlungen, unverknüpfte Bankbeträge, nicht abgeglichene Geldbewegungen, Quelländerungen, Zeitraumslücken und nicht geprüfte Datumsdifferenzen bleiben offen. Die Funktion erzeugt weder Zahlung noch Eingangsbeleg, Rechnungszuordnung, Lohnzahlung oder EÜR-Posting. Für eine fehlende Quelle führt sie zum vorhandenen belegten Erfassungsablauf; ein Bankbetrag allein ersetzt dessen fachliche Prüfung nicht.

Ein Bericht unterscheidet ausdrücklich:

1. Rechnerische Vollständigkeit des hochgeladenen Auszugs anhand der bestätigten Salden und Zeilen.
2. Vollständigkeit der bestätigten Bank-/Geldbewegungszuordnung im erklärten Konten-/Zeitraumumfang.
3. Eigenständige steuerliche Vollständigkeit der EÜR-Quellen.

Keiner dieser Zustände behauptet eine Bankverifikation oder automatische vollständige Unternehmensliquidität. Der nächste EÜR-Periodenabschluss kann einen unveränderlichen Banknachweis referenzieren; historische Abschlüsse mit bloßer manueller Prüfaussage bleiben unverändert lesbar. Der genaue additive Periodenvertrag wird mit dem EÜR-Verantwortlichen vor Umsetzung abgestimmt.

## Vorgeschlagenes Modul und Datenmodell

Separates Modul `business_bank_reconciliation`, Feature `bank_reconciliation`, getrennte Browser-/Flutter-Komponenten mit Einstieg unter Finanzen. Keine Änderung der bestehenden Accounting-Tabellen oder PayrollCash-Originale.

| Neue Tabelle | Inhalt |
|---|---|
| `business_bank_account_versions` | Versionierte Bankidentität mit gebundenem Accounting-Konto, IBAN, Hash/Vorgänger/Autor/Grund |
| `business_bank_statements` | Unveränderliche Originaldatei, Dateihash, geprüfter Parservertrag, Konto-/Saldo-/Zeitraummetadaten |
| `business_bank_transactions` | Einmalige kontogebundene externe Transaktions-ID, normierte Buchung, Ursprungs-/Inhaltshash |
| `business_bank_statement_lines` | Unveränderte Dateizeilennummer und Bezug zur kanonischen Banktransaktion |
| `business_bank_match_events` | Zusätzliche Zuordnungsfassungen mit vollständigen Bank-/Geldquellensnapshots, Teilbeträgen und Korrekturgrund |
| `business_bank_reconciliations` | Ausdrücklich bestätigter Bericht mit Konten-/Zeitraumumfang, Salden, offenen Posten und Quellmanifest; Vorlage für unveränderliche Exporte/Periodenbezug |
| `business_bank_requests` | Vorgangs-ID/Requesthash und ausschließlich referenzierende unveränderte Quittung |

Alle Fachfassungen und Originale append-only; exakte Nonce-Wiederholungen. Eine gemeinsame transaktionale Serialisierung schützt konkurrierende Importe, kontogebundene ID-Dubletten und die Kapazität beider Zuordnungsseiten. Schema, Runtime-Privilegien, Trigger, Restore-Validierung und Exportkatalog werden gemeinsam ergänzt. Die Tabelle der Originale enthält sensible Bankdaten; keine pauschale Aufbewahrungs- oder Löschzusage ohne dokumentierten Zweck.

## Vorgeschlagener API-Vertrag

- `GET/POST /bank/accounts`: vorhandene Bankbindungen lesen bzw. neue dokumentierte Fassung speichern.
- `POST /bank/import/preview`: Datei und explizite Metadaten prüfen; Liefert original_sha256, normalisierte Vorschau, Dubletten/Fehler und preview_hash. Keine dauerhafte Finanzmutation.
- `POST /bank/statements`: exakt dieselbe geprüfte Vorschau mit request_id/preview_hash/confirmation speichern; ein Original, einmalige Transaktionen und Zeilenbindungen.
- `GET /bank/statements`, `GET /bank/statements/{id}`, `GET /bank/statements/{id}/original`: paginierte Metadaten, Auszugszeilen/Abgleichstand und geprüftes Original.
- `GET /bank/transactions/{id}/candidates`: ausschließlich aktuelle zugängliche Geldbewegungen mit Quellenmanifest und verbleibenden Beträgen.
- `POST /bank/transactions/{id}/preview`, `POST /bank/transactions/{id}/matches`: vollständige explizite Zuordnungsliste bzw. begründete leere Liste zum Aufheben; aktuelle Revision und Vorschauhash sind Pflicht.
- `GET /bank/transactions/{id}/history`: unveränderte Fachfassungen.
- `POST /bank/reconciliations/preview`, `POST /bank/reconciliations`: ausdrücklicher Bericht für Konto/Auszug/Zeitraum mit vollständiger Quellenbindung. Unvollständige Berichte behalten offene Fälle und dürfen nicht als vollständig bestätigt werden.
- `GET /bank/reconciliations/{id}/{json|csv|pdf}`: exakt archivierte Berichtsfassung mit Hash-/Größenmanifest. Textwerte im CSV werden gegen Tabellenformeln geschützt.

Bezeichnungen und endgültige Spalten werden nach Architekturentscheidung fixiert und vor Implementierung der Clients an Root/Exportverantwortliche gemeldet. Kein Provideraufruf, keine Überweisung und kein amtlicher Versand gehört zu diesem Modul.

## Geplante Abnahmen

- Strikter Dateivertrag: UTF-8/CSV-Quoting, Geld-/Datumsgrenzen, Zeilen-/Dateigröße, unbekannte Spalten, ungültige Salden, doppelte/konfligierende IDs, wiederholte und überlappende Auszüge.
- Betragssplitting in beiden Richtungen, Sammelzahlung, Über-/Unterdeckung, Gegenrichtung, fremdes Geldkonto, zeitliche Abweichung, Quelländerung und ausdrückliche Korrektur.
- Unveränderte Accounting-/Finanz-/Payroll-/EÜR-Summen vor und nach Import/Zuordnung; keine zweite Zahlung.
- Aktuelle globale und tatsächliche Quellenrechte, sensible Originale, Rechteentzug vor verlorener Antwort/Wiederholung, Kompatibilitätsmodus, abgeschaltetes Finanzmodul und Wiederherstellungsfreigabe.
- PostgreSQL mit unabhängigen Verbindungen für gleichzeitige Import-/Zuordnungskapazität; echte Runtime-ACLs, MFA/HTTP und vollständiger Dump/Restore mit Original-/Berichtshashes.
- Browser und Flutter: Vorschau, Fehler, Original, bewusste Zuordnung, Historie, unvollständiger/vollständiger Bericht, Export sowie unveränderter Wiederholungsauftrag.

Echte externe Restpunkte: Auswahl des Bankanbieters und offiziell belegtes Export-/API-Format für dessen direkte Nutzung, notwendige produktive Zugänge und separate Produktivabnahme. Diese Punkte verhindern den neutralen belegten Datei-/Abgleichkern nicht, bleiben aber von dessen Entwicklungsabnahme getrennt.
