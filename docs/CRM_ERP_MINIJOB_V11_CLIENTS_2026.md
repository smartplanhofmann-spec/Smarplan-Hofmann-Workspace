# Individuell besteuerter Minijob: Browser und native App

Der neue Quellenvertrag wird in Browser und App ausdrücklich ausgewählt. Er ergänzt den belegten Vollmonat eines allein beschäftigten gewerblichen Minijobbers mit gesetzlicher Familienversicherung und individueller Besteuerung. Die fachlichen Voraussetzungen und amtlichen Referenzwerte stehen in [CRM_ERP_MINIJOB_INDIVIDUELL_V11_2026.md](CRM_ERP_MINIJOB_INDIVIDUELL_V11_2026.md). Dieser Abschnitt führt keine neuen Lohnformeln ein.

## Bedienung und Originale

- Im Lohnkonto wird die neue Art des ELStAM-Nachweises ausdrücklich gewählt. Die bisherige Nachweisart bleibt voreingestellt. Das tatsächliche Versicherungsprofil wird nicht in eine private Krankenversicherung umbenannt; der technische PAP-Parameter PKV ist kein Versicherungsstatus.
- Unter den Abrechnungsfällen gibt es **Individuell besteuerten Minijob prüfen**. Der Nutzer wählt den vollständigen ursprünglichen Monatsfall, die Beschäftigung, das Profil und den ELStAM-Nachweis, fünf konkrete private Belegverweise, deren Wirkungszeitraum und sechs einzelne Bestätigungen. Die Bestätigungen sind nicht vorangekreuzt.
- Ein vorher gesperrter und noch unbenutzter individueller v5-Fall kann über **Individuellen Minijob ausdrücklich neu beurteilen** mit derselben ID, der aktuellen Revision und einer Begründung korrigiert werden. Die Backendprüfung bleibt für die tatsächliche bisherige Verwendung maßgeblich. Alte Fassungen und alte Wiederholungsaufträge behalten ihren ursprünglichen Vertrag.
- Eine angenommene Antwort muss zum ursprünglichen Auftrag, den privaten Originalen, Regelvertrag, Plan, Steuer- und Beitragswerten passen. Nach einer verlorenen Antwort wird derselbe ursprüngliche Auftrag mit derselben Vorgangskennung erneut geprüft. Fehlende aktuelle Rechte oder eine fehlende Funktionsfreigabe lösen keinen neuen Schreibversuch aus.
- Es werden keine Reisen, Einmalbezüge, Zusatzansprüche, Faktoren oder Teilmonate in diesen Umfang hineingedeutet. Ein gespeicherter gesperrter Nachweis bleibt als solcher lesbar; daraus entsteht kein berechnetes Netto.

## Prüfstand

Erster Browser-Nachweis gegen die echte lokale Flask-/SQLite-Anwendung: Anmeldung einschließlich MFA, beide RV-Fälle, neue Identitätsart und Auswahl der fünf privaten Belege, sechs bewusste Bestätigungen, identische Wiederholung nach verlorener Antwort für Identität/Gesamtfall/Lohnlauf, absichtliche v5-Neubeurteilung unter Erhaltung der Originalhistorie, private Original- und PDF-Downloads sowie 390-Pixel-Ansicht. Chromium lief mit überprüfter Namespace-/PID-/Netzwerk-/Seccomp-Sandbox. Dies ist kein Server- oder Geräteabnahmenachweis.

Die erste Browser-Regression umfasst 42 Testdateien einschließlich der bisherigen v5-/v10- und Lohnkonto-Wege. Dreizehn gezielte neue Browserfälle sind grün. Zusätzlich zu der unveränderten Backendfixture werden zwei echte angenommene Grenzfälle durch `scripts/generate-individual-minijob-client-fixture.py` erzeugt: weiter reichender Gültigkeitszeitraum mit mehrzeiligem Unicode-Prüftext und ein wegen unvollständiger Einkommensprüfung gesperrter Fall. Es werden keine Quellhashes von Hand hergestellt.

Nachweise: [evidence/minijob-v11-clients-2026-11-09](evidence/minijob-v11-clients-2026-11-09). Der abschließende gemeinsame Browser-/App-Lauf und die zusätzliche unveränderte Lohnlaufkorrektur werden vor Übergabe hier ergänzt.
