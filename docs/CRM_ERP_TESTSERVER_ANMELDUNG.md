# Anmeldung auf dem Smartplan-Testserver

Für `office.smartplan-hofmann.de` ist auf Wunsch des Betreibers eine Anmeldung mit E-Mail-Adresse und Passwort für alle aktiven Smartplan-Konten einschließlich Administratoren vorgesehen. Die Auswahl gilt für den Browser und für Apps, die diesen Testserver verwenden. Die Geräteentsperrung auf iPhone oder Windows und eine Anmeldung bei GitHub werden separat verwaltet.

## Passwortanmeldung einschalten

Der Funktionsstand für die Passwortanmeldung ist `6eb6a883b5f99c805fe933ec690db68a606ccbb0`. Der folgende Ablauf aktualisiert den bestätigten Serverstand `4bb5071` und aktiviert anschließend die Passwortanmeldung. Bei einer Wiederholung auf bereits installiertem Zielstand überspringt er das Datenbankupdate.

1. In Windows PowerShell die bekannte SSH-Verbindung öffnen.

   ```powershell
   ssh -i "$env:USERPROFILE\.ssh\smartplan_hetzner" root@office.smartplan-hofmann.de
   ```

2. Im verbundenen Linux-Terminal den folgenden Block ausführen. Das koordinierte Update prüft seine Sicherung und die Kandidatendatenbank. Der abschließende Befehl aktiviert die Passwortanmeldung und prüft die HTTPS-Bereitschaft samt Datenbank.

   ```bash
   (
     set -eu
     cd /opt/smartplan-test
     ziel=6eb6a883b5f99c805fe933ec690db68a606ccbb0
     git diff --quiet
     git diff --cached --quiet
     git fetch origin codex/testupdate-0.7-projects-20261104
     git merge-base --is-ancestor "$ziel" FETCH_HEAD
     installiert=$(cat /opt/smartplan-online/SOURCE_COMMIT)
     git merge-base --is-ancestor "$installiert" "$ziel"
     git switch --detach "$ziel"
     if [ "$installiert" != "$ziel" ]; then
       git config --local tar.umask 0022
       bash deploy/hetzner/online/update-online.sh
     fi
     test "$(cat /opt/smartplan-online/SOURCE_COMMIT)" = "$ziel"
     bash deploy/hetzner/online/set-test-login.sh password
   )
   ```

3. Nach der Meldung `Testserver bereit. Anmeldeverfahren: Passwort.` Smartplan Office in einem privaten Browserfenster öffnen. Mit der persönlichen E-Mail-Adresse und dem Passwort anmelden. Die Arbeitsoberfläche soll sich sofort öffnen. Mit einem aktiven Administratorkonto wiederholen und die jeweils verfügbaren Bereiche prüfen. [Smartplan Office](https://office.smartplan-hofmann.de/office/)

4. Auf Windows und iPhone abmelden und beim gleichen Server erneut anmelden. Ein falsches Passwort muss die Anmeldung zurückweisen. Bereits eingerichtete Authenticatoren und gespeicherte Wiederherstellungscodes für eine spätere Rückkehr zur Zwei-Faktor-Anmeldung aufbewahren.

## Zwei-Faktor-Pflicht wieder einschalten

Im verbundenen Linux-Terminal ausführen.

```bash
bash /opt/smartplan-test/deploy/hetzner/online/set-test-login.sh mfa
```

Nach der Meldung `Testserver bereit. Anmeldeverfahren: Passwort und zweiter Faktor.` in einem neuen privaten Browserfenster anmelden. Bereits eingerichtete Konten erhalten die Codeabfrage. Bei einem bisher nicht eingerichteten Konto führt die Anwendung durch die Einrichtung. Eine zuvor allein mit Passwort eröffnete Sitzung muss bei der nächsten geschützten Serverabfrage eine neue Anmeldung verlangen.

## Betrieb

Die Dienstdatei `/etc/smartplan-online/service.env` enthält die Auswahl unter `SMARTPLAN_TEST_PASSWORD_ONLY`. Der Betreiberbefehl prüft die konfigurierte Testdomain, erhält Besitzer und Dateirechte und verwendet dieselbe Sperre wie das Serverupdate. Weitere koordinierte Updates übernehmen die Einstellung. Sie wird beim Neustart der Anwendung wirksam. Eine fehlgeschlagene Bereitschaftsprüfung beim Einschalten löst die Rückkehr zur Zwei-Faktor-Pflicht aus. Beide Befehle melden Fehler im SSH-Terminal.
