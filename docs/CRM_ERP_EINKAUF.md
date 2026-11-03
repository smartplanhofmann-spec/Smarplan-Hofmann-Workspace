# Einkauf und Wareneingänge

Stand: 03.11.2026. Dieser Abschnitt ergänzt die vorhandenen Bestellvorschläge
um dokumentierte Bestellungen und positionsgebundene Teil-/Restlieferungen.
Er gehört zu R07.02 und Abnahme C aus `CRM_ERP_Gesamtziel.txt`.

## Ablauf in Browser und App

1. Im Bereich **Material** einen Bestellvorschlag anlegen: Projekt,
   Lieferant, Artikel und Mengen auswählen. Ein Vorschlag ist intern und noch
   keine Bestellung beim Lieferanten.
2. Positionen prüfen und den Vorschlag freigeben. Die freigegebene Fassung
   bleibt erhalten; sie bestimmt Artikel, Einheiten und maximale Liefermengen.
3. Eine tatsächlich außerhalb der Anwendung erteilte Bestellung mit
   Referenz und Datum dokumentieren und ausdrücklich bestätigen.
4. Für jede Lieferung **Wareneingang buchen** öffnen. Belegreferenz, Datum,
   Ziellager, tatsächlich gelieferte Mengen und tatsächliche Nettoeinstandspreise
   eingeben. Es können einzelne Positionen und Teilmengen gebucht werden.
5. Die Historie zeigt jede Lieferung und die noch offene Menge je Position.
   Nach der Restlieferung ist die Bestellung vollständig geliefert.
6. Material über die vorhandene Entnahmefunktion einem Projekt zuordnen.
   Erst die Entnahme erzeugt tatsächliche Materialkosten im Projekt.

Die Anwendung versendet in diesem Entwicklungsabschnitt keine Bestellung.
Der technische Status `delivery_status=not_sent` beschreibt diesen Versandweg;
die gesonderte Bestellbestätigung dokumentiert den extern erfolgten Vorgang.
[Belegte Mengenänderungen, Reststornierungen und Lieferantenretouren](CRM_ERP_EINKAUF_RETOUREN.md)
sind inzwischen ergänzt und geprüft. Die ursprünglichen Positionen und
Lieferungen bleiben erhalten; weitere Wareneingänge binden die aktuelle
Änderungsrevision. Automatische Einheitenumrechnung und eine direkte
Lieferantenschnittstelle bleiben offen. Belegreferenzen werden gespeichert. Die ergänzte Verknüpfung mit hochgeladenen
Original-Lieferscheinen sowie die explizite Geräteherkunft sind in
[Original-Lieferschein, Geräteherkunft und Wartung](CRM_ERP_GERAETEHERKUNFT.md)
beschrieben (Stand: 03.11.2026).

## Mengen und Kosten

Jede Lieferposition verweist auf genau eine freigegebene Bestellposition und
eine Lagerbewegung. Mengen und Einstandspreise werden mit vier Nachkommastellen
als Dezimalwerte verarbeitet. Überlieferungen, doppelte Positionen und
Wareneingänge vor dem dokumentierten Bestelldatum werden abgewiesen. Ein Fehler
in einer Lieferung verwirft die gesamte Buchung einschließlich Lagerbewegungen.

Beispiel aus dem HTTP-Test: 3 Stück zu 10,25 EUR und 7 Stück zu 12,00 EUR ergeben
10 Stück mit 114,75 EUR Lagerwert. Eine Entnahme von 4 Stück kostet beim
gewichteten Einstandspreis 45,90 EUR; 6 Stück mit 68,85 EUR bleiben im Lager.
Eine spätere Änderung des Artikelpreises bewertet diese Historie nicht neu.

Einheit und Artikelart sind nach einer freigegebenen Bestellung, Reservierung
oder Lagerbewegung gesperrt. Für eine andere Mengeneinheit ist ein eigener
Artikel erforderlich. Namen, Preise und Aktivstatus können weiterhin geändert
werden. Eine bereits vorhandene widersprüchliche Altquelle wird bei einem
Wareneingang abgewiesen, statt ihre Menge automatisch umzudeuten.

## Rechte, Wiederholung und Historie

| Aktion | Erforderliche Rechte im Projekt |
| --- | --- |
| Bestellungen und Lieferhistorie lesen | `inventory.read` |
| Aktive Einkaufsartikel suchen | `inventory.read`, bei Projektwahl zusätzlich dessen Zugriff |
| Vorschlag anlegen oder bearbeiten | `inventory.write` |
| Vorschlag freigeben / externe Bestellung dokumentieren | `inventory.write` und `finance.approve` |
| Wareneingang buchen | `inventory.write` und `finance.write` |
| Finanzwerte lesen | zusätzlich `finance.read` |

Mit der Serverfähigkeit `purchasing_catalog` können Browser und Flutter auch
Lagerrollen ohne Finanzleserecht aktive Material- und Maschinenartikel suchen,
weitere Treffer laden und Artikel ohne bisherigen Bestand auswählen. Bereits
gewählte Positionen und ihre Mengen bleiben bei einer anderen Suche erhalten.
Auch unbestätigte Formulare behalten ihre ursprüngliche Wiederholungsbindung.

Der Suchkatalog enthält für alle Rollen nur ID, Revision, Artikelnummer, Name,
Artikelart, Einheit und Aktivstatus. Lagerantworten ohne Finanzleserecht geben
auch bei Scan, Bestellvorschlag und verschachtelten Artikelsnapshots nur diese
operativen Artikelangaben zurück. Die gespeicherten Kalkulationen und die
vollständige Ansicht für Finanzberechtigte bleiben erhalten.

Bei einem älteren Server ohne diese Fähigkeit verwendet der Browser weiterhin
vorhandene Lagerartikel; Flutter benötigt dort für den bisherigen Katalogweg
Finanzleserecht. Beide Clients zeigen die Grenze und rufen die fehlende neue
Route nicht auf. Für den vollständigen preisfreien Suchablauf ist das aktuelle
Serverpaket erforderlich.

Jede Änderung enthält eine eindeutige Anfrage-ID. Die identische Wiederholung
liefert das gespeicherte Ergebnis und erzeugt keine zweite Buchung. Geänderte
Daten unter derselben ID werden abgewiesen. Die Rechte werden auch bei einer
Wiederholung erneut geprüft; Finanzwerte werden nach den aktuellen Leserechten
ausgeblendet. Dieselbe normalisierte Lieferscheinreferenz kann je Bestellung
nicht ein zweites Mal unter einer neuen Anfrage-ID gebucht werden.

Quellrevision und Lieferrevision schützen vor veralteten Formularen und
gleichzeitiger Buchung derselben Restmenge. Ein solcher Konflikt verlangt
erneutes Laden und fachliche Prüfung. Die Deaktivierung des Materialmoduls
sperrt neue Buchungen mit Status 423, erhält aber die lesbare Historie und
die Anfrage-ID eines ausstehenden Formularvorgangs.

Die Flutter-Einkaufseditoren erhalten unbestätigte Originaleingaben innerhalb
der laufenden Sitzung auch beim Schließen und erneuten Öffnen. Projekt, Datum,
Werte und Anfrage-ID bleiben dabei gebunden. Nach Abmeldung oder einem
vollständigen Prozessneustart ist dieser Sitzungspuffer nicht verfügbar;
Bestell-/Lieferhistorie vor einer erneuten manuellen Erfassung prüfen. Dies ist
noch kein dauerhaftes Offline-Wareneingangsjournal.

Bestellbestätigung, Lieferungen und Wiederholungsbelege sind anhängende
Historie. Datenbanktrigger sperren UPDATE/DELETE sowie die SQLite-Umgehung
durch `INSERT OR REPLACE`; die PostgreSQL-Laufzeitrolle besitzt für die neuen
Tabellen nur SELECT/INSERT. Integritätsprüfungen gleichen Bestellquelle,
Summenmengen, Lieferrevisionen, Referenzen und Lagerbewegungen ab.

## API und Migration

Der bestehende API-Stamm `/api/v1/business` erhält:

| Methode und Pfad | Zweck |
| --- | --- |
| `GET /purchasing/articles?project_id=…&query=…&limit=25&offset=0` | Preisfreier Einkaufsartikelkatalog mit Suche und weiteren Treffern |
| `GET /purchasing/orders?project_id=…` | Sichtbare Bestellungen und Restmengen |
| `GET /purchasing/orders/{id}` | Eine Bestellung mit Lieferstatus |
| `POST /purchasing/orders/{id}/confirm` | Extern erteilte Bestellung dokumentieren |
| `GET /purchasing/orders/{id}/receipts` | Lieferhistorie |
| `POST /purchasing/orders/{id}/receipts` | Lieferung atomar ins Lager buchen |

Entwurf und Freigabe bleiben unter `/inventory/orders`. Die neue Fähigkeit
heißt `purchasing_receipts`. Der additive Schema-7-Modulbaustein
`business_purchasing` erweitert den vorhandenen Bestand um vier Tabellen;
bestehende Module und ihre Checksummen bleiben unverändert. Online wird vor
dem Anwendungsstart die vorhandene explizite Migration mit Betreiberrechten
benötigt. Laufzeitrollen anschließend über den vorhandenen Grant-Schritt
aktualisieren. Ein HTTP-Start führt diese Migration nicht selbst aus.

Die zusätzliche Katalogroute verändert weder Tabellen noch bestehende
Migrationsprüfsummen. Sie meldet `items`, `total` und `next_offset` und erlaubt
höchstens 100 Treffer je Seite, einen Suchtext bis 200 Zeichen sowie Offsets bis
100000. Gesucht wird unabhängig von Groß-/Kleinschreibung nach Artikelnummer
oder Name. Doppelte oder unbekannte Parameter werden abgewiesen. Jeder Abruf
prüft die aktuellen Rechte; die Reihenfolge bleibt für unveränderte Stammdaten
stabil. Bei sehr großen Treffermengen die Suche eingrenzen.

Die aktuelle Suche liest den Artikelbestand unter der bestehenden
Transaktionssperre. Datenbankabrufe und Ergebnisspeicher sind begrenzt; jede
Suchseite durchsucht dennoch den Katalog. Eine indexgestützte Suche für große
Lieferantenkataloge ist eine spätere, separat zu migrierende Optimierung.

## Nachweise und verbleibende Abnahme

Testdateien stehen in `backend/test_business_purchasing.py`,
`backend/test_stock_article_identity.py` und
`backend/online/test_purchasing_journey.py`; Browser- und Fluttertests liegen
bei den jeweiligen Clients. Die tatsächlich ausgeführten Ergebnisse werden im
[Fortschrittsbericht](CRM_ERP_FORTSCHRITT.md) festgehalten.

Der durchgehende HTTP-Test umfasst zusätzlich die vorhandene Geräteanlage,
Wartung, einen unterschriebenen Servicebericht und einen Neustart. Das Gerät
ist dabei über das Projekt und eine dokumentierte Bestell-/Entnahmereferenz
zugeordnet. Ein struktureller Fremdschlüssel zwischen geliefertem Gerät und
Bestell-/Entnahmeposition fehlt noch. Deshalb ist der Test ein Nachweis des
lokalen Teilablaufs und keine vollständige Abnahme C oder Produktivfreigabe.
