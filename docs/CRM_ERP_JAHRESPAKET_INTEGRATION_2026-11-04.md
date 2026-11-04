# Jahresnachweispaket: gezielte Integration

Arbeitsbaum `/workspace/smartplan-year-review-export-20261104` basiert auf
`b0b96024f0a7cf2c7097fb3b77c64032265850a5` und dem exakt eingefrorenen
Altpostenbackendmanifest `4fc7db209ebf5ce98799400d330182692f88ffdb5c9b9e1e924649385c6f3a88`.
Die 2044 ursprünglichen Dateihashes stehen im Backendnachweis `baseline.json`.
Dieser geerbte Altpostenumfang gehört nicht erneut als neuer Jahrespaketcode
über den aktuellen Hauptstand kopiert.

Die neue Funktion ist rein lesend: vorhandener unveränderter EÜR-Jahresexport,
seine damaligen aufgelösten Originale und Journalentscheidungen als deterministisches
ZIP. Keine neue Mutation, Tabelle, Migrationsnummer oder Finanzhorizonterhöhung.
Der unabhängige Review weist die echte Grenze alter Abhängigkeitsbindungen aus:
kein intrinsischer Vollständigkeitsbeweis, verpflichtender separat authentisiert
bestätigter Archivhash. Alle Oberflächen und Offlineprüfer dokumentieren diese
Grenze. Die ursprüngliche EÜR-Jahresvollständigkeit bleibt eine andere Angabe.

## Geteilte Dateien

- `backend/business_accounting_euer.py`: zusätzliches Feature und GET-Routen/
  read-only `year_evidence`; die enge `euer-year-package.patch` im ersten
  Backendnachweis bezieht sich auf die dort ebenfalls gesicherte ursprüngliche
  Overlayfassung. Neuere Jahresvortrags-/EÜR-Registrierungen bewahren.
- `backend/online/web.py`: statische Allowlist der beiden neuen Browsermodule;
  die geerbten Altposten-Uploadlimits sind bereits gesonderter Bestand.
- `web/office/office.js` und `accounting-euer.js`: schmale Jahresnachweis-
  Einstiegspunkte, Dialog-/Sitzungs-/Hintergrundgrenzen und frische Rechteprüfung
  auch beim alten JSON-/CSV-Abruf. Browserowner liefert einen eigenen Patch gegen
  den hashgebundenen Basisschritt; neuere unabhängige Oberflächen bewahren.
- `app/lib/business_accounting_euer.dart`: enger Eintrag an der vorhandenen
  gespeicherten Exportkarte; zwei neue native Module. Nativeowner liefert den
  eigenen schmalen Patch. Keine Session-/API-/Exporter-Neudefinition.
- Beide Paketskripte und CI: neue Backendmodule, Dokumentnachweise, zusätzlicher
  gezielter PG-Test und tatsächlicher Browserworkflow. Native Tests werden durch
  die vorhandene Gesamtdiscovery erfasst. Neuere Operatorlisten nicht ersetzen.

Die sechs tatsächlichen V1-Clientfixtures sind bytegleich in `docs/fixtures` und
`app/test/fixtures`, 719679 Bytes, SHA-256
`a859f2bbbcfab6f890c2968a05aa2fa839299117ae43b8e15e2d7852c82d36a0`.
Der ältere Fixturestand sowie rote unabhängige Gegenfälle sind ausdrücklich
historische Nachweise vor der Prüferkorrektur und bleiben unverändert erhalten.

## Tatsächliche getrennte Abnahmen

Der aktuelle gemeinsame Backendlauf besteht mit 49 Fällen: 17 eigene,
12 unabhängige, zwei echte HTTP-/MFA-Fälle und 18 bestehende EÜR-Fälle.
Browserowner meldet 659 vollständige Nodefälle, tatsächlichen neuen ZIP-/MFA-
Workflow und unveränderten alten EÜR-Workflow. Der unabhängige Browserreview
prüft echte Quellrechte nach bereits geholtem ZIP; der Nachtrag prüft sechs
neue tatsächliche Archive sowie 18 negative Hash-/Bytevarianten.
Nativeowner meldet 49 Fälle einschließlich echter 390px-HTTP-/Dateiablage und
externem Standardbibliotheksprüfer, Analyse ohne Befund. Der unabhängige native
Review besteht mit 16 eigenen Fällen und einem tatsächlichen HTTP-Fall; sein
eigenes Manifest ist gebunden. Frühere PostgreSQL-/Restore-
Ergebnisse und der aktuelle Nachlauf werden im finalen Backendmanifest getrennt
geführt; aus einem früheren Lauf wird keine neue Hashabnahme abgeleitet.

## Separater V2-Nachtrag

`/workspace/smartplan-year-review-export-carryover-20261104` enthält einen eigenen
Adapter für die inzwischen tatsächlich vorhandene Quelle `opening_year_values`.
Sein Manifest bindet die genaue Jahresvortragsbasis und einen kleinen getrennten
EÜR-Dispatchpatch. Nur betroffene damalige Exporte wählen `smartplan-year-evidence-v2`;
spätere neue Quellen ändern alte V1-ZIPs nicht. Seine vier zusätzlichen echten
Fixtures ersetzen die sechs V1-Fälle nicht. Die V2-Oberflächenanbindung ist eine
getrennte Aufgabe nach dem V1-Freeze. Nicht den gesamten Adapterarbeitsbaum über
neuere Hauptrepositorydateien kopieren.

Keine Produktionskontakte, echten Daten, Nachrichten, Zahlungen, Commits oder
pauschale Gesamtfertigstellungsbehauptung dieses Handoffs.

Abschließender gemeinsamer PG-Nachlauf: drei Fälle bestanden in 19,002 Sekunden,
einschließlich der zwei V1-Archive und des gesonderten V2-Originaljournals.
Beide V1-Kerndateien sind bytegleich; EÜR-Routenauswahl und Finanzhorizont-15-Basis
gehören zum getrennten Adapter. Sichere eigene Metadatenkontrolle: nur
`smartplan_check`, keine weiteren Verbindungen. Operatorregistrierung 16/16
bestanden in 6,183 Sekunden; keine weitere Produktänderung aus diesen Läufen.
