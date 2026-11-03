# Reiseabrechnung 2026 – belegter Implementierungsstand

Stand 03.11.2026. Der Backendstand implementiert die vollständige veröffentlichte
2026-Tabelle, eigene Reiseakten und tatsächliche Erstattungsnachweise. Er ist
keine Behauptung, dass sämtliche steuerlichen Sonderfälle oder das gesamte
CRM/ERP bereits abgeschlossen seien.

## Anforderungen und Ergebnis

| Paket | Umgesetzt | Noch erforderlicher Abschluss |
| --- | --- | --- |
| T1 | 214 Auslandspositionen plus Inland, getrennte Kurz-/Voll-/Übernachtungssätze; >8h und Tagesaddition; Fristphasen/28 volle Tage/Monatsende; einzelne Nächte; Mahlzeiten/Eigenentgelte/Ersatz/60-EUR-Grenze; vollständiger Flug-/Schiffsnachweis mit Ortsdaten | Gemischte Privat-/Dienstreise und reine Boden-Ortsdatumsgrenze folgen als eigene v3-Entwicklung; derzeit konkrete Fachblocker |
| T2 | Unveränderliche Stätten/Reisen, eigene Einreichung und fremde Freigabe, Vorschau/Quellendrift/Originalexport, private Statusquittung, tatsächliches MFA/HTTP, heutige Personal-/Projekt-/Dateirechte | Client-Endabnahme dokumentiert der Clientverantwortliche separat |
| T3 | Belegte Auslagenaufteilung, gegenseitige Sperre gegen alte Erstattung, tatsächliche Teil-/Rückzahlung, Korrektur/Void, Finanzübernahme alter tatsächlicher Zahlung, öffentliche Quelle ohne private Reisedaten, EÜR/Bank-Integration | Der neue v5-Lohnlauf muss steuerpflichtige/M-Quellen wirklich verarbeiten; bis dahin bleibt die betroffene Auszahlung gesperrt |
| T4 | Acht additive Tabellen/Guards, Export-/Privacy-/Paketeinbindung, Finanzhorizont11/Bericht12; echte parallele PostgreSQL-Schreiber; additive Migration und echtes Dump/Restore | Neue v3-Zweige und neue Lohnverarbeitungsverknüpfung benötigen eigene Endprüfungen |

`de_travel_2026_v1` und `de_travel_2026_v2` sind eigene eingefrorene Rechenmodule.
Historische Fassungen werden mit ihrer ursprünglichen Version rekonstruiert.
V2 bindet den isolierten Transporthelper mit dessen tatsächlichem Modulhash.
Die Ratentabelle ist als Webtexttranskription gekennzeichnet; ein heruntergeladenes
amtliches PDF oder dessen Hash wird nicht vorgetäuscht. Die unabhängige Prüfung
hat alle 214 Namen/Regionen und 642 Betragszellen verglichen.

## Finanzielle Bedeutung

Eine Freigabe ist kein Geldfluss. Neue Erstattung und tatsächliche Rückzahlung
benötigen Betrag, Datum, ausgewähltes EUR-Geldkonto und geschütztes Original.
Altes und neues Datum bei Korrektur müssen in offenen EÜR-Perioden liegen.
Eine dokumentarische Aufhebung liefert aktuell keine Geldbewegung, während die
historische Fassung unverändert bleibt. Eine Korrektur darf keine tatsächlichen
Rückzahlungen ohne entsprechend belegte Auszahlung stehen lassen.

`adopt_legacy` ergänzt Konto und Original einer alten tatsächlichen
Auslagenzahlung. Ursprünglicher Betrag/Tag/Richtung/Referenz bleiben unverändert;
es wird weder eine zweite Auszahlung ausgelöst noch verfügbare Kapazität
verbraucht. Der erste historische Zahlungsnachweis und alle Originalpositionen
werden nachgeprüft. Private oder schon gestellte Anteile dürfen nicht über die
steuerfreie Finanzquelle abgezogen werden.

TravelCash zahlt ausschließlich den steuerfreien Anteil. Steuerpflichtige
Erstattungsmehrbeträge gehören genau einmal in den neuen Lohnlauf. Mahlzeiten-
Sachbezüge erhöhen die einschlägigen Bruttobasen mit gleichem Nettoabzug; M allein
ist kein zusätzlicher Geldbetrag. Aktuelle Lohnfreigabe und unveränderlicher
historischer Verarbeitungsnachweis sind getrennte Funktionen.

## Tatsächlich ausgeführte Prüfungen

Die maschinenlesbaren Ergebnisse und Hashes stehen in
`CRM_ERP_REISEPAUSCHALEN_PRUEFUNG_2026-11-03.json`. Der aktuelle PostgreSQL-Lauf
bestand aus vier echten Fällen: MFA/HTTP plus Runtime-/Migrator-Guards und
Neustart; zwei unabhängige Verbindungen für Tagesexklusivität und identische
Zahlungsquittung; alte Personaloriginale unverändert migriert und tatsächlich
gesichert/wiederhergestellt mit Finanzhorizont11/Bericht12; tatsächliche
Altzahlungsübernahme mit unverändertem HR-Original und getrennter Auszahlung nur
des übrigen Pauschalenbetrags. Alle vier Fälle bestanden in 15,752 Sekunden.
Der letzte vollständige gezielte v2-Fachlauf umfasst 74 bestandene Prüfungen in
9,821 Sekunden. Die zusätzlich verschärfte ursprüngliche Auslagenhistorie wurde
anschließend mit 19 Fällen in 7,710 Sekunden geprüft. Überlappende Läufe werden
nicht als zusätzliche unterschiedliche Testfälle addiert.

Nach dem Cloud-Neustart bestanden zwei tatsächliche MFA-/HTTP-Reisefälle erneut
in 1,065 Sekunden. Der vollständige wiederholte Browserlauf
`work/verification/travel-browser-resumed-final.log` bestand einschließlich
Altzahlungsübernahme, Konto-Korrektur, dokumentarischer Aufhebung und
ausdrücklicher EÜR-Berichtigung. Der vorausgegangene Browserlauf hatte beim
Katalogabruf einen HTTP-500-Fehler. Er wurde im Wiederholungslauf nicht
reproduziert; eine konkrete Fehlerursache oder ein Produktfix dafür ist nicht
nachgewiesen. Der erste Fehlernachweis bleibt getrennt erhalten.

Die getrennte v3-Entwicklung und ihre bislang 17 isolierten Fachtests sind im
`CRM_ERP_REISE_V3_VERTRAG_2026.md` dokumentiert. Sie ändern weder den aktiven
v2-Standard noch historische Berechnungen.

Die Fachprüfungen enthalten unabhängig formulierte Gegenfälle und anschließend
geschlossene Fehler: zu frühes Monatsfristende, falsches M bei >60-Essen,
Heimaufenthalt als Abwesenheit, unbelegte Nächte, negative Zahlungsnettos,
erneute Auszahlung nach niedrigerer Korrektur, erfundene Mitarbeiterversion und
veränderte Originalreservierung. Die Finanzgegenprüfung deckt tatsächliche
Reise→EÜR→Bank-Ketten und beide Richtungen der Doppelreservierung ab.

Es wurden keine echten Personal-/Bankdaten, Providerübertragungen oder
Produktionsauszahlungen verwendet.
