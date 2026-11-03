# Kontrollierte Dateiübernahme aus HERO und sevdesk

Stand: 03.11.2026. Architektur und Quellenprüfung; die Umsetzung und tatsächliche
Prüfergebnisse werden getrennt im Workflowbericht geführt. Keine echten Konten,
Zugangsdaten, externen Abrufe von Kundendaten oder produktiven Migrationen benutzt.

## Tatsächlich belegte Anbieterwege

| Quelle | Nachgewiesen | Noch nicht nachgewiesen |
|---|---|---|
| [HERO Datenexport](https://hero-software.de/features/stammdaten/daten-export) | Export von Projekten, Dokumenten und Dateien als PDF, CSV und Excel wird offiziell angeboten. | Verbindliche Spaltennamen, Zeichensatz, Datums-/Zahlenkonventionen und Vollständigkeit eines konkreten Mandantenexports. |
| [HERO GraphQL-Anleitung](https://hero-software.de/api-doku/graphql-guide) | API-Schlüssel vom Support; Bearer-Authentifizierung, Endpunkt `https://login.hero-software.de/api/external/v7/graphql`. Öffentliche Beispiele nennen `contacts`, `project_matches`, `customer_documents`, Kontaktadressen und Kunden-/Ansprechpartnerbezüge. | Vollständiges Schema und Referenz sind zugangsgeschützt; keine Live-Kontoabnahme, kein bestätigter vollständiger Exportvertrag. |
| [sevdesk Export](https://hilfe.sevdesk.de/de/articles/9373838-export) | Manueller Datei-Export enthält CSV-Buchungsstapel/Stammdaten und ZIP-Belegbilder. Zeitraum und Auswahl offener/festgeschriebener Belege beeinflussen den Inhalt. Die Stammdaten umfassen Kontakte des ausgewählten Zeitraums. | Ein solcher Export ist kein belegter vollständiger CRM-/Vorgangsexport. Keine vollständig spezifizierte automatische Interpretation aller DATEV-Versionen. |
| [sevdesk API-Referenz](https://api.sevdesk.de/) | Öffentliche Referenz nennt getrennte Kontaktadressen und `Invoice/{invoiceId}/getPdf`. Letzteres besitzt `preventSendBy` mit Versandbezug. | Ein unverändernder PDF-Abruf ist damit nicht hinreichend belegt; diese Route bleibt gesperrt. Die API-Startseite war im Webabruf leer, die indexierte offizielle Referenz lieferte die genannten Einzelverträge. |

Die bestehenden [Integrationsquellen](../backend/online/INTEGRATIONEN_QUELLEN.md)
dokumentieren frühere Zugriffsbeschränkungen und den ausdrücklich inoffiziellen
OpenAPI-Mirror. Die aktuelle Recherche ersetzt diese historische Aussage nicht
durch eine behauptete Kontoabnahme. Der vorhandene sevdesk-Adapter ist eine
ausgewählte, lesende Metadatenintegration; er ist kein Migrationsimport.

## Konkreter nächster Umfang

Ein eigener Dateiworkflow übernimmt Originale unverändert und führt den Anwender
durch Zuordnung, Vorschau und Übernahme. Er bezeichnet sein Eingabeformat als
**Smartplan-Dateiimport v1**, auch wenn die Originaldatei aus HERO oder sevdesk
stammt. Eine automatische Anbieterkompatibilität wird nicht behauptet. CSV-
Spalten werden ausdrücklich zugeordnet; JSON verwendet ein dokumentiertes
Smartplan-Zeilenschema. Nicht unterstützte Excel-/ZIP-Varianten bleiben als
Original aufbewahrt und werden nicht heimlich interpretiert.

1. Quelle, Quellkonto, Exportzeitraum und beabsichtigter Umfang festhalten.
   Dateien einzeln hochladen, Originalname, Bytes, Länge und SHA-256 archivieren.
   Parsergrenzen, Zeichensatz und Trennzeichen ausdrücklich wählen. Keine
   Dateipfade/URLs aus Daten abrufen, keine Formeln ausführen.
2. Zuordnung als neue Version speichern. Die Originaldatei bleibt unverändert;
   jede Zeile und jedes Feld behält Datei-/Zeilenherkunft. Kontakte, Projekte und
   historische Dokumente benötigen stabile Quellkennungen; fehlende IDs werden
   nicht aus Namen geraten.
3. Vorschau zeigt normale Datensätze, fehlende Pflichtwerte, ungültige Zahlen,
   doppelte Quellkennungen, fehlende Beziehungen und Dublettenkandidaten im
   bestehenden Bestand. Gleiche Namen oder E-Mail-Adressen führen niemals zu
   automatischem Zusammenführen. Anwender entscheidet bewusst neu/verknüpfen/
   ausschließen; Ausschlüsse bleiben im Bericht.
4. Eine gebundene Vorschau umfasst Originalhashes, Zuordnungsversion, heutige
   Zielrevisionen, Quellbezüge und exakte Beträge. Übernahme prüft diese Fakten
   erneut, aktuelle Rechte und fachliche Aktivierung. Ein einziger atomarer
   Vorgang erzeugt neue Kontakte/Projekte, eindeutige Herkunftszuordnungen und
   unveränderliche historische Dokumente. Bestehende Kontakte/Projekte werden
   durch Verknüpfen nicht überschrieben. Wiederholung derselben Nonce liest den
   ursprünglichen Ergebnisbeleg; Änderungen benötigen einen neuen Auftrag.
5. Ergebnisbericht stellt Quell-/übernommene/ausgeschlossene/fehlerhafte Anzahlen,
   Beziehungen, Originalhashes und deklarierte Dokumentbeträge je Währung und
   Dokumentart gegenüber. Fehlende Beträge bleiben fehlend; kein EUR-Ersatz,
   kein Vollständigkeitsversprechen aus einem gefilterten Export. Ein
   ausdrücklich bestätigter Abgleich dokumentiert nur diesen Umfang.

Historische Rechnungen werden weder neu ausgestellt noch in native Nummernkreise,
Zahlungen, offene Posten, Umsatzsteuer oder EÜR übernommen. Ein gesonderter
Eröffnungsprozess benötigt echte offene Einzelposten, Zahlungs-/Stichtagsnachweise
und fachliche Freigabe. Aus archivierten Summen entstehen keine Buchungen.

## Additive Integration

- Neue Domäne `backend/business_migrations.py`; eigene Tabellen für Pakete,
  Originale, Mappingversionen, Herkunftsverknüpfungen, Dokumentarchive und
  Quittungen. SQLite-/PostgreSQL-Guards und Integritätsprüfung; bestehende
  Migrationsprüfsummen bleiben unverändert.
- Bestehende kanonische Kontakte (`BusinessFoundation`) und Projekte wiederverwenden.
  Die Dokumentoriginale erhalten einen eigenen historischen Archivtyp, damit
  sie nicht als von Smartplan ausgestellte oder bezahlte Dokumente erscheinen.
- API unter `/business/migrations`; Browser und Flutter zeigen denselben
  Prüfablauf, Datenbindung und Wiederholungsstatus. Importadministration verlangt
  `settings.manage`, Stammdatenzugriff `contacts.read/write`, Projektanlage
  `projects.manage`, Finanzdokumentzugriff `finance.read`; zusätzlich gelten
  aktuelle Objekt-/Projektberechtigungen und aktive Fachmodule.
- Quellkennungen werden mit System **und** ausdrücklich gewähltem Quellkonto
  gebunden. Kollidierende IDs verschiedener Konten sind unterschiedliche Quellen.
  Verknüpfungen über spätere Pakete bleiben eindeutig; veränderte Quellzeilen
  werden als Konflikt angezeigt und überschreiben keine übernommenen Daten.
- Datenschutzexport/-sperren berücksichtigen Originaldateien und historische
  Kundendaten; kein stilles Löschen von Nachweisen. Backup/Restore erhält
  Originale/Quittungen und erzwingt bei unvollständigen Daten einen Integritätsfehler.

## Verifikation und verbleibende Voraussetzungen

Notwendige Tests: Parsergrenzen/Encoding/CSV-Zeilenfehler, Null/fehlend/exakte
Dezimalwerte, doppelte Quell- und Zielzuordnungen, falsche Kunden-/Projektbezüge,
veraltete Vorschau, Rechteentzug und Wiederholung nach verlorener Antwort,
Rollback bei Fehler nach Kontakt-/Projektanlage, konkurrierende Übernahme,
Original-/Quittungsschutz, echtes PostgreSQL/MFA/HTTP/Restore, beide Clients und
Browserablauf einschließlich Fehlervorschau und abschließendem Abgleich.

Ohne Zugangsdaten umsetzbar ist der gesamte lokale Dateiworkflow mit kontrollierten
Testdaten. Für bestätigte HERO-/sevdesk-Profile fehlen echte anonymisierte
Exportbeispiele samt Exportoptionen/Version, für Liveabrufe zusätzlich freigegebene
Testkonten und belegte Nur-Lese-Verträge. Diese offenen Voraussetzungen hindern
die unabhängige Dateiübernahme nicht; sie dürfen nicht als bereits abgenommen
ausgegeben werden.
