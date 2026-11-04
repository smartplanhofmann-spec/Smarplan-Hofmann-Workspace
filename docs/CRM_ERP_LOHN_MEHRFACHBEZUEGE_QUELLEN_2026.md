# Mehrere Einmalbezüge und getrennte Zuflüsse: Quellen für den nächsten Vertrag

Abruf und Prüfung: **04.11.2026 (UTC)**. Ergänzung zum [Fortsetzungsplan](CRM_ERP_LOHN_EINMALBEZUG_FORTSETZUNGSPLAN_2026-11-04.md). Dieses Dokument enthält gelesene Fachquellen, daraus hergeleitete Vertragsanforderungen und unabhängige Rechenbeispiele. Es ist keine Implementierungs-, Melde- oder Produktivfreigabe. Produktcode wurde hierfür nicht geändert; die Beispiele sind keine ausgeführten Produkttests.

**Wesentliches Ergebnis:** Die Sozialversicherung verlangt bei mehreren Einmalzahlungen im selben Monat des ersten Quartals eine gemeinsame Märzklauselprüfung. Eine ausschließlich chronologische Kette unabhängiger Einzelberechnungen reicht deshalb nicht. Die steuerliche Gruppenbildung benötigt eine eigene Entscheidung: Der PAP liefert bei getrennten und zusammengefassten Aufrufen unter Umständen unterschiedliche Solidaritätszuschläge. Steuergruppe, SV-Monatsgruppe, Anspruch und Banktransaktion dürfen nicht dieselbe technische Identität sein.

## 1. Quellenregister und tatsächlicher Prüfstatus

Die nachstehenden Seitenzahlen sind die sichtbaren Dokumentseiten, sofern nicht ausdrücklich als PDF-Seite bezeichnet. HTML-Abschnittsbezeichnungen sind stabiler als Zeilennummern des Abrufwerkzeugs. Bei den Spiegeln wurde der zugängliche Dokumenttext gelesen; ein vom Originalserver heruntergeladenes, gehashtes PDF wird nicht behauptet.

| ID | Quelle und Fassung | Gelesene Fundstelle / Abrufstatus |
| --- | --- | --- |
| E | [EStG, amtliches Gesamt-PDF](https://www.gesetze-im-internet.de/estg/EStG.pdf), Kopf: zuletzt geändert durch Art. 1 G vom 15.10.2026, BGBl. 2026 I Nr. 307 | §38a Abs.1 auf S.154; §41c Abs.1–4 auf S.173–174. Zusätzlich [§39b Einzeltext](https://www.gesetze-im-internet.de/estg/__39b.html), insbesondere Abs.3 und5. Volltexte zugänglich. |
| R | [BMF LStH2026, R39b.6](https://amtliche-handbuecher.bundesfinanzministerium.de/lsth/2026/A-Einkommensteuergesetz/VI-Steuererhebung-36-47/2-Steuerabzug-vom-Arbeitslohn-Lohnsteuer-38-42g/Paragraf-39b/r-39b-6.html) | Die aktuelle BMF-Seite war im Suchindex auffindbar; direkte Abrufe einschließlich übergeordneter Seite scheiterten mit503. Daher **kein erfolgreich gelesener vollständiger 2026-Handbuchabruf**. |
| R2 | [BStBl2022 Nr.S2, LStR2023 vom05.12.2022, Spiegel FragDenStaat](https://media.frag-den-staat.de/files/docs/58/87/65/588765db0e33433fa82243330f2e0feb/bstbl_2022_s2.pdf) | R39b.6 Abs.1–2 auf PDF-S.42–43 von59; R39b.5 auf PDF-S.42; R39b.9 auf PDF-S.44. Text erfolgreich gelesen. Die [NWB-Normfassung R39b.6](https://datenbank.nwb.de/Dokument/1000289_39b___6/) kennzeichnet VZ2023–2026 als aktuell und bestätigt zugänglich Abs.1–2. Alte Abs.4–5 werden hier nicht als neue2026-Sonderfallfreigabe verwendet. |
| P | [BMF PAP2026 Anlage1, endgültig12.11.2025, Spiegel IHK München](https://www.ihk-muenchen.de/ihk/documents/Recht-Steuern/Steuerrecht/Einkommensteuer/2025-11-12-PAP-2026-anlage-1.pdf) | S.3 Rundung/Vorprüfung; S.4 JRE4; S.6 SONSTB; S.14 SOLZFREI; S.33–37 MSONST/STSMIN/MSOLZSTS/MOSONST; S.39 allgemeine Jahresprüftabelle. Text erfolgreich gelesen, einschließlich Kopf „endgültig“. [BMF-Veröffentlichung12.11.2025](https://www.bundesfinanzministerium.de/Content/DE/Downloads/Steuern/Steuerarten/Lohnsteuer/Programmablaufplan/2025-11-12-PAP-2026.html) nachgewiesen; direkte PDF-Versuche scheiterten oder lieferten einen Entwurf25.09.2025. Dieser Entwurf ist **keine** Grundlage dieser Beispiele. |
| S | [§23a SGBIV, Normtext im DRV-Rechtsportal](https://rvrecht.deutsche-rentenversicherung.de/SharedDocs/rvRecht/05_Normen_und_Vertraege/01_Sozialgesetzbuch/04_SGB_IV/pp_0001_25/0023a/0023a_2020_07_01.html) | Abs.1–5 vollständig gelesen; Portal führt Rechtsstand ab01.07.2020. Der direkte Abruf bei Gesetze-im-Internet scheiterte am Timeout. |
| D | [DRV-GRA §23a](https://rvrecht.deutsche-rentenversicherung.de/SharedDocs/rvRecht/01_GRA_SGB/04_SGB_IV/pp_0001_25/gra_sgb004_p_0023a.html), Stand01.06.2023, Version003.00 | Abschnitte2,3,3.2,3.2.1,3.3,4.1–4.3,8,11.1 und Beispiel8 gelesen. Die Jahreszahlen der historischen Beispiele sind keine2026-Grenzwerte. |
| D2 | [DRV-GRA §22](https://rvrecht.deutsche-rentenversicherung.de/SharedDocs/rvRecht/01_GRA_SGB/04_SGB_IV/pp_0001_25/gra_sgb004_p_0022.html) | Abschnitt „Einmalig gezahltes Arbeitsentgelt“ gelesen: Anspruchsentstehung bei Auszahlung, Abgrenzung zur regelmäßigen monatlichen Zwölftelzahlung. |
| K | [DRV Knappschaft-Bahn-See: Die Beitragspflicht von einmalig gezahltem Arbeitsentgelt](https://www.kbs.de/SharedDocs/Downloads/DE/VersicherungsrechtBeitraegeMeldungen/Broschueren/DieBeitragspflichtvoneinmaliggezahltemArbeitsentgelt.pdf?__blob=publicationFile), Impressum StandJanuar2026, Vordruck12251/5.26 | S.18 Abschnitt9.1; S.19 Abschnitt10 und13.1; S.20–21 Abschnitte13.3–13.5. Volltext einschließlich Impressum gelesen. Dies ist eine amtliche Trägerpublikation, kein gemeinsames Rundschreiben aller Spitzenorganisationen. |
| T | [TK: Beiträge aus Einmalzahlungen](https://www.tk.de/resource/blob/2031414/9e6a0f7936f10f5601e9902db664ac5a/beratungsblatt-einmalzahlungen-data.pdf), Kennung305008/06.2026 | S.2–4 Abschnitte3–7; S.5 Abschnitt8. GKV-Trägerinformation, erfolgreich gelesen. Die vereinfachte Übersicht auf S.5 ersetzt keine verbindliche DEÜV-Verfahrensprüfung. |
| B | [BMAS Sozialversicherungsrechengrößen-Verordnung2026](https://www.bmas.de/DE/Service/Gesetze-und-Gesetzesvorhaben/sozialversicherungs-rechengroessenverordnung-2026.html) und [DRV aktuelle KV/PV-Grenzen](https://rvrecht.deutsche-rentenversicherung.de/SharedDocs/rvRecht/07_AktuelleWerte/A-C/awert_bybmgzkvpv.html) | Aktuelle indexierte Tabellen, bestätigt durch vollständig gelesene TK2026-Tabelle S.2: KV/PV69.750 jährlich /5.812,50 monatlich; allgemeine RV/ALV101.400 /8.450 Euro. |

Ein gezielter Suchlauf nach einem aktuellen gemeinsamen GKV-Spitzenverbandsrundschreiben zur **untermonatigen Mehrfachzahlung desselben Arbeitgebers** lieferte keinen zusätzlichen gelesenen Primärbeleg. Die belegte Monatsregel stammt aus K. Mehrfachbeschäftigungsregeln nach §22 Abs.2 sind keine Ersatzquelle für diesen Fall.

## 2. Gesicherte Regeln, knapp mit Fundstelle

### Steuer und tatsächlicher Zufluss

E: §38a Abs.1 unterscheidet beim Steuerjahr laufenden Lohn nach Ende des Lohnzahlungszeitraums und sonstige Bezüge nach Zuflussjahr. §39b Abs.3 verlangt die Jahressteuervergleichsrechnung ohne und mit aktuellem sonstigem Bezug. §41c Abs.1 ermöglicht beziehungsweise verpflichtet unter den dortigen Voraussetzungen zur Korrektur bei nächster Lohnzahlung. Nach Jahres-/Beschäftigungsende begrenzt Abs.3 Änderungen durch die Lohnsteuerbescheinigung; Erstattung nach Jahresende ist grundsätzlich dem Jahresausgleich vorbehalten. Abs.4 regelt die Anzeige nicht nachgeholter Lohnsteuer. **Technische Folgerung:** Neuberechnung, zulässige Steuerkorrektur und tatsächlicher Geldfluss sind getrennte Zustände.

R/R2, R39b.6 Abs.1–2: Maßgeblich ist der tatsächliche Zufluss; die ELStAM gelten zum Ende des Zuflussmonats. Die Prognose berücksichtigt bereits gezahlte sonstige Bezüge, aber keine erst künftig erwarteten sonstigen Bezüge. Der noch erwartete laufende Lohn gehört zur Prognose. **Folgerung:** Ein geplanter Bonus B darf nicht bereits als Vorbezug von A eingehen. Dieselbe Monatsnummer erlaubt nicht, bereits tatsächlich erfüllte und noch offene Ansprüche gleichzusetzen. R39b.5/§39b Abs.5 enthalten besondere Abschlagsregeln für laufenden Lohn; daraus folgt keine generelle Stundung der Bonusbesteuerung bis Monatsabschluss.

P: JRE4(S.4) nennt ausdrücklich sonstige Bezüge aus einem vorherigen Abrechnungszeitraum. MSONST(S.33) bildet den Jahressteuerunterschied; STSMIN(S.34) begrenzt im regulären MBV=0-Zweig negative STS. MSOLZSTS(S.35) bestimmt den Soli anhand der maßgebenden Jahressteuer mit Bezug und der STS, nicht durch Subtraktion zweier Jahres-Solibeträge. **Offen bleibt:** Der gelesene PAP erläutert nicht abschließend die steuerliche Gruppierung mehrerer separat ausgezahlter Bezüge innerhalb desselben Abrechnungsmonats und erforderliche Nachkorrekturen früherer Solibeträge. Ein beliebiger Sortierschlüssel oder Monats-Summenaufruf ist daher noch keine geprüfte Regel.

### Sozialversicherung und Folgezahlungen

S, §23a Abs.1,3–5: Grundsätzlich Auszahlungsperiode; beitragspflichtig nur bis zum verbleibenden anteiligen Grenzbetrag. Für Januar–März kann die gesamte Zahlung ins Vorjahr gehören. Bei KV-Pflicht entscheidet dafür die KV-Grenze; nach31.03. tatsächlich gezahlte Beträge fallen nicht allein wegen rückwirkender Periodenzuordnung unter diese Klausel.

D, Abschnitte3.2,4.1–4.3: Je Versicherungszweig zählen belegte Tage und bereits beitragspflichtiges Entgelt, einschließlich früherer Einmalzahlungen **nur im beitragspflichtigen Umfang**. Beitragssätze/-gruppen stammen aus der Zuordnungsperiode. Historisches Beispiel8 bestätigt den Verbrauch einer früheren Sonderzahlung bei der folgenden Berechnung. D2 trennt tatsächliche Auszahlung von bloßem Einmalanspruch; regelmäßige monatliche Zwölftel verlieren den Einmalcharakter.

K, Abschnitt13.1/S.19: Mehrere Einmalzahlungen eines Monats bis31.03. sind für die Märzklausel **gemeinsam** zu beurteilen. Abschnitt10/S.19: Nachzahlungen gelten grundsätzlich als eigene Gewährung am Auszahlungstermin; bei ursprünglicher Untererfüllung eines von Beginn an bestimmten Anspruchs wird eine Korrektur der ursprünglichen SV-Abrechnung zugelassen. Rückzahlungen verlangen deren Korrektur. Abschnitt13.5/S.21 einschließlich Beispiel zeigt, dass eine rückwirkende Änderung laufenden Entgelts die Jahreszuordnung einer bereits berechneten Sonderzahlung ändern kann. T, Abschnitt8/S.5 bestätigt bei Rückzahlung die rückwirkende Beitragsberechnung und unterscheidet davon die Behandlung im laufenden Beitragsnachweis.

## 3. Konkrete Präzisierung des v7-Vertrags

Die folgenden Punkte sind **eigene technische Ableitungen** für den im Repository vorhandenen Aufbau; keine Aussage, dass die genannten Felder bereits implementiert sind.

1. **Vier Identitäten:** `claim_key` für den Anspruch, `receipt_event_key` für nachgewiesenen Bruttozufluss/Teilzufluss, `tax_group_key` für die fachlich freigegebene Steuerberechnung und `sv_month_group_key` für die gemeinsame Monatsprüfung. Bankteile erhalten weiterhin ihre echte Transaktionsidentität. Keiner dieser Schlüssel darf nur die Monatslauf-ID sein.
2. **Märzklausel zuerst vollständig entscheiden:** Der neue Kompositionskern bildet die vollständige Gruppe tatsächlicher bzw. im Vorschauzweig ausdrücklich geplanter Zahlungen eines Monats. Er prüft die Monatsgruppe gegen die aktuelle belegte SV-Basis. Erst nach Jahreszuordnung werden Zweigbasen verbraucht. Ein neuer Märzbonus kann deshalb auch für einen zuvor aktuellen ersten Märzbonus einen Korrekturplan benötigen. Bestehender Verbrauch dieser Gruppe darf nicht zusätzlich in der Anfangsbasis stehen.
3. **Steuerfolge getrennt:** Je freigegebenem Steuerereignis werden Prognose, bereits gezahlte Vorbezüge, geltende Merkmale, PAP-Eingaben und Ergebnis gebunden. Die SV-Gruppierung darf keine steuerlichen Zuflusstage verschmelzen. Ungeklärte untermonatige Steuergruppierung bekommt einen ausdrücklichen fachlichen Status; keine errechnete Endabrechnung auf Basis einer stillen Annahme.
4. **Zahlungsbeweis statt Nettoquote:** Laufendes Netto am30.10. und Bonusnetto am31.10. sind zwei echte Zahlungsteile. Eine Nettozahlung beweist ohne gebundene Abrechnung/Erfüllungszuordnung nicht, welcher Bruttoteil eines Anspruchs zugeflossen ist. Ein Anspruch kann in mehrere belegte Bruttoereignisse zerfallen; die Summe verbrauchter Teilansprüche darf den wirksamen Anspruch nicht überschreiten. Ein offener Rest wird weder Cash noch Steuerbezug. Nettolohnvereinbarungen, Aufrechnung und Sachleistung benötigen eigene geprüfte Regeln.
5. **Korrekturarten ausdrücklich unterscheiden:** Rechen-/Erfassungsfehler ohne neue Zahlung; neue Nachzahlung; dokumentierte ursprüngliche Untererfüllung; tatsächliche Rückzahlung. Grund, Originalreferenz, tatsächliche Ereignisse und steuerlicher Änderungsstatus werden gebunden. Ein höherer revidierter Anspruch allein darf nicht den ursprünglichen Zufluss vergrößern. Der PAP-Negativschutz darf nicht durch Eingabe eines negativen Bonus umgangen werden.
6. **Abhängigkeiten neu prüfen, Originale behalten:** Ändert sich A, wird die betroffene SV-Monatsgruppe und die fachlich abhängige Steuerfolge einschließlich B neu hergeleitet. Originalrevisionen und tatsächliche Transfers bleiben erhalten; Differenzen werden gesondert ausgewiesen. Vorherige Zahlungen erhalten durch die Neuberechnung kein neues Datum und werden nicht nochmals importiert.

Das ergänzt den bisherigen Plan an einer entscheidenden Stelle: Die dort skizzierte Fortschreibung „nach jedem Ereignis“ ist für SV in Januar–März **nicht als unabhängige Einzelentscheidung innerhalb desselben Monats** umzusetzen.

### Betroffene Bestandsfunktionen und Kompatibilität

| Bestand | Eng begrenzte Erweiterung |
| --- | --- |
| `payroll_oneoff_composition_2026.calculate_oneoff_source`, v6 | Eingefroren lassen. Neuer v7-Kompositionszweig mit getrennter Steuer-/SV-Gruppenbildung. Nicht vollständige v6-Monatsnettos mehrfach addieren. |
| `payroll_oneoff_2026.annual_social_room` / `select_one_off_assignment` | Geprüfte Rechenbausteine unter neuem Orchestrator verwenden; Eingaben gruppenvollständig und ohne Selbstverbrauch herleiten. Alte Semantik nicht ändern. |
| `business_payroll_oneoff_cases._snapshot` / Verbrauchsquittungen | Source4-Sperre für anderen Anspruch desselben Monats erhalten. Neuer Monatsfall benötigt komponentenweise Eigentümerschaft einschließlich Prüfung alter Quittungen. |
| `business_payroll_annual_basis._project_run`, `_relevant_run`, `_snapshot` | Neue Projektion mit getrennten laufenden Perioden, Zuflussereignissen und SV-Gruppen. Die gerade fertiggestellte Source4-Jahresbasis ist Eingangsbestand; nicht erneut implementieren. Nur ersetzte eigene Komponenten aus ihrer Vorbasis ausschließen, keine anderen Vorjahresverbräuche. |
| `business_payroll_accounts._payment_fields`, `_normalize` | Zahlungsquellenvertrag2 für Zuordnung und offene Erfüllung; Altvertrag behält Gleichheitsprüfung zum einzigen Bonusdatum. |
| `payroll_cash_sources.part_key` und Originalteilerhaltung | Echte Transaktionen wiederverwenden; private Aufteilung erzeugt keine weiteren Bankbewegungen. |
| Beide Clients, Ledger und Arbeitnehmerausgabe | Neue Version strikt erkennen; getrennte Zufluss-/Zuordnungsjahre, offene Beträge, Korrekturgrund und Gruppenänderung anzeigen. Keine privaten Jahresoriginale in Arbeitnehmer-/Finance-Ausgaben. |

Alte v5/v6-Regelhashes, gespeicherte Quellen, Berechnungen, Jahresreferenzen, Quittungen, PDFs und Cash-Nachweise bleiben unverändert nachprüfbar. Neue Status-/Gruppenfelder gehören in einen neuen Vertragszweig. Der bestehende Monatslauf wird revisioniert; laufender Lohn bleibt darin genau einmal enthalten. Die neue Quellenversion wird erst nach Kollisionsprüfung benannt/registriert.

## 4. Unabhängig hergeleitete Zahlen- und Grenzfälle

Alle Beträge sind Euro. Die Erwartung wird aus den angegebenen Quellen und einfacher Dezimalarithmetik hergeleitet, **ohne Aufruf des Produktionsrechners**. Wo eine Rechtsfrage offen ist, steht ausdrücklich nur eine Sensitivitätsrechnung, kein Produkt-Sollwert.

### 4.1 Steuerreferenzen und gefährliche Aggregation

Aus P/S.39, allgemeine Prüftabelle, SteuerklasseI: Jahresbrutto40.000→Jahreslohnsteuer4.407;42.500→4.982;45.000→5.570;87.500→18.486;90.000→19.438;92.500→20.390. Parameter: ALV=KRV=PKV=0, KVZ=2,90, PVZ=1; für die abgeleiteten Fälle zusätzlich F=1, ZKF=0, R=0, PVS=PVA=ALTER1=0, keine Freibeträge, Versorgungs-/Entschädigungs-/§19a-Beträge.

| ID | Eingabe und Rechnung | Unabhängige Erwartung / Status |
| --- | --- | --- |
| T1 | Getrennte bereits abgeschlossene Steuerereignisse: Basis40.000; A2.500, danach B2.500 bei unveränderter laufender Prognose. | A=4.982−4.407=575 LSt; B=5.570−4.982=588; zusammen1.163. Zweimal die unveränderte40.000-Basis ergäbe1.150, also13 zu wenig. Als Referenz für **vorangegangene Abrechnungszeiträume** gesichert; untermonatige Gruppenentscheidung separat prüfen. |
| T2 | Basis87.500; A2.500, B2.500; Soli-Freigrenze20.350 aus P/S.14. | Getrennte PAP-Aufrufe: A-LSt952, Soli0; B-LSt952, Soli52,36. Zusammengefasster Aufruf5.000: LSt1.904, Soli104,72. Differenz52,36 beweist fehlende Gruppierungsinvarianz. **Sensitivitätsfall**, bis steuerliche Gruppen-/Nachkorrekturregel für denselben Monat belegt ist. |
| T3 | A wird tatsächlich gezahlt, B ist nur geplant. | B geht nicht als schon gezahlter Vorbezug in A ein. Spätere Änderung/Absage von B darf keinen erfundenen Zufluss in A hinterlassen. |
| T4 | Anspruch2.500; belegter Brutto-Teilzufluss1.000 am31.12.2026, Rest1.500 am02.01.2027. | Zwei Zuflussjahre; kein gesamter2026-Zufluss aus dem ursprünglichen Anspruch ableitbar. Der2027-Rechenzweig bleibt ohne eigene Regeln gesperrt. Ein bloßer Teilnetto-Bankbetrag genügt nicht als Bruttoaufteilung. |

### 4.2 SV-Monatsgruppe, Schwellen und Folgezahlungen

Voraussetzung für S1–S4: reguläre durchgängige KV-pflichtige Beschäftigung beim selben Arbeitgeber auch im Vorjahr; 2026 laufend5.000 monatlich, volle SV-Monate, keine anderen aktuellen Einmalbezüge. Abweichende Vorjahresräume werden jeweils als **bereits belegte Eingangsgröße** bezeichnet, nicht aus unbenannten Vorjahreswerten geschätzt.

| ID | Eingabe und Handrechnung | Erwartung |
| --- | --- | --- |
| S1 | März-KV-Grenze69.750×90/360=17.437,50; laufend15.000; Raum2.437,50. A1.500 am10.03., B1.000 am25.03. | Gemeinsam2.500>2.437,50: gesamte Monatsgruppe ins Vorjahr. A darf nicht endgültig aktuell bleiben, nur weil es allein zuerst passte. Der KV-Auslöser gilt auch für RV/ALV. |
| S2 | Wie S1, aber B937,50; Variante B937,51. | Bei Gesamtsumme2.437,50 keine Überschreitung; bei2.437,51 Vorjahreszuordnung der gesamten Gruppe. Exakter Centvergleich, keine Float-Toleranz. |
| S3 | Januar A1.000: aktueller KV-Raum812,50. Vorjahresraum vor A: KV1.000/RV2.000. Februar B2.000: aktueller KV-Raum1.625. | A ins Vorjahr, verbraucht je1.000. B ebenfalls ins Vorjahr, verbleibende beitragspflichtige Basis KV0/RV1.000. Frühere Vorjahresverbräuche bleiben erhalten; Steuerjahr beider Zahlungen2026. Andere Monate sind keine gemeinsame März-Monatsgruppe. |
| S4 | Märzgruppe2.400 zunächst bei laufend15.000: Raum2.437,50. Danach belegte rückwirkende Erhöhung laufend um insgesamt100. | Neuer Raum2.337,50: Zuordnung der Gruppe kippt ins Vorjahr. Erforderlich ist eine dokumentierte Folgeberechnung, kein bloßes Update des laufenden Nettos. K/S.21 Beispiel unterstützt diesen Mechanismus. |
| S5 | Mai: laufend25.000; KV-Grenze29.062,50, Raum4.062,50; RV-Grenze42.250, Raum17.250; A5.000 und B1.000. | Gesamt beitragspflichtig KV4.062,50/RV6.000. Ein beitragsfreier Teil von A darf keine zusätzliche Luft verbrauchen. Die Verteilung von Gruppenbeiträgen auf Komponenten muss Cent-Summen erhalten und fachlich festgelegt werden. |
| S6 | Identischer Anspruch mit tatsächlichem Zufluss31.03. versus01.04.; sonst gleiche belegte Person/Jahresbasis. | March-Entscheidung nur für den31.03.-Fall. Eine rückwirkende Zuordnung des Aprilzuflusses in eine Märzperiode begründet für sich keine Märzklausel. |
| S7 | Zwei gleiche Ansprüche/Bruttobeträge, Eingabeliste A,B versus B,A; Datum und Nachweise unverändert. | Gleiche SV-Monatsgruppe, gleiche Gesamtzuordnung und Zweigbasen. JSON-Reihenfolge darf keine andere Jahresentscheidung erzeugen. |

### 4.3 Korrektur, Zahlungsnachweis und Historie

| ID | Fall | Erwartung |
| --- | --- | --- |
| K1 | Märzgruppe A+B; A wird später korrigiert, B bleibt wirksam. | Neue Revision enthält A und B und prüft die gesamte Gruppe. Nur A als eigener ersetzter Bestandteil wird aus der entsprechenden Vorbasis entfernt; fremde/andere Verbräuche bleiben. |
| K2 | Ursprünglich vereinbart1.000, später neu beschlossener zusätzlicher Bonus200 versus ursprünglich vereinbart1.200, irrtümlich nur1.000 ausgezahlt. | Unterschiedliche belegte Korrekturarten. Nicht jeden neuen Betrag als rückwirkende Anspruchsrevision behandeln. Die SV-Erleichterung für Untererfüllung schreibt den Steuerzufluss nicht automatisch zurück. |
| K3 | Gezahlter Bonus wird rechnerisch um200 vermindert, aber keine Rückzahlung nachgewiesen. | Keine erfundene Cash-Gutschrift. Tatsächlicher Transfer bleibt stehen; Differenz/Erstattungsanspruch bleibt offen. Steueränderung durch §41c-Status begrenzen. |
| K4 | Laufendes Netto30.10.; vollständiges Bonusnetto31.10.; danach zweiter tatsächlich belegter Bonus. | Drei unveränderte echte Transfers, laufende Monatsrechnung einmal, zwei eigene Bonusereignisse. Kein Teil wird auf ein gemeinsames Datum verschoben oder doppelt in Cash übernommen. |
| K5 | Eine Banküberweisung erfüllt laufend+A+B. | Ein Cash-Vorgang, private Zuordnungen summieren sich exakt zu dessen Betrag; dieselbe Referenz erzeugt keine drei vermeintlichen Originalüberweisungen. |
| K6 | Korrektur nach übermittelter Lohnsteuerbescheinigung beziehungsweise nach Jahresende. | Historie/Neuberechnung bleibt möglich, aber keine automatische reguläre Steuererstattung allein aus negativem Rechendelta. Gesetzlich zulässiger Korrekturweg muss belegt sein. |

## 5. Noch zu schließende Fachfragen und kleinster sicherer Beginn

| Offene Frage | Konkreter Abschlussnachweis vor Freischaltung |
| --- | --- |
| Steuerliche Behandlung mehrerer realer Zuflüsse innerhalb desselben Monats, gleichzeitig gezahlte verschiedene Ansprüche | Aktuelle BMF-Verwaltungsfundstelle oder fachlich dokumentierte Auskunft mit Beispielen für getrennte Tage und einen gemeinsamen Tag; Abgleich zu JRE4-Wortlaut und T2. Insbesondere klären, ob/wann eine spätere untermonatige Abrechnung frühere LSt/Soli aufrollt. |
| Teilzufluss eines einzelnen Bruttoanspruchs und Zeitpunkt der Nachkorrektur bei späterem SV-Gruppensprung | Verbindlicher Brutto-Erfüllungsnachweis, Abzug-/Restanspruchsbehandlung und Ablauf einer späteren Nach-/Erstattung. Keine pauschale Nettoquote. |
| Aufteilung gemeinsamer SV-Gruppenbeiträge auf einzelne Zahlungsereignisse | Fachlich geprüfte Zuordnungs- und Rundungsregel, einschließlich Korrektur bereits ausgezahlter Netti. Gesamtbasis allein beantwortet nicht, welcher Zahlungsnettoanspruch sich nachträglich ändert. |
| Steuerliche Rückzahlung/negativer Arbeitslohn und Jahreswechsel | Eigener Quellenfall mit tatsächlicher Rückzahlung, §41c-/Bescheinigungsstatus und Abgrenzung zum Jahresausgleich; nicht allein SV-Rückrechnung auf Steuer übertragen. |
| Aktuelle vollständige Primärabrufe und Meldedetails | BMF-Handbuch2026 vollständig erfolgreich abrufen; benötigte aktuelle gemeinsame Melde-/Beitragskorrekturregeln gezielt prüfen. Keine echte DEÜV-/ELSTER-Übermittlung aus diesem Rechercheergebnis ableiten. |

Unabhängig davon können jetzt die additiven Identitäten, Originalreferenzen, getrennten Zahlungsnachweise, Erfüllungszustände, SV-Monatsgruppierung und Negativfälle entwickelt werden. Erster freischaltbarer fachlicher Umfang muss ausdrücklich benannt sein; unbekannte steuerliche Untermonatsgruppen dürfen nicht mit plausiblen Zahlen als fertig erscheinen. Bestehende v6-Fälle mit einem Anspruch bleiben weiter nutzbar, soweit ihre bereits geprüften Grenzen eingehalten werden.

Backend-Verantwortlicher hat am04.11.2026 bestätigt, nach Abschluss von v6 auf Root-Zuweisung den v7-Vertrag übernehmen zu können. Ihm und der Integration wurden die KBS-Monatsregel und die Korrekturabgrenzung direkt übermittelt. Dieses Dokument ersetzt keine neue Zuweisung und behauptet keine bereits erfolgte v7-Implementierung.

Dokumentprüfung am04.11.2026: 15 unabhängige Dezimalrechnungen mit Python `decimal` gegen festgehaltene Sollwerte geprüft; alle stimmen. 17 eindeutige Fallkennungen, lokale Verknüpfungen und Leerzeichen am Zeilenende geprüft. Keine Produktionsfunktionen importiert oder Produkttests als Teil dieser Recherche ausgeführt. Der Backend-Verantwortliche bestätigte anschließend den von Root erteilten v7-Auftrag; die offenen Steuergruppenfragen wurden ihm dabei ausdrücklich genannt.
