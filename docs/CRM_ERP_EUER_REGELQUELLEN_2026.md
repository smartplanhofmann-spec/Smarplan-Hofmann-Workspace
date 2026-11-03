# EÜR und Umsatzsteuer: geprüfte Regelquellen für die Umsetzung

Recherche: **03.11.2026**. Gegenstand ist ein deutsches Einzelunternehmen mit EÜR,
Regelbesteuerung und ausdrücklich bestätigter Ist-Versteuerung. Die bestätigte
Standardeinstellung von 19 % ersetzt weder die Belegprüfung noch einen gesetzlichen
Steuertatbestand. Buchführungsbeginn, steuerlicher Gültigkeitsbeginn und historische
Übernahmewerte bleiben instanzbezogene Angaben; diese Recherche setzt sie nicht.

Dieses Dokument beschreibt **fachliche Anforderungen und Referenzfälle**. Es ist
kein Nachweis ihrer Implementierung, keine Abnahme eines Unternehmensjahres und
kein amtlicher Erklärungsdatensatz. Aussagen über tatsächlich unterstützte Fälle
und ausgeführte Tests müssen die jeweilige Modulbeschreibung und der Prüfbericht
gesondert belegen.

## Quellenstand und Abrufgrenzen

Die Gesetze wurden über die amtlichen Einzelnormen bzw. deren amtliche
Suchindexauszüge geprüft. Einige Direktabrufe von Gesetze-im-Internet und dem BMF
scheiterten mit Timeout/503; diese Grenzen stehen jeweils dabei. Bei den
Handbüchern ist das bezeichnete Ausgabejahr maßgeblich, nicht das Abrufjahr.
Kurze wörtliche Ausschnitte dienen der Identifizierung; die Umsetzungsfolgen sind
eigene fachliche Ableitungen.

| Kennung | Primärquelle, Stand/Abruf | Kurzer Beleg und Bedeutung |
| --- | --- | --- |
| S01 | [§ 4 EStG](https://www.gesetze-im-internet.de/estg/__4.html), aktueller amtlicher Suchindex; Direktabruf Timeout | Absatz 3: „Überschuss der Betriebseinnahmen über die Betriebsausgaben“. Durchlaufende Posten scheiden aus; GWG-, Sammelposten- und AfA-Vorschriften bleiben anzuwenden. Nicht abnutzbare Anlagen und bestimmte Wirtschaftsgüter haben besondere Abzugszeitpunkte. |
| S02 | [§ 11 EStG](https://www.gesetze-im-internet.de/estg/__11.html), aktueller amtlicher Suchindex; Direktabruf Timeout | Absatz 2: „Ausgaben sind für das Kalenderjahr abzusetzen, in dem sie geleistet worden sind.“ Die Norm regelt Zufluss, Abfluss, regelmäßig wiederkehrende Vorgänge und Sonderregeln für langfristige vorausbezahlte Nutzungsüberlassungen. |
| S03 | [BFH, X R 2/21, Urteil vom 16.02.2022, Pressemitteilung vom 27.05.2022](https://www.bundesfinanzhof.de/de/presse/pressemeldungen/detail/faelligkeitserfordernis-bei-regelmaessig-wiederkehrenden-einnahmen-und-ausgaben/), direkt gelesen | „nicht nur gezahlt, sondern auch fällig geworden“. Der kurze Zeitraum um den Jahreswechsel beträgt zehn Tage; verspätet bezahlte, längst fällige Umsatzsteuer erfüllt die Ausnahme nicht. |
| S04 | [§ 13 UStG](https://www.gesetze-im-internet.de/ustg_1980/__13.html), aktueller amtlicher Suchindex; Direktabruf Timeout | Absatz 1 Nummer 1 Buchstabe b: „in dem die Entgelte vereinnahmt worden sind“. Ist-Umsatzsteuer entsteht mit Ablauf dieses Voranmeldungszeitraums. |
| S05 | [§ 20 UStG](https://www.gesetze-im-internet.de/ustg_1980/__20.html), aktueller Text direkt gelesen | „Das Finanzamt kann auf Antrag gestatten“. EÜR allein begründet keine Ist-Versteuerung; bei einem Methodenwechsel dürfen Umsätze weder doppelt erfasst werden noch unversteuert bleiben. |
| S06 | [§ 15 UStG](https://www.gesetze-im-internet.de/ustg_1980/__15.html), aktueller Text direkt gelesen | „wenn die Rechnung vorliegt und die Zahlung geleistet worden ist“ betrifft Anzahlungen. Bei normalen ausgeführten Leistungen setzt der Abzug unter anderem die Rechnung voraus. Betriebliche Verwendung, Ausschlüsse und Aufteilung sind separat zu prüfen. |
| S07 | [§ 9b EStG](https://www.gesetze-im-internet.de/estg/__9b.html), aktueller Text direkt gelesen | „nicht zu den Anschaffungs- oder Herstellungskosten“. Das gilt für Umsatzsteuer, soweit sie als Vorsteuer abgezogen werden kann; Vorsteuerberichtigungen haben eigene ertragsteuerliche Folgen. |
| S08 | [ELSTER-Anleitung EÜR 2025](https://www.elster.de/eportal/helpGlobal?themaGlobal=help_euer_ufa_77_2025), Ausgabe 2025 direkt gelesen | „gehören im Zeitpunkt ihrer Bezahlung zu den Betriebsausgaben“: abziehbare Vorsteuer aus Eingangsrechnungen. Vereinnahmte Umsatzsteuer und Erstattungen des Finanzamts sind Einnahmen; Umsatzsteuerzahlungen an das Finanzamt sind Ausgaben. Dies ist eine zusätzliche fachliche Erläuterung, **kein Nachweis der Formularzeilen 2026**. |
| S09 | [§ 12 EStG](https://www.gesetze-im-internet.de/estg/__12.html), aktueller Text direkt gelesen | „Aufwendungen für die Lebensführung“. Private Kosten, persönliche Steuern und weitere ausdrückliche Abzugsverbote dürfen nicht als gewöhnlicher Betriebsaufwand behandelt werden. |
| S10 | [BMF vom 06.07.2010, gemischte Aufwendungen, LStH 2025 Anhang 18a](https://erbsth.bundesfinanzministerium.de/lsth/2025/B-Anhaenge/Anhang-18a/inhalt.html), amtlicher Suchindex | „nach einem an objektiven Kriterien orientierten Maßstab“. Ein betrieblicher Anteil braucht eine nachvollziehbare Grundlage; eine frei gewählte Prozentzahl ersetzt diesen Nachweis nicht. |
| S11 | [EStH 2025, H 4.5 (2)](https://usth.bundesfinanzministerium.de/esth/2025/A-Einkommensteuergesetz/II-Einkommen-2-24b/3-Gewinn-4-7i/Paragraf-4/h-4-5-2.html), amtlicher Suchindex; Direktabruf 503 | „keine Betriebseinnahmen“ für Darlehensaufnahme; Tilgung ist keine Betriebsausgabe. Darlehenszinsen, Verluste und Fremdwährungsfolgen sind eigenständige Sachverhalte. |
| S12 | [§ 6 EStG](https://www.gesetze-im-internet.de/estg/__6.html), aktueller Text direkt gelesen | Absatz 2: „800 Euro nicht übersteigen“. GWG setzen unter anderem abnutzbares bewegliches Anlagevermögen und selbständige Nutzbarkeit voraus. Der Sammelposten nach Absatz 2a ist ein gesondertes Wahlrecht. |
| S13 | [§ 7 EStG](https://www.gesetze-im-internet.de/estg/__7.html), aktueller Text direkt gelesen | „betriebsgewöhnlichen Nutzungsdauer“. Lineare AfA ist zeitanteilig; im aktuellen Text bestehen daneben unter anderem befristete degressive Optionen für Anschaffungen nach dem 30.06.2025 und vor dem 01.01.2028. |
| S14 | [§ 17 UStG](https://www.gesetze-im-internet.de/ustg_1980/__17.html), aktueller amtlicher Suchindex; Direktabruf Timeout | „in dem die Änderung der Bemessungsgrundlage eingetreten ist“. Steuerliche Berichtigung und bloße Korrektur eines Erfassungsfehlers brauchen unterscheidbare Ursprünge und Zeitpunkte. |
| S15 | [§ 146 AO](https://www.gesetze-im-internet.de/ao_1977/__146.html), aktueller amtlicher Gesetzesindex; Direktabruf Timeout | „dass der ursprüngliche Inhalt nicht mehr feststellbar ist“ beschreibt die unzulässige Änderung. Ein Journal muss Ursprung und Änderung erkennbar halten. |
| S16 | [§ 153 AO](https://www.gesetze-im-internet.de/ao_1977/__153.html), aktueller Text direkt gelesen | „unverzüglich anzuzeigen und die erforderliche Richtigstellung vorzunehmen“. Eine interne Periodensperre beseitigt keine Pflicht zur Berichtigung bereits abgegebener Erklärungen. |
| S17 | [DATEV: Kontenrahmen und Steuerschlüssel 2026](https://www.datev.de/web/de/berufsgruppenuebergreifend/service-und-support/wichtige-informationen-zum-jahreswechsel/jahreswechsel-rechnungswesen/anpassungen-in-den-programmen/DATEV-Kontenrahmen), Herstellerseite direkt gelesen | „DATEV-Standardkontenrahmen 2026“. Die Seite verlinkt die Jahresfassung der Kontenrahmen, deren Änderungen und gesonderte Steuerschlüssel. Das ist eine Herstellerquelle, kein Gesetz. |

Der amtliche BMF-Suchindex führt die Veröffentlichung
[Anlage EÜR 2026](https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Einkommensteuer/2026-09-01-anlage-EUER-2026.html).
Der direkte HTML-Abruf und die verlinkten PDF-Abrufe mit den Versionsparametern
`v=2` und `v=4` lieferten 503. Die ELSTER-Hilfe für 2026 war über das Recherchetool
nicht zugänglich. **Die Formularstruktur, Kennzahlen und Zeilennummern 2026 sind
daher in dieser Recherche nicht direkt verifiziert.** Die erreichbare
ELSTER-Anleitung 2025 darf nicht stillschweigend zur Ausgabe 2026 umetikettiert
werden. Eine lesbare eigene Jahresauswertung kann fachliche Kategorien verwenden;
eine amtliche Überleitung benötigt zusätzlich den geprüften aktuellen Datensatz.

## Verbindliche fachliche Unterschiede für die Umsetzung

1. **Geldfluss, EÜR und Umsatzsteuer sind getrennte Sichten.** Ein CashEvent
   beweist zunächst einen Geldfluss. Erst die belegte Einordnung bestimmt, ob er
   Einnahme, abziehbare Ausgabe, nicht abziehbarer Aufwand, Privatbewegung,
   Darlehenshauptbetrag, Umbuchung oder durchlaufender Posten ist. Rechnungserlös
   und Projektkosten sind keine ersatzweise EÜR. Bezüge: S01, S02, S09, S11.
2. **EÜR enthält die Geldwirkung der Umsatzsteuer.** Ein gewöhnlicher Verkauf
   erfordert getrennte Einnahmenkomponenten für Nettobetrag und vereinnahmte USt.
   Bei einer gewöhnlichen voll betrieblichen Ausgabe werden Nettokosten und
   bezahlte abziehbare Vorsteuer getrennt ausgewiesen. Nicht abziehbare Vorsteuer
   ist nach ihrem Sachverhalt den Kosten zuzuordnen. Finanzamtszahlungen und
   -erstattungen sind eigenständige Quellen und keine bloße Differenz aus den
   Belegsteuern. Bezüge: S07, S08.
3. **Vorsteuer ist kein spiegelbildliches Ist-Umsatzsteuerverfahren.** Bei einer
   ausgeführten Leistung kann das Vorsteuerrecht vor der Bezahlung bestehen.
   Ein Datenmodell benötigt dafür die tatsächlich vorliegende Rechnung,
   Leistungsstand und den bestätigten Abzugszeitraum. Anzahlungen brauchen
   Rechnung und Zahlung. Ein ausschließlich zahlungsbasiertes Quelleninventar
   kann deshalb keine vollständige USt-Auswertung beweisen. Bezüge: S04–S06.
4. **Quellenbeträge gehen vor Standardprozentsätzen.** Vorhandene geprüfte
   Netto-/Steuer-/Bruttokomponenten, Steuergruppen, Restcents und
   Erstattungsursprünge bleiben die Basis. Der Steuersatz 19 % darf weder aus
   einem unbekannten Bruttobetrag eine angeblich geprüfte Steuer erzeugen noch
   7 %, steuerfreie, gemischte oder besondere Fälle überschreiben. Steuerfreie
   und nicht steuerbare Umsätze sind unterschiedliche Tatbestände.
5. **Die Zehn-Tage-Regel ist eine geprüfte Ausnahme.** Nötig sind wiederkehrender
   Charakter, wirtschaftliche Zugehörigkeit, tatsächlicher steuerlicher
   Zufluss/Abfluss und Fälligkeit. Zahlung allein im Januar genügt nicht.
   Kalenderjahreswechsel, die tatsächliche Fälligkeit und mögliche besondere
   Zahlungsregeln müssen ausdrücklich nachvollziehbar sein. Bankbuchungstag,
   Rechnungsdatum und steuerlicher Zahlungszeitpunkt dürfen nicht automatisch
   gleichgesetzt werden. Die EÜR-Jahresverschiebung verschiebt nicht automatisch
   die USt-Voranmeldung. Bezüge: S02–S04.
6. **Privatanteil und nicht abziehbarer Betriebsanteil sind verschieden.** Die
   Aufteilung braucht Cents, Methode, Begründung und Nachweis. Der ertragsteuerlich
   abziehbare Anteil bestimmt nicht automatisch dieselbe Vorsteuerquote.
   Sachentnahmen und unentgeltliche Wertabgaben können zusätzliche steuerliche
   Wirkungen haben und sind keine bloßen neutralen Geldentnahmen. Bezüge:
   S01, S06, S09, S10.
7. **Anlagen sind kein gewöhnlicher sofortiger Aufwand.** Ein Geräte- oder
   Wartungsdatensatz ist noch kein steuerliches Anlagenverzeichnis. Erforderlich
   sind Eigentums-/Betriebszuordnung, Anschaffungsdatum und -kosten, abziehbare
   Vorsteuer, dokumentierte Nutzungsdauer, gewählte Methode sowie bisherige
   Abschreibungen/Abgänge. Fehlen diese Angaben, bleibt die Ergebniswirkung
   offen. Bezüge: S01, S07, S12, S13.
8. **SKR04 braucht überprüfte, versionierte Zuordnungen.** Ein eigenes
   fachliches Journal kann ohne geratenes Sachkonto rechnen. Für die
   Beraterausgabe ist eine ausdrücklich bestätigte Zuordnung mit Jahresfassung,
   Konto, Steuerschlüssel, Gültigkeit, Referenz und Prüfer nachvollziehbar. Diese
   Bestätigung ersetzt weder die fachliche Regelprüfung noch eine technische
   DATEV-Importabnahme. Fehlende Zuordnungen erscheinen als offene Exportfälle.
   Eine Steuerautomatik des Zielkontos darf keine schon separat ausgewiesene
   Steuer ein zweites Mal erzeugen. Bezug: S17; dies ist eine
   Schnittstellenanforderung, keine gesetzliche DATEV-Pflicht.

## Konkrete Grenzen und sichere Fallbehandlung

| Fallgruppe | Voraussetzungen für eine belastbare Einordnung | Ohne diese Voraussetzungen |
| --- | --- | --- |
| Gewöhnliche inländische Kundenzahlung | Gültiges Ist-Profil, eindeutiger Zahlungs-/Rechnungsursprung, geprüfte Steuergruppe und exakte zugeordnete Cents | Offene Einordnung; keine pauschale Umrechnung mit 19 % |
| Gewöhnliche betriebliche Lieferantenausgabe | Original, geprüfte Rechnung, Zahlung, Kostenart, geschäftliche Veranlassung, gesonderte Prüfung des Vorsteuerrechts | CashEvent bleibt sichtbar; keine erfundene Ausgabe-/Vorsteuerwirkung |
| Finanzamtszahlung oder Erstattung | Tatsächliche Quelle, Steuerart, zugehöriger Zeitraum und gegebenenfalls belegte Verrechnung | Keine aus anderen Belegbeträgen erzeugte Scheinzahlung |
| Einlage/Entnahme von Geld, eigene Kontoumbuchung | Richtige Identität beider Seiten bzw. Eigentümerbezug; keine zusätzliche Leistung | Neutraler Geldfluss nur nach Prüfung; keine Umsatzkategorie |
| Darlehenshauptbetrag | Vertrag/Referenz und Trennung von Zinsen/Gebühren | Ungeklärt; keine Behandlung der ganzen Rate als Aufwand |
| Gemischte laufende Kosten | Nachvollziehbare betriebliche/private Centaufteilung; eigenständig geprüfte Vorsteuerbehandlung | Keine geschätzte Quote durch Software |
| GWG | Beweglich, abnutzbar, selbständig nutzbar; Voraussetzungen des gewählten Verfahrens und Bezugsjahr belegt | Als Anlagenklärungsfall führen |
| Lineare AfA | Ausdrücklich gewählte Methode, geprüfte Nutzungsdauer/Basis, zeitanteiliger Beginn, Restwert und Bestandsübernahme | Keine automatische Nutzungsdauer aus Gerätename/Artikelpreis |
| Jahreswechsel | Alle Voraussetzungen von S02/S03 belegt, nicht nur ein Datum im Zehn-Tage-Fenster | Keine automatische Verschiebung; unklaren Jahresanteil offenlegen |
| Berichtigung/Erstattung | Erfassungsfehler oder tatsächliche wirtschaftliche Änderung unterscheidbar, exakter Ursprung und verbleibende Cents | Keine zweite Einnahmen-/Ausgabenwirkung aus derselben Korrektur |

Die GWG-Grenze nach § 6 Absatz 2 beträgt aktuell 800 Euro nach der gesetzlichen
Bereinigung um enthaltene Vorsteuer. Oberhalb von 250 Euro sind zusätzliche
Verzeichnisanforderungen zu beachten. Der Sammelposten betrifft die gesetzlich
definierte Spanne über 250 bis 1.000 Euro und wird über fünf Jahre aufgelöst;
das Jahreswahlrecht darf nicht je Beleg beliebig mit dem GWG-Verfahren gemischt
werden. Eine Zahlung in mehreren Raten vervielfacht keine GWG-Grenze. S12.

Für bewegliche Anlagegüter mit Anschaffung nach dem 30.06.2025 und vor dem
01.01.2028 sieht § 7 Absatz 2 eine degressive Option bis zum Dreifachen des
linearen Satzes, höchstens 30 %, vor. Für bestimmte Elektrofahrzeuge enthält
Absatz 2a eine andere Staffel. Dies begründet **keine pauschale Wahl** dieser
Methoden. Abschreibungsbeginn, Nutzungsdauer, Jahresanteile und spätere
Methodenwechsel müssen zum tatsächlichen Fall passen. S13.

Insbesondere Ausland/Reverse Charge, § 15a-Berichtigungen, spezielle
Privatnutzungsregeln, Bewirtung/Geschenke, Überentnahmen/Schuldzinsenbegrenzung,
langfristige Vorauszahlungen, nicht abnutzbare Anlagen, Grundstücke, Sonder-AfA,
Investitionsabzugsbeträge und historische Übernahme sind eigene Regelgruppen.
Eine allgemeine manuelle Kategorienauswahl beweist deren korrekte Behandlung
nicht. Unimplementierte Regeln müssen Ergebnisvollständigkeit begrenzen und
einen belegten Klärungsweg behalten.

## Fachliche Referenzfälle für Implementierungstests

Die folgenden Fälle sind abgeleitete **Sollwerte**, keine bereits ausgeführten
Tests. Sie setzen gewöhnliche voll betriebliche und ordnungsgemäß belegte
Inlandsfälle ohne weitere Besonderheiten voraus.

| Fall | Erwartetes Ergebnis |
| --- | --- |
| Kunde bezahlt 119,00 Euro für 100,00 netto + 19,00 USt; sonst nichts | Geldzufluss 119,00; EÜR-Einnahmen 100,00 und 19,00 getrennt; Ist-USt 19,00 im Vereinnahmungszeitraum |
| Dazu bezahlte Ausgabe 50,00 netto + 9,50 voll abziehbare Vorsteuer; noch keine Zahlung an das Finanzamt | EÜR-Ausgaben 50,00 und 9,50; EÜR-Zwischenergebnis 59,50. Der Netto-Projektbeitrag 50,00 ist ein anderer Wert. |
| Danach tatsächliche Zahlung von 9,50 USt an das Finanzamt, gleicher EÜR-Zeitraum | Zusätzliche Ausgabe 9,50; EÜR-Ergebnis 50,00. Die Zahlung wird nicht aus dem Steuer-Saldo erfunden. |
| Leistung und ordnungsgemäße Eingangsrechnung am 15.12.2026; Zahlung 59,50 erst 20.01.2027 | Bei erfülltem § 15 Vorsteuerabzug 9,50 bereits im Dezember möglich; gewöhnlicher EÜR-Abfluss 59,50 erst 2027. Keine Zehn-Tage-Ausnahme. |
| Wiederkehrende Dezemberverpflichtung, fällig 10.01.2027, bezahlt 08.01.2027 | Bei belegter wirtschaftlicher Zugehörigkeit EÜR 2026. Eine im September 2026 fällige, erst 08.01.2027 bezahlte Nachzahlung bleibt dagegen 2027. |
| Zwei Teilzahlungen von jeweils 59,50 auf die erste Kundenrechnung | Gesamte zugeordnete Komponenten exakt 100,00/19,00. Die Abschlussrechnung darf dieselben bereits bezahlten Anteile nicht erneut ergebniswirksam machen. |
| Darlehenszufluss 1.000,00, spätere Tilgung 100,00 | Beide Hauptbeträge neutral. Gesonderte Zinsen benötigen eine eigene Prüfung. |
| Nachträgliche Korrektur einer falschen Kostenart | Alteintrag bleibt lesbar; Gegenbuchung hebt genau seine Wirkung auf; Ersetzung erzeugt genau die neue Wirkung. Keine neue tatsächliche Bankbewegung. |
| Unklassifizierte Zahlung oder ungeklärte Anlage in der Jahresmenge | Betrag und Ursache erscheinen offen. Ein vollständiger Jahresgewinn darf nicht aus einer Summe behauptet werden, die diesen Vorgang als null behandelt. |

## Journal, Perioden und Ausgabe

Aus S15 wird für den technischen Vertrag abgeleitet: feste Quellenstände,
unveränderliche Einträge, nachvollziehbare Gegenbuchungen, klare Beziehungen
zwischen Original und Ersatz sowie gespeicherte Erstellungs-/Prüfidentität.
Eine Periodensperre muss jeden ergebnisrelevanten Schreibweg erfassen; eine
begründete Wiederöffnung darf vorhandene Einträge nicht verändern. Beeinflusst
ein später erfasster Vorgang einen gesperrten Zeitraum, gehört er sichtbar in die
Klärung und darf nicht automatisch in einen offenen Monat verschoben werden.

Ein Jahres-/Beraterpaket sollte Quelldaten, vollständige Einordnungen,
unbekannte Wirkungen, Korrekturen, Periodenstatus, Regel-/Profilversion,
Übernahmegrenze, Beträge und Hashes zusammen einfrieren. Eine neue Buchung
verändert keinen früher erzeugten Stand. Vollständigkeit des erfassten Journals,
Vollständigkeit des Unternehmensjahres und Gültigkeit einer amtlichen Erklärung
sind getrennte Aussagen. Erfasste Rechnungen oder CashEvents allein beweisen
keine lückenlose Bank-, Kassen-, Anlagen- oder Jahresabstimmung. S01, S02, S15, S16.

Eine Ausgabe heißt fachlich nachvollziehbare Jahresauswertung bzw. Beraterpaket,
solange die aktuelle amtliche Überleitung bzw. ein konkreter DATEV-Import nicht
gesondert verifiziert ist. Dieses Dokument autorisiert keine Übermittlung an
Finanzamt, Bank oder Steuerberatung.
