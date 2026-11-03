# Belegte Lohnfakten und getrennte Perioden 2026

Stand: 03.11.2026. P2 ergänzt die private Faktenhistorie für Beschäftigung,
vereinbarte Teilentgeltberechnung, vollständige Arbeitspläne und konkrete
Abrechnungsmonate. Das Backend ist mit echten Fachquellen, HTTP, PostgreSQL,
Parallelität und Wiederherstellung geprüft. Der
[API-Vertrag](CRM_ERP_LOHN_ZEITACHSEN_API.md) beschreibt den genauen Datenumfang;
[Quellen und Referenzen](CRM_ERP_LOHN_ZEITACHSEN_TEILMONATE_ENTWURF.md) begründen
die getrennten Zeitachsen. Die neue P3-Rechenintegration und die Clientabnahme
haben zusätzliche eigene Nachweise; P2 allein ist keine vollständige
Lohnproduktfreigabe.

## Was sich tatsächlich erfassen lässt

Ein Beschäftigungsfakt bindet den vorhandenen Personalstamm, konkrete
Entgeltvereinbarungen, private Originale und die tatsächlich vereinbarte
Teilmonatsmethode. Kalendertage, vertragliche Dreißigstel, Sollarbeitstage und
Sollsekunden sind ausdrücklich verschiedene Methoden. Es wird kein üblicher
Quotient ungefragt vorausgesetzt.

Ein Arbeitsplan enthält jeden Kalendertag des Monats, auch Tage ohne geplante
Arbeitszeit. Sollsekunden, Arbeitsort und Bundesland werden belegt erfasst.
Diese Planung erzeugt keine geleisteten Projektstunden und bestätigt für sich
noch keinen Urlaubs-, Feiertags- oder Entgeltfortzahlungsanspruch.

Ein Monatsfall bindet die abgeschlossene aktuelle HR-Monatsvorbereitung,
Beschäftigungs-/Arbeitsplanfakten, konkrete Lohnprofil- und Identitätsfassungen
sowie eigene belegte Anspruchsentscheidungen. Der reine Periodenkern leitet
Beschäftigungs-, Entgelt-, Steuer- und SV-Zeiträume aus diesen Quellen ab.
Steuer-/SV-Tage, Brutto und Bemessungsgrundlagen sind keine freien Ergebnisfelder.
Die tatsächliche Zahlung bleibt der separate bestehende Zahlungsnachweis.

Die Vorschau speichert nichts. Ein fachlich noch nicht berechenbarer, aber
korrekt belegter Anspruch kann als bestätigter Monatsfall erhalten bleiben.
`can_confirm` und `can_calculate` sind deshalb getrennt. Konkrete offene Punkte
erscheinen im Plan; ein fehlendes Netto wird nicht als null ausgegeben. Eine
Krankheitserklärung wird beispielsweise nicht durch einen Bestätigungs-Bool zur
fertig berechneten Entgeltfortzahlung.

## Quellen und historische Korrekturen

Jede Fassung ist anhängend und bindet ihren Vorgänger, Originalhashes,
kanonische Quellenfassungen, ihren Plan und den ursprünglichen Auftrag.
Korrekturen brauchen einen Grund. Eine Archivierung bewahrt die bisherigen
Details und Quellen; sie löscht keine Historie. Ein inzwischen ersetztes
Original darf für diese historische Archivierung erhalten bleiben, kann aber
keine neue aktive Fachwirkung begründen.

Die aktuelle Benutzerbindung eines Mitarbeiters kann durch den normalen
Personalweg nicht geändert werden. Die Faktenprüfung kontrolliert diese
Bindung unabhängig vom eigenen Faktenhash. Die eingefrorene Stammrevision wird
zusätzlich mit der tatsächlich angenommenen Personalstammquittung und der
kanonischen Mitarbeiter-Zeithistorie verglichen. Eine neue Namens- oder
Vertragskorrektur interpretiert den alten Stand nicht neu.

Neue Berechnungen verlangen aktuelle Monats-, Fakten- und Profilquellen.
Eine bereits angenommene Quittung verlangt dagegen ihre ursprüngliche genaue
Fassung und frische Rechte. Der identische Auftrag bleibt nach einer späteren
legitimen Korrektur, Archivierung oder Moduldeaktivierung lesbar. Geänderte
Eingaben unter derselben Anfrage-ID werden abgewiesen. Eine fremde
Mitarbeiterquelle oder nachträglich neu gehashte widersprüchliche Quellenansicht
wird bei Replay beziehungsweise Restore nicht als Original akzeptiert.

Profile nach dem tatsächlichen Beschäftigungsende werden nicht für den früheren
Teilmonat verlangt. Ein während der tatsächlichen Beschäftigung gültiger
Profilwechsel bleibt eine ausdrückliche eigene Fachquelle; er darf nicht durch
Weglassen zu einem einfachen Standardfall werden.

## Private Berechtigungen und Datenhaltung

Lesen verlangt aktuelles globales `personnel.read`. Das eigene Mitarbeiterkonto
mit ausschließlich `time.own` kann diese zusätzliche private Anspruchshistorie
nicht lesen. Beschäftigungsfakten und Arbeitspläne brauchen `personnel.write`,
Monatsfälle `personnel.approve`, jeweils zusätzlich zum Leserecht. Modulaktivität
und Rechte sind getrennte Zustände. Gerätezugänge für Offline-Baustellenfunktionen
erhalten keinen Zugriff auf die neuen Routen.

Die zwei neuen Tabellen `business_payroll_fact_events` und
`business_payroll_fact_requests` sind unveränderlich; die PostgreSQL-Laufzeitrolle
hat nur SELECT/INSERT. Originale bleiben in der vorhandenen privaten Personalakte.
Technische Quittungen enthalten Referenzen und Hashes, keine zweite vollständige
private Auftragskopie. Fachfassungen gehören als sensible Personalhistorie in
den Unternehmensexport; technische Quittungen werden ausgeschlossen. Ein
allgemeiner Finanz- oder Assistenzkontext erhält keine Anspruchsgründe oder
privaten Identitätsdaten.

## Tatsächlich ausgeführte Prüfungen

| Nachweis | Ergebnis | Geprüfter Ablauf |
| --- | --- | --- |
| Gemeinsamer P2-Fach-/HTTP-/Reviewlauf | 27/27, 7,530 s, kein Skip | 15 Fachfälle, zehn unabhängige Gegenproben und zwei echte lokale HTTPfälle |
| PostgreSQL nach den Reviewkorrekturen | 3/3, 9,421 s, kein Skip | MFA/HTTP, private Rechte/Offline-Abweisung, Modulpausen-Replay, Runtime-/Owner-Guards, zwei konkurrierende Verbindungen, alte additive HR-Migration und tatsächliches Dump/Restore |
| Unabhängiger P2/P3-Review | Separat 22/22 | Zehn eigene API-/Integrationsfälle plus zwölf eigene Kernfälle; siehe [Gegenprüfung](CRM_ERP_LOHN_TEILMONATE_GEGENPRUEFUNG_2026.md) |

Diese Mengen überschneiden sich und werden nicht addiert. Der lokale Ablauf
prüft einen tatsächlichen Beschäftigungsbeginn am 15. Oktober: 17 Kalendertage,
belegte Methode 17/31, 603,00 EUR vertragliches Monatsentgelt und 330,68 EUR
Teilbrutto. Eine vollständige Arbeitsplanvariante leitet unabhängig davon
12/22 Sollarbeitstage und 328,91 EUR ab. Speicherung der Fakten erzeugt weder
einen Lohnlauf noch eine Bank- oder EÜR-Zahlung.

Der PostgreSQL-Lauf prüft eine fachliche Änderung über zwei tatsächliche
Datenbankverbindungen: identische Originalaufträge erzeugen genau eine neue
Revision; ein separater veralteter Auftrag wird abgewiesen. Nach tatsächlichem
Dump/Restore bleiben Quellen, private Originalbytes, Monatsvorbereitungs-PDF,
Quittung und Periodenplan identisch. Der frühere HR-Datenbestand wird durch die
additive Migration nicht neu geschrieben.

Während der Entwicklung wurden echte Befunde geschlossen: Der lokale
HTTP-Queryumschlag wurde korrekt an die Quellenroute gebunden; eine angenommene
aktive Faktenfassung wird nun an die ursprüngliche Mitarbeiterrevision gebunden;
eine konsistent neu gehashte fremde Benutzerzuordnung wird zurückgewiesen; die
Profilauswahl endet am tatsächlichen Beschäftigungsende. Die unabhängigen
negativen Erstfälle und ihre Korrektur sind im Reviewnachweis erhalten.

Die ersten PostgreSQL-Testansätze hatten falsche Testannahmen zum vorhandenen
Uploadstatus, zum simulierten früheren Registryumfang und zum vorgesehenen
Runtimebenutzer des Restoreabschlusses. Diese Testfehler wurden korrigiert;
die Sicherheitsgrenze für den privilegierten Betreiber wurde nicht gelockert.
Nur der abschließende vollständige 3/3-Lauf wird als grün angegeben.

Reproduzierbare Testdateien: `backend/test_business_payroll_facts.py`,
`backend/test_business_payroll_facts_transport.py`,
`backend/test_business_payroll_facts_review.py` und
`backend/online/test_business_payroll_facts_pg.py`. Tatsächliche Logpfade,
Dateihashes, Laufzeiten und Quellstände stehen im
[maschinenlesbaren Prüfnachweis](CRM_ERP_LOHN_FAKTEN_PRUEFUNG_2026-11-03.json).

## Verbleibende Arbeit

Die vollständige Anspruchsberechnung für bezahlte/unbezahlte Abwesenheit,
untermonatige Kassen-/Beitragswechsel, Einmalbezüge, Minijob-Statuslebensläufe und
weitere Steuerfälle bleiben konkrete Code- und Prüfarbeit gemäß
[Lückenplan](CRM_ERP_LOHN_LUECKENPLAN_2026.md). Die erste P2-Faktenfassung enthält
keine stillschweigende Umsetzung dieser Fälle. Fachliche Produktivabnahme,
amtliche Meldung, notwendige Zulassungen und tatsächlicher Gerätebetrieb sind
zusätzliche Nachweise. Es wurden nur synthetische Mitarbeiter verwendet und
keine Meldungen, Nachrichten oder Zahlungen ausgelöst.
