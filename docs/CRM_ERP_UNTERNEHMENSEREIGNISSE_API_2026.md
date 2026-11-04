# Unternehmensereignisse – API und echte Clientfixture

Stand 04.11.2026. Additives Backend im isolierten Arbeitsbaum; noch keine
Gesamt- oder Produktionsfreigabe. Fachliche Grenze:
[Vertrag](CRM_ERP_UNTERNEHMENSEREIGNISSE_VERTRAG_2026-11-04.md).

## Zugriff und gemeinsame Form

Basis `/business/company-events`, Feature `company_event_rules`, Capability
`business_company_events`. Keine Offline-/Kunden-/Portalautorisierung.
`assistant.use` ist für alle Zugriffe erforderlich. Regeln und Läufe benötigen
zusätzlich `settings.manage`. Beobachtungen/Pläne prüfen aktuelle Projekt- und
Quellenrechte; Listen filtern nicht lesbare Vorgänge. Eine Regeldelegation
erteilt weder Projektzuweisung noch `projects.manage`, `finance.write`,
`finance.approve` oder `assistant.approve`. Eine operatorseitig eingerichtete
`business_instance_identity` muss vor der ersten Regel existieren. Der Client
sendet weder Unternehmenskennung noch Quellenfakten.

Alle GETs akzeptieren ausschließlich dokumentierte Queryparameter, keine
Bodies. POSTs akzeptieren exakt dokumentierte Felder und keine Queryparameter.
IDs sind 32 kleine Hexzeichen, Hashes 64. Alle Antworten sind privat/no-store.
POSTs liefern 200 und ergänzen den Fachwert um:

```json
{"acceptance":{"request_id":"<Original-ID>","operation":"scan","request_hash":"<SHA256>"}}
```

`request_hash = SHA256(UTF8(canonical([operation, kompletter Originalbody])))`.
Canonical ist sortiertes JSON ohne Leerzeichen, Unicode unverändert. Die
Annahme kommt aus der dauerhaft gespeicherten Originalquittung, nicht aus der
zurückgegebenen aktuellen Ansicht. `operation` ist `rule`, `scan`,
`approve:<plan_id>`, `reject:<plan_id>` oder `execute:<plan_id>`.
GET-Antworten enthalten kein `acceptance`. Die jeweilige gespeicherte
`sha256` schließt abgeleitete Felder wie `status`, `source_current`,
`can_execute`, `blocked`, `execution`, `outcome`, `decision`, die ausgegebene
`id`, `created_at` und POST-`acceptance` nicht ein. Bei Regeln sind `id` und
`created_at` hingegen Bestandteil der gespeicherten Regelfassung; die Regel
liefert selbst keinen separaten `sha256`-Zusatz. Ihre Referenz berechnet sich
aus der vollständigen Regelfassung ohne `acceptance`.

Antwortverlust behält den vollständigen alten Body einschließlich request_id.
Nur dieselbe Annahme darf die lokale Warteschlange auflösen. Bei 409 mit
`request_resolution: not_accepted` steht das Fehlen einer Annahme unter dieser
ID fest. Eine Kollision mit einer bereits anders verwendeten ID erhält dieses
Attribut nicht. Eine neue Execute-ID für einen schon gestarteten Anlass wird
abgewiesen; die ursprüngliche Annahme und die Historie bleiben lesbar.

## Status, Regeln und Vorlagen

- `GET /status`: Auslöser, typisierte Bedingungsfelder, passende Aktionen,
  tatsächliche Ausführbarkeit, Modi, `timezone: Europe/Berlin`, maximale
  Seitengröße 100, keine Lohnquellen/Modellaufrufe.
- `GET /rules`: `{schema_version:1,items:[Regelfassungen]}`.
- `GET /rules/<id>/history`: sämtliche unveränderten Regelfassungen.
- `POST /rules`: exakt `request_id,id,revision,title,enabled,project_ids,
  trigger,action,mode,conditions,template,responsible_id,confirmation`.
  `revision` ist die erwartete bisherige Fassung (neu 0); Bestätigung true.
  `project_ids` ist null für alle erreichbaren Projekte oder eine sortierte,
  eindeutige Liste mit 1–100 IDs. Fassung/Ersteller/Zeit/Instanz/Vorhash werden
  serverseitig erzeugt. Deaktivieren ist eine neue Fassung mit enabled=false.
- Bedingung: exakt `{field,operator,value}`, höchstens acht, Operator
  eq/gte/lte; Text/Bool nur eq. Tage, Stufen und Revisionen sind JSON-Integer.
  Geld-Centwerte `open_minor`/`total_cost_minor` sind **kanonische Strings**,
  auch in Fakten und Quellprojektionen; Regeln erlauben nichtnegative
  Ganzzahlstrings mit höchstens 40 Ziffern. Kein float/gerundeter Number.
- `task.create`: Vorlage `{title,details,priority,due_days}`, priority
  normal/high, due_days null oder 0–365. Tatsächliche Aufgabe der zuständigen
  Person, keine rekursive Überfälligkeit der automatisch erzeugten Aufgabe.
- `offer.draft`: Vorlage `{title,due_days,positions}`, due_days 0–365,
  1–6 Positionen `{article_id,article_revision,quantity}`; quantity ist ein
  positiver Dezimalstring. Preise stammen aus der aktuellen Artikelquelle.
- `document.email` und `dunning.email`: leere Vorlage `{}`, Ziel ausschließlich
  aus dem passenden Ereignis. `payment.execute` bleibt ohne Adapter gesperrt;
  supplier.order besitzt in dieser Fallklasse keinen verfügbaren Auslöser.

Aktuelle Kostenquellen übernehmen `costs.total_net` aus ProjectEconomics einmal,
mit `cost_total_basis: project_economics_total_net_v2`. Historische unmarkierte
Assistant-Quellen enthielten Kategorie- und Gesamtsumme doppelt. Diese alten
Originalnachweise werden nicht neu bewertet; ein offener alter Plan ist durch
den geänderten aktuellen Quellenhash veraltet. Ein neuer Kostenplan verwendet
ausschließlich den tatsächlichen aktuellen Gesamtbetrag.

## Läufe, Beobachtungen, Pläne

- `POST /scan`: exakt `{request_id,limit,after}`, limit 1–100, after null oder
  die zurückgegebene `next_after`-Position. Datum und Ereignisse kommen nur aus
  serverseitigen Fachabfragen. Der erste Lauf berücksichtigt bereits vorhandene
  passende Vorgänge. Quellenrechte werden vor der Seitenbildung geprüft;
  unlesbare Originalkennungen erscheinen auch nicht in issues/next_after.
  `complete` bezeichnet Vollständigkeit dieser berechtigten Abfrage,
  nicht erfolgreichen Abschluss jeder Aktion. Bei `next_after` ausdrücklich
  die nächste Seite verarbeiten. Dauerhafte `processing.items` protokollieren
  die tatsächlichen Ergebnisse beziehungsweise denied/awaiting_approval/blocked.
  Die Laufkennung ist an Instanz, aktuellen Akteur und die originale Request-ID
  gebunden; zwei verschiedene Aufträge mit gleichen Filtern bleiben verschieden.
- `GET /runs`, `/events`, `/plans`: `{schema_version:1,items,next_after}`;
  optionale `after`-ID und `limit` (1–100, Standard50). Keine heimliche
  Beschränkung auf die laufende Sitzung. Beobachtungen ohne passenden Plan
  bleiben auffindbar.
- `GET /runs/<id>`, `/events/<id>`, `/plans/<id>`: jeweiliger einzelner Nachweis.
  Ein Lauf verknüpft Beobachtungen und tatsächliche Plan-IDs. Wiederholte
  Beobachtungen können auf eine bereits gestartete ältere Planfassung für
  denselben `action_key` verweisen.
- Beobachtung bindet `identity,project_id,trigger,as_of,source,facts,active,
  occurrence_key`. `source` enthält descriptor/source_id/data/sha256;
  Quelltexte sind ausschließlich Daten, keine ausführbaren Anweisungen.
- Plan bindet `event_id,event_sha256,project_id,action,action_key,policy,
  context,parameters,preparation_error`, schema_version1 und optional
  `reprepared_after_restore`. Kontext enthält die konkrete Ereignisquelle und
  zusätzlich benötigte Artikel/Projektquellen.
- `policy.mode` ist bereits die effektive Entscheidung. `company_mode`
  bewahrt die Unternehmensregelentscheidung. `project_policies` enthält
  relevante bestehende Projektregeln für manual und denselben Fachauslöser.
  Ein bestehendes Verbot gewinnt, eine Projektfreigabe verstärkt auto zu
  approval, eine abweichende Zuständigkeit verbietet. Freigabe bezieht sich
  auf diesen einen Plan mit beiden Regelständen, nicht auf zwei lose Flows.
- Jede `project_policies`-Position bindet trigger, `original_json` (exakter
  kanonischer Text), `original_sha256` und die sichtbare `policy`-Projektion.
  Geld-Centwerte in der sichtbaren Projektion sind Strings. Der Originaltext
  bleibt ein **String** und wird zur Hashprüfung nicht verlustbehaftet durch
  JavaScript Number geparst. Das Backend prüft seine tatsächlichen alten
  Regelreferenzen und Fakten. Die alten Assistant-Daten werden nicht geändert.
- Abgeleitete Planfelder: status, source_current, can_execute, blocked,
  decision, execution, outcome. Status denied/awaiting_approval/ready/rejected/
  stale/suspended_after_restore/succeeded/failed/unknown/blocked/unconfirmed.
  `blocked` liefert nur aktuelles status_code/message. Eine bekannte frühere
  Ausführung bleibt erkennbar, auch wenn aktuelle Quellen veraltet sind.

## Entscheidung und Ausführung

`POST /plans/<id>/approve` oder `/reject` erhält exakt
`request_id,plan_sha256,reason,confirmation`. Erfordert die zuständige Person,
aktuelle Quelle/Regeln und `assistant.approve`. Eine Entscheidung ist endgültig
für diese Fassung; geänderte Quellen/Regeln brauchen einen neuen Scan.

`POST /plans/<id>/execute` erhält exakt
`request_id,plan_sha256,confirmation`. Die aktuelle zuständige Person und alle
Fachrechte werden erneut geprüft. Auto-Pläne werden bereits vom Scan mit einem
dauerhaft gebundenen serverseitigen Originalauftrag ausgeführt. Externe
Ausführungen verwenden ausschließlich bestehende Fachadapter und Versandgates.
Ein Anspruch wird vor I/O gespeichert. Unklarer Ausgang wird nicht wiederholt.
Bei Restore bleiben Claims erhalten; offene Pläne werden gesperrt. Nach
Betreiberabgleich kann ein neuer Scan nur ungestartete Vorgänge neu vorbereiten.

## Tatsächliche Fixture

`scripts/generate-company-events-fixture.py` erzeugt ausschließlich temporäre
synthetische Daten über den realen Dispatcher. Identische Artefakte:
`docs/fixtures/company_events_2026.json` und
`app/test/fixtures/company_events_2026.json`.
Szenarien auto, approval, deny, project_approval, external_unknown und
external_unconfirmed enthalten
Originalcommands, echte Annahmen, GETs, Listen, Folgefassungen und exakte Replays.
external_unconfirmed wird durch einen wirklichen Testprozessabbruch nach dem
dauerhaften Versandclaim erzeugt. Sein ursprünglicher Execute-Replay hat
`status: unconfirmed`, eine execution, `outcome: null` und die Originalannahme.
Diese gültige Claimannahme darf den lokalen offenen Auftrag auflösen; sie ist
kein Versandnachweis und erlaubt keinen neuen Ausführungsauftrag.
Der externe Testtransport existiert nur im Generator; kein Providerkontakt.
HTTP-/MFA- und unabhängige Domainprüfungen sind zusätzlich ausgeführt. Der
PostgreSQL-/Restore-Nachweis dieses neuen Pakets wurde zusätzlich mit drei
tatsächlichen Fällen erbracht: parallele Claims, bestehende Versandgates und
befüllte Wiederherstellung samt neuer Freigabe nach Betreiberabgleich. Die
JSON-Fixtures selbst bleiben tatsächliche SQLite-Dispatcherantworten.
