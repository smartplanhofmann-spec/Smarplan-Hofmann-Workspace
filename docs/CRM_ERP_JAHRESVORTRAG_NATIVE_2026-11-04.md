# Native belegte Jahresvorträge

Abnahme vom 04.11.2026 im isolierten Baum `smartplan-opening-year-values-20261104`. Die eigene Umsetzung ist abgeschlossen und für den unabhängigen Review eingefroren. Backend- und Browserdateien wurden nicht geändert. Keine Mainänderung und keine Commits.

## Anforderungen und Umsetzung

Die neue Seite öffnet belegte frühere Jahreswerte vom EÜR-Bereich. Sie unterstützt Originalupload und -download, Auswahl unveränderlicher bestätigter Altposten, vollständig erledigte externe Rechnungen mit ihren alten tatsächlichen Zahlungen und ausgeübter Vorsteuer, unabhängig eingegebene Journal-Kontrollsummen, Vorschau, ausdrückliche Annahme, Korrektur, Aufhebung und ursprüngliche Historien. Die gesonderte EÜR-Übernahme benutzt die bestehenden ausdrücklichen Prüf-, Perioden- und Gegenbuchungswege.

Alle Datums-, Betrags-, Steuersatz- und Kontofelder bleiben bei einem neuen Vorgang leer. Die kanonische Altpostenauswahl übernimmt ausschließlich die gewählte unveränderte Fassung. Erledigte externe Rechnungen benötigen ihre eigenen belegten vollständigen Werte. Ein eigenständiges Zeitraumjournal und drei ausdrückliche Prüfaussagen sind Pflicht. Die Kontrollsummen werden separat angegeben; die Vorschau prüft sie gegen die historischen Zeilen.

Der Parser bindet ursprüngliche Zahlungstage, Konten, Centwerte und ausgeübte Vorsteuer an die aufgelösten Rechnungshistorien. Kanonische Altposten werden zusätzlich aus ihrer exakten ursprünglichen Historienfassung gelesen; der heutige Kopf ersetzt diese Fassung nicht. Die Jahresquelle wird gegen die ursprüngliche Jahresfassung gebunden. Auch eine neu berechnete Antwortprüfsumme erlaubt weder verlegte Zahlungstage noch abweichende Centwerte oder Konten. Öffentliche kopierte Werte und projizierte Journalbeträge werden zusätzlich direkt gegengeprüft.

Historische Jahreswerte erzeugen keine neue Geldbewegung und keinen neuen Vorsteueranspruch. Die EÜR-Projektion erhält die ursprünglichen Tage, Konten und Beträge und bindet die angezeigte Zeitdeckung an die aktive originale Journalübernahme. Teilzeiträume bleiben unvollständig; ein fehlendes Jahresergebnis wird nicht als null angezeigt. Die Oberfläche beschreibt ausdrücklich die Grenze erklärter Journaldeckung gegenüber eigenständig bewiesener Vollständigkeit sämtlicher externer Altdaten.

Unvollständige heutige Profile bleiben lesbar. Die aktuelle technische `can_prepare`-Angabe wird von der fachlichen Freigabe eines neuen Editors getrennt. Fehlt heute der Starttag oder die Ist-/Sollangabe, bleibt der ursprüngliche historische Nachweis zugänglich. Eine bereits angenommene identische Anfrage kann ihre ursprüngliche Quittung unter heutigen Rechten/Gates wiedererhalten, ohne dass der Client dafür neue Profilwerte erfindet.

## Annahmen und Kontextwechsel

Der enge Sessionhook hält unbekannte Antworten mit exakt ursprünglichem Körper, Nonce und Quittungsprüfer offen. Er liest aktuelle Rechte und Finanzfreigabe erneut und verhindert einen noch nicht begonnenen POST nach einem Kontextwechsel während des Vorlaufs. Er erneuert keine alte Quell-/Profilreferenz beim Wiederholen. Serverseitige Gates bleiben maßgeblich.

Sitzungs-, Token-, Funktionsstand-, Schreib-/Leserechte- und Hintergrundwechsel verwerfen alte private Formulardaten und späte Antworten. Die Seite besitzt ihre eigenen Kontrollsummen-/Altzahlungsdialogrouten. Entfernen oder Ersetzen der Seite schließt genau diese Routen, ohne einen fremden Dialog zu schließen.

Originalbytes müssen zu Größe und SHA-256 passen. Der tatsächliche Desktop-Speicherweg liest nach dem Dateiauswahldialog unter aktuellen Rechten nochmals genau dasselbe geschützte Original, prüft erneut Größe und Hash und schreibt erst anschließend. Ein stiller Einzelquellenentzug bei erhaltenem globalem Recht verhindert die Ablage. Die bestehende mobile Dateiausgabe erhält den laufenden Kontextguard; sie wurde nicht auf einem Mobilgerät getestet.

## Tatsächliche Daten und Abhängigkeiten

API: [CRM_ERP_JAHRESVORTRAG_API.md](CRM_ERP_JAHRESVORTRAG_API.md).
Die unveränderte tatsächliche dreifache Kernfixture ist `docs/fixtures/accounting_year_values_v1.json`, identisch zur nativen Testkopie, SHA-256 `441f0665a27dd304f229dbf604c09f5463013c636c222c47cf8f581e3b7eb5d5`. Alle drei Szenarien werden gelesen: vollständiger Jahresvortrag mit tatsächlicher Folgezahlung, Teilzeitraum mit späterer Korrektur und erledigter externer Beleg.

Die separate zusätzliche Fixture `accounting_year_values_native_boundaries_v1.json` wird von `scripts/generate-accounting-year-values-native-boundaries.py` aus echten angenommenen Domänenvorgängen erzeugt. Sie belegt erhaltene alte Annahmen nach heute fehlendem Startdatum beziehungsweise `vat_timing=null`, einschließlich unmittelbar erhaltener Vorschau, Originalauftrag und tatsächlichem identischem Replay. Die Kernfixture wurde dafür nicht regeneriert oder verändert.

Die einzige kopierte Lesedependenz ist die final unabhängig geprüfte `business_accounting_open_items_contract.dart`, bytegleich SHA-256 `f07acfd9db354f5f7eabcce222b5d1a5b993209420b07c7c75ba83f28c6a9b9d`. Herkunft und finaler Altpostenreview sind in `reader-dependency.json` gebunden. Keine alte globale Datei wurde übernommen. Der EÜR- und Sessionanschluss ist als schmaler Patch gegen den nach SHA geprüften tatsächlichen Ausgangsstand dokumentiert.

## Testergebnisse und behobene Befunde

Der endgültige gemeinsame Lauf ist **59/59 grün**: **10 Vertragsfälle**, **21 Session-/Widget-/Lifecycle-/Desktop-/Profilfälle**, **ein tatsächlicher 390×844-HTTP-Ablauf** und **27 bestehende EÜR-/Accountingregressionen**. Die statische Analyse der fünf Runtime- und drei neuen Testdateien meldet **0 Probleme**.

Der tatsächliche HTTP-Ablauf führt Originalupload mit verlorener Annahmeantwort, unveränderten Replay, manuell ausgefüllte Quell-/Konten-/Buchungsidentitäts-/Kontrollsummenfelder, Vorschau, Jahresannahme mit erneutem Antwortverlust und die gesonderte EÜR-Buchung aus. Er bestätigt 59,50 historische Ausgaben und 19,00 bereits ausgeübte Vorsteuer bei null neuen Geldbewegungen. Er prüft die tatsächliche Sperre einer Quellenkorrektur bei aktiver EÜR-Übernahme, führt die ausdrückliche Gegenbuchung über die API aus, hebt die Originalquelle über die Oberfläche auf, nimmt die korrigierte Fassung an, liest das Original und die alte historische Quelle erneut und prüft abschließend einen tatsächlichen Leserechteentzug. Kein produktiver Kontakt und keine Steuerübermittlung.

Die erste 390-px-Abnahme fand einen zu breiten Wiederholungsbutton in einer Pendingkarte. Die Karte verwendet jetzt vertikale Zeilen. Scrollen konnte aufgeklappte Historien und Originale schließen; eigene stabile Speicherschlüssel erhalten den Zustand, und der auswählbare Originalhash besitzt einen separaten Schlüssel. Die roten Logs bleiben erhalten.

Der unabhängige Reviewer reproduzierte zwei offene Eingabedialoge nach Entfernen oder Ersetzen ihrer Seite. Daraufhin wurden die eigenen Dialogrouten gezielt verwaltet und geschlossen. Sein unveränderter roter Nachweis liegt getrennt unter `year-values-native-independent-2026-11-04`; sein abschließender Nachlauf wird dort eigenständig gebunden. Testseitige fehlende Scrollpositionen, Plattformdialogsteuerung und Prozessbereinigung wurden getrennt korrigiert und sind keine Produktbefunde.

Eigene endgültige Logs, Hashes und Integrationspatch: [Abnahmeverzeichnis](evidence/year-values-native-2026-11-04/README.md). Ein unabhängiger Review und Roots Integration bleiben separate Abnahmeschritte. Der Jahrespaket-v2-Adapter ist ein eigener Auftrag und wurde hier nicht geändert.
