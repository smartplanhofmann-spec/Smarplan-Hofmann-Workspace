# Smartplan Office – Arbeitsabläufe der CRM-/ERP-Version

Stand: 3. November 2026. Dieses Handbuch beschreibt den entwickelten Funktionsumfang.
Welche Abläufe aktuell getestet sind und welche Freigaben fehlen, steht im
[Integrationsstand](CRM_ERP_INTEGRATIONSSTAND_2026-11-03.md). Die vorhandene
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

## Einkauf, Lager, Geräte und Betriebsmittel

Bestellungen enthalten konkrete Positionen. Teil- und Restlieferungen werden
gegen diese Positionen erfasst; der Original-Lieferschein bleibt erhalten.
Lagerbewegungen, Reservierungen und Projektentnahmen sind eigene belegte Schritte.
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
