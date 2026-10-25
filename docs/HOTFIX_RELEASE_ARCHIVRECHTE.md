# Server-Hotfix: sichere Archivdateirechte

Der erste Updateversuch mit Quellstand `420c4c7700d7543a725d787d48eef8bdb2319152` wurde auf dem Hetzner-Server mit „Release darf nicht durch Gruppe oder andere Benutzer verändert werden“ abgebrochen. Die Ausgabe bestätigt die Rückkehr zum vorherigen Dienst mit unveränderter Originaldatenbank. Sie bestätigt keine erfolgreiche Installation von 0.12.

## Ursache und Korrektur

Git erstellt TAR-Archive standardmäßig mit `tar.umask=0002`. Dadurch enthalten sie Verzeichnisse mit `0775` und normale Dateien mit `0664`. Eine TAR-Extraktion als root übernimmt diese Archivmodi; die Shell-Umask `0022` schützt diesen Schritt allein nicht. Die bereits vorhandene Sicherheitsprüfung lehnt diese gruppenschreibbaren Releasepfade korrekt ab. Der bisherige isolierte Operatorablauf hatte Git synthetisch ersetzt und diesen realen Archivfall nicht abgedeckt.

Update und Erstinstallation setzen jetzt beim tatsächlichen Git-Export ausdrücklich `tar.umask=0022` und exportieren die zuvor erfasste Commit-ID. Die Erstinstallation schreibt genau dieselbe ID in `SOURCE_COMMIT`. Der Schutz gegen fremdveränderbare Releasepfade bleibt vollständig erhalten. Es gibt keine pauschale Rechteänderung an bestehenden Releases, Datenverzeichnissen oder Sicherungen.

## Nachweise

Die neuen [Archivregressionen](../scripts/test_release_archive.py) erzeugen ein echtes temporäres Git-Repository und führen die tatsächlichen Exportbefehle beider Installer aus. GNU tar übernimmt dabei mit `--same-permissions` die Archivmodi wie bei einer Root-Extraktion. Geprüft werden lokale Git-Konfigurationen `0000` und `0002`, Dateirechte, ausführbare Dateien, unveränderte Inhalte, Ausschluss anderer Dateien und die Bindung an den erfassten Commit trotz später geändertem HEAD. Die Tests reproduzierten den Fehler vor der Korrektur. Sie laufen vor den bestehenden isolierten Operatorprüfungen.

Lokale Abnahme: zwei reale Git-/TAR-Regressionsmethoden grün, alle 60 bestehenden Operatorfälle im netzlosen Container grün. Die 116 Gmail-/Anhangsverträge waren vor und nach der Korrektur grün. Bashsyntax und Diffprüfung sind sauber.

Der [Hotfix-PR](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/pull/6) enthält den genauen Test- und CI-Nachweis. Änderungen an App-, Backend- und Browser-Laufzeitquellen sowie Datenbankschema sind nicht erforderlich. Das bereits geprüfte Windows-Online-Paket aus dem vorherigen Stand bleibt verwendbar.

## Erneuter Updateversuch

Nur den vollständig geprüften Hotfix-Commit verwenden; die gepinnte Befehlsfolge steht in der Übergabe. Zuerst unter Windows in PowerShell verbinden:

```powershell
ssh -i "$env:USERPROFILE\.ssh\smartplan_hetzner" root@office.smartplan-hofmann.de
```

Im SSH-Serverfenster den laufenden alten Dienst und die HTTPS-Bereitschaft prüfen. Ein offenes `UPDATE_IN_PROGRESS`-Journal muss untersucht werden; es wird nicht blind entfernt. Der vorhandene Updater prüft diese Bedingungen vor dem neuen Versuch und legt ein neues getrenntes Release an. Die beim abgebrochenen Versuch erhaltenen Dateien und Sicherungen bleiben bestehen.

Nach Erfolg muss `/ready` weiterhin Version `0.12.0-online-pilot`, physisches Schema `7` und `business_suite` melden. Die führende Sevdesk-Nutzung und die vorhandenen Freigaben für Schnittstellen werden durch diesen Hotfix nicht umgestellt.
