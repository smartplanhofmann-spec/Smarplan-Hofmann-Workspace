# Projektmeilensteine: gemeinsame Prüfung vom 09.11.2026

Meilensteine besitzen jetzt einen eigenen Projektbereich in Browser und App:
Titel, Beschreibung, optionaler Termin und Verantwortlicher sowie die manuell
gesetzten Zustände „Geplant“, „Erreicht“ und „Entfallen“. Alte Fassungen bleiben
mit ihren Originalwerten erhalten. Der Status löst keine Rechnung, Zahlung,
Aufgabenerledigung oder rechtliche Abnahme aus.

Die eigenen Tabellen ergänzen das bestehende Schema. Projektaufgaben, Termine,
deren Quittungen und die bisherigen Migrationen bleiben unverändert. Neue
Zuweisungen verlangen ein aktuelles Teammitglied; historische ausgeschiedene
Zuweisungen bleiben nachweisbar. Gleichzeitige und wiederholte Aufträge,
Rechteentzug, Modulpausen und das Schließen einer Ansicht sind berücksichtigt.

| Gemeinsame Prüfung | Ergebnis |
| --- | --- |
| Native Meilensteine, Sitzung, Projektregister, Projektanlage und Offline-Testabschluss | 130 bestanden, kein Skip |
| Vollständiger Browsermodulsatz | 927 bestanden, kein Skip |
| Meilenstein-Backend, Migrations-/Export-/Datenschutzkatalog und HTTP-Vertrag | 23 bestanden, kein Skip |
| Tatsächliche PostgreSQL-Migration, Konkurrenz und Dump/Restore | 2 bestanden, kein Skip |
| Tatsächliche Paketerzeugung und Backendimport | 16 bestanden, kein Skip |
| Echter abschließender Browserablauf | bestanden; MFA, sechs Fassungen, Unicode/CRLF, verlorene Antworten, Rechtewechsel, Konkurrenz und 390px |

Die PostgreSQL-Prüfung erhält alte Tabellen-Fingerprints und Aufgabenoriginale.
Typisierte JSONB-Abfragen finden frühere Verantwortliche und einen nur in einer
Zwischenfassung tätigen Bearbeiter auch nach einer späteren Neuzuweisung.
Diese Quellen bleiben nach Wiederherstellung erhalten. Der verwendete eigene
Datenbankcontainer wurde anschließend entfernt.

Im Browserverlauf stehen verständliche Angaben im Vordergrund; technische
Kennungen und Hashes bleiben im aufklappbaren Originalnachweis zugänglich.
Unveränderte Texte behalten auch bei einer reinen Statusänderung ihre CRLF-
Zeilenenden. Native Wiederöffnungsrennen verwenden die ursprüngliche
Auftragskennung und können keine zweite Anlage auslösen.

[Quellbindungen und Rohprotokolle](evidence/project-milestones-integration-2026-11-09/verification.json),
[Backendvertrag](CRM_ERP_PROJEKTMEILENSTEINE_2026.md),
[Browsernachweis](CRM_ERP_PROJEKTMEILENSTEINE_BROWSER_2026.md) und
[nativer Nachweis](../app/test/evidence/project_milestones_20261109/manifest.json).
Prüfgruppen überlappen; daraus wird kein Fertigstellungsprozentsatz berechnet.

Die zwei CI-Testfehler des älteren veröffentlichten 3859a1c sind zusätzlich
lokal korrigiert: Der Windows-Test wartet auf den verschlüsselten Schreibabschluss;
die Jahresarchiv-HTTP-Tests auf die vollständige Ausgabe und den UI-Zustand.
Die ursprünglichen Fehlerprotokolle bleiben erhalten. Eine neue Remoteprüfung
und Server-/Geräteinstallation sind separate Nachweise. Die zusätzlich
reproduzierte Offline-Firmenisolationslücke wird im nächsten eigenen Abschnitt
behoben; diese Meilensteine schließen nicht das gesamte CRM-/ERP-Ziel ab.
