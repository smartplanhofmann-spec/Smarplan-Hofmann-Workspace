# Reisen und Pauschalen: Clientvertrag für Browser und Flutter

Stand: 03.11.2026. **Historischer Entwurf; inzwischen umgesetzt.**
Der aktuelle Implementierungs- und Teststand steht in
[CRM_ERP_REISEPAUSCHALEN_CLIENTS.md](CRM_ERP_REISEPAUSCHALEN_CLIENTS.md).
Ergänzt den [Fachvertrag](CRM_ERP_REISEPAUSCHALEN_ENTWURF_2026.md). Die endgültigen
Routen und Feldnamen werden vor der Implementierung mit dem Reisebackend
abgestimmt. Die bestehenden tatsächlichen Auslagen, Originale, Freigaben,
Erstattungen und Monatsvorbereitungen bleiben erhalten.

## Einstieg und tägliche Arbeit

Unter Personal öffnet **Reisen und Pauschalen** die für den aktuellen Benutzer
erlaubten Mitarbeiter. Der eigene Mitarbeiterzugang zeigt ausschließlich die
eigenen freigegebenen Quellen und Anträge. Die Personalverwaltung kann die
berechtigten Mitarbeiter auswählen. Projektbezug und steuerliche
Tätigkeitsstätte sind zwei getrennte Angaben; ein Projektwechsel erzeugt keine
neue Stätte und setzt keine Frist zurück.

Die Mitarbeiteransicht enthält vier klar benannte Bereiche:

| Bereich | Sichtbare Daten und Aktionen |
| --- | --- |
| Reisen | Zweck, tatsächlicher Zeitraum, beantragter Betrag, aktuelle Fassung und Fachstatus; neue Reise, fortsetzen, Historie und Korrektur |
| Orte und Nachweise | Wohnung, erste Tätigkeitsstätte und tatsächliche auswärtige Stätten mit Gültigkeit und freigegebenem Original; keine automatische Rechtsbewertung aus einer Adresse |
| Abrechnungen | Freigegebene Tagesherleitung, Beträge nach Steuerbehandlung, offene Entscheidungen, ursprüngliche Fassungen und erlaubte Originaldownloads |
| Erstattungen | Tatsächlich belegte Zahlungen, Rückzahlungen und verbleibender Anspruch; Berechnung und Auszahlung getrennt |

Sichtbare Summen stammen aus der aktuellen Serverantwort. Fehlen benötigte
Quellen oder sind Beträge noch nicht eingeordnet, erscheint **Noch nicht
berechenbar** beziehungsweise der konkrete offene Betrag. Fehlende Werte werden
nicht als null dargestellt. Entwurf, eingereicht, zurückgewiesen, freigegeben,
teilweise erstattet und erstattet bleiben unterschiedliche Zustände.

## Reise erfassen

Der Editor führt durch die fachlich zusammengehörigen Angaben und verwendet
benannte Eingabefelder und wiederholbare Zeilen, kein freies JSON-Feld:

1. **Reisezweck und Belege:** Mitarbeiter, Zweck, freiwilliger Projektbezug und
   ausdrücklich gewählte Originale. Neue Originale verwenden zunächst den
   bestehenden privaten Personaldateiweg; dessen Typ- und Größengrenzen werden
   nicht durch den Client erweitert.
2. **Abwesenheit und Stationen:** Tatsächlicher Beginn und Schluss je Intervall,
   IANA-Zeitzone, Stätte beziehungsweise Land und Gebiet, Tätigkeit oder Transit.
   Die Felder bleiben ohne erfundenen Reisebeginn leer. Unterkunft und bloße
   nächtliche Arbeit werden getrennt erfasst. Flug, notwendige Zwischenlandung
   und Schiff haben ihre eigenen benannten Angaben.
3. **Mahlzeiten und Unterkunft:** Datum, Frühstück/Mittag/Abend, bereitgestellt
   durch beziehungsweise auf Veranlassung des Arbeitgebers, Kosten und eigener
   Anteil, gegebenenfalls Ersatzmahlzeit. Mahlzeiten ohne ausreichenden
   Nachweis bleiben ungeklärt. Unterkunft wird als bereits fremdbezahlt,
   tatsächliche eigene Auslage oder ausdrücklich beantragte Pauschale erfasst;
   ein Original darf nicht nochmals als neue Auslage erscheinen.
4. **Stättenbesuche und Vorgeschichte:** Vorhandene tatsächliche Besuche laden,
   fehlende belegte Vorgeschichte ergänzen, bekannte Unterbrechungen zeigen.
   Frühere Arbeit vor Jahresbeginn wird nicht automatisch als unbekanntes null
   Tage langes Intervall angenommen. Die serverseitige Fristbeurteilung zeigt
   ihre zugrunde liegende Stätte und Historienfassung.
5. **Antrag und Vorschau:** Gewünschte Erstattung, bestehende tatsächliche
   Auslagen beziehungsweise Vorzahlungen und ausgewählte Abrechnungseinheit.
   Der Server berechnet die Tagesherleitung und die offenen Entscheidungen.

Länderliste und Stadt-/Gebietsausnahmen stammen aus dem versionierten
Regelkatalog. Das kurze Tagesgeld wird aus dem veröffentlichten Wert angezeigt,
nicht im Client aus dem vollen Betrag zurückgerechnet. Für nicht gelistete
Staaten oder Außengebiete muss die zulässige Zuordnung ausdrücklich sichtbar
sein; ein unbekannter Ortsname darf keinen stillen Ersatzsatz wählen.

Lokale Zeit, Zeitzone und serverseitig aufgelöster UTC-Zeitpunkt bleiben
verbunden. Bei einer doppelten lokalen Uhrzeit verlangt die Oberfläche die
konkrete Zeitlage; eine nicht existierende Uhrzeit wird zurückgewiesen. Der
Client setzt das Datum nicht durch `toISOString().slice(...)` unbemerkt in eine
andere Zeitzone um. Euroangaben werden exakt zu ganzzahligen Centbeträgen
geparst; Eigenanteil null ist ein ausdrücklicher gültiger Wert, ein leeres Feld
ist kein null Euro hoher Nachweis.

## Vorschau, Einreichen und fremde Prüfung

Die Vorschau zeigt je Kalendertag Abwesenheitsart, maßgeblichen Ort, vollen und
kurzen Satz, konkreten Tagesanspruch, Mahlzeitenkürzungen und Eigenanteile,
Fristentscheidung sowie den verbleibenden Betrag. Auf Mobilgeräten bleiben die
Werte lesbar; eine breite Tagesliste scrollt innerhalb ihres Bereichs. Darunter
stehen getrennt steuerfreier Anteil, noch zu prüfender Sachbezug,
pauschalierbarer Anteil, individuell steuerpflichtiger Anteil und bereits
belegter Geldfluss. Es gibt keine zusätzliche lokale Steuerrechnung.

Jeder offene Punkt nennt den betroffenen Tag beziehungsweise Nachweis und die
passende Bearbeitungsaktion. Änderungen an Reisefakten, Orten, Mahlzeiten,
Erstattung oder Quellen verwerfen die alte Vorschau. Eine erst verspätet
eingetroffene Vorschau darf nach Mitarbeiter-, Sitzungs- oder Ansichtswechsel
keinen Dialog wieder öffnen. Die Bestätigung bindet exakt den gewählten
Mitarbeiter, Fall, die erwartete Revision, sämtliche Quellhashes und den
Vorschauhash.

**Einreichen** erzeugt noch keine Freigabe. Die prüfende Person sieht Originale,
Stättenbeurteilung, Vorgeschichte, Tagesrechnung und vorgeschlagene
Steuerbehandlung. **Zurückweisen** benötigt einen Grund. **Freigeben** bleibt
gesperrt, wenn dieselbe Person Antragsteller oder einreichender Akteur ist,
fachliche Blocker bestehen oder Quellen inzwischen geändert wurden. Ein
allgemeiner Bestätigungs-Haken ersetzt keine fehlende Anspruchs- oder
Steuerentscheidung.

Abrechnungsfassungen und zugehörige PDF-/JSON-Dateien werden jeweils mit
Revision und Prüfsumme geöffnet. Eine Korrektur erzeugt eine neue Fassung mit
Grund; die ursprüngliche Tagesherleitung und Auszahlung bleiben lesbar. Ein
geänderter Anspruch wird nicht als bereits geschehene Rückzahlung dargestellt.

## Tatsächliche Erstattung und Finanzübernahme

Der Zahlungsdialog listet ausschließlich tatsächlich freigegebene,
unverbrauchte Quellen und ausdrücklich referenzierte frühere Zahlungen. Er
verlangt Betrag, tatsächlichen Tag, Geldkonto und Original des Zahlungsnachweises.
Vor der Bestätigung sind Restanspruch, gewählter Teilbetrag und geplante
Quellenbindung sichtbar. Wiederholte Teilzahlungen, Rückzahlungen und
Nachweiskorrekturen haben eigene Aktionen und eindeutige Bezeichnungen.

Ein Vorschau- oder Freigabeklick löst keine Überweisung aus. Steuerpflichtige
Anteile können nicht gleichzeitig als steuerfreie Reiseauszahlung bestätigt
werden. Solange die erforderliche Lohnverarbeitung fehlt, nennt die Oberfläche
den konkreten offenen Lohnschritt. Vorhandene erstattete Auslagen werden nicht
erneut angeboten. Die neue gemeinsame Quellenbelegung muss auch am alten
Auslagen-Erstattungsweg eine doppelte Bestätigung verhindern.

Die öffentliche Finanzprojektion zeigt den zulässigen gruppierten Zahlungstag,
Betrag, Kategorie und Prüfbezug. Sie enthält weder Reiseroute noch Anschrift,
Mahlzeiten oder private Personaloriginale. Berechtigte Buchhalter können diese
Quelle anschließend in der EÜR einordnen, ohne private Personalrechte zu
erhalten. Eine Pauschale führt nicht automatisch zu einem Vorsteuerbetrag.

## Technischer Clientvertrag vor Umsetzung

Gemeinsame Dateien: `web/office/travel-allowances.js` und
`app/lib/business_travel_allowances.dart`. Die Einbindung in die bestehenden
Personalansichten bleibt schmal. Globale Session-, Transport-, API-, Schema-,
Paket- und CI-Registrierungen liegen beim Integrationsverantwortlichen.

| Vertragsgruppe | Benötigter Inhalt |
| --- | --- |
| Funktionen und Rechte | Ausgewiesenes Feature; frische globale Fähigkeiten; Mitarbeiterbindung; konkrete Lese-/Schreib-/Prüf-/Export-/Zahlungsaktionen; aktive Module und Read-only-Status |
| Quellen | Mitarbeiter, freigegebene Originalmetadaten, erlaubte Projekte, Stätten-/Historienfassungen, vorhandene Auslagen und Zahlungen; keine geheimen Originalinhalte in Listen |
| Katalog | Regelversion, Gültigkeitsjahr, vollständige Länder-/Gebietskennungen, drei getrennte Geldbeträge, zulässige Ersatzzuordnungen und ausdrücklich benannte Herkunftsart/-hash |
| Fall | Stabile ID, Mitarbeiter, Revision, Status, normalisierte Eingaben, Quellreferenzen, Inhalts-/Plan-/Regelhashes und erlaubte Folgeaktionen |
| Vorschau | Unveränderlich zu bindende Eingaben, Tagesherleitung, Summen, Quellenbelegung, Blocker, Warnungen und `can_confirm`; Fähigkeiten zählen nicht als fachlicher Hashinhalt |
| Mutationsquittung | Anfrage-ID, Originalaktion, Akteur-/Fall-/Mitarbeiterbindung, angenommene Revision und unveränderliche Ergebnisreferenz; keine bloße Erfolgsmeldung |
| Statusprüfung | Nur eigener, ausdrücklich gewählter Auftrag; bestätigt angenommene Referenz oder einen eindeutigen Status; fehlende Rechte sind kein Nachweis der Nichtannahme |
| Export | Gebundene Fall-/Abrechnungsrevision, Dateiname, Medientyp, Größe und SHA-256; aktuelle Rechte vor und nach dem vollständigen Download |

Der Fachentwurf sieht `/personnel/travel` als Wurzel vor. Vor dem Schreiben der
Clients müssen die genauen Kindrouten für Katalog, Quellen, Stätten, Reisen,
Vorschau, Einreichen, fremde Entscheidung, Historie, Exporte, Zahlungen und
Status in einem eigenständigen stabilen API-Dokument stehen. Beispielantworten
sollen unverändert als gemeinsame JSON-Fixture für Node und Flutter dienen.

## Unklare Antworten und private Eingaben

Private Entwürfe und offene vollständige Auftragsdaten liegen nur im
Arbeitsspeicher. Abmelden, Mitarbeiter-/Identitätswechsel, Rechteverlust und
Hintergrundwechsel entfernen diese Inhalte und widerrufen offene
Originalvorschauen. Die Oberfläche erklärt, dass bereits serverseitig
gespeicherte Fassungen dadurch nicht rückgängig gemacht werden.

Nach einer unklaren Antwort zeigt sie **Bestätigung noch offen**. Zuerst wird
der Status derselben Anfrage abgefragt; es entsteht keine neue Anfrage-ID und
kein automatischer Zahlungsversuch. Eine unveränderte ausdrückliche
Wiederholung ist nur mit frischen Rechten, identischer Fallbindung und dem
originalen Auftrag möglich. Ein neuerer Fallstand allein beweist nicht, dass
ein früherer Auftrag abgewiesen wurde. Nach Verwerfen des RAM-Entwurfs wird die
serverseitige Historie frisch gelesen, statt denselben Antrag neu zu erzeugen.

Die generische gemeinsame Wiederholungswarteschlange darf private Daten nicht
länger als dieser Lebenszyklus speichern. Vor Implementierung ist deshalb
entweder ein eigener privater Befehlscontroller nach dem Datenschutzfallmuster
oder eine ausdrücklich gleichwertige RAM-Variante im gemeinsamen Transport
festzulegen. Automatische Hintergrundwiederholung von Reisezahlungen ist nicht
Teil des Vertrags.

## Abnahme beider Oberflächen

- Gemeinsame Fixture prüft identische exakte Cent-/Zeit-/Quellenwerte,
  Vorschaubindung und Quittungsvalidierung in Node und Flutter.
- Eigener Mitarbeiter erfasst eine Reise; eine andere berechtigte Person prüft
  und genehmigt sie. Selbstfreigabe und fremde unberechtigte Originale bleiben
  gesperrt, einschließlich nachträglichem Rechteentzug.
- 8:00/8:01 Stunden, Nachtarbeit, Sommerzeit, Land-/Stadtwahl, gestellte Mahlzeit
  mit Eigenanteil, zwei Reisen am selben Tag und Fristvorgeschichte werden in
  konkreten Eingabe-/Vorschauzuständen bedient. Die gesetzlichen Sollbeträge
  kommen aus den unabhängigen Backendreferenzen.
- Echte verlorene Antwort nach angenommener Speicherung, Freigabe und Zahlung:
  Statusprüfung beziehungsweise identische Wiederholung bestätigt genau eine
  Fachwirkung. Sitzung/Mitarbeiter/Hintergrund wechseln während einer Anfrage;
  späte Antworten verwenden keine frühere private Ansicht.
- Originaldownload prüft Bytes, Größe und Hash unter frischen Rechten;
  Korrektur erhält alte PDF-/JSON-Fassung und ursprüngliche Zahlungen.
- Teilzahlung, Restzahlung, tatsächliche Rückzahlung und bereits anderweitig
  erstattete Auslage werden durchgängig geprüft. Die öffentliche EÜR-Quelle ist
  für Finanzrollen ohne privaten Personalzugriff bedienbar.
- Tatsächlicher MFA-/HTTP-Browserablauf, 390-Pixel-Ansicht, Tastaturfokus,
  lesbare Fehlermeldungen und Flutter-Widget-/Transportprüfung. Reale
  Windows-/iPhone-Geräteprüfung wird dadurch nicht behauptet.

Dieser Entwurf wurde aus den vorhandenen Personal-, Datenschutzfall- und
Lohnzahlungsclients sowie dem fachlichen Reiseentwurf abgeleitet. Die damalige Entwurfsphase enthielt noch keinen Reiseproduktcode. Die
inzwischen umgesetzten Formulare und ausschließlich synthetischen
Testzahlungen sind im oben verlinkten Implementierungsnachweis dokumentiert.
