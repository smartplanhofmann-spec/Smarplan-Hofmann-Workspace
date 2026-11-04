# Service und Betriebsmittel – native Kontextkorrektur integriert

Auf `d5f1978` schließen die beiden nativen Seiten private Ansichten und eigene
Dialoge bei Sitzungs-/Quellwechsel, Rechteverlust, Hintergrundwechsel und Abbau
der Seite. Späte Originalantworten und Fehlermeldungen füllen keine inzwischen
ersetzte Ansicht. Eine fremde darüberliegende Route bleibt erhalten. Bereits
unbestätigte Originalaufträge bleiben in ihrer ursprünglichen Sitzung.

Vier tatsächliche ursprüngliche Widgetgegenfälle wurden vor dem Fix rot
gesichert. Der isolierte Bearbeiter ergänzte die beiden Seiten und einen
optionalen Kontextguard in genau zwei Wiederholungsmethoden der gemeinsamen
Session. Root übernahm die Seiten unverändert und wandte ausschließlich diesen
Methodenpatch auf die aktuelle Session an. Jahresvortrag, Assistent, Ereignisse
und sonstige Sessionabläufe bleiben bytegleich außerhalb dieser beiden Methoden.

## Nachprüfung

35 betroffene Tests bestanden auf dem endgültigen Stand in 11,468 Sekunden:
20 ursprüngliche/erweiterte Kontextfälle, 13 bestehende Service-/Betriebsmittelfälle
und zwei neue tatsächliche lokale HTTP-Fälle. Die vollständige App-Analyse meldet
keine Befunde (9,869 Sekunden). Der
[Gesamtnachweis](evidence/service-equipment-integrated-regression-2026-11-04.json)
bindet die endgültigen Quellen, Originalfehler und Protokolle.

Die zwei HTTP-Fälle starten einen wirklichen lokalen Pythonserver mit
Wegwerfdatenbank und verwenden den nativen Produkttransport. Je ein Service-
Statuswechsel bzw. eine Betriebsmittelprofiländerung wird tatsächlich angenommen;
erst danach unterdrückt der Test die erfolgreiche Antwort. Während der
anschließenden vorbereitenden Leseabfrage wird der Ansichtskontext geschlossen.
Kein zweiter POST erfolgt, und der Originalauftrag bleibt offen. Eine spätere
ausdrückliche Wiederholung übermittelt exakt denselben Body und dieselbe Nonce,
liefert dieselbe Annahmequittung und erzeugt keine weitere Fachversion. Die
vorherige Originalversion bleibt in der Historie erhalten.

Diese HTTP-Strecke nutzt synthetische angemeldete Sitzungen und den bereits
verwendeten lokalen Proxy-Testumschlag. Sie ist keine neue MFA-/TLS-/Geräteabnahme.
Die Widgets prüfen unter anderem ein Windows-Ziel; reale Windows-/iPhone-Geräte
und die vollständige mobile Bedienabnahme bleiben gesondert offen.

Der erste 35-Fälle-Lauf war bereits grün. Danach wurden die temporären
Python-Fixturedaten ausdrücklich im übergeordneten Testverzeichnis untergebracht,
damit die Testbereinigung sie mit entfernt. Der ursprüngliche Testtext und die
ersten Logs bleiben erhalten; derselbe vollständige betroffene Umfang und die
Analyse bestanden nach dieser reinen Testaufbaukorrektur erneut.

Keine Backend-/Browser-Produktdatei, Fachstruktur, Finanzregel oder Paketliste
wurde geändert. Finanzhorizont 15/Bericht 16 und 144/213 Paketpfade bleiben
erhalten. Frühere vollständige App-/Backend-/PostgreSQLnachweise behalten ihre
jeweiligen Quellstände; es wird keine erneute vollständige Matrix behauptet.

Der Bearbeiter wurde vor seiner abschließenden HTTP-Prüfung durch ein Nutzungslimit
gestoppt. Root führte diese beiden echten HTTP-Fälle und die Zusammenführung zu
Ende; eine zusätzliche neue externe unabhängige Abnahme wird nicht behauptet.
R07.07, betriebliche Geräte-/Prüfnachweise und Gesamtabnahmen A–G bleiben offen.
Keine Produktivmigration, Zahlung, Meldung, externe Nachricht oder Bereitstellung.
