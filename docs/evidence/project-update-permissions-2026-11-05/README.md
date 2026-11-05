# Root-Archivextraktion und Updateabbruch

Auf dem echten Server wurde das Update a93cb4d... vor der Kandidatenerstellung
bei der Release-Berechtigungsprüfung abgebrochen. Der Nutzer bestätigt danach
zwei aktive Dienste, den weiter installierten alten Quellstand und root-eigene
Releasepfade mit 0775/0664. Die bestehende Schutzprüfung ist richtig; es war
kein Anlass, sie zu entfernen oder private Schlüsselverzeichnisse zu ändern.

Git archive verwendet standardmäßig tar.umask=0002. Dadurch stehen 0775/0664
in den Archivheadern. GNU tar übernimmt als root standardmäßig die Rechte aus
dem Archiv und beachtet die Shell-umask dabei nicht wie ein normaler Benutzer.
Ein umask 0022 vor git archive | tar -x reicht für diesen Rootpfad nicht aus.

Die neuen dauerhaften Operatorpfade verwenden explizit git -c tar.umask=0022
und tar --no-same-permissions unter umask 0022. Das gilt für Update und
Erstinstallation. Der Guard bleibt erhalten und nennt jetzt zusätzlich Pfad
und Modus. Die bisherige Git-Testgrenze erzeugte künstlich 0644-Dateien ohne
Verzeichnisheader. Sie bildet jetzt den echten Git-Default 0775/0664 und
seine explizite tar.umask-Option ab. Mit dieser realistischeren Grenze scheitert
der vorhandene Erfolgsfall vor dem Fix genau wie auf dem Server und führt die
vorhandene Rückkehr aus. Nachher prüft er sämtliche neuen Releasepfade auf
fehlende Gruppen-/Fremdschreibrechte; alle ursprünglichen Integritäts-,
Reihenfolge-, Daten- und Wiederherstellungsassertionen bleiben erhalten.

Zusätzlich werden tatsächliche auf dem Host erzeugte Git-Archive mit GNU tar
als UID 0 in einem eigenen netzisolierten kurzlebigen Container extrahiert:
Default, eingeschränkte Gitmaske, umask-beachtende Extraktion und beide
Maßnahmen gemeinsam. Nur der Default ist gruppenschreibbar. Alle drei
Korrekturvarianten liefern 0755/0644 und erhalten die Quell-Ausführungsbits.
Die gewählten Shellquellen sind im Git selbst 0644 und werden über bash
aufgerufen; der erste Probetreiber hatte fälschlich ein gesetztes Execute-Bit
vorausgesetzt und wurde auf den Vergleich mit dem tatsächlichen Githeader
korrigiert. Diese Annahme wird nicht als Produktfehler gezählt.

Für den bereits fest ausgecheckten und tatsächlich gebauten Serverstand
A93 genügt vor dem erneuten Versuch die explizite repository-lokale Einstellung
git config --local tar.umask 0022. Die echten Root-Archivtests prüfen genau
auch diese Variante mit ansonsten unverändertem altem tar-Aufruf. Dadurch
bleibt der installierte Produktquellstand an die vorhandenen nativen Builds
gebunden. Kein pauschales chmod -R, keine Umgehung des Guards und kein
Entfernen von UPDATE_IN_PROGRESS. Bereits vorhandene fehlgeschlagene Releases
bleiben als Nachweis erhalten; ein neuer Versuch bekommt eine neue Release-ID.
