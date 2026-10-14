# Windows-Installation ohne PyPI-Verbindung

Wenn pip keine Verbindung zu `pypi.org` aufbauen kann, steht unter
`downloads/Smartplan_Windows_Python312_Offline.zip` ein Offline-Paket bereit.
Es enthält genau die sechs Versionen aus `backend/requirements.lock`, als
vorgefertigte Wheels für Windows x64 / Python 3.12. Die Pakete wurden über
HTTPS von PyPI heruntergeladen und gegen die dort veröffentlichten
SHA-256-Werte geprüft. Ihre Lizenzdateien bleiben in den Wheels enthalten.

1. Das ZIP von GitHub herunterladen und mit **Alle extrahieren** entpacken.
2. Im entpackten Ordner **Installieren.cmd** doppelt anklicken.
3. Die Abschlussmeldung kontrollieren und anschließend im bestehenden
   Smartplan-Quellordner mit Backend-Tests und Kontoeinrichtung fortfahren.

Python 3.12 (64 Bit) mit verfügbarem `py`-Befehl ist Voraussetzung. Die bereits
vorhandene Umgebung unter `%LOCALAPPDATA%\SmartplanOffice\.venv` wird verwendet.
Falls sie fehlt, legt das Skript sie an. Eine Umgebung mit einer anderen
Python-Version wird nicht gelöscht oder überschrieben; die Prüfung bricht ab.

pip arbeitet mit `--no-index`, lokalen Wheel-Dateien und `--require-hashes`.
Es benötigt während dieser Installation keine Paketregistry. Es werden keine
TLS-, Signatur- oder Prüfsummenprüfungen deaktiviert. Danach erfolgen
`pip check` sowie eine PDF-Erzeugungs- und Verschlüsselungsprüfung. Das Paket
ist kein Windows-App-Installer und enthält weder Flutter noch Buildwerkzeuge.

Die Cloud-Prüfung bestätigt die vollständige Offline-Paketauflösung und die
Prüfsummen für das Windows-Ziel. Der native Lauf von Installieren.cmd und den
Windows-Bibliotheken muss auf dem Windows-PC bestätigt werden.

Alternativ kann im entpackten Offline-Ordner per PowerShell installiert werden:

```powershell
& "$env:LOCALAPPDATA\SmartplanOffice\.venv\Scripts\python.exe" -m pip install --no-index --find-links .\wheels --require-hashes -r .\requirements-windows.lock
```

Die Datenbank wird separat eingerichtet und soll ebenfalls außerhalb des
OneDrive-Ordners liegen. Der Quellordner muss für dieses Offline-Paket weder
verschoben noch ersetzt werden.
