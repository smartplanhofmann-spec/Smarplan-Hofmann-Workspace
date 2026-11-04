# Unabhängige Gegenprüfung des Jahrespakets im Browser · 04.11.2026

Geprüfter Arbeitsbaum: `/workspace/smartplan-year-review-export-20261104`. Die Prüfung betrifft den tatsächlich gespeicherten EÜR-Jahresexport und dessen ausschließlich lesbaren Jahresnachweis mit Originaldateien. Sie ersetzt keine fachliche Freigabe der gesamten Software oder steuerliche Prüfung. Der Reviewer hat keine Produktdatei verändert; die drei reproduzierten Kontextfehler hat der zuständige Browserowner gezielt behoben.

## Nachgewiesenes Ergebnis

- **21 eigene Nodefälle bestanden**, zusammen mit 28 Ownerfällen und 11 bestehenden EÜR-Fällen **60/60**; keine übersprungenen Fälle.
- **Ein eigener echter Chromium/MFA/HTTP-Ablauf bestanden**, einschließlich projektbezogenem Rechteentzug erst nach dem tatsächlichen ZIP-Abruf, weiterhin vorhandenen globalen Leserechten und 390-px-Ansicht ohne horizontalen Überlauf.
- **Sechs tatsächlich vom Backend erzeugte Archive unabhängig geprüft**, ohne Extraktion und ohne Ausführung ihres enthaltenen Prüfers.
- **Drei ursprüngliche rote Gegenfälle behoben und erneut grün**. Keine weiteren bestätigten offenen Befunde in dieser Gegenprüfung.

Die Nodefälle verwenden die echten DTOs mit kontrolliertem DOM und Transport. Sie sind von dem separat protokollierten tatsächlichen Browser-/HTTP-Test zu unterscheiden. Der vorliegende Stand bindet die Backendfixture `bd3ff5a40bf10211b67ca563dcf14ad2850949e43be54cdb19deba4b5e0557cc` (689672 Bytes). Sie bleibt als unveränderte Prüfkopie im Evidenzordner erhalten. Eine danach angekündigte Härtung des Offlineprüfers und neue Archivbytes erhalten einen eigenen Nachtrag; sie sind nicht stillschweigend Bestandteil dieser Ergebnisse.

## Reproduzierte und behobene Fehler

1. Ein anfänglicher GET des gespeicherten Originalexports lief noch, bevor ein Dialog existierte. Nach Hintergrund und Rückkehr in den Vordergrund öffnete seine alte Erfolgsantwort den privaten Export erneut.
2. Unter derselben Folge konnte ein verspäteter 409-Fehler wieder erscheinen.
3. Bei zwei ausdrücklich nacheinander gewählten Originalexporten A und B ohne bestehenden Dialog gewann fälschlich A, wenn dessen Antwort zuerst zurückkam. Dessen Dialogwechsel machte den später gewünschten Export B ungültig.

Der Browserowner ergänzte einen eigenen `exportGeneration`-Zähler im bestehenden `createAccountingEuer`: Jeder Exportaufruf und `clear()` machen frühere Exportabsichten ungültig. Der tatsächliche globale `visibilitychange`-Handler ruft bei Hintergrund stets `accountingEuer.invalidateExport()` auf, auch ohne Modal. Der Zähler betrifft die Exportansicht und löscht keine anderen Buchungsentwürfe oder Pendingaufträge. Die drei Ergebnisassertionen blieben unverändert; lediglich der Testhost bildet den neuen tatsächlichen Hintergrundhook ab. Ursprüngliches rotes Protokoll und die damaligen Datei-Hashes sind archiviert.

## Abdeckung und Originalbindung

Gehaltene Metadaten und ZIP-Antworten werden jeweils als Erfolg und Fehler nach Sitzungswechsel, anderer Exportfassung sowie Hintergrund-/Vordergrundwechsel freigegeben: zwölf eigene Fälle. Hinzu kommen JSON-/CSV-Originalabrufe nach Exportwechsel, verkürzte und veränderte ZIP-Bytes, unzulässiger Inhaltstyp sowie Änderungen an Exporthash, Jahr, Instanz, ursprünglicher Vollständigkeit und Originalzahl zwischen den authentisierten Metadatenabrufen.

Der ursprüngliche Export enthält bewusst keine `instance_id`. Die erste authentisierte Metadatenantwort bindet deshalb die Instanz für alle späteren Vergleiche; es wird kein nicht vorhandenes Instanzfeld des alten Exports behauptet. Export-ID, Report-/CSV-Hash, Jahr und Originalvollständigkeit bleiben an dessen tatsächlich gespeicherten Inhalt gebunden. Das reine Paketlesen erzeugt keine Annahme, Buchung oder neue Nonce.

Die sechs Archive umfassen einen korrigierten normalen Jahresfall, ein ausdrücklich unvollständiges Jahr, denselben alten Export nach einer Profiländerung, historische Anlagen mit altem Lieferantenoriginal sowie öffentliche Lohn- und Reisekostenquellen. Geprüft sind ZIP-Gesamthash/-größe, eindeutige sortierte Mitglieder, feste ZIP-Zeitstempel und Speicherung, jedes Mitglied mit SHA256 und Länge, sämtliche Originaldateinamen gegen die tatsächlichen Bytes, Originalanzahl, ursprüngliches Report-JSON und bytegleiches CSV. Der spätere Profilwechsel verändert das alte Archiv nicht.

Unvollständige Jahre bleiben sichtbar unvollständig. Öffentliche Lohn-/Reisekostennachweise behaupten keine enthaltenen privaten Personaloriginale; bekannte Quellen ohne entsprechende private Grenze werden abgewiesen. Es wird weder eine vollständige Unternehmensbuchführung, eine Steuererklärung noch DATEV-Zertifizierung aus der technischen Archivverfügbarkeit abgeleitet. Hashprüfung ist keine Signaturprüfung.

## Tatsächlicher Entzug eines einzelnen Originalrechts

Der separate Browserlauf startet eine temporäre tatsächliche Instanz mit synthetischen Daten, MFA und echtem HTTP. Er ermittelt den Projektbezug des tatsächlichen Originalbelegs. Der Leser besitzt weiterhin global `finance.read` und `accounting.read`.

Der ZIP-Abruf erhält tatsächlich HTTP 200; nur seine Zustellung an den Browser wird gehalten. Danach entzieht der Owner über die tatsächliche Berechtigungs-API ausschließlich `finance.read` im Projekt dieses Originalbelegs. Ein frischer Fähigkeitenabruf bestätigt beide globalen Leserechte weiterhin. Nach Freigabe der Bytes endet die erneute Metadaten-/Einzelquellprüfung mit HTTP 403. Der Browser zeigt einen neutralen nicht freigegebenen Jahresnachweis, keine frühere Export-ID und beginnt **keinen Download**. Zwei Screenshots und die tatsächlichen Statusfolgen liegen im Evidenzordner. Chromium lief mit nachgewiesenem Namespace-, PID-, Netzwerk- und Seccomp-Sandboxschutz; keine Produktionskontakte.

## Wiederholbare Nachweise

```sh
/tmp/smartplan-backend-verified/bin/python web/office/tests/accounting-year-package-independent-fixture.py
/tmp/smartplan-backend-verified/bin/python web/office/tests/accounting-year-package-independent-archive-check.py
node --test --test-isolation=none web/office/tests/accounting-year-package-independent.test.mjs web/office/tests/accounting-year-package.test.mjs web/office/tests/accounting-euer.test.mjs
```

Der echte Browserlauf nutzt den vorhandenen tatsächlichen E2E-Serverstart und ausschließlich den eigenen Ablauf über `accounting-year-package-independent-preload.cjs`. Dafür sind `SMARTPLAN_BROWSER_TEST_PYTHON=/tmp/smartplan-backend-verified/bin/python`, `SMARTPLAN_BROWSER_NAMESPACE_SANDBOX=1`, das Evidenzverzeichnis als `SMARTPLAN_BROWSER_SCREENSHOT_DIR` und die absolute Preload-Datei über `NODE_OPTIONS=--require=…` gesetzt; Einstieg ist `node tests/accounting-year-package-e2e.cjs` im Verzeichnis `web/office`. Die dafür benötigte lokale Browser-/Socketausführung war autorisiert.

Eigene sechs Test-/Generator-/Ablaufdateien und die echte ergänzende Zweiexportfixture sind dauerhaft im Repository. [Manifest und exakte Datei-Hashes](evidence/year-package-browser-independent-2026-11-04/manifest.json) unterscheiden eigene Artefakte von nur gelesenen Produktdateien; das Manifest enthält seinen eigenen Hash nicht. Es wurden keine Commits oder Stagingänderungen vorgenommen.
