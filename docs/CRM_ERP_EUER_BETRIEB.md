# EÜR-Vorbereitung: Geldflüsse und Wiederherstellung

Stand: 02.11.2026. Dieser Abschnitt beschreibt E1a, das belegte EUR-Vorjournal.
Es erfasst bestätigte Geldflüsse mit Herkunft und ersetzt noch keine vollständige
EÜR, Steuerberechnung, Kassenführung oder Bankabstimmung. Es löst keine Zahlung
aus. Die erste vollständige Buchhaltung ist für ein Einzelunternehmen mit EÜR
vorgesehen; der tatsächliche Umsatzsteuerstatus ist noch offen.

## Benutzung

Im Bereich **Finanzen → EÜR-Vorbereitung** stehen Geldkonten, vorhandene
Kundenzahlungen, geprüfte Eingangsbelege und das Vorjournal zur Verfügung.
Browser und Flutter verwenden dieselben Quellen und Berechtigungen. Die
Kennzeichnung „Nur freigegebene Quellen“ gilt auch für Seitenzahlen und Treffer:
ein eingeschränkter Benutzer sieht keinen Nachweis des vollständigen Bestands.
Ein ausgewähltes Projekt begrenzt diese globale Ansicht nicht.

Der Eigentümer kann die globalen Rechte `accounting.read`, `accounting.prepare`
und `accounting.admin` ausdrücklich vergeben. Lesen verlangt zusätzlich global
`finance.read`, Geldflüsse erfassen `accounting.prepare`, Geldkonten anlegen oder
ändern `accounting.admin`. Die vorhandenen Rechte auf Rechnungen, Projekte und
Eingangsbelege gelten zusätzlich. Diese Rechte sind keine Mitarbeiterdefaults;
projektbezogene Accountingfreigaben werden abgewiesen.

1. Ein Geldkonto mit stabilem Code, verständlichem Namen und Art Bank, Bargeld
   oder Zahlungsdienst anlegen. Die Währung ist EUR. Es wird keine Bankverbindung
   eingerichtet. Namen und Aktivstatus lassen sich mit neuer Version ändern;
   bestehende Geldflüsse behalten ihre bestätigte Kontoversion.
2. Eine bestehende Kundenzahlung erst nach Abgleich mit dem tatsächlichen
   Geldfluss übernehmen. Konto, Zahlungsdatum und eindeutige Nachweisreferenz
   bestätigen. Die vorhandene Zahlung und ihre Rechnungszuordnungen bleiben
   unverändert; ihre Übernahme erzeugt keinen zweiten Zahlungseingang oder
   veränderten offenen Posten. Eine Zahlung kann genau einmal übernommen werden.
3. Bei Auszahlungen zuerst das Eingangsoriginal über den vorhandenen Finanzablauf
   erfassen und prüfen. Dann Konto, tatsächliches Zahlungsdatum, Nachweisreferenz,
   Betrag und Verwendungszweck bestätigen. Teilzahlungen sind möglich; ihre Summe
   darf den geprüften Bruttobetrag nicht überschreiten. Derselbe Originalinhalt
   unter einer anderen Beleg-ID eröffnet keinen zweiten Auszahlungsbetrag.
4. Das Vorjournal zeigt bestätigte Herkunft und Kontoversion. Steuerliche
   Einordnung bleibt `unclassified`; fehlendes Steuerprofil und fehlender
   ursprünglicher Bezug alter Rückerstattungen bleiben als Klärungsfälle sichtbar.

Beträge werden centgenau ohne Rundung angenommen. Die Nachweisreferenz muss den
Geldfluss auf dem Konto eindeutig identifizieren. Für den Dublettenvergleich
werden Unicode-NFKC, Groß-/Kleinschreibung und mehrfache Leerzeichen normalisiert;
die Anzeige bewahrt die getrimmte Schreibweise. Nur Datum und Betrag genügen
nicht als eindeutiger Zahlungsnachweis.

Nach unklarer Übertragungsantwort denselben vorgemerkten Vorgang erneut senden.
Clients bewahren dessen ursprüngliche Anfrage-ID und bestätigte Versionen im
Sitzungsspeicher. Sie erstellen daraus keine heimlich aktualisierte Buchung.
Nach Neustart oder Sitzungswechsel zuerst den Serverstand prüfen. Rechte- und
Betriebssperren gelten auch bei Wiederholungen. Ändert sich die Belegprüfung
nach einer Auszahlung, bleiben die alten Nachweise erhalten und weitere
Auszahlungen sind bis zur späteren fachlichen Klärung gesperrt. E1a enthält
noch keine Korrektur-/Stornooberfläche.

## Wiederherstellung einer lokalen SQLite-Sicherung

Eine Wiederherstellung erhält Geldflüsse, Originale und Historie. Bei einem
Businessbestand setzt sie eine Finanzsperre und eine neue Restore-ID. Lesen
bleibt im Rahmen der Rechte möglich; neue Finanzvorgänge sind bis zum
Betreiberabgleich gesperrt. Eine normale Migration setzt diese Sperre nicht.

Der Abgleich erfolgt mit dem im Quell-/Windows-Supportpaket enthaltenen
`scripts/reconcile-accounting-restore.py`. Es ist eine lokale Betreiberaktion,
keine HTTP-Funktion und keine zusätzliche Mitarbeiterberechtigung.

1. Alle Apps und Server mit Zugriff auf diese Datenbank vollständig beenden.
   Sicherung, vorhandenen Originalbestand und unabhängig vorhandene Zahlungs-,
   Beleg- und Versandnachweise erhalten. Den vollständigen Zeitraum seit dem
   Sicherungszeitpunkt abgleichen; ein Hash derselben alten Sicherung kann
   zwischenzeitlich erfolgte Zahlungen nicht erkennen.
2. Den tatsächlich wiederhergestellten Stand lesend ermitteln. Aus dem
   Paket-/Repositoryhauptverzeichnis mit dem eingerichteten Backend-Python:

   ```sh
   python scripts/reconcile-accounting-restore.py --database /pfad/wiederhergestellt.sqlite --inspect
   ```

   Dieser Aufruf erzeugt keine Tabellen und gibt keine Freigabe. Die ausgegebenen
   Restore-ID, Nummernhorizonte und der Accountinghorizont dienen dem Vergleich.
   Unter Windows dieselben Argumente mit dem eingerichteten privaten Python und
   entsprechendem Windows-Dateipfad verwenden.
3. Einen UTF-8-JSON-Prüfbericht gemäß [Schema 2](CRM_ERP_EUER_E1A_API.md#betreiberabgleich)
   erstellen. Er enthält genau `schema:2`, `restore_id`, `reviewed_by`,
   `reviewed_at` mit Zeitzone, `number_horizons`, `outbound_reconciled:true`,
   `accounting_horizon`, `accounting_reconciled:true` und
   `accounting_external_review`. Letzteres enthält `reviewed_since_backup:true`,
   den SHA-256 des **unabhängigen** Prüfungsnachweises als `evidence_sha256` und
   eine aussagekräftige `note` über Quellen, Zeitraum und Ergebnis. Alle
   Bestätigungen erst nach der tatsächlichen Prüfung setzen. Den unabhängigen
   Nachweis separat geschützt aufbewahren. Ungeklärte Differenzen nicht durch
   Änderung des Hashes oder manuelle Datenbankkorrektur verdecken.
4. Bericht privat speichern: unter POSIX höchstens Eigentümerrechte, etwa
   `chmod 600 abgleich.json`; unter Windows Zugriff über die Dateirechte auf die
   zuständigen Betreiber begrenzen. Keine Symlinks, keine öffentlichen Ablagen.
   Bericht maximal 4 MiB; doppelte Felder und ungültige JSON-Werte werden
   abgewiesen. Die Anwendung weiter geschlossen halten und freigeben:

   ```sh
   python scripts/reconcile-accounting-restore.py --database /pfad/wiederhergestellt.sqlite --evidence /pfad/abgleich.json --application-stopped
   ```

5. Die erfolgreiche Quittung zusammen mit Bericht und unabhängigem Nachweis
   aufbewahren. Sie enthält den vom Werkzeug berechneten SHA-256 der tatsächlich
   gelesenen Berichtsbytes. Eine unveränderte Wiederholung ist wirkungsfrei.
   Erst danach App/Server starten und vorhandene Geldflüsse prüfen.

Das Werkzeug legt keine fehlende Datenbank an und migriert keine Altstände.
Es prüft Original-/Historienintegrität und den aktuellen Stand innerhalb einer
exklusiven Schreibtransaktion. Der Schalter `--application-stopped` bestätigt
den zuvor erfolgten Stopp; die Datenbanksperre beweist nicht, dass alle
WAL-Leseprozesse beendet wurden. Fachliche Richtigkeit oder externe Vollständigkeit
kann das Werkzeug nicht aus einem Hash beweisen. Bei Ablehnung bleibt die
Finanzsperre erhalten. Die Ursache vor einer erneuten Freigabe klären.

PostgreSQL verwendet weiterhin den vorhandenen Release-/Operatorpfad mit
getrennter Datenbankrolle, gestoppten Datenbanknutzern und Datenschutzabgleich.
Auch dort ist bei installiertem Accountingmodul Schema 2 erforderlich, selbst
bei leerem Vorjournal. Die lokale SQLite-CLI ist nicht für PostgreSQL bestimmt.

## Grenzen und nächste Schritte

Zuordnung zu Buchhaltungs-/Steuerkomponenten, Quellenkorrekturen, Perioden,
Anlagen, Privatanteile, Lohnbuchungen und Beraterpaket folgen gesondert. Ein
Bankkonto in dieser Oberfläche ist kein Bankfeed; Bargeldkonto ist kein
abgenommenes Kassenbuch. Keine vollständige Jahres-EÜR oder amtliche Meldung
ableiten. Die Quellenlisten prüfen aktuell alle sichtbaren Originalnachweise
vor der Seitenauswahl; eine Leistungsfreigabe für große Bestände liegt nicht vor.
