# Einmalbezüge: mehrere Ansprüche und getrennte tatsächliche Zahlungstage

Nachtrag vom selben Tag: Die inzwischen durchgeführte [amtliche Quellenprüfung](CRM_ERP_LOHN_MEHRFACHBEZUEGE_QUELLEN_2026.md) präzisiert diesen Plan. Insbesondere werden Einmalzahlungen desselben Monats im ersten Quartal für die Märzklausel gemeinsam geprüft; die unten skizzierte Ereignisfolge darf dabei keine unabhängigen SV-Einzelentscheidungen treffen. Die steuerliche Untermonatsgruppierung bleibt ausdrücklich offen.

Stand: 04.11.2026. Unabhängige Bestandsaufnahme und nächster Umsetzungsschritt; noch keine Implementierungs- oder Produktivfreigabe. Gelesen wurden das vollständige `CRM_ERP_Gesamtziel.txt` sowie die unten bezeichneten Rechen-, Quellen-, Lauf-, Jahres-, Lohnkonto-, Cash- und Clientverträge. Für dieses Dokument wurden keine Produktdateien geändert und keine neuen Tests ausgeführt. Vorhandene Tests werden als nachlesbare Spezifikation genannt, nicht als in dieser Bestandsaufnahme erneut bestanden ausgegeben.

## 1. Ergebnis und Abgrenzung

Der aktuelle Source4/v6-Vertrag verarbeitet **einen konkreten Einmalanspruch innerhalb einer monatlichen Gesamtberechnung**. Mehrere Nettozahlungsteile sind vorhanden; im Source4-Fall müssen aber sämtliche Teile, einschließlich bereits gezahltem laufendem Lohn, auf den gebundenen Bonuszuflusstag fallen. Ein anderer Bonus desselben Monats wird ausdrücklich gesperrt. Diese Schutzprüfungen einfach zu entfernen wäre fachlich falsch: Der aktuelle Vertrag könnte den ersten Bonus aus der Monatsrechnung verlieren und besitzt keine Zuordnung von tatsächlichen Zahlungsteilen zu laufendem Lohn oder einzelnen Bonusansprüchen.

Der kleinste zusammenhängende Ausbau besteht deshalb aus einer additiven, versionierten Monatskomposition mit mehreren identifizierbaren Bonuskomponenten **und** einem privaten Zahlungszuordnungsvertrag. Die bestehende monatliche Laufidentität mit Korrekturrevisionen bleibt erhalten. Es entstehen keine parallelen vollständigen Monatsläufe, die laufenden Lohn mehrfach zählen.

Die gerade ergänzte Übernahme früherer Source4-Läufe in die Jahresbasis ist bereits Bestand dieser Analyse. `_project_run`, `_compact_run`, `_relevant_run` und die Source4-Jahresprojektion werden hier nicht als neu zu entwickelnde Jahresbasis beschrieben. Der Backend-Verantwortliche bestätigt, dass die Sperren für einen zweiten Anspruch im selben Monat und unterschiedliche Zahlungstage bewusst bestehen bleiben.

Bezug zum Gesamtziel: Abschnitte 8, 9 und 14 D verlangen belegte Geldbewegungen, reproduzierbare Lohnberechnungen und nachvollziehbare Korrekturen. Das Gesamtziel wird durch diesen Ausbau nicht auf den heutigen Rechenumfang reduziert. Insbesondere ist die Source4-Komposition heute nur für `regular_standard_oneoff` abschließbar; Mini-/Midijob- und weitere Versicherungsfälle bleiben eigene offene Entwicklungspakete.

## 2. Tatsächlicher Vertrag und konkrete Engstellen

| Bereich | Gelesener Bestand | Konsequenz für den nächsten Schritt |
| --- | --- | --- |
| Rechenkern | `backend/payroll_oneoff_composition_2026.py`, `calculate_oneoff_source`: `de_2026_oneoff_composition_v6`, Quellenvertrag 1, genau `one_off_earning`, `annual_tax_forecast` und `one_off_details`. Die laufende v5-Rechnung wird einmal übernommen und um diesen Anspruch ergänzt. | Eine bloße Liste im Formular reicht nicht. Die Steuer-/SV-Quellen und Ergebnisse müssen je Bonus bzw. fachlich bestimmter Zuflussgruppe gebunden sein. |
| Fälle | `backend/business_payroll_oneoff_cases.py`, `normalize_details`, `identity_key`, `_snapshot`: Identität `earning:<id>`; beim frischen Quellenaufbau wird ein weiterer anderer Anspruch im bereits Source4-abgerechneten Monat mit 409 abgewiesen. | Neuer Monatsfall benötigt eine eigene Identität und die vollständige Menge bereits gebundener Ansprüche. Alte Einzelfallidentität nicht umdeuten. |
| Laufadapter | `backend/payroll_oneoff_runs.py`, `prepare`, `calculate_run_source`, `verify_record`: Source4-Eingabe enthält genau `one_off_case_ref`; historische Quellen werden gegen tatsächliche Originalereignisse nachgerechnet. | Neuer Adapter mit explizitem Versionszweig; Source4 bleibt unverändert lesbar und nachrechenbar. |
| Monatsrevision | `backend/business_payroll.py`, `finalize`: nur ein Lauf pro Mitarbeiter/Monat, spätere Änderung als Revision; Source4 darf nicht zu bloß laufendem Lohn zurückwechseln. | Neue Boni erweitern dieselbe Monatsrevision. Der ältere Anspruch darf dabei nicht verschwinden. |
| Verbrauch | `business_payroll_oneoff_consumptions`: Primärschlüssel `(run_id, run_revision)`, erster Eigentümer je `(employee_id, claim_identity_key)`; `record_run_consumption`/`validate_run_consumption` binden einen Anspruch je Revision. | Mehrfachverbrauch braucht ergänzende Kindzeilen je Komponente, keine Aufweichung der alten Einzelfallquittung. |
| Jahresbasis | `backend/business_payroll_annual_basis.py`, `_project_run`: laufende v5-Werte getrennt, aber genau ein `one_off_payment`; tatsächliche Zahlung vollständig am Bonusdatum erforderlich. `_relevant_run` ersetzt mit dem aktuellen laufenden Fall den gesamten eigenen Monat. | Im neuen Vertrag laufende Monatsperiode einmal verwenden und frühere Boni desselben Monats zusätzlich behalten. Ein pauschales Ausfiltern des eigenen Monats würde sie verlieren. |
| Jahresarithmetik | `backend/payroll_annual_basis_2026.py`, `build_annual_plan`, und `backend/payroll_oneoff_2026.py`, `annual_social_room`: frühere Bonusbasen werden abgezogen; Einmalquellen werden nach `source_ref.id` dedupliziert. Bisherige interne Bonusquelle ist die Laufreferenz. | Zwei Bonuszeilen mit derselben Monatslaufreferenz sind keine zulässige neue Darstellung. Jede Komponente braucht eine stabile, belegte eigene Referenz, zusätzlich zur Laufreferenz. |
| Zahlungsnachweis | `backend/business_payroll_accounts.py`, `_payment_fields`, `_normalize`, `save`: Zahlungsteil hat nur `paid_on`, `amount_minor`, `payment_reference`; Summe entspricht vollständigem berechnetem Auszahlungsnetto. Source4 verlangt alle Tage gleich `receipt_date`. | Die Zahlung enthält derzeit keine fachliche Aufteilung. Getrennte Tage benötigen eine ausdrückliche Zuordnung; Bruttozufluss darf nicht aus Nettoanteilen geschätzt werden. |
| Cash/EÜR | `backend/payroll_cash_sources.py`, `part_key`, `require_preserved_actual_net_parts`, `Sources.account/build`; `backend/business_payroll_cash.py`, `_prepare`: echte Teile können einzeln übernommen werden; alte Teile bleiben durch Tag/Referenz/Betrag geschützt. Öffentliche Geldbewegungen werden nach Datum und Richtung zusammengefasst. | Diese Geldflusslogik wiederverwenden. Komponenten und private Jahresquellen bleiben im privaten Adapter; keine erneute Gesamtübernahme bereits gezahlten Lohns. |
| Nachweise | `backend/payroll_ledger.py` erzeugt `recorded_one_off_payments`; `backend/business_payroll_statements.py` erzeugt bislang eine `one_off_summary` in Arbeitnehmerfassung 3. | Neue versionierte Listen, Summen und Korrekturbezüge erforderlich; persönliche Jahresoriginale gehören weiterhin nicht in die Arbeitnehmerausgabe. |

Bestehende Spezifikationen zeigen die Grenzen ausdrücklich: `test_actual_receipt_date_is_not_a_free_payment_date_and_cannot_erase_claim`, `test_paid_v5_original_part_is_preserved_and_only_new_bonus_difference_becomes_cash` und `test_paid_v5_part_cannot_be_moved_to_a_different_bonus_receipt_date` in `backend/test_business_payroll_oneoff_runs.py`; `test_second_claim_same_month_does_not_hide_first_bonus` in `backend/test_business_payroll_oneoff_annual.py`.

## 3. Unveränderliche Altverträge

Neue Versionsnamen sind ein Vorschlag, noch keine registrierten Fähigkeiten: **Source5 / `de_2026_oneoff_month_v7` / Quellenvertrag 1** für die Mehrfachkomposition. Vor Registrierung noch einmal auf Kollisionen mit paralleler Entwicklung prüfen.

Unverändert bleiben die tatsächlichen alten Quellen, Regel-/Plan-/Inhaltshashes und Berechnungssemantiken von Source1–4, insbesondere v5 und `de_2026_oneoff_composition_v6`. Das gilt auch für alte Einmalverbrauchsquittungen, Jahresbasis-v1-Snapshots einschließlich `source4_annual_reference_v1`, Zahlungsnachweise, Cash-Batches, gespeicherte PDF-Dateien und Exporte fest gebundener Revisionen. Die neuen Fähigkeiten dürfen alte Quellen nicht nachträglich umformen.

Für neue Vertragszweige darf Dispatcher-Code ergänzt werden. Ein neuer Jahresprojektions- oder Zahlungsleser muss am gespeicherten Vertrag erkennbar sein; bislang unversionierte Zahlungsdetails gelten ausdrücklich als Altvertrag 1. Alte Validatoren dürfen nicht einfach die bisher verbotenen Formen akzeptieren. Bestehende Clients müssen unbekannte Vertragsversionen sichtbar ablehnen, bis der passende Client ausgeliefert wurde.

Die v7-Quellen können einen existierenden Source3- oder Source4-Lauf als Vorgänger referenzieren. Dabei ist nachzuweisen, dass bereits gebundene Ansprüche weiterhin zum selben Monatslauf gehören. Alte Source4-Quittungen bleiben stehen; die neue Verbrauchsprüfung berücksichtigt deren Eigentümerschaft. Eine neue Tabelle allein mit einer isolierten UNIQUE-Prüfung würde einen bereits in Source4 verbrauchten Anspruch sonst erneut zulassen.

## 4. Kleinster fachlich zusammenhängender Erweiterungsvertrag

### 4.1 Monatsfall und deterministische Komponenten

Neuer privater Monatsfall, beispielsweise in `business_payroll_oneoff_months.py`, mit einem laufenden `calculation_case_ref`, dem tatsächlichen Vorgängerlauf, vollständigen Originalreferenzen und einer Liste eindeutig identifizierter Anspruchskomponenten. Jede Komponente bindet ihren `one_off_earning_ref`, den geplanten Zuflusstag, aktuelle/Vorjahresbasis, Steuergrundlage und die belegte Zuordnungsentscheidung. Die bestehende `one_off_earning`-Erfassung kann wiederverwendet werden; ihr bisheriger Inhalt wird nicht umgeschrieben.

Eine Komponente hat eine stabile Identität aus dem tatsächlichen Anspruch, keine Listenposition und keinen zufälligen neuen Schlüssel bei jeder Korrektur. Die neue Ergebnisliste enthält je Komponente oder geprüfter Zuflussgruppe mindestens Brutto, STS/SOLZS/BKS bzw. Kirchensteuer, AN-/AG-Beiträge, Umlagen, Steuerjahr, SV-Jahr, konkrete Zuordnungsperiode, verbrauchte Beitragsbasen und Nettoanteil. Die laufende Rechnung und ihre Nettoabzüge werden nur einmal addiert. Gesamtbeträge sind exakte Cent-Summen der ausgewiesenen Teile; fertige Steuer- oder SV-Summen aus dem Client sind keine Eingabe.

Der neue reine Berechner verwendet die bereits geprüften unteren Bausteine `annual_social_room`, `select_one_off_assignment`, `calculate_regular_one_off_contributions` und `calculate_standard_one_off_tax`, soweit deren festgeschriebener Umfang passt. Er ruft nicht mehrfach v6 auf und summiert dessen vollständige Monatsnettos. Das würde laufenden Lohn und seine Abzüge mehrfach erfassen.

Für mehrere Zuflussereignisse wird eine reproduzierbare Folge gebildet. Nach jedem Ereignis werden seine tatsächlich ermittelten Beitragsbasen ausschließlich im zugeordneten SV-Jahr verbraucht und seine für die Folgeberechnung relevanten sonstigen Steuerbezüge fortgeschrieben. Diese Zustände bleiben getrennt: Märzklausel 2025 bedeutet nicht Steuerjahr 2025. Der neue Schrittzustand bindet Anfangsjahresquelle und vorherige Komponenten; historische Originalpläne werden dafür nicht verändert.

**Fachliche Vorbedingung:** Behandlung mehrerer Bezüge am selben Tag, deren Gruppierung und Rundung ist vor Implementierung anhand der unter Abschnitt 7 genannten Quellen festzulegen. UUID-/Eingabereihenfolge ist keine steuerliche Regel. Belegte Gruppen müssen unter Umordnung ihrer Eingabeliste dasselbe Ergebnis ergeben. Geplante Komponenten innerhalb einer gemeinsamen Vorschau und bereits tatsächlich zugeflossene Vorgänger sind im Quellenvertrag unterscheidbar; eine Planung wird nicht zur erfundenen Zahlung.

### 4.2 Atomare Eigentümerschaft und Korrektur

Neue append-only Verbrauchszeilen mindestens mit `(run_id, run_revision, component_key)`, exakter Anspruchsreferenz, Fallreferenz, Zuordnung, Beträgen und Vorgängerbezug. Ein Anspruch darf über alte und neue Tabellen hinweg nur einem Monatslauf gehören; spätere Revisionen dieses Laufs dürfen ihn erneut abbilden. Frische Quellenprüfung, Vollständigkeitsprüfung und Reservierung sämtlicher Komponenten erfolgen gemeinsam in der vorhandenen Transaktion/PG-Sperre.

Neue Revisionen enthalten alle weiterhin wirksamen ursprünglichen Komponenten. Eine Korrektur des ersten Bonus muss die davon abhängigen späteren Berechnungsschritte neu prüfen; nur den letzten Bonus auszutauschen genügt nicht. Originalauszahlungen werden dabei weder verschoben noch still verrechnet. Entfernen/Stornieren eines bereits gebundenen Anspruchs benötigt einen eigenen fachlich geprüften Korrekturfall; ein ausgelassenes Listenelement ist keine Stornierung.

Betroffen sind der neue Fallresolver/Verbrauchsvalidator sowie die Versionszweige in `Payroll._prepare`, `_calculate_source`, `_verify_calculation_record`, `finalize`, Integritätsprüfung, Schema-/Export-/Restore-Registrierung. Die vorhandene Ein-Lauf-pro-Monat-Regel bleibt erhalten.

### 4.3 Tatsächlicher Geldfluss mit privater Zuordnung

Neuer Zahlungsquellenvertrag 2 neben dem alten `payment`-Vertrag. Er referenziert die exakte aktuelle Monatsrevision und führt weiter die echten Transaktionen mit Datum, Betrag und Originalreferenz. Zusätzlich ordnet er Centanteile ausdrücklich den stabilen Komponenten `running` und `one_off:<Anspruch>` zu. Eine echte Sammelüberweisung darf mehrere Komponenten decken; sie bleibt trotzdem eine einzige Transaktion. Mehrere Bankteile derselben Komponente dürfen nicht zu mehrfachen Bruttozuflüssen werden.

Die Zuordnung erfüllt zwei unterschiedliche Abstimmungen: je Transaktion Summe der Zuordnungen gleich tatsächlicher Transaktionsbetrag; je Komponente dokumentierter Erfüllungsstand gegen den aus der Rechnung hergeleiteten Nettoanspruch. Bekannte alte Zahlungsteile werden unverändert referenziert/übernommen. Ein bereits gezahltes Source3-Netto vom 30.10. und ein Bonusnetto vom 31.10. können damit in derselben neuen Monatsrevision stehen, ohne den 30.10. umzudatieren.

Noch nicht gezahlte Restbeträge sind ausdrücklich offen, erzeugen keinen Cash-Vorgang und keinen nachgewiesenen Steuerzufluss. Der neue Vertrag muss solche Zwischenstände darstellen können, damit ein früher tatsächlich gezahlter Bonus nicht erst nach späterer Auszahlung sämtlicher anderer Monatskomponenten belegbar wird. Das ist ein eigener, strikt versionierter Zustand; die alte Prüfung `Summe aller Zahlungen = gesamtes Monatsnetto` darf nicht global entfallen.

Für den ersten Ausbau gilt als klar zu prüfende Unterstützungsgrenze: eine vollständig zugeflossene Bonuskomponente hat genau einen tatsächlichen Zuflusstag; beliebige Teilzuflüsse desselben Anspruchs über mehrere Tage brauchen eine zusätzliche fachliche Aufteilung. Tatsächliche Teilzahlungen dürfen dokumentiert werden, bleiben für eine daraus noch nicht belegbare Steuerjahresprojektion aber ungeklärt. Nettoanteile werden niemals proportional in Steuerbrutto umgerechnet. Aufrechnung, Nullnetto und Sachleistungszufluss sind keine nachgewiesenen Bankzahlungen und benötigen ihre eigene geprüfte Erfüllungsquelle.

`PayrollAccounts._normalize/_payment_fields/save`, `Sources.account/build` und die Integritätsleser erhalten dafür explizite neue Zweige. `part_key`, die Prüfung bereits übernommener Originalteile und das Verbot doppelter Cash-Übernahme bleiben erhalten. In öffentlichen Buchhaltungs-/Bankdaten erscheint weiterhin nur der erforderliche Geldfluss; Anspruchsreferenzen und Jahresquellen bleiben privat. Abführungen an Finanzamt/Sozialversicherung behalten ihre vorhandenen separaten tatsächlichen Nachweise.

### 4.4 Jahresfortschreibung als Erweiterung des vorhandenen Adapters

Neuer Projektionszweig neben `source4_annual_reference_v1`, der eine laufende Monatsperiode und mehrere separat identifizierte Bonuszuflüsse liefert. Jeder Bonus führt Anspruchs-/Komponentenreferenz, ursprüngliche Laufrevision, tatsächlichen Zahlungsbezug, Steuer-/SV-Jahr und eigene verbrauchte Zweigbasen. Für die Einmal-Deduplizierung ist die komponentenspezifische Originalreferenz maßgeblich; dieselbe Lauf-ID darf nicht die Identität aller Boni ersetzen.

Für die aktuelle Kandidatenperiode ersetzt die laufende Monatsquelle nur den laufenden Anteil. Bereits wirksame Bonuskomponenten desselben Monats werden zusätzlich vollständig gebunden oder im neuen Monatsplan ausdrücklich neu hergeleitet. Sie dürfen weder entfallen noch zugleich als Vorbezug und aktuelle Komponente zählen. Frische Vollständigkeitsprüfung muss auch bereits bekannte aktuelle Zahlungszuordnungen und korrigierte Anspruchsrevisionen erkennen.

`PayrollAnnualBasis._project_run`, `_relevant_run`, `_snapshot` und `build_annual_plan` benötigen einen gesonderten Versionszweig/Adapter für diese Darstellung, keine Änderung der eingefrorenen v1-Arithmetik. Der aktuelle kompakte Referenzansatz bleibt sinnvoll: Quellen archiviert nachprüfen, keine rekursive Kopie sämtlicher früherer Jahresstände in jedem neuen Monat. Die bereits laufende Source4-Jahresbasisarbeit ist hierfür Eingangsbestand.

## 5. Abhängige Benutzeroberflächen und Ausgaben

| Vertrag | Notwendige Anpassung |
| --- | --- |
| Native und Browser Einmalfälle | `app/lib/business_payroll_oneoff_case_contract.dart`, `business_payroll_oneoff_cases.dart`, `web/office/payroll-oneoff-cases.js`: alte Einzelanspruchvalidatoren erhalten; neue explizite Monatsliste mit Originalbezug, Zuflussgruppe, Summen und Vollständigkeitsprüfung ergänzen. |
| Laufvorschau/Korrektur | `app/lib/business_payroll.dart`, `business_session.dart`, `web/office/payroll.js`: neue Sourceversion, eigener Input-/Antwortvalidator, Vorschauhash, idempotenter Wiederholungsvertrag; Korrekturauswahl bindet Monatsbestand statt nur gleichen Einzelanspruch. |
| Lohnkonto/Zahlungszuordnung | `app/lib/business_payroll_accounts.dart`, `web/office/payroll-accounts.js`: Transaktion und ihre Komponenten getrennt darstellen, tatsächliche Tage und offene Erfüllung zeigen. Alte Source4-Prüfung auf gemeinsamen Tag erhalten. Keine vorausgefüllte erfundene Überweisung. |
| Jahresquellen | `business_payroll_annual_basis_contract.dart`, zugehörige Forms/Page und `web/office/payroll-annual-basis.js`: Mehrfachkomponenten und Zahlungsbezüge des neuen Projektionsvertrags prüfen; keine manuelle Eingabe fertiger SV-Luft oder Jahressteuer. |
| Cash | `business_payroll_cash.dart`, `business_payroll_cash_page.dart`, `web/office/payroll-cash.js`: nur tatsächlich dokumentierte Teile auswählbar, bereits übernommene Teile gesperrt; eine offene Komponente ist kein Zahlbetrag. |
| Lohnkonto/Arbeitnehmerdokument | `payroll_ledger.py`, `business_payroll_statements.py`, `business_payroll.py::_render` und die jeweiligen Clientvalidatoren: neue Ausgabefassung mit getrennten Komponenten und Gesamtbetrag; alte Revisionen und eng begrenzte Arbeitnehmeransicht erhalten. |

Bestehende Lebenszyklusanforderungen gelten auch für neue Listen und Zuordnungen: Session-/Mitarbeiterwechsel, Hintergrundwechsel und Rechteentzug schließen private Erfassung und verwerfen verspätete Vorschauen. Reine Leseberechtigung erlaubt keine weiterlaufende Bestätigung. Einmalfall-Jahresoriginale dürfen nicht in das Mitarbeiterdokument oder öffentliche Finance-DTOs geraten.

## 6. Umsetzung in drei überprüfbaren Schritten

1. **Quellenentscheidung und Vertrag:** die offenen Fachfragen aus Abschnitt 7 mit Fundstelle und Zahlenbeispiel abschließen; Versions-/Komponentenschema und neue Zahlungszustände festschreiben. Bestehende historische Source3/4-/Jahres-/Cash-Fixtures samt exportierter Bytes sichern. Neuer reiner Berechner mit zwei tatsächlich verschiedenen Bonusansprüchen und getrennten Zahlungsereignissen; noch keine Freischaltung ohne vollständigen Folgepfad.
2. **Persistenz und Folgepfad gemeinsam:** Monatsfall, atomarer Mehrfachverbrauch, neuer Zahlungsnachweis, Jahresprojektion, Cash-Adapter und historische Integritätsprüfung entwickeln. Ein synthetischer Oktoberfall durchläuft bereits gezahlten laufenden Lohn, ersten Bonus, zweiten Bonus, Monatsrevision, nächste Jahresbasis und belegte neue Cash-Differenz. PostgreSQL-Wettläufe und Restore gehören vor Ende dieses Schrittes dazu.
3. **Beide Clients und Nachweise:** identische strikte DTO-Verträge, Vorschau/Korrektur/Wiederholung, private Originale, Lohnkonto und Arbeitnehmerausgaben integrieren. Negative Antworten, verlorene Bestätigung und veraltete Quellen prüfen. Funktionsfreigabe erst nach grünem durchgängigem Fall und unveränderten alten Referenzen; fachliche Produktivprüfung und reale Meldung bleiben gesonderte Nachweise.

## 7. Annahmen und noch notwendige Quellenprüfung

Dieses Dokument prüft vorhandenen Code; es behauptet keine neu durchgeführte amtliche Quellenprüfung. Bestehende 2026-PAP- und 2025/2026-SV-Referenzen sind wiederzuverwenden. Für die neue Mehrfach- und Zahlungssemantik fehlen noch gezielte belegte Entscheidungen:

| Frage | Vor Implementierung zu prüfen |
| --- | --- |
| Mehrere sonstige Bezüge, insbesondere am selben Tag | Aktuelle Fassung [EStG §39b Abs.3](https://www.gesetze-im-internet.de/estg/__39b.html), amtliche Lohnsteuerhinweise R/H 39b.6 und der im Repository gebundene BMF-PAP 2026: Einbeziehung früherer sonstiger Bezüge, Gruppenbildung, Reihenfolge und Cent-/Euro-Rundungen. Kein frei erfundener Sortierschlüssel. |
| Unterschiedliche laufende/sonstige Zuflüsse | [EStG §38a](https://www.gesetze-im-internet.de/estg/__38a.html), §39b und zugehörige Verwaltungsanweisungen: tatsächlicher Zufluss, Abgrenzung laufend/sonstig, Nachzahlung, Teilzufluss und Jahreswechsel. Die bisherige `running_tax_year`-Regel nicht ungeprüft auf einzelne Bonusnettos übertragen. |
| Mehrfachbonus und Märzklausel | [SGB IV §23a](https://www.gesetze-im-internet.de/sgb_4/__23a.html) und [DRV-GRA §23a](https://rvrecht.deutsche-rentenversicherung.de/SharedDocs/rvRecht/01_GRA_SGB/04_SGB_IV/pp_0001_25/gra_sgb004_p_0023a.html): Reihenfolge mehrerer Zahlungen, bereits verbrauchte aktuelle/Vorjahresluft und Zusammenspiel mit laufender Monatsabrechnung. |
| Rückrechnung schon erfüllter Komponenten | [EStG §41c](https://www.gesetze-im-internet.de/estg/__41c.html), einschlägige SV-Korrekturregeln und Nachweispflichten: Differenz, Rückzahlung, Storno, Auswirkungen auf nachfolgende Boni. Berechnungsdifferenz ist nicht automatisch tatsächliche Rückzahlung. |
| Kein positiver Geldtransfer trotz Bezug | Rechtliche Zufluss-/Erfüllungsgrundlage für Aufrechnung und Nettoabzüge separat prüfen. Nullnetto darf weder künstlichen Cash erzeugen noch ohne Quelle den Bruttozufluss beweisen. |

Technische Annahme für den ersten kompatiblen Ausbau: bestehende private Original-/Mandanten-/Rollenmodelle und die Ein-Lauf-pro-Monat-Architektur bleiben tragfähig. Fachlicher Anfangsumfang ist derselbe tatsächlich geprüfte reguläre 2026-Zweig; daraus folgt keine Ablehnung der zusätzlich vereinbarten Minijobentwicklung. Zahlungen 2027 oder frei gewählte SV-Sonderfälle sind durch dieses Dokument nicht automatisch freigeschaltet.

## 8. Unabhängige Grenz- und Abnahmefälle

Numerische Sollwerte für Steuer/SV werden aus unabhängig dokumentierten Fachreferenzen festgelegt, nicht aus einem zweiten Aufruf derselben Produktionsfunktion. Nebenbeträge lassen sich zusätzlich durch exakte Erhaltungssummen prüfen.

| Fall | Erwartete nachweisbare Eigenschaft |
| --- | --- |
| Laufendes Netto 30.10., Bonus A 31.10. | Alte Transaktion behält Datum, Referenz, Betrag und Cash-/EÜR-Nachweis; nur das tatsächlich neue Bonusnetto wird zusätzlich übernommen. Die bislang absichtlich gesperrte Konstellation funktioniert ausschließlich im neuen Vertrag. |
| Bonus A am 10.10., Bonus B am 25.10. | B sieht relevante Steuer-Vorbezüge und bereits verbrauchte Zweigbasen von A. Laufendes Monatsbrutto, Steuer-/SV-Tage und laufende Abzüge zählen einmal. Die nächste Jahresbasis enthält zwei Bonusidentitäten, nicht zwei komplette Oktoberperioden. |
| Zwei Ansprüche am selben Tag | Fachlich freigegebene Gruppierung liefert unabhängig von JSON-/Auswahlreihenfolge identische Ergebnisse; doppelte Anspruchsreferenz wird abgewiesen. Rundungsgrenzen ausdrücklich mit externer Erwartung prüfen. |
| KV-Luft erschöpft, RV-Luft noch offen | Der zweite Bonus verbraucht nur den belegten jeweiligen Rest. Keine globale Restgröße für alle Zweige; keine zweite Nutzung derselben Quelle. |
| Zwei Märzbezüge, gegebenenfalls unterschiedliche Beitragsjahre | Steuerjahr bleibt korrekt 2026; jede Zuordnung verbraucht nur ihre aktuelle oder 2025-Jahresluft. Die konkrete Schwellenentscheidung wird nach amtlicher Referenz geprüft. 31.03./01.04. als getrennte Monats-/Jahresbasisfolge testen. |
| A bereits Source4-verbraucht, Übergang zu neuem Monatsfall A+B | A bleibt demselben Lauf zugeordnet, wird nicht erneut Eigentum eines anderen Laufs; ursprüngliche v6-Quittung und alter Export unverändert. |
| A korrigiert, B bereits abhängig berechnet | Neue Monatsrevision rechnet alle abhängigen Schritte nach; alte Revisionen bleiben lesbar. Tatsächliche A-/B-Zahlungen bleiben unverändert, neue Nach-/Rückzahlung braucht eigenen Nachweis. |
| Zahlung nur teilweise dokumentiert | Offener Rest bleibt offen, keine künstliche Zahlung und kein aus Netto hochgerechnetes Steuerbrutto. Nur belegte Cash-Teile sind übernehmbar; ungeklärter Jahreszufluss verhindert eine scheinbar vollständige Folgegrundlage. |
| Laufender Lohn später als früher Bonus | Tatsächliche Bonusquelle kann unabhängig vom noch offenen laufenden Netto geführt werden. Ein nachträglich erfasster laufender Zufluss schreibt den früher eingefrorenen Bonusquellenstand nicht um. |
| Eine Sammelüberweisung für laufend+A+B | Private Zuordnung stimmt in beiden Richtungen centgenau; öffentliche Buchhaltung enthält die echte Transaktion genau einmal. Keine dreifache Bankbewegung. |
| Zwei Finalisierungen A+B bzw. A+C parallel | Höchstens eine passende erwartete Monatsrevision gewinnt; keine doppelte Reservierung, kein Teilverbrauch nach Rollback. Wiederholung derselben Vorgangs-ID liefert genau das ursprüngliche Ergebnis. |
| Quellenkorrektur nach Vorschau / verlorene Antwort | Veraltete Jahres-/Anspruchs-/Zahlungsreferenz wird abgewehrt. Wiederholung sendet denselben Inhalt; kein neues stilles Bonusereignis. |
| Fremde Person, fremde Firma, Rechteentzug, Hintergrundwechsel | Kein Original, Vorschauinhalt oder privater Fehler erscheint im falschen Kontext. Arbeitnehmeransicht und Finance-DTO enthalten keine privaten Jahresquellen. |
| Restore und historische Formate | SQLite und PostgreSQL rekonstruieren alte und neue Quittungen einschließlich Ansprüche und Cash-Eigentümerschaft. Alte Regelresultate, gespeicherte PDFs und Exporte fest gebundener Revisionen bleiben unverändert; neue Felder erhalten eine neue Fassung. |

Der Entwicklungsabschnitt ist erst abgeschlossen, wenn der konkrete getrennte Zahlungstagsfall und zwei Boni desselben Monats durch beide Clients, unveränderliche Monatsrevision, Jahresbasis, Lohnkonto, Arbeitnehmerdokument und tatsächlichen Cash-Nachweis zusammen funktionieren. Dieses Dokument markiert diese Arbeit weiterhin als **offen/geplant**.
