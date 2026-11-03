# Anpassbare Zusatzfelder – Stand 03.11.2026

Gesamtziel Abschnitt 3: Unternehmen können eigene Angaben für Kontakte, Projekte und Geräte definieren. Die drei Entitätstypen verwenden dieselbe versionierte Funktion in Browser und Flutter. Keine Zusatzfelddefinition existiert automatisch; Pflichtangaben entstehen ausschließlich durch ausdrücklich gespeicherte Definitionen.

## Umgesetzter Umfang

- Text, exakte Dezimalzahl, Datum, Auswahl und Ja/Nein. Zahlen werden als Dezimaltext mit maximal zwölf Vor- und sechs Nachkommastellen gespeichert; keine Gleitkommaumwandlung. `false` und `0` sind ausgefüllte Werte. Optionale Angaben dürfen ausdrücklich leer bleiben.
- Unternehmensweite Definitionen besitzen Bezeichnung, Ausfüllhilfe, Feldart, explizite Pflichtfeld-/Aktivierungsschalter und bei Auswahlfeldern stabile Auswahl-IDs. Höchstens 100 Definitionen je Entitätstyp und 100 Optionen je Auswahlfeld.
- Jede Änderung erzeugt eine zusätzliche Fassung mit Vorgängerhash, Autor, Zeitpunkt und Änderungsgrund. Definitionen und Werte haben eigene lesbare Historienseiten. Datenbankrechte und Trigger untersagen Überschreiben, Löschen und Ersetzen bestehender Fassungen.
- Gespeicherte Werte behalten ihre vollständige damalige Definition. Sobald ein Feld einen nichtleeren historischen Wert besitzt, darf seine Feldart nicht mehr gewechselt werden. Für eine andere Bedeutung wird eine neue Definition angelegt und die alte archiviert.
- Verwendete Auswahl-IDs dürfen nicht entfernt werden. Archivierte Optionen bleiben bei unverändertem Bestandswert zulässig; sie können nicht neu ausgewählt werden. Archivierte Felder werden bei späteren Wertänderungen unverändert mitgeführt. Historische Labels bleiben in den jeweiligen Fassungen lesbar.
- Neu aktivierte Pflichtfelder machen bestehende unvollständige Zusatzangaben sichtbar. Es werden keine Vorgabewerte erfunden. Eine Änderung der Zusatzwerte verlangt alle aktuell aktiven Felder; die Bearbeitung eigenständiger Kernfelder wird durch dieses additive Modul nicht nachträglich umgedeutet.
- Die Zusatzwerte ändern keine Berechtigungen, Kernfelder, Steuermerkmale, Zahlungen, EÜR-Summen, Projektkennzahlen oder Assistentenaktionen.

## Zugriff und Datenschutz

Definitionen benötigen `settings.manage`. Werte und Historien werden ausschließlich über den tatsächlich zugehörigen Datensatz gelesen: Kontakte `contacts.read` über den vorhandenen Kunden-/Projektbezug; Projekte `documents.read` im tatsächlichen Projekt; Geräte `documents.read` im tatsächlich gespeicherten Geräteprojekt. Schreiben erfordert zusätzlich `contacts.write`, `projects.manage` beziehungsweise `documents.write` im selben tatsächlichen Bezug. Ein übergebener Rollenname oder fremder Projektparameter gewährt keinen Zugriff. Archivierte Kontakte/Geräte sowie der Kompatibilitätsmodus bleiben lesbar; Schreibvorgänge sind gesperrt.

Die Rechte werden bei jeder Operation und vor dem Schreiben erneut aus dem aktuellen Benutzer-/Freigabestand gelesen. Auch eine identische Wiederholung einer bereits bestätigten Mutation benötigt aktuelle Lese- und Schreibrechte. Die Clients behalten verlorene oder widersprüchliche Antworten als offenen Vorgang; Wiederholen prüft die aktuellen Fähigkeiten und den tatsächlichen Datensatz erneut und verwendet dieselbe ursprüngliche Vorgangs-ID. Nach Verlust der Lesefreigabe verschwinden native Ansicht und geöffnete Historie; Browserdialoge werden beim Rechte-/Ansichtsrefresh geschlossen.

Freitext kann vertrauliche Geschäfts- und Personendaten enthalten. Der Exportkatalog enthält sämtliche Definitions- und Wertefassungen; technische Requests mit ACK-Snapshots bleiben als interne Quittungen ausgeschlossen und als sensibel klassifiziert. Historische nichtleere Kontaktwerte verhindern eine fälschlich als vollständig ausgewiesene Kernkontakt-Anonymisierung, auch wenn der heutige Wert geleert wurde. Eine Löschung benötigt den gesonderten Datenschutz-Bereinigungsplan. Es besteht keine pauschale Aufbewahrungsfrist nur aufgrund der freien Feldart.

## API und Archivvertrag

Feature `custom_fields`, Capability `business_custom_fields`.

| Pfad | Methode | Bedeutung |
|---|---|---|
| `/custom-fields/definitions` | GET | Definitionsbestand; optional `entity_type=contact|project|asset` |
| `/custom-fields/definitions` | POST | Neue oder zusätzliche Definitionsfassung |
| `/custom-fields/definitions/{id}/history` | GET | Definitionshistorie |
| `/custom-fields/entities/{type}/{id}` | GET | Tatsächliche Entität, aktuelle Definitionen, aktuelle Werte, fehlende Pflichtfelder, `can_write` |
| `/custom-fields/entities/{type}/{id}` | POST | Zusätzliche Wertefassung |
| `/custom-fields/entities/{type}/{id}/history` | GET | Wertehistorie |

Historien liefern `items` absteigend nach Revision und `next_before_revision`. `limit` beträgt standardmäßig 50, höchstens 100; `before_revision` ist exklusiv. Unbekannte Felder, zusätzliche Queryparameter und nicht vorgesehene HTTP-Methoden werden abgewiesen.

Definitions-POST: `request_id`, optional bestehende `id`, erwartete `revision`, `reason`, `definition` mit `entity_type,label,help_text,field_type,required,active,options`. Jede Option enthält `id,label,active`. Der Änderungsgrund ist bei vorhandenen Fassungen Pflicht.

Werte-POST: `request_id`, erwartete `revision`, `definitions_hash`, `reason`, `values` mit genau allen aktuell aktiven Definitions-IDs. Der Server ergänzt ausschließlich unveränderte archivierte Werte aus der bisherigen Fassung. Die Antwort enthält die vollständige damalige `definitions`-Liste, deren Hash, sowie `values:{field_id:{definition:<vollständige Definitionsfassung>,value:<Typwert>}}`.

GET der Entität liefert `entity`, `definitions`, `definitions_hash`, `current`, `missing_required`, `complete`, `can_write`. Noch nicht gespeicherte Werte haben Revision 0 und leere Werte. Eine Definitionsänderung macht eine bereits geöffnete Schreibvorschau ungültig; der Server liefert 409 erst nach Prüfung einer möglichen ursprünglichen Quittung. `request_resolution=not_accepted` bezeichnet ausschließlich sicher nicht angenommene neue Vorgänge.

Alle Ereignishashes verwenden SHA-256 über UTF-8 der kanonischen JSON-Hülle (sortierte Schlüssel, ohne unnötige Leerzeichen): Stammdaten der Fassung plus `payload`. Der vollständige damalige Definitionsbestand wird für Werteereignisse mitgespeichert und beim Restore einschließlich Hash, Feldtypen, aktiven Feldern, unverändert archivierten Werten und Definitionsreferenzen nachgeprüft. PostgreSQL serialisiert Definitions- und Wertänderungen über denselben transaktionalen Advisory-Lock; SQLite verwendet `BEGIN IMMEDIATE`.

Tabellen: `business_custom_field_definitions`, `business_custom_field_values`, `business_custom_field_requests`. Die ersten beiden Tabellen enthalten vollständige Fachfassungen, die dritte unveränderte Vorgangsquittungen. Änderungen benötigen keine zusätzlichen externen Dienste.

## Prüfbelege

Die genauen Ausführungen und Dateihashes stehen in `CRM_ERP_ZUSATZFELDER_PRUEFUNG_2026-11-03.json`. Die Abnahmen verwenden ausschließlich synthetische Kontakte, Mitarbeiter, Projekte, Geräte und Werte.

- Fachtests: Typgrenzen, echte Präzision, explizite Pflichtwerte, archivierte Optionen/Felder, historische Bedeutungen, stale Definitionen/Revisionen, noncegebundene Wiederholung, aktuelle Rechte, unveränderte Kernfelder, Append-only-Schutz, semantisch manipulierte Restore-Snapshots, Datenschutzblocker und Kompatibilitätsmodus.
- PostgreSQL: echte MFA-/HTTP-Aufrufe, Runtime-SQL-Rechte, Offline-Device-Sperre, konkurrierende unabhängige Verbindungen mit exakt einer angenommenen Definitions-/Wertänderung, tatsächlicher Dump/Restore mit identischen Fassungen und ursprünglicher Quittung.
- Browser: tatsächliche Anlage aller fünf Feldarten, Projekt-/Kontakt-/Gerätewerte, verlorene Antwort und identischer Wiederholungsauftrag, archivierte Bestandsauswahl, Historie, lesender Techniker, schmale Ansicht und Screenshots. Chromium-Namespace-, PID-, Netzwerk- und Seccomp-Sandbox wurden vor Zugriff überprüft.
- Flutter: Typ-/Quittungs-/Wiederholungstests, echte Editor-Widgetansicht und unmittelbares Entfernen einer geöffneten vertraulichen Historie nach Rechteentzug; statische Analyse der Komponente und ihrer Einstiege.

Dieser Nachweis betrifft Zusatzfelder. Er erklärt weder das gesamte CRM/ERP noch externe Bank-/Steuer-/Lohnverfahren pauschal für vollständig.
