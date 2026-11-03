# Belegter Bankabgleich – Umfang und Entwicklungsabnahme

Stand: 03.11.2026. Der additive Backendkern für R08.03 ist implementiert und anhand synthetischer Originale, echter Finanzquellen und PostgreSQL abgenommen. Browser- und Flutter-Bedienung sind getrennt gegen den [API-Vertrag](CRM_ERP_BANKABGLEICH_API.md) geprüft; Nachweise stehen in [CRM_ERP_BANKABGLEICH_CLIENTS.md](CRM_ERP_BANKABGLEICH_CLIENTS.md). Dies ist keine Bestätigung einer Bankanbindung oder einer Produktivinstallation.

## Erfasster fachlicher Umfang

Ein vorhandenes EUR-Geldkonto der Art Bank erhält eine ausdrücklich bestätigte, versionierte Bankidentität mit IBAN und Beginn/gegebenenfalls Ende der Kontoführung. Die IBAN-Prüfziffer wird geprüft; Kontoinhaberschaft und Banksalden werden damit nicht extern bestätigt. Identität und Kontoführungsbeginn bleiben nach Erstanlage unverändert.

Der neutral definierte CSV-Vertrag `smartplan_bank_csv_v1` erfasst unveränderte UTF-8-Originalbytes mit SHA-256, stabile externe Transaktions-IDs, Buchungs-/Valutadatum, tatsächlichen EUR-Centbetrag, Gegenpartei und Verwendungszweck. Zeitraum, Anfangs-/Endsaldo, Auszugsreferenz und Vollständigkeit werden ausdrücklich erfasst. Maximal 5 MiB und 10.000 Datenzeilen; ungültige Zeilen, ungleiche Salden oder widersprüchliche Identitäten verhindern die gesamte Übernahme.

Eine Datei nur mit korrektem Kopf ist ein belegter Nullaktivitätsauszug, wenn Anfangs- und Endsaldo gleich sind. Die gleichen Headerbytes dürfen für ausdrücklich verschiedene, nicht überlappende Zeiträume verwendet werden; jede Übernahme besitzt eigene Referenz, Metadaten und Bestätigung. Nullbetragzeilen und eine 0-Byte-Datei bleiben unzulässig.

Identische bekannte Transaktions-IDs werden in weiteren Auszügen referenziert und erzeugen keine zweite Bewegung. Gleiche Inhalte mit verschiedenen IDs verlangen einen dokumentierten Nachweis eigenständiger Zahlungen. Die Anwendung fasst solche Zahlungen nicht automatisch zusammen. Wiederholungen mit identischer Vorgangs-ID liefern die ursprüngliche Quittung nach erneuter Rechteprüfung.

Zuordnungen verbinden beliebige positive Teile bestehender Geldbewegungen und Bankzeilen. Beide Seiten begrenzen die Gesamtsumme; Konten und Zahlungsrichtung müssen übereinstimmen. Abweichende Bank-/Geldflusstage benötigen eine Begründung, ändern aber keinen EÜR-Zahlungstag. Unterstützt sind tatsächliche `cash_event`-Bewegungen, bestätigte externe EÜR-Geldflüsse und öffentlich aggregierte PayrollCash-Bewegungen. Der Bankabgleich erzeugt keine Zahlung, Rechnungszuordnung, Personalzahlung oder Steuerbuchung.

Korrekturen sind zusätzliche unveränderliche Zuordnungsfassungen. Berichte binden genaue Bankoriginale, Quellen und alle relevanten Zuordnungen. Monatsabdeckung muss innerhalb des erklärten Kontoführungszeitraums lückenlos sein; aufeinanderfolgende Auszüge benötigen anschließende Salden. Bank- und Geldquellenreste bleiben sichtbar. Spätere Quellen-/Zuordnungsänderungen machen den alten Bericht erkennbar veraltet; seine archivierten JSON-, CSV- und PDF-Bytes bleiben gleich.

## EÜR-Abschluss, Rechte und Wiederherstellung

Neue EÜR-Abschlüsse referenzieren für jedes zeitlich relevante eingerichtete Bankkonto einen aktuellen vollständigen Bankbericht. Fehlende oder veraltete Berichte verhindern den Abschluss. Änderungen betroffener geschlossener Monate verlangen die bestehende begründete Wiederöffnung mit den bestehenden Abschlussrechten. Alte manuelle Abschlüsse werden nicht umgeschrieben; spätere Korrekturen verändern keinen historischen Bericht oder Abschlussnachweis.

Bankoriginale können persönliche Namen, Kontodaten und Gehaltsverwendungen enthalten. Lesen benötigt ausdrücklich `bank.read`, `accounting.read` und `finance.read`; Schreiben zusätzlich `bank.prepare`, `accounting.prepare` und `finance.write`. Kontobindungen verlangen zusätzlich `bank.admin` und `accounting.admin`. Es gibt keine automatische Erweiterung gewöhnlicher Benutzerrollen. Tatsächliche Quellenrechte werden erneut geprüft, auch bei Wiederholung. Private Personalakten werden durch die öffentlich aggregierte Lohnzahlungsquelle nicht freigegeben.

Alle sieben Tabellen sind unveränderlich für die Laufzeitrolle; technische Requests enthalten nur Hash-/Referenzquittungen. Ein gemeinsamer transaktionaler PostgreSQL-Lock schützt Importe, konkurrierende Zuordnungskapazitäten und den Bankprüfstand des EÜR-Abschlusses. Der Restore-Horizont umfasst sämtliche Tabelleninhalte und geprüfte Originalhashes. Zusätzliche Validierung rekonstruiert Salden, Kontoführungszeiträume, Zuordnungssummen und historische Berichtsergebnisse aus den gebundenen Originalquellen.

Die sechs Fachtabellen stehen explizit im Unternehmensexport; das technische Wiederholungsjournal wird nicht als Fachausgabe exportiert. Bankdaten sind konservativ als sensible Finanzdaten inventarisiert. Freitext wird nicht automatisch einer Person zugeordnet oder pauschal gelöscht.

## Nachweise

| Prüfung | Ergebnis | Nachweis |
|---|---:|---|
| Finale Bankfachfälle | 17/17, 6,261 s | `work/verification/bank-domain-final.log` |
| Bank und bestehende EÜR | 32/32, 17,285 s | `work/verification/bank-domain.log` – 14 damalige Bankfälle und 18 EÜR-Fälle; drei zusätzliche Bankfälle separat final geprüft |
| PostgreSQL/MFA/HTTP, echte Parallelität und Dump/Restore | 3/3, 24,684 s | `work/verification/bank-postgres.log` |

Keine übersprungenen Fälle. Die PostgreSQL-Abnahme verwendet die bewachte lokale Wegwerfdatenbank und getrennte Operator-/Laufzeitrollen; keine Bank, kein Zahlungsanbieter und keine Behörde wird aufgerufen. Nach echtem Restore bleiben Schreibwege bis zur getrennten Betreiberfreigabe gesperrt. Der Prüfbericht verwendet den integrierten globalen Finanzhorizont 10 und Berichtsschema 11.

Geprüft sind insbesondere Mehrfachzuordnung ohne Veränderung bestehender Geld-/Steuerdaten, konkurrierende Überbelegung (genau ein Erfolg), parallele identische Importe (genau eine Übernahme), Rechteentzug vor Wiederholung, echte Originalbytes, konstante Exporthashes, historische EÜR-Abschlussreferenzen nach Wiederöffnung, externe Geldflussumkehr und echte Lohnzahlungsstornierung ohne Verlust alter Nachweise. Verfälschte Originale, umgerechnete Quellenbeträge und nachträglich neu gehashte falsche Vollständigkeitsbehauptungen werden abgewiesen.

Maschinenlesbare Quell-/Loghashes: [CRM_ERP_BANKABGLEICH_PRUEFUNG_2026-11-03.json](CRM_ERP_BANKABGLEICH_PRUEFUNG_2026-11-03.json).

## Noch getrennt abzunehmen

Die Browser-/Flutter-Entwicklungsabnahme ist [gesondert dokumentiert](CRM_ERP_BANKABGLEICH_CLIENTS.md). Ein direkter Anbieterimport oder Livefeed benötigt eine verbindliche Auswahl und einen offiziell belegten Format-/API-Vertrag; der neutrale CSV-Vertrag behauptet keine Qonto-Kompatibilität. Echte Bankunterlagen, Kontobindungen und Produktivberechtigungen müssen vor tatsächlicher Nutzung im vorgesehenen Betrieb geprüft werden. Andere Währungen und vorgemerkte Buchungen liegen außerhalb dieses erfassten Dateivertrags.
