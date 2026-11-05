# Projektbetrieb: aktueller Fertigstellungsumfang

Stand: 05.11.2026. Historischer Ausgangspunkt ist `c875ea5` im Hauptprojekt
`/workspace/Smarplan-Hofmann-Workspace`. Die letzte Nutzerentscheidung ersetzt
die bisherige Reihenfolge: **zuerst den Projektbetrieb einschließlich Angeboten,
Rechnungen und Zeiterfassung in Browser, mobiler App und Windows-App abschließen;
Lohnabrechnung und Buchhaltung zurückstellen.** Das ursprüngliche
[Gesamtziel](../CRM_ERP_Gesamtziel.txt) bleibt bytegleich erhalten.

Die mobile Auslieferung folgt dem vorhandenen iPhone-/TestFlight-Weg. Ein neuer
Androidumfang wurde nicht vereinbart. Rechnungen einschließlich Preisen, Steuern, Nummerierung, Original-PDF, Korrekturen und projektbezogenen offenen
Zahlungen gehören ausdrücklich zu dieser Phase. EÜR, steuerlicher Abschluss,
Bankautomatisierung und neue Lohnfälle werden nicht weiter vorgezogen.
Vorhandene Daten und Funktionen bleiben erhalten; Zurückstellen löscht und
deaktiviert keine Bestände.

## Prüfkette und Abschlusskriterien

| Schritt | Erwartetes Ergebnis | Nachweis für den Abschluss |
| --- | --- | --- |
| Kunde und Projekt | Bestehenden Kunden eindeutig übernehmen; Rechnungsadresse und kanonische Projektkennung erhalten | Bedienablauf mit bestehendem Kunden, Adressprüfung, keine Dublette |
| Angebot und Auftrag | Positionen, Preise und Versionen bearbeiten; Angebot annehmen; Auftrag im selben Projekt weiterführen | Browser- und Appablauf mit Originalen und unverändertem Projektbezug |
| Projektdurchführung | Aufgaben, Termine, Pläne, Fotos, Material und unterschriebene Berichte erreichbar und projektgebunden | Reale Clientbedienung, Rechteprüfung, gespeicherte Originale wieder öffnen |
| Arbeitszeit | Start/Pause/Fortsetzen/Stoppen, manuelle Zeit, Projektzuordnung, Freigabe und begründete Korrektur | Browser und App; App zusätzlich offline, Neustart und einmalige Synchronisation |
| Rechnung | Entwurf aus Projekt/Leistungen, vollständige Empfängeranschrift, tatsächliche Ausstellung und abrufbares Original | Autoritativer PostgreSQL-Dienst und echte Ausstellungsquittung; vorarchivierte Testrechnung genügt nicht |
| Navigation und Rollen | Alle erlaubten Projektregister öffnen; sichere Rückkehr; Modulwechsel ohne falsches Register oder Datenverlust | Gezielte Widget-/Browserprüfungen, anschließend Gerätebedienung |
| Bereitstellung | Browser, Windows-Programm und iPhone-Build verwenden denselben kompatiblen Serverstand | Eindeutige Buildversion und Quellstand, Start/Login, gemeinsames Testprojekt und Geräteprüfung |

Die Browseroberfläche ist online zu prüfen. Die native App besitzt die
Offline-Warteschlange; eine gleichwertige Browser-Offlinesynchronisation wird
nicht aus der Appfunktion abgeleitet. Ein Windows-Quell-/Support-ZIP ersetzt
kein startbares Windows-Programm. Ein Simulator oder ein unsignierter iOS-Build
ersetzt keine installierbare iPhone-App.

## Zu Beginn bestätigte Lücken und ihre Bearbeitung

1. **Projekt- und Belegkette:** Browser-Projektanlage übernimmt vorhandene
   Kunden bisher nur über Freitext und kann dadurch eine Dublette ohne Adresse
   erzeugen. Strukturierte Rechnungsanschriften sind im Browserkontaktformular
   zu ergänzen. Die API- und Appfunktionen werden dabei wiederverwendet.
2. **Stunden:** In der App kann die gemischte Server-/Offline-Ereigniskette
   unvollständig angezeigt werden. Die vorhandene serverseitige Korrektur
   freigegebener Zeiten ist in beiden Clients zugänglich zu machen. Rechte für
   Export und Korrektur müssen mit dem Server übereinstimmen.
3. **Projektnavigation:** Fachregister außerhalb der sieben Grundregister
   können auf einen ungültigen Index zugreifen. Stabile Registerkennungen,
   Modulwechsel und Rückkehr aus der weiteren Verwaltung werden geprüft und
   korrigiert; ungespeicherte Planänderungen bleiben geschützt.
4. **Auslieferung:** Der aktuelle lokale Stand ist noch nicht auf GitHub.
   Vorhandene ältere Windows-/iPhone-Builds belegen keine aktuelle
   Auslieferung. Parallele Navigationskorrekturen aus PR 7/8 werden mit dem
   heutigen Code abgeglichen; danach folgt ein eindeutig versionierter Build.

Diese Liste ist ein aktueller Arbeitsstand, keine Erklärung, dass alle übrigen
Anforderungen bereits abgenommen sind. Der frühere Orientierungswert von rund
65 % zählt ungewichtete Zeilen des Gesamtziels und ist weder der Fortschritt
dieser Phase noch ein Zeitversprechen. Der gewünschte Kundentest am 05.11.2026
bleibt ein Ziel; die vollständige Fertigstellung wird nicht ungeprüft zugesagt.

## Aktueller Abschluss des Quellblocks

Die genannten Korrekturen sind im [gemeinsamen Stand 0.13.0](CRM_ERP_PROJEKTBETRIEB_INTEGRATION_2026-11-04.md)
integriert und mit abgegrenzten gemeinsamen Läufen nachgeprüft. Windows 0.13.0
ist tatsächlich gebaut und als Online-Programm verfügbar; auch der unsignierte
iPhone-Gerätebuild 167 ist erfolgreich. Die [Buildnachweise](CRM_ERP_PROJEKT_BUILD_FREIGABE_2026-11-04.md)
trennen diese Erfolge vom noch offenen signierten iPhone-Paket, dem
Serverabgleich und der realen Gerätebedienung. Die [abschließenden lokalen Nachprüfungen](CRM_ERP_PROJEKT_CI_NACHPRUEFUNG_2026-11-04.md)
sind abgeschlossen; die erneute Remote-CI auf a93cb4d läuft separat.

## Zurückgestellte Arbeit erhalten

Die vorbereiteten privaten Lohnvergleichs-/SV-/Quellenpakete bleiben im
isolierten Worktree
`/workspace/smartplan-payroll-foundations-integration-20261104` erhalten.
Sie werden für diese Projektphase nicht in Main integriert. Die zuletzt dort
bestandenen 39 SV-Fälle, 13 Gegenprüfungen und 16 Paketprüfungen sind getrennte,
teilweise überlappende Nachweise. Ein gemeinsamer vollständiger Prüflauf oder
eine Freigabe zur Lohnabrechnung wird daraus nicht behauptet.

## Nachweisführung

Jeder abgeschlossene Abschnitt hält konkrete Änderungen, ausgeführte Tests,
Quellstand und verbleibende Grenzen im Repository fest. Historische Prüfungen
werden nicht als neue Läufe ausgegeben. Zusammenführung erst nach Prüfung der
überlappenden Änderungen; anschließend passende gemeinsame Regressionen.
Geräte- und Serverauslieferung werden getrennt vom lokalen Quellabschluss
bewertet. Echte Kunden-, Steuer- oder Zahlungsdaten werden nicht als Testdaten
erzeugt.
