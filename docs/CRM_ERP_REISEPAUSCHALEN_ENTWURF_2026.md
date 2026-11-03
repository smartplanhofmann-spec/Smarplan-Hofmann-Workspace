# Reisepauschalen 2026: Fachvertrag und additive Umsetzung

Stand: 3. November 2026. Konkretisierung von Abschnitt 6 des
[Lohn-Lückenplans](CRM_ERP_LOHN_LUECKENPLAN_2026.md). Dieses Dokument ist der
Umsetzungsentwurf; es behauptet weder einen bereits abgenommenen Reiseberechner
noch eine tatsächliche Zahlung oder amtliche Meldung. Der Auftrag umfasst die
vollständige Inland-/Auslandstabelle 2026 und die fachlich verbundenen Prüfwege,
nicht nur zwei ausgewählte Länder.

## Befund im bestehenden Programm

`business_personnel_workflow._expense_payload` erfasst gegenwärtig tatsächliche
EUR-Auslagen mit einem unveränderten Original je Position. Seine ausdrücklichen
Ergebnismerkmale sind `allowance_calculation=False` und
`tax_treatment='not_determined'`. Der vorhandene Weg umfasst Einreichen, fremde
Freigabe, tatsächliche vollständige Erstattung und bestätigte Rückzahlung.
Reisebeginn/-ende sind bisher nur Datumsangaben. Tätigkeitsstätten, einzelne
Abwesenheitsintervalle, Länderwechsel und Mahlzeiten fehlen.

`business_payroll` und `business_payroll_accounts` halten Reisekosten ausdrücklich
außerhalb des Gehaltsnettos. `payroll_cash_sources.Sources.account` lehnt Quellen
mit zusätzlichen steuerfreien Bezügen ab. Die vorhandene PayrollCash-Brücke darf
deshalb nicht durch Umbenennen einer Reisepauschale in Barlohn benutzt werden.
`business_accounting_euer` kennt die Ausgabenkategorie `travel`, hat aber noch
keine automatische, private und gegen Doppelerfassung gesicherte Reisequelle.
Die Verknüpfung von Erstattung und Geldjournal ist echte neue Entwicklungsarbeit.

## Amtliche Quellen und Nachweisstand

| Quelle | Gegenstand | Tatsächlicher Nachweis dieses Entwurfs |
|---|---|---|
| [EStG §9 Abs.4/4a](https://www.gesetze-im-internet.de/estg/__9.html) | Tätigkeitsstätte, Tagesanspruch, Mahlzeiten, Frist | Vollständiger Normtext gelesen; nur die einschlägigen 2026-Regeln übernehmen |
| [BMF 05.12.2025, GZ IV C 5 – S 2353/00094/007/012](https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Lohnsteuer/2025-12-05-steuerliche-behandlung-reisekosten-2026.pdf?__blob=publicationFile&v=5) | Ausland ab 01.01.2026, sieben Tabellenblätter nach drei Textseiten | Text und sämtliche Tabellenabschnitte über die Webquelle gelesen; noch kein lokal gespeicherter PDF-Originalhash |
| [BMF 25.11.2020, amtliches Schreiben als IHK-PDF](https://www.ihk.de/blueprint/servlet/resource/blob/5260010/6167648501baf85de6053f701b93e9b5/bmf-schreiben-25-11-2020-data.pdf) | Rz.47–59, 61–99, 117–135; weiterhin in LStH 2026 referenziert | Relevante Abschnitte mit amtlichen Beispielen gelesen; alte Sachbezugswerte nicht übernehmen |
| [LStH 2026 R9.6](https://ao.bundesfinanzministerium.de/lsth/2026/A-Einkommensteuergesetz/II-Einkommen-2-24b/4-Ueberschuss-d-Einnahmen-ueber-die-Werbungsk-8-9a/Paragraf-9/r-9-6.html) | Flug-/Schiffsreisen und Ersatzländer | Amtliche indexierte Regeltexte verfügbar; vollständiger HTML-Abruf derzeit 503 |
| [EStG §3 Nr.16](https://www.gesetze-im-internet.de/estg/__3.html), [§40 Abs.2](https://www.gesetze-im-internet.de/estg/__40.html) | Steuerfreie Erstattung, zulässige Pauschalversteuerung | §3 vollständig gelesen; §40 über amtlichen Index und BMF Rz.58–59/94–99 gegengeprüft |
| [Knappschaft-Bahn-See: Sachbezugswerte 2026](https://www.kbs.de/DE/AngeboteFuerFirmen/VersicherungsrechtBeitraegeUndMeldungen/news/25_08_Sachbezugswerte_2026?nn=69281838401de22f3aa41c76), [SvEV §2](https://www.gesetze-im-internet.de/svev/__2.html) | Mahlzeiten-Sachbezug | Amtlich indexiert: Frühstück 2,37 EUR, Mittag/Abend je 4,57 EUR; zeitlich passende Normfassung vor Freigabe festschreiben |

Der konkrete Abruf des BMF-PDF im Cloud-Executor wurde auch mit der gezielten
Netzwerkfreigabe versucht; der Netzwerkproxy antwortet `403 Forbidden`. Das ist
kein erfolgreicher Originaldownload. Die Webquelle liefert den amtlichen Text,
aber keine Originalbytes. Die Umsetzung muss deshalb den Hash eines nachweislich
abgerufenen Originals oder einen ausdrücklich als solchen bezeichneten Hash der
abgenommenen Transkription verwenden. Beides darf nicht verwechselt werden.

## Regelumfang

Die nachstehenden Regeln werden als nachvollziehbare Rechenschritte mit
Fundstelle ausgegeben. Widersprüchliche oder fehlende Eingaben erzeugen konkrete
offene Entscheidungen; sie werden nicht als Nullanspruch oder als steuerfrei
behandelt.

| Bereich | Erforderliches Verhalten |
|---|---|
| Inland | 28 EUR am vollen Kalendertag; 14 EUR für An-/Abreise mit zugehöriger Auswärtsübernachtung; ohne Übernachtung erst bei mehr als acht Stunden. Mehrere Abwesenheiten werden ohne Überschneidungen zusammengeführt. Übernachtarbeit wird nach der überwiegenden Abwesenheit zugeordnet; ein Tagesanspruch darf nicht doppelt entstehen. |
| Ausland | Veröffentlichten vollen und kurzen Betrag getrennt speichern; den kurzen Betrag nicht aus dem vollen zurückrechnen. Tagesort aus tatsächlichen Orts-/Tätigkeitsereignissen bestimmen. Rückkehr und weitere Reise am selben Tag erhalten nur den höheren Anspruch. Mahlzeitenkürzung verwendet den maßgeblichen Tagessatz, nicht das Land der Mahlzeit. |
| Gesamte Tabelle | Alle veröffentlichten Staaten, Stadt-/Gebietsausnahmen und Restgebiete; Mikronesien→Philippinen sowie die im Schreiben genannten Karibik-/Südamerikastaaten→Trinidad und Tobago. Nicht aufgeführte Staaten→Luxemburg, nicht aufgeführte Außengebiete→Mutterland. Unbekannte freie Ortsnamen dürfen keinen stillen Ersatzsatz auslösen. |
| Beförderung | Flugland nach Landung; bloße Zwischenlandung nur bei notwendiger Übernachtung relevant; Zwischenflugtage bei mehr als zwei Kalendertagen nach Österreich. Schiffstage nach Luxemburg, Ein-/Ausschiffung nach Hafen; besondere deutsche Schiffsbesatzung ausdrücklich gesondert. |
| Tätigkeitsstätten | Tatsächliche ortsfeste Stätte unabhängig von Projekt-ID erfassen. Dasselbe Betriebsgelände bleibt eine Stätte; verschiedene Kundenstätten werden getrennt beurteilt. Ab drei tatsächlichen Tagen pro Woche greift die Dreimonatsprüfung, einschließlich belegter Vorgeschichte vor 2026. Vier volle Wochen Unterbrechung starten neu. Mobile Einrichtungen und weiträumige Gebiete sind eigene Fallarten. |
| Verpflegung | Frühstück 20 %, Mittag/Abend je 40 % des vollen Tagesbetrags; Eigenentgelt mindert die jeweilige Kürzung, Gesamtkürzung höchstens Tagesanspruch. Nicht gegessene bereitgestellte Mahlzeit kann weiterhin kürzen; Ersatzmahlzeit, bloßer Snack, eigenständige Fremdbewirtung und Arbeitgeberveranlassung werden getrennt erfasst. |
| Sachbezug/Steuer | Übliche gestellte Mahlzeit ohne dem Grunde nach zulässige Pauschale benötigt Sachbezugsprüfung. Belohnungsessen über 60 EUR und ein normaler Pauschalenüberschuss sind unterschiedliche Steuerfälle. Großbuchstabe M ist eine eigene Lohnkontoquelle. Zulässiger 25-%-Weg wird ausdrücklich gewählt und begründet; nach Ablauf der Dreimonatsfrist gilt er nicht für zusätzliche Verpflegungspauschalen. |
| Übernachtung | Arbeitnehmererstattung darf bei erfüllten Voraussetzungen die veröffentlichte Pauschale oder tatsächlichen Aufwand verwenden. Bereits bezahlte Unterkunft, tatsächlicher Auslagenbeleg und Pauschale dürfen sich nicht doppeln. Unterkunfts-/Mahlzeitenaufteilung erhält eine eigene Herleitung. Unternehmer-EÜR und Arbeitnehmer-Werbungskosten verwenden keine automatische Übernachtungspauschale. |
| Zusammenfassung | Abrechnungseinheit ausdrücklich festlegen. BMF Rz.134 erlaubt unter Voraussetzungen eine Zusammenfassung zulässiger steuerfreier Beträge; eine bloß tägliche Überschussformel wäre unvollständig. Vorherige Erstattungen und bereits verbrauchte Freigrenzen bleiben gebunden. |

Kontrollwerte aus der Auslandstabelle, jeweils voller/kurzer/Übernachtungsbetrag:
Belgien 59/40/141, Bern 82/55/195, Genf 70/47/197, Luxemburg 63/42/139,
Österreich 50/33/117 EUR. Amtliches länderübergreifendes Beispiel 2026:
Straßburg→Wohnung→Kopenhagen, gestelltes Frühstück in Frankreich:
50 − 20 % × 75 = **35 EUR**. Das ist eine unabhängige Erwartung, keine Ableitung
durch den später getesteten Berechner.

Die 2020-Beispiele erklären die Methode; darin genannte ausländische Beträge,
Mahlzeiten-Sachbezugswerte und die damalige Kraftfahrerpauschale sind keine
2026-Parameter. Letztere beträgt nach aktuellem §9 Abs.1 Satz3 Nr.5b 9 EUR und
benötigt einen gesonderten, im Kalenderjahr einheitlichen Behandlungsnachweis.
Doppelte Haushaltsführung, gemischt veranlasste Reisen und Unternehmerreisen
bleiben benannte eigenständige Regelzweige. Ihre Voraussetzungen dürfen nicht
durch eine gewöhnliche Arbeitnehmerreise als erfüllt gelten.

## Datenvertrag und unveränderliche Quellen

Vorgesehen sind eigene Module `payroll_travel_2026.py`,
`payroll_travel_rates_2026.py`, `business_travel_allowances.py` und
`travel_allowance_cash.py`. Alte Personal-/Lohnschemas, Quittungen und
Regelversionen bleiben unverändert lesbar. Der reine Berechner benötigt keine
Datenbank und führt keine externe Aktion aus.

1. **Orts- und Zuordnungsnachweis:** stabile Stätten-ID, Typ Wohnung/erste
   Tätigkeitsstätte/auswärtige feste Stätte/mobil/weiträumig, Gültigkeitszeitraum,
   Originalreferenz, Autor, Änderungsgrund und Revision. Projekt-ID ist ein
   optionaler Kostenbezug, keine steuerliche Stättenidentität.
2. **Reise:** Mitarbeiter, Zweck, tatsächliche Abwesenheitsintervalle mit
   IANA-Zeitzone und eindeutiger UTC-Zeit, Ortswechsel, Tätigkeit/Transit,
   Übernachtung, privater Anteil, Mahlzeitenherkunft/-art/-kosten/Eigenanteil,
   tatsächliche Stättenbesuche und belegte Vorgeschichte. Überlappungen,
   mehrdeutige Sommerzeitpunkte und ungeklärte Datumsgrenze werden zurückgewiesen.
3. **Berechnung:** Eingabehash, Regel-/Tabellenhash, verwendete Ortsnachweise und
   Historienrevision, Tagesherleitung, zulässiger steuerfreier Betrag,
   Sachbezug, pauschalierbarer und individuell steuerpflichtiger Anteil,
   tatsächlicher gewünschter Erstattungsbetrag, vorherige Erstattungen und
   getrennte offene Entscheidungen. Kein Fließkommageld.
4. **Abrechnung:** unveränderliche genehmigte Fassung mit allen Quellhashes,
   ausgewählter Abrechnungseinheit und PDF/JSON. Änderungen erzeugen neue
   Fassungen; bereits bezahlte Quellen verlangen eine echte Ausgleichsbuchung.
5. **Zahlung:** tatsächlicher Tag, Betrag, Bank-/Kassennachweis und Original,
   ausgewählte unverbrauchte Positionen, Auszahlung oder Rückzahlung.
   Rein rechnerischer Anspruch ist kein Geldfluss.

Additive Tabellengruppen: Stättennachweise, Reisestamm und Reiseversionen,
Abrechnungen, Tages-/Quellenbelegungen, Zahlungs-/Ausgleichsereignisse sowie
technische Referenzquittungen. Stabile SQL-Namen und Spalten werden vor globaler
Registrierung separat übergeben. Append-only-Guards, aktuelle Rechte,
kanonische Hashes und Wiederherstellungsprüfung gelten für jede Gruppe.
Die Kombination Mitarbeiter+Kalendertag wird bei Freigabe unter echter
Datenbanksperre geprüft. Neu hinzugekommene Reisen, Stättenbesuche oder
Erstattungen machen eine alte Vorschau ungültig; eine Vorschau reserviert noch
keinen Anspruch.

## Fachablauf und Clients

Unter Personal erscheint „Reisen und Pauschalen“ neben den tatsächlichen
Auslagen. Mitarbeiter erfassen eigene Reisen mit benannten Orten und Belegen.
Tagesansprüche, Kürzungen und offene Nachweise werden vor dem Einreichen
sichtbar. Die prüfende Person bestätigt die maßgebliche Tätigkeitsstätte,
vollständige Vorgeschichte, Abrechnungseinheit und Steuerentscheidung. Eigene
oder selbst eingereichte Anträge können nicht selbst genehmigt werden.

Vorgesehene API unter `/personnel/travel`: Länder-/Regelkatalog, Stättennachweise,
Reisen samt Historie, Vorschau, Einreichen, Zurückweisen, Freigeben,
Abrechnungsdownload und Referenzstatus. Zahlung und Finanzprojektion erhalten
eigene Endpunkte. Jeder Schreibauftrag bindet `request_id`, erwartete Revision
und exakte Quellenhashes. Nach unbekannter Antwort wird zunächst die eigene
Referenz abgefragt; kein neuer Auftrag und keine automatische Zahlung.

Browser `web/office/travel-allowances.js` und Flutter
`app/lib/business_travel_allowances.dart` verwenden denselben Vertrag.
Fachrechte `personnel.read/write/approve/export`, eigene Mitarbeiterzuordnung
und tatsächliche Projektrechte werden vor jedem Quellzugriff erneut geprüft.
Finanzfreigabe benötigt zusätzlich die vorhandenen Finanz-/Buchführungsrechte.
Private Texte und unbestätigte Aufträge bleiben im RAM und verschwinden bei
Abmelden, Rechte-/Mitarbeiterwechsel und Hintergrundwechsel. Öffentliche
Finanzprojektionen enthalten keine Reiseroute, Mitarbeiteranschrift oder Mahlzeit.

## Brücke zu Auslagen, Lohnkonto, Geldjournal und EÜR

Ein gemeinsamer Quellennachweis reserviert tatsächliche Belegpositionen und
Pauschalen getrennt. Bestehende bereits erstattete Auslagen werden als bezahlt
referenziert und nicht nochmals ausgezahlt. Die alte Auslagen-Erstattungsaktion
muss eine anderweitig gebundene Quelle erkennen; diese enge Schutzintegration
benötigt keinen Umbau historischer Personalevents.

Steuerfreie Reisepauschalen gehen in einen eigenen tatsächlichen Zahlungsweg.
Individuell steuerpflichtige Beträge und Sachbezüge gehen mit unveränderlicher
Herkunft in den abgestimmten Lohn-Entgeltartenvertrag; sie werden nicht gleichzeitig
als steuerfreie Reiseauszahlung markiert. Nettolohn und ein bereits geleisteter
Vorschuss müssen getrennt verrechnet werden. Bis der jeweilige Lohnzweig die
Quelle vollständig verarbeitet, bleibt seine endgültige Freigabe sichtbar offen.
Das ist eine Entwicklungsabhängigkeit, keine externe Zulassungsfrage.

Die Reise-Finanzprojektion folgt dem vorhandenen privaten/öffentlichen Muster
der PayrollCash-Brücke: ein signierter Quellenhash mit gruppiertem Datum,
Betrag und Kategorie. Gemeinsame Beleg-/Originalreservierung verhindert eine
zweite Erfassung als freier Geldjournal-, Bank-, Lohn- oder Reiseposten.
EÜR übernimmt ausschließlich belegte tatsächliche Zahlungen mit expliziter
Steuerentscheidung. Eine Pauschale erzeugt keine Vorsteuer. Ein bereits in der
Lieferantenrechnung bezahltes Hotel wird nicht erneut als Mitarbeiterauslage
angesetzt. Korrekturen lassen frühere Geldfluss- und Jahresnachweise bestehen.

Personenbezogene Orts-/Reisedaten gehören in das bestehende Datenschutzinventar
mit `personnel`-Schutzbedarf und quellenbezogener Aufbewahrung. Gesamtexport und
Datenschutzfall prüfen die aktuellen Personalrechte; Rohoriginale werden nicht
zu allgemein sichtbaren Projektunterlagen. Keine zusätzliche pauschale
Aufbewahrungsfrist für freie Reisetexte erfinden.

## Umsetzung und Abnahme

| Paket | Konkrete Änderungen | Nachweis vor Abschluss |
|---|---|---|
| T1 – deterministischer Regelkern | Gesamte 2026-Ratentabelle mit Herkunftsmanifest, prüfbare Tages-/Orts-/Mahlzeiten-/Fristregeln in eigenen Dateien | Jede Tabellenzeile gegen Quelle geprüft; unabhängige BMF-Fälle, Grenzzeiten, Jahres-/Zeitzonenwechsel, keine stillen Standards bei fehlenden Fakten |
| T2 – privater vollständiger Ablauf | Neue Fachhistorie, Quellenbelegung, strikte API, Browser/Flutter, unveränderliche Abrechnung | Eigene/fremde Rechte, Vier-Augen-Prüfung, Quellendrift, verlorene Antwort, echte MFA/HTTP und mobile Ansicht |
| T3 – Erstattung und steuerliche Übergabe | Enge Auslagensperre, getrennte steuerfreie Zahlung, abgestimmte Lohnkonto-/Steuerquellen, öffentliche Finanzprojektion | Doppelerfassung in beiden Richtungen gesperrt, tatsächliche Teil-/Rückzahlung, fehlende Steuerverarbeitung verhindert falsche Endfreigabe |
| T4 – Integration und Wiederherstellung | Expliziter Export-/Privacykatalog, Packaging, CI, echte PostgreSQL-Parallelität, Backup/Restore | Historische Lohn-/Auslagenexporte unverändert; aktuelle Finanzhorizonte bleiben gesperrt bis Abgleich; keine Wiederbelebung erledigter oder gelöschter Privatinhalte |

Konkrete Referenzfälle: 8:00/8:01 Stunden, zwei Reisen am selben Tag, Nachtarbeit
ohne Schlafen, voller Zwischentag, Rückkehr für eine Stunde, Frühstück 14−5,60,
alle drei Mahlzeiten→0, Eigenanteil und Ersatzmahlzeit, Belgien/Bern/Genf und
Restgebiet, Straßburg/Kopenhagen→35 EUR, Sommerzeit und Datumsgrenze,
April–Juni versus Juli, zwei versus drei Stättentage je Woche, 27/28 Tage
Unterbrechung, gleiche Stätte über Projektwechsel, mobile Tätigkeit,
Vorgeschichte vor Jahresbeginn, tatsächliche Unterkunft versus Pauschale,
steuerpflichtiger Überschuss, 25-%-Grenze, Mahlzeit ohne Pauschalanspruch,
gemeinsame Abrechnung nach BMF-Beispiel 70, bereits erstatteter Originalbeleg,
gleichzeitige Freigaben, Rollenentzug während Download, Altbackup und Neustart.

Globale Registrierung/Packaging/Retry sowie Änderungen der parallel entwickelten
Lohn-Zeitachsen werden mit dem Integrationsverantwortlichen abgestimmt. T1 kann
ohne Mutation gemeinsamer Schemas beginnen. Echte Stammdaten, externe
Übermittlung und Produktivfreigabe sind für die synthetische Entwicklung nicht
erforderlich und werden hier nicht ausgeführt.
