# Reisen und Pauschalen – Browser und Flutter

Implementierungsstand 03.11.2026. Die beiden Personaloberflächen öffnen die
belegten Reisen unter **Reisen und Pauschalen**. Der
[API-Vertrag](CRM_ERP_REISEPAUSCHALEN_API.md), der
[Transportvertrag](CRM_ERP_REISE_TRANSPORT_VERTRAG_2026.md) und die
[Fachgegenprüfung](CRM_ERP_REISEPAUSCHALEN_GEGENPRUEFUNG_2026.md) bleiben die
maßgeblichen fachlichen Quellen. Dieser Nachweis betrifft die Clientintegration;
er erklärt nicht das gesamte CRM/ERP oder alle Veröffentlichungsplattformen für
abgenommen.

## Belegtes gemischtes Reiseprogramm und örtlicher Kalender (v3)

Neue Reiseabrechnungen verwenden die abgestimmt aktivierte Regelversion
`de_travel_2026_v3`. Gespeicherte v1-/v2-Abrechnungen behalten ihre ursprüngliche
Berechnung und Originale. Der
[v3-Vertrag](CRM_ERP_REISE_V3_VERTRAG_2026.md) beschreibt den fachlichen Umfang.

Im Reiseentwurf führt **Programmbeurteilung bearbeiten** zu den tatsächlichen
Originalen des Gesamtprogramms und dessen Prüfvermerk. Über **Programmpunkt
hinzufügen** wird jeder berufliche oder private Programmpunkt mit Anfang, Ende,
Ortszeitzone, ausdrücklich gewählter Art und eigenen Originalen erfasst.
Die Ortszeit wird durch den vorhandenen Server-Zeitnachweis aufgelöst; bei einer
doppelten Uhrzeit muss die tatsächliche Zeitlage gewählt werden. Die tatsächlichen
Privatzeiten werden zusätzlich unter **Private Reiseabschnitte** eingegeben.

Nachdem alle Punkte vollständig erfasst sind, wird die Programmbeurteilung
erneut geöffnet. **Das gesamte berufliche und private Programm ist vollständig
belegt** und **Die Originalkosten sind getrennt beruflich, privat und bereitgestellt
geprüft** sind zwei ausdrückliche Prüfbestätigungen. Hinzufügen, Ändern oder Entfernen
eines Programmpunkts setzt beide Bestätigungen zurück. Die Bedienoberfläche
berechnet keine gewünschte Quote und schlägt keine Tatsachen oder Belege vor.

Bei der fremden Freigabe zeigt die Tagesherleitung die Bemessung vor Aufteilung,
den belegten beruflichen Bruch und die anschließende Mahlzeitenkürzung. Die
Programmherleitung nennt tatsächliche berufliche/private Sekunden und die Anzahl
der Originalnachweise; der Ortskalender zeigt je Datum Abwesenheit und Zeitzone.
Auslagen behalten ihre gesondert belegte berufliche/private Zuordnung und werden
nicht nochmals mit der Programmquote multipliziert. Die Quellen sind an genau
die gewählten Reisefassungen gebunden, auch in historischen Abrechnungen.

Eine Privatzeit ohne vollständige Beurteilung wird als konkreter Fachblocker
angezeigt. Separate Urlaubsverlängerungen ohne belegtes Gesamtprogramm sowie
verschiedene Programmquoten mehrerer Reisen am selben Tag bleiben gesperrt,
bis eine passende belegte Abgrenzungsmethode vorhanden ist.

Der tatsächliche v3-Domainprüffall bindet 14 EUR × 2/3 = 9,33 EUR Pauschale,
separat 6 EUR berufliche Originalauslage und damit 15,33 EUR steuerfreien Umfang.
Eine dokumentierte Zahlung von 10 EUR und die spätere Korrektur des beantragten
Verpflegungsbetrags verändern die ursprüngliche Historie nicht. Das native
gerenderte Formular prüft das erneute Bestätigen des Programms und unveränderte
Auslagen- sowie Privatzeitreferenzen. Die detaillierten Testnachweise werden
getrennt vom früheren v2-Abnahmestand geführt.

Ausgeführt unter aktivem v3: 19 Node-Tests, 22 Flutter-Tests und statische
Analyse von zwei Dart-Dateien ohne Befund. Zwei vollständige echte Browserläufe
bestanden: der neue Programm-/Kalender-/JSON-Originalablauf und der bestehende
Reise-/Altzahlungs-/EÜR-Gesamtablauf. Die mobile Ansicht wurde zusätzlich visuell
geprüft. Ein sichtbarer `null`-Platzhalter für eine nicht verfügbare Altzahlungsaktion
wurde dabei entfernt; der abschließende Browserlauf prüft dessen Abwesenheit.
Die erste neue Historien-Testassertion wartete nicht auf den asynchronen Dialog:
dieser Testfehler ist samt ursprünglichem Log erhalten, die Wartebedingung
korrigiert und der komplette Ablauf erneut bestanden. Das ist kein Nachweis
einer Ursache des früheren, gesondert dokumentierten Katalog-HTTP500.

Dauerhafte Logs, Prüfumfang, Grenzen und Dateihashes:
[`evidence/travel-v3-clients-2026-11-03.json`](evidence/travel-v3-clients-2026-11-03.json).

## Umgesetzte Eingaben und Quellen

Browser `web/office/travel-allowances.js` und Flutter
`app/lib/business_travel_allowances.dart` besitzen dieselben fachlichen Schritte:

- Stätten mit Anschrift, Land/Gebiet aus dem Backendkatalog, Zeitzone,
  Zuordnungsgrund, Gültigkeitsdaten, vollständig belegter Vorgeschichte und
  Originaldateien. Geänderte Einsatzhäufigkeiten haben eigene datierte Phasen
  einschließlich Originalzuordnung; eine historische Wochenhäufigkeit wird
  nicht aus Projektstunden abgeleitet.
- Reisegrunddaten und wiederholbare Stationen, Mahlzeiten, Außenübernachtungen
  und private Intervalle. Datum und Uhrzeit bleiben ohne tatsächliche Angabe
  leer. Die Zeitauflösung erfolgt mit tatsächlicher IANA-Zone auf dem Server;
  doppelte Ortszeiten verlangen eine Auswahl, nicht existente Zeiten bleiben
  ein Fehler.
- Zusammenhängende Flugverbindungen mit tatsächlichen Abflug-/Ankunftsstätten
  und konkreten notwendigen Zwischenübernachtungen. Schiffsreisen binden ihre
  Abschnitte, Ein-/Ausschiffungsorte, Rolle und belegte Hochseeabschnitte. Die
  private Wohnung steht für diese Verkehrsorte nicht zur Auswahl.
- Unterkunftsart einschließlich Fahrzeug, Schlafwagen und Schiffskabine sowie
  ausdrücklich belegtem Beginn/Ende in anderer Unterkunft. Ein Unterkunfts-
  original kann genau einer bereits erfassten Auslagenposition zugeordnet werden.
- Vorhandene tatsächliche Auslagen werden pro Original in beruflich, privat und
  bereitgestellt aufgeteilt. Die Summe muss centgenau den gespeicherten Betrag
  ergeben. Bereits erstattete Auslagen bleiben als bezahlt gebunden.
- Einreichen, fremde Prüfung, Tagesvorschau mit konkreten Blockern, gesonderter
  vorgesehener Zuflussmonat steuerpflichtiger Mehrbeträge und unveränderliche
  Freigabe. Ein erforderlicher Lohnschritt wird ausdrücklich angezeigt. Die
  Oberfläche berechnet keine eigenen Steuerpauschalen.
- Historische Fassungen und geprüfte Originaldownloads; gespeicherte PDF-/JSON-
  Dateien werden über Dateigröße und SHA256 kontrolliert. Die angezeigte
  historische Tagesrechnung wird ausdrücklich als Stand ihrer Fassung benannt;
  spätere Zahlungen haben eigene Nachweise.

Es gibt keine JSON-Freitextfelder. Die Daten werden durch benannte Formulare,
Auswahllisten und wiederholbare Zeilen erfasst. Euroangaben werden zu exakten
Integer-Cents geparst. Alte `de_travel_2026_v1`-Ansichten verlangen keine erst in
v2 eingeführten Auslagensummen.

## Tatsächliche Zahlungen und frühere Auslagenzahlungen

Neue tatsächliche Erstattung und Rückzahlung verlangen einen belegten Tag,
Betrag, Referenz, ein ausdrücklich gewähltes aktuelles Geldkonto und ein
unverändertes geschütztes Zahlungsoriginal. Es wird kein Bankauftrag ausgelöst.
Eine dokumentarische Aufhebung behält die ursprünglichen Zahlungsdaten bei;
sie erzeugt keine erfundene Rückzahlung. Neue Anspruchsfassungen und neue
Geldbewegungen bleiben getrennte Vorgänge.

Die zusätzliche Aktion **Bereits belegte Auslagenzahlung für Finanzen
übernehmen** wählt eine konkrete Zahlung aus den gebundenen alten Auslagen.
Datum, Zahlungsart, Betrag und Referenz bleiben gesperrt. Der Benutzer ergänzt
nur Geldkonto und geschütztes Finanzoriginal. `legacy_payment` bindet
Auslagenfassung, Index und Hash des ursprünglichen Zahlungseintrags. Diese
Übernahme zählt den bereits bezahlten Anspruch nicht nochmals. Korrektur und
Aufhebung behalten diese Originalbindung; die Aufhebung betrifft allein die
Finanz-Nachweisübernahme und lässt die ursprüngliche tatsächliche Zahlung
bestehen. Der Backendvertrag erlaubt diesen Weg ausschließlich für vollständig
berufliche Originalauslagen.

## Private Befehle und Sitzungswechsel

Die Reisecontroller speichern vollständige private Aufträge nur im eigenen RAM.
Sie verwenden weder die allgemeine Office-Befehlsliste noch die allgemeine
`BusinessSession`-Zwischenspeicherung. Jeder Auftrag hat vor dem Versand eine
feste Ziel-ID und Nonce. Die Statusbestätigung prüft Akteur, Mitarbeiter,
Operation, Ziel, Revision, kanonischen Anfragehash und Ergebnis-Hash.

Eine verlorene Antwort erzeugt keine neue Zahlung. **Status prüfen** liest die
ursprüngliche Quittung. Ein ausdrücklich ausgelöstes erneutes Senden liest
zuerst denselben Status; eine bereits angenommene Quittung wird ohne zweiten
POST übernommen. Nur ein weiterhin unbestätigter Auftrag kann mit genau
unverändertem Body und derselben Nonce wiederholt werden. Ein 404 allein löscht
keinen Auftrag. Frische Rechte und Aktivierung werden vor erneutem Schreiben
geprüft. Akteur-/Mitarbeiter-/Sitzungswechsel, Schließen der privaten Ansicht und
Hintergrundwechsel verwerfen die privaten Eingaben.

Lokale Flutter-Eingabefehler haben einen normalen Validierungsstatus. Sie dürfen
nicht als ungeklärter Netzwerkabbruch die Felder sperren. Bei tatsächlicher
Befehlsunsicherheit erläutert der Editor den unveränderten erneuten Versuch;
dessen Controller liest zuerst den Status. Die gesonderte Statusaktion bleibt
in der privaten Übersicht verfügbar.

## Finanzoberflächen

`travel-cash.js` und `business_travel_cash.dart` prüfen ausschließlich den
öffentlichen `travel_cash`-Vertrag. Private Zusatzfelder werden auf Quellen-,
Geldbewegungs-, Konto- und Kategorieebene zurückgewiesen. Aktive Quellen besitzen
genau einen tatsächlichen Geldfluss; aufgehobene Quellen keinen. Kalendertage
werden auf tatsächliche Existenz geprüft, nicht nur auf ihr Textformat.

EÜR und Bankabgleich verwenden diese öffentlichen Quellen ohne Import des
privaten Reisecontrollers. Eine Reisequelle benötigt eine ausdrücklich gewählte
SKR04-Einordnung. Die Kategorie ist ausschließlich `travel_allowance`, ohne
Vorsteuer. Aufgehobene Quellen werden mit leeren Sachkonten ausdrücklich
berichtigt. Frühere öffentliche Fassungen bleiben lesbar. Der tatsächliche
Browsernachweis verwendet außerdem einen Buchhalter ohne Personal-Leserecht.

## Prüfstand und Reproduktion

Der abschließende maschinenlesbare Nachweis liegt unter
`docs/evidence/travel-clients-2026-11-03.json`; dort stehen Testbefehle,
Dateihashes und dauerhafte Logpfade. Die zusätzlich von Root erstellten
öffentlichen Finanzgegenproben bleiben separat unter
`docs/evidence/travel-finance-integration-2026-11-03.json` erhalten.

Der eingefrorene v2-Clientstand besteht mit **44/44 Node**, **44/44 Flutter**,
Analyze ohne Befunde in sieben betroffenen Dateien und dem vollständig
abgeschlossenen echten Reise-Browserablauf. Dieser umfasst zusätzlich die
Kontokorrektur und dokumentarische Aufhebung einer übernommenen alten
Auslagenzahlung einschließlich ausdrücklicher EÜR-Berichtigung. Das
ursprüngliche HR-Zahlungsereignis und die ursprüngliche Reiseabrechnung bleiben
dabei unverändert.

Ein früherer letzter Browserlauf hatte beim erneuten Laden des Reisekatalogs
einen HTTP500-Fehler. Nach dem Cloud-Neustart wurden im synthetischen Testserver
datensparsame Fehlerdiagnosen ergänzt und derselbe vollständige Ablauf unter
einem neuen Lognamen wiederholt. Der Endlauf ist grün; die frühere Ursache wurde
nicht reproduziert und wird daher nicht als nachgewiesen behoben bezeichnet.
Der erste Fehlerlog bleibt neben dem bestandenen Endlauf erhalten.

`app/test/fixtures/travel_allowances.json` enthält echte synthetische
Domainantworten, erzeugt durch `web/office/tests/travel_fixture.py`. Sie bindet
unter anderem 14 EUR Pauschale plus 6 EUR beruflichen Anteil eines 10-EUR-
Originals, 4 EUR privaten Anteil, eine gesonderte Verkehrs-Stätte sowie eine
vorher vollständig erstattete berufliche Auslage. Browser und Flutter prüfen
kanonische Originalquittungen derselben Daten.

Die tatsächliche Chromium-Prüfung läuft über echte Anmeldung mit MFA, Flask,
HTTP und eine wegwerfbare SQLite-Datenbank. Sie prüft eigene Erfassung, fremde
Freigabe, Original/PDF, Teilzahlungen, verlorene Bestätigungen ohne doppelten
POST, öffentliche EÜR, historische Zahlungsaufhebung und Berichtigung,
Altzahlungsübernahme sowie die 390-Pixel-Ansicht. Namespace-, PID-, Netzwerk-
und Seccomp-Sandbox werden vor dem Anwendungszugriff geprüft. Der Loopback-
Transport ist keine TLS-Abnahme und kein Produktivbetrieb.

Die Flutter-Prüfung enthält echte gerenderte Formulare, Centfehlerkorrektur,
unveränderte Flug-/Auslagenreferenzen, Altzahlungsübernahme und
Hintergrundbereinigung. Zusätzlich laufen die betroffenen bestehenden EÜR-,
HTTP-, Bank- und Personaltests. Reale Windows-/iPhone-/Android-Geräteabnahmen,
Veröffentlichung und zusätzliche freie steuerliche Sonderfälle werden durch
diesen Clientnachweis nicht behauptet.
