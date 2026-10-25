# Update 0.12.2: Fachregister und sichere Rückwege

Client **0.12.2+122** behebt die grauen Projektregister und ergänzt die Funktions-/Rückwegprüfung über alle vorhandenen Bereiche. Das Dashboard und die Hauptnavigation behalten ihren Aufbau. Der [Prüfbericht](FUNKTIONSPRUEFUNG_0_12_2.md) beschreibt die einzelnen Wege und die Grenzen der Abnahme.

## Server und Windows-App aktualisieren

Die Registerkorrektur liegt im nativen Client. Für die zusätzliche Artikelwahl ohne Finanzrecht enthält das Paket außerdem eine abwärtskompatible Serverergänzung. Beide Teile aktualisieren; die neue App allein ersetzt keinen laufenden Server.

Unter Windows in PowerShell verbinden:

```powershell
ssh -i "$env:USERPROFILE\.ssh\smartplan_hetzner" root@office.smartplan-hofmann.de
```

Im SSH-Fenster den im geprüften Updatehinweis genannten **festen Commit** nach `/opt/smartplan-test` holen und als abgetrennten HEAD auschecken. Vorhandene lokale Änderungen zuerst erhalten und prüfen. Danach den bestehenden geschützten Ablauf verwenden:

```bash
bash /opt/smartplan-test/deploy/hetzner/online/update-online.sh
```

Der Ablauf behält Sicherungen und die separate Kandidatendatenbank bei. Keine manuelle Rückkehr auf alte Datenbanken oder Löschung von Update-Markern durchführen. [Betriebsleitfaden](BETRIEB_BUSINESS_UPDATE.md).

Anschließend prüfen:

```bash
systemctl is-active smartplan-online.service smartplan-https.service
curl --fail --silent --show-error --max-time 15 https://office.smartplan-hofmann.de/ready
```

Erwartet: `0.12.2-online-pilot`, `database: ok`, Schema `7`, im Businessmodus weiterhin `business_suite`. Es ist keine neue Datenbankmigration nötig. Die Artikelreferenz-Funktion steht unter den authentifizierten Business-Feature-Metadaten, nicht in der öffentlichen Bereitschaftsantwort.

Die bisherige Windows-App vollständig schließen. Das im Updatehinweis verlinkte **Smartplan-Office-Windows-Online-Pilot** vollständig in einen neuen Ordner entpacken und dessen `smartplan_office.exe` starten. Version **0.12.2** prüfen. Appdaten und verschlüsselte Offlinewarteschlangen erhalten; keine Deinstallation oder Datenlöschung durchführen. Das lokale Pythonpaket ist für diesen Onlinezugang nicht erforderlich.

## Kurzer Praxistest

1. Ein Testprojekt öffnen. Arbeitszeit, Einsatzplanung, Material, Kalkulation, Dokumentation und die übrigen freigegebenen Register öffnen; jeweils zurück zur Übersicht und zur Projektliste wechseln.
2. Eine Aufgabe beziehungsweise einen Belegeditor öffnen und abbrechen. Die Ausgangsliste muss wieder bedienbar sein.
3. Einen Testplan bearbeiten, ohne ihn zu speichern, ein anderes Register wählen und das Projekt verlassen. „Weiterbearbeiten“ muss die Eingabe erhalten; Verwerfen erfordert eine ausdrückliche Bestätigung.
4. Unter Material alle Unterbereiche wechseln. Ohne ausgewähltes Projekt muss der Bereichswähler erreichbar bleiben.
5. „Weitere Verwaltung“ öffnen und über „Zur Übersicht“ zurückkehren.

Für Rechnungen und Versendungen weiterhin ausschließlich die eingerichteten Betriebsregeln verwenden. Der Patch aktiviert keine Finanzfunktion automatisch. Windows-Signierung/SmartScreen sowie reale Mobilgeräte- und Anbieterabnahmen bleiben offen.
