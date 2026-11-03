# Betriebsmittel: Browser- und Flutterablauf

Stand: 03.11.2026. Umgesetzter interner Ablauf zu R07.07. Fachmodell, API,
Kalendersperren, Datenbank- und Wiederherstellungsnachweise stehen in
[CRM_ERP_BETRIEBSMITTEL.md](CRM_ERP_BETRIEBSMITTEL.md); der vorausgegangene
Restbefund bleibt in [CRM_ERP_BETRIEBSMITTEL_ENTWURF.md](CRM_ERP_BETRIEBSMITTEL_ENTWURF.md).

## Erreichbarer zusammenhängender Ablauf

Der Einstieg **Betriebsmittel und Nachweise** befindet sich in der Einsatzplanung,
auch innerhalb eines Projekts, sowie im Kundenservice. Die Verwaltung verwendet
bestehende Planungsressourcen. Eine neue Ressource oder eine Änderung von Name,
Ressourcenart, Code und Aktivierung läuft über den vorhandenen `/resources`-Weg.
Es entsteht kein zweiter Fahrzeug-, Maschinen- oder Werkzeugstamm und keine
Umdeutung einer Kundenanlage in ein firmeneigenes Betriebsmittel.

1. Die Übersicht zeigt kanonische Ressource, Art, Code, Zustand, offene Ausgabe,
   Inaktivierung und konkrete Nutzungssperren. Ein fehlender Anforderungsstand
   erscheint ausdrücklich als **Prüfanforderungen noch nicht erfasst**.
2. Das ergänzende Profil erhält Hersteller, Modell, Serien-/Inventarnummer,
   Standort und eine begründete Zustandsfassung. Der Editor übernimmt den
   aktuell wirksamen Zustand aus Prüfung/Übergabe/Rücknahme; eine ältere
   Profilangabe hebt einen später gemeldeten Defekt nicht unbemerkt auf.
3. Konkrete Anforderungen erhalten eine ausdrücklich gesetzte Fälligkeit,
   Nutzungsrelevanz, Beschreibung und Begründung. Änderungen und Aufhebungen
   erzeugen weitere Fassungen. Es werden keine gesetzlichen Intervalle geraten.
4. PDF-, PNG- oder JPEG-Originale bis 2 MiB werden unverändert hochgeladen und
   vor einem Download anhand von SHA-256 und Bytezahl geprüft. Prüfung und
   Korrektur wählen eine konkrete gespeicherte Originaldatei dieser Ressource.
5. Eine Prüfaussage erfasst tatsächlichen Zeitpunkt, benannte prüfende Person,
   dokumentiertes Ergebnis, Original, Notiz und ausdrücklich gewählten
   Folgetermin. Der aktuelle Ergebnis-/Folgetermin steht direkt bei der
   Anforderung; die Einzelbelege bleiben im Verlauf. Eine Korrektur der jüngsten
   Prüfaussage benötigt den ursprünglichen Nachweis und einen Korrekturgrund.
6. Eine Ausgabe wählt einen aktiven Mitarbeiter oder ein freigegebenes Projekt,
   tatsächlichen Ausgabezeitpunkt, erwartete Rückgabe, Zustand und Notiz.
   Ausgaben mit Projektbezug übernehmen den konkreten Projektvorschlag aus dem
   Einstieg. Ein bereits offen ausgegebenes Betriebsmittel bietet eine Rücknahme
   an; eine parallele Ausgabe wird serverseitig abgewiesen.
7. Die tatsächliche Rücknahme bindet genau die offene Ausgabe. Empfänger,
   Zeitpunkt, Zustand, Mängel und optionaler Originalbeleg werden dokumentiert.
   Überfällige Rückgaben sind sichtbar. Ein gemeldeter Schaden bleibt eine
   konkrete Nutzungssperre.
8. **Verfügbarkeit prüfen** ermittelt einen ausdrücklich gewählten Zeitraum,
   Mitarbeiter, Projekt und eine Zeitzone. Die tatsächliche Terminplanung und
   Service-Disposition prüfen dieselben Voraussetzungen erneut. Eine
   Terminkollision oder technische Sperre wird nicht durch die Oberfläche
   übergangen; bestehende Termine werden nicht still gelöscht.
9. Der Verlauf zeigt Profil- und Anforderungsfassungen, Prüfungen, ursprüngliche
   Ausgaben und Rücknahmen sowie belegte Korrekturen. Historische Namen stammen
   aus dem jeweiligen gespeicherten Quellenstand. Bewegungsberichtigungen
   benötigen einen Originalbeleg und eine Begründung; Ursprungsdatensatz und
   berichtigte Werte bleiben getrennt sichtbar. Eine Rücknahme kann durch die
   Korrektur keiner anderen Ausgabe zugeordnet werden.

Die Oberfläche erteilt keine technische Zertifizierung und behauptet keinen
Werkstatt-, TÜV-, Telematik- oder Schlüsselübergabeanschluss. Sie dokumentiert
bewusste betriebliche Eingaben und deren Quellen.

## Rechte, Antwortverlust und Zustand

Vollständige Ressourcen- und Mitarbeiterhistorien benötigen **globale**
`planning.read`- und `planning.write`-Rechte. Eine Projektfreigabe verleiht keine
globale Verwaltungsfreigabe. Flutter öffnet aus Projekt- und Serviceansichten
`sharedGlobalSession()`: die vom Elternfenster gehaltene globale Session wird
wiederverwendet beziehungsweise eine eigenständig berechtigte globale Session
angelegt und frisch geladen. Die Oberfläche löscht geladene Inhalte bei
Rechteverlust oder Sitzungswechsel. Lese- und Originaldownloadpfade werden
serverseitig erneut autorisiert.

Neue Änderungen benötigen Schreibmodus und ein aktives Planungsmodul. Ein
unbestätigter Originalauftrag behält Pfad, Inhalt und Request-ID. Beide Clients
prüfen vor seiner Wiederholung globale Rechte und die konkrete kanonische
Ressource frisch. Der Browser sperrt bearbeitete Eingaben und zeigt die
ursprünglichen Werte ohne die Base64-Dateidaten. Flutter nutzt die gemeinsame
Pending-Editor- und Sessionlogik. Ein Loginwechsel während der Prüfung kann
keinen alten Auftrag unter neuer Identität senden.

Eine nachweislich abgewiesene neue Anfrage darf nach Fehlerkorrektur erneut
vorbereitet werden. Eine unbekannte Quittung bleibt offen. Bei einer inzwischen
deaktivierten Planung entscheidet der Server anhand seiner unveränderlichen
Quittung, ob er einen schon angenommenen Originalauftrag bestätigt oder eine
neue Wirkung sperrt. Eine Quittungswiederholung erzeugt weder zweite Ausgabe
noch zweite Rücknahme. **Aktuellen Stand laden** erlaubt nach zwischenzeitlichen
Kalender- oder Quellenänderungen eine bewusste neue Prüfung.

## Nachweise

| Prüfung | Ergebnis | Abgedeckter Sachverhalt |
| --- | --- | --- |
| Browser-Vertragstests `resource-custody.test.mjs` | 5/5 bestanden | Kanonische Identität, expliziter Empfänger, offene Ausgabe, falsche Rücknahmequittung, Originalhash, globaler Rechteverlust, exakte Wiederholung nach Moduldeaktivierung, Loginwechsel |
| Benachbarte Node-Prüfungen | Insgesamt 24/24 bestanden | 5 Betriebsmittel-, 6 Service- und 13 bestehende Client-Verträge |
| Flutter `business_resource_custody_test.dart` | 6/6 bestanden | Quellbindung, Rücknahmequittung, Antwortverlust, wirksamer Rückgabezustand im Profileditor, Projekt-zu-Global-Freigabe, Rechteentzug |
| Benachbarte Flutter-Prüfungen | Insgesamt 13/13 bestanden | 6 Betriebsmittel- und 7 Serviceprüfungen |
| Echter Browser `resource-custody-flow.cjs` | 1/1 bestanden | Lokale Owner-MFA/HTTP, native Ressourcenanlage, Profil, Anforderung, Original, Prüfung, verlorene Ausgabeantwort, gleiche Quittung ohne zweite Ausgabe, Projekt-/Mitarbeiterbindung, native Kalenderwirkung, beschädigte Rücknahme, belegte Korrektur, bytegleicher Download |
| Flutter-Analyse | Ohne Befund | Neue Seite, Planungs-/Serviceeinstiege und gezielter Widgettest |
| Darstellung | Desktop und 390-Pixel-Ansicht geprüft | Lesbarer Verlauf, umbrochene Aktionen und kein horizontaler Seitenüberlauf |

Der Browsernachweis läuft mit aktiver Chromium-Namespace-, PID-, Netzwerk- und
Seccomp-Sandbox. Die absichtlich verlorene Antwort wird erst **nach** einer
real angenommenen HTTP-Mutation abgeschnitten; die zweite Antwort bestätigt
dieselbe unveränderte Quittung. Die Prüfung benutzt synthetische Ressourcen,
Originale, Zustandsangaben und Mitarbeiterausgaben. Es wurden keine realen
Betriebsmittel bewegt oder externe Empfänger kontaktiert.

Die zugehörigen lokalen Logs und Screenshots liegen unter
`work/verification/resource-custody-*`; sie sind Laufartefakte. Die permanenten
Tests liegen in `web/office/tests/` und `app/test/`. Flutter-Widgettests und ein
Browserlauf ersetzen keine reale Windows-/iPhone-Geräteabnahme.
