# Einmalbezüge: explizite Zusammensetzung v6

Stand: 04.11.2026. Der reguläre Einmalbezug ist als explizite Source4/v6-Rechnung im Repository integriert: private Quellenannahme, Lohnlauf, atomarer Anspruchsverbrauch, Lohnkonto, Zahlungsnachweis und die tatsächliche Cash-/EÜR-Kette. Die APIs, Schemafamilien und Paketregistrierungen sind global eingebunden. Die nachstehenden Nachweise betreffen die isolierte Entwicklungs- und Testumgebung; eine Produktionsauslieferung ist damit nicht behauptet.

Ein angenommener Jahresfakt oder Einmalbezugsfall allein erzeugt weiterhin weder Lohnlauf noch Zahlung. Die getrennten Bestätigungen und jeweiligen aktuellen Rechte bleiben erforderlich.

## Expliziter Rechen- und Quellenvertrag

Datei `backend/payroll_oneoff_composition_2026.py`, Funktion
`calculate_oneoff_source(snapshot, rule_version=..., source_contract_version=...)`.
Regel: `de_2026_oneoff_composition_v6`; Quellenvertrag: ganze Zahl `1`.
Die äußere Lohnlauf-API verwendet ausdrücklich `source_schema_version=4` und genau `employee_id` sowie `one_off_case_ref`. Bestehende v1–v5-Rechnungen behalten ihre eigenen Regeln und ursprünglichen Quellenverträge.

Der reine Quellenstand besitzt genau folgende Felder:

```text
schema_version: 1
source_contract_version: 1
rule_version: de_2026_oneoff_composition_v6
employee_id, month
running_calculation_case
one_off_earning
current_annual_basis
previous_annual_basis|null
annual_tax_forecast
```

Alle fünf Quellenwerte sind vollständige, angenommene Originalobjekte ihrer
jeweiligen privaten Dienste. Der aufrufende private Resolver muss Existenz,
Frische, Rechte, aktuelle Quellenrevisionen und Originalquittungen prüfen.
Der reine Kern prüft zusätzlich konkrete Identität, Quellenverbindungen und
erneute fachliche Ableitung. Freie Jahresbeträge, fertige SV-Luft oder vom
Client gewählte Beitragssätze sind kein Bestandteil dieses Vertrags.

`running_calculation_case` ist ausdrücklich v5. Seine ursprüngliche Rechnung
wird mit `calculate_calculation_source` wiederholt. Die aktuelle Jahresbasis
muss genau diesen Fall als `current_calculation_case_ref` enthalten; ihre
aktuelle Periodenprojektion wird nochmals aus derselben Rechnung hergeleitet.
Eine bereits bezahlte v5-Rechnung kann als begründete Revision desselben Lohnlaufs um diesen Einmalanspruch ergänzt werden. Die ursprünglichen Zahlungsteile bleiben dabei exakt erhalten; nur der tatsächlich zusätzliche Zahlungsteil kann zusätzlich in Cash übernommen werden. Ein neu erfundener zusammengefasster Transfer darf die ursprüngliche Zahlung nicht ersetzen.

Anspruch, Jahresbasis und Steuerprognose müssen exakt denselben Zuflussfall,
Arbeitnehmer und Arbeitgeber binden. Die Basis reicht bis zum Monatsende,
ihr `as_of_date` entspricht dem geplanten tatsächlichen Zuflussdatum. Die
Steuerprognose muss denselben aktuellen Anspruch ausschließen. Anspruchstage
werden gegen die wirklichen Entgeltvereinbarungen ihrer Beschäftigungsfakten
geprüft; ein frei behaupteter Versicherungsabschnitt genügt nicht.

## Zuordnung und Steuerrechnung

Die Zuordnungsperiode ist der letzte konkrete Abschnitt der passenden
Jahresbasis. Bei mehreren ursprünglichen SV-Abschnitten archiviert die
Zusammensetzung zusätzlich dessen `assigned_part_key`. SV-Luft wird aus
tatsächlichen Intervallen, bereits verbeitragten Beträgen und früheren
Einmalbezügen berechnet. KV/PV und RV/AV behalten ihre eigenen Restbeträge.

Bei möglicher Märzklausel reicht ein fehlendes Vorjahr nicht als Nachweis
fehlender Vorbeschäftigung. Benötigt wird eine vollständige 2025-Jahresbasis
bis 31.12.2025 mit demselben Zuflussstichtag. Sie kann ausdrücklich das ganze
Jahr als belegte Nichtbeschäftigung enthalten. Bei Zuordnung zu 2025 stammen
Beitragssätze und persönliche PV-Merkmale aus der tatsächlichen ursprünglichen
2025-Periode; die Steuer bleibt eine 2026-Rechnung mit den tatsächlich am
Zuflussmonatsende geltenden Merkmalen und Jahresfreibeträgen.

Der aktuelle reguläre Zweig addiert Beiträge, Sonderlohnsteuer, Soli und
Kirchensteuer zur unveränderten laufenden v5-Rechnung. Er berechnet laufenden
Lohn nicht erneut als sonstigen Bezug. U1 und U2 werden auf den regulären
Einmalbezug nicht erhoben. Insolvenzgeldumlage folgt der tatsächlichen
zusätzlichen RV-Basis. Bereits im laufenden Fall enthaltene Reisesteuern und
belegte Nettoabzüge bleiben in der Zusammenrechnung erhalten.

Das Ergebnis enthält die bestehenden Lohnsummen, `running_calculation` als
unveränderte v5-Rechnung sowie `one_off_details` mit Quellenreferenzen,
Zuordnung, historischem Beitragsprofil, einzelnen SV-/PAP-Beträgen und
`actual_payment_created=false`. Nicht unterstützte Fälle liefern ausdrückliche
Blocker und unbekanntes Netto, keine angenommene Nullabrechnung.

## Private Annahme und tatsächliche Geldkette

`business_payroll_oneoff_cases.py` stellt `/payroll/one-off-cases` einschließlich Quellen, Vorschau, Einzelabruf und Historie bereit. Ein angenommener Fall bindet genaue Revisionen von laufender Rechnung, Anspruch, aktueller und gegebenenfalls vorheriger Jahresbasis sowie Steuerprognose. Angenommene Originalaufträge bleiben nur im geschützten Archiv; Antwortobjekte geben sie nicht aus. Frische Rechte, Mitarbeiterrevisionen, Originaldateien und sämtliche Quellenbeziehungen werden erneut geprüft.

Beim tatsächlichen Finalize entstehen Lohnrevision und `business_payroll_oneoff_consumptions` in derselben Transaktion. Der Anspruch besitzt einen dauerhaften eindeutigen Lohnlaufbesitzer. Parallele Wiederholung erzeugt keine zweite Revision oder Reservierung; eine Korrektur bleibt beim selben Anspruch. Ein Wechsel zurück zu Source3 kann den verbrauchten Anspruch nicht entfernen. Ein fehlender oder geänderter Verbrauch sperrt auch Lohnabruf, PDF, Zahlung, Konto und Integritätsprüfung ohne vorherigen Cash-Import.

Lohnkonto und Export zeigen laufenden Lohn und sonstigen Bezug getrennt, einschließlich tatsächlicher Steuer-/SV-Jahreszuordnung. Nettozahlung und Arbeitgeberabführung fließen über die bestehende geprüfte Geldkette in Cash und EÜR ein. Eine laufende Reisepauschalsteuer sowie ein belegter Arbeitnehmer-Nettoabzug bleiben erhalten; der Arbeitgebergesamtbetrag stimmt mit tatsächlicher Auszahlung plus Abführung überein. Öffentliche Finanzprojektionen enthalten keine privaten Jahres-, Anspruchs- oder Personaloriginale.

Der aktuelle Zahlungszweig verlangt für sämtliche tatsächlichen Zahlungsteile den belegten Bonuszuflusstag. Eine Zahlung mit einem anderen Tag wird abgewiesen. Bereits bezahlte v5-Teile können deshalb derzeit nur übernommen werden, wenn ihr tatsächlicher Tag auch diesem Zuflusstag entspricht.

## Jahresfolgen ohne erneute Nutzung verbrauchter SV-Luft

Eine neue Jahresbasis übernimmt tatsächlich bestätigte Source4-Läufe mit ihren vollständig gebundenen Zahlungsnachweisen. Der laufende Anteil stammt unverändert aus `running_calculation`; der Bonus wird separat als früherer sonstiger Bezug und mit seinen tatsächlichen branchengenauen Beitragsbasen berücksichtigt. Die spätere Steuerprognose enthält frühere Boni und schließt allein den aktuellen Anspruch aus. Fehlt die tatsächliche Zahlung, liegt sie nach dem Stichtag oder wird ein bekannter Lauf beziehungsweise Zahlungsnachweis ausgelassen, ist die neue Basis gesperrt.

Die Märzklausel behält getrennte Jahre: Ein im Januar 2026 gezahlter Bonus mit SV-Zuordnung Dezember 2025 verbraucht die entsprechende Luft der 2025-Basis; sein Steuerbetrag gehört in die 2026-Basis. Die ursprüngliche konkrete Zuordnungsperiode muss enthalten sein. Ein solcher Lauf erfindet keine laufenden Beschäftigungstage im falschen Jahr. Bei der begründeten Korrektur desselben Anspruchs wird ausschließlich dessen zu ersetzender eigener Verbrauch serverseitig ausgenommen; andere bereits verarbeitete Ansprüche bleiben erforderlich. Ein tatsächlicher zweiter Märzklauselbonus im Februar erhält deshalb nur die nach dem Januarbonus verbleibende 2025-Luft.

Damit Jahresfolgen keine vollständigen älteren Jahresbäume erneut kopieren, enthalten neue Source4-Jahresquellen `projection_format: source4_annual_reference_v1` mit exakten Lohnreferenzen. Zahlungsteile, tatsächliche Beitragsprojektion und die jeweiligen historischen Profile/Abschnittsschlüssel werden flach gespeichert. Der private Resolver rekonstruiert diese Daten bei der Prüfung aus den tatsächlichen angenommenen Originalen. Ein neu gehashtes manipuliertes Profil einschließlich passend veränderter Annahme und Quittung wird daher abgewiesen. Vorhandene v1–v5-Jahresquellen behalten ihre bisherige Darstellung.

Erfolgreiche Prüfungen derselben unveränderlichen Jahresquelle werden nur innerhalb eines Lesevorgangs wiederverwendet. Die nächste Anfrage beginnt ohne Prüfcache; Frischeprüfungen werden stets ausgeführt. Drei über tatsächliche Annahmebefehle erzeugte synthetische Bonusmonate Oktober/November/Dezember (isolierte Testuhr am 31.12.2026) ergaben kompakte Lohnobjekte von 206183, 217530 und 228168 Bytes; unveränderte frühere Quittungen blieben reproduzierbar.

## Noch nicht abgeschlossene Zweige

- Mini-/Midijob-Prognose, unvorhersehbare Überschreitung und konkret nachzurechnende Übergangsbereichsperioden; isolierte Rechenprimitive existieren.
- Wechsel zwischen geringfügigen und regulären Anspruchsabschnitten sowie weitere Versicherungsfälle. Ein belegter vorheriger Minijob wird ausdrücklich gesperrt.
- Mehrere verschiedene Bonusansprüche im selben Lohnmonat. Die private Vorschau weist einen weiteren Anspruch im bereits Source4-abgerechneten Monat ausdrücklich zurück; er darf den ersten Bonus nicht stillschweigend aus der Jahresbasis entfernen.
- Getrennte tatsächliche Zahlungstage für laufenden Lohn und Bonus sowie die vollständige nachfolgende Korrektur abhängiger späterer Zuordnungen.
- Der eigene U-Merkmal-Zweig für Source4 und weitere gesetzliche Sonderfälle außerhalb des belegten regulären Zweigs. Eine freie S-Eingabe ersetzt keine Jahresvorbelege.
- Externe fachliche Gesamtfreigabe, amtliche Übermittlungen und Produktionsauslieferung.

## Aktuelle Backendnachweise vom 04.11.2026

Die abschließende gemeinsame Regression bestand mit 55/55 Kern-, Domänen- und unabhängigen Gegenfällen in 90,742 Sekunden. Darin enthalten sind acht neue tatsächliche Jahresfolgefälle: gezahlter Source4-Vortrag, fehlende/verspätete/ausgelassene Quellen, drei Bonusmonate, getrennte Märzklauseljahre, Korrektur desselben Januaranspruchs, weiterer Februarbonus mit verbleibender 2025-Luft, zweiter Anspruch im selben Monat und Manipulation des historischen Profils trotz vollständig neu berechneter Hashes. Der vollständige Quellenkatalog nach drei Bonusmonaten umfasst 2340035 Bytes und liegt unter der bestehenden 4-MiB-Clientgrenze. Einzelheiten, frühere Versuche und Quellprüfsummen stehen unter `docs/evidence/payroll-oneoff-annual-followup-2026-11-04.json`.

Vier gesicherte PostgreSQL-Fälle prüfen echte MFA-/HTTP-Rechte, getrennte parallele Verbindungen, Annahmekonflikte, Rollen/Unveränderlichkeit sowie tatsächliche Sicherung/Wiederherstellung von Fall, Lauf, Zahlung, Verbrauch und PDF-Dateien. Abgrenzung und Originalprotokolle: `docs/CRM_ERP_LOHN_EINMALBEZUG_PG_PRUEFUNG_2026-11-04.md`. Der zusätzliche vierte PG-Fall prüft die bezahlte Source4-Jahresfolge einschließlich tatsächlicher Sicherung und Wiederherstellung; seine Nachweise sind dort gesondert dokumentiert.

Die tatsächliche Clientfixture `app/test/fixtures/payroll_oneoff_runs.json` enthält außerdem eine Source4-Korrektur von 50000 auf 70000 Cent sowie die Übernahme eines tatsächlich bezahlten v5-Laufs in v6. Beide binden unveränderte Originalzahlung und tatsächlichen zusätzlichen Zahlungsteil. Der reproduzierbare Generator liegt in `scripts/generate-payroll-oneoff-run-fixture.py`.

## Historische Gegenfälle vom 03.11.2026

`backend/test_payroll_oneoff_composition_2026.py`: 9/9 Fälle in 3,605 Sekunden
grün. Sie erzeugen ihre Originale über tatsächliche private Domänenbefehle.
Geprüft: laufende Rechnung unverändert; Geldsummen; echte getrennte BBG-Luft;
Märzklausel mit historischem Zusatzbeitrag/Sachsen/Kinderabschlag und aktuellen
Steuermerkmalen; fehlendes Vorjahr; belegte Nichtbeschäftigung; manipulierte
Jahresprojektion trotz neu berechnetem Plan; andere Fallbindung; explizite
Version; vorheriger Minijob. Der erste Lauf zeigte drei Fixturefehler beim
zweiten Identitätsnachweis; die Fixture verwendet nun eine echte begründete
Korrekturversion. Beide Logs bleiben erhalten.

Logs: `work/verification/payroll-oneoff-composition-first.log`,
`work/verification/payroll-oneoff-composition-second.log`,
`work/verification/payroll-oneoff-composition-boundaries.log`.

## Unabhängige Prüfung des reinen Kerns

Vier zusätzliche, getrennt hergeleitete Gegenfälle bestehen zusammen mit den neun Entwicklungstests (13/13;5,443s). Die Märzklausel wurde genau bei164859Cent aktueller KV-Luft und einen Cent darüber mit echten angenommenen privaten Originalen geprüft. Weitere Fälle prüfen getrennte KV-/RV-Basen, historische Beiträge, unveränderten laufenden Lohn und Personen-/Monatsbindung. Nachweis: `docs/evidence/payroll-oneoff-composition-independent-2026-11-03.json`.

Der erste unabhängige Lauf enthielt zwei falsche Erwartungen bei der Pflegebeitragsrundung. Nach Prüfung der GKV-Hinweise vom31.03.2025, Abschnitt3.3, Druckseite12, wurden nur die Erwartungen auf die dort ausdrücklich zugelassene getrennte Rundung berichtigt:2967+989=3956Cent. Der Produktcode blieb unverändert. Dieser historische Kernnachweis belegt allein den damals geprüften Rechenkern. Der aktuelle Stand der später ergänzten Source4-Fallannahme und Geldkette steht oben.
