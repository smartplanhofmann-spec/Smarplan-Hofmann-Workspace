# Komponenten und Sicherheitsmeldungen

Stand: 03.11.2026. Dieser Nachweis betrifft festgeschriebene Quellabhängigkeiten.
Er ersetzt weder einen unabhängigen Sicherheitstest noch die Prüfung eines
ausgelieferten Windows-/iOS-/Serverpakets.

## Tatsächlich durchgeführte Prüfung

Der Abgleich gegen veröffentlichte Python-Sicherheitsmeldungen ergab zunächst
43 unterschiedliche Meldungskennungen zu den beiden Paketen `cryptography`
46.0.7 und `Pillow` 12.3.0. Die unterstützten, auf PyPI verfügbaren Versionen
wurden auf `cryptography==50.0.0` und `pillow==13.0.0` angehoben. Die Online-,
lokalen Backend- und Planimport-Lockdateien sowie die offenen
Installationsbedingungen sind aufeinander abgestimmt. Pillow 13 setzt Python
3.11 oder neuer voraus; die geprüfte Umgebung verwendet Python 3.12.

| Prüfung | Ergebnis am Prüftag | Umfang |
| --- | --- | --- |
| pip-audit 2.10.1, PyPI | 0 bekannte Meldungen nach Update | 21 unterschiedliche festgeschriebene Pakete aus Online-Backend und Planimport |
| npm audit | 0 bekannte Meldungen | Browser-Prüfwerkzeuge aus `web/office/package-lock.json`, einschließlich Entwicklungsabhängigkeiten |
| Dart `pub outdated --show-all --json` | 0 betroffene oder zurückgezogene aktuelle Versionen; 0 unbekannte Meldungszustände | 132 Pakete der Flutter-Auflösung |
| CycloneDX-Quellinventar | 153 unterschiedliche Komponenten | Fünf Lockdateien; Flutter-SDK-Pseudopakete ausdrücklich ausgeschlossen |

Die maschinenlesbaren Ergebnisse, verwendeten Lockdatei-Hashes, alten
Meldungskennungen und Umfangsgrenzen stehen in
[source-advisories-2026-11-03.json](evidence/source-advisories-2026-11-03.json).
Das reproduzierbare Verzeichnis liegt in
[product-source-bom.json](evidence/product-source-bom.json). Es wird mit
`python scripts/product-inventory.py --output <Datei>` erzeugt. Die CI prüft,
dass das gespeicherte Verzeichnis genau den Lockdateien entspricht. Dieses
Inventarskript führt selbst keinen Netzabgleich durch.

## Funktionsprüfung der angehobenen Versionen

Die neue Laufzeit wurde getrennt unter `/tmp/smartplan-backend-verified`
installiert. `pip check` besteht; der tatsächlich ausgeführte Planimport
bestand alle 67 Tests einschließlich PDF-Verarbeitung. Der erste breite
Backendlauf führte 850 Tests aus: 848 bestanden, ein Windows-Fall wurde unter
Linux ausgelassen. Ein neuer HTTP-Test brach beim Senden eines bereits anhand
der Kopfzeilen abgewiesenen großen Körpers ab. Die Testanfrage wurde korrigiert;
der gezielte Wiederholungslauf bestand bei unveränderter Transportsperre.
Dieser erste breite Lauf wird deshalb ausdrücklich nicht als vollständig
bestandener Gesamtlauf gewertet. Zusätzlich bestanden alle 95 kaufmännischen Regressionen mit tatsächlichen
E-Rechnungsvalidatoren und lokalen SMTP-Teststrecken. Weitere gemeinsame Prüfergebnisse werden im
[Integrationsstand](CRM_ERP_INTEGRATIONSSTAND_2026-11-03.md) festgehalten.

## Pflege und Reaktion

Vor einer Releasefreigabe werden die Abgleiche erneut ausgeführt und mit Datum,
Quell-Commit, Lockdateien, eingesetzten Werkzeugversionen und tatsächlichen
Auslassungen archiviert. Neue Meldungen werden nach betroffener Funktion und
erreichbarem Code bewertet. Korrigierte Pins erhalten gezielte Funktions- und
Installationsprüfungen; eine Ausnahme benötigt eine begründete, befristete
Entscheidung des benannten Betreibers. Eine unveränderte alte Prüfung gilt
nicht als aktueller Sicherheitsnachweis.

Bei einem bestätigten Vorfall hält der Betreiber Zeitpunkt, betroffene
Instanz/Version, beobachtete Zugriffe und Maßnahmen fest. Betroffene Zugänge
werden gezielt gesperrt und Schlüssel rotiert; laufende Übertragungen bleiben
bei unklarem Ergebnis als unbestätigt erhalten. Beweise werden zugriffsgeschützt
gesichert. Wiederherstellungen müssen die aktuellen unabhängigen
Datenschutz-Checkpoints und Finanzabgleiche bestehen. Nach Behebung folgen
Nachprüfung und eine dokumentierte Betriebsentscheidung. Datenschutzrechtliche
Melde- oder Benachrichtigungspflichten werden am tatsächlichen Vorfall geprüft.
Zuständigkeit und Kontaktweg sind vor Produktivbetrieb noch konkret einzutragen.

Offen bleiben die vollständige Lizenz-/Weitergabebewertung, Betriebssysteme,
Flutter-Engine/SDK, native Bibliotheken, Java und Rechnungsvalidatoren sowie
Herkunft und Sicherheitsprüfung der fertig gebauten Pakete. Der aktuelle
Abgleich findet bekannte veröffentlichte Meldungen; er beweist keine
Schwachstellenfreiheit.
