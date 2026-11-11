# Verbindlicher aktueller Arbeitsstand

Stand: 11.11.2026. Der aktive Auftrag bleibt die vollständige CRM-/ERP-Software
nach Nutzerauftrag und unveränderter `CRM_ERP_Gesamtziel.txt`. Ein abgeschlossener
Lieferabschnitt ist keine Verkleinerung des Gesamtziels und beendet den Auftrag nicht.

## Aktive Fortsetzung: Auslagenoriginale über Mitarbeiter hinweg

Die [zusätzliche Auslagenkorrektur](CRM_ERP_AUSLAGEN_ORIGINALSPERRE_2026-11-11.md)
schließt eine tatsächlich reproduzierte doppelte Einreichung desselben bereits
erstatteten Originals durch einen zweiten Mitarbeiter. Einreichung, Freigabe,
Erstattung und neue Reiseabrechnung prüfen die Unternehmensbindung. Unbezahlte
Freigaben lassen sich begründet und mit unveränderter Historie zurücknehmen,
bedienbar in Browser und App mit eigener Serverfähigkeit.

80 betroffene Backend-/Reisefälle und drei tatsächliche PostgreSQL-/MFA-/
Konkurrenz-/Komplettrestorefälle bestehen. Zwölf native Personalprüfungen und
die vollständige Appanalyse bestehen. Alle 1.120 Browsermodulfälle und der
finale tatsächliche Browserablauf bestehen. Die ursprüngliche Fehlerprobe
besteht unverändert; Ziel und 64 Lohnmodule sind bytegleich. Gemeinsamer
Remote-Nachlauf wird getrennt ergänzt. Eigene Arbeitskopie:
`/tmp/smartplan-expense-originals-20261111`; Hauptprojekt bleibt unverändert
unter dem nachstehenden kanonischen Pfad. Die früheren ab6b615-Paketnachweise
belegen ausschließlich ihren damaligen Funktionsstand.

Die automatische Freigabeprüfung hat den TestFlight-Start auf Grundlage von
„Ok. Mach fertig“ abgelehnt, weil die konkrete App-Übermittlung an Apple darin
nicht ausdrücklich genug benannt ist. Keine Ausführung dieses abgelehnten
Starts. Die neu konkret gestellte Uploadfrage ist weiter unbeantwortet;
Upload bleibt false. Die neue Auslagenfunktion ist nicht vom abgefragten
älteren ab6b615-Funktionsstand umfasst.

## Projekt, Quelle und zulässige Veröffentlichung

- Hauptprojekt: `/workspace/Smarplan-Hofmann-Workspace`, lokaler Branch
  `codex/factor-transition-periods-20261110`.
- Einziger autorisierter Veröffentlichungsbranch:
  `codex/testupdate-0.7-projects-20261104` im bestehenden GitHub-Repository.
  Kein Force-Push und keine Änderung des Standardbranches daraus ableiten.
- Aktueller veröffentlichter Produktquellstand:
  `3c824c174ec6247d50219a70612ba42fed75d017`; eigener gemeinsamer Nachlauf
  42966124379 und iPhone-Läufe 42966124295/42966356463 laufen. Die signierte
  Vorbereitung verwendet ausdrücklich `upload_to_testflight=false`.
- Zuletzt vollständig abgeschlossener vorheriger Plattformnachweis:
  `ab6b61535a35f8306bbf04ebe6557acdb2ac3f41`.
- Originalziel: 23.863 Bytes, SHA256
  `a4dea28f6de4afd3e36d1549441aad91ce16dad374f56097979cc2d79b07fbf5`.
  Original und 63 historische Lohnmodule sind gegen 4aa0abd bytegleich geprüft.
- Eigene RV-Arbeitskopie: `/tmp/smartplan-minijob-rv-20261110`, Branch
  `codex/minijob-rv-lifecycle-20261110`. Der frühere Workspacepfad ist ein
  Kompatibilitätslink. Die geprüfte Verlagerung hat alle 2.335 Einträge erhalten.

## Abgeschlossene gemeinsame Developmentprüfung des aktuellen Codes

Der korrigierte RV-Stand besteht alle 20 eigenen Developmentgruppen in Lauf
42923602362: 2.225 Backendfälle in 1.023,039 Sekunden mit drei ausgewiesenen
Auslassungen, 2.033 Linux-Apphauptfälle plus drei native PDF-Fälle, 1.119
Browsermodulfälle, sechs wirkliche Browser- und sechs PostgreSQL-/API-Gruppen,
Runtime/MFA, Isolation, HTTPS, Update und Restore. Die beiden im Backendlauf
mangels Test-DSN ausgelassenen PostgreSQL-Gegenfälle bestehen getrennt in der
tatsächlichen PG-Gruppe. Der dritte Fall benötigt Windows und ist im dortigen
portablen Backendprüfumfang enthalten.

Windows besteht mit 1.988 Apphauptfällen, drei nativen PDF-Fällen und 81 portablen
Backendfällen. Tatsächlicher Releasebau, Paketierung, Start/Sicherung/Restore
und das getrennte Onlinepaket sind erfolgreich. Die Paketmetadaten und
verlustfreien Rohlogs liegen unter
`docs/evidence/minijob-rv-lifecycle-2026-11-10/`.

Der zusätzliche Lauf besteht 22 Paket-/Archivfälle in 17,556 Sekunden.
Darin prüft das tatsächliche ab6b615-Commitarchiv nach MFA seinen Quellmarker,
die neue RV-Fähigkeit und die Browser-Einstiegsdateien. Nach dem Einfrieren wurde kein Runtimecode verändert.
Appanalyse ohne Befund. [Genauer RV-Umfang](CRM_ERP_MINIJOB_RV_INTEGRATION_2026-11-10.md).

Der erste Kandidat 51c404b bleibt nicht freigegeben: Sein eigener Lauf endet
mit 17 erfolgreichen und drei roten Gruppen. Die Altbelegregression ist durch
9a20836 behoben; eine gesonderte Nullsekunden-Testeingabe für Betriebsmittel
ist in ab6b615 korrigiert. Beide Ursachen sind im neuen gemeinsamen Lauf
nachgeprüft. Fehlgeschlagene Erstlogs werden nicht nachträglich umgedeutet.

Ein weiterer tatsächlicher PG-/MFA-/Konkurrenz-/Geld-/EÜR-/Export-/
Komplettrestorefall besteht in 44,962 Sekunden am unveränderten Produktcode:
581,29 EUR Netto plus 209,66 EUR Abführung ergeben 790,95 EUR EÜR-Aufwand ohne
Vorsteuer. Quittungen und Exporte bleiben nach Restore exakt erhalten. Eigener
Container nach voller ID/Label/Loopback-Port entfernt; kein externer Fachnachweis.

## Eigene iPhone-Auslieferung vollständig technisch geprüft

Der manuelle Lauf 42924966961 besteht mit beiden Jobs. Signiertes Paket 216,
Artefakt 13815294262, 30.028.710 Bytes, ist vorhanden; endgültige Signatur-/Team-/
Keychain-Prüfung und Schlüsselbereinigung sind erfolgreich. TestFlight-Schritt
ist ausgelassen. Die tatsächliche Vorprüfung bestätigt 2.028 Apphauptfälle plus
drei native PDF-Fälle mit fünf ausgewiesenen Linux-Auslassungen.

Der automatische Lauf 42923602365 meldete zunächst nach 53 Minuten einen
Runnerkontaktverlust. Dessen zugrunde liegende Ursache ist nicht weiter belegt;
ein vollständiges Joblog fehlt. Dieser erste Versuch bleibt als Fehler erhalten.
Die gezielte unveränderte Wiederholung im Versuch 2, Job 130229438142, besteht
vollständig einschließlich derselben App-/PDF-Fälle, Gerätebuild und Paketprüfung.
Automatisches unsigniertes Paket 215, Artefakt 13817987677, ist vorhanden.

Alle drei eigenen Läufe sind nach tatsächlich abschließend beobachteter
Laufkennung exakt an ab6b615 gebunden. Nach dem Einfrieren wurde kein Runtimecode
geändert. Der [Lieferstand](CRM_ERP_LIEFERSTAND_AKTUELL.md) enthält die tatsächlichen
Paketmetadaten, Digests, Erstfehler und die konkrete Serveranleitung.

Nächste notwendige Betriebsschritte: geschützten Serverzugang beziehungsweise
vorbereitete Windows-SSH-Befehle verwenden, tatsächlichen Installationsstand
abgleichen und reale Geräte-/Fach-/Sicherheitsabnahmen durchführen. TestFlight
ist noch nicht freigegeben: Für den konkreten geprüften Funktionsstand ab6b615
mit fertiger signierter Vorbereitung 216 ist eine eigene Frage gestellt. Erst
auf eine ausdrückliche passende Antwort handeln; keine Antwort ist keine
Freigabe. Eine ältere offene Frage zu Paket 210/29b02c8 gilt nicht für diesen
neuen Funktionsstand. Bislang nur `prepare_signed_ipa=true`,
`upload_to_testflight=false`; kein tatsächlicher Upload ist erfolgt.

## Gesamtziel, Nutzerentscheidungen und tatsächliche Grenzen

Deutschland/EUR, Einzelunternehmen/EÜR, Regelbesteuerung/Ist, Standard 19 %, SKR04,
Nettopreise; reguläre Mitarbeiter und gewerbliche Minijobs. Die frühere Reihenfolge
Projektbetrieb zuerst hat Buchhaltung und Lohn nicht aus dem Gesamtziel gestrichen.

Gewählte Banken: Qonto, Kreissparkasse Rottweil, Amex Business-Karte. Lieferanten:
Granzow, Alexander Bürkle, Loxone, Voltus. Tatsächliche Providerzugänge und
Anbieterdateien sind nicht vorhanden. Loxones Hostfreigabe ist vom Nutzer
explizit auf später verschoben; nicht erneut als unbeantwortete Frage behandeln.
Keine echte Bank-/Lieferantenverbindung oder Herstellerfreigabe behaupten.

Letzte bestätigte Serverinstallation: a93cb4d02eab610e5f2a8b07fbd1ee51ae99c3e5,
Nutzerbestätigung vom 05.11. Hier fehlen SSH-Schlüssel, Agent und konfigurierte
Remoteidentität; der Serverhost ist in der Cloud nicht freigegeben. Kein neuer
Serverupdate ist ausgeführt. Die bekannte Windows-SSH-Verbindung und der
kontrollierte Updateweg werden im konkreten Lieferpaket beibehalten.

Alle 34 realen Gerätefälle bleiben ungeprüft; die ursprünglichen 31 Zeilen sind
bytegleich erhalten. Keine Fach-/Sicherheitsprüfung oder Gesamtabnahme A–G ist
ersetzt. Keine echten Zahlungen, Meldungen, Nachrichten oder produktiven
Migrationen aus dem Entwicklungsauftrag ableiten.

Die [Anforderungsmatrix](CRM_ERP_ANFORDERUNGEN.md), der
[Umsetzungsplan](CRM_ERP_UMSETZUNGSPLAN.md), das
[Fortschrittsprotokoll](CRM_ERP_FORTSCHRITT.md) und das
[Benutzerhandbuch](CRM_ERP_BENUTZERHANDBUCH.md) bleiben maßgeblich. Weitere offene
Code- und Fachfälle, insbesondere die dort beschriebenen Source5-Gruppen,
Offline-Altbestände und weiteren Lohnumfänge, sind nicht pauschal extern erledigt.
Nicht unterstützte Fälle bleiben gesperrt. Für die zusätzliche gleichzeitige
Source5-Gruppe fehlt weiterhin die verifizierte fachliche Gruppierungsgrundlage;
weitere tatsächlich geöffnete amtliche Ansichten liefern 503. Keine Regel raten.

Der [unverändert archivierte vorherige Arbeitsstand](CRM_ERP_ARBEITSSTAND_VOR_RV_ABSCHLUSS_2026-11-10.md)
erhält sämtliche früheren Abschnitte samt damaligen Quellen und Grenzen.
Der vorherige V16-Paketnachweis zu 4aa0abd bleibt im
[unveränderten Lieferarchiv](CRM_ERP_LIEFERSTAND_V16_VOR_RV_2026-11-10.md) erhalten.
Die gesamte Software ist weiterhin nicht vollständig produktiv freigegeben.
