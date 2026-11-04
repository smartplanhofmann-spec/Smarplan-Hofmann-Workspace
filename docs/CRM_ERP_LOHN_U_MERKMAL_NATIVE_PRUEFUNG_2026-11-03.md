# Native Jahresprüfung des U-Merkmals: ausgeführter Nachweis

Stand 03.11.2026. Die Flutter-Oberfläche `BusinessPayrollWageInterruptionsPage`
und ihr separater Quellenvertrag sind implementiert. Maßgeblich bleibt der
[fachliche U-Vertrag](CRM_ERP_LOHN_U_MERKMAL_VERTRAG_2026.md); der unabhängige
[Browsernachweis](CRM_ERP_LOHN_U_MERKMAL_CLIENTS.md) ergänzt diesen Bericht.

## Bedienung und Quellenschutz

Die Oberfläche führt von der tatsächlichen Auswahl der Beschäftigungsfassungen,
angenommenen Lohnläufe, Tagesarbeitspläne, Anspruchsnachweise und Personaloriginale
zu einem privaten Entwurf. Jede der acht gesetzlichen Ausnahmeleistungsarten
beginnt ungeprüft. Vorhandene Ausnahmen benötigen ausdrücklich Art, tatsächlichen
Zeitraum und geschützte Originale. Quellen- und Zeitraumänderungen verwerfen alle
acht Prüfbestätigungen. Erst nach erneuter Prüfung wird die Vorschau abgerufen.

Die Tagesherleitung und Anzahl U bleiben ausschließlich aus den Quellen
abgeleitet und schreibgeschützt. Ungeklärt bleibt `number_u: null` mit sichtbaren
Blockern, niemals eine still angenommene Null. Die konkrete Vorschau wird getrennt
bestätigt. Korrektur, Aufhebung, erneute Korrektur einer aufgehobenen aktuellen
Fassung und historische Ansicht verwenden die jeweilige ursprüngliche Fassung.

Die Antwortprüfung bindet Tagesnachweise an die genauen Lauf-, Beschäftigungs-,
Arbeitsplan- und Dateireferenzen der Vorschau. Eine unerwartete Antwort ersetzt
keine Originalquittung und lässt den Auftrag unbestätigt. Wiederholung erfolgt
über `BusinessSession.repeatPayrollWageInterruptionsCommand` mit ursprünglicher
Nonce, unverändertem Body und ursprünglichem Validator. Aktuelle globale Rechte
und der private Mitarbeiterkontext werden erneut geprüft. Eine spätere
Personalpause oder Quellenrevision verändert den bereits gesendeten Auftrag
nicht. Rechteentzug, Mitarbeiterwechsel und Hintergrundwechsel bereinigen die
private Ansicht; ein noch offener Quelleneditor wird geschlossen.

## Tatsächlich ausgeführte Prüfungen

**10 von 10 Flutter-Tests bestanden**, anschließend **Analyze über die zwei
Produktdateien und den Test ohne Befund**. Die tatsächlichen Backend-Fixtures
stammen aus `scripts/generate-payroll-wage-interruptions-fixture.py` und enthalten
Source3-Lauf, P4-Anspruchsnachweis, Arbeitsplan, Vorschau sowie angenommene Erst-,
Korrektur- und Aufhebungsfassungen mit Historie.

- Originale Erstannahme, Korrektur und Aufhebung; fünf vertragliche Arbeitstage
  vom 20. bis 26. Oktober ergeben U1.
- Fehlende, widersprüchliche oder erfundene Ausnahmeprüfung; konkrete gebundene
  Leistungszeiträume und überlappende Zeiträume.
- Unbekannte Anzahl gegen falsche Null; ersetzte tägliche Quellenreferenzen,
  Beschäftigungsintervalle, Originaldatei, Mitarbeiterrevision und Tagesabdeckung.
- Abweichende Quittung, Vorschau und Revisionskette bleiben ungültig.
- Verlorene angenommene Antwort, ungültige erste Wiederholungsquittung und erneute
  identische Wiederholung trotz Personalpause und Mitarbeiterrevision 99;
  fehlende aktuelle Rechte und fremde Mitarbeiterquellen verhindern den POST.
- Tatsächlich gerenderte Korrektur: acht ausdrückliche Auswahlen, Rücksetzen nach
  Quellenänderung, erneute Prüfung, Vorschau, separate Bestätigung und identischer
  Wiederholungsauftrag über die UI. Rechteentzug entfernt die privaten Inhalte.
- Mobile Darstellung mit 390 Pixeln, schreibgeschützte Tagesherleitung und
  ausdrücklicher unbekannter Anzahl; neue Form ohne vorausgesetztes Datum oder
  Quellenwahl; Mitarbeiterwechsel und Korrektureinstieg nach Aufhebung.

Die Flutter-Transportfälle verwenden eine instrumentierte lokale API mit echten
angenommenen Domain-Fixtures. Sie sind keine native Prüfung gegen einen live
laufenden HTTP-Server. Tatsächliche HTTP/MFA/PostgreSQL- und Browsernachweise sind
in den separaten Backend- und Browserberichten dokumentiert. Dieser Nachweis
behauptet keine Gerätefreigabe, amtliche Übermittlung oder fachliche Abdeckung
der im Vertrag ausdrücklich gesperrten Fälle.

Die ersten gezielten Läufe fanden und behoben eine lokale Null-Listenbehandlung,
den falschen abschließenden Fehlerstatus einer ungültigen Quittung und den noch
offenen privaten Editor nach Rechteentzug. Erstprotokolle bleiben getrennt vom
abschließenden grünen Ergebnis erhalten. Zwei vorherige Startfehler betrafen die
Testumgebung (fehlender clang-Pfad bzw. nicht freigegebener Loopback-Socket),
nicht ausgeführte Fachprüfungen.

Prüfbefehle, Dateiprüfsummen und dauerhafte Protokolle:
[`evidence/payroll-wage-interruptions-native-2026-11-03.json`](evidence/payroll-wage-interruptions-native-2026-11-03.json).
