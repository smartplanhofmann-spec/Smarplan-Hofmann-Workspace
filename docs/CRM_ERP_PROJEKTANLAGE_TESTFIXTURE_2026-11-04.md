# Kunden-Projektanlage: alte Testfixture korrigiert – 04.11.2026

Die gemeinsame Flutter-Prüfung fand im bestehenden `customer_test.dart` eine
veraltete synthetische Erfolgsantwort: `new-project` ist keine gültige
32-stellige Projekt-ID. Der neue Client akzeptiert diese Antwort daher zu Recht
nicht als bestätigte Anlage; die bisherige Erwartung „2 Projekte“ wurde nicht
erreicht.

Ausschließlich die zwei IDs der erzeugten Fixture und ihrer Rückgabe wurden
auf denselben gültigen 32-Hex-Wert geändert. Alle Testkörper und Assertions
bleiben bytegleich. Keine Produktdatei wurde für diese Korrektur geändert.
Die Suche nach anderen direkten `/api/projects`-Anlagemocks fand keine weitere
vergleichbare ungültige Erfolgs-ID. Bestehende Kurz-IDs in reinen Lese-/Plan-
Fixtures werden dadurch nicht pauschal umgeschrieben.

**20/20 gezielte Fälle bestanden:** fünf bestehende Kundenfälle und die
15 neuen Projektanlage-/Wiederholungsfälle. Der Lauf verwendete ausdrücklich
`SMARTPLAN_TEST_PYTHON=/tmp/smartplan-backend-verified/bin/python`.
Fünf relevante Quelldateien waren vor/nach dem Lauf identisch. Die zusätzliche
Teilprüfung wird nicht als weitere eindeutige Gesamtsuite addiert.

[Manifest, alte Fixture, ursprünglicher Fehlerausschnitt und Rohlog](evidence/project-customer-fixture-supplement-2026-11-04/manifest.json)
bewahren die Änderung und deren Grenzen. Der Fehlerausschnitt stammt aus dem
zu diesem Zeitpunkt noch laufenden Gesamtlauf; er ist kein vollständiger
Gesamtsuitenbericht. Alte Navigations-/Wiederholungsmanifeste bleiben unverändert.
Keine Aussage zu weiteren Fehlern oder Python-Umgebungsreparaturen der
Gesamtprüfung, keine Server-/Geräteabnahme.
