# Projektaufgaben im Browser – 09.11.2026

Eigener Kandidat auf Basis `51786b1` mit dem mobilen Anmeldefix `a7f8562`
(lokale identische Basis `cdb0b53`). Dieser Abschnitt ergänzt die bereits
vorhandene Projektmappe für R06.01. Er ändert keine Aufgaben- oder
Meilensteinsemantik und ist keine Gesamtabnahme A–G.

## Ergebnis und Bedienung

Unter **Projekte → Projekt öffnen → Aufgaben** lassen sich Aufgaben mit
Titel, Beschreibung, Fälligkeit, Priorität und Verantwortlichem anlegen und
bearbeiten. Die Prioritäten sind entsprechend dem vorhandenen Backend
**Normal** und **Hoch**; die zuvor angebotene, vom Server abgelehnte Option
„Niedrig“ entfällt. Statuswerte sind **Offen**, **In Bearbeitung**, **Erledigt**
und **Abgebrochen**. Die Aktionen „Erledigt“ und „Wieder öffnen“ öffnen eine
vorbelegte Bearbeitung; erst „Speichern“ bestätigt die Änderung. Abbruch ist
im selben Statusfeld verfügbar. Es wird keine Aufgabe gelöscht.

Der Verlauf zeigt jede gespeicherte vollständige Fassung mit Versionsnummer
und Zeitpunkt, einschließlich ursprünglicher Beschreibung, Fälligkeit und
Verantwortungszuordnung. Alte Fassungen enthalten keine Bearbeitungsfelder.
Eine nicht mehr aktive Person kann als unveränderter Verantwortlicher erhalten
bleiben; neue Zuweisungen stammen aus dem aktuellen Projektteam.

## Unveränderte Schreibverträge und neuer Lesevertrag

Die bestehenden POST-Verträge bleiben unverändert. Neue Aufgaben besitzen
keine Eingaberevision; Änderungen tragen die geprüfte aktuelle `revision`.
Der Client sendet die sechs vorhandenen Fachfelder sowie dieselbe
Vorgangskennung bei einer unveränderten Wiederholung. Texte, Datum, Status und
Priorität werden gegen die vorhandenen Feldgrenzen geprüft. Unbekannte
Prioritäten oder fremde neue Verantwortliche werden nicht angeboten/übernommen.

Neu ist ausschließlich:

```text
GET /api/v1/projects/{project_id}/tasks/{task_id}/history
200 {"items": [vollständige gespeicherte Fassung 1, Fassung 2, ...]}
```

Der Endpunkt prüft die aktuell zugängliche Einzelaufgabe im selben Projekt
und liest anschließend ausschließlich deren bereits gespeicherte
`workspace_versions`, aufsteigend nach Revision. Er berechnet keine neue
Historie, verändert keine Daten und benötigt keine Schemaänderung. Fremde
Aufgaben, Projekte und Arten sind nicht zugänglich. Es gelten die bestehenden
Leserollen: Ein zugeordneter Buchhalter darf lesen, aber keine Aufgabe ändern.
Anonyme/inaktive Benutzer und entzogener Projektzugriff bleiben gesperrt.
Bestehende ausreichend berechtigte Workspace-Offlinetoken behalten ihren
vorhandenen Leseumfang; alte reine Plantoken werden nicht erweitert.

Der Browser prüft die Projekt-/Aufgabenbindung jeder Fassung, lückenlose
Versionsfolge, unveränderte Erstellmetadaten und Gleichheit der letzten
Fassung mit dem frisch gelesenen aktuellen Datensatz. Bei inzwischen geänderter
Aufgabe muss der Verlauf erneut geladen werden.

## Rechte, Konkurrenz und unbestätigte Antworten

Vor Öffnen und Speichern werden Projektzugriff, aktuelle Benutzerrolle,
Betriebsmodus und Projektteam neu gelesen. Vor einer neuen Änderung wird
zusätzlich die vollständige aktuelle Aufgabe mit dem geöffneten Original
verglichen. Ein konkurrierender Stand überschreibt keine Daten und wird
nicht automatisch zur neuen Eingaberevision. Das vorhandene Backend prüft
Revision, Rolle und neue Zuweisung nochmals in seiner Schreibtransaktion.

Die quittierte Antwort wird vollständig gegen Auftrag, Projekt, Aufgabe und
erwartete Folgerevision geprüft. Fehlende Antworten und lokal unpassende
Erfolgsantworten behalten die ursprüngliche Anfrage. Die erneute Freigabe
prüft den aktuellen Zugriff, erhält jedoch die alte Anfrage und deren
historische Antwort auch nach späteren Revisionen. Ein Quellen-/Quittungsfehler
ist kein belegter POST-Revisionskonflikt und verwirft deshalb keine Anfrage.
Echte serverseitige Revisionskonflikte bleiben davon getrennt.

Nach Rechteentzug entfernt die Bearbeitung ihre Eingabefelder. Eine noch
ungeklärte Anfrage bleibt über „Antworten offen“ unverändert klärbar.
Projekt-/Seiten-/Dialogwechsel oder Sitzungstausch verhindern, dass verspätete
Lese-/Schreibantworten eine neue Ansicht ersetzen oder schließen.

## Ausgeführte Prüfungen

Die [Prüfübersicht mit Dateihashes](evidence/project-tasks-browser-2026-11-09/verification.json)
gehört zu diesem Kandidaten:

- Vollständige vorhandene Workspace-Domainprüfung: **21 bestanden** in
  17,376 Sekunden, einschließlich zwei neuer Historienfälle.
- Zwei neue tatsächliche History-HTTP-Fälle sowie bestehende
  Rollen-/Zuordnungs- und Replay-/Konkurrenzfälle: **4 bestanden** in
  6,213 Sekunden. Anonym/inaktiv, andere Projekte/Arten, widerrufene Zuordnung,
  nur lesender Zugriff und unveränderte Originale sind abgedeckt.
- Gesamter Browser-Modulsatz: **912 bestanden**, kein Skip, in
  19,156 Sekunden. Zehn neue Aufgabenfälle prüfen Felder, historisches Team,
  fremde/veränderte Fassungen, Revision, aktuelles Recht, exakten Replay,
  inkonsistente Erfolgsantwort/Retry-Quelle und verspätete Antwort.
- Echter Chromiumablauf mit verifiziertem Namespace-/PID-/Netzwerk-/Seccomp-
  Sandboxbetrieb: **Exit 0**. Tatsächliche MFA, Anlage/Bearbeitung, Zuweisung,
  Abbruch/Wiederöffnung/Erledigung, sieben erhaltene Fassungen, echte
  konkurrierende Änderung, verlorene Create-/Edit-Antwort, real entzogener
  Projektzugriff und identischer Replay nach Wiederzuordnung, verspätete
  GET-Antwort sowie 390 × 844 Pixel. Keine ersetzten Fachserverantworten;
  Antwortverlust und Verzögerung betreffen echte bereits ausgeführte Requests.
- Unabhängige Prüfung fand einen Pending-Verlust bei lokal unpassender
  Erfolgsantwort. Er ist korrigiert und durch einen eigenen Regressionstest
  sowie erneute unabhängige Prüfung bestätigt.

Der erste Browserlauf scheiterte, weil der Test die Auswahloptionen vor dem
asynchronen Erscheinen des Formulars las. Ein explizites Warten auf das reale
Prioritätsfeld korrigiert nur den Test. Der ursprüngliche Fehlerlog bleibt
unverändert erhalten; Folge- und Schlusslauf sind getrennt gespeichert.
Frühere Python-Importversuche mit unvollständiger Interpreterumgebung werden
nicht als Produktfehler oder erfolgreiche HTTP-Tests gezählt. Die erfolgreichen
Läufe verwendeten die vorhandene Haupt-`.venv`; nichts wurde installiert.

Die CI enthält den neuen gezielten Ablauf `project-tasks` im Projektblock.
Eine neue Remote-CI, Serverinstallation oder menschliche Gerätebedienung wird
mit diesen lokalen Nachweisen nicht behauptet. Die neue Moduldatei
`web/office/project-tasks.js` ist in der expliziten HTTP-Assetliste enthalten.
