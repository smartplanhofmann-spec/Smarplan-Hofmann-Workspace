# EÜR-Vorbereitung: Geldflüsse und Wiederherstellung

Stand: 03.11.2026. Dieser Abschnitt beschreibt E1a, das belegte EUR-Vorjournal,
die zusätzliche Rechnungszuordnung E1b-1 und die dokumentarische
Belegaufteilung E1b-2 sowie die ausdrücklichen Erstattungsursprünge E1b-3a.
Die genaue Wiederverwendung zurückgegebener Beleganteile E1b-3b ist im unten
beschriebenen Umfang implementiert. Der Implementierungsvertrag ist keine
Gesamtabnahme.
Ausgeführte Prüfungen und ihre Grenzen stehen im
[Fortschrittsbericht](CRM_ERP_FORTSCHRITT.md).
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
   ursprünglicher Bezug alter Rückerstattungen bleiben im damaligen E1a-Nachweis
   sichtbar. Neue Ursprungsbindungen werden in einer eigenen aktuellen Ansicht
   dokumentiert; sie schreiben diesen historischen Nachweis nicht um.

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
Stornobezug. Dieser Zuordnungsschritt allein dokumentiert noch keine
Erstattungsursprünge oder Netto-/Steueranteile; dafür gelten die folgenden
getrennten Abläufe. Bestätigte Zuordnungen lassen sich hier noch nicht aufheben oder
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

Die positive Aufteilung allein ordnet Erstattungen noch nicht ihren
ursprünglichen Komponenten zu; diese Bindung erfolgt im folgenden eigenen
Erstattungsablauf. Auch eine dort bestätigte Bindung gibt noch keine
Gruppenkapazität automatisch frei. Ein erneuter tatsächlicher Zahlungseingang
bleibt als Geldfluss
erfasst, auch wenn seine Aufteilung bei erschöpfter Gruppe noch ungeklärt ist.
Aufteilungen lassen sich noch nicht aufheben oder ersetzen. Die steuerliche
Einordnung bleibt ausdrücklich offen; dies ist keine fertige EÜR.

## Ursprüngliche Zahlungsanteile einer Erstattung dokumentieren

Beim übernommenen Kundenerstattungs-Geldfluss öffnet „Erstattungsursprung zuordnen“
die noch ungeklärten ursprünglichen Rechnungsanteile. Ein Anteil wird immer
als Ganzes dokumentiert. Erzeugt werden ausschließlich Nachweise zu bereits
erfassten Geldflüssen; es wird keine weitere Zahlung ausgeführt oder gebucht.

1. Den festen Rechnungsanteil der Erstattung auswählen. Rechnung, Kunde,
   Betrag, Zahlungsdatum und Nachweisreferenz prüfen. Noch gar keiner Rechnung
   zugeordnete Erstattungsbeträge müssen gesondert geklärt werden.
2. Die passenden ursprünglichen dokumentierten Zahlungsanteile ausdrücklich
   wählen. Datum, Zahlungsnachweis, Verwendungszweck, Nummer der dokumentierten
   Aufteilung und Beleggruppe unterscheiden die angebotenen Ursprünge. Nur
   Ursprünge derselben Rechnung mit einem Zahlungsdatum spätestens am
   Erstattungsdatum kommen infrage. Die Software errät keine Zuordnung.
3. Die positiven Bruttobeträge auf die gewählten Ursprünge verteilen. Ihre
   Summe muss genau dem festen Erstattungsanteil entsprechen; jeder Ursprung
   darf höchstens seinen angezeigten verbleibenden Betrag tragen.
4. Die Vorschau prüfen und gesondert bestätigen. Netto- und ausgewiesene
   Steuercents stammen aus den ursprünglichen Aufteilungen; auch mehrere
   Teilerstattungen führen zusammen exakt auf diese Cents zurück. Bei einem
   konkurrierend geänderten Ursprung neu laden und eine neue Vorschau prüfen.
   Bei verlorener Antwort denselben unveränderten vorgemerkten Auftrag senden.

Die Historie zeigt die damalige Bestätigung. Spätere Stornierung der Rechnung
oder Stilllegung eines Geldkontos verhindert eine dokumentierte echte
Erstattung auf einen gültigen alten Zahlungsanteil nicht. Vollständige aktuelle
Quellrechte auf Erstattung und sämtliche verwendeten ursprünglichen Zahlungen
gelten auch für Historie und Wiederholung. Fehlt ein benötigter Zugriff, wird
der gesamte zugehörige Erstattungsstand verborgen.

Dieser Schritt gibt keine Beleggruppenkapazität für neue Einnahmen frei und
ist keine steuerliche Gegenbuchung. Der ungeklärte Betrag bezieht sich auf
den geöffneten Erstattungsgeldfluss; er beweist keine vollständige Klärung
aller Erstattungen einer Rechnung oder des Unternehmens.

## Zurückgegebene Beleganteile erneut verwenden

Dieser Ablauf beschreibt den
[Implementierungsvertrag zur Wiederverwendung](CRM_ERP_EUER_E1B3B_API.md).
Ausgeführte Prüfungen und noch ausstehende Nachweise sind im
[Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_E1B3B.json) getrennt festgehalten.

Bei einem erneuten bestätigten Kundenzahlungseingang können die genau
zurückgegebenen Netto-/Steuercents derselben normalen EUR-Rechnung wieder
verwendbar werden. Voraussetzung sind bereits bestätigte Erstattungsursprünge.
Eine Rechnung wird mit allen ihren Beleggruppen gemeinsam übernommen; ihre
alten Aufteilungen und Erstattungsnachweise behalten unverändert ihre Werte.

1. Einen ganzen noch undokumentierten Einnahmenanteil wählen. Der Betrag ist
   fest. Vor der ersten Übernahme müssen sämtliche vorhandenen ausdrücklich
   dieser Rechnung zugeordneten Erstattungsanteile als Geldfluss übernommen
   und mit ihren ursprünglichen Aufteilungen verbunden sein. Das gilt auch
   für bereits in Finanzen erfasste, aber noch nicht ins Vorjournal übernommene
   Erstattungen. Es muss mindestens eine bestätigte Rücknahme zur Übernahme
   bereitstehen.
2. Die verfügbaren Beträge prüfen. Die Ansicht unterscheidet bereits
   verfügbare Reste, zusätzlich zur Übernahme angebotene Rücknahmecents und
   noch nicht freigegebene Rücknahmen. Erst die Vorschau legt fest, welche
   zusätzlichen Cents in diesem Vorgang tatsächlich übernommen werden.
   Bei mehreren Gruppen Bruttobeträge ausdrücklich verteilen; ihre Summe
   muss genau dem ganzen Einnahmenanteil entsprechen.
3. Zahlungsdatum und Rechte prüfen. Für die erste gemeinsame Übernahme darf
   das neue Einnahmendatum nicht vor einem der übernommenen Erstattungsdaten
   liegen. Später gilt je verwendetem Rest die jüngste mitgetragene
   Erstattungsdatumsgrenze. Benötigt werden vollständige aktuelle Rechte auf
   die Einnahme und alle tatsächlich verwendeten Erstattungen samt ihren
   ursprünglichen Zahlungen. Eine ungeklärte Erstattung, ein zu frühes Datum
   oder fehlender Quellzugriff verhindert die zusätzliche Freigabe.
4. Die vollständige Vorschau prüfen. Sie zeigt die neue positive Aufteilung
   und alle zusätzlich übernommenen Gruppenreste. Die erste Übernahme aller
   Rechnungsgruppen und die erste neue Aufteilung werden gemeinsam bestätigt;
   es gibt keine isolierte oder automatische Freigabe. Eine veraltete Vorschau
   neu laden und erneut prüfen.

Vor der ersten Übernahme bleibt eine bisher mögliche ursprüngliche Aufteilung
innerhalb des alten Rests zulässig. So lassen sich noch fehlende ursprüngliche
Zahlungsanteile dokumentieren und danach Erstattungen daran binden. Nach der
Übernahme gibt es keinen Rückwechsel zum früheren Aufteilungsverfahren.

Später ungeklärt hinzugekommene Erstattungen verändern alte Nachweise nicht.
Ein bereits freigegebener, ausreichend datierter Rest bleibt innerhalb seiner
Grenzen nutzbar; zusätzlich noch ungeklärte Rücknahmecents werden dabei nicht
mitverwendet. Unzugeordnete Erstattungsreste werden keiner Rechnung geraten
zugeordnet. Die Ansicht beweist keinen vollständigen Unternehmensabgleich.

Bei verlorener Antwort denselben unveränderten vorgemerkten Vorgang erneut
senden, auch wenn die Rechnung inzwischen übernommen wurde. Ein offener
Vorgang wird nicht automatisch in eine neue Aufteilung umgeschrieben.
Wiederholung und Historie benötigen weiterhin die vollständigen aktuellen
Quellrechte; gespeicherte Details werden bis dahin nicht erneut angezeigt.
Das gilt auch für eine damals mitangezeigte Beleggruppe, aus der die konkrete
Aufteilung keinen Betrag verbraucht hat, wenn deren Rücknahmequellen Teil des
gespeicherten Nachweises sind.

Eine zwischenzeitliche Rechte-, Betriebs- oder Wiederherstellungssperre klärt
den ursprünglichen Übertragungsausgang nicht. Der vorgemerkte
Aufteilungsauftrag bleibt deshalb erhalten. Erst eine erfolgreiche Antwort
oder die ausdrückliche serverseitige Bestätigung, dass genau dieser Auftrag
nicht angenommen wurde, erlaubt einen neuen Vorgang. Diese zusätzliche
Absicherung gilt für Bestätigungen der bisherigen und neuen Belegaufteilung;
andere Vorgangsarten werden dadurch nicht verändert. Eine alte Serverfassung
kann einen unklaren Auftrag nicht allein durch eine gewöhnliche
Konfliktmeldung auflösen.

Weitere Erstattungen können weiterhin vorhandene ursprüngliche Aufteilungen
zurücknehmen. **Neu nach der Übernahme erzeugte Aufteilungen sind in diesem
Schritt noch nicht als Erstattungsursprung unterstützt.** Benötigt eine ganze
Erstattung solche neuen Anteile, bleibt sie ungeklärt; auch eine Mischung
alter und neuer Ursprünge wird nicht teilweise bestätigt.

Der Ablauf erzeugt keine Zahlung, zusätzliche Rechnungszuordnung, OP-Wirkung
oder Steuerbuchung. Offene Posten, Mahnung, Bank-/Zahlungsdaten und frühere
Nachweise behalten ihre jeweilige Wirkung. Lieferantenauszahlungen bleiben im
bisherigen Aufteilungsablauf. Steuerstatus und vollständige EÜR bleiben offen.

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
   mit zusätzlichem Zuordnungsmodul ohne Komponenten,
   [Schema 4](CRM_ERP_EUER_E1B2_API.md#wiederherstellung-und-clients)
   mit Komponentenmodul ohne Erstattungsursprünge,
   [Schema 5](CRM_ERP_EUER_E1B3A_API.md#restorehorizont-und-historische-betreiberquittungen)
   mit Erstattungsmodul ohne Wiederverwendungsmodul oder
   [Schema 6](CRM_ERP_EUER_E1B3B_API.md#horizonte-projektionen-und-nachweisgrenze),
   sobald `business_accounting_capacity` installiert ist. Der gesamte
   installierte Umfang gilt auch bei leeren Tabellen. Die Schema-6-Regeln
   erweitern den technischen Restoreabgleich und ersetzen keine fachliche
   Prüfung der tatsächlich vorhandenen Zahlungs- und Belegnachweise.
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
   Schema 5 verwendet `schema_version:4` mit zusätzlich `refunds`. Dieser
   vierte Teil bindet Erstattungsursprünge, Rücknahmezeilen und Quittungen;
   die drei bisherigen Teilhorizonte bleiben unverändert enthalten.
   Schema 6 verwendet den vollständigen H5-Horizont:

   ```text
   {schema_version:5,prejournal:<H1>,allocations:<A1>,components:<C1>,
    refunds:<R1>,capacity:<K1>}
   ```

   K1 ist ein unabhängiger weiterer Teilhorizont mit exakt
   `schema_version:1`, `table_counts` und `sha256`. Seine Tabellenanzahlen sind
   genau `business_accounting_capacity_handoffs`,
   `business_accounting_capacity_segments`, `business_accounting_capacity_releases`,
   `business_accounting_capacity_entries`, `business_accounting_capacity_lines`
   und `business_accounting_capacity_requests`. Der Hash bindet alle vollständigen
   eigenen Zeilen einschließlich Quittungen nach Integritätsprüfung.
   Die bisherigen H1/A1/C1/R1-Teile bleiben unverändert. Die oben genannten
   äußeren Betreiberfelder und die drei Felder von `accounting_external_review`
   sind auch für Schema 6 exakt dieselben; keine zusätzlichen äußeren Felder.
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

Historische Berichtsschemata behalten ihre festen Felder und Tabellenmengen;
ein alter H4-Bericht erhält kein nachträgliches `capacity`-Feld. Eine bereits
erfolgreiche alte Betreiberquittung darf nur bei unveränderter Restore-ID,
identischen Berichtsbytes, erfüllten Betreiber-/Stillstandsprüfungen und bereits
aufgehobener Sperre wirkungslos wiederholt werden. Ein alter Bericht entsperrt
keine neue Wiederherstellung. Dafür ist stets das Schema für den vollständig
installierten aktuellen Umfang erforderlich.

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
Komponenten, Schema 4 mit Komponenten ohne Erstattungsmodul, Schema 5
mit Erstattungsmodul ohne Wiederverwendungsmodul und Schema 6 bei installiertem
`business_accounting_capacity`, selbst bei leeren Tabellen.
Die lokale SQLite-CLI ist nicht für PostgreSQL bestimmt.

## Grenzen und nächste Schritte

Die Wiederverwendung ist auf die oben beschriebenen Quellen und Fälle begrenzt.
Steuerliche Freigabe der dokumentarischen Komponenten, Erstattungen auf neue
Aufteilungen nach der Übernahme, Quellenkorrekturen, Perioden,
Anlagen, Privatanteile, Lohnbuchungen und Beraterpaket folgen gesondert. Ein
Bankkonto in dieser Oberfläche ist kein Bankfeed; Bargeldkonto ist kein
abgenommenes Kassenbuch. Keine vollständige Jahres-EÜR oder amtliche Meldung
ableiten. Die Quellenlisten prüfen aktuell alle sichtbaren Originalnachweise
vor der Seitenauswahl; eine Leistungsfreigabe für große Bestände liegt nicht vor.
