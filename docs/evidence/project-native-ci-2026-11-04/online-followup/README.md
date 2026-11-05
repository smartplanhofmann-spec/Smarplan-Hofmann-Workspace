# Lokale PostgreSQL-/HTTPS-Nachprüfung

Die Läufe verwenden ausschließlich selbst angelegte entbehrliche Datenbanken
und synthetische Nutzer/Belege. Der vorhandene Hostcluster auf Port 55433 wurde
weder gelesen noch verändert. Docker-Runner sind unprivilegiert (postgres),
verwenden --init, ein schreibgeschütztes Root-Dateisystem und eine eigene
beschreibbare /tmp-Tmpfs. Ein separater eigener PostgreSQL-16-Container läuft
mit --network none; nur der eigene Runner teilt dessen privates Netzwerk.
Es werden keine Hostports veröffentlicht. Produktionsdienste, Schlüssel,
Vaults, Kundenkonten und externe Provider werden nicht benutzt.

`test-runner.Dockerfile` kombiniert die lokal verfügbaren offiziellen
postgres:16- und python:3.12-slim-Images (Debian 13). Die 17 gepinnten
Python-Abhängigkeiten aus backend/online/requirements.lock wurden als Wheels
über den normalen TLS-geprüften Proxy geladen und anschließend mit
--network none installiert. Caddy 2.11.7 stammt aus dem bestehenden
fetch-caddy.sh mit erfolgreicher SHA-512-Prüfung. Das Buildcontext-Verzeichnis
work/verification/online-private-context enthält eine Kopie der getrackten
Quellen ohne docs/evidence sowie Wheels und Caddy; keine Produktionssecrets,
keinen kopierten Sitzungs-CA-Schlüssel und keine Docker-Anmeldedaten. Es liegt
im ignorierten Arbeitsbereich. Der Imagebau ändert die Originalquellen nicht.

Die vollständigen früheren Fehlversuche bleiben als solche erhalten. Der
nsenter-Ansatz in run.py scheiterte am /proc-Namespace-Zugriff, bevor Tests
liefen; result-original.json bewahrt die damals unzutreffend aus bloßer
PID-Präsenz abgeleitete Namespace-Aussage. result.json korrigiert diese auf
unbestätigt und weist null Testausführungen aus. Nachfolgende erfolgreiche
Läufe verwenden ausschließlich den regulären Docker-Netzwerkmechanismus.

Die Treiber in ../online-isolated, ../online-isolated-recheck,
../provisioning-connection-diagnostic, ../online-final und
../provisioning-final dokumentieren die konkreten getrennten Nachläufe.
Dateinamen und Image-Tags allein sind keine Erfolgsnachweise; maßgeblich
sind Exitcodes, unveränderte vollständige Logs und die Abschlussbindung in
../final/verification-summary.json. Insbesondere der erste kombinierte Lauf
ist rot; die abschließend korrigierte Provisionierung ist separat grün.

Der längere online-final-Lauf benutzt das vor der letzten reinen
Provisionierungsfixturekorrektur gebaute unveränderliche Image. Während
dieses Laufs wurde nur diese eine Fixturedatei geändert, nachdem genau ihre
fehlgeschlagene Gruppe bereits beendet war. Die korrigierte Gruppe besteht
in provisioning-final mit dem neu gebauten Image. Der Schlussabgleich
benennt diese Ausnahme ausdrücklich; es wird keine vollständige Bytegleichheit
beider unterschiedlicher Provisionierungsfixtures behauptet.
