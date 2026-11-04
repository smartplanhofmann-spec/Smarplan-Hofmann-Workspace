# Unabhängige Prüfung der nativen Jahresvorträge

Stand: 4. November 2026. Prüfbaum: `/workspace/smartplan-opening-year-values-20261104`.

Die abschließenden **23 eigenen Tests bestehen**. Die statische Analyse der eigenen Testdatei meldet keine Probleme. Zwei konkrete Produktbefunde wurden vor der Korrektur reproduziert und mit unveränderten roten Nachweisen gesichert. Der Implementierungsowner behob beide; der Reviewer änderte keine Produktdateien. Dieser Bericht ist eine gezielte unabhängige Prüfung des engen Jahresvortragsvertrags, keine Freigabe zusätzlicher Steuerfälle oder produktiver Meldungen.

## Befunde und Nachprüfung

1. Der private Kontrollsummeneditor blieb nach Entfernen seiner Seite bei erhaltenem Navigator beziehungsweise nach Austausch der Sitzung geöffnet. Die Originaltests und das rote Protokoll liegen unter `docs/evidence/year-values-native-independent-2026-11-04/original-dialog-*`. Die Seite verwaltet jetzt ihre konkrete Dialogroute. Die unveränderten ursprünglichen Erwartungen bestehen; zusätzlich wurden Rückkehr aus dem Hintergrund und das Entfernen der Seite unter einer fremden, erhalten bleibenden Dialogroute geprüft.
2. Eine originale Void-Korrektur wurde von `BusinessSession.yearValuesCommand` mit 423 gesperrt, sobald im aktuellen Profil der Buchführungsbeginn fehlte. Die tatsächliche Backendfolge war bereits zulässig: ursprünglicher Vortrag → EÜR-Zuordnung → dokumentierte 409-Sperre der Aufhebung → tatsächliche EÜR-Gegenbuchung → heute fehlender Beginn → neue Aufhebung mit ursprünglichem Profil und ursprünglichem Inhalt. Eine separat erzeugte SQLite-Fixture enthält diese Antworten und unveränderten historischen Bezüge. Der enge Sessionfix erlaubt diesen Void-Confirm bei weiterhin aktuellen Rechten, Kontextprüfungen und serverseitiger Originalprüfung. Neue aktive Annahmen und Aufhebungen ohne Schreibrechte bleiben in eigenen Gegenfällen gesperrt. Originalrepro, rote Ausgabe und vollständiger damaliger Sessionstand liegen unter `original-void-*` beziehungsweise `session-before-void-fix.dart`.

Der ursprüngliche Owner-Handoff `35bd199a…fabadfa` bleibt historisch erhalten. Der Nachlauf bindet den additiven Runtime-Freeze `ce865b8e…d6cdd`; nur der Sessionhook wurde gegenüber dem ursprünglichen Owner-Freeze verändert. Sein vollständiger neuer SHA-256 lautet `3d07efc7ec86a1e36c903127b7454901ca3b3d53941fdf1515a0de4857fb0d1a`.

## Geprüfte Original- und Fachbindungen

- Sechs tatsächliche Manipulationen wurden trotz korrekt neu berechneter Preview-Prüfsumme zurückgewiesen: alter Zahlungstag, alter Zahlungscent, Netto-Buchungsbetrag, Buchungskonto, ursprünglicher Vorsteuerzeitpunkt und Zeitpunkt des bereits ausgeübten Vorsteuerabzugs. Die unveränderte ursprüngliche Belegquelle blieb jeweils erhalten. Dadurch prüft der Test die Bindung an diese Quelle und nicht lediglich einen veralteten äußeren Hash.
- Der unveränderte Ausgangsfall enthält am 20. August 50,00 Euro Nettoausgabe auf 5400 und 9,50 Euro gezahlte Vorsteuer auf 1406 sowie die getrennte historische Vorsteuerwirkung von 19,00 Euro am 11. Juni. Der dokumentierte alte Abzugstag bleibt der 10. Juli. Die Übernahme erzeugt weder eine aktuelle Geldbewegung noch einen neuen Vorsteueranspruch.
- Die private Altpostenoriginalhistorie bleibt für die Verifikation erforderlich. Ein gültiger, aber anderer Originalfall darf sie nicht ersetzen.
- Fehlende Kontrollsummen beziehungsweise fehlender Originaljournalbeleg werden zurückgewiesen. Ein separat tatsächlich angenommener Nulljournalfall besitzt dagegen einen ausdrücklichen Originalbeleg und die vereinbarten Erklärungen; dessen gültige Übernahme wird nicht mit fehlenden Belegen gleichgesetzt.
- Die tatsächlichen Zustände `bookkeeping_start=null` beziehungsweise `vat_timing=null` bleiben mit ihren historischen Einträgen lesbar. Die ursprünglichen Quittungen behalten ihren damaligen vollständigen Profilbezug. Aktuelle fehlende Konfiguration wird nicht als fachliche Freigabe neuer Vorträge interpretiert.

## Native Abläufe und Grenzen

Sieben eigene Widgetfälle prüfen die beiden ursprünglichen Dialogfehler, die Rückkehr aus dem Hintergrund, einen fremden Dialog sowie die tatsächliche Desktop-Dateiauswahl bei Hintergrundwechsel, Sitzungsaustausch und einem echten Dateischreibfehler. Die Dateiprüfungen verwenden den Produkt-Exportpfad und eine echte temporäre Datei; sie ersetzen nur den Systemdialog. Bei verworfenem Kontext wird keine Datei angelegt. Bei einem Schreibfehler erscheint der Fehlerzustand.

Der erste erweiterte Nachlauf hatte eine fehlerhafte Lifecycle-Sequenz im eigenen Test (`paused` unmittelbar zu `resumed`) und prüfte die Dialogentfernung noch während pausierter, unterdrückter Frames. Dieses Harnessproblem ist ausdrücklich kein zusätzlicher Produktbefund. Das ursprüngliche Zwischenprotokoll bleibt erhalten; der finale Test benutzt die gültige Folge über `hidden` und `inactive` und beobachtet die Rückkehr in die sichtbare App. Produktcode wurde dafür nicht geändert.

Der Implementierungsowner meldet separat 59/59 Fälle einschließlich seines tatsächlichen HTTP-Ablaufs und der EÜR-/Accounting-Bestandsprüfungen. Diese 59 werden nicht als eigene Tests gezählt. Der unabhängige Lauf umfasst 16 Vertrags-/Sessionfälle und sieben Widgetfälle; die zwei zusätzlichen Backend-Fixtures wurden zuvor durch echte SQLite-Domainabläufe erzeugt. Keine PostgreSQL-Nutzung und keine Geräte- oder Storeabnahme erfolgte in diesem Review.

## Reproduzierbarkeit

Eigene Tests: `app/test/business_accounting_year_values_independent_review_test.dart`. Eigener Generator: `scripts/generate-year-values-native-independent-fixture.py`. Die zusätzliche tatsächliche Fixture hat SHA-256 `ded46003dda3e608fee62710c306a2134dd6a2ba61abe3d8203556d9628efcbc`; die bestehende Kernfixture `441f0665…eb5d5` wurde nicht regeneriert oder verändert. Ein erneuter Generatorlauf erstellt neue synthetische Identitäten und ersetzt deshalb nicht die historische Prüfgrundlage.

Der finale Lauf steht in `work/verification/year-values-native-independent-final-second-2026-11-04.log`; die finale Analyse in `year-values-native-independent-analysis-final-second-2026-11-04.log`. Das Manifest unter `docs/evidence/year-values-native-independent-2026-11-04/manifest.json` bindet Lauf, Originalbefunde, Fixtures, Generator, Testdatei, die fünf gelesenen nativen Produktdateien und den unveränderten fachlichen Backendstand. Keine Hauptprojektänderung und kein Commit erfolgten durch den Reviewer.
