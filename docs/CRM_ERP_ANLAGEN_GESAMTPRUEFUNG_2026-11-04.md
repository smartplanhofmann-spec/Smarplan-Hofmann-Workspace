# Historische Anlagen: integrierter Entwicklungsstand

Stand 04.11.2026, auf Basis `8858db4`. Die belegte Übernahme historischer linearer
Anlagen ist mit Browser, nativer App, EÜR und Wiederherstellung zusammengeführt.
Anfangssalden, Katalogoriginale und die Source5-Lohnabläufe bleiben erhalten.

## Fachlicher Umfang

Übernommen werden vollständig betrieblich genutzte bewegliche Anlagen mit
unveränderter belegter linearer AfA. Anschaffungs-/Nutzungsmonat, ursprüngliche
Nutzungsdauer, Kostenbasis, bisherige AfA und Restbuchwert bleiben gebunden.
Ein unterjähriger Beginn berücksichtigt die bereits gebuchte Startjahres-AfA.
Die Übernahme erzeugt keine neue Anschaffung, Zahlung oder Vorsteuer. Die
verbleibende Folge-AfA wird ausdrücklich im EÜR-Journal bestätigt.

Originale, Vorschau, Annahme, Korrektur und Historie sind in beiden Clients
bedienbar. Unklare Speicherantworten verwenden bei Wiederholung denselben
ursprünglichen Auftrag. Geschlossene Perioden und aktive Folge-AfA verhindern
unzulässige Änderungen; Rechte werden bei jedem Vorgang frisch geprüft.

## Tatsächliche Prüfungen

| Prüfung | Ergebnis |
| --- | --- |
| Vollständiges Backend | 1.675 ausgeführt, 1.674 bestanden, ein vorhandener Windows-spezifischer Skip; 825,995 s |
| Browsermodule | 578/578; 13,052 s |
| Vollständige Fluttertests | 1.225/1.225; 565,024 s |
| Flutteranalyse | Keine Befunde; 21,746 s |
| Paketprüfungen | 16/16; 10,502 s |
| Betroffene bestehende Finanz-HTTP-Prüfungen | 49/49; 167,164 s |
| PostgreSQL-Regression | Alle 107 unterschiedlichen Fälle abschließend bestanden, einschließlich dokumentierter Testfixture-Korrektur |
| Zusätzliche befüllte gemeinsame Wiederherstellung | 1/1; 29,669 s; Anlagen, Anfangssalden, Katalogoriginal, bezahlter Source5-Lauf, Anspruch und EÜR-Export |
| Tatsächlicher Chromiumablauf | Anlagen 26,148 s; Source5 45,917 s; unabhängiger verspäteter Dialogaufruf 21,593 s, jeweils bestanden |

Die PostgreSQL-Teststeuerung stoppte zunächst nach 240 Sekunden; 18 Fälle waren
bereits erfolgreich. Die übrigen 89 wurden separat fortgesetzt. Dabei bestand
ein alter Migrationsaufbau irrtümlich aus Anfangssalden/Anlagen ohne deren
Reisekosten-Vorgängermodul. Die Produktprüfung wies diesen inkonsistenten Aufbau
korrekt ab. Nur diese Testfixture wurde auf den tatsächlichen älteren
Modulumfang korrigiert; der betroffene echte Migrations-/Restorefall bestand
anschließend. Die restlichen 88 Fälle des Nachlaufs waren bereits erfolgreich.
Die ursprünglichen Protokolle bleiben unverändert erhalten.

Der [maschinelle Gesamtnachweis](evidence/assets-integrated-regression-2026-11-04.json)
und das [Quellmanifest](evidence/assets-integrated-source-snapshot-2026-11-04.json)
binden Eingaben, Protokolle, den nachträglichen reinen Fixturewechsel und den
finalen Nachlauf. Der gemeinsame Restore verlangt Finanzhorizont 13/Bericht 14;
ein älterer oder nachträglich unvollständig gemachter Bericht schaltet ihn nicht
frei. Der unabhängige Mergecheck bestätigt 122 bytegleiche Handoffdateien und
11 nachvollziehbar zusammengeführte globale Dateien ohne Produktbefund.

## Behobene konkrete Fehler

Unabhängige Gegenfälle haben einen verschobenen ursprünglichen Nutzungsmonat,
eine doppelte Originalposition und einen unvollständig gemachten Restorebericht
abgesichert. Ein später initialer Browseraufruf darf keinen fremden Dialog
überschreiben. Gleichzeitige native Sitzungsabrufe warten jetzt auf denselben
laufenden Abruf; ein verfrühtes Weiterarbeiten wird verhindert. Die erhaltenen
alten Lohn-/Katalog-Replaypfade bleiben geschützt.

## Verbleibende Grenzen

GWG, Sammelposten, Gebäude, Privatnutzung, Methodenwechsel, Sonder-/degressive
AfA und Abgangsautomatik gehören nicht zu diesem linearen Vertrag. Historische
offene Kunden-/Lieferantenposten sind in Umsetzung. Datierte Katalogpreise und
Unternehmensereignisse werden separat integriert. Weitere Steuer-/Lohnfälle,
Steuerberater-/Behördenwege, vollständige Fachprüfung und reale Geräte-/
Betriebsabnahmen bleiben offen. Dieser Checkpoint ist keine Fertigmeldung der
gesamten Buchhaltung oder Software und enthält keine Produktivmigration.
