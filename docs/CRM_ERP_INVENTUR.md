# Physische Inventur

Stand: 03.11.2026. Bestandteil von R07.03. Implementierung:
[Server](../backend/business_inventory_counts.py),
[Browser](../web/office/inventory-counts.js),
[Flutter](../app/lib/business_inventory_counts.dart).

Im Materialbereich öffnet **Inventur öffnen** die Zählaufträge. Ein neuer Auftrag
legt einen Lagerort, einen tatsächlichen Zähltag und eine ausdrücklich ausgewählte
Artikelmenge fest. Die Auswahl umfasst bis zu 200 physische Artikel; es wird keine
Vollinventur aller übrigen Lagerorte oder Artikel behauptet. Sollmengen,
Reservierungen, Artikelfassungen und historische Lagerwerte werden dabei
eingefroren. Jede ausgewählte Position ist einschließlich tatsächlicher Nullmengen
auszufüllen. Abweichungen benötigen einen Grund. Korrigierte Zählungen erhalten
die vorangegangenen Fassungen.

Die Zählung allein verändert keine Bestände. Zur Freigabe sind aktuelle globale
Rechte `inventory.read`, `inventory.write`, `finance.read`, `finance.write` und
`finance.approve` erforderlich; Zählen benötigt nur die beiden Inventarrechte.
Die Vorschau zeigt Mengen- und Wertdifferenzen vor der verbindlichen Bestätigung.
Ohne Finanzleserecht werden Lagerwerte auch aus alten Fassungen und wiederholten
Antworten entfernt. Ein deaktivierter Materialbereich bleibt lesbar und sperrt
neue Zählungen und Freigaben.

Differenzen verwenden den historischen gewichteten Einstandswert. Bei vollständigem
Abgang wird der gesamte Restwert verbraucht, sodass kein Wert ohne Bestand
zurückbleibt. Mehrbestand ohne bisherigen Bestand erfordert einen ausdrücklich
bestätigten Einstandspreis, einschließlich eines tatsächlichen Nullpreises.
Bewertet wird reproduzierbar mit `Decimal` und vier Dezimalstellen im Lagerjournal.
Inventurdifferenzen sind weder Lieferantenwareneingänge noch Projektverbrauch und
werden nicht automatisch in EÜR oder Projektkosten gebucht. Folgende reguläre
Entnahmen verwenden den korrigierten Lagerbestand und dessen Wert.

Ändern sich relevante Bewegungen, Reservierungen, Artikelfassung oder Lagerort
nach Zählbeginn, wird die Freigabe gesperrt – auch bei zwischenzeitlichem Abgang
und Rückgang auf dieselbe Menge. Der Auftrag muss abgebrochen und neu gezählt
werden. Eine Zählung unter bereits reservierten Mengen wird ebenfalls nicht
freigegeben. Eine spätere Berichtigung einer freigegebenen Inventur beginnt als
neuer Auftrag mit demselben Zählumfang und explizitem Korrekturbezug.

Die additive Migration führt drei unveränderliche Tabellen ein:
`business_inventory_count_events`, `business_inventory_count_requests` und
`business_inventory_adjustments`. Das bestehende Bewegungsschema und seine
zulässigen Bewegungsarten bleiben unverändert. Bestandsdifferenzen werden nach
einer dokumentierten Bewegungsnummer eingeordnet; die Integritätsprüfung spielt
beide Journale in dieser Reihenfolge ab und prüft Zählfassungen, Bewertungsgrundlage,
Freigaben und exakte Differenzen. Laufzeitrollen können diese Einträge nicht
ändern oder entfernen. Es werden keine Stammdaten im Anfragepfad migriert.

Die API verwendet `/inventory/counts`, `/inventory/count-sources`, historische
Fassungen über `/inventory/counts/{id}?revision=…`, `/history` und die getrennten
Aktionen `/count`, `/preview`, `/approve`, `/cancel`. Bei einer verlorenen
Erfolgsantwort behalten beide Clients den ursprünglichen Auftrag einschließlich
Vorgangs-ID. Vor einer Wiederholung prüfen sie Rechte und Objekt erneut; eine
bereits fortgeschriebene Inventurversion führt nicht zur Erzeugung eines neuen
Freigabeauftrags. Der Server quittiert den ursprünglichen unveränderten Vorgang.

## Nachweise

- [Domainfälle](../backend/test_business_inventory_counts.py): gewichtete Bewertung,
  Fehl-/Mehr-/Nullbestand, Abbruch, Korrektur, Quellenänderung, Reservierung,
  Rechteentzug, unveränderte Wiederholung, Neustart, konkurrierende Freigaben und
  beschädigte Daten. Zusammen mit Lager- und Geräteherkunftsregressionen sowie
  [HTTP-Prüfung](../backend/online/test_business_inventory_counts_http.py):
  **44 Tests bestanden**, 7,783 s.
- [PostgreSQL](../backend/online/test_business_inventory_counts_pg.py): tatsächliche
  MFA/HTTP-Aufrufe, getrennte operative Rolle, beschränkte Datenbankrechte,
  Neustart sowie echter `pg_dump`/Restore mit alten Fassungen und Quittungen:
  **1 durchgängiger Test bestanden**, 4,112 s. Die zusätzliche deterministische
  Bewertungsprüfung wurde danach durch die 44 Domain-/HTTP-Tests bestätigt.
- [Browserverträge](../web/office/tests/inventory-counts.test.mjs): **6 Tests
  bestanden**, darunter verlorene Antwort, Rechteentzug vor erneutem POST und
  identische Wiederholung.
- [Chromium-Ablauf](../web/office/tests/inventory-counts-flow.cjs): **1 tatsächlicher
  Ablauf bestanden**. Zählung 10 → 8 bei 2 EUR Einstand führt zu 8 Einheiten und
  16 EUR Lagerwert; verlorene Freigabeantwort erzeugt genau eine Differenz.
  Historische Fassungen sind lesbar und nicht editierbar; Desktop- und
  390-Pixel-Mobilansicht wurden geprüft. Namespace-, PID-, Netzwerk- und
  Seccomp-Sandbox blieben aktiv.
- [Flutter](../app/test/business_inventory_counts_test.dart): **4 Tests bestanden**,
  gezielte Mengen-,
  Archiv-, Wiederholungs- und tatsächliche Widgetabläufe einschließlich
  Freigabevorschau und Rechteentzug.

Alle Geschäftsdaten in diesen Prüfungen sind synthetisch. Reale Bestandszählung,
Bewertungsprüfung, Zielgeräteabnahme und betriebliche Inventurverantwortung bleiben
Aufgaben des konkreten Betriebs. Die Funktion ist kein Nachweis einer vollständigen
Produkt- oder Steuerfreigabe.
