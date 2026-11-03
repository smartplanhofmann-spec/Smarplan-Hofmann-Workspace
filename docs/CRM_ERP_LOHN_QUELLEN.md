# Deutsche Lohnabrechnung: Quellen, Umsetzung und verbleibende Nachweise

Recherche und Implementierungsstand: 3. November 2026. Firmenumfang laut Nutzer: Einzelunternehmen mit EÜR; Beschäftigungsfälle reguläre Mitarbeiter und gewerbliche Minijobs.

## Tatsächlich implementierter Umfang

`backend/business_personnel_workflow.py` ergänzt eine geschützte Personalakte, ausdrücklich belegte Entgeltvereinbarungen, belegte EUR-Reisekosten mit Einreichung/Prüfung/Korrektur sowie dokumentierte tatsächliche Erstattungen und Rückzahlungen. Monatliche Abschlüsse frieren freigegebene Zeitdaten, Zeitkorrekturen, genehmigte Abwesenheiten, Entgeltvereinbarungen und Reisen ein. PDF, CSV, vollständiger JSON-Quellennachweis und historische Versionen bleiben abrufbar. Der interne Projektkostensatz `hourly_cost_minor` wird nicht als Lohn verwendet.

Darauf baut inzwischen `business_payroll.py` mit versionierten Steuer-/SV-Profilen, Berechnungsvorschau, unveränderlichen Monatsläufen, begründeten Korrekturen und historischen PDF-/JSON-Belegen auf. Personenbezogene Originale werden separat von Projektdateien aufbewahrt; Projekt- oder Finanzberechtigungen verleihen keinen Personalzugriff.

Das lokale Rechenwerk unterstützt gewerbliche Minijobs mit Arbeitgeber-Pauschsteuer und reguläre laufende Vollmonatsentgelte 2026 in gesetzlicher Pflichtversicherung außerhalb des Übergangsbereichs. Reguläre Berechnungen enthalten Lohnsteuer nach dem begrenzten PAP-Teilumfang, Solidaritätszuschlag, Standard-Kirchenlohnsteuer, einzelne Arbeitnehmer-/Arbeitgeberbeiträge, kassenindividuelle Umlagen und Netto. Der Monatsfreibetrag und Hinzurechnungsbetrag müssen ausdrücklich belegt eingegeben werden, auch bei null. Fehlende Merkmale erzeugen ausschließlich einen ausdrücklich unvollständigen SV-Beleg, kein erfundenes Netto. Reisepauschalen, Unfallversicherung, amtliche Meldungen und Zahlungen sind nicht Teil dieses Rechenwerks.

Die Berechnungsumfänge heißen `commercial_minijob_flat_tax`, `regular_standard_monthly`, `social_contributions_only` und `unsupported`. Ein abgeschlossener Berechnungsbeleg behauptet keine amtliche Systemzulassung oder vollständige gesetzliche Entgeltunterlagen. Details und reproduzierbare Prüfungen: [Lohn-Rechenwerk 2026](CRM_ERP_LOHN_RECHENWERK_2026.md).

## Amtliche Quellen 2026

### BMF: Lohnsteuer-PAP

- Programmierservice und XML-Veröffentlichungen: <https://www.bmf-steuerrechner.de/interface/pseudocodes.xhtml>
- Offizieller XML-Link 2026, auf dieser Seite bestätigt: <https://www.bmf-steuerrechner.de/javax.faces.resource/daten/xmls/Lohnsteuer2026.xml.xhtml>
- Veröffentlichung PAP 2026 vom 12. November 2025: <https://www.bundesfinanzministerium.de/Content/DE/Downloads/Steuern/Steuerarten/Lohnsteuer/Programmablaufplan/2025-11-12-PAP-2026.html>
- Nutzung der externen Testschnittstelle: <https://www.bmf-steuerrechner.de/interface/einganginterface.xhtml>

Der PAP deckt Lohnsteuer, Solidaritätszuschlag und Kirchensteuer-Bemessungsgrundlage ab. Er ersetzt kein vollständiges Brutto-Netto-Rechenwerk mit Sozialversicherung. Die BMF-Schnittstelle dient Programmtests; produktive/kommerzielle Nutzung ohne Zustimmung ist untersagt. Die Anwendung muss einen geprüften, versionierten PAP lokal ausführen. Vergleichsaufrufe dürfen nur zulässige Tests mit synthetischen Daten sein.

Die amtliche 40-seitige Anlage 1 vom 12. November 2025 ist über [IHK München](https://www.ihk-muenchen.de/ihk/documents/Recht-Steuern/Steuerrecht/Einkommensteuer/2025-11-12-PAP-2026-anlage-1.pdf) lesbar. `payroll_pap_2026.py` setzt den ausdrücklich unterstützten Standardfall anhand dieses Ablaufs offline um. Alle **258 Beträge** der allgemeinen maschinellen Jahreslohnsteuer-Prüftabelle auf Seite 39 stimmen in den Tests überein. Zusätzlich sind monatliche Aufteilung, Soli-Milderungszone und Eingabegrenzen geprüft. Das Original-XML wurde weiterhin nicht heruntergeladen; die PAP-Prüfsumme im Ergebnis bezeichnet die versionierten Quellenmetadaten, keine behauptete Originaldatei-Prüfsumme. Es wurden keine BMF-Schnittstellenaufrufe oder Personaldatenübertragungen vorgenommen.

### GKV: Rechengrößen 2026

Vollständig gelesenes offizielles Faktenblatt, Stand 1. Januar 2026:
<https://www.gkv-spitzenverband.de/media/dokumente/presse/zahlen_und_grafiken/20260101_Faktenblatt_Rechengroessen_Beitragsrecht.pdf>

| Parameter | Wert 2026 |
|---|---:|
| KV allgemein / ermäßigt | 14,6 % / 14,0 % |
| Durchschnittlicher Zusatzbeitrag | 2,9 % |
| Pflegeversicherung / Kinderlosenzuschlag | 3,6 % / 0,6 % |
| PV-Abschlag je berücksichtigtem zweiten bis fünften Kind | 0,25 % |
| Rentenversicherung / Arbeitslosenversicherung | 18,6 % / 2,6 % |
| Insolvenzgeldumlage | 0,15 % |
| Monatliche BBG KV/PV | 5.812,50 EUR |
| Monatliche BBG RV/AV | 8.450,00 EUR |
| Minijobgrenze / Obergrenze Übergangsbereich | 603 EUR / 2.000 EUR |
| Übergangsbereich Faktor F | 0,6619 |
| Mindestbemessungsgrundlage Minijob-RV | 175 EUR |

Der durchschnittliche Zusatzbeitrag ist kein Ersatz für die tatsächliche Krankenkasse. Kassenindividuelle Zusatzbeiträge, U1/U2, Unfallversicherung und Versicherungsmerkmale sind zeitlich gültige Stammdaten. Sachsen, Kindermerkmale, Teilmonate und besondere Beitragsgruppen benötigen eigene Regeln.

### Minijob-Zentrale und DRV

- Gewerbliche Beiträge 2026: <https://magazin.minijob-zentrale.de/minijob-beitraege-2026/>
- RV-Pflicht und Mindestbeitrag: <https://www.minijob-zentrale.de/DE/die-minijobs/rentenversicherungspflicht>
- Übergangsbereich: <https://www.deutsche-rentenversicherung.de/DRV/DE/Experten/Arbeitgeber-und-Steuerberater/summa-summarum/Lexikon/U/uebergangsbereich.html>

Für gewerbliche Minijobs nennt die Minijob-Zentrale KV 13 %, RV 15 %, U1 0,80 %, U2 0,22 %, Insolvenzgeldumlage 0,15 % und bei entsprechender Wahl 2 % Pauschsteuer auf Arbeitgeberseite. Unfallversicherung kommt gesondert hinzu. Der reguläre Arbeitnehmer-RV-Anteil von 3,6 % ist bei Befreiung beziehungsweise Mindestbemessungsgrundlage nicht pauschal anwendbar. Mehrfachbeschäftigung und tatsächliche Steuerwahl müssen geprüft werden. Einzelbeiträge benötigen jeweils ihre vorgeschriebene Rundung.

Im Übergangsbereich sind Gesamt- und Arbeitnehmer-Bemessungsgrundlage getrennt zu bestimmen. Die vollständigen Formeln und Rundungsregeln sind vor einer produktiven Implementierung noch als geprüfte Referenzfälle zu hinterlegen.

### Reisekosten

- Inland: <https://www.gesetze-im-internet.de/estg/__9.html>
- Ausland 2026, BMF vom 5. Dezember 2025: <https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Lohnsteuer/2025-12-05-steuerliche-behandlung-reisekosten-2026.html>

Die aktuelle Implementierung übernimmt ausschließlich tatsächlich belegte EUR-Auslagen; sie legt keine steuerfreie Behandlung fest. Automatische Pauschalen sind offen. Vor deren Umsetzung müssen unter anderem Mahlzeitenkürzungen, Dreimonatsregel und vollständige gültige Auslandstabellen mit unabhängigen Referenzfällen abgedeckt werden.

## Direkte Meldungen und Zulassungen

- GKV-Grundsätze zur Systemuntersuchung, wirksam 1. Januar 2026, vollständig gelesen: <https://www.gkv-datenaustausch.de/media/dokumente/arbeitgeber/entgeltabrechnung/systemuntersuchung/GG_DEUEV_22_012026.pdf>
- Veröffentlichung und weitere Spezifikationen: <https://www.gkv-datenaustausch.de/arbeitgeber/entgeltabrechnung/entgeltabrechnung.jsp>
- ELSTER-Entwicklerzugang: <https://www.elster.de/elsterweb/infoseite/entwickler>
- Arbeitgeberinformationen: <https://www.elster.de/elsterweb/infoseite/arbeitgeber?locale=de_DE>

Die GKV-Grundsätze verlangen Systemprüfung, Pilotierung und Qualitätssicherung. Zum Basismodul gehören weit mehr als reguläre Vollmonatsgehälter und Minijobs, etwa Einmalentgelt/Märzklausel, Kurzarbeitergeld, Übergangsbereich, Rückrechnung, Beitragsnachweise, UV und zusätzliche Meldeverfahren. Eine begrenzte Ausnahme für ausschließlich eigene Entwicklungen gilt nicht automatisch für vertriebene Software. Ein erzeugter Export oder lokaler Test ersetzt weder die Systemuntersuchung noch einen tatsächlichen Annahmenachweis.

Für ELSTER folgen auf die Entwicklerregistrierung die Prüfung, der ERiC-Zugang und eine Hersteller-ID. Arbeitgeberzertifikate und produktive Zugangsvoraussetzungen sind zusätzlich erforderlich. Keine Registrierung, Datenübermittlung oder kostenpflichtige Beauftragung wurde vorgenommen.

## Geprüfter möglicher Entwicklungsbaustein

<https://github.com/jenner/LstGen> bietet unter MIT-Lizenz Python-Codegenerierung und eine PAP-Zuordnung `2026_1`. In der gelesenen Quelldatei <https://github.com/jenner/LstGen/blob/main/src/lstgen/pap.py> verwenden Download- und Schnittstellenhelfer `verify=False`. Diese Netzwerkhelfer wurden nicht ausgeführt und dürfen nicht unverändert übernommen werden. Eine mögliche Verwendung benötigt einen geprüften festgeschriebenen Versionsstand, Lizenzbeilage, TLS-geprüft beschafftes offizielles XML und Offline-Generierung. Das Drittprojekt ist keine amtliche Abnahme.

## Verbleibender Entwicklungs- und Prüfplan

1. Übergangsbereich, Teilmonate, Mehrfachbeschäftigung, Einmalentgelt/Märzklausel, weitere Versicherungsfälle, Altersentlastung und übrige Sonderfälle mit eigenen fachlichen Referenzen ergänzen. Aktuell blockieren diese Fälle ausdrücklich. PV/Sachsen/Kinderabschläge und Minijob-Mindestbeitrag sind bereits implementiert.
2. Weitere Entgeltunterlagen, amtlichen DLS-Prüfexport und Buchhaltungsübergabe ohne doppelte Ausgaben ergänzen. Für unterstützte Standardfälle sind inzwischen ausdrückliche Lohnkonto-Pflichtdaten, Identitäts-/Steuernachweise, tatsächliche Zahlungstage, belegte neu berechnete Monatsvorträge, Jahresübersichten und Korrekturen implementiert. Vollständigkeit wird anhand der vorhandenen Nachweise und des tatsächlichen Beschäftigungszeitraums geprüft; fehlende Felder bleiben offen. [Details](CRM_ERP_LOHN_RECHENWERK_2026.md).
3. Über die amtliche allgemeine PAP-Prüftabelle hinaus weitere unabhängige fachliche und produktbezogene Vergleichsprüfungen durchführen; tatsächliche Fachabnahme einholen.
4. Für tatsächliche Meldungen Zugang, Zulassungsweg oder geprüften Dienstleister sowie Annahme-/Ablehnungsnachweise implementieren und nachweisen.

Für die Entwicklung sind keine weiteren Routinenutzerfreigaben nötig. Vor Produktivabrechnungen müssen echte Stammdaten und gegebenenfalls Vortragswerte in der geschützten Anwendung vorliegen. Anbieterwahl, Verträge und reale externe Personaldatenübermittlung erfordern die entsprechende konkrete Beauftragung. Das Gesamtziel Lohnabrechnung bleibt bis zum vollständigen erklärten Fallumfang, zur Fachabnahme und zu erforderlichen amtlichen Voraussetzungen offen.
