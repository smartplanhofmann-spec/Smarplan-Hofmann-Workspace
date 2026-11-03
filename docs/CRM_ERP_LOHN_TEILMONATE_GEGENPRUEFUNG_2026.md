# Unabhängige Gegenprüfung: Lohnzeitachsen und Teilmonate 2026

Stand: 03.11.2026. Dieser Bericht prüft den
[P2/P3-Vertrag](CRM_ERP_LOHN_ZEITACHSEN_TEILMONATE_ENTWURF.md) und den neuen
reinen Teilmonatskern unabhängig von dessen Implementierungstests.
Er behauptet keine Meldestrecke und keine fachliche Produktivfreigabe. Bestehende
Vollmonatsregeln und Originalabrechnungen bleiben unverändert.

## Tages-PAP und Entgeltrest

Die drei Jahreszeilen 45.000/67.500/90.000 EUR wurden erneut mit der allgemeinen
Prüftabelle auf Seite 39 des [endgültigen PAP 2026](https://www.ihk-muenchen.de/ihk/documents/Recht-Steuern/Steuerrecht/Einkommensteuer/2025-11-12-PAP-2026-anlage-1.pdf)
abgeglichen. Alle 18 übernommenen Lohnsteuerwerte stimmen. Die Tageswerte
werden daraus unabhängig durch Abschneiden der jährlichen Centbeträge nach
Division durch 360 hergeleitet; dies ist keine amtlich veröffentlichte eigene
Tagestabelle. Der PAP beschreibt Ganzzahl-Centfelder, Abschneiden am
Empfangsfeld und keine zusätzliche Rundung technischer Zwischenfelder.

Die Wiederverwendung des unveränderten jährlichen PAP mit exakt 360-fachen
Tages-Eingaben ist für dessen bereits unterstützte Versicherungs-/Steuerfälle
zulässig: Die Hochrechnung ist dieselbe. Erst danach werden LSt, Soli und
Maßstabsteuer jeweils auf den einzelnen Tag zurückverteilt. Bereits gekürzte
Tageswerte werden summiert. Ein Fall mit 17 Tagen und Klasse I trennt beide
Reihenfolgen: 917,83 EUR statt 917,90 EUR.

Zusätzlicher Eingabegegenfall: 375,02 EUR über drei Steuertage ergeben für
`RE4` 12.500 Cent und einen Rest von zwei Cent bei Nenner drei. Die belegten
375,02 EUR dürfen weder auf 375,00 EUR geändert noch durch Verteilung des Rests
in künstlich verschiedene Tageslöhne ersetzt werden. Die gleichmäßig
hergeleitete LSt beträgt im referenzierten Klasse-I-Fall 46,41 EUR.

## Freibetrag ist kein Bruttolohn-Rundungsfall

[R 39a.1 Absatz 7 im LStH 2026](https://gewsth.bundesfinanzministerium.de/lsth/2026/A-Einkommensteuergesetz/VI-Steuererhebung-36-47/2-Steuerabzug-vom-Arbeitslohn-Lohnsteuer-38-42g/Paragraf-39a/inhalt.html)
legt eine eigene Aufrundung für Tagesfreibeträge und Hinzurechnungsbeträge
auf fünf Cent fest. Der vollständige Wortlaut wurde zusätzlich in der
[endgültigen Richtlinienveröffentlichung, Seite 40](https://media.frag-den-staat.de/files/docs/58/87/65/588765db0e33433fa82243330f2e0feb/bstbl_2022_s2.pdf)
gelesen. R 39b.5 Absatz 3 verlangt bei der Ableitung durch den Arbeitgeber den
bereits aufgerundeten Monatsbetrag als Ausgangspunkt.

Die einfache Übertragung der Brutto-Regel `monthly_minor // 30` auf den
Freibetrag ist deshalb keine ausreichende fachliche Herleitung. Ein monatlicher
Betrag von 100 EUR trennt 3,33 EUR von 3,35 EUR. Abgestimmt und umgesetzt ist
die ausdrückliche Ableitung aus dem belegten Monatsmerkmal, für Freibetrag und
Hinzurechnungsbetrag gleichermaßen. Die Herkunft ist im Ergebnis erkennbar;
die Prüfung erfindet kein amtlich bereitgestelltes Tagesmerkmal.

## Kirchensteuer nach ermittelter Maßstabsteuer

Der PAP liefert die Maßstabsteuer `BK`, nicht die Kirchensteuer.
[Art. 8 BayKirchStG](https://www.gesetze-bayern.de/Content/Document/BayKirchStG-8),
[Art. 13 BayKirchStG](https://www.gesetze-bayern.de/Content/Document/BayKirchStG-13)
und [§ 9 Absatz 2 AVKirchStG](https://www.gesetze-bayern.de/Content/Document/BayAVKirchStG-9)
binden den Zuschlag an die ermittelte Lohnsteuer, den Abzug an die Lohnzahlung
und verlangen Abschneiden von Centbruchteilen. Daraus folgt für eine gemeinsame
Lohnzahlung des tatsächlichen Teil-LZZ: zuerst dessen täglich ermittelte
Maßstabsteuer summieren, danach den Zuschlag auf Cent abschneiden. Diese
Herleitung ist eine gesetzesbezogene Ableitung; eine ausdrückliche amtliche
17-Tage-Kirchensteuertabelle wurde nicht gefunden.

Gegenfall Bayern, Klasse VI, 17 Tage à 250 EUR, ohne Kinderfreibetrag:
`BK = 17 × 7.466 = 126.922` Cent. Bei 8 % ergeben sich 10.153 Cent. Tägliches
Abschneiden der Kirchensteuer vor der Summierung ergäbe dagegen 10.149 Cent.
Ein eigener Kirchen-/Konfessionssonderfall oder mehrere getrennte Lohnzahlungen
wird dadurch nicht automatisch freigegeben. Die bayerischen Normen sind keine
behauptete vollständige Rechtsprüfung sämtlicher Landesregelungen.

## Sozialversicherung: tatsächlicher Anlass einer Aufteilung

Die Formulierung, dass beliebige Teilperioden immer eine einzige unveränderte
Monats-BBG teilen, ist zu grob. Die
[GKV-Anlage 11, Version 2025.2, Seiten a11-1/2](https://gkv-ag.de/wp-content/uploads/2025/05/Pflichtenheft-EA-V2025-2-Anlagen-Gesamtdokument.pdf)
unterscheidet sachlich notwendige Mehrfachabrechnungen. Ihr Beispiel eines
Beitragsgruppenwechsels am 16. Juli zählt 15 und 16, insgesamt 31 SV-Tage.
Die aktuelle [GKV-Fassung vom 17.06.2026, Abschnitt 2.2.3, Seiten 42–43](https://www.gkv-datenaustausch.de/media/dokumente/arbeitgeber/deuev/gemeinsame_rundschreiben/2026-06-17_GemRS.pdf)
bestätigt die besonderen Grenzen für Meldedaten. Die zusätzlich dort genannte
Februar-Toleranz ist eine Meldeprüfung und darf keine fiktiven Entgelte oder
Abrechnungstage erzeugen. Die aktuelle Anlage 2026.2 ist verlinkt, ihr ZIP war
mit dem Web-Lesewerkzeug nicht lesbar; ein gelesener Volltext wird nicht behauptet.

Aus den 2026-Jahresgrenzen unabhängig hergeleitet: Ein fachlich erforderlicher
Juli-Split 15/16 hat KV/PV-Grenzen von 2.906,25/3.100,00 EUR und RV/AV-Grenzen
von 4.225,00/4.506,67 EUR. Das ist von zwei frei erfassten Entgeltzeilen ohne
Versicherungsereignis zu unterscheiden: Solche Zeilen schaffen keine zweite
BBG. P3b benötigt daher einen typisierten belegten Aufteilungsanlass.

Nach [§ 1 BVV](https://www.gesetze-im-internet.de/beitrvv/__1.html) werden die
Teil-BBG ohne vorgezogene Tagesrundung hergeleitet. Ein ganzer Februar hat
30 SV-Tage; Beschäftigung vom 17. bis 28. Februar hat zwölf. Ein echtes
eintägiges Dienstverhältnis am 31. hat einen SV-Tag. Unbezahlte Tage bei
fortbestehendem Dienstverhältnis sind weder automatisch Austritt noch ein
verkürzter steuerlicher LZZ.

## Minijob-Mindestbasis und Quellenabweichung

Die [Geringfügigkeits-Richtlinien vom 05.01.2026](https://www.minijob-zentrale.de/SharedDocs/Downloads/DE/Rundschreiben/Geringfuegigkeitsrichtlinien-2026.pdf?__blob=publicationFile)
beschreiben in C 3.2.1 den anteiligen Mindestbetrag. Beispiel 29, Seite 117,
setzt zunächst die anteilige Grundlage auf 116,67 EUR fest und berechnet
anschließend ausdrücklich 18,6 % aus dieser Grundlage. Zusammen mit den
[Berechnungsregeln der BVV](https://www.gesetze-im-internet.de/beitrvv/BVV.pdf)
wurde die getrennte Rundung der fertigen Teilbasis und des anschließenden
Beitrags mit dem Implementierer abgestimmt. Daraus folgt für einen einzelnen
SV-Tag eine Grundlage von 5,83 EUR und ein Mindestbeitrag von 1,08 EUR.
Das ist eine begründete Ableitung der Rechenschritte; eine unmittelbar
veröffentlichte amtliche Ein-Tages-Tabelle liegt dafür nicht vor.

Beispiel 30 derselben Richtlinie druckt für 157,50 EUR Grundlage einen Beitrag
von 29,31 EUR. Die ausgewiesene Operation `157,50 × 18,6 %` ergibt dagegen
29,295 EUR und kaufmännisch 29,30 EUR. Der Produktgegenfall übernimmt diese
Quellenabweichung nicht: Bei 50 EUR gewerblichem Minijoblohn verbleiben
21,80 EUR Arbeitnehmer- und 7,50 EUR Arbeitgeberbeitrag. Der Test verwendet
einen tatsächlich 27 Tage dauernden Beschäftigungszeitraum; die im Original
beschriebene längere unbezahlte Unterbrechung ist damit ausdrücklich noch nicht
als implementierter Anspruchsfall nachgewiesen.

## Teilmonat im Übergangsbereich

Das [gemeinsame Rundschreiben vom 20.12.2022](https://www.kbs.de/SharedDocs/Downloads/DE/VersicherungsrechtBeitraegeMeldungen/Downloads/Uebergangsbereich_idF_20_12_2022.pdf?__blob=publicationFile&v=2)
fordert in 4.3.2.1 ungerundete Zwischenergebnisse und berücksichtigt in 4.3.2.5
ausdrücklich abweichende arbeitsvertragliche Teilentgeltquotienten. Die Beispiele
6 und 7b wurden erneut gelesen. Die dortigen Zahlen gehören zum Regelstand
2023 und werden nicht als fertige 2026-Werte übernommen.

Unabhängige rationale Arithmetik mit den 2026-Parametern trennt vorgezogene
Vollbasisrundung von der Rundung der fertigen Teilbasis: 20,31 EUR tatsächlicher
Lohn bei Quote 1/30 und 609,30 EUR regelmäßigem Monatslohn ergibt 13,54 EUR
Gesamtbasis und 0,30 EUR Arbeitnehmerbasis. Vorgerundete Vollbasis ergäbe
13,55 EUR. Bei 311,71 EUR und Vertragsquote 16/31 sind es 206,56 EUR und
0,69 EUR. Die 16 SV-Tage ersetzen die belegte Vertragsquote nicht durch 16/30.
Auch diese Grenzen sind aus den Normen abgeleitete Regressionen, keine amtlich
publizierten Teilmonatstabellen.

## Integrität und Rechte als unabhängige Gegenfälle

Für die neue Faktenhistorie sind zusätzlich vorgesehen:

- Fachlich widersprüchliche Quittungen mit neu berechnetem eigenem Hash müssen
  gegen die tatsächlich gebundenen Quellen auffallen.
- Nach einer legitimen späteren Korrektur bleibt die alte angenommene Anfrage
  exakt wiederholbar; ein aktueller Rechteentzug sperrt trotzdem die Ausgabe.
- Ein ausdrücklich gebundener Arbeitsplan, ein Profil oder eine Entgeltfassung
  darf nicht still durch den aktuellen Stand ersetzt werden.
- Mitarbeiter- und Originalzuordnung werden unabhängig vom eigenen
  Dokumenthash geprüft; private Zeitachsen bleiben aus dem allgemeinen
  Finanz- und Assistentenkontext ausgeschlossen.

## Ausgeführte Produktgegenprüfung

`backend/test_payroll_periods_review.py`: **12 Tests bestanden**, ausgeführt mit
`PYTHONPATH=backend:backend/online /tmp/smartplan-backend-verified/bin/python -m unittest -v test_payroll_periods_review`.
Die Tests übernehmen nur den synthetischen Quellenaufbau aus dem Kern-Testmodul;
Erwartungswerte werden weder aus dessen Referenz-JSON noch aus dem produktiven
Jahres-PAP berechnet. Abgedeckt sind die vorstehenden numerischen Gegenfälle,
ein negativer Minijob-Nettobetrag mit getrennter Arbeitnehmernachzahlung,
fehlende Mindestbasis bei anderweitiger RV-Pflicht, volle Februar-/tatsächliche
Juli-Steuertage sowie blockierte untermonatige Kassenwechsel und unbezahlte
Abwesenheiten. Es wurde kein PostgreSQL-Lauf durchgeführt.

`backend/test_business_payroll_facts_review.py`: **10 weitere unabhängige Tests
bestanden**. Drei konkret reproduzierte Befunde wurden vom zuständigen
Implementierer behoben und anschließend unabhängig erneut geprüft:

1. Die ursprüngliche Mitarbeiterrevision des angenommenen Auftrags muss zur
   eingefrorenen aktiven Faktenquelle passen, selbst wenn eine spätere Revision
   tatsächlich existiert. Eine spätere Archivierung darf weiterhin die historische
   Quelle erhalten.
2. Die eingefrorene Mitarbeiter-/Benutzerzuordnung wird gegen den unabhängigen
   Personalstamm und die ursprüngliche Personalquittung der betreffenden Revision
   geprüft. Neue eigene Hashwerte einschließlich angepasster technischer Quittung
   legitimieren keine fremde Zuordnung.
3. Ein erst nach dem tatsächlichen Austritt wirksames Profil wird nicht für den
   früheren Beschäftigungszeitraum verlangt. Der Test trennt den Austritt am
   20. Oktober vom späteren Profilbeginn am 25. Oktober.

Die weiteren Gegenfälle manipulieren Plan, gebundenes Lohnprofil und
Originalmetadaten einschließlich passender neuer Ereignis-/Quittungshashes.
Sie prüfen außerdem eine Arbeitsplankorrektur ohne Austausch historischer
Quellen, getrennte Schreib-/Freigaberechte und deren aktuellen Entzug sowie
unveränderte JSON-/PDF-Originale eines finalisierten v4-Laufs nach späterer
Archivierung der Fakten und Modulpausierung.

Der gemeinsame unabhängige Abschlusslauf umfasst damit **22 bestandene Tests,
keine Fehler, keine übersprungenen Tests**. Der
[vollständige Testlauf](evidence/payroll-period-review-2026-11-03.txt) und seine
[Prüfsummen/Dateistände](evidence/payroll-period-review-2026-11-03.json) sind
festgehalten. Das ist die Freigabe dieser abgegrenzten Gegenprüfung. Mehrere
untermonatige Versicherungs-/Kassenperioden, eigene Anspruchsberechnungen und
gesetzliche Meldestrecken sind damit weiterhin nicht als implementiert belegt.
