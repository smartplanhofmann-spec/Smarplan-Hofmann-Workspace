# Betriebliche Reise-Pauschalsteuer: Browser und Native

Stand 03.11.2026. Der globale Dialog erfasst eine tatsächlich belegte betriebliche
Entscheidung für einen vollständigen Anmeldemonat, ein Quartal oder das Jahr 2026.
Zeitraum, lohnsteuerliche Betriebsstätte, vereinfachtes oder Nachweisverfahren,
regionale Kirchensteuerzuständigkeit und wirtschaftliche Kostenübernahme müssen
ausdrücklich angegeben werden. Neue Formulare setzen keine dieser Angaben voraus.
Die einheitliche Anwendung wird eigens bestätigt; der Dialog wählt kein Verfahren
nach dem günstigsten Ergebnis einzelner Mitarbeiter.

Geschützte Personaloriginale werden über den globalen Quellenkatalog ausgewählt.
Vorschau und abschließende Bestätigung sind getrennt. Korrekturen erhalten die
Identität des Zeitraums und der Betriebsstätte, Aufhebungen die ursprünglichen
Nachweise. Historische Fassungen bleiben lesbar und unverändert. Die Daten bleiben
im privaten Sitzungsspeicher und werden bei Entzug der Rechte verworfen. Eine
verlorene angenommene Speicherantwort wird mit exakt demselben ursprünglichen
Auftrag und derselben Nonce erneut geprüft; es entsteht keine zweite Entscheidung.

Produktiver Browser-Einstieg: Personalakte → Lohnberechnung 2026 →
„Betriebliche Reise-Pauschalsteuer öffnen“. Native bietet denselben Dialog über
`showPayrollTravelTaxPolicies(...)`. Eine optionale Auswahl liefert erst nach
frischer Quellen- und Rechteprüfung die unveränderte aktive Fassung zurück.
Die eigentliche Reise-Lohnberechnung verlangt anschließend eine eigene Vorschau
und Bestätigung. Dieser Dialog erzeugt keine Überweisung oder Steuerübermittlung.

Ausgeführte Prüfung: 8 Node-Tests, 8 Flutter-Tests und statische Analyse von drei
Dart-Dateien ohne Befund. Ein echter sandboxierter Chromium-Ablauf mit lokaler
MFA/HTTP-Anmeldung bestätigt den produktiven Einstieg, leere Pflichtauswahl,
Originaldownload mit SHA-256, getrennte Vorschau/Bestätigung, verlorene Antwort,
identische Wiederholung, Korrektur, Aufhebung, unveränderte Historie und Mobile390.
Alle Daten stammen aus isolierten synthetischen lokalen Domainbefehlen.

Nachweise und genaue Grenzen:
[`evidence/payroll-travel-policy-clients-2026-11-03.json`](evidence/payroll-travel-policy-clients-2026-11-03.json).
Frühere fehlgeschlagene Flutter-Aufrufe sind im Arbeitsverzeichnis erhalten und
im Nachweis als Werkzeugpfad-, Testsignatur- beziehungsweise Testscroll-Probleme
erklärt. Sie werden nicht als bestandene Läufe gezählt.
