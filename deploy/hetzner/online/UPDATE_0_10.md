# Gebündeltes Update 0.10 – Mailanhänge

Bestätigter Nutzerstand ist 0.9 / Schema 4 aus Commit
**822fe58be148f5df52ab14d6ff8a9267c696932e**. Der Mailbot liefert Texte bereits
erfolgreich ein und meldet einen laufenden Fünfminutenjob. Dieses Paket ergänzt
Originalanhänge, Projektablage und die ausdrückliche Übernahme als Planquelle.

## Server

Der vorhandene [geschützte Updateablauf](UPDATE_0_7.md) bleibt maßgeblich:
Wartungsgrenze, Writerstopp, Sicherung, Kandidatendatenbank, Fingerprintvergleich,
Migration der Kopie und kontrollierte Aktivierung. Bestehende aktive Schlüssel,
MFA und Vault bleiben erhalten. Bei einer Disaster-Wiederherstellung werden
Zugänge wie bisher gesperrt; ein normales Update widerruft sie nicht.

Zuerst aus Windows PowerShell verbinden:

    ssh -i "$env:USERPROFILE\.ssh\smartplan_hetzner" root@office.smartplan-hofmann.de

Im Serverfenster den exakten grünen Quellcommit aus dem Paketmanifest im sauberen
Checkout /opt/smartplan-test bereitstellen. Danach:

    cd /opt/smartplan-test &&
    bash deploy/hetzner/online/update-online.sh &&
    systemctl is-active smartplan-online.service smartplan-https.service smartplan-plan-import.service &&
    curl --fail --silent --show-error --max-time 15 https://office.smartplan-hofmann.de/ready

Erwartet: Version **0.10.0-online-pilot**, Schema **5**, Datenbank/Status **ok**,
**mail_attachments** und dreimal **active**. API-/Importdienste und Parser-Locks
entsprechen weiterhin der abgenommenen Installation. Erstinstaller nicht erneut
ausführen. Bei Fehlern ein offenes Updatejournal erhalten und das Runbook verwenden.

## Windows und Mailbot

1. Das neue Online-Windows-Paket vollständig in einen neuen Ordner entpacken und
   die alte App vorher schließen. Vorhandene App-Daten und Offline-Eingaben behalten.
2. Den bestehenden Mailbot mit dem neuen
   [Anschlusspaket und Auftrag](../../../integrations/mail_bot/README.md)
   aktualisieren. Vorhandenen Job und gültigen geschützten Eingangsschlüssel
   weiterverwenden. Keine zweite parallele Automatik anlegen.
3. Den Bot die Anhänge bereits bestätigter Anfragen gezielt nachtragen lassen.
   Die bisherige Liste bestätigter Mail-IDs erhalten. Ein Text-POST 201 schließt
   den Anhangtransfer nicht ab; erst das vollständige Gesamtmanifest zählt.
4. Eine neue Testmail mit zwei Anhängen nach dem nächsten automatischen Lauf
   kontrollieren. Beide Dateien müssen in der Anfrage vollständig erscheinen.
   Downloadgröße und Inhalt prüfen; derselbe Lauf erzeugt keine Kopien.
5. Anfrage einem Kunden/Projekt übergeben. Unter **Dokumente** stehen die
   Originale, und PDF/JPEG/PNG lassen sich ausdrücklich in **Pläne** übernehmen.
   Das Entfernen einer Plankopie erhält den Mailanhang; das Entfernen eines
   Mailanhangs darf eine bestehende Plankopie nicht beseitigen.

Die Fähigkeiten des konkreten externen Bots zum Abruf unveränderter Anhangbytes
müssen tatsächlich vorhanden sein. Ein fehlender Byteabruf wird als Fehler oder
offene Übernahme angezeigt, nicht als erfolgreiche anhanglose Mail.

Dateien bleiben auf dem eigenen Hetzner-System, soweit es um Speicherung und
Planverarbeitung in Smartplan geht. Der vorhandene Bot leitet Originalbytes aus
Gmail weiter und führt keine externe Plan-/Dokumentanalyse aus. Mobile
Speichern-/Teilen-Funktionen und unsignierte Windows-Prüfpakete benötigen weiterhin
die tatsächliche Geräte-/Betriebsabnahme.
