# Projektwirtschaftlichkeit in Browser und Flutter

Stand: 03.11.2026. Bestandteil der CRM-/ERP-Umsetzung für Smartplan Hofmann; keine Erklärung, dass das gesamte Gesamtziel oder eine steuerliche Gewinnermittlung abgeschlossen ist.

## Bedienbarer Ablauf

1. Im ausgewählten Projekt **Kalkulation** öffnen. Die aktuelle Projektwirtschaftlichkeit benötigt das serverseitige Modul und Merkmal `project_economics` sowie `finance.read`.
2. **Projekt-Eingangsbelege** öffnen, ein unverändertes PDF-, PNG- oder JPEG-Original auswählen und übertragen. Dateien bis 20 MiB werden in Blöcken übertragen. Original, Dateityp und SHA-256 werden vor der weiteren Bearbeitung geprüft. XML-Belege gehören nicht zu diesem Dateiauswahldialog.
3. Original öffnen und die tatsächlich ausgewiesenen Angaben kontrollieren. Lieferant, Belegnummer, Datum, Netto-, Steuer- und Bruttobetrag sowie Prüfergebnis ausdrücklich erfassen. Netto plus ausgewiesene Steuer muss Brutto entsprechen. Die Prüfung entscheidet weder über Vorsteuerabzug noch über eine Zahlung. Der betriebliche Standardsteuersatz wird nicht ungeprüft auf Eingangsbelege angewandt.
4. Den vollständigen geprüften Nettobetrag auf Fremdleistungen, Maschinen, sonstige Kosten, bereits über Lagerentnahmen berücksichtigtes Material oder begründet ausgeschlossene Beträge aufteilen. Die Summe muss exakt stimmen. Abgelehnte Belege können nur begründet ausgeschlossen werden.
5. Die unverbindliche Vorschau prüfen und die Einordnung anschließend ausdrücklich bestätigen. Korrekturen erzeugen neue nachvollziehbare Fassungen; Original und frühere Fassungen bleiben erhalten. Eine geänderte Belegprüfung verlangt eine neue Einordnung.
6. Budget einschließlich freigegebener Nachträge, Materialentnahmen, genehmigte bewertete Arbeitszeit, Belegkosten, Rechnungen/Gutschriften und Zahlungen getrennt vergleichen. Quellen und frühere Einordnungen sind aus der Oberfläche zugänglich. Budget und Nachträge können mit entsprechenden Rechten gepflegt werden.

## Bedeutung und Grenzen der Anzeige

- Die Auswertung ist eine dokumentarische Nettoansicht der erfassten Quellen, keine EÜR und kein steuerlicher Gewinn. Fehlende oder nicht mehr aktuelle Belegprüfungen/-einordnungen und unbewertete Zeiten verhindern ein scheinbar vollständiges Ergebnis.
- Lieferantenauszahlungen und Cashsaldo stammen ausschließlich aus bestätigten Buchhaltungsereignissen. Fehlen dafür globale Leserechte oder ein erforderlicher Abgleich, erscheinen diese Beträge als nicht verfügbar. Ein fehlender Betrag ist keine Null.
- Material aus Lagerentnahmen wird nicht durch eine zusätzliche Belegzuordnung doppelt gezählt. Der Server verhindert darüber hinaus doppelte Kosten bei mehrfach erfassten identischen Originalen.
- Rechte, Modulzustand und Datenstand begrenzen auch bereits geöffnete Ansichten. Ein geänderter Datenstand verwirft veraltete Projektübersichten und Quelldetails; eine neue Abfrage beziehungsweise das erneute Öffnen liefert aktuelle Daten.

## Unbestätigte Übertragungen

Capture, Belegprüfung und Kosteneinordnung erhalten bei einer verlorenen oder unpassenden Bestätigung den ursprünglichen Auftrag einschließlich Eingaben und Vorgangskennung. Wiederholung sendet denselben Auftrag; die Rückmeldung wird vor dem Entfernen des offenen Auftrags gegen die eingefrorenen Eingaben geprüft. Geänderte lokale Eingaben werden nicht stillschweigend als Wiederholung gesendet. Rechte werden vor geschützten Wiederholungen neu gelesen. Unbestätigte Vorgänge bleiben bei mehrdeutigen Fehlern erhalten.

In Flutter bleiben ausgewählte Originaldateien und Übertragungsfortschritt im Arbeitsspeicher derselben angemeldeten Sitzung erhalten, auch wenn die Belegseite geschlossen wird. Sie werden nicht als unverschlüsselter dauerhafter Finanzcache abgelegt. Abmelden, Prozessende oder Sitzungsende beendet diese lokale Wiederaufnahme; dies ist keine Zusage einer geräteübergreifenden Offlineübertragung.

## Prüfung und Nachweise

Ergebnis des abschließenden gezielten Laufs: **8/8 Flutter-Tests bestanden**, statische Analyse der sechs betroffenen UI-/Testdateien **ohne Befund**, `git diff --check` ohne Beanstandung. Die Prüfungen bestehen aus sieben Unit-/Widgettests und einer echten Flutter-HTTP-Integration gegen den Python-Server. Sie prüfen Cent-genaue Beträge, falsche Bestätigungen, Rechte- und Datenstandswechsel, die schmale 390-Pixel-Ansicht, vollständige Einordnung mit verlorener Antwort, Schließen/Wiederöffnen der Belegseite, den tatsächlichen Belegprüfungsendpunkt sowie das Sperren von Schreibfunktionen ohne Freigaberecht.

Die echte HTTP-Kette umfasst Originalupload und bytegleichen Download, verlorene Antworten nach tatsächlich gespeicherter Erfassung und Prüfung, eine nach tatsächlicher Speicherung verfälschte Einordnungsbestätigung, unveränderte Wiederholung ohne Duplikat, geänderte Belegprüfung, unterdrücktes veraltetes Ergebnis und anschließende Korrektur mit unveränderter früherer Historie.

Browser: 16 neue Modultests, 38 gezielte Modulregressionen und ein echter Chromium-Ablauf decken Originalupload/-download, Belegprüfung, Einordnung, verlorene Bestätigung, Wiederholung, Korrektur/Historie, geänderte Belegquelle sowie Budget und Quellen ab. Desktop und 390-Pixel-Ansicht wurden geprüft. Flutter wurde über Widgettests mit Windows-Zielplattform und echten HTTP-Aufrufen geprüft; eine Installation auf einem physischen Mobilgerät wird damit nicht behauptet.

Reproduzierbare Nachweise:

- `app/test/business_project_economics_test.dart`
- `app/test/project_economics_backend_integration_test.dart`
- `web/office/tests/project-economics.test.mjs`
- `web/office/tests/project-economics-flow.cjs`
- `work/verification/project-economics-flutter-final.log`
- `work/verification/project-economics-flutter-final-analyze.log`
- `work/verification/project-economics-node-regression.log`
- `work/verification/project-economics-browser-final.log`
- `work/verification/project-economics-browser-final-previews/`

Gezielte Ausführung aus `app`: `flutter test --no-pub test/business_project_economics_test.dart test/project_economics_backend_integration_test.dart`. Der Browser-End-to-End-Runner unterstützt `SMARTPLAN_BROWSER_WORKFLOW=project-economics`.
