# Restbefund und additiver Entwurf: Kundenservice und Reklamationen

Stand: 03.11.2026. Befund aus Quellcode und aktueller Anforderungsmatrix;
noch keine Behauptung einer implementierten Fallverwaltung.

## Ergebnis der Bestandsprüfung

Der in Gesamtziel Abschnitt 7 verlangte zusammenhängende Kundenservice ist
noch nicht vorhanden. [R07.07](CRM_ERP_ANFORDERUNGEN.md) bleibt zutreffend offen;
auch die Nachbetreuung in R06.04 ist nicht allein durch Wartungsseiten erfüllt.

| Vorhanden | Konkreter Vertrag | Fehlende Verbindung |
|---|---|---|
| [Projektmängel](../backend/business_operations.py) | Titel, Details, Ort, Frist, Projektzuständiger, Fotos, Zustände `open/in_progress/resolved/accepted`, Abschlussbegründung und Versionen | Kein kanonischer Kundenanliegen-/Reklamationsfall, keine Eingangskanäle/Erstreaktion/Wiedervorlage oder Verknüpfung zum Serviceeinsatz |
| [Geräte und Wartungsverträge](../backend/business_maintenance.py) | Projektgerät mit Seriennummer, Ort, Medien; Vertrag mit Tages-/Monatsintervall und Startdatum | Kein allgemeiner Kundenservice außerhalb einer Wartungsserie; Gerätebezug nicht direkt an einen Reklamationsfall gebunden |
| Wartungsserien/-historie | Wiederholungssichere Fälligkeiten, pro Vertrag eindeutiger Terminindex, eingefrorener Vertrags-/Gerätestand | Fälligkeit ist kein disponierter Termin mit Beginn, Ende, Mitarbeiter und Betriebsmittel |
| Wartungsabschluss | Unterzeichnetes Serviceprotokoll desselben Projekts erforderlich, eingefrorener PDF-Hash, ein Bericht nur einem Besuch zuordenbar | Kein kompletter Fallabschluss mit dokumentierter Lösung, Kundenrückfrage und Wiedereröffnung |
| [Einsatzplanung](../backend/business_planning.py) | Kanonische Termine, Mitarbeiter, Ressourcen, Abwesenheiten und Konfliktprüfung | Kein Servicefall-/Wartungsbesuchbezug am Dispositionsvorgang |
| Serviceberichte | Online/Offline erfassen, geschütztes signiertes Original/PDF, Herkunft und Wiederholung | Bericht ist kein Eingangsticket und keine vollständige Reklamationsakte |
| [Geräteherkunft](CRM_ERP_GERAETEHERKUNFT.md) | Lieferschein, Bestell-/Wareneingangs-/Entnahmeposition zum Gerät | Keine Reklamationsentscheidung oder automatische Rückabwicklung; diese darf aus einer Gerätezuordnung nicht entstehen |

Die bestehenden Wartungstests belegen Monatsende/Schaltjahr, unveränderten
Serienanker, Wiederholung ohne Doppelbesuch, pausierte Verträge, Rechteentzug
und denselben Projekt-/Berichtsbezug. Sie belegen keine komplette Kundenanfrage
bis zum wiedereröffneten Reklamationsabschluss. Es wurde bei dieser Recherche
kein neuer Kundenkontakt, Termin, Versand oder produktiver Vorgang angelegt.

## Zusammenhängender nächster Ablauf

**Kunde/Anfrage oder Projektmangel → Servicefall → Prüfung und Zuständigkeit →
kanonisches Projekt/Gerät → disponierter Einsatz → vorhandene Zeit-/Material-
und Berichtserfassung → belegte Lösung → interner Abschluss oder Wiedereröffnung.**

1. Fall mit bestehendem Kunden und optionalem Ansprechpartner anlegen; optional
   eine vorhandene Anfrage oder einen Projektmangel als Herkunft auswählen.
   Geräte-/Wartungsfälle können einen bestehenden Besuch eindeutig übernehmen.
   Jede Herkunft wird nur einmal übernommen. Kunden-, Personen-, Projekt-,
   Geräte- und Vertragsbezüge werden serverseitig gegeneinander geprüft.
2. Art `request/complaint/maintenance`, Priorität, Betreff, Beschreibung,
   Verantwortlicher, Eingangsdatum und nächste Wiedervorlage führen. Bei Fällen
   ohne Projekt bleibt die Anlage zunächst der Geschäftsführung vorbehalten;
   Projektrollen sehen ausschließlich heute berechtigte Projekte und Quellen.
3. Ein kontrollierter Zustand führt von `open` über `triaged`, `planned`,
   `in_progress` und gegebenenfalls `waiting_customer/waiting_supplier` nach
   `resolved/closed`; `cancelled` erfordert eine Begründung. Wiedereröffnung
   ist ein ausdrücklich begründetes neues Ereignis und löscht keinen Abschluss.
4. Historische Notizen, erfasste Telefon-/E-Mail-Kontakte, Entscheidungen und
   Korrekturen unveränderlich festhalten. Eine Aktivität „E-Mail dokumentiert“
   löst keinen Versand aus. Kundenannahme/Gewährleistung/Kulanz werden nicht
   aus einem Status oder einer einfachen Unterschrift rechtlich abgeleitet.
5. Disposition ruft die **bestehende** Terminplanung auf, einschließlich
   Mitarbeiter-/Ressourcen- und Abwesenheitskonflikten. Fall und Termin werden
   atomar verbunden. Mehrere Einsätze pro Fall sind möglich; die Wiederholung
   eines konkreten Dispositionsauftrags erzeugt keinen zweiten Termin.
6. Vorhandene Projekterfassung für Zeiten, Material, Fotos und Protokolle nutzen.
   Ein ausgewählter Nachweis muss zum Fallprojekt gehören; aktuelle Leserechte,
   Klassifizierung und unveränderte Quellenhashes gelten weiterhin. Es wird
   keine zweite Material-/Kostenbuchhaltung aufgebaut.
7. Lösung und Nachweis festhalten. Wenn ein Wartungsbesuch abgeschlossen wird,
   muss der vorhandene signierte Servicebericht die nativen Abschlussbedingungen
   erfüllen. Ein allgemeines telefonisch gelöstes Anliegen kann mit begründeter
   Lösung ohne erfundenen Außeneinsatz geschlossen werden. Geschlossene Fälle
   zeigen weiterhin ursprüngliche Quellen, Termine, Protokolle und Verlauf.

## Additives Daten- und API-Modell

Neues Modul `backend/business_service.py`, Browser `web/office/service.js`,
Flutter `app/lib/business_service.dart`; keine Änderung historischer
Schema-Prüfsummen. Bestehende Anfragen, Kontakte, Projekte, Geräte, Wartungsbesuche,
Planungstermine und Berichte bleiben kanonisch.

Vorgeschlagene Tabellen:

- `business_service_cases`: feste Kunden-/Herkunftsidentität und Ersteller.
- `business_service_versions`: vollständige Fallversion mit Quellenständen,
  Verantwortlichkeit, Status, Wiedervorlage und Inhalts-Hash.
- `business_service_events`: unveränderliche Aktivitäten, Statusentscheidungen,
  Abschluss-/Wiedereröffnungsgründe und begründete Korrekturverweise.
- `business_service_links`: konkrete Projekt-, Mangel-, Geräte-, Besuchs-,
  Termin- und Berichtverknüpfungen mit Originalversion/-hash; eindeutige
  Herkunftsübernahme und dokumentierte Beziehung, keine kopierten Fachobjekte.
- `business_service_requests`: identische Wiederholung und unveränderlicher
  Ergebnisbeleg; technische Quittungen bleiben im allgemeinen Export getrennt.

`GET /service/options`, `GET/POST /service/cases`, `GET /service/cases/{id}`,
`GET /service/cases/{id}/history`, `POST .../events`, `POST .../project`,
`POST .../dispatch`, `POST .../evidence`, `POST .../transition` bilden den
abgegrenzten Vertrag. Filter nach Kunde/Projekt/Gerät, Status, Priorität,
Verantwortlichem und fälliger Wiedervorlage beziehen sich nur auf sichtbare Fälle.

Ein Termin wird nicht über beliebige frei übergebene Fremd-IDs angehängt:
Vorschau/Übernahme prüft Projekt, aktuelle Planungsversion und Rechte erneut.
Ein Fall ohne Projekt übernimmt einmal ein vorhandenes passendes Projekt oder
legt über die kanonische Projektpolitik genau eines an. Weitere Arbeiten bleiben
diesem Projekt zugeordnet. Der native Wartungsabschluss wird unverändert
wiederverwendet und in derselben Transaktion mit dem Fallnachweis quittiert.

Rechte: globale Übersicht zunächst Geschäftsführung oder bestehende objektweise
berechtigte Projektrollen; Kundendaten über `contacts.read`, operative Fallarbeit
über `documents.read/write` im Projekt, Disposition über die bestehenden
Planungsrechte und Projektverwaltung über `projects.manage`. Finanzbezüge
benötigen zusätzlich aktuelle Finanzrechte; fehlende Finanzrechte dürfen keine
Preise aus dem Servicefall ableitbar machen. Die konkrete Implementierung soll
diese Wiederverwendung mit den bestehenden Rollen prüfen, bevor neue Rechte
oder eine zusätzliche Unternehmensmodulgruppe eingeführt werden.

Aktivierung: allgemeine Fallverwaltung hängt nicht vom Personal- oder
Finanzmodul ab. Tatsächliche Termin-/Dokumentoperationen respektieren die
bestehenden fachlichen Aktivierungen. Deaktivieren oder Ausblenden löscht keine
Servicehistorie. Kontakte und Projekte erhalten einen engen Einstieg in ihre
Fälle; die zentrale Serviceübersicht bündelt offene Zuständigkeiten und Fristen.

## Notwendige Abnahme

- Kunden-/Anfrage-/Mangelübernahme genau einmal, fremde Kunden/Projekte/Personen
  und veraltete Quellen abweisen; Verantwortlicher muss aktuell berechtigt sein.
- Fallstatus und Übergänge, überfällige Wiedervorlage, begründete Korrektur,
  Abschluss und Wiedereröffnung mit unverändertem früherem Verlauf.
- Disposition mit echten Planungskonflikten, mehrere Einsätze, verlorene Antwort,
  Rechteentzug vor Wiederholung und atomarer Rollback nach Terminanlage.
- Signierter eigener Projektbericht akzeptiert; fremder/unsignierter/geänderter
  Bericht abgewiesen. Wartungsabschluss behält den bisherigen PDF-/Serienbezug.
- SQLite-/PostgreSQL-Schutz, tatsächlicher MFA-/HTTP-Ablauf, konkurrierende
  Wiederholung, Backup/Restore, Datenschutz-/Exportkatalog, beide Clients und
  echte Browserkette einschließlich schmalem Bildschirm.
- Keine externe Nachricht, automatische Erstattung, Bestellung, Rechnung oder
  Rechtsentscheidung aus einem Fallstatus; solche Aktionen benötigen ihre
  bereits bestehenden eigenständigen Freigabe- und Nachweiswege.

## Weiter verbleibender Teil von R07.07

Eine Fallverwaltung schließt die gesamte Betriebsmittelanforderung noch nicht.
`business_resources` kennt bisher insbesondere Namen, Art (`vehicle/machine/tool`),
Code und Aktivstatus sowie die Zuordnung in Terminen. Eine nachvollziehbare
Übergabe/Rückgabe an Mitarbeiter/Projekte, Zustand, Prüffristen und
Instandhaltung eigener Betriebsmittel ist nicht als zusammenhängender Ablauf
belegt. Diese Aufgabe sollte danach separat auf denselben Ressourcen aufbauen,
ohne Kundenanlagen und firmeneigene Betriebsmittel still zusammenzuführen.
