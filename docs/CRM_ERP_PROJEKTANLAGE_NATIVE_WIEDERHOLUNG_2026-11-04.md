# Native Projektanlage: Eingaben und unklare Antworten – 04.11.2026

Diese Folgeänderung ergänzt den eingefrorenen
[Navigationsstand](CRM_ERP_PROJEKT_NAVIGATION_2026-11-04.md).
Nur `app/lib/main.dart` erhält weitere Produktänderungen. Das alte
Navigationsmanifest bleibt unverändert; dessen frühere Main-Datei ist im
neuen Prüfverzeichnis bytegleich archiviert.

## Verhalten

Die native Projektanlage bewahrt den ersten tatsächlichen Auftrag mit
Projektname, Kundenzuordnung und zufälliger `request_id`. Eine unklare Antwort
schließt das Formular nicht mehr. Seine Werte bleiben erhalten und gesperrt;
„Erneut versuchen“ verwendet den unveränderten Auftrag. Auch „Später fortsetzen“
und erneutes Öffnen behalten denselben Vorgang im laufenden Arbeitsbereich.
Erst eine bestätigte Projekt-ID schließt ihn ab.

Wiederholung setzt das Serverfeature `project_creation_receipts` voraus.
Es muss schon für den ursprünglichen Auftrag vorhanden gewesen sein und wird
vor jedem Retry mit einer frischen Capability-Abfrage erneut geprüft.
Ältere Server erlauben weiterhin die erste Anlage. Nach unklarer Antwort wird
jedoch kein zweiter POST angeboten: Die Projektliste kann aktualisiert und
geprüft werden. „Als geprüft abschließen“ entfernt nach ausdrücklicher
Bestätigung ausschließlich den lokalen offenen Vorgang, ohne Schreibaufruf.
Ein nachträgliches Serverupdate macht einen vorher ungesichert gesendeten
Auftrag nicht rückwirkend sicher wiederholbar.

Eine definitive Ablehnung des ersten Versuchs lässt die Eingaben zur Korrektur
stehen. Ein späterer 400/403-Fehler beim Retry ist dagegen kein Beleg, dass der
ursprüngliche Auftrag nie angenommen wurde; Body und ID bleiben dann erhalten.
Eine ausdrücklich gemeldete `request_resolution=not_accepted` wird gesondert
berücksichtigt.

Jeder Auftrag ist an API-Objekt, Server, API-Version, Sitzung, Benutzer und die
konkrete aktuelle Operation gebunden. Änderungen verwerfen nur deren eigene
Dialogroute und machen alte Antworten/Callbacks wirkungslos. Auch ein Wechsel
A→B→A belebt die frühere Operation nicht wieder. Nach erfolgreicher Anlage
aktualisiert sich die tatsächlich geöffnete Verwaltungs-Projektliste.

## Nachweise

- **15/15 neue Widgetfälle bestanden:** tatsächlicher POST-Body und Request-ID,
  Wiederholung nach Antwortverlust, Schließen/Wiederöffnen, API-/Host-/Versions-/
  Sitzungswechsel, verspätete Kundenliste, Wechsel während der Retry-Vorabprüfung,
  entfallenes Serverfeature, Altserver ohne erneuten POST, lokale Klärung,
  definitive Erst-Ablehnung, abgelehnter Retry und abgelöste UI-Callbacks.
- **12/12 bestehende Verwaltungs-, Workspace- und Login/Rollenfälle bestanden.**
- **Vollständige Flutter-Analyse ohne Befund.**
- Acht Quellbindungen vor/nach dem abschließenden Lauf identisch. Alle alten
  Navigationsquellen außer der ausdrücklich ersetzten Main-Datei unverändert.

[Manifest und Rohlogs](evidence/project-create-replay-2026-11-04/manifest.json)
enthalten die exakten Befehle, Zwischenstände und Hashes. Frühere Läufe mit
10, 25 und 26 Fällen werden nicht zur Zahl eindeutiger Abschlusstests addiert.
Die zwischenzeitlichen sechs Analysewarnungen betrafen den direkten Aufruf der
Notifier-Methode; die Schlussfassung verwendet den öffentlichen ValueNotifier.

## Grenzen

Dies sind Linux-Flutterwidgettests mit kontrollierten synthetischen Antworten.
Sie beweisen die Clientaufrufe und deren Unterdrückung, nicht die serverseitige
Einmaligkeit oder eine tatsächliche Windows-/iPhone-Installation. Der zugehörige
Backend-Quittungsvertrag und dessen HTTP-/Datenbankprüfungen werden separat von
Root integriert. Der offene Auftrag bleibt im Arbeitsspeicher des laufenden
Arbeitsbereichs; ein Prozessneustart wird damit nicht abgesichert. Keine
Lohn-/Buchhaltungsfunktion, Migration, Veröffentlichung oder Bereitstellung.
