# Smartplan Office – Arbeitsabläufe der CRM-/ERP-Version

Stand: 10. November 2026. Dieses Handbuch beschreibt den entwickelten Funktionsumfang.
Welche Abläufe aktuell getestet sind und welche Freigaben fehlen, steht im
[aktuellen Arbeitsstand](CRM_ERP_ARBEITSSTAND.md). Die vorhandene
Installation erhält diese Erweiterungen erst durch ein kontrolliertes Update.

## Einstieg und Unternehmenseinstellungen

Nach der Anmeldung zeigt die Übersicht Aufgaben, Termine und berechtigte
Kennzahlen. Ein Kennzahlenwert führt zu seinen Quellen. Fehlende oder nicht
vollständig erfasste Grundlagen werden angezeigt; ein solcher Stand ist keine
vollständige betriebliche Auswertung.

Unter Einstellungen wird der Unternehmensbedarf erfasst. Ein vorgeschlagenes
Modul kann sichtbar, ausgeblendet, aktiv oder deaktiviert sein. Die persönliche
Berechtigung wird gesondert vergeben. Ausblenden löscht keine Daten; Deaktivieren
sperrt neue Fachänderungen, während vorhandene berechtigte Archive lesbar bleiben.

Für Smartplan Hofmann ist vereinbart: Einzelunternehmen mit EÜR,
Regelbesteuerung und Ist-Versteuerung, SKR04, 19 % Standard-Umsatzsteuer und
Nettopreise. Den tatsächlichen Gültigkeitsbeginn, Geldkonten, Anfangsbestände und
Ausstellerangaben tragen Sie anhand Ihrer Unterlagen ein. Ein Standardsteuersatz
ersetzt nicht die Prüfung des einzelnen Geschäftsvorfalls.

## Version und Support

Nach einem passenden Serverupdate unter **Einstellungen → Version und Support →
Serverstand anzeigen** den Quellstand der verbundenen Installation lesen.
Dafür sind aktuelle Administrationsrechte nötig. Fehlt ein verlässlicher
Paketnachweis, zeigt die Anwendung diesen Stand ausdrücklich als nicht erfasst.
Eine vorhandene API-Kompatibilitätskennung wie0.12.0-online-pilot ist keine
App-Buildnummer. Ein neuer Testbranch aktualisiert die laufende Installation
nicht automatisch. Bei einem älteren Server wird diese neue Aktion nicht angeboten.

## Vom Kunden zum ausgeführten Auftrag

1. Einen Kunden und gegebenenfalls Ansprechpartner unter Kontakte erfassen.
   Eine vorhandene Anfrage kann in das kanonische Projekt übernommen werden.
2. Artikel und Leistungen auswählen, Mengen, Preise und Steuern prüfen und ein
   Angebot vorbereiten. Bei Änderungen bleibt der ältere Belegstand erhalten.
3. Ein Angebot ausdrücklich für den Kunden freigeben. Die Portalentscheidung
   dokumentiert Annahme oder Ablehnung. Eine angenommene Fassung wird intern
   ausdrücklich in die Auftragsbestätigung übernommen; das Projekt bleibt dasselbe.
4. Termine, zuständige Mitarbeiter und Ressourcen planen. Zeiten freigeben,
   Materialentnahmen und zusätzliche Originalkosten dem Projekt zuordnen.
5. Ausführung mit Fotos und Berichten dokumentieren. Ein unterschriebenes
   Protokoll wird als unveränderlicher Stand gespeichert. Eine spätere Korrektur
   erhält einen eigenen Nachweis.
6. Rechnung und tatsächliche Zahlung verfolgen. Projektwirtschaftlichkeit und
   EÜR sind getrennte Ansichten: Projektkosten, Erlöse, Geldfluss und Steuern
   können zu unterschiedlichen Zeitpunkten entstehen.

Die zusammenhängende technische Prüfung und ihre Rechenbeispiele stehen unter
[Kundenauftrag](CRM_ERP_KUNDENAUFTRAG.md). Weitere Kundeninformationen und
Originale werden im [Kundenarbeitsbereich](CRM_ERP_KUNDENARBEITSBEREICH.md)
einzeln veröffentlicht. Ein Kundenupload wird erst nach interner Prüfung übernommen.

## Länderumfang der Rechnungsstellung

Unter **Einstellungen → Länderumfang der Rechnungsstellung** ist zusätzlich
erkennbar, welches Ausstellerland die eigene Rechnungsstellung unterstützt.
Die erste deutsche Version unterstützt deutsche Aussteller und EUR. Ein
unterstütztes Land aktiviert die Ausgabe noch nicht; die ausdrückliche
Ausstellerfreigabe und die Belegprüfung bleiben erforderlich. Nicht unterstützte
Aussteller bleiben vor einer neuen Rechnungsnummer gesperrt. Alte Originale
bleiben lesbar. [Details](CRM_ERP_AUSSTELLER_LAENDERGRENZE_2026-11-09.md).

## Alte Offline-Aufträge prüfen

In der aktuellen Windows-/iPhone-App steht für erhaltene alte Gerätebestände
**Alte Offline-Aufträge prüfen** in der Navigation. Nach Onlineanmeldung
**Gerätebestand prüfen** wählen und das Gerät entsperren. Bei einem prüfbaren
Planauftrag **Ursprüngliche Annahme prüfen** verwenden. Erst nach einer
passenden Originalquittung erscheint der Titel des Serveroriginals. Ein
fehlender Treffer ist keine Erlaubnis, den alten Auftrag neu anzulegen oder
zu senden. Alte Dateien und übrige Eingaben bleiben unverändert erhalten;
dies ist ein einzelner lesender Abgleich und keine vollständige Altdatenübernahme.

Bei einem prüfbaren alten Zeitauftrag **Ursprüngliches Zeitereignis prüfen**
wählen. Eine passende Bestätigung zeigt Aktion und ursprünglichen Zeitpunkt
in Gerätezeit. Fehlt die damals gespeicherte Mitarbeiterbasis, bleibt der
Auftrag ungeklärt erhalten. Der Ablauf ergänzt keine Daten aus einem heutigen
Profil und startet oder beendet keinen Timer. Details zum
[begrenzten Zeitabgleich](CRM_ERP_OFFLINE_ALTZEITEN_2026-11-09.md).

Bei einem prüfbaren alten Servicebericht **Ursprüngliches Protokoll prüfen**
wählen. Der Abgleich überträgt nur Kennungen und Hashmetadaten. Erst eine
passende ursprüngliche Archivquittung und die Prüfung des tatsächlichen PDFs
bestätigen das Original in der angemeldeten Firma. Berichtstext und Unterschrift
werden dabei nicht erneut übertragen. Ein fehlender Treffer bleibt ungeklärt;
alte Gerätebestände und Schlüssel erhalten. [Einzelheiten](CRM_ERP_ALTBERICHT_ABGLEICH_2026-11-10.md).

## Zeiterfassung finden und Zeiten abrechnen

Im Browser liegt die Zeiterfassung unter **Personal → Personal & Zeiten**.

**Zeit starten** beginnt einen Vorgang für das gewählte Projekt; laufende Zeit
kann geöffnet, pausiert und beendet werden. Fehlt diese Aktion, muss dem
angemeldeten Benutzer ein aktives Mitarbeiterprofil zugeordnet sein. Modul-
und Zugriffsrechte gelten zusätzlich. In der Windows-/iPhone-Oberfläche liegt
**Arbeitszeit** im konkreten Projekt; schmale Fenster zeigen dafür das Auswahlfeld
**Projektbereich**.

Für die Übernahme in einen Browserbeleg:

1. Den Arbeitstag prüfen und die abzurechnenden Projektzeiten freigeben.
2. Im selben Projekt einen Angebots- oder Rechnungsentwurf öffnen.
3. Unter **Freigegebene Arbeitszeiten übernehmen** die gewünschten Zeiten
   auswählen und **Abrechnungssatz netto je Stunde (€)** sowie
   **Umsatzsteuer für Arbeitszeiten (%)** ausdrücklich eintragen.
4. Den Entwurf speichern und die angenommenen Zeitpositionen zusammen mit
   bestehenden freien und Katalogpositionen prüfen. Eine geänderte Zeitquelle
   verlangt eine erneute Prüfung; ein gespeicherter Entwurf ist noch keine
   ausgestellte Rechnung.
5. Die Rechnung gesondert prüfen und ausstellen. Bereits endgültig abgerechnete
   Zeiten dürfen nicht erneut berechnet werden.

Werden keine Zeiten angezeigt, Projekt, Freigabe, Abrechenbarkeit, bestehende
Zeitpositionen und Zugriffsrechte prüfen. **Freigegebene Zeiten neu laden**
aktualisiert die Auswahl. Bei einer unklaren Speicherantwort den angebotenen
ursprünglichen Auftrag erneut prüfen; keine Ersatzrechnung anlegen, solange
das Ergebnis des ersten Auftrags unbekannt ist.

Der Projektwähler erscheint nur in projektbezogenen Ansichten. Übersicht,
Kontakte und andere allgemeine Unternehmensbereiche benötigen keinen
pauschalen Projektfilter.

## Projektaufgaben und Meilensteine

Aufgaben und Meilensteine gehören zum geöffneten Projekt. Ein Meilenstein
hat einen Titel, optionalen Termin und Verantwortlichen sowie einen manuell
gepflegten Status. Bei Änderungen bleibt der bisherige Verlauf lesbar. Sein
Abschluss stellt keine Rechnung aus und verändert kein Budget automatisch.

## Einkauf, Lager, Geräte und Betriebsmittel

Bestellungen enthalten konkrete Positionen. Teil- und Restlieferungen werden
gegen diese Positionen erfasst; der Original-Lieferschein bleibt erhalten.
Lagerbewegungen, Reservierungen und Projektentnahmen sind eigene belegte Schritte.
Für eine Rückgabe im Bereich der Lagerbewegungen **Material zurückgeben** wählen.
Projekt und ursprüngliche Entnahme ausdrücklich auswählen, Ziellager und
tatsächlich zurückgegebene Menge angeben und bestätigen. Artikel und historischer
Einstand stammen aus der Originalentnahme; sie werden nicht neu festgelegt.
Der Server prüft die verbleibende Menge. Eine Lagerrolle benötigt dafür keinen
Zugriff auf Einkaufspreise. Bestand und Projektkosten werden gemeinsam angepasst.

Bei einer unklaren Antwort **Ursprüngliche Rückgabe erneut prüfen** verwenden.
Die aktuelle native App erhält den Originalauftrag bei bestätigter Firmenbindung
auch über einen Neustart. Mit demselben Konto in derselben Firma und demselben
Projekt erneut **Material zurückgeben** öffnen und die ursprüngliche Rückgabe
prüfen. Es wird keine neue Vorgangskennung angelegt. Auch der aktuelle Browser
erhält diesen Auftrag bei bestätigter Firmenbindung verschlüsselt über ein
Neuladen und eine erneute MFA-Anmeldung. Im selben Browserprofil mit demselben
Konto das ursprüngliche Projekt öffnen und **Ursprüngliche Rückgabe erneut
prüfen** wählen. Bei einer fehlenden Freigabe oder einem nicht lesbaren
Altauftrag den Browserspeicher erhalten und das ursprüngliche Lagerjournal
prüfen. Die Rückgabe benötigt eine Onlineverbindung.

Die Inventur vergleicht eine ausdrücklich gezählte Menge mit einem gebundenen
Lagerstand. Differenzen benötigen einen Grund und gegebenenfalls eine Bewertung.

Ausgelieferte Geräte können mit ihrer Herkunft und Wartung verbunden werden.
Betriebsmittel wie Fahrzeuge oder Werkzeuge verwenden die vorhandenen
Planungsressourcen. Profil, Prüfanforderungen, Prüfbelege, Ausgabe, Rückgabe
und begründete Korrekturen bilden ihre Historie. Ein defekter oder ungeprüfter
Zustand wird durch eine dokumentierte Übergabe nicht zu einer Nutzungsfreigabe.
Die Einsatzplanung berücksichtigt die daraus entstehenden Sperren.

Details: [Einkauf](CRM_ERP_EINKAUF.md), [Inventur](CRM_ERP_INVENTUR.md),
[Geräteherkunft](CRM_ERP_GERAETEHERKUNFT.md),
[Betriebsmittel](CRM_ERP_BETRIEBSMITTEL.md).

## Kundenservice und Nachbetreuung

Unter Kundenservice wird eine Anfrage, Reklamation oder Wartung mit Kunde,
Zuständigkeit und Wiedervorlage erfasst. Vorhandene Projekte, Geräte, Mängel und
Wartungsbesuche können verknüpft werden. Ein Einsatz verwendet die gemeinsame
Planung; der signierte Bericht bleibt der Ausführungsnachweis. Lösung und
Abschluss werden dokumentiert. Eine Wiedereröffnung benötigt eine Begründung.
Der Fallabschluss löst keine Zahlung oder Gewährleistungsentscheidung aus.

Details: [Kundenservice in beiden Oberflächen](CRM_ERP_SERVICE_CLIENTS.md).

Im Browser können Wartungsverträge bearbeitet, pausiert und wieder aktiviert
werden. Eine Pause verhindert die Erzeugung weiterer Einsätze; bereits geplante
Besuche und ihre Nachweise bleiben erhalten. Für eine andere Serie kann ein
neuer Vertrag erforderlich sein. Beim Speichern einer inzwischen geänderten
Fassung zuerst den aktuellen Vertrag laden und die Eingabe abgleichen.

In der App bleibt eine unbestätigte manuelle Serviceanlage auch nach einem
Neustart als ursprünglicher Auftrag erhalten. Nach erneuter Anmeldung in
derselben Firma den angebotenen offenen Auftrag prüfen, damit ein bereits
angenommener Servicefall nicht ein zweites Mal angelegt wird.

## Finanzen, EÜR und Banknachweise

Originalbelege werden erfasst und geprüft. Tatsächliche Geldbewegungen erhalten
eine ausdrückliche Belegzuordnung; Teilbeträge und Rückzahlungen bleiben
nachvollziehbar. Die EÜR verwendet diese Quellen zur steuerlichen Einordnung.
Vorschau und Bestätigung sind getrennte Schritte. Fehler werden durch belegte
Berichtigung oder Gegenbuchung korrigiert; alte Ausgaben bleiben erhalten.

Der Bankabgleich importiert einen genau definierten CSV-Auszug mit Original,
Konto, Zeitraum und bestätigten Anfangs-/Endsalden. Seine Buchungen werden
vorhandenen Geldbewegungen ausdrücklich zugeordnet. Der Import erzeugt keine
zweite Zahlung. Ein unvollständiger oder veralteter Bankbericht bleibt als
solcher erkennbar; eingerichtete Bankkonten benötigen für einen neuen EÜR-
Periodenabschluss einen aktuellen vollständigen Nachweis.

Geschlossene Perioden werden vor einer erforderlichen Änderung ausdrücklich
wieder geöffnet. Jahresprüfpakete und historische Exporte besitzen gebundene
Quellen. Ein internes Prüfpaket ist keine bereits eingereichte Steuererklärung.

Details: [EÜR-Bedienung](CRM_ERP_EUER_CLIENTS.md),
[Bankabgleich](CRM_ERP_BANKABGLEICH.md),
[Wiederherstellung und Finanzabgleich](CRM_ERP_EUER_BETRIEB.md).

## Personal, Lohn und tatsächlich gezahlte Beträge

Personalakten und Originale sind gesondert geschützt. Reisekostenauslagen werden
belegt und durch eine andere berechtigte Person freigegeben. Erstattung,
Rückzahlung und Korrektur behalten ihren tatsächlichen Zahlungsbezug.

Vor einer Lohnberechnung werden die belegten Mitarbeiterdaten und das passende
Profil gepflegt. Der unterstützte Umfang der 2026-Rechnung steht ausdrücklich
in der [Lohndokumentation](CRM_ERP_LOHN_RECHENWERK_2026.md). Nicht unterstützte
Fälle müssen geklärt werden; ihre Eingaben dürfen nicht passend abgeändert werden.

Eine Berechnung ist kein Zahlungsnachweis. Tatsächliche Nettozahlungsteile und
gesonderte Abführungen werden mit Originalen erfasst. Ihre Übernahme erzeugt
eine aggregierte Finanzquelle, die anschließend in der EÜR eingeordnet wird.
Finanzleser erhalten dadurch keinen Zugriff auf private Mitarbeiterakten.

Für Ein- und Austritte werden zuerst die tatsächlichen Beschäftigungszeiten,
Entgeltvereinbarungen, Steuer-/Versicherungsprofile und Arbeitspläne belegt.
Der bestätigte Monatsfall zeigt Anspruchstage, Steuertage und SV-Tage getrennt.
Ein blockierter Plan bleibt als nachvollziehbarer Nachweis erhalten; seine
Sperrgründe müssen vor dem Lohnabschluss geklärt werden.

Unter „Private Anspruchsnachweise“ werden Krankheitsvorzeiten, regelmäßige
Ausfallvergütung, Urlaubsreferenz und unbezahlte Unterbrechungen mit ihren
Originalen erfasst. Die Vorschau zeigt die hergeleiteten Fristen und Beträge.
Eine Bestätigung verändert keine tatsächlichen Projektstunden. Berichtigungen
erzeugen eine weitere Fassung, eine Aufhebung erhält den ursprünglichen Nachweis.
Die verfügbaren Krankheitsregeln und ihre Grenzen stehen in der
[Versionsbeschreibung](CRM_ERP_LOHN_KRANKHEIT_VERSIONEN_2026.md).

Eine Reisekostenabrechnung trennt Pauschalen, belegte Auslagen, steuerpflichtige
Lohnanteile und tatsächliche Erstattungen. Alte bereits erstattete Auslagen
werden nur mit ihrem ursprünglichen Zahlungsnachweis übernommen. Der Betrag
wird dabei nicht erneut ausgezahlt. Aufhebung einer dokumentierten Zahlung
erfindet keine Rückzahlung; ein tatsächlicher Geldrückfluss braucht einen eigenen
Nachweis. [Reisebedienung](CRM_ERP_REISEPAUSCHALEN_CLIENTS.md).

**Kilometererstattungen** verwenden im Personal-/Reisebereich einen eigenen
Ablauf für dienstliche Inlands-Rundfahrten eines Mitarbeiters im privaten Pkw.
Wohnung beziehungsweise erste Tätigkeitsstätte, tatsächliche auswärtige Orte,
Abfahrts-/Ankunftszeiten, Teilstrecken in Metern und die geforderten Originale
erfassen. Die Erklärungen zu Fahrzeugkosten, Dienstwagen, Privatanteilen,
Arbeitswegen und anderer Erstattung bewusst prüfen; sie sind nicht vorbestätigt.
Eine andere berechtigte Person prüft die eingereichte Fahrt und gibt die
berechnete Erstattung frei.

Eine Freigabe ist kein Zahlungsnachweis. Tatsächliche Überweisungen oder
Rückzahlungen gesondert mit ihren Originalen erfassen. Bei einer späteren
Streckenkorrektur bleiben alte Auszahlungen erhalten. Eine ausgewiesene
Überzahlung verschwindet erst mit belegter tatsächlicher Rückzahlung.
Bereits verwendete Streckenoriginale werden auch bei neuen Kombinationen mit
weiteren Belegen gesperrt. Das ist keine Erfassung eigener Unternehmerfahrten,
von Arbeitswegen, Dienstwagen oder gemischten Reisen.

Der neue Ablauf benötigt eine Onlineverbindung. In der aktuellen nativen App
mit bestätigter Firmenbindung bleibt ein unbestätigter Originalauftrag über
einen Neustart geschützt erhalten. Mit demselben Konto den ursprünglichen
Mitarbeiter und **Private Pkw-Kilometererstattung** öffnen, dann **Status des
ursprünglichen Auftrags prüfen** wählen. Nur wenn der Auftrag noch nicht
angenommen ist, seine unveränderte Wiederholung verwenden. Es wird keine zweite
Zahlung angelegt. Auch im aktuellen Browser bleibt das Original bei bestätigter
Firmenbindung verschlüsselt erhalten. Nach Neuladen im selben Browserprofil
erneut mit MFA anmelden, denselben Mitarbeiter öffnen und zuerst den
ursprünglichen Status prüfen. Der Auftrag wird nicht automatisch gesendet.
Bei gesperrten oder beschädigten Altaufträgen den Browserspeicher erhalten;
ein neuer Auftrag ersetzt keine ungeklärte ursprüngliche Zahlung.

Bei zusätzlichen pauschal zu versteuernden Verpflegungszuschüssen wird zuerst
die betriebliche Steuerentscheidung für den Anmeldezeitraum belegt. Das
Kirchensteuerverfahren und die Betriebsstätte werden ausdrücklich gewählt.
Die anschließende Lohnberechnung verlangt eine eigene Prüfung und Bestätigung.
Der [Steuerdialog](CRM_ERP_REISE_PAUSCHALSTEUER_CLIENTS.md) selbst löst weder
eine Steuerübermittlung noch eine Überweisung aus.

Die eigene Mitarbeiteransicht zeigt freigegebene Abrechnungen, das zugehörige
PDF und ihre Historie. Private Steuerentscheidungen und Personaloriginale
werden darüber nicht zugänglich. Die Zugriffsgrenzen und derzeit geprüften
Abrechnungsversionen stehen unter
[Eigene Mitarbeiterabrechnung](CRM_ERP_LOHN_MITARBEITERBELEG.md).

Details: [Personalworkflow](CRM_ERP_PERSONAL_WORKFLOW.md),
[Lohnbedienung](CRM_ERP_LOHN_CLIENTS.md),
[belegte Zahlungen zur EÜR](CRM_ERP_LOHNZAHLUNGEN_EUER_CLIENTS.md).

### Faktor-Monat mit Ansprüchen und bereits bezahlten Reisen

Den Mitarbeiter und den tatsächlichen Abrechnungsmonat öffnen, dann
**Abrechnungsfälle mit Ansprüchen und Reisen** und
**Faktor-Monat mit Ansprüchen und bezahlten Reisen** wählen. Die native App
zeigt denselben neuen Fall im Bereich der belegten Abrechnungsfälle.

Den bestätigten Faktor-Monat, Beschäftigungs-, Profil- und Identitätsfassungen,
sämtliche aktiven Anspruchsnachweise sowie die tatsächlichen Reiseabrechnungen
und vollständigen Zahlungsnachweise auswählen. Erstattungs- und gegebenenfalls
Rückzahlungsfassungen gehören zum ursprünglichen Nachweis. Eine noch unbezahlte,
nicht vollständig belegte oder zusätzlich steuerpflichtige Reise passt nicht
zu diesem begrenzten Fall.

Die Vorschau zeigt Anspruchsbrutto und die bereits separat gezahlte Reise.
Beispiel aus den kontrollierten Prüfdaten: Aus5000 Euro ursprünglichem
Monatsgehalt und fünf belegten unbezahlten Tagen entstehen4193,55 Euro
Anspruchsbrutto und2850,54 Euro Netto. Die bereits erstatteten14 Euro werden
nicht erneut zum Lohnnetto addiert. Bezahlte Feiertage bei Stundenlohn werden
als Anspruch belegt; es werden dafür keine Projektarbeitsstunden erfunden.

Erst den geprüften Gesamtfall festhalten und danach die Lohnberechnung separat
bestätigen. Bei verlorener Antwort den ursprünglichen Auftrag unverändert
wiederholen. Vorhandene Rechte und die serverseitige Verfügbarkeit werden dabei
neu geprüft. Eine Berechnung löst keine Überweisung oder Behördenmeldung aus.

Bei einem bisherigen Faktorfall kann **Fehlenden Anspruchs- oder
Reisebestandteil belegt ergänzen** angeboten werden. Diese Ergänzung benötigt
einen ausdrücklichen Prüfvermerk und die Bestätigung, dass der ursprüngliche
Fall noch nicht verwendet wurde. Ursprüngliche Bestandteile und Fassungen
bleiben erhalten. Ein bereits verwendeter Fall oder eine unvollständige
Verwendungshistorie bleibt gesperrt und erfordert fachliche Klärung.
[Geprüfter Umfang und Grenzen](CRM_ERP_FAKTOR_ANSPRUECHE_BEZAHLTE_REISEN_V13_2026-11-10.md).

## Assistent, Sprache und Regeln

Der Assistent zeigt seine berechtigten Quellen und schlägt konkrete Aktionen
vor. Unternehmensregeln bestimmen, welche unterstützte Aktion automatisch,
nach Freigabe oder überhaupt nicht ausgeführt werden darf. Eine fehlende
Quelle oder Berechtigung wird nicht durch eine freie Antwort ersetzt.

Eine Sprachaufnahme wird ausdrücklich gestartet. Vor einer Übertragung an
einen eingerichteten Anbieter wird die erforderliche Zustimmung eingeholt.
Der entstandene Text ist zunächst ein Entwurf. Regeln und Rechte gelten auch
für eine anschließend gewählte Fachaktion.

Details: [Assistent](CRM_ERP_ASSISTENT_CLIENTS.md), [Sprache](CRM_ERP_SPRACHE.md).

## Import, Datenschutz und Unternehmensübergabe

Der Dateiimport bewahrt Originale und zeigt Zuordnungen, Fehler und Dubletten
vor der Übernahme. Historische Belege werden nicht erneut als Rechnung gestellt.
Der dokumentierte neutrale Dateivertrag ist keine Zusage, beliebige HERO- oder
sevDesk-Dateien direkt einlesen zu können.

Ein Datenschutzfall beginnt mit einer benannten Person und der Prüfung ihrer
Identität. Quellen, Aufbewahrungsgründe, fremde Personen und unstrukturierte
Originale werden einzeln bewertet. Eine ausdrücklich bestätigte Berichtigung
oder zulässige Bereinigung hält ihren Nachweis fest. Frühere Backups dürfen
eine solche Bereinigung nicht still zurücknehmen.

Der Unternehmensexport enthält ein überprüfbares Archiv mit Originalen und
einem mitgelieferten Prüfer. Ein erfolgreicher Export ist noch keine bestätigte
Datenübernahme durch ein anderes System und keine Stilllegung der Instanz.

Details: [Dateiimport](CRM_ERP_DATEIIMPORT.md),
[Datenschutzfälle](CRM_ERP_DATENSCHUTZFAELLE.md),
[Unternehmensübergabe](CRM_ERP_UNTERNEHMENSEXPORT.md).

## Verbindungsabbruch und Offlinearbeit

Bei einer unklaren Antwort bleibt der ursprüngliche Fachauftrag zur Wiederholung
erhalten. Verwenden Sie die angebotene Wiederholung mit unverändertem Inhalt.
Legen Sie denselben Vorgang nicht vorsorglich neu an. Vor der Wiederholung prüft
die Anwendung aktuelle Rechte; eine frühere Berechtigung gilt nicht dauerhaft.

Vorbereitete native Offlinearbeit verwendet die verschlüsselte Projektablage.
Eine lokale Erfassung ist erst nach bestätigter Synchronisation auf dem Server
angekommen. Konflikte und fehlende Rechte bleiben sichtbar. Bei einem
Sitzungswechsel werden sensible flüchtige Arbeitsstände entfernt. Die konkreten
unterstützten Offlineberichte stehen unter
[Offline-Serviceberichte](CRM_ERP_OFFLINE_SERVICEBERICHTE.md).

Neue Offlinearbeit benötigt eine aktuelle Freigabe für dieselbe Firma und
dasselbe Benutzerkonto. Server und App müssen diesen gemeinsamen Stand
unterstützen. Meldet die App, dass der Server keine Firmenbindung bestätigt,
kann online weitergearbeitet werden; eine neue Offlinefreigabe wird verweigert.
Die Meldung wird durch erneutes Anlegen desselben Vorgangs nicht behoben.

Ältere Offlinebestände werden erhalten und keiner anderen Firma automatisch
zugeordnet. Bei einem Firmen- oder Serverwechsel zuerst die Zuordnung und
ausstehenden Originalaufträge klären. Eine vollständige Übernahme bisher
ungebundener Altbestände ist ein eigener noch offener Schritt. Die lokalen
Dateien dafür nicht vorsorglich löschen oder in die Ablage einer anderen
Firma kopieren.
