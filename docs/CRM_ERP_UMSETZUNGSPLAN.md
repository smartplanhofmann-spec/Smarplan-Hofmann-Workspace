# CRM/ERP – laufender Umsetzungsplan

Stand: 03.11.2026. Maßgeblich bleiben das unveränderte
[Gesamtziel](../CRM_ERP_Gesamtziel.txt) und die
[Anforderungsmatrix](CRM_ERP_ANFORDERUNGEN.md). Projekt:
`/workspace/Smarplan-Hofmann-Workspace`, Branch `work`.

## Verbindlicher fachlicher Rahmen

Einzelunternehmen mit EÜR, Regelbesteuerung, Ist-Versteuerung, 19 %
Standard-Umsatzsteuer, SKR04 und Nettopreise. Personalumfang: reguläre
Beschäftigte und Minijobs. Gültigkeitsbeginn, echte Personen-/Steuerdaten und
Anfangsbestände bleiben ausdrückliche Eingaben. Einzelne geprüfte Lohnfälle
ersetzen keine vollständige Fachabnahme aller Beschäftigungsfälle.

Vorhandene Flutter-/Browseroberflächen, Python-Kern, PostgreSQL-Onlinedienst
und begrenzte lokale SQLite-Variante werden weiterentwickelt. Kanonische
Kunden-/Projektkennungen, unterschriebene Archive, Quittungen und bestehende
Daten bleiben erhalten. Die ursprüngliche Bestandsaufnahme und früheren
Entwicklungsschritte stehen im Fortschrittsbericht, nicht als aktuelle
Restarbeiten in diesem Plan.

## Bereits belegte Entwicklungsabschnitte

| Abschnitt | Abgegrenztes Ergebnis | Aktueller Nachweis |
| --- | --- | --- |
| Bestand/Unternehmensgrundlage | Vorhandenen Quellstand konsolidiert, Bedarf/Module, Sichtbarkeit/Aktivierung/Rechte, feste Instanzbindung | Bestandsaufnahme, Modul-/Instanzdokumentation |
| Kundenauftrag | Anfrage/Katalog/Angebot/Portalannahme/kanonischer Auftrag, Offline-Serviceprotokoll, Rechnung und Zahlung | `CRM_ERP_KUNDENAUFTRAG.md`, `CRM_ERP_OFFLINE_SERVICEBERICHTE.md` |
| Projektkosten und Übersicht | Geprüfte Originalkosten, Zeit/Material, Budget/Nachträge, getrennte Erlöse/Zahlungen, nachvollziehbare Kennzahlen | `CRM_ERP_PROJEKTWIRTSCHAFTLICHKEIT_CLIENTS.md`, `CRM_ERP_UNTERNEHMENSUEBERSICHT.md` |
| Einkauf/Geräte/Inventur | Teil-/Restlieferung, Original-Lieferschein, Entnahme/Geräteherkunft, Wartung, Zählung und Bestandskorrektur | `CRM_ERP_EINKAUF.md`, `CRM_ERP_GERAETEHERKUNFT.md`, `CRM_ERP_INVENTUR.md` |
| Kundenbereich und Vertrieb | Isolierte freigegebene Informationen/Originale/Uploads; Chancen, Aktivitäten, Wiedervorlagen und Projekt-/Angebotsübernahme | `CRM_ERP_KUNDENARBEITSBEREICH.md`, `CRM_ERP_VERTRIEB.md` |
| EÜR | Quellen-/Geldjournal, exakte Komponenten, Erstattungen, steuerliche Einordnung, AfA, Gegenbuchung, Perioden und Jahresprüfpaket; Abschlags-/Schlussketten | `CRM_ERP_EUER_WORKFLOW_PRUEFUNG.md`, `CRM_ERP_EUER_KETTEN_ANALYSE.md` |
| Personal/Lohn | Private Originalakten, Auslagen/Fremdfreigabe/Erstattung, Monatsvorbereitung, begrenzte 2026-Lohnfälle, Lohnkonten/Zahlungsteile/Vorträge/Jahresausgabe | `CRM_ERP_PERSONAL_WORKFLOW.md`, `CRM_ERP_LOHN_RECHENWERK_2026.md`, `CRM_ERP_LOHN_CLIENTS.md` |
| Assistent und Sprache | Berechtigte Quellen, belegbare Antworten/Entwürfe, Regeln/Freigaben, native Versandgates, ausdrücklich gestartete Sprachentwürfe | `CRM_ERP_ASSISTENT.md`, `CRM_ERP_ASSISTENT_CLIENTS.md`, `CRM_ERP_SPRACHE.md` |
| Migration/Übergabe | Kontrollierter neutraler Dateiimport mit Originalen/Abgleich; portables Unternehmensarchiv mit eigenem Prüfer und expliziter Übergabeprüfung | `CRM_ERP_DATEIMIGRATION.md`, `CRM_ERP_DATEIIMPORT.md`, `CRM_ERP_UNTERNEHMENSEXPORT.md` |
| Anpassbarkeit | Fünf typisierte Zusatzfeldarten für Kontakte/Projekte/Geräte, Pflichtangaben und unveränderte Historie | `CRM_ERP_ZUSATZFELDER.md` |
| Datenschutzfälle | Identität/Quellenprüfung, begrenzter Export, kanonische Berichtigung und Bereinigung mit unabhängigem Restore-Checkpoint | `CRM_ERP_DATENSCHUTZFAELLE.md` |
| Lohnzahlungen/EÜR | Belegte tatsächliche Zahlungsteile und Abführungen; private Originale und aggregierte Finanzquelle | `CRM_ERP_LOHNZAHLUNGEN_EUER_CLIENTS.md` |
| Bankabgleich | Originalauszüge, bestehende Geldbewegungen, Teilzuordnung, Korrekturen, unveränderliche Berichte und EÜR-Periodenbindung in beiden Clients | `CRM_ERP_BANKABGLEICH_CLIENTS.md`, `CRM_ERP_BANK_EUER_INTEGRATION_PRUEFUNG.md` |
| Betriebsmittel | Kanonische Ressourcen, Prüfnachweise, Ausgabe/Rückgabe, Nutzungssperren und historische Korrektur | `CRM_ERP_BETRIEBSMITTEL_CLIENTS.md` |
| Midijob 2026 | Explizite belegte Prognose, getrennte Bemessungsgrundlagen, PV-Korrektur, historische Lohnkonten und Zahlungskette | `CRM_ERP_LOHN_MIDIJOB_2026.md`, `CRM_ERP_LOHN_MIDIJOB_CLIENTS.md` |
| Kundenservice | Anfrage/Reklamation/Wartung, Disposition, signierter Bericht, Lösung, Abschluss und Wiedereröffnung | `CRM_ERP_SERVICE_CLIENTS.md` |
| Browserbedienung | Gerenderte WCAG-Stichproben, korrigierte Kontraste, Tastaturdialog und mobile Ansichten | `CRM_ERP_BEDIENBARKEIT.md` |
| Sicherheit/Quellen | Aktualisierte Python-Pins, aktuelle Meldungsabgleiche, reproduzierbares Quellinventar, Pflege-/Vorfallsablauf und aktuelle fachliche Nachweisliste | `CRM_ERP_ABHAENGIGKEITEN_SICHERHEIT.md`, `CRM_ERP_KONFORMITAET_QUELLEN.md` |

Testzahlen, konkrete Grenzen und laufende Integration stehen im
[Integrationsstand](CRM_ERP_INTEGRATIONSSTAND_2026-11-03.md). Keine Tabellenzeile
ist allein eine Produktivfreigabe oder eine abgeschlossene Gesamtabnahme A–G.

## Aktive Arbeitspakete

1. **Einkaufsänderungen abschließen.** Lieferantenretouren und belegte Änderungen
   offener Bestellmengen verbinden tatsächliche Lieferpositionen, Reservierungen,
   Inventur und Gerätekapazitäten. Beide Clients sind fertig; historische
   Quittungen werden zusätzlich gegen die ursprünglichen Journalstände geprüft.
2. **Gemeinsame Abnahme durchführen.** Bankabgleich, Betriebsmittel,
   Midijob-Vollmonate und die lokale Zweifirmen-Provisionierung sind implementiert
   und abgegrenzt geprüft. Vollständige Node-/Flutterläufe bestehen; breite
   Backend-/Browserregression, alte PostgreSQL-Betreiberwege und Paketprüfung
   schließen den stabilisierten Integrationsstand ab.
3. **Lohnzeitachsen und Teilmonate umsetzen.** Entgeltanspruch,
   Beschäftigungszeit, Sozialversicherungstage, steuerlichen Lohnzahlungszeitraum
   und tatsächliche Zahlung getrennt belegen. Neue versionierte Rechenfälle
   anhand unabhängiger amtlicher Referenzen prüfen, alte Abrechnungen erhalten.
   Weitere Lohnfälle stehen konkret im `CRM_ERP_LOHN_LUECKENPLAN_2026.md`.
4. **Reisekostenpauschalen ergänzen.** Belegte Dienstreisen, Inland-/Auslandssätze
   2026, Mahlzeitenkürzung, Dreimonatsfrist und tatsächliche Erstattung an den
   bestehenden Personalworkflow anbinden; keine pauschale Steuerfreiheit aus
   einem bloßen Betrag ableiten.

## Noch offener Zielumfang

Nach den aktiven Paketen werden verbleibende konkrete Steuer-/Lohnfälle,
vollständige menschliche und gerätebezogene Bedienprüfung und die
vollständigen technischen Abnahmen A–G abgearbeitet. Dabei werden vorhandene
Teilnachweise verbunden und Lücken gezielt ergänzt. Neue Anbieter-/Dateiformate
werden nur mit verifiziertem Vertrag implementiert; ein neutraler Import gilt
nicht als Herstellerabnahme.

Die externen Nachweise umfassen reale Windows-/iPhone-Geräte und Verteilung,
betriebliche Anfangsdaten/Freigaben, unabhängige Sicherheitsprüfung, fachliche
Lohn-/Steuerprüfung und notwendige Meldezulassungen sowie tatsächliche ausgewählte
Providerzugänge. Fehlender unabhängiger Code wird nicht als extern blockiert
bezeichnet. Unabhängige Entwicklung läuft weiter.

## Arbeitsregeln und Abschlusskriterium

Neue Module werden additiv migriert. Historische Schema-/Quittungsformate bleiben
prüfbar; aktuelle Restores verlangen den vollständigen installierten Umfang.
Fehlende Bestände oder ungeprüfte Quellen werden nicht als Null, Gewinn oder
Erfolg angezeigt. Tests verwenden synthetische Daten und entbehrliche lokale
Dienste. Echte Zahlungen, Nachrichten, Bestellungen, Meldungen, produktive
Migrationen, Remote-Push und öffentliche Bereitstellung werden dadurch nicht
automatisch autorisiert.

Anforderungen, Entscheidungen, Quelländerungen und tatsächlich ausgeführte
Prüfungen werden im Repository dokumentiert. Fertigstellung setzt den benannten
Funktionsumfang, durchgängige Abnahmen, Installation/Betrieb und erforderliche
externe Nachweise voraus. Es wird kein Fertigstellungsprozentsatz aus der Zahl
der Dateien oder Einzeltests abgeleitet.
