# Kundenservice und Reklamationen

Stand: 03.11.2026. Der additive Serviceworkflow verbindet kanonische Kunden,
Anfragen oder Mängel mit Projekten, Geräten, Planung und unterzeichneten
Protokollen. [Clients und Browserprüfung](CRM_ERP_SERVICE_CLIENTS.md) ergänzen
diesen Backend-/API-Bericht; der [frühere Entwurf](CRM_ERP_SERVICE_ENTWURF.md)
dokumentiert Bestandsbefund und weiter verbleibende Betriebsmittelaufgaben.

## Zusammenhängender Ablauf

Ein Fall besitzt einen festen Kunden und wahlweise genau eine Eingangshistorie:
Anfrage, Projektmangel oder vorhandenen Wartungsbesuch. Ansprechpartner,
Verantwortlicher, Art (`request`, `complaint`, `maintenance`), Priorität,
Beschreibung und Wiedervorlage werden ausdrücklich gewählt. Eine Eingangsquelle
kann nur einmal in einen Fall übernommen werden. Fremde Kunden, Projekte,
Personen, Geräte oder Verträge werden serverseitig abgewiesen.

Ein allgemeines Kundenanliegen kann ohne Projekt beginnen. Die Geschäftsführung
übernimmt es später in ein vorhandenes passendes Projekt oder legt genau eines
an. Bei einer Anfrage wird die bestehende Anfragekonvertierung genutzt; wurde
die Anfrage bereits in einem anderen Ablauf konvertiert, wird ihr ursprüngliches
Projekt übernommen. Wiederholung erzeugt kein zweites Projekt.

Die Disposition erzeugt einen echten Termin in der bestehenden Einsatzplanung.
Mitarbeiter, Ressourcen, Zeitzone und Zeiträume unterliegen deren nativen
Rechte-, Abwesenheits- und Kollisionsprüfungen. Der Serviceweg bietet keinen
stillen Konflikt-Override. Weitere Einsätze benötigen neue bewusste Aufträge;
eine wiederholte Vorgangs-ID bestätigt denselben Termin. Zeiten, Material,
Fotos und weitere Kosten werden über das kanonische Projekt erfasst und nicht
nochmals in einem parallelen Servicejournal gebucht.

Unterzeichnete Serviceberichte desselben Projekts können als unveränderliche
Lösungsnachweise verknüpft werden. Ein Bericht kann nur einem Servicefall
zugeordnet sein. Bei Wartungsfällen erfolgt der vorhandene native
Wartungsabschluss in derselben Transaktion; Serienindex, Geräte-/Vertragsstand
und PDF-Hash bleiben erhalten. Ein Entwurf, fremder Bericht oder verändertes
Original erfüllt den Nachweis nicht. Telefonisch gelöste allgemeine Anliegen
benötigen dagegen keinen erfundenen Außeneinsatz oder Wartungsbericht.

## Zustände und Verlauf

Der Fall beginnt als `open`. Prüfung und Bearbeitung führen über `triaged`,
`planned`, `in_progress`, `waiting_customer` oder `waiting_supplier` zu
`resolved` und danach `closed`. `cancelled` dokumentiert einen begründeten
Abbruch. Abschlüsse und Abbrüche können ausdrücklich nach `triaged`
wiedereröffnet werden; ursprüngliche Entscheidungen bleiben sichtbar.

Die Detailantwort enthält die derzeit zulässigen `allowed_transitions`.
`planned` benötigt einen nicht abgesagten Planungstermin; die konkrete
Disposition stellt diesen Zustand selbst her. `resolved/closed` benötigen
eine dokumentierte Lösung. Bei verknüpftem Wartungsbesuch ist zusätzlich dessen
belegter Abschluss erforderlich. Geschlossene/abgebrochene Fälle erlauben keine
neue Disposition oder Quellenübernahme vor der Wiedereröffnung.

Notizen sowie dokumentierte Telefon-, E-Mail- und Besprechungskontakte werden
als eigene Ereignisse gespeichert. Eine spätere Korrektur verweist begründet
auf das ursprüngliche Ereignis. Die monotone `ordinal` erhält die Reihenfolge
auch bei mehreren Aktivitäten innerhalb derselben Sekunde. Aktivitäten
verändern keine Fallrevision; Änderungen des Fallstands erzeugen neue
Versionen. Kunden-/Ansprechpartnerstände werden dabei historisch erhalten.

Ein dokumentierter E-Mail-Kontakt sendet keine Nachricht. Fallstatus und einfache
Unterschrift erklären weder eine gesetzliche Gewährleistung noch Kundenannahme,
Kulanz, Erstattung oder Forderung. Es entsteht keine Rechnung, Bestellung,
Zahlung oder sonstige Außenwirkung. Solche Geschäftsaktionen bleiben in ihren
eigenen bestehenden Freigabe- und Nachweiswegen.

## API

Pfade stehen unter `/business` (lokal `/api`, online `/api/v1`).

| Pfad | Methode | Inhalt |
|---|---|---|
| `/service/options` | GET | Heute erlaubte Kontakte, Projekte, Personen, Geräte, Verträge, Besuche, Mängel, Berichte, Mitarbeiter und Ressourcen; optional `customer_id/project_id` |
| `/service/cases` | GET | Sichtbare Fälle; Filter `q`, `customer_id`, `project_id`, `status`, `priority`, `responsible_id`, `due=overdue` |
| `/service/cases` | POST | Anlage oder versionierte Änderung; Quellenbezüge bleiben nach Anlage fest |
| `/service/cases/{id}` | GET | Aktueller Fall, Quellhash, Links und erlaubte Übergänge |
| `/service/cases/{id}/history` | GET | Unveränderliche Versionen und geordnete Ereignisse |
| `.../events` | POST | Aktivität oder begründete Korrektur |
| `.../project` | POST | Einmalige kanonische Projektübernahme |
| `.../dispatch` | POST | Konkreten echten Planungstermin erzeugen |
| `.../evidence` | POST | Unterzeichneten Servicebericht verknüpfen, gegebenenfalls Wartung abschließen |
| `.../transition` | POST | Zulässige begründete Statusentscheidung |

Anlage/Änderung enthält `request_id`, `revision`, bei Änderung `id`, außerdem
`customer_id`, `person_id`, `project_id`, `asset_id`, `contract_id`, `visit_id`,
`inquiry_id`, `defect_id`, `title`, `kind`, `priority`, `responsible_id`,
`follow_up_on`, `description`. Nicht gewählte Referenzen sind `null`.
Ein gewählter Wartungsbesuch ergänzt seine wirklichen Projekt-, Geräte- und
Vertragskennungen; ein Mangel ergänzt sein Projekt.

Jeder fallbezogene Befehl bindet `revision` und den aktuellen `source_sha256`.
Übernahmen verlangen `confirmation:true`; Statuswechsel `status`, `reason`
und `resolution`. Historische Versionen enthalten ihren gespeicherten Stand;
die aktuelle Quellenprüfung darf nicht nachträglich als historischer Quellenhash
ausgegeben werden. Ereignisse halten den tatsächlich geprüften Eingabehash fest.

Anlage/Änderung liefern direkt den Fall. Andere Befehle liefern
`{case, event?, link?}`. Angenommene Originalaufträge liefern dieselbe
unveränderliche Quittung, auch nach eigener Projektanlage, neuer Verknüpfung,
weiterer Fallversion oder Restore. Vor Rückgabe gelten heutige Identität und
Rechte; die alte Version/der alte Quellhash wird bei einem bereits angenommenen
Auftrag nicht erneut als neue Schreibabsicht bewertet. Ein nachweislich nicht
angenommener Konflikt trägt `request_resolution=not_accepted`; belegte
Vorgangs-ID-Kollisionen erhalten diese Aussage nicht.

## Rechte und fachliche Aktivierung

Projektfälle benötigen aktuelle Projektberechtigung, `contacts.read` und
`documents.read`; Schreiben zusätzlich `documents.write`. Der Verantwortliche
muss den Fall und seine ausgewählten Quellen heute selbst bearbeiten/lesen
können. Fälle ohne Projekt sind der Geschäftsführung vorbehalten, Schreiben
verlangt dort `contacts.write`. Eingeschränkte Projektrollen erhalten keine
fremden Eingangshistorien oder globale Kundenakten. Das allgemeine Listing
filtert jeden Fall erneut nach seinen eigenen Quellenrechten.

Projektübernahme verlangt `projects.manage`. Neue Disposition verlangt
`planning.write` und das aktive Planungsmodul. Neue Berichtsverknüpfung und
Wartungsabschluss benötigen das aktive Dokumentmodul. Eine deaktivierte
Planungs-/Dokumentgruppe sperrt diese neuen Fachwirkungen, nicht die gesamte
Kernfallverwaltung. Bereits angenommene Originalquittungen bleiben serverseitig
ohne neue Wirkung wiederlesbar. Clients können vor einer Wiederholung bereits
konservativ eine erneute Aktivierung verlangen. Offline-/Projektgerätetokens
öffnen die Fallverwaltung nicht.

## Daten, Export und Wiederherstellung

Fünf neue Tabellen speichern `business_service_cases`, `versions`, `events`,
`links` und `requests`, jeweils mit Präfix `business_service_`. Fachstände und
Quittungen sind nur einfügbar; SQLite schützt auch ersetzende Inserts,
PostgreSQL trennt Runtime-SELECT/INSERT und zusätzliche Migratortrigger.
Bestehende Schema-Prüfsummen wurden nicht verändert.

Die Integritätsprüfung kontrolliert feste Kunden-/Quellbezüge, lückenlose
Versionen und Ereignisse, Korrekturreihenfolge, kanonische Projekt-/Terminbezüge,
unveränderte signierte Berichte und Quittungsgleichheit mit dem ursprünglichen
Fall-/Ereignis-/Verknüpfungsstand. Backup/Restore erhält diese Nachweise; es
werden keine Termine oder Außenwirkungen automatisch neu ausgeführt.

Servicehistorien sind personenbezogene Fachnachweise. Der Firmenexportkatalog
enthält die vier fachlichen Tabellen und behandelt technische Requests getrennt.
Die Datenschutzquelleninventur folgt dem Kundenbezug in die Fallhistorie;
eine automatische vollständige Löschung wird nicht behauptet. Die konkrete
Servicehistorien-Löschsperre verlangt einen gesonderten Bereinigungsplan.

## Tatsächliche Verifikation

- Domain: `backend/test_business_service.py`, **9/9 bestanden, 1,638 Sekunden**, prüft Anfragekonvertierung und
  Übernahme eines bereits entstandenen Projekts, Zustände/Wiedereröffnung,
  Aktivitäten/Korrekturen, native Planungskollision, späteren Fehlerrollback,
  echte Moduldeaktivierung, Fremdquellen, alte Versionen/Quellen, unveränderliche
  Wartungsberichte und Originalquittungen.
- PostgreSQL: `backend/online/test_business_service_pg.py`, **2/2 bestanden,
  8,392 Sekunden, keine Skips**. Echte MFA-/HTTP-Routen, konkurrierende
  Erst-Disposition über zwei Laufzeitverbindungen, Wiederholung nach eigener
  Wirkung und Neustart, Rollen-/Gerätetokenbegrenzung, Runtime-/Migratorguards,
  normale Migration und tatsächlicher `pg_dump`/Restore in eine getrennte DB.
- Logs: `work/verification/service-domain.log`,
  `work/verification/service-pg.log`. Client-/Browsernachweise stehen im
  [gesonderten Bericht](CRM_ERP_SERVICE_CLIENTS.md).

Alle Fälle sind synthetisch. Es wurden keine echten Kunden kontaktiert,
Termine in externe Kalender geschrieben oder produktive Vorgänge ausgeführt.
Der noch fehlende eigenständige Betriebsmittelausgabe-/Rückgabe-/Prüffristenablauf
wird durch diese Serviceabnahme nicht als abgeschlossen erklärt.
