# Native Kataloghistorie und Originalübernahme

Stand 04.11.2026. Der native CSV-v1-/begrenzte DATANORM-Ablauf ist auf dem
geprüften Anfangssalden-/Source4-Stand `c7dbab0` integriert. Die vollständige
Flutterregression besteht **1.163/1.163 Tests**, die vollständige Analyse meldet
keine Befunde. Backend und Browsercode sind gegenüber `c7dbab0` unverändert;
deren vorhandene Prüfungen wurden für diese reine Clientergänzung nicht erneut
als neuer Gesamtlauf ausgegeben.

Die App verwendet dieselbe serverseitige Vorschau und dieselben unveränderten
Original-/Annahmebelege wie der Browser. Sie bietet Historie und Originaldownload,
prüft Dateihashes und wiederholt unklare Import-/Annahmeaufträge mit ursprünglichen
Werten und Vorgangskennungen. Nur die konkreten großen Katalogantworten dürfen
32 MiB besitzen; andere allgemeine JSON-Antworten behalten ihre 20-MiB-Grenze.
Die tatsächlichen Grenzen einschließlich jeweils eines zusätzlichen Bytes
sind über lokalen HTTP-Transport geprüft.

Zwei echte Navigationsgegenfälle sind behoben: Eine darüber geöffnete
Katalogseite darf nach Austausch der Sitzung nicht an der vorherigen Sitzung
hängen bleiben. Das Entfernen einer alten Route darf außerdem nicht während
Flutter gerade die Ansicht aufbaut stattfinden. Die vorhandenen Öffnungs-,
Rechte-, Hintergrund- und späten Antwortprüfungen bleiben Bestandteil der
vollständigen Regression.

Der ursprüngliche Teilnachweis enthält 45 neue Fälle und 84 gemeinsame
Regressionen. Der integrierte Nachweis bindet die tatsächlich zusammengeführten
Dateihashes und vollständigen Protokolle:
[evidence/catalog-native-integrated-2026-11-04.json](evidence/catalog-native-integrated-2026-11-04.json).
Datierte Preise v2 und weitere Source5-/Anlagenfunktionen werden separat
entwickelt. Es wurden keine produktiven Anbieter oder Geschäftsdaten verwendet.
