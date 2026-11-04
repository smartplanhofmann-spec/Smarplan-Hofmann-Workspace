# Datierte Katalogpreise und Kostensummenkorrektur: Gesamtprüfung

Stand 04.11.2026, auf Basis `80e051a`. Browser, native App und Backend für
explizit datierte Einkaufs-/Verkaufspreise sind zusammengeführt. Die vorhandenen
Anfangssalden, historischen Anlagen, Katalog-v1-Originale und Source5-Lohnwege
bleiben erhalten. Das ursprüngliche Gesamtziel bleibt bytegleich.

## Nutzbarer abgegrenzter Umfang

Eigene CSV-v2-Originale erhalten Quellen, Gültigkeitszeiträume, Preisrollen und
exakte Preisbasen. Ein Preis von 1 EUR je 3 Stück wird nicht bereits beim Import
auf einen verkürzten Einzelpreis umgerechnet. Vorschau und ausdrückliche
Übernahme binden Artikel, Original, Preisrevision und Stichtag. Lücken,
Überlappungen, falsche Rollen oder unpassende Einheiten ergeben keine stille
Ersatzwahl. Korrekturen und Rücknahme behalten die alte Historie.

Angebote, Kalkulationen, Verkaufsübernahme und Bestellungen verwenden ihre
explizite Preisquelle. Alte Belege behalten ihren ursprünglichen Snapshot.
Ein technisch leerer Stammwert wird nicht als verwendbarer Nullpreis behandelt.
Wareneingänge benötigen weiterhin ihre tatsächlichen Kosten. Beide Clients
prüfen ursprüngliche Quittungen, Rechte und den aktuellen Ansichtskontext.

Der getrennte Assistentenfix verwendet die bereits berechnete
Projektkostensumme genau einmal. Ein tatsächlich erfasster Beleg über 100 EUR
netto ergab bisher fälschlich 200 EUR im Assistentenkontext. Neue Quellen tragen
einen ausdrücklichen Herkunftsmarker; alte Annahmebytes bleiben nach ihrem
ursprünglichen Vertrag prüfbar. Offene alte Pläne werden durch den neuen
Quellenhash veraltet, statt still neu bewertet zu werden.

## Tatsächliche Prüfungen des gemeinsamen Standes

| Prüfung | Ergebnis |
| --- | --- |
| Vollständiges Backend | 1.738 ausgeführt, 1.737 bestanden, ein vorhandener Windows-Skip; 801,497 s |
| Vollständige Fluttertests | 1.312/1.312; 521,252 s |
| Browsermodule | 610/610; 5,883 s |
| Flutteranalyse | Keine Befunde; 9,785 s |
| Paketprüfungen nach Dokumentergänzung | 16/16; 9,294 s |
| Gezielte Katalog-/Kostenregression | 80/80; 19,366 s; Überschneidung mit der vollständigen Suite |
| Tatsächliches PostgreSQL | 4/4; 56,389 s; Rechte, Konkurrenz und befüllte Wiederherstellung |
| Tatsächliches Chromium/MFA/HTTP | Katalog-v2 18,680 s, bestehende Rechnungskette 17,883 s, Anlagen 40,967 s und Source5 einschließlich eigener Belege 38,917 s bestanden |

Der gemeinsame Restore enthält einen tatsächlich gespeicherten datierten
Angebotspreis, Katalog-v1-Original, historische Anlage/Folge-AfA, Anfangssaldo,
Source5-Lauf/Anspruch und EÜR-Export. Originale, historische Werte und Quittungen
bleiben unverändert. Finanzhorizont 13 und Restorebericht 14 bleiben erforderlich.
Chromium prüfte seine Namespace-/PID-/Netzwerk-/Seccomp-Isolation. Die Flutter-
Prüfung ersetzt keine installierte Windows-/iPhone-Abnahme.

Alle 1.206 abschließend gebundenen Eingabedateien sind unverändert. Der
[Gesamtnachweis](evidence/catalog-v2-integrated-regression-2026-11-04.json) und
[Quellstand](evidence/catalog-v2-integrated-source-snapshot-2026-11-04.json)
enthalten Befehle, Dauer, Logs und Hashes. Ein unabhängiger Mergecheck bestätigt
89 bytegleiche der 101 Ownerdateien; zwölf globale Einbindungen wurden geprüft,
ohne Produktbefund. Eigenständige Preis-/Verbraucherdateien bleiben unverändert.

Eine alte Testskriptwurzel verursachte zunächst Importfehler, bevor ein
PostgreSQL-Test ausgeführt wurde. Ein anderer Browserlauf verlor beim rein
beobachtenden CDP-Zugriff den bereits mit HTTP200 gelieferten Mitarbeiterbeleg.
Der Test liest nun die unveränderte tatsächliche Serverantwort vor ihrer
Weitergabe an den Browser. Die fachlichen PDF-/JSON-/Privatheitsprüfungen bleiben
gleich; der gesamte Source5-Ablauf und alle Browsermodultests wurden wiederholt.
Fehlprotokolle und alter Testbeobachter bleiben erhalten.

Die Paketlisten enthalten fünf neue Bedien-/Vertragsdokumente. Eine bestehende
Abweichung der Windows-CI wurde behoben: Beide Paketwege und CI enthalten jetzt
dieselben 131 Backend- und 138 Operatorpfade ohne Dubletten. Dies ist ein
Quell-/Paketnachweis und keine ausgeführte Windowsinstallation.

## Weiter offener Umfang

Konkrete Lieferantenformate, Staffel-/Rabatt-/Fremdwährungsmodelle und reale
Anbieterabnahmen bleiben gesondert. Die integrierte CSV-v2-Schnittstelle behauptet
keine Herstellerzertifizierung. Unternehmensweite Ereignisregeln und historische
offene Posten haben eigene laufende Client-/Gesamtintegrationen. Belegte
Jahreswerte vor einem unterjährigen Wechsel sowie ein jahresbezogenes Original-/
Journalpaket sind weitere konkrete Buchhaltungsarbeit. Mehrere Bonussteuergruppen,
weitere Steuer-/Lohnfälle und vollständige Fach-/Betriebsabnahmen bleiben offen.
Die gesamte Buchhaltung oder CRM-/ERP-Software ist damit nicht fertig.
