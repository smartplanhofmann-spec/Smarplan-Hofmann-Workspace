# Belegte Bestelländerungen und Lieferantenretouren

Stand: 03.11.2026. Der abgegrenzte Einkaufsumfang zu R07.02 ist implementiert
und in Domain, HTTP, PostgreSQL/Restore sowie beiden Clients geprüft. Dieser
Nachweis beschreibt den technischen Entwicklungsstand. Eine reale Rücksendung,
eine Lieferantengutschrift oder ein produktiver Betriebswechsel wird dadurch
nicht ausgelöst oder bestätigt.

Der genaue [API-Vertrag](CRM_ERP_EINKAUF_RETOUREN_API.md), die
[Clientabläufe](CRM_ERP_EINKAUF_RETOUREN_CLIENTS.md) und die
[unabhängige Gegenprüfung](CRM_ERP_EINKAUF_RETOUREN_GEGENPRUEFUNG.md) gehören
zu diesem Nachweis. Der [ursprüngliche Entwurf](CRM_ERP_EINKAUF_RETOUREN_ENTWURF.md)
bleibt als Herleitung erhalten.

## Tatsächlicher Fachumfang

Die ursprüngliche Bestellung und jede bisherige Lieferung bleiben erhalten.
Eine belegte Mengenänderung legt eine neue kumulierte Bruttolieferfreigabe pro
ursprünglicher Position fest. Artikel, Einheit, Lieferant und Projekt werden
nicht ausgetauscht. Die Freigabe kann nie unter die bereits empfangene Menge
fallen. Eine Reststornierung setzt sie genau auf die empfangene Menge;
eine ausdrücklich vereinbarte Ersatzlieferung erhöht sie. Der bestehende
Wareneingang prüft anschließend die aktuelle Änderungsrevision.

Eine Lieferantenretoure bindet die konkrete ursprüngliche Wareneingangsposition
und deren Eingangslager. Die zulässige Menge ist durch bereits retournierte
Mengen, an Geräte gebundene Herkunft und tatsächlich freien Lagerbestand
begrenzt. Mehrere Positionen desselben Artikels teilen sich diesen Bestand;
Reservierungen bleiben wirksam. Eine Rücksendung allein schafft keine weitere
Lieferfreigabe.

Das neue kanonische Rücksendejournal vermindert Bestand und gewichteten Lagerwert.
Es wird in der tatsächlichen Reihenfolge mit nativen Lagerbewegungen und
Inventurkorrekturen ausgewertet. Jede Rücksendezeile bindet sowohl die vorherige
Bewegungs- als auch die Inventursequenz. Spätere Einkaufspreise oder Inventuren
bewerten die ursprüngliche Quittung nicht neu. Projektkosten entstehen weiterhin
aus den tatsächlich zugehörigen Entnahmen; eine Lieferantenretoure ist keine
zusätzliche Projektentnahme. Finanz-, Bank- und EÜR-Journale ändern sich dadurch
nicht automatisch.

Änderungen und Rücksendungen benötigen ein unverändertes Original, eine externe
Referenz, ein tatsächliches Datum, einen Grund und die ausdrückliche Bestätigung
der gebundenen Vorschau. PDF/PNG/JPEG/XML bis 2 MiB werden mit Bytezahl und SHA-256
aufbewahrt. Die Anwendung versendet keine Bestellung oder Rücksendung und
erzeugt keine fingierte Zahlung, Gutschrift oder Erstattung.

## Datenhaltung, Rechte und historische Prüfung

`business_purchase_changes.py` ergänzt sechs Tabellen: Mengenänderungen,
Versionsbindung neuer Wareneingänge, Retourenköpfe, Retourenpositionen,
Originalbelege und technische Auftragsquittungen. Neue Tabellen sind anhängend;
SQLite-Guards und PostgreSQL-Runtimeprivilegien verhindern UPDATE/DELETE und
Ersetzung. Die bisherigen Einkaufs-, Lager- und Belegschemata bleiben erhalten.
Unternehmensarchiv und Datenschutzquellen berücksichtigen den neuen Umfang;
technische Auftragsquittungen sind kein zweiter fachlicher Export.

Der tatsächliche Bestellprojektbezug bestimmt die Rechte. Mengenänderungen
verlangen `inventory.read/write` und `finance.approve`; Rücksendungen und
Originaluploads verlangen `inventory.read/write` und `finance.write`.
Finanzwerte und Originalbytes benötigen zusätzlich `finance.read`. Neue
Fachwirkung verlangt ein aktives Materialmodul. Eine bereits angenommene
Quittung bleibt unter frischen Rechten nach einer späteren Moduldeaktivierung
wiederholbar und wird gegebenenfalls preisfrei ausgegeben.

Unklare Antworten behalten ihren exakten Auftrag und dieselbe Anfrage-ID.
Akzeptierte Wiederholungen prüfen die ursprüngliche Eingabe, Normalisierung,
Bestätigung und Originalbindung erneut. Die gesamte historische Bestellansicht
wird aus den damals gebundenen Liefer-, Änderungs- und Rücksendefassungen sowie
Journalgrenzen rekonstruiert. Ein bloß erneuerter Eigenhash einer widersprüchlichen
Quittung genügt nicht. Diese Prüfung schloss zwei tatsächlich reproduzierte
Befunde der unabhängigen Gegenprüfung; deren fehlgeschlagene Erstläufe bleiben
dort ausdrücklich dokumentiert.

## Ausgeführte Prüfungen

| Lauf | Tatsächliches Ergebnis | Wesentlicher Umfang |
| --- | --- | --- |
| Breite Einkaufsregression | 118/118, 28,617 s, kein Skip | Neue Domain-/HTTPfälle, bestehender Einkauf, Lager, Inventur, Geräteherkunft und bestehende Einkaufsjourneys |
| Unabhängige Gegenprüfung | 96/96, 23,397 s, kein Skip | Sieben eigene Gegenproben, 13 neue Domainfälle, zwei HTTPfälle und 74 bestehende Fachfälle; beschädigte Quittungen, gleiche Artikel, Reservierungen, Lagerwechsel und Journalfolge |
| Tatsächliche PostgreSQL-Abnahme nach Reviewkorrektur | 3/3, 13,732 s, kein Skip | MFA/HTTP, zwei konkurrierende Retouren, frische Rechte, Runtime-ACL, alte additive Migration, reales Dump/Restore und unveränderte finalisierte Rechnung/PDF |
| Browser und Flutter | Abgegrenzt bestanden | 17 kombinierte Node-/24 Flutterfälle, Analyse und echter Browser mit Originalupload, verlorener Antwort, Ersatzfreigabe, versionsgebundenem Wareneingang und Reststornierung; genaue Einzelmengen im Clientnachweis |

Die Testmengen überschneiden sich; sie werden nicht addiert. Der nach dem
Backendfreeze angesetzte erneute Browserlauf und die breite Gesamtregression
werden vom Integrationsverantwortlichen separat dokumentiert. Hier wird nur
der bereits vorhandene erfolgreiche Clientnachweis beansprucht.

Permanente Tests liegen in `backend/test_business_purchase_changes.py`,
`backend/test_business_purchase_changes_transport.py`,
`backend/test_business_purchase_changes_review.py` und
`backend/online/test_business_purchase_changes_pg.py`. Die tatsächlichen
Rohprotokolle unter `work/verification/` haben folgende SHA-256-Werte:

- `purchase-changes-regression.log`: `3c2df2954046923ca6627b8f739fd91369f13f66c8978b592ab5aac9ffa89f34`
- `purchase-changes-independent-final.log`: `6b9dc4fa6f6eeb1628ef5aaefd538d5ed121e34fd4d32b921138682c94a83033`
- `purchase-changes-pg.log`: `30a6737351d5669ec8e3d86de1faac0ec94ea36594042c466bf2f9f117aac19b`

Die PostgreSQL-Prüfung verwendet ausschließlich eine ausdrücklich entbehrliche
lokale Datenbank. Vorhandene Rechnungen, PDFs, Lieferoriginale und alte
Wiederholungsquittungen bleiben im geprüften Ablauf unverändert. Lieferanten-
schnittstellen, automatische Einheitenumrechnung, echte Waren-/Geldbewegungen
und die Windows-/iPhone-Geräteabnahme sind eigene, hier nicht behauptete Nachweise.


## Erneuter PostgreSQL-Nachweis nach Rohlogverlust

Der ursprünglich oben dokumentierte erfolgreiche Lauf mit drei Fällen in
13,732 s wurde damals tatsächlich ausgeführt und vor dem späteren Verlust
inhaltlich gelesen. Sein damaliger SHA-256 bleibt als historische Angabe
stehen. Der ignorierte Rohlog `work/verification/purchase-changes-pg.log` wurde
anschließend beim Kopieren eines Testwrappers versehentlich durch einen
fehlgeschlagenen Lohnfakten-Anlauf überschrieben. Er ist nicht mehr als
ursprünglicher Rohbeleg verfügbar; es wurde kein rekonstruierter Log als
Original ausgegeben. Produktquellen und betriebliche Daten waren davon nicht
betroffen.

Die drei Retouren-PostgreSQL-Fälle wurden danach auf der ausdrücklich
entbehrlichen Testdatenbank vollständig erneut ausgeführt: **3/3 bestanden,
13,413 s, kein Skip**. MFA/HTTP, parallele identische Retoure, frische Rechte,
Runtime-/Owner-Guards, alte additive Migration und tatsächliches Dump/Restore
mit unveränderlicher Rechnung/PDF bestehen im neuen Lauf. Der eigenständige
Rohbeleg liegt unter
`work/verification/purchase-changes-pg-recheck-after-log-loss.log`, SHA-256:
`f44c6e38d44e1551f088b6c015e4da0503a8bd774daf645774cb70d48f97e0a8`.
Dieser spätere Nachweis ersetzt die historische Laufzeit/Prüfsumme nicht still.
