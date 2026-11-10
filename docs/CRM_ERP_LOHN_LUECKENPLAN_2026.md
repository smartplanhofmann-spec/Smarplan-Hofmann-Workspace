# Lohn 2026 – verbleibende Standardfälle und konkreter Umsetzungsplan

## Aktueller Abgleich10.11.2026

Der folgende ältere Befund bleibt als Entwicklungshistorie erhalten. Er ist
keine aktuelle Liste sämtlicher noch fehlender Funktionen. Zusätzlich zu den
früheren Voll-/Teilmonats-, Midijob-, P4-, Source4-/Source5- und Reisebausteinen
sind diese begrenzten Faktorfolgen inzwischen implementiert und geprüft:

| Version | Tatsächlich geprüfter Umfang |
|---|---|
| V8 | [Regulärer voller Faktor-Monat](CRM_ERP_LOHN_FAKTOR_2026.md), originale LF-/CRLF-Historie erhalten |
| V9 | [Belegter Faktor-Teilmonat](CRM_ERP_LOHN_FAKTOR_TEILMONATE_2026.md), Quelle2 mit Korrektur und Geld-/Restorekette |
| V10 | [Faktor mit bezahlter steuerfreier Reise](CRM_ERP_FAKTOR_REISE_CLIENTS_2026.md), Erstattung nicht erneut im Netto |
| V11 | [Individuell versteuerter gewerblicher Minijob](CRM_ERP_MINIJOB_V11_CLIENTS_2026.md), enger dokumentierter Vollmonatsfall |
| V12 | [Faktor mit belegten P4-Ansprüchen](CRM_ERP_FAKTOR_ANSPRUECHE_V12_2026-11-10.md), Monats-/Stundenentgelt ohne erfundene Arbeitszeit |
| V13 | [Faktor, P4 und bereits bezahlte Reise](CRM_ERP_FAKTOR_ANSPRUECHE_BEZAHLTE_REISEN_V13_2026-11-10.md), vollständige Quellenbindung und belegte Ergänzung unbenutzter V10-/V12-Fälle |

V13 ist mit39 gemeinsamen Backendfällen plus CRLF-/CI-Verträgen, unabhängigen
Clientverträgen, wirklichen Browserabläufen und PostgreSQL-/MFA-/Parallelitäts-/
EÜR-/Jahres-/vollständigen Restoreketten geprüft. Der nachfolgende gemeinsame
Installationsstand c4a2d8f besteht1939 gesamte Appfälle und alle20 eigenen
Development-Gruppen sowie den unsignierten iPhone-Release. Die genauen Rohdaten
stehen im [V13-Archiv](evidence/factor-claims-paid-travel-2026-11-10/manifest.json)
und [Installationsarchiv](evidence/installation-context-2026-11-10/manifest.json).
Dies ist keine unabhängige Lohnfachprüfung oder Meldungsfreigabe.

Offen bleiben insbesondere Faktor-Midijobs und Faktor-Einmalbezüge, zusätzliche
Perioden-/Versicherungs-/Leistungsfälle, weitere Source5-Gruppen und Änderungen
der Brutto-/Steuer-/SV-Zuordnung sowie der neue Korrekturvertrag zur nachträglichen
V13-Erweiterung bereits verwendeter V10-/V12-Fälle. Die bisher vorhandene
Korrektur unter ihrer ursprünglichen Regelversion wird dadurch nicht entfernt.
Die bloße Ergänzung eines verwendeten Altfalles ist weiterhin ausdrücklich
gesperrt. Sonstige unten genannte noch nicht belegte Fälle bleiben offen.

Für [Source5-Gruppen](CRM_ERP_SOURCE5_MEHRFACH_GRUPPEN_RESTPLAN_2026.md)
fehlt weiterhin die verifizierte aktuelle Gruppierungsgrundlage. Die ergänzende
öffentliche Web-Recherche am10.11. findet amtliche2026-Verweise, erhält für die
vollständigen R39b.6-/§39b-/Inhaltsseiten aber jeweils503. Suchauszüge oder
ältere Jahresfassungen ersetzen diesen Nachweis nicht; es wird keine neue
Gruppenberechnung daraus freigeschaltet. Reale Fach-/Sicherheitsabnahme und
Meldezugänge werden getrennt von dieser verbleibenden Codearbeit geführt.

## Historische Fortschreibung09.11.2026

Der reguläre volle Monat mit ausdrücklich
belegtem Faktor in Steuerklasse IV ist als additive v8-Regel integriert.
Jetzt ist auch der [belegte reguläre Faktor-Teilmonat v9](CRM_ERP_LOHN_FAKTOR_TEILMONATE_2026.md)
mit Quelle2, beiden Clients, Original/Korrektur, tatsächlichem PG-Restore und
Zahlungs-/Bank-/EÜR-Kette geprüft. Ansprüche, Reisen, Midijobs und Einmalbezüge
mit Faktor sowie die übrigen unten benannten Lücken bleiben Codearbeit.
Der Vergleich mit tatsächlichen Windows-Paketquellen zeigt zusätzlich alte
plattformabhängige Lohn-Quellmetadaten. Neue v9-Metadaten sind portabel geprüft;
der [v8-Faktor-Vollmonat](CRM_ERP_LOHN_PLATTFORMHISTORIE_2026.md) wird jetzt
mit exakt hergeleiteten Metadatenpaaren ohne Originaländerung wiederverwendet.
Der [v2/v3-Reiseabgleich](CRM_ERP_REISEN_PLATTFORMHISTORIE_2026.md) ist
inzwischen ebenfalls geprüft. Rohe Dateihash-Nachweise bei Einmalbezügen bleiben
zu prüfen. Historische Rechenkerne und Originalhashes bleiben erhalten.

Bestandsaufnahme und Quellenprüfung: 03.11.2026. Maßstab bleibt die gewünschte erste Version für **reguläre Mitarbeiter und gewerbliche Minijobs**, nicht nur der bisher berechenbare Vollmonat. Diese Analyse ändert keine Rechenlogik und erklärt keine fachliche oder amtliche Zulassung.

## Fortschreibung nach P1, P2 und P3a

Midijob-Vollmonate sind als eigene neue Regelversion geprüft:
[Kernel-/PG-Abnahme](CRM_ERP_LOHN_MIDIJOB_2026.md) und
[Clients](CRM_ERP_LOHN_MIDIJOB_CLIENTS.md). P2-Lohnfakten sind inzwischen
[implementiert und geprüft](CRM_ERP_LOHN_FAKTEN_2026.md). P3a ergänzt belegte
Teilmonate für eine Beschäftigungsepisode, eine Entgeltvereinbarung und ein
SV-Profil: [Backend-/PG-Nachweis](CRM_ERP_LOHN_TEILMONATE_2026.md),
[unabhängige Gegenprüfung](CRM_ERP_LOHN_TEILMONATE_GEGENPRUEFUNG_2026.md) und
[beide Clients](CRM_ERP_LOHN_ZEITACHSEN_CLIENTS.md). R39b.5 wurde vollständig
beschafft; die frühere Beschaffungslücke im historischen Abschnitt unten ist
für P3a geschlossen. Die alten Vollmonatsregeln und v4 einschließlich ihrer
historischen Sperrgründe bleiben unter ihren gespeicherten Versionen erhalten.

Der begrenzte eigene Mitarbeiterbeleg für v1–v4 ist inzwischen geprüft.
P4 besitzt geprüfte private Anspruchsfakten; die neue Stundenlohn-Regel v2
behandelt zusätzlich den fachlich nachgewiesenen AU-Beginn am freien Tag.
Die v5-Zusammenrechnung mehrerer belegter Beschäftigungs-/Entgelt-/SV-
Abschnitte mit P4 und Reisen ist inzwischen einschließlich beider Clients,
Mitarbeiterbeleg, PostgreSQL und Wiederherstellung geprüft. Jahresquellen für
Einmalbezüge sind als private API und Browser-/App-Erfassung vorhanden.
Die reine v6-Zusammenrechnung besitzt vier unabhängige Grenzfälle zusätzlich
zu neun Entwicklungstests. Aktiv entsteht die vollständige Source4-Kette
mit Anspruchsbindung, Abrechnung und tatsächlich belegtem Zufluss.
Das U-Merkmal und der Nachweis ohne Nettozahlung wurden separat ergänzt;
ihre begrenzten Verträge ersetzen nicht die noch fehlenden Leistungsbeträge,
Jahresüberträge und weiteren benannten Lohnfälle. Die folgende Bestandsaufnahme bewahrt den Ausgangspunkt vor P1
und darf nicht als aktueller Vollständigkeitsnachweis gelesen werden.

## Codebefund vor P1

| Fall | Tatsächlicher heutiger Code | Fehlende Funktion |
|---|---|---|
| Eintritt/Austritt innerhalb des Monats | `business_payroll._calculate_source` und `payroll_de_2026._calculate_contributions` erzeugen `full_month_required`; Monatsfreibetrag und monatliche BBG bleiben alleinige Rechenbasis | Belegte Entgeltaufteilung, getrennte Steuer-/SV-Zeiträume, Teil-BBG, Tages-PAP, vollständige Teilmonatsunterlagen |
| Übergangsbereich/Midijob | Vollmonate inzwischen abgeschlossen: explizite belegte Prognose, Regelversion `de_2026_transition_monthly_pap_v3`, getrennte Basen, AN-/AG-Beiträge und vollständiges Netto; [Fach-/PG-Nachweis](CRM_ERP_LOHN_MIDIJOB_2026.md), [Clients](CRM_ERP_LOHN_MIDIJOB_CLIENTS.md). Historischer Ausgangspunkt war `transition_not_supported`. | Teilmonate und weitere nachfolgend benannte Fälle bleiben P3/P4/P5; Vollmonatszweig ist kein offener Codepunkt mehr |
| Einmalzahlungen | `special_cases:one_off_payment` blockiert; die Quelle erwartet eine einzige laufende Monats-/Stundenvereinbarung | Eigenständige Entgeltart, steuerlicher Jahresbezug, SV-Luft, Märzklausel, Vorjahresquellen und Rückrechnung |
| Krankheit/Abwesenheit | Abwesenheiten sind vorhanden; nur Urlaub bei Monatsentgelt bleibt im Standardlauf zulässig. Krankheit, sonstige Abwesenheit und Urlaub bei Stundenlohn erzeugen `absence_requires_review` | Bezahlte Ausfallstunden, Entgeltfortzahlungsanspruch und Fortsetzungsfälle, unbezahlte Unterbrechung, korrekte Steuer-/SV-Tage, Nullentgeltmonate |
| Feiertage/Stundenlohn | Quellenbrutto ist Stundenentgelt × freigegebene tatsächliche Nettoarbeitszeit | Gesetzlich bezahlte Ausfallzeit ist keine geleistete Projektarbeitszeit und muss separat belegt/berechnet werden |
| Reisepauschalen | `business_personnel_workflow` erfasst belegte Auslagen und tatsächliche Erstattung; `travel_expenses_included_in_net` bleibt false | Reisezeit-/Ortsdaten, gesetzliche Pauschalen, Mahlzeiten, Tätigkeitsstättenhistorie und steuerliche Klassifizierung |
| Minijob im Jahresverlauf | Monat >603 EUR oder Regeljahresentgelt >7.236 EUR wird pauschal blockiert; RV-Befreiung ist ein Profil-Bool | Prognose einschließlich sicherer Sonderzahlungen, begründetes zulässiges Überschreiten und RV-Befreiungs-/Aufhebungslaufzeit |

Vorhandene unveränderliche Profile, Monatsvorbereitungen, Korrekturrevisionen, Lohnkontoidentität, tatsächliche Zahlungstage, Vorträge, Jahresausgabe und PayrollCash sind wiederverwendbare Grundlagen. Die vorhandene Jahresübersicht ersetzt **keine** SV-Vortragsrechnung: ihr Vortragsvertrag setzt erneut unterstützte Vollmonatsrechnungen voraus und besitzt keine unabhängigen SV-Tage oder verbrauchten Jahres-BBG je Versicherungszweig. Ebenso bilden `approved_absences` und `target_seconds` noch keine dokumentierte lohnrechtliche Anspruchsentscheidung ab.

## Priorisierte Umsetzung

Die Reihenfolge ist eine technische Umsetzungsempfehlung. Jeder Eintrag bleibt bis zu seiner eigenen Abnahme offen; ein früher fertiggestelltes Paket verkleinert den vereinbarten Gesamtumfang nicht.

| Priorität | Konkretes Paket | Ergebnis und Abhängigkeiten |
|---|---|---|
| 1, abgeschlossen | Midijob für belegte reguläre Vollmonate | Eigenständiger neuer Regelzweig mit vollständigem AN-/AG-/Steuer-/Nettoergebnis; alte Versionen unverändert. [Abnahme: 67 Fachtests, 3 neue + 9 historische PG-Fälle](CRM_ERP_LOHN_MIDIJOB_2026.md), [beide Clients und Browser](CRM_ERP_LOHN_MIDIJOB_CLIENTS.md). |
| 2, abgeschlossen | Belegte Lohnfälle und getrennte Zeitachsen | Versionierte Entscheidungen für Entgeltart, Beschäftigungs-/SV-Zeiträume, Lohnzahlungszeitraum, Anspruch und Vorträge. Grundlage der folgenden Pakete. |
| 3a abgeschlossen; 3b aktiv | Eintritt/Austritt, Tarif-/Profilwechsel und Teilmonate | Tages-PAP, Teil-BBG, Vertragsaufteilung, Minijob-Mindestbeitrag, Midijob-Teilmonat. Historische Vollmonatsläufe bleiben unter ihrer alten Regelversion reproduzierbar. |
| 4 | Bezahlte/unbezahlte Abwesenheit | Krankheit/Entgeltfortzahlung, Feiertage, Urlaub bei Stundenlohn und Unterbrechungen mit monatsübergreifender Anspruchshistorie. Kein automatisches Hochsetzen tatsächlich gearbeiteter Projektstunden. |
| 5 | Einmalbezug einschließlich Märzklausel | Steuer-/SV-Jahresvorträge, getrennte laufende und einmalige Anteile, Vorjahreszuordnung sowie Folgekorrekturen. Baut auf Zeitachsen und Jahresvorträgen auf. |
| 6, parallel unabhängig möglich | Reisepauschalen Inland und Ausland 2026 | Separater Reiseberechner mit belegter Steuerentscheidung, eigener unveränderlicher Abrechnung und einmaliger Übergabe zur bestehenden Erstattung/Geldflusskette. |
| Querschnitt | Minijobstatus und RV-Lebenslauf 2026 | Prognose, Überschreitungsjahr, echte Befreiungs-/Aufhebungsbelege und wirksame Daten; Änderungen dürfen den früheren Status nicht bloß überschreiben. |

## 1. Midijob: Regeln und Referenzen

Amtlicher 2026-Parameterstand: `G=603.00`, `U=2000.00`, `F=0.6619`. Für ein innerhalb der Zone liegendes tatsächliches Entgelt `AE` gelten getrennt:

```text
BE_gesamt = F*G + (U/(U-G) - G/(U-G)*F)*(AE-G)
BE_AN     = U/(U-G)*(AE-G)
```

Die prognostisch regelmäßige Beschäftigung entscheidet über die Anwendung; ein einzelner niedriger Monat darf nicht automatisch zum Minijob werden. Bei Unterschreiten trotz Midijobstatus ist der Gesamtansatz `F*AE`; bei Überschreiten von 2.000 EUR gelten für diesen Monat die allgemeinen Beitragsregeln. Die DRV veröffentlicht folgende unabhängigen 2026-Prüfwerte. [Quelle: DRV-Lexikon Übergangsbereich](https://www.deutsche-rentenversicherung.de/DRV/DE/Experten/Arbeitgeber-und-Steuerberater/summa-summarum/Lexikon/U/uebergangsbereich).

| AE EUR | BE gesamt EUR | BE AN EUR |
|---:|---:|---:|
| 603,01 | 399,14 | 0,01 |
| 700,00 | 510,28 | 138,87 |
| 800,00 | 624,88 | 282,03 |
| 1.000,00 | 854,06 | 568,36 |
| 1.200,00 | 1.083,25 | 854,69 |
| 1.400,00 | 1.312,44 | 1.141,02 |
| 1.600,00 | 1.541,63 | 1.427,34 |
| 1.800,00 | 1.770,81 | 1.713,67 |
| 2.000,00 | 2.000,00 | 2.000,00 |

Je Versicherungszweig ist zuerst der halbe Beitrag aus `BE_gesamt` centgenau zu runden und anschließend zu verdoppeln. Der AN-Anteil wird aus `BE_AN` berechnet; der AG-Anteil ergibt sich als verbleibender Betrag. KV-Grund- und Zusatzbeitrag benötigen ihre vorgeschriebene getrennte Behandlung. PV-Kinderlosenzuschlag 0,6 % verwendet `BE_gesamt`, der Kinderabschlag hingegen `BE_AN`. Sachsen verlangt den eigenen Anteil nach §58 SGB XI; die pauschale Anwendung der normalen Vollmonatssätze auf beide Bemessungsgrundlagen wäre falsch. Quellen: [BVV §2](https://www.gesetze-im-internet.de/beitrvv/__2.html), [aktuelle DRV-Berechnung](https://www.deutsche-rentenversicherung.de/DRV/DE/Experten/Arbeitgeber-und-Steuerberater/Gleitzone-Uebergangsbereich/uebergangsbereich_gleitzone.html), [GKV-Hinweise vom 31.03.2025, Abschnitt 4, Seite 12](https://www.gkv-spitzenverband.de/media/dokumente/pflegeversicherung/grundprinzipien/2025-03-31_GH_Beitragssatzdifferenzierung_sPV.pdf).

Tests: alle neun veröffentlichten Bemessungspaare; Centgrenzen 603,00/603,01 und 2.000,00/2.000,01; schwankendes Entgelt unterhalb der Grenze ohne Statuswechsel; getrennte KV-Rundungen, Sachsen, Kinderlosigkeit und zwei bis fünf berücksichtigte Kinder; kassenindividuelle Umlagen; Lohnsteuerklasse VI; Vergleich der alten Regelversion und Historie. Keine Ableitung der Erwartungen durch Aufruf derselben zu testenden Formel.

## 2–3. Zeitachsen, Eintritt/Austritt und Teilmonate

Benötigte Eingaben sind getrennte belegte Beschäftigungsdaten, tatsächlicher Lohnzahlungszeitraum, beitragspflichtige SV-Zeiträume, gültige Beitrags-/ELStAM-Fassungen und arbeits-/tarifvertragliche Teilentgeltberechnung. Die Monatslohnaufteilung darf nicht standardmäßig mit 30 Tagen angenommen werden: tatsächliche Arbeitstage, Kalendertage oder eine ausdrücklich vereinbarte Berechnung sind unterschiedliche Vertragsgrundlagen.

SV: voller Monat 30 Tage, Teilmonat tatsächliche beitragspflichtige Kalendertage. Die Jahres-BBG 2026 beträgt 69.750 EUR KV/PV beziehungsweise 101.400 EUR RV/AV; die Teil-BBG ist aus Jahreswert × SV-Tage /360 zu bestimmen und anschließend zu runden. Bereits gerundete Tageswerte dürfen nicht mit der Tageszahl multipliziert werden. Amtliche Beispielgrenzen für 17.–28.02.2026: 2.325,00/3.380,00 EUR; für 01.–16.03.2026: 3.100,00/4.506,67 EUR. [DRV, Beiträge 2026, Abschnitte 1.3–1.4 und Seiten 12–14](https://www.deutsche-rentenversicherung.de/SharedDocs/Downloads/DE/Fachliteratur_Kommentare_Gesetzestexte/summa_summarum/e_paper_und_broschueren/broschueren/beitraege.pdf?__blob=publicationFile&v=10), [SGB V §223 Abs.1–3](https://www.gesetze-im-internet.de/sgb_5/__223.html). Die aktuelle konsolidierte Norm enthält bereits eine gesonderte Regel für 2027; deren Jahreswerte gehören nicht in die 2026-Rechnung.

Steuer: PAP `LZZ=3` ist Woche, `LZZ=4` Tag; Jahreshochrechnung 360/7 beziehungsweise 360, Rückverteilung entsprechend mit PAP-Abrundung. Tagessteuer ist keine anteilige Monatssteuer. Dienstverhältnisbeginn/-ende und bloß unbezahlte Arbeitstage sind getrennt zu behandeln. Quelle: [EStG §39b Abs.2](https://www.gesetze-im-internet.de/estg/__39b.html), [LStH 2026 R39b.5](https://ao.bundesfinanzministerium.de/lsth/2026/A-Einkommensteuergesetz/VI-Steuererhebung-36-47/2-Steuerabzug-vom-Arbeitslohn-Lohnsteuer-38-42g/Paragraf-39b/r-39b-5.html), [amtlicher PAP 2026, bereitgestellte Anlage bei IHK München, Seiten 5, 15 und 32](https://www.ihk-muenchen.de/ihk/documents/Recht-Steuern/Steuerrecht/Einkommensteuer/2025-11-12-PAP-2026-anlage-1.pdf). Der vollständige Richtlinientext R39b.5 war bei dieser Abfrage nicht abrufbar (503); vor Freigabe des täglichen Wrappers sind die vollständige Richtlinie und unabhängige Tagesvergleichsfälle noch zu hinterlegen. Der PAP selbst wurde an den genannten Stellen gelesen.

Midijob-Teilmonat: erst das Teilentgelt auf den Vollmonat beziehen, daraus beide Bemessungsgrundlagen bestimmen und wieder auf die belegten SV-Tage reduzieren; ausdrücklich abweichende arbeitsvertragliche Entgeltaufteilung berücksichtigen. Kein Hochrechnen bei bloß unbezahlter Unterbrechung ohne gekürzte SV-Tage. [Gemeinsames Rundschreiben 20.12.2022, Abschnitte 4.3.2.5/4.3.3.5](https://www.kbs.de/SharedDocs/Downloads/DE/VersicherungsrechtBeitraegeMeldungen/Downloads/Uebergangsbereich_idF_20_12_2022.pdf?__blob=publicationFile&v=2). Seine damaligen Entgeltgrenzen, F- und PV-Werte dürfen nicht als 2026-Parameter übernommen werden.

Minijob: anteilige RV-Mindestbasis `175 EUR × SV-Tage /30`; ein unbezahlter Urlaub bis zu einem Monat verkürzt sie nicht automatisch. In einem Monat ohne tatsächliches Entgelt fällt kein Mindestbeitrag an. Tests umfassen die veröffentlichten Beispiele 29/30 und eigene gewerbliche Varianten, Januar/Februar/31-Tage-Monat, einen Beschäftigungstag, getrennte Ein-/Austrittsdaten, hohe Teilentgelte an Teil-BBG sowie rückwirkende Datenkorrektur. [Geringfügigkeits-Richtlinien 2026, C3.2.1 und Beispiele 29/30](https://www.minijob-zentrale.de/SharedDocs/Downloads/DE/Rundschreiben/Geringfuegigkeitsrichtlinien-2026.pdf?__blob=publicationFile).

## 4. Krankheit, Urlaub, Feiertage und unbezahlte Zeiten

Erforderlich ist eine geschützte Anspruchsentscheidung zusätzlich zum genehmigten Abwesenheitskalender: Art, Zeitraum, bezahlte Sollstunden, Vertrags-/Arbeitsplanquelle, Anspruchsbeginn/-ende, berücksichtigte Vorzeiten und Originalnachweis. Eine Krankheitsdiagnose gehört nicht in Projekt- oder Finanzansichten. Für Wiederholungsfälle genügt eine geschützte Fallreferenz mit fachlich bestätigter Zuordnung; keine Diagnoseableitung durch die Anwendung.

Entgeltfortzahlung setzt grundsätzlich vier Wochen ununterbrochenes Arbeitsverhältnis voraus und reicht bis sechs Wochen. Bei derselben Krankheit sind die Sechsmonats-/Zwölfmonatsbedingungen zu prüfen; die Berechnungsgrundlage ist das regelmäßige Arbeitsentgelt, nicht beliebig die letzten erfassten Projektstunden. Feiertagsentgelt betrifft ausgefallene reguläre Arbeitszeit. Quellen: [EntgFG §§2–4](https://www.gesetze-im-internet.de/entgfg/BJNR106500994.html). Urlaub bei Stundenlohn benötigt eine eigenständige Durchschnittsgrundlage gemäß [BUrlG §11](https://www.gesetze-im-internet.de/burlg/__11.html); vollständige unabhängige Referenzfälle hierzu sind noch zu ergänzen.

Ein unbezahlter Ausfall beendet die SV-Beschäftigung nicht sofort; §7 Abs.3 SGB IV nennt grundsätzlich bis zu einen Monat Fortbestand. Krankengeldbezug und andere beitragsfreie Unterbrechungen sind getrennte Fälle. Die Monats-BBG darf nicht wegen jeder unbezahlt gemeldeten Stunde verkürzt werden. Quellen: [SGB IV §7](https://www.gesetze-im-internet.de/sgb_4/__7.html), DRV-Beiträge 2026, Abschnitte 1.4.3–1.4.4.

Tests: Tag 28/29 nach Eintritt, Tag 42/43 derselben Krankheit, Jahreswechsel, vorheriger verbundener Krankheitsfall, Urlaub und Feiertag bei Stundenlohn, Krankheit über Monatsende, unbezahlter Urlaub innerhalb/über einen Monat, Restentgelt und echter Nullentgeltmonat. Jede Ausfallstunde darf höchstens einmal als Arbeits-/Urlaubs-/Krankheits-/Feiertagsentgelt zählen. Krankengeld wird nicht als Arbeitgebernetto erfunden; eAU/AAG-Meldung und tatsächliche Erstattung bleiben eigene Ereignisse.

## 5. Einmalzahlungen und Märzklausel

Neue Entgeltpositionen benötigen Art, Zahlungs-/Zuordnungsdatum, Betrag, Original, Zusage-/Prognosestatus und explizite laufend/sonstig/SV-einmalig-Einordnung. Die steuerliche und die SV-Einordnung dürfen nicht über einen einzigen Bool gekoppelt werden.

Steuerlich fehlen die PAP-Zweige für sonstige Bezüge mit belegtem `JRE4`, `SONSTB`, jährlichen Frei-/Hinzurechnungsbeträgen und den relevanten Vorbezügen; Ausgaben sind getrennt `STS`, `SOLZS`, `BKS`. Einmalbezug darf nicht zum Monatsgehalt addiert und einfach mit zwölf hochgerechnet werden. Quelle: [PAP 2026, Seiten 4–7 und 33–37](https://www.ihk-muenchen.de/ihk/documents/Recht-Steuern/Steuerrecht/Einkommensteuer/2025-11-12-PAP-2026-anlage-1.pdf), [EStG §39b Abs.3](https://www.gesetze-im-internet.de/estg/__39b.html).

SV: je Versicherungszweig belegte anteilige Jahres-BBG abzüglich bereits verbrauchter beitragspflichtiger Entgelte; beitragsfreie Zeiten aus der Jahresgrenze herausnehmen. Bei Zahlung Januar–März ist die Vorjahreszuordnung nach §23a zu prüfen; für KV-Pflichtversicherte entscheidet dafür die KV-Grenze. Bei Vorjahreszuordnung werden **Vorjahresregeln und echte Vorträge** benötigt. Ein ausschließliches 2026-Regelwerk genügt dafür nicht. U1/U2-Einmalentgeltbehandlung und Insolvenzgeldumlage bleiben getrennt. Quellen: [SGB IV §23a](https://www.gesetze-im-internet.de/sgb_4/__23a.html), [AAG §7](https://www.gesetze-im-internet.de/aufag/__7.html).

Tests: Bonus mit und ohne verbleibende SV-Luft, KV-BBG erreicht/RV-BBG offen, mehrere Einmalzahlungen, März/April-Grenze, Vorjahr ohne Beschäftigung, Zahlung nach Austritt, beitragsfreie Monate, Vorjahresbeitragssatzwechsel, fehlender Vortrag statt angenommener null, neue Rückrechnung mit unverändertem alten Lohnkonto/Bank-/EÜR-Nachweis. Ein numerisch abgenommener 2025-SV-Parameterbestand und unabhängige BMF-Sonderbezugsfälle sind vor Abschluss dieses Pakets zusätzlich erforderlich.

## 6. Reisepauschalen

Erforderliche Daten: Reisebeginn/-ende mit Zeitzone, Wohnung/erste Tätigkeitsstätte oder belegtes Fehlen einer solchen, tatsächliche Tätigkeitsorte je Tag, Länder-/Städtewechsel, Übernachtung, gestellte Mahlzeiten/Eigenanteile, Unterbrechungen derselben Tätigkeitsstätte, bereits erstattete Pauschalen. Die bestehende Reise mit Datumsbereich und Belegbeträgen enthält diese Entscheidungsgrundlagen noch nicht.

Inland: 28 EUR für 24 Stunden, 14 EUR für An-/Abreisetage bei zugehöriger Auswärtsübernachtung sowie für eintägige Abwesenheit **über** acht Stunden. Mahlzeitenkürzung anhand des vollen Tageswerts: Frühstück 20 %, Mittag/Abend je 40 %, begrenzt auf den Tagesanspruch; Eigenanteile mindern die Kürzung. Dreimonatsbegrenzung bei derselben Tätigkeitsstätte, Neubeginn nach mindestens vier Wochen Unterbrechung. [EStG §9 Abs.4/4a](https://www.gesetze-im-internet.de/estg/__9.html).

Ausland: vollständige versionierte Länder-/Städtetabelle und die Orts-/Anreise-/Abreiseregeln aus [BMF-Schreiben 05.12.2025, gültig 01.01.2026](https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Lohnsteuer/2025-12-05-steuerliche-behandlung-reisekosten-2026.pdf?__blob=publicationFile&v=5). Gelesene Kontrollwerte: Belgien 59/40/141 EUR, Schweiz Bern 82/55/195 EUR (voller Tag/An-Abreisetag/Übernachtungspauschale). Die gesamte Tabelle muss vor Freigabe separat vollständig übertragen und geprüft werden. Übernachtungspauschalen sind nicht ohne Weiteres als EÜR-Eigenbeleg des Unternehmers verwendbar; Arbeitnehmererstattung und Betriebsausgabenprüfung bleiben verschiedene Entscheidungen.

Tests: 8:00 gegenüber 8:01 Stunden; 24-Stunden-Tag; Reise über Mitternacht ohne Übernachtung; Anreise mit Frühstück (14−5,60=8,40 EUR); Volltag mit drei gestellten Mahlzeiten (0 EUR); Eigenanteil; Dreimonatsgrenze und 27/28-Tage-Unterbrechung; Länderwechsel/Ortszeit; Stadt- gegenüber Landesresttabelle; keine doppelte Beleg-/Pauschal-/Gehaltsnettoerstattung. Steuerfreie und gegebenenfalls steuerpflichtige Erstattung werden getrennt ausgewiesen; die bestehende Auszahlungskette erzeugt den tatsächlichen Geldfluss genau einmal.

### Weitere Reisesteueroption: gestellte Mahlzeiten nach §40 Abs.2 Nr.1a

Der aktuelle Reise-Pauschalsteuerbaustein behandelt §40 Abs.2 Satz1 Nr.4 EStG
(zusätzliche Verpflegungszuschüsse). Die davon verschiedene Arbeitgeberwahl
nach Nr.1a für übliche gestellte Mahlzeiten, etwa ohne Anspruch auf
Verpflegungspauschalen oder nach Ablauf der Dreimonatsfrist, ist noch kein
eigener implementierter Policyfall. Solche Mahlzeiten werden aktuell als
Sachbezug im individuellen Lohnweg erfasst. Die zusätzliche Wahlmöglichkeit
darf deshalb nicht als bereits vollständig verfügbar ausgewiesen werden.
Erforderlich bleiben ein eigener Tatbestand mit belegten Voraussetzungen,
Arbeitgeberwahl und Kostenübernahme sowie unabhängige Steuer-/SV-Grenzfälle.
Quelle: [BMF 25.11.2020, Rz.94–99](https://www.ihk.de/blueprint/servlet/resource/blob/5260010/6167648501baf85de6053f701b93e9b5/bmf-schreiben-25-11-2020-data.pdf).

## Zusätzliche 2026-Minijoblücken

Die 2026-Richtlinien erlauben unter genauen Bedingungen unvorhersehbares Überschreiten bis zum Doppelten der Monatsgrenze in höchstens zwei Monaten eines rollierenden Zeitjahres. 2026 sind dies 1.206 EUR; die gewöhnliche Jahresentgeltprognose bleibt 7.236 EUR. Code benötigt die begründete Prognose und belegte Überschreitungshistorie statt einer pauschalen Monatsobergrenze.

Ab 01.07.2026 kann eine RV-Befreiung einmalig für die Zukunft aufgehoben werden, grundsätzlich ab dem auf Antragseingang folgenden Monat; eine spätere erneute Befreiung derselben fortbestehenden Beschäftigung ist nicht beliebig zulässig. Der heutige Profil-Bool prüft diesen Lebenslauf nicht. Quelle für beide Fälle: [Geringfügigkeits-Richtlinien 2026, B2.2.4.7/B3.1.3](https://www.minijob-zentrale.de/SharedDocs/Downloads/DE/Rundschreiben/Geringfuegigkeitsrichtlinien-2026.pdf?__blob=publicationFile). Erforderliche Tests: zweite/dritte Überschreitung im rollierenden Jahr, 1.206,00/1.206,01 EUR, vorhersehbarer Bonus, Antrag im Juni/Juli, Wirkung zum Folgemonat und unzulässiger erneuter Befreiungswechsel.

Individuell versteuerter Minijob, Mehrfachbeschäftigung, freiwillige/private KV, Arbeitnehmer ab 65, weitere Faktor-Teilmonats-/Einmalbezugsfälle, Sachbezüge/bAV und Unfallversicherung bleiben weitere **Code- und Prüffälle** innerhalb eines vollständigen Lohnprodukts. Der abgegrenzte reguläre Faktor-Vollmonat ist seit 08.11. und der belegte reguläre Faktor-Teilmonat seit 09.11. additiv integriert. Die Bezeichnung „regulärer Mitarbeiter“ schließt die übrigen Fälle nicht fachlich aus. Ihre heutige Sperre ist sichtbar und schützt vor falschen Berechnungen, ersetzt aber ihre Umsetzung nicht.

## Additiver technischer Vertrag für die Umsetzung

Vorgeschlagen sind eigenständige, deterministische Berechner `payroll_transition_2026`, `payroll_periods_2026`, `payroll_oneoff_2026` und `payroll_travel_2026` mit festgeschriebenen Quellen-/Regelhashes. Das bestehende `payroll_pap_2026.calculate_standard_tax` und die bisherigen Regelversionen bleiben als historische Leser unverändert. Neue Tages-/Sonderbezugszweige bekommen eigene Version und zusätzliche unabhängig belegte Erwartungen.

Eine separate private Fachhistorie `business_payroll_facts` soll explizite Anspruchs-/Entgelt-/Vortragsentscheidungen mit Mitarbeiter, Gültigkeitszeitraum, Referenz auf geschützte Originale, Vorgänger, Autor und Änderungsgrund speichern. Vorschau/Bestätigung bindet exakt die verwendeten Fassungen; keine automatische Anwendung unbestätigter Kalender- oder Profiländerungen. Ob neue Tabellen oder eine gezielte zusätzliche Ereignisart verwendet werden, ist vor Registrierung mit dem Integrationsverantwortlichen festzulegen.

Neue Ergebnisse trennen mindestens tatsächliches Brutto, Steuerbrutto, SV-Bemessungsgrundlagen je Zweig, Steuer-/SV-Tage, laufende/sonstige Steuer, AN-/AG-Beiträge, Umlagen, beitrags-/steuerfreie Erstattungen und Auszahlung. Lohnkonto, Jahresvorträge, Privatbelege, PayrollCash, EÜR und Bankbezüge müssen dieselben neuen Quellfassungen nachvollziehen. Vergangene Auszahlungen werden durch eine neue Berechnung nicht umgeschrieben. Nachgezahlt oder zurückgezahlt wird erst über den vorhandenen belegten Zahlungsvorgang.

Pro Paket folgen echte Domainfälle, native/Browser-Flows, MFA/HTTP, Rechteentzug und verlorene Antwort, PostgreSQL-Parallelität, unveränderte historische Exporte und Dump/Restore. Vergleichsergebnisse werden zusammen mit amtlicher Fundstelle und Wirksamkeitsdatum im Repository hinterlegt.

## Was extern bleibt – und was nicht

Die hier beschriebenen Berechner, Eingabe-/Historienmodelle, Fehlerfälle, Exporte und Quellbindungen sind Entwicklungsarbeit und benötigen keine externe Zulassung, um korrekt implementiert und synthetisch getestet zu werden. Echte Stammdaten/Vorträge werden später ausdrücklich in der geschützten Anwendung erfasst; ihre Abwesenheit ist kein Grund, ihre Erfassungslogik offen zu lassen.

Die tatsächliche fachliche Produktivabnahme, gegebenenfalls erforderliche Systemuntersuchung, ELSTER-/GKV-Zugänge und reale Übermittlung mit Annahme-/Ablehnungsnachweis sind zusätzliche externe Schritte. Auch deren Transport-/Status-/Fehlerlogik ist zunächst Codearbeit. Ein vorhandener CSV/PDF-Export oder eine geprüfte Rechenformel ist keine amtliche Meldung. Für diese Analyse wurden ausschließlich öffentliche Quellen gelesen; keine Personaldaten wurden übermittelt und keine Anträge oder Meldungen versandt.
