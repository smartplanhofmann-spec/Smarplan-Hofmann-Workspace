# Private Jahresquellen in Browser und Flutter

Stand 03.11.2026. Der Einstieg „Jahresquellen und Einmalansprüche öffnen“ ist in beiden Lohnoberflächen vorhanden. Grundlage ist der Fachvertrag `CRM_ERP_LOHN_JAHRESBASIS_VERTRAG_2026.md`. Die gemeinsame Regel lautet `de_2025_2026_annual_basis_v1`.

## Anforderungen und Umsetzung

Die fünf Arten besitzen eigene strukturierte Formulare: externe Lohnperiode, bereits verarbeiteter externer Einmalbezug, vollständige Jahresbasis, geplanter Einmalanspruch und Jahressteuergrundlage. Quellenwahl und konkrete Fachangaben sind getrennte Schritte. Jede Art bindet die tatsächliche Arbeitgeberidentität und geschützte Originale. Beiträge werden pro Versicherungszweig mit belegten Zeitintervallen und Rechtsgrund erfasst; tatsächliche Zuflüsse besitzen eigene Zahlungsoriginale. Jahreslücken, Anspruchszeiträume, verbleibende Vertragsmonate und frühere Arbeitgeber erhalten ausdrücklich ausgewählte Originalbezüge.

Neue Formulare lassen Geldbeträge, bekannte Nullwerte und konkrete Zeiträume offen, bis sie angegeben werden. Eine Auswahl wird auf die aktuelle kanonische Fassung aufgelöst. Die Oberfläche bietet keinen freien JSON-Editor und erzeugt keine Zahlung aus einem geplanten Anspruch. Die ursprüngliche externe Steuerberechnung wird nicht als neu berechnete PAP-Steuer ausgegeben. Der aktuelle Einmalanspruch bleibt aus der davor liegenden Jahressteuergrundlage ausgeschlossen.

Vorschau und ausdrückliche Bestätigung sind getrennt. Korrekturen erzeugen neue Fassungen mit Begründung; Aufhebungen bewahren die zuvor bestätigten Quellen und den Plan. Frühere Fassungen bleiben lesbar und besitzen keinen Bearbeitungseinstieg. Der Browser bietet geschützte Originaldownloads und prüft vor Zugriffen die aktuellen globalen Personalrechte. Ungewisse Antworten behalten das exakte Originalkommando und seine Vorgangskennung. Ein pausiertes Personalmodul erlaubt ausschließlich die unveränderte Wiederholung mit frischen Rechten. Der OfficeApi-Guard verweigert auch einen passenden Jahresquellen-Endpunkt unter einem fremden Vorgangsschlüssel.

Die Flutter-Seite und ihre strukturierten Formulare werden zusätzlich in `business_payroll_annual_basis.dart` und `business_payroll_annual_basis_forms.dart` geprüft. Der gemeinsame Dart-Vertrag und die produktive Einbindung sind Teil dieses Clientpakets. Die detaillierten Native-Formular-, Lifecycle- und Freigabetests werden separat dokumentiert; ihre Ergebnisse werden hier nicht vorweggenommen.

## Nachgewiesene Prüfung

Die tatsächliche synthetische Service-Fixture `fixtures/payroll-annual-basis-2026.json` enthält alle fünf Arten mit Originalauftrag, Vorschau, bestätigter Fassung und Historie. JavaScript und Dart lösen die gewählten Quellen daraus wieder auf und vergleichen die vollständigen kanonischen Aufträge und Antworten. Gegenprüfungen verweigern fremde Personaloriginale, ausgetauschte Arbeitgeberidentitäten, Pläne und unklare Geldwerte.

Der echte Chromium-Lauf verwendet MFA und die tatsächliche HTTP-API. Namespace-, PID-, Netzwerk- und Seccomp-Sandboxen werden vor dem Appzugriff geprüft. Er erfasst alle fünf Formulare: eine externe Oktoberperiode mit 30 SV-Tagen, einen bereits verarbeiteten Einmalbezug, die lückenlos belegte Jahresbasis, einen getrennten geplanten Anspruch und die Jahressteuergrundlage. Die Jahresbasis enthält 120.000 Cent verbrauchte Beitragsbasis. Der geplante aktuelle Anspruch von 50.000 Cent bleibt aus den 1.120.000 Cent Jahresarbeitslohn davor ausgeschlossen. Eine nach tatsächlicher Annahme verlorene Antwort wird exakt wiederholt. Anschließend werden Korrektur, Aufhebung, drei unveränderte historische Fassungen, Originaldatei-Hash und die Darstellung bei 390 Pixeln geprüft.

Das Clientpaket prüft 19 Node-Fälle (17 Jahresquellenfälle einschließlich tatsächlicher OfficeApi-Guards, zwei Gesamtfall-Replayregressionen), 30 Flutter-Fälle (sieben neue Vertragsfälle und bestehende Lohn-, Gesamtfall- und Mitarbeiterbelegregressionen) sowie drei Dart-Dateien ohne Analysebefund. Logs, Screenshot und maschinenlesbarer Stand liegen unter `docs/evidence/payroll-annual-clients-*` und `CRM_ERP_LOHN_JAHRESQUELLEN_CLIENTS_PRUEFUNG_2026-11-03.json`.

Die Jahresquellen sind die überprüfbare Grundlage für einen folgenden Einmalbezugs-Lohnlauf. Dieser Nachweis behauptet weder einen fertigen v6-Lohnlauf noch eine tatsächliche Bankzahlung oder eine amtliche Übermittlung.
