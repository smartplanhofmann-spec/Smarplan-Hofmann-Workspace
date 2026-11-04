# Jahrespaket: Fortschritt und Prüfstand

Isolierter Arbeitsbaum `/workspace/smartplan-year-review-export-20261104`.
Basis und Altpostenbackend-Overlay sind im Vertragsdokument und im
`work/verification/year-review-export-baseline.json` gebunden. Kein Commit,
keine Produktivdaten und kein externer Versand.

Der erste eingefrorene Backendlauf hatte 36/36 Fälle bestanden (40,985 Sekunden):
16 neue Domain-/Archivfälle, zwei tatsächliche HTTP-/MFA-Fälle und 18 bestehende
EÜR-Fälle. Geprüft sind bezahlter Einkauf,
Ausgangsrechnung und Korrektur, unveränderte spätere Wiederholung, historische
Anlage mit belegtem Vortrag und Altpostenzahlung mit früher ausgeübter Vorsteuer,
Finanzzugriff ohne private Lohnoriginale, frischer Projektentzug auch bei einem
ungebuchten alten Reportverweis sowie lokaler Prüfer nach geschlossenem Office.
Beschädigte CSV, fehlende Originale, gekreuzte Quellen, entfernte Korrekturursprünge,
ZIP-Duplikate und Pfadtraversal werden abgewiesen.

Der unabhängige Reviewer reproduzierte im frühen Prüfer eine konkrete Lücke:
Entfernte Dokumentknoten/-links und Originalbytes konnten bei neu berechneter
äußerer Dateiliste als vollständig durchgehen. Die unveränderte eigentliche
Geldflussquelle enthielt den fehlenden Rechnungsbezug weiterhin. Der Prüfer leitet
erforderliche Dokument-/Beleg-/Vorläuferverknüpfungen nun aus diesen ursprünglichen
Payloads ab. Der unveränderte unabhängige Gegenlauf und ein eigener gleichartiger
Test weisen das manipulierte Paket nun ab. Ein exakter früher Quellhash wurde
vom Reviewer nicht gesichert und wird hier nicht nachträglich erfunden.

Echter lokaler HTTP-Download und tatsächliche MFA-Routen sind mit 2/2 Fällen
bestanden: passende Größe/Hash/Dateiname, `no-store`, unveränderte Wiederholung,
strikte Parameter, fremde Exportkennung und frischer Benutzerentzug.

Der erste Domainlauf hatte einen falschen erwarteten Testzählwert (fünf statt
sechs tatsächliche Journalentscheidungen). Zwei neue Finanzleserfälle brauchten
die ausdrücklich vorgesehenen echten `accounting.read`-Grants bzw. eine aktuelle
Projektzuweisung. Diese Fixturekorrekturen änderten keine Produktrechte.

Zusätzlich bestanden sind unveränderte Originalrevisionen nach späterer
Receiptprüfung, Profiländerung und neuen Projektdaten, jahresübergreifende
Korrekturursprünge, echte Vorauszahlungen ohne nachträglich hineingeratene
Rechnungskomponenten sowie der tatsächlich gebuchte gemeinsame Ablauf aus
Komponenten und beiden Erstattungsfassungen (`c1`, `c2`, `r1`, `r2`). Öffentliche
Lohn- und Reisegeldquellen enthalten keine privaten Mitarbeiter-/Reiseoriginale.
Unbekannte Quellarten und übergroße Pakete werden ausdrücklich abgewiesen; der
Größengegenfall bestätigt unveränderte Datenbankinhalte.

Zwei echte PostgreSQL-Fälle bestanden in 14,847 Sekunden: tatsächliche
Ausgangsrechnung mit Teilzahlung, HTTP-Download und Wiederöffnung sowie ein
befüllter Dump/Restore mit Altpostenoriginalen und unverändertem ZIP. Der erste
PG-Lauf traf korrekt die fehlende Unternehmensbindung seiner neuen Testfixture;
die Fixture erhielt die vorhandene Betreiberbindung, der Produktcode blieb
unverändert. Der anschließende getrennte Metadatenkontrollversuch scheiterte
zunächst ohne Passwort. Das automatische Freigabesystem lehnte das danach
vorgeschlagene Auslesen eines Passworts aus dem bestehenden Testwrapper ab.
Dieser Weg wurde nicht ausgeführt oder umgangen. Root bestätigte anschließend
über eine genehmigte Alternative ohne Credentiallesen (`docker exec -u postgres`,
reine PostgreSQL-Metadatenabfrage) ausschließlich `smartplan_check`, keine weiteren
Verbindungen und kein Restoreziel. Diese Nachkontrolle ist Roots Nachweis, keine
erneute Messung dieses Owners. Es bleibt keine Freigabe oder Bereinigung offen.

Die 16 Paketprüfungen bestanden in 8,295 Sekunden. Die tatsächliche Clientfixture
enthält sechs Szenarien, ist in `docs/fixtures` und `app/test/fixtures` bytegleich
und hat 689672 Bytes, SHA-256
`bd3ff5a40bf10211b67ca563dcf14ad2850949e43be54cdb19deba4b5e0557cc`.
Domain-, HTTP-, PG-, Paket- und frühere Fehlerprotokolle sind unverändert unter
`docs/evidence/year-package-backend-2026-11-04/` archiviert und im dortigen
Manifest an ihre tatsächlich geprüften Dateien gebunden.

Browseroberfläche und unabhängige Browsergegenprüfung sowie der native Zugang
werden getrennt abgenommen; ihr Endstand und die gemeinsame Integration sind
noch offen. Der parallele Jahresvortrag wird erst nach dessen tatsächlichem
Quellenvertrag ergänzt. Es gibt keine Gesamtfertigstellungs- oder Prozentbehauptung.

## Nachtrag nach unabhängiger Backendprüfung

Der aktuelle gemeinsame Lauf besteht mit 49/49 Fällen in 83,775 Sekunden:
17 eigene Domain-/Archivfälle, zwölf unabhängige Fälle, zwei tatsächliche
HTTP-/MFA-Fälle und 18 bestehende EÜR-Fälle. Die belegten Grenzen der alten
Journale und der verpflichtende separat authentisierte Archivhash sind im
[Verifikationsnachtrag](CRM_ERP_JAHRESPAKET_VERIFIKATION_NACHTRAG_2026-11-04.md)
und im unabhängigen Backendbericht dokumentiert. Intrinsische Vollständigkeit
aller Ursprungsabhängigkeiten wird ausdrücklich nicht behauptet.

Die endgültig neu erzeugte V1-Fixture umfasst dieselben sechs tatsächlichen
Szenarien, nun 719679 Bytes, SHA-256
`a859f2bbbcfab6f890c2968a05aa2fa839299117ae43b8e15e2d7852c82d36a0`.
Der ältere Fixturehash oben und das Backendmanifest `e2f22817…` bleiben historische
Kandidaten, keine finale Abnahme. Der unveränderte alte EÜR-Export und seine
Belegbytes wurden nicht umgeschrieben. Browser und native App führen einen
gezielten Nachlauf gegen den korrigierten eingebetteten Prüfer aus. Ein gezielter
PG-Nachlauf dieses letzten Archivstands wartet auf den koordinierten freien
Testslot; die vorherigen zwei echten PG-/Restorefälle bleiben separat belegt.

## Abschließende koordinierte Abnahme

Die drei gezielten Archiv-PG-Fälle sind bestanden (19,002 Sekunden): zwei
V1-Rechnungs-/Altpostenfälle und ein V2-Jahresvortragfall im gemeinsamen
Adapterruntime mit tatsächlichem Dump/Restore. Beide V1-Builder-/Prüferdateien
sind bytegleich mit diesem Stand; die gemeinsame EÜR-Routenauswahl ist im
separaten Adaptermanifest gebunden. Kein Produktfix war für PG nötig. Die eigene
genehmigte reine Docker-psql-Metadatenkontrolle ohne Credentiallesen bestätigte
nur `smartplan_check` und keine weiteren Verbindungen; der Slot wurde freigegeben.

Die endgültige Operator-/Clientregistrierung besteht 16/16 Paketprüfungen in
6,183 Sekunden. Browser und native V1-App sind einschließlich unabhängiger
Gegenprüfungen eingefroren. Alle Nachweise und Dateiübergaben sind im finalen
Backendmanifest bzw. `work/verification/year-package-handoff-files.json` gebunden.
V2 erhält einen getrennten kleinen Clientnachtrag; das ist keine Behauptung,
dass das gesamte CRM-/ERP-Gesamtziel fertiggestellt sei.
