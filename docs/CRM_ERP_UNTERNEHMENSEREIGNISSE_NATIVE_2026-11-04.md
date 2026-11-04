# Unternehmensereignisse in der nativen Anwendung

Stand: 04.11.2026. Isolierter Arbeitsbaum:
`/workspace/smartplan-company-events-20261104`, Ausgangscommit
`4c2f0086b4a9979b7cbe9d261fc22a97cd046913`.
Die Umsetzung folgt dem [API-Vertrag](CRM_ERP_UNTERNEHMENSEREIGNISSE_API_2026.md)
und dem [fachlichen Vertrag](CRM_ERP_UNTERNEHMENSEREIGNISSE_VERTRAG_2026-11-04.md).
Sie ist kein Nachweis einer produktiven Freigabe oder der Vollständigkeit des Gesamtziels.

## Bedienung

Der bestehende Assistent erhält einen Einstieg zu Unternehmensereignissen. Die
Seite bietet getrennte Übersichten für Aktionspläne, ursprüngliche Ereignisse,
Regeln und dauerhaft gespeicherte Läufe. Regeln und Läufe benötigen zusätzlich
`settings.manage`; Originale und Pläne werden anhand ihrer tatsächlichen
Projekt- und Quellenrechte geprüft.

Eine Regel bindet ausdrücklich Auslöser, passende Aktion, Entscheidung,
Zuständigkeit, Projektmenge, bis zu acht typisierte Bedingungen und eine feste
Vorlage. Aufgaben können optional ein relatives Fälligkeitsintervall haben;
Angebotsvorlagen verwenden eine bis sechs ausdrücklich ausgewählte aktive
Artikelfassungen und genaue Mengen. Die Deaktivierung speichert eine weitere
Regelfassung, die Historie bleibt sichtbar. Eingaben in Euro werden über
`BigInt` in kanonische Centstrings umgerechnet, auch bei 40-stelligen Werten.
Es werden keine Geldwerte per `double` gerundet.

Ein Ereignislauf benötigt eine eigene Bestätigung seiner möglichen Wirkung.
Datum, Zeitzone, Ereignisse und Quellen liefert ausschließlich der Server.
Eine nächste Quellenseite wird mit dem tatsächlich zurückgegebenen Cursor
ausdrücklich gestartet. Abfragevollständigkeit und Erfolg einzelner Aktionen
werden getrennt angezeigt. Historien haben ebenfalls explizite Seitenfortsetzung.

Ein Plan zeigt Originalereignis, Quellenhash, konkrete Parameter, Unternehmens-
und Projektregeln, Zuständigkeit, Entscheidung sowie den tatsächlichen
Ausführungsstand. Originaltexte bleiben darstellbare Daten. Freigabe, Ablehnung
und Ausführung benötigen getrennte ausdrückliche Bestätigungen. Eine erzeugte
Aufgabe lässt sich über ihren echten bestehenden Projekt-Endpunkt erneut lesen.
Fehlende Adapter, geänderte Quellen, Restore-Sperren und ungeklärte Ausgänge
werden nicht als erfolgreich ausgeführte Aktionen dargestellt.

Eine gültige Annahme eines bereits dauerhaft gespeicherten Ausführungsanspruchs
darf die lokale Warteschlange auch dann auflösen, wenn noch kein Endergebnis
vorliegt: `execution` ist vorhanden, `outcome` ist null und `status` ist
`unconfirmed`. Die Seite bietet dann keine neue Ausführung an. Dasselbe gilt
für den Zustand `unknown` mit ungeklärtem Transportergebnis.

## Originalbindung und privater Lebenszyklus

`business_company_event_contract.dart` prüft die geschlossenen DTOs einschließlich
kanonischer Hashes. Ereignis, erste Planquelle und `action_key` müssen zusammenpassen.
Die eingebettete frühere Projektregel wird aus ihrem unveränderten `original_json`
als Text gehasht. Die sichtbare Centstring-Projektion wird ohne Umweg über numerisches
JSON gegen dieses Original geprüft. Historische Ausführungen dürfen zu einem
früheren Plan desselben Anlasses gehören; die tatsächliche Aufgabenzuständigkeit
wird deshalb gegen `execution.created_by` geprüft.

POST-Quittungen müssen genau `request_id`, Operation und den Hash über den
vollständigen ursprünglichen Body bestätigen. Hinzu kommen konkrete Ergebnisbindungen
wie Regelfassung oder Planhash. Ein falscher Hash oder unbekannter Antwortausgang
löscht den ursprünglichen Auftrag nicht. Erst `request_resolution: not_accepted`
belegt bei einem entsprechenden Konflikt das Fehlen der Annahme.

Der neue Sessionhook ist ausschließlich auf die dokumentierten Company-Events-
POSTs und ihre passenden logischen Schlüssel begrenzt. Er verändert keine
generische Wiederholungsberechtigung. Vor jeder Wiederholung werden aktuelle
Unternehmens-, Projekt-, Quellen-, Zuständigkeits- und Fachrechte geprüft.
Die ursprünglichen Werte, Kennung und Antwortprüfung bleiben erhalten.
Gleichzeitige gleiche Aufrufe teilen dieselbe laufende Future; eine abweichende
Anforderung unter demselben Schlüssel wird abgewiesen.

Der noch nicht gestartete POST wird zusätzlich abgebrochen, wenn die auslösende
Ansicht während der Vorprüfung geschlossen oder ausgetauscht wurde. Wird ein
neuer Funktionsstand erst dabei entdeckt, bleibt der Originalauftrag offen; eine
erneute ausdrückliche Wiederholung erfolgt aus der aktualisierten Ansicht.
Bereits abgesendete Antworten können ihre ursprüngliche Quittung bestätigen,
dürfen aber keine spätere andere Ansicht mit alten Daten oder Fehlermeldungen füllen.

Sessionwechsel, Rechte-/Modul-/Generationswechsel und App-Hintergrund löschen
private Ansichts- und Editorwerte. Auch verspätete Fehler sind an die ursprüngliche
Ansicht gebunden. Quellenrechte werden nach gehaltenen Antworten erneut geprüft.
Der Einstieg besitzt ausschließlich seine eigene Route und entfernt diese bei
Austausch der Elternsession; er schließt keine inzwischen neu geöffnete Route.

Die lokale offene Anforderung liegt nur im Speicher derselben authentifizierten
Sitzung. Sie überlebt das Schließen und erneute Öffnen der Seite, wird aber nicht
als private Datei auf dem Gerät gespeichert. Serverseitige Historien und
Ausführungsansprüche sind davon getrennte dauerhafte Nachweise.

## Ausgeführte Prüfungen

Die tatsächliche gemeinsame Fixture liegt in
`docs/fixtures/company_events_2026.json` und
`app/test/fixtures/company_events_2026.json`.
Geprüfter SHA256 beider Dateien:
`2b10534178c4efef9c6ea6ed69b626b675617b3da6e6d2168915d5394bc29f20`.
Der Backendgenerator erzeugt die sechs Szenarien über den echten Dispatcher:
auto, approval, deny, project_approval, external_unknown und external_unconfirmed.
Die native Implementierung hat diese Fixture nicht verändert.

| Prüfung | Ergebnis | Nachweis |
| --- | --- | --- |
| Neue Vertrags-, Session-, Widget- und HTTP-Fälle | **60 bestanden** | Drei neue `business_company_event*test.dart`-Dateien; im finalen gemeinsamen Lauf enthalten |
| Gemeinsamer Lauf mit bestehenden Assistenten-, Session-, Shell-, Editor-, Organisations- und Katalogtests | **149 bestanden** | [regression-final.txt](evidence/company-events-native-2026-11-04/regression-final.txt) |
| Statische Analyse der vier Runtime- und drei Testdateien | **0 Befunde** | [analyze-final.txt](evidence/company-events-native-2026-11-04/analyze-final.txt) |
| Zuvor roter Elternsession-/Routenfall | Fehler reproduziert und behoben; grüne Gegenprobe im gemeinsamen Lauf | [route-before.txt](evidence/company-events-native-2026-11-04/route-before.txt) |

Die neuen Fälle enthalten echte Fixturehashes, exakte große Beträge, verfälschte
Quittungen/Originale, angenommene Claims ohne Endergebnis, 390-Pixel-Ansichten,
ausdrückliche Regel-/Scanbestätigungen, verlorene ACKs nach Seitenwechsel,
unsichere HTTP-Statuscodes, Freigaberechtentzug mit erhaltenem Leserecht,
zwölf verspätete GET-Erfolge/-Fehler, zwölf verspätete Freigabeantworten und vier
abgebrochene Vorprüfungen vor dem POST.

Der native HTTP-Test startet eine lokale temporäre Installation mit tatsächlich
provisionierter Unternehmensidentität und privater Serverablage. Er verwendet
den echten bestehenden HTTP-/Domainpfad: Regelannahme, Scan, Plan/Original,
Freigabe, Ausführung, Wiederholung verlorener Regel-/Scan-/Execute-Antworten,
genau eine neue Aufgabe, erneuter Fachabruf und unveränderte Regelhistorie nach
Deaktivierung. Es werden keine realen Nachrichten oder Zahlungen ausgelöst.
Der Test verwendet eine synthetische bereits authentifizierte Sitzung; er ist
kein separater MFA-, TLS-, Gerätebuild- oder Produktionsnachweis. Die entsprechenden
Backend-/Betriebsprüfungen bleiben getrennt dokumentiert.

## Integrationsgrenzen und Übergabe

Neue native Runtime-Dateien:

- `app/lib/business_company_event_contract.dart`
- `app/lib/business_company_events.dart`

Gemeinsame Runtime-Dateien, **gezielt zu integrieren**:

- `app/lib/business_session.dart`: nur der neue enge Company-Events-Hook und seine
  Einordnung als dokumentarischer Auftrag; bestehende Funktionen wurden nicht umgeschrieben.
- `app/lib/business_assistant.dart`: ein Import und der neue Entry.

Unverändert sind insbesondere `api.dart`, `business_widgets.dart`, die bisherigen
nativen Katalogdateien und deren Tests. Es gibt keine neue allgemeine Antwortgrößengrenze.
Die exakten Ausgangshashes stehen in
`work/verification/company-events-native-baseline.json`; Root integriert neuere
Source5-, Anlagen- und V2-Sessionzusätze separat. Eine alte gemeinsame Sessiondatei
darf nicht unverändert über einen neueren Hauptstand kopiert werden.

Die neue Angebotsvorlage hat laut bestehendem Ereignisvertrag keine datierte
V2-Preisauswahl. Als `dated_catalog` gekennzeichnete Artikel werden daher in diesem
Editor nicht automatisch mit technischen Stammwerten verwendet. Die spätere
gemeinsame Integration muss den serverseitigen V2-Verbrauchervertrag ebenfalls
erhalten; diese native Änderung erweitert weder Preis-API noch Backend.

Backend, Browser, globale Paketlisten und CI liegen bei ihren jeweiligen Ownern.
Dieser Nachweis beinhaltet keine Änderungen an diesen Dateien, keine Commits und
keine Veröffentlichung. Ein unabhängiger Native-Review sowie die Gesamtintegration
folgen anhand des eingefrorenen Handoffmanifests.

## Unabhängiger Statusbefund und gezielte Nachprüfung

Die unabhängige Gegenprüfung zeigte eine widersprüchliche Projektion: Ein tatsächlicher dauerhaft angenommener Versandclaim ohne Ergebnis (`external_unconfirmed`, `outcome:null`) durfte bei unverändertem Original den abgeleiteten Status `succeeded` tragen. Der enge Vertragsnachtrag verlangt dafür nun eine Ausführung und ein tatsächliches `outcome.status=succeeded`. Historische `stale`-/`suspended`-Ansichten mit früheren Ergebnissen bleiben lesbar. Nur `business_company_event_contract.dart` wurde geändert.

Nach diesem Fix sind die eigenen **60** Vertrags-, Widget- und tatsächlichen HTTP-Fälle erneut grün; Analyse des geänderten Vertrags: **0** Befunde. Belege: `status-fix-tests.txt` und `status-fix-analyze.txt` im bestehenden Evidenzordner. Die früheren 149 gemeinsamen Fälle bleiben als vorheriger Bestandslauf dokumentiert; der unabhängige neue Gegenlauf wird separat vom Reviewer abgegeben.

Der echte HTTP-Test verliert jeweils erst die bereits erfolgreiche Serverantwort für `POST /company-events/rules`, `POST /company-events/scan` sowie `POST /company-events/plans/{id}/execute`. Er wiederholt jeweils den identischen vollständigen Body einschließlich ursprünglicher Vorgangskennung und prüft genau eine neu erzeugte Aufgabe. Das ist ein lokaler HTTP-Nachweis, keine zusätzliche MFA-/TLS-/Geräteabnahme. Alle vier Runtime-Dateien, die drei eigenen Testdateien sowie beide tatsächlichen Fixturekopien entsprachen vor dem gezielten Statusfix vollständig dem ursprünglichen Freeze-Manifest `9b737c63…`; die Fixture bleibt unverändert bei `2b105341…`.
