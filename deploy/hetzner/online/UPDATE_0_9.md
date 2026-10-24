# Gebündeltes Update 0.9

Dieses Paket erweitert den bestätigten Stand 0.8 / PostgreSQL-Schema 3 auf
0.9 / Schema 4: Anfrageeingang, Projektmappe, Aufgaben, Termine, Bautagebuch,
Dokumentverweise, Offline-Projektarbeit und verbesserter Planimport.

## Vorbereitet statt erneut installieren

Der Nutzer besitzt bereits API, Caddy/HTTPS und den abgenommenen Importdienst auf
Ubuntu 24.04 ARM64. Dafür weder `install-online.sh` noch den Erstinstaller für den
Importdienst erneut ausführen. Parser-Locks und bekannte Importunit bleiben gleich.

Vor dem Update müssen die Prüfungen des exakten Quellcommits erfolgreich sein.
Der vorhandene [geschützte Updateablauf](UPDATE_0_7.md) bleibt maßgeblich: eigenes
Journal, Wartungssperre, geordneter Worker-/API-Stopp, Originaldump, unabhängige
Kandidatendatenbank, Fingerprintvergleich, Migration und öffentliche Aktivierung.
Vault-Key, Betriebskonfiguration und ursprüngliche Datenbank bleiben erhalten.
Getrennte Betriebssicherung und freier Speicher bleiben Voraussetzungen.

## Ein gemeinsamer Serverdurchlauf

Verbindung in Windows PowerShell:

```powershell
ssh -i "$env:USERPROFILE\.ssh\smartplan_hetzner" root@office.smartplan-hofmann.de
```

Im Serverfenster aus dem sauberen `/opt/smartplan-test` auf den **exakten geprüften
Commit aus dem Paketmanifest** wechseln. Danach:

```bash
cd /opt/smartplan-test &&
bash deploy/hetzner/online/update-online.sh &&
systemctl is-active smartplan-online.service smartplan-https.service smartplan-plan-import.service &&
curl --fail --silent --show-error --max-time 15 https://office.smartplan-hofmann.de/ready
```

Bei Fehler stoppt die Kette. Ein offenes Updatejournal wird nicht gelöscht, um
einfach erneut zu starten. Nach `activating` bleiben neue Datenbank und neue
Schreibvorgänge erhalten; siehe Fehlerbehebung im gemeinsamen Runbook.

Erwartete Bereitschaft: Version `0.9.0-online-pilot`, Schema `4`, Datenbank `ok`
und `plan_deletion`, `project_workspace`, `inquiry_intake`, `gmail_intake`,
`offline_workspace` neben bisherigen Fähigkeiten. Eine Fähigkeit beschreibt
verfügbaren Code, keine bereits erteilte externe Anbieterfreigabe.

## Gemeinsam testen

1. Online-Windows-Prüfpaket vollständig in einen neuen Ordner entpacken, alte App
   schließen und neue EXE öffnen. App-/Offline-Daten nicht manuell löschen. Die
   sichtbare Version ist `0.9.0`.
2. Fiktive Anfrage oder EML aufnehmen, bestehenden Kunden bestätigen oder neuen
   Kunden bewusst anlegen und Projekt übernehmen. Auch frühe Klärung ohne Zusage
   muss funktionieren.
3. Aufgabe, Termin und Tagebuch erfassen; Dropbox-Ordner und Sevdesk-Vorgang als
   benannte Links zuordnen. Zeitplan, Anzahlung und Material unabhängig ändern.
4. Testplan importieren, drehen, vergrößern, Erkennung bei Bedarf einblenden und
   nach Bestätigung entfernen. Erneuter Abruf darf ihn nicht wieder anlegen. Für
   die Abnahme alle beteiligten Geräte aktualisieren.
5. Mappe online laden, offline bearbeiten, App neu starten und wieder verbinden.
   Gleichzeitigen zweiten Stand als Konflikt behandeln, lokale Eingaben erhalten.
6. Gmail erst über die [separate Einrichtung](../../../integrations/google_apps_script/SETUP.md)
   anschließen. Nur das ausgewählte Label wird gelesen. Schlüssel ausschließlich
   in sicheren vorgesehenen Feldern verwenden und nicht im Chat zeigen.

Kalenderdateien und externe Links sind ausdrückliche Übergaben. Dropbox-/Sevdesk-
Liveabgleich, WhatsApp Business Platform und Google-Autorisierung sind keine
heimlich aktivierten Teile des Updates. Tatsächliche Geräte-/Betriebsabnahme
bleibt nötig. Windows-Pakete bleiben bis zur getrennten Herausgebersignierung
interne unsignierte Prüfausgaben.
