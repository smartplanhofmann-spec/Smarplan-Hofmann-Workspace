# Nullnetto-Lohnkontonachweise: Browserbedienung und Prüfung

Der Produktweg lautet **Personalakte → Lohnberechnung 2026 → Lohnkonto-Nachweise
öffnen → Tatsächliche Lohnzahlung erfassen**. Zuerst wird die konkrete bereits
angenommene Monatsberechnung ausdrücklich ausgewählt. Ergibt ihr vollständig
geprüfter Quellenstand keine geschuldete Nettozahlung, zeigt die Erfassung
**Keine Nettozahlung geschuldet** und bietet keine Zahlungsteile, Zahlungstage
oder erfundenen Null-Euro-Zahlungen an.

Der gültige Stammnachweis, das geschützte Original und gesondert belegte
steuerfreie Bezüge werden weiterhin ausdrücklich erfasst. Beide Prüfbestätigungen
starten leer. Eine Korrektur wählt die ursprüngliche Monatsfassung erneut und
verlangt beide Bestätigungen sowie einen belegten Grund. Frühere Fassungen
bleiben in der Nachweishistorie erhalten. Eine verlorene angenommene Antwort
wird mit demselben ursprünglichen Auftrag und derselben Nonce wiederholt.

Die Jahresübersicht bezeichnet den Monatsstand als **Keine Nettozahlung
geschuldet**. Steuer- und Beitragsabführungen müssen weiterhin separat belegt
werden. Fehlende U-Jahresnachweise werden als verständliche Handlungsanweisung
angezeigt; der Nullnetto-Nachweis macht aus einem unvollständigen Jahreskonto
kein vollständiges.

## Ausgeführte tatsächliche Browserläufe

**Zwei finale Chromium-Abläufe bestanden:** der neue Nullnetto-Fall und die
bestehende Lohnregression. Beide liefen nach echter lokaler MFA-Anmeldung mit
aktiver Namespace-, PID-, Netzwerk- und Seccomp-Sandbox.

Der neue Fall erzeugt per HTTP einen belegten Beschäftigungsbeginn am
15. Oktober, vollständigen Anspruchsausfall bis Monatsende, P2/P4-Originale
und einen vollständigen Source3-Lohnlauf mit 17 unbezahlten Beschäftigungstagen.
Brutto und Auszahlungsnetto betragen tatsächlich null. Geprüft werden die
Bedienung, zwei getrennte Bestätigungen, der Originaldownload mit Prüfsumme,
unveränderte Wiederholung nach verlorener Antwort, Korrektur und erhaltene
Historie, das tatsächliche Monatskonto, der exakte Jahres-JSON-Export und die
390-Pixel-Ansicht.

Die bestehende Regression prüft zusätzlich positive Minijob- und reguläre
Lohnzahlungen, mehrere Zahlungsteile, Vortragsmonate, Korrekturen und
PDF-/CSV-/JSON-Exporte mit der vorgeschalteten Laufwahl. Die Mitarbeiteransicht
wird gegen die inzwischen vorhandenen eigenen Lohnnachweise geprüft. Interner
PDF-Export und private Fachquellen bleiben dort per HTTP gesperrt. Der
bestehende eigene Lesezugriff auf alte Schema1-Läufe wurde nicht verändert.

Der erste Nullnetto-Lauf bestand fachlich; seine mobile Sichtprüfung fand einen
rohen U-Fehlerschlüssel. Der Produktowner ersetzte ihn durch die deutsche
Handlungsmeldung, der zweite Lauf prüft sie ausdrücklich. Zwei rote
Bestands-Testläufe beruhten auf veralteter Dialogerwartung beziehungsweise einer
neu eingeführten, zu weit reichenden Annahme über Schema1-Eigenleserechte.
Diese Testvertragskorrekturen sind getrennt von Produktbefunden dokumentiert.

Alle Daten sind synthetisch. Die Browserprüfung ersetzt weder reale
Geräteabnahme noch amtliche Übermittlung oder Prüfung tatsächlicher
Arbeitgeberunterlagen. Native Ergebnisse werden separat geführt.

Befehle, finale und frühere Logs, Screenshot und Dateiprüfsummen:
[evidence/payroll-zero-account-browser-2026-11-04.json](evidence/payroll-zero-account-browser-2026-11-04.json).
