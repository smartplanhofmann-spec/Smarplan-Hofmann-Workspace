# Tatsachenvertrag für Flug-, Schiffs- und Ortsdatumstage2026

Stand03.11.2026. Implementierung:
`backend/payroll_travel_transport_2026.py`.
Eigene Tests: `backend/test_payroll_travel_transport_2026.py`, derzeit 17/17
bestanden. Diese Tests sind Implementierungstests. Die unabhängige Gegenprüfung
des neuen Helfers und seiner Integration übernimmt `travel_backend`; die zuvor
unabhängig geprüften20 Basisfälle bleiben unverändert archiviert.

## Geltung und Versionierung

`resolve_transport_days(trip, sites)` ist rein fachlich: keine Datenbank,
keine Freigabe, keine Zahlung. `sites` ist eine Liste unveränderlicher
Stättenfassungen oder das entsprechende Dictionary. Der Helfer verwendet
`de_travel_transport_2026_v1` und `TRAVEL_TRANSPORT_HASH`; dessen Inhalt bindet
Tabellenhash, Regelbezeichnung, Primärquelle und den SHA256 seiner tatsächlichen
Python-Moduldatei. Jede Dateiänderung ändert daher den Nachweishash.

Die Integration erfolgt ausschließlich in die neue Reiseberechnung
`de_travel_2026_v2`. Bereits gespeicherte `de_travel_2026_v1`-Abrechnungen werden
weiter mit dem eingefrorenen alten Rechenkern geprüft. Ein später geänderter
Helfer darf nicht stillschweigend historische Abrechnungen neu interpretieren.

Primärquelle: Amtliche LStH2026, R9.6 Abs.3:
https://amtliche-handbuecher.bundesfinanzministerium.de/lsth/2026/A-Einkommensteuergesetz/II-Einkommen-2-24b/4-Ueberschuss-d-Einnahmen-ueber-die-Werbungsk-8-9a/Paragraf-9/r-9-6.html

Am03.11.2026 war der direkte HTTP-Abruf mit503 nicht verfügbar; der Suchindex
stellte den vollständigen amtlichen Text bereit. Die2026-Beträge wurden
zusätzlich vollständig gegen das unabhängig erfasste BMF-Schreiben verglichen,
siehe `CRM_ERP_REISEPAUSCHALEN_GEGENPRUEFUNG_2026.md`. Ein heruntergeladenes
Original-PDF oder dessen Hash wird nicht behauptet.

## Eingabe

`trip.details.transport_facts` ist optional und standardmäßig `[]`. Bei einer
gewöhnlichen Bodenreise ohne solche Fakten liefert der Helfer keine Overrides.
Bei Flug-/Schiffsabschnitten ohne dazugehörige Fakten bleibt ein konkreter
Freigabeblocker bestehen.

Jeder Fakt enthält eine eindeutige32-stellige Hex-ID und eine nichtleere Liste
`source_file_ids`. Der API-Dienst muss diese Originale mit aktuellen Rechten und
passender Mitarbeiterbindung auflösen, archivieren und beim Restore unverändert
rekonstruieren. Der Helfer prüft Form und Zuordnung, nicht die Dateiinhalte.
Eine frei gewählte Pauschale, Landessatz-ID oder ein zweiter Zeitpunkt ist in
diesen Fakten ausdrücklich kein erlaubtes Feld.

Flugverbindung:

```json
{
  "id": "32-stellige-Hex-ID",
  "kind": "flight",
  "legs": [
    {
      "segment_id": "ID-eines-vorhandenen-Flugabschnitts",
      "departure_site_ref": {"id":"...", "revision":1, "content_hash":"..."},
      "arrival_site_ref": {"id":"...", "revision":1, "content_hash":"..."}
    }
  ],
  "stopovers": [
    {
      "after_segment_id": "Flugabschnitt-vor-der-Zwischenübernachtung",
      "overnight_ids": ["ID-einer-vorhandenen-tatsächlichen-Nacht"]
    }
  ],
  "source_file_ids": ["Original-ID"]
}
```

Die Flugabschnitte werden in tatsächlicher Reihenfolge angegeben. Jeder muss
`transport=flight` besitzen. Zeiten stammen ausschließlich aus dem gebundenen
Abschnitt. Zwischen zwei Flügen müssen alle tatsächlichen Transfer-/Aufenthalts-
abschnitte lückenlos dokumentiert sein; eine zwischenzeitliche Arbeitstätigkeit
ist kein bloßer technischer Anschluss und verlangt getrennte Verbindungen.

Ohne notwendige Zwischenübernachtung bleibt die Zwischenlandung für den
Landessatz unberücksichtigt. Ein notwendiger Stopp bindet eine vorhandene Nacht
an einen tatsächlich über örtliche Mitternacht reichenden Außenaufenthalt
`activity=stay`, `transport=ground`, `necessary_stopover=true` mit derselben
Stättenfassung. Die Nacht darf nicht die eigene Wohnung/erste Tätigkeitsstätte
sein. Ein allein angekreuzter Stopp ohne die zugehörige Nacht ist ein Blocker;
eine falsch zugeordnete Nacht ist ein fehlerhafter Auftrag. Es gibt keine
Zwischenübernachtung nach dem letzten Flug einer Verbindung.

Schiffsreise:

```json
{
  "id": "32-stellige-Hex-ID",
  "kind": "ship",
  "segment_ids": ["Schiffsabschnitt-1", "Schiffsabschnitt-2"],
  "departure_site_ref": {"id":"...", "revision":1, "content_hash":"..."},
  "arrival_site_ref": {"id":"...", "revision":1, "content_hash":"..."},
  "role": "passenger",
  "high_seas_segment_ids": [],
  "source_file_ids": ["Original-ID"]
}
```

Die Schiffsabschnitte bilden eine unmittelbar aufeinanderfolgende, lückenlose
Fahrt. Zulässige Rollen: `passenger`, `german_state_crew`,
`german_merchant_crew`. Die letzte Rolle bedeutet Personal der Handelsmarine
unter deutscher Flagge; das ist mit den Originalen nachzuweisen und keine
allgemeine Arbeitnehmereigenschaft. `high_seas_segment_ids` ist eine Teilmenge
der gebundenen Schiffsabschnitte. Unterschiedliche Gewässer werden durch echte
Abschnitte getrennt. Das Hafenortsdatum wird aus tatsächlichem Ein-/Ausstieg und
der gebundenen Ortszeitzone ermittelt. Ein-/Ausschiffungstage haben Vorrang vor
dem allgemeinen Seetagessatz.

Alle Flug-/Schiffsabschnitte einer Reise müssen jeweils genau einmal zugeordnet
sein. Doppelte Zuordnung, erfundene Abschnitts-/Nacht-IDs, freie zusätzliche
Felder, eine zeitliche Anschlusslücke oder ein außerhalb der Fahrt zugeordneter
Hochseeabschnitt führen zu400. Fehlende Fakten oder eine am Transportdatum nicht
gültige Stättenfassung führen zu nachvollziehbaren Blockern. Sämtliche Reise-
abschnitte müssen insgesamt exakt die belegte Abreise bis Rückkehr abdecken.

## Ausgabe und Kalenderbedeutung

```text
{
  days: {
    "YYYY-MM-DD": {
      rate_id, reason, source, timezone
    }
  },
  calendar_days: [
    {date, timezone, utc_from, utc_to, elapsed_overlap_seconds,
     attribution: "one_local_calendar_date", source}
  ],
  blockers: [{code, text, source_ref}],
  facts_hash,
  transport_rule_version,
  transport_rule_hash
}
```

`days` enthält nur durch die belegten Transporte betroffene Tage. Jeder lokale
Datumswert kommt genau einmal vor. Flugankünfte werden ab tatsächlicher Landung
berücksichtigt. Ganze Zwischentage einer Flugverbindung über mehr als zwei
örtliche Kalendertage erhalten den Österreichsatz. Technische Zwischenlandungen
werden ignoriert; ein nachgewiesener notwendiger Übernachtungsstopp unterteilt
die Verbindung und lässt den tatsächlichen Aufenthaltsort wirken. Bei Rückkehr
nach Deutschland bleibt ein maßgeblicher letzter ausländischer Tätigkeitsort
erhalten.

Für einen wiederholten Ortsdatumswert nach westlicher Datumsgrenzenquerung wird
die tatsächlich spätere relevante Ankunft beziehungsweise der spätere
Bodenaufenthalt gewählt. Ein zweiter Anspruch für denselben Mitarbeitertag wird
nicht erzeugt. Beispiel: Tokio03.02.00 Uhr → Honolulu02.02.12 Uhr, anschließend
Aufenthalt bis04.02.; der wiederholte02.02. wird einmal dem tatsächlich zuletzt
erreichten Ort Honolulu zugeordnet, ebenso der dort folgende03.02.

Die UTC-Grenzen dokumentieren den jeweiligen **örtlichen Kalendertag**. Sie sind
keine künstlich lückenlose, addierbare Reisedauer: Durch Ortszeitwechsel können
sich diese Grenzen überschneiden oder Abstand haben. Die tatsächlich verstrichene
Reisezeit bleibt die Differenz ihrer unveränderten UTC-Zeitpunkte. Tagesansprüche,
Mahlzeiten und bereits belegte Mitarbeitertage müssen vom Hauptrechenkern auf
derselben eindeutigen Datumszuordnung zusammengeführt werden. Ein örtliches Datum
außerhalb der belegten gesamten Reisetage erzeugt einen konkreten Blocker statt
eines erfundenen weiteren Tags. Gewöhnliche Bodenreisen über unterschiedliche
Ortsdatumsgrenzen werden durch diesen Transportvertrag noch nicht automatisch
freigegeben.

`facts_hash` bindet die genaue Reise, Stättenfassungen, Transportfakten,
berechneten Tageszuordnungen und Blocker. Die Hauptberechnung muss jeden Blocker
übernehmen. Ein pauschaler alter Flug-/Kalenderblocker darf nur ersetzt werden,
wenn der vollständige neue Nachweis tatsächlich geprüft ist. Unterkunftskosten,
Mahlzeiten, Dreimonatsfrist, privater Reiseanteil und steuerpflichtiger Lohnanteil
bleiben eigenständige Tatbestände; ein gültiger Transportnachweis erteilt ihnen
keine pauschale Freigabe.

## Zahlenreferenzen und Prüfstand

Die 17 eigenen Fälle umfassen: Zeitpunkt tatsächlicher Landung; Deutschland14,
Österreich50 bei Zwischenflugtag; technischer Stopp gegenüber notwendiger Nacht
Singapur71; Rückkehr mit letztem ausländischem Tätigkeitsort; Kiel14/Seetag
Luxemburg63/Oslo50; qualifizierte deutsche Besatzung auf Hoher See28; wiederholtes
Ortsdatum; fehlende Nachweise, falsche Nacht, abgelaufener Hafenbeleg, unzulässige
Felder, Reihenfolge-/Deckungsfehler und veränderte Originalbindung. Die Werte
sind aus den amtlichen Regeln abgeleitete eigene Referenzfälle und keine
veröffentlichten amtlichen Reisebeispiele.

Die unabhängige Integration fand zusätzlich einen widersprüchlichen Nachweis:
Eine als Wohnung (`kind=home`) erfasste Stätte konnte als Flughafen oder Hafen
gebunden werden. Der Helfer weist diese Verwendung jetzt für Abflug, Landung,
Ein- und Ausschiffung zurück. Eine tatsächliche Flughafen-/Hafenstätte darf
zugleich erste Tätigkeitsstätte sein; `first_workplace` wird deshalb nicht
pauschal ausgeschlossen. Der eigene Gegenfall prüft alle vier Verwendungen
und beide zulässigen Transportarten mit einer ersten Tätigkeitsstätte.

Helferstand nach diesem Befund am 03.11.2026 eingefroren:
`TRAVEL_TRANSPORT_HASH=dd2e2558bc0ace9f18e31488f5da600f838a522e2fd7174da404d89844af84a9`.
17/17 eigene Tests sind grün. Änderungen erfolgen anschließend nur nach
abgestimmtem konkretem Gegenbefund; die 20 früheren unabhängigen Reiseprüfungen
bleiben unverändert.

```sh
PYTHONPATH=backend:backend/online /tmp/smartplan-backend-verified/bin/python -m unittest -v test_payroll_travel_transport_2026
```

Ausstehend sind die unabhängigen Gegenproben, die vollständige v2-Integration in
API/Clients/Archivprüfung und deren End-to-End-Nachweis. Ein grüner isolierter
Helfertest allein schließt diesen Integrationsschritt nicht ab.
