# Alte Einmalbezugsoriginale zwischen Windows und Linux

Stand: 09.11.2026. Gesamtziel R09.03, R08.05, R02.02 und Auslieferung.

Die alten v6/Source4- und v7/Source5-Einmalbezugsregeln binden teilweise rohe
Modulbytes in ihre Nachweise ein. Deshalb unterscheiden sich ihre Metadaten
bei LF-/CRLF-Zeilenenden trotz identischer Jahresquellen, Zuweisung, Steuer,
Sozialversicherung und Nettobeträge. Der bisherige Plattformwechsel kann eine
gültige Originalabrechnung als verändert zurückweisen. Historische Werte oder
Regelhashes dürfen deshalb nicht überschrieben werden.

Der neue reine Prüfer `oneoff_provenance_compat.py` rechnet zuerst mit den
unveränderten nativen Regeln. Bei einem Unterschied reproduziert er höchstens
acht genau hergeleitete Varianten der drei unveränderten historischen Module
für PAP-Jahresgrundlage, PAP-Einmalbezug und SV-Einmalbezug. Er bindet die
abhängigen v6-Regel-, Zuweisungs-, SV- und PAP-Hashes sowie die v7-Monatsgruppe
und eingebettete v6-Originalrechnung nach. Alle anderen Inhalte müssen
vollständig übereinstimmen. Ein beliebiger gültig aussehender Hash oder ein
zusammengemischtes Metadatenpaar ist keine zulässige Variante.

Die historischen Case-/Run-Adapter geben nach erfolgreicher Nachrechnung eine
getrennte Kopie des angenommenen Originalplans zurück. Das Original und seine
Quell-, Vorschau-, Beleg- und PDF-Bindungen bleiben erhalten. Neue Fälle werden
wie bisher mit den tatsächlich verwendeten Regeln vorbereitet. Es gibt keine
Datenbankmigration oder Umschreibung alter Fälle.

Source5-Zahlungen benötigen zusätzlich die Bindung ihres v1-Zahlungsplans an
die tatsächlich angenommene Originalabrechnung. Der private Resolver prüft
den unveränderten reinen Zahlungsplan und bindet ausschließlich dessen
Kompositionshash und den davon abhängigen Planhash an das exakt nachgerechnete
Original. Die ursprüngliche `build_single_payment_plan`-Funktion ist bytegleich;
Anspruch, Netto, Zuflusstag, echte Zahlungen, frühere Zahlungsteile und
Zuordnungen werden nicht geändert. Bereits angenommene alte v1-Pläne bleiben
unverändert lesbar.

Die kontrollierten unabhängigen Prüfungen verwenden eine eigene CRLF-Kopie
der tatsächlichen Produktionsquellen in einem isolierten Python-Prozess.
Sie umfassen v6 einschließlich tatsächlich ins SV-Jahr2025 fallender
Märzklausel, v7, ausdrücklich weiterhin blockierte Mehrfachansprüche,
Originalfälle/Läufe/PDF/Quittungen, echte Zahlung und EÜR-Verbrauch sowie
aufgelöste Jahresfolgen. Die umgekehrte Richtung LF-Original unter CRLF-Modulen
wird ebenfalls geprüft. Alle sieben neuen Fachkettenfälle einschließlich der Jahresfolge bestehen.
Ein anfangs falsch vorbereitetes Fixture mit überlappenden Beschäftigungsfakten
ist korrigiert. Im gemeinsamen Sammellauf mit 694 verschiedenen Lohn-/Reisefällen
bestehen 683 Fälle; elf tatsächliche lokale HTTP-Fälle scheitern ausschließlich
beim Socketaufbau mit EPERM in der Sandbox. Genau diese elf bestehen nach
Socketfreigabe in 24,294 Sekunden ohne Skip. Damit sind alle 694 verschiedenen
Fälle erfolgreich geprüft, verteilt auf beide Läufe. Der erste Sammellauf bleibt
mit 1115,245 Sekunden und Exit 1 erhalten; ein einzelner vollständig grüner
Sammellauf wird nicht behauptet. Die erste gezielte Wiederholung verwendete
versehentlich doppelte Methodennamen; auch dieses Ladeprotokoll ist erhalten.
[Exakter Abgleich der Testkennungen](evidence/oneoff-provenance-2026-11-09/regression-outcomes.json).

Vier tatsächliche PostgreSQL16.15-/MFA-Fälle bestehen ohne Skip in 186,817
Sekunden: v6/v7-Originale mit zwei parallelen Verarbeitern, privatem Personal-
und Offline-Ausschluss, unveränderlichen Tabellen, tatsächlichen Zahlungen,
Jahresquellen, PDF, Quittung und `pg_dump`/`pg_restore`. Die kurzlebige eigene
Testinstanz ist nach diesen und vier getrennten EÜR-Prüfungen wieder entfernt.

884 Browser-Modulprüfungen bestehen ohne Skip, darunter drei neue Prüfungen
mit tatsächlichen angenommenen CRLF-Originalen. 31 ausgewählte native
Source4-/Source5-/Zahlungsprüfungen bestehen, ebenfalls drei neue Fälle mit
denselben Originalen. Die App-Analyse ist ohne Befund. Die Clientprüfungen
bestätigen vollständige Originalbindung und unveränderte v1-Zahlungspläne;
die Produktionsverträge beider Clients werden nicht abgeschwächt.

Die 16 Paketprüfungen bestehen. Der erste Lauf in der eigenen Arbeitskopie
fehlte ausschließlich wegen der dort nicht eingerichteten Backend-Virtualenv;
der gültige bestehende Interpreter ist anschließend ausdrücklich eingebunden.
Eine erste Analyse versuchte den Paket-Meldungsabruf im netzbeschränkten
Sandboxprozess; nach bereits erfolgreichem Offline-Lockbezug besteht
`flutter analyze --no-pub`. Die ursprünglichen Fehlprotokolle bleiben erhalten.

Der unabhängige Paketvergleich prüft den bereits heruntergeladenen Windows-
Archivdigest und alle 146 darin enthaltenen Python-Quellen gegen 2598c96,
bevor deren Code ausgeführt wird. Die tatsächlich veröffentlichten alten
Windows-Quellen reproduzieren beide vollständigen v6/v7-Originalrechnungen
und den ursprünglichen v1-Zahlungsplan exakt. Dies ist ein Quellenvergleich
unter Linux, keine neue Prüfung auf einem Windowsgerät. Die 32 bisherigen
2026-Rechenmodule bleiben bytegleich; der Beleg steht unter
`docs/evidence/oneoff-provenance-2026-11-09/unchanged-kernels.json`.

Diese Erweiterung ergänzt die bereits belegten v8-Faktor- und Reise-
Plattformnachweise. Sie implementiert keine neuen Steuerfälle, keinen
Mehrfachgruppen-Nettoabschluss und keinen Korrekturvertrag bereits bezahlter
Source5-Revisionen. Diese Fälle und die weiteren im Gesamtplan genannten
Lohn-/EÜR-Erweiterungen bleiben eigenständige aktive Arbeitspakete. Der Produktcode ist als 894ecdd gemeinsam mit der Übersichtskorrektur 4b8ec08
auf dem autorisierten Testbranch veröffentlicht. Seine eigenen Prüfungen
[Development42624525741](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42624525741) und
[iPhone42624525589](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42624525589)
laufen; ein Erfolg wird noch nicht behauptet. Der signierte Upload ist nicht
angefordert. Serverinstallation, Geräteprüfung und Gesamtabnahme A–G bleiben
offen. Die fünf zusätzlich gemeinsam integrierten Original-/Lese-/Zahlungs-/
EÜR-Prüfungen bestehen in 21,932 Sekunden.

Alle Rohprotokolle und der tatsächliche Windows-Quellenvergleich stehen unter
`docs/evidence/oneoff-provenance-2026-11-09/`. Der ursprüngliche Gesamtzieltext
bleibt unverändert.
