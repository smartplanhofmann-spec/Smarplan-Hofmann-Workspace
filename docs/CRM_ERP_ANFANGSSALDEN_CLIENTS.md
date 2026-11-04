# Anfangsbestände und belegte Liquidität: Clientvertrag

Stand: 4. November 2026. Dieser Vertrag beschreibt den im Repository implementierten Client-Teil für `accounting_opening_balances`. Er dokumentiert keine Auslieferung oder Produktivfreigabe. Der tatsächliche HTTP-/Domänenvertrag steht in [CRM_ERP_ANFANGSSALDEN_API.md](CRM_ERP_ANFANGSSALDEN_API.md).

## Bedienweg und bestätigte Grundlagen

Im Browser führt **Finanzen → EÜR-Vorbereitung → Anfangsbestände und Liquidität** zu den Geldkonten. Auch die Kontenansicht und der EÜR-Arbeitsbereich verlinken diese Oberfläche. Die native Buchführungsansicht und der native EÜR-Arbeitsbereich öffnen dieselben fachlichen Vorgänge über ihre eigene Oberfläche.

Ein fehlender Anfangsbestand wird als **nicht festgestellt** angezeigt. Die Betragserfassung ist leer; weder null noch ein Datum werden als tatsächliche Unternehmensangaben angenommen. Der Beginn stammt ausschließlich aus dem ausdrücklich bestätigten Buchführungsprofil. Konto, Kontofassung, Profilfassung, Quellenstand und ursprüngliche Quelle bleiben mit Vorschau und Bestätigung verbunden.

Für ein eigenes Original wird zunächst ein PDF, PNG oder JPEG bis 5 MiB zum ausdrücklich ausgewählten Geldkonto hochgeladen. Der Client prüft Dateityp und Größe, der Server bestimmt die Metadaten aus den tatsächlichen Bytes. Die angenommene Originalquittung muss exakt zu Dateiname, Typ, Größe und SHA-256 der gewählten Datei passen. Anschließend werden Betrag, Quelle, Beginn vor der ersten Tagesbewegung und Prüfgrund ausdrücklich angegeben. Auch ein tatsächlicher Nullbestand benötigt diese Angaben. Ein negativer Kassenbestand wird abgelehnt; ein belegter negativer Bankbestand ist möglich.

Alternativ wird ein bereits importierter, unveränderter Bankauszug gewählt. Anfangssaldo und Endsaldo der unmittelbar vorherigen Periode werden anhand ihrer wirklichen Tagesgrenzen geprüft. Der ursprüngliche Saldo wird übernommen; das Eingabefeld für eigene Originalbeträge ersetzt ihn nicht.

Eine unverbindliche Vorschau speichert keinen Anfangsbestand. Erst eine zusätzliche, zunächst nicht gesetzte Bestätigung hält genau die geprüfte Vorschau fest. Neue Erkenntnisse erzeugen eine neue Bestandsfassung mit Grund und ursprünglichem Vorgänger. Eine ausdrückliche Aufhebung erhält Betrag, Quelle, Profil und Vorgängerhistorie. Die Konto-Historie zeigt alle Fassungen und ihre geschützten Originale.

## Ergebnis und Liquiditätsumfang

Anfangsbestände erzeugen keine Geldbewegung, keinen Ertrag und keine Steuerbuchung. Die bestehenden EÜR-Ergebnisse bleiben unverändert. Die Liquiditätsansicht zeigt Anfangsbestand, aufgezeichnete Zu- und Abflüsse, rechnerischen Stand sowie den daraus bestätigten Stand je Konto. Im Browser wird der Stichtag ausdrücklich eingegeben. Die native Ansicht zeigt zunächst den sichtbaren aktuellen Stichtag und erlaubt dessen Änderung. Dieser Abfragestichtag setzt keinen Buchführungsbeginn und bestätigt keinen Bestand.

Der Umfang lautet **aufgezeichnete Bewegungen**. Fehlende Anfangsbestände, ungeklärte Quellen, geänderte Profile, offene Wiederherstellungsabgleiche, widersprechende Bankauszüge und rechnerisch negative Kassenbestände verhindern einen uneingeschränkt bestätigten Bestand. Die bekannte Teilsumme wird ausdrücklich vom vollständigen Gesamtbestand unterschieden. Wenn kein Konto bestätigt ist, bleiben bekannte Summe und Gesamtbestand unbekannt; eine leere Datenlage wird nicht zu null umgedeutet.

Die Clients rechnen die centgenauen Bewegungs- und Kontosummen mit exakten Ganzzahlen nach. Die Grenze von elf Vorkommastellen für einzelne Anfangsbeträge wird nicht auf daraus errechnete Salden oder Summen übertragen. Ein zulässiger Anfang von 99.999.999.999,99 € plus ein tatsächlicher Zufluss von 119,00 € bleibt beispielsweise als 100.000.000.118,99 € lesbar. Die Eingabegrenzen und die Prüfung ursprünglicher Einzelquellen bleiben erhalten. Bankanschlüsse müssen zusätzlich den tatsächlichen Tagesbewegungen entsprechen: Ein Anfangssaldo steht vor den Bewegungen seines Tages, ein Endsaldo nach den Bewegungen seines Tages. Ein Endsaldo des Vortags kann den folgenden Buchführungsbeginn belegen. Die Anzahl bekannter Konten, die Teilsumme und der vollständige Gesamtbestand müssen zur gelieferten Kontenliste passen.

## Rechte, Sitzung und unklare Antworten

Lesen erfordert die globalen Rechte `accounting.read`, `finance.read` und `bank.read`. Schreiben benötigt zusätzlich `accounting.admin`, `accounting.prepare`, `finance.write`, einen freigegebenen Finanzbetrieb und den aktuellen serverseitigen Vorbereitungsstatus. Projektbezogene Freigaben ersetzen diese Rechte nicht.

Jeder schutzbedürftige Abruf und jede Freigabe prüft den aktuellen Kontext. Ein Rechteentzug entfernt die geschützten Inhalte einschließlich privater Kontoangaben im Dialogtitel; eine verspätete Vorschau oder Originalantwort darf nach einem Ansichts- oder Sitzungswechsel keine neue private Ansicht öffnen oder Datei ausliefern. Hintergrundwechsel schließen die Browseransicht. Native Ansichten binden ihre Arbeit zusätzlich an das tatsächliche Sitzungsobjekt und ihren Lebenszyklus.

Original- und Bestätigungsaufträge mit unklarer Antwort bleiben ausschließlich im aktuellen Sitzungsspeicher. Die Wiederholung nutzt dieselben vollständigen Werte, dieselbe Vorgangskennung und den ursprünglich eingefrorenen Quittungsprüfer. Eine abweichende Quittung wird nicht als Erfolg gewertet. Die neutrale Liste offener Antworten zeigt keine Originalbytes oder Bestandsbeträge.

Vor einer Wiederholung werden Rechte, Kontozugriff und Finanzfreigabe erneut geprüft. Ein pausierter Finanzbetrieb sperrt hier auch die unveränderte Wiederholung; der offene Auftrag bleibt erhalten. Nach der Freigabe kann derselbe Auftrag erneut gesendet werden. Ein endgültiger serverseitiger Nachweis der Nichtannahme kann einen Auftrag beenden. Ein verlorener Empfangsnachweis allein tut dies nicht.

Die gemeinsame Browser-API wartet auf die asynchrone vollständige Hashprüfung. Erst danach darf genau der weiterhin aktuelle Vorgang aus dem Speicher entfernt werden. Ein Sitzungswechsel oder ein zwischenzeitlich ersetzter Vorgang kann weder durch die alte Hashantwort gelöscht werden noch einen fremden Erfolg erhalten. Vorhandene synchrone Quittungsprüfer bleiben unterstützt.

## Implementierung und Prüfung

Browser: `web/office/accounting-openings.js`, Integration in `office.js` und `accounting-euer.js`; statische Registrierung in `backend/online/web.py`. Native Oberfläche und Vertrag: `app/lib/business_accounting_openings.dart` und `app/lib/business_accounting_openings_contract.dart`; Integration in Session, Buchführung und EÜR.

Die gemeinsamen synthetischen Vertragsdaten werden durch `scripts/generate-accounting-opening-fixture.py` über tatsächliche Domain-Kommandos erzeugt und identisch in `docs/fixtures/accounting_openings_2026.json` und `app/test/fixtures/accounting_openings_2026.json` abgelegt. Die Daten enthalten tatsächliche Originalannahme, Vorschau, Annahme, Korrektur, Aufhebung, Historie, Liquidität mit Geldbewegungen und einen belegten negativen Banksaldo. Sie sind keine angenommenen Unternehmensbestände.

Verbindliche Testzählungen, Laufpfade, Quellprüfsummen und Einschränkungen stehen in [accounting-openings-clients-2026-11-04.json](evidence/accounting-openings-clients-2026-11-04.json). Browser-Vertragstests laufen in der vollständigen Node-Suite; der echte Chromium-/MFA-/HTTP-Ablauf ist als `SMARTPLAN_BROWSER_WORKFLOW=accounting-openings` im bestehenden CI-Workflow registriert. Chromium-, Namespace-, PID-, Netzwerk- und Seccomp-Sandbox bleiben aktiviert. Native Prüfungen verwenden den tatsächlichen Flutter-Client und einen isolierten lokalen HTTP-Server.

Dieser Client-Teil bestätigt keine vollständige Unternehmensliquidität außerhalb der aufgezeichneten und geprüften Quellen. Er schließt auch nicht die noch separat geplante Übernahme alter Anlagegüter oder das gesamte CRM-/ERP-Gesamtziel ab.
