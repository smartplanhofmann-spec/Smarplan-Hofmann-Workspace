# Kilometererstattung im gemeinsamen Produktstand

Backend ae0c851, beide Clients 44eaab0 und der unabhängige Folgefix 03fbded
sind mit Materialrückgabe und dem vorherigen Gesamtstand zusammengeführt.
Die beiden Importlisten und Workflowzweige sind als Vereinigung aufgelöst;
Material- und Kilometerablauf bleiben gleichzeitig erreichbar. Der bisherige
TravelCommand-Standardpfad bleibt erhalten.

## Unterstützter Ablauf

Eine tatsächlich abgeschlossene rein dienstliche Inlands-Rundfahrt 2026 im
privaten Pkw eines Mitarbeiters: gebundene Stätten, Fahrzeug-/Streckenoriginale,
ganze Meter, sechs ausdrücklich abgegebene Erklärungen und unabhängige Freigabe.
30 Cent je Kilometer werden einmal auf der Gesamtstrecke centgenau gerundet.
Arbeitsweg, Dienstwagen, gemischte/private Fahrt, Unternehmer-Eigenfahrt und
weitere Fallgruppen gehören nicht zu diesem engen Vertrag.

Freigabe, tatsächliche Zahlung und spätere Korrektur sind getrennt. Ein
100-km-Original mit tatsächlich gezahlten 30 EUR bleibt bei einer Korrektur
auf 50 km unverändert. Erst die belegte tatsächliche Rückzahlung von 15 EUR
vermindert Geldfluss und EÜR. Es entsteht keine automatische Überweisung oder
zusätzliche Nettolohnzahlung. Die alten Reisepfade übernehmen V4 nicht als V3.
Historische Originale bleiben mit aktuellen Leserechten erreichbar.

[Vertrag](CRM_ERP_KILOMETERERSTATTUNG_VERTRAG_2026.md),
[Backendprüfungen](CRM_ERP_KILOMETERERSTATTUNG_BACKEND_PRUEFUNG_2026.md),
[beide Clients](CRM_ERP_KILOMETERERSTATTUNG_CLIENTS_2026.md).

## Unabhängiger Doppelbelegbefund und Abschluss

Der erste Kandidat reservierte nur den Hash einer ganzen Originalmenge.
Zwei unabhängige Fälle konnten deshalb einen verwendeten Teil X durch eine
neue Kombination `{X,Y}` nochmals tatsächlich freigeben: anderer Tag oder
andere Person. Es wurden keine Zahlungen ausgeführt.

Der Folgefix schützt jedes einzelne Original-SHA, berücksichtigt alle
erhaltenen V4-Fassungen einschließlich tatsächlicher alter Bündelclaims und
behält die eigene Korrekturkette. Die ursprünglichen Altzeilen werden nicht
umgeschrieben. Beide unveränderten Root-Gegenproben werden nun tatsächlich
mit 409 abgewiesen; genau ein ursprünglicher Abschluss und null Zahlungen
bleiben bestehen. Der Blocker gibt keine fremde Quellenreferenz aus.
[Vorher und Nachher](CRM_ERP_KILOMETER_TEILBELEG_REVIEW_2026-11-09.md).

## Gemeinsame Ergebnisse

| Prüfung | Tatsächliches Ergebnis |
| --- | --- |
| Alle Browsermodultests | 992 bestanden, kein Fehler/Skip, 13,367 Sekunden |
| Acht native Kilometer-/Reise-/Material-/Beleg-/Preis-/Offline-/Service-Suiten | 65 bestanden, kein Fehler/Skip, 52 Sekunden im Fortschrittslog |
| Gesamte Appanalyse | Kein Befund, 23,7 Sekunden |
| Root-Doppelbelegfälle, Kilometerkern, Fach-/HTTP- und Paketprüfungen | 45 bestanden, 45,165 Sekunden |
| Tatsächlicher früherer Bündelstand, Originalquittung und eigene Korrektur | Ein Fall bestanden, 0,842 Sekunden |
| Tatsächliche Browserabläufe auf dem gemeinsamen letzten Produktstand | Materialrückgabe, Kilometererstattung und datierte Katalogpreise jeweils vollständig bestanden |

Der Kilometerbrowserablauf verwendet zwei MFA-Akteure, drei tatsächlich
verlorene angenommene Antworten, private Originale, Korrektur, erhaltene alte
Zahlung, tatsächliche Rückzahlung, EÜR 30→15 EUR, PDF/Verlauf und 390px-Ansicht.
Die eigenständigen tatsächlichen PostgreSQL-/Konkurrenz-/Bank-/Archiv-/Restore-
Nachweise des Folgefixes bleiben im Backendbericht separat erhalten.

App- und Browserdateien sind nach ihren genannten gemeinsamen Läufen nicht
geändert. Alle 32 historischen Rechenmodule, ursprüngliche Zahlungsarithmetik,
Clientfixture 30c0d238… und das Originalziel sind erneut bytegleich geprüft.
[Vollständige Rohlogs und genaue Quellstände](evidence/mileage-integration-2026-11-09/verification.json).

Ein neuer vollständiger Remote-/Geräte-/Produktivnachweis folgt daraus noch
nicht. Der vorherige vollständige App-Lauf betrifft genau 8273852 mit 1.770
Fällen und drei separat bestandenen nativen PDF-Fällen. Offene Clientaufträge
dieses Onlineablaufs liegen bislang im Arbeitsspeicher der aktuellen privaten
Sitzung. Prozessneustartpersistenz ist keine gelieferte Eigenschaft.

Der gemeinsame Stand ist als 19ec4e9 auf dem autorisierten Testbranch
veröffentlicht. Die eigenen vollständigen Remoteprüfungen laufen:
Development42670555279 und iPhone42670554193. Update und HTTPS bestehen im
ersten Abruf, alle übrigen Jobs sind noch offen. Dieser Zwischenstand ersetzt
keinen Abschluss; Server und echte Geräte sind nicht neu abgenommen.
[Veröffentlichung und tatsächlicher erster Abruf](evidence/mileage-integration-2026-11-09/publication-initial.json).
