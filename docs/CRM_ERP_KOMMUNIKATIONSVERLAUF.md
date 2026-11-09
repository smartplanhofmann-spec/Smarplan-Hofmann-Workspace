# Gemeinsamer Kommunikationsverlauf am Kunden und Projekt

Stand: 09.11.2026. Teil von R05.02 des unveränderten Gesamtziels.

Im Browser steht der Verlauf in **Kontakte → Kommunikationsverlauf** und in
der Projektmappe unter **Kommunikation**. In der nativen App öffnet er sich
aus der Kontaktansicht beziehungsweise dem Projektregister **Kommunikation**.
Die App-Quellen gelten gemeinsam für Windows und iPhone; eine neue tatsächliche
Geräteabnahme oder Serverinstallation wird damit nicht behauptet.

Die Ansicht verbindet ausdrücklich zugeordnete Anfragen, Fassungen von
Verkaufschancen und Servicefällen, manuell protokollierte Aktivitäten,
aktuelle Belegstände, Belegversandnachweise und operative Projektnotizen.
Gleiche Namen oder E-Mail-Adressen erzeugen keine Zuordnung. Suche, Quelle und
Zeitraum lassen sich eingrenzen. Korrekturen ersetzen den sichtbaren Original-
nachweis nicht; Original und Korrektur bleiben unterscheidbar.

Eine protokollierte E-Mail ist kein Versandnachweis. Bei tatsächlichen
Belegversandquittungen heißt `accepted` ausdrücklich **Vom Versandserver
angenommen**; weder Zustellung noch Lesen werden bestätigt. Taggenaue
Aktivitäten erhalten keine erfundene Uhrzeit. Anfragen und Dokumente werden
als ihre aktuell gespeicherte Revision gezeigt, nicht als erfundene vollständige
Änderungshistorie. Für Chancen und Servicefälle bestehen native Fassungsquellen.

## Zugriff und Datenhaltung

`GET /api/v1/business/sales/communication-history` gehört zum vorhandenen
Vertriebsmodul `business_sales`; das neue Merkmal heißt `communication_history`.
Es gibt keine neue Tabelle, Schemaänderung, Berechtigung oder externe Aktion.
Der Verlauf ist eine reine Lesesicht auf die vorhandenen Fachquellen. Die
normalen nativen Schreibwege, unveränderlichen Quittungen und Archive bleiben
maßgeblich. Der Aufruf legt weder Aktivitäten an noch sendet er Nachrichten.

Erforderlich sind ein ausdrücklicher Kunden-/Projektbezug und frisches
`contacts.read`. Jede Quelle verwendet zusätzlich ihre vorhandenen Leser:
Projektzuordnung und Projektverweigerungen, nur Eigentümern zugängliche
Anfragen, `finance.read` für Belege/Versand und `documents.read` für operative
Projektnotizen. Finanz-, Personal- und eingeschränkte Logbuchnotizen werden
auch für Eigentümer nicht in diese gemeinsame Ansicht kopiert. Verborgene
Quellen werden weder gezählt noch mit Existenzhinweisen versehen.
Bekannte fremde Kundenkennungen einer zweiten Instanz öffnen keinen Verlauf.

Native Gerätezugänge für begrenzte Offlineerfassung erhalten keinen Zugriff.
Die Clients halten Verlaufsseiten im flüchtigen Ansichtszustand und benötigen
eine erreichbare authentifizierte API. Sie prüfen aktuelle Fähigkeiten vor
und nach einem Abruf und verwerfen Ergebnisse nach Rechte-/Kontextwechseln.
Hintergrundwechsel, Abmeldung und geschlossene Browserdialoge leeren die Sicht;
inaktive native Projektregister verwerfen auch verspätete Antworten. Eine
bereits abgeholte Seite ist keine Zusage dauerhafter zukünftiger Leserechte.

## Vertrag und nachvollziehbares Nachladen

Filter: `customer_id`, `project_id`, `kind`, `q`, `from`, `to`, `limit`, `cursor`.
Unbekannte/doppelte Parameter, GET-Schreibkörper, ungültige Kennungen, Daten,
Suchsteuerzeichen und Seitengrößen werden verworfen. Quellen: `inquiry`,
`sales`, `service`, `document`, `delivery`, `project_note`.

Jeder Eintrag nennt Quellenkennung, Revision, SHA-256, belegten Zeitpunkt mit
Genauigkeit, Erfassungszeit, Projektbezüge und Herkunft. Original/Korrektur
sind über eigene Schlüssel verbunden. Die Schlüssel enthalten Quellentyp
und Herkunft, damit etwa Anfrage- und Versandkennungen nicht kollidieren.
Clients prüfen das Antwortschema, Bezug, Seitenlänge, Zeitpunkte, Reihenfolge,
Duplikate und die Versandbedeutung vor der Anzeige. Inhalte bleiben Klartext.

Pro Seite sind 1–100 Einträge möglich, die Oberflächen verwenden 50. Die
Fortsetzung bindet Filter und vollständigen sichtbaren Quellstand. Ändert
sich dieser, liefert der Server 409 und verlangt erneutes Laden; die Clients
mischen keine alten und neuen Seiten. Mehr als 2.000 passende sichtbare
Einträge oder acht Millionen Textbytes verlangen eine engere Filterung
(413), statt den Verlauf still abzuschneiden. Es wird keine Gesamtzahl
unsichtbarer Datensätze ausgegeben.

## Nachweise und Grenzen

- [Fach-/HTTP-Tests](../backend/test_communication_history.py): 14 neue Fälle,
  einschließlich echter Dokumentausgabe und nativer Outbox mit kontrolliertem
  Transport, Original/Korrektur, Snapshotseiten, Rechteentzug, Firmenabgrenzung,
  privater Notizen und Mengen-/Textbudget. Kein echtes SMTP.
- [PostgreSQL/MFA/Restore](../backend/online/test_communication_history_pg.py):
  zwei tatsächliche Fälle mit eingeschränkter Runtime-Rolle, Neustart,
  frischen Freigaben, Offlinezugangsverweigerung und wirklichem Dump/Restore.
  Die unveränderten nativen Quellen ergeben wieder denselben Verlauf.
- [Browserablauf](../web/office/tests/communication-history-flow.cjs): echte
  Eigentümeranmeldung mit MFA und HTTP, kanonische Fachschreibwege,
  50er-Seiten, veralteter Cursor, Suche/Quelle, HTML als Text, 390-Pixel-Ansicht,
  Kunden-/Projektnavigation und verspätete Antwort nach Seitenwechsel.
- [Flutter](../app/test/business_communication_history_test.dart) und
  [Browserverträge](../web/office/tests/communication-history.test.mjs):
  dieselbe tatsächlich aus sechs Fachquellen erzeugte synthetische Fixture,
  ungültige Antworten und Rechte-/Hintergrundwechsel. Bestehende native
  Projektnavigation prüft alle 22 Register in Desktop-/Mobilbreite.

Rohprotokolle, Bildschirmnachweise und genaue Prüfstände stehen unter
[completion-2026-11-09](evidence/completion-2026-11-09/verification.json).
Die anfänglichen fehlgeschlagenen Prüfungen bleiben erhalten und sind dort
von den bestandenen Nachläufen getrennt.

Eine vollständige externe Kanalintegration, freie Mail-Postfächer, Telefonie,
beliebige Nachrichtendienste, technische Zustell-/Lesebestätigungen und eine
vollständig offline verfügbare CRM-Akte sind damit nicht umgesetzt. Das
Gesamtziel einschließlich Buchhaltung, Lohn und Abnahmen A–G bleibt offen.
