# Historische offene Posten in der nativen App

Stand 04.11.2026, isolierter Baum `smartplan-opening-items-20261104`.
Die native Implementierung des belegten Altpostenvertrags v1 ist abgeschlossen
und für den unabhängigen Review eingefroren. Integration in das Hauptprojekt
und unabhängige Abnahme erfolgen durch Root. Keine Backendänderung, kein Commit
und kein Kontakt zu produktiven Finanzdiensten durch diesen Clientauftrag.

Verbindlich sind [API](CRM_ERP_ALTPOSTEN_API.md), die tatsächlichen
Backendfixtures und die serverseitigen Annahmeprüfungen. Die bereits vorhandenen
Anfangsbestände/Liquidität, historischen Anlagen, EÜR-Journal und Bankabgleich
bleiben eigene Abläufe.

## Anforderungen und Umsetzung

| Anforderung | Umsetzung und konkreter Nachweis |
| --- | --- |
| Belegte externe offene Rechnung | Neue native Seite mit eigener unveränderlicher Rechnungs- und Stichtagsdatei, Fremdsystem/-kennung, Gegenpartei, ursprünglichen Tagen, ausdrücklich eingegebenen Netto-/Steuer-/Bruttowerten. Tatsächliche 390px-HTTP-Annahme für Kunden- und Lieferantenrechnung. |
| Keine erfundenen Altwerte | Keine Vorbelegung von Beträgen, Steuersatz, Daten, Zahlungs- oder Steuerhistorie. Leere Altraten erfordern ausdrückliche Bestätigung der vollständig unbezahlten Historie. Quelle und Umfang werden explizit bestätigt. |
| Frühere Teilzahlungen | Eigene Originalzuordnung, tatsächlicher alter Tag/Referenz und unveränderte historische Centwerte je Teilzahlung. Ursprüngliche 39,67 EUR (33,34 netto/6,33 Steuer) und neue 39,67/39,66 werden tatsächlich durchlaufen. Entfernen einer vorherigen Formularzeile erhält die sichtbaren Angaben der verbleibenden Zeile. |
| Bereits ausgeübte Vorsteuer | Lieferantenfall verlangt Betrag, Anspruchstag, Erklärungsmonat, tatsächlichen früheren Ausübungstag und Original. Die echte spätere 119-EUR-Zahlung ergibt zwei negative EÜR-Postings; keinen zweiten Vorsteuerabzug. |
| Vorschau und ausdrückliche Annahme | Geschlossene DTO-Formen und kanonische Hashes; Vorschau gehört exakt zum eingefrorenen Body und Originalvorgänger. Endquittung bindet Vorschau, Profil, Originale, Werte und Journalstand. |
| Originale | Tatsächlicher Dateiinhalt, MIME/Größe/Hash, Serverkennung und unveränderte Bytes beim Export geprüft. Servergrenzen: 1 Byte bis 5 MiB, Dateiname bis 200 Zeichen ohne Pfadtrenner. |
| Neue Restzahlungen | Wirklicher Zahlungstag, Betrag, gewähltes aktives EUR-Konto (bank/cash/payment_service), eigene Zahlungsdatei, Referenz und ausdrückliche Bestätigung. Keine Rechnung oder Geldbuchung durch die ursprüngliche Übernahme. |
| Korrektur/Aufhebung/History | Originalgebundene Berichtigung, gesonderte Aufhebung falscher Erfassung ohne behauptete Erstattung und unveränderliche Historie. Tatsächliche Ein-Cent-Korrektur der letzten Rate und anschließende Aufhebung im HTTP-Test. |
| EÜR | Neue Quelle `opening_item_cash` in bestehendem Quellen-/Journalablauf; ausdrückliche Kontenzuordnung. Tatsächliche Annahme, Kontoberichtigung und Gegenbuchung im nativen HTTP-Test. Zusatzvalidator prüft ausschließlich die neue Wirkung; alte Operationen/Exporte bleiben im bisherigen Vertrag. |
| Bank/Liquidität | Einstiege in vorhandene Seiten; echte unveränderte Zahlungsquelle im Liquiditäts-GET und 1.079,33 EUR aus separat belegtem 1.000-EUR-Anfangsbestand plus 79,33 EUR neuem Eingang. Bankseite tatsächlich geöffnet; die vollständige Bankzuordnung ist gesondert beim Backend/Browserowner geprüft. |
| Verlorene Antwort | Originalupload, Übernahmebestätigung und EÜR-Annahme verlieren im Test jeweils erst nach tatsächlicher Serverannahme ihre Antwort. Wiederholung sendet dieselbe Nonce und denselben eingefrorenen Auftrag. Fremde gültige Quittung lässt Auftrag offen; neuere Generation verändert Originaldaten nicht. |
| Frische Rechte und Kontext | Globales accounting.read + finance.read; Schreiben zusätzlich accounting.admin + accounting.prepare + finance.write, aktives Finanzmodul und serverseitiges can_prepare. Gehaltene Historie/Kontenliste/Preview, Sitzungsersatz, tatsächlicher Rechteentzug, geschlossener Wiederholungs-Preflight und Backgroundwechsel geprüft. Private Originale und ausgefüllte Entwürfe verschwinden; Wiederaufnahme verlangt ausdrückliches Neuladen. |

Neue technische Übernahmekennungen sind stabile generierte ASCII-Hexwerte;
fachliche Fremdkennungen werden separat erfasst. Vorhandene normalisierte
Serverkennungen werden unverändert gelesen und gesendet. Die App bildet keine
abweichende Unicode-Normalisierung nach.

Der begrenzte Fachumfang bleibt vollständig betriebliche gewöhnliche deutsche
EUR-Rechnungen mit genau einer 19- oder 7-Prozent-Gruppe bei bestätigter
Einzelunternehmen-/EÜR-/Ist-/Regelbesteuerung. Gemischte Steuern, Anlagen,
ungeklärte/teilweise alte Vorsteuer, Skonto, Rückzahlungen und andere Sonderfälle
werden nicht durch erfundene Ersatzwerte in diesen Vertrag gezwungen.

## Tests und Fortschritt

- **23/23 neue Fälle grün**, davon zwölf Contracttests, zehn Lifecycle-/Sitzungs-/Formularfälle und ein vollständiger tatsächlicher lokaler HTTP-Widgetablauf bei 390×844 Pixeln. Der HTTP-Ablauf umfasst beide Rechnungsrichtungen sowie Korrektur/Gegenbuchung.
- **106/106 bestehende Regressionen grün**: Accounting, EÜR einschließlich realem HTTP, Anfangsbestände einschließlich Lifecycle und realem HTTP, historische Anlagen einschließlich realem HTTP, Bankabgleich, Sessions und Profilrechte.
- **Dart Analyzer: keine Befunde** für die fünf Produktdateien und drei neuen Testdateien.
- Der vermutete Teilzahlungs-Zeilenverlust wurde mit einem neuen echten Widgetgegenfall gegen unveränderte Runtime widerlegt. Kein Produktfix dafür erforderlich; der Nachweis bleibt separat erhalten.
- Frühe Testiteration verlangte fälschlich einen bekannten Liquiditätsbestand ohne bestätigtes Bankoriginal. Die Teststrecke wurde um eine tatsächliche separate Originalannahme ergänzt; die fachlich richtige unbekannte Liquidität wurde nicht geändert.

Dauerhafte Logs, Basishashes, unveränderte Dateiprüfungen und finaler Umfang:
[evidence/opening-items-native-2026-11-04/manifest.json](evidence/opening-items-native-2026-11-04/manifest.json).

Die gemeinsame Session-Datei basiert auf dem dokumentierten Stand vor den
neueren Company-Events-Hooks. Deshalb den engen dokumentierten Integrationspatch
verwenden, statt andere später integrierte Session-Funktionen zu überschreiben.
Alle vorherigen Opening-/Historical-Assets-/Source5-Hooks bleiben unverändert.
