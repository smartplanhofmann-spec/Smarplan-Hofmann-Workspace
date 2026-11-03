# Krankheitsansprüche: nachvollziehbare Regelversionen 2026

Stand: 03.11.2026. Private Anspruchsfakten, keine Krankheitsdiagnosen.

## Korrektur der Frist beim arbeitsfreien AU-Anfang

`de_2026_sickness_v2` korrigiert den Stundenlohnfall, in dem die AU an einem
arbeitsfreien Tag beginnt und der erste ausgefallene Solltag später als am
Folgetag liegt. Die 42 Kalendertage beginnen am Folgetag. Der tatsächliche
erste ausgefallene Solltag bleibt unverändert als belegte Eingabe erhalten.
Beim Monatsentgelt zählt der arbeitsfreie Anfangstag mit. Bei Erkrankung im
Laufe der Arbeit beginnt die Frist am Folgetag; der verbleibende gewöhnliche
Lohn am begonnenen Arbeitstag wird getrennt ausgewiesen.

Belegtes Beispiel: AU ab Samstag, 01.08.2026, erster Solltag Montag, 03.08.
Stundenlohn: 02.08.–12.09.2026; Monatsentgelt: 01.08.–11.09.2026.
V1 verschob beim Stundenlohn die Frist unzutreffend bis zum ersten Solltag.

Quelle: [IKK classic, Entgeltfortzahlung, 35. Auflage, Stand 01.01.2026,
Druckseite 8](https://cdn.ikk-classic.de/exporter/5147-fachbroschuere-efzg.pdf),
vollständig geöffnet und einschließlich der veröffentlichten Beispieldaten
gelesen. BAG 03.03.1993 – 5 AZR 132/92 belegt keine solche Verschiebung bis
zum nächsten Solltag und wird dafür nicht verwendet.

## Historie und neue Entscheidungen

`payroll_entitlements_2026.py` bleibt unverändert. Der neue explizite Dispatcher
`payroll_entitlement_dispatch.py` berechnet gespeicherte Pläne ausschließlich
mit deren gespeicherter Regelversion. Er rät keine Ersatzversion. Neue
`sickness_history`-Vorschauen und Bestätigungen verwenden v2; die anderen drei
Anspruchsarten verwenden unverändert v1. Die Eingabe- und Ausgabefelder für
v2 bleiben identisch, `rule_version`, `rules_hash`, Ergebnis und Planhash
weisen die tatsächlich verwendete Regel aus.

Für den bekannten falschen v1-Grenzfall wird eine neue Anwendung gesperrt,
einschließlich einer `regular_absence`, die ihn mittelbar referenziert.
Lesen, Integritätsprüfung, Wiederherstellung und Wiederholung des bereits
angenommenen ursprünglichen Befehls bleiben möglich. Eine neue ausdrückliche
Korrektur erzeugt v2 als weitere Revision; ein Storno bewahrt den alten Plan.
Die Wiederholungsquittung wird vor einer Neuberechnung aufgelöst.

## Überlappende Ursachen: ausdrückliche Version v3

V2 berechnet nur getrennte, belegte Verhinderungsfälle. Überlappungen verwenden
`de_2026_sickness_phases_v3` mit disjunkten Phasen und belegter Fallzuordnung.
Weder ein neuer 42-Tage-Anspruch noch eine doppelte Zahlung entsteht allein
aus einer weiteren AU-Ursache. Auch ein kleinerer Restanspruch der anfänglichen
Ursache begrenzt den zusammenhängenden Fall; sein Hinzutritt verlängert ihn nicht.

Die gelesenen Quellen für diesen Zweig sind:

- [BAG 11.12.2019 – 5 AZR 505/18, insbesondere Rn. 13–21](https://www.bundesarbeitsgericht.de/entscheidung/5-azr-505-18/):
  Zusammenhängende Verhinderung bleibt auf sechs Wochen begrenzt. Eine neue
  eigenständige Verhinderung erfordert tatsächlich belegte zwischenzeitliche
  Arbeitsfähigkeit; freie Tage oder eine neue Erstbescheinigung genügen nicht.
- [TK, Entgeltfortzahlung im Krankheitsfall, Abschnitt 11 und Beispiele 17–19,
  Druckseiten 14–15](https://www.tk.de/resource/blob/2033356/251a73f03ded71105f354f276142289c/beratungsblatt-entgeltfortzahlung-bei-krankheit-data.pdf):
  Die hinzutretende wiederholte Ursache verbraucht während der weiterhin
  maßgebenden Erstursache ihren eigenen Restanspruch nicht. Nach Ende der
  Erstursache begrenzen Restanspruch und gemeinsame Sechswochenfrist die Zahlung.
- [AOK, Dauer der Entgeltfortzahlung, aktualisiert 29.06.2026](https://www.aok.de/fk/sozialversicherung/entgeltfortzahlung-und-ausgleichsverfahren/dauer-der-entgeltfortzahlung/):
  Beispiele zu hinzugetretenen Krankheiten und Vorerkrankungszeiten bestätigen
  diese Unterscheidung.

Die ergänzend gelesenen [GKV-Grundsätze vom 25.06.1998, Abschnitt 6,
Druckseiten 43–46](https://www.gkv-datenaustausch.de/media/dokumente/arbeitgeber/eel/gem_rs_kg/1998_06_25_GR_SpiKK_EFZG.pdf)
belegen die Anfangsrestgrenze, die maßgebende eigene Phase und ihre Fristen.
Die dortigen Beispiele a–d wurden unabhängig auf 2025/2026 übertragen.
Andere historische, inzwischen überholte Regelteile des Rundschreibens werden
nicht übernommen. Eine während der zuerst maßgebenden Ursache vollständig
beendete hinzutretende Ursache verbraucht keinen eigenen Anspruch. Wird sie
später allein maßgebend, beginnt ihr eigener Fristenbezug in dieser Phase;
ohne eigenen Zahlungsanspruch wird kein neuer Zwölfmonatsanker erzeugt.

Die neue Eingabe `prevention_cases` enthält je Fall `id`, `episode_ids` und
`evidence_refs`. Jede Episode gehört genau einem belegten Fall. Die Fallerste
behält die bisherigen Beginnangaben und `recovery_before: true`. Echte
Hinzutritte verwenden `onset: during_existing_au`, `recovery_before: false`
und `first_scheduled_day: null`. Originalursachen bleiben unverändert erhalten.
Der Plan ergänzt `prevention_cases` mit Anfangsrest und Fristende sowie
disjunkte `phases` mit aktiven Ursachen, maßgebender Ursache, Anspruch und
gegebenenfalls gewöhnlichem Restlohn des ersten Tages. Bei der Anwendung
werden diese Phasen genau einmal je Kalendertag ausgewertet.

Gleichzeitiger unklarer Ursachenbeginn, eine künstliche Trennung überlappender
Fälle und fehlende Genesungsbelege werden abgelehnt. Wird eine hinzugetretene
Ursache bereits während der Beschäftigungswartezeit allein maßgebend und
reicht über deren Ende hinaus, benötigt ihr Zwölfmonatsanker einen separaten
Beleg; dieser konkrete Fall bleibt gesperrt. Die Quellenprüfung hat ihn nicht
durch eine Annahme ersetzt.

## AU vor Beschäftigungsaufnahme: ausdrückliche Version v4

`de_2026_sickness_start_v4` ergänzt einen nach Vertragsabschluss eingetretenen
AU-Beginn vor dem vereinbarten Beschäftigungsbeginn. Grundlage ist das
IKK-Beispiel auf Druckseite 7: Vertrag 16.09., AU 25.09.–31.10., Beschäftigung
ab 01.10.; daraus folgen Wartezeit bis 28.10. und EFZ vom 29.–31.10.

Die Eingabe ergänzt v3 um `employment_commencement` mit tatsächlichem
`contract_concluded_on` und `evidence_refs`. Die ursprüngliche Episode hat
`onset: before_employment` und keinen erfundenen ersten Solltag. Eine eigene
rechtliche Projektion begrenzt den Arbeitgeberanspruch auf das tatsächlich
vereinbarte Beschäftigungsverhältnis. `legal_projection_hash` bindet diese
Projektion, während Eingabehash und Episode den ursprünglichen AU-Beginn
bewahren. `preemployment_periods` weist den vorgelagerten Zeitraum ohne
Entgeltanspruch aus diesem Beschäftigungsverhältnis aus. Die abrechenbaren
Phasen beginnen erst ab Beschäftigungsaufnahme.

Eigene Gegenfälle prüfen die volle Frist 29.10.–09.12. bei länger dauernder AU,
den Stundenlohn ohne fiktiven Solltag, den späteren Hinzutritt ohne neue Frist,
einen abweichenden Vertragsbeleg bei unverändertem Ergebnis sowie Ablehnung
eines nicht belegten zeitlichen Vertragszusammenhangs. Mehrere bereits vor
Beschäftigungsbeginn bestehende Ursachen benötigen eine eigene Anfangsentscheidung.

Stundenlohn-AU ausschließlich an freien Tagen ohne tatsächlich ausgefallenen
Solltag bleibt als ausdrücklich ausführbarer offener Negativfall erhalten.
Der konkrete Vorverbrauch ohne jeden Arbeitsausfall ist durch die gelesenen
Beispiele noch nicht entschieden. Ein Solltag oder Vorverbrauch wird nicht
erfunden. Tarifliche Sonderregeln sind weiterhin gesonderte Fälle.

## Prüfungen

Die ausführbaren Nachweise liegen in den `test_payroll_sickness*`- und
`test_business_payroll_sickness*`-Modulen sowie den HTTP-/PostgreSQL-
Anspruchstests. V2-Ergebnisprotokolle und SHA-256-Zuordnung stehen unter
`docs/evidence/payroll-sickness-v2-2026-11-03.json`; der vollständige Versionslauf
unter `docs/evidence/payroll-sickness-versions-2026-11-03.json`. Die unabhängige
v3-Gegenprüfung ist separat als `payroll-sickness-phases-independent-review`
archiviert. Die unabhängige v4-Gegenprüfung durch Root umfasst vier weitere grüne Fälle: Monatsende mit Februar-Wartefrist, Ende innerhalb der Wartezeit, spätere Wiedererkrankung mit 39 Resttagen und getrennte Bindung des Vertragsoriginals. Ihr Nachweis liegt unter `payroll-sickness-start-independent-review-2026-11-03.json`.
