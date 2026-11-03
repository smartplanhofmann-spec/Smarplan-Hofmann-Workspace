# Bankabgleich: Browser- und Flutterabnahme

Stand 03.11.2026. Der Einstieg liegt unter Finanzen → Bankabgleich. Die Clients implementieren den [stabilen API-Vertrag](CRM_ERP_BANKABGLEICH_API.md) des [fachlich geprüften Bankkerns](CRM_ERP_BANKABGLEICH.md).

## Bedienumfang

Vorhandene EUR-Bankgeldkonten werden mit ausdrücklich eingegebener IBAN, Bankbezeichnung, Kontoführungsbeginn und gegebenenfalls Ende verbunden. Neue Aktivierung und Bestätigung sind nicht vorausgewählt. Die Kontoführung wird nicht aus der ersten Datei erraten. Bestehende Identität und Beginn bleiben erhalten.

Originale CSV-Dateien werden unverändert gewählt und vorab vollständig geprüft. Auszugsreferenz, Zeitraum, Salden und Trennzeichen sind ausdrückliche Eingaben; der vollständige Zeitraum wird separat bestätigt. Der Client berechnet mit exakten Dezimaltexten, rundet keine Bankwerte und erzeugt keine externe ID. Fehler verhindern die gesamte Übernahme. Inhaltsgleiche Zeilen mit unterschiedlichen IDs erfordern einen konkret eingegebenen Prüfgrund und eine neue Vorschau. Ein Nullaktivitätsauszug nur mit Kopf ist bei gleichen Salden zulässig.

Die Zuordnung zeigt vorhandene tatsächliche Geldquellen und ihren verfügbaren Rest. Quellen und Beträge werden neu ausdrücklich gewählt. Teilzuordnungen bleiben sichtbar; eine leere Zuordnung benötigt einen Aufhebungsgrund. Abweichende Zahlungs- und Banktage benötigen einen Beleggrund und ändern keinen EÜR-Zahlungstag. Historische Fassungen sind paginiert lesbar.

Monatsberichte zeigen Kontoführungsumfang, tatsächliche Salden, Bank- und Geldflusssummen, konkrete offene Prüfpunkte sowie aufklappbare Bank-/Geldquellenzeilen. Unvollständige Berichte können dokumentiert werden und werden als nicht abschlussfähig bezeichnet. Spätere Quellen-/Zuordnungsänderungen machen den alten Bericht ausdrücklich veraltet. Archivierte Exporte bleiben unverändert; vor dem Speichern prüfen beide Clients vollständige Bytes, SHA-256 und Größe. JSON wird zusätzlich mit genau dem gespeicherten Ereignis verglichen. Native MIME-Prüfung berücksichtigt archivierte Charset-Parameter.

Bei großen Auszügen zeigt die Ansicht die ersten 100 Zeilen. Weitere einzelne Bankzeilen lassen sich über ihre exakte externe ID öffnen; JSON/CSV dokumentieren den vollständigen Bericht. Kontoauszüge, Zuordnungsverläufe und gespeicherte Prüfstände besitzen weitere Seiten. Neue Berichte wählen ausdrücklich höchstens 100 Auszüge.

## Rechte und offene Antworten

Vor Lesen, Schreiben, Wiederholung und Download werden globale Bank-, Finanz- und Buchführungsrechte neu geprüft. Bankkontobindungen benötigen zusätzlich beide Verwaltungsrechte. Allgemeine Finanzrechte allein öffnen keine Bankoriginale und Bankrechte öffnen keine privaten Personalakten. Native Bankdaten und offene Editoren werden bei Rechte-/Sitzungswechsel ausgeblendet.

Verlorene Import-, Zuordnungs-, Bindungs- und Berichtsantworten behalten Kennung und Originalbody. Frische Rechte und dieselben tatsächlichen Konten/Transaktionen werden vor Wiederholung gelesen; die inzwischen höhere aktuelle Revision ersetzt niemals die akzeptierte Originalrevision. Ungeklärte Rollen-/Noncekonflikte behalten den Vorgang. Native `pendingBankKeys` zeigt nach Navigation ausschließlich neutrale Wiederholzugänge; Browser verwendet das bestehende globale Menü für offene Antworten.

## Ausgeführte Nachweise

Alle Konten, CSV-Dateien, Personen und Finanzquellen sind synthetisch. Es gab weder Bankzugriff noch Geldübertragung oder amtliche Übermittlung.

| Prüfung | Ergebnis | Inhalt |
|---|---:|---|
| `web/office/tests/bank-reconciliation.test.mjs` | 11/11 | Exakte Cents, explizite Quellen, Bankrechte, vollständige verschachtelte Quittungen, Dateihashes, Dublettenprüfgründe, unveränderte Wiederholung nach Rechteentzug und veränderter Revision |
| `app/test/business_bank_reconciliation_test.dart` | 11/11 | Gleiche Fachbindungen, gemeinsame native Replay-Helfer, neutrale offene Kennungen, falsche Transaktion, MIME-/Hashprüfung, 390px-Ansicht und Ausblenden bei Rechteentzug, leere Fakten und unbestätigte Aktivierung |
| Flutter Analyze | Ohne Befund | Integrierter App-Quellstand nach den Clientkorrekturen |
| Echter Chromium-Browser | Bestanden | MFA/HTTP, explizite Kontobindung, unverändertes CSV-Original, verlorene Import-/Zuordnungs-/Berichtsantworten mit identischem Replay, 100,00→119,00 € Teil-/Vollzuordnung, unvollständiger/vollständiger Monatsbericht, exakte JSON/CSV/PDF-Downloads, historische unveränderte Nachweise nach Aufhebung, konkrete Dublettenunterscheidung, Nullaktivitätsauszug, fremder Originalzugriff abgewiesen, 390px |

Chromium lief mit geprüfter Namespace-, PID-, Netzwerk- und Seccomp-Isolation. Der Browservergleich bestätigt außerdem, dass weiterhin genau der vorher vorhandene Geldjournaleintrag existiert; Bankvorgänge erzeugten keine neue Zahlung. Die mobile Berichtansicht wurde visuell geprüft.

Reproduzierbarer Browserlauf: `SMARTPLAN_BROWSER_WORKFLOW=bank-reconciliation node web/office/tests/e2e.cjs`. Die Testdaten unter `app/test/fixtures/bank_reconciliation.json` wurden direkt durch den echten Backendkern erzeugt. Logs: `work/verification/bank-clients-{node,flutter,analyze,browser}.log`. Screenshots und synthetische Befehle: `work/verification/bank-clients-browser/`.

Nicht behauptet werden eine Bankanbindung, eine Qonto-Formatkompatibilität, tatsächlich geprüfte Kontoinhaberschaft oder eine externe fachliche/gerätespezifische Nutzerabnahme. Der neutrale CSV-Vertrag, die bestehenden Quellenrechte und der unterstützte EUR-Umfang gelten unverändert.
