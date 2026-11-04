# Unabhängige Katalog-v2-Gegenprüfung — 04.11.2026

**Abgeschlossen: 12/12 unabhängige Fälle und insgesamt 103/103 Prüfungen erfolgreich.** Die beiden fachlichen Befunde mit drei roten Reproduktionen wurden durch den Katalogowner eng korrigiert und anschließend unabhängig erneut geprüft. Maßgeblicher Lauf: `integrated-final.txt`.

Diese Prüfung gehört ausschließlich zum isolierten Baum `/workspace/smartplan-catalog-prices-v2-20261104`. Der Reviewer verändert nur `backend/test_catalog_prices_independent_review.py` und diesen Nachweisordner. Produktkorrekturen erfolgen durch den Katalogowner. Die Grundlage ist `work/verification/catalog-prices-v2-baseline.json`, nicht ein angenommener Git-HEAD des gemeinsamen Integrationsbaums.

## Reproduzierte Befunde

1. **Zusätzliche Verwendung eines zurückgenommenen Stücklistenpreises:** Eine tatsächlich angenommene Komponente wurde nach Preisrücknahme unverändert weitergeführt. Das ist erlaubt. Dieselbe Komponente ließ sich aber zusätzlich kopieren, weil `component in previous` jedes weitere Vorkommen als historischen Bestand anerkannte. Der rote Gegenfall zeigt die Annahme einer zweiten, vorher nicht vorhandenen Position ohne neue Preiswahl. Die fachlich bestätigte Korrektur muss alte Vorkommen jeweils genau einmal erhalten, ohne legitime bereits ursprünglich mehrfach erfasste Komponenten pauschal zu verbieten.

2. **Ungeprüfte historische Artikelrevision bei Stücklisten:** Nach einer echten Leistungserfassung und einer späteren reinen Umbenennung wurde nur in der alten Artikelversion die Komponenten-Artikelrevision auf die nicht existierende Revision 999 gesetzt. Der Versionshash wurde neu berechnet. Alle für die Testmanipulation entfernten SQL-Guards wurden vor der Integritätsprüfung exakt wiederhergestellt. Trotzdem wurde das veränderte historische Original zunächst akzeptiert. Die intrinsische Prüfung muss die tatsächlich benannte ursprüngliche Artikelfassung beachten; heutige Artikel- oder Preisköpfe dürfen alte Nachweise nicht nachträglich invalidieren.

3. **Gleiche Lücke bei historischer Dokumentposition:** Derselbe gezielte Gegenfall mit der Artikelrevision einer alten Angebotsposition wurde ebenfalls akzeptiert. Auch hier waren alle SQL-Guards wiederhergestellt. Dieser Fall gehört fachlich zu Befund 2, betrifft aber den separaten Dokumentpfad und wird durch einen eigenen Test abgesichert.

Die roten Logs bleiben erhalten: `before-component-occurrence-fix.txt`, `before-component-identity-fix.txt`, `before-document-position-identity-fix.txt`. Die ersten beiden begleitenden JSON-Dateien halten den damaligen Produktquellhash fest. Diese Befunde entstanden aus tatsächlichen CSV-Originalen und Domainannahmen, nicht aus erfundenen Antworten.

## Unabhängige positive Grenzen

Die zwölf eigenen Tests erfassen zusätzlich unveränderte finale PDF-Bytes nach Preisrücknahme, ursprüngliche Quellen nach ausdrücklicher Artikelneubindung, gleiche/gefälschte Positionsidentitäten, neu gehashte andere Auswahlstichtage innerhalb eines an sich gültigen Preisfensters, getrennte Einkaufs-/Verkaufsrollen am Schalttag, bestätigte Bestellung nach Preisrücknahme, tatsächliche Zugangskosten statt Katalog-Neubewertung, stale Kalkulationsablehnung, legitime ursprüngliche doppelte Stücklistenpositionen und atomaren Abbruch einer CRM-Angebotsübernahme mit erstem gültigem und zweitem zurückgenommenem Preis.

Die Preisrücknahme verändert keine frühere Originalauswahl. Neue Verwendungen müssen den aktuellen Kopf und die aktuelle Bindung ausdrücklich auswählen. Bestellquittungen behalten bei Replay die ursprüngliche bestätigte Antwort; der heutige Wareneingangsstatus wird separat gelesen. Der Bestandsbericht zeigt Centbeträge, während das Lagerjournal tatsächliche Zugangskosten mit vier Nachkommastellen führt.

## Ausführung

Python: `/tmp/smartplan-backend-verified/bin/python`, Arbeitsverzeichnis `backend`. Die unabhängige Prüfung führt echte lokale SQLite-Domänenvorgänge ohne Produktivkontakte aus. HTTP-/MFA-/PostgreSQL-/Browser-/Native-Abnahmen anderer Owner werden damit nicht als eigene Prüfungen behauptet. Das abschließende Manifest hält Produkt- und Testhashes, konkrete Befehle, Prüfzahlen und den Stand nach den koordinierten Korrekturen fest.

Die Korrektur erhält jedes ursprünglich vorhandene Komponenten-Vorkommen höchstens einmal. Ein neuer intrinsischer Helper prüft bei datierten Dokumentpositionen und Komponenten die konkret benannte ursprüngliche Artikelfassung samt gespeicherter Prüfsumme, damaligem Aktivstatus und Einheit; Komponenten außerdem Name und Art. Die freie Dokumentbeschreibung und ausdrückliche Belegsteuer bleiben erhalten. Keine aktuelle Kopfversion wird für historische Originale verlangt.
