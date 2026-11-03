# Lohnfakten und Periodenplan – verbindlicher P2/P3-Vertrag

Stand: 03.11.2026. Implementierungsvertrag nach lokalem Checkpoint `31c5184`;
P2-Backendnachweise stehen in [Lohnfakten](CRM_ERP_LOHN_FAKTEN_2026.md).
Der Vertrag allein ersetzt keine Produktfreigabe. Feature `payroll_period_facts`,
Modul `business_payroll_facts`, private Businessrouten unter `/payroll`.
Der [fachliche Entwurf](CRM_ERP_LOHN_ZEITACHSEN_TEILMONATE_ENTWURF.md) liefert
Quellen und Abgrenzungen. Bestehende v1/v2/v3-Lohnbelege bleiben unverändert.

## Referenzen und Rechte

Alle Objektkennungen sind wie in den bestehenden Payrollquellen 32 kleine
Hexzeichen; die frühere Entwurfsidee eines `payfact_`-Präfixes wird nicht verwendet.
`ref = {id,revision,content_hash}`, positive ganzzahlige Revision und SHA-256.
`file = {id,employee_id,purpose,owner_visible,filename,media_type,size,sha256,
content_hash,supersedes,created_by,created_at}` entspricht der bestehenden
Personalakten-Metadatenansicht. Originalupload/-download bleiben auf den
vorhandenen `/personnel/files`-Routen. Keine zusätzliche Originalkopie.

Jeder neue Leseweg verlangt frisches globales `personnel.read`; ein eigenes
Mitarbeiterkonto mit nur `time.own` erhält diese private Faktenhistorie nicht.
`employment_terms` und `work_schedule` verlangen zusätzlich `personnel.write`,
`period_case` zusätzlich `personnel.approve`. Ein aktives Personalmodul ist für
neue Fachwirkung erforderlich. Bereits angenommene Originalaufträge werden vor
diesem Aktivierungsgate unter frischen Lese-/Aktionsrechten geprüft; eine spätere
Deaktivierung verhindert die Bestätigung ihrer ursprünglichen Quittung nicht.
Kompatibilitäts-/Serverfreigaben bleiben gesondert wirksam.

Fähigkeiten werden getrennt ausgegeben: `can_write` und `can_approve` sind die
frischen Rechte, `writes_enabled` ist die aktuelle Personalmodulaktivierung.
Keine Fähigkeit ist Teil eines fachlichen Quellen- oder Vorschauhashes.

## Quellen, Listen und Historie

`GET /payroll/facts/sources?employee_id=…` liefert exakt die Struktur:

```text
{
 employee: {id,user_id,name,employment_from,employment_to,revision},
 employee_id, files:[file], agreements:[bestehende vollständige HR-Vereinbarung],
 preparations:[bestehende vollständige HR-Monatsvorbereitung],
 profiles:[bestehendes vollständiges Payroll-Profil],
 identities:[bestehender vollständiger Lohnkonto-Identitätsnachweis],
 facts:[fact], absences:[genehmigte kanonische Abwesenheit ohne details-Freitext],
 can_write,can_approve,writes_enabled
}
```

Nur aktuelle Fassungen derselben Person; Dateien mit Zweck `personnel`.
Historische Quellen bleiben über ihre unveränderlichen konkreten Referenzen
prüfbar. Eine ersetzte Originaldatei kann für neue Fakten nicht stillschweigend
weiterverwendet werden. Bereits angenommene historische Fassungen bleiben gültig.

`GET /payroll/facts?employee_id=…[&kind=…]`:
`{employee_id,items:[fact],can_write,can_approve,writes_enabled}`.
`GET /payroll/facts/{id}` liefert eine aktuelle `fact`.
`GET /payroll/facts/{id}/history`:
`{employee_id,items:[fact]}` in aufsteigender Revision.

```text
fact = {
 id,revision,employee_id,kind,effective_from,effective_to,status,
 details,source_file_ids,source_hash,sources,plan,preview_hash,
 correction_reason,previous_hash,content_hash,created_by,created_at
}
```

`status` ist `active` oder `void`; `plan` ist nur für `period_case` ein Objekt,
sonst null; `preview_hash` ist entsprechend der ursprüngliche Periodenvorschauhash
oder null. `sources` ist der vollständige private kanonische Quellsnapshot,
`source_hash` dessen SHA-256. Das Quellenobjekt enthält nur benötigte Daten;
keine Diagnosen oder ursprünglichen Datei-Bytes. Technische Anfragehashes und
interne Eindeutigkeitsschlüssel erscheinen nicht im DTO.

## Die drei typisierten Details

```text
employment_terms.details = {
 employment_from: YYYY-MM-DD, employment_to: YYYY-MM-DD|null,
 agreement_refs:[ref],
 proration_method: calendar_days_actual|contractual_30_days|scheduled_workdays|scheduled_seconds,
 reason: nichtleerer Text
}
```

Beschäftigungsdaten müssen zum aktuellen Personalstamm passen. Mindestens eine
geprüfte Vereinbarung; gleicher Mitarbeiter, exakte aktuelle Fassung. Änderungen
brauchen einen begründeten neuen Faktstand. Überlappende aktive Beschäftigungs-
fakten sind unzulässig; eine zukünftige neue Beschäftigung darf nicht durch
Überschreiben eines früheren Ursprungs behauptet werden.

```text
work_schedule.details = {
 month: 2026-MM,
 days:[{date:YYYY-MM-DD,scheduled_seconds:0..86400,
        workplace:Text,federal_state:DE-Länderkürzel}],
 reason:nichtleerer Text
}
```

Der Plan enthält jeden Kalendertag des Monats genau einmal und chronologisch,
auch arbeitsfreie Tage mit null Sekunden. Gültige Länderkürzel:
`BW,BY,BE,BB,HB,HH,HE,MV,NI,NW,RP,SL,SN,ST,SH,TH`.
`workplace` darf an arbeitsfreien Tagen leer sein, sonst ist es erforderlich.
Arbeits-/Kalendertagszähler werden serverseitig hergeleitet; kein editierbares
Ergebnisfeld. Keine automatische Feiertags-/Urlaubs-/EFZ-Anspruchsbestätigung.

```text
period_case.details = {
 month:2026-MM, preparation_ref:ref, employment_terms_ref:ref,
 work_schedule_ref:null|ref, profile_refs:[ref], identity_refs:[ref],
 tax_treatment:domestic_running_wages,
 entitlement_decisions:[{
   kind:ordinary_work|public_holiday|vacation|sickness_continued_pay|unpaid_leave|sickness_after_entitlement,
   from:YYYY-MM-DD,to:YYYY-MM-DD,source_absence_id:null|ID,
   source_file_ids:[ID],reason:nichtleerer Text
 }],
 verification_note:nichtleerer Text
}
```

Keine freien Brutto-, Steuer-/SV-Tages- oder Bemessungsfelder. Leere
`entitlement_decisions` ist für einen gewöhnlichen Fall ohne zu prüfende
Abwesenheit zulässig. Vorhandene Quellen werden nicht dadurch ausgeblendet;
ungeklärte oder noch nicht berechenbare Fälle erscheinen als konkrete Blocker.
Alle Originale der Anspruchsentscheidungen stehen zusätzlich in der äußeren
`source_file_ids`-Liste. Profile/Identitätsnachweise werden vollständig mit den
für den Monat einschlägigen aktuellen Fassungen gebunden; ausgelassene spätere
Merkmaländerungen werden nicht als unveränderter Standardfall behandelt.

## Vorschau und Bestätigung

`POST /payroll/periods/preview`:

```text
{employee_id,employee_revision,details:period_case.details,source_file_ids:[ID]}
```

Die frische Monatsvorbereitung muss weiterhin zu den aktuellen freigegebenen
HR-Quellen passen. Ergebnis:

```text
{
 employee_id,month,source_snapshot,source_hash,plan,preview_hash,
 can_confirm,can_calculate,can_write,can_approve,writes_enabled
}
```

`can_confirm` bedeutet ein korrekt gebundenes, speicherbares Faktenbild;
`can_calculate` setzt zusätzlich einen vollständig unterstützten Rechenfall
voraus. Ein bestätigter, noch fachlich blockierter Fall ist keine Netto-0-
Abrechnung. `plan.blockers` erklärt die fehlenden Entscheidungen/Funktionen.
`preview_hash` bindet `{source_snapshot,plan}`; Fähigkeiten gehören nicht hinein.

`POST /payroll/facts`:

```text
{
 request_id,employee_id,employee_revision,kind,revision,status,details,
 source_file_ids:[ID],confirmed:true,
 id?,correction_reason?,preview_hash?
}
```

Neue Identität: `revision:0`, ohne `id`; Korrektur: vorhandene `id`, bisherige
Revision und nichtleerer Grund. `preview_hash` ist genau für `period_case`
erforderlich; andere Arten akzeptieren dieses Feld nicht. `source_file_ids`
enthält ein bis zwanzig unterschiedliche private Originale derselben Person.
Neue Erstfassungen können nur `active` sein. `void` erzeugt eine begründete
archivierte Fassung mit identischen bisherigen fachlichen Quellen/Details;
es entfernt keine Historie. Ein archivierter Monatsfall verwendet seinen
ursprünglichen `preview_hash` ohne neue Vorschau; inzwischen ersetzte Originale
bleiben für diese unveränderte historische Archivierung zulässig. Wiederaktivierung verlangt neue aktuelle Quellen.
Pro Mitarbeiter und Monat besteht genau eine kanonische Arbeitsplan- und
Monatsfallidentität; weitere Fassungen sind begründete Korrekturen.

Antwort ist die unveränderliche angenommene `fact`, HTTP 200. Wiederholung mit
identischer Anfrage-ID und identischem vollständigem Originalbody liefert
diese konkrete Fassung; Änderungen unter derselben ID ergeben 409. Rechte,
Mitarbeiterbezug, Quelldateiintegrität und ursprüngliche Fassung werden frisch
geprüft. Neue Quell-/Stammrevisionen sperren neue Fachwirkung; sie überschreiben
keine bereits angenommene Quittung. `409 request_resolution:not_accepted`
bedeutet nachgewiesen keine Annahme; ohne diese Markierung Auftrag erhalten.
403/404 entfernt Zugriff, 423 pausiert neue Fachwirkung, 5xx/Netzverlust lässt
den exakten Auftrag offen. Alle Quellen- und Mutationswege sind online; kein
stilles Offline-Archiv sensibler Anspruchsentscheidungen.

## Reiner P3-Vertrag und Payroll-Integration

P2 sammelt und bindet dieses private Quellenobjekt; der Rechenkern benötigt
keinen Datenbankzugriff:

```text
source_snapshot = {
 schema_version:1,employee_id,month,
 preparation:<vollständige historische HR-Vorbereitung>,
 profiles:[vollständige gebundene Payroll-Profile],
 identities:[vollständige gebundene Lohnkontoidentitäten],
 employment_terms:<vollständige gebundene fact>,
 work_schedule:<vollständige gebundene fact>|null,
 case_details:<normalisierte period_case.details>,
 source_files:[file]
}
```

`payroll_periods_2026.build_period_plan(source_snapshot) -> plan` ist rein und
deterministisch. `calculate_period_source(source_snapshot,rule_version=None)`
liefert das vollständige Berechnungsergebnis. Regelversion
`de_2026_periods_pap_v4`; unterstützte Scopes `regular_standard_period`,
`regular_transition_period`, `commercial_minijob_period_flat_tax`. Der Planhash
enthält Regelversion, Quellen und Blocker, keine aktuellen Benutzerrechte.

Neuer alternativer Payroll-Vorschauinput:
`{source_schema_version:2,employee_id,period_case_ref:ref}`.
Die v2-Lohnquelle bindet `source_schema_version:2`, den vollständigen ursprünglichen
Monatsfall und dessen Snapshot/Plan; vorhandene `profile`-/`preparation`-Felder
bleiben für kompatible Leser erhalten. Der bisherige vollständige v1-Input
bleibt unverändert. Finalisierung verwendet den bestehenden Rahmen
`request_id,preview_hash,accepted_scope,confirmed,id?,revision,correction_reason?`.

P2 stellt `PayrollFacts.resolve_period_case(actor,employee_id,ref,fresh=True)`
bereit: genaue aktive Monatsfallfassung, Rechte und bei neuer Berechnung aktuelle
Quellen; Resultat vollständige `fact`. Historische Prüfung verwendet
`validate_fact_sources(office,fact)` ohne heutige Stammdatenbindung und
`validate_integrity(office)` über alle Fassungen/Annahmen. Keine zyklischen
Imports: P2 importiert Payroll/Profile und Konten ausschließlich beim Auflösen
konkreter Quellen; der reine P3-Kern importiert P2 nicht.

## Additive Datenhaltung und Integrationsvertrag

Genau zwei Tabellen, keine Änderung einer alten Tabellendefinition:

```text
business_payroll_fact_events(
 id,revision,employee_id,kind,effective_from,effective_to,status,
 payload_json,sources_json,source_hash,previous_hash,content_hash,
 created_by,created_at,identity_key,command_hash
)
PRIMARY KEY(id,revision), UNIQUE(employee_id,identity_key)

business_payroll_fact_requests(
 user_id,request_id,operation,request_hash,
 fact_id,fact_revision,fact_content_hash,created_at
)
PRIMARY KEY(user_id,request_id)
```

Alle Tabellen erhalten SELECT/INSERT als Runtimeprivileg und Immutable-Guards.
`identity_key` ist nur auf Erstfassungen belegt und bindet Art plus Beginn/Monat.
`command_hash` liegt im gehashten Faktereignis und bindet den exakten ursprünglichen
Auftrag an die technische Quittung, ohne eine zweite private Bodykopie zu speichern.
`payload_json` enthält Details, Original-IDs, Plan und Korrekturgrund;
`sources_json` die damaligen kanonischen Quellen. Der Fachhash bindet die
vollständige Fassung einschließlich Quellenhash und ursprünglichem Auftrag.

Root registriert Modul/API/Strict-Transport, Feature, Paketdateien und
Original-/Export-/Privacy-/Restoreintegration. Unternehmensexport nimmt
`business_payroll_fact_events` als sensible Personalhistorie auf;
`business_payroll_fact_requests` ist technische Wiederholungsverwaltung und
wird ausgeschlossen. Personeninventar bindet `employee_id`, relevante
Originale und historische Fakten; allgemeine Finanz-/Assistentenansichten
erhalten keine Anspruchsgründe. Restore validiert Quellenreferenzen und alle
Originalhashes, bevor neue Lohn-/Zahlungswirkung freigegeben wird.
