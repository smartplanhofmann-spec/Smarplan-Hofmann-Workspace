# Jahresbelegpaket V2 – Browser und native Anwendung

Stand: 4. November 2026. Separater Nachtrag zum eingefrorenen V1-Jahresbelegpaket. Keine neue Buchung, Migration, Zahlung oder Änderung bestehender Exportoriginale.

## Bedienung und Vertragsgrenze

Der gespeicherte EÜR-Exporteintrag öffnet weiterhin denselben lesenden Jahresnachweis. Beide Clients akzeptieren jetzt ausschließlich die vorhandenen Formate `smartplan-year-evidence-v1` und `smartplan-year-evidence-v2`. V2 enthält die tatsächlich an den damaligen Jahresprüfstand gebundenen Jahresvortragsquellen. Die ursprüngliche Metadatenform mit 16 Feldern bleibt unverändert. Unbekannte Formate werden abgewiesen; ein Formatwechsel nach dem ersten authentisierten Lesen darf den gewählten Export nicht ersetzen.

Nach exakter Prüfung von Exportkennung, Originalhash, Jahr, Vollständigkeitskennzeichnung, ZIP-Größe und ZIP-SHA lesen beide Clients dieselben Metadaten erneut. Dadurch werden die aktuellen Einzelquellrechte unmittelbar vor Ablage nochmals serverseitig geprüft. Es gibt keine neue Instanzannahme, Mutation oder Quittungsform. Der erforderliche separat authentisiert bestätigte Archivhash und `intrinsic_dependency_closure=false` bleiben unverändert. Die Hashprüfung behauptet keine eigenständige Vollständigkeit sämtlicher historischer Abhängigkeiten und keine Vollständigkeit des gesamten Unternehmensjahrs.

## Tatsächliche Abnahmen

- 76 benannte Nodefälle: bestehende EÜR-/V1-Verträge und Kontextfälle, acht eigene neue V2-Grenzfälle und acht unabhängige V2-Gegenfälle.
- 16 Paketprüfungen bestanden (6,452 Sekunden); die Operator-Dokumente und vorhandenen Backendmodule bleiben paketierbar.
- 53 native Fälle: V1 und V2 einschließlich tatsächlicher HTTP-/Dateiablage, selektivem Projekt-Rechteentzug bei erhaltenem globalem Finanzrecht, unbekannter Downloadantwort, Metadatenwechsel nach Dateiauswahl und verspäteten Antworten. Darin acht unabhängige V2-Fälle; Analyse der drei eigenen betroffenen Dateien ohne Befund.
- Tatsächlicher Chromium-/MFA-/HTTP-Ablauf mit Jahresvortrag, neuer Altpostenzahlung und zusätzlich projektgebundenem normalen Beleg. V2-Archiv zweimal bytegleich heruntergeladen, mit Repository-Prüfer und externem authentisiertem SHA geprüft. Vollständiger und unvollständiger damaliger Prüfstand, beide Antwortreihenfolgen des Exporteinstiegs, Hintergrundwechsel, vertauschte Metadaten, verspätete/korrupte Archivbytes, tatsächlicher Rechteentzug sowie 390 Pixel Breite geprüft. Namespace-, PID-, Netzwerk- und Seccomp-Sandbox vor Appzugriff nachgewiesen.

Die vier echten V2-Fixturefälle bleiben unverändert: `pending_review`, `partial_coverage`, `complete_history`, `old_partial_after_correction`; SHA-256 `2f9a1664eb1bf1d2615c7f25de9673aba4dc8ee95acad32367588411ba9f64d5`. Die sechs finalen V1-Fixtures behalten SHA-256 `a859f2bbbcfab6f890c2968a05aa2fa839299117ae43b8e15e2d7852c82d36a0`.

## Basen und Zusammenführung

Eigener Produktnachtrag: ausschließlich die Formatprüfung in `web/office/accounting-year-package-contract.js` und `app/lib/business_accounting_year_evidence_contract.dart`. Die Patches und unveränderten V1-Basisbytes stehen im Nachweisordner. Der Backendadapter bleibt auf dem separaten, bereits geprüften Stand; seine vorherigen Manifeste werden nicht umgeschrieben.

Für den echten Browserlauf reichte die reine eingefrorene V1-EÜR-Baseline noch nicht: Sie wies neue Jahresvortrags-/Altpostenquellen bereits vor dem Exporteinstieg ab. Dieser erste tatsächliche Lauf bleibt dokumentiert. Nach Abstimmung mit dem Jahresvortragsowner wurde ausschließlich dessen `euerSources`-Funktion mit `yvSource`/`oiSource`-Imports, den beiden zugehörigen Vertragsmodulen und zwei statischen Freigaben als fremde Testbaseline übernommen. Der gesamte V1-Exporteinstieg samt späteren Antwort-/Dialogschutz blieb unverändert. Dieses Overlay ist ausdrücklich kein eigener zusätzlicher V2-Funktionsumfang; beim gemeinsamen Merge sind die vollständigen geprüften Jahresvortrags-/Altposten-Ownerfassungen zu verwenden. Die im unabhängigen Review zunächst dokumentierte 23-Dateien-V1-Basis liegt zeitlich vor diesem gesondert manifestierten Overlay. Die dort geprüften zwei Reader sind weiterhin bytegleich.

Globale Änderungen dieses Nachtrags: zusätzlicher Browser-CI-Aufruf `node tests/accounting-year-package-v2-e2e.cjs` sowie additive Operator-Dokumente in beiden Paketlisten und der Windows-CI-Liste. Native Tests werden durch die vorhandene Discovery erfasst. Keine vollständige ältere globale Datei über einen neueren Hauptstand kopieren.

## Nachweise

- [Eigener Clientnachtrag](evidence/year-package-v2-clients-2026-11-04/manifest.json)
- [Unabhängiger Clientreview](CRM_ERP_JAHRESPAKET_V2_UNABHAENGIGER_CLIENTREVIEW_2026-11-04.md)
- [Unabhängiger Backendreview](CRM_ERP_JAHRESPAKET_V2_UNABHAENGIGER_BACKENDREVIEW_2026-11-04.md)
- [Backendvertrag](CRM_ERP_JAHRESPAKET_VORTRAG_V2_2026-11-04.md)

Alle Daten sind synthetisch. Kein Produktivkontakt und keine Anbieterformat- oder DATEV-Kompatibilitätsbehauptung.

## Enger Nachlauf des geliehenen Quellenlesers

Nach dem ersten grünen Browserlauf behob der Jahresvortragsowner drei unabhängig reproduzierte innere Datums-/Netto-/Postingwidersprüche in seinem Vertragsleser. Die zuvor verwendete Originaldatei, das damalige Kandidatenmanifest und die grünen Erstnachweise wurden unverändert unter `historical-before-borrowed-reader-followup` gesichert. Der jetzt vom Owner stabil erklärte Leser hat SHA-256 `58c08734d5dbe55954415735e02b3f646fb378e8e2007bb7907c8d81f22b3459`. Der unveränderte reale V2-Browserablauf und alle 76 gezielten Nodefälle wurden gegen ihn erneut grün ausgeführt. Die eigenen beiden V2-Formatreader, der Backendadapter, die tatsächlichen Fixtures und der native Stand änderten sich dabei nicht.
