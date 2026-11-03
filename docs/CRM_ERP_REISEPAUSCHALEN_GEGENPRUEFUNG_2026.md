# Unabhängige Gegenprüfung der Reisepauschalen 2026

Stand: 03.11.2026, unabhängige Basisgegenprüfung mit **20/20 bestandenen Tests eingefroren**.
Dies ist keine abschließende Abnahme sämtlicher Reise-Sonderfälle.
Die Prüfung verwendet eigene Testdateien und unabhängig eingesehene Quellen.
Sie verändert keine Produktdateien. PostgreSQL ist für diese Gegenprüfung noch
nicht ausgeführt; die Finanzintegration wird zusätzlich durch den Hauptagenten
geprüft.

## Vollständige Auslandstabelle

Die 214 Auslandspositionen mit Land/Region und jeweils drei Beträgen wurden
gegen die unabhängig abgerufene Textdarstellung des BMF-Schreibens vom
05.12.2025 verglichen: **214 Namen/Regionen und 642 Betragszellen stimmen überein**.
Deutschland ist eine zusätzliche, gesonderte Position. Die Quelle enthält
keine Afghanistan-Zeile; nicht erfasste Staaten dürfen nicht als vermeintliche
amtliche Einzelzeile ausgegeben werden.

Quelle des amtlichen Schreibens, bereitgestellt durch die IHK München:
https://www.ihk-muenchen.de/ihk/documents/Recht-Steuern/Steuerrecht/Einkommensteuer/2025-12-05-steuerliche-behandlung-reisekosten-2026.pdf

Der eigene Nachweis `evidence/travel-rates-2026-independent-source.json` ist
vollständiger, separat abgerufener **Web-PDF-Text**, kein heruntergeladenes
Original-PDF. Deshalb wird kein Originaldatei-Hash behauptet. Der unabhängige
Test rekonstruiert Namen und Zahlen aus den Seiten-/Zeilenbereichen dieser
Quelle und vergleicht nicht nur die bereits vom Implementierer angelegte
Transkriptionsdatei. Er erfasst auch die Tabellenfortsetzungen China und Türkei,
mehrzeilige Ländernamen und die getrennten Zahlenspalten der letzten Seite.

## Fachliche Gegenfälle und Quellen

Gesetz: https://www.gesetze-im-internet.de/estg/__9.html

BMF 25.11.2020, IV C 5 – S 2353/19/10011 :006, BStBl I S.1228,
amtliches Schreiben über IHK:
https://www.ihk.de/blueprint/servlet/resource/blob/5260010/6167648501baf85de6053f701b93e9b5/bmf-schreiben-25-11-2020-data.pdf

Monatsfristen: https://www.gesetze-im-internet.de/bgb/__187.html und
https://www.gesetze-im-internet.de/bgb/__188.html

Die Erwartungen der eigenen Rechentests stammen aus folgenden Regeln:

| Gegenfall | Erwartung / Grundlage | Zuletzt geprüft |
| --- | --- | --- |
| Zwei einzelne Reisen mit zusammen genau 8 Stunden, danach 8 Stunden + 1 Sekunde | 0 bzw.14 EUR; Zeit zu Hause zwischen den Reisen zählt nicht. §9 Abs.4a, BMF Rz.47 | bestanden |
| Abgelaufene Dreimonatsfrist an Stätte A und weiterer Kundeneinsatz B | Zeit an A abziehen; bei B genau 8 Stunden kein Anspruch, bei 8 Stunden + 1 Sekunde 14 EUR. BMF Rz.55 Beispiel41 | bestanden nach Korrektur |
| Nur eine belegte Nacht für eine viertägige Reise | Fehlende Übernachtungen verhindern Freigabe; kein stiller Anspruch für sämtliche Tage | bestanden nach Korrektur |
| Eintägig Belgien, danach Tätigkeit in Deutschland | Letzter ausländischer Tätigkeitsort: Belgien40 EUR. BMF05.12.2025 | bestanden nach Korrektur |
| Fristbeginn31.01.2026 | 30.04. einschließlich; nicht29.04. BGB188 Abs.2/3 | bestanden nach Korrektur |
| Mahlzeit60,01 EUR, Eigenanteil10 EUR | Sachwert50,01 EUR, keine Pauschalenkürzung, kein Kennzeichen M aus dieser Mahlzeit. BMF Rz.93 | bestanden nach Korrektur |
| Überzahlung des Frühstück-Eigenanteils | Nicht mit Mittagessenkürzung verrechnen. BMF Rz.78 | bestanden |
| Stätte April2, ab Mai3 Tage/Woche | Fristbeginn erst01.05.; BMF Beispiel40 | bestanden nach zeitlichem Frequenzvertrag |
| Stätte April3, ab Mai2 Tage/Woche | Bereits laufende Frist endet weiterhin30.06.; BMF Beispiel40 | bestanden nach zeitlichem Frequenzvertrag |
| 27 gegenüber28 vollen Abwesenheitstagen, anschließend2 Tage/Woche | Erst28 volle Tage unterbrechen; bei neuem Zweitage-Muster noch kein neuer Dreimonatslauf | bestanden |
| 8 Stunden auswärts plus2 Stunden zu Hause als `stay` | Keine10 Stunden Abwesenheit; korrekt kürzen oder widersprüchliche Reise sperren | bestanden nach Korrektur |
| Angebliche Außenübernachtung an eigener Wohnung, `claim_method=none` | Kein An-/Abreisetagsanspruch allein aus diesem Eintrag | bestanden nach Korrektur |

Es handelt sich bei den künstlichen Sekunden- und Monatsendfällen um selbst
abgeleitete Grenzfälle, nicht um vom BMF veröffentlichte Zahlenbeispiele.
Die Frequenzphasen enthalten unveränderliche Originalreferenzen. Ein heutiger
Skalar darf frühere Besuchsmuster nicht rückwirkend umdeuten.

## Flug- und Schiffsreisen: zusätzliche fachliche Fälle vor Freigabe

Amtliche LStH2026 R9.6 Abs.3:
https://amtliche-handbuecher.bundesfinanzministerium.de/lsth/2026/A-Einkommensteuergesetz/II-Einkommen-2-24b/4-Ueberschuss-d-Einnahmen-ueber-die-Werbungsk-8-9a/Paragraf-9/r-9-6.html

Am03.11.2026 lieferte der direkte Abruf503, der Suchindex dagegen den vollständigen
amtlichen Richtlinientext. Die Regeln wurden anhand dieser Fassung geprüft.
Landung, notwendige Zwischenübernachtung, Hafen und Schiffsbesatzung sind
rechtserhebliche Tatsachen. Eine allgemeine Transportbezeichnung genügt nicht.

| Tatsächlicher Fall | Zu prüfendes Ergebnis2026 |
| --- | --- |
| Flugabflug Deutschland am02.02., Landung Belgien erst03.02. | Belgien nicht schon vor der Landung verwenden; für den deutschen Anreisetag14 EUR, für spätere tatsächliche Aufenthaltstage der passende belgische Satz |
| Flug von Deutschland02.02.21 Uhr nach Tokio mit Landung04.02.06 Uhr Ortszeit | Für den dazwischenliegenden Flugtag03.02. Österreich50 EUR; Ankunftsland erst mit Landung erreicht |
| Derselbe mehrtägige Flug mit bloßer technischer Zwischenlandung Singapur ohne notwendige Übernachtung | Zwischenlandung allein ersetzt den maßgeblichen Flugtagessatz nicht |
| Tatsächlich notwendige, belegte Zwischenübernachtung in Singapur während dieses Fluges | Zwischenlandung ist zu berücksichtigen; bei voller Tagesabwesenheit71 EUR Singapur statt50 EUR Österreich |
| Gewöhnliche Schiffsreise: Einschiffung Kiel, voller Seetag, Ausschiffung Oslo | Hafenort an Ein-/Ausschiffung, regulärer voller Seetag63 EUR Luxemburg; bei Reisebeginn/-ende entsprechend14 EUR Deutschland bzw.50 EUR Norwegen |
| Deutsches Staats- oder Handelsschiffpersonal unter deutscher Flagge auf Hoher See | Voller Seetag28 EUR Inland statt63 EUR Luxemburg; Status und Hohe See müssen belegt sein |
| Datumsgrenze/mehrmals derselbe lokale Kalendertag | Zeitpunkte, Ortszeiten und tatsächlich zugeordnete Kalendertage müssen reproduzierbar bleiben; keine Verdoppelung eines Mitarbeitertags und keine freie Auswahl eines Satzes |

Die Flugmatrix beschreibt abgeleitete Referenzfälle und die jeweils bestimmte
Regel. Sie ist noch kein erfolgreich ausgeführter Integrationstest. Gerade der
Datumsgrenzenfall verlangt einen konkreten Zeitachsenvertrag, bevor vollständige
Betragserwartungen verantwortbar festgelegt werden können.

Zusätzlich R9.7 Abs.3:
https://amtliche-handbuecher.bundesfinanzministerium.de/lsth/2026/A-Einkommensteuergesetz/II-Einkommen-2-24b/4-Ueberschuss-d-Einnahmen-ueber-die-Werbungsk-8-9a/Paragraf-9/r-9-7.html

Normale Übernachtungspauschalen sind bei Unterkunft im Fahrzeug ausgeschlossen.
Für Schlafwagen/Schiffskabine braucht die Ausnahme einen tatsächlichen Beginn
oder ein Ende der Übernachtung in anderer Unterkunft. `site.kind=mobile` oder
`transport=ship` darf daher nicht allein einen Unterkunftspauschalanspruch
erzeugen. Die besondere Kraftfahrerpauschale ist ein anderer Tatbestand.

## Zahlungen und historische Integrität

Eigene Tests verwenden echte SQLite-Journale, Originaldateien, Mitarbeitende,
Geldkonten, Einreichung, unabhängige Freigabe und Zahlung. Keine Zahlungswirkung
wird durch einen Stub ersetzt.

| Gegenprobe | Zuletzt geprüft |
| --- | --- |
| Wiederholung einer angenommenen Zahlung nach aktuellem Entzug der Finanzrechte | verweigert, bestanden |
| Dokumentarisches Void erzeugt keine Rückzahlung; historischer Originalgeldfluss bleibt; alte Referenz kann nicht als neue Zahlung wiederverwendet werden | bestanden |
| Auszahlung14 EUR, Rückzahlung10 EUR, ursprüngliche Auszahlung auf5 EUR berichtigen | negatives Netto wird zurückgewiesen; bestanden nach Korrektur |
| Auszahlung nach bestehender echter Rückzahlung dokumentarisch aufheben | ungedeckte Rückzahlung wird zurückgewiesen; bestanden nach Korrektur |
| Nach Auszahlung14 EUR Abrechnung auf7 EUR vermindern | vorherige tatsächliche Zahlung berücksichtigt; keine weitere Auszahlung; bestanden nach Korrektur |
| Historischen Mitarbeitersnapshot samt Hash und Ergebnisquittung auf erfundene Identität/Revision umschreiben | kanonische Originalrevision und Nutzerbindung werden geprüft; bestanden nach Korrektur |
| Reservierten Originaldatei-Hash in der Evidenztabelle verändern | Bindung gegen erste tatsächliche Zahlungsfassung wird geprüft; bestanden nach Korrektur |

Die beiden letzten Tests entfernen ausschließlich in ihrer isolierten
Testdatenbank die gewöhnlichen Mutationssperren. Sie simulieren beschädigte
Import-/Restore-Daten, um zusätzlich zur normalen Unveränderlichkeit die
unabhängige Quellenrekonstruktion nachzuweisen. Ein angepasster Eigenhash ist
kein Ersatz für den ursprünglichen Nachweis.

Bei einer verminderten Abrechnung bleibt die echte frühere Zahlung erhalten.
Ein Erstattungsüberhang verlangt eine echte, separat belegte Rückzahlung oder
eine sachlich begründete Berichtigung des fehlerhaft erfassten Zahlungsvorgangs.
Er darf weder automatisch als Rückzahlung noch als neues Auszahlungspotenzial
ausgewiesen werden. Historische Zahlungspräfixe müssen dabei reproduzierbar
bleiben; heutige Zahlungen dürfen nicht alte Abrechnungsfassungen umrechnen.

## Eigene Testdateien und Ausführung

- `backend/test_payroll_travel_review.py`: 13 Tests,13 bestanden.
- `backend/test_business_travel_review.py`: 7 Tests,7 bestanden.
- `docs/evidence/travel-rates-2026-independent-source.json`: unabhängige Quellendarstellung der vollständigen Auslandstabelle.

```sh
PYTHONPATH=backend:backend/online /tmp/smartplan-backend-verified/bin/python -m unittest -v test_payroll_travel_review test_business_travel_review
```

Die dokumentierten roten Gegenfälle wurden vom Implementierer korrigiert und
unabhängig erneut geprüft: alle20 bestanden. Nachweise stehen in
`evidence/travel-review-base-2026-11-03.json` und der zugehörigen Textdatei.
Diese beiden eigenen Testdateien bleiben für die nächste Entwicklungsphase
unverändert. Der Prüfer übernimmt danach den isolierten Transport-Regelhelfer;
dieser neue Code wird ausdrücklich durch den bisherigen Backendimplementierer
gegengeprüft. Die unabhängige Prüfung der Basis wird damit nicht nachträglich
als unabhängige Prüfung des eigenen Transportcodes ausgegeben.

Flugtage,
Schiffstage, Auslagenbindung, gemischte Veranlassung, Ersatzmahlzeiten und die
vollständige Verarbeitung steuerpflichtiger Anteile benötigen weiterhin eigene
vollständige fachliche und technische Nachweise; sie gelten nicht allein durch
einen vorläufigen Sperrhinweis als fertig.
