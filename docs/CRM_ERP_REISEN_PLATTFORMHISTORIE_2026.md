# Alte Reiseabrechnungen zwischen Windows und Linux erhalten

Stand: 09.11.2026. Fortsetzung des Gesamtziels bei Reisekosten, Finanzübergabe
und Wiederherstellung. Die fachlichen Reiseberechner v1, v2 und v3 bleiben
bytegleich erhalten.

Eine auf Windows angenommene Reiseabrechnung kann nach dem Wechsel auf Linux
jetzt wieder aus ihren Originalquellen geprüft werden. Der umgekehrte Abgleich
ist ebenfalls geprüft. Die Korrektur umfasst Transportquellen der Versionen
v2/v3 sowie die Bodentages- und gemischten Programmquellen der Version v3.
Gespeicherte Originaldaten, Regel-/Faktenhashes, Quittungen und Exporte bleiben
unverändert. Vorschau und neue Annahme verwenden weiterhin die aktuelle native
Ausgabe der ausdrücklich gewählten historischen Regel.

## Konkreter Fehler und Prüfmethode

Die alten Reisequellnachweise enthalten rohe Dateihashes dreier unveränderter
Rechenmodule. Das veröffentlichte Windows-Paket besitzt CRLF-Zeilenenden, die
Linux-Quellen LF. Die fachliche Neuberechnung ergibt dieselben Tage, Quoten,
Pauschalen und Beträge, während Regel-/Faktenhashes voneinander abweichen.
Die bisherige vollständige Gleichheitsprüfung lehnte deshalb Originale ab.

Die Anwendung berechnet zuerst die gesamte Reise erneut. Der zusätzliche reine
Prüfer leitet höchstens acht Kombinationen der drei tatsächlich installierten
vertrauenswürdigen Module mit LF/CRLF ab. Für jede Kombination entstehen die
zusammengehörenden Regelhashes und alle abhängigen Faktenhashes erneut aus
der unveränderten Reise, den ursprünglichen Stätten, Zeitabschnitten und
berechneten Ergebnissen. Anschließend muss das gesamte Ergebnis exakt dem
Original entsprechen. Unbekannte Hashes, falsch zusammengefügte Nachweise,
andere Zeit-/Programmquellen und abweichende Geldbeträge bestehen diese Prüfung
nicht. Die alten v1-Ergebnisse behalten ihre bisherige exakte Gleichheitsprüfung.

Frische Mitarbeiter-/Datei-/Mandantenrechte, tatsächliche Annahmequittungen,
Belegung eines Reisetags, Zahlungsjournal und eingefrorene Exportbytes werden
weiter an ihren bisherigen Stellen geprüft. Der Prüfer verändert keine
globalen Rechenkonstanten und benötigt weder Unterprozess noch Netzwerk im
Produkt. Es gibt keine Migration oder Umschreibung alter Finanzdaten.

## Ausgeführte Prüfungen

Sieben neue Fachkettenfälle führen die vertrauenswürdigen Produktionsquellen
isoliert mit CRLF aus und nehmen deren Ausgabe über die tatsächliche private
Reisekette an. Unter LF bestehen anschließend Originalprüfung, Quittungswiederholung,
JSON/PDF-Export, Rechteentzug, tatsächliche Teilzahlungen, Bankabgleich und EÜR.
Eine gemischte Reise mit belegter Quote 2/3 ergibt ursprünglich 9,33 EUR.
Nach bestätigter Zahlung und begründeter Korrektur auf 9,00 EUR bleiben die
ursprünglichen 9,33 EUR erhalten; die Anwendung weist 0,33 EUR Überzahlung aus.
Es wird keine Rücküberweisung erfunden. Die bisherigen Exporte bleiben bytegleich.

Gezielte Gegenproben ändern Modul-/Fakten-/Regelhash, tauschen einzeln richtige,
aber nicht zusammengehörende Nachweise aus oder ändern Geldbeträge. Sie bleiben
abgewiesen. Eine tatsächliche Flugroute prüft beide historischen Versionen v2
und v3. Der umgekehrte LF-Originalabgleich unter CRLF ist enthalten.

Drei tatsächliche PostgreSQL-/MFA-/HTTP-Fälle bestehen ohne Skip: private
Reise-/Finanzgrenzen und Neustart, zwei konkurrierende Verbindungen mit genau
einer angenommenen Tagesbelegung/Zahlungsquittung sowie echter Dump/Restore
eines gemischten v3-Originals unter anschließendem v2-Standard. Die Originaldatei,
der öffentliche Geldfluss und das eingefrorene JSON bleiben erhalten. Der
ausschließlich hierfür angelegte Testcontainer ist danach entfernt.

Die tatsächlichen Chromiumabläufe für Reise v3 und das ebenfalls korrigierte
Unternehmensprofil bestehen mit MFA/HTTP, überprüfter Browser-Sandbox und
390-Pixel-Darstellung. 881 Browsermodule, 24 native Reiseprüfungen und 16
Paketfälle bestehen. Beide Clients lesen das tatsächliche alte CRLF-Original
mit erhaltenen Hashes; unvollständige Quellenreferenzen bleiben abgewiesen.
Die App-Analyse meldet keinen Befund. Das neue
Backendmodul ist in beiden Windows-Quelllisten und in der CI-Kopierliste enthalten.
Die gemeinsame Lohn-/Reiseregression besteht alle 687 unterschiedlichen Fälle
ohne Skip in 690,291 Sekunden. Die erste native Ausführung fehlte wegen der
noch nicht ausgewählten vorhandenen Compilerkette; anschließend verhinderte
die Dateisandbox lokale Test-Sockets. Die vollständige Wiederholung mit der
vorhandenen Compilerkette und genehmigten lokalen Sockets besteht. Beide
Fehlprotokolle bleiben erhalten.

## Unabhängiger Paketabgleich und weitere Grenzen

Das tatsächlich heruntergeladene Windows-Supportpaket auf 2598c96 ist gegen den
veröffentlichten Archivdigest, inneren ZIP-Digest und 146 enthaltene Repository-
Pythonquellen geprüft. Sein unveränderter alter Dispatcher erzeugt aus dem
eingefrorenen synthetischen Reiseoriginal exakt dieselbe CRLF-Reiseberechnung
wie der Testaufbau; der neue Prüfer bestätigt sie unter LF. Der gleiche Lauf
prüft weiterhin alte Faktor-Vollmonate v8 und plattformneutrale Teilmonate v9.
Diese Ausführung auf Linux ist keine Bedienung auf einem echten Windowsgerät.

Die Erstattungs- und Prüfverbesserung erweitert keine steuerlichen Reisefälle
und erklärt keine vollständige Lohn-/Buchhaltungsfreigabe. Alte rohe Dateihash-
Nachweise bei Einmalbezügen, weitere Faktor-/Minijob-/Versicherungsfälle,
Integrationen und Abnahmen A–G bleiben konkrete offene Arbeit.

[Genauer Nachweis, Rohprotokolle und Paketabgleich](evidence/completion-followup-2026-11-09/verification.json).

## Zugehörige CI-Korrektur

Der vollständige Browserlauf auf 3025747 brach im Unternehmensprofil ab, weil
ein Test den Antwortinhalt erst nach einem Seitenwechsel las. Er verwendet
jetzt die bereits im echten HTTP-Routenbeobachter gelesene Antwort. Der
gezielte Ablauf besteht mit tatsächlicher MFA, administrativem Profilrecht
ohne Finanz-Schreibrecht, verlorener Annahmeantwort, Rechteentzug und
unveränderten Finanz-/Offenpostenquellen. Es werden keine Fachantworten ersetzt.

Der separat fehlgeschlagene Simulatorjob auf 3025747 besitzt beim ersten
Logabruf nur eine GitHub-BlobNotFound-Antwort. Der ausdrücklich gestartete
Wiederholungslauf besteht inzwischen. Seine ursprüngliche Ursache bleibt damit
unbestätigt. 3025747 besteht sieben Development-Jobs und den unsignierten
iPhone-Build; sein alter vollständiger Browserjob bleibt als Fehler erhalten.
Die neue Softwareänderung benötigt eine eigene neue Gesamtprüfung.
