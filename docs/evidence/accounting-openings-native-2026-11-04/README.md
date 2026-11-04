# Native Anfangsbestände: Umsetzungs- und Prüfnachweis

Stand: 4. November 2026. Isolierter Arbeitsbaum `/workspace/smartplan-financial-opening-20261104`. Keine Produktivkontakte, keine tatsächlichen Unternehmensbestände und kein Git-Commit durch diesen Teilauftrag.

## Umgesetzte Anforderungen

Die globale Buchführungsansicht öffnet den Anfangsbestandsbereich; jedes Geldkonto besitzt einen gezielten Einstieg. Der EÜR-Arbeitsbereich verweist bei vorhandenem serverseitigem `opening_balances_path` auf diese getrennte Sicht. Bestehende EÜR-Ergebnisse und der CompanyOverview-Vertrag bleiben unverändert.

Der native Client liest den tatsächlichen Quellenstand, nimmt unveränderte Bestandsoriginale an und prüft deren Empfangsquittung gegen Dateiname, Typ, Größe und SHA-256 der gewählten Bytes. Er zeigt eine ausdrücklich gewählte Original- oder Bankauszugsquelle. Eigene Beträge beginnen leer. Ausgewählte Bankauszüge liefern ihren unveränderlichen Saldo automatisch. Beginn und Profilfassung stammen ausschließlich aus dem bestätigten Buchführungsprofil. Vorschau, Bestätigung, Berichtigung und Aufhebung sind an die tatsächliche Quellen-, Profil-, Konto- und Journalfassung gebunden.

Liquidität wird für den sichtbaren, editierbaren Stichtag dargestellt; der Anfangswert ist der aktuelle UTC-Kalendertag. Fehlende Bestände bleiben unbekannt. Kontobewegungen, Bankanschlüsse, bekannte Teilsumme und Gesamtbestand werden centgenau nachgerechnet. Negative Kassenbestände müssen ungeklärt bleiben. Die Gegenrechnung eines Bankanfangssaldos verwendet nur vorangehende Tagesbewegungen; ein Endsaldo enthält die Bewegungen seines Tages. Ein passender Vortags-Endsaldo ist zulässig. Aggregatrechnung verwendet BigInt; die getrennte Begrenzung einzelner Original-/Vorschaubeträge bleibt erhalten.

Nicht eindeutig quittierte Original- und Bestätigungsaufträge bleiben im Sitzungsspeicher. Wiederholung verwendet unverändert den ursprünglichen vollständigen Auftrag, die Vorgangskennung und den ursprünglichen Quittungsprüfer. Ein verlorener Empfangsnachweis erzeugt keine zweite Buchungsfassung. Neue Rechte-/Finanzfreigaben werden vor Wiederholung geprüft.

Read-Entzug entfernt Konto, Originalnamen, Verlauf, Vorschau und Draft; der AppBar-Titel enthält generell keine privaten Kontodaten. Quellen- und Vorschauantworten führen vor Anzeige eine abschließende aktuelle Rechteprüfung aus. Originalbytes werden nach Empfang und vor Export erneut geprüft. Sitzungsersatz und verzögerte Antwort sind an die tatsächliche Session, Generation, Token und Ansichts-Epoche gebunden. Hintergrundwechsel (`paused`, `hidden`, `detached`) leeren die private Ansicht. Nach Rückkehr ist ein explizites Neuladen erforderlich.

## Tests und Grenzen

Der fokussierte Satz umfasst reale, vom Backend erzeugte Vertragsdaten sowie kontrollierte transportbedingte Fehlerfälle. Die Widgetfälle prüfen gehaltene State-, Quellen- und Previewantworten, den Dateidialog nach Kontextverlust, Sessionersatz, Hintergrundwechsel mit verspäteter Antwort sowie den automatisch übernommenen Bankbetrag.

Der HTTP-Widgettest startet tatsächlich `online.web.create_app` mit isolierter SQLite-Datenbank und dem bestehenden synthetischen lokalen HTTPS-/Host-Proxyumschlag. Bei 390 × 844 Pixeln führt ein ausdrücklich berechtigter regulärer Buchhaltungsnutzer durch echten PDF-Upload, negativen Bankanfangsbestand, angenommene Bestätigung mit anschließend verlorenem Empfangsnachweis, identische Wiederholung, bytegenauen Originalexport, Korrektur auf ausdrücklich null und dokumentierte Aufhebung. Der Server bestätigt genau drei historische Fassungen. Ein separater Administrator entzieht danach tatsächlich `bank.read`; die native Oberfläche entfernt ihre privaten Inhalte.

Der native HTTP-Test nutzt einen synthetischen Core-Login. Er belegt kein eigenes MFA-Enrolment und keine reale Betriebssystem-Dateiauswahl oder tatsächliche Speicherung außerhalb des Testprozesses; Picker und Exportziel werden injiziert, die ausgewählten PDF-Bytes kommen jedoch aus einer tatsächlichen temporären Datei. Der separate Browsernachweis ergänzt den tatsächlichen MFA-Ablauf. Sämtliche Daten sind synthetisch; es wird kein Bestand von Smartplan Hofmann behauptet.

`focused-before-aggregate-review.txt` enthält die erste abgeschlossene Abnahme mit 14/14 Tests. `regressions.txt` enthält 73/73 bestehende Buchhaltungs-, EÜR-, Bank- und Sitzungstests. Die anschließende Prüfung des tatsächlichen Aggregatgrenzfalls und die endgültigen Hashes/Resultate stehen im abschließenden Manifest. Dieser Nachweis schließt weder die separat geplante Übernahme alter Anlagegüter noch das gesamte CRM-/ERP-Gesamtziel ab.

Die endgültige native Abnahme umfasst **15/15** bestandene Fälle (7 Verträge, 7 Widgets/Lifecycle, 1 tatsächlicher HTTP-Ablauf), **73/73** vorhandene Regressionen und einen Analyzer ohne Befund. `focused-final.txt`, `analyze-final.txt` und `manifest.json` halten den finalen Stand einschließlich beider tatsächlich erzeugter großer positiver und negativer Salden fest. Einzelbetrags- und Quellenlimits bleiben unverändert.
