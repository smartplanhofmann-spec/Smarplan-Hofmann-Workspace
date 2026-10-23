# Austauschbare Dokumentablage

Standard ist der vom Nutzer gewählte Cloudbetrieb auf der vorhandenen Hetzner-VM:
Projektverwaltung, Benutzer, Datenbank und maßgebliche unterschriebene PDFs bleiben
dort gemeinsam verfügbar. Die zusätzliche Dokumentablage
ist wählbar: Smartplan-Server, persönliches OneDrive oder ein HTTPS-WebDAV-Speicher,
zum Beispiel eine passende Cloud oder ein NAS. Es wird kein Anbieter automatisch
verbunden. Die Geschäftsführung wählt einen vorbereiteten Anschluss in der App
unter **Ablage** aus. Ein Wechsel verschiebt oder löscht keine vorhandenen Dateien.

**Betriebsort und Dokumentablage sind zwei getrennte Entscheidungen.** Der
Smartplan-Server mit API und Datenbank läuft heute auf der bereits eingerichteten
Hetzner-VM. Die Auswahl **Smartplan-Server** speichert zusätzliche Dokumentdateien
auf dieser VM. Die Wahl eines NAS oder OneDrive verlagert nur die zusätzliche
Dateiablage; die Projektverwaltung und Datenbank bleiben auf Hetzner.

Ein vollständiger Betrieb vor Ort würde API, PostgreSQL und Dateien auf einem
eigenen Rechner/Server betreiben. Für unterwegs zugreifende iPhones braucht es
dann einen kontrollierten Netzwerkzugang, etwa VPN, sowie eigene Zuständigkeit
für Updates, Sicherung und Erreichbarkeit. Ein solcher Vor-Ort-Betrieb ist mit
diesem Anschluss noch nicht eingerichtet oder abgenommen. Für den bestätigten
gemeinsamen Windows-/iPhone-Betrieb bleibt zunächst die vorhandene Hetzner-VM
der Betriebsort; die zusätzliche Dokumentablage kann davon unabhängig gewählt
werden.

Unterschriebene PDFs können beispielsweise zusätzlich in OneDrive abgelegt und
dort pro Projekt geordnet werden. Die übrigen Projektmanagementdaten werden
dadurch nicht in OneDrive exportiert oder über OneDrive synchronisiert.

Die Adaptergrenze erlaubt weitere Anschlüsse. S3, SFTP und direkte SMB-Verbindungen
sind mit diesen drei Anschlüssen noch nicht implementiert. Ein vom Betreiber auf
dem Smartplan-Server eingebundener NAS-Datenträger kann als Serververzeichnis
verwendet werden. Eine solche Einbindung und deren Zugangsdaten sind ein eigener
Betriebsschritt.

## Bestehenden Online-Dienst aktualisieren

Im vorhandenen SSH-Serverfenster als root den freigegebenen Branch aktualisieren
und die neue Codekopie installieren:

```bash
cd /opt/smartplan-test
git pull --ff-only origin codex/smartplan-office-0.2
bash deploy/hetzner/online/update-online.sh
```

Der Updateablauf erstellt zuerst mit dem vorhandenen Dienst eine PostgreSQL-
Sicherung. Neue Quellen und Abhängigkeiten werden in einem eigenen Releasepfad
vorbereitet. Erst danach wird der Dienst kurz angehalten und auf den neuen Stand
umgestellt. Schlägt Start oder Bereitschaftsprüfung fehl, werden die vorherigen
Codepfade wiederhergestellt. Alte Releases werden nicht automatisch gelöscht.

Datenbank, Microsoft-Tokens, bestehende Berichte, MFA-Tresorschlüssel und HTTPS-
Konfiguration bleiben erhalten. Das Skript führt keine Datenmigration oder
Datenwiederherstellung aus. Ein Wechsel des Datenbankschemas braucht einen eigenen
Migrations- und Rückkehrplan. Die Sicherung bleibt auf dem Server; das ersetzt
kein getrenntes Sicherungsziel.

Die vorhandene Erstinstallation `install-online.sh` nicht erneut ausführen.
Ein `git pull` allein aktualisiert die installierte Codekopie nicht.

## Anschluss vorbereiten

```bash
bash /opt/smartplan-test/deploy/hetzner/online/configure-storage.sh
```

Das Skript fragt interaktiv nach dem Anschluss. Geheimnisse werden ausgeblendet
direkt am Serverterminal eingegeben. Sie gehören nicht in Chat, Screenshots,
Git-Dateien oder Befehlsargumente. Bereits eingerichtete andere Anschlüsse bleiben
erhalten. Die geschützte Datei `/etc/smartplan-online/storage.json` gehört root,
ist für die Dienstgruppe lesbar (0640) und enthält die Anschlussdaten. In
`service.env` steht nur ihr Pfad. Der bestehende MFA-Tresorschlüssel wird weiter
verwendet und nicht neu erzeugt. Nach der Einrichtung wird der Dienst neu gestartet.

Die Datei muss in die geschützte Betriebssicherung einbezogen werden. Auch diese
Dateisicherung enthält Geheimnisse und benötigt passende Verschlüsselung sowie
Zugriffsschutz.

### Smartplan-Server

Standardpfad: `/var/lib/smartplan-online/documents`. Er gehört ausschließlich dem
Dienstkonto `smartplan-online` (0700). Die zusätzliche Ablage verwendet eigene
Projektordner und deterministische PDF-Dateinamen. Ein wiederholter Upload erzeugt
keine neue Kopie mit zufälligem Namen.

Für einen vorhandenen NAS-Mount oder ein anderes dediziertes Verzeichnis muss der
Betreiber Eigentümer, Rechte und Erreichbarkeit einrichten. Die systemd-Unit
schützt das Dateisystem mit `ProtectSystem=strict`. Außerhalb des eigenen
Zustandsverzeichnisses ist deshalb ein gezieltes `ReadWritePaths=`-Drop-in für
genau den benötigten Dokumentpfad erforderlich; nicht den gesamten Dateisystem-
schutz abschalten. Bei einem Mount kann außerdem `RequiresMountsFor=` den Start
an die Einbindung binden. Verbindungsausfälle und Wiederanlauf separat prüfen.

### OneDrive Personal / Microsoft 365 Family

Der Anschluss betrifft den App-Ordner **eines** persönlichen Microsoft-Kontos.
Ein Family-Abonnement erzeugt keine gemeinsame Ablage aller Familienmitglieder.
Bestehende Projektordner außerhalb des App-Ordners werden nicht eingelesen.

1. In [Microsoft Entra](https://entra.microsoft.com/) **App-Registrierungen → Neue
   Registrierung** öffnen. Persönliche Microsoft-Konten müssen unterstützt sein.
2. Eine **Web**-Rücksprungadresse exakt registrieren:
   `https://office.smartplan-hofmann.de/api/v1/storage/callback`.
3. Delegierte Rechte `Files.ReadWrite.AppFolder` und `offline_access` verwenden.
   Kein unbeaufsichtigter Zugriff über Client Credentials.
4. Die **Anwendungs-ID (Client-ID)** notieren und einen zeitlich begrenzten
   geheimen Clientschlüssel erstellen. Den **Wert** sicher aufbewahren; er wird
   nur einmal vollständig angezeigt. Ablauf rechtzeitig überwachen.
5. Im Konfigurationsskript OneDrive wählen, Client-ID und geheimen Wert am
   Server eingeben. Danach in der App OneDrive auswählen und **verbinden**.
6. Microsoft-Anmeldung im Browser mit dem gewünschten Konto abschließen. Danach
   in Smartplan den Status aktualisieren und einen fiktiven unterschriebenen
   Bericht ablegen. Er muss unter
   `Apps/<Name der Microsoft-App>/Projekt - <Projektname> - <Projekt-ID>/`
   auffindbar sein. Der Ordner bleibt bei einer späteren Umbenennung des Projekts
   derselbe. Ein Wiederholen desselben Uploads erzeugt keine zweite PDF-Datei.

Der Callback liegt unter der bestehenden API-Proxyroute; weitere Firewallports
oder eine Freigabe der bisherigen `/oauth/*`-Route sind nicht nötig. OAuth-State
und PKCE sowie verschlüsselte Tokens werden serverseitig verwaltet. Microsoft
übermittelt Code und State als Formular, damit sie nicht in der Callback-URL
stehen. Der reine
Status „Anmeldung gespeichert“ ersetzt keinen nachgewiesenen Datei-Upload.

Ein Microsoft-365-Family-Abo allein belegt noch keinen Zugang zur Appregistrierung.
Ein eventuell erforderlicher Entra-/Azure-Zugang muss separat verfügbar sein;
keine zusätzliche kostenpflichtige Leistung ohne konkreten Auftrag buchen.

### Cloud oder NAS über WebDAV

Der Anbieter muss HTTPS-WebDAV mit gültigem Zertifikat und Schreibzugriff im
gewählten Zielordner unterstützen. Bei Nextcloud ist dies beispielsweise die
persönliche WebDAV-Dateiadresse; die genaue Adresse aus den Einstellungen des
Anbieters übernehmen. Ein dediziertes App-Passwort verwenden, wenn unterstützt.

Im Skript die vollständige HTTPS-Zieladresse, Benutzer und Passwort eintragen.
Smartplan verwendet darunter seinen eigenen `Smartplan`-Ordner. Der Zielordner
muss bereits existieren; die Smartplan-Unterordner werden bei Bedarf angelegt.
Weiterleitungen werden nicht verfolgt. Anbieter mit ausschließlich S3- oder
proprietärer API sind durch den WebDAV-Anschluss nicht abgedeckt.

Ein NAS im privaten Heim-/Büronetz ist vom Hetzner-Server nicht automatisch
erreichbar. Dafür muss ein kontrollierter Netzwerkweg, etwa ein bereits
eingerichtetes VPN, vorhanden sein. Das Skript richtet kein VPN ein und öffnet
keine Ports am NAS. Ein erreichbarer Name und ein dazu passendes vertrauenswürdiges
HTTPS-Zertifikat sind erforderlich.

## Geräteabnahme

Nur fiktive Daten verwenden: Anschluss auswählen, unterschriebenes PDF ablegen,
Datei am Ziel öffnen und Inhalt/Unterschrift mit Smartplan vergleichen. Den Upload
wiederholen und prüfen, dass nur die vorgesehene Datei aktualisiert wird. Danach
einen zweiten vorbereiteten Anschluss auswählen und prüfen, dass neue Uploads
dort landen und vorhandene Dateien im ersten Ziel erhalten bleiben. Fehler und
erneute Anmeldung dürfen nicht als erfolgreicher Upload angezeigt werden.
