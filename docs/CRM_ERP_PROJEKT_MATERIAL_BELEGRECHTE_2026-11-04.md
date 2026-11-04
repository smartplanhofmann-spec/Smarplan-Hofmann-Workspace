# Materialreferenzen und Belegbearbeitung für den Projektbetrieb

Stand: 4. November 2026. Isolierte Ergänzung auf `c875ea5a221e5d38533bb7d50a1d96b9c455d22f`; keine Änderung am Hauptverzeichnis, kein Push, kein Build auf Windows/macOS und keine Bereitstellung.

## Anforderungen und Ergebnis

| Anforderung | Umsetzung |
| --- | --- |
| Lagerrollen können Material in Bewegung/Reservierung auswählen, ohne Preise lesen zu dürfen. | Additive Capability `inventory_article_refs`; `GET /api/v1/business/inventory/articles` liefert ausschließlich `id`, `revision`, `code`, `name`, `unit`, `active`. Nur aktive Material-/Maschinenartikel, aktuelle `inventory.read`- und Projektprüfung, keine neuen Rechte. |
| Vollständige, zuverlässige native Materialauswahl. | Native Auswahl lädt ID-seitige Seiten bis zum expliziten Ende, prüft Reihenfolge/Duplikate/Cursor und verwirft verspätete Antworten bei Rechte-/Kontextwechsel. Bis zu 20.000 Einträge, darüber ausdrücklicher Fehler statt Teilanzeige. Kein Rückgriff auf die Finanzartikelroute. Alte Server zeigen einen Aktualisierungshinweis. |
| Offene Belegpositionsdialoge halten aktuelle Rechte ein. | Lesen benötigt `finance.read`; Schreiben benötigt bei Belegen `finance.write`, bei Vorlagen `settings.manage`. Aktuelle Rechte werden sowohl vom Dialog als auch vor der Positionsübernahme geprüft; Leseentzug entfernt Eingabedaten. Der Hauptspeicherknopf folgt ebenfalls diesen Rechten. |
| Unterstützte Stornoart statt ungültigem `cancellation`. | Native Anzeige verwendet `credit_note`. Ein Stornoentwurf entsteht weiterhin ausschließlich aus einer finalen Rechnung, wie vom Backend verlangt. Die allgemeine Neubelegauswahl bietet keine unzulässige freie Stornoerstellung an. |
| Vorhandene Stornoentwürfe sind bearbeitbar. | Eigene Ansicht für Titel, Datum, Stornogrund und Begleittexte. Empfänger, Quelle, Positionen und Beträge bleiben gebunden. Die Update-Nutzlast enthält nur die vom Backend zugelassenen Metadaten und Revision. |
| Unbestätigte Stornobearbeitung bleibt derselbe Vorgang. | Stabile ID `credit-note-document-<beleg-id>` in der vorhandenen authentisierten Sitzung. Beim erneuten Öffnen werden nur die offenen Metadaten übernommen; Originalpositionen bleiben sichtbar. Wiederholung verwendet denselben Request und unveränderte Nutzlast. |
| Bestehende Preisbindungen und Vorlagen bleiben erhalten. | Datierte Katalogpreisflüsse und Quellbindungen bleiben bestehen. Bestehende echte Belegarten bleiben unveränderlich; Vorlagen behalten ihre editierbare Art. |

## Validierung

Backend: **15 neue Prüfungen** bestanden (9 Domain, 6 echte Flask-Anfragen mit Passwort/MFA), dazu **40 bestehende Inventar-/API-/Einkaufsregressionen** bestanden, keine Skips. Isolierte synthetische SQLite-Datenbanken; keine Bestandsdatenbank verändert.

**62 kombinierte Flutterprüfungen** bestanden (8 neue Fälle und 54 bestehende Beleg-/Katalogpreisfälle). Ein abschließender gezielter Lauf der 8 neuen Fälle einschließlich bestehender Vorlage mit `settings.manage` ohne `finance.write` bestand ebenfalls. Die Dart-Analyse der beiden Produktdateien und des neuen Tests meldet keine Befunde. Genaue Hashes stehen im zugehörigen Manifest `docs/evidence/project-release-readiness-2026-11-04/material-document-completion.json`. Neue Widgetprüfungen bedienen echte Dialoge für eine Lagerrolle, prüfen mehrere Artikelseiten, fehlende Capability, inkonsistente Pagination, verspätete Antworten nach Rechteentzug, offene Beleg-/Vorlagendialoge und Stornometadaten einschließlich unbestätigter Wiederholung nach erneutem Öffnen. Bestehende Beleg- und Katalogpreisprüfungen werden gemeinsam ausgeführt.

Der erste neue Widgetlauf hatte sieben erfolgreiche Fälle und einen fehlerhaften Testfinder: Auswahlfelder besitzen keine Textfeld-ID; korrigiert wurde ausschließlich der Finder. Die vorbereitenden Umgebungsfehler (Compilerpfad, fehlender lokaler PDFium-Cache, gesperrter Loopback-Socket) bleiben getrennt nachweisbar. Verwendet werden vorhandene Toolchains und eine Kopie des vorhandenen PDFium-Caches; keine Produktabhängigkeit wurde geändert.

Ein unabhängiger Quellreview fand die zunächst fehlende Wiederherstellung offener Stornometadaten, eine zu breite Sperre bestehender Vorlagenarten und eine unvollständige Abschlusscursor-Prüfung. Diese Punkte wurden vor dem abschließenden Prüflauf korrigiert.

## Umfang und Grenzen

Die Backend-Implementierung inklusive SQL-Dialektzweig ist enthalten; eine PostgreSQL-Ausführung wurde in diesem Teilauftrag nicht vorgenommen. Der bestehende generische HTTP-Transport ignoriert GET-Bodies; Queryparameter und direkte Dispatch-Eingaben sind streng geprüft. Eine zentrale Änderung der GET-Body-Behandlung gehört nicht zu diesem Patch.

Die Browser-Materialanbindung wird durch den separaten Projekt-/Browserauftrag integriert. Dort ist gegen exakt diesen Backendhash ein echter Lagerrollenablauf mit MFA, Reservierung und Teilentnahme auf Desktop-/Mobilansicht geprüft worden; dessen eigene Evidenz ist separat zu übernehmen. Die hier ausgeführten Flutter-Widgettests ersetzen weder einen neuen Windows-/iPhone-Build noch einen Gerätetest oder eine Freigabe für echte Kundendaten.

## Reproduktion

```sh
cd app
PATH=/workspace/toolchains/clang-19/bin:$PATH \
PUB_CACHE=/workspace/toolchains/pub-cache \
/workspace/toolchains/flutter/bin/flutter test --no-pub \
  test/business_material_document_access_test.dart \
  test/business_documents_widget_test.dart \
  test/business_document_completion_test.dart \
  test/business_catalog_price_consumers_test.dart \
  test/business_catalog_price_workflows_test.dart --reporter expanded
```

Detaillierter Backendvertrag und Befehle/Logs: `docs/evidence/project-release-readiness-2026-11-04/inventory-article-references-contract.json`.
