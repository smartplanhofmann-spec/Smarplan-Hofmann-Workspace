# Projektmeilensteine

Vertragsstand 09.11.2026, abgestimmt für Backend, Browser und native App.
Gesamtziel Abschnitt 6 verlangt ausdrücklich Meilensteine neben Aufgaben und
Terminen. Ein Meilenstein ist hier ein manuell gepflegtes Projektziel mit
optionalem Fälligkeitsdatum und Verantwortlichem. Er erzeugt keine Aufgabe,
Planungsbuchung, Zahlung oder fachliche Abnahme.

## API-Vertrag Version 1

Feature: `project_milestones`; Modul: `business_project_milestones`.

| Methode und Pfad relativ zu `/business` | Ergebnis |
| --- | --- |
| GET `/projects/{project_id}/milestones` | `{schema_version:1,project_id,items:[aktuelle Records]}` |
| POST `/projects/{project_id}/milestones` | Neuer Record, HTTP201 |
| GET `/projects/{project_id}/milestones/{id}` | Aktueller Record |
| POST `/projects/{project_id}/milestones/{id}` | Neue vollständige Fassung, HTTP200 |
| GET `/projects/{project_id}/milestones/{id}/history` | `{schema_version:1,project_id,milestone_id,items:[Records 1 bis n]}` |

Alle Kennungen sind 32-stellige kleingeschriebene Hexwerte. Es gibt keine
zusätzlichen Queryparameter. Erstellen erwartet exakt:

```json
{
  "schema_version": 1,
  "request_id": "0123456789abcdef0123456789abcdef",
  "title": "Projektziel",
  "details": "Beschreibung",
  "due_date": "2026-11-30",
  "assignee_id": null,
  "status": "planned"
}
```

Eine Änderung enthält zusätzlich die zuletzt gelesene `revision` ab 1.
Alle Fachfelder sind vollständig anzugeben; `due_date` und `assignee_id`
verwenden `null` für keine Auswahl. Titel ist nicht leer und höchstens 200
Zeichen lang, Beschreibung höchstens 10.000. Titel und Beschreibung bleiben
zeichengetreu, einschließlich Rand-Leerraum und Zeilenumbrüchen. Fälligkeit ist ein tatsächliches
ISO-Datum im unterstützten Zeitraum 1900 bis 2200. Status ist `planned`,
`achieved` oder `cancelled`; eine ausdrücklich gespeicherte Rückkehr zu
`planned` ist möglich. Änderungen an einem erreichten Meilenstein sind
sichtbare neue Fassungen, keine Änderung des früheren Originals.

Ein Record hat exakt diese Felder:

```text
schema_version, id, project_id, title, details, due_date, assignee_id, status,
revision, created_by, created_at, updated_by, updated_at, content_hash
```

`content_hash` ist SHA-256 über die kanonische UTF-8-JSON-Darstellung des
vollständigen Records ohne dieses Hashfeld: Schlüssel sortiert, keine
zusätzlichen Leerzeichen, Unicode nicht durch ASCII-Ersatzsequenzen ersetzt.
Zeitpunkte besitzen eine Zeitzone. Die Revisionsfolge bleibt maßgeblich, auch
wenn die Systemuhr zwischen zwei Speicherungen zurückgestellt wird. Die Anlageangaben bleiben über alle
Revisionen gleich. Historie ist vollständig und aufsteigend nach Revision;
die Liste sortiert nach offenem Status, Fälligkeit und stabiler Kennung.

## Rechte, Wiederholung und Verantwortung

Lesen verlangt frische `planning.read`-Berechtigung auf das kanonische Projekt.
Schreiben verlangt zusätzlich `projects.manage`. Benutzer-, Projekt- und
Unternehmensgrenzen werden serverseitig geprüft, auch vor der Wiederholung
eines bereits angenommenen Auftrags. Ein Konflikt der Ausgangsversion ist
HTTP409 mit `request_resolution: "not_accepted"`, nachdem das Fehlen einer
eigenen Annahmequittung geprüft wurde. Eine kollidierte Kennung oder unklare
Quittung enthält diesen Hinweis ausdrücklich nicht. Derselbe unveränderte Auftrag liefert seine ursprüngliche Antwort;
abweichender Inhalt mit derselben Kennung wird nicht als neuer Auftrag behandelt.

Verantwortliche werden aus der bestehenden Quelle
`GET /api/projects/{project_id}/workspace` gewählt: `team` enthält aktive
Benutzer mit `id`, `email`, `role`, die Geschäftsführung oder diesem Projekt
zugewiesen sind. Eine neue oder geänderte Verantwortlichkeit muss dort aktuell
enthalten sein. Eine unveränderte frühere Zuordnung darf bei einer späteren
Projekt-/Personaländerung erhalten bleiben. Clients zeigen dafür bei fehlendem
aktuellen Teammitglied „Nicht mehr im aktuellen Projektteam“, ohne fremde
Benutzerstammdaten nachzuladen.

## Speicherung und Grenzen

Eigene aktuelle Datensätze, unveränderliche Revisionen und Annahmequittungen
werden additiv gespeichert. Die alten Workspace-Tabellen und ihr CHECK-Vertrag
werden nicht verändert. Schema-/Paket-/Export- und Datenschutzinventare werden
für die neuen Tabellen ergänzt. Historische Verantwortlichen- und Bearbeiterkennungen sind
strukturierte Datenschutzquellen. Es gibt keine automatische Löschung von
Projektgeschichte und keine erfundene Aufbewahrungsfrist.

Ein deaktiviertes Planungsmodul blockiert Anlage, Änderung und schreibende
Wiederholung mit HTTP423. Im Kompatibilitäts-Lesemodus sind diese Vorgänge mit
HTTP409 gesperrt. Vorhandene Meilensteine und Historien bleiben bei frischer
Leseberechtigung zugänglich; nach Reaktivierung bleiben ursprüngliche
Annahmequittungen verwendbar. Technische Wiederholungsquittungen werden nicht
in das allgemeine Unternehmensarchiv aufgenommen.

Meilensteine sind zunächst Online-Funktionen. Bestehende Offlineaufträge,
Aufgaben- und Terminverträge werden nicht umgedeutet. Der Status „erreicht“
bestätigt eine Benutzereingabe und ersetzt keine unterschriebene fachliche
Abnahme. Test- und Auslieferungsnachweise werden nach tatsächlicher Ausführung
ergänzt.

## Backend-Prüfstand

Die [gemeinsame echte Clientfixture](../app/test/fixtures/project_milestones.json)
stammt aus [diesem Generator](../scripts/generate-project-milestones-fixture.py).
Er verwendet den produktiven Domainablauf mit deterministischen Testkennungen,
keine von Hand nachgebauten Antwortobjekte. Vier Originalfassungen, eine
später entfernte Teamzuordnung, Rand-Leerraum, Emoji und echte abschließende
Zeilenumbrüche sind enthalten. Eine Wiederholung des Generators ergab
byteidentischen Inhalt.

Der [Backendnachweis](evidence/project-milestones-backend-2026-11-09/verification.json)
bindet Quellstand und komprimierte vollständige Rohprotokolle. Domain-,
MFA-/HTTP-, Archiv-, Datenschutz-, Paket- und Migrationsprüfungen bleiben von
den separaten Browser-, App-, PostgreSQL- und Geräteprüfungen getrennt.

Zwei unabhängige Konsistenzbefunde wurden vor Abschluss behoben und mit
gezielten Teständerungen an synthetischen Datenbanken geprüft: Zusätzliche
reservierte Felder im aktuellen JSON dürfen nicht durch Spaltenwerte verdeckt
werden; eine Annahmequittung darf nicht durch eine andere gültige spätere
Fassung ersetzt werden. Zusätzlich prüfen Tests ungültige UTF-8-Skalare,
historische Benutzerreferenzen, Planungspause und Lesemodus. Ungültige Eingaben
erzeugen keine teilweise gespeicherten Meilensteine.
