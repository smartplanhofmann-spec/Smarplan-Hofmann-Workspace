# Lohnzeitachsen und Teilmonate – Clientabnahme P2/P3a

Stand: 03.11.2026. Browser und Flutter bieten die privaten belegten Lohnfakten
und die Berechnung unterstützter Ein- und Austrittsmonate an. Beide verwenden
den [endgültigen Faktenvertrag](CRM_ERP_LOHN_ZEITACHSEN_API.md) und den
[eingefrorenen v4-Rechenkern](CRM_ERP_LOHN_TEILMONATE_2026.md). Der
[ursprüngliche Cliententwurf](CRM_ERP_LOHN_ZEITACHSEN_CLIENTS_ENTWURF.md)
bleibt als Entstehungsnachweis erhalten. Dies ist die Abnahme dieses
Entwicklungspakets, keine Erklärung einer insgesamt fertigen Lohnsoftware.

## Bedienung und tatsächlich vorhandener Umfang

Der Einstieg liegt unter **Personal → Personalakte, Reisen und Lohnvorbereitung
→ Lohnberechnung 2026 → Lohnzeitachsen und Teilmonate**. Die privaten Fakten
benötigen globale Personal-Leserechte und die Serverfähigkeit
`payroll_period_facts`. `time.own` eröffnet diesen Bereich nicht. Beschäftigung
und Arbeitsplan verlangen zusätzlich Personal-Schreibrechte, Monatsfälle die
Personal-Freigabeberechtigung. Server und Oberfläche prüfen aktuelle Rechte;
ein Rechte- oder Sitzungswechsel entfernt die aktiven privaten Ansichten.

| Nachweis | Vorhandene Eingabe und Prüfung |
|---|---|
| Beschäftigung und Entgelt | Tatsächlicher Beginn und optionales Ende, vorhandene Vereinbarungsfassungen, ausdrücklich belegte Teilentgeltmethode, Personaloriginale und Vertragsgrund. Datum und Methode sind beim Neuanlegen leer. Der Personalstamm wird abgeglichen. |
| Datierter Arbeitsplan | Jeder tatsächliche Kalendertag des gewählten Monats mit ausdrücklicher Sollzeit, Arbeitsort und Bundesland. Auch bekannte Nullzeiten werden erfasst. Es gibt keine ungeprüfte Wochenend- oder Feiertagsvorbelegung. |
| Bestätigter Monatsfall | Vorhandene HR-Vorbereitung, Beschäftigungsnachweis, gegebenenfalls Arbeitsplan, genaue Profil- und Identitätsfassungen, steuerliche Einordnung, strukturierte Anspruchsentscheidungen, Originale und Prüfvermerk. |

Anspruchsentscheidungen enthalten Art, Zeitraum, gegebenenfalls eine genehmigte
Abwesenheit desselben Mitarbeiters, Originale und einen belegten Grund. Sie
werden ohne JSON-Freifeld eingegeben. Quellenantworten mit fremder Person,
nicht genehmigter Abwesenheit oder unnötigem Abwesenheitsfreitext werden
verworfen. Ein gewählter Anspruchszeitraum muss in der gewählten Abwesenheit
liegen; die serverseitige Prüfung bindet zusätzlich die HR-Monatsfassung.

**Periodenplan unverbindlich prüfen**, **Geprüften Fallnachweis festhalten**
und **Lohn aus diesem Fall berechnen** sind getrennte Schritte. Die anschließende
Lohnvorschau erfordert weiterhin einen eigenen ausdrücklichen Abschluss.
Ein dokumentierbarer, noch nicht berechenbarer Anspruch zeigt seine Blocker und
bietet keinen scheinbar vollständigen Lohnabschluss an. Nicht ermitteltes Netto
bleibt als solches sichtbar.

Die Darstellung trennt Beschäftigungsintervalle, Entgeltquotienten,
Steuerzeiträume und SV-Zeiträume mit anteiligen Beitragsbemessungsgrenzen.
Die Browseransicht passt Tabellen und Abstände im Lohnbereich an schmale
Bildschirme an. Die Clients ergänzen keine Bruttosumme und keine frei gewählten
Steuer-/SV-Tage: Die v2-Eingabe besteht ausschließlich aus Mitarbeiter-ID,
`source_schema_version: 2` und der Referenz der bestätigten Monatsfallfassung.

## Historie, Wiederholung und vorhandene Monatsberechnungen

Fakten lassen sich historisch ansehen, begründet korrigieren und begründet
aufheben. Eine Aufhebung bindet den vorherigen Quellen- und Planstand; heutige
Stammdaten ersetzen ihn nicht. Originaldownloads prüfen aktuelle Freigabe,
Mitarbeiterzuordnung, Bytezahl und SHA-256. Die vorhandenen historischen
Payroll-PDF-/JSON-Nachweise bleiben erhalten.

Eine unklare Schreibantwort hält den ursprünglichen Auftrag im geschützten
Sitzungsspeicher fest. Die Wiederholung sendet dieselben Werte und dieselbe
Anfragekennung. Vorher werden Rechte und Mitarbeiterzugang frisch gelesen.
Eine bereits angenommene Wiederholung bleibt nach Modulpausierung oder
Fortschritt heutiger Quellen möglich; ein Rechteentzug erlaubt sie nicht.
Die gemeinsamen Wiederholungsgrenzen liegen in BusinessSession/OfficeApi.
Es gibt dafür keine neue LocalStorage- oder Offlinewarteschlange.

Die bestehenden Lohnansichten verstehen alle drei v4-Umfänge:
`regular_standard_period`, `regular_transition_period` und
`commercial_minijob_period_flat_tax`. Bei einer v4-Korrektur wählen Berechtigte
einen bestätigten Monatsfall desselben Monats und begründen die Korrektur.
Jahresübersichten zählen weiterhin genau die letzte wirksame Monatsfassung.
Pauschal versteuerte Minijob-Teilmonate werden dabei mit null individueller
Lohnsteuer eingeordnet; unbekannte Beträge werden nicht zu Nullwerten umgedeutet.

## Ausgeführte Prüfungen

Die gemeinsame synthetische Fixture
`app/test/fixtures/payroll_facts.json` stammt aus tatsächlichen Backendbefehlen,
Vorschauen, Korrekturen, Aufhebung, Laufabschluss und Jahresausgabe. Sie enthält
Minijob-, reguläre und Midijob-Teilmonate. Der Generator
`web/office/tests/payroll_period_fixture.py` erzeugt sie erneut aus temporären
Testdatenbanken. JavaScript und Dart führen kein zweites Steuerrechenwerk aus.
Die unabhängigen steuerlichen Sollwerte sind im Backendnachweis dokumentiert.

| Prüfung | Tatsächliches Ergebnis |
|---|---|
| JavaScript-Lohnregression einschließlich neuer Fakten, Wiederholungsgrenzen und bisheriger Lohn-/Cash-/Jahresfälle | 51/51 bestanden, keine ausgelassenen Fälle |
| Flutter-Lohnregression: Fakten, bestehende Berechnung, Midijob, Lohnkonto und Lohnzahlungen | 52/52 bestanden |
| Flutter-Analyse der beiden geänderten Lohnansichten | Keine Befunde |
| Echter Chromium-Ablauf `payroll-periods` | Vollständiger Ablauf bestanden, einschließlich MFA/HTTP, Originaldownload, Wiederholungen, Historie und Tabellen bei 390 px; Namespace-/PID-/Netzwerk-/Seccomp-Sandboxschutz tatsächlich geprüft |

Die neuen Clienttests prüfen insbesondere falsche Personen-/Quellenbindungen,
fehlende Angaben gegenüber ausdrücklicher Null, gültige Kalendergrenzen,
vollständige Arbeitspläne, dokumentierbare fachliche Blocker, unveränderte
Aufhebungsquellen, falsche Quittungen, verlorene angenommene Antworten,
Modulpausierung, Rechteentzug und nur einmal gezählte Korrekturen. Native
Widgetfälle prüfen eine 390-px-Ansicht und das Entfernen privater Angaben nach
Rechteentzug sowie leere Neuanlagefelder.

Der echte Browserablauf meldet sich über Passwort und MFA an und arbeitet gegen
einen lokalen HTTP-Server mit temporärer Datenbank. Er erfasst den tatsächlichen
Eintritt am 15.10.2026, alle 31 Arbeitsplantage und einen bestätigten Monatsfall.
Bei 5.000 EUR monatlicher Vereinbarung und belegter Kalendertagsmethode entstehen
2.741,94 EUR Teilbrutto und 17 SV-Tage. Verlorene Antworten für Fakten und
Lohnabschluss führen zu identischen Wiederholungen. Originaldownload und altes
Lohn-PDF werden anhand ihrer tatsächlichen Bytes geprüft. Eine nachfolgende
Anspruchskorrektur bleibt fachlich gesperrt und verändert den früheren Lauf
oder dessen PDF nicht. Die Jahresübersicht enthält genau einen wirksamen Monat.

Während der Entwicklung gefundene Fehler wurden behoben: optionale noch nicht
geladene native Listen, doppelte leere optionale Auswahlwerte, ein falsches
Testorakel zur absichtlich leeren Methodenauswahl, fehlende Einordnung der neuen
Minijob-Steuerart in der Jahresprüfung und schmale verschachtelte Browsertabellen.
Ein paralleler Reise-Modulimport verursachte beim erneuten Browserstart einen
separat protokollierten 404; dieser fehlgeschlagene Lauf wird nicht als bestandene
Prüfung gezählt.

Maschinenlesbare Ergebnisse und Dateihashes stehen im
[Prüfnachweis](CRM_ERP_LOHN_ZEITACHSEN_CLIENTS_PRUEFUNG_2026-11-03.json).
Die Protokolle liegen zusätzlich unter `work/verification/payroll-periods-*`;
die versionierten Ergebnisprotokolle stehen unter `docs/evidence/`.
Die Testzahlen überlappen andere Lohnprüfungen und werden nicht als zusätzliche
unabhängige Gesamttestzahl addiert.

## Noch offene Entwicklung

Der vorhandene v4-Umfang deckt P3a mit einer inländischen Beschäftigungsepisode,
einer wirksamen Entgeltvereinbarung und unverändertem Profil ab. P3b mit mehreren
Vereinbarungen oder untermonatigen Versicherungswechseln, P4 mit tatsächlicher
Urlaubs-/Feiertags-/Entgeltfortzahlungsberechnung und P5 mit weiteren
Einmal-/Nachzahlungs-/Übernahmefällen bleiben Entwicklungspakete. Fakten dazu
speichern zu können, erledigt deren Berechnung nicht. Eine schmale
Mitarbeiter-Selbstansicht ohne private Anspruchsakten und amtliche Meldeverfahren
sind ebenfalls gesondert offen. Berechnung, tatsächliche Zahlung und Bankabgleich
bleiben getrennte Vorgänge. Dieser Browsernachweis behauptet keinen darin nicht
ausgeführten Zahlungs- oder Meldevorgang.
