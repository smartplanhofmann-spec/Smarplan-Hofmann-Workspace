# Gebündeltes Update 0.11 – Bürointegrationen

Der Nutzer hat Mailanhänge und die App 0.10.1 als funktionierend bestätigt.
Dieses Paket ergänzt Sevdesk und die bereits am Bot angeschlossenen Google-
Kalender-/OneDrive-Verbindungen. OneDrive ersetzt die zuvor irrtümliche
Dropbox-Annahme. Der neue Stand ist vor der manuellen Ausführung nicht auf dem
Nutzer-Server installiert.

## Serververbindung

Zuerst in Windows PowerShell verbinden:

    ssh -i "$env:USERPROFILE\.ssh\smartplan_hetzner" root@office.smartplan-hofmann.de

Die folgenden Linux-Befehle gehören in das verbundene Serverfenster.
Den exakten grünen Quellcommit des neuen Pakets im sauberen Checkout
/opt/smartplan-test bereitstellen. Danach den vorhandenen geschützten Ablauf:

    cd /opt/smartplan-test &&
    bash deploy/hetzner/online/update-online.sh &&
    systemctl is-active smartplan-online.service smartplan-https.service smartplan-plan-import.service &&
    curl --fail --silent --show-error --max-time 15 https://office.smartplan-hofmann.de/ready

Erwartet: dreimal active; status/database ok; Version 0.11.0-online-pilot,
Schema 6 und business_integrations. Wartungsgrenze, Writerstopp, Sicherung,
Kandidatendatenbank und Integritätsvergleich bleiben maßgeblich. Die bestehende
AppFolder-Ablage, Mail-Eingangsschlüssel und Mailoriginale werden beim normalen
Update erhalten. Ein Erstinstaller oder neuer Importworker ist nicht erforderlich.
Bei Fehlern das Updatejournal erhalten und den vorhandenen Wiederanlaufpfad nutzen.

## App und einmalige Verbindungen

1. Alte App schließen; neues Windows-Online-ZIP vollständig in einen neuen
   Ordner entpacken und daraus starten. App-Daten und Offline-Eingaben erhalten.
2. Unter Integrationen den Sevdesk-API-Zugang im geschützten Eingabefeld der
   App hinterlegen. Keinen Schlüssel in Chat oder Screenshots weitergeben.
3. Vorhandenen Projektbot verbinden: neuen SPIX-Zugang ins geschützte Botfeld
   SMARTPLAN_INTEGRATION_TOKEN übernehmen und das neue Projektbotpaket mit
   BOT_AUFTRAG.md geben. Den bestehenden Fünfminutenjob ergänzen, keinen zweiten
   anlegen. SPIN-Maileingang und bestätigte Gmail-IDs behalten.
4. Nach der tatsächlichen Kataloglieferung zeigt Smartplan die Botverbindung
   als bestätigt. Dann im Projekt einzelne Sevdesk-Belege, Kalendertermine und
   einen OneDrive-Ordner ausdrücklich auswählen. Noch angeforderte Ressourcen
   werden beim nächsten Botlauf geliefert und anschließend erneut geladen.
5. Ein ausgewähltes Ereignis und eine Datei im Projekt prüfen. Die Datei öffnet
   ihren ursprünglichen Microsoft-Browserlink. Bestehende Mailanhänge behalten
   ihre direkte PDF-/Bildvorschau innerhalb Smartplans.

Die neue Bridge ist eine lesende Metadatenübergabe, keine vollständige Dateikopie,
kein Kalender-Schreibabgleich und keine zweite Buchhaltung. Es werden keine
neuen Anbieterabos bestellt oder echten Cloudkonten während der Entwicklung benutzt.
Reale Providerfreigabe und die Windows-/Mobilgeräteabnahme erfolgen beim Nutzer.

Eine Disaster-Wiederherstellung prüft erst die Integrität und trennt anschließend
neue Integrations-/Bot-/OAuth-Zugänge; alte Lieferung oder Schlüsselquittungen
können sie nicht wiederbeleben. Das ist vom normalen Update zu unterscheiden.
