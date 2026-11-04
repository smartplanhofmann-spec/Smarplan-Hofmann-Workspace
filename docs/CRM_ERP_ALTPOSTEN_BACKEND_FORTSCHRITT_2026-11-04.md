# Altposten: Backendstand und abgegrenzte Prüfungen

04.11.2026, isolierter Baum `/workspace/smartplan-opening-items-20261104`.
Der Backendkandidat ist eingefroren. Browser, native Oberfläche und die gemeinsame
Integration werden getrennt fertiggestellt; damit ist weder das Altpostenpaket
als Ganzes noch die Gesamtsoftware als fertig bezeichnet.

## Erreichtes Verhalten

Der [ausführbare API-Vertrag](CRM_ERP_ALTPOSTEN_API.md) unterstützt belegte externe
Restforderungen und Restverbindlichkeiten beim unveränderten EÜR-/Ist-Softwarewechsel.
Originalrechnung, Stichtagsaufstellung, alte tatsächlich bezahlte Anteile und der
wirklich früher ausgeübte Vorsteuerabzug bleiben getrennte Originalnachweise.
Die Übernahme erzeugt weder Ersatzrechnung noch Geld-/Steuerbuchung.

Spätere tatsächliche Einzelzahlungen verbrauchen den Rest centgenau. Forderungen
erzeugen nur auf diese neuen Beträge EÜR-Erlös und Ist-USt. Verbindlichkeiten mit
belegtem altem vollständigem Abzug erzeugen Nettoaufwand und gezahlte Vorsteuer
als EÜR-Ausgabe, aber keine zweite VAT-input-Buchung. Die gleiche Geldquelle ist
im Bankabgleich und in der Liquidität mit separat belegtem Anfangssaldo verfügbar.

Korrekturen erhalten alte Originale und Annahmen. Vor Änderung einer Zahlung sind
aktive EÜR-Buchung und Bankzuordnung ausdrücklich aufzuheben; spätere Centverbräuche
schützen frühere Raten. Neue Anfragen prüfen das aktuelle Profil, Konto, Rechte,
Finanzmodul, Restorefreigabe und Perioden. Exakte alte Annahmen bleiben wiederholbar,
ohne alte Profile oder Berichte umzuschreiben.

Die drei neuen append-only Tabellen sind vollständig im Export-, Runtime- und
Migrationskatalog registriert. Finanzhorizont14/Restorebericht15 prüfen den gesamten
neuen Umfang. Vorherige Horizonte und bereits angenommene Freigaben bleiben historisch
überprüfbar; sie können einen neuen Restore dieses erweiterten Bestands nicht freischalten.

## Tatsächliche Nachweise

| Prüfung | Ergebnis und Bedeutung |
| --- | --- |
| Bestandsaufnahme | 3/3: vorhandene lokale Rechnung bleibt zahlbar; alter berechtigter Vorsteuerzeitpunkt darf nicht verschoben werden; freie Zahlung ist keine externe Rechnungsquelle |
| Abschließender neuer Backendstand | **35/35** in32,975s: eigene und unabhängige Domainfälle, lokale HTTP-/MFA-Kette, Originalgröße/Replays, Finanzmodul-/Offlinegates, Bank, Restcent, Profile, Perioden und exakte Restorehorizonte |
| PostgreSQL auf letztem Produktstand | **3/3** in34,393s: echte getrennte Runtime-/Operatorrechte, zwei konkurrierende Verbindungen, gleiche Annahme nur einmal, unterschiedliche Restverbraucher201/409, Neustart und befüllter tatsächlicher Dump/Restore |
| Bestehende EÜR/Anfangssalden/Anlagen plus neue Fälle | **125/125** in90,010s vor dem abschließenden engeren direkten Finanzmodulgate; dessen Wirkung wurde im35er-Nachlauf ausdrücklich geprüft |
| Weitere aktuelle/historische Finanzscopes | 65/66 zunächst grün; der verbleibende Test verglich neue leere Tabellen mit der ausdrücklich alten H6-Tabellenauswahl. Nur diese historische Fixtureabgrenzung wurde ergänzt; gezielter Nachlauf **1/1** in2,375s grün. Kein Produktfehler oder geänderter historischer Zahlenwert. |
| Unabhängige Fach-/Produktprüfung | [Quellen und zehn Zahlenfälle](CRM_ERP_ALTPOSTEN_QUELLEN_GEGENPRUEFUNG_2026-11-04.md), [zehn eigenständige Produktgegenfälle](CRM_ERP_ALTPOSTEN_UNABHAENGIGE_PRODUKTPRUEFUNG_2026-11-04.md); die zehn Produktfälle sind im abschließenden35er-Lauf enthalten |
| Tatsächliche Clientfixture | Drei real angenommene Szenarien in `docs/fixtures/accounting_open_items_v1.json`, generiert durch `scripts/generate-accounting-open-items-fixture.py`; SHA256 `121d22f4fbbc42521965ac6806d7d63049f29ca85365f98ad688d3beb48b5bce` |

Der PG-Restore hat alle Originalbytes, alte Exportartefakte, EÜR-/Altpostenquittungen
und Tabellenfingerprints erhalten. Eine vorherige/verkürzte Finanzfreigabe und eine
manipulierte neue Prüfsumme wurden ohne Schreibwirkung abgewiesen. Nach Freigabe
wurden die alten bestätigten Befehle exakt wiederholt. Port55433 wurde anschließend
freigegeben; kein Restoreziel und keine weitere Fixtureverbindung blieben bestehen.
Es gab keine realen Zahlungen, Steuermeldungen oder externen Nachrichten.

Alte Testfixtures behalten ihre tatsächlichen historischen Registries. Prüfungen
des heute vollständig installierten Bestands erwarten dagegen ausdrücklich14/15.
Die angepassten früheren PG-Suiten sind Teil des Integrationspatches; diese separate
Abnahme behauptet keinen erneuten vollständigen Lauf sämtlicher alter PG-Suiten.
Der bereits in Hauptstand80e051a behobene Reise-PG-Fixtureaufbau wurde übernommen,
damit der ältere isolierte Kandidat diese Korrektur nicht zurücksetzt.

## Unveränderte Grenzen

Offene/teilweise/streitige alte Vorsteueransprüche, Methoden- oder Besteuerungswechsel,
gemischte Steuergruppen, abweichende belegte Altrundungen, Rabatte, wirtschaftliche
Rückzahlungen, Aufrechnung, Anlagekäufe, Privat-/Auslands-/Zehntagesfälle sind nicht
freigegeben. Die alten Centbeträge werden in solchen Fällen nicht umgedeutet.

Unterjährige Altposten und Bankanfangsbestände machen keine vollständige Jahres-EÜR.
Die fehlenden laufenden Jahreswerte vor dem Softwarebeginn bleiben ausdrücklich
offen; sie sind der nächste getrennte Buchhaltungsumfang. Die laufende Clientabnahme
und die endgültige gemeinsame Integration dieses Backendstands sind ebenfalls offen.

Der Datei-/Prüfmanifest liegt unter
`docs/evidence/opening-items-backend-2026-11-04/manifest.json`. Frühere fehlgeschlagene
Fixture-/Sandboxläufe werden dort als historische Nachweise aufbewahrt und nicht
als erfolgreiche Produktprüfungen gezählt.
