# Unternehmensereignisse – tatsächlicher Umsetzungsstand

Isolierter Arbeitsbaum `/workspace/smartplan-company-events-20261104`, Basis
`4c2f008`. Keine Produktionsänderung und kein Commit. Das unveränderte Gesamtziel
Abschnitt 10 / Abnahme E ist der Maßstab; dies ist ein geprüftes Teilpaket,
keine Erklärung, dass das vollständige CRM-/ERP-Gesamtziel erreicht sei.

## Implementierter Backendumfang

Sechs tatsächliche Fachquellen, unternehmensweite versionierte Regeln,
typisierte Bedingungen, ausdrückliche Zuständigkeit, Automatik/Freigabe/Verbot,
dauerhafte Beobachtungen, Pläne und Laufhistorien sind verbunden. Tatsächliche
Projektaufgaben und aktuelle artikelgebundene Angebotsentwürfe werden durch die
vorhandenen Fachmodule erzeugt. Beleg-/Mahnversand verwendet deren Originale,
Vorschauen und beide bestehenden Versandgates. Alle Nachweise verwenden nur
synthetische Daten und lokale Testtransporte.

Quellen-, Regel-, Instanz-, Plan- und Originalauftragsbindung werden auch bei
Wiederholung geprüft. Bestehende Projektregeln verstärken die neue Entscheidung;
der alte Assistant-Ereigniseinstieg kann die Unternehmensregel nicht umgehen.
Die neue geschlossene Verarbeitung erzeugt keine Modellrechte, individuelle
Personal-/Lohnquelle, Überweisung oder Lieferantenbestellung ohne vorhandenen
Fachadapter. Eingegangene Kommunikation ist in diesem Paket eine bereits
tatsächlich einem Projekt zugeordnete Anfrage.

Der begrenzte Worker und HTTP verwenden denselben Kern. Ein gestarteter
Ausführungsanspruch bleibt über Wiederholung, Regeländerung, Neustart und Restore
erhalten. Interne Wirkung und Annahme sind atomar. Ein externer Prozessabbruch
nach dem Claim wird als ungeklärt dargestellt und sendet nicht nochmals.
Wiederherstellung sperrt ungestartete Pläne bis zur erneuten Vorbereitung nach
dem tatsächlichen Betreiberabgleich. Der Finanzhorizont wird durch dieses
Paket nicht verändert, weil keine neue Finanzquelle eingeführt wird.

## Ausgeführte Nachweise

| Prüfung | Tatsächliches Ergebnis |
|---|---|
| Neue Domain, Worker/SQLite-Restore, Registrierungen, unabhängige Gegenfälle und echte MFA/HTTP-Kommandos | 40/40 grün |
| Gemeinsamer Lauf einschließlich bestehendem Assistant, ursprünglichen Kostenquellen, Sprachtransport, lokalem TLS-SMTP und Assistant-HTTP | 75/75 grün |
| Native-/Windows-Quellpakete, einschließlich tatsächlichem Import aus dem erzeugten Archiv | 16/16 grün |
| Neuer PostgreSQL-Lauf mit Parallelität, Runtime-ACL und befülltem Restore | 3/3 grün, echte gebundene Instanz, Laufzeit 10,516 s |
| CLI-Instanzbindung, Worker/Restore und bestehende Zweifirmen-/Speichermarkergrenzen | 19/19 grün, davon zwei neue tatsächliche CLI-Fälle |
| Browser | 557/557 Nodefälle, tatsächlicher Ereignisflow und bestehender Assistantflow grün; unabhängige Kontext-/Claimprüfung dokumentiert |
| Native Oberfläche | 60 neue und 89 bestehende Fälle, zusammen149/149 grün, Analyzer0; tatsächlicher HTTP-Widgetweg enthalten. Unabhängiger Schlussreview läuft separat. |

Die 40 Fälle bestehen aus 11 eigenen Fachfällen, sieben Worker-/Restorefällen,
drei Registry-/Exportfällen, 16 unabhängigen Fachgegenfällen und drei HTTPfällen.
Der gemeinsame 75er-Lauf enthält diese 40; die Zahlen sind nicht zu addieren.
Die Fixture wird vom echten Dispatcher über temporäre synthetische Offices
erzeugt, einschließlich angenommener Ausführung ohne bestätigtes Versandende.

Bestätigte Fehler und enge Korrekturen bleiben nachvollziehbar: bestehendes
Projektverbot für denselben Fachauslöser, geschützte Quellkennung in einem
Scanfehlercursor, Umgehung über die ältere Assistant-Automatik sowie fehlender
Originalnachweis einer Freigabe. Aktuelle Kosten übernahmen früher Kategorien
und Gesamtsumme doppelt; der getrennte additive Kostenfix erhält alte Nachweise
bytegleich und markiert neue Quellen ausdrücklich. Dessen eigenständiger Handoff
ist `CRM_ERP_ASSISTENT_KOSTENSUMME_V2_2026-11-04.md`.

Ein früher Worker-Testlauf verwendete eine nicht abgeschlossene native
Quell-Fixture-Transaktion; die Testquelle wird jetzt wie ein echter Aufrufer
festgeschrieben. Weitere Erstläufe scheiterten ausschließlich an fehlender
lokaler Socketberechtigung, falschem Testimportpfad oder fehlendem isolierten
Interpreterlink. Diese Läufe werden nicht als Produktfehler oder bestandene
Nachweise gezählt. Finale Wiederholungen sind im Evidenzverzeichnis abgelegt.

Der erste PostgreSQL-Lauf deckte einen neuen Funktionsnamen außerhalb der
vorhandenen strengen Ownershippräfixe auf. Nur die neue Guardfunktion wurde
korrekt mit `business_` benannt; die Sicherheitsregel blieb unverändert. Der
zweite Lauf zeigte zwei Testaufbaufehler (Instanz ohne echten Speichermarker
beim Neustart sowie eine noch offene eigene Verbindung vor Restore). Der
finale Lauf verwendet die echte Betreiberbindung und schließt die eigene
Verbindung geordnet. Abschließend wurden ausschließlich `smartplan_check`
und keine weitere Testverbindung festgestellt; kein Restoreziel blieb zurück.

Ein letzter eigener CLI-Gegenfall zeigte, dass der neue Einmalaufruf die feste
Prozesskonfiguration noch nicht gegen die bestehende Unternehmensbindung prüfte.
Der CLI verwendet nun denselben `verify_worker`-Guard wie der vorhandene
Importworker. Falsche Instanz und falscher Host werden vor Scan und Fachaktion
abgewiesen; eine exakt gebundene Konfiguration erzeugt die reale synthetische
Aufgabe. Dieser enge CLI-Fix verändert keine HTTP-/Clientantwort.

## Integrationsstellen

Neue Module: `business_company_events.py`, `company_event_sources.py`,
`company_event_worker.py`; CLI `scripts/process-company-events.py`.
Globale Änderungen betreffen `business_schema.py` und `business_api.py`,
die zwei bestehenden Assistant-Versand-/Ausführungsgates,
`restore.py` und `online/restore.py`, den exakten Unternehmensexportkatalog,
statische Browserdateien sowie die beiden Paketlisten und CI.

Das neue Exportpräfix ist ausdrücklich sensibel und quellenabhängig, ohne
pauschale Aufbewahrungsfrist. Originalrequests bleiben technische Daten;
der portable Unternehmensexport wird nicht als rückspielbare Datenbanksicherung
ausgegeben. Neue Tabellen sind in Runtime nur lesbar und ergänzbar.

Browser- und Nativeowner betreuen ihre neuen Oberflächen, begrenzten Sessionhooks
und jeweiligen Nachweise getrennt. Vor Übernahme in den neueren Hauptstand müssen
Source5, historische Anlagen, Katalog und die gemeinsamen Registrierungen gezielt
zusammengeführt werden; der alte isolierte Baselinebestand darf sie nicht ersetzen.

## Abschließender unabhängiger Native-Nachtrag

Der unabhängige Review ist mit 74/74 gemeinsamen Fällen abgeschlossen
(14 eigene und 60 Ownerfälle einschließlich echtem HTTP); Analyse ohne Befunde.
Der tatsächlich reproduzierte falsche Erfolgsstatus ohne Outcome ist durch einen
engen Readerfix behoben. Vorherige erfolgreiche Ergebnisse bei späterer
Veraltung/Sperrung bleiben lesbar. Rotbelege, Ownerfix und finale Hashes stehen
in `docs/evidence/company-events-native-independent-2026-11-04/manifest.json`.
Die neue Ownerhashliste ersetzt den vorläufigen Native-Stand; Backend und Fixture
sind unverändert. Die Gesamtliste gegen die exakte Basis 4c2f008 wird nach dem
Paketnachlauf erneut erstellt; die Integration in den neueren Hauptstand bleibt
ein separater Schritt.
