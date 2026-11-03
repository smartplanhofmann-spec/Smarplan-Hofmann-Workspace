# Neuer Abrechnungsfall für Segmente, Ansprüche und Reise-Lohnwerte

Stand: 03.11.2026. `de_2026_segments_entitlements_v5` ist additiv in Schema, API, privaten Exportkatalog und Laufzeitpakete integriert. Tatsächliche Quellen → Vorschau → Fall → Lohnlauf → Identität/Zahlung → Cash/EÜR sowie PostgreSQL-Neustart und Dump/Restore sind geprüft. **Der Gesamtregelstand ist während der laufenden unabhängigen Client-/Komponentenabnahme noch nicht eingefroren.** P2 und die v1–v4-Kernmodule bleiben unverändert, einschließlich historisch bestätigter blockierter Pläne. Fachlich noch nicht abgedeckte Varianten bleiben ausdrücklich blockiert.

## Dateieigentum und Komposition

| Baustein | Zuständige Dateien | Ergebnis |
|---|---|---|
| Segmentierung und Entgeltzuordnung | `payroll_segments_2026.py` | reine Beschäftigungs-/Entgelt-/SV-Intervalle; fachliche Segmentgründe getrennt von technischen Profilzeilen |
| Anspruchsberechnung und private Belege | `payroll_entitlements_2026.py`, `business_payroll_entitlements.py` | versionierte Anspruchsfakten und getrennte Anspruchs-/SV-Intervalle |
| Reise-Lohnquelle | `travel_payroll_sources.py` | versionierter Adapter tatsächlicher bestätigter Reiseabrechnungen |
| Neuer privater Gesamtfall | `business_payroll_calculation_cases.py` | frische kanonische Quellenauflösung, unveränderliche Revisionen/Quittungen, Quellenintegrität |
| Gesamtplan und Rechnung | `payroll_calculations_2026.py` | expliziter Versionsdispatcher, v5-Plan und Netto-/Steuer-/SV-Komposition |
| Reise-Verarbeitungsnachweis | `payroll_travel_link.py` | schmale Bindung einer Reisequelle an den tatsächlich wirksamen v5-Lauf |
| Tatsächliche Pauschalsteuererfassung | `payroll_travel_recording.py` | eigener unveränderlicher Nachweis, atomar mit dem tatsächlichen Lohnlauf |
| Registrierung | Integration | DDL-/API-/Exportkatalog-/Paketlisten; erst nach stabilen Modulen |

P4 liefert den expliziten `payroll_entitlement_dispatch.build_entitlement_plan(snapshot, rule_version)` und `resolve_entitlement_case(actor, employee_id, ref, fresh=True)`. Historische Rekonstruktion reicht stets die gespeicherte Regel. Krankheitsfassungen v3/v4 werden über ihre disjunkten Anspruchsphasen komponiert; hinzugetretene Ursachen erzeugen weder doppeltes Ausfallentgelt noch einen neuen Anspruchsbeginn. Einzelpläne tragen `schema_version`, `rule_version`, `rules_hash`, `kind`, `source_hash`, `plan_hash`. Ihre Rechnungen werden nicht durch manipulierte P2-Vorbereitungen oder erfundene Projektarbeitszeit ersetzt.

## Eingabe des neuen Lohnlaufs

```json
{
  "source_schema_version": 3,
  "employee_id": "<32hex>",
  "calculation_case_ref": {
    "id": "<32hex>",
    "revision": 1,
    "content_hash": "<64hex>"
  }
}
```

Das ist ein vollständiger alternativer Eingabesatz. Brutto, Steuertage, SV-Tage, Beitragssummen oder ein gewünschter Steuerbetrag werden nicht aus Client-Eingaben übernommen. Abschluss ergänzt die bisherigen technischen Felder `request_id`, `preview_hash`, `accepted_scope`, `confirmed`, `revision`, gegebenenfalls `id`/`correction_reason`. Der Fall enthält Regelname und Quellenvertragsversion; der Lohnlauf darf sie nicht stillschweigend auf den neuesten Stand wechseln.

## Neuer privater Gesamtfall

Registrierte Routen:

- `GET /payroll/calculation-cases?employee_id=…&month=…`
- `GET /payroll/calculation-cases/sources?employee_id=…&month=…`
- `GET /payroll/calculation-cases/{id}` sowie `/{id}/history`
- `POST /payroll/calculation-cases/preview`
- `POST /payroll/calculation-cases`

Alle Rohquellen benötigen frisches `personnel.read`; Bestätigung benötigt zusätzlich `personnel.approve`, aktuelle Personenzuordnung und Online/MFA. `void` erzeugt eine neue historische Revision, entfernt keine Quelle. Bereits angenommene Quittungen bleiben nach Modulpausierung mit frischen Rechten wiederholbar; neue Verarbeitung bleibt gesperrt. Die schmale eigene Mitarbeiteransicht ist ein separater Projektionspfad und erhält keine Rohfakten.

Der neue Fallumschlag bindet `employee_id`, `employee_revision`, `rule_version`, `source_contract_version: 1`, `status`, `details`, `source_file_ids`, `confirmed`, technischen Nonce/Vorgänger und Korrekturgrund. `details` enthält:

```text
month
period_case_ref                   # vorhandener kanonischer P2-Basisfall, auch blockiert zulässig
employment_terms_refs[]            # vollständige tatsächliche Beschäftigungsepisoden
profile_refs[]                     # jede für die Episoden relevante aktuelle Originalfassung
identity_refs[]                    # Identität/Steuermerkmale für die tatsächlichen Teilzeiträume
segment_events[]                   # explizite fachliche Ereignisse mit Quellen davor/danach
thirty_day_rule                    # null oder ausdrücklich belegte konkrete Vertragsverteilung
entitlement_case_refs[]            # P4-Fakten, keine freien Anspruchsbeträge
travel_settlement_refs[]           # vollständige unveränderliche Reiseabrechnungen
flat_tax_decision                  # null oder belegter Auftrag zur 25%-Reisepauschalierung
verification_note
```

Ein `segment_event` enthält `kind`, `effective_from`, `before_profile_ref`, `after_profile_ref`, `source_file_ids`, `reason`. Steueränderung, Versicherungs-/Beitragsstatus, Mitgliedschaft und reine Datenkorrektur werden unterschieden. Der Server prüft den tatsächlichen Feldunterschied und die fachliche Wirkung. Ein frei gewählter Ereignisname kann keinen falschen SV-Split legitimieren. Entgeltvertragsgrenzen ergeben sich aus den tatsächlichen Vereinbarungen; sie erzeugen nicht selbst eine neue Teil-BBG.

Die Ereignistaxonomie ist im normalisierten DTO festgelegt. Tatsächliche Änderungen von SV-Merkmalen innerhalb einer Beschäftigungsepisode bleiben bis zur fachlichen Zuordnungsregel blockiert. Der Entgelthelfer unterstützt bei ausdrücklichem Vertragsnachweis `actual_days_capped_per_claim`: tatsächliche Anspruchstage, höchstens30, geteilt durch30; ein durchgehender voller Monat behält den vollen Anspruch. Das ist keine automatische arbeitsrechtliche Standardregel für sämtliche Verträge. Bei fehlender eindeutiger Vertragsregel bleibt ein präziser Blocker bestehen.

Der gespeicherte `sources`-Snapshot enthält vollständig den P2-Basisfall, zusätzlich aufgelöste Beschäftigungs-/Profil-/Identitätsquellen, Originalmetadaten, die normalisierten Segmentereignisse, P4-Fakten samt Plänen und Reiseadapterergebnisse. Die Zugehörigkeit zu Person/Monat wird an den tatsächlichen kanonischen Originalen und historischen Personalzuordnungen geprüft. Hash-Konsistenz allein genügt nicht. Neue Verwendung prüft Aktualität; historischer Replay verwendet genau die damaligen Quellen.

Vorschau liefert `source_snapshot`, `source_hash`, `plan`, `preview_hash`, `can_confirm`, `can_calculate` und frische Fähigkeiten. Bestätigung speichert genau diese geprüfte Fassung. Die unveränderlichen Quittungen binden den ursprünglichen Requesthash und die tatsächlich gespeicherte Fallrevision. `accepted_command` bleibt ausschließlich im privaten Datenbank-Payload; es wird wie bei P4 nicht in API-DTOs oder verschachtelten Quellen publiziert. Jede Integritätsprüfung vergleicht trotzdem das tatsächliche Originalkommando mit seiner konkreten Annahmequittung.

Neue Fälle müssen alle aktuellen aktiven Beschäftigungsepisoden und P4-Fakten binden, deren belegter Zeitraum den Monat überschneidet. Weglassen einer früheren Episode nach Wiedereintritt oder einer bekannten unbezahlten Anspruchsphase ist kein Umgehungspfad. Spätere, für den Monat nicht einschlägige Fakten werden nicht erzwungen. Der alte bestätigte Fall bleibt unverändert wiederholbar.

## Rechner und historischer Dispatcher

Der Gesamtplan hält Beschäftigung, Anspruch/Entgelt, Steuer-LZZ, SV-Perioden, Merkmale und Zahlung getrennt. Er bindet jeden Komponentenregel-/Quellenhash und enthält fachliche Blocker. Seine Hashbildung schließt den eigenen Hash und rollenabhängige Fähigkeiten aus.

Der Dispatcher wählt ausschließlich nach dem gespeicherten `rule_version` und `source_contract_version`. Alte P2/v4-Pläne werden weiterhin nur mit ihrem v4-Builder geprüft. Unbekannte Regeln scheitern explizit. Sobald v5 gespeichert und eingefroren ist, wird eine neue fachliche Unterstützung nicht nachträglich unter derselben Version ergänzt; sie braucht einen weiteren Regelstand. Dies gilt auch für ursprünglich blockierte Fälle.

Die Integration erhält weiterhin genau einen wirksamen Lauf je Person/Monat. Segment- und Anspruchspositionen werden nicht als parallel zählende Monatsläufe gespeichert. Identitätsnachweise decken ihre tatsächlichen Merkmals-/Beschäftigungsintervalle; Steuer-Endmerkmale werden auf ihren tatsächlichen Gültigkeitstag geprüft, nicht pauschal auf jeden Tag vor ihrer Wirksamkeit.

## Reiseadapter und eindeutige Auszahlung

Der Travel-Owner stellt bereit:

```text
travel_payroll_source(office, actor, settlement_ref, month) -> {
  kind: "travel_allowances", employee_id, month,
  settlement_ref, rule_version,
  tax_free_external_minor,
  flat_taxable_payroll_minor,
  individual_taxable_payroll_minor,
  benefit_in_kind_non_cash_minor,
  letter_m,
  allocations: [{key, month, amount_minor, kind, source_hash}],
  source_hash
}
```

Die Bestätigung der tatsächlichen Reisefakten ist von der vollständigen Lohnverarbeitung getrennt. Deshalb kann der neue Gesamtfall eine bestätigte, noch nicht lohnverarbeitete Reisequelle binden, ohne einen zirkulären Freigabebedarf zu erzeugen. Gemischte Reiseauszahlungen bleiben bis zum tatsächlichen Lohnnachweis gesperrt.

Die Eigentümerschaft der Geldbeträge ist verbindlich:

| Betrag | Berechnung | Einmalige Auszahlung |
|---|---|---|
| `tax_free_external_minor` | steuerfreier Reisebetrag, bei Bedarf M-Nachweis | bestehende Reiseerstattung/TravelCash; nicht zusätzlich im Lohnnetto |
| `individual_taxable_payroll_minor` | individuell steuerpflichtige Erstattung, SV-Behandlung ausdrücklich prüfen | neue Lohnzahlung |
| `flat_taxable_payroll_minor` | eigener nachgewiesener 25%-Pauschalsteuerzweig einschließlich seiner Nebensteuern und SV-Behandlung | neue Lohnzahlung, kein zweiter TravelCash-Betrag |
| `benefit_in_kind_non_cash_minor` | einschlägiges Steuer-/SV-Brutto und gleich hoher Sachbezugs-Nettoabzug | keine zweite Barauszahlung des Sachbezugs |
| `letter_m` | Lohnkonto-/Jahresmerkmal nach tatsächlicher Mahlzeit | keine Auszahlung |

Erstattungsmehrbeträge werden dem ausdrücklich gewählten Zuflussmonat zugeordnet; Sachbezug/M folgen dem tatsächlichen Mahlzeitenmonat. Keine freie Verteilung auf Reisetage. Alle Betragsschlüssel werden genau einmal gebunden. Tatsächliche Zahlung und geplanter Zuflussmonat müssen zusammenpassen; Abweichungen erfordern eine nachvollziehbare Korrektur.

`assert_travel_processed(office, actor, settlement_ref, month, source_hash)` prüft frischen privaten Lesezugriff, den wirksamen vollständig angenommenen v5-Lauf, die exakte Reise-/Adapterfassung und historische Quellenintegrität. Es liefert lediglich `run_ref` und einen `processing_hash`, keine Rohakte. Mehrmonatige Allocations benötigen passende Nachweise je betroffenem Monat. Eine spätere Laufkorrektur kann den aktuellen Verarbeitungsnachweis entwerten; historische Zahlungen/Originale werden dadurch nicht verändert.

Der 25%-Steuerzweig einschließlich Nebensteuern ist in eigenen unabhängigen Quellen-/Rechentests und tatsächlichen Finalisierungsfällen geprüft. Echte 4EUR-Mehrerstattung in BW mit vereinfachtem Kirchensteuersatz erzeugt 100Cent Lohnsteuer, 5Cent Solidaritätszuschlag und 4Cent Kirchensteuer. Die zulässige Arbeitnehmerübernahme wird als belegter 109Cent-Nettoabzug geführt. Sachbezug oberhalb60EUR, M ohne zusätzlichen Lohn-Cash, individuelle Mehrerstattung und getrennte steuerfreie TravelCash-Erstattung sind tatsächliche Domainfälle. Reisefassungen v2 und v3 werden jeweils explizit nach ihrer gespeicherten Regel geprüft.

## Arbeitgeberweite Steuerentscheidung und atomare Erfassung

`GET/POST /payroll/travel-tax-policies`, `POST /payroll/travel-tax-policies/preview`, `GET /payroll/travel-tax-policies/{id}` und `/{id}/history` verwenden denselben unveränderlichen Fallvertrag mit `employee_id:null`. `GET /payroll/travel-tax-policies/sources` benötigt globales frisches `personnel.read`; es liefert aktuelle geschützte Personaloriginal-Metadaten als `files`, kanonische `file_references`, aktuelle `policies` und Fähigkeiten. Originaldateiinhalte werden über den bestehenden geschützten Personaloriginalpfad gelesen.

Der Policy-Datensatz bindet Anmeldezeitraum, Bundesland, regionale Kirchensteuersatzwahl, einheitliche Methode für den betrieblichen Tatbestand, Kostenübernahme und Originale. Einzelfallentscheidungen enthalten `policy_ref`, tatsächliche `church_membership_evidence`, gegebenenfalls `employee_deduction_file_ref`, `tax_certificate_file_ref`/`tax_certificate_issued_on` sowie `record_on_finalize:true`. Die amtliche Arbeitnehmererklärung bzw. ein belegter allgemeiner Kirchensteuersatz sind ausdrückliche Nachweisarten; unbekannte Zugehörigkeit wird nicht als steuerfreies Nichtmitglied erfunden.

Die Vorschau bindet den vorgesehenen Erfassungstag. Im gespeicherten Originalauftrag bleibt `recording_context.actual_recorded:false` erhalten. **Erst** `Payroll.finalize` schreibt nach dem tatsächlichen Lauf in derselben Transaktion die unveränderliche Zeile `business_payroll_travel_tax_recordings`. Sie bindet Run-/Fall-/Policyreferenz, alle Reisequellenhashes, Steuerbeträge, Kostenübernahme, tatsächlichen Erfassungstag und Ersteller. Jeder Fehler rollt auch Lauf und Annahmequittung zurück; der identische Request erzeugt nur eine Zeile. Ein Datumswechsel erfordert eine neue überprüfte Fallrevision.

Der Nachweis bedeutet `actual_recorded:true`, `actual_payment_created:false`, `statutory_transmitted:false`. Er erzeugt weder Geldfluss noch amtliche Übermittlung. Jeder Source3-Lauf-Read, Export, Replay, Zahlungsnachweis, Cash-Quellenzugriff und Restore-Integritätslauf prüft ihn gegen das wirkliche Original. Eine fehlende oder umgehashte Zeile wird auch dann erkannt, wenn noch keine Zahlung existiert. Ein Void der Policy entfernt nicht die Methodenbindung eines wirksamen tatsächlichen Lohnlaufs. Historische Laufkorrekturen behalten den alten Erfassungsnachweis; nur der aktuelle Lauf erteilt eine aktuelle Reiseverarbeitungsfreigabe.

## Zahlung, Lohnkonto und offene Varianten

Tatsächliche Lohnzahlungen müssen `net_minor - net_deductions_minor` entsprechen. Der Zahlungsnachweis archiviert zusätzlich alle `sources.identity_intervals` mit Zeitraum, Profilreferenz und vollständiger tatsächlicher Identitätsfassung. Der ausgewählte Endmerkmalsnachweis ersetzt nicht die anderen Beschäftigungsabschnitte. Bei steuerpflichtigen Reise-Mehrerstattungen wird ein abweichender tatsächlicher Zuflussmonat gesperrt, bis eine neue belegte Zuordnung vorliegt.

Das Jahreskonto summiert `net_deductions_minor`, stellt alle datierten Identitätsabschnitte dar und führt `recorded_travel` mit M und den getrennten Reisearten sowie `recorded_unpaid_periods`. Überholte Identitäten einer inzwischen korrigierten Profilrevision bleiben im Archiv, erzeugen aber keinen erfundenen zusätzlichen Beschäftigungszeitraum. Tatsächlicher Austritt15.–20.10. und Wiedereintritt25.–31.10. sind bis zur Zahlung und zum vollständigen unterstützten Lohnkonto geprüft.

Unbezahlte Tage setzen derzeit `unpaid_statutory_marker_requires_evidence`: die gesetzliche U-Aufzeichnung ist eine echte verbleibende Funktionslücke, siehe [U-Merkmalsvertrag](CRM_ERP_LOHN_U_MERKMAL_VERTRAG_2026.md). Weitere konkrete Blocker betreffen untermonatige SV-Status-/Kassenänderung, Reise beim Minijob, Übergangsbereich mit Anspruchs-/Reiseentgelt, nicht belegte Mehrperioden-Reisezuordnung und die nicht unterstützten allgemeinen Sonderfälle. P5-Einmalbezüge erhalten eine getrennte neue Gesamtregel; sie ändern v5 nicht nach dessen Freeze.

## Prüfbare Integrationskriterien

Vor Aktivierung werden echte P3b/P4-/Reisequellen durch Vorschau, Bestätigung, Laufkorrektur, Lohnkonto, tatsächliche Zahlungen, Jahresfassung, Cash/EÜR und Bank verfolgt. Rechenwerte erhalten unabhängige Erwartungen. Historische v1–v4-Originale einschließlich damals blockierter P2-Fälle bleiben exakt gleich. Zwei echte PostgreSQL-Verbindungen, Rechteentzug vor Erstaufruf und Replay, Lost-ACK in beiden Clients, Offline-Sperre, Neustart und Dump/Restore gehören zum Gesamtstand. Die weitere Ausarbeitung erfolgt ohne Änderungen an eingefrorenen v4-Regeln.
