# Projektinformationen und Dateien für Kunden

Stand: 3. November 2026. Dieser Ablauf ergänzt das bestehende Angebotsportal. Eine Angebotsfreigabe eröffnet keinen Projektzugang; Projektzugänge verwenden eigene Einladungen und Sitzungen.

## Bedienung

Im Office ein Projekt auswählen und **Dokumente → Kundenbereich** öffnen. Die Ansicht benötigt aktuelle Portal- und Dokumentrechte für genau dieses Projekt.

1. **Projektinformationen veröffentlichen**: öffentlichen Titel, Text, Status und optionalen Zeitraum eingeben. Die Bestätigung bezieht sich ausdrücklich auf alle aktuellen Kundenfreigaben dieses Projekts. Interne Projekttexte werden nicht automatisch übernommen.
2. **Originaldatei freigeben**: eine berechtigte Quelle auswählen, das Original herunterladen und prüfen, den öffentlichen Titel festlegen und die Veröffentlichung bestätigen. Die Freigabe bindet die geprüfte Dateifassung und ihren SHA-256-Wert.
3. **Projektzugang freigeben**: Empfängername, E-Mail-Adresse, Gültigkeit von einem bis 30 Tagen und optionalen Dateieingang festlegen. Den einmal sichtbaren Zugang gezielt sichern. Die Anwendung verschickt dabei keine Nachricht und verifiziert die Empfängeradresse nicht extern.
4. Der Kunde öffnet den Projektlink, sieht ausschließlich freigegebene Projektinformationen und Dateien und kann Originale herunterladen. Bei erlaubtem Dateieingang kann er PDF, PNG, JPEG oder WebP bis vier MiB mit einem Hinweis übermitteln.
5. Der **Kundenposteingang** zeigt diese Datei zunächst als eingegangen an. Mitarbeitende laden das Original zur Prüfung herunter und übernehmen es ausdrücklich in das Projekt. Die Zielklassifikation ist auswählbar; Vorgabe ist **Geschützt**. Finanz- und Personalklassifikationen benötigen entsprechende Rechte. Ein Kundeneingang wird niemals allein durch das Hochladen zur freigegebenen Projektdatei.
6. Zugänge und Dateifreigaben lassen sich mit dokumentiertem Grund widerrufen. Auch bei fachlich pausiertem Dokumentmodul bleiben berechtigte Widerrufe möglich. Bereits heruntergeladene Kopien können damit nicht zurückgeholt werden.

## Unklare Antworten und Zugriff

Nach verlorener Empfangsbestätigung behält der Kundenbrowser die unveränderte Uploadanfrage einschließlich Request-ID nur im Arbeitsspeicher. Er zeigt **Ursprüngliche Übertragung erneut versuchen** und warnt vor dem Schließen des Tabs. Ein bestätigter Retry erzeugt keinen zweiten Eingang. Ein abweichender Upload kann den unklaren Vorgang nicht ersetzen.

Interne Änderungen benutzen die bestehenden Office-Request-Receipts. Nach verlorener Antwort dieselbe Eingabe erneut bestätigen. Geht die erste Antwort eines neu erstellten Zugangs verloren, bestätigt die Wiederholung die vorhandene Freigabe, zeigt ihren geheimen Link aber nicht erneut. Den Zugang dann prüfen, erforderlichenfalls widerrufen und neu erstellen.

Einladungsfragmente werden unmittelbar aus der Adresszeile entfernt. Projektsitzung, Einladung und ausstehende Kundendatei werden nicht in Cookies, Local Storage, Session Storage oder IndexedDB gespeichert. Öffentliche Zugriffe verwenden ausschließlich die eigene Kundenbereich-API, ohne Cookies, Weiterleitungen oder Referrer. Originaldownloads werden vor der Ausgabe auf Größe, Medientyp und SHA-256 geprüft. Beim Widerruf oder Sitzungsende wird die sichtbare Kundenansicht neutralisiert.

Die interne Ansicht prüft Projekt-ID, Kundenbindung, aktuelle API-Sitzung und Renderkontext. Ein Projekt- oder Loginwechsel kann keine verspätete Antwort in die neue Ansicht übernehmen. Projektspezifische Berechtigungen werden beim Öffnen erneut geladen; der Server prüft sie bei jedem Fachaufruf.

## Dateien

- `web/office/customer-workspace.html` und `customer-workspace.js`: eigener öffentlicher Kundenbereich.
- `web/office/customer-workspace-staff.js`: interner Renderer mit injizierter Office-API.
- `web/office/office.js`: Import und projektgebundene Einfügung im Dokumentbereich.
- `web/office/tests/customer-workspace.test.mjs` und `customer-workspace-staff.test.mjs`: Transport-, Rechte-, Datenbindungs-, Integritäts- und Wiederholungstests.
- `web/office/tests/customer-workspace-e2e.cjs` mit `customer_workspace_fixture.py`: echter lokaler Browserablauf mit Anmeldung, MFA und temporärer Datenbank.
- `app/test/business_customer_workspace_test.dart`: Flutter-Widgettests für unveränderte Wiederholungen, Rechteentzug und Widerrufe trotz Dokumentpause oder Rückkehrmodus.

## Prüfnachweis

Die gezielten Node-Tests prüfen unter anderem getrennte Tokenfamilien, Fragmententfernung, verbotene Fremdrouten, gefilterte öffentliche Daten, fremde Projekte/Uploads, exakte Originalbytes, falsche Empfangsbestätigungen, Antwortverlust, Widerruf, spätes Antwortende und Klassifikationsbindung.

Ergebnis dieses Arbeitsstands: **21 gezielte Tests bestanden; 188 Browser-Modultests einschließlich bestehender Bereiche sowie acht neue Flutter-Widgettests bestanden; zusammen mit den bestehenden Angebotsportaltests liefen 18 Widgettests seriell erfolgreich.** Der echte Browserablauf wurde mit aktivem Sandboxschutz erfolgreich ausgeführt, einschließlich öffentlicher und interner Ansicht bei 390 Pixeln Breite. Die dabei gefundene ungenaue Beschriftung der Klassifikationsauswahl wurde vor dem erfolgreichen Lauf korrigiert.

Der echte Chromium-Ablauf prüft Anmeldung mit MFA, interne Veröffentlichung, Originalvorschau, explizite Projektfreigabe, öffentliche Desktop- und Mobilansicht, sicheren Text mit HTML-Zeichen, Dateiübertragung, interne Übernahme als geschütztes Projektdokument, Projektwechsel und Widerrufe. Er lässt die echten Serverantworten für Freigabe, Sitzung, Upload und Übernahme jeweils einmal verloren gehen und prüft danach die unveränderte Wiederholung. Die Browser-Sandbox einschließlich Namespace-, PID-, Netzwerk- und Seccomp-Isolation bleibt eingeschaltet.

Ausführung aus dem Repository:

```sh
node --test web/office/tests/customer-workspace*.test.mjs
SMARTPLAN_BROWSER_TEST_PYTHON=backend/.venv/bin/python node web/office/tests/customer-workspace-e2e.cjs
```

Optional: `SMARTPLAN_CHROMIUM_BINARY` für das Chromium-Binary, `SMARTPLAN_BROWSER_SCREENSHOT_DIR` für Screenshots und `SMARTPLAN_BROWSER_NAMESPACE_SANDBOX=1` für die ausdrücklich geprüfte Namespace-Alternative zum SUID-Helper. Playwright muss im Node-Suchpfad vorhanden sein. Der Test verwendet ausschließlich eine temporäre lokale Testinstanz und synthetische Kundendaten. Produktiver TLS-/Proxybetrieb, echte Nachrichten und externe Empfängerbestätigung werden damit nicht nachgewiesen.

Die acht ergänzenden Flutter-Widgettests und die bestehenden Angebotsportaltests wurden mit `flutter test --no-pub --concurrency=1 test/business_customer_workspace_test.dart test/business_portal_test.dart` im Verzeichnis `app` ausgeführt. Sie prüfen eine verlorene Grant-Antwort mit unveränderter wiedergeöffneter Anfrage, das Entfernen sichtbarer Geheimnisse und Projektinformationen bei aktuellem Dokumentrechteentzug, unveränderte Widerrufswiederholungen bei Dokumentpause jeweils mit und ohne Rückkehrmodus, eine verspätete Grant-Erfolgsantwort nach Rechteentzug, Originaldateien mit falscher Prüfsumme oder Größe sowie eine abweichende Übernahmeklassifikation mit unveränderter Wiederholung der geschützten Zielklasse. Dafür wurden der vorhandene Flutter-/Clang-Pfad und Paketcache verwendet; die Testlaufzeit benötigt einen lokalen Loopback-Socket.

Die Prüflogs und Screenshots dieses Arbeitsstands liegen unter `work/verification/customer-workspace-*`; der gesamte Softwarezielumfang ist damit nicht als abgeschlossen erklärt.
