# Source4: eingefrorene gemeinsame Prüfung am 04.11.2026

Der neue gemeinsame Zwischenstand verbindet Jahresquellen, das belegte
U-Merkmal, Nullnetto-Nachweise und reguläre Source4/v6-Einmalbezüge mit
Lohnkonto, tatsächlichen Zahlungen, Cash/EÜR und beiden Oberflächen.
Eigene Mitarbeiterbelege bleiben auf die zulässige persönliche Projektion
begrenzt. Die reine SV-/Steuer-/Jahresfortschreibung und die dazugehörigen
PostgreSQL-/Browsernachweise sind in den jeweiligen Fachprotokollen abgegrenzt.

| Prüfung auf eingefrorener Kopie | Ergebnis |
| --- | --- |
| Vollständige Backendregression | 1.508 bestanden; ein Windows-spezifischer Test unter Linux ausgelassen; 480,949 s |
| Sämtliche Browser-JavaScript-Tests | 473 bestanden |
| Sämtliche Fluttertests | 1.103 bestanden |
| Vollständige Flutteranalyse | Keine Befunde |
| Native Paket-/Quellarchivprüfungen | 16 bestanden |

Alle 1.515 erfassten Dateien wurden nach den Prüfungen gegen ihre SHA-256
kontrolliert. Das erste Manifest und die spätere Fassung mit ausschließlich
zwei geänderten Python-Testdateien bleiben getrennt erhalten. Die vollständigen
Protokolle und Prüfsummen stehen in
[evidence/payroll-source4-integrated-regression-2026-11-04.json](evidence/payroll-source4-integrated-regression-2026-11-04.json).

Der erste Backendlauf hatte vier Fehler: Die synthetische Assistenten-Domäne
verwendete den 3. November, einzelne native Versand- und Sprach-HTTP-Wege
den tatsächlichen aktuellen Tag. Die Testfixture nutzt jetzt für beide Wege
dieselbe Uhr. Ein zusätzlicher echter HTTP-Gegenfall prüft weiterhin die
Abweisung eines alten Kontexts nach Tageswechsel vor einer Providerübertragung
und die erfolgreiche neue Quellenauswahl. Die 35 betroffenen Prüfungen und die
anschließende vollständige Wiederholung bestehen; Produktcode und
Quellen-Frischeprüfung wurden dafür nicht geändert.

Der erste Paketlauf hatte 15 bestandene Fälle und eine fehlende lokale
Testinterpreter-Konfiguration. Nach Ergänzung des ignorierten Interpreterpfads
bestand die gesamte Paketprüfung ohne Änderung der Paketquellen. Beide
fehlgeschlagenen Erstläufe bleiben unverändert im Nachweis erhalten.

Die Weiterentwicklung von V7, Finanz-Anfangssalden und Katalogimport liegt
außerhalb dieses eingefrorenen Quellstands. Mehrere Einmalbezüge im selben
Monat, getrennte Zuflusstage und die weiteren benannten Lohn-/Steuerfälle
sind damit nicht abgeschlossen. Geräteinstallation, betriebliche Freigaben
und die vollständigen Gesamtziel-Abnahmen A–G bleiben gesonderte Arbeit.
Der Nachweis ist ein lokaler Entwicklungszwischenstand, keine Auslieferung.
