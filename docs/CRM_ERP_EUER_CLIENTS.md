# Eigene EÜR: Bedienablauf und Clientnachweise

Stand: 03.11.2026. Diese Umsetzung verbindet vorhandene Originalbelege und Geldflüsse mit einem eigenen fachlichen EÜR-/USt-Journal. Sie ist keine Abnahme des gesamten CRM-/ERP-Gesamtziels, keine amtliche Jahreserklärung und keine Zusage eines geprüften DATEV-Imports.

## Einstieg und vollständiger Ablauf

Im bestehenden Bereich **EÜR-Vorbereitung** öffnet Flutter über **Eigene EÜR: Quellen bis Jahresausgabe** die gemeinsame Arbeitsfläche. Der Browser integriert die eigene EÜR in den bisherigen Accounting-Bereich. Die vorhandenen Geldfluss-, Beleganteils- und Profilansichten bleiben erreichbar.

1. **Unternehmensprofil und Gültigkeit prüfen.** Einzelunternehmen/EÜR, Regelbesteuerung und Ist-Versteuerung müssen mit ihren tatsächlichen Gültigkeits- und Buchführungsdaten ausdrücklich bestätigt sein. Startdaten werden nicht vorgegeben. Die Jahresauswertung zeigt den bestätigten Buchführungsbeginn; eine fehlende zeitliche Abdeckung bleibt offen.
2. **Quellen vorbereiten.** Bestehende Kundenzahlungen mit dem Geldflussvorjournal verknüpfen; tatsächliche Lieferantenauszahlungen anhand von Original und Konto bestätigen. Fehlende dokumentarische Netto-/Steueranteile über die vorhandene Beleganteilsprüfung ergänzen. Eingangsoriginale können projektbezogen erfasst, geöffnet und geprüft werden. Der Wechsel aus der globalen EÜR in die Projektbelegprüfung lädt eigene aktuelle Projektrechte.
3. **Vorsteuerrecht getrennt prüfen.** Rechnungseingang, Leistungsdatum beziehungsweise vollständige Vorauszahlung, Eintritt der Voraussetzungen und abziehbaren Betrag ausdrücklich erfassen. Eine normale Vorsteuerentscheidung ist nicht vom späteren Geldflusstag abhängig. Auch ein Abzug von 0,00 ist eine fachliche Entscheidung. Für Vorauszahlungen muss die passende belegte Zahlung gewählt werden.
4. **Geldflüsse fachlich einordnen.** Jede vorhandene C1-/C2-/R1-/R2-Einheit wird genau einmal erfasst. Betrieblicher Netto-/Steueranteil, abziehbarer Nettoaufwand, bezahlte abziehbare Vorsteuer und gegebenenfalls als Kosten abziehbare Steuer bleiben getrennte Centbeträge. Die Oberfläche erfindet weder Abzugsquoten noch Kontonummern. Konten werden ausdrücklich als vierstellige SKR04-Zuordnungen eingegeben.
5. **Weitere belegte Sachverhalte erfassen.** Unterstützt sind gesonderte vollständige Umsatzsteuerzahlungen/-erstattungen, Geldeinlagen/-entnahmen und Darlehenshauptbeträge mit Original, tatsächlichem Geldkonto und eindeutiger Zahlungsnachweis-ID. Neue Anlagegüter benötigen belegte betriebliche Basis, Nutzungsbeginn und ausdrücklich gewählte lineare Nutzungsdauer. Die Jahres-AfA wird aus dieser Basis geprüft; sie erzeugt keine zweite Bankzahlung.
6. **Vorschau und Bestätigung.** Jeder der neun Vorgänge besitzt eine unverbindliche Vorschau. Diese zeigt die eingegebenen Fachangaben sowie die getrennten EÜR-, USt-, neutralen oder nicht abziehbaren Wirkungen. Erst die zusätzliche ausdrückliche Bestätigung erzeugt den unveränderlichen Journaleintrag.
7. **Berichtigen oder gegenbuchen.** Im Journal sind historische Angaben, Herkunft und Gegenbuchungsbeziehungen sichtbar. Eine Berichtigung erzeugt genaue Gegenposten und eine geprüfte Ersetzung; ein Storno hebt die bisherige Wirkung genau auf. Frühere Einträge bleiben erhalten. Abhängige Anlage-/Vorsteuerbuchungen und gesperrte Zeiträume werden vom Server geprüft.
8. **Monatsperiode und Jahr prüfen.** Eine Periode darf erst nach ausdrücklichem Kontenabgleich, bestätigter Originalvollständigkeit, Sonderfallprüfung und Auflösung der offenen Quellen geschlossen werden. Die begründete Wiederöffnung ist ein eigener Journalvorgang. Die Jahresansicht trennt bestätigte Summen von einem wegen offener Fälle nicht verfügbaren Gesamtergebnis.
9. **Jahresprüfpaket festhalten und speichern.** Ein eigener Exportvorgang friert Bericht, Journalstand, offene Fälle, Quellenmanifest und CSV ein. Im Journal lassen sich das unveränderte JSON-Prüfpaket und die CSV-Buchungsliste speichern. Ein späterer Eintrag ändert kein früheres Paket. Flutter prüft vor Dateiausgabe die Zugehörigkeit zum gespeicherten Eintrag sowie die SHA-256-Prüfsummen von Bericht und CSV.

## Fachliche Grenzen

Die unterstützten Regeln und Quellen stehen in `CRM_ERP_EUER_WORKFLOW_API.md` und `CRM_ERP_EUER_REGELQUELLEN_2026.md`. Die bestätigte Standardeinstellung von 19 % ersetzt keine Prüfung der einzelnen Quelle. Unterstützte gewöhnliche inländische 19-/7-Prozent-Ist-Umsätze werden aus ihren belegten Komponenten übernommen; aus einem Bruttobetrag wird keine Steuer geraten.

Ausland/Reverse Charge, besondere Privatnutzungs- und Vorsteuerberichtigungsfälle, Teilvorauszahlungen, GWG-/Sammelpostenwahlrechte, Anlageveräußerungen, Eröffnungsbestände sowie Sonder- oder degressive AfA sind keine durch diese Oberfläche zusätzlich behaupteten Automatiken. Die lineare Nutzungsdauer wird nicht aus einem Gerätenamen geschätzt. Die Quellen- und Jahresansichten bewahren offene Gründe und unbekannte Wirkungen. Bestätigte Zwischensummen belegen keine lückenlose Erfassung eines Unternehmensjahres.

An das EÜR-Journal gebundene Umsatzsteuer-/Privat-/Darlehensoriginale erscheinen als Zahlungsnachweis und nicht als offene Lieferantenverbindlichkeit. Auch nach einer Gegenbuchung bleibt dieser Originalzweck erhalten: Die externe Geldbewegung ist erneut einzuordnen; eine Vorsteuer- oder Anlagenaktion wird dafür nicht angeboten.

Geldkonten zeigen Zuflüsse, Abflüsse und Bewegungssalden. Unbekannte Anfangs- und Endbestände werden nicht ergänzt. Hier wird weder eine Bankbewegung ausgelöst noch an Finanzamt, DATEV oder Steuerberatung übermittelt.

## Rechte und unklare Antworten

Das globale Journal benötigt `accounting.read` und `finance.read`. Schreiben benötigt zusätzlich `accounting.prepare`, `accounting.admin` und `finance.write`, das aktive Finanzmodul und die betriebliche Schreibfreigabe. Projektbezogene Quellenrechte werden gesondert geprüft. Rechte-, Modul- und Datenstandswechsel verwerfen veraltete private Ansichten und Vorschauen.

Bestätigungen verwenden einen eingefrorenen Auftrag mit unveränderter Vorgangskennung. Eine verlorene oder unpassende Antwort entfernt diesen Auftrag nicht. Die Empfangsprüfung vergleicht Kommando, Vorschau, Gegenbuchungen, Profil, Ergebniswirkungen und Paket-/Periodennachweis, bevor der offene Auftrag entfernt wird. Wiederholung lädt aktuelle Rechte und verwendet den ursprünglichen Inhalt auch über einen geänderten Datenstand hinweg. Mehrdeutige 403/404/409 bleiben offen; nur ein ausdrücklich als nicht angenommen bestätigter Konflikt löst den offenen Auftrag.

Eine aus der EÜR geöffnete Projektbelegprüfung nutzt eine untergeordnete Sitzung derselben Anmeldung. Ihre offenen Aufträge überleben den Rückweg zur EÜR; Abmeldung oder Widerruf der übergeordneten Sitzung räumt sie auf. Dies ist eine Wiederaufnahme innerhalb derselben laufenden Anmeldung, keine Zusage eines dauerhaften geräteübergreifenden Offlinejournals.

## Ausgeführte Flutter-Prüfungen

Gezielter gemeinsamer Lauf: **66/66 Tests bestanden**. Nach dem letzten Quellenvertrag zur Abgrenzung von Zahlungsnachweisen wurden die **7/7 EÜR-Tests erneut erfolgreich** ausgeführt. Darin enthalten sind **7 neue EÜR-Tests** und **59 bestehende Accounting-/Profilregressionen**. Die statische Analyse der fünf neuen/geänderten UI-/Testdateien meldet **keine Befunde**.

Die sechs neuen Unit-/Widgettests prüfen Centbeträge ohne Rundung, fehlende automatische Startdaten/Konten, frische Rechte, Generationenwechsel, falsche Bestätigungen, erhaltene Vorgangskennungen bei mehrdeutigen Fehlern, ausdrücklich nicht angenommene Konflikte, den vollständigen Cash-Eingabedialog mit Bestätigung, Wiederaufnahme nach Seitenschluss, Korrektureinstieg, eine 390-Pixel-Jahresansicht und die Navigation in die Projektbelegprüfung einschließlich Aufräumen ihrer offenen Aufträge bei Widerruf. Ein eigener Widgetfall prüft, dass gebundene Zahlungsnachweise keine Lieferantenverbindlichkeit und keine unpassenden Vorsteuer-/Anlageaktionen erzeugen.

Die zusätzliche echte Flutter-HTTP-Kette läuft gegen Flask/WSGI und isolierte SQLite-Domänen mit synthetischen Daten. Nur die archivierte Ausgangsrechnung stammt aus dem bestehenden ausdrücklich synthetischen SQLite-Ausstellerfixture; dies ist kein Produktionsfreigabenachweis für Rechnungsausstellung oder PostgreSQL. Alle EÜR-Vorschauen, Bestätigungen, Quelldaten, Berichte und Wiederholungen gehen durch den tatsächlichen HTTP-/Domänencode.

Geprüfter Referenzfall: 119,00 Einnahme, 59,50 bezahlter Lieferant und anschließend separat belegte 9,50 Finanzamtszahlung ergeben 50,00 EÜR. Das Vorsteuerrecht wird separat gebucht. Eine neue Anlage mit 1.200,00 Basis, 36 Monaten Nutzungsdauer und Beginn im Dezember ergibt 33,33 Jahres-AfA und ein gespeichertes Jahresergebnis von 16,67. Nach späterer Gegenbuchung bleibt das frühere Prüfpaket byteinhaltlich unverändert, während der aktuelle Jahresbericht die offene Einordnung mit unbekanntem Gesamtergebnis zeigt. Getestet sind außerdem Korrektur, Monatsabschluss, gesperrte Gegenbuchung, Wiederöffnung, tatsächlich verlorene/verfälschte Antworten nach Speicherung und unveränderte Wiederholung ohne Duplikat sowie geprüfte JSON-/CSV-Dateiinhalte und Ablehnung eines manipulierten Pakets. Der tatsächliche HTTP-Vertrag zu gebundenen Zahlungsnachweisen wird vor und nach einer externen Gegenbuchung geprüft.

Nachweise:

- `app/test/business_accounting_euer_test.dart`
- `app/test/business_accounting_euer_http_test.dart`
- `app/test/euer_fixture.dart`
- `work/verification/euer-flutter-final.log`
- `work/verification/euer-flutter-final-analyze.log`
- `work/verification/euer-flutter-final-targeted.log`

Ausführung aus `app`: `flutter test --no-pub test/business_accounting_euer_test.dart test/business_accounting_euer_http_test.dart test/business_accounting_test.dart test/business_accounting_profile_test.dart`.

Die Browserprüfungen und ihre eigenständigen Nachweise stehen in `CRM_ERP_EUER_BROWSER.md`. Eine Installation oder Abnahme auf physischen Endgeräten wird durch die beschriebenen Tests nicht behauptet.
