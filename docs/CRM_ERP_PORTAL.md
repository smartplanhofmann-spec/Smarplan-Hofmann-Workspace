# Angebotsportal: erster Entwicklungsumfang

Stand: 02.11.2026. Grundlage sind R05.04/R05.05 im
[Anforderungskatalog](CRM_ERP_ANFORDERUNGEN.md), der
[Portalplan](CRM_ERP_PORTAL_PLAN.md) und der
[Schnittstellenvertrag](CRM_ERP_PORTAL_API.md).
Aktuelle Prüfläufe und verbleibende Abnahmegrenzen stehen im
[Fortschrittsbericht](CRM_ERP_FORTSCHRITT.md).

## Interner Ablauf

1. Im bestehenden Projekt ein Angebot erstellen, prüfen und finalisieren.
   Der Beleg benötigt eine aktive Kundenbindung und ein unverändertes
   Originalarchiv. Ein Entwurf kann nicht freigegeben werden.
2. Das finale Angebot öffnen und dessen Kundenportal verwalten. Name,
   E-Mail-Adresse und Zugangsdauer von 1 bis 30 Tagen erfassen; Freigabe
   ausdrücklich bestätigen. Es darf jeweils nur einen aktiven Zugang für
   dieses Angebot geben. Die Empfängeradresse wird dokumentiert, aber weder
   verifiziert noch automatisch angeschrieben.
3. Den einmal angezeigten Link sichern und gezielt an den vorgesehenen
   Empfänger weitergeben. Ein Kopieren erfolgt nur auf ausdrückliche Aktion.
   Der Link ist ein Zugangsschlüssel und gehört nicht in öffentliche Ablagen.
4. Später die dokumentierte Annahme oder Ablehnung im Angebot einsehen.
   Nur bei Annahme kann ein zusätzlich berechtigter Mitarbeiter die geprüfte
   Fassung ausdrücklich in einen Auftragsbestätigungsentwurf übernehmen.

Der Auftrag bleibt im vorhandenen Projekt. Die Übernahme erzeugt keine
Rechnung, Zahlung, Terminbuchung, Materialbewegung oder Nachricht. Ein bereits
manuell aus derselben Quelle erzeugter Auftragsbestätigungsbeleg verhindert
einen zweiten Entwurf. Die interne Übernahme verwendet den tatsächlichen
Mitarbeiter und erzeugt zusammen mit dem Entwurf einen unveränderlichen Beleg.

| Interne Aktion | Erforderliche aktuelle Rechte im Quellprojekt |
| --- | --- |
| Übersicht, Freigabe, Widerruf | `portal.manage` und `finance.read` |
| Annahme in Auftragsentwurf übernehmen | zusätzlich `finance.write` und `projects.manage` |

Projektzuweisung und einzelne Sperren gelten zusätzlich. Das neue Portalrecht
ist kein Standardrecht für Mitarbeiterrollen. Browser und Flutter bieten die
internen Schritte an; die Kundenseite ist zunächst eine eigene Browserseite.
Der lokale Backendserver erzeugt keine scheinbar erreichbaren Online-Links.

## Kundenseite

Der Kunde öffnet den ausdrücklich freigegebenen Link. Die Seite entfernt das
Zugangsgeheimnis sofort aus der angezeigten URL und öffnet eine eigene
Kundensitzung. Diese gilt höchstens 30 Minuten und nie länger als die Freigabe.
Ein gültiger Link kann erneut verwendet werden; er ist kein einmaliger
Aktivierungscode. Pro Freigabe sind höchstens fünf aktive Sitzungen erlaubt.

Die Ansicht enthält die freigegebene Angebotsfassung mit Anschriften,
Positionen, Mengen, Verkaufspreisen, Rabatten, Steuern und Summen. Das
Original-PDF kann heruntergeladen werden. Interne Kosten, Margen, Stücklisten,
Personal- oder Kalkulationsnachweise werden nicht in das Kundenformat kopiert.
Annahme und Ablehnung erfordern Auswahl, erklärten Namen, angezeigten Wortlaut
und ausdrückliche Bestätigung. Fassung, Dokument- und PDF-Hash, Zeitpunkt und
Erklärungswortlaut bleiben zusammen gespeichert. Es gibt höchstens eine
abschließende Erklärung je Angebot.

Das Freigabeende betrifft den Zugang. Es ändert keine Angebotsbedingungen und
macht das Belegdatum nicht zu einer rechtlich festgelegten Bindefrist.
Linkbesitz und eingegebener Name belegen keine extern verifizierte
Vertretungsberechtigung und keine qualifizierte elektronische Signatur.

## Unklare Antworten und Widerruf

- Bei verlorener Antwort bleiben Anfrage-ID und Inhalt für die unveränderte
  Wiederholung gebunden. Eine Wiederholung erzeugt keine zweite Entscheidung
  oder Übernahme. Aktuelle Berechtigungen werden trotzdem erneut geprüft.
- Das Geheimnis einer erstellten Freigabe wird nur gehasht gespeichert. Eine
  wiederholte Erstellungsantwort zeigt die vorhandene Freigabe ohne Link. Für
  einen neuen Link muss der Mitarbeiter die alte Freigabe ausdrücklich
  widerrufen und anschließend neu freigeben.
- Nach einem konkurrierenden Abschluss lädt die Kundenseite die tatsächlich
  gespeicherte Erklärung. Ein Neuladen nach einer unklaren Antwort kann über
  denselben gültigen Zugangslink ebenfalls den tatsächlichen Stand zeigen.
- Widerruf sperrt bestehende Sitzungen und den Einladungslink. Kundenlöschung,
  Deaktivierung oder eine geänderte Kundenbindung des Projekts verhindern
  ebenfalls weiteren Kundenzugriff. Historische Erklärungen werden dabei
  nicht verändert.
- Die interne Widerrufsaktion bleibt bei deaktiviertem Dokumentenmodul und
  im lesenden Kompatibilitätsmodus erlaubt. Neue Freigaben, Erklärungen und
  Übernahmen sind dann gesperrt. Auch diese Ausnahme verlangt aktuelle Rechte.

Kundentokens, Links und unbestätigte Eingaben werden im Kundenbrowser nur im
Arbeitsspeicher gehalten. Die erste Version bietet keinen dauerhaften
Offline-Portalauftrag. Mitarbeiter- und Kundentokens sind gegenseitig ungültig.

## Sicherung und Wiederherstellung

Eine normale additive Softwaremigration erhält vorhandene Freigaben und
Historie. Ein tatsächlicher PostgreSQL- oder SQLite-Restore widerruft dagegen
alte Freigaben, deaktiviert Kundenprincipals und entfernt Kundensitzungen sowie
Ratenzähler. Annahmen, Ablehnungen, Übernahmen und Angebotsarchive bleiben
erhalten. Der Restore erfindet dafür keinen Mitarbeiter als handelnde Person.
Eine erneute Freigabe setzt die bestehenden Betriebs-/Restoreprüfungen voraus.

## Weitere Arbeit

Dieser Abschnitt schließt den abgegrenzten Angebotsablauf. Für das gesamte
Kundenportal fehlen weiterhin allgemeine Kundenkonten, Dateiaustausch und
ausdrücklich freigegebene Projektinformationen. Angebote ohne vorbestehendes
Projekt benötigen eine gesonderte Modellergänzung. Der erste Ablauf behauptet
keine vollständige Abnahme B oder G, keinen Produktivbetrieb und keine bereits
erfolgte Fach-/Rechtsprüfung. Die EÜR- und Lohnumsetzung bleibt ein eigener
Entwicklungsabschnitt gemäß den bestätigten Nutzerentscheidungen.
