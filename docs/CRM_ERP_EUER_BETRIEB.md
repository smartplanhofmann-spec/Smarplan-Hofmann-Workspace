# EÜR-Vorbereitung: Geldflüsse und Wiederherstellung

Stand: 02.11.2026. Dieser Abschnitt beschreibt E1a, das belegte EUR-Vorjournal,
die zusätzliche Rechnungszuordnung E1b-1 und die dokumentarische
Belegaufteilung E1b-2.
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

## Freie Kundenzahlungen einer Rechnung zuordnen

Bei einer bereits übernommenen Kundenzahlung öffnet „Rechnung zuordnen“ den
aktuellen Zuordnungsstand. Die im alten E1a-Nachweis gespeicherte Zuordnung
bleibt die damalige Fassung; die neue Ansicht zeigt zusätzlich bestätigte
Zuordnungen und den tatsächlich noch freien Zahlungsbetrag.

1. Eine angebotene normale finale EUR-Rechnung auswählen. Alle bisherigen
   und neuen Rechnungszuordnungen müssen zu derselben gespeicherten
   Kundennummer gehören. Bei zuvor völlig unzugeordneter Zahlung wird der Kunde
   erstmals ausdrücklich bestätigt; die Software errät ihn nicht aus dem
   Verwendungszweck.
2. Kundenbindung, centgenauen Teilbetrag und einzeilige Begründung prüfen.
   Der Betrag darf weder den freien Zahlungsrest noch den offenen Rechnungsrest
   überschreiten. Ein nicht zugeordneter Überschuss bleibt als solcher erhalten.
3. Die Vorschau aufrufen. Sie zeigt Rechnung, Betrag sowie Zahlungs- und
   Rechnungsrest vorher/nachher. Dieser Schritt speichert keine Zuordnung.
4. Nach Prüfung ausdrücklich bestätigen. Haben andere Vorgänge den Zahlungs-
   oder Rechnungsstand verändert, wird die Bestätigung abgewiesen: Stand neu
   laden und eine neue Vorschau prüfen. Bei verlorener Antwort stattdessen
   denselben unveränderten vorgemerkten Auftrag erneut senden.

Jeder weitere Teilbetrag ist ein eigener bestätigter Vorgang. Der Eintrag
erzeugt keine neue Zahlung oder Steuerbuchung. Er wirkt gemeinsam mit den
ursprünglichen Zuordnungen auf Zahlungslisten, offene Posten, Mahnvorschläge
und neu erzeugte vorhandene Prüfexporte. Schon gespeicherte Exporte behalten
ihre Originalbytes. Eine bestehende Erstattung verändert den Rechnungsrest,
öffnet aber nicht erneut das Budget derselben ursprünglichen Zahlung.

Zusätzlich zu den E1a-Leserechten werden für Vorschau und Bestätigung global
`accounting.prepare`, global `finance.write` und entsprechende Rechte für alle
bisherigen und neu betroffenen Projekte benötigt. Nach einer Zuordnung zu
einem weiteren Projekt können deshalb bisher sichtbare Gesamtzahlungen für
eingeschränkte Benutzer verborgen werden. Die offenen Posten einer weiterhin
berechtigten Rechnung bleiben trotzdem vollständig berechnet. Ursprünglich
private unzugeordnete Zahlungen bleiben auf Eigentümer/Ersteller begrenzt.

Dieser Abschnitt unterstützt normale Rechnungen ohne Abschlags-/Schluss- oder
Stornobezug. Erstattungsursprünge und steuerliche Komponenten werden noch nicht
zugeordnet. Bestätigte Zuordnungen lassen sich hier noch nicht aufheben oder
ersetzen; vor der Bestätigung müssen Rechnung, Kunde und Betrag stimmen.

## Netto- und ausgewiesene Steueranteile dokumentieren

Im Zahlungsnachweis öffnet „Beleganteile aufteilen“ die zugehörigen ganzen
Quellenanteile: ursprüngliche Rechnungszuordnungen, zusätzliche bestätigte
Zuordnungen oder die einzelne bestätigte Auszahlung auf einen geprüften
Eingangsbeleg. Ein unzugeordneter Zahlungsrest muss zuvor gesondert geklärt
werden. Die Aufteilung verändert weder die Zahlung noch offene Posten.

1. Einen noch nicht dokumentierten Quellenanteil auswählen. Sein Gesamtbetrag
   ist fest. Rechnungsnummer, Kunde/Lieferant und Belegquelle prüfen.
2. Bei mehreren ausgewiesenen Steuergruppen die Bruttobeträge ausdrücklich
   verteilen. Ihre Summe muss genau dem gewählten Anteil entsprechen; jede
   Gruppe darf höchstens ihren angezeigten verfügbaren Rest verbrauchen.
   Bei einer Gruppe kann der gesamte Anteil vorbelegt sein.
3. „Vorschau prüfen“ zeigt die daraus berechneten Netto-/ausgewiesenen
   Steueranteile und die Gruppenreste. Rundungscents werden über alle bereits
   bestätigten Anteile desselben Belegs hinweg erhalten. Bei Eingangsbelegen
   werden nur die bestätigten Gesamtsummen der festen Prüfversion verwendet;
   es wird kein Steuersatz und kein Vorsteueranspruch daraus abgeleitet.
4. Die Vorschau prüfen und die Aufteilung gesondert bestätigen. Eine veraltete
   Vorschau wird abgewiesen. Bei verlorener Antwort den exakt vorgemerkten
   Vorgang wiederholen; keine zweite neue Bestätigung anlegen.

Die Historie hält die damaligen Werte fest. Jede ganze Quellenportion ist nur
einmal verwendbar. Eine spätere oder rückdatierte Zahlung verändert keine
bereits bestätigten Rundungscents. Eine vollständig bezahlte Rechnung oder ein
inaktives Geldkonto verhindert die Dokumentation vorhandener Anteile nicht.
Hat sich die Eingangsprüfung seit der Auszahlung geändert, bleibt eine neue
Aufteilung bis zur Klärung gesperrt; frühere Nachweise bleiben lesbar.

Erstattungen werden in diesem Abschnitt noch nicht ihren ursprünglichen
Komponenten zugeordnet. Sie geben deshalb keine Gruppenkapazität automatisch
wieder frei. Ein erneuter tatsächlicher Zahlungseingang bleibt als Geldfluss
erfasst, auch wenn seine Aufteilung bei erschöpfter Gruppe noch ungeklärt ist.
Aufteilungen lassen sich noch nicht aufheben oder ersetzen. Die steuerliche
Einordnung bleibt ausdrücklich offen; dies ist keine fertige EÜR.

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
3. Einen UTF-8-JSON-Prüfbericht im von `--inspect` ausgegebenen
   `evidence_schema` erstellen: [Schema 2](CRM_ERP_EUER_E1A_API.md#betreiberabgleich)
   für einen reinen E1a-Bestand, [Schema 3](CRM_ERP_EUER_E1B1_API.md#restore-und-clients)
   mit zusätzlichem Zuordnungsmodul ohne Komponenten oder
   [Schema 4](CRM_ERP_EUER_E1B2_API.md#wiederherstellung-und-clients)
   mit Komponentenmodul, auch wenn dessen Tabellen noch leer sind.
   Er enthält genau `schema`, `restore_id`, `reviewed_by`,
   `reviewed_at` mit Zeitzone, `number_horizons`, `outbound_reconciled:true`,
   `accounting_horizon`, `accounting_reconciled:true` und
   `accounting_external_review`. Letzteres enthält `reviewed_since_backup:true`,
   den SHA-256 des **unabhängigen** Prüfungsnachweises als `evidence_sha256` und
   eine aussagekräftige `note` über Quellen, Zeitraum und Ergebnis. Alle
   Bestätigungen erst nach der tatsächlichen Prüfung setzen. Den unabhängigen
   Nachweis separat geschützt aufbewahren. Ungeklärte Differenzen nicht durch
   Änderung des Hashes oder manuelle Datenbankkorrektur verdecken.
   Schema 3 verwendet als `accounting_horizon` den vollständig ausgegebenen
   zusammengesetzten Horizont mit `schema_version:2`, `prejournal` und
   `allocations`. Die ursprüngliche E1a-Prüfsumme bleibt darin unverändert;
   der zusätzliche Teil umfasst alle Zuordnungseinträge und Quittungen.
   Schema 4 verwendet `schema_version:3` und zusätzlich `components`.
   Dieser dritte Teil bindet alle bestätigten Aufteilungen, Gruppenzeilen und
   Quittungen. Beide bisherigen Teilhorizonte bleiben unverändert enthalten.
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
Auch dort ist der Bericht für den gesamten installierten Umfang erforderlich:
Schema 2 nur mit E1a, Schema 3 mit zusätzlicher Rechnungszuordnung ohne
Komponenten oder Schema 4 mit Komponentenmodul, selbst bei leeren Tabellen.
Die lokale SQLite-CLI ist nicht für PostgreSQL bestimmt.

## Grenzen und nächste Schritte

Steuerliche Freigabe der dokumentarischen Komponenten, Erstattungsbezüge,
Quellenkorrekturen, Perioden,
Anlagen, Privatanteile, Lohnbuchungen und Beraterpaket folgen gesondert. Ein
Bankkonto in dieser Oberfläche ist kein Bankfeed; Bargeldkonto ist kein
abgenommenes Kassenbuch. Keine vollständige Jahres-EÜR oder amtliche Meldung
ableiten. Die Quellenlisten prüfen aktuell alle sichtbaren Originalnachweise
vor der Seitenauswahl; eine Leistungsfreigabe für große Bestände liegt nicht vor.
