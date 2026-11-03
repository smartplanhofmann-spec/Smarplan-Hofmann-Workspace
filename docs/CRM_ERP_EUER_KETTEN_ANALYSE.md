# EÜR-Quellen: Abschlags-, kumulative und Schlussrechnungen

Stand: 03.11.2026. Die bisherige Folgeanalyse ist als lesender Quellenvalidator
und als durchgängige Erweiterung von Zahlungszuordnung, Beleganteilen,
Rückzahlungsursprüngen und EÜR implementiert. Die ursprünglichen Anforderungen
in `CRM_ERP_Gesamtziel.txt` bleiben unverändert.

## Verhalten

`accounting_invoice_sources.py` prüft ausschließlich finale EUR-Rechnungen der
Arten `advance_invoice`, `cumulative_invoice` und `final_invoice`. Bei einer Kette
mit 30,00 EUR Abschlag, kumulativ 70,00 EUR und abschließend 100,00 EUR sind die
zusätzlich berechneten Nettoanteile **30,00 / 40,00 / 30,00 EUR**. Bei 19 % USt
sind das zusammen **100,00 EUR netto, 19,00 EUR Steuer und 119,00 EUR brutto**.
Die vollen Vertragssummen werden nicht als neue Erlöse addiert. Ausschlaggebend
für die hier unterstützte Ist-Versteuerung sind die dokumentierten Zahlungen.

Die Prüfung umfasst:

* unveränderte Rechnungs-, PDF- und gegebenenfalls XML-Archive und vergebene
  Belegnummern;
* gleiche Unternehmens-, Kunden- und Projektzuordnung aller Vorgänger;
* höchstens 500 eindeutige Dokumente, keine Zyklen oder überlappenden
  Vorgängerzweige;
* volle Positionsberechnung gleich `contract_totals`, zusätzliche Beträge genau
  gleich voller Steuer-/Leistungsgruppe abzüglich unmittelbarer Vorgänger;
* exakte Centbeträge je Steuersatz, Steuerkategorie und Begründung sowie je
  Positionsart; Nullgruppen erzeugen keine positiven Anteile;
* unveränderte `deducts`-Beziehungen einschließlich archivierter Payload-Hashes.

Ein kumulativer Vorgänger trägt seine volle Vertragsbasis in den nächsten
Abzug ein. Seine früheren Abschläge zusätzlich abzuziehen wäre eine doppelte
Kürzung und wird nicht akzeptiert.

## Historie, Erstattungen und bestehende Daten

Die neue JSON-Beweisfamilie heißt `incremental_invoice_v1`. Nur für diese neuen
Quellen enthalten Gruppen- und Quellen-Hashes zusätzlich einen eingefrorenen
Kettenbeweis. Der normale `invoice`-Zweig behält seine bisherige Beweisform,
Gruppenidentität und gespeicherten Antworten. Es gibt keine neue Tabelle,
Modulregistrierung oder Umschreibung historischer Journale.

Die Erweiterung gilt gemeinsam für nachträgliche Zahlungszuordnung (A1),
ursprüngliche Beleganteile (C1), belegte Rückzahlungen (R1), wiederverwendete
Anteile (C2) und versionierte Rückzahlungen (R2). EÜR übernimmt deren belegte
Netto-/Steuerbeträge über die bereits vorhandenen Cash-Quellen.

Eine spätere Stornierung des Belegs oder eines Vorgängers sperrt neue positive
Einordnungen. Bereits dokumentierte Antworten und Ursprungsbeweise bleiben
unverändert abrufbar; eine reale Rückzahlung darf weiterhin ausdrücklich gegen
den früheren belegten Ursprung dokumentiert werden. Eine Gutschrift allein
schafft keine zusätzliche Zahlung oder Kapazität. Tatsächlich eingegangene
Überzahlungen dürfen als Bankvorgänge erfasst werden, aber nicht als zusätzliche
steuerliche Rechnungsanteile über die belegte Kapazität hinaus.

## Prüfungen

Die neue SQLite-Domainprüfung
[`test_business_accounting_invoice_chain.py`](../backend/test_business_accounting_invoice_chain.py)
verwendet nur für die Belegausstellung den vorhandenen ausdrücklich
synthetischen Ausstelleradapter. **9/9 Tests bestanden** (27,115 s). Sie prüft:

1. Abschlag und Schlussrechnung bis EÜR ohne Vertragsdoppelzählung;
2. dreistufige Rechnungskette mit Teilzahlungen und Restcents;
3. gemischte 19-/7-Prozent-Gruppen, Überzahlung und negative Restgruppen;
4. zunächst unzugeordnete Zahlung mit späterer Bindung ohne zweites CashEvent;
5. C1 → R1 → C2 → gemischtes R2 → C2 → EÜR;
6. spätere Vorbelegstornierung bei gleichbleibender historischer Antwort;
7. Überschneidungen, fremdes Projekt und manipulierte Beziehungen;
8. fehlendes Vorbelegarchiv;
9. zyklische Vorgänger trotz neu berechnetem Payload-Hash.

Der bestehende A1/C1/R1/C2/R2/EÜR-Regressionssatz lief mit **107/107 bestandenen
Tests** (56,918 s). Die getrennte PostgreSQL-Prüfung
[`test_business_accounting_invoice_chain_pg.py`](../backend/online/test_business_accounting_invoice_chain_pg.py)
verwendet den echten Aussteller, Runtime-Rollen, MFA/HTTP, zwei unabhängige
Verbindungen, erneute Migration und tatsächlichen Dump/Restore: **2/2 Tests
bestanden** (144,286 s). Alte normale C1-Beweiszeilen bleiben bytegleich; alle
ursprünglichen C1/R1/C2/R2/EÜR-Antworten werden nach Neustart und nach
abgeglichenem Restore exakt wiederholt.

Lokale Protokolle liegen unter `work/verification/invoice-chain-*.log` und
enthalten ausschließlich synthetische Fachdaten. Wiederholbare Domainprüfung:

```sh
PYTHONPATH=backend:backend/online backend/.venv/bin/python -m unittest test_business_accounting_invoice_chain -v
```

Die PostgreSQL-Prüfung benötigt wie die anderen Integrationsprüfungen eine
explizite isolierte Loopback-Testdatenbank (`SMARTPLAN_TEST_DSN`), verfügbare
PostgreSQL-Werkzeuge und passende Testrollen. Sie setzt das Schema dieser
Testdatenbank zurück; keine Produktionsdatenbank verwenden.

## Browser und Flutter

Beide Clients bieten jetzt die bestehende Server-Umwandlungskette an:
festgeschriebener Abschlag → kumulative Rechnung → weitere kumulative Rechnung
oder Schlussrechnung. Nicht festgeschriebene Kettenglieder müssen zuerst
fertiggestellt werden. Der Flutter-Vorbelegdialog bietet ausschließlich finale
Abschlags- und kumulative Rechnungen an, nicht normale oder Schlussrechnungen.
Er weist darauf hin, nur die unmittelbare neueste Vertragsbasis abzuziehen.

Browserentwürfe erhalten bei der Umwandlung den serverseitig ausgewählten
Vorbeleg und erhalten diese IDs auch bei einer Bearbeitung. Beide Detailseiten
zeigen volle Vertragsbruttosumme, bereits berechnete Vertragsbasis, Vorbelege
und zusätzlich berechneten Rechnungsbetrag getrennt. Sie erfinden keine
steuerliche Differenzberechnung im Client.

* Flutter: **30/30 Tests bestanden**, davon drei neue Ketten-Widgettests
  ([Quelle](../app/test/business_invoice_chain_test.dart)) und 27 bestehende
  Dokument-, Rechte- und Kalkulationstests. Die neuen Tests prüfen exakte
  Wiederholung nach verlorener Antwort, zulässige Vorbelegauswahl und
  verständliche Schlussrechnungsbeträge.
* Flutter-Analyse: **keine Befunde** (11,6 s).
* Chromium: **1/1 tatsächlicher MFA/HTTP-Ablauf bestanden**
  ([Quelle](../web/office/tests/invoice-chain-flow.cjs)); verlorene echte
  Conversion-Antwort, identischer Request/Beleg beim Wiederholen, Bearbeitung
  eines kumulativen Entwurfs bei unverändertem Vorbeleg, Vertrags-/Restanzeige,
  390-px-Ansicht ohne Seitenüberlauf. Namespace-, PID-, Netzwerk- und
  Seccomp-Sandbox waren aktiv.

Der Browserfall verwendet ausschließlich zuvor mit dem expliziten Testadapter
archivierte synthetische Rechnungen. Die laufende SQLite-Ausstellersperre wird
nicht verändert. Die echte Neuausstellung und das Festschreiben der gesamten
Rechnungskette sind im getrennten PostgreSQL-Test abgenommen.

Reproduzierbare Browserprüfung in `web/office` mit installiertem Playwright und
verfügbarem Chromium:

```sh
SMARTPLAN_BROWSER_WORKFLOW=invoice-chain node tests/e2e.cjs
```

Lokale Browsernachweise und Screenshots:
`work/verification/invoice-chain-browser.log` und
`work/verification/invoice-chain-browser/`; Flutterprotokolle:
`invoice-chain-flutter.log` und `invoice-chain-analyze.log` im selben
Verifikationsverzeichnis.

## Grenzen

Unterstützt sind die im bestehenden Aussteller archivierten positiven
EUR-Rechnungsketten und dokumentierten Zahlungs-/Rückzahlungsfälle. Das ist
keine automatische steuerliche Beurteilung aller Abschlags-, Gutschrift-,
Sonderleistungs- oder grenzüberschreitenden Fälle. Die bestehenden EÜR-Grenzen,
expliziten Profilentscheidungen und fachlichen Freigaben bleiben maßgeblich.
Die Domain- und PostgreSQL-Prüfung ersetzt keine neue Bedienabnahme der gesamten
Kette auf realen Windows- und iPhone-Geräten. Die bestehenden Komponenten- und
EÜR-Clients verwenden dieselben DTOs und benötigen dafür keine neue
Geldberechnung im Client.
