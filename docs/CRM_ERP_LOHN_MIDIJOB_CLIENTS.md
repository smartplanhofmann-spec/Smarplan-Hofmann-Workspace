# Belegter Übergangsbereich: Browser- und Flutterabnahme

Stand 03.11.2026. Browser und Flutter ergänzen den [Midijob-Rechenumfang 2026](CRM_ERP_LOHN_MIDIJOB_2026.md) im vorhandenen Lohnprofil-/Monatsablauf. Die zusätzliche Wahl wird nicht aus dem Brutto erraten und nicht in bestehende Profile eingefügt.

## Ausdrückliche Prognose und Berechnung

Neue Profile verlangen die ausdrückliche Beurteilung des Übergangsbereichs. Die Wahl „Keine belegte Übergangsbereichsprognose“ behält den bisherigen Berechnungsumfang. Die neue Vollmonatswahl verlangt reguläre Beschäftigung, vollständige ausdrücklich eingetragene Steuermerkmale und alle sechs Prognoseangaben: dokumentierter Status, Prüfdatum, regelmäßiges Monatsbrutto, ausdrücklich gewählter Zwölfmonatszeitraum, Ja-/Nein-Angabe vorhersehbarer Einmalzahlungen und Prüfvermerk. Das bereits ausgewählte geschützte Personaloriginal muss die Prognose und Versicherungsmerkmale belegen.

Die Clients prüfen den Prognosebereich von 603,01 bis 2.000,00 € und den centgenauen Zusammenhang mit dem Jahresbrutto. Unbekannte Datums-/Entgelt-/Einmalzahlungswerte bleiben leer. Vorhersehbare Einmalzahlungen dürfen wahrheitsgemäß dokumentiert werden; der entsprechend gesperrte Lauf zeigt kein vermeintliches Netto und keine berechneten Bemessungsgrundlagen.

Der vollständige Scope `regular_transition_monthly` zeigt PAP-Steuern, Arbeitnehmer-/Arbeitgeberbeiträge und Netto sowie die prognostische Monatsgröße, Faktor 2026, getrennte Gesamt-/Arbeitnehmergrundlagen jedes Beitragszweigs, Umlagebasis und PV-Zuschlag/Kinderabschläge. Das tatsächliche Monatsentgelt wird ausdrücklich als innerhalb, bis zur unteren oder oberhalb der oberen Grenze angezeigt. Der belegte Status wechselt bei einem schwankenden tatsächlichen Entgelt nicht automatisch zum Minijob.

Korrekturen binden die aktuelle Profil-/Monatsquelle, unveränderten Originalauftrag und vollständige Steuer-/Beitragsdifferenz. Der neue Scope wird auch in Monatsverlauf und Jahresübersicht validiert; nur die wirksame neueste Fassung trägt zu den Jahressummen bei. Frühere Profile, Laufquittungen und PDF-/JSON-Exporte bleiben unverändert.

## Ausgeführte Prüfungen

Sämtliche Personen, Originale, Verträge und Entgelte sind synthetisch. Es wurde weder überwiesen noch amtlich gemeldet.

| Nachweis | Ergebnis | Umfang |
|---|---:|---|
| Node: Übergangsbereich und vorhandene Payroll-/Kontonachweis-/Cash-Verträge | 37/37 | Atomare Prognose, leere Pflichtangaben, kein automatischer Status, tatsächliche Unter-/Überschreitungen, gesperrte Einmalzahlung, manipulierte Bemessung/PV abgewiesen, exakte Korrekturen und Jahressummen; bestehende Fälle bleiben gültig |
| Flutter: Übergangsbereich und vorhandene Payroll-/Kontonachweis-/Cash-Fälle | 41/41 | Entsprechende Fachbindungen, Replay-/Rechtefälle, native 390px-Ansicht mit tatsächlichem Scrollen und Öffnen der Beitragsgrundlagen, Daten werden bei Rechteentzug ausgeblendet |
| Flutter Analyze | Ohne Befund, 5,6 s | Finaler integrierter App-Quellstand |
| Echter Chromium: `payroll-transition` | Bestanden | MFA/HTTP, vollständige Prognoseeingabe, verlorene Profil- und Laufantwort mit identischen Originalwiederholungen, 1.000,00 € Brutto → 874,67 € Netto, belegte Elternschaftskorrektur → 881,21 € Netto, 6,54 € Differenz ohne geänderten Arbeitgeberbeitrag, unverändertes altes PDF, aktuelle Jahressumme und ausdrückliche Einmalzahlungssperre |

Die echten Backenddaten des neuen Scopes stehen in `app/test/fixtures/payroll_transition.json`. Neue reproduzierbare Tests: `web/office/tests/payroll-transition.test.mjs`, `app/test/business_payroll_transition_test.dart`, `web/office/tests/payroll-transition-flow.cjs`. Der Browser läuft mit `SMARTPLAN_BROWSER_WORKFLOW=payroll-transition`; Namespace-, PID-, Netzwerk- und Seccomp-Sandbox waren aktiviert und geprüft. Die 390px-Ansicht wurde visuell geprüft.

Lokale Logs: `work/verification/payroll-transition-{node,flutter,analyze,browser}.log`. Screenshots und synthetische Befehle liegen in `work/verification/payroll-transition-browser/`. Auch die vollständige bisherige Payroll→EÜR-Browserstrecke gegen diese neue Profilmaske ist erneut bestanden: Minijob, reguläre PAP-Berechnung, Kontonachweise/Vortrag, Jahresübersicht, private tatsächliche Zahlungen und allgemeine EÜR ohne Personalrechte. Protokoll: `work/verification/payroll-cash-after-transition-browser.log`.

Die beschriebenen Vollmonats-/Prognosegrenzen gelten unverändert. Teilmonate, vorhersehbare Einmalzahlungen und andere im Backend nicht unterstützte Sonderfälle werden nicht durch diesen Client als berechnet freigegeben. Eine externe fachliche oder gerätespezifische Nutzerabnahme wird damit nicht behauptet.
