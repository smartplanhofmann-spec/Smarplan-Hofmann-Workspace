# Jahresnachweis mit Originalen im Browser

Arbeitsstand 04.11.2026 im isolierten Baum
`/workspace/smartplan-year-review-export-20261104`. Der Client setzt den
[Jahrespaketvertrag](CRM_ERP_JAHRESPAKET_VERTRAG_2026-11-04.md) und die
[tatsächliche v1-API](CRM_ERP_JAHRESPAKET_API_2026.md) um. Er ergänzt einen
vorhandenen, ausdrücklich angenommenen unveränderlichen EÜR-Jahresexport.
Keine Gesamtfertigmeldung, keine Steuererklärung und keine Auslieferungsbehauptung.

## Bedienung und Fachgrenzen

Im gespeicherten Jahresprüfpaket führt **Jahresnachweis mit Originalen öffnen**
zum Paket mit aufgelösten Originalen. Sichtbar sind Jahr, Originalexport und
sein Hash, die gebundene Unternehmensinstanz, Originalanzahl, ZIP-Größe und die
separate ZIP-Prüfsumme. Die Anzeige trennt die technische Paketverfügbarkeit von
der damaligen fachlichen Vollständigkeit der erfassten Quellen und der nicht
behaupteten Vollständigkeit des gesamten Unternehmensjahres.

Offene Quellen bleiben ausdrücklich offen. Für enthaltene öffentliche Lohn- und
Reisefinanzquellen wird die bewusste Grenze zu privaten Personaloriginalen
angezeigt. Enthält der ursprüngliche Report diese Quelltypen, darf die
Paketantwort ihre entsprechende Grenze nicht weglassen. Die Oberfläche
bestätigt weder private Lohnberechnungen noch Behörden- oder DATEV-Freigaben.

**Gebundenes Belegpaket herunterladen** liest ausschließlich vorhandene Daten.
Es gibt dafür keinen POST, keine Vorgangskennung und keine neue Annahme. Frühere
Jahreswerte, Zahlungsflüsse und Buchungsentscheidungen bleiben unverändert.
JSON und CSV des bisherigen Exports bleiben zusätzlich verfügbar.

Die Hashprüfung bindet die tatsächlich ausgegebene Datei. Sie beweist nicht
eigenständig die Vollständigkeit aller ursprünglichen Belege und Abhängigkeiten.
Diese Grenze der nachträglich aufgelösten Altquellen wird ausdrücklich angezeigt.
Der Offlineprüfer benötigt zwingend den separat authentisiert angezeigten
Archivhash; der Client startet keinen aus dem Archiv entnommenen Prüfer. Ein
fehlender oder falscher Vergleichshash darf keine erfolgreiche Prüfung ergeben.

## Bindung, Rechte und verspätete Antworten

Der Browser prüft die echten gespeicherten Report-/CSVbytes gegen ihre Hashes.
Paket-ID, Exporthash, Jahr und damalige Vollständigkeit müssen exakt zur
geöffneten Exportfassung passen; Dateipfad und Dateiname sind fest an dieselbe
ID gebunden. Schema, Format, Größenbegrenzung und ausdrückliche Ausschlüsse
werden überprüft. Fremde Felder oder private Zusätze werden abgewiesen.

Der unveränderte ältere Exportvertrag enthält keine Unternehmenskennung.
Deshalb bindet der Client die Instanz aus der ersten authentisierten
Paketmetadatenantwort an genau diesen Export und die aktuelle Sitzung. Er
nimmt keinen heutigen Profilwert als alten Instanznachweis an und ergänzt den
alten Exportvertrag nicht.

Unmittelbar vor dem ZIP-Abruf werden die Paketmetadaten erneut geladen.
Anschließend werden Größe, Dateityp und SHA-256 der tatsächlichen Bytes geprüft.
Vor der Dateiablage erfolgt ein weiterer authentisierter Metadatenabruf, der
auch sämtliche tatsächlich eingeschlossenen Quellrechte erneut prüfen lässt.
Alle Metadaten einschließlich Instanz und Exportbezug müssen unverändert sein.
Zusätzliche aktuelle globale Leserechte werden vor und nach diesen Abrufen
geprüft. Eine entzogene einzelne Quellfreigabe verhindert ebenfalls die Ausgabe.

Sitzung, Ansicht, Dialoggeneration, konkrete verbundene Ansicht und Hintergrund-
status begrenzen laufende Lese- und Hashoperationen. Der ursprüngliche
Exportdialog schützt auch seinen initialen Abruf sowie vorhandene JSON-/CSV-
Downloads. Eine eigene Exportabsichts-Epoche priorisiert bereits beim Anfordern
die zuletzt gewählte Fassung. Der echte Hintergrundhook invalidiert diese Epoche
auch dann, wenn vor der ersten Antwort noch kein Dialog besteht. Eine späte alte Antwort oder ein alter Fehler darf einen anderen
Dialog nicht verändern. Ein aktueller Rechtefehler ersetzt privaten Inhalt
und Titel durch eine neutrale Erklärung; es wird keine Datei ausgegeben.

## Nachweisstand

Der Backendnachtrag am eingebetteten Offlineprüfer ist im finalen Clientstand
berücksichtigt. Die folgenden Prüfungen wurden gegen die tatsächlich neu
erzeugten Pakete wiederholt; die vorherigen Originalfixtures, ZIPs und Logs
bleiben als historische Nachweise erhalten.

Die echten unveränderten Backendfixtures befinden sich unter
`docs/fixtures/accounting_year_package_v1.json`, SHA-256
`a859f2bbbcfab6f890c2968a05aa2fa839299117ae43b8e15e2d7852c82d36a0`.
Sie enthalten sechs tatsächliche Szenarien: gewöhnliche Buchungen mit Korrektur,
unvollständiges Jahr, alter Export nach Profilwechsel, historische Anlage mit
Altverbindlichkeit sowie öffentliche Lohn- und Reisefinanzprojektionen.

Der endgültige Gesamtlauf besteht **659/659 benannte Node-Tests**, ohne Fehler
oder übersprungene Fälle. Darin sind 28 eigene neue Vertrags-/Kontextfälle und
21 unabhängige Gegenfälle enthalten. Der erste vollständige Lauf mit 637 Fällen
bleibt als früherer Stand erhalten.

Ein eigener negativer Fall zur ausdrücklich sichtbaren privaten Originalgrenze
war tatsächlich rot und ist nach engem Readerfix grün. Der unabhängige Review
reproduzierte anschließend drei echte Fehler am initialen Exportzugang: alter
Erfolg und alter Fehler nach Hintergrund/Zurück sowie die Reihenfolge A gewählt,
B gewählt, A antwortet vor B. Die enge zusätzliche Exportabsichts-Epoche und der
Hintergrundhook verhindern diese veralteten Antworten, ohne andere
Buchungsentwürfe zu löschen. Die roten Originalausgaben bleiben erhalten.
Die unabhängige Node-Matrix ist vollständig grün; sie enthält auch bestehende
JSON-/CSV-Downloadbindung, verspätete Fehler und aktuelle einzelne Quellrechte.

Der tatsächliche Chromium/MFA/HTTP-Ablauf verwendet eine echte gebundene lokale
Instanz und angenommene synthetische Originale. Er prüft den deterministischen
ZIP-Download, denselben Download erneut, den eigenständigen Prüfer, vollständige
und unvollständige alte Jahresstände, verzögerte Antworten, beide initialen Exportantwortreihenfolgen,
einen simulierten Hintergrund-/Vordergrundwechsel über den tatsächlichen
Browserhook, fremde Exportauswahl, beschädigte Bytes, echten Rechteentzug während des Downloads und 390px.
Der bisherige vollständige EÜR-Browserablauf mit unverändertem JSON-/CSVexport
ist ebenfalls grün. Die Browserisolation bleibt eingeschaltet. Ein zusätzlicher unabhängiger
Chromiumlauf entzieht ausschließlich die Lesefreigabe einer tatsächlich
enthaltenen Original-Projektquelle nach Abruf der ZIPbytes; beide globalen
Leserechte bleiben nachweislich erhalten. Der letzte Metadatenabruf verweigert
dann die Ausgabe, ohne privaten Inhalt im neutralen Dialog zu behalten.

Der Client startet keine Datei aus einem heruntergeladenen Archiv. Der Browser-
Test prüft das tatsächliche ZIP mit dem vertrauten Prüfer aus dem Repository;
Originalbytes und dessen Prüfausgabe werden dauerhaft archiviert. Sämtliche
Testquellen sind synthetisch, alle Server laufen lokal; kein Produktivkontakt,
keine externe Zahlung und kein Versand.

## Integration und Zuständigkeit

Browsermodule, eigene Tests und Browserhooks: `finish_v6_clients`.
Backend/Fixtures: `overall_completion_review`; Native separat durch Root.
Die unabhängige Browsergegenprüfung verwendet eigene Dateien und ändert keine
Runtime. Der Altpostenbaum bleibt eingefroren und unangetastet.

Neue Module: `accounting-year-package-contract.js`, `accounting-year-package.js`.
Gemeinsame Hooks betreffen ausschließlich `office.js`, den gespeicherten
Exportdialog in `accounting-euer.js` und eine zusätzliche Browser-CI-Zeile.
Die statische Modulregistrierung gehört zum Backendhandoff. Root führt diese
Hooks additiv mit aktuellen Company-Events-, Source5-, Anlagen- und
Altpostenänderungen zusammen; der bestehende Dialogzähler wird mitverwendet.

Das [Abschlussmanifest](evidence/year-package-browser-2026-11-04.json) bindet
Dateihashes und unveränderte frühere Fehlernachweise;
[dauerhafte Logs und Artefakte](evidence/year-package-browser-2026-11-04/README.md)
enthalten auch die tatsächlich abgelegte ZIP-Datei und ihre Prüfausgabe.
