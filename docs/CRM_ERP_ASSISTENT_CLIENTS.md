# Assistent und Unternehmensregeln in Browser und nativer App

Stand: 03.11.2026. Fachvertrag und serverseitige Grenzen: [CRM_ERP_ASSISTENT.md](CRM_ERP_ASSISTENT.md).

## Umgesetzter Bedienablauf

Die zentrale Navigation **Assistent** und der entsprechende Bereich innerhalb eines Projekts verwenden dieselben aktuellen Projekt- und Fachrechte. Die native zentrale Ansicht lädt eine eigene, vom angemeldeten Hauptcontroller gehaltene Projektsitzung. Offene Vorgänge überleben einen Wechsel zwischen Projekten innerhalb dieser Sitzung, erben aber keine Rechte eines anderen Projekts.

1. Projekt auswählen und zugängliche Fachquellen durchsuchen. Die Suche umfasst Bezeichnung, Art und Kennung; Seiten mit jeweils 100 Treffern machen auch größere Kataloge vollständig erreichbar. Bis zu acht ausdrücklich ausgewählte Quellen bilden den Kontext. Bereits bestätigte Quellen bleiben bei Suche und Seitenwechsel in der Auswahl enthalten.
2. Jede ausgewählte Quelle mit ihren belegten Angaben und ihrer unveränderlichen Referenz prüfen. Jeder Quellenlink liest die Quelle erneut unter aktuellen Rechten. Externe Kommunikation wird als externer Inhalt kenntlich gemacht und erteilt keine Ausführungsfreigabe.
3. Bei eingerichteter KI kann der Nutzer eine konkrete Frage stellen und die Weitergabe der ausgewählten Daten an den eingerichteten Anbieter ausdrücklich bestätigen. Die Antwort zeigt nur serverseitig aufgelöste Fakten mit passenden Quellenangaben. Beide Clients prüfen zusätzlich Projekt, Quellenzuordnung und exakte belegte Werte. Frühere eigene Chatantworten bleiben über die Historie aufrufbar, solange die aktuellen Quellenrechte bestehen.
4. Ein konkreter Aktionsauftrag legt Auslöser, Parameter und Begründung fest. Aufgaben und Angebotsentwürfe sind echte Fachvorgänge. Ein Angebot enthält als Eingabe ausschließlich ausgewählte Artikelkennungen, deren Revisionen und Mengen; Verkaufspreise und Steuern stammen aus den serverseitigen Artikelfassungen. Die Bestätigung erklärt ausdrücklich, dass eine passende Automatikregel den konkreten Auftrag sofort ausführen kann.
5. Die Auftragsansicht zeigt die verbindliche Regelentscheidung, unabhängige belegte Regelfakten, Zuständigkeit, angewendete Regelfassungen, ausgewählte Quellen, Freigabe und dokumentiertes Ergebnis. Freigabe und Ausführung beziehen sich auf genau den geprüften Planhash. Aktuelle Rechte und Zuständigkeit werden vor jeder Fachaktion serverseitig erneut geprüft.
6. Benutzer mit `settings.manage` können versionierte Regeln anlegen, bearbeiten und deaktivieren. Unterstützt sind Verbot, Freigabe und Automatik sowie typisierte Bedingungen aus belegten Zahlungs-, Aufgaben- und Kostenfakten. Die Historie erhält alle Regelfassungen; Deaktivierung löscht keine frühere Entscheidung.

## Verlorene Antworten und Rechtewechsel

Unbestätigte Änderungen behalten die ursprüngliche Kennung, den Pfad und die vollständigen Werte im Arbeitsspeicher. Die zugehörigen Eingabefelder werden gesperrt. Eine Wiederholung verwendet denselben Auftrag nach erneuter Prüfung des ursprünglichen Projekts, der Berechtigungen und des Quellen- oder Planobjekts. Ein anderer Projektkontext, entzogene Quellenrechte oder eine neue Sitzung geben den ursprünglichen Auftrag nicht frei. Eine explizit serverseitig bestätigte Nichtannahme kann einen Konflikt auflösen; ein unbekannter Ausgang bleibt offen.

Erfolgsantworten werden vor dem Entfernen des offenen Vorgangs gegen Projekt, ausgewählte Quellen, Regelfassung beziehungsweise konkreten Auftrag geprüft. Ein bereits ausgeführter Auftrag wird durch die dokumentarische Wiederholung nicht erneut ausgeführt. Ein unklarer externer Ausgang wird nicht blind wiederholt. Rechteverlust entfernt zuvor angezeigte Quelldaten; ein erneuter Abruf benötigt aktuelle Berechtigungen.

## Nachweise

- `app/test/business_assistant_test.dart`: acht Tests für quellgebundene Werte, reine Artikelpositionen ohne Modellpreise, typisierte Bedingungen, ehrliche Anbieteranzeige, gesperrte Eingaben nach verlorener Antwort, frische Rechte/Generation, versionierten Regel-Editor und projektgebundenen Replay sowie Quellensuche im Lesemodus. Ausführung als Flutter-Widgettests mit Windows-Variante; keine Abnahme auf einem realen Windows-Gerät.
- `web/office/tests/assistant.test.mjs`: zehn Tests für dieselben Datenverträge, erneut geprüfte Quellenlinks, Projektwechsel, aktuelle Pending-Rechte, unveränderte Kennung und Werte, Sitzungswechsel und strenge Erfolgsquittungen.
- `web/office/tests/assistant-flow.cjs`, gestartet über `SMARTPLAN_BROWSER_WORKFLOW=assistant`: echte lokale MFA, HTTP und Fachpersistenz; Standardverbot, Aufgabenfreigabe, verlorene Erfolgsantwort mit exakt gleichem Retry, genau eine neue Aufgabe, Automatik, Verbotsvorrang, Regelfassungen, Artikel außerhalb der ersten Katalogseite, quellenbasiertes Angebot mit serverseitigen Preisen sowie Projektwechsel. Die erweiterte Prüfung umfasst außerdem eine echte Mitarbeiterrolle ohne Finanzquellen und den Entzug ihrer Quellenrechte.
- Gezielte Flutter-Analyse der neuen Ansicht und Navigationshooks ohne Befunde. Die Chromium-Prüfung verwendet nachgewiesene Namespace-, PID-, Netzwerk- und Seccomp-Isolation. Alle Daten sind synthetisch; außer der lokalen Testinstanz ist kein Netzwerkziel zugelassen.

Lokale Protokolle: `work/verification/assistant-flutter.log`, `assistant-browser-contract.log`, `assistant-analyze.log`, `assistant-browser.log`. Screenshots und tatsächliche HTTP-Quittungen: `work/verification/assistant-browser-previews/`. Diese Prüfartefakte enthalten ausschließlich Wegwerf-Testdaten und werden nicht als Produktionsdaten ausgeliefert.

## Noch erforderliche externe Einrichtung

Ein produktiver Modellanbieter ist nicht konfiguriert. Deshalb zeigt die Oberfläche den konkreten Einrichtungsbedarf und erzeugt keine simulierte Chatantwort. Ausgewählte Quellen, Regeln und manuell formulierte Aktionsaufträge funktionieren unabhängig davon. Ein realer Modellaufruf mit freigegebenen Unternehmensdaten ist noch separat abzunehmen.

Die ausdrücklich gestartete Sprachaufnahme ist als gesonderter, bestätigter Eingabeablauf implementiert; Konfiguration, Nachweise und Zielgeräte-Abnahmegrenzen stehen in [CRM_ERP_SPRACHE.md](CRM_ERP_SPRACHE.md). Ohne freigegebenen Anbieter bleibt sie gesperrt. Lieferantenbestellung und Zahlungsausführung bleiben ohne den jeweiligen freigegebenen Adapter ausdrücklich gesperrt. Echte externe Zustellung, produktive KI, Sprache, TLS im Zielbetrieb und reale Windows-/Android-Geräte sind durch die lokalen Clientprüfungen nicht abgenommen.
