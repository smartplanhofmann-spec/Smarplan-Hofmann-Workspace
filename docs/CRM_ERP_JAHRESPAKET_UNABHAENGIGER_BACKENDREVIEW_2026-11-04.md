# Unabhängige Gegenprüfung des Jahrespakets V1

Die Prüfung betrifft den eingefrorenen Backendkandidaten
`e2f228173bb6d0eb3408d1cf48dadf0f7cbfd0e138c19ea3dc8ed8f89f13d069`
im Baum `/workspace/smartplan-year-review-export-20261104`. Keine Produktdatei,
kein Client und kein PostgreSQL-Bestand wurde durch diesen Reviewer geändert.
Der separate Jahresvortragadapter gehört nicht zu dieser V1-Prüfung.

Eigene tatsächliche Fälle stehen in
`backend/test_accounting_year_package_independent_review.py`.
Sie verwenden angenommene Originalquellen und EÜR-Vorgänge. Bei manipulierten
Archivkopien bleiben `report.json`, `postings.csv`, die ursprüngliche Export-
entscheidung einschließlich Annahmequittung und der originale Exporthash
nachweislich byte-/wertgleich. Lediglich Nachweisbestand und äußere Dateihashes
werden verändert. Ein bereits separat vertrauenswürdig bestätigter ZIP-Hash
würde diese Kopien weiterhin erkennen; geprüft wird die zusätzlich zugesagte
intrinsische Vollständigkeit der ursprünglichen Nachweisketten.

## Aktueller Abschluss nach ausdrücklicher Vertragsbegrenzung

Root hat nach den nachgewiesenen Grenzen einen engeren Vertrag bestätigt.
Das Jahrespaket behauptet **keine intrinsische Vollständigkeit sämtlicher
historischer Abhängigkeiten**. Der separat über die authentisierte Anwendung
bestätigte SHA-256 des gesamten ZIP ist zwingend. Ohne diesen oder mit einer
anderen Kennung scheitert die Prüfung. Manifest und Ergebnis tragen ausdrücklich
`intrinsic_dependency_closure:false`; das Manifest verlangt
`required_trust:"separately_authenticated_archive_sha256"`.

Der aktuelle unabhängige12er-Lauf ist vollständig grün:12/12 in16,350s,
`year-package-independent-authenticated-final-2026-11-04.log`.
Die ursprüngliche10er-Intrinsikprüfung ist bytegleich separat archiviert. Sie
wurde nicht rückwirkend als bestanden bezeichnet. Die neue Prüfung unterscheidet:

- unveränderte echte Pakete gegen den tatsächlich ursprünglichen Außenanker;
- manipulierte Kopien gegen exakt denselben ursprünglichen Außenanker;
- weiterhin ausdrücklich unterstützte innere Struktur-/Original-/Privacyprüfungen
  auch unter einem hypothetisch vom Angreifer mitgelieferten Ersatzhash;
- die verbleibende Herkunftsgrenze: übernimmt ein Empfänger stattdessen den vom
  Angreifer gelieferten Hash, kann SHA-256 dessen Paket nicht authentifizieren.
  Ein eigener tatsächlicher Fall bestätigt, dass dann intern konsistente, aber
  intrinsisch unvollständige Altquellen weiter lesbar sein können. Das Ergebnis
  weist entsprechend keine intrinsische Abhängigkeitsschließung aus.

Die beiden zuletzt gefundenen Umgehungen sind damit eine ausdrücklich dokumentierte
Grenze des engeren Formats, kein als gelöst behaupteter kryptografischer Beweis.
Der authentisierte Archivvergleich schützt das tatsächlich ausgegebene gesamte
Paket. Bestehende direkte Bindungen und private Grenzen werden zusätzlich geprüft.
Die Metadaten-API bleibt in ihrer16-Felder-Gestalt erhalten; die tatsächlichen
ZIPbytes und ihr SHA ändern sich beim nicht freigegebenen Kandidatennachtrag.

## Tatsächlich gefundene Lücken

Der erste Lauf gegen den unveränderten Kandidaten reproduzierte drei Annahmen
unvollständiger Pakete durch `verify()`:

1. Vorjahres-Vorsteuerentscheidung aus dem Paket einer wirklichen späteren
   Lieferantenzahlung entfernen. Der ursprüngliche EÜR-Zahlungsvorgang benötigt
   diese Entscheidung; sie beeinflusst jedoch nicht die Jahrespostings des
   exportierten Folgejahres.
2. Ursprüngliche Altpostenrevision1 entfernen, obwohl die unveränderte Revision2
   und ihre tatsächliche Zahlung enthalten bleiben.
3. Eine tatsächliche Vorjahres-Teilzahlung39,67 EUR samt ihrer Originaldatei
   entfernen, während der spätere unveränderte Restcentteil33,33 EUR netto und
   6,34 EUR Steuer enthalten bleibt.

Log `year-package-independent-first-2026-11-04.log`:3 rote Fälle in2,192s.
Der Owner ergänzte darauf ausschließlich den V1-Prüfer. Die unveränderten drei
Gegenfälle wurden zusammen mit fünf weiteren unabhängigen Fällen grün:
8/8 in10,692s (`year-package-independent-second-2026-11-04.log`).

Zwei unmittelbar daraus abgeleitete weitere Umgehungen wurden anschließend
gegen diesen ersten Fix bestätigt:

4. Die entfernte Vorjahres-Vorsteuerentscheidung lässt sich weiterhin verbergen,
   wenn zusätzlich ihr bloßer `prefix.target_hash`-Hinweis umbenannt wird.
   Der ursprüngliche `entry_hash` bleibt unverändert; der Hilfshinweis ist ohne
   enthaltene Entscheidung nicht intrinsisch an deren ursprünglichen Inhalt
   gebunden.
5. Tatsächlicher Ablauf: fehlerhafte ZahlungA39,67 → explizites VoidA → wirkliche
   ZahlungB39,67 → späterer RestC39,67. Entfernt man VoidA und B samt B-Original,
   kann die ungültige A die reine Betragsprüfung des unveränderten C erfüllen.
   Die tatsächlich zugrunde liegende ursprüngliche ZahlungB fehlt dennoch.

Log `year-package-independent-third-2026-11-04.log`:2 rote Fälle in1,777s.
Diese Befunde wurden unmittelbar dem Owner und Root gemeldet. Der damalige intrinsische10er-Vertrag wurde danach ausdrücklich begrenzt; siehe aktuellen Abschluss oben. Eine vollständige intrinsische Freigabe wird weiterhin nicht behauptet.

## Weitere tatsächlich geprüfte Grenzen

- Echte mehrstufige Abschlags-/Schlussrechnung: Vorgängeroriginal kann nicht
  herausgeschnitten werden.
- Aktuelle Verweigerung eines fremden, nicht eingeschlossenen Projekts blockiert
  den alten selektiven Export nicht. Verweigerung der tatsächlich enthaltenen
  Quelle blockiert ihn mit403; keine fremden Projekt-/Rechnungsdaten im ZIP.
- Echte Source5-Lohnkorrektur mit separaten laufenden und Bonuszahlungen wird
  ausschließlich als öffentliche Finanzprojektion exportiert. Mitarbeiter-,
  Lauf-, Anspruchs-, Zahlungs- und Originalkennungen bleiben privat. Ein
  nachträglich angehängtes privates Original wird abgewiesen.
- Echte jahresübergreifende Zehntageskorrektur benötigt ihren ursprünglichen
  Vorgang des anderen Jahres; ein bereits erzeugtes altes ZIP bleibt identisch.
- Dateianzahl-/Bytegrenzen, nicht freigegebene Kompression und ersetzte
  Originalbytes werden abgefangen. Größenablehnung erzeugt keine DB-Schreibwirkung.

Die Archivprüfung wird nicht als Herkunftssignatur, amtliche Steuerprüfung oder
private Lohnquellenprüfung ausgegeben. Die tatsächlichen Runtime-/Testhashes und
unveränderten roten Logs stehen unter
`docs/evidence/year-package-independent-2026-11-04/`.
Der erste geprüfte V1-Prüfer wurde zusätzlich aus der tatsächlichen eingefrorenen
ZIP-Fixture bytegleich unter `original-frozen-v1-checker.py` gesichert; SHA-256
`2137aaecccbc2e254a176c00c7aa53495edc4ce12c8d6191092c673bf3707980`.
