# Unternehmensereignisse im Browser

Stand 04.11.2026. Im Repository implementierter Browserteil zu Abschnitt 10
und Abnahme E des unveränderten Gesamtziels. Dies ist keine Gesamt- oder
Produktionsfreigabe. Backendvertrag und zulässige Fallklassen stehen in
[API-Vertrag](CRM_ERP_UNTERNEHMENSEREIGNISSE_API_2026.md).

## Bedienung

Im **Assistenten → Unternehmensereignisse öffnen** sind Aktionspläne und
Ereignishistorie erreichbar. Regelverwaltung und Laufhistorie erfordern
zusätzlich `settings.manage`; Schreibaktionen sind im Lesemodus deaktiviert.
Quellen- und Projektrechte werden vor und nach asynchronen Abrufen geprüft.

Eine Unternehmensregel bindet Auslöser, ausdrückliche Projektmenge oder alle
aktuell erreichbaren Projekte, Bedingungen, zuständige Person, feste Vorlage
und Entscheidung. Neue Fassungen erhalten frühere Originale. Die Modi sind
Automatik, konkrete Freigabe und Verbot; ein Verbot gewinnt. Bestehende
Projektregeln können eine Unternehmensautomatik einschränken. Zuständigkeit
verleiht keine Fach- oder Projektberechtigung.

Der bewusst gestartete Ereignislauf verwendet aktuelle serverseitige Quellen.
Er zeigt Abfragedatum, geprüfte Quellen, tatsächliche Verarbeitung, Fehler und
gegebenenfalls eine nächste Seite. Er behauptet keine lückenlose frühere
Ereignisaufzeichnung. Gespeicherte Beobachtungen ohne Aktionsplan bleiben über
die Ereignishistorie auffindbar.

Ein Aktionsplan zeigt ursprüngliches Ereignis, Fakten, Quellenhash,
Unternehmens- und Projektregelfassungen, Zuständigkeit, Parameter, Freigabe und
tatsächliches Ergebnis. Eine genehmigte interne Aufgabe ist anschließend im
Projekt erreichbar. Angebotsentwürfe übernehmen die ausgewählte Artikelrevision
und Menge; ein Eingangstext darf weder Preis noch Aktion bestimmen. Versand-
und Zahlungsaktionen bleiben an die bestehenden fachlichen Gates gebunden;
fehlende ausführende Adapter werden ausdrücklich angezeigt.

Eine verlorene Antwort erhält den vollständigen Originalauftrag. Das Formular
wird gesperrt und bietet nur die unveränderte Wiederholung an; die zentrale
Anzeige „Antwort offen“ erreicht denselben Auftrag. Eine fremde gültige Quittung
kann ihn nicht abschließen. Geänderte Quellen oder Regeln benötigen eine neue
Vorbereitung. Begonnene externe Aktionen mit unklarem Ergebnis werden nicht
blind wiederholt. Eine dauerhaft angenommene Ausführung ohne Ergebnis
(`unconfirmed`, `execution` vorhanden, `outcome=null`) quittiert nur den
ursprünglichen Auftrag. Die Ansicht zeigt ausdrücklich „ungeklärt“, keinen
Erfolg und keinen erneuten Ausführungsbutton.

## Vertrag und Kontextschutz

Die getrennten Module `company-events-contract.js` und `company-events.js`
prüfen echte Backendantworten. Jeder POST bindet `acceptance.request_id`,
Operation und den Hash des vollständigen ursprünglichen Bodys. OfficeApi gibt
dem asynchronen Validator eine isolierte Kopie dieses Bodys. Nach der Prüfung
müssen Sitzung und identische offene Operation weiterhin übereinstimmen.
Bestehende synchrone Validatoren bleiben kompatibel.

Geldbedingungen und Centfakten bleiben kanonische Strings; Berechnung und
Darstellung verwenden exakte Ganzzahlen. Eingebettete bisherige Projektregeln
binden ihren unveränderten kanonischen Originaltext und dessen Hash. Dessen
Geldprojektion wird ohne verlustbehaftete JavaScript-Zahlen verglichen.

Ein eigener Dialogzähler bindet bereits den ersten Abruf an den tatsächlich
geöffneten Dialog. Session-, Projekt-, Dialog- und Hintergrundwechsel verhindern,
dass verspätete Werte einen neuen Kontext ersetzen. Der unabhängige Review
reproduzierte zusätzlich eine späte private Fehlernachricht nach Dialog- oder
Projektwechsel. Derselbe Kontextguard umfasst jetzt auch Fehlerpfade.

## Anforderungen und aktueller Nachweisstand

| Anforderung | Stand | Nachweis |
|---|---|---|
| Regelversion, Projektumfang, Zuständigkeit, Wirkung | implementiert und im echten Browser geprüft | `web/office/tests/company-events-flow.cjs` |
| Quellen, Ereignisse, dauerhafte Lauf- und Planhistorie | implementiert und im echten Browser geprüft | derselbe reale HTTP-/MFA-Ablauf |
| Konkrete Freigabe, interne Aufgabe, automatische Aufgabe, Verbot | getestet | echte Fachvorgänge mit synthetischen Originalen |
| Tatsächlicher Angebotsentwurf aus aktueller Artikelrevision | getestet | Netto 199,75 EUR aus 2,5 × 79,90 EUR |
| Vier verlorene Antworten und unveränderte Wiederholung | getestet | Regel, Scan, Entscheidung, Ausführung; identische Originalbodies |
| Quellenrechte nach verspäteten Antworten, 390px | getestet; unabhängiger Review abgeschlossen | eigener kompletter Browserablauf und zusätzliche Gegenfälle |
| Vorhandene Projektverbote und bisheriger Assistant-Einstieg | behoben und unabhängig geprüft | `backend/test_business_company_events_independent_review.py` |
| Nicht lesbare Belegkennung im Scanfehler/Cursor | behoben und unabhängig geprüft | derselbe unabhängige Domainreview |
| Verspätete private Fehlermeldung im neuen Kontext | behoben, unveränderte Gegenfälle und drei echte Chromium-Kontextfälle grün | separate Reviewerdatei und unveränderte Rotnachweise |
| Angenommene Ausführung ohne bestätigtes Ergebnis | unabhängig geprüft, keine erneute Ausführung | tatsächliche `external_unconfirmed`-Fixture, exakte Quittung und UI-Gegenfall |
| Produktive Außenaktionen | nicht ausgeführt | lokale synthetische Daten, kein Versand oder Zahlung durch Browserabnahme |

Der endgültige Stand besteht **557/557 benannte Node-Tests**, einschließlich
35 gezielter Unternehmensereignisfälle (22 eigene, 13 unabhängige). Die
**16 unabhängigen Backend-Gegenfälle** sind grün. Der vollständige neue
Browserablauf und der bisherige Assistantablauf sind im tatsächlichen
Chromium/MFA/HTTP-Test grün. Hinzu kommen drei unabhängige echte Browserfälle
für verspätete Antworten nach Dialog- und Projektwechsel.

Der [maschinenlesbare Abschlussnachweis](evidence/company-events-browser-2026-11-04.json)
bindet Quellstand, unveränderte Originalfixture, Testdateien, vollständige Logs,
synthetische HTTP-Nachweise und Screenshots mit SHA-256. Er verweist auf den
[unabhängigen Review](evidence/company-events-independent-2026-11-04/README.md)
und dessen [Ungeklärt-Nachtrag](evidence/company-events-independent-2026-11-04/UNCONFIRMED_ADDENDUM.md).
Zwischenläufe und Rotnachweise bleiben erhalten. Die allgemeine Cloud-/
Browserprüfung ist kein TLS-/Origin-Produktionsnachweis. Der vorhandene
Browserrunner prüft Namespace-, PID-, Netzwerk- und Seccomp-Sandbox vor dem
Anwendungszugriff.

## Zuständigkeit und Integration

Arbeitsbaum: `/workspace/smartplan-company-events-20261104`. Backend und API:
`overall_completion_review`; Browser und eigene Domaingegenfälle:
`finish_v6_clients`; unabhängiger Browserreview: `own_v6_projection`.
Native Oberfläche und ihre Abnahme sind ein eigener Arbeitsumfang.

Globale Browseranschlüsse betreffen OfficeApi, den Assistenteneinstieg,
Dialog-/Sitzungswechsel, Styles, E2E-Registry und die Browser-CI-Zeile. Beim
Merge müssen die inzwischen im Hauptprojekt ergänzten Source5-, Opening- und
Assets-Hooks erhalten bleiben. Der Dialogzähler ist mit dem bereits vorhandenen
Assetszähler zusammenzuführen; es darf nur einen Zähler geben. Keine Commits,
Hauptprojektänderungen oder echten Außenaktionen erfolgen durch diesen Scope.
