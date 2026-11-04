# Mehrere Einmalbezüge: additiver Source5/v7-Vertrag

Stand: 04.11.2026. Implementiert sind der kanonische Planungskern, private unveränderliche Monatsfälle und der begrenzte **Source5-Einzelanspruch mit getrennten tatsächlichen Zahlungstagen**. Private Domainbefehle prüfen Lohnrevision, atomaren Anspruchs-/Ereignisverbrauch, Zahlungsoriginale, Cash/EÜR und Jahresfolge. Der reine Rechenkern erzeugt weiterhin keine Zahlung oder Reservierung. Die globale API-/Schema-/Exportregistrierung ist angeschlossen und der echte PostgreSQL-Nachweis ist mit 3/3 Fällen grün, einschließlich paralleler Annahme, Rollenrechten und vollständiger Backup-/Restore-Runde. Vorhandene Source4/v6-Quittungen, Ausgabeformen und PDFs bleiben unverändert.

Fachquellen: [amtlicher Quellenabgleich mit Grenzfällen](CRM_ERP_LOHN_MEHRFACHBEZUEGE_QUELLEN_2026.md). KBS, Stand Januar 2026, Abschnitt 13.1/S.19 verlangt die gemeinsame Märzklauselprüfung mehrerer Einmalzahlungen desselben Monats bis 31.03. Die steuerliche Zusammenfassung mehrerer verschiedener Ansprüche am selben Tag ist durch die bisher erfolgreich gelesenen Quellen ebenfalls **nicht abschließend geklärt**. Ein Datum oder eine JSON-Reihenfolge ersetzt diese Entscheidung nicht.

## 1. Explizite Version und jetziger Funktionsumfang

Neuer Kern: `backend/payroll_multiple_oneoff_2026.py`.

```text
rule_version = de_2026_multiple_oneoff_v7
source_contract_version = 1
source_schema_version = 5  # expliziter privater Run-Adapter und registrierte private Route
calculate_multiple_source(snapshot, rule_version=..., source_contract_version=...)
```

Der erste Kern prüft kanonische tatsächliche v5-/Jahres-/Anspruchsoriginale und neue ausdrücklich **geplante** Bruttoereignisse. Er bildet die vollständige SV-Monatsgruppe einschließlich getrennter KV/PV- und RV/AV-Grenzen. Ein einzelner vollständiger Anspruch mit unveränderter tatsächlicher Steuerprognose verwendet exakt die bereits geprüfte v6-Rechnung. Ihre Geldwerte und ihre ursprüngliche Berechnung werden nicht verändert.

Bei mehreren Anspruchs- oder Zuflussereignissen sind die steuerliche Gruppenregel und die Verteilung der gemeinsamen Beiträge auf einzelne Zahlungsereignisse noch gesperrt. `payroll_calculation_complete=false`; endgültige Steuer-, Beitrags-, Arbeitgeber- und Nettobeträge bleiben `null`. Eine bekannte gesamte SV-Basis ist keine erfundene Einzel-Nettozuordnung. Teilansprüche zeigen den geplanten und verbleibenden Anspruch; sie werden nicht als tatsächlich erfüllt ausgegeben.

## 2. Kanonischer Quellenstand

Der reine Quellenstand besitzt genau:

```text
schema_version: 1
source_contract_version: 1
rule_version: de_2026_multiple_oneoff_v7
employee_id, month
running_calculation_case                  # unveränderter angenommener v5-Fall
components: [{
  component_key,                         # genau ID des ursprünglichen Anspruchs
  earning,                               # angenommener one_off_earning-Fakt
  planned_receipts: [{
    event_key,                           # stabile, unabhängige 32-stellige ID
    receipt_date,
    gross_minor,
    document_refs[]                      # genaue geschützte Originalfassungen
  }]
}]
current_annual_basis
previous_annual_basis|null
annual_tax_forecasts: [{event_key, annual_tax_forecast}]
completeness: {month_events_complete: true, evidence_ref}
```

Jede Komponente gehört genau zu einem wirksamen Originalanspruch derselben Person und desselben rechtlichen Arbeitgebers. Verschiedene Ereignisse können denselben Anspruch teilweise erfüllen; ihre geplante Summe darf den wirksamen Anspruch nicht überschreiten. In diesem ersten Kern ist das eine Planung, keine bereits gezahlte Teil-Erfüllung. `actual_paid`, freie Jahressummen, fertige SV-Luft und selbst gewählte steuerliche Gruppierungsarten werden nicht akzeptiert.

Komponenten werden nach ihrer stabilen Identität, Ereignisse nach Datum und Ereignisidentität kanonisiert. Reine Listenreihenfolge ändert weder Gruppenentscheidung noch Quellenhash. Gleiche Ereignisidentität in mehreren Komponenten, doppelte Anspruchskomponenten, andere Quellenversionen, boolesche Geldbeträge und nicht gebundene Originalreferenzen werden abgewiesen. Grenzen: 20 Anspruchskomponenten, 20 geplante Ereignisse je Komponente, insgesamt 100 Ereignisse in genau einem Monat 2026.

Die laufende Rechnung und ihre aktuelle Jahresprojektion werden erneut hergeleitet. Die aktuelle SV-Basis bindet genau diesen Fall, das Monatsende und den letzten Gruppenzuflusstag. Eine benötigte 2025-Basis bindet 31.12.2025 und denselben Gruppenzuflussstichtag. Die konkrete Zuordnungsperiode stammt aus den tatsächlichen Jahresoriginalen. Der private Resolver prüft zusätzlich tatsächlich vorhandene Lohnläufe desselben Monats. Ein bereits verbrauchter Source4-Fall sperrt den ungeprüften Versionswechsel. Bei Source5 müssen dieselben Anspruchs- und Ereignisidentitäten mit unveränderten Bruttobeträgen und Zuflussdaten erhalten bleiben. Mehrere tatsächliche Nettobeiträge werden nicht freigegeben; die Bestätigung im reinen Snapshot ersetzt diesen Datenbankabgleich nicht.

Eine Steuerquelle bindet ihr konkretes Ereignis, seinen Originalanspruch, seinen Zuflusstag und denselben laufenden Fall. Bei ungeklärten Mehrfachgruppen darf die Quellenliste leer sein; der Plan bleibt ausdrücklich unvollständig. Der aktuelle Anspruch wird nicht durch einen weiteren geplanten Anspruch in der Steuerprognose künstlich vorbelastet.

## 3. Vier voneinander unabhängige Identitäten

| Identität | Bedeutung und zulässige Änderung |
| --- | --- |
| `component_key` | Identität des ursprünglichen Anspruchs. Eine Korrektur ändert dessen Revision, nicht seine Herkunft oder Eigentümerschaft. |
| `event_key` | Eigenständiger belegter Bruttozufluss beziehungsweise zunächst dessen geplanter Vorgang. Eine später neue Zahlung bekommt eine eigene Identität. |
| `sv_month_group_key` | Serverseitig aus Person, rechtlichem Arbeitgeber und Zuflussmonat abgeleitet. Umfasst die vollständige Monatsgruppe; keine freie Clientwahl. |
| Steuergruppenidentität | Erst nach fachlicher Festlegung ableitbar. Im derzeitigen Mehrfachzweig `tax_groups=null`; weder Monat noch Tag werden stillschweigend als Steuergruppe übernommen. |

Die Banktransaktion besitzt zusätzlich ihre eigene Zahlungsidentität. Eine Überweisung, die laufenden Lohn und zwei Ansprüche erfüllt, bleibt genau eine tatsächliche Überweisung. Umgekehrt können ein Anspruch und seine tatsächliche Bruttoerfüllung mehrere getrennte Zahlungsteile benötigen.

## 4. SV-Monatsentscheidung und noch fehlende Zuordnung einzelner Beiträge

`select_monthly_assignment` summiert die exakt gebundenen Ereignisse des Monats und entscheidet deren gemeinsame Jahreszuordnung. Der Januar–März-Auslöser wird gegen die gesamte aktuelle KV-Luft geprüft. Bei einer Überschreitung wird die vollständige Gruppe der tatsächlichen passenden Vorjahresperiode zugeordnet. Der zuerst allein passende Bonus bleibt nicht endgültig im aktuellen Jahr stehen. Eine Aprilzahlung erhält durch eine frühere Zuordnungsperiode keine Märzklausel.

Beitragspflichtige frühere Einmalbezüge anderer Gruppen vermindern die jeweilige Jahresluft. Bereits vorhandener Verbrauch derselben zu korrigierenden Gruppe darf nicht zusätzlich in ihrer Anfangsbasis stehen. Der erste reine Vertrag weist eine in der Basis enthaltene Lohnperiode desselben Zuflussmonats deshalb ausdrücklich zurück; ihre automatische Ersetzung wird erst mit dem privaten Korrekturvertrag zugelassen.

Aus der gemeinsamen Zuordnung entstehen `bases_minor` und die tatsächliche Jahres-/Periodenreferenz. Eine Verteilung dieser Basen und insbesondere gerundeter Beiträge auf bereits ausgezahlte Einzelnetti erfolgt noch nicht. Hierfür bleiben `component_allocations=null` und ein eigener fachlicher Blocker erhalten.

## 5. Implementierte private Annahme und atomarer Verbrauch

`business_payroll_multiple_cases.py` speichert Monatsfälle in `business_payroll_multiple_case_events` und ursprüngliche Annahmen in `business_payroll_multiple_case_requests`. `business_payroll_multiple_consumptions` bindet jede freigegebene Lohnrevision an die genaue Komponente und Ereignisidentität; beide besitzen einen unabhängigen eindeutigen ersten Eigentümer. Der anfänglich freigegebene Zweig enthält genau einen vollständig erfüllbaren Originalanspruch. Die privat vorgesehene Route lautet `/payroll/multiple-one-off-cases` einschließlich Vorschau, Quellen, Original und Verlauf; sie ist global in API, Schema, Privatkatalog und Laufzeitpaketen registriert.

Die private Annahme speichert den vollständigen Monatsfall, ursprünglichen Auftrag, genaue Originalfassungen, Rechenplan und Vorschauhash unveränderlich. Vorschau, Annahme, Wiederholung und Originalabruf prüfen aktuelle Personalrechte. Quellenfrische wird vor jeder neuen Wirkung erneut geprüft; historische angenommene Aufträge bleiben als ursprüngliche Fassung wiederholbar.

Beim Source5-Finalize entstehen Lohnrevision, eindeutige Ereigniseigentümerschaft und komponentenweise Verbrauchsquittung in derselben gesperrten Transaktion. Derselbe tatsächliche Bruttozufluss darf genau einem Lohnlauf gehören. Unterbrechung oder Konflikt darf keine einzelne Reservierung ohne zugehörigen Lauf hinterlassen. Wiederholung desselben angenommenen Auftrags erzeugt keine zweite Wirkung. Korrekturen behalten ihre Vorgänger- und Komponentenreferenzen.

Teilansprüche benötigen zusätzlich die Summe aller wirksamen tatsächlichen Erfüllungen ihres ursprünglichen Anspruchs. Ein einfacher einmaliger Schlüssel je Anspruch genügt dafür nicht. Vorhandene v6-Anspruchseigentümerschaft muss beim Übergang in denselben Lohnlauf ausdrücklich nachgewiesen werden; sie darf nicht durch eine neue v7-Ereignis-ID umgangen werden. Bis dieser Übergang geprüft ist, bleibt eine solche Übernahme gesperrt.

Neue Module, Tabellen, API-Routen und Export-/Runtime-Registrierungen werden vor ihrer Einführung getrennt an die Integrationsverantwortung gemeldet. Der reine Kern registriert nichts automatisch.

## 6. Tatsächliche Zahlung und separate Erfüllung

Der implementierte Zahlungsnachweis in `payroll_multiple_payments.py` bindet jeden unveränderten tatsächlichen Zahlungsteil mit Datum, Betrag und Transaktionsreferenz. Eine private Zuordnung beschreibt, welche laufende beziehungsweise sonstige Nettoforderung damit erfüllt wurde; die Summe der Zuordnungen muss exakt dem tatsächlichen Teil entsprechen. Diese Zuordnung ist keine zweite Zahlung.

Eine tatsächliche Bruttoerfüllung braucht ihre eigene Originalquelle. Sie wird nicht aus einer Nettoquote oder einem geänderten Anspruchsbetrag errechnet. Laufendes Netto am 30.10. und Bonusnetto am 31.10. dürfen deshalb getrennt erhalten bleiben. Cash übernimmt jeden echten Zahlungsteil höchstens einmal und nur im tatsächlich neuen Umfang; öffentliche Finanzprojektionen enthalten keine privaten Anspruchs-, Jahres- oder Personaloriginale.

Der freigegebene Domainzweig ist ein vollständig belegter einzelner Anspruch mit getrenntem laufendem Zahlungstag. Er benötigt keine unbewiesene Mehrfach-Steueraggregation. Mehrere steuerlich ungeklärte Ereignisse bleiben auch bei vollständigen Bankbelegen für Finalize gesperrt.

Source5-Zahlungen verlangen zusätzlich zu den bisherigen Lohnkontofeldern genau:

```text
payment_source_schema_version: 1
settlement_allocations: [{
  payment_index,
  running_minor,
  one_off_allocations: [{event_key, net_minor}]
}]
prior_payment_ref: {id, revision, content_hash}|null
```

Der tatsächliche Bonusanteil muss genau am ursprünglichen Bruttozuflusstag liegen. Laufendes Netto und Bonusnetto werden getrennt aus der geprüften Rechnung hergeleitet und jeweils vollständig erfüllt; keine prozentuale Zuordnung. Ein kombinierter Transfer bleibt ein einziger Cashteil. Die Summe aller privaten Zuordnungen entspricht exakt der Summe tatsächlicher Teile. Negative Bonusnetti, Rückzahlungen und freie Verrechnungen sind für diesen Zweig ausdrücklich gesperrt.

Ein bereits gezahlter v5-Lauf kann in derselben Lauf-ID um den einzelnen Bonus ergänzt werden. Seine tatsächlich angenommenen Zahlungsteile bleiben mit Datum, Betrag, Referenz und Reihenfolge unverändert erhalten. Die Ermittlung der vorherigen Zahlung durchsucht **alle früheren Lohnrevisionen**, nicht nur den direkten Vorgänger. Unbezahlte Source3-/Source5-Zwischenrevisionen dürfen eine frühere tatsächliche Zahlung weder entfernen noch umbenennen. Die referenzierte frühere Zahlung bindet ihre tatsächliche Lohnrevision und ursprüngliche Annahmequittung. Mehrere voneinander abweichende frühere Zahlungsfassungen benötigen den noch gesondert zu prüfenden Differenzvertrag und werden vor einer neuen Wirkung abgewiesen.

Die Jahresbasis projiziert laufende und sonstige Bezüge getrennt. Sie prüft die unterschiedlichen tatsächlichen Zahlungstage gegen ihre privaten Zuordnungen und speichert kompakte `source5_annual_reference_v1`-Referenzen mit verifizierten historischen Profilen. Frühere Boni vermindern die richtige SV-Luft und erhöhen die entsprechende steuerliche Jahresbasis; eine ganze verschachtelte Jahresgeschichte wird nicht rekursiv kopiert.

## 7. Echte Folgekorrekturen

Bereits umgesetzt: bezahlter v5-Lauf → Source5-Korrektur mit unverändertem laufenden Original und ausschließlich zusätzlichem tatsächlichem Bonusgeld; unbezahlte Source5-Revision → neue Revision desselben unveränderten Anspruchs-/Zuflussereignisses. Eine bereits bezahlte Source5-Vorfassung sperrt den neuen Source5-Folgekorrekturzweig auch über unbezahlte Zwischenrevisionen hinweg. Weitere Nach-/Rückzahlungspfade sind damit ausdrücklich **nicht** freigegeben.


Rechen-/Erfassungsfehler, später neu gewährte Nachzahlung, ursprüngliche Untererfüllung und tatsächliche Rückzahlung werden als unterschiedliche belegte Fälle behandelt. Eine erhöhte Anspruchsrevision schreibt keinen früheren tatsächlichen Zufluss um. Ein negativer Rechenunterschied wird ohne Rückzahlungsnachweis nicht zu einer Cash-Gutschrift.

Eine Änderung der laufenden SV-Basis oder eines Gruppenbestandteils kann die Jahreszuordnung der gesamten Monatsgruppe ändern. Der Korrekturplan muss deshalb sämtliche weiterhin wirksamen Gruppenbestandteile, alle betroffenen späteren Jahresverbräuche und die zulässige Steuerkorrektur binden. Originalrevisionen, bestehende PDFs und tatsächliche Transfers bleiben erhalten; neue Rechnungsdifferenzen und offene Forderungen werden getrennt ausgewiesen.

Eine zulässige SV-Rückrechnung ersetzt nicht die Prüfung des steuerlichen Zuflusses und der Grenzen des §41c EStG beziehungsweise der bereits übermittelten Lohnsteuerbescheinigung. Diese fachlich noch nicht vollständig festgelegten Korrekturwege werden nicht durch negative PAP-Eingaben simuliert.

## 8. Ausführbare Nachweise und verbleibende Integration

`backend/test_payroll_multiple_oneoff_2026.py` prüft kanonische Originalbindungen, Teilansprüche, doppelte Identitäten, Überverbrauch, fehlendes Vorjahr, Listenreihenfolge, v6-Geldparität und die fachlich begründeten Sperren.

Die unabhängig aus den Quellen hergeleiteten Rechenfälle enthalten die März-Monatsgrenze bei 243750 Cent und einen Cent darüber, die gemeinsame Verlagerung von zunächst allein passenden 150000 plus späteren 100000 Cent, den Zuordnungswechsel nach einer rückwirkenden Erhöhung laufenden Entgelts, getrennte Mai-Grenzen sowie die Aprilgrenze. Der PAP-Sensitivitätsfall ist ausführbar: Jahreslohn 87500 Euro, zweimal 2500 Euro sonstiger Bezug, getrennt 5236 Cent Soli gegenüber 10472 Cent bei Zusammenfassung. Er belegt die notwendige Sperre, keine freigegebene Untermonats-Steuerregel.

Die Zusammensetzungsfixtures erzeugen ihre v5-/Jahres-/Anspruchsoriginale über tatsächliche private Domänenbefehle. Die neuen Ereignisse sind ausdrücklich Planvorschläge. Eine bereits vorhandene Datenbankannahme oder tatsächliche Zahlung dieser v7-Ereignisse wird nicht behauptet. Ausführungsprotokolle und Dateihashes: `docs/evidence/payroll-multiple-oneoff-core-2026-11-04.json`.


`backend/test_business_payroll_multiple.py` erzeugt tatsächliche private Originale, Lohnrevisionen, Verbrauchsquittungen, Zahlungsbelege, Cashteile und EÜR-Übernahmen. Die 16 integrierten Domainfälle sind grün; enthalten sind getrennte Tage 30./31.10., unveränderte alte Quittungen, atomarer Rollback, Verlust der Verbrauchsquittung, Rechte, Quellenrevisionen, mehrere weiterhin gesperrte Ansprüche, kompakte Jahresprojektion und privater Ledger-/PDF-Export. `backend/test_payroll_multiple_payments.py` enthält sieben zusätzliche reine Zahlungsgegenfälle. Die unabhängige Prüfung der gesamten Vorgängerkette führte zu einem konkreten Fix; ihr Repro und ihre Regression bleiben als gesonderte Evidenz erhalten.

Private Jahresübersichten mit Source5 verwenden `schema_version=4` und `recorded_multiple_one_off_payments`; bisherige Source4-Ledger bleiben unverändert. Eigene Mitarbeiterbelege verwenden jetzt die gesonderte reduzierte Schemafassung 4 einschließlich geschütztem PDF-/JSON-Abruf. Die positive Allowlist gibt keine privaten Jahres-, Anspruchs- oder Ereignisoriginale aus. Backend, Browserverträge und native Belegansicht besitzen eigene Prüfungen; die vollständige private Source5-Clientkette wird noch zusammengeführt. Siehe `CRM_ERP_SOURCE5_MITARBEITERBELEGE_2026-11-04.md`. Globale Registrierung und realer PostgreSQL-/Restore-Nachweis sind grün.


Abschluss dieses privaten Pakets: **26/26** Fälle im finalen Domainlauf (16 private Workflows, 7 Zahlungsplanfälle, 3 unabhängig geschriebene Laufkettenregressionen), **3/3** echte PostgreSQL-Fälle in 34,637 Sekunden. Eine echte Novemberfolge nach bezahltem Source5-Oktober nutzt 50000 Cent vorherigen Bonus, 464516 Cent laufende Jahresbezüge, 396109 Cent KV-Rest und 814516 Cent Steuerprognose vor dem nächsten Bonus. Die ältere breite Auswahl hatte ausschließlich einen falschen Testmodulnamen als Loaderfehler; der spätere isolierte HTTP-Fall benötigte localhost-Netzfreigabe und ist danach 1/1 grün. Fehlversuche bleiben mit dem jeweiligen Grund archiviert.

Dauerhafte Protokolle, Dateihashes und präzise Restgrenzen: [privater Source5-Integrationsnachweis](evidence/payroll-source5-private-integration-2026-11-04.json). Reale Clientdaten aus angenommenen synthetischen Originalen: `app/test/fixtures/payroll_multiple_runs.json`, reproduzierbar mit `scripts/generate-payroll-multiple-run-fixture.py`. Enthalten sind Anfangsfall, bezahlter v5-Übergang, echte getrennte Cashteile und EÜR sowie eine weiterhin blockierte Mehrfachgruppe. Kompakte Einzelantworten dieser Fälle liegen unter 355000 Byte.

Die vorhandene Bindung der tatsächlichen Pauschalreisesteuer an ihren geplanten Erfassungstag bleibt erhalten. Unterschiedliche Banktage sind belegt; eine Erfassung an einem späteren Tag wird nicht durch stillschweigende Wiederverwendung oder Rückdatierung eines Reise-Steuerereignisses freigegeben.
