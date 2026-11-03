# P3b – Ereignisse, Segmentrechnung und unveränderliche Rechenfassungen

Stand: 03.11.2026. **Segment-/Anspruchs-/Reise-Komposition unter `de_2026_segments_entitlements_v5` implementiert und additiv registriert; abschließende Client-/Komponentenabnahme und Freeze laufen.** [P3a/v4](CRM_ERP_LOHN_TEILMONATE_2026.md) bleibt unverändert. Mehrere Entgeltvereinbarungen, datierte steuerliche Merkmale und tatsächliche Aus-/Wiedereintritte werden im neuen Gesamtfall zusammengeführt. Fachlich noch nicht vollständig belegte SV-Status-/Kassenwechsel bleiben konkrete Blocker. Der aktuelle Quellen-, Prüfungs- und Integrationsstand steht in [Berechnungsfälle-API](CRM_ERP_LOHN_BERECHNUNGSFAELLE_API.md); die folgenden Entwurfsabschnitte dokumentieren die ursprüngliche Abgrenzung und Quellen.

## Historischer Vertrag ohne stillen Versionswechsel

Auch ein bestätigter, damals blockierter P2-Periodenfall ist ein unveränderlicher fachlicher Nachweis. Sein `rule_version`, `plan_hash`, seine Blocker und `can_calculate: false` müssen nach Einführung von P3b gleich bleiben. Ein altes `multiple_wage_agreements` darf bei einer historischen Integritätsprüfung nicht durch einen inzwischen erweiterten Standard-Builder verschwinden.

Vorgeschlagene additive Architektur:

1. P2-Quellen und die v4-Kernmodule bleiben bytegleich. Ihre bestehenden Resolver validieren historische P2-/v4-Fassungen weiter nach v4.
2. Ein **neuer Abrechnungsfall** bindet explizit `rule_version`, `source_contract_version`, einen vollständigen historischen Quellenstand und den daraus berechneten Plan. Er kann einen P2-Basisfall referenzieren, ergänzt ihn aber durch eigene belegte Segment-/Beschäftigungsereignisse und später P4-Anspruchsfakten. Er schreibt weder die P2-Vorbereitung noch die Entgeltvereinbarungen nachträglich um.
3. Neue Payroll-Eingabe als Vertragsvorschlag: `{source_schema_version: 3, employee_id, calculation_case_ref}`. Der Aufrufer übergibt keine Brutto-/Steuer-/SV-Summen. Der Server löst die exakte Fallrevision auf; Regelname und Quellenformat stammen aus diesem Fall.
4. Ein expliziter Dispatcher ordnet jeder gespeicherten Regelversion ihren damaligen reinen Builder und Rechner zu. Unbekannte Versionen scheitern; `latest`, aktuelle Profile oder aktuelle Anspruchsregeln sind kein historischer Ersatz.
5. Erst eine neu bestätigte Fallrevision und anschließend eine ausdrückliche Laufkorrektur dürfen eine neue Rechenversion anwenden. Die bisherigen Originale, Zahlungen, Jahresfassungen und Bankbelege bleiben unverändert.

Der neue Abrechnungsfall verwendet eigene Ereignis-/Quittungstabellen, einen Quellenresolver und die bestehenden frischen privaten Rechte-, MFA-, Modul- und Instanzprüfungen. DDL, API, Exportkatalog und Paketregistrierung sind zentral ergänzt. Echte PostgreSQL-HTTP-Fälle prüfen zwei gleichzeitige Schreiber, Originalreplay, Rechteentzug, Offline-Sperre und Dump/Restore einschließlich tatsächlicher Pauschalsteuererfassung.

## Fachliche Ereignisse statt beliebiger Profilzeilen

Ein Profil enthält gleichzeitig steuerliche, beitragsrechtliche und rein beschreibende Angaben. Seine neue Zeile ist deshalb allein noch keine Abrechnungsgrenze. Geplant ist die folgende explizite Trennung:

| Belegtes Ereignis | Entgelt | Steuer-LZZ | SV-Berechnung |
|---|---|---|---|
| neue wirksame Entgeltvereinbarung | eigene belegte Entgeltposition; bei Stundenlohn tatsächliche Stunden je Wirksamkeitsintervall | bestehender tatsächlicher LZZ bleibt zusammenhängend | Entgelte desselben Versicherungszeitraums zuerst zusammenführen; keine zusätzliche BBG wegen einer Vertragszeile |
| neue ELStAM-/Steuermerkmale | kein zusätzliches Entgelt | Merkmale grundsätzlich am Ende des tatsächlichen LZZ; vorzeitige Zahlungen/rückwirkende Merkmale brauchen ihren eigenen Korrekturbezug | kein zusätzlicher SV-Zeitraum allein aus Steuerklasse oder Freibetrag |
| korrigierter Name oder Prüfvermerk | kein zusätzliches Entgelt | unverändert | unverändert; keine künstliche Cent-Rundung je technischer Revision |
| tatsächlicher Beitrags-/Personengruppenwechsel | Entgelt der jeweiligen tatsächlichen Periode zuordnen | nach Dienstverhältnis/LZZ gesondert prüfen | echte fachliche Teilzeiträume, tatsächliche Tage und getrennte Beitragsbasen je einschlägigem Zweig |
| tatsächlicher Aus- und Wiedereintritt | getrennte belegte Beschäftigungsepisoden | tatsächliche LZZ-/Dienstverhältnisgrenzen | fachliche Teilzeiträume; Lücke nicht als Beschäftigung behandeln |
| unbezahlte Unterbrechung mit Wiederaufnahme | Anspruchsende und Ausfallentgelt stammen aus P4 | fortbestehendes Dienstverhältnis wird durch unbezahlte Tage nicht automatisch gekürzt | Fortbestandsende und spätere Wiederaufnahme stammen aus belegtem P4-Fall, nicht aus fehlenden Projektstunden |
| Kassenwechsel/Änderung eines Kassensatzes | kein Entgeltgrund | eigener Steuermerkmalsstand prüfen | tatsächliche Wirksamkeit und Rechtsgrund getrennt belegen; eine neue Kassenbezeichnung allein ist kein Teil-BBG-Auslöser |

Die normative Grundlage zur Steuerachse ist [R39b.5 Absätze 1–5](CRM_ERP_LOHN_R39B5_QUELLENAUSZUG_2026-11-03.txt). Ein neuer Steuerwert am 16. eines Vollmonats darf den Monat nicht automatisch in zwei Tages-LZZ zerlegen. Eine Zuordnung nach Zahlungstag ersetzt nicht die rechtliche Zuordnung zum LZZ.

## Erneut gelesene Primärquellen zur SV-Segmentierung

- [GKV-Pflichtenheft EA 2026.2, gültig 01.07.2026](https://gkv-ag.de/wp-content/uploads/2026/06/Pflichtenheft_EA_2026.2.pdf), Seite 450, Modul 0900, Kriterium `d5f08ddd-c728-41fb-96bc-7e01c88dda0d`: Für Mehrfachabrechnungen verweist der aktuelle Kriterienkatalog auf Anlage 11. Gelesen wurden die einschlägigen Fundstellen, nicht sämtliche 653 Seiten. Die Verweise zu Kassen-/Meldezeiträumen ersetzen noch keinen vollständigen Beitragssatz- oder Entgeltaufteilungsalgorithmus.
- [GKV-Anlage 11 in Ausgabe 2025.2](https://gkv-ag.de/wp-content/uploads/2025/05/Pflichtenheft-EA-V2025-2-Anlagen-Gesamtdokument.pdf), PDF-Seiten 41–42, interner Stand 13.12.2021: nennt konkrete fachliche Mehrfachabrechnungsereignisse und tatsächliche Tage bei Aufteilung eines Nicht-30-Tage-Monats. Ihr Juli-Beispiel verwendet 15+16 Tage beim Beitragsgruppenwechsel. Diese Quelle ist ausdrücklich eine ältere gelesene Anlagenfassung.
- [Aktuelles gemeinsames DEÜV-Rundschreiben vom 17.06.2026](https://www.gkv-datenaustausch.de/media/dokumente/arbeitgeber/deuev/gemeinsame_rundschreiben/2026-06-17_GemRS.pdf), veröffentlicht 25.08.2026, Abschnitt 2.2.3, Seiten 42–43: beschreibt weiterhin die mögliche Überschreitung aus tatsächlichen Teilzeiträumen und die Toleranzen der Meldedatenprüfung. Die zusätzliche Februar-Prüftoleranz ist keine allgemeine Erhöhung der tatsächlichen Abrechnungs-BBG.
- [DRV-Rechtsanwendung zu §159 SGB VI](https://rvrecht.deutsche-rentenversicherung.de/SharedDocs/rvRecht/01_GRA_SGB/06_SGB_VI/pp_0151_175/gra_sgb006_p_0159.html?nn=1504346): Teilmonate bemessen sich nach den Versicherungspflichttagen; Verweis auf §189/§123 SGB VI und §1 BVV. Zusammen mit den P3a-Referenzen begründet dies getrennte Tage-/BBG-Achsen, nicht eine frei wählbare Zahl von Teil-BBG.
- [BMG zum Krankenkassenwechsel](https://www.bundesgesundheitsministerium.de/themen/krankenversicherung/online-ratgeber-krankenversicherung/krankenversicherung/wahl-und-wechsel-der-krankenkasse): normale Wechsel haben Bindungs-/Kündigungsfristen. Untermonatige Sonderereignisse müssen deshalb aus dem tatsächlichen Mitgliedschafts- beziehungsweise Statusnachweis stammen; kein frei erfundener Kassenwechsel nur zum Erzeugen eines Teilzeitraums.

Die [Veröffentlichungsseite des aktuellen Pflichtenhefts](https://gkv-ag.de/pruef-testverfahren/pflichtenhefte/pflichtenheft-entgeltabrechnungsprogramme-ea/) verlinkt das [Anlagen-ZIP 2026.2 vom 06.07.2026](https://gkv-ag.de/wp-content/uploads/2026/07/Anlagen-zum-Pflichtenheft-EA_2026.2_2026-07-06.zip). Der Webleser meldete für dieses ZIP `Unsupported content-type: application/zip`. Deshalb wird kein Vollabgleich der aktuellen Anlage 11 behauptet. Die aktuelle Hauptquelle und das aktuelle Rundschreiben wurden erfolgreich gelesen; die Anlagenprüfung wird weiterverfolgt.

## Geplanter Quellen- und Ergebnisvertrag

`build_segment_plan(snapshot)` bleibt rein: keine Datenbank, aktuelle Systemzeit, Rechteentscheidung oder aktuelle Quelle. Der neue Snapshot bindet die originalen Personalvorbereitungen, alle wirksamen Entgeltvereinbarungen, belegte Beschäftigungsepisoden, alle benötigten Profil-/Identitätsfassungen, Vertragsmethoden und tatsächlichen Arbeitspläne sowie eine versionierte Ereignisliste. P4-Anspruchsergebnisse werden als eigenständige, mit Regel-/Quellenhash gebundene Bausteine ergänzt. Eine neue gemeinsame Quellenfassung darf eine alte v4-Quelle einschließen, aber nicht verändern.

Jedes Ereignis braucht Typ, Wirksamkeitstag, betroffene Quellen davor/danach, geschützte Originalreferenzen und belegten Grund. Fachlicher Ereignistyp und automatisch ermittelter Feldunterschied müssen zusammenpassen. Ein als reiner Steuerwechsel bezeichnetes Ereignis darf keinen gleichzeitig geänderten Versicherungsstatus verbergen. Widersprüchliche oder nicht vollständig gedeckte Intervalle bleiben präzise blockiert.

Geplante Ergebniselemente:

- `employment_episodes`: tatsächliche, nicht überlappende Beschäftigungsintervalle mit Quellenreferenzen;
- `earnings`: je tatsächlich wirksamer Vereinbarung/Anspruchsart eigener Zeitraum, Entgeltbasis, exakter Quotient, Centbetrag und Herkunft;
- `tax_periods`: tatsächlicher LZZ, Summe seiner steuerpflichtigen laufenden Entgelte, Endmerkmalsfassung, PAP-Eingaben und Divisionrest;
- `social_assessments`: fachliche Beitragszeiträume, auslösender Ereignistyp, zugeordnete Entgeltpositionen, Tageszahl, BBG/Basis sowie AN-/AG-Beiträge je Zweig;
- `rounding_steps`: nur gesetzliche beziehungsweise belegte vertragliche Rundungsstellen; keine Rundung an beliebigen UI-Zeilen;
- `provenance`, `blockers`, `plan_hash`: einschließlich aller beteiligten Regel-/Quellenfassungen.

Eine Entgeltposition darf innerhalb desselben Steuer-/Versicherungszweigs nicht doppelt zugeordnet sein. Vollständige Abrechnung setzt lückenlose Zuordnung voraus. Mehrere Segmente erzeugen weiterhin nur eine wirksame Monatsabrechnung; Korrektur, Identität, Zahlung, Jahresausgabe, Cash und Bank binden die genaue neue Fall-/Laufrevision.

## Vor Implementierung zu präzisierende Rechenfälle

1. **Vertragliche Aufteilung bei mehreren Monatsbeträgen:** Tatsächliche Kalendertage und belegte Solltage/-sekunden sind direkt ableitbar. Die bloße Kennzeichnung `contractual_30_days` legt die Entgeltverteilung an mehreren Grenzen eines 28-/31-Tage-Monats noch nicht eindeutig fest. Die ergänzende Vertragsmethode muss ausdrücklich festlegen, ob tatsächliche Teilabschnittstage oder eine feste 30-Tage-Zählweise gelten. SV-Tage dürfen diese Entgeltentscheidung nicht ersetzen.
2. **Midijob bei mehr als einer Entgeltposition:** Entgelte derselben rechtlichen Beitragsperiode vor der Übergangsformel zusammenführen. Eine fiktive Vollmonatsbasis je willkürlicher Gehaltszeile würde Entlastung und Rundung mehrfach anwenden. Tatsächlicher Statuswechsel benötigt dagegen die eigene Prognose und die rechtliche Teilperiodenregel.
3. **KV/PV- und Steuermerkmale:** Kassenwirksamkeit, Beitragsgruppengültigkeit und für den PAP maßgebliche Merkmale sind verschiedene Zeitachsen. Ein Versicherungswechsel darf weder ungeprüft die gesamte Monatssteuer mit einem Mischsatz berechnen noch automatisch tägliche Steuersegmente erzeugen.
4. **Aus-/Wiedereintritt und Fortbestand:** Tatsächliche Vertragsenden/-anfänge werden durch eigene Originale belegt. P4 liefert den SV-Fortbestand bei unbezahlter Unterbrechung. Eine bloße neue Personalstammzeile oder ein leerer Stundenzettel beweist kein Ende des Dienstverhältnisses.
5. **Historie:** Neue Fähigkeitsprüfung verwendet neue Regeln nur für den neuen Fall. Die alte gespeicherte Blockerliste bleibt Bestandteil ihrer damaligen Version. Dies wird vor neuer Integration als eigener Migrations-/Replay-Gegenfall geprüft.

Für jede fachliche Variante folgen unabhängig hergeleitete 28-/30-/31-Tage-Zahlen, Centgrenzen, eine vollständige tatsächliche Quellenkette, aktuelle und historische Korrektur, beide Clients und PostgreSQL/Restore. Neue Rechenfälle gelten erst nach diesen Prüfungen als implementiert.

## Erster isolierter Implementierungsstand

`backend/payroll_segments_2026.py` enthält reine Beschäftigungsintervalle, belegte Mehrvertragsentgelte und tatsächliche SV-Teilzeiträume. Die reinen Fälle prüfen Vertragsquotienten, Stundenlohn, Monatsarbeitspläne, tatsächliche 28-/30-/31-Tage-Splits, getrennte Teil-BBG, kosmetische Nicht-Split-Ereignisse und unveränderte alte v4-Blocker. Diese Komponenten sind inzwischen im ausdrücklich versionierten Gesamtfall integriert. Tatsächlicher Aus-/Wiedereintritt, P4-Anspruchsphasen, PAP, Beiträge, Reisebezüge, Nettoabzüge und Cash/EÜR sind zusätzliche echte Domainfälle. Eine bloße freie SV-Ereignisbezeichnung wird weiterhin nicht als Beleg einer neuen Teil-BBG akzeptiert.
