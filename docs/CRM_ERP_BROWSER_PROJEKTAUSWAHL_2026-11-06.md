# Projektauswahl passend zum Browserbereich

Der Nutzer meldet die bisher in jeder Kategorie sichtbare Projektauswahl als
unverständlich und beauftragt die Anpassung. Die allgemeine Übersicht soll
den Betrieb zeigen; ein unsichtbarer Projektkontext darf weder Vorbelegungen
noch effektive Rechte in allgemeinen Bereichen beeinflussen.

| Browserbereich | Neue Anzeige und Bedeutung |
| --- | --- |
| Übersicht | Betriebsübersicht über die für den Zugang freigegebenen Projekte; kein Projekt-Dropdown. Kennzahlen und Feed werden ohne Projektfilter geladen. |
| Anfragen, Kontakte, Personal, Einstellungen | Kein Projekt-Dropdown. Der bisherige Projektkontext wird beim Öffnen entfernt. |
| Projekte | Auswahl **Projekt öffnen** mit **Projektübersicht** für die Projektliste. Eine gewählte Projektmappe bleibt ausdrücklich erkennbar. |
| Einsatzplanung, Dokumente, Material, Finanzen, Assistent, Kundenservice | Sichtbarer **Projektfilter** mit **Alle Projekte** oder einem konkreten Projekt. Ein Wechsel zwischen diesen Bereichen erhält den gewählten Filter. |

Nach einem Wechsel in einen allgemeinen Bereich öffnet Projekte wieder die
Projektliste. Die Zeiterfassung unter Personal verlangt im Stempeldialog eine
ausdrückliche Projektwahl. Ein zuvor in Dokumenten geöffnetes Projekt wird
dort nicht heimlich vorbelegt. Vorhandene Zeiteinträge und deren Projektbezug
werden nicht verändert.

Die Hauptnavigation berücksichtigt für allgemeine Bereiche globale Rechte,
für projektbezogene Bereiche weiterhin die effektiven Projektrechte. Auch
ausgeblendete Fachbereiche behalten diese Unterscheidung. Eine projektspezifische
Sperre der eigenen Zeit blendet den allgemeinen Bereich Personal nicht aus;
die tatsächlich für dieses Projekt gesperrte Buchung wird vom Server weiterhin
abgelehnt. Serverseitige Autorisierung, API-Verträge und Datenbank bleiben
unverändert.

Beim Bereichs-/Projektwechsel wird der gemeinsame Kopf auch dann erneuert,
wenn die Berechtigungsnamen gleich bleiben. Der Ladehinweis bleibt bis zur
fertigen Ansicht erhalten. Späte Antworten für die vorige Projektmappe dürfen
keinen bereits verlassenen Projektkontext wiederherstellen. Die bisherige
Anweisung in der Betriebsübersicht, oben ein Projekt zu wählen, ist entfernt.

## Prüfung und Vorschau

Der tatsächliche Chromium-Ablauf verwendet temporäre SQLite-Testdaten,
echte HTTP-/MFA-Anmeldung und aktive Namespace-/PID-/Netzwerk-/Seccomp-Sandbox.
Er prüft alle allgemeinen Bereiche, Projekt-/Filterbeschriftung, gefilterte
Fachansichten, die Rückkehr zur Projektliste, leere Projektvorbelegung beim
Stempeln, verzögerte Projektantworten, Mitarbeiterrechte und eine vom Server
abgelehnte gesperrte Projektbuchung. Die 390-Pixel-Ansicht hat keinen
horizontalen Überlauf; Screenshots werden nach Ende der Menüanimation erzeugt.

- [Dokumente mit Projektfilter, mobil](evidence/project-context-2026-11-06/screenshots/project-filter-mobile.png)
- [Personal ohne Projektfilter, mobil](evidence/project-context-2026-11-06/screenshots/personnel-company-mobile.png)
- [Vorherige Übersicht mit allgemeinem Dropdown](evidence/project-context-2026-11-06/before/before-overview-global-picker.png)
- [Prüfnachweis](evidence/project-context-2026-11-06/verification.json)

Die neue Regression ist im Browser-CI als eigener Workflow project-context
eingetragen. Bestehende Browserabläufe wählen Projekte jetzt über eine
tatsächlich projektbezogene Ansicht statt über das alte globale Dropdown.
Die Unternehmensübersicht wird nach einem vorher geöffneten Projekt erneut
als allgemeine Übersicht geprüft. Bestehende API-Tests für optionale
projektbezogene Kennzahlen bleiben unverändert.

## Auslieferungsstand

Die Produktänderung betrifft ausschließlich office.js und office.css.
Backend, Datenbankschema und Windows-/iPhone-App werden nicht geändert.
Der zuletzt tatsächlich bestätigte Serverstand ist weiterhin A93. Die neue
Browseransicht benötigt die koordinierte Aktualisierung dieses Servers;
Quelländerung und lokale Tests sind noch kein Nachweis dieser Installation.
Ein neuer signierter iPhone-Build oder eine neue native Geräteabnahme wird
hiermit nicht behauptet.
