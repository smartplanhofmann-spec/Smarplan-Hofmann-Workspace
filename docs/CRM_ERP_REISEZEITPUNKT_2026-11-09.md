# Reiseeinreichung am Sekundenwechsel und belastbare Aufgabenprüfung

Bezug: R09.02 sowie Aufgaben-/Projektabnahme A. Der eigene Remote-Lauf
Development42702226560 auf Produkt9271be7 bestätigt sechs erfolgreiche Jobs
(einschließlich Windows, Mac-Simulator und vollständiger Appprüfung), aber
Fehler in Online-API und Business-Browser. Der alte Lauf wird nicht grün erklärt.
Sein [tatsächlicher Abruf und Fehlerauszüge](evidence/ci-travel-clock-2026-11-09/previous-publication.json)
bleiben erhalten. Der iPhone-Build lief beim damaligen Abruf noch.

Die Online-Gegenprobe trifft einen echten Schreibfehler: `submitted_at` und
`created_at` einer Reiseeinreichung wurden in zwei getrennten Uhrabfragen
erzeugt. Beim Sekundenwechsel konnte die anschließende bestehende
Integritätsprüfung deshalb eine soeben erzeugte Fassung zurückweisen. Neue
Einreichungen verwenden jetzt denselben Ereigniszeitpunkt für beide Angaben.
Zurückweisungen erhalten ihren bisherigen Einreichungszeitpunkt. Historische
Fassungen, Quellen, Zahlungen und Rechenregeln werden nicht umgeschrieben;
die strenge Integritätsbedingung bleibt bestehen.

Eine deterministisch jede Sekunde weiterschaltende Uhr reproduziert auf dem
alten Produkt denselben Fehler und besteht nach der Korrektur. Alle fünf
Reiseworkflow-Fälle bestehen. Die vier tatsächlichen PostgreSQL-/MFA-/HTTP-
Fälle des betroffenen Faktor-/Reise-Reviews bestehen einschließlich Rechteentzug,
unveränderten Originalen, Zahlungen und tatsächlichem Dump/Restore (67,441 s).
Der erste lokale PG-Lauf ohne `pg_dump` bleibt als Umgebungsfehler erhalten.
Der erfolgreiche Nachlauf verwendet echte, nur auf die eigene Testinstanz
begrenzte PostgreSQL-Werkzeuge.

Der Aufgaben-Browsertest änderte die Aufgabe parallel, bevor sein alter Editor
nachweislich geladen war. Die Gegenprobe wartet jetzt auf die sichtbare
Fassung 5 und erzeugt danach die konkurrierende Fassung. Sie besteht mit
tatsächlicher MFA/HTTP, unveränderten Originalen, Rechteentzug, verspäteter
Antwort und 390px-Ansicht. Der Produktcode für Aufgaben bleibt unverändert.

[Unveränderte Rohläufe und Quellhashes](evidence/ci-travel-clock-2026-11-09/manifest.json).
Dies ist eine lokale Korrekturprüfung, keine neue Serverinstallation oder
vollständig abgeschlossene Remote- und Geräteabnahme.
