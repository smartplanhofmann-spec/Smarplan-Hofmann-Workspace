# Zeitabrechnung: gemeinsamer PostgreSQL-Browsernachlauf

Am 09.11.2026 wurde der unveränderte gemeinsame Integrationsstand
`487977a94d15f16a387a8995d51dcdcd44d86e9e` in
`/workspace/smartplan-minijob-integration-20261109` geprüft. Er enthält
Zeitabrechnung, V10 und V11 einschließlich der additiv zusammengeführten
Browser-Einstiegspunkte. Dieser Nachweis ändert keinen Produkt- oder Testcode.

Der bestehende Browserablauf `document-time-billing` besteht auf einer neuen,
leeren lokalen PostgreSQL-Datenbank vollständig mit Exitcode 0. Verwendet
wurden die produktive Runtime-Rolle, Instanz-/Speicherbindung, MFA und aktive
Chromium-Sandbox. Es wurde keine SQLite-Ausstellungssperre aufgehoben.

Der Ablauf prüft unter anderem:

- Teilmengenauswahl freigegebener Zeiten, sieben Sekunden als exakte
  Preisbasis 3600 sowie freie und katalogbasierte Positionen.
- Erhalt vorhandener Quellen bei nachträglicher Ergänzung.
- Verlorene Annahmeantwort, zwischenzeitlichen Rechteentzug und identischen
  Originalretry nach Wiederfreigabe.
- Tatsächliche Festschreibung einer Rechnung mit zwei Zeitbindungen und
  Abweisung einer zweiten Abrechnung derselben Quelle.
- Quellenänderung vor dem letzten Abruf sowie während der Annahme mit
  sichtbarem Prüfhinweis statt unauflösbarer Pending-Antwort.
- Verspätete Antworten nach Projekt- und Dialogwechsel sowie 390px-Darstellung.

Eine zusätzliche unabhängige Datenbankabfrage bestätigt die echte
`smartplan-online`-Rolle und Runtime-Sicherheit, die finale Rechnung,
beide Originalzeitbindungen, den passenden Archiv-PDF-Hash sowie die
Zeit- und Belegintegritätsprüfer. Der konkurrierende Entwurf bleibt ein Entwurf.

Die unabhängige Integrationssicht fand keinen verlorenen Zeitpfad. Das
Zeitmodul, seine 14 Modultests, der Browserablauf und die PG-Fixture sind
bytegleich zur vorangegangenen geprüften Lieferung. Die Unterschiede im
gemeinsamen Browser-Einstieg sind additive V10/V11-Funktionen.

HEAD und alle sieben vor und nach dem Lauf erfassten Quell-/Testdateihashes
blieben unverändert. Die zuerst zusätzlich verlangte vollständig leere
Git-Statusausgabe war am Ende wegen des parallel durch den Hauptagenten
angelegten Verzeichnisses `docs/evidence/final-assembly-2026-11-09/` nicht
mehr leer. Dieses Verzeichnis wurde von dieser Prüfung weder angelegt noch
verändert; es betrifft keine der geprüften Quell-/Testdateien.

Rohlog, tatsächliche Browserantworten, Screenshot, Quellvergleiche,
Integrationsreview und Datenbankprüfung stehen im
[Nachweisverzeichnis](evidence/browser-time-integration-2026-11-09/).
Das [Manifest](evidence/browser-time-integration-2026-11-09/manifest.json)
enthält Datei- und ursprüngliche Loghashes.

Der eigene kurzlebige Container `smartplan-time-integration-pg-20261109`
wurde nach Sicherung der Ergebnisse entfernt. Es gab keine Veröffentlichung,
Kundenserveränderung oder neue Featureentwicklung. Der frühere Einzel- und
Fehlernachweis bleibt im
[Zeitabrechnungsbericht](CRM_ERP_ZEITABRECHNUNG_BROWSER_2026.md) erhalten.
