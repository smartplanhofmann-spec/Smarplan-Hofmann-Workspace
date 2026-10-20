# Windows: Start und Datensicherung

Stand: 20. Oktober 2026. Zusatzpaket 1.0 zur bereits getesteten App 0.2.1.

## Einrichten

Das Zusatzpaket `downloads/Smartplan_Windows_Start_und_Sicherung.zip`
herunterladen und vollständig entpacken. Die vorhandene App schließen und
den bisher manuell gestarteten Server in seinem Terminal mit **Strg+C** beenden.
**Starten.cmd** öffnen und einmal die vorhandene `smartplan_office.exe` auswählen.
Alle DLLs und der Flutter-Ordner `data` müssen bei der EXE bleiben.
Das vollständige neue Windows-Paket aus GitHub Actions enthält den Starter
bereits neben der EXE; dort entfällt die Dateiauswahl.

Der Starter verwendet `%LOCALAPPDATA%\SmartplanOffice\.venv\Scripts\python.exe`
und zunächst `%LOCALAPPDATA%\SmartplanOffice\data\office.sqlite3`.
Er installiert keine Pakete, ändert keine bestehenden Konten und legt bei
fehlender Datenbank keine leere Ersatzdatenbank an. Eine vorhandene manuelle
Serverinstanz muss zuerst beendet werden. Ein zweiter Starter wird durch eine
Betriebssystem-Sperre verhindert; die Sperre löst sich auch nach einem Absturz.

Danach immer **Starten.cmd** verwenden. Es startet den Server ausschließlich
auf `127.0.0.1:8765`, wartet auf dessen Gesundheitsantwort mit einer Kennung
dieses Starts und öffnet die App. Das Startfenster bleibt während der Nutzung
geöffnet. Beim Schließen der App beendet der Starter ausschließlich seinen
eigenen Server. Ein Windows-Jobobjekt beendet diesen Server auch dann, wenn
das Startfenster zwangsweise geschlossen wird; dabei gibt es keine abschließende
Sicherung. Keine Administratorrechte oder PowerShell-Ausführungsrichtlinien
müssen geändert werden. Für einen Desktop-Zugang im Explorer eine Verknüpfung
zu `Starten.cmd` anlegen; alle Dateien im entpackten Paket zusammen lassen.

## Sichern

Vor dem Start und nach dem Schließen der App wird eine konsistente SQLite-Kopie
mit Integritäts- und Fremdschlüsselprüfung erstellt. Ziele werden nie
überschrieben. Die Dateien liegen unter `%LOCALAPPDATA%\SmartplanOffice\backups`.
Jede Datenbank bekommt eine SHA-256-Prüfsumme als `.sqlite3.sha256`-Begleitdatei.
Es gibt keine automatische Löschung und keine Sicherung bei ausgeschaltetem PC.
Bei Stromausfall fehlt die abschließende Sicherung; die Sicherung vor dem Start
bleibt erhalten. Der aktuelle Arbeitsstand liegt weiterhin in der Datenbank.

Für eine Kopie auf einem anderen Laufwerk die App schließen,
**Sicherung_erstellen.cmd** öffnen und einen geschützten Zielordner wählen,
beispielsweise auf einem USB-Stick. Beide Dateien zusammen aufbewahren.
Eine Sicherung auf derselben Festplatte schützt nicht vor Ausfall oder Verlust
des PCs. Sicherungen enthalten unter anderem Geschäftsdaten, PDFs,
Unterschriften, Passwort-Hashes und Sitzungen; sie sind nicht verschlüsselt.
Die Prüfsumme erkennt Beschädigungen und ersetzt keine digitale Signatur.
Ein gegebenenfalls eingerichteter `OFFICE_VAULT_KEY` für Microsoft-Tokens muss
separat gesichert werden; echte OneDrive-Anmeldung wurde bisher nicht eingerichtet.

## Wiederherstellen

App und Starter schließen, auch einen manuell gestarteten Server beenden.
**Sicherung_wiederherstellen.cmd** öffnen, eine `.sqlite3`-Sicherung auswählen
und den angezeigten Stand bestätigen. Ihre Prüfsummendatei muss daneben liegen.
Ein beschädigter oder unvollständiger Stand wird abgewiesen.

Das Werkzeug prüft eine private Kopie der ausgewählten Datei, sichert den
bisherigen Arbeitsstand und erstellt einen neuen Datenordner unter
`%LOCALAPPDATA%\SmartplanOffice\restored`. Alte Sitzungen werden gelöscht.
Erst nach erfolgreicher Wiederherstellung wird `start-config.json` atomar auf
den neuen Datenordner umgestellt. Die bisherige Datenbank und alle Sicherungen
bleiben erhalten. Neuere Änderungen sind im älteren Stand nicht enthalten;
es gibt keine automatische Zusammenführung. Danach **Starten.cmd** öffnen und
mit dem zum Sicherungszeitpunkt gültigen Passwort erneut anmelden.

Die Auswahl der App und des aktiven Datenordners wird in
`%LOCALAPPDATA%\SmartplanOffice\start-config.json` gespeichert.
Nach einer Wiederherstellung gilt der neue Datenordner nur für diesen Starter;
alte manuelle Serverbefehle lesen diese Konfiguration nicht.
Serverprotokolle stehen unter `%LOCALAPPDATA%\SmartplanOffice\logs`;
Anfrageinhalte und Passwörter werden vom Server nicht protokolliert.

## Entwicklung und Prüfung

`backend/windows_office.py` enthält Sicherungs-/Startlogik mit einer kleinen
Tkinter-Oberfläche aus der offiziellen Windows-Python-Installation.
Die drei CMD-Dateien unter `windows/` verwenden die eingerichtete Python-Umgebung.
`scripts/package-windows-support.py` erzeugt ein reproduzierbares ZIP aus einer
festen Liste von Quellen. Benutzerdateien, Konten und Datenbanken werden nie
eingepackt. Das vollständige Windows-CI-Paket enthält dieselben Dateien.

Die Backend-Suite umfasst jetzt 24 Tests, davon sieben für beschädigte/fehlende
Prüfsummen, wiederholte Sicherung, fehlende Datenbank, doppelte Starter,
belegte Ports, echten Serverstart und -stopp bei App-Fehler sowie Erhalt von
Projekten und identischen signierten PDF-Bytes nach Wiederherstellung.
Der Lebenszyklustest verwendet einen echten Python-Server und einen simulierten
App-Aufruf. Ein Test prüft zusätzlich auf Windows das zwangsweise Beenden des
Starters und das automatische Ende seines versteckten Servers; auf Linux wird
nur dieser Test übersprungen. Die CMD-Dateidialoge und der gemeinsame Start mit der tatsächlichen
Flutter-EXE müssen zusätzlich auf dem Nutzer-PC abgenommen werden.

Der Nutzer bestätigte zuvor unter Windows Anmeldung, Projekte,
Servicebericht und Unterschrift, PDF-Ausgabe, Benutzerverwaltung,
Technikerzuweisung und Entzug des Projektzugriffs. Diese Bestätigungen gelten
für die bestehende App; sie sind noch keine Abnahme des neuen Starters.
