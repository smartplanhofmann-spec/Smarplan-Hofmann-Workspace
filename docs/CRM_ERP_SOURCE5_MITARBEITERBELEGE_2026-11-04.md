# Eigene Mitarbeiterbelege für den einzelnen Source5-Anspruch

Stand 04.11.2026, isolierter Clientbaum. Die eigene Mitarbeitersicht unterstützt den vollständig geprüften einzelnen Source5-Anspruch mit `schema_version=4`. Browser und native App zeigen nur eigene Beträge, Zeiträume sowie Steuer- und SV-Zuordnungsjahr. Die Darstellung ist weiterhin eine Berechnung; ein tatsächlich erfolgter Zahlungseingang wird dadurch nicht behauptet.

Die Projektion verwendet eine positive Liste auch in verschachtelten Strukturen. Anspruchs- und Ereigniskennungen, Jahresprognosen, Quellenoriginale, steuerliche Vergleichsrechnungen, Zuordnungsreferenzen und private Zahlungszuordnungen werden nicht ausgegeben. Vor jedem Abruf prüft der Server den tatsächlichen ursprünglichen Lauf, seine angenommene Quelle und den atomaren Verbrauch. Fehlende Verbrauchsquittungen sperren Liste, Detail, Historie, PDF und JSON. Ungeklärte Mehrfachgruppen werden nicht zu eigenen Nettobelegen.

`/payroll/employee-statements/{id}/json` ergänzt den geschützten PDF-Abruf. Beide Formate benötigen die konkrete Revision und den geprüften `statement_hash`; aktuelle Mitarbeiterrechte werden vor und nach der Erzeugung erneut geprüft. Das fertige JSON wird als UTF-8-Anhang übertragen. Browser und native App prüfen seine gesamte enge Struktur, den ausgewählten ursprünglichen Beleg und seine Prüfsumme. Es wird nur kanonisches JSON akzeptiert: Doppelte Schlüssel dürfen keine verborgenen privaten Werte im heruntergeladenen Text hinterlassen.

Beide Clients prüfen Freigabe und Belegfassung vor und nach dem Download. Die native Ansicht verwirft verspätete Antworten nach Rechteentzug, App-Pause oder Tokenwechsel. Der Browser verwirft Antworten eines inzwischen geschlossenen oder ersetzten Dialogs. Die bisherigen Belegfassungen 1, 2 und 3 und ihre bestehenden PDF-Dateien bleiben unverändert.

Nachweise:

- Backend einschließlich echtem lokalem HTTP, privatem Quellenzugriff, Rechteentzug während der Erzeugung und eingefrorenen alten PDFs: **26/26 grün**.
- Browservertrag für alle vier Belegfassungen einschließlich privater Zusätze, ungültiger Versionsbindungen und vollständigem JSON-Abgleich: **12/12 grün**.
- Native Verträge und Widgets einschließlich 390-Pixel-Ansicht, JSON-Export, historischer Navigation, Rechteentzug und verspäteter Antworten: **16/16 grün**. Gezielte statische Analyse ohne Befund.
- Der echte integrierte Source5-Browserablauf ist vollständig grün, einschließlich reduziertem Schema-4-Beleg, eigenem PDF/JSON, Ausschluss privater Originalkennungen, historischer Navigation und 390-Pixel-Ansicht. Protokoll: `work/verification/source5-browser-final-second-2026-11-04.log`. Ein Timingfehler im Testhelper wurde durch das sofortige Lesen der tatsächlich empfangenen HTTP-Antwort behoben; die Produktschnittstelle blieb unverändert.

Echte synthetische Quelldaten und unabhängig erzeugte PDF-/JSON-Dateien liegen in `app/test/fixtures/payroll_statements_v7.json`; der Generator ist `scripts/generate-payroll-multiple-statement-fixture.py`. Protokolle, ursprüngliche Fehlversuche und Dateihashes: [Prüfnachweis](evidence/source5-own-statements-2026-11-04.json). Die anfangs fehlerhafte JSON-MIME-Behandlung und ein falscher Zugriff auf die ältere Fixturehülle sind korrigiert; ihre Logs bleiben erhalten.
