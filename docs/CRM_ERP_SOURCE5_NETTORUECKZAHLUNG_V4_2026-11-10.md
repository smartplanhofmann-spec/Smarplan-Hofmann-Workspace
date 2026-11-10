# Source5 V4: belegte tatsächliche Netto-Rückzahlung

**Aktueller Folgeabgleich:** Der unten historisch offene weitere positive,
negative oder betragsgleiche Abschluss ist inzwischen als
[V5-Nettoausgleich](CRM_ERP_SOURCE5_NETTOAUSGLEICHE_V5_2026-11-10.md) implementiert
und in Backend, Browser, App sowie tatsächlichem PostgreSQL/Restore geprüft.
V5 ist im geprüften Produktstand 29b02c8 samt eigenen erfolgreichen
20 Developmentgruppen und signiertem iPhone-Paket 210 enthalten.
Der historische Restabsatz wird dadurch zeitlich eingeordnet, nicht gelöscht.

Der abgegrenzte neue Fall ist in Backend, Browser und App implementiert und
getestet. Er wird getrennt von der produktiven Gesamt-/Fachfreigabe geführt.
Er ergänzt eine tatsächliche Beschäftigtenrückzahlung zu einem bereits
angenommenen korrigierten Einzelbonuslauf mit unverändertem Bruttoereignis.
Die veröffentlichten V1-/V2-/V3-Verträge und 32 historischen Rechenmodule bleiben
erhalten. Neue Steuersätze, Bruttoereignisse und behördliche Erstattungen werden
nicht aus dieser Zahlungsänderung abgeleitet.

Die neue Vollständigkeitsprüfung trägt schema_version:2 und
contract:source5_actual_net_repayment_review_v1. Im Browser und in der App wird
die Rückzahlungsrichtung ausdrücklich gewählt; vollständige Zahlungen und
Abführungen einschließlich externer Vorgänge benötigen weiterhin zwei bewusste
Bestätigungen und ein aktuelles privates Original. Der versionierte Übergang
source5_net_repayment_v1 bindet die letzte tatsächliche Zahlung, den aktuellen
korrigierten Lauf, den bisherigen Abführungspräfix und eine negative genaue
net_delta_minor. Nur das unveränderte laufende Netto und ein nichtnegatives
verbleibendes Bonusnetto werden unterstützt.

Der Lohnkontonachweis verwendet payment_source_schema_version:4 und
source5_actual_net_repayment_v4. Alle früheren positiven V1-/V2-/V3-Zahlungen
und ihre geordneten Zuordnungen bleiben unverändert. Neue Teile sind negative
Centbeträge ausschließlich desselben Bonusereignisses, mit eindeutigem Original
und wirklichem Tag im Jahr 2026. Sie dürfen weder vor dem bisherigen Präfix
noch nach dem heutigen Tag liegen. Ihre Summe erfüllt exakt die nachgerechnete
Rückzahlungsverpflichtung. Die Geldflussübernahme wählt nur neue Teile: ein
positiver Eingang vermindert die Lohnausgabe in der EÜR. Kein Geld wird eingezogen.

Browser und App zeigen Rückzahlung, ursprünglichen Bruttozufluss und tatsächliche
Geldtage getrennt. Die früheren Teile sind nicht editierbar. Neue Beträge werden
bewusst mit negativem Vorzeichen eingegeben. Aktuelle Personal-/Fachrechte,
aktiver Monatsgruppenbereich und das neue Feature payroll_source5_net_repayments
sind vor Annahme erforderlich. Unbestätigte ursprüngliche Lauf-/Zahlungsaufträge
werden nach verlorener Antwort unverändert wiederholt. Rechteentzug blockiert
neue Annahmen; zugängliche historische Originale bleiben unter ihren Regeln.

Die Jahresbasis liest die vollständig aufgelöste neue Zahlungsfassung. Ein
positiver ursprünglicher Bonusnachweis am Bruttoereignistag bleibt nötig; alle
späteren Nettofakten müssen bis zum Stichtag vorliegen. Der ursprüngliche
500-EUR-Bonus wird nur einmal in der Jahresprojektion gezählt. Das bestehende
kompakte Referenzformat bleibt unverändert; die neue Zahlung ist ausdrücklich
versioniert. Die gemeinsam entwickelte V3-Folgekorrektur b437f2c erhält zugleich
bereits bestätigte spätere Bonuspräfixe und ihre ursprüngliche Jahreszuordnung.

Tatsächliche Ergebnisse am 10.11.:

- 50 neue/historische Backendfälle bestehen in 373,767 Sekunden, darunter
  Rückzahlung, unveränderter Ursprung/PDF, alte Vertragsgrenzen, falsche Tage,
  Versionen und Beträge sowie das Verbot eines neuen Rückzahlungsreviews im
  alten positiven Übergang. Alte Lohn-/Reise-/Jahresfälle bleiben unverändert.
- 1.026 Browsermodultests bestehen ohne Skip. Der echte Chromium-/MFA-/HTTP-
  Bedienablauf über die neue ausdrücklich gewählte Richtung besteht mit
  privatem Vorarbeitgeberoriginal, angenommenem korrigiertem Lauf, tatsächlicher
  negativer Nettozahlung, verlorenen Lauf-/Zahlungsantworten und identischen
  Wiederholungsaufträgen. Die 390-Pixel-Ergebnisanzeige wurde visuell geprüft.
  Keine angenommenen Finanzantworten werden für diesen Ablauf erfunden.
- Die vollständige App-Suite besteht mit 1.878 sichtbaren Fällen ohne Skip;
  der maschinenlesbare Endsatz bestätigt success:true nach 693.950 ms.
  14 gezielte V2-/V3-/V4-Bedien-/Vertragsfälle und die Analyse ohne Befund
  ergänzen dies. Der Testimport ohne Verwendung wurde entfernt und die Analyse
  erneut ausgeführt. Die Produkt-Dartdateien bleiben dabei unverändert.
- 21 tatsächliche Paket-/Inventarfälle bestehen in 15,980 Sekunden. Der neue
  lokale Backendbaustein ist in der einen kanonischen Paketliste enthalten;
  das Browsermodul wird über die explizite statische HTTP-Liste ausgeliefert.
- Die echte gebundene PostgreSQL-/MFA-Kette besteht mit separaten Produktions-
  rollen, ursprünglichem CRLF-Lohnlauf, V3-Vorzahlung, V4-Rückzahlung, EÜR,
  einmaliger Jahresprojektion, privaten Technikergrenzen und pg_dump/pg_restore.
  PDF, Zahlungs-/Geldfluss-/Jahresquittungen und EÜR-Summen bleiben nach Restore
  unverändert. Der einzelne erfolgreiche Vorlauf dauert 562,836 Sekunden.
  Im späteren Zweifalllauf in 623,387 Sekunden besteht dieser Restorefall erneut;
  dessen Konkurrenzfall scheitert zunächst an der bestehenden Zehnsekundensperre.
  Der fehlerhafte Gesamtlauf bleibt ausdrücklich erhalten.
- Nach gezielter Sperrfehlerbehandlung bestehen Konkurrenz und deterministische
  HTTP-Sperrprüfung gemeinsam als zwei Fälle in 83,502 Sekunden. Beobachtet sind
  zwei gleiche angenommene Quittungen bei genau einem gespeicherten Auftrag;
  Rollenentzug und erneute echte MFA werden geprüft. Der separat gehaltene
  Datenbanklock bestätigt die Beschäftigt-Antwort und saubere Verbindung.

Die PostgreSQL-Transaktionshülle behält ihre zehnsekündige Sperrgrenze und das
bereits vorhandene Aufräumen bei fehlgeschlagenem Eintritt. Neu ist die gezielte
Übersetzung von LockNotAvailable beim Erwerb der globalen Schreibsperre in
Status423 mit verständlicher Wiederholungsnachricht. Sie behauptet niemals,
der ursprüngliche Auftrag sei nicht angenommen worden: Auch ein zeitweise
blockierter Retry könnte eine früher angenommene Operation betreffen.
Ein deterministischer tatsächlicher MFA-/HTTP-Fall hält die Sperre, verkürzt
nur seine eigene Testverbindung auf 100ms und bestätigt Rollback, keinen neuen
Datensatz, keinen falschen request_resolution-Wert und den späteren Auftrag.
Produktive Zeitgrenzen werden nicht erhöht; SQL-/Verbindungsdaten gelangen
nicht in die Fehlermeldung. Der entsprechende erste Einzelfall besteht in
3,166 Sekunden. Die neue gemeinsame Prüfung behält zusätzlich tatsächliche
konkurrierende Schreiber und die eindeutige Originalannahme bei.

Vorläufe bleiben als Nachweise erhalten: unbekannter neuer Reviewvertrag,
Reisemonatsgrenze auf bereits belegtem V3-Präfix, ursprüngliche Gleichdatums-
prüfung der Jahresbasis, fehlende statische Browserdatei, isolierter Node-
Dateirahmen und der echte PG-Sperrzeitfehler. Der Dateirahmen zählt nicht als
zwei ausgeführte Fachfälle; der explizite Nachlauf bestätigt beide Einzeltests.
Alte positive Regeln oder Prüfungen wurden für diese Fehler nicht aufgehoben.
Der ausschließlich eigene markierte PostgreSQL-Container ist nach den Prüfungen
entfernt; andere Container und Livebetrieb wurden nicht verändert.

Noch offen ist der weitere positive, negative oder betragsgleiche Abschluss
nach einem bereits abgeschlossenen V4-Rückzahlungspräfix. Dieser braucht einen
eigenen gemischten Nettoausgleichsvertrag und bleibt konkrete folgende
Codearbeit. Mehrere Bonusgruppen, andere Brutto-/SV-Zuordnungen, Jahreswechsel,
allgemeine steuerliche Rückwirkung und behördliche Erstattungen bleiben eigene
Fälle beziehungsweise Fachnachweise. Dieser Abschnitt führt keine Meldung,
Überweisung, Liveinstallation, Signierung oder produktive Gesamtfreigabe aus.

Produktcode 749a19d6f42ece098c70fe494ebae97abb3d87f8 ist auf b437f2c eingeordnet. Alle 14 geprüften Laufzeitdateien sind nach dem Rebase bytegleich; der zusätzliche V3-PG-Jahresfall und beide Fortschrittseinträge bleiben erhalten. [Quellhashes, Rohläufe, vollständiger App-Bericht und Grenzen](evidence/source5-repayment-2026-11-10/manifest.json).
