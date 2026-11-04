# Native datierte Katalogpreise CSV-v2 — geprüfter Teilstand vom 04.11.2026

Arbeitsbaum: `/workspace/smartplan-catalog-prices-v2-20261104`. Dieser Bericht betrifft die native V2-Katalogstrecke. Er behauptet keine Fertigstellung des gesamten CRM/ERP und keine produktive Inbetriebnahme.

## Anforderungen und Umsetzung

- Eigene CSV-v2-Quellenverwaltung unter den Adaptern: Quelle mit belegter Referenz, tatsächliche Dateiauswahl bis 2 MiB, ausdrücklich benannte Originalrevision, paginierte Historie und Export der nach Länge/SHA256 geprüften Originalbytes.
- Der Server liefert die verbindliche Vorschau einschließlich Artikelbindung, Quellenversion, Originalhash, Vorher-/Nachher-Fakten und Korrekturbedarf. Die App prüft die vollständige kanonische Vorschau. Eine Korrektur erhält erst nach gesonderter Bestätigung eine neue Vorschau; die Annahme benötigt eine weitere ausdrückliche Bestätigung. Preisverlauf und begründete Rücknahme sind verfügbar.
- Ein Stichtag wird nicht aus der Geräteuhr übernommen. Der Nutzer wählt Datum und geeignete Quelle. Gleichnamige Quellen sind anhand ihrer belegten Referenz unterscheidbar. Nicht geeignete, noch nicht gültige, abgelaufene oder zurückgenommene Kandidaten werden erklärt. Vor Übernahme wird der gewählte Kandidat nochmals frisch abgefragt.
- Belegpositionen und Vertriebsangebote erhalten die ausdrückliche `sales_net`-Auswahl einschließlich Artikelidentität. Die konkrete Beleg-Umsatzsteuer kann separat entschieden werden, während die Quellbindung erhalten bleibt. Historische Positionen verlieren ihre Bindung nicht bei einer Mengen-/Steueränderung.
- Kalkulationen verwenden `purchase_net`: Root-Quelle als `source_price_selection`, Komponenten als `price_selection`. Bei einer Root-Quelle entfällt der manuelle Basiskostenbetrag. Die App rundet weder Rohbetrag noch Bezugsmenge; beispielsweise bleibt 1 EUR / 3 ST bis zur serverseitigen Rechnung erhalten.
- Bestellvorschläge verwenden ausdrückliche Einkaufspreise auch für Benutzer mit `inventory.write` ohne `finance.write`. Die Freigabe erhält die Auswahl. Bei datierten Bestellungen ist das tatsächlich bestätigte Bestelldatum zunächst leer und muss zum gewählten Preisstand passen. Tatsächliche Wareneingangskosten bleiben eine eigene explizite Angabe.
- Technische Stammpreiswerte verwalteter Artikel werden nicht als aktueller VK/EK angezeigt oder vorbefüllt. Ihre Stammdatenmaske führt datierte Preise separat. Die bestehende native Artikelmaske erzeugt keine Artikelkalkulation; Kalkulationsübernahme findet im Beleg statt.
- Quellen-/Import-/Annahme-/Rücknahmebefehle und tatsächlich datierte Dokument-/Bestellbefehle erhalten enge Session-Hooks für identisches Replay nach unklaren Antworten. Vor einem Replay werden aktuelle Rechte und Module geprüft. Daten, Quellenauswahl und `request_id` bleiben identisch. Der Dokumenteditor findet einen offenen datierten Auftrag nach Wiederöffnung über die Projekt-/Belegkennung wieder. Ungebundene alte Befehle behalten die bisherige Session-Regel.
- Eigene Dialoge und asynchrone Vorgänge werden bei Session-, Artikel-, Generation-, Rechte-, Modul- und Hintergrundwechsel invalidiert. Späte Dateien, Preise, Fehler und Speicherrückgaben können die geschlossene Auswahl nicht wiederherstellen oder in eine andere Ansicht navigieren.

## Prüfungen

Die fünf neuen Testdateien enthalten 70 gezielte Prüfungen. Der finale kombinierte Lauf mit 112 ausgewählten Bestandsfällen bestand vollständig: **182/182 grün**. Die statische Analyse aller 14 betroffenen Dart-Produkt-/Testdateien meldet **0 Befunde**. Dazu gehören tatsächliche Python-/HTTP-Aufrufe mit einem 2-MiB-Original und 2.000 Preiszeilen, Originalexport, gebundene Vorschau, unbestätigte Annahmen und ein tatsächlich erzeugtes Novemberangebot. Ein separater echter HTTP-Test prüft exakt 32 MiB und 32 MiB + 1 Byte an V2-Katalog-JSON-Pfaden sowie die unveränderte 20-MiB-Grenze gewöhnlicher Pfade. `/original` erhält keine angehobene JSON-Grenze.

Weitere Gegenfälle prüfen November/Dezember, Rohbetrag/Bezugsmenge, separate Belegsteuer, Bestellfreigabe und falsches tatsächliches Bestelldatum, sessiongebundenes Replay bei 0/403/404/409, Kontextwechsel während Dateiauswahl und Preisabfrage, verspätete Fehler/Erfolge sowie 390 Pixel Breite. Die JSON-Testfakten entstehen durch den echten Backendgenerator `app/test/fixtures/generate_catalog_prices_v2.py`; sie sind keine nachgezeichneten UI-Antworten.

Gefundene und behobene Probleme:

1. Nach dem Anlegen eines Bestellvorschlags wechselte die ausgewählte Kennung und machte den eigenen noch laufenden Kontext ungültig; dadurch fehlte das anschließende Neuladen. Der Kontext folgt nun nur der eigenen bestätigten Kennung.
2. Das leere, gesperrte Basiskostenfeld verlangte trotz ausdrücklicher Root-Quelle noch eine manuelle Eingabe. Die Pflicht entfällt ausschließlich bei dieser gebundenen Quelle. Ein roter Widgetbeleg ist aufbewahrt.
3. Auch bei global geöffnetem Dokumenteditor ohne vorgewähltes Projekt wird nach der ausdrücklichen Projektwahl ein bereits offener datierter Auftrag wiederhergestellt. Ein zusätzlicher roter Gegenfall belegte die zuvor fehlende Wiederherstellung; der Auftrag wird jetzt mit identischen Werten und Nonce wiederholt.
4. Der neue Dialogwächter erfasste zunächst auch alte undatierte Bestellbestätigungen. Ein Bestandstest erkannte die unerwünschte Änderung. Der zusätzliche Wächter ist jetzt auf datierte Bestellungen begrenzt.

Die konkreten Abschlussprotokolle sind `docs/evidence/catalog-prices-native-2026-11-04-regression-final.txt` und `docs/evidence/catalog-prices-native-2026-11-04-analyze-final.txt`. Das Handoffmanifest bindet sie an die Dateihashes. Es wurden keine externen Lieferanten kontaktiert. HTTP-Prüfungen verwenden ein synthetisches lokales Backend und den bereits vorhandenen vertrauenswürdigen Proxy-Testumschlag; sie sind kein neuer Produktions-TLS-/Gerätenachweis.

## Integration

Grundlage ist das exakte Freezeverzeichnis `work/verification/catalog-prices-v2-baseline.json`, nicht nur dessen historischer Git-HEAD. Die fünf zuvor übernommenen nativen V1-Dateien haben die eigene Grundlage `work/verification/catalog-prices-v2-native-v1-baseline.json` aus Commit `4c2f0086b4a9979b7cbe9d261fc22a97cd046913`. Der Handoff benennt pro Datei Basis- und Endhash. `business_session.dart` und `api.dart` sind gezielt gegen diese Grundlagen zu integrieren; später eingegangene Opening-/Source5-Änderungen dürfen nicht überschrieben werden.

`business_widgets.dart`, die native V1-Katalogseite und ihre V1-Testdatei blieben bytegleich. Backend-/Browser-/Paketlisten-/CI-Änderungen gehören zum separaten Parent-/Root-Paket. Keine Commits oder Staging durch diesen Teilauftrag.
