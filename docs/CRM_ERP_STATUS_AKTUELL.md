# Aktueller Stand der CRM-/ERP-Entwicklung

Stand: 04.11.2026. Hauptprojekt: `/workspace/Smarplan-Hofmann-Workspace`.
Das [unveränderte Gesamtziel](../CRM_ERP_Gesamtziel.txt) bleibt maßgeblich.
Einzelunternehmen, EÜR, Regelbesteuerung/Ist, SKR04, Nettopreise und reguläre
Beschäftigte/Minijobs sind der vereinbarte Rahmen.

## Bereits vorhandene und abgegrenzt geprüfte Funktionen

- Kunden, Projekte, Angebote, Portalannahme, Aufträge und Projektkosten.
- Einkauf, Teil-/Restlieferung, Lagerbewegungen, Inventur, Geräte und Service.
- Rechnungen einschließlich Abschlags-/Schlussketten, Korrekturen, offene
  Posten, Mahnungen, Teilzahlungen und Erstattungen.
- EÜR-Geldjournal, steuerliche Einordnung, Privat-/Kapitalbewegungen,
  Vorsteuerzeitpunkte, lineare Abschreibung, Gegenbuchung, Periodensperren
  und nachvollziehbares Jahresprüfpaket.
- Original-Bankauszüge, Zahlungsabgleich und belegte Bank-/Kassen-Anfangssalden.
- Personalunterlagen, Zeiten, Abwesenheiten, Reisekosten sowie begrenzte,
  ausdrücklich versionierte Lohnfälle. Dies ist keine vollständige deutsche
  Lohnabrechnung für sämtliche Beschäftigungsfälle.
- Katalogoriginale, Vorschau, bestätigte Übernahme und Historie in Browser/App.
- Projektbezogener Assistent mit Freigaben; Sicherung, Wiederherstellung,
  Rechteprüfungen und Unternehmensübergabe mit eigenen Nachweisen.

Die [Anforderungsmatrix](CRM_ERP_ANFORDERUNGEN.md) und der
[Umsetzungsplan](CRM_ERP_UMSETZUNGSPLAN.md) benennen je Teilumfang die Nachweise.
Technisch geprüfte Entwicklungsfunktionen sind keine vollständige Fach- oder
Betriebsfreigabe.

## Laufende Integration und Entwicklung

1. Source5-Lohnabläufe verbinden einen vollständigen ursprünglichen Bonus
   mit getrennten tatsächlichen Zahlungstagen, erhalten bereits bezahlte
   laufende Lohnteile und liefern reduzierte eigene Mitarbeiterbelege.
   Versions- und private Dialogfehler wurden unabhängig reproduziert und
   korrigiert. Die [gemeinsame Regression](CRM_ERP_SOURCE5_GESAMTPRUEFUNG_2026-11-04.md)
   ist abgeschlossen: 1.626 Backend-, 555 Browser- und 1.208 Appfälle bestanden;
   ein Windows-spezifischer Backendfall wurde unter Linux ausgelassen.
2. Historische lineare Anlagen übernehmen belegte Anschaffungswerte, bisherige
   AfA und Restbuchwerte. Beide Clients, EÜR und Wiederherstellung sind
   [gemeinsam geprüft](CRM_ERP_ANLAGEN_GESAMTPRUEFUNG_2026-11-04.md):
   1.674 Backendfälle bei einem Windows-Skip, 578 Browser- und 1.225 Appfälle,
   107 PostgreSQL-Fälle und ein zusätzlicher gemeinsamer Restore bestanden.
3. Katalogpreise erhalten Gültigkeitszeiträume, Einkaufs-/Verkaufsrollen und
   exakte Preisbasen. Alte Angebote bleiben an ihrer ursprünglichen Fassung.
   Beide Clients, Beleg-/Bestellverbraucher und die Korrektur doppelt gezählter
   Assistentenkosten sind [gemeinsam geprüft](CRM_ERP_KATALOG_V2_GESAMTPRUEFUNG_2026-11-04.md):
   1.737 Backendfälle bei einem Windows-Skip, 1.312 App- und 610 Browsermodulfälle
   sowie vier echte PostgreSQL- und vier Browserabläufe bestanden.
4. Unternehmensweite Ereignisregeln werden zusätzlich zur vorhandenen
   projektbezogenen Planautomatik implementiert.
5. Historische offene Kunden-/Lieferantenposten erhalten einen eigenen
   belegten Zahlungsweg zu EÜR, Bankabgleich und Liquidität. Backend, HTTP,
   PostgreSQL und unabhängiger Fachreview sind separat geprüft; beide Clients
   und die gemeinsame Integration sind in Arbeit.
6. Eine getrennte SV-Gruppenkorrekturgrundlage befindet sich im unabhängigen
   Review. Die tatsächliche Berechnung mehrerer Bonus-Steuergruppen bleibt
   gesperrt; diese Grundlage berechnet noch keine freigegebenen Nettobeträge.
7. Belegte laufende Jahreswerte vor einem unterjährigen Softwarebeginn und
   ein auf ein Jahr begrenztes Original-/Journalpaket sind die nächsten
   konkret am Code nachgewiesenen Buchhaltungsaufgaben.

## Noch offene Buchhaltungs- und Gesamtanforderungen

Weitere Steuerfälle, historische offene Posten, geeignete Steuerberater-/DATEV-
und Behördenwege sowie die vollständige fachliche Buchhaltungsprüfung bleiben
offen. Ein automatischer Bankabruf benötigt zusätzlich einen ausgewählten
Anbieter und dessen echten Vertrag. Weitere Lohn-/Korrektur-/Versicherungsfälle,
Meldeverfahren, durchgängige Gesamtabnahmen A–G und reale Windows-/iPhone-
Betriebsnachweise sind weiterhin erforderlich.

Die genannte Schätzung von zwei bis vier Stunden bezog sich auf die damals
laufenden Erweiterungen und deren Integration. Sie ist weder ein belastbarer
Endtermin noch eine Zusage für die vollständige Buchhaltung oder Software.
Aus Testzahlen wird kein Fertigstellungsprozentsatz abgeleitet.
