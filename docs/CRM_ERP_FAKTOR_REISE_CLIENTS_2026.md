# Faktor-Vollmonat mit bereits bezahlter steuerfreier Reise

Die Clients ergänzen für R09.03 einen ausdrücklich gewählten, eng begrenzten
Abrechnungsfall. Die vorhandene v5-Abrechnung bleibt unverändert auswählbar.
Der neue Knopf heißt **Faktor-Vollmonat mit bezahlter steuerfreier Reise**.

Vorausgesetzt werden genau ein bestätigter v9-Faktorfall für den vollständigen
Monat und je ein ursprünglicher Beschäftigungs-, Profil- und Identitätsnachweis.
Die ausgewählten Reisen müssen vollständig steuerfrei und bereits außerhalb
des Lohns erstattet sein. Sämtliche ursprünglichen Zahlungsfassungen der
ausgewählten Reiseabrechnungen werden ausdrücklich gebunden, einschließlich
Rückzahlungen und aufgehobener Nachweise. Die Erstattung wird nicht erneut
zum Lohnnetto addiert.

Neue Regel: `de_2026_factor_taxfree_travel_month_v10`, Quellenvertrag 2.
Der äußere Lohnlauf bleibt Source3 mit `calculation_case_ref`. Das bestehende
Fachmodell speichert unveränderliche Gesamtfälle, Quittungen und Lohnläufe.
Historische Personaloriginale und Zahlungsaussagen bleiben in ihrer jeweiligen
Fassung sichtbar. Die neue Quellenliste ersetzt nicht den bisherigen
v5-Filter für Periodenfälle.

Ansprüche, Profilwechsel, Teilmonate, steuerpflichtige beziehungsweise pauschal
versteuerte Reisen, Sachbezüge und das Mahlzeitenmerkmal M gehören nicht zu
diesem Fall. Der Client erzeugt keine zusätzliche Zahlung oder Übermittlung.

## Nachweise

Die gemeinsame synthetische Datei
`app/test/fixtures/payroll_factor_travel.json` stammt aus den tatsächlichen
privaten Backend-, Reise-, Zahlungs- und Lohndiensten. Sie enthält den
unveränderten v8-/v9-Geldvergleich sowie die tatsächlichen v10-Quittungen.

Sieben neue Browser-Vertragsfälle bestehen gegen diese Datei: genaue
Quellen-/Zahlungsreferenzen, Vorschau und Quittung, unveränderte Nettowerte,
abgelehnte unvollständige beziehungsweise ersetzte Nachweise, die echte
Faktorkorrektur mit unveränderter Reisezahlung und exakte Wiederholung nach angenommener Antwort mit anschließend entzogenem Zugriff.
Alle 40 Browser-Lohntestdateien bestehen im gemeinsamen Lauf. Der tatsächliche
Chromium-/MFA-/HTTP-Ablauf auf der Backend-Featurebasis besteht: ursprünglicher
Faktor-Vollmonat, Reiseeinreichung, geprüfte Abrechnung, belegte Zahlung, neue
UI-Quellenwahl, verlorene Antworten bei Fall- und Lohnbestätigung, exakte
Wiederholung, unverändertes Netto und unveränderte alte Reisezahlung sowie
private Original-/PDF-Downloads und mobile Darstellung. Der erste Lauf stoppte
am fehlenden Instanzaufbau der Testeinrichtung; der vorhandene gebundene
Reise-Testmodus korrigiert ausschließlich diesen Aufbau.

Zwölf neue native Fälle bestehen gegen dieselbe echte Backendfixture,
einschließlich exakter Widget-Quellenwahl, Faktorkorrektur, Zahlungssumme,
Faktor-/Quellenbindung, aufgehobener Zahlungsfassung und ursprünglichem
Lohnlauf bei später entzogenem Funktionszugang. Der gemeinsame finale Lauf besteht 26 ausgewählte native Fälle, einschließlich
der zwölf neuen Fälle und bestehender Source3-/Kontextgegenfälle. Die
Dart-Analyse von vier Produktdateien und dem neuen Test meldet keinen Befund.

## Gemeinsame Integrationsbasis

Die Prüfung verwendet den zusammengeführten Backendstand einschließlich
`35f94e4` (in der Integrationsarbeitskopie `69ddb4a`) mit getrennten
v10-Periodenmetadaten für die Jahresprojektion. Offline V2, Servicejournal,
Projektmeilensteine und die Wartungsvertragsbearbeitung bleiben erhalten.
Die gemeinsame Originalwiederholung in `OfficeApi` berücksichtigt sowohl
Wartungsverträge als auch den neuen Faktorfall und dessen Lohnlauf.

41 Browser-Testdateien einschließlich der Wartungsvertragsregression bestehen.
26 ausgewählte native Fälle bestehen; die Analyse meldet keinen Befund.
Der abschließende gemeinsame Chromiumlauf besteht mit tatsächlicher MFA, HTTP und
geprüften Chromium-Namespace-/PID-/Netzwerk-/Seccomp-Sandboxes.

Die unabhängige native Gegenprüfung reproduzierte zunächst drei fehlende
Quervergleiche: Zahlungssumme gegen Plan, Planfaktor gegen Originalprofil und
Rechnungsfaktor gegen Plan. Die korrigierten Gegenfälle und die Erhaltung
aufgehobener Zahlungsfassungen sind jetzt geprüft. Die ursprünglichen roten
Protokolle bleiben zusammen mit den erfolgreichen Läufen erhalten.

[Maschinenlesbarer Nachweis und Protokolle](evidence/factor-travel-clients-2026-11-09/verification.json).

Die Prüfungen verwenden synthetische Daten. Sie belegen keine neue
Serverinstallation, Geräteabnahme, fachliche Gesamtfreigabe oder amtliche
Zulassung.
