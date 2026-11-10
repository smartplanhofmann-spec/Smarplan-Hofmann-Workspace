# Faktor-Einmalbezug V15: Originalquellen, Bedienung und Nachweise

Stand10.11.2026. Der neue begrenzte Faktor-/P4-Einmalfall ist lokal mit eigenem
Jahresquellenvertrag, privater Fallführung, Source4-Lauf, Lohnkonto, tatsächlicher
Zahlung, Cash/EÜR, Jahresfortschreibung und reduziertem Mitarbeiterbeleg verbunden.
Die tatsächlichen PostgreSQL-/MFA-/Konkurrenz-/Restore- sowie Browser-/Appabläufe
sind geprüft. Die vollständige lokale Appprüfung besteht mit1.971 Fällen. Veröffentlichung,
eigene neue Remote-CI, Serverinstallation, Geräte- und Fachabnahme sind getrennte
Nachweise. Keine Bankzahlung, amtliche Meldung oder Produktivfreigabe ausgelöst.

## Bereits tatsächlich geprüft

`backend/payroll_factor_oneoff_2026.py` berechnet STS, SOLZS und BKS für einen
sonstigen Bezug2026 mit ausdrücklich belegtem Faktor der KlasseIV. BKS ist
die Kirchensteuerbemessung, nicht die landesspezifische Kirchensteuer.
Begrenzter Erstumfang: gesetzliche Pflichtversicherung, keine zusätzlichen
Jahresfrei-/Hinzurechnungsbeträge, Alters-/Versorgungs-/Entschädigungsfälle.
Ein tatsächlicher Faktor0.000 bleibt von einem fehlenden Faktor unterschieden.

344 synthetische Grenz-/Zufallsfälle werden unabhängig aus den unveränderten
Dezimalausdrücken der fest gehashten PAP-XML in Java erzeugt. Der Runner
importiert keinen Produktionslohncode. XML-SHA256:
`63d8981646d139eba2f4dd990c13b43c4fb3883b402a5a40cddf253aa7aa96b4`.
Der dokumentierte Spiegel ist an einen festen Commit gebunden; ein direkter
offizieller XML-Download oder eine amtliche Softwarefreigabe wird nicht behauptet.
Alle344 Ausgaben stimmen centgenau überein. Originalfaktor-/Standard- und
Einmalbezugskerne bleiben unverändert. Die neue Quellenprovenienz ist mit
tatsächlichen CRLF-Kopien beider beteiligten Dateien portabel geprüft.

Der Faktor wird auf die unskalierte Jahressteuerdifferenz angewendet, danach
erfolgt die PAP-Abrundung auf volle Euro. Zwei vorher einzeln faktorisierte
Jahressteuerbeträge dürfen nicht voneinander abgezogen werden. Die gesonderte
kinderbereinigte, faktorisierte Jahresbemessung entscheidet über SOLZS.
Laufender Lohn wird nicht nochmals als Einmalbezug versteuert.

Eine zusätzliche tatsächliche API-Gegenprobe bindet einen gespeicherten
V12-Faktor-/P4-Fall an die alte geplante Jahresbasis. Der bestehende V1-Vertrag
verweigert dies ausdrücklich mit409 und verlangt einen eigenen Jahresvorschau-
vertrag. Keine Jahres-, Lohnlauf- oder Cashzeile wird erzeugt. Diese Grenze
bleibt erhalten; ein umetikettierter oder umgerechneter V5-Schattenfall wäre
keine gültige neue Originalquelle.

## Integrationsvertrag und Prüfpunkte

1. Explizit versionierte Jahresvorschau für tatsächliche Faktor-Originalfälle.
   Originale Profile, ELStAM-Identitäten, Beschäftigung, P4, Jahresperioden,
   bereits erfolgte Zuflüsse und echte Zukunftsvereinbarungen unverändert
   binden. Alte V1-Originale und ihre Pläne bleiben unverändert nachrechenbar.
   Der erste neue Jahresvertrag unterstützt nur nachgewiesene Fälle; weitere
   Faktor-/Midijob- oder Untermonatsfälle erhalten keine bloße Freigabeflagge.
2. Neue versionierte Einmalbezugszusammensetzung für einen tatsächlichen
   unveränderten Faktor-/P4-Monatsfall, einen eigenen Anspruch und seine
   vollständigen Jahres-/Steuerprognosen. Steuer und SV bleiben getrennt.
   Märzklausel, historische Beitragssätze und vorhandene Jahresbezüge müssen
   aus echten Perioden stammen. Bestehende Brutto-/Netto- und Kirchensteuer-
   Erhaltungsgleichungen sowie frische Originalprüfungen übernehmen.
3. Private Fall-/Vorschau-/Laufwege explizit registrieren. Vorhandene globale
   Anspruchsverbrauchsgrenze muss über alte und neue Regelversionen hinweg
   doppelte Einmalbezüge verhindern. Korrektur und unveränderte Wiederholung
   nach verlorener Antwort dürfen keine zweite Zahlung erzeugen.
4. Jahresbasis, reduzierte Mitarbeiterbelege, Lohnkonto, Zahlungen, Bankabgleich
   und EÜR mit ihren tatsächlichen Quellen verbinden. Neue Regel-/Umfangspaare
   in beiden Beleglesern ausdrücklich ergänzen, unbekannte Paare weiter sperren.
5. Browser und native App mit Originalauswahl, Vorschau und ausdrücklicher
   Bestätigung ergänzen; aktuelle Rechte und verlorene Antworten prüfen.
   Tatsächliche PostgreSQL-/MFA-/Konkurrenz-/CRLF-/volle Restorekette sowie
   gemeinsame Schlussprüfung vor Veröffentlichung abschließen.

Die nachstehenden Integrationsnachweise ergänzen den reinen Steuerbaustein.
R09.03/D und die Gesamtabnahmen werden dadurch nicht abgeschlossen.
Gewählte Banken/Lieferanten und deren bereits abgeschlossene Codearbeit
bleiben parallel im [aktuellen Arbeitsstand](CRM_ERP_ARBEITSSTAND.md) erhalten.

## Integrationsnachweis im laufenden Arbeitsstand10.11.

Der neue V2-Jahresweg besteht69 gemeinsame Backend-/Paketfälle208,674s und
einen tatsächlichen MFA-/PostgreSQL-/Konkurrenz-/Restorefall25,482s. Die neue
Zusammensetzung verwendet außerdem12 unabhängige XML-Steuergegenwerte für
die tatsächlichen Testprofile; positiver STS/SOLZS ist ausdrücklich geprüft.
Zehn neue/alte private Falltests44,262s bestehen. Neue/alte Laufprüfung fand
zunächst die fehlende ausdrückliche Abschlussumfangsfreigabe; Erstfehler bleibt
erhalten. Nach gezielter Ergänzung bestehen die tatsächliche Netto-/Abgaben-/
EÜR-Kette und Originalwiederholung sowie der bereits bezahlte laufende
Originalbetrag mit ausschließlich zusätzlicher Bonusdifferenz. Fünf gemeinsame
CRLF-/Quellen-/Zahlungsfälle17,588s bestehen.57 alte Lohnmodule bleiben erhalten.

Der vollständige neue PostgreSQL-/MFA-Fall besteht76,023s (Runner77,791s): zwei
wirkliche konkurrierende Fall- und Laufbestätigungen erzeugen jeweils nur ein
Original und einen Anspruchsverbrauch. Tatsächlicher Zahlungsbeleg, Netto-Cash,
EÜR, abgeschlossene Jahresbasis, reduzierter Mitarbeiterbeleg, Original-PDF,
Sicherung, vollständige Wiederherstellung, exakte Quittungswiederholung,
Sperre der alten Sitzung und neue echte MFA-Anmeldung bestehen. Die eigene
512MiB-tmpfs-Datenbank ist nach exakter ID-/Label-/Loopbackprüfung entfernt.
Kein Kundenserver oder Originalbestand wurde verändert.

Explizite Quellenwege /payroll/annual-facts/factor-v2 und
/payroll/one-off-cases/factor-v15 sind lokal angebunden. Die alte V1-/V6-Grenze
bleibt erhalten; keine V5-Schattenquelle. Der Source4-Lauf wählt seine Regel
aus dem tatsächlich autorisierten gespeicherten Original. Gemeinsame
Anspruchsidentität und Verbrauchstabellen verhindern einen zweiten Eigentümer.

Der Mitarbeiterbeleg besitzt eine eigene Schema5-Projektion mit bekannten
Regel-/Umfangspaaren. Beide Leser prüfen tatsächliche API-/PDF-Fixtures;
keine privaten Jahresquellen oder Faktoren im Mitarbeiterbeleg.36 gemeinsame
Browserverträge1,085s und sieben native Vertrags-/Beleg-/390px-Fälle bestehen.
Erster nativer Sandboxlauf konnte keinen lokalen Testsocket öffnen; der gleiche
Lauf mit regulärer Ausführungsfreigabe besteht. Neue private Oberflächenauswahl
und getrennte Wiederholungskennungen sind eingebaut. Ihre tatsächliche
Browser-/App-Bedienung, Freigabeentzug und gemeinsame Schlussprüfung laufen
noch. Daher noch keine Veröffentlichung oder vollständige V15-Clientabnahme.

Die Nutzerpräzisierung Kreissparkasse Rottweil / Amex Business und die auf
später verschobene Loxone-Hostfreigabe sind im Hauptprojekt unter
[Bank-/Lieferantenverträgen](CRM_ERP_BANK_LIEFERANTEN_ANBINDUNGEN_2026-11-10.md)
festgehalten. Sie ersetzen keine tatsächliche Bank-/Lieferantenfreischaltung.

## Bedienung und aktuelle gemeinsame Prüfung

Nach Aktualisierung von Server und Client unter Personal die betreffende Person,
danach Personalakte/Lohnberechnung öffnen. **Faktor-Jahresbasis und Steuerprognose**
öffnet ausschließlich die beiden dafür geprüften Jahresquellenarten. Der geplante
Einmalanspruch wird weiterhin im gemeinsamen ursprünglichen Jahresquellenbereich
angelegt. Anschließend **Faktor-Einmalbezugsfälle** öffnen, Zuflussmonat und genau
die ursprünglichen Monats-/Anspruchs-/Jahresfassungen auswählen, Vorschau prüfen
und ausdrücklich bestätigen. Der belegte ELStAM-Faktor bleibt sichtbar. Die
anschließende Lohnfreigabe und der tatsächliche Zahlungsnachweis sind eigene
Vorgänge. Keine Werte oder fehlenden Quellen werden aus einem anderen Fall ersetzt.

Neue Varianten besitzen getrennte Vorgangskennungen und feste Pfade. Der echte
Browsernachweis hat einen gemeinsamen Wiederholungsrouterfehler gefunden:
Der neue Fall wurde nach verlorener erfolgreicher Antwort zunächst zur allgemeinen
Lohnwiederholung geschickt. Der Router ist gezielt ergänzt; der rote Erstablauf
bleibt erhalten. Der tatsächliche Schlussablauf besteht mit zwei unveränderten
wiederholten Quittungen, Original-PDF, echter reduzierter Schema5-Belegnavigation,
eigenständigem Mitarbeiter-PDF, unveränderter Historie und390px. Während der
Mitarbeiterbelegnavigation wird kein privater Lohn-/Jahres-/Personalaktenpfad gelesen.

1.086 vollständige Browserverträge28,681s ohne Fehler/Auslassungen bestehen.
28 gemeinsame native Formular-/Original-/Belegfälle und sechs neue native
Faktor-/Jahres-/Wiederholungsfälle bestehen; Entzug der aktuellen Freigabe räumt
die private Ansicht, und eine pausierte Fachfunktion erlaubt nur die unveränderte
angenommene Wiederholung. Ein tatsächlicher gespeicherter Zahlungsbeleg wird
auch durch den gemeinsamen Browser-/App-Lohnkontoleser geprüft.

Die gemeinsame Backendgruppe endet mit48 ausgeführten Fällen298,029s, davon47
bestehend und einem wegen Sandbox-Socketrechten nicht startbaren alten HTTP-Test.
Genau dieser Fall besteht mit regulärer Loopback-Freigabe1/6,157s. Der Erstlauf
wird nicht nachträglich als vollständig grün bezeichnet.31 Paket-/CI-/Inventar-/
Quellarchivfälle32,201s und der tatsächliche eingefrorene MFA-Archivstart1/4,929s
bestehen.153 Abhängigkeitskomponenten stimmen exakt mit der bestehenden Stückliste
überein; keine neue Laufzeitabhängigkeit. Abschließende Appanalyse: keine Probleme.
57 historische Lohnmodule und das23863-Byte-Originalziel sind unverändert.

## Abschluss der lokalen Appprüfung

Die tatsächliche vollständige lokale App-Suite endet mit1.971 bestandenen Fällen
in21:48. Der nachträglich gezielt ergänzte ursprüngliche Zahlungsbeleg-/Lohnkonto-
leser besteht zusätzlich in drei nativen und fünf Browserfällen.62 Rohdateien
einschließlich der ursprünglichen roten Versuche sind nach Länge und SHA geprüft.
Veröffentlichung und eigene neue Remoteprüfungen werden nach tatsächlicher
Ausführung separat festgehalten. Gesamtsoftware, weitere Provider-/Lohnfälle
und reale Abnahmen bleiben offen; keine pauschale Gesamtfertigmeldung.
