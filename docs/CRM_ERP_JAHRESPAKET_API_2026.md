# Jahresnachweis-API, Version 1

Die spätere unabhängige Gegenprüfung begrenzt den Nachweis ausdrücklich: Das
Paket enthält die aufgelösten Originale, beweist aber keine intrinsische
Vollständigkeit aller ursprünglichen Abhängigkeiten. Die alten Journale besitzen
dafür keinen unveränderlichen vollständigen Auswahlindex. Eine erfolgreiche
Archivhashprüfung ist keine vollständige fachliche Prüfung.

Der lokale Prüfer benötigt zwingend den separat über die authentisierte
Metadatenantwort bestätigten Archiv-SHA-256. Ein nur im Archiv selbst enthaltenes
oder aus der zu prüfenden fremden Datei berechnetes Gegenstück ist kein solcher
Vertrauensanker. Ohne oder mit falschem Anker schlägt die Prüfung fehl.
Manifestfelder `intrinsic_dependency_closure: false` und
`required_trust: "separately_authenticated_archive_sha256"` sowie das entsprechende
Prüferergebnis weisen diese Grenze aus. Die 16 HTTP-Metadatenfelder ändern sich
dadurch nicht; `original_year_complete` bezeichnet weiterhin ausschließlich den
ursprünglichen EÜR-Bericht.

Feature `accounting_year_evidence_v1` im vorhandenen EÜR-Modul. Keine neuen
Finanztabellen, keine neue Mutation, keine neue Migrationsnummer.

Voraussetzung ist ein vorhandener bestätigter EÜR-Exporteintrag. Eine bloße
Reportvorschau hat keinen Exporteintrag und wird nicht als Jahrespaket ausgegeben.
Die Operatorbindung der Unternehmensinstanz muss vorhanden sein. Aktuelle
`accounting.read`-/`finance.read`-Rechte sowie sämtliche eingeschlossenen
Projekt-/Fachquellen werden bei jedem Abruf erneut geprüft. Private Lohn- oder
Reisequellen werden auch für die Geschäftsführung nicht in dieses Finanzformat
ausgedehnt.

## Metadaten

`GET /business/accounting/euer/exports/{export_id}/evidence`

Keine Queryparameter und kein Requestbody. Antwort 200 JSON:

```json
{
  "format": "smartplan-year-evidence-v1",
  "schema_version": 1,
  "instance_id": "32stellige_unternehmenskennung",
  "year": 2026,
  "export_id": "32stellige_originale_exportkennung",
  "export_hash": "64stelliger_hash_des_unveraenderten_exporteintrags",
  "sha256": "64stelliger_sha256_der_exakten_zipbytes",
  "size": 12345,
  "filename": "smartplan-jahresnachweis-2026-EXPORTID.zip",
  "archive_path": "/accounting/euer/exports/EXPORTID/evidence/archive",
  "original_count": 2,
  "original_year_complete": false,
  "private_source_boundaries": ["payroll_cash"],
  "official_tax_return": false,
  "datev_certified": false,
  "private_personnel_originals_included": false
}
```

Das Beispiel erklärt Feldformen und ist keine Testfixture. Reale Clientfixtures
werden ausschließlich über den Domain-/Dispatchgenerator erzeugt.
`original_year_complete` ist exakt die damalige fachliche Vollständigkeit des
unveränderten EÜR-Reports. Ein technisch lesbares Archiv macht einen unvollständigen
Jahresstand nicht vollständig. `private_source_boundaries` nennt die tatsächlich
enthaltenen öffentlichen Finanzprojektionen (`payroll_cash`, `travel_cash`), deren
private Personaloriginale bewusst nicht beigefügt sind.

## Dateiabruf

`GET /business/accounting/euer/exports/{export_id}/evidence/archive`

Antwort 200 `application/zip`, geschützter Download mit `Cache-Control: no-store`
und kontrolliertem `Content-Disposition`-Dateinamen. Der Client prüft vor Ablage
Größe und SHA-256 gegen genau die bereits gelesenen Metadaten sowie Instanz,
Export-ID/-Hash und Jahr gegen die geöffnete Exportfassung. Bei Kontextwechsel,
Rechteentzug oder fremden Bytes keine Datei ausgeben. Wiederholung ist rein
lesend und ergibt für dieselbe v1-Exportfassung identische Bytes.

404 bei nicht vorhandenem Export, 401/403 bzw. absichtlich verborgener 404 bei
fehlenden aktuellen Zugriffsrechten, 409 bei fehlender Instanzbindung, unbekannter
Quellenform oder beschädigter Originalbindung, 413 bei Überschreiten der Grenzen.
400 bei zusätzlichen Parametern, 405 für eine andere Methode. Es gibt keine
`request_id`, keine Annahmequittung und keine neue Buchung für diesen Leseabruf.
Die originalen EÜR-Annahmequittungen bleiben im gespeicherten Journal gebunden.

## Archiv und lokale Prüfung

Feste UTF-8-Dateien `manifest.json`, `report.json`, `postings.csv`, `journal.json`,
`proofs.json`, `README.txt` und `verify_year_package.py`; Originale ausschließlich
unter `originals/{sha256}.bin`. Originaldateinamen sind beschreibende Metadaten,
niemals Extraktionspfade. Dateien sind sortiert, unkomprimiert und haben den
festen ZIP-Zeitstempel 01.01.1980. Ausgabe höchstens 128 MiB und 10.000 Dateien;
höchstens 100.000 Positionen im ursprünglichen Journalpräfix. Überschreitung
erzeugt kein Teilpaket.

Der eigenständige Standardbibliothek-Prüfer kontrolliert das Paket ohne Datenbank
und ohne Extraktion. Der separat bestätigte Archivhash muss übergeben werden:

```text
python verify_year_package.py jahr.zip --sha256 SEPARAT_BESTAETIGTER_HASH
```

Ein intern neu gehashtes Paket ist keine Signatur. Der externe Archivhash bindet
seine Herkunft, soweit dieser Anker separat authentisiert wurde; der Prüfer prüft zusätzlich die ausdrücklichen Beziehungen der
ursprünglichen Report-/Journal-/Quellfassung und zugehörigen Originale. Eine
fachliche Steuerprüfung oder Prüfung privater Lohnberechnungen wird nicht behauptet.
