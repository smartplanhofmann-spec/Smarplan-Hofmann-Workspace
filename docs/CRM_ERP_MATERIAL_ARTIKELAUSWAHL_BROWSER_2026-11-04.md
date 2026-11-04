# Materialauswahl im Browser ohne Finanzrechte

Stand: 4. November 2026. Ergänzung im isolierten Arbeitsbaum `smartplan-project-flow-20261104`.

## Befund und Änderung

Die Materialansicht lud ihre Artikelauswahl bisher ausschließlich über `/business/articles`, falls `finance.read` vorhanden war. Eine Lagerrolle ohne Finanzrechte erhielt deshalb leere Auswahllisten für Lagerbewegungen und Reservierungen, obwohl sie diese Vorgänge fachlich bedienen durfte.

Die Browseransicht verwendet bei der neuen Serverfunktion `inventory_article_refs` nun die dafür vorgesehenen preisfreien Referenzen:

```text
GET /api/v1/business/inventory/articles?project_id=<optional>&after=<optional>&limit=200
{items:[{id,revision,code,name,unit,active:true}],has_more,next_after}
```

`loadInventoryArticleRefs` in `web/office/office.js` lädt die Seiten mit fortlaufendem Cursor und erhält den Projektbezug. Der Helfer prüft die genaue Antwortform, aktive Artikel, Reihenfolge und vollständige Fortsetzungen. Eine Änderung des Arbeitsbereichs oder seiner Rechte verwirft eine noch laufende Auswahl. Es werden maximal 100 Seiten beziehungsweise 20.000 Einträge geladen; größere Bestände führen zu einer ausdrücklichen Meldung und werden nicht still abgeschnitten.

Lagerbewegungen und Reservierungen nutzen diese Referenzen. Der kaufmännische Artikelbereich und der berechtigte Einkaufs-/Preisfluss behalten ihre bisherigen Datenquellen. Bei älteren Servern ohne Featurekennung bleibt das bisherige Verhalten bestehen. Die bisherige Einschränkung älterer Server wird damit nicht als behoben behauptet.

## Abhängigkeit und Besitz

Die neue Backendroute stammt aus dem parallelen Release-Arbeitsbaum:

`/workspace/smartplan-project-release-readiness-20261104/backend/business_inventory.py`

SHA256: `b8353c608e207d7b260af44ea16624b95919ce7c6a4e694270df04a6510aef9b`.

Diese Datei wurde unverändert als Testabhängigkeit übernommen. Sie gehört zum Backend-Handoff des Release-Agenten und ist keine eigenständige Backendänderung dieses Browserpakets. Das Handoff dort dokumentiert 15 neue Domain-/MFA-HTTP-Tests und 40 vorhandene Regressionen. Hier werden diese Ergebnisse nicht als erneut selbst ausgeführte Tests gezählt.

Eigene Änderungen: Materialabschnitt und Helfer in `web/office/office.js`, `web/office/tests/inventory-article-refs.test.mjs`, `web/office/tests/inventory-article-refs-flow.cjs` sowie Registrierung des Testablaufs in `web/office/tests/e2e.cjs`.

## Prüfung

Der echte Browserablauf meldet einen Lagerbenutzer mit MFA an, der keine Finanzleserechte besitzt. Er prüft die preisfreien Antwortschlüssel, aktive Artikel ohne Lagerbestand sowie den Ausschluss inaktiver Artikel und Dienstleistungen. Danach reserviert er vorhandenes Material und entnimmt einen Teil davon über die realen Schnittstellen. Der Lauf bestätigt, dass `/api/v1/business/articles` nicht aufgerufen wurde. Desktop- und mobile Darstellung sind im Nachweis enthalten.

Die drei neuen Modulprüfungen decken mehrseitige Antworten, beschädigte Cursor/Antworten und einen während des Ladens wechselnden Arbeitsbereich ab. Zusammen mit vorhandenen Client-, Vertriebs-, Portal- und Einkaufsprüfungen bestanden **44 Node-Einzelfälle**.

Nachweise: `docs/evidence/project-customer-flow-2026-11-04/final-warehouse.txt`, `final-warehouse/`, `browser-unit-final.txt` und der abschließende gemeinsame Lauf `final-browser-runs.json`. Ein früherer Startversuch mit einer zusätzlichen JS-Datei wurde durch die bestehende statische Serverfreigabe abgewiesen; der Helfer wurde daraufhin in das bereits freigegebene `office.js` aufgenommen. Es wurde keine Serverfreigabe erweitert.

Der Nachweis betrifft Browser und echte lokale Testdaten. Die parallele native Anbindung sowie installierte Windows-/iPhone-Versionen werden gesondert geprüft und zusammengeführt.
