# Aktueller Stand der CRM-/ERP-Entwicklung

Stand: 04.11.2026. Hauptprojekt: `/workspace/Smarplan-Hofmann-Workspace`.
Das [unveränderte Gesamtziel](../CRM_ERP_Gesamtziel.txt) bleibt maßgeblich.
Einzelunternehmen, EÜR, Regelbesteuerung/Ist, SKR04, Nettopreise und reguläre
Beschäftigte/Minijobs sind der vereinbarte Rahmen.

## Nachvollziehbarer Orientierungswert

Die Statusverteilung bleibt in diesem Integrationsstand unverändert: 40 von
62 Anforderungszeilen sind „implementiert“ oder „getestet“. Das sind 64,5 %,
gerundet etwa 65 %, als ungewichtete Zeilenzählung. Fünf Zeilen sind teilweise
umgesetzt, elf offen und sechs extern blockiert. Keine Zeile wird allein wegen
der zusätzlichen Jahresvortrags- und Archivtests höher eingestuft.

Die unterschiedlichen Umfänge und offenen Abnahmen A–G erlauben daraus weder
eine Fertigstellungs- oder Arbeitszeitquote noch einen Termin. Die
[ursprüngliche Zählung am Stand `13af5bc`](evidence/requirements-progress-count-2026-11-04.json)
bleibt als Bezugsnachweis erhalten; die [erneute Zählung](evidence/requirements-progress-year-values-2026-11-04.json)
bestätigt dieselben Statuswerte am aktuellen Integrationsstand.

Der [gemeinsam geprüfte Integrationsstand](CRM_ERP_JAHRESVORTRAG_GESAMTPRUEFUNG_2026-11-04.md)
auf Basis `2e2ed5c` integriert Jahresvorträge und V2-Archive. Der
[Gesamtnachweis](evidence/year-values-integrated-regression-2026-11-04.json)
bindet die endgültigen Quellen und archivierten Prüfläufe.

## Bereits vorhandene und abgegrenzt geprüfte Funktionen

- Kunden, Projekte, Angebote, Portalannahme, Aufträge und Projektkosten.
- Einkauf, Teil-/Restlieferung, Lagerbewegungen, Inventur, Geräte und Service.
- Rechnungen einschließlich Abschlags-/Schlussketten, Korrekturen, offene
  Posten, Mahnungen, Teilzahlungen und Erstattungen.
- EÜR-Geldjournal, steuerliche Einordnung, Privat-/Kapitalbewegungen,
  Vorsteuerzeitpunkte, lineare Abschreibung, Gegenbuchung, Periodensperren
  und nachvollziehbares Jahresprüfpaket; im aktuellen Integrationsstand zusätzlich
  belegte unterjährige Jahresvorträge und der zugehörige V2-Originalnachweis.
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
4. Unternehmensweite Ereignisregeln sind zusätzlich zur Projektregelautomatik
   [gemeinsam geprüft](CRM_ERP_EREIGNISSE_GESAMTPRUEFUNG_2026-11-04.md):
   1.778 Backendfälle bei einem Windows-Skip, 1.386 App- und 647 Browsermodulfälle,
   vier tatsächliche PostgreSQLfälle und echte Browserabläufe bestehen.
   Quellenbindung, Freigaben, Wiederholung und Restore sind einbezogen.
   Zwei unabhängig belegte Browserfehler und die fehlende vorbereitende
   V2-Preisgrenze wurden korrigiert und erneut geprüft.
5. Historische offene Kunden-/Lieferantenposten sind mit beiden Clients,
   tatsächlichen Zahlungswegen zu EÜR, Bankabgleich und Liquidität
   [gemeinsam geprüft](CRM_ERP_ALTPOSTEN_GESAMTPRUEFUNG_2026-11-04.md):
   1.816 Backendfälle bei einem Windows-Skip, 1.434 App- und 713 Browsermodulfälle,
   109 unterschiedliche PostgreSQLfälle und vier tatsächliche Browserabläufe
   bestehen. Zwei native Originalbindungsfehler und verspätete Browserantworten
   wurden unabhängig reproduziert, korrigiert und erneut geprüft.
6. Eine getrennte SV-Gruppenkorrekturgrundlage ist isoliert und unabhängig
   geprüft, aber noch nicht integriert. Die Berechnung mehrerer Bonus-Steuergruppen bleibt
   gesperrt; diese Grundlage berechnet noch keine freigegebenen Nettobeträge.
7. Belegte laufende Jahreswerte vor einem unterjährigen Softwarebeginn sind
   mit beiden Clients und V2-Archivanschluss im Integrationsstand
   [technisch integriert und gemeinsam geprüft](CRM_ERP_JAHRESVORTRAG_GESAMTPRUEFUNG_2026-11-04.md):
   1.899 von 1.900 Backendfällen (ein Windows-Skip), 1.542 Flutter-, 842 Node-
   und 16 Paketfälle bestehen; Analyse ohne Befund. 121 unterschiedliche
   PostgreSQLfälle sind nach vier gezielten Nachprüfungen erfolgreich abgedeckt.
   Drei Fehler des Erstlaufs betrafen historische Testaufbauten; ausschließlich
   vier PG-Testdateien wurden nach den Gesamtprüfungen angepasst. Fünf echte
   Browserabläufe bestehen. Der separate mobile CSS-Nachtrag besitzt einen
   weiteren bestandenen Browsernachlauf und seine finale Quellbindung.
   Historische Werte erzeugen keinen neuen Geldfluss oder Vorsteueranspruch.
   Finanzhorizont 15/Bericht 16 sowie 144 Backend- und 209 Betreiberpfade sind
   registriert.
8. Das ergänzende Original-/Journalpaket ist mit beiden Clients
   [gemeinsam geprüft](CRM_ERP_JAHRESPAKET_GESAMTPRUEFUNG_2026-11-04.md):
   84 betroffene Backend-, 401 Buchhaltungs-/Export-App- und alle 762 Nodefälle,
   drei tatsächliche PostgreSQLfälle und vier echte Browserabläufe bestehen.
   Die ZIP-Prüfung benötigt den separat vertrauenswürdig gesicherten Hash;
   sie beweist allein keine vollständige Menge aller ursprünglichen Belege.
9. Ein privater Vergleich einer bereits bezahlten Bonussteuer bei belegtem
   ursprünglichem Vorarbeitgeberbetragsfehler ist isoliert und unabhängig geprüft.
   Er ist noch nicht integriert und enthält keine Zulässigkeitsentscheidung,
   Korrekturannahme, neue Zahlung oder Meldung. Weitere private Lohnquellenpakete
   befinden sich ebenfalls außerhalb dieses Integrationsstands.
10. Die Korrekturen für Unternehmenswechsel, private Assistentendialoge und
    Sprachkontext sind [integriert und geprüft](CRM_ERP_UNTERNEHMENSISOLATION_GESAMTPRUEFUNG_2026-11-04.md):
    91 betroffene Appfälle, sieben tatsächliche Zwei-Prozess-HTTP-Fälle,
    ein CI-Guardfall und alle 848 Browsermodulfälle bestehen. Analyse ohne Befund,
    16 Paketprüfungen. Produktive Isolations-/Sicherheitsabnahme bleibt offen.
11. Service-/Betriebsmittelkorrekturen sowie private Lohnvergleichs- und
    Quellenpakete liegen weiterhin in separaten Arbeitsständen. Nach dem
    Nutzungslimit der parallelen Bearbeiter sind ihre ausstehenden Prüfungen
    vor einer Integration wieder aufzunehmen.

## Noch offene Buchhaltungs- und Gesamtanforderungen

Weitere Steuerfälle, geeignete Steuerberater-/DATEV- und Behördenwege sowie
die vollständige fachliche Buchhaltungsprüfung bleiben offen. Der technisch
integrierte Jahresvortrag mit V2-Archivanschluss schließt diese Gesamtanforderung
nicht. Ein automatischer Bankabruf benötigt zusätzlich einen ausgewählten
Anbieter und dessen echten Vertrag. Weitere Lohn-/Korrektur-/Versicherungsfälle,
Meldeverfahren, durchgängige Gesamtabnahmen A–G und reale Windows-/iPhone-
Betriebsnachweise sind weiterhin erforderlich.

Die genannte Schätzung von zwei bis vier Stunden bezog sich auf die damals
laufenden Erweiterungen und deren Integration. Sie ist weder ein belastbarer
Endtermin noch eine Zusage für die vollständige Buchhaltung oder Software.
Aus Testzahlen wird kein Fertigstellungsprozentsatz abgeleitet.
