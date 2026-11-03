# Betriebsmittel: Identifikation, Nachweise, Ausgabe und tatsächliche Verfügbarkeit

Stand: 03.11.2026. Implementierter Teil von R07.07 auf dem bestehenden
Ressourcenstamm `business_resources`. Das Modul legt keine zweite Fahrzeug-,
Maschinen- oder Werkzeugdatenbank an. Kundenanlagen `business_assets` bleiben
projektgebundene Kundenanlagen; gleiche Namen oder Seriennummern verbinden
beide Bereiche nicht automatisch.

Bedienung und echte Clientabnahme:
[CRM_ERP_BETRIEBSMITTEL_CLIENTS.md](CRM_ERP_BETRIEBSMITTEL_CLIENTS.md).
Der ursprüngliche [Entwurf](CRM_ERP_BETRIEBSMITTEL_ENTWURF.md) bleibt als
Planungsstand erhalten; dieser Bericht beschreibt den tatsächlichen Vertrag.

## Fachlicher Ablauf

Eine kanonische Planungsressource erhält versionierte Seriennummer, Hersteller,
Modell, Standort, Zustand und Notiz. Jede Änderung benötigt einen Grund und den
frisch gelesenen Quellenstand. Während einer offenen Ausgabe lassen sich
Seriennummer, Hersteller, Modell sowie nativer Ressourcentyp/-code nicht
umdeuten. Namens- und Standortkorrekturen ändern die Identität nicht.

Ausdrücklich angelegte Anforderungen enthalten Bezeichnung, Fälligkeit,
Nutzungsverbindlichkeit und Aktivstatus. Es gibt keine automatisch abgeleiteten
Prüfpflichten oder gesetzlichen Intervalle. Eine verbindliche aktive Anforderung
sperrt neue Einsätze, bis für ihre aktuelle Version ein tatsächlich dokumentierter,
bestandener Nachweis zur aktuellen Ressourcenidentität vorliegt. Eine bloße
Anforderungsänderung übernimmt keinen früheren Prüfnachweis auf neue Bedingungen.
Eine rein informative Anforderung sperrt nicht. Deaktivierung und Umstellung
bleiben mit Grund in der Historie.

Eine Prüfaussage benennt Zeitpunkt, prüfende Person, tatsächliches Ergebnis
(`passed`, `failed`, `review_required`), Notiz und einen unveränderten Originalbeleg.
Ein zukünftiger tatsächlicher Prüfzeitpunkt wird abgewiesen. Der nächste Termin
wird ausdrücklich angegeben oder leer gelassen; aus einem leeren Termin wird
kein gesetzlicher Wiederholungsrhythmus abgeleitet. Ein angegebenes Datum gilt
bis einschließlich dieses Kalendertags in der Zeitzone des geplanten Einsatzes.
Der ursprüngliche Anforderungstermin beschreibt die gewünschte Erstfälligkeit;
nach einem bestandenen Nachweis gilt dessen ausdrücklich angegebener Folgetermin.
Die Software führt keine technische Prüfung durch und erteilt kein Prüfzertifikat.

Ausgabe dokumentiert eine wirkliche Übergabe an mindestens einen aktiven
kanonischen Mitarbeiter oder ein zugängliches Projekt. Bei beiden Bezügen muss
der Mitarbeiter das Projekt tatsächlich sehen dürfen. Originale enthalten sichere
Mitarbeiter- und Projektsnapshots, Ausgabezeit, erwartete Rückgabe, Zustand und
Vermerk. Kosten oder Gehälter werden nicht in die Auswahl übernommen. Pro
Ressource gibt es höchstens eine offene Ausgabe. Die erwartete Rückgabe schließt
sie niemals automatisch.

Rücknahme verweist auf genau eine offene Ausgabe und erfasst den wirklichen
Zeitpunkt, optional den empfangenden tatsächlichen Mitarbeiter, Zustand und
Vermerk. Ausgaben und Rückgaben dürfen nicht in der Zukunft liegen; tatsächliche
Ausgabezeiträume dürfen sich nicht überschneiden. Eine physische Übergabe darf
auch einen defekten Zustand dokumentieren, beispielsweise eine tatsächlich
erfolgte Übergabe zur Reparatur. Diese Dokumentation gibt die Nutzung nicht frei.

Fehlerhafte Ausgabe-/Rücknahmeangaben werden ausschließlich durch zusätzliche,
begründete Korrekturen mit verpflichtendem Originalbeleg berichtigt. Originale
bleiben unverändert. `effective` enthält die aktuelle fachliche Fassung. Eine
Korrektur einer alten, bereits abgeschlossenen Übergabe hebt einen später
festgestellten Schaden nicht auf. Auch die Rückgabe darf nicht nachträglich
auf eine andere Ausgabe umgebucht werden. Zeitüberschneidungen werden bei jeder
Korrektur erneut geprüft.

## Verbindung mit dem tatsächlichen Kalender und Service

`business_planning.Planning` prüft vor jeder neuen oder geänderten geplanten
Zuordnung den dokumentierten Zustand, aktuelle verbindliche Nachweise und deren
Gültigkeit sowie die tatsächlichen Ausgabezeiträume. Eine offene Ausgabe an
Mitarbeiter und Projekt erlaubt nur Zuordnungen mit demselben Mitarbeiter und
Projekt. Eine Ausgabe ausschließlich an ein Projekt bindet an dieses Projekt;
eine reine Mitarbeiterausgabe bindet an diesen Mitarbeiter.

Nutzungssperren sind mit `planning.override` nicht übersteuerbar. Normale
Kalenderkonflikte behalten ihren bestehenden ausdrücklichen Übersteuerungsweg.
Der Service-/Reklamationsworkflow ruft dieselbe native Terminplanung auf und
kann die Betriebsmittelsperre nicht umgehen. Ein bereits vorhandener Termin
bleibt historisch lesbar, auch wenn später ein Schaden dokumentiert wird. Er
wird nicht still verschoben, gelöscht oder als ausgeführt erklärt. Die ausdrückliche
Stornierung bleibt auch bei einer inzwischen deaktivierten Ressource möglich.

Die Übersicht berücksichtigt aktuelle Buchungen in der nächsten Minute sowie
Zustand, Nachweise und Ausgabe. Die genaue Verfügbarkeitsabfrage verwendet den
gewählten Zeitraum, Mitarbeiter und Projekt und zeigt tatsächliche
Kalenderüberschneidungen. Eine reine Kalenderlücke behauptet keine technische
Einsatzfähigkeit. Bestehende Ressourcen ohne konfigurierte Anforderungen bleiben
als `inspection_knowledge=unconfigured` lesbar und nach bisherigem Kalenderverhalten
planbar; die Software behauptet für sie keine bestandene Prüfung.

## Schnittstelle und unveränderliche Daten

Modul: `business_resource_custody`, Feature: `resource_custody`. Die folgenden
relativen Wege liegen unter `/api/business` lokal und `/api/v1/business` online:

| Weg | Wirkung |
| --- | --- |
| `GET /resource-custody` | Aktuelle kanonische Ressourcen mit Fachzustand |
| `GET /resource-custody/options` | Tatsächliche Ressourcen, sichere Mitarbeiterauswahl, zugängliche Projekte |
| `GET /resource-custody/{id}` | Profil, Anforderungen, Prüfaussagen, Originale, Übergaben samt `effective`, Zustand und `source_sha256` |
| `GET /resource-custody/{id}/history` | Unveränderte Profil-/Anforderungsversionen, Prüfaussagen, Ausgaben, Rückgaben, Korrekturen |
| `GET /resource-custody/{id}/availability` | `start_at`, `end_at`, `timezone`, optional `employee_id`, `project_id` |
| `POST /resource-custody/{id}/files` | Unveränderte Originaldatei; keine Ersetzung gleicher Dateinamen |
| `GET /resource-custody/{id}/files/{file}/original` | Originalbytes mit frischen Berechtigungen |
| `POST /resource-custody/{id}/profile` | Neue vollständige Profilrevision |
| `POST /resource-custody/{id}/requirements` | Neue Anforderung oder nächste Revision einer vorhandenen ID |
| `POST /resource-custody/{id}/inspections` | Tatsächliche Prüfaussage; optional begründete Korrektur der jüngsten |
| `POST /resource-custody/{id}/handoffs` | Ausdrückliche tatsächliche Ausgabe |
| `POST /resource-custody/{id}/returns` | Tatsächliche Rücknahme |
| `POST /resource-custody/{id}/corrections` | Zusätzliche Korrektur einer Ausgabe/Rücknahme mit Originalbeleg |

Alle Fachaktionen verlangen `request_id`, `source_sha256` und
`confirmation=true`; Profil und Anforderung zusätzlich ihre aktuelle `revision`.
Aktionsfelder sind strikt, unbekannte Felder oder Schreibquerys werden abgewiesen.
Der Quellenhash bindet sämtliche Fachversionen/Originalmetadaten, den nativen
Ressourcenstand und aktuelle Kalenderrevisionen. Eine eigene spätere Wirkung
verhindert das Lesen einer bereits angenommenen Originalquittung nicht.

Fachquittungen enthalten `{resource, record}`; `record` ist flach mit
`id`, `resource_id`, `revision`, `sequence`, Autor, Erfassungszeit und den
ursprünglich angenommenen Feldern. Originalupload liefert das Dateiobjekt.
Eine unverändert wiederholte Vorgangs-ID liefert exakt die ursprüngliche
Quittung. Dieselbe ID mit anderen Inhalten wird abgewiesen. Neue Entscheidungen
auf alten Quellenständen haben keine Wirkung. Ein nachweislich nicht angenommener
409-Vorgang erhält `request_resolution=not_accepted`; eine kollidierende bereits
benutzte ID erhält diese Entwarnung nicht.

Korrekturen enthalten `target_kind=handoff|return`, `target_id`, `reason`,
einen verpflichtenden äußeren `evidence_id` und vollständige `values`.
Ausgabewerte: `employee_id`, `project_id`, `issued_at`, `expected_return_at`,
`condition`, `notes`, `evidence_id`. Rückgabewerte: `handoff_id`, `returned_at`,
`received_by_employee_id`, `condition`, `notes`, `evidence_id`. Der innere Beleg
gehört zur fachlichen Bewegung; der äußere belegt die Korrektur selbst.

Originale: 1 Byte bis 2 MiB, höchstens 200 Dateien pro Ressource, PDF/PNG/JPEG/XML.
Der unveränderte Inhalt bleibt mit SHA-256 gespeichert. Die HTTP-Uploadgrenze ist
nur für diesen Uploadweg 2.850.000 Byte; die übrigen Transportgrenzen bleiben
bestehen. Dateien werden als Download ausgeliefert, nicht als ausführbarer Inhalt.

Acht neue Tabellen: `business_resource_profiles`, `business_resource_requirements`,
`business_resource_inspections`, `business_resource_handoffs`,
`business_resource_returns`, `business_resource_corrections`,
`business_resource_evidence`, `business_resource_requests`. Die ersten sieben
enthalten Fachhistorie/Originale, die letzte technische Quittungen. Die bestehenden
Migrationen und Prüfsummen wurden nicht verändert. SQLite und PostgreSQL schützen
Originale vor Änderung/Löschung; PostgreSQL-Runtime-Rechte erlauben nur SELECT/INSERT.
Der Integritätsabgleich prüft Originalhashes, Ressourcen-/Anforderungs-/Rückgabebezüge,
Versionsfolgen, chronologische Übergaben und Quittungen gegen die Originaldatensätze.

## Rechte, Datenschutz und Betriebsgrenzen

Die vollständige Betriebsmittelakte verlangt aktuell globale `planning.read`
und `planning.write`. Projektplaner erhalten im nativen Konfliktweg ausschließlich
sachliche Nutzungsblocker ohne fremde Übergabe-, Prüfer- oder Mitarbeiterdetails.
Neue Betriebsmittelaktionen verlangen ein aktives Planungsmodul. Bereits angenommene
Quittungen bleiben nach dessen Deaktivierung lesbar, aber nur bei weiterhin gültiger
Identität, Instanz, Schema-Schreibzustand und aktuellen globalen Rechten. Offline-
Gerätetoken erhalten keinen Zugriff auf diesen Verwaltungsworkflow.

Der Unternehmens-Exportkatalog enthält die sieben sensiblen Fach-/Originaltabellen
und prüft Originalbytes gegen SHA-256. Technische Requests sind ausgeschlossen.
Personenbezüge in Originaldateien, Prüfernamen, Snapshots und polymorphen Korrekturen
lassen sich nicht allein aus einem Mitarbeiter-FK vollständig erkennen. Der
Datenschutzprozess verlangt weiterhin manuelle Quellen-/Fremdpersonenprüfung;
Betriebsmittelhistorie wird nicht als automatisch vollständig löschbar dargestellt.

Es wurden keine realen Mitarbeiterausgaben, technischen Prüfungen, Termine,
Providerabrufe oder externen Mitteilungen für den Nutzerbetrieb ausgelöst. Die
Abnahmen verwenden isolierte synthetische Ressourcen und Originalbelege.

## Nachweise

| Nachweis | Tatsächliches Ergebnis |
| --- | --- |
| Neue Domainprüfung `test_business_resource_custody.py` | 8/8 bestanden |
| Bestehende native Planning- und Serviceprüfungen gemeinsam mit Betriebsmitteln | 27/27 bestanden in 5,827 s |
| Lokaler echter HTTP-Server `test_business_resource_custody_transport.py` | 2/2 bestanden in 1,501 s |
| Echte PostgreSQL-/MFA-/HTTP-Prüfungen `online/test_business_resource_custody_pg.py` | 2/2 bestanden in 10,521 s; keine Skips |

Domainnachweise umfassen Altressourcen ohne erfundene Prüfung, Kalenderquellen,
Verbindlichkeit/Fristen/Identität, Service-Dispatch, Stornierung nach Deaktivierung,
tatsächliche Ausgabe/Rücknahme, nicht automatisch schließende Erwartungsfrist,
belegte historische Korrekturen ohne spätere Schadenfreigabe, Rollback bei spätem
Fehler, Moduldeaktivierung, aktuelle Rechte und beschädigte Originale.

HTTP prüft genau 2 MiB, bytegleichen Download und identische Wiederholungsquittung,
zu große dekodierte Originale, Transportgrenzen, GET-Inhalte und unbekannte Querys.
PostgreSQL ergänzt zwei parallele identische Ausgaben mit genau einer Fachwirkung,
MFA, aktuellen Rollen-/Offlinezugang, native tatsächliche Kalendernutzung,
Runtime-/Migrator-Unveränderlichkeit sowie vollständiges Backup und Restore in
eine separate Datenbank. Nach Restore sind Originaldatei, alle Fachhistorien und
angenommenen Quittungen identisch; die Quelldatenbank bleibt unverändert.

Logs: `work/verification/resource-custody-domain.log`,
`work/verification/resource-custody-http.log`,
`work/verification/resource-custody-pg.log`. Die getrennten Browser-/Flutter-
Nachweise stehen im oben verlinkten Clientbericht.
