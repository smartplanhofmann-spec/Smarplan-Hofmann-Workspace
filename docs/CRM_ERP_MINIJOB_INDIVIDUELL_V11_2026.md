# Individuell besteuerter gewerblicher Minijob – v11

## Belegter Anfangsumfang

Dieser additive Vertrag gilt für einen vollständigen Kalendermonat 2026, einen einzigen gewerblichen Minijob mit unverändertem Monatslohn von 175 bis 603 EUR, Steuerklasse I oder V und belegter beitragsfreier gesetzlicher Familienversicherung. RV-Pflicht und wirksame RV-Befreiung sind getrennte Fälle. Weitere Beschäftigungen, relevante weitere Einkünfte, Auslandsversicherung, sonstige Bezüge, Reisen, Abwesenheiten, untermonatige Änderungen, Kinderfreibeträge, Kirchensteuer, Faktoren und weitere Sonderfälle gehören nicht zu diesem ersten Umfang.

Die Grundlagen und Grenzen des Abrufs stehen im [Primärquellenaudit](CRM_ERP_MINIJOB_PAP_MERKMALE_AUDIT_2026.md). Das Original-PDF des BMF konnte dort nicht archiviert werden; ein PDF-Hash wird nicht behauptet. Die bereits gepinnte XML wird separat durch den Java-BigDecimal-Generator ausgeführt. 36 unabhängige Referenzfälle für beide RV-Zweige und Klassen I/V einschließlich der Bereichsgrenzen liegen in `backend/testdata/minijob_individual_xml_2026.json`.

## Keine Umdeutung der Versicherung

Das tatsächliche Profil bleibt `health_insurance: "statutory_other"`; die zusätzliche belegte Prüfung präzisiert `actual_health_insurance: "statutory_family"`. Das Merkmal `PKV=1` erscheint ausschließlich unter den technischen PAP-Parametern. Es setzt die ausdrückliche Anweisung in BMF-Randnummer 16 um, weil aus diesem Minijob kein Arbeitnehmerbeitrag zur KV/PV anfällt. Es behauptet keine tatsächliche Privatversicherung. `PKPV=PKPVAGZ=0`, `ALV=1`; `KRV` ist bei belegter RV-Befreiung 1, bei RV-Pflicht 0. Der tatsächliche RV-Abzug von 3,6 % und die PAP-Vorsorgepauschale sind verschiedene Größen.

## Bestehende Routen, ausdrücklich neue Vertragsfassung

Es werden keine Datenbanktabellen oder alten Regeldateien geändert. Der bestehende `calculation_case` verwendet:

```json
{
  "rule_version": "de_2026_individual_minijob_month_v11",
  "source_contract_version": 3,
  "details": {
    "month": "2026-10",
    "period_case_ref": {"id":"…", "revision":1, "content_hash":"…"},
    "employment_terms_refs": [{"id":"…", "revision":1, "content_hash":"…"}],
    "profile_refs": [{"id":"…", "revision":1, "content_hash":"…"}],
    "identity_refs": [{"id":"…", "revision":1, "content_hash":"…"}],
    "segment_events": [], "thirty_day_rule": null,
    "entitlement_case_refs": [], "travel_settlement_refs": [],
    "flat_tax_decision": null,
    "verification_note": "Tatsächliche Monatsquellen geprüft",
    "individual_minijob_assessment": {
      "schema_version":1,
      "employee_id":"…",
      "valid_from":"2026-10-01", "valid_to":"2026-10-31",
      "declaration_date":"2026-11-03",
      "actual_health_insurance":"statutory_family",
      "pension_status":"compulsory",
      "sole_employment_confirmed":true,
      "income_review_complete":true,
      "no_other_relevant_income_confirmed":true,
      "domestic_commercial_employment_confirmed":true,
      "no_foreign_insurance_confirmed":true,
      "no_other_special_cases_confirmed":true,
      "health_evidence_ref":{"id":"…","revision":1,"content_hash":"…"},
      "pension_evidence_ref":{"id":"…","revision":1,"content_hash":"…"},
      "employment_evidence_ref":{"id":"…","revision":1,"content_hash":"…"},
      "income_evidence_ref":{"id":"…","revision":1,"content_hash":"…"},
      "elstam_evidence_ref":{"id":"…","revision":1,"content_hash":"…"},
      "verification_note":"Gültige Originale und Wirkung vollständig geprüft"
    }
  }
}
```

Die Hüllenfelder `employee_id`, `employee_revision`, `kind`, `source_file_ids` bleiben gleich. Annahme benötigt weiterhin `request_id`, Ausgangsrevision, Status, ausdrückliche Bestätigung und den Hash der aktuellen Vorschau. Sämtliche genannten Dateien müssen eigene geschützte Personalaktenoriginale sein, unveränderte Hashes besitzen und in `source_file_ids` enthalten sein. Ein fremder Mitarbeiter, ersetzter Beleg, abweichender Zeitraum oder fehlende Prüfung erlaubt keine Berechnung. Die negative Erklärung ist dauerhaft an Person, Wirkungszeitraum und tatsächliche Originale gebunden; eine freie Checkbox allein genügt nicht.

Für die tatsächliche ELStAM-Identität erweitert ausschließlich der neue individuelle Minijob die bestehenden Identitätsdetails um `identity_source_schema_version: 2`. Alle bisherigen Identitätsfelder bleiben erforderlich; `tax_source` ist `elstam_imported`, Jahresfreibeträge und Hinzurechnungen sind 0, Religionsmerkmal ist `none`. Der ELStAM-Referenzbeleg der Prüfung muss genau dem Original der Identitätsfassung entsprechen. Alte Identitäten ohne dieses neue Feld und alte Pauschsteuerbezeichnungen bleiben unverändert.

Der Lauf verwendet weiterhin Source3 (`source_schema_version: 3`, `calculation_case_ref`). Die bestätigte Scope lautet `commercial_minijob_individual_month`. Quittung, historischer Quellenstand, Delta und PDF bleiben über die bestehenden unveränderlichen Archive gebunden. Das Ergebnis enthält Lohnsteuer, Arbeitnehmer-RV, Arbeitgeber-KV/RV und Umlagen; Arbeitgeber-Pauschsteuer beträgt in diesem Zweig 0. Mitarbeiterbeleg und Lohnkonto verwenden dieselben angenommenen Beträge. Tatsächliche Auszahlungen werden durch eine Berechnung nicht behauptet.

Abgeschlossene verifizierte v11-Läufe zählen in einer neuen Jahresprojektion mit ihrem individuell steuerpflichtigen Lohn, sobald der tatsächliche Zufluss durch die gebundene Zahlung belegt ist. Ein unbezahlter Lauf behauptet keinen Zufluss. Noch nicht abgeschlossene v10-/v11-Kandidaten sind im alten Jahresvorschauvertrag nicht zulässig. Einmal-/Mehrfachbezüge erhalten hierdurch keinen neuen Regelumfang.

## Ausdrückliche Korrektur eines bisher gesperrten Altfalls

Ein bereits angelegter aktiver v5-/Quellenvertrag-1-Gesamtfall kann unter seiner bestehenden ID in v11-/Quellenvertrag-3 korrigiert werden. Das ist nur möglich, wenn der historische Originalplan nachweislich nicht berechenbar ist, den Blocker `minijob_individual_tax` enthält und genau ein tatsächlich individuell besteuertes Minijobprofil bindet. Der neue Originalplan muss vollständig berechenbar sein. Die Monats- und Personenidentität bleiben gleich; neue Vorschau, aktuelle Ausgangsrevision und ein ausdrücklicher Korrekturgrund sind Pflicht. Unbekannte Vertragswechsel, Rückwärtswechsel und ein weiterhin gesperrter Zielplan werden abgewiesen.

Vor der Annahme werden in derselben Schreibtransaktion zunächst die vollständigen bestehenden fachlichen Archivvalidatoren für Lohn, Konto/Zahlung, Jahres-, Einmal- und Mehrfachfälle ausgeführt. Sie prüfen neben den Hüllhashes auch Originalquellen, Rechenergebnisse, Historien und Quittungen; eine korrekt gehashte, fachlich beschädigte Hülle ist kein gültiger Nachweis. Erst danach werden die Originale dieser Person nach der Fall-ID durchsucht. Jede bestehende Verwendung der Fall-ID, auch einer früheren oder später aufgehobenen Revision, sperrt diesen Vertragswechsel. Nicht prüfbare Originale gelten nicht als Nachweis fehlender Verwendung. Die globale PostgreSQL-Transaktionssperre verhindert, dass zwei gleichzeitige Korrekturen beide dieselbe Ausgangsrevision verbrauchen.

Die Umstellung ersetzt weder Originale noch Quittungen: Die neue Revision verweist auf den bisherigen `content_hash`; alte Details, Blocker, Quellen, Hashes und exakte Auftragswiederholungen bleiben unverändert abrufbar. Es gibt keine automatische Umstellung und keinen automatischen Lohnabschluss oder Zahlungsvorgang. Die Clients müssen diese Aktion als bewusste Korrektur mit Begründung darstellen.

## Historie und Prüfung

Die 32 zuvor vorhandenen 2026-Rechenkerne bleiben bytegleich; ihr Ausgangsstand ist unter `evidence/minijob-individual-v11-2026-11-09/historical-kernel-hashes.json` gesichert. Alte v1–v10-Sperren werden nicht entfernt. Die neuen Versicherungs- und Steuermerkmale werden ausschließlich im expliziten v11-Vertrag ausgewertet. Ungültige Unicode-Surrogate in neuen Prüftexten/Korrekturgründen führen vor der Hashbildung zu HTTP 400; unstrukturierte Identitätsdetails ebenso.

Die gemeinsame echte synthetische Fixture `app/test/fixtures/individual_minijob_v11.json` wird durch `scripts/generate-individual-minijob-fixture.py` mit unveränderten produktiven APIs erzeugt. Sie enthält RV-Pflicht, RV-Befreiung und die ausdrücklich begründete Korrektur eines gesperrten Altfalls einschließlich privater Originalmetadaten, Inputs, Vorschauen, angenommener Fälle/Läufe und Quittungen. Diese Daten ersetzen keine echte Geräteabnahme.

Implementierungsstand: Die unabhängigen 36 Steuervergleichsfälle stimmen überein. Die konkreten Fachketten-, HTTP-, PostgreSQL-/Restore- und Paketnachweise stehen mit unveränderten Ausgaben im [Evidenzverzeichnis](evidence/minijob-individual-v11-2026-11-09/). Browser-/App-Integration und Geräteabnahme sind eigene ausstehende Schritte dieses Backendkandidaten.
