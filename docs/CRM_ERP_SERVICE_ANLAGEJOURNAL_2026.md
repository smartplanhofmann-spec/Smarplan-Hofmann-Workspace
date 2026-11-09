# Dauerhafter Auftrag für manuelle Servicefallanlage

## Konkrete Lücke und Grenze

Nach einem angenommenen `POST /api/v1/business/service/cases` mit verlorener Antwort konnte eine vollständig neu angelegte App-Sitzung bisher eine neue `request_id` vergeben. Derselbe manuelle Fall entstand dadurch zweimal. Der ursprüngliche Gegenbeweis stammt aus `/tmp/service_restart_duplicate_probe_test.dart` und dem unveränderten Laufprotokoll vom 09.11.2026.

Der neue Clientpfad betrifft ausschließlich `service-case-new`, `/service/cases`, `revision: 0`, ohne `id` und ohne `inquiry_id`, `defect_id` oder `visit_id`. Bearbeitungen, Statuswechsel, Disposition und aus Eingängen abgeleitete Fälle behalten ihre bisherigen Verträge. Es gibt keine neue Backendroute und keine Servermigration.

## Speicherung und Wiederaufnahme

Vor dem ersten POST wird der vollständige bestehende JSON-Befehl einschließlich seiner zufälligen `request_id` unverändert in einem separaten AES-GCM-Vault gesichert. Die 16 vorhandenen Felder werden weder aus heutigen Stammdaten rekonstruiert noch bei einer Wiederholung aktualisiert. Eingaben werden vor dem ersten asynchronen Schritt vom aufrufenden Formular getrennt.

Das Journal verwendet den eigenen Namensraum `service-creation-journal-v1`, Serveradresse, API-Version und Konto. Seine verschlüsselte Hülle enthält `schema_version: 1`, `scope` und `pending`. `scope` umfasst Server, Version, Konto und Firmeninstanz; `pending` ist entweder der vollständige Originalbefehl oder `null`. Die Instanzkennung kommt aus dem vorhandenen authentifizierten `project_creation_scope`, dessen Format strikt geprüft wird. Ohne bestätigte Firmenbindung wird nur die neue manuelle Anlage gesperrt. Es werden keine alten ungebundenen Speicher übernommen.

Eine noch offene Anlage der Firma A verhindert die Wiederverwendung desselben Journals unter Firma B. Private Inhalte werden dabei nicht angezeigt und Dateien beziehungsweise Schlüssel nicht entfernt. Andere Konten haben getrennte Schlüssel. Beschädigte, unbekannte oder gleichzeitig geänderte Speicherstände werden gesperrt; ein beschädigter letzter Stand führt nicht zum Rückgriff auf ältere Befehle.

Das Öffnen und Senden verlangt eine aktuelle Onlineanmeldung, frische Capabilities und `/api/me`, die unveränderte Firmen-/Kontobindung und heutige Service-, Kontakt- und gegebenenfalls Projektrechte. Auch nach jedem asynchronen Schritt werden Sitzung und Aufrufkontext geprüft. Ein Neustart sendet nichts automatisch. Erst „Servicefall anlegen“ öffnet einen vorhandenen Auftrag; „Erneut senden“ wiederholt genau diesen Befehl. Der Server prüft weiterhin seine aktuellen Quell- und Schreibrechte.

## Abschluss und unklare Antworten

Vor dem dauerhaften Abschluss müssen die Antwort die ursprüngliche Revision 1, manuelle Herkunft, anlegendes Konto, Zeitangaben, Quellenhash und sämtliche ursprünglichen Fachfelder bestätigen. Für Titel und Beschreibung wird ausschließlich die dokumentierte serverseitige `str.strip()`-Darstellung verglichen; der gespeicherte Befehl bleibt unverändert.

Netzwerkverlust, 5xx, 429, Rechteentzug, Lesemodus, unbekannte 409-Antworten und unpassende Erfolgsantworten behalten den Auftrag. Nur ein direkt vom POST zurückgegebener Fehler `409` mit `request_resolution: not_accepted` darf ihn als nachweislich nicht angenommen abschließen. Ein späterer lokaler Validator darf diesen Nachweis nicht ersetzen. Auch ein Fehler beim lokalen Abschluss hält den ursprünglichen Befehl für die sichere Wiederholung bereit.

## Gezielte Abnahme

Die Journaltests verwenden tatsächliche verschlüsselte Dateien und den echten Vault-Versionsvergleich. Die HTTP-Abnahme startet den unveränderten Produktserver mit zwei getrennt gebundenen synthetischen Firmen und gleichen kopierten Konto-/Projektkennungen. Sie prüft App-Neuerstellung, explizite Wiederholung bei 390 Pixeln, genau einen Fall/eine Anfangsversion/ein Erstellungsereignis, identische Request-ID, falsche Firma, entzogene Projektzuordnung, Lesemodus, späte Abmeldung, unpassende Quittung und lokale Schreibfehler. Die Ergebnisprotokolle und Grenzen werden unter `docs/evidence/service-creation-journal-2026-11-09/` festgehalten.

Der tatsächliche wiederhergestellte Dialog hat zwei vorhandene UI-Fehler aufgedeckt: Die Servicefilter konnten bei 390 Pixeln überlaufen; sie verwenden nun die verfügbare Breite. Außerdem ergänzte der gemeinsame Formulardialog eine zweite leere Auswahl, obwohl das Servicefeld bereits eine eigene anbot. Die Ergänzung erfolgt jetzt nur, wenn noch keine leere Auswahl existiert. Ein eigener Widgettest prüft beide Varianten und die weiterhin funktionierende Auswahl. Weitere Formularregeln ändern sich nicht.

Die Serverinstallation und die Abnahme auf einem echten Windows-/Mobilgerät bleiben separate Schritte. Das Journal macht keine automatische Zahlung, Nachricht, Rechnung oder Disposition.
