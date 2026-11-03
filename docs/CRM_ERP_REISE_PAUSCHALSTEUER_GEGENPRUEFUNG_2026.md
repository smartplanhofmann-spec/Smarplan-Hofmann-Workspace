# Unabhängige Gegenprüfung Reise-Pauschalsteuer 2026

Stand: 03.11.2026. Review durch den P4-Faktenagenten; Produktverantwortung des geprüften `backend/payroll_travel_tax_2026.py` bleibt beim Root-Agenten. Eigene Fälle stehen in `backend/test_payroll_travel_tax_review.py`; die Fixtures und Sollwerte sind separat formuliert. Dieser Review betrifft den reinen Steuerbaustein, nicht die noch laufende private Quellen-/v5-Abschlussintegration.

## Befunde und Reproduktion

Erster eigener Lauf: zehn Testmethoden, acht grün und zwei rot (drei fehlgeschlagene Unterfälle). Der unveränderte Rohlog liegt in `work/verification/payroll-travel-tax-review-initial.log`.

1. Eine nach amtlichem Muster belegte Arbeitnehmererklärung ist bei fehlendem ELStAM-/Ersatznachweis zulässig. Der Erststand akzeptierte ausschließlich diese beiden amtlichen Abruf-/Bescheinigungsarten und sperrte die ebenfalls zulässige Erklärung. Gegenprobe verwendet `church_membership_evidence.kind=official_employee_declaration` mit konkreter Originalreferenz und belegter Mitgliedschaft oder Nichtmitgliedschaft.
2. Für nach dokumentierter Prüfung nicht ermittelbare Zugehörigkeit sieht der Erlass den allgemeinen Kirchensteuersatz vor. Der Erststand blockierte diesen Fall. Gegenprobe verwendet `unknown_membership_general_rate` mit Originalreferenz und `church_tax:null`; inBE ergeben123,47EUR steuerpflichtiger Reisekostenersatz30,86EUR pauschale Lohnsteuer,1,69EUR Solidaritätszuschlag und2,77EUR Kirchensteuer. Unbelegtes `null` bleibt gesperrt.

Kein weiterer Rechen-/Fristbefund in den acht übrigen eigenen Methoden: getrenntes Centabschneiden, quartalsübergreifend einheitliche Policykennung, spätere Quellfassungen mit verändertem Quellhash, echte Kapazitätsgrenze, frühere Lohnsteuerbescheinigung, Ende-Februar-Obergrenze, wirtschaftlicher Arbeitnehmerabzug bei unveränderter Arbeitgebersteuerschuld sowie unzulässige Regions-/Referenztypen.

Nach Korrektur durch den Produktverantwortlichen sind beide Befunde geschlossen. Ein zusätzlicher eigener Gegenfall prüft, dass eine dokumentierte unbekannte Zugehörigkeit keinem zugleich behaupteten bekannten Status widersprechen darf und eine Mustererklärung ohne konkreten Status nicht steuerfrei wird. Unabhängiger Abschlusslauf: **21/21 in0,006 Sekunden**, davon11 eigene Reviewfälle und10 Autorentests, ohne Skip. [Nachweis mit Quellhashes](evidence/payroll-travel-tax-review-2026-11-03.json), [erster roter Lauf](evidence/payroll-travel-tax-review-initial-2026-11-03.txt), [grüner Abschlusslauf](evidence/payroll-travel-tax-review-final-2026-11-03.txt).

## Tatsächlich unabhängig gelesene Quellen

| Quelle | Zugriff und Aussage |
|---|---|
| [Gleichlautender Erlass Kirchensteuer, amtliches REVOSax](https://www.recht.sachsen.de/vorschrift/16974) | Aktuellen vollständigen Text gelesen; Stand zuletzt durch Verwaltungsvorschrift02.12.2025 bestätigt. I.2.b belegt die Mustererklärung als Alternative, I.2.d den allgemeinen Satz bei ungeklärter Zugehörigkeit. I.1/I.2 unterscheiden sämtliche Empfänger im vereinfachten Verfahren von individuellem Nachweis. |
| [DRV: Beiträge2026](https://www.deutsche-rentenversicherung.de/SharedDocs/Downloads/DE/Fachliteratur_Kommentare_Gesetzestexte/summa_summarum/e_paper_und_broschueren/broschueren/beitraege.pdf?__blob=publicationFile&v=10) | PDF tatsächlich geöffnet; Abschnitte5.3/5.4, insbesondere Druckseite38, gelesen. Der allgemeine Absatz nennt ausdrücklich auch§40 Abs.2 und bindet nachträgliche Änderung an die Bescheinigung, spätestens EndeFebruar. Die zusätzliche Passage aufS.40 betrifft Betriebsveranstaltungen und wird nicht als alleiniger Reisenachweis verwendet. |
| [§4 SolZG](https://www.gesetze-im-internet.de/solzg_1995/__4.html) | Volltext gelesen:5,5% und Weglassen von Centbruchteilen. |
| [Abresa August2024, SAP-Hinweis3476420](https://abresa.de/wp-content/uploads/2025/02/Abresa_HCM-Kundeninfo-August-2024.pdf) | PDF und konkrete Passage Druckseite46 gelesen. Dokumentierte Korrektur kaufmännischer Pauschalsteuerrundung zugunsten des Centabschneidens; fachliche Sekundärquelle, kein eigener Gesetzestext. |
| [BMF-Muster Lohnsteuer-Anmeldung2026, IHK-Spiegel](https://www.ihk-muenchen.de/ihk/documents/Recht-Steuern/Steuerrecht/Einkommensteuer/2025-08-14-Muster-Lohnsteuer-Anmeldung-2026.pdf) | Das amtliche Formular im erreichbaren IHK-Spiegel gelesen, einschließlich Hinweise zum vereinfachten Verfahren und Anmeldezeitraum. Es ist keine vollständige Tabelle der16 Kirchensteuersätze. Direkter BMF-PDF-Abruf503. |

Der direkte erneute SvEV-Abruf lief in ein Timeout. Die16 Landessteuersätze und die Regionalausnahmen wurden in dieser unabhängigen Runde nicht sämtlich anhand einzelner Landesnormen erneut geprüft; der differenzierte Quellenstand des Produktdokuments bleibt maßgeblich. Kein Nachweis wird durch eine synthetische Originalreferenz rechtlich festgestellt: Besitz, tatsächlicher Inhalt, Betragskapazität, Betriebsstätte, Arbeitgeberpolicy und Erfassungszeitpunkt gehören weiterhin in den privaten Resolver.
