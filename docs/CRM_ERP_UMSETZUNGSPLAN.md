# CRM/ERP – Umsetzungsplan

Stand: 02.11.2026. Maßgeblich ist die unveränderte `../CRM_ERP_Gesamtziel.txt`.
Das Endziel bleibt vollständig bestehen. Dieser Plan trennt überprüfbare
Entwicklungsabschnitte von Produktivfreigaben und extern erforderlichen Nachweisen.

## Ausgangspunkt und Erhalt vorhandener Arbeit

Das Hauptrepository ist `/workspace/Smarplan-Hofmann-Workspace`. Der zunächst
ausgecheckte Stand `822fe58` enthielt die Projektbasis. In vorhandenen lokalen
Entwicklungszweigen lagen bereits umfangreiche Business-Erweiterungen. Der
Hauptbranch wurde ohne Konflikte per Fast-forward auf `420c4c7` gebracht;
die vier anderen Arbeitskopien bleiben bestehen. Es gab keinen Remote-Push,
keine Bereitstellung und keine Änderung produktiver Datenbanken.

Weiterverwendet werden Flutter für Windows/iPhone, der Python-Domänenkern,
PostgreSQL für den Onlinedienst und die bestehende Browseroberfläche unter
`web/office`. SQLite bleibt lokale Variante mit ausdrücklich begrenzten
Finanzfunktionen. Ein Neubau würde vorhandene geprüfte Regeln und Datenpfade
unnötig ersetzen. Die aktuelle Bewertung steht in
[Bestandsaufnahme](CRM_ERP_BESTANDSAUFNAHME.md); einzelne Anforderungen und
Abnahmen A–G werden in [Anforderungen](CRM_ERP_ANFORDERUNGEN.md) nachverfolgt.

## Reihenfolge und überprüfbare Ergebnisse

| Abschnitt | Ergebnis und Prüfung | Status |
| --- | --- | --- |
| 0. Bestand konsolidieren | Vorhandene Business-Suite integrieren; Backend-, Browser- und App-Prüfungen erneut ausführen; historische Aussagen kennzeichnen | umgesetzt und geprüft; ursprüngliche Browserblockade im zweiten Abschnitt behoben, 8 echte Browserabläufe bestanden |
| 1. Unternehmensgrundlage und Dokumenterhalt | Bedarf erfassen; manuell korrigierbare Modulvorschläge; Sichtbarkeit, Aktivierung und Rechte trennen; feste Unternehmensinstanz an Datenbank/Ablage binden; signierte Protokolle gegen beschädigte Inhalte und verlorene Antworten absichern | implementiert und mit den im Fortschrittsbericht genannten Prüfungen getestet; vollständige Infrastrukturtrennung bleibt offen |
| 2. Anfrage bis Zahlung vervollständigen | Vorhandene Angebote/Kalkulation/Zeiten/Kosten/Rechnungen verbinden; Kundenportal mit enger Freigabe und nachvollziehbarer Annahme; durchgängige Abnahme B mit Wiederholung/Neustart/Rechteentzug | erster [Angebotsportalabschnitt](CRM_ERP_PORTAL.md) implementiert; vollständige Abnahme B weiter offen |
| 3. Einkauf bis Service | Bestellungen mit Teil-/Restwareneingängen, Lagerbewegungen und Projektkosten verbinden; Katalogimporte mit Vorschau/Einheiten/Fehlerbericht; Service- und Betriebsmittelhistorie, Abnahme C | lokaler Bestell-/Liefer-/Kostenablauf implementiert; [Umfang und Grenzen](CRM_ERP_EINKAUF.md); tatsächliche Bestellauslösung, Originalbeleg- und strukturierte Gerätebindung weiter offen |
| 4. Buchführung | Erste vollständige Version für Einzelunternehmen mit EÜR: reproduzierbares Journal, Zahlungs-/Steuerzuordnung, Perioden/Korrekturen und Steuerberaterexport; weitere Buchführungsfälle separat | offen; bestätigter Umfang und konkreter [EÜR-Journalplan E1a–E1d](CRM_ERP_EUER_PLAN.md) vorbereitet |
| 5. Personal und Lohn | Erste deutsche Lohnabrechnung für reguläre Mitarbeiter und Minijobs: vorhandene Mitarbeiter/Zeiten/Abwesenheiten ergänzen, Reisekosten, geprüfte Abrechnungsfälle/Korrekturen und Meldungen nach tatsächlichen Zugangs-/Prüfvorgaben, Abnahme D | offen; Beschäftigungsumfang vom Nutzer am 02.11.2026 festgelegt |
| 6. KI und Regeln | Berechtigungsgebundene Datenwerkzeuge, belegbare Antworten, Freigaben, Wiederholschutz, Unternehmensisolation und Schutz gegen Dokumentanweisungen; Chat/Sprachbedienung, Abnahme E | offen |
| 7. Betrieb und Clients | Browser-/Windows-/iPhone-Abläufe zusammenführen, Offline-Berichte und Konfliktfälle, Installation/Updates/Backup/Restore, Kundenexport/-ausstieg, Abnahmen F/G | offen |
| 8. Produktfreigabe | Unabhängige Sicherheitsprüfung und Nachprüfung; fachliche/rechtliche Nachweise; echte Installationen und autorisierte Anbieterabnahmen; Nachweisliste schließen | extern erforderliche Nachweise offen |

Nach Abschnitt 1 wurde die lokale Lieferkettenlücke aus Abschnitt 3 bearbeitet.
Die ergänzende preisfreie Artikelwahl schließt den Einstieg für reine Lagerrollen.
Danach wurde der erste [Angebotsportalabschnitt](CRM_ERP_PORTAL.md) aus
Abschnitt 2 entwickelt: eigene Kundensitzung, ausdrückliche Erklärung und
gesonderte interne Übernahme. Er verwendet das vorhandene Projekt-/Belegmodell
und ersetzt noch nicht die gesamte Abnahme B. Allgemeiner Dateiaustausch,
Projektfreigaben und Projektanlage nach Annahme bleiben weitere Arbeit.
Der nächste unabhängige Finanzabschnitt ist E1a des
[EÜR-Plans](CRM_ERP_EUER_PLAN.md): Quellen und tatsächlich bestätigte
EUR-Geldflüsse mit sichtbaren Klärungsfällen. Der noch offene Umsatzsteuerstatus
wird nicht aus der EÜR-Auswahl abgeleitet.

Abschnitt 1 verwendet zunächst einen eigenen Prozess, Datenbankzugang,
Dateibestand, Geheimnissatz, Datenschutz-Checkpoint und Worker je Unternehmen.
Ein frei wählbarer Unternehmensparameter im Request schafft keine Isolation.
Gemeinsamer Quellcode und automatisierbare Bereitstellung erlauben trotzdem
einen Onlinedienst für mehrere Unternehmen. Ein gemeinsames Datenbankschema mit
Zeilenmandanten wird erst bei einem begründeten Bedarf separat bewertet.

## Entwicklung und Migration

- Neue Tabellen werden additiv und nachvollziehbar migriert. Die vorhandenen
  Schema-7-Moduldefinitionen sind über Checksummen festgeschrieben; sie werden
  nicht still verändert. PostgreSQL-HTTP-Start führt keine Migration aus.
- Signierte Dokumente, bestehende Geschäftsvorfälle, Originaldaten und lokale
  Warteschlangen werden erhalten. Sichtbarkeit eines Moduls löscht keine Daten.
- Tests verwenden synthetische Daten, entbehrliche Datenbanken und lokale
  Dienste. Bestehende Anbieter- oder Betriebszugänge werden nicht als Erlaubnis
  für Nachrichten, Zahlungen, Meldungen oder Migrationen verwendet.
- Jeder Abschnitt erhält gezielte Fach-/Integrations-/Fehlerfalltests.
  Ein grüner Teiltest belegt nur seinen ausdrücklich beschriebenen Umfang.
- Fortschritt, konkrete Testbefehle, Ergebnisse und Einschränkungen stehen in
  [Fortschritt und Tests](CRM_ERP_FORTSCHRITT.md).

## Entscheidungen und externe Abhängigkeiten

Der Nutzer hat am 02.11.2026 die erste vollständige Version auf
**Einzelunternehmen mit EÜR** und die erste deutsche Lohnabrechnung auf
**reguläre Mitarbeiter und Minijobs** festgelegt. Das ist die verbindliche
Priorität für die Fachumsetzung. Umsatzsteuerfälle, Sonderfälle der Beschäftigung,
Abrechnungsjahr, fachliche Referenzen und Meldewege werden innerhalb dieses
Umfangs konkretisiert. Eine doppelte Buchführung oder weitere Rechtsformen
werden dadurch nicht als bereits umgesetzt oder geprüft behandelt.

Endgültiger Produktname, Lieferanten/Katalogformate, erste Bank-/Kommunikations-
anbieter, KI-Anbieter, Hosting und Verkaufspreise sind gemäß Ziel noch offen.
Die technische Basis kann unabhängig davon wachsen.
Produktive Anbieteraufrufe, Signierung/Installation auf Windows und iPhone,
Behördenfreigaben sowie unabhängige Sicherheits- und Fachprüfungen benötigen
reale Zugänge beziehungsweise zuständige Personen. Simulationen ersetzen diese
Nachweise nicht. Der Nutzer hat bisher nur ein digital unterschreibbares
Protokoll selbst getestet; alte Repository-Behauptungen erweitern diese Abnahme
nicht.
