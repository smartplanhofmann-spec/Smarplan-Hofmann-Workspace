# Unabhängige Browsergegenprüfung der belegten Altposten

Stand: 04.11.2026. Arbeitsbaum `/workspace/smartplan-opening-items-20261104`.
Die Prüfung ergänzt den eigenen Browser-/HTTP-Nachweis des Implementierungsowners. Sie ist keine Gesamtfreigabe der Software und keine fachliche Zulassung.

## Nachweis und Umfang

- **30 neue unabhängige Fälle** in `web/office/tests/accounting-open-items-independent.test.mjs`.
- **73/73 grün** zusammen mit vorhandenen Altposten-Vertrags-/Kontexttests sowie EÜR- und Bank-Vertragstests. Befehl und Hashes stehen im Evidenzmanifest.
- Tatsächliche Backend-UI-Fixture `docs/fixtures/accounting_open_items_ui_v1.json`, SHA-256 `24fac53baf96261bdfa42c837c1a498e2e2f87436438438e4113046fea98a708`, unverändert gelesen.
- Zusätzliche eigene Bankfixture durch den unverändert ausgeführten bestehenden SQLite-Test `OpeningItemWorkflow.test_real_bank_matching_and_liquidity_share_exact_single_money_source`. Der Generator ersetzt keine Fachfunktion: Er ruft Originalmethoden auf und kopiert deren Rückgaben. Enthalten sind echte Kandidaten, Vorschau, Annahme und ursprüngliche Zahlungsquelle.

Die Nodefälle verwenden echte `OfficeApi`-/UI-/Vertragsmodule und eine kontrollierte DOM-/Transporthülle. Zeitlich gehaltene Antworten werden gezielt nach einem Kontextwechsel freigegeben. Wirtschaftliche Daten stammen aus echten Backendfixtures. Für EÜR-Lifecyclefälle bindet eine Transporthülle den jeweiligen tatsächlichen Auftrag an die unveränderten ursprünglichen Source-/Postingdaten; sie ist kein zusätzlicher HTTP- oder Zahlenberechnungstest. Ein wirklicher Chromium-/MFA-/HTTP-Ablauf wird getrennt durch den Browserowner geführt.

## Unabhängig reproduzierte Befunde und Nachprüfung

Insgesamt wurden elf negative Ablaufvarianten vor der Korrektur rot nachgewiesen:

1. Eine gehaltene EÜR-Vorschau der neuen Altpostenzahlung öffnete nach Schließen oder Wechseln des Editors erneut die private Bestätigungsmaske: zwei Fälle.
2. Ein initial gehaltener EÜR-Quellenabruf öffnete nach Schließen oder Dialogwechsel einen privaten Editor: zwei Fälle.
3. Eine bereits gültig angenommene EÜR-Quittung konnte nach einem Dialogwechsel den neuen Dialog schließen oder nach dem Schließen unnötig aktualisieren: zwei Fälle.
4. Eine verspätete Rechteverweigerung während Initialabruf, Vorschau oder Bestätigung schloss über den bisherigen `onDenied`-Pfad einen inzwischen neu geöffneten Dialog: drei Fälle.
5. Eine gültige Wiederholungsquittung eines bereits offenen EÜR-Auftrags schloss nach dem Kontextwechsel ebenfalls einen fremden Dialog: ein Fall.
6. Ein initialer Quellenabruf konnte nach einem zwischenzeitlichen tatsächlichen Entzug von `finance.read` ohne vorherige lokale Benachrichtigung weiterhin private Altpostendaten anzeigen: ein Fall.

Der Browserowner korrigierte ausschließlich den neuen `opening_item_cash`-Pfad im bestehenden EÜR-Client: konkreter Dialog-/Editor-/Sitzungskontext, neutrale Behandlung veralteter Fehler, frische Rechte nach Quellenabruf, Annahmeauflösung unabhängig von Sichtbarkeit und keine verspäteten `closeModal`-/Refresh-Nebenwirkungen. Die unabhängigen Gegenfälle blieben für die Nachprüfung unverändert. Der Reviewer änderte keinen Produktcode. Die früheren roten Logs bleiben neben dem abschließenden grünen Lauf erhalten.

## Erhaltene Originale und wirtschaftliche Grenzen

Die gerenderte Forderung bewahrt die alte Zahlung `33,34 / 6,33 / 39,67` und den ursprünglichen offenen Rest `66,66 / 12,67 / 79,33`. Die Verbindlichkeit zeigt ausdrücklich den bereits ausgeübten vollen Vorsteuerabzug; eine neue Zahlung wird in der EÜR als `−100,00` Nettoaufwand und `−19,00` bezahlte Vorsteuer eingeordnet. Der neue Vorgang schafft keinen zweiten Vorsteueranspruch. Die unveränderten fachlichen Rechtsgrenzen stehen in der gesonderten amtlichen Quellengegenprüfung und der API-Dokumentation.

Lokale Dateiabrufe und Originaldownloads wurden bei spätem Erfolg und Fehler nach Dialog-, Sitzungs- und Hintergrundwechsel geprüft. Originalbytes mit falscher Länge/Prüfsumme werden verworfen. Ein tatsächlicher Entzug des Finanzleserechts nach dem Byteabruf verhindert Download und private Restanzeige.

Drei unterschiedliche offene Aktionen – Originalannahme, Altpostenübernahme und Zahlungsnachweis – bleiben gleichzeitig getrennt erhalten. Nach weiter fortgeschrittenem Journalstand werden sie in anderer Reihenfolge jeweils mit exakt demselben vollständigen Body und derselben ursprünglichen Nonce beantwortet. Eine gültige ursprüngliche Annahme kann das Pending intern auflösen, ohne einen späteren Dialog anzufassen.

Die reale Bankfixture bindet `119,00` derselben `opening_item_cash`-Zahlung an dasselbe Konto und deren ursprünglichen Hash. Änderungen der ausgewählten Quelle, des Kontos oder des Quellhashes werden verworfen; die tatsächliche Annahme wird exakt gegen ihre Vorschau geprüft. Der ausgeführte Backendfall bestätigt `1.000,00 + 119,00 = 1.119,00` Liquidität ohne neue Zahlung durch den Abgleich und sperrt die Aufhebung eines aktiv bankgebundenen Nachweises.

## Abgabe

Eigene Dateien: neuer unabhängiger Node-Test, eigener Bankfixturegenerator, dessen tatsächliche JSON-Rückgaben, dieser Bericht und `docs/evidence/opening-items-browser-independent-2026-11-04/`. Produktänderungen gehören ausschließlich dem Browserowner. Die integrierte Gesamtprüfung und der erneute vollständige reale Browserlauf bleiben beim Root/Owner; hier wird weder ein produktiver Bankkontakt noch eine vollständige Softwareabnahme behauptet.
