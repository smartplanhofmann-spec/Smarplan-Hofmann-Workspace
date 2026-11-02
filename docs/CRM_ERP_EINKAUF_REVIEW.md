# Einkauf, Lager und Wartung: unabhängiger Review

Stand: 02.11.2026. Geprüft wurde der neue Abschnitt `business_purchasing` auf
dem bestehenden Produktkern. Ergebnis: der unten beschriebene Backend-Ablauf
funktioniert mit synthetischen Daten. **Abnahmefall C ist damit nicht insgesamt
abgenommen.** Ergänzende UI-Prüfungen und ihre Grenzen stehen unten.

## Nachweis über die HTTP-Schnittstelle

Aus `/workspace/Smarplan-Hofmann-Workspace/backend` ausgeführt:

```sh
PYTHONPATH=.:online .venv/bin/python -m unittest online.test_purchasing_journey -v
```

Ergebnis nach Einbau der Schutztrigger: **4 Tests, 0,896 Sekunden, OK**.
Die Tests verwenden echte Flask-Handler, MFA, Berechtigungen und eine dauerhaft
gespeicherte SQLite-Testdatenbank. Sie rufen keine Lieferanten oder sonstigen
externen Dienste auf.

Der durchgehende Test erzeugt einen freigegebenen Bestellvorschlag, dokumentiert
die externe Bestellung und bucht Teil- und Restlieferung: 3 Stück zu 10,25 EUR
und 7 Stück zu 12,00 EUR ergeben 10 Stück mit 114,75 EUR Lagerwert. Die Zugänge
belasten die Projektkosten noch nicht. Eine spätere Artikelpreisänderung ändert
diesen Lagerwert nicht. Die Entnahme von 4 Stück ergibt 45,90 EUR Projektkosten
und lässt 6 Stück mit 68,85 EUR Lagerwert zurück.

Anschließend entstehen Gerät, Wartungsvertrag, Termin und unterschriebener
Servicebericht im selben Projekt. Der abgeschlossene Wartungseintrag verweist
auf das unveränderte PDF. Nach erneutem Öffnen der Datenbank stimmen
Bestellstatus, beide Wareneingänge, Bestände, Projektkosten, Wartungshistorie und
PDF-Bytes weiterhin überein. Wiederholte Requests erzeugen keine zusätzlichen
Wareneingänge, Entnahmen oder Wartungstermine.

Weitere HTTP-Fälle prüfen fehlende und entzogene Finanzrechte, Projektgrenzen,
Preisredaktion ohne Finanzleserecht, Referenzduplikate mit neuer Request-ID,
veraltete Eingangsrevisionen, atomare Ablehnung eines teilweise ungültigen
Wareneingangs sowie deaktiviertes Materialmodul: Schreiben wird mit 423
abgelehnt, berechtigte historische Lesezugriffe bleiben möglich.

## Review und Bestandserhalt

Zwei getrennte Codeprüfungen fanden im geprüften Umfang keinen weiteren
bestätigten hohen Fehler in Berechtigungen, Wiederholungsschutz, konkurrierenden
Eingängen oder Bewertung. Projekt- und zusätzliche Finanzrechte werden vor
einer gespeicherten Wiederholungsantwort erneut geprüft. Erwartete Revision,
normalisierte Belegreferenz, Eingangspositionen und Lagerbewegungen liegen in
derselben serialisierten Transaktion.

Zwei konkrete Befunde wurden behoben:

- Geänderte Artikel-Einheit oder Artikelart darf vorhandene Bestell- und
  Bestandsmengen nicht umdeuten. Die Artikelverwaltung sperrt solche Änderungen;
  der Wareneingang prüft zusätzlich alte inkonsistente Daten und lehnt sie ab.
- SQLite kann bei `INSERT OR REPLACE` gewöhnliche DELETE-Trigger umgehen.
  Zusätzliche INSERT-Schutztrigger verhindern Ersatz über sämtliche Primär-
  und eindeutigen Schlüssel der neuen unveränderlichen Tabellen.

Die vom Backend-Autor ergänzten Bestandserhalt- und Triggerfälle wurden
anschließend unabhängig ausgeführt:

```sh
PYTHONPATH=.:online .venv/bin/python -m unittest \
  test_business_purchasing.PurchasingMigrationTests.test_existing_schema7_orders_signed_reports_and_invoice_drafts_are_unchanged \
  test_business_purchasing.PurchasingTests.test_sqlite_replace_cannot_bypass_any_append_only_key -v
```

Ergebnis: **2 Tests, 0,354 Sekunden, OK**. Die additive Migration aus Schema 7
ohne Einkaufsmodul erhält sämtliche bereits vorhandenen Fachdatensätze,
signiertes Legacy-Protokoll einschließlich bytegleicher PDF, Artikel,
freigegebenen Bestellvorschlag und Rechnungsentwurf. Wiederholte Migration und
vollständiger Integritätscheck lassen diese Daten unverändert. Dies ist kein
Nachweis einer finalisierten Rechnungsfreigabe unter SQLite.

Ergänzend meldet der PostgreSQL-Prüfer **5 Tests, 7,450 Sekunden, OK, keine
übersprungenen Tests**. Aus dem Projektverzeichnis, mit zuvor gesetzter
synthetischer Testdatenbank-Konfiguration:

```sh
PYTHONPATH=backend PYTHONDONTWRITEBYTECODE=1 backend/.venv/bin/python -m unittest discover -s backend/online -p test_postgres_purchasing_integration.py -v
```

Der zusätzliche Migrationsfall erzeugt vor der Einkaufserweiterung unter der
eingeschränkten Laufzeitrolle eine tatsächlich finalisierte Rechnung mit PDF
(`einvoice_format=none`). Nach Migration und erneuter Rechtevergabe bleiben
alle alten Tabellen-Fingerprints außer dem Migrationsjournal sowie
Rechnungsobjekt, PDF-Bytes, Nummern und Audit unverändert. Dies belegt keine
XML-Konformität. Log: `work/verification/pg-test_postgres_purchasing_integration.log`.

## Gezielter UI-Review

Im Browser wurden zwei konkrete Bedienungsfehler korrigiert: Bestellvorschläge
können jetzt ohne Projekt entstehen; das Bestelldetail lädt die effektiven
Rechte seines Projekts statt globale Rechte für Freigabe, Wareneingang und
Kostenanzeige zu übernehmen. Mengen bleiben Dezimaltexte; der Browser prüft
vier Nachkommastellen mit Ganzzahlarithmetik. Bei unklarer Antwort und 423
bleiben Request-ID und ursprüngliche Nutzdaten für die Wiederholung erhalten.
Bestätigung und Status behaupten keinen Lieferantenversand.

Gemeldete Prüfergebnisse der jeweiligen UI-Verantwortlichen: Browser **52
Node-Tests** einschließlich 11 Einkaufsfällen; echter Browser-E2E **8
Workflows**, einschließlich Einkauf; Flutter **337 Tests** und Analyse ohne
Befund. Diese Läufe wurden nicht vom Verfasser dieses unabhängigen Reviews
erneut ausgeführt. Der Flutter-Code blendet bereits geladene Kosten bei einer
aktualisierten Finanzrechte-Entziehung aus und hält offene Eingaben für
unbestätigte Wiederholungen unverändert.

Die anschließende unabhängige Codeprüfung fand drei Flutter-Fehler, deren
Korrekturen im Code nachgeprüft wurden: Das globale Bestelldetail lädt jetzt
zusätzlich die Rechte seines Bestellprojekts. Aktionen und Kostenanzeige nutzen
diese Rechte; vor Änderungen werden sie erneut geladen. Ein bekannter
401/403/404-Lesefehler entfernt bereits geladene Details sofort. Einkaufsmengen
und Einstandspreise werden vor dem Senden auf zwölf Stellen vor und vier
Stellen nach dem Komma geprüft, ohne Rundung.

Nach unklarer Antwort hält die ursprüngliche Sitzung nun zusätzlich die
eingefrorenen Formulardaten. Dadurch lässt sich ein geschlossener Dialog mit
ursprünglichem Datum und Projekt wieder öffnen und mit derselben Request-ID
wiederholen. Auch ein während der Anfrage geschlossener Dialog erhält diesen
Wiederaufnahmeweg. Die Schlüssel trennen Vorgangsart, Bestellung und beim
Vorschlag auch den Projektkontext. Tokenwechsel, Sitzungsende und definitive
Serverantworten entfernen die Wiederholungsdaten.

Nach diesen Korrekturen meldet der Flutter-Verantwortliche **20 gezielte Tests
grün** (13 Einkaufs-Widgetfälle, ein Test gegen die echte HTTP-Schnittstelle,
sechs Sitzungstests) und Analyse ohne Befund. Logs:
`work/verification/purchasing-flutter-review-targeted.log` und
`work/verification/purchasing-flutter-review-analyze.log`.
Der abschließende Gesamtlauf auf unverändertem Code bestätigt **337 Tests,
1:40 Minuten, Exit 0, keine übersprungenen Tests**; Log:
`work/verification/purchasing-flutter-review-full.log`.

## Offene Grenzen

- Die Bestätigung dokumentiert eine bereits extern erteilte Bestellung.
  Lieferantenversand und externe Bestellübermittlung sind nicht implementiert.
- Gerät und Wartung gehören zum selben Projekt. Der Test hält Bestell- und
  Entnahme-ID in der Gerätenotiz fest; ein strukturierter Fremdschlüssel von
  Gerät zu Einkaufsposition beziehungsweise Lagerbewegung fehlt noch.
- Lieferantenretouren, Änderungen bestätigter Bestellungen und automatische
  Einheitenumrechnung sind nicht Bestandteil dieses Abschnitts.
- Ohne globales Finanzleserecht kann der Browser nur Artikel mit bisherigen
  Lagerbewegungen und bereits verwendete Vorschlagspositionen auswählen.
  Flutter verlangt für den Vorschlagseditor Finanzleserecht. Eine vollständige
  Einkaufsartikelsuche ohne Preisrecht fehlt; die bestehende redigierte
  Einzelcodesuche ist noch nicht in diese Editoren eingebunden.
- Der Wiederholungscache dieser Einkaufsdialoge liegt im Arbeitsspeicher der
  laufenden Sitzung. Eine dauerhafte Wiederaufnahme nach App- oder
  Browser-Neustart ist damit nicht nachgewiesen.
- Diese Prüfung ersetzt weder Produktionsbetrieb, einen unabhängigen
  Sicherheitstest noch die vollständigen übrigen Anforderungen aus
  `CRM_ERP_Gesamtziel.txt`.
