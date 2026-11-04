# Historische lineare Anlagen: Anforderungen, Fortschritt und Nachweise

Stand: 04.11.2026. Arbeitsbaum: `/workspace/smartplan-historical-assets-20261104`.
Keine Commits, Produktivkontakte oder echten Unternehmensdaten in diesem Paket.

## Abgedeckte Anforderung

Vor dem bestätigten Buchführungsbeginn vorhandene bewegliche Anlagen lassen
sich mit ursprünglichem Anschaffungsnachweis, vollständiger bisheriger
AfA-Historie, Restbuchwert und bereits gebuchter Startjahres-AfA übernehmen.
Ein bereits genutztes Wirtschaftsgut wird dadurch weder neu angeschafft noch
neu bezahlt; ursprünglicher Beginn, Nutzungsdauer und tatsächliche Alt-Cents
bleiben erhalten. Die verbleibende lineare Jahres-AfA wird getrennt im
vorhandenen EÜR-Journal geprüft und bestätigt.

Der [API-Vertrag](CRM_ERP_HISTORISCHE_ANLAGEN_API.md) grenzt diese Version auf
belegte unveränderte lineare, vollständig betrieblich genutzte bewegliche
Anlagen ein. Andere Methoden, Sonder-AfA, Privatanteile, Gebäude, GWG,
Sammelposten und Abgänge bleiben eigene offene fachliche Pakete. Unterschiedliche
Anschaffungs- und AfA-Monate werden hier nicht ungeprüft verschoben.

## Fertige Abläufe dieses Pakets

- Geschützte PDF-/PNG-/JPEG-Originale bis 5 MiB, Inventaridentität, Datei-SHA256,
  Originalposition und Historiestichtag sind dauerhaft gebunden. Die gleiche
  Originalposition kann nicht unter anderem Inventarnamen doppelt aktiv sein.
- Vorschau, ausdrückliche Annahme, Korrektur, Aufhebung und Historie verwenden
  unveränderliche Fassungen und identische Wiederholungsquittungen. Entzogene
  Finanzrechte gelten auch bei Wiederholung; Bankrechte sind nicht erforderlich.
- Bereits gebuchte positive Folgejahre müssen vor Quellenänderung ausdrücklich
  rückwärts gegengebucht werden. Geschlossene betroffene Perioden bleiben gesperrt.
- EÜR, bestehende Quellen, alte JSON-/CSV-Exporte und deren ursprüngliche
  Quittungen bleiben reproduzierbar. Neue gespeicherte Anlagenübersichten werden
  gegen Originalquellen und den tatsächlichen damaligen Journalpräfix geprüft.
- Drei eigene unveränderliche Tabellen sind im exakten Unternehmensexport und
  Restorehorizont erfasst. Technische Annahmequittungen sind nicht Bestandteil
  des portablen Fachauszugs. Aktueller Finanzhorizont: 13; Restorebericht: 14.
- Der Browser bietet Inventarnummerprüfung, Originalupload, Werteingabe,
  ausdrückliche Vorschau/Annahme, Historie, Originaldownload, Korrektur/Aufhebung
  und getrennte EÜR-Folge-AfA. Unklare Antworten behalten den vollständigen alten
  Auftrag. Private Dialoge verschwinden bei Rechteentzug oder Hintergrundwechsel.

## Tatsächlich ausgeführte Prüfungen

Zahlen überschneiden sich zwischen gezielten und gemeinsamen Läufen; sie werden
nicht zu einer vermeintlichen Gesamtzahl addiert. Logs bleiben unter
`docs/evidence/historical-assets-2026-11-04/` erhalten.

| Prüfung | Ergebnis | Aussage |
| --- | --- | --- |
| Gemeinsame Domain-/Schema-/Exportprüfung | 97/97 | Regeln, echte Übernahme/AfA, Rechte, Perioden, atomarer Fehler, aktuelle und alte Restorefreigaben, Exporte |
| Unabhängiger Review einschließlich EÜR-Regression | 35/35 | 17 eigene Reviewfälle, 900 Fraction-/Kalenderfälle, echter alter Exportcode, vier vollständig neu gehashte Exportverfälschungen |
| Bestehende Finanzregression | 77/77 | Vorjournal, Zuordnungen, Erstattungen, Lohn-/Reisegeld, Bank-EÜR-Anschluss |
| Bestehende HTTP-/Restore-CLI-Regression | 49/49 | Alte Quellen und Berichte bleiben exakt; aktuelle Freigabe verlangt vollständigen neuen Horizont |
| Lokaler HTTP-/MFA-Originaltransport und Identität | 7/7 | Echte 5-MiB-Originale, Byte-/SHA-Download, Übergröße, strenge JSON-Anfrage und Unicode-Identität |
| Getrennte PostgreSQL-Runtime und befüllter Restore | 3/3 | Zwei Verbindungen, unveränderliche Rechte aller drei Tabellen, echte Sicherung/Wiederherstellung, Quellen und Annahmequittungen erhalten |
| Native-/Windows-Quellpakete | 16/16 | Echte ZIP-Manifeste, Importe aus entpacktem Paket, Restorewerkzeug verfügbar |
| Browser-Vertrag und Kontextgrenzen | 11/11 | Echte DTOs, LostACK, Datei-/Hash-/Vorschauverzögerung, Quellenbindung und Rechteentzug |
| Vollständige Node-Regression nach unabhängigem Dialogfix | 516/516 | Bestehende Browsermodule mit neuen Anlagen-/EÜR-/Office-Hooks |
| Echter Chromium-/MFA-/HTTP-Ablauf | 1/1 | Unicode-Identität, Upload/Annahme-LostACK, Financepause, SHA-Original, Folge-AfA/Gegenbuchung, Korrektur/Aufhebung, 390 px, späte Vorschau und private Titelbereinigung |
| Unicode-Längengrenze nach Casefold | 23/23 | Neuer tatsächlicher Gegenfall plus Regeln, unabhängige Regeln und Rechte-/Periodengrenzen |

Die Chromiumprüfung bestätigt Namespace-, PID-, Netzwerk- und Seccomp-Sandbox
vor dem Zugriff auf die lokale Testanwendung. Es wurden keine externen
Finanzanbieter oder Produktionssysteme angesprochen. PostgreSQL verwendete nur
den exklusiv reservierten Loopback-Testcluster; ein vorhandenes Restoreziel
würde unverändert abgewiesen. Der Slot wurde anschließend wieder freigegeben.

Die lesende unabhängige Prüfung führte zur Sperre unterschiedlicher
Anschaffungs-/AfA-Monate; der anschließende Gegenfall war bereits grün. Die
erhaltenen tatsächlichen roten Läufe betreffen einen neuen Export ohne
Anlagenfeld nach historischer AfA, die 413-Antwort für Originalübergröße und
alte Test-Snapshots mit neu hinzugekommenen leeren Tabellen. Ein durch Casefold
auf mehr als 100 Zeichen erweiterter Inventarschlüssel wird bereits bei der
Identitätsprüfung abgewiesen. Reale Altwerte werden nicht geändert.

## Integrationsgrenzen

Die ursprünglichen 1563 Baseline-Dateien wurden vollständig gegen
`work/verification/historical-assets-opening-backend-baseline.json` geprüft.
Die autorisierte separate Anfangssaldo-Summenkorrektur und die später von Root
eingebrachten Opening-Clients sind mit eigenen Vor-/Nachhash-Manifesten in
`work/verification` dokumentiert. Der Hauptbaum besitzt inzwischen weitere
Katalog- und Lohnänderungen; globale Dateien deshalb gezielt zusammenführen.

Neue Backenddateien:

- `backend/accounting_asset_opening_rules.py`
- `backend/business_accounting_asset_openings.py`
- `backend/accounting_asset_opening_sources.py`

Globale Produktänderungen dieses Pakets:

- `backend/business_accounting_euer.py`: additive Quelle/Folge-AfA, gemeinsame
  Sperre mit Vortragsbestätigung, aktive Abhängigkeiten, Reportvalidierung.
- `backend/business_schema.py`: Modulregistrierung, Abhängigkeit und exakter
  Finanzhorizont 13/Restorebericht 14 einschließlich alter freigegebener Berichte.
- `backend/business_api.py`, `backend/business_organization.py`: Routen,
  strenge Anfrageform und bestehendes Finanzmodul.
- `backend/company_export_catalog.py`: ausschließlich die drei exakten neuen
  Finanzquellen; keine Erweiterung auf fremde Bank-/Personaldaten.
- `backend/server.py`, `backend/online/web.py`: begrenzter Originalupload und
  explizite Browserdateien.
- `scripts/native-release.py`, `scripts/package-windows-support.py`,
  `.github/workflows/checks.yml`: explizite Runtime-/Paket-/Browserregistrierungen.
- `web/office/office.js`, `web/office/accounting-euer.js`,
  `web/office/tests/e2e.cjs`: eng begrenzte Anlagen-/EÜR-/Retry-/Lebenszyklushooks.

Die alten Finanztests erweitern nur aktuelle Horizonterwartungen und schließen
neue Module bei absichtlich historischen Migrationen ausdrücklich aus. Alte
Quellstände und bereits angenommene alte Freigabeberichte werden nicht umgedeutet.
Die ursprüngliche Opening-Registrierungsprüfung bleibt ausdrücklich auf ihren
historischen Horizont 12/Report 13 begrenzt; das neue Paket prüft den wirklichen
additiven Übergang zu 13/14 separat.

## Abgeschlossene Clientprüfung und Übergabe

Der unabhängige Browserreview besteht mit 12 neuen Fällen (zusammen mit den
11 eigenen Fällen 23/23) und einem tatsächlichen Chromium-Gegenfall. Ein
initialer Anlagenabruf konnte eine zwischenzeitlich geöffnete Profilansicht
verdrängen. Der neue, ausschließlich für den Anlagen-Host ausgewertete
Dialogzähler verwirft diese verspätete Antwort. Der unveränderte echte
Gegenfall und danach der vollständige Anlagenbrowserablauf bestehen; die
gesamte Node-Regression beträgt jetzt 516/516. Vorherige rote Nachweise
bleiben im [unabhängigen Review](evidence/historical-assets-browser-independent-review-2026-11-04.json) erhalten.

Die [native Anlagenoberfläche](CRM_ERP_HISTORISCHE_ANLAGEN_NATIVE.md) ist mit
17 neuen Tests, 145 bestehenden Regressionen und Analyse ohne Befund geprüft.
Der echte HTTP-Ablauf bei 390 px benutzt einen gewöhnlichen Accountant ohne
`bank.read`: Unicode-Identität, Originaltransport, Original-/Vortrag-/AfA-
Antwortverlust, Kontokorrektur, Perioden, Gegenbuchung, neue Anlagenfassung,
Aufhebung, Originalhistorie und tatsächlicher Rechteentzug. Der eng begrenzte
BusinessSession-Ladefix ist im nativen Nachweis separat erläutert. Beide
Flutter-CI-Läufe entdecken alle Testdateien einschließlich der vier neuen
Dateien; es ist keine zusätzliche selektive Testliste erforderlich.

Backend und beide Clients sind für die gezielte Integration in den aktuellen
Hauptbaum eingefroren. Die Hauptintegration und ihre gemeinsame Regression
führt Root aus. Diese Paketabnahme ersetzt keine Gesamtzielabnahme und keine
steuerliche Freigabe tatsächlicher Daten.
