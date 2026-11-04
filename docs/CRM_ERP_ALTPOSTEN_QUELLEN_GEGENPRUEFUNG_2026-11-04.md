# Alte offene Posten: unabhängige Quellen- und Vertragsgegenprüfung

Stand und Abruf: **04.11.2026**. Arbeitsbaum: `/workspace/smartplan-opening-items-20261104`.
Gegenstand ist ausschließlich die Fortführung eines bestehenden Einzelunternehmens
mit EÜR, Regelbesteuerung und belegter Istbesteuerung beim technischen Softwarewechsel.
Dieses Dokument ändert keinen Produktcode und bestätigt keine fachliche Zulassung,
Steuererklärung oder Vollständigkeit eines Unternehmensjahres.

## Ergebnis und Voraussetzungen

**Ein unbezahlter Rechnungsrest wird beim Import nicht zu einer Zahlung.** Bei einer
späteren tatsächlichen Zahlung gelten für den hier begrenzten Fortführungsfall:

| Ursprungsfall | Neue Geldbewegung | Neue EÜR-Wirkung | Neue Umsatzsteuer-Wirkung |
| --- | --- | --- | --- |
| Alte Kundenrechnung, bisher nicht vereinnahmter Rest; durchgehend genehmigte Istbesteuerung | Tatsächlich erhaltenes Brutto | Nettoerlös und vereinnahmte USt getrennt | USt auf den neu vereinnahmten Anteil |
| Alte Lieferantenrechnung, Vorsteuer **bereits rechtmäßig und vollständig vor dem Wechsel abgezogen**, Rest noch nicht bezahlt | Tatsächlich ausgezahltes Brutto | Laufender Nettoaufwand und bezahlte abziehbare Vorsteuer getrennt | **Kein erneuter Vorsteuerabzug** |
| Import der Forderung/Verbindlichkeit oder Übernahme eines Bankanfangsbestands | Keine | Keine | Keine |

Dies folgt für die Zahlungszeitpunkte aus [§ 11 EStG](https://www.gesetze-im-internet.de/estg/__11.html),
für Ist-USt aus [§ 13 Abs. 1 Nr. 1 Buchst. b UStG](https://www.gesetze-im-internet.de/ustg_1980/__13.html)
und für die EÜR-Wirkung gezahlter Umsatzsteuer insbesondere aus
[BFH, 29.10.2020, VIII B 54/20, Gründe Rz. 6](https://www.bundesfinanzhof.de/de/entscheidung/entscheidungen-online/detail/STRE202150002/).
Die Behandlung des technischen Imports ist die daraus abgeleitete Vertragsentscheidung,
keine in diesen Normen eigens geregelte Softwarefunktion.

Vorausgesetzt sind voll betriebliche gewöhnliche inländische EUR-Rechnungen mit
geprüften 19- oder 7-Prozent-Komponenten. Leistung und ursprüngliche Rechnung liegen
vor `bookkeeping_start`, aber innerhalb des belegten umsatzsteuerlichen Geltungszeitraums.
Die ursprünglichen Beträge, tatsächlichen früheren Zahlungen und deren Netto-/Steueranteile
sind nachgewiesen. Die vorliegende Prüfung setzt diese Angaben nicht für ein Unternehmen.

## Gelesene amtliche Belege

Der Abrufnachweis steht in
[sources.json](evidence/altposten-quellen-2026-11-04/sources.json).
Er unterscheidet direkt gelesenen Webtext, nicht erreichbare Dokumente und Suchtreffer.
Das sind dokumentierte Rechercheauszüge; es wurden keine unveränderten amtlichen
HTML-/PDF-Originaldateien archiviert.

| ID | Amtliche Quelle und genaue Fundstelle | Bedeutung und Grenze |
| --- | --- | --- |
| S01 | [§ 4 EStG](https://www.gesetze-im-internet.de/estg/__4.html), Abs. 3 Sätze 1–4 und Abs. 4; amtliche Einzelnorm am 04.11.2026 direkt gelesen | EÜR ist die Gegenüberstellung betrieblicher Einnahmen und Ausgaben. Besondere Anlage-/AfA-Regeln gelten daneben. Der hier betrachtete gewöhnliche Aufwand darf diese Ausnahmen nicht verdrängen. |
| S02 | [§ 11 EStG](https://www.gesetze-im-internet.de/estg/__11.html), Abs. 1 Satz 1 und Abs. 2 Sätze 1–3; direkt gelesen | Maßgeblich sind tatsächlicher Zufluss/Abfluss; gesetzliche Ausnahmen sind gesondert zu prüfen. Alte Rechnungsdaten verschieben gewöhnliche spätere Zahlungen nicht in das Rechnungsjahr. |
| S03 | [§ 13 UStG](https://www.gesetze-im-internet.de/ustg_1980/__13.html), Abs. 1 Nr. 1 Buchst. a/b; direkt gelesen | Bei Istbesteuerung entsteht die Steuer mit Ablauf des Voranmeldungszeitraums der Vereinnahmung. Rechnungsdatum, Softwareimport und bloße offene Forderung lösen diesen Zufluss nicht aus. |
| S04 | [§ 20 UStG](https://www.gesetze-im-internet.de/ustg_1980/__20.html), Eingangssatz und Schlussregel zum Besteuerungswechsel; direkt gelesen | Istbesteuerung benötigt die Gestattung des Finanzamts. Ein Besteuerungswechsel verlangt Schutz vor doppelter oder ausbleibender Besteuerung und ist nicht Teil dieses einfachen Übernahmefalls. |
| S05 | [§ 15 UStG](https://www.gesetze-im-internet.de/ustg_1980/__15.html), Abs. 1 Satz 1 Nr. 1, Abs. 2/4; direkt gelesen | Die Abzugsberechtigung setzt eigene rechtliche Tatsachen voraus. Vorauszahlungen und Einschränkungen sind gesonderte Fälle. Eine spätere Zahlung setzt einen bereits wirksam ausgeübten gleichen Anspruch nicht nochmals frei. |
| S06 | [ELSTER-Anleitung EÜR **2025**](https://www.elster.de/eportal/helpGlobal?themaGlobal=help_euer_ufa_77_2025), Abschnitte zu Zeilen 15/17/18, 57/58 und 89; direkt gelesen | Erlös und vereinnahmte USt, bezahlte Vorsteuer sowie tatsächliche Finanzamtszahlungen/-erstattungen haben getrennte EÜR-Kategorien. Zeile 89 betrifft den echten Wechsel der Gewinnermittlungsart. **Die genannten Zeilen sind Ausgabe 2025, nicht verifizierte Formularzeilen 2026.** |
| S07 | [BFH, Beschluss 29.10.2020, VIII B 54/20](https://www.bundesfinanzhof.de/de/entscheidung/entscheidungen-online/detail/STRE202150002/), Leitsatz und Gründe Rz. 6; direkt gelesen | Vereinnahmte und verausgabte Umsatzsteuer gehört zur EÜR; sie ist dabei kein auszuscheidender durchlaufender Posten. Zahlungen an Lieferanten und tatsächliche Zahlungen an das Finanzamt sind zu unterscheiden. |
| S08 | [BFH, Urteil 12.07.2023, XI R 5/21](https://www.bundesfinanzhof.de/de/entscheidung/entscheidungen-online/detail/STRE202310237/), Leitsatz 2, Gründe II.3 Rz. 19–25; direkt gelesen | Bei einem selbst Ist-besteuernden Lieferanten stellt sich eine besondere unionsrechtliche Frage zum vorgezogenen Abzug beim Empfänger. Das Urteil lässt deren nationale Umsetzung im dortigen Empfängerverfahren offen. Es ist kein pauschaler Beleg für die Rechtmäßigkeit jedes behaupteten Alt-Abzugs. |

Der aktuelle amtliche §-15-Text allein beweist weder eine konkrete alte Steueranmeldung
noch deren Richtigkeit. Der enge Vertragsfall setzt die belegte rechtmäßige frühere
Ausübung voraus; strittige, später korrigierte oder nur behauptete Ansprüche müssen
gesondert geklärt werden. Die eigene Istbesteuerung des Rechnungsempfängers darf
nicht als Beweis für die Besteuerungsart des Lieferanten benutzt werden. S05/S08.

**Abrufgrenzen:** Die direkte Verbindung aus der Shell scheiterte an der vorhandenen
Proxyfreigabe (403); die erreichbaren Quellen wurden anschließend über das Webtool
gelesen. ELSTER 2026 und die BMF-Veröffentlichung zur Anlage EÜR 2026 waren dort
nicht vollständig erreichbar, die BMF-HTML-/PDF-Abrufe lieferten 503. Dasselbe gilt
für den aktuellen UStAE und die geöffneten EStH/UStH-Seiten. § 9b EStG lieferte
Timeout und wird hier nicht als neu geprüfter Beleg verwendet. Aus diesen Fehlern
folgt weder das Nichtbestehen einer Veröffentlichung noch eine Bestätigung ihrer Inhalte.

## Notwendige Trennung im Übernahmevertrag

Die folgenden Anforderungen sind eigene Umsetzungsableitungen aus S01–S08 und dem
gelesenen Repositoryvertrag. Sie ersetzen keine Prüfung eines echten Originalbelegs.

1. **Rechnung und Anspruch:** unverändertes Original, Rechnungsaussteller/-empfänger,
   Leistung, Rechnungseingang, Währung sowie Brutto/Netto/USt je Steuergruppe.
2. **Frühere steuerliche Behandlung:** tatsächlicher Vorsteuerabzug mit Datum,
   Betrag, Voranmeldungs-/Erklärungszeitraum und Herkunftsnachweis. Bei Forderungen
   belegte durchgehende Istbesteuerung und Behandlung früherer vereinnahmter Anteile.
3. **Geldbewegungen:** frühere tatsächliche Zahlungen mit ihren belegten Anteilen;
   später jeweils ein eigener datierter Zahlungsnachweis. Ein einziges Feld
   „bereits erfasst“ reicht nicht, weil es entweder Steuerrecht oder Geldfluss meinen könnte.

Aus einer alten Vorsteueranmeldung folgt **keine** Zahlung des Finanzamts. Ein
Erstattungsüberhang kann mit anderen Steuerbeträgen verrechnet oder später ausgezahlt
worden sein. Nur der tatsächliche belegte Vorgang begründet die entsprechende
Finanzamts-Geldbewegung. Eine pauschale zusätzliche Erstattung in Höhe der
Rechnungsvorsteuer wäre erfunden. Für diese getrennten EÜR-Kategorien: S06/S07.

`bookkeeping_start` bezeichnet hier den Beginn der Erfassung in dieser Software,
nicht den Beginn des Unternehmens oder einen Wechsel von Bilanz zu EÜR. Für eine
echte Änderung der Gewinnermittlungsart braucht es eine andere Übergangsrechnung;
die EÜR-Anleitung 2025 behandelt dies gesondert bei Zeile 89. Ein bloßer
Programmwechsel erzeugt daher in diesem Vertrag keinen Übergangsgewinn. S01/S06.

Bei einem Start innerhalb eines Kalenderjahres fehlen ohne gesonderte Übernahme
auch die bereits bezahlten laufenden Vorgänge vor dem Start. Ein korrektes neues
Teiljahresjournal und ein vollständiger Forderungsrest beweisen deshalb keine
vollständige Jahres-EÜR. Anfangsbankbestand und offene Posten ersetzen diese
Vorperiodenwerte nicht.

## Unabhängig hergeleitete Geldfälle

Alle Beträge sind EUR. Vorzeichen in der EÜR: Einnahme positiv, Ausgabe negativ.
Die Steuer-Spalten beschreiben **zusätzliche** Wirkungen nach dem Softwarebeginn;
ein früherer Abzug wird nur als Herkunftstatsache geführt. Die Fälle wurden mit
[einem unabhängigen Decimal-Rechner](evidence/altposten-quellen-2026-11-04/calculate_expected.py)
ohne Import eines Produktmoduls gerechnet; Ergebnisse stehen in
[expected-cases.json](evidence/altposten-quellen-2026-11-04/expected-cases.json).
Das ist eine Prüfung der Referenzarithmetik, kein ausgeführter Produkttest.

| Fall | Nachgewiesene Tatsachen | Erwartete neue Wirkung |
| --- | --- | --- |
| F01 | Forderung 1.000 + 190 = 1.190; bisher unbezahlt; Eingang 595 im November, weitere 595 im folgenden Februar | Je Zahlung EÜR +500 Erlös/+95 USt; Ist-USt jeweils 95 im tatsächlichen Monat. Nach erster Zahlung Rest 500/95/595, am Ende 0. |
| F02 | Forderung 100 + 7 = 107; vor Beginn 53,50 mit 50/3,50 vereinnahmt; Rest 53,50 später | Nur +50/+3,50 und neue Ist-USt 3,50. Keine erneute Einnahme der alten 53,50. |
| F03 | Lieferantenrechnung 100 + 19 = 119; Vorsteuer 19 rechtmäßig vor Beginn vollständig abgezogen; vorher keine Zahlung; später 119 bezahlt | Cash −119; EÜR −100 Aufwand/−19 bezahlte Vorsteuer; neue VAT-input **0**. Nur −100 EÜR wäre um 19 falsch. |
| F04 | Lieferantenrechnung 1.000 + 190; Alt-Abzug 190; vor Beginn 238 mit 200/38 bezahlt; später 357 und 595 | Neue EÜR −300/−57 und −500/−95; zusammen −952. Neue VAT-input beide Male 0. Alte 238 bleiben alt. |
| F05 | Wie F03; tatsächliche isolierte FA-Erstattung 19 bereits im Vorjahr; Lieferantenzahlung 119 jetzt | Frühere EÜR +19; neue EÜR −119; über beide Zeiträume −100. Im neuen Zeitraum allein −119, **keine** neue Erstattung. |
| F06 | Wie F03; tatsächliche isolierte FA-Erstattung 19 erst jetzt, separat belegt | Jetzt EÜR +19 FA-Erstattung und −119 Lieferantenzahlung = −100; zwei echte Cashvorgänge, neue VAT-input weiterhin 0. |
| F07 | Original 100/19/119; alte Zahlung 39,67 mit belegten 33,34/6,33; neue Zahlungen 39,67 und 39,66 | Bei der unten ausdrücklich gewählten kumulativen Rundung neue Anteile 33,33/6,34 sowie 33,33/6,33. Neuer Restverbrauch netto 66,66, Steuer 12,67, brutto 79,33. |
| F08 | Softwarebeginn 01.11.; gleiches Jahr: 59,50 Ausgabe vor Beginn und 59,50 danach, jeweils 50/9,50 | Neues Teiljahr −59,50; gesamte betroffene Jahresausgabe −119 nur mit belegten Altjahreswerten. Bankanfangsbestand fügt keine Ausgabe hinzu. |
| F09 | Nicht wiederkehrende gewöhnliche Forderung 100/19/119, tatsächlicher Eingang genau am 01.11., Beginn 01.11. | Vollständig neuer Cash-/EÜR-/Ist-USt-Fall. Tatsächlicher Eingang 31.10. wäre vollständig historisch. Import am 04.11. ändert den Geldtag nicht. |
| F10 | Import offener Forderung 119 und Bankanfangsbestand 500, noch keine neue Zahlung | Neuer Umsatz, EÜR, USt und Cash jeweils 0; Forderungsrest 119 und gesonderter Anfangsbankbestand 500 bleiben Bestandsinformationen. |

F05/F06 setzen ausdrücklich einen isolierten tatsächlichen Erstattungsnachweis voraus;
sie modellieren keine automatisch aus einer Einzelrechnung berechnete Steuererstattung.

### Centaufteilung: belegte Altanteile zuerst

Die Gesetze und die hier gelesene EÜR-Anleitung schreiben für diesen Import keine
universelle maschinelle Teilzahlungs-Rundungsformel vor. Der vorhandene C1/C2/R1/R2-
Vertrag verwendet kumulative Halbauf-Rundung des Steueranteils auf Cent. Für F07
wird **dieser ausdrücklich gewählte technische Vertrag** unabhängig gerechnet:
Steuer bis 39,67 = 6,33; bis 79,34 = 12,67; bis 119 = 19. Die Differenzen sind
6,33 / 6,34 / 6,33. Einzelrundung jeder Rate ergäbe nur 18,99 und wäre für diesen
Vertrag falsch. Es handelt sich nicht um den Nachweis einer gesetzlichen Rundungspflicht.

Alte belegte Werte sind unveränderliche Eingaben. Wäre die frühere 39,67-Zahlung
tatsächlich mit 33,33/6,34 erfasst worden, darf der Import daraus nicht still 33,34/6,33
machen. Dann sind zunächst echte Restwerte 66,67/12,66/79,33 zu erhalten. Ob und wie
ein anderer historischer Aufteilungsvertrag im neuen Modul unterstützt wird, braucht
eine ausdrückliche Entscheidung. Im engen ersten Vertrag ist das ein blockierter
Klärungsfall. Mehrere Steuergruppen müssen jeweils eigene begrenzte Original- und
Verbrauchsanteile behalten; eine pauschale 19/119-Rechnung über einen gemischten Rest genügt nicht.

## Gezielte Gegenfälle für die spätere Produktprüfung

- Eine bereits bezahlte Altkomponente erneut als Zahlung oder mittels anderem
  `request_id` als zweiten importierten Ursprung ausgeben: keine zusätzliche Wirkung.
  Originalidentität und Wiederholungsidentität sind verschiedene Schutzmaßnahmen.
- Alt-Vorsteuer 19 als neuen `input_vat`-Posten auf Zahlungsdatum verschieben:
  verhindern; EÜR-bezahlte-Vorsteuer und VAT-input dürfen nicht gekoppelt werden.
- Vorsteuerabzug lediglich behauptet, unvollständig, widersprüchlich oder später
  berichtigt: kein Durchfallen in den normalen Abzugspfad. Der enge geprüfte Fall
  passt nicht; Klärung sichtbar lassen.
- Restgross, Restnetto oder Reststeuer überschreiten; Original vollständig bezahlt;
  historischer Komponentenverbrauch passt nicht zum Original: kein neuer Verbrauch.
- Neue Zahlung trifft gesperrten Monat: nicht auf einen offenen Monat verschieben.
- Erfolgreiche Annahme mit verlorenem ACK, danach Wiederholung: genau dasselbe
  Ergebnis/Nonce, keine zweite Geldbewegung. Korrektur eines Erfassungsfehlers ist
  keine zweite tatsächliche Zahlung und benötigt nachvollziehbaren Gegenbezug.
- Wechsel Bilanz→EÜR, Soll→Ist oder Kleinunternehmer→Regelbesteuerung: nicht als
  gewöhnliche Alt-Forderung/-Verbindlichkeit akzeptieren; sonst drohen Doppel- oder
  Nichterfassung. Die Existenz einer Alt-Rechnung allein reicht nicht zur Einordnung.

Die ersten drei Zahlungs-/Steuer-Grenzen sind aus den Quellen abgeleitet; Nonce,
Originalhash, Sperrperioden und Gegenbezüge sind technische Anforderungen des
vorhandenen Repositoryvertrags, keine gesetzlichen API-Vorgaben.

## Gegenprüfung des vorhandenen EÜR-/Geldvertrags

Gelesen wurden `CRM_ERP_EUER_E1A_API.md`, `CRM_ERP_EUER_WORKFLOW_API.md`,
`CRM_ERP_EUER_E1B4A1_API.md`, `CRM_ERP_ANFANGSSALDEN_API.md` und die bestehenden
Quellenhinweise. Die exakten Dateihashes des gelesenen Stands sind im Evidenzmanifest.

- `EuerAccounting._profile_dates` sperrt neue Buchungstage vor dem bestätigten
  Beginn. Der historische Nachweis darf diese Grenze nicht durch ein erfundenes
  neues Anspruchsdatum umgehen.
- `EuerAccounting._prepare_cash` verlangt bei Lieferantenzahlungen bislang einen
  aktiven `input_vat`-Nachweis im eigenen Journal. `_prepare_input_vat` erzeugt
  zugleich den neuen VAT-input-Posten. Für den belegten Alt-Abzug braucht es deshalb
  eine ausdrücklich andere Herkunftsbindung; normales Neu-Anmelden wäre falsch.
- `_prepare_cash` trennt bereits EÜR-Aufwand und `paid_input_vat` von der VAT-input-
  Buchung. Diese Trennung soll der neue Altfall beibehalten.
- `DocumentComponents._tax/_line` bildet die oben beschriebene kumulative
  Centaufteilung ab. Das ist Bestandsverhalten, keine unabhängige Rechtsquelle.
- `EuerAccounting._report` meldet bei unterjährigem Profilbeginn bereits
  `partial_period_profile_coverage`. Ein neues Altpostenmodul darf dieses Problem
  nicht allein durch vorhandene offene Rechnungen als erledigt behandeln.
- Der Anfangssaldenvertrag setzt die Grenze unmittelbar vor den Bewegungen des
  Starttags (00:00 Europe/Berlin). Der Anfangssaldo erzeugt keine rückdatierte
  künstliche Bewegung. Alte offene Posten müssen das ebenfalls einhalten.

Diese Gegenprüfung beschreibt die gelesenen Bestandsfunktionen, nicht einen Test
der parallel entstehenden Erweiterung. Es wurden keine Runtime-/API-Dateien geändert.

## Bewusst offen und außerhalb dieses Nachweises

Nicht behandelt sind echte Methoden-/Rechtsform-/USt-Regimewechsel, Anlagen und AfA,
uneinbringliche oder streitige Forderungen, Rabatte/Gutschriften/Skonti, Verjährung,
Aufrechnung/Abtretung, Anzahlungen, Reverse Charge/Ausland, private oder nicht
abziehbare Anteile, §-15a-Berichtigung sowie Zehntages- und andere Sonderfälle.
Ein später korrigierter Alt-Abzug oder ein nachträglich entfallener Anspruch braucht
einen eigenen Korrekturvertrag. Ungeklärte Tatsachen erhalten keinen geratenen Zahlenwert.

Die aktuelle amtliche Formular-/Datensatzzuordnung 2026 und die besondere
Abzugsfrage bei einem selbst Ist-besteuernden Lieferanten sind mit dieser Recherche
nicht abschließend freigegeben. Das vorhandene Recht sowie die dokumentierten
Quellen tragen den engeren Fortführungsfall mit nachweislich rechtmäßigem Alt-Abzug.
Eine fachliche Prüfung konkreter Unternehmensbelege bleibt davon getrennt.
