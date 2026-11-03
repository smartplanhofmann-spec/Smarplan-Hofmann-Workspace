# Midijob 2026 – explizite Vollmonatsberechnung

Arbeitsstand 03.11.2026. Additiver Regelstand `de_2026_transition_monthly_pap_v3`; bestehende v1-/v2-Berechnungen, Profile, Quellhashes, Quittungen und archivierte PDF-/JSON-Ausgaben bleiben unverändert lesbar. Die neue Berechnung ist nur über eine vollständig bestätigte neue Profilfassung erreichbar. Sie ist keine amtliche Meldung oder Systemzulassung. Weitere Standardfälle aus [dem Lückenplan](CRM_ERP_LOHN_LUECKENPLAN_2026.md) bleiben eigenständige Entwicklungsaufgaben.

## Stabiler Profil- und API-Vertrag

Keine zusätzlichen Tabellen oder Endpunkte. `POST /business/payroll/profiles` verwendet weiterhin geschützten `source_file_id`, `confirmed:true`, Revision, Änderungsgrund und eigene Vorgangs-ID. Das reguläre Profil muss die beiden bisherigen monatlichen Steuerfelder enthalten; zusätzlich kann genau dieses vollständige Objekt gewählt werden:

```json
{
  "transition_assessment": {
    "status": "within_transition_area",
    "assessed_on": "2026-01-01",
    "regular_monthly_gross_minor": 100000,
    "forecast_months": 12,
    "foreseeable_one_off_payments": false,
    "note": "Belegte Grundlage der regelmäßigen Zwölfmonatsprognose"
  }
}
```

Das Beispiel ist synthetisch und kein vorgeschlagener Benutzerwert. Grenzen: Prognosemonat 60.301–200.000 Cent; Regeljahresentgelt exakt zwölfmal Prognosemonat; zwölf Prognosemonate; gültiges tatsächliches Prüfdatum, bei Speicherung nicht zukünftig; nichtleerer Vermerk mit höchstens 2.000 Zeichen. Der bestehende private Profilnachweis belegt Statusprognose sowie tatsächliche Kassenparameter. Monatliches Istentgelt stammt weiter aus dem belegten Vertrag und freigegebenen Quellen. Die Prognose wird weder daraus automatisch abgeleitet noch nachträglich in alte Profile eingefügt.

Vorhersehbare Einmalzahlungen lassen sich ausdrücklich als `true` dokumentieren; sie sperren diesen Vollmonatszweig mit `special_case:one_off_payment`. Mehrfachbeschäftigung und die übrigen noch nicht unterstützten Sonderfälle bleiben sichtbar gesperrt. Das Weglassen eines Pflichtfelds, eine halbe Prognose, unbekannte Felder oder widersprüchliche Jahresbeträge sind Eingabefehler, keine stillen Annahmen.

Die bisherigen Vorschau-/Abschlussbefehle binden weiterhin aktuelle Profil- und Monatsvorbereitungsrevisionen sowie die vollständige Quell-/Ergebnis-Prüfsumme. `accepted_scope` lautet im vollständigen neuen Fall `regular_transition_monthly`. Rechte bleiben `personnel.read` plus `personnel.write` für Profile beziehungsweise `personnel.approve` für Abschluss; Download zusätzlich `personnel.export`. Wiederholung prüft frische tatsächliche Rechte vor einer gespeicherten Quittung. Geänderte Quellen erfordern neue Vorschau und ausdrücklich bestätigte Korrektur; alte erfolgreiche Quittungen liefern ihr ursprüngliches Ergebnis.

`GET /business/payroll/rules` ergänzt `regular_transition_rules` und `regular_transition_rules_sha256`; bestehende Regelmetadaten ändern sich nicht. Es gibt keinen erforderlichen Client-Default und keine neue automatische Konten-/Entgeltzuordnung.

## Berechnungsdaten

Bestehende Brutto-/Steuer-/AN-/AG-/Umlagen-/Nettofelder behalten Namen und Centdatentyp. Im neuen Ergebnis steht zusätzlich `transition`, bei gesperrtem Ergebnis `null`, sonst:

| Feld | Bedeutung |
|---|---|
| `regime` | `within_transition_area`, `below_or_at_lower_limit` oder `above_upper_limit`; beschreibt tatsächliches Monatsentgelt, keinen automatischen Statuswechsel |
| `regular_monthly_gross_minor` | Unveränderte ausdrücklich belegte Statusprognose |
| `factor` | Exakter Parametertext `0.6619` |
| `total_assessment_minor`, `employee_assessment_minor` | Zwei separat berechnete und centgenau gerundete Bemessungsgrundlagen vor Zweig-BBG |
| `levy_assessment_minor` | Tatsächlich verwendete reduzierte RV-Basis beziehungsweise begrenzte Normalbasis oberhalb 2.000 EUR |
| `branch_bases` | Je `health_general`, `health_additional`, `pension`, `unemployment`, `care`: `total_minor` und `employee_minor` nach jeweiliger BBG |
| `care_adjustments` | `employee_before_adjustments_minor`, `childless_surcharge_minor`, `children_discount_minor`, `employee_base_percent`, `employer_normal_percent` |

Für ein innerhalb der Zone liegendes Istentgelt werden die beiden gesetzlichen Formeln mit G=603, U=2.000 und F=0,6619 ohne gerundete Kurzformelkoeffizienten gerechnet. Bei Istentgelt bis G gilt Gesamtbasis=F×Ist und AN-Basis=0; Kinderlosenzuschlag bleibt gegebenenfalls separat fällig. Über U gelten die normalen tatsächlichen Beitragsgrundlagen mit BBG. Ein prognostisch regelmäßiger Midijob wird dadurch nicht zum Minijob umklassifiziert. Ein tatsächlich niedriger Monat allein aktiviert den neuen Regelzweig nicht.

Gesamtbeiträge entstehen je Zweig durch Rundung des halben Beitrags und anschließende Verdoppelung; KV-Grund- und Zusatzbeitrag bleiben getrennt. Arbeitgeberanteil ist der Rest nach dem rechnerischen AN-Anteil. Sachsen verwendet den eigenen PV-Anteil. Kinderlosenzuschlag basiert auf der Gesamtbasis, Kinderabschlag auf der AN-Basis; beide werden separat gerundet. Der Kinderabschlag senkt ausschließlich AN und erhöht AG nicht. Oberhalb des Übergangsbereichs ist dieselbe zulässige getrennte PV-Rundungsmethode ausdrücklich Bestandteil dieser neuen Regelversion.

Die individuelle monatliche Lohnsteuer verwendet unverändert den geprüften PAP-2026-Kern auf dem tatsächlichen steuerpflichtigen Brutto; die reduzierte SV-Basis ist kein reduziertes Steuerbrutto. Einmalbezüge werden nicht in diesen Lauf hineingerechnet. Nettoberechnung löst keine Zahlung aus.

## Quellen und aufgelöste Abgrenzung

- [DRV, Übergangsbereich, Werte 2026](https://www.deutsche-rentenversicherung.de/DRV/DE/Experten/Arbeitgeber-und-Steuerberater/summa-summarum/Lexikon/U/uebergangsbereich): G/F/U, Formeln und neun unabhängige Bemessungspaare; siehe `test_payroll_transition_2026.DRV_BASES`.
- [BVV §2, Rechtsstand 01.01.2025, DRV-Rechtsportal](https://rvrecht.deutsche-rentenversicherung.de/SharedDocs/rvRecht/05_Normen_und_Vertraege/02_A-B/BVV/0002/0002_2025_01_01.html): gesetzliche Rechenschritte, Fälle bis zur Geringfügigkeitsgrenze, gesonderte Zuschläge/Abschläge.
- [GKV-Spitzenverband, Hinweise 31.03.2025, Abschnitt 3.3, Seiten 12/13](https://www.gkv-spitzenverband.de/media/dokumente/pflegeversicherung/grundprinzipien/2025-03-31_GH_Beitragssatzdifferenzierung_sPV.pdf): unabhängiges veröffentlichtes Beispiel mit Gesamtbasis 815,90 EUR, AN-Basis 545,71 EUR, AG-PV 19,56 EUR, AN vor Abschlag 9,82 EUR, Abschlag 1,36 EUR, AN danach 8,46 EUR. Diese Beispielbasen sind ausdrücklich aus 2025; sie prüfen die weiterhin geltende Beitragsfolge, nicht den 2026-Faktor.
- [Gemeinsames Rundschreiben 20.12.2022, insbesondere 4.3.3, 4.3.8, 4.3.9](https://www.kbs.de/SharedDocs/Downloads/DE/VersicherungsrechtBeitraegeMeldungen/Downloads/Uebergangsbereich_idF_20_12_2022.pdf?__blob=publicationFile&v=2): Beitragstragung sowie reduzierte Umlagebasis. U1/U2: Abschnitt 4.3.8 auf gedruckter Seite 37; Insolvenzgeldumlage: Abschnitt 4.3.9 auf Seite 38; unabhängige Zuordnungsbeispiele 26–28 auf Seite 57. Alle verwenden für den jeweiligen laufenden Übergangsbereichsfall die Gesamt-Bemessungsgrundlage, nicht die gesonderte AN-Basis oder pauschal das Istbrutto. Einmalentgelt bleibt für U1/U2 ausgeschlossen; solche Fälle sind in diesem Regelzweig insgesamt gesperrt. Historische Entgeltgrenzen/Faktoren/PV-Sätze daraus werden nicht übernommen.
- [DRV, aktuelle Erläuterung](https://www.deutsche-rentenversicherung.de/DRV/DE/Experten/Arbeitgeber-und-Steuerberater/Gleitzone-Uebergangsbereich/uebergangsbereich_gleitzone.html): 2026-Bereich, getrennte KV-Beiträge und Sachsen. Die dortige verkürzte Aussage zur Berücksichtigung von Kinderabschlägen beim AG-Abzug wird nicht als AG-Erhöhung umgesetzt: maßgebend sind BVV-Reihenfolge und das ausdrückliche GKV-Beispiel einschließlich unverändertem rechnerischem AN-Anteil für AG.

Die geprüfte PAP-Herkunft und die 258 jährlichen amtlichen Steuervergleichswerte bleiben in den bestehenden Lohn-Quellen und `test_payroll_pap_2026` festgehalten. Eine neue PAP-Implementierung wurde hierfür nicht erzeugt.

## Historie, Exporte und Geldfluss

Korrekturen führen neue Fassungen und Centdifferenzen einschließlich LSt/Soli/KiSt/Netto. Die Jahresansicht zählt nur die wirksame Monatsrevision; Korrekturdifferenzen werden nicht nochmals summiert. Monats-PDF, Jahres-CSV/PDF und vollständiges JSON enthalten die neue Regel und Bemessungsnachweise. Alte Ausgaben erhalten keine nachträglichen Midijobfelder.

Die bestehenden Lohnkonto-Identitäts-/Zahlungsnachweise und belegten Vorträge können vollständige v3-Ergebnisse verwenden. PayrollCash prüft dieselbe unveränderliche Rechnung erneut und übernimmt ausschließlich belegte tatsächliche Zahlungen. EÜR bekommt Netto und tatsächlich abgeführte AN-/AG-/Umlageanteile genau einmal; kein erfundener Bruttogeldfluss und keine Vorsteuer. Vergangene Zahlung bleibt auch bei späterer Berechnungskorrektur erhalten.

## Abnahme

Abnahme vom 03.11.2026, Backend eingefroren:

| Prüfung | Ergebnis | Nachweis |
|---|---:|---|
| Gesamte Lohn-Fachregression einschließlich 15 neuer Midijobfälle | 67/67, 18,423 s | `work/verification/midijob-payroll-regression.log` |
| Darin amtliche DRV-Bemessungsreferenzen | 9/9 Wertepaare | `test_payroll_transition_2026.DRV_BASES` |
| Darin unveränderte offizielle BMF-Jahresreferenzen | 258/258 Werte | `test_payroll_pap_2026` |
| Neue tatsächliche PostgreSQL-/MFA-/HTTP-Abnahme | 3/3, 11,193 s, keine Skips | `work/verification/midijob-postgres.log` |
| Historische Lohn-/Lohnkonto-/PayrollCash-PG-Regression | 9/9, 54,926 s, keine Skips | `work/verification/midijob-historical-postgres.log` |

Dateien: `test_payroll_transition_2026.py`, `test_business_payroll_transition.py`, `online/test_business_payroll_transition_pg.py`. Die Fachfälle prüfen unabhängige Zahlen, ausdrücklich belegte Wahl, Schwankungsmonate aus tatsächlicher freigegebener Arbeitszeit, Quelländerung, alte v2-Exporte, Korrekturen/Jahressummen, belegten Monatsvortrag und tatsächliche EÜR-Zahlungen. Eine spätere SV-Korrektur verändert bereits belegte tatsächliche Zahlungen und EÜR-Aufwendungen nicht. PostgreSQL prüft zusätzlich MFA/HTTP, verlorene Antwort/Wiederholung, Rechteentzug, zwei echte Verbindungen und Dump/Restore mit separater Operatorfreigabe. Nach technischer Restoreprüfung ist eine historische reine Berechnungsquittung lesbar; die tatsächliche Geldflussübernahme bleibt bis zur finanziellen Operatorfreigabe gesperrt. Der erste PG-Test wurde an genau diese vorhandene Trennung angepasst, ohne Produktregeln aufzuweichen.

Maschinenlesbare Datei-/Log-Prüfsummen: [CRM_ERP_LOHN_MIDIJOB_PRUEFUNG_2026-11-03.json](CRM_ERP_LOHN_MIDIJOB_PRUEFUNG_2026-11-03.json). Die inzwischen abgeschlossene [Clientabnahme](CRM_ERP_LOHN_MIDIJOB_CLIENTS.md) dokumentiert zusätzlich 37 Node-/41 Flutter-Tests, Flutter Analyze, den echten Midijob-Browserablauf einschließlich verlorener Antworten und die erneute vollständige bisherige Payroll→EÜR-Browserstrecke. Keine dieser technischen Prüfungen ist eine amtliche Fachzulassung.

Teilmonate, Entgeltfortzahlung, Einmalbezüge, Reise-Pauschalen und weitere im Lückenplan benannte Fallgruppen sind dadurch noch nicht abgeschlossen. Sichtbare Sperren bleiben bis zur jeweiligen eigenen Implementierung und Abnahme erhalten.
