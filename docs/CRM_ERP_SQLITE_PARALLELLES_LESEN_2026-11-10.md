# Verlässliche gleichzeitige Lesezugriffe auf die lokale Datenbank

Der tatsächliche Browserjob129611954657 auf 936f40f scheitert beim Öffnen des
Lagers nach einer Teillieferung mit HTTP500. Die Diagnose führt zu
`business_schema.state`: Kontrolltabellen fehlen im gerade gelesenen Ergebnis.
Der Originalfehler bleibt im V4-Veröffentlichungsnachweis erhalten.

Die isolierte Reproduktion mit der tatsächlichen `Office`-SQLite-Verbindung
unter Python3.12.14 enthält keinerlei Änderungen der Tabellen oder Daten:
acht gleichzeitige Leser führen dieselbe Schemaabfrage aus. Sechs Leser sehen
unvollständige/vergrößerte Ergebnismengen statt der unveränderten 328 Tabellen;
mehreren fehlen dabei dieselben Kontrolltabellen. Der erste eigenständige
Regressionstest scheitert außerdem an einer leeren Ergebniszeile (`IndexError`).

Die gemeinsame lokale Verbindung verwendet jetzt `cached_statements=0`.
Damit werden vorbereitete SQLite-Abfragen nicht zwischen gleichzeitig aktiven
Lese-Cursorn wiederverwendet. Schema- und Integritätsprüfungen, Sperren,
Transaktionen, Rechte und Archivschutz bleiben vollständig aktiv. Die
PostgreSQL-Verbindung wird nicht geändert.

Tatsächliche Nachweise:

- Neue Threadprüfung: 2.400 echte Schemaabfragen mit acht Lesern, alle Zeilen
  und Kontrolltabellen exakt erhalten; ein Fall/2,820s.
- Gemeinsame Schema-, Inventar-, Bestell-, Liefer- und Zählprüfungen samt neuer
  Threadprüfung: 77 Fälle/25,842s erfolgreich.
- Echter isolierter Browser mit Test-MFA: Bestellvorschlag, Freigabe, tatsächliche
  externe Bestellung, Teil- und Restlieferung, verlorene Bestätigung und genau
  eine Lagerbuchung sowie mobile Ansicht erfolgreich. Der bestehende Ablauf
  ist zusätzlich direkt als `purchasing-receipts` auswählbar.

[Manifest, ursprüngliche Fehler und Rohläufe](evidence/sqlite-shared-reads-2026-11-10/manifest.json).
Der vollständige Remote-Nachlauf des neuen Quellstands bleibt gesondert
erforderlich. Keine neue Serverinstallation oder vollständige Gesamtabnahme.
