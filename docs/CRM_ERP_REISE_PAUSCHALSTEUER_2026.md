# Reiseerstattung: eigene 25%-Pauschalsteuer 2026

Stand: 03.11.2026. `payroll_travel_tax_2026.py` ist ein reiner Rechenbaustein. Seine zehn Autorentests und elf zusätzliche unabhängige Gegenproben bestehen. Die tatsächliche v5-Quellen-/Abschlussintegration läuft noch. Dieser Stand bestätigt weder eine Steuerübermittlung noch eine vollständig integrierte Lohnabrechnung. [Unabhängiger Prüfbericht und genaue Quellen](CRM_ERP_REISE_PAUSCHALSTEUER_GEGENPRUEFUNG_2026.md).

## Rechenumfang

§40 Abs.2 Satz1 Nr.4 EStG erlaubt für den einschlägigen zusätzlichen Verpflegungsersatz 25% Lohnsteuer. Die Obergrenze muss aus den tatsächlichen, ungekürzten einschlägigen Verpflegungspauschalen der belegten Reise abgeleitet werden. Der Helfer akzeptiert keine selbstgewählte Erhöhung dieser Grenze und kappt Überschreitungen nicht stillschweigend. Tatsächliche Reisequellen und deren einmalige Zuordnung prüft der private v5-Resolver.

Pauschale Lohnsteuer, darauf entfallender Solidaritätszuschlag von5,5% und Kirchensteuer werden getrennt in ganzen Cent berechnet. Je Steuer wird ein verbleibender Centbruchteil abgeschnitten. Kinderfreibeträge, die Freigrenze des gewöhnlichen Solidaritätszuschlags und die gewöhnliche Lohnsteuerrechnung werden nicht auf diese Nebenrechnung übertragen. Bei14EUR einschlägiger Erstattung und vereinfachtem Kirchensteuerverfahren inBW ergeben sich350Cent Lohnsteuer,19Cent Soli und15Cent Kirchensteuer.

Die gesetzliche Steuerschuld des Arbeitgebers bleibt getrennt von seiner wirtschaftlichen Kostenübernahme. Eine Abwälzung auf den Arbeitnehmer verlangt eine konkret gebundene Vereinbarung und ergibt einen eigenen Nettoabzug; sie beseitigt nicht die gesetzliche Arbeitgebersteuerschuld.

## Kirchensteuerentscheidung

Die optionale 25-%-Besteuerung üblicher gestellter Mahlzeiten nach §40 Abs.2
Satz1 Nr.1a EStG ist ein anderer Tatbestand und noch kein implementierter
Policyfall. Nach [BMF 25.11.2020 Rz.94–99](https://www.ihk.de/blueprint/servlet/resource/blob/5260010/6167648501baf85de6053f701b93e9b5/bmf-schreiben-25-11-2020-data.pdf)
kann sie beispielsweise bei fehlendem Pauschalenanspruch oder nach der
Dreimonatsfrist relevant werden. Der aktuelle Lohnweg erfasst den einschlägigen
Sachbezug individuell. Die Nr.4-Policy darf nicht als Wahl oder Nachweis für
Nr.1a verwendet werden; hierfür fehlen ein eigener belegter Entscheidungsfall
und die entsprechende fachliche Abnahme.

Die Entscheidung gilt einheitlich für den tatsächlichen Anmeldezeitraum und den Pauschalierungstatbestand. Im vereinfachten Verfahren fallen Nebensteuern auch für Nichtmitglieder an. Im Nachweisverfahren sind Mitgliedschaft oder Nichtmitgliedschaft durch ELStAM, Ersatzbescheinigung oder die zulässige Erklärung nach amtlichem Muster konkret nachzuweisen. Bei dokumentiert nicht ermittelbarer Zugehörigkeit wird ausdrücklich der allgemeine Satz verwendet; ein unbelegter unbekannter Status ergibt keine Steuerfreiheit. Die beiden zusätzlichen zulässigen Wege wurden in der unabhängigen Quellenprüfung gefunden und vor dem Regelabschluss ergänzt. Der Fallresolver muss widersprüchliche Entscheidungen im selben Geltungsbereich verhindern. Ein bloßer `true`-Schalter im Client ist dafür kein Nachweis.

Maßgeblich ist die belegte lohnsteuerliche Betriebsstätte. Der Helfer verwendet folgende vereinfachte Sätze, jeweils Prozent der pauschalen Lohnsteuer:

| Land | Satz | Land | Satz |
|---|---:|---|---:|
| BW |4,5| BY |7|
| BE |5| BB |5|
| HB |7| HH |4|
| HE |7| MV |5|
| NI |6| NW |7|
| RP |7| SL |7|
| SN |5| ST |5|
| SH |6| TH |5|

Die niedersächsische Zuständigkeit der Evangelischen Kirche von Westfalen wird ausdrücklich mit7% behandelt. Im Nachweisverfahren gelten grundsätzlich8% inBW/BY und9% in den übrigen Ländern; die ausdrücklich belegte Mainzer Zuständigkeit inBad Wimpfen ist ein eigener9%-Fall. Solche Zuständigkeiten dürfen nicht aus einem Wohnort geraten werden.

## Tatsächliche Steuererfassung und Sozialversicherung

Die Steuerrechnung und die SV-Freiheit sind verschiedene Ergebnisse. §1 SvEV verlangt die tatsächliche entsprechende steuerliche Behandlung. Als späteste Frist wird das Ende Februar des Folgejahrs und gegebenenfalls die frühere Ausstellung der Lohnsteuerbescheinigung berücksichtigt. Eine verspätete Behandlung kann daher dieselbe Pauschalsteuer, aber einen zusätzlichen SV-Bruttobetrag ergeben. Ein fehlender tatsächlicher Erfassungskontext liefert einen konkreten Blocker; er wird nicht automatisch durch ein gewünschtes Datum ersetzt.

Für den neuen Softwareabschluss ist vorgesehen: Die Vorschau zeigt ausdrücklich eine noch nicht erfolgte Steuererfassung zum serverseitig vorgesehenen Abschlusstag. Erst die erfolgreiche Bestätigung schreibt den Lohnlauf und seinen tatsächlichen Steuererfassungsnachweis atomar. Ein Datumswechsel oder geänderte Quellen erzwingt eine neue Vorschau. Historische Prüfung bindet den Nachweis an die ursprüngliche Laufrevision und deren tatsächlichen Zeitpunkt. Ein extern bereits erfasster Vorgang braucht seinen belegten Importnachweis. Keine dieser Aktionen erzeugt eine Bankzahlung oder meldet eine Übermittlung anELSTER.

## Gelesene Quellen und Grenzen der Quellenprüfung

Abruf/Prüfung am03.11.2026. Volltext und Suchindexauszug werden hier ausdrücklich unterschieden. Die16-Länder-Tabelle ist als vollständige aktuelle Sekundärquelle gelesen und für mehrere Länder mit Primärquellen gegengeprüft; dies ist keine Behauptung einer vollständigen Einzelprüfung aller16 Landeserlasse.

| Aussage | Quelle und tatsächlich verfügbarer Zugriff |
|---|---|
|25%-Tatbestand und Arbeitgebersteuerschuld|[§40 EStG](https://www.gesetze-im-internet.de/estg/__40.html), amtlicher Suchindexauszug; direkter Volltextabruf lief wiederholt in Zeitüberschreitung. [BMF LStH2026 §40](https://ao.bundesfinanzministerium.de/lsth/2026/A-Einkommensteuergesetz/VI-Steuererhebung-36-47/2-Steuerabzug-vom-Arbeitslohn-Lohnsteuer-38-42g/Paragraf-40/inhalt.html), indexierte Hinweise zu ungekürzten Pauschbeträgen; direkter Abruf503.|
|SV-Behandlung|[§1 SvEV](https://www.gesetze-im-internet.de/svev/__1.html), Volltext gelesen, insbesondere Abs.1 Satz1 Nr.3 und Satz2. [DRV-Lexikon Pauschalbesteuerung](https://www.deutsche-rentenversicherung.de/DRV/DE/Experten/Arbeitgeber-und-Steuerberater/summa-summarum/Lexikon/P/pauschalbesteuerung_nach_%C2%A740_abs.1_satz1_nr.1_estg), relevante Fristpassage im Suchindex; Seitenabruf vorhanden, Fristpassage dort noch nicht separat extrahiert.|
|Soli-Grundlage,5,5% und Centbruchteil|[§3 SolZG](https://www.gesetze-im-internet.de/solzg_1995/__3.html) und [§4 SolZG](https://www.gesetze-im-internet.de/solzg_1995/__4.html), Volltexte gelesen.|
|Centabschneiden bei Lohnsteuer|[§39b EStG](https://www.gesetze-im-internet.de/estg/__39b.html), Volltext gelesen. Die Übertragung auf pauschale Lohnsteuer ist zusätzlich mit der [dokumentierten SAP-Korrektur bei Abresa, August2024](https://abresa.de/wp-content/uploads/2025/02/Abresa_HCM-Kundeninfo-August-2024.pdf) im indexierten Abschnitt gegengeprüft; nicht als ausdrücklicher Wortlaut von§40 ausgegeben.|
|Verfahrenswahl und Mitgliedschaft|[BMF LStH2026 Anhang21b](https://amtliche-handbuecher.bundesfinanzministerium.de/lsth/2026/B-Anhaenge/Anhang-21b/inhalt.html), Suchindexauszug, Volltext503; [Finanzamt Brandenburg](https://finanzamt.brandenburg.de/fa/de/steuern/steuerinformationen/kirchensteuer/), relevante Passage im Volltext gelesen. Andere veraltete Minijobangaben derselben Seite werden nicht übernommen.|
|Vollständige vereinfachte Ländertabelle|[Haufe, Kirchensteuerpauschsätze](https://www.haufe.de/id/beitrag/kirchensteuer-im-lohnsteuerabzugsverfahren-22-kirchensteuerpauschsaetze-HI7404419.html), vollständige Tabelle gelesen.|
|BW4,5%/8%|[Evangelische Landeskirche Württemberg, §2 Haushalt2025/2026](https://www.kirchenrecht-ekwue.de/document/57727), Primärvolltext; [LandesrechtBW, Erlass22.05.2026](https://www.landesrecht-bw.de/bsbw/document/VVBW-VVBW000046194), indexierter Auszug, direkte Seite nurJavaScript.|
|HH4%, MV5%, SH6%|[Nordkirche, Kirchensteuerordnung](https://www.kirchenrecht-nordkirche.de/document/28498), Volltext einschließlich Änderungsstand20.03.2026 gelesen.|
|NI6% / Westfalen7%|[NWB, Erlass01.04.2026](https://datenbank.nwb.de/Dokument/1094280/), aktueller indexierter Erlassauszug. Das [2026 veröffentlichte niedersächsische PDF Nr.122](https://www.verkuendung-niedersachsen.de/api/ndsmbl/2026/122/0/mbl-2026-122.pdf) wurde vollständig gelesen, betrifft aber ausdrücklich2025 und ist deshalb kein alleiniger2026-Nachweis.|

Die fachliche Belegprüfung der realen Betriebsstätte, des Anmeldezeitraums, der Zugehörigkeit, der Fristen und der Originalunterlagen bleibt Aufgabe des tatsächlichen privaten Arbeitsablaufs. Synthetische Tests erzeugen hierfür keine Unternehmensdaten.
