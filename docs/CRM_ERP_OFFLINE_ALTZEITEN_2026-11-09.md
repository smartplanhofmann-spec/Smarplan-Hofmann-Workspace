# Alte native Zeitereignisse anhand ihres erhaltenen Kerns prüfen

Die vorhandene Ansicht **Alte Offline-Aufträge prüfen** kann zusätzlich einen
bereits angenommenen alten Zeitauftrag lesend bestätigen. Das ergänzt
R11.02/R11.03; es ist keine vollständige V1-Migration. Nach aktueller
Firmenanmeldung und Geräteentsperrung erscheinen zunächst nur **Zeitauftrag N**
und der Prüfstatus. **Ursprüngliches Zeitereignis prüfen** zeigt erst nach
vollständigem Abgleich Beginn, Pause, Fortsetzung oder Ende und den damaligen
Zeitpunkt in Gerätezeit. Stundensummen, Kosten, Standort und heutiger
Timerstatus werden daraus nicht als damaliges Original ausgegeben.

Die Grundlage stammt aus dem tatsächlichen historischen V1-Format des
Quellstands `7b54dddfeb85bdef718bf4c76d369b0f673a5ede`: eingefrorener
Zeitauftrag sowie getrennt erhaltene alte Mitarbeiter- und Kategoriebasis.
Die Basis wird niemals aus dem heutigen Profil einer neuen Firma ergänzt.
Fehlt sie, bleibt der Auftrag unter den übrigen erhaltenen Aufträgen;
es erfolgt keine Zeitabfrage und kein Profilabruf zur Rekonstruktion.
Nicht unterstützte Zusatzfelder oder nicht exakt normierbare Zeitpunkte
bleiben ebenfalls ungeklärt.

## Enger additiver Serververtrag

`POST /api/v1/business/offline/recovery/time-event` ist ausschließlich ein
lesender Metadatenabgleich. Die sieben zulässigen Felder sind
`schema_version:3`, zufällige `nonce`, `kind:time_event_core`, `project_id`,
`entry_id`, `request_id` und `request_hash`. Der Client sendet weder den alten
Befehl noch Mitarbeiter-/Kategoriebasis, Zeitpunkt, Position oder Cache.
Der neue Featuremarker heißt `offline_time_event_recovery` und wird nur bei
tatsächlich gebundener Instanz angeboten. Fehlende Fähigkeiten eröffnen
keinen Ersatzweg. Bestehende V2-Planabgleiche behalten ihren Vertrag.

Der Server verlangt frische normale Anmeldung, eigene ursprüngliche
Ereigniszuordnung, aktives Mitarbeiterprofil, `time.own`, aktuellen Projektzugang
und lesbares Zeitmodul. Beide Offline-Tokenarten bleiben auch mit gültigem
Bindungsheader ausgeschlossen. Die Abfrage funktioniert im ausdrücklich
freigegebenen Lesemodus, ohne Zeit-Schreibzugriff zu eröffnen. Doppelte Felder,
Zusatzfelder, Queryparameter, falsche Methode und mehr als 4.096 Rohbytes
werden sowohl im Onlinedienst als auch im paketierten lokalen Server verworfen.

Der historische Ereigniskern umfasst `entry_id`, `employee_id`, `project_id`,
`category_id`, `action`, normiertes UTC-`occurred_at`, `device_id`, `sequence`
und die ursprüngliche erwartete `revision`. Sein SHA-256 wird unabhängig aus
dem tatsächlichen gespeicherten Ereignis rekonstruiert und gegen den
gespeicherten sowie den separat erhaltenen Clienthash geprüft. Positionsdaten
und die ursprüngliche Schreibweise des gesendeten Zeitpunkts sind nicht in
diesem alten Hash enthalten. Diese Erweiterung bestätigt deshalb ausdrücklich
den Ereigniskern und keinen vollständigen damaligen Rohbefehl oder GPS-Beleg.

Die Antwort bindet die frische Nonce, den vollständigen Abfragehash, Instanz,
Konto und alle Abfragebezüge. Das Original enthält Ereignis-/Auftragskennung,
ursprünglichen Akteur, Kernhash, gespeicherten Empfangszeitpunkt und Kern.
Der Client prüft die exakte Form, sämtliche Kernwerte, Ganzzahltypen und Hashes
gegen seinen separat erhaltenen alten Kern. Der Empfangszeitpunkt wird auf
sein Format geprüft, gehört jedoch nicht zum historischen Kernhash und wird
nicht als separat bewiesene Zeit angezeigt. Die Antwort ist `no-store`.

## Erhaltung und Grenzen

Tagesfreigabe und Standortlöschung verändern diesen historischen Kern nicht.
Aktuelle Tages- oder Timerantworten ersetzen die Originalprüfung nicht.
Fehlender Treffer, veränderte Quelle, entzogene Rechte oder Verbindungsfehler
bleiben **Annahme ungeklärt**. Insbesondere erzeugt kein solcher Fehler eine
bestätigte Nichtannahme oder Erlaubnis zum erneuten Senden.

Vor jeder Prüfung werden Anmeldung, Firma, Fähigkeiten und der vollständige
verschlüsselte Altbestand erneut geprüft. Geänderte Dateigeneration oder
Inhalte blockieren die Abfrage. Zugangswechsel und echte App-Pause löschen
den gelesenen Arbeitsspeicher; verspätete Antworten dürfen ihn nicht erneuern.
Dateien, Geräteschlüssel, alte Token, Auswahl und Warteschlangen bleiben
unverändert. Es gibt keine automatische Abfertigung oder Löschung bestätigter
Altaufträge und keine dauerhafte neue Firmenzuordnung des gesamten Altbestands.

## Ausgeführte Nachweise

- 81 betroffene Backendfälle bestehen, darunter elf neue tatsächliche
  MFA-/Flask-/TCP-Fälle, bisherige Planabgleiche, Rechte-/Firmenbindung,
  Zeiterfassung, Schema und ursprüngliche Projekt-/Material-/Reisequittungen.
- Fünf tatsächliche PostgreSQL-Fälle bestehen mit getrennten Verbindungen,
  Runtime-Rechten, unveränderten Tabellenfingerprints, Tagesfreigabe,
  Standortlöschung und wirklichem Dump/Restore. Fehlende oder beschädigte
  Originale erzeugen keine Nichtannahmefreigabe.
- 64 betroffene Appfälle bestehen einschließlich tatsächlicher erneuter
  MFA-/HTTP-Kommunikation mit zwei Firmen bei gleichen Konto-/Projekt-/Ereignis-
  kennungen, altem verschlüsseltem Dateispeicher, 390px-Ansicht, Lebenszyklus,
  Navigation und bisheriger V2-Zeit-/Planarbeit. Keine Altdaten werden übertragen
  oder umgeschrieben. Die vollständige Appanalyse besteht ohne Befund.

Der erste gemeinsame Appaufruf besaß nicht den erforderlichen Python-Pfad;
drei HTTP-Aufbauten scheiterten vor dem Serverstart. Der erste Paketaufruf
hatte kein von ihm vorausgesetztes `backend/.venv`. Die korrigierten Aufbauten
verwenden die vorhandene Projektumgebung. Die fehlgeschlagenen Rohläufe bleiben
erhalten und werden nicht als erfolgreich ausgegeben.
[Quellhashes und unveränderte Rohläufe](evidence/offline-legacy-time-core-2026-11-09/manifest.json).

Offen bleiben nicht vollständig belegte alte Zeiten, weitere Warteschlangen,
geschützte Konfliktklärung und vollständige Übernahme. Reale Geräteentsperrung,
Installation, Kundenabnahme und eine neue Serverinstallation sind davon
getrennt. Der zuletzt vom Nutzer bestätigte Server bleibt A93.
