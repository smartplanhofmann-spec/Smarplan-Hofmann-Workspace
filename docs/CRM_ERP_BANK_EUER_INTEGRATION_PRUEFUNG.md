# Unabhängige Prüfung der Bank-/EÜR-Integration

Stand 03.11.2026. Geprüft wurden die additive Einbindung des Bankabgleichs in
EÜR-Perioden und den finanziellen Restore-Nachweis sowie ihre Auswirkungen auf
historische Quellen. Es ergab sich kein bestätigter Fehler in diesem
Integrationsumfang; Produktionscode musste nicht geändert werden.

## Geprüfter Vertrag

`business_schema.financial_accounting_horizon` erweitert den vorherigen
Gesamthorizont 9 um genau sieben Banktabellen zu Horizont 10. Bericht 11 bindet
exakte Tabellennamen, nichtnegative ganzzahlige Zeilenanzahlen und SHA-256.
Boolesche Werte werden nicht als Zähler oder Schemaversion akzeptiert.
Fehlende beziehungsweise zusätzliche Tabellen und ungültige Hashes werden
abgewiesen. Ein installierter Bankbereich ohne die erforderlichen vorherigen
Finanzmodule ist kein gültiger Mischstand.

Die Prüfung älterer Berichte bleibt rekursiv auf deren unverändertem Umfang.
Ein historischer Bericht 10 wird weiterhin unverändert gelesen, erfüllt aber
nicht den Pflichtumfang eines neuen Restores mit Bankmodul. Die bestehende
Weitergabe einer bereits bestätigten Quittung erfolgt vor der Prüfung des
heute für einen neuen Restore erforderlichen Schemas. Die vollständige
Operator-/Stillstandstrennung wurde zusätzlich im zusammenhängenden
[B/C-Dump/Restore](CRM_ERP_KUNDENAUFTRAG.md) tatsächlich geprüft.

Ein neuer EÜR-Periodenabschluss bindet für ausdrücklich eingerichtete,
zeitlich einschlägige Bankkonten aktuelle vollständige Abgleichberichte.
Fehlender oder nach einer Kontofassung veralteter Abgleich verhindert den
neuen Abschluss. Die Vorschau bindet die konkrete Berichtsfassung. Ein
früherer manueller Periodenabschluss wird durch eine spätere Bankeinrichtung
nicht rückwirkend umgeschrieben.

Historische Abschlüsse prüfen eingefrorene Banknachweise, ohne deren heutigen
Status als damaligen Zustand auszugeben. Allgemeine EÜR-Leser benötigen dafür
weder Bankleserechte noch Personalrechte. Neue Bankprüfhandlungen bleiben durch
ihre zusätzlichen Bankrechte geschützt. Es entstehen keine Banküberweisung und
keine weitere Geldbuchung aus dem Abgleich.

## Tatsächlich ausgeführte Nachweise

[test_business_bank_euer_review.py](../backend/test_business_bank_euer_review.py)
enthält zwei unabhängige Fälle mit echten SQLite-Fachquellen:

- Alter manueller Abschluss bleibt bytegleich wiederholbar; ein neuer
  Abschluss wird ohne vollständigen Bankbericht abgewiesen. Nach bestätigtem
  Nullaktivitätsauszug gelingt der Abschluss mit konkretem Berichtsnachweis.
  Nach Wiederöffnung und neuer Kontofassung ist der vorherige Abgleich für
  einen neuen Abschluss zu alt. Die historische EÜR bleibt für einen
  berechtigten Finanzleser ohne `bank.read` unverändert lesbar.
- Der vollständige Horizont wird geprüft, die ursprüngliche Datenstruktur
  bleibt dabei unverändert. Fehlende/zusätzliche Tabellen, boolesche/negative
  Zähler, boolesche Version, ungültiger Hash und vertauschte alte/neue
  Berichtsschemas werden jeweils abgewiesen.

Zusammen mit 18 aktualisierten Export-Domain-/HTTP-Fällen bestanden **20/20 in
6,953 s**, ohne Skip, auf `/tmp/smartplan-backend-verified/bin/python` mit den
geprüften Abhängigkeiten cryptography 50/Pillow 13. Befehl:

```sh
PYTHONPATH=backend:backend/online python -m unittest \
  test_business_bank_euer_review test_business_company_handover \
  online.test_company_handover_http -v
```

Protokoll: `work/verification/bank-euer-independent-and-catalog.log`.
Diese Teilmenge wird nicht zu anderen vollständigen Regressionszahlen addiert.
Bankdateiformate, Abgleichkapazitäten, Bank-Clients und externe Bankanbieter
sind Gegenstand eigener Nachweise; aus dieser Integrationsprüfung folgt keine
produktive Anbieteranbindung.
