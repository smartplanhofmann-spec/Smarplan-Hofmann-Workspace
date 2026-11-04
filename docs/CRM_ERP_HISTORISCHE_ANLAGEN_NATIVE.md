# Native Übernahme historischer Anlagen — 04.11.2026

Die Flutter-Oberfläche verwendet den tatsächlichen Vertrag aus `CRM_ERP_HISTORISCHE_ANLAGEN_API.md` und die unveränderte Domainfixture `app/test/fixtures/accounting_historical_assets_2026.json`. Die Umsetzung gehört zum isolierten Anlagenbaum. Die bestehende Anfangssaldenbasis aus `c7dbab0cc1ad2a5e64b864a88d42ac6c9f79efeb` bleibt erhalten.

## Bedienung und fachlicher Umfang

Der Einstieg liegt in der Buchhaltung und im EÜR-Quellenbereich. Vorhandene Originale und angenommene Fassungen lassen sich nach Inventaridentität auswählen. Eine neue Erfassung enthält keine vorgegebenen Anschaffungswerte, Nutzungsdauer, Vorsteuer, AfA-Vorträge, Restbuchwerte oder Konten. Der Übernahmestichtag stammt ausschließlich aus dem ausdrücklich bestätigten Buchführungsprofil. Das Auswertungsjahr ist sichtbar und änderbar.

Die Inventarnummer wird unverändert an `/accounting/historical-assets/identity` gesendet. Ausschließlich der Server ermittelt NFKC-/Casefold-Identität; Flutter bildet Unicode-Kennungen nicht näherungsweise nach. Originale werden als echte PDF-/PNG-/JPEG-Datei hochgeladen. Größe, Inhalt, SHA-256, Originalkennung und Quittung werden gebunden geprüft. Auch bereits gespeicherte Originale müssen ausdrücklich ausgewählt werden. Der Originaldownload prüft die unveränderten Bytes und den aktuellen Zugriff erneut vor dem Export.

Unterstützt werden belegte, unverändert lineare bewegliche Anlagen bei ausschließlich betrieblicher Nutzung, mit identischem Anschaffungs-/Nutzungsmonat. Die drei tatsächlich belegbaren Rundungsverfahren bleiben getrennt. Die Oberfläche verlangt die ausdrückliche Bestätigung von Altverfahren und unveränderter Historie. Vorjahres-AfA, bereits gebuchte Startjahres-AfA und Restbuchwert müssen zur ursprünglichen Kostenbasis passen. GWG, Methodenwechsel, Sonder-/degressive AfA, Privatanteile und Abgänge werden nicht automatisch beurteilt.

Die Übernahme erzeugt keine Zahlung, Vorsteuer oder neue Anschaffung. Vorschau und Annahme sind getrennt. Eine spätere Folge-AfA wird im vorhandenen EÜR-Journal ausdrücklich vorbereitet und bestätigt. Jahr und geprüftes Sachkonto gehören zu diesem separaten Auftrag. Bei unterjähriger Übernahme zeigt die Seite ursprüngliche Jahresquote, bereits gebuchten Vortrag und den verbleibenden Betrag getrennt. Eine Nullquote wird nicht durch eine Scheinbuchung ersetzt.

Buchungsberichtigung, Gegenbuchung, Periodenschluss und begründete Wiederöffnung verwenden die vorhandenen EÜR-Wege. Die Anlage behält ihre eigenen ursprünglichen Quellen- und Inhaltsprüfsummen. Quellkorrektur und ausdrückliche Aufhebung erzeugen neue historische Fassungen; alte Originale und Historie bleiben sichtbar. Aktive Folge-AfA oder geschlossene betroffene Perioden werden serverseitig berücksichtigt.

## Zugriff, verspätete Antworten und Wiederholung

Die Anlagenseite verlangt globale `accounting.read` und `finance.read`, das Feature `accounting_historical_assets` und die Capability `business_accounting_asset_openings`. Sie verlangt kein `bank.read`. Schreiben benötigt zusätzlich `accounting.admin`, `accounting.prepare`, `finance.write`, aktiven Finanzbetrieb und das tatsächliche `can_prepare` des Servers. Die EÜR-Folgehandlung verlangt außerdem die vorhandenen EÜR-Freigaben.

Jeder Antwortpfad bleibt an Sitzungsobjekt, Token, Generation und Seitenepoch gebunden. Gehaltene Quellen und Vorschauen werden vor der Anzeige nochmals gegen aktuelle Rechte geprüft. Sitzungswechsel, Leseentzug und Hintergrundwechsel entfernen private Inhalte und Entwürfe. Auch ein bereits gefüllter EÜR-Dialog ersetzt nach Kontext-/Schreibrechteverlust Inhalt und Titel durch eine neutrale Meldung. Nach Hintergrundwechsel ist ein explizites Neuladen erforderlich.

Unbekannt beantwortete Original-, Anlagen- und EÜR-Aufträge bleiben nur in der authentifizierten Sitzung. Wiederholung verwendet genau denselben Request, dieselbe `request_id`, dieselben Quellen und denselben ursprünglichen Quittungsprüfer. Eine fremde oder veränderte Quittung darf den offenen Auftrag nicht löschen. Nach einer unklar beantworteten Originalannahme muss ein verworfener Eingabeentwurf erneut aus dem nun ausdrücklich ausgewählten Original vorbereitet werden; die Datei wird nicht erneut als neuer Auftrag geraten.

## Enger gemeinsamer Sitzungsfix

Der echte HTTP-Ablauf hat einen bestehenden Race in `BusinessSession.load()` reproduziert: Während der periodische Capability-Abruf noch lief, lieferte ein paralleler Workflow-Aufruf wegen `if (loading) return` sofort zurück. Die sichere nachgelagerte Rechteprüfung wies diesen Vorgang deshalb ab, obwohl das Ergebnis noch ausstand.

`load()` veröffentlicht jetzt vor der ersten Benachrichtigung einen gemeinsamen Future. Parallele und synchron reentrante Aufrufer warten auf denselben tatsächlichen Abruf. Die bestehende Epoch-/Token-/Dispose-Prüfung bleibt erhalten. Nur der identische abgeschlossene Future darf die Inflight-Referenz leeren. Ein gesonderter Test dokumentiert den roten Vorzustand und prüft Widerruf, Fehler, Wiederholung, Tokenwechsel, Disposal und eine neue unabhängige Sitzung.

Dieser Fix ist bei der Zusammenführung separat zu übernehmen. Der Source5-Clientbaum ergänzt seinen eigenen Payroll-Retryhook; dessen Hook und die bisherigen Source4-/Opening-Hooks dürfen durch einen vollständigen Dateiaustausch nicht verloren gehen.

## Nachweise und Grenzen

Die konkreten Befehle, Ergebnisse, Quell- und Fixtureprüfsummen stehen in `evidence/historical-assets-native-2026-11-04/manifest.json` und den daneben archivierten Textlogs. Die vorher abgeschlossene unabhängige Backendprüfung einschließlich unveränderter alter EÜR-Exporte liegt separat unter `evidence/historical-assets-independent-2026-11-04/`.

Die native Abnahme verwendet synthetische Unternehmensdaten und einen lokalen echten HTTP-/SQLite-Server. Sie ist keine Anmeldung an einer Produktivfirma und keine neue MFA-Einrichtungsprüfung. Der mobile Ablauf wird im Flutter-Widgetrunner mit 390 × 844 Pixeln ausgeführt; daraus folgt kein Nachweis einer installierten iOS-/Android-/Windows-Auslieferung. Die fachlichen Grenzen und Originalbelegpflichten des Backendvertrags bleiben bestehen.
