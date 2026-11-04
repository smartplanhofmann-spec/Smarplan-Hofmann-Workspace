# Jahresvortrag und V2-Archive – gemeinsame Prüfung vom 04.11.2026

Der Kandidat `/workspace/smartplan-year-values-integration-20261104` auf Basis
`2e2ed5c` integriert belegte laufende Jahreswerte vor einem unterjährigen
Softwarebeginn mit Browser, nativer Anwendung, EÜR und Original-/Journalarchiv
V2. Der vereinbarte Rahmen bleibt Einzelunternehmen, EÜR, Regelbesteuerung mit
Ist-Versteuerung, SKR04 und Nettopreise. Der
[maschinelle Gesamtnachweis](evidence/year-values-integrated-regression-2026-11-04.json)
bindet die Prüfprotokolle und 1.223 endgültige Quelldateien. Die unabhängige
Zusammenführungsprüfung bestätigt zusätzlich 398 unveränderte Dateibindungen.

## Technisch integrierter Umfang

Die Übernahme bindet ursprüngliche Rechnungs- und Journaloriginale, belegte alte
Netto-/Steueranteile, tatsächliche Zahlungstage und bereits ausgeübte
Vorsteuerrechte. Ein unabhängig belegter zusammenhängender Zeitraum und die
Kontrollsummen werden ausdrücklich geprüft. Reine Zeitraumsdeckung ersetzt
keine vollständige Einordnung aller vorhandenen Quellen. Ein belegtes Nulljournal
wird nur ohne bekannte Gegenwerte angenommen. Nicht unterstützte historische
Sonderquellen werden nicht stillschweigend in diese begrenzte Fallklasse gezogen.

Historische Werte erzeugen keinen neuen Geldfluss oder Vorsteueranspruch.
Nachträgliche Korrekturen erhalten Originale und Annahmequittungen; erforderliche
EÜR-Gegenbuchungen, geöffnete Perioden und aktuelle Rechte bleiben maßgeblich.
Beide Clients verwenden die tatsächlichen Quellen und behandeln verlorene
Antworten, Quellwechsel, Hintergrundwechsel und entzogene Rechte entsprechend
dem bestehenden Vertrag. Siehe [API](CRM_ERP_JAHRESVORTRAG_API.md),
[V2-Archivvertrag](CRM_ERP_JAHRESPAKET_VORTRAG_V2_2026-11-04.md) und
[gemeinsamer Finanznachweis](CRM_ERP_JAHRESVORTRAG_FINANZ_PG_2026-11-04.md).

V2 ergänzt genau den eingefrorenen Jahresprüfstand um die zugehörigen
Jahresvortragsoriginale. Alte V1-Ausgaben und ursprüngliche Exportbytes werden
nicht nachträglich aufgewertet oder umgeschrieben. Der separat authentisiert
bestätigte Archivhash bleibt verpflichtend. Die Verifikation weist weiterhin
`intrinsic_dependency_closure=false` aus und behauptet keine vollständige
Menge sämtlicher historischer Abhängigkeiten. Private Lohnoriginale werden
nicht aufgrund bloßer Finanzrechte in das Paket übernommen.

## Tatsächlich ausgeführte gemeinsame Prüfungen

| Prüfung | Ergebnis | Nachweis |
| --- | --- | --- |
| Vollständiges Backend | 1.899 von 1.900 bestanden; ein Windows-spezifischer Skip unter Linux | [Protokoll](evidence/year-values-integrated-backend-2026-11-04.txt) |
| Vollständige Flutter-Suite | 1.542 bestanden | [Protokoll](evidence/year-values-integrated-flutter-2026-11-04.txt) |
| Vollständige Node-Suite | 842 bestanden | [Protokoll](evidence/year-values-integrated-node-2026-11-04.txt) |
| App-Analyse | Keine Befunde | [Protokoll](evidence/year-values-integrated-analyze-2026-11-04.txt) |
| Paketprüfungen | 16 bestanden | [Protokoll](evidence/year-values-integrated-packages-2026-11-04.txt) |
| Finanz-PostgreSQL | 121 unterschiedliche Fälle mit jeweils bestandenem letztem Ergebnis; Erstlauf 118 bestanden und drei historische Fixturefehler, anschließend genau vier Methoden grün | [Vollständiger Nachweis](evidence/year-values-financial-postgres-2026-11-04/manifest.json) |
| Neuer gefüllter gemeinsamer Restore | Beim ersten Einzelaufbau und erneut in der vollständigen Matrix bestanden | [Nachweis](evidence/year-values-full-financial-restore-pg-2026-11-04.json) |

Fünf tatsächliche Chromiumabläufe mit aktiver Sandbox sind grün:

| Ablauf | Dauer | Protokoll |
| --- | --- | --- |
| Jahresvortrag | 69,341 s | [Jahresvortrag](evidence/year-values-integrated-browser-year-values-2026-11-04.txt) |
| V2-Jahres-ZIP | 40,339 s | [V2-Archiv](evidence/year-values-integrated-browser-year-package-v2-2026-11-04.txt) |
| Bestehende EÜR | 63,155 s | [EÜR](evidence/year-values-integrated-browser-legacy-euer-2026-11-04.txt) |
| Historische offene Posten | 71,281 s | [Altposten](evidence/year-values-integrated-browser-accounting-open-items-2026-11-04.txt) |
| Unternehmensereignisse | 51,199 s | [Ereignisse](evidence/year-values-integrated-browser-company-events-2026-11-04.txt) |

Der separate CSS-Nachtrag behandelt zerrissene Datums-, SKR04- und Betragswerte
in der 390-Pixel-Tabelle. Ein zusätzlicher tatsächlicher Root-Browsernachlauf
besteht in 26,494 Sekunden ([Protokoll](evidence/year-values-integrated-browser-year-values-mobile-table-final-2026-11-04.txt)).
Dieser spätere Darstellungsstand ist [separat an seine finale Quelle gebunden](evidence/year-values-mobile-table-2026-11-04/manifest.json);
die ursprünglichen fünf Abläufe und frühere Ganzbaumhashes werden nicht
nachträglich als Läufe auf dem späteren CSS-Stand ausgegeben. Die abschließende
CSS-/Gesamtmanifestbindung ist im maschinellen Gesamtnachweis enthalten.

## Erhaltene Quellen, Wiederherstellung und Nachträge

Der vollständige PG-Lauf umfasst 25 Module und dauerte 1.334,667 Sekunden.
Alle 517 Backend-Pythondateien blieben während dieses Laufs bytegleich.
Die Endtracebacks bestätigten drei Fehler in der Konstruktion ausdrücklich
älterer Teststände: Anlagen- und Anfangssaldentest enthielten die neue
`year_values`-Familie noch in ihren alten Horizonten; die Vor-Reisekosten-Fixture
installierte den späteren Jahresvortrag ohne seine ausgeschlossenen Vorgänger.

Nach Abschluss der Gesamtprüfungen wurde ausschließlich der unabhängig
vorgeschlagene Patch in vier PG-Testdateien übernommen. Der vierte Altpostenfall
war zuvor bereits grün; seine zusätzliche strukturelle Vorprüfung verhindert
eine Ablehnung aus dem falschen Grund. Genau diese vier Methoden bestanden
anschließend in 39,118 Sekunden. Es sind 125 Ausführungen, weiterhin 121
unterschiedliche Fälle. Die drei roten Erstbefunde, ursprünglichen Testdateien,
Patchvorschlag und Vorher-/Nachherhashes bleiben erhalten. Produktlogik,
Appdateien und Paketregister wurden dadurch nicht geändert. Die ursprünglichen
Backend-/App-/Paketnachweise behalten ihre eigenen Quellbindungen; spätere
Ganzbaumhashes unterscheiden sich um die vier dokumentierten Testdateien.

Der gemeinsam gefüllte Restore verbindet einen Anfangssaldo von 1.000,00 €,
1.200,00 € historische Folge-AfA, einen alten Lieferantenposten mit 119,00 €
neuer Zahlung sowie 59,50 € alte und 59,50 € neue Teile einer weiteren Rechnung.
Das ursprüngliche Vorsteuerrecht bleibt in seiner belegten alten Periode.
Ergebnis: 1.438,00 € EÜR-Ausgaben, 178,50 € neuer Geldabfluss und 821,50 € Bestand.
V1- und V2-Archive bleiben vor und nach der Restorefreigabe bytegleich.
Source5, beide Katalogversionen, Anlagen, Anfangsbestände, Altposten und
Ereignisquittungen bleiben gemeinsam erhalten. Zu alte oder manipulierte
Freigaben werden abgewiesen.

Aktueller Finanzhorizont: 15; Restorebericht: 16. Der Kandidat registriert
144 Backend- und 209 Betreiberpfade. Die abschließende lokale
Docker-/psql-Metadatenkontrolle bestätigte ausschließlich `smartplan_check`
und keine weiteren Verbindungen oder Restoreziele. Keine Produktivdaten oder
externen Anbieter wurden für diese Prüfungen verwendet.

## Gesamtziel und verbleibender Umfang

Jahresvortrag und V2-Archivanschluss sind technisch integriert. Gesamtbuchhaltung,
weitere Steuer-/Lohnfälle, Steuerberater-/DATEV-/Behördenwege, Fach- und
Betriebsnachweise sowie alle Gesamtabnahmen A–G bleiben offen. Die parallelen
Arbeitsstände für Isolation, native Assistenten-/Sprachabläufe,
Service/Betriebsmittel und private Lohnvergleichs-/Quellenpakete sind noch nicht
in diesem Checkpoint enthalten.

Die unveränderte Anforderungsmatrix zählt 40 von 62 Zeilen als implementiert
oder getestet, fünf als teilweise, elf als offen und sechs als extern blockiert.
40/62 entspricht 64,5 %, gerundet etwa 65 %, nach ungewichteter Zeilenzahl.
Das ist weder eine Fertigstellungs- oder Arbeitszeitquote noch eine vollständige
Produktfreigabe. Keine Statushochsetzung erfolgt aus der Zahl neuer Tests.
