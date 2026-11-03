# Betriebsmittel: Restbefund und additiver Entwurf

Stand: 03.11.2026, nach fachlicher Service-/Reklamationsimplementierung.
Dieser Bericht beschreibt den noch offenen Betriebsmittelteil von R07.07;
er behauptet keinen bereits umgesetzten Ausgabe-/Prüffristenworkflow.

## Vorhandene Grundlage und konkrete Lücke

Die kanonische Tabelle `business_resources` in
[business_planning.py](../backend/business_planning.py) verwaltet Fahrzeuge,
Maschinen und Werkzeuge mit `id`, `name`, `kind`, `code`, `active`, `revision`
und `updated_at`. `business_appointment_resources` bindet dieselben Ressourcen
an echte Planungstermine. Terminprüfung erkennt bereits Ressourcenüberschneidungen.
Ein späteres Betriebsmittelmodul muss genau diese Ressourcen-IDs weiterverwenden.

Es fehlen ein versionierter Identifikations-/Zustandsstand, dokumentierte
Ausgabe/Rücknahme an wirkliche Mitarbeiter bzw. Projekte, offene Rückgabefristen
und nachvollziehbare Prüffälligkeiten. Der Kundenservice ergänzt dies nicht:
`business_assets` beschreibt Kundenanlagen im Projekt samt Wartungsverträgen.
Eine Kundenanlage wird durch ihren Namen oder eine gleiche Seriennummer nicht
automatisch zu einem firmeneigenen Werkzeug oder Fahrzeug.

## Vorgeschlagener zusammenhängender Ablauf

**Vorhandene Planungsressource → Identifikation und Anforderungen → belegte
Prüfung/Zustand → ausdrückliche Ausgabe → tatsächliche Nutzung/Terminplanung →
Rückgabe und Zustand → wieder verfügbare oder gesperrte Ressource.**

1. Eine bestehende Ressource auswählen oder über den nativen Ressourcenweg
   anlegen. Ein ergänzendes Profil erfasst Hersteller, Modell, Serien-/Inventarnummer,
   Standort, Zustandsnotiz und gegebenenfalls Kennzeichen. Der native Ressourcen-
   code bleibt kanonisch; kein zweiter Ressourcenstamm wird angelegt.
2. Relevante Termine ausdrücklich hinterlegen: Bezeichnung, Art
   (`inspection/maintenance/other`), Fälligkeit und ob eine nicht erfüllte
   Anforderung die Nutzung sperrt. Es werden keine gesetzlichen Intervalle,
   Zulassungen oder Prüfpflichten anhand von Gerätetyp oder Modell erfunden.
3. Eine tatsächlich durchgeführte Prüfung mit Datum, benannter prüfender Person,
   Ergebnis, Notiz und Originalbeleg/prüfbarer Referenz erfassen. Ergebniswerte
   `passed/failed/review_required` sind dokumentierte Bedienereingaben, keine
   automatisch erteilte Zertifizierung. Ein fehlender Nachweis darf nicht als
   bestandene Prüfung erscheinen. Folgetermin wird ausdrücklich gewählt.
4. Ressource an einen aktiven kanonischen Mitarbeiter aus `business_employees`
   ausgeben, optional an ein zugängliches Projekt binden. Ausgabezeitpunkt,
   erwartete Rückgabe, Zustand, verantwortlicher Bearbeiter und optionale
   Originale festhalten. Eine Ressource kann nicht gleichzeitig zwei offenen
   Ausgaben besitzen. Ein bereits angenommener Auftrag erzeugt keine zweite
   Übergabe.
5. Rückgabe verweist auf genau die ursprüngliche offene Ausgabe. Tatsächlicher
   Zeitpunkt, empfangende Person, Zustand und Mängel werden festgehalten.
   Ein Schaden oder gesperrter Zustand gibt das Betriebsmittel nicht still frei.
   Falsche Angaben werden begründet korrigiert; Ausgabe- und Rückgabeoriginal
   werden nicht überschrieben.
6. Übersicht zeigt offen ausgegebene, überfällige, in Terminen gebundene,
   inaktive, wegen Zustand/Prüfung gesperrte und für einen konkreten Zeitraum
   nutzbare Ressourcen getrennt. Ein freier Kalender allein bedeutet keine
   belegte technische Einsatzfähigkeit.

## Datenhaltung ohne zweiten Ressourcenstamm

Neues Modul beispielsweise `business_resource_custody.py`, Browser
`resource_custody.js`, Flutter `business_resource_custody.dart`. Jede Fachtabelle
besitzt einen echten FK auf `business_resources.id`.

- `business_resource_profiles`: appendierte vollständige Profilversionen,
  aktuelle native Ressourcenrevision und Quellenhash.
- `business_resource_deadlines`: versionierte konkrete Prüf-/Wartungsanforderung;
  aufgehobene Anforderungen bleiben begründet historisch erhalten.
- `business_resource_inspections`: unveränderliche tatsächliche Prüfaussage mit
  Anforderungs-/Profilstand und Originalbelegbezug; Korrektur verweist auf das
  frühere Ereignis.
- `business_resource_handoffs`: tatsächliche Ausgabe mit Ressourcen-, Mitarbeiter-
  und optionalem Projektstand; genau eine offene Ausgabe pro Ressource.
- `business_resource_returns`: einmalige Rücknahme je Ausgabe mit Zustand und
  Quellenstand. Korrekturen als zusätzliche Ereignisse statt Überschreiben.
- `business_resource_evidence`: unveränderte hochgeladene Belege/Bilder mit
  SHA-256 und Ressourcenbezug, soweit die vorhandenen projektgebundenen Medien
  keine passende eindeutige Ablage bieten. Keine zweite Kunden-/Projektablage.
- `business_resource_requests`: unveränderliche technische Auftragsquittungen.

Die genaue Tabellenaufteilung kann vor der ersten Migration vereinfacht werden;
die kanonische Identität und Nachweiskette bleiben verbindlich. Bestehende
Schema-Prüfsummen werden nicht geändert. SQLite und PostgreSQL prüfen
Versionen, eindeutige offene Ausgabe, einmalige Rücknahme und Originale.

## Konkreter Rechte- und Kalenderbezug

Lesen nutzt die vorhandenen `planning.read`-Rechte. Mitarbeiter werden über die
bereits eingeschränkten Planungs-DTOs ausgewählt; Gehalt, Personalkosten und
sonstige Personalakten gehören nicht in diesen Ablauf. Projektgebundene
Ausgaben verlangen aktuelle Projektberechtigung. Neue Profile, Fristen,
Prüfaussagen und Ausgabe/Rückgabe benötigen zunächst `planning.write` und
einen dafür tatsächlich berechtigten Bearbeiter. Ohne globale Planungsrechte
entsteht kein globaler Zugriff auf sämtliche Übergabehistorien. Die praktische
Rollenprüfung muss klären, ob für delegierte Materialausgabe ein eigenständiges
Recht erforderlich ist; `inventory.write` darf nicht still globale Personal-
oder Fahrzeugverwaltung eröffnen.

Die Freigabe wird **serverseitig in der nativen Terminplanung** vor neuen
Ressourcenbindungen geprüft, zusätzlich zur bestehenden Kollisionsprüfung.
Nur eine Prüfung in einer neuen Oberfläche würde direkte native Termine,
Service-Disposition oder spätere Wiederholungen umgehen lassen.

Verfügbarkeitsauskunft bindet Ressource/Profil, offene Ausgabe, bestätigte
Rücknahme, relevante Prüfergebnisse/Fälligkeiten und heutige Termine an einen
konkreten Zeitraum. Der schreibende Terminweg prüft dieselben Fakten innerhalb
seiner bestehenden Transaktion erneut. Eine Ausgabe an einen Mitarbeiter kann
dessen eigenen Termin zulassen, sperrt aber eine parallele Vergabe an andere
Mitarbeiter. Eine ausdrückliche Projektbindung muss zum Terminprojekt passen.
Diese Zuordnung wird im API sichtbar erklärt und nicht aus einer Terminnotiz
geraten.

Inaktive Ressourcen, ausdrücklich gesperrter Zustand und nicht erfüllte
nutzungsrelevante Anforderungen sperren neue Bindungen. Bestehende Termine
bleiben als historische Planung erhalten; sie zeigen bei späterer Sperre einen
konkreten Konflikt und werden nicht automatisch gelöscht oder umgebucht.
Angenommene Originalaufträge bleiben nach frischer Berechtigungsprüfung reine
Quittungsreplays, auch wenn das Betriebsmittel inzwischen zurückgegeben wurde.

Für Bestandsressourcen ohne ergänztes Profil wird fehlendes Wissen sichtbar
als „Prüfanforderungen noch nicht erfasst“ gekennzeichnet. Daraus wird weder
eine bestandene Prüfung noch eine neu erfundene gesetzliche Pflicht abgeleitet.
Ein einmal ausdrücklich verlangter Nachweis darf dagegen nicht durch Weglassen
eines Profilfelds oder Umbenennung umgangen werden.

## Abgegrenzte API und Abnahme

Ein additives `/resource-custody` bietet Ressourcenliste/Verfügbarkeit,
Profil-/Fristenhistorie, Originalupload, Prüfnachweis, Ausgabe, Rückgabe und
Korrektur. Native Ressourcen- und Planungsendpunkte bleiben die kanonischen
Wege. Neue Ressourcen werden dort angelegt, nicht durch eine parallele
`create-resource`-Implementierung im Zusatzmodul.

Notwendige Prüfungen:

- echte aktive Mitarbeiter und erlaubte Projekte; keine Fremd-/Gehaltsdaten;
  keine zwei offenen Ausgaben, falsche Ausgabe-/Rückgabezuordnung abweisen;
- exakte Originalnonce nach verlorener Antwort, parallele Ausgaben/Rückgaben,
  Rechteentzug, vollständiger Rollback und unveränderte Vergangenheit;
- Datum/Zustand/Prüfpflicht explizit; fehlende oder ungültige Originale erzeugen
  keine erfolgreiche Prüfung, überfällige Rückgabe bleibt sichtbar;
- dieselbe Verfügbarkeit im Zusatzmodul, nativen Kalender und Service-Dispatch,
  auch bei direkten API-Aufrufen und zwischenzeitlich geänderten Quellen;
- keine stille Löschung bestehender Termine, keine Freigabe durch unpassenden
  Mitarbeitenden-/Projektbezug, keine erfundenen Prüfintervalle;
- echte SQLite-/PostgreSQL-/MFA-/HTTP-/Restoreprüfungen, Export-/Datenschutzkatalog,
  Browser und Flutter einschließlich mobilem Verlauf und Fehlerzuständen.

Externe Werkstatt-, TÜV-/Prüfer-, Telematik- oder Schlüsselübergabeschnittstellen
sind für diesen unabhängigen internen Ablauf nicht erforderlich und werden
ohne verifizierten Vertrag nicht vorgetäuscht. Bestandsdaten und reale Geräte
werden erst im ausdrücklich autorisierten Betriebsablauf übernommen.
