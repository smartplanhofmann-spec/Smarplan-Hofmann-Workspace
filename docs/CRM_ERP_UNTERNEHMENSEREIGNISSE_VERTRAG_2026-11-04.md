# Unternehmensereignisse – additiver Vertrag

Stand 04.11.2026; Entwicklung auf `4c2f008` im isolierten Baum
`/workspace/smartplan-company-events-20261104`. Maßstab sind Abschnitt 10 und
Abnahme E des unveränderten Gesamtziels. Dieses Dokument beschreibt die jetzt
implementierte Fallklasse; Test- und Integrationsstand werden separat ergänzt.

## Geprüfter Ausgangspunkt

`business_assistant.py` besitzt bereits versionierte Projektregeln, Quellen-
und Rechteprüfung, Freigaben, tatsächliche Aufgaben-/Angebotserzeugung und
Versand über die bestehenden Beleg-/Mahngates. Ein Modell erhält keine
Ausführungsrechte. Der bisherige Einstieg benötigt ein ausgewähltes Projekt,
einen Kontext und einen manuell erzeugten Plan; es existiert kein
unternehmensweiter Ereignislauf. Diese Historie bleibt unverändert gültig.

## Neue Fachgrenze

Eine Regel gilt für alle aktuell erreichbaren Projekte oder eine ausdrücklich
gespeicherte Projektmenge derselben Installation. Sie bindet Auslöser,
typisierte Quellenbedingungen, geschlossene Aktion, feste Vorlage,
zuständige aktive Person und `auto`, `approval` oder `deny`. Konkurrierende
Verbote gewinnen; widersprechende Zuständigkeiten/Vorlagen und nicht prüfbare
Bedingungen erlauben keine Aktion. Regeln benötigen `settings.manage` und
`assistant.use`; die Zuständigkeit verleiht keine Fach- oder Projektrechte.

Auslöser stammen aus tatsächlichen Fachabfragen:

| Auslöser | Beleg | Wiederholungsgrenze |
|---|---|---|
| `task.overdue` | Offene Aufgabe und belegtes Fälligkeitsdatum | Aufgabe und Fälligkeit |
| `payment.overdue` | Offener Rechnungsbetrag und Fälligkeit | Rechnung und Fälligkeit |
| `cost.threshold` | Erfasste, vollständige aggregierte Projektkosten | Hash des tatsächlichen Kostenstands |
| `communication.received` | Tatsächlich einem Projekt zugeordnete Anfrage | Anfrage-ID |
| `document.finalized` | Finaler Beleg und archivgebundene Versandvorschau | Beleg und finale Revision |
| `dunning.ready` | Bereits fachlich freigegebene Mahnfassung | Outbox-ID und Operation-ID |

Ein Scan ist eine ausdrücklich gestartete serverseitige Bestandsabfrage am
aktuellen Datum in Europe/Berlin, kein vom Client eingespeistes Ereignis und
keine Behauptung einer lückenlosen früheren Ereignisaufzeichnung. Bereits
vorhandene passende Vorgänge werden beim ersten Lauf berücksichtigt. Jede
beobachtete Fassung besitzt einen kanonischen Hash, Quellenkennung,
Installationsbindung und Abfragedatum. Text in Anfragen/Belegen bleibt Daten.
Personalakten und einzelne Lohn-/Zeitwerte sind keine Ereignisquellen.

Ein Ereignis kann je Aktionsart höchstens einmal **gestartet** werden. Gleiche
Scans, Antwortenverlust, Folgetage und Regeländerungen erzeugen damit keine
zweite Aufgabe, keinen zweiten Angebotsentwurf und keinen erneuten Versand.
Eine neue Fälligkeit, finale Revision oder Mahnoperation ist ein ausdrücklich
anderes Ereignis. Die bloße Änderung einer Regel setzt diese Sperre nicht
zurück. Unausgeführte veraltete Pläne werden bei einem neuen Scan mit neuer
Quellen-/Regelbindung ersetzt; alte Entscheidungen bleiben lesbar. Bedingungen
wie „mindestens sieben Tage überfällig“ werden bei jedem Scan frisch geprüft,
auch wenn derselbe Vorgang schon früher beobachtet wurde.

## Tatsächliche Aktionen und Freigabe

`task.create` verwendet eine feste Textvorlage, Priorität und optional einen
relativen Fälligkeitstag; die bestehende Projektaufgabe wird der zuständigen
Person zugeordnet. `offer.draft` verwendet ausdrücklich gespeicherte aktuelle
Artikelrevisionen und Mengen, niemals einen aus Eingangstext erfundenen Preis.
`document.email` und `dunning.email` binden ausschließlich das passende
Ereignisziel und verwenden die bestehenden Originale, Vorschauen, Quittungen
und zwei nativen Versandprüfungen. Bestehende Projektregeln können nicht durch
eine Unternehmensregel gelockert werden. Die effektive Entscheidung bindet
auch bestehende Regeln für `manual` und denselben Fachauslöser; deren Verbot
gewinnt und deren Freigabe verstärkt eine Unternehmensautomatik. Ein solcher
Plan benötigt eine gemeinsame Freigabe mit beiden belegten Regelständen.
Der alte Assistant-Ereigniseinstieg kann diese Unternehmensregeln nicht
umgehen: Ein geregelter Fachauslöser muss den eindeutig gebundenen neuen
Ereignislauf verwenden. Bestell-/Zahlungsaktionen ohne
tatsächlichen ausführenden Adapter bleiben ausdrücklich gesperrt.

Automatik bedeutet reale Ausführung nach einer ausdrücklich gespeicherten
Regel, unter erneut geprüften Rechten der zuständigen Person. Freigabe bindet
den exakten Planhash, diese Person und `assistant.approve`. Unbekannte Quellen,
entzogene Rechte, deaktivierte Fachmodule, veränderte Regeln oder Quellen und
ausstehender Restoreabgleich verhindern eine neue Ausführung.

Interne Wirkung und Ausführungsquittung werden atomar gespeichert. Vor
Außenwirkung wird der eindeutige Ausführungsanspruch festgeschrieben;
Timeout/Prozessabbruch bleibt ungeklärt und wird niemals blind wiederholt.
Ein erneuter Aufruf liest die gespeicherte Annahme unter aktuellen
Quellenrechten. Ein noch offener Plan wird bei Wiederherstellung gesperrt;
ein neuer Scan kann ihn neu vorbereiten, aber einen alten gestarteten
Ausführungsanspruch niemals umgehen.

Regeln, Läufe, Entscheidungen und Ausführungsansprüche benötigen jeweils die
dauerhafte Annahme ihres vollständigen Originalauftrags. Fehlt ein solcher
Nachweis, verweigert auch die aktuelle Ausführung und Historienprüfung den
weiteren Gebrauch. Eine Entscheidung allein ersetzt keine verlorene originale
Freigabequittung.

## Betrieb und Abnahme

Der HTTP-Lauf und ein begrenzter Workeraufruf nutzen denselben Kern. Eine
Installation oder ein Zeitplan aktiviert keine Regel und erteilt keine
Rechte. Entwicklung und Nachweise verwenden ausschließlich synthetische
Daten und lokale Testtransporte, keine tatsächlichen Nachrichten/Zahlungen.
Erforderliche Abnahmen: mehrere Projekte, alle drei Entscheidungen, echte
Aufgaben/Entwürfe/Versandgates, manipulative Eingangsdaten, fremde Projekte,
Rechteentzug, geänderte Quellen, parallele Läufe, Antwortverlust, Neustart,
append-only PostgreSQL-Rollen und befüllte Wiederherstellung. Browser und
native Oberfläche folgen dem tatsächlich geprüften API-/Fixturevertrag.

Der begrenzte CLI-Einstieg ist `scripts/process-company-events.py` mit
ausdrücklichem aktivem `--actor-id`, `--request-id` und bestehender
`SMARTPLAN_DATABASE_DSN` des Runtimekontos. `--page-size` ist auf 1–100,
`--max-pages` auf 1–100 begrenzt. Dieselbe Request-ID setzt dieselben bereits
angenommenen Seiten fort; für einen späteren unabhängigen Lauf ist eine neue
ID erforderlich. Exit 0 bedeutet vollständig abgefragten berechtigten
Quellenumfang, Exit 2 einen fortsetzbaren oder fachlich unvollständigen Lauf,
Exit 1 einen Fehler. Das ist keine Zusage, dass jede einzelne Aktion erfolgreich
war; deren dauerhaftes Ergebnis steht im jeweiligen Lauf. Der Befehl migriert
keine Datenbank und installiert weder Zeitplan noch Anbieterzugang.

Vor jedem CLI-Lauf prüft der bestehende Instanz-Worker-Guard die fest konfigurierte
`SMARTPLAN_INSTANCE_ID` und `SMARTPLAN_PUBLIC_HOST` gegen die Datenbankbindung.
Eine falsche oder fehlende Bindung erlaubt weder Scan noch Fachaktion. Der
HTTP-Pfad verwendet unverändert seine eigene verifizierte Instanzeinrichtung.
