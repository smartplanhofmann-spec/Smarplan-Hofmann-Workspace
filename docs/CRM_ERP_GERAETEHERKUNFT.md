# Original-Lieferschein, Geräteherkunft und Wartung

Stand: 03.11.2026. Ergänzung zu R07.02 und Abnahme C aus
`CRM_ERP_Gesamtziel.txt`; ergänzt [Einkauf und Wareneingänge](CRM_ERP_EINKAUF.md).

Die bestätigte Geräteherkunft verbindet eine freigegebene, als extern erteilt
dokumentierte Bestellung mit ihrer konkreten Wareneingangsposition, dem
Original-Lieferschein, einer Projektentnahme, dem Gerät mit Seriennummer und
seiner bestehenden Wartungshistorie. Die Zuordnung erzeugt weder eine weitere
Lagerbewegung noch weitere Projektkosten.

## Ablauf

1. Bestellung und Wareneingang wie bisher erfassen; das Material aus dem
   Empfangslager auf dasselbe Projekt entnehmen.
2. Das tatsächliche Lieferscheinoriginal im selben Projekt unter **Fotos & Doku**
   hochladen. Unter **Projekte → Wartung → Lieferungen und Geräte** die Lieferung
   auswählen und das Original verbindlich zuordnen. Im Browser ist das Original
   außerdem unmittelbar aus der Lieferhistorie einer Bestellung erreichbar.
3. **Gerät aus Lieferung** öffnen, Seriennummer, tatsächliche Entnahme und Menge
   angeben und die physische Herkunft ausdrücklich bestätigen. Alternativ lässt
   sich einem vorhandenen aktiven Gerät mit Seriennummer einmalig eine Herkunft
   zuordnen. Die Gerätefassung muss dabei unverändert sein.
4. Die Geräteherkunft zeigt Bestellreferenz, Lieferschein, Position, Entnahme und
   Seriennummer. Original, Bestellung und Entnahme können geöffnet werden.
   Bestehende Wartungsverträge und abgeschlossene Besuche bleiben an derselben
   Geräte-ID; signierte Serviceberichte sind aus der Herkunftsansicht erreichbar.

Flutter bietet denselben Ablauf unter **Anlagen → Lieferungen und Geräte**
sowie über das Öffnen einer Anlage. Die Vorschau des Originals prüft Größe und
SHA-256 gegen die gebundene Quelle. Browserdownloads laufen über den bereits
authentifizierten Medienweg.

Die Bestätigung beruht auf einer tatsächlichen Prüfung durch den Benutzer.
Das Lager bewertet Material mit gewichteten Einstandspreisen; es führt keine
Seriennummernlose. Die Software behauptet deshalb keine automatisch erkannte
FIFO-Herkunft. Unterstützt werden direkte Entnahmen nach dem Wareneingang aus
dessen Empfangslager. Herkunft über Umlagerungsketten, Lieferantenretouren und
das Aufheben einer bestätigten Geräteherkunft sind weiterhin gesonderte Abläufe.
Eine normale Rückgabe kann nur die noch keinem Gerät zugeordnete Entnahmemenge
zurückbuchen.

## Schutz und Wiederholung

- Originalbindung und Geräteherkunft sind anhängende Historie. Datenbanktrigger
  sperren Änderungen und Löschungen; die PostgreSQL-Laufzeitrolle besitzt auf
  diesen Tabellen nur SELECT/INSERT. SQLite verhindert auch INSERT OR REPLACE.
- Ein Gerät erhält höchstens eine Herkunft. Dieselbe normalisierte Kombination
  aus Artikel und Seriennummer kann nicht ein zweites Mal gebunden werden.
  Die Seriennummer eines gebundenen Geräts bleibt unveränderlich; andere
  vorhandene Anlagenfelder behalten ihr bisheriges Verhalten.
- Die Summe der Zuordnungen ist durch Liefermenge und Entnahmemenge nach
  Rückgaben begrenzt. Fehler rollen Geräteanlage und Herkunft gemeinsam zurück.
- Lesen verlangt im Projekt `documents.read` und `inventory.read`; Schreiben
  zusätzlich `documents.write` und `inventory.write` sowie ein aktives
  Materialmodul. Die vorhandene Geräteanlage prüft ihr eigenes Recht weiterhin.
  Die aktuelle Medienklassifikation gilt auch bei Wiederholungen. Ein
  Finanzleseverbot lässt sich nicht durch die preisfreie Herkunft umgehen.
- Jede Mutation besitzt eine Anfrage-ID. Gleiche Eingaben liefern das gleiche
  gespeicherte Ergebnis; abweichende Eingaben werden abgewiesen. Browser:
  nach verlorener Antwort **Antworten offen → Unverändert erneut senden**.
  Flutter erhält die ursprüngliche Anfrage auch nach Schließen und erneutem
  Öffnen des Editors innerhalb derselben Sitzung, selbst wenn die Quelle
  bereits vollständig verbraucht wurde. Das ist kein dauerhaftes Offlinejournal.
- Abschalten des Materialmoduls erhält lesbare Historie, sperrt jedoch neue
  Bestätigungen und deren Wiederholungen bis zur erneuten Freigabe.

## API und Datenbestand

API-Stamm `/api/v1/business`, Fähigkeit `asset_delivery_provenance`:

| Methode / Pfad | Ergebnis |
| --- | --- |
| GET/POST `/purchasing/receipts/{id}/document` | Originalbindung der Lieferung |
| GET `/assets/origin-sources?project_id=…` | Preisfreie Lieferpositionen und zulässige direkte Entnahmen; paginiert |
| POST `/assets/from-delivery` | Atomare Geräteanlage und bestätigte Herkunft |
| GET/POST `/assets/{id}/origin` | Herkunft lesen oder einmalig einem bestehenden Gerät zuordnen |

Die additive Migration führt `business_delivery_documents`,
`business_asset_origins` und `business_asset_provenance_requests` ein.
Bestehende Einkaufs-, Geräte- und Wartungshistorien bleiben erhalten. Ein
Datenbestand ohne dieses Modul behält bisherige Anlagen-/Rückgabeabläufe;
eine nur teilweise vorhandene Migration wird ausdrücklich abgewiesen.

## Nachweise

Gezielte Prüfungen vom 03.11.2026, ausschließlich synthetische lokale Daten:

| Prüfung | Ergebnis |
| --- | --- |
| Geräteherkunft plus bestehende Wartung, Einkauf und Lager | 67/67 Tests bestanden |
| Echte Flask-HTTP-Anmeldung mit MFA, Lieferung, Original, Gerät, signierte Wartung, Neustart | 1/1 bestanden |
| PostgreSQL mit getrennter Laufzeitrolle, tatsächlichem pg_dump/pg_restore, neuer MFA-Anmeldung, identischer Wiederholung und bytegleichen Originalen/PDFs | 1/1 bestanden |
| Flutter: Befehlsvalidierung, verlorene Erfolgsantwort, erneutes Öffnen trotz verbrauchter Quelle, Rechteentzug | 6/6 bestanden |
| Flutter-Analyse | Keine Befunde |
| JavaScript-Befehlsvalidierung | 4/4 bestanden |
| Echter Chromium-Klickablauf mit MFA, Originalauswahl/-download, Gerät, verlorener Antwort, identischer Wiederholung, Quellenlinks und signiertem Wartungs-PDF | 1/1 bestanden |

Der Browserlauf verwendet eine lokale synthetische Einkaufs- und
Wartungsvorbereitung über die echte HTTP-API; Originalzuordnung, Geräteanlage,
Wiederholung, Quellenansicht und Downloads werden tatsächlich geklickt.
Namespace-, PID-, Netzwerk- und Seccomp-Sandbox wurden vor Anwendungszugriff
geprüft; Desktop und 390-Pixel-Ansicht wurden visuell geprüft. Dieser Nachweis
ersetzt keine Abnahme auf einem echten Android-/Windows-Gerät oder die
Betriebsfreigabe externer Lieferantenwege.

Reproduzierbare Tests liegen in `backend/test_business_asset_provenance.py`,
`backend/online/test_business_asset_provenance_api.py`,
`backend/online/test_business_asset_provenance_pg.py`,
`app/test/business_asset_provenance_test.dart` sowie
`web/office/tests/asset-provenance.test.mjs` und `asset-provenance-flow.cjs`.
Der Browserlauf wird mit `SMARTPLAN_BROWSER_WORKFLOW=asset-provenance` gestartet.
Lokale Ausführungsprotokolle und Screenshots stehen unter
`work/verification/asset-provenance-*`; dieser Arbeitsordner ist nicht Teil
des Lieferpakets. Die PostgreSQL-Tests verlangen ausdrücklich den vorhandenen,
wegwerfbaren Loopback-Testdatenbestand und dürfen nicht parallel zu anderen
Tests mit Schemareset laufen.
