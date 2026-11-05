# Kontrollierter Abschluss nach der Parserreparatur

Der Nutzer bestätigt im tatsächlichen SSH-Terminal am 05.11.2026 um 20:23 UTC:
Sandbox-Startprüfung bestanden, Importcontroller anschließend mehrfach idle,
drei aktive Dienste und API-/Datenbankbereitschaft ok im Businessmodus mit
Schema 7. Die Kennung 0.12.0-online-pilot ist die beibehaltene API-Kompatibilität.
[Erfasster Befund](evidence/project-update-forward-2026-11-05/observed-parser-repair-success.json).
Das ist noch kein Nachweis eines formal abgeschlossenen Updatejournals oder
einer vollständigen Kunden-/Geräteabnahme.

Der vorbereitete [Abschlusshelfer](../deploy/hetzner/online/complete-online-update.py)
wird mit dem installierten API-Python als root und einem ausdrücklich benannten
vollständigen Zielcommit ausgeführt. Der bestehende globale Verwaltungslock
verhindert parallele Updates. Das tatsächlich aktive App-Release bestimmt das
Journal; es wird kein Zeitstempel abgeschrieben oder das neueste Verzeichnis
gewählt. App, API-Venv, SOURCE_COMMIT und geschützte Journalmetadaten müssen
zusammenpassen. Nur bereits aktivierte Updates werden berücksichtigt.

Der Helfer liest die Dienstkonfiguration ohne Ausgabe der Zugangsdaten und
vergleicht Kandidatenbindung, Prozessumgebung und tatsächliches Arbeitsverzeichnis
der laufenden API und des Controllers. Die API-Bereitschaft muss zum vorhandenen
Migrationsbericht passen; der lokale öffentliche HTTPS-Weg muss ohne Anmeldung
401 liefern. Parserpakete müssen dem aktuellen Quell-Lock entsprechen. Die
Sandbox-Prüfung und die Arbeitsschleife werden nur aus der aktuellen systemd-
Invocation und für die Schleife aus dem aktuellen Controller-PID akzeptiert.
Historische Fehlermeldungen oder alte erfolgreiche Starts reichen nicht aus.

Ein zuvor aktiver Lead-Antwort-Timer wird nur entsprechend dem gespeicherten
Journalzustand wieder aufgenommen. Der damalige Zustand des Sicherungstimers
wurde vom ursprünglichen Updater nicht gespeichert: sein jetziger aktiver oder
inaktiver Zustand wird protokolliert und erhalten; ein fehlgeschlagener Timer
verhindert den Abschluss. Es wird kein früherer Timerzustand erfunden.

Erst nach allen Prüfungen schreibt der Helfer einen neuen privaten Nachweis
forward-verification.json, setzt die Phasen atomar auf active und entfernt den
zugehörigen globalen Marker. Verzeichnisse werden synchronisiert. Originales
Migrationsprotokoll, Metadaten, Datenbanken, Parser-Sicherung und bisherige
Releases bleiben erhalten. Der Helfer öffnet keine Datenbankverbindung und
führt keine Migration, Rücksicherung oder Paketinstallation aus. Vorhandene
neue Schreibvorgänge werden nicht mit einem alten Zeilenfingerabdruck verglichen.

Bei einer fehlgeschlagenen Prüfung bleibt der Marker erhalten. Eine Unterbrechung
zwischen den abschließenden Dateischritten kann nach erneuter Prüfung vorwärts
abgeschlossen werden. Eine bereits bestätigte Fertigstellung wird ebenfalls
neu geprüft, ohne wieder eine Updatesperre anzulegen.

Lokale Prüfungen: echte temporäre Dateien, Dateirechte, flock, atomare Schreib-
und Fehlerpfade sowie ein echter synthetischer Prozess für die /proc-Bindung.
Systemd, HTTP und Paketversionen bleiben in diesen Tests simulierte Grenzen.
Die tatsächliche Ausführung des Abschlusshelfers auf dem Server ist noch offen.

Gezielt sind 22 Fälle bestanden; der gesamte Operatorlauf besteht mit 82 Fällen
ohne Skip in 231 Sekunden. [Prüfnachweis](evidence/project-update-forward-2026-11-05/forward-completion-verification.json).

```bash
python3 -m unittest discover -s tests/update_flow -p test_forward_completion.py -v
```

Die noch offene automatische Parser-Kompatibilitätsprüfung vor zukünftigen
API-Updates bleibt ein eigener Operatorpunkt. Dieser incidentbezogene Abschluss
ersetzt keine allgemeine Auslieferungs- oder fachliche Freigabe.
