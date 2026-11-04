# CRM/ERP – Fortschritt und Testergebnisse

Die Abschnitte sind chronologisch; die neuesten Einträge stehen am Ende.
Der [aktuelle Integrationsstand](CRM_ERP_INTEGRATIONSSTAND_2026-11-03.md) bündelt
die belegten Teilabläufe und laufenden Arbeiten. Frühere Zwischenstände und
fehlgeschlagene bzw. unterbrochene Läufe bleiben als Verlauf erhalten.
Der erste Abschnitt gehört zum lokalen Commit `14fe4c9`, der zweite zu `64bdc26`.

## 02.11.2026 – Bestand, Integration und erste Entwicklung

- `CRM_ERP_Gesamtziel.txt` vollständig gelesen und unverändert im Hauptverzeichnis
  gespeichert. 23.863 Bytes, SHA-256
  `a4dea28f6de4afd3e36d1549441aad91ce16dad374f56097979cc2d79b07fbf5`.
- Hauptrepository und vorhandene Arbeitskopien überprüft. `work` lokal von
  `822fe58` auf den vorhandenen integrierten Branchstand `420c4c7` vorgezogen.
- Vorhandene Funktionen und neue Abnahmekriterien werden getrennt dokumentiert.
- Erster Abschnitt gemäß [Umsetzungsplan](CRM_ERP_UMSETZUNGSPLAN.md) umgesetzt:
  Unternehmensbedarf/Module, Instanzbindung und Erhalt signierter Protokolle.

### Implementierter Umfang

1. **Unternehmensbedarf und Module:** fünf Bedarfsangaben, automatische
   Personalvorschläge aus aktiven Mitarbeiterprofilen, manuelle Navigation und
   getrennte fachliche Aktivierung. Flutter und Browser haben eine entsprechende
   Einstellungsoberfläche; berechtigte Nutzer können ausgeblendete Bereiche
   ausdrücklich öffnen. Änderungen sind versioniert und wiederholsicher;
   Ausblenden/Deaktivieren löscht keine Fachdaten. [Nutzung/Migration](CRM_ERP_MODULE.md).
2. **Serverseitige Aktivierungsgrenze:** neue Schreibvorgänge in deaktivierten
   Bereichen werden gesperrt, einschließlich Katalog-/Angebotsübernahmen über
   Adapter. Historische Lesezugriffe behalten ihre bisherigen Rechte. Temporäre
   Sperren verwenden 423, sodass Offlinezeiten erhalten bleiben und nach erneuter
   Aktivierung automatisch synchronisieren. Bereits gebuchte identische
   Zeitereignisse werden nach erneuter Rechte-/Inhaltsprüfung quittiert.
3. **Feste Unternehmensinstanz:** explizite Betreiberbindung zwischen
   Datenbank, Host, Vault-Schlüssel und privater Serverablage; Startprüfung
   ohne Schreibwirkung, Planimport-Worker-Prüfung und unveränderliche
   Identitätszeile. Reservierte Ablagen sind auch vor ungebundenen Altinstanzen
   geschützt. PostgreSQL-Laufzeitrolle hat nur SELECT auf die Identität.
   [Betriebsmodell und Grenzen](CRM_ERP_INSTANZEN.md).
4. **Protokollabschluss:** Inhalts-/Projekt-/Dokumentbindung und gespeichertes
   signiertes PDF werden geprüft. Fehlende signierte PDFs werden nicht neu
   erzeugt. Identische Signaturwiederholung durch denselben Benutzer liefert
   den bestehenden Abschluss; Änderungen bleiben abgewiesen. Bestehende
   Archivbytes werden nicht umgeschrieben. Keine QES behauptet.
5. **Lieferumfang:** neue Module sind in den Windows-Quellpaketlisten enthalten;
   CI führt die neuen HTTP-/PostgreSQL-Prüfungen aus. Die Speicherversion bleibt 7,
   neue Module benötigen dennoch ausdrücklich Migration und Laufzeitrechte.

### Nachprüfung und behobene Befunde

Der unabhängige Code-Review innerhalb dieser Entwicklung fand zwei relevante
Aktivierungslücken: permanente Offline-Konfliktmarkierung bei Deaktivierung
und einen Adapterweg, der die Sperre umgehen konnte. Beide wurden behoben und
durch Regressionstests abgedeckt. Der Instanz-Review fand außerdem die mögliche
Nutzung einer reservierten Ablage durch eine ungebundene Altinstanz und SQLite
`INSERT OR REPLACE` auf der Identitätszeile. Beide Wege sind nun gesperrt; die
Nachprüfung fand im untersuchten Änderungsumfang keinen weiteren offensichtlichen
Befund. Das ist kein unabhängiger externer Sicherheitstest für die Produktfreigabe.

### Prüfungen dieser Sitzung

| Prüfung | Ergebnis | Einordnung |
| --- | --- | --- |
| Bytevergleich Upload/Zieldatei | identisch | Originaldokument unverändert |
| Backend am ursprünglichen Stand `822fe58` | 95 Tests; 21 Fehler, 1 übersprungen | Lauf ohne lokale Socketberechtigung; Socketfehler sind Umgebungsfehler, kein grüner Baseline-Nachweis. Log `work/baseline-backend.log` |
| Backend am integrierten Ausgangsstand | 354 ausgeführt, 353 bestanden, 1 übersprungen | `work/integrated-backend.log`; Skip nur Windows-Job-Object-Test auf Linux |
| Backend nach Entwicklung | 379 ausgeführt, 378 bestanden, 1 übersprungen | `work/final-backend.log`; einschließlich neuer Konfigurations-/Migrations-/Protokollfälle; derselbe Windows-Skip |
| Kaufmännische Fachsuite | 95 bestanden, keine Skips | `work/business-tests.log`; echte lokale KoSIT-/Mustang-/veraPDF-Prüfer und synthetischer SMTP-TLS-Dienst, keine externen Nachrichten |
| Unternehmens-Domäne und HTTP | 16 bestanden | `work/organization-tests.log`; inklusive Antwortverlust, Rollback, Rechteentzug, Adapter-Sperre, 423, gefüllte Schema-7-Migration mit unverändertem PDF |
| Instanz-/Storage-/Schema-/HTTP-Prüfung | 53 bestanden | Zwei synthetische Firmen, MFA/Sitzungen/Objekte/PDFs/Marker/Worker; gezielte Nachläufe nach Review ebenfalls erfolgreich |
| PostgreSQL-CI-Auswahl | 315 Ausführungen, keine Skips; ein gefundener Kompatibilitätsfehler behoben | Legacy-Readiness-Test mit vereinfachtem Storage-Testobjekt kompatibel gemacht; gesamte betroffene Releasegruppe mit 21 Tests danach bestanden, übrige Gruppen zuvor grün. `work/verification/pg-summary.json` |
| Neue PostgreSQL-Protokollfälle | 12 bestanden | Zwei echte Datenbankverbindungen, identischer Signatur-Retry, ein Abschluss/Audit; `work/verification/pg-test_report_integrity_pg.log` |
| PostgreSQL-Konfiguration und Instanzrolle | 4 bestanden | Laufzeitrolle, konkurrierende Schreiber, explizite Migrationsrolle, verbotene Runtime-DML, Neustart und falsche Konfiguration; `work/verification/pg-test_organization_pg.log` |
| Echte HTTPS-Dienstkette | 1 Ablauf plus 1 TLS-Wartungstest bestanden | Lokales Caddy→Gunicorn→PostgreSQL mit MFA/PDF/Ablage/Neustart, ausschließlich Testdaten |
| Flutter am integrierten Ausgangsstand | 310 bestanden, keine Skips; Analyze ohne Befund | `work/verification/flutter-tests.jsonl`, `flutter-analyze.log` |
| Neue/angepasste Flutter-Fälle | Unternehmens-UI mit 18 Tests und Offline-/Protokollgruppen erfolgreich | Breiten 390/1200 px, versteckte Historie ohne Admin, genaue Retry-IDs, echter HTTP-Offlineablauf mit Neustart und 423; gezielte Logs unter `work/` |
| Flutter vollständige Endprüfung | 323 bestanden, keine Fehler/Skips; Analyze ohne Befund | `work/verification/final-flutter.log`, Laufzeit 1:36; `work/organization-flutter-analyze.log` |
| Browser-Komponententests | 39 bestanden, keine Skips | Bestehende 30 plus 9 neue Organisationsfälle |
| Browser-E2E | extern durch Hostumgebung blockiert | Chromium-Sandboxhelfer gehört nicht root; Usernamespace-Alternative kann `/proc/self/uid_map` nicht schreiben. Sandbox wurde nicht deaktiviert. Fixture/Workflowtests vorhanden, kein bestandener visueller Gesamtablauf behauptet |
| Paket-/Quellkonfiguration | 14 Tests bestanden; Source-Check erfolgreich | Neue Backendmodule in Support-/Windowsmanifesten, `work/package-tests.log`; kein nativer Windows-/iPhone-Build auf Linux behauptet |
| Dateierhalt und Diff | Original-SHA unverändert; `git diff --check` ohne Befund | Nur angeforderte Entwicklung und Dokumentation |

Testzahlen sind Ausführungen einzelner Gruppen mit teilweise gemeinsamen
Fixtures; sie werden nicht zu einer angeblichen Gesamtzahl einzigartiger
Abnahmefälle addiert. Logs liegen im ignorierten Arbeitsverzeichnis `work/`;
dieser Bericht und die Tests selbst werden im Repository gehalten.
Der maschinenlesbare [Prüfnachweis](CRM_ERP_PRUEFNACHWEIS.json) hält außerdem
die Ergebnisse, die integrierte Basis und SHA-256-Werte der geänderten
Code-/Testdateien fest.

### Reproduktion

Die vorhandene Python-Umgebung `backend/.venv` und Flutter 3.47.7/Dart 3.13.5 wurden
verwendet. Backendbefehle vom Hauptverzeichnis:

```sh
backend/.venv/bin/python -m unittest discover -s backend -v
PYTHONPATH=backend:backend/online backend/.venv/bin/python -m unittest test_business_organization online.test_organization_http -v
backend/.venv/bin/python -m unittest discover -s scripts -p test_native_release.py -v
node --test web/office/tests/*.test.mjs
```

PostgreSQL verwendet ausschließlich eine neu erzeugte entbehrliche
`smartplan_check`-Datenbank auf Loopback-Port 55433 mit PostgreSQL 16.15.
Die bestehenden Tests verweigern andere DB-Namen/Ziele. Die genaue CI-Auswahl
und neuen PG-Fälle stehen in `.github/workflows/checks.yml`. Die kaufmännische
Suite benötigt die in CI benannten lokalen Validator-/ICC-Pfade. Fluttertests
benötigen das vorhandene SDK/Cache und die Clang-Toolchain für native PDF-Tests.
Lokale Testserver benötigen erlaubte Loopback-Sockets.

### Nächste Entwicklungsabschnitte

- Bestellpositionsgebundene Teil-/Restwareneingänge mit Lager-/Kostenbezug
  als nächste überschaubare Fachlücke innerhalb Abnahme C bearbeiten.
- Angebot/Annahme/Kundenportal und Offline-Protokollkette nach Abnahme B ergänzen.
- Die noch offenen Buchführungs-/Lohnfälle vor der betreffenden Fachumsetzung
  konkretisieren; die damals noch ausstehenden Grundentscheidungen wurden
  später beantwortet (siehe unten).
- Vollständige Instanz-Provisionierung, Schlüssel-/Hostrotation, Restore der
  Bindung und Prozess-/Connector-Isolation ergänzen.

Die Kriterien A–G sind noch nicht vollständig abgenommen. In dieser Sitzung
wurde kein produktiver Server aktualisiert, keine externe Nachricht versendet
und keine produktive Migration oder finanzielle Aktion ausgeführt.

## 02.11.2026 – Einkauf und positionsgebundene Wareneingänge

Ausgangsbasis ist der lokale Grundlagen-Commit `14fe4c9`. Dieser Abschnitt
bearbeitet die Lieferkettenlücke aus R07.02 und den lokalen Teil von Abnahme C.
[Nutzung, Datenvertrag und Grenzen](CRM_ERP_EINKAUF.md) sowie der
[unabhängige interne Review](CRM_ERP_EINKAUF_REVIEW.md) ergänzen diesen Nachweis.

### Implementierter Umfang

- Browser und Flutter führen durch Bestellvorschlag, Korrektur des Entwurfs,
  interne Freigabe, ausdrückliche Dokumentation einer extern erteilten Bestellung
  sowie Teil-/Restlieferungen mit dauerhaftem Verlauf. Lagerbedarf kann auch
  ohne Projekt erfasst werden. Die Anwendung versendet keine Bestellung.
- Jede Lieferung bindet Mengen und tatsächliche Nettoeinstandspreise an die
  ursprünglichen Bestellpositionen und erzeugt echte Lagerbewegungen. Zugänge
  bewerten Lagerbestand; eine Projektentnahme übernimmt den gewichteten
  Einstandspreis und erzeugt Projektkosten.
- Serverseitige Rechte, Quellen-/Lieferrevisionen, wiederholsichere Anfrage-IDs,
  normalisierte Belegreferenzen und atomare Transaktionen verhindern doppelte
  oder zu große Lieferungen und Teilbuchungen bei einem Fehler. Finanzwerte
  werden auch bei Wiederholungen nach aktuellen Leserechten ausgeblendet.
- Browser und App erhalten ausstehende Anfrage-IDs bei verlorenen Antworten
  oder vorübergehender Modulsperre 423. Deaktivierung des Materialmoduls erhält
  die berechtigt lesbare Historie.
- Einheit und Artikelart bleiben nach Freigabe, Reservierung oder Lagerbewegung
  gebunden. Der Wareneingang weist inkonsistente Altquellen zusätzlich ab.
- Vier additive Einkaufs-/Historientabellen sind in Schema, API, Laufzeitrechten,
  Modulsteuerung, CI und Windows-Quellpaketen registriert. Bestehende
  Schema-7-Moduldefinitionen wurden nicht geändert. UPDATE/DELETE und SQLite
  `INSERT OR REPLACE` können die neue Historie nicht ersetzen.

### Prüfungen dieses Abschnitts

| Prüfung | Ergebnis | Umfang / Log |
| --- | --- | --- |
| Einkaufskern und Migration | 24 bestanden | Teil-/Restmengen, Duplikate, Rechte, Konkurrenz, Rollback, alle SQLite-REPLACE-Schlüssel und Migration mit unverändertem signierten Legacy-PDF/Rechnungsentwurf; `backend/test_business_purchasing.py` |
| Artikelidentität und vorhandenes Lager | 19 bestanden | Vier neue Einheiten-/Artikelartfälle plus 15 bestehende Inventarfälle; `work/stock-identity-tests.log` |
| Unabhängiger HTTP-/MFA-Ablauf | 4 bestanden | Einkauf→Teil/Rest→Bestand114,75 EUR→Projektentnahme45,90 EUR→Gerätewartung→signierter Bericht→Neustart; Rechte, 423, Rollback und alte Einheit; `backend/online/test_purchasing_journey.py` |
| Unabhängige Nachprüfung der Datenhaltung | 2 bestanden | Bestandserhalt/Migration und SQLite-REPLACE-Schutz separat erneut ausgeführt; [Review](CRM_ERP_EINKAUF_REVIEW.md) |
| Vollständiges Backend | 407 ausgeführt, 406 bestanden, 1 übersprungen | 59,985 s; nur Windows-Job-Object-Bereinigung auf Linux übersprungen; `work/verification/purchasing-backend-full.log` |
| Kaufmännische Fachsuite | 95 bestanden, keine Skips | 130,129 s; echte lokale KoSIT-/Mustang-/veraPDF-Prüfer und synthetischer SMTP-TLS-Dienst; `work/verification/purchasing-business-services.log` |
| PostgreSQL-Einkauf | 5 bestanden, keine Skips | 7,450 s; Runtime-HTTP, konkurrierende Restlieferung, Rollback, Rechteentzug und additive Migration mit erhaltener tatsächlich finalisierter Rechnung/PDF, Nummern und Audit; `work/verification/pg-test_postgres_purchasing_integration.log` |
| Flutter-Einkauf und Sitzung nach Review | 20 bestanden | 13 Widgetfälle einschließlich 390/1200 px, Projektrollen, Rechteentzug, Präzision, Dialogschließen und Wiederaufnahme; 1 echter HTTP-Ablauf mit 15 m / 52,50 EUR; 6 Sitzungstests; `work/verification/purchasing-flutter-review-targeted.log` |
| Vollständiges Flutter / Analyze nach Review | 337 bestanden, keine Skips; Analyze ohne Befund | Abschließender unveränderter Codestand, 1:40 Laufzeit; `work/verification/purchasing-flutter-review-full.log` und `purchasing-flutter-review-analyze.log` |
| Browser-Komponententests | 52 bestanden | Formular-/Mengenvalidierung, Wiederholung/423, projektbezogene Aktionsrechte sowie Sandbox-Diagnose |
| Echter Browserablauf | 8 Workflows bestanden | Bestehende MFA-/Kalender-/Signatur-/PDF-/Formularabläufe plus neue Einkaufskette, verlorene Antwort, Technikerredaktion und 390-px-Ansicht; `work/verification/browser-e2e-purchasing.log` |
| Paket-/Quellprüfung | 14 bestanden; Source-Check erfolgreich | `work/purchasing-package-tests.log`, `work/purchasing-source-check.log`; kein Windows-/iPhone-Installationsnachweis |

Die Zahlen einzelner Gruppen überschneiden sich und werden nicht addiert.
Alle Prüfdaten sind synthetisch. Die aufgeführten Abschlussprüfungen sind
beendet. Der maschinenlesbare
[Einkaufs-Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_EINKAUF.json) bindet diese Ergebnisse
an die Ausgangsbasis und SHA-256-Werte der geänderten Code-/Testdateien.

Der erste Aufruf der kaufmännischen Suite hatte einen unvollständigen lokalen
`PYTHONPATH`; zwei Testmodule konnten deshalb nicht importiert werden. Nach
Korrektur des Befehls wurde die gesamte Suite mit 95 Fällen erfolgreich
ausgeführt. Das erste Log bleibt unter
`work/verification/purchasing-business-services-initial.log` erhalten.

Die bisherige Browserblockade wurde mit einem ausdrücklich gewählten
Usernamespace-Start behoben. Namespace-, PID-, Netzwerk- und Seccomp-Schutz
werden vor Appzugriff tatsächlich überprüft; die Sandbox bleibt eingeschaltet.
Desktop- und mobile Lieferhistorie wurden zusätzlich anhand der Screenshots
unter `work/verification/browser-purchasing-previews/` visuell geprüft. Der
Loopback-Browserlauf ersetzt keinen neuen HTTPS- oder echten iPhone-Nachweis.
Die PostgreSQL-Migration beweist den Erhalt einer finalisierten Rechnung mit
PDF; dieser besondere Migrationsfall umfasst keine XML-Konformitätsprüfung.

Der abschließende UI-Review führte zu gezielten Korrekturen: Der Browser erlaubt
projektlosen Lagerbedarf und verwendet beim geöffneten Auftrag dessen
Projektberechtigungen. Flutter lädt ebenfalls die Rechte des Detailprojekts,
leert die Anzeige bei einer bekannten Zugriffsverweigerung und begrenzt
Mengen/Einstandspreise passend zum Backend auf vier Nachkommastellen. Seine
Einkaufseditoren bewahren unbestätigte Originaleingaben beim Schließen in der
laufenden Sitzung auf und verwenden beim Wiederöffnen denselben Anfragebeleg.
Dieser Puffer wird bei Abmeldung/definitiver Antwort entfernt; er übersteht
keinen vollständigen Prozessneustart. Der Review und die gezielten neuen
Fehlerfalltests prüfen diese begrenzte Zusage.

Reproduzierbare neue Backendbefehle vom Hauptverzeichnis:

```sh
PYTHONPATH=backend backend/.venv/bin/python -m unittest test_business_purchasing test_stock_article_identity -v
PYTHONPATH=backend:backend/online backend/.venv/bin/python -m unittest online.test_purchasing_journey -v
PYTHONPATH=backend:backend/online backend/.venv/bin/python -m unittest online.test_postgres_purchasing_integration -v
node --test web/office/tests/*.test.mjs
node web/office/tests/e2e.cjs
```

Die PostgreSQL-Prüfung benötigt wie zuvor `SMARTPLAN_TEST_DSN` zur bewachten
entbehrlichen Loopback-Datenbank `smartplan_check`. Der Browserlauf benötigt
Playwright/Chromium und die Python-Testumgebung; die bewusste Alternative
`SMARTPLAN_BROWSER_NAMESPACE_SANDBOX=1` funktioniert nur mit tatsächlich
verfügbarer und anschließend geprüfter Namespace-Sandbox. CI registriert
beide neuen Online-Testdateien ausdrücklich.

### Abnahmestand und nächste Schritte

Der lokale Liefer-/Lager-/Kostenablauf ergänzt den bestehenden Servicekern.
Eine tatsächlich ausgelöste Lieferantenbestellung, verknüpfte Original-
Lieferscheine und die strukturierte Gerätebindung an die Bestell-/Entnahmeposition
sind noch offen. Der HTTP-Test nutzt für die Gerätezuordnung Projekt und
dokumentierte Referenzen in der Notiz. Retouren, Storno und Bestelländerungen
sind noch nicht implementiert. C ist deshalb weiterhin insgesamt offen.

Als nächster größerer Abschnitt folgen Angebotsannahme und Kundenportal aus B.
Zuvor wird die eingeschränkte Artikelwahl für reine Lagerrollen gezielt ergänzt:
Flutter benötigt im Vorschlagseditor derzeit Finanzleserecht; der Browser
findet ohne globales Finanzleserecht nur Artikel mit Lagerhistorie bzw.
vorhandenen Vorschlagspositionen. Eine preisfreie sichere Katalogsuche fehlt.
Die übrigen offenen Punkte des Gesamtplans sowie echte Geräte-, Betriebs- und
Fachabnahmen bleiben bestehen. In diesem Schritt wurden keine produktiven
Daten verändert und keine externe Bestellung oder Nachricht ausgelöst.

### Konkretisierung durch den Nutzer

Am 02.11.2026 hat der Nutzer die zwei offenen Grundentscheidungen beantwortet:

- Erste vollständige Buchhaltung: **Einzelunternehmen mit EÜR**.
- Erste deutsche Lohnabrechnung: **reguläre Mitarbeiter und Minijobs**.

Anforderungsmatrix, Umsetzungsplan und Übergabe halten diese Entscheidungen
fest. Sie bestimmen den nächsten Fachumfang und sind noch kein Nachweis einer
implementierten oder fachlich abgenommenen Buchhaltung beziehungsweise Payroll.

## 02.11.2026 – Preisfreier Einkaufskatalog und vollständige Artikelredaktion

Ausgangsbasis ist `64bdc26`. Die im vorherigen Abschnitt dokumentierte
Artikelauswahlgrenze für reine Lagerrollen wurde geschlossen. Browser und
Flutter verwenden bei passender Serverfähigkeit die neue preisfreie Suche;
ältere Server behalten einen ausdrücklich erkennbaren Fallback. Der vorhandene
Bestell-/Lieferablauf und die Bindung unbestätigter Anfragen bleiben erhalten.

### Änderung und Review

- `GET /business/purchasing/articles` liefert genau sieben operative
  Artikelfelder, auch an Finanzberechtigte. Aktive Material-/Maschinenartikel
  ohne Lagerhistorie sind auswählbar. Suche, begrenzte Seiten und aktuelle
  Projektrechte werden serverseitig geprüft. Der Abruf schreibt keine Daten.
- Browser und App ergänzen Suche und weitere Treffer. Vorhandene Auswahl und
  Mengen bleiben beim Suchen erhalten. Die neue Serverfähigkeit
  `purchasing_catalog` verhindert Anfragen an nicht vorhandene alte Endpunkte.
- Die erweiterte Prüfung fand einen tatsächlichen Fehler im bisherigen
  Lagerdatenvertrag: Eine reine Feldsperrliste ließ verschachtelte Margen- und
  Kalkulationswerte aus echten `pricing_preview`-/`save_article`-Vorgängen
  passieren. Drei neue Regressionen reproduzierten den Fehler vor der Korrektur.
- Scan, Bestellantworten, Bewegungen und deren Wiederholungen verwenden für
  unberechtigte Leser jetzt eine ausdrückliche Artikelfeldliste. Gespeicherte
  Preisnachweise, Stücklisten, Lagerjournale und die vollständige Ansicht für
  Finanzberechtigte werden nicht umgeschrieben. Schema-/Guarddefinitionen
  bleiben unverändert. Der unabhängige HTTP-/PostgreSQL-Review bestätigt den Fix.

### Prüfungen dieses Abschnitts

| Prüfung | Ergebnis | Nachweis |
| --- | --- | --- |
| Einkauf und Lager nach Redaktionsfix | 49 bestanden | 31 Purchasing-Fälle einschließlich sieben neuer Katalogfälle; 18 Inventarfälle einschließlich drei echter Kalkulations-/Stücklistenregressionen; `work/verification/inventory-calculated-redaction-domain.log` |
| Unabhängige HTTP-/MFA-Fälle | 4 bestanden | Preisfreie Auswahl ohne Bestand, Vorschlag ohne Finanzrecht, Suche/Seiten, frische Rollen/Projektgrenzen, unveränderte Datenbank und echte Kalkulationsdaten in Scan-/Bestellantworten; `work/verification/catalog-http.log` |
| PostgreSQL | 6 bestanden; betroffener Katalogfall nach Preisfix erneut bestanden | Getrennte Laufzeitrolle, Lagerbenutzer ohne Finanzrecht, unveränderte Daten-/Schemasummen; erneuter Fall mit tatsächlich kalkuliertem Artikel; `work/verification/catalog-postgres.log`, `catalog-postgres-calculated.log` |
| Vollständiges Backend | 417 ausgeführt, 416 bestanden, 1 übersprungen | 66,091 s; nur vorhandener Windows-Job-Object-Test auf Linux übersprungen; `work/verification/catalog-backend-full.log` |
| Flutter | 342 bestanden, keine Skips; Analyse ohne Befund | Unveränderter Appstand; `work/verification/purchasing-catalog-flutter-full.log` und `purchasing-catalog-flutter-analyze.log` |
| Flutter gezielt nach Backend-Preisfix | 19 bestanden | 18 Widgetfälle plus echter HTTP-Ablauf der Lagerrolle; `work/verification/purchasing-catalog-flutter-after-redaction.log` |
| Browser-Komponenten | 58 bestanden | Katalogzustand, Suchwechsel/Seiten, Projektrechte, preisfreie Antwortfelder, ältere Server und Wiederholung |
| Echter Browserablauf | 9 Workflows bestanden | Einschließlich Lagerrolle, Artikeln ohne Bestand, Suche/Seiten, projektlosem Vorschlag/Bearbeitung, kalkuliertem Artikel, Preisredaktion und 390-px-Ansicht; `work/verification/catalog-browser-e2e.log` |

Gruppenzahlen überschneiden sich und werden nicht zu einzigartigen Abnahmen
addiert. Originaldaten und Betriebszugänge werden von den synthetischen Tests
nicht verwendet. Vorher-/Nachherbelege des Preisfehlers bleiben unter
`work/verification/inventory-calculated-redaction-before.log` und dem
angegebenen erfolgreichen Domänenlog erhalten.

Zwei Browseranläufe scheiterten beim nachträglichen Lesen eines bereits
verfallenen DevTools-Antwortkörpers. Der Testhelper erfasst nun die echten
Serverantworten vor ihrer Weitergabe an den Browser. Die kontrolliert verlorene
Wareneingangsantwort bleibt ein eigener Fehlerfall mit realer Buchung und
identischer Wiederholung. Der abschließende Gesamtlauf ist grün. Namespace-,
PID-, Netzwerk- und Seccomp-Sandbox wurden vor Appzugriff erneut live geprüft.
Desktop- und Mobilansicht der Suche wurden anhand der Screenshots unter
`work/verification/catalog-browser-previews/` zusätzlich visuell geprüft.

Der [Katalog-Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_KATALOG.json) enthält
Ausgangscommit, Ergebnisse und SHA-256-Werte der geänderten Code-/Testdateien.
Reproduktion der gezielten Backendfälle vom Hauptverzeichnis:

```sh
PYTHONPATH=backend backend/.venv/bin/python -m unittest test_business_inventory test_business_purchasing -v
PYTHONPATH=backend:backend/online backend/.venv/bin/python -m unittest online.test_purchasing_catalog_http -v
PYTHONPATH=backend:backend/online backend/.venv/bin/python -m unittest online.test_postgres_purchasing_integration -v
node --test web/office/tests/*.test.mjs
node web/office/tests/e2e.cjs
```

Für PostgreSQL und Chromium gelten die beschriebenen Loopback-/Sandbox-
Voraussetzungen des vorherigen Abschnitts. Die neue HTTP-Datei ist ausdrücklich
in CI registriert. Diese Prüfungen stellen keine Produktivinstallation dar.

### Grenzen und nächster Abschnitt

Die preisfreie Suche verwendet derzeit einen Katalogscan unter der bestehenden
Transaktionssperre. Begrenzte Antwortseiten sind kein Nachweis hoher
Suchleistung bei sehr großen Lieferantenkatalogen; eine indexgestützte Suche
bleibt eine spätere Optimierung. Lieferantenversand, strukturierte Gerätebindung,
Original-Lieferscheinverknüpfung und dauerhafte Offline-Wareneingänge bleiben
wie im vorherigen Abschnitt offen. C ist weiterhin nicht insgesamt abgenommen.

Der [Portalplan](CRM_ERP_PORTAL_PLAN.md) beschreibt den nächsten eigenständig
umsetzbaren Abschnitt: getrennte Kundenzugänge, Ansicht/PDF eines ausdrücklich
freigegebenen finalen Angebots, nachvollziehbare Annahme/Ablehnung und eine
gesonderte interne Übernahme in einen Auftragsbestätigungsentwurf. Er bewahrt
das bisherige Projekt-/Belegmodell und trennt Kunden- von internen Sitzungen.
Der Plan ist noch kein implementiertes Kundenportal; die Gesamtabnahme B bleibt
offen. Die Entscheidungen EÜR sowie reguläre Mitarbeiter/Minijobs gelten weiter.

## 02.11.2026 – Angebotsportal mit getrennter Kundenerklärung

Ausgangsbasis ist `54b08c2`. Der [entwickelte Umfang](CRM_ERP_PORTAL.md)
ergänzt finale Angebote im bestehenden Kundenprojekt um eine gezielte Freigabe,
eine getrennte Kundensitzung, die Original-PDF-Ansicht, ausdrückliche Annahme
oder Ablehnung und eine gesonderte interne Übernahme in einen
Auftragsbestätigungsentwurf. Der [API-Vertrag](CRM_ERP_PORTAL_API.md) hält
Felder, Rechte, Wiederholungen und Restoreverhalten fest.

### Umsetzung und überprüfte Grenzen

- Das additive Modul `business_portal` erhält eigene Kundenprincipals,
  Freigaben, Sitzungen und unveränderliche Erklärungs-/Übernahmebelege.
  Mitarbeiter, Offlinegeräte und Kunden verwenden getrennte Zugangsdaten.
  `portal.manage` ergänzt die bestehenden projektspezifischen Fachrechte;
  Mitarbeiterrollen erhalten es nicht automatisch.
- Der Online-Dienst meldet `offer_portal` nur im geprüften HTTPS-Kontext.
  Lokale Server bieten keinen scheinbar erreichbaren Kundenlink an. Die neue
  Kundenoberfläche importiert weder das interne Officeprogramm noch dessen
  Sitzung. Eine feste Feldliste entfernt interne Kosten, Margen und Quellen.
- Ein Kundenlink wird genau einmal ausgegeben; gespeichert wird nur sein
  Geheimnishash. Eine identische Erstellungswiederholung liefert dieselbe
  Freigabe ohne Geheimnis. Ein Ersatz verlangt einen ausdrücklichen Widerruf
  und eine neue Freigabe. Auch nach einer Entscheidung ist ein neuer reiner
  Lesezugang zur historischen Fassung möglich; eine zweite Erklärung nicht.
- Annahme/Ablehnung bindet Fassung, Inhalts-/PDF-Hash, erklärten Namen,
  Zeitpunkt und Wortlaut. Es gibt höchstens eine abschließende Erklärung je
  Angebot. Die interne Übernahme benötigt zusätzliche Rechte und schreibt
  ihren Nachweis atomar mit genau einem echten Auftragsbestätigungsentwurf.
  Bereits vorhandene manuelle Zielbelege verhindern eine doppelte Übernahme.
- Widerruf bleibt bei fachlich deaktivierten Belegen und im lesenden
  Kompatibilitätsmodus möglich. Aktuelle Rechte werden auch vor Antworten auf
  Wiederholungen geprüft. Neue geschäftliche Portalaktionen beachten Modul-,
  Betriebs- und Restore-/Finanzabgleichssperren.
- Öffentliche Anfragen prüfen HTTPS-Origin, Host, Tokenart, Methode, genaue
  JSON-Felder und 16-KiB-Grenze. HMAC-Ratenzähler werden vor anschließenden
  Eingabe-/Authentifizierungsfehlern festgeschrieben. Die Grenzen je
  Proxy-Client/60 Sekunden sind 120 Anfragen, 10 Sitzungsöffnungen und
  30 Entscheidungsversuche; rohe IPs/Geheimnisse werden nicht gespeichert.
- Normale Migrationen erhalten Freigaben. Ein tatsächlicher SQLite- oder
  PostgreSQL-Restore widerruft alte Einladungen, deaktiviert Principals und
  entfernt Kundensitzungen. Historische Erklärungen, Übernahmen und Archive
  bleiben erhalten. Es wird kein Mitarbeiter für Kunden-/Restoreaktionen
  erfunden.

### Prüfstand Backend und Betrieb

| Prüfung | Ergebnis | Nachweis |
| --- | --- | --- |
| Portal-Domäne und Registrierung | 26 bestanden | 22 Domänen-/Migrationsfälle und 4 Registrierungsfälle; `work/verification/portal-domain.log` |
| Registrierung und Router | 10 bestanden | Echte lokale/Online-/Offline-/Legacy-Fähigkeiten, alte Modulinstallation und bestehende Routinggrenzen; `portal-registration.log` |
| Schema, Foundation und Organisation | 58 bestanden | Bestehende Rechte, Module, Migrationen und Datenintegrität; `portal-registry-foundation-regressions.log` |
| Unabhängige Portalreisen | 9 bestanden | 8 Flask-HTTPS-/MFA-Fälle plus ein echter TLS-Socketfall; `portal-http-tls-journey.log` |
| HTTP-/Restore- und bestehende Regressionen | 59 bestanden | 7 neue Transport-/Restorefälle, unabhängige Reisen sowie Instanz-, Intake-, Backup-, Kunden-, Offline- und Schemaprüfungen; `portal-http.log` |
| PostgreSQL mit getrennten Rollen | 8 bestanden, keine Skips | Echte Migration, Laufzeit-ACLs/Trigger, parallele Verbindungen, Rollback, Neustart und pg_dump/pg_restore; `pg-test_postgres_portal_integration.log` |
| Echter Caddy-TLS-/Wartungstest | 1 bestanden | Neue Portaldateien und öffentliche Portalrouten im vorhandenen Proxy-/Wartungsvertrag; eigene vertrauenswürdige Test-CA, synthetischer Upstream; `portal-caddy-tls.log` |
| Vollständiges Backend | 443 ausgeführt, 442 bestanden, 1 übersprungen | 69,135 s; bestehender Windows-Job-Object-Test auf Linux übersprungen; `portal-backend-full.log` |
| Paketquellen | 14 bestanden | Native-/Windows-Supportmanifeste enthalten das neue Modul; kein nativer Gerätebuild behauptet; `portal-native-release.log` |

Die Gruppen überschneiden sich und werden nicht als einzigartige Abnahmen
addiert. Alle genannten Protokolle liegen unter `work/verification/`.
Der TLS-Fall verwendet einen realen lokalen Server, eine ausdrücklich
vertraute synthetische CA und aktive Hostnamenprüfung. Unbekannte CA und
falscher Hostname werden abgewiesen. PostgreSQL-HTTP-Fälle verwenden dagegen
den Flask-Testclient mit echter Datenbank. Ein zusätzlicher echter Caddy-Lauf
prüft TLS, CSP und Wartungssperre für die neuen Portalpfade gegen einen
synthetischen Upstream. Keiner dieser Nachweise ist ein produktives
Caddy-/Hostingdeployment.

Die erste Integration reproduzierte und korrigierte eine fehlende statische
Featuredeklaration sowie die falsche Feldprüfung in SQLite-Rows. Die
Registrierungs-/Domänen-/HTTP-Regressionen prüfen diese realen Datenwege.
Historische Migrationen erhalten vorbestehende finale Angebote/PDFs und
signierte Protokolle. Echte Restorefälle erhalten Erklärungen, Entwürfe,
Nummern und Audit; ein absichtlich fehlgeschlagener SQLite-Restore entfernt
nur den neu erzeugten Kandidaten und erhält Quelle und Sicherung.

### Bedienoberflächen und unabhängiger Review

Browser und Flutter ergänzen die Portalverwaltung am finalen Angebot. Der
Flutter-Einstellungsbereich bietet außerdem einen generischen Fachrechteeditor
für die vorhandenen Rechte und Geltungsbereiche. Er verwendet die bestehenden
Benutzer-/Grant-Routen und erweitert keine serverseitige Berechtigung.
Kundenseite, Token und unbestätigte Erklärung bleiben getrennt vom internen
Officeprogramm und nur im Arbeitsspeicher des Browserfensters.

Der unabhängige Flutter-Review reproduzierte einen verspäteten
Erstellungsabschluss: Nach zwischenzeitlich bekanntem Rechteentzug oder
Widerruf konnte die Oberfläche erneut einen Kundenlink anzeigen. Der korrigierte
Vorgangsvergleich verwirft diese späte Antwort. Zwei verzögerte-Antwort-Fälle
sichern die Änderung; andere geschäftliche Wiederholungen umgehen weiterhin
keinen Betriebsmoduswechsel. Nur der genau definierte Portalwiderruf bleibt als
Sicherheitsaktion bei identischem Inhalt, Anfrage-ID und Sitzung nutzbar.

Der vollständige Flutterlauf besteht **362 Tests ohne Skips** in rund
104 Sekunden; `flutter analyze` meldet keine Befunde. Das gezielte Set enthält
**26 bestandene Prüfungen**: zehn Portalwidgets, einen echten HTTP-Ablauf,
neun Fachrechtefälle und sechs Sessionfälle. Die Protokolle liegen unter
`work/verification/portal-flutter-full.log`, `portal-flutter-analyze.log` und
`portal-flutter-targeted.log`. Das belegt keine physische
Windows-/iPhone-Installation.

Die Browser-Unitprüfungen bestehen **72 Tests**. Die echte Chromiumprüfung
verwendet synthetische Daten und den lokalen HTTP-Fixtureadapter für den
bestehenden HTTPS-Proxyvertrag; ihr tatsächlicher TLS-Nachweis ist der oben
separat genannte Sockettest. Namespace-, PID-, Netzwerk- und Seccomp-Sandbox
werden vor Anwendungszugriff live geprüft. Desktop und 390-px-Kundenseite
wurden zusätzlich anhand der Screenshots unter
`work/verification/portal-browser-previews/` visuell geprüft.

Der abschließende Browser-Gesamtlauf besteht **zehn echte Abläufe**
(`work/verification/portal-browser-e2e.log`). Der neue Portalablauf prüft
verlorene Erstellungs-, Sitzungs- und Entscheidungsantworten, bewusste
Neufreigabe, zwei getrennte Kunden, bytegleiches Original-PDF, Annahme und
Ablehnung, ausdrückliche Auftragsübernahme, Widerruf bei deaktivierten Belegen
und die schmale Kundenseite. Die vorhandenen Einkaufs-, Planungs-,
Dokumentations-, Signatur-, Rollen- und Formularabläufe bleiben enthalten.

Zwei erste Browserläufe deckten Fehler im Testablauf auf: eine falsche
Feldbezeichnung für die Belegaktivierung und eine fehlende Wartebedingung beim
Wechsel auf die ältere Kalenderansicht. Der korrigierte Test wartet auf den
tatsächlich sichtbaren Kalender und prüft weiter exakt sieben Tage sowie
fehlende Timeline/Ansichtsauswahl. Keine Produktberechtigung oder
Sandboxbedingung wurde abgeschwächt. Die ersten Logs bleiben als
`portal-browser-initial.log` und `portal-browser-calendar-wait.log` erhalten.

### Reproduktion und nächster Umfang

Der [Portal-Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_PORTAL.json) enthält
Ausgangscommit, Ergebnisse und SHA-256-Werte der geänderten Code-/Testdateien.
Gezielte Befehle vom Hauptverzeichnis:

```sh
PYTHONPATH=backend backend/.venv/bin/python -m unittest test_business_portal test_business_portal_registration -v
PYTHONPATH=backend:backend/online backend/.venv/bin/python -m unittest online.test_portal_http online.test_portal_journey -v
PYTHONPATH=backend:backend/online backend/.venv/bin/python -m unittest online.test_postgres_portal_integration -v
node --test web/office/tests/*.test.mjs
node web/office/tests/e2e.cjs
```

Für PostgreSQL gilt weiterhin die ausschließlich synthetische Loopback-DSN
`smartplan_check` mit getrennten Migrations-/Laufzeitrollen. Der PG-Test
verweigert ein vorhandenes Restoreziel und entfernt nur seine eigens erzeugte
Testdatenbank. Chromium benötigt die dokumentierte aktive Sandbox;
`test_release_tls` zusätzlich `SMARTPLAN_CADDY_BINARY`. Die neuen Onlinefälle
sind ausdrücklich in CI registriert. Alle Ergebnisse beziehen sich auf
synthetische Daten und lokale Dienste; es wurde kein Kundenlink versendet und
keine produktive Installation durchgeführt.

Das Originalziel ist weiterhin bytegleich zum Upload, SHA-256
`a4dea28f6de4afd3e36d1549441aad91ce16dad374f56097979cc2d79b07fbf5`.
R05.04/R05.05 und Abnahme B/G bleiben als Gesamtanforderungen offen: allgemeine
Kundenkonten, Dateiaustausch, Projektfreigaben, Angebote vor Projektanlage,
Offline-Protokollkette und vollständige Kosten-/Finanzabstimmung fehlen noch.
Die unabhängige EÜR-Vorbereitung prüft nun vorhandene Zahlungen und
Eingangsbelege. EÜR legt die umsatzsteuerliche Ist-/Sollversteuerung nicht fest;
der tatsächliche Umsatzsteuerstatus wurde separat erfragt und ist bis zur
Antwort als offen zu behandeln. Das blockiert die übrige Entwicklung nicht.

Der geprüfte Portalumfang ist im lokalen Commit `cb60561` gesichert. Der
[EÜR-Plan](CRM_ERP_EUER_PLAN.md) hält anschließend den tatsächlichen Bestand,
offizielle Quellen mit Abrufgrenzen und die nächsten Schritte E1a–E1d fest.
Er trennt vorhandene Kundenzahlungen, Eingangsoriginale und Prüfexporte von
einem noch zu entwickelnden Journal. Als erstes folgt Quellen-/Geldfluss-
erfassung; Zuordnung, Korrekturen, Perioden und Beraterpaket bauen darauf auf.
Der Plan ist Dokumentation und kein neuer Funktions- oder Testnachweis.

## 02.11.2026 – E1a: belegte EUR-Geldflüsse

Auf Basis `060246b` ergänzt das additive Modul `business_accounting` sechs
eigene Tabellen für Geldkonten/Versionen, Geldflüsse, Quellenbeziehungen,
Originalbindungen und Anfragequittungen. Alte Kundenzahlungen, Zuordnungen,
Belegoriginale, finale Archive und historische Schemachecksummen bleiben
unverändert. [Bedienung und Betreiberablauf](CRM_ERP_EUER_BETRIEB.md) sowie
[API-Vertrag](CRM_ERP_EUER_E1A_API.md) halten den tatsächlichen Umfang fest.

Die bestätigte Nutzervorgabe bleibt **Einzelunternehmen mit EÜR**; reguläre
Mitarbeiter und Minijobs gehören zum späteren Lohnmodul. Umsatzsteuerstatus und
Übernahmegrenze sind weiterhin offen. E1a berechnet weder Steuern noch Gewinn
oder eine Jahres-EÜR. Alle Geldflüsse bleiben steuerlich ungeklärt; bestehende
Refunds ohne ursprüngliche Erstattungsreferenz erhalten einen eigenen offenen
Klärungsgrund. R08.05 ist teilweise umgesetzt, seine vollständige Abnahme offen.

### Verhalten und Schutz der Historie

Versionierte EUR-Geldkonten können ausdrücklich angelegt, umbenannt und
deaktiviert werden. Eine bestehende Kundenzahlung lässt sich genau einmal
lesend übernehmen. Manuelle Auszahlungen verweisen auf ein geprüftes
Eingangsoriginal und eine konkrete Prüfversion. Teil-/Restauszahlungen werden
über alle Konten und Benutzer gemeinsam gegen den geprüften Bruttobetrag
begrenzt. Ein identisches Original unter anderer Beleg-ID eröffnet keine
zweite Zahlungskapazität. Geldflüsse lösen keine Überweisung aus und verändern
keinen bisherigen offenen Posten.

Anfragen binden bestätigte Quellenhashes, Originale, Kontoversionen und
Auszahlungsstände. Nach unklarer Übertragungsantwort liefert dieselbe Anfrage
den bestätigten historischen Geldfluss zurück, auch nach späterer legitimer
Kontenumbenennung/Deaktivierung oder erneuter Belegprüfung. Frische Rechte,
Quellenintegrität und Betriebssperren gelten weiterhin. Neue Vorgänge prüfen
aktuelle Versionen; eine geänderte Belegprüfung nach erster Auszahlung bleibt
bis zur späteren fachlichen Klärung gesperrt. Originalbytes und archivierte
Dokumente werden tatsächlich gegen ihre Nachweise geprüft.

Globale Accountingrechte und globales `finance.read` sind zusätzlich zu den
bisherigen Quell-/Projektrechten erforderlich. Neue Mitarbeiterdefaults oder
projektbezogene Accountingfreigaben gibt es nicht. Bei mehrprojektigen
Zahlungen muss die gesamte Quelle berechtigt sein. Verborgene Einträge werden
weder teilweise angezeigt noch in Trefferzahlen verraten. Die Ansicht
kennzeichnet „Nur freigegebene Quellen“, ohne Projektfilter oder Behauptung
einer vollständigen Unternehmenssicht.

SQLite erhält additive Konfliktguards auch für die alten Finanzquellen, sodass
`INSERT OR REPLACE` deren Unveränderlichkeit nicht umgehen kann. PostgreSQL
verwendet getrennte Runtime-/Migrationsrollen und die vorhandene gemeinsame
Transaktionssperre. Ein Fehler nach Einfügen eines Geldflusses rollt auch
Quellenbindung, Anfragequittung und Audit zurück.

### Wiederherstellung und Paketierung

Ein tatsächlicher lokaler SQLite-Restore setzt nun ebenfalls eine frische
Restore-ID und Finanzsperre. PostgreSQL erhält den bestehenden Datenschutz-/
Operatorablauf. Bei installiertem Accountingmodul verlangt der Finanzabgleich
Schema 2 mit exakt passendem Accountinghorizont und einer gesonderten
Bestätigung des unabhängig geprüften Zeitraums seit der Sicherung. Ein aus
derselben Sicherung berechneter Hash ersetzt keinen externen Zahlungsabgleich.

Die lokale CLI öffnet nur vorhandene Dateien, erzeugt keine Tabellen und
migriert keine Altstände. `--inspect` liest einen konsistenten Snapshot und
erteilt keine Freigabe. Die getrennte Freigabe verlangt einen privaten,
eindeutigen JSON-Bericht sowie den ausdrücklich bestätigten App-/Serverstopp;
sie speichert den Hash der tatsächlich gelesenen Berichtsbytes. Die
Schreibtransaktion schützt gegen parallele Writer, beweist aber nicht die
Abwesenheit von WAL-Leseprozessen. Fehlgeschlagene Prüfungen lassen die Sperre
und Historie unverändert. Betreiberwerkzeug, Bedienungsanleitung und
Schema-2-Vertrag sind im lokalen Windows-/Supportmanifest enthalten.

### Ausgeführte Backend-/Betriebsprüfungen

| Gruppe | Ergebnis | Nachweis unter `work/verification/` |
| --- | --- | --- |
| E1a-Domäne/Migration | 19 bestanden, 3,633 s | `accounting-domain.log` |
| Registrierung/Rechte/Capabilities | 4 bestanden | `accounting-registration.log` |
| Unabhängige HTTP-/MFA-Journeys | 8 bestanden, 2,079 s | `accounting-http-journey.log` |
| HTTP-/Restore-/Operator- und Bestandsregressionen | 41 bestanden, 8,043 s, davon 8 neue Operator-/Grenzfälle | `accounting-http-restore.log` |
| Neue PostgreSQL-Abnahmefälle | 10 unterschiedliche Fälle bestanden, keine Skips | `pg-accounting-domain.log`, `pg-accounting-migration-rollback-restore.log` |
| Bestehende PG-Release-/Restore-/Migrationsregressionen | 12 bestanden, 27,869 s | `pg-accounting-release-regression.log` |
| Vollständiges Backend | 466 ausgeführt, 465 bestanden, 1 übersprungen, 78,854 s | `accounting-backend-full.log`; vorhandener Windows-Job-Object-Test auf Linux übersprungen |
| Native-/Supportpaketquellen | 15 bestanden, 2,795 s | `accounting-native-release.log`; echte Paketentpackung, Backendimport und Betreiber-CLI-Aufruf, kein nativer Gerätebuild |

Die Gruppen überschneiden sich und werden nicht als einzigartige Abnahmen
addiert. HTTP verwendet Flask-HTTPS-Testclients mit echtem MFA und SQLite bzw.
PostgreSQL, keinen neuen tatsächlichen TLS-/Hostingnachweis. PostgreSQL benutzt
ausschließlich den synthetischen Loopbackbestand `smartplan_check`; tatsächliche
Rechnungsausstellung unter Runtime-Policy, unabhängige Verbindungen/Races,
SQL-Fehlerrollback, additive Migration und `pg_dump`/Restore sind enthalten.
Das eigens erzeugte Restoreziel wurde anschließend entfernt.

Zwei anfängliche PostgreSQL-Fehler betrafen ausschließlich neue Testfixtures:
falsche Protokollart und falscher Eigentümer einer zur Fehlerauslösung angelegten
Triggerfunktion. Die betroffenen Fälle bestanden nach Korrektur; produktive
Rechte/Guards wurden nicht gelockert. Ein enger Domainfix übersetzt beschädigte
gespeicherte Quellen in einen Integritätskonflikt 409; ungültige neue Eingaben
bleiben 400, fehlende Quellenrechte 403/404. Eine eigene Regression prüft dies.

### Browser, Flutter und unabhängiger Review

Browser und Flutter ergänzen den globalen Einstieg „EÜR-Vorbereitung“ im
Finanzbereich mit Geldkonten, Zahlungsquellen, Auszahlungen und Vorjournal.
Alte Server ohne Feature werden nicht mit neuen Accountingrouten angesprochen;
Offline-/Restore-/Modulsperren bleiben wirksam. Die Fachrechteeditoren bieten
Accountingrechte nur global an. Kein neuer allgemeiner Hauptbereich oder
Projektfilter behauptet eine vollständige Unternehmensbuchhaltung.

Der unabhängige Review führte zu eng begrenzten Korrekturen: Ein bestätigter
Quellenrechteentzug entfernt veraltete Browserdetails; ein verspäteter Fehler
schließt keinen inzwischen neu geöffneten Dialog. Flutter bindet erneut
geöffnete Formulare an den ursprünglichen vorgemerkten Vorgang und verwirft
späte Abschlüsse nach Wechsel des Kontexts. Die tief kopierten Pendingwerte
können den gespeicherten Befehl nicht verändern. Zwei Regressionen prüfen den
erneut geöffneten Vorgang während einer laufenden Übertragung und die später
eintreffende erste Quittung; es entsteht keine zweite Auszahlung. Einzeilige
Verwendungszwecke und strikte Kalenderdaten entsprechen dem Serververtrag.

Die gezielte Fluttergruppe besteht **38 Prüfungen**: 20 Accountingwidgets,
einen echten HTTP-Ablauf, elf Fachrechte- und sechs Sessionfälle. Der vollständige
Flutterlauf besteht **385 Tests ohne Skips** in rund 130 Sekunden
(`e1a-flutter-full.log`).
`flutter analyze` meldet keine Befunde (5,0 s). Nachweise:
`e1a-flutter-targeted.log` und `e1a-flutter-analyze.log`. Der HTTP-Fall verwendet
einen berechtigten Nicht-Owner, frische globale/Projekt-/Quellrechte, verlorene
Antworten, spätere Konten-/Belegänderungen und unveränderte Altzahlungen.

Die Browser-Unitgruppe besteht **81 Prüfungen**; der abschließende echte
Chromiumlauf besteht **elf Arbeitsabläufe**, einschließlich des neuen E1a-Wegs
und sämtlicher vorhandener Portal-/Einkaufs-/Kalender-/Dokumentationsabläufe.
E1a prüft globale Rechte, alte Server, receipt/refund-Übernahme, bytegleiches
Eingangsoriginal, Teil-/Restzahlung, verlorene Antwort, gesperrtes Modul,
deaktivierte/historische Kontoversion, Rechteentzug und 390-px-Darstellung.
Nachweise: `accounting-browser-unit.log`, `accounting-browser-e2e.log`.
Namespace-, PID-, Netzwerk- und Seccomp-Sandbox wurden vor Zugriff live
bestätigt. Der Browserlauf verwendet einen lokalen HTTP-Fixtureadapter für
den bestehenden HTTPS-/Originvertrag; ein neuer realer TLS-Nachweis wird
daraus nicht abgeleitet.

Der erste funktional grüne Browserlauf zeigte bei visueller Prüfung einen
versehentlich angehängten `null`-Text und zu schmale mobile Textspalten.
Accountingzeilen stehen mobil nun untereinander; Screenshots warten auf eine
vollständig geschlossene Sidebar. Der abschließende Gesamtlauf prüft beides
zusätzlich, und Desktop-/Handyansicht unter `accounting-browser-previews/`
wurden erneut visuell geprüft. Der erste Lauf bleibt als
`accounting-browser-initial.log` erhalten. Ein Node-Aufruf ohne die erforderliche
Umgebungsberechtigung für lokale Prozesse meldete nur einen fehlgeschlagenen
Dateilauf; derselbe Aufruf mit der vorgesehenen Testberechtigung besteht alle
81 Fälle. Keine Produktprüfung wurde dafür abgeschwächt.

### Nächster Abschnitt und verbleibende Abnahmen

Der [E1b-Entwurf](CRM_ERP_EUER_E1B_ENTWURF.md) ist ausdrücklich Planung. Er
beschreibt elf konkrete Akzeptanzfälle für nachträgliche Quellenzuordnung,
gemeinsame OP-Projektion, dokumentarische Centaufteilung und Erstattungsbezug.
Neue Zuordnungen dürfen die vollständigen ursprünglichen Zahlungszuordnungen
im E1a-Quellenhash nicht verändern. Die steuerliche Einordnung, E1c-Korrekturen/
Perioden und E1d-Beraterpaket bleiben weitere Implementierung.

R08.05 und die Abnahmen A–G bleiben insgesamt offen. Die Tests ersetzen keine
fachliche Jahresabstimmung, steuerliche Freigabe, Bankanbindung, physische
Windows-/iPhone-Abnahme oder Produktivinstallation. Das Originalziel bleibt
bytegleich zum Upload mit SHA-256
`a4dea28f6de4afd3e36d1549441aad91ce16dad374f56097979cc2d79b07fbf5`.

Der implementierte E1a-Stand ist im lokalen Commit `47707c9` gesichert.
Der [E1a-Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_E1A.json) speichert Ausgangscommit,
Ergebnisse und Hashes der geprüften Code-/Testdateien. Die Rohprotokolle liegen
unter dem ignorierten Verzeichnis `work/verification/`; Testquellen und
zusammengefasste Ergebnisse sind versioniert. Reproduktion im Hauptverzeichnis:

```sh
PYTHONPATH=backend backend/.venv/bin/python -m unittest test_business_accounting test_accounting_registration -v
PYTHONPATH=backend:backend/online backend/.venv/bin/python -m unittest online.test_accounting_journey online.test_accounting_http -v
PYTHONPATH=backend:backend/online backend/.venv/bin/python -m unittest online.test_postgres_accounting_integration -v
env -u SMARTPLAN_TEST_DSN PYTHONPATH=backend:backend/online backend/.venv/bin/python -m unittest discover -s backend -v
backend/.venv/bin/python -m unittest discover -s scripts -p test_native_release.py -v
node --test web/office/tests/*.test.mjs
node web/office/tests/e2e.cjs
```

Für PostgreSQL ausschließlich die synthetische lokale Test-DSN verwenden;
Fixtures verweigern fremde bzw. vorhandene Restoreziele. Für Chromium gelten
die oben dokumentierte Namespace-Sandbox, synthetische lokale Dienste und der
Fixture-Pythonpfad. Flutteranalyse/-tests laufen im Verzeichnis `app` mit dem
eingerichteten Flutter-/Pub-Cache und den vorhandenen PDF-Testbibliotheken.

## 02.11.2026 – E1b-1: zusätzliche Rechnungszuordnung, implementiert und geprüft

Nach dem Umgebungsneustart wurde der saubere Stand `acb46b4` geprüft; die
Originaldatei stimmt weiterhin mit ihrem gespeicherten SHA-256 überein.
Der [E1b-1-Vertrag](CRM_ERP_EUER_E1B1_API.md) konkretisiert den nächsten
Abschnitt: freie Teile bereits übernommener Kundenzahlungen ausdrücklich einer
normalen Rechnung zuordnen, Vorschau und Bestätigung trennen und eine gemeinsame
effektive Zahlungsprojektion für OP/Mahnen/Exports verwenden. Alte E1a-Quellen-
beweise und Zuordnungszeilen werden nicht geändert. Neue Rechnungszuordnungen
verengen bei Bedarf die vollständige Quellsicht; ursprünglich private Zahlungen
werden nicht durch eine Projektzuordnung freigegeben.

Die Umsetzung umfasst Browser, Flutter, globale/Projekt-/Quellrechte,
Konkurrenz mit dem bisherigen Zahlungseingangspfad und einen versionierten
Restorehorizont. Steuerliche Aufteilung, Refund-Ursprünge und Korrekturen sind
gesonderte nächste Schritte.

### Ergebnis und Erhalt bestehender Daten

Eine berechtigte Person kann den freien Teil einer bereits übernommenen
EUR-Kundenzahlung mit ausdrücklicher Kundenbindung einer normalen finalen
Rechnung zuordnen. Die Vorschau erzeugt keine Buchung oder Audit-/Requestzeile.
Die Bestätigung bindet Quellstand, Rechnung, Archive, Betrag und Begründung;
veraltete Vorschauen werden abgewiesen. Jeder bestätigte Vorgang ist
unveränderlich und mit derselben Anforderungskennung wiederholbar.

Die beiden neuen Tabellen enthalten ausschließlich zusätzliche Einträge und
Quittungen. Ursprüngliche Zahlungen, Zuordnungen, Rechnungsarchive, E1a-Ereignisse
und Quellenhashes bleiben erhalten. Historische Migrationsdefinitionen und der
alte E1a-Restorehorizont wurden nicht umgeschrieben. Gemeinsame Projektionen
berechnen Zahlungen, offene Posten, Mahnvorschläge, Erstattungsbudget und neue
vorhandene Prüfexporte aus den alten und zusätzlichen Zuordnungen. Erstattungen
öffnen nicht erneut das Budget der ursprünglichen Zahlung. Auch der bisherige
Zahlungseingangspfad prüft für neue normale Rechnungszuordnungen den aktuellen
Rechnungsrest, damit konkurrierende Vorgänge ihn nicht doppelt verbrauchen.

Für jede ganze Zahlung werden alle ursprünglichen und zusätzlich betroffenen
Projektrechte frisch geprüft, auch bei früher erzeugten Exporten und beim
Wiederholen bestätigter Vorgänge. Ursprünglich private unzugeordnete Zahlungen
bleiben auf Eigentümer/Ersteller beschränkt. Berechtigte Rechnungs-OP werden
trotz eingeschränkter Sicht auf die gesamte Zahlung vollständig berechnet.
Die Clients prüfen nach Rechteentzug auch noch unbestätigte Zielrechnungen,
entfernen veraltete Details und erhalten den unveränderten Wiederholungsauftrag.

Ein eigener Zuordnungshorizont ergänzt den unveränderten E1a-Horizont. Frische
Wiederherstellungen verlangen bei installiertem Modul einen vollständigen
Schema-3-Abgleich einschließlich unabhängiger externer Bestätigung. Bereits
freigegebene identische Schema-2-Quittungen können nach einem normalen Update
unter den bestehenden Betreiber-/Datenschutz-/Stillstandsbedingungen erneut
abgerufen werden; sie entsperren keinen neuen Restore. Der paketierte lokale
Operator prüft denselben Umfang.

### Tatsächlich ausgeführte Prüfungen

Die Gruppen überschneiden sich; ihre Zahlen werden nicht zu einer Zahl
eindeutiger Abnahmen addiert. Alle Daten und Dienstzugänge waren synthetisch.

| Prüfgruppe | Ergebnis | Rohprotokoll unter `work/verification/` |
| --- | --- | --- |
| Domäne, E1a und bestehende Finanz-/Mahnpfade | 68/68, davon 19 neue Zuordnungsfälle; 33,665 s | `accounting-allocations-domain.log` |
| Registration und echter lokaler HTTP-Transport | 6/6; 1,603 s | `accounting-allocation-registration-transport.log` |
| Unabhängige reale HTTPS-Verbindung mit normaler Anmeldung und MFA | 6/6; 8,371 s; eigene vertrauenswürdige Test-CA und Hostnamenprüfung | `accounting-allocations-http-journey.log` |
| HTTP, lokaler Betreiber, Restore und bestehende Regressionen | 47/47; 10,488 s | `accounting-allocations-http-restore.log` |
| Gespeicherte Exportrechte und bestehende Commercial-Fälle | 12/12; 0,625 s | `accounting-allocation-export-scope.log` |
| PostgreSQL-Zuordnung und im Lauf mitentdeckte E1a-Fälle | 17/17: acht neue Fälle und neun bestehende E1a-Fälle; 33,738 s | `pg-accounting-allocations.log` |
| Bestehende PostgreSQL-Release-/Restore-Prüfungen | 12/12; 36,788 s | `pg-accounting-allocations-release-regression.log` |
| Vollständiger Backend-Discoverylauf | 491 ausgeführt: 490 bestanden, ein bestehender Windows-Job-Object-Test unter Linux übersprungen; 83,295 s | `accounting-allocation-backend-full.log` |
| Paketierung und extrahierter lokaler Operator | 15/15; 3,076 s vor abschließender Dokumenttextpflege | `accounting-allocation-native-release.log` |
| Flutter gezielt | 47/47, einschließlich realer HTTP-Clientfälle; 9 s | `e1b1-flutter-targeted.log` |
| Flutter vollständig | 405/405; 134 s; keine Skips | `e1b1-flutter-full.log` |
| Flutteranalyse | keine Befunde; 5,4 s | `e1b1-flutter-analyze.log` |
| Browser-Unitgruppe | 89/89; keine Skips | `accounting-allocations-node-agent.log` |
| Echter Chromium-Gesamtlauf | zwölf Arbeitsabläufe bestanden; Namespace-, PID-, Netzwerk- und Seccomp-Sandbox vor Zugriff bestätigt | `accounting-allocation-browser-e2e.log` |
| Flutter nach abschließender Textpflege | 39/39 gezielte Fälle; 7 s; erneute Analyse ohne Befunde, 4,9 s | `e1b1-flutter-ui-copy-test.log`, `e1b1-flutter-ui-copy-analyze.log` |
| Echter Zuordnungsablauf nach Textpflege | bestanden; tatsächliche Anmeldung und Konto-/Zahlungsübernahme per Oberfläche, erneute Desktop-/390-px-Sichtprüfung | `accounting-allocation-browser-final.log` |
| Paketierung nach abschließender Betreiber-Dokumentpflege | 15/15; 2,103 s | `accounting-allocation-native-final.log` |

PostgreSQL prüft die tatsächliche produktive Rechnungsausstellung unter
getrennter Laufzeit-/Migrationsrolle, konkurrierende Verbindungen um Zahlungs-
und Rechnungsrest, Erstattungen, Zeilenschutz, atomaren Rollback, zweifache
Migration vom E1a-Bestand und einen echten Dump/Restore mit Schema 3.
Ein direkt importierter TestCase ließ zunächst zusätzlich neun bestehende
E1a-Fälle mitlaufen. Der Import wurde auf einen Modulalias umgestellt; eine
anschließende lesende Loaderprüfung findet exakt die acht neuen Fälle.
Produktverhalten und Fallinhalt wurden dadurch nicht geändert. Das getrennte
Restore-Testziel wurde entfernt; keine Nicht-Testdatenbank wurde geändert.

Der reale HTTPS-Lauf verwendet echte verschlüsselte Loopback-Verbindungen
und die normale Passwort-/TOTP-Anmeldung. Für diese SQLite-Transportfixture
sind bestehende synthetische Rechnungsarchive vorbereitet; sie beansprucht
keine eigene produktive Rechnungsausstellung. Unbekannte GET-Bodies und
POST-Queryparameter werden nun schon an beiden HTTP-Einstiegen der neuen
Zuordnungsrouten abgewiesen. Der Browser verwendet weiterhin den synthetischen
HTTP-Fixtureadapter für den vorhandenen Origin-/Proxyvertrag; der HTTPS-Nachweis
stammt aus der getrennten Transportprüfung.

Die Clients prüfen alte Server, fehlende Rechte, inaktive Geldkonten,
verlorene Antworten, spätere Rechnungsänderungen, paginierte Kandidaten,
unveränderte alte Nachweise, Original-PDF und 390-px-Darstellung. Bei der
visuellen Schlussprüfung wurden technische Begriffe in den neuen Dialogen
durch verständliche Angaben zum ursprünglichen Zahlungsnachweis ersetzt.
Betroffene Clientprüfungen und Screenshots sind nach dieser Textpflege
gesondert im maschinenlesbaren Nachweis festgehalten. Die 89 Browser-Unitfälle
wurden ebenfalls auf dem endgültigen Textstand ausgeführt. Der vollständige
Flutterlauf vor der Textpflege und der abschließende Stand sind mit getrennten
Dateihashlisten dokumentiert; die Fachlogik blieb bei dieser Pflege unverändert.

Der unabhängige Abschlussreview fand nach den gezielten Korrekturen keine
offenen konkreten Befunde in Quellrechten, DTO-Datengrenzen, historischem
Replay und Schema-3-Abgleich. Dies ist ein Entwicklungsreview und keine
externe Sicherheits- oder steuerliche Abnahme.

### Nachweis und nächste Arbeit

Der [E1b-1-Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_E1B1.json) bindet die Ergebnisse
an Ausgangscommit, geprüfte Code-/Testdateien, paketierte Verträge und
Protokoll-/Screenshot-Hashes. Rohprotokolle und Bilder liegen im ignorierten
`work/verification/`; Testquellen und Zusammenfassung sind versioniert.
Der [Betreiberablauf](CRM_ERP_EUER_BETRIEB.md) beschreibt Bedienung und
Wiederherstellung. Die Original-Zieldatei bleibt unverändert.

Gezielte Reproduktion aus dem Hauptverzeichnis:

```sh
PYTHONPATH=backend:backend/business_tests backend/.venv/bin/python -m unittest test_business_accounting_allocations test_business_accounting test_accounting_registration test_accounting_allocation_transport test_adapter_payment_scope -v
PYTHONPATH=backend:backend/online backend/.venv/bin/python -m unittest online.test_accounting_allocations_journey online.test_accounting_allocations_http -v
PYTHONPATH=backend:backend/online backend/.venv/bin/python -m unittest online.test_postgres_accounting_allocations_integration -v
env -u SMARTPLAN_TEST_DSN PYTHONPATH=backend:backend/online backend/.venv/bin/python -m unittest discover -s backend -v
backend/.venv/bin/python -m unittest discover -s scripts -p test_native_release.py -v
node --test web/office/tests/*.test.mjs
node web/office/tests/e2e.cjs
```

PostgreSQL- und Browservoraussetzungen entsprechen dem vorherigen Abschnitt;
reale TLS-Prüfungen benötigen lokale Socketfreigabe. Die nächsten E1b-Fälle sind
belegte Betragsaufteilung und Erstattungsursprünge, danach folgen Korrekturen,
Perioden und Beraterpaket. Umsatzsteuerstatus bleibt offen. R08.05, vollständige
EÜR, Lohnabrechnung und die Abnahmen A–G bleiben insgesamt offen.

Der geprüfte E1b-1-Code ist im lokalen Commit `6e35f9e` gesichert.
Der zugehörige Prüfnachweis ist an diesen vollständigen Commit gebunden.
Es erfolgten kein Remote-Push und keine Produktivbereitstellung.

## Fortsetzung – E1b-2 implementiert und geprüft

Der Nutzer hat klargestellt, dass die Entwicklung bis zum Gesamtziel
weiterzuführen ist. Der Abschluss eines Teilabschnitts ist kein Grund, das
Gesamtziel als erledigt zu markieren. Nach Prüfung des sauberen Stands
`a8fa548` wird die unabhängige Entwicklung fortgesetzt.

Der [E1b-2-Vertrag](CRM_ERP_EUER_E1B2_API.md) beschreibt die Umsetzung:
ganze unveränderliche Quellenanteile bestehender Ein-/Auszahlungen ausdrücklich
in belegte Netto-/ausgewiesene Steueranteile aufteilen. Jeder Anteil wird nur
einmal verwendet; mehrere Beleggruppen verlangen eine bestätigte Bruttoverteilung.
Gemeinsame Gruppenreste und kumulative Integer-Centrechnung verhindern
verlorene oder doppelte Rundungscents über mehrere Zahlungen hinweg.

Die additive Entwicklung umfasst Domäne, Browser, Flutter, frische Quellrechte,
reale HTTP-/PostgreSQL-Prüfungen und Schema-4-Restoreabgleich. E1a-/E1b-1-Daten,
OP-Wirkung und gespeicherte Exporte bleiben bestehen. Erstattungsbezüge sind
der anschließende Fachschritt; Erstattungen geben bis dahin keine Komponenten
automatisch frei. Steuerstatus bleibt ausdrücklich unkonfiguriert. Der folgende
Prüfstand belegt diesen Teilabschnitt und nicht die Gesamtabnahme. Die
Entwicklung wird mit den Erstattungsursprüngen fortgesetzt.

### Ausgeführte E1b-2-Prüfungen

Drei neue unveränderliche Tabellen speichern bestätigte Anteile, Gruppenzeilen
und Anforderungsquittungen. Ursprüngliche und zusätzliche Rechnungszuordnungen
bleiben getrennte stabile Quellenanteile. Lieferantenzahlungen verwenden die
konkrete bestätigte Belegprüfung. Mehrere Zahlungen teilen die Gruppenreste
desselben unveränderten Belegs. Die Integer-Centrechnung ergibt für
39,67/39,67/39,66 auf 100,00+19,00 exakt
33,34/6,33; 33,33/6,34; 33,33/6,33.

| Gruppe | Tatsächliches Ergebnis | Rohprotokoll unter `work/verification/` |
| --- | --- | --- |
| Neue Domänenfälle | 16/16, 3,969 s | `accounting-components-domain.log` |
| Neue Domäne mit E1a-/E1b-1-Regressionen | 54/54, keine Skips, 12,962 s | `accounting-components-domain-regression.log` |
| Registrierung und tatsächlicher lokaler HTTP-Einstieg | 8/8, 2,192 s | `accounting-components-registration-transport.log` |
| Unabhängige tatsächliche HTTPS-/MFA-Abläufe nach Domainfreeze | 9/9, keine Skips, 11,152 s | `accounting-components-http-journey.log` |
| HTTP, Betreiberabgleich, Backup/Restore und bestehende Regressionen | 53/53, keine Skips, 12,783 s; sechs neue Fälle | `accounting-components-http-restore.log` |
| PostgreSQL final | 16/16, keine Skips, 57,245 s; zwölf neue Fälle und vier betroffene ältere Migration-/Restorefälle | `pg-accounting-components-final.log` |
| Vollständiger Backendlauf | 509 ausgeführt: 508 bestanden, ein bestehender Windows-Job-Object-Test unter Linux übersprungen; 94,190 s | `accounting-components-backend-full.log` |
| Flutter gezielt | 69/69, rund 11 s, einschließlich echter Client-HTTP-Strecke | `e1b2-flutter-targeted.log` |
| Flutter vollständig | 429/429, keine Skips, 127 s | `e1b2-flutter-full.log` |
| Flutteranalyse | keine Befunde, 4,5 s | `e1b2-flutter-analyze.log` |
| Browser-Unitgruppe | 98/98 | `accounting-components-node-agent.log` |
| Korrigierter Browser-Testhelfer | 9/9 | `accounting-components-node-helper-check.log` |
| Vollständiger echter Browserlauf | 13/13; Desktop und 390-Pixel-Ansicht zusätzlich visuell geprüft | `accounting-components-browser-e2e.log` |
| Abschließende native Paketprüfung | 15/15, 2,237 s; keine native Geräteabnahme | `accounting-components-native-final.log` |

Die Gruppen überschneiden sich und werden nicht als eindeutige Abnahmen addiert.
Der erste Browserlauf wurde wegen einer unbegrenzten Wartebedingung im neuen
Testhelfer beendet. Begrenzte Wartezeiten und garantierte Freigabe der gehaltenen
Antwort beheben den Testablauf; Produktcode blieb dabei unverändert. Der danach
vollständig wiederholte Browserlauf endete erfolgreich. Die Screenshots zeigen
lesbare Vorschauen und explizite Bestätigung auch bei 390 Pixeln; der Dialog
scrollt innerhalb der Ansicht. Der Paketlauf verwendet den endgültigen
paketierten Code und die endgültigen Betreiber-/API-Dokumente.

Der Review führte zu gezielten Korrekturen: Historische Zeilen binden ihren
vorherigen Gruppenbetrag an den rekonstruierten Stand; fremde Gruppenbeiträge
binden den ganzen echten Quellenanteil. Zwei Regressionen schreiben Entry-/
Request-Prüfsummen konsistent neu und belegen, dass ein falscher letzter
Vorstand beziehungsweise ein verkürzter fremder Beitrag trotzdem abgewiesen
wird. Die Beweisreferenzen bleiben flach, ohne rekursive Historieneinbettung.

Die Clients verwenden für größere gültige archivierte Gruppensummen exakte
String-/BigInt-Werte; neue Eingaben bleiben begrenzt. Kategorie und Befreiungsgrund
unterscheiden auch gleiche oder mehrere Nullsteuersätze. Flutter lädt nach einer
während des Wiederöffnens eintreffenden Quittung den bestätigten Stand neu.
Verlorene Antworten vor und nach Serverannahme, frischer Quellenrechteentzug
und späte Antworten sind gezielt berücksichtigt.

Die echte HTTPS-Strecke prüft CA-Vertrauen, Zertifikatshost, HTTP-Host und normale
Passwort-/TOTP-Anmeldung. Sie verwendet ausdrücklich synthetische SQLite-
Rechnungsarchive für Transport-/Fachmechanik. PostgreSQL prüft die tatsächliche
produktive Rechnungsausstellung unter getrennter Laufzeit-/Migrationsrolle,
konkurrierende Verbindungen, atomaren SQL-Rollback, Tabellenrechte, doppelte
Migration vom E1b-1-Bestand und echten Dump/Restore mit Schema 4. Zwei anfängliche
PG-Fixturefehler betrafen die historische Paketmodulliste und erwartete 404 statt
der korrekten 403 bei privaten Quellen; beide wurden berichtigt. Der finale
16er-Lauf bestand auf unveränderten Produkt-/Testquellen.

Historische Testregistries schließen nun auch Komponenten aus, wenn sie einen
älteren E1a- oder Vor-Accounting-Stand darstellen. Produktmigrationen wurden
dafür nicht abgeschwächt. Der Betreiberpfad erhält H1-/H2-Teilhorizonte und
verlangt mit Komponenten H3/Schema 4. Alte erfolgreich freigegebene identische
Schema-3-Quittungen bleiben wiederholbar und entsperren keinen neuen Restore.

Der [E1b-2-Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_E1B2.json) bindet geprüfte
Quellen, paketierte Verträge, Protokolle und Screenshots an ihre Prüfsummen.
Die unveränderte Original-Zieldatei wurde erneut byteweise verglichen.
Kein Remote-Push, keine Produktivbereitstellung und keine echte Zahlung wurden
ausgeführt. Als nächster laufender Fachschritt verknüpft E1b-3a vorhandene
Erstattungen ausdrücklich mit ihren ursprünglichen dokumentierten
Zahlungsanteilen. Erst E1b-3b verwendet die exakt zurückgeführten Netto-/
Steuercents für neue Einnahmen; alte Komponentenbeweise bleiben unverändert.

Der geprüfte E1b-2-Code ist im lokalen Commit `81a42b38` gesichert.
Der Prüfnachweis bindet die oben genannten Ergebnisse an diesen vollständigen
Commit; die Entwicklung wird anschließend mit E1b-3a fortgesetzt.

## 03.11.2026 – E1b-3a umgesetzt und geprüft

Ausgehend vom gesicherten E1b-2-Stand `2261712` ist die ausdrückliche
Dokumentation von Erstattungsursprüngen umgesetzt. Ein ganzer ursprünglicher
Rechnungsanteil einer bereits übernommenen Erstattung wird auf ausgewählte
Komponentenzeilen ihrer ursprünglichen Einnahmen derselben Rechnung bezogen.
Der Geldfluss, seine alten Rechnungszuordnungen, offene Posten und sämtliche
E1a-/E1b-1-/E1b-2-Nachweise bleiben bestehen.

Jedes ursprüngliche Komponentenlos trägt seine tatsächlich dokumentierten
Netto-/Steuercents. Die neue kumulative Rückführung verwendet genau diese
Basis. Damit wird zum Beispiel ein Los 39,67 = 33,33 + 6,34 auch nach mehreren
Teilerstattungen exakt auf diese ursprünglichen Cents zurückgeführt.
Ausdrückliche Ursprungswahl, Rechnung, Kunde, Geldflussdatum, globale
Restbeträge und frische vollständige Rechte sind Teil der Bestätigung.
E1b-3a gibt noch keine Kapazität für neue Belegaufteilungen frei.

Registrierung, strikte HTTP-Grenzen, native Paketlisten und CI-Einstiege für das
neue Modul sind umgesetzt. Drei unveränderliche Tabellen ergänzen die bisherigen
Nachweise; der eigenständige R1-Horizont erweitert den Betreiberabgleich zu
H4/Schema 5. Historische H1-/A1-/C1-Nachweise und erfolgreiche alte
Restorequittungen bleiben erhalten. Ein alter Nachweis entsperrt keinen neuen
Restore. Browser und Flutter erlauben ausdrückliche, centgenaue Ursprungswahl,
Vorschau und gesonderte Bestätigung. Verlorene Antworten werden mit demselben
Befehl wiederholt; frische Rechte auf die ganze Erstattung und alle betroffenen
Ursprünge bleiben Voraussetzung.

### Tatsächlich ausgeführte Prüfungen

| Gruppe | Ergebnis | Rohprotokoll unter `work/verification/` |
| --- | --- | --- |
| Neue Domänenfälle | 17/17, 4,968 s | `accounting-refunds-domain.log` |
| Registrierung und tatsächlicher lokaler HTTP-Einstieg | 10/10, 2,887 s | `accounting-refunds-registration-transport.log` |
| Unabhängige echte HTTPS-/MFA-Strecke | 9/9, 16,213 s | `accounting-refunds-http-journey.log` |
| HTTP, Betreiberabgleich, Backup/Restore und Regressionen | 60/60, 17,168 s | `accounting-refunds-http-restore.log` |
| Neue PostgreSQL-Fälle | 12/12, 49,037 s | `pg-accounting-refunds-initial.log` |
| Betroffene ältere PostgreSQL-Migrationen und Restorefälle | 6/6, 23,463 s | `pg-accounting-refunds-regression.log` |
| Vollständiger Backendlauf auf aktuellem Code | 528 ausgeführt: 527 bestanden, ein bestehender Windows-Job-Object-Test unter Linux übersprungen; 98,789 s | `accounting-refunds-backend-full.log` |
| Flutter gezielt | 99/99, rund 17 s | `e1b3a-flutter-targeted.log` |
| Flutter vollständig | 459/459, rund 139 s | `e1b3a-flutter-full.log` |
| Flutteranalyse | keine Befunde, 9,1 s | `e1b3a-flutter-analyze.log` |
| Browser-Unitgruppe | 109/109, rund 0,54 s | `accounting-refunds-node-agent.log` |
| Tatsächlicher gezielter Erstattungsablauf im Browser | 1/1; Desktop und 390-Pixel-Ansicht visuell geprüft | `accounting-refunds-browser-final.log` |
| Vollständige tatsächliche Browserregression | 14/14 | `accounting-refunds-browser-full.log` |
| Abschließende native Paketprüfung | 15/15, 2,891 s | `accounting-refunds-native-final.log` |

Die Gruppen überschneiden sich und werden nicht als eindeutige Abnahmen addiert.
Der PostgreSQL- und erste HTTPS-Nachweis bindet den Refundmodulstand
`23b8c700…`. Anschließend wurden zwei enge Prüfungen ergänzt: Ein boolescher
Wert ist keine gültige Proof-Schemaversion, und eine fehlende gespeicherte
C1-Zeile wird auch bei konsistent neu geschriebenen Hashes abgewiesen.
Der aktuelle Modulstand `98ebbdd3…` ist durch die 17 Domänenfälle, den aktuellen
vollständigen Backendlauf und die abschließenden Clientprüfungen belegt.
Der ältere PostgreSQL-Lauf wird ausdrücklich nicht als Wiederholung auf diesem
späteren Modulstand dargestellt. Die PostgreSQL-Prüfung umfasste tatsächliche
Rechnungsausstellung, getrennte Rollen, konkurrierende Verbindungen, atomaren
Rollback, unveränderliche Tabellen sowie echten Dump/Restore mit Schema 5.

Ein erster Flutter-Vollsuitenstart scheiterte vor den Tests am fehlenden
clang-Pfad. Mit dem bereits installierten Wrapper lief die gesamte Suite
erfolgreich; dafür wurde kein Produktcode geändert. Der gezielte Browserlauf
verwendete nachweislich Namespace-, PID-, Netzwerk- und Seccomp-Sandboxing.
Die lokal erzeugten Rechnungsarchive der SQLite-/Browserfixtures sind
synthetisch; produktive Rechnungsausstellung wird getrennt in PostgreSQL geprüft.

Die visuelle Prüfung zeigt lesbare Erstattungsnachweise und eine gesonderte
Bestätigung in Desktop- und schmaler Ansicht; der Dialog scrollt innerhalb der
Ansicht. Die fünf geprüften Flutter-Dateien blieben während der abschließenden
Suite unverändert. Unabhängige Fach- und Clientreviews ergaben keine weiteren
bestätigten Befunde. Die Paketprüfung importiert das tatsächlich extrahierte
Supportarchiv und enthält die aktuellen API-/Betreiberdokumente.

Der [E1b-3a-Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_E1B3A.json) hält Ergebnisse,
Versionengrenzen und Prüfsummen fest. Die ursprüngliche Zieldatei bleibt
unverändert. Der nächste Fachschritt E1b-3b behandelt neue Verteilungsabschnitte
aus alten Resten und exakt zurückgeführten Beträgen; er ist durch diese
Erstattungsursprünge noch nicht erledigt. EÜR-Ergebnis, Lohnabrechnung und
Gesamtziel A–G bleiben offen.

### Zwischenstand auf Nutzerfrage – 03.11.2026

Die aktuelle Anforderungsmatrix umfasst 62 abgegrenzte Bausteine: 24 sind
`implementiert`, vier `getestet`, 27 `offen`, einer ausdrücklich teilweise und
sechs `extern_blockiert`. Damit sind 28/62, also 45,2 %, als implementiert oder
getestet geführt. Diese ungewichtete Zählung enthält auch den vorhandenen
Bestandsquellcode und ist keine belastbare Aufwandsschätzung. Große offene
Bereiche wie vollständige EÜR, Lohn und KI sowie die innerhalb einzelner
Bausteine genannten Restarbeiten werden dadurch nicht als erledigt bewertet.
Keine der sieben Gesamtabnahmen A–G ist abgeschlossen. Die unabhängige
Entwicklung wird fortgesetzt.

Der E1b-3a-Code ist im lokalen Commit `ec69d13f` gesichert; der
Prüfnachweis bindet seine Quellen an den vollständigen Commit. Auch die
abschließende vollständige Browserregression über alle 14 Abläufe ist grün.
Die Weiterentwicklung von E1b-3b hat mit dem isolierten Rechenkern und dem
Vertrag begonnen; sie ist kein Teil dieser E1b-3a-Abnahme.

## 03.11.2026 – E1b-3b begonnen

Ausgehend vom gesicherten E1b-3a-Stand `2a8d6b9` entwickelt der nächste
Abschnitt die Wiederverwendung ausdrücklich zurückgeführter Belegcents.
Der [Entwurf](CRM_ERP_EUER_E1B3B_ENTWURF.md) beschreibt die atomare Übernahme
einer ganzen Rechnung, getrennte unveränderliche Restabschnitte, den Abgleich
aller zugeordneten Finance-Erstattungen und unveränderte alte Quittungen.
Neue Erstattungen gegen die erst hier entstehenden Komponenten benötigen
anschließend eine eigene Ursprungsfassung; das bleibt ausdrücklich offen.

Der isolierte Rechenkern `backend/accounting_component_segments.py` verwendet
unveränderliche ganze Centbeträge. Ein Nachfolgeabschnitt setzt sich aus den
exakten ungenutzten Netto-/Steuer-/Bruttocents seines Vorgängers und den exakten
Rücknahmecents zusammen. Er berechnet die Rücknahme nicht erneut aus dem
ursprünglichen Steuersatz. Die 13 gezielten Tests bestanden in 0,004 Sekunden
(`work/verification/e1b3b-segment-domain.log`); ein unabhängiger Rechenreview
ergab keine Befunde. Das ist noch keine Prüfung der neuen Datenbank-/API- oder
Clientintegration und gibt allein keine gespeicherte Kapazität frei.

Domäne, Additivmigration, Betreiberhorizont, Browser und Flutter sind inzwischen
implementiert. Die abschließende Browser-/Paketprüfung läuft noch; der gesamte
Abschnitt ist daher noch nicht abschließend geprüft. Die Anforderungsquote
bleibt 28/62. Der [API-Vertrag](CRM_ERP_EUER_E1B3B_API.md) und der
[vorläufige Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_E1B3B.json) unterscheiden
Implementierung, tatsächlich ausgeführte Prüfungen und ausstehende Nachweise.

### Bisherige Integrationsprüfungen für E1b-3b

| Gruppe | Tatsächliches Ergebnis | Rohprotokoll unter `work/verification/` |
| --- | --- | --- |
| Isolierter Cent-Rechenkern | 13/13, 0,004 s | `e1b3b-segment-domain.log` |
| Neue Domänenfälle | 15/15; außerdem im aktuellen Backendlauf enthalten | `accounting-capacity-backend-full.log` |
| Registrierung und tatsächlicher lokaler HTTP-Einstieg | 14/14, 5,478 s | `accounting-capacity-registration-transport-final.log` |
| HTTP, Betreiberabgleich und Restore | 67/67, 24,722 s; sieben neue Fälle und 60 Regressionen | `accounting-capacity-http-restore.log` |
| Unabhängige tatsächliche HTTPS-/MFA-Abläufe | 9/9, 16,720 s | `accounting-capacity-http-journey.log` |
| Neue PostgreSQL-Fälle | 14 unterschiedliche Fälle erfolgreich abgedeckt: zunächst 12/14, anschließend die zwei korrigierten Fixtures 2/2 | `pg-accounting-capacity-initial.log`, `pg-accounting-capacity-corrected.log` |
| Ältere PostgreSQL-Migrationen und Restorefälle | 8/8, 47,453 s | `pg-accounting-capacity-regression.log` |
| Vollständiger Backendlauf | 560 ausgeführt: 559 bestanden, ein bestehender Windows-Job-Object-Test unter Linux übersprungen; 112,801 s | `accounting-capacity-backend-full.log` |
| Flutter vollständig vor abschließendem Texthinweis | 514/514, 154 s | `e1b3b-flutter-full.log` |
| Flutter: abschließende betroffene Widgets | 31/31, 6 s | `e1b3b-flutter-copy-targeted.log` |
| Abschließende Flutteranalyse | keine Befunde, 6,7 s | `e1b3b-flutter-final-analyze.log` |
| Echter Flutter-/HTTP-Ablauf | 1/1 | `e1b3b-flutter-http.log` |
| Browser-Unitgruppe vor Texthinweis/Testhelferkorrektur | 121/121 | `accounting-capacity-node.log` |
| Betroffene Browser-Unitgruppe danach | 21/21 | `accounting-capacity-node-copy-helper.log` |

Die Gruppen überschneiden sich und sind keine zusätzlichen eindeutigen
Gesamtabnahmen. Die zwei anfänglichen PostgreSQL-Fehler betrafen ausschließlich
neue Rechnungsfixtures vor Ausführung der Kapazitätsdomäne: falscher
Positionsfeldname und zu korrigierende kanonische Einheit. Nur die zwei
betroffenen Fälle wurden nach Korrektur wiederholt; der Produktcode blieb
unverändert. Ein einzelner abschließender 14/14-Gesamtlauf wird nicht behauptet.

Der Review fand zwei konkrete Probleme, die vor den endgültigen HTTP-/HTTPS-
und PostgreSQL-Prüfungen behoben wurden. Historische Einträge autorisieren nun
auch sämtliche lediglich im damaligen Gruppenstand gebundenen Quellen ohne
neue Einnahmenlinie. Eine kanonische `access_segments_json`-Bindung wird vor
Details ausgewertet und anschließend gegen den rekonstruierten Beweis geprüft.
Ein Zweigruppenfall belegt den vollständigen Rechteentzug für Stand, Historie
und Wiederholung auch auf PostgreSQL und über echtes HTTPS.

Außerdem unterscheiden Komponentenbestätigungen nun einen unbekannten
Ausgang von einer sicher unangenommenen Anfrage. Nur nach geprüft fehlender
Quittung und vor neuen Schreibvorgängen trägt ein 409-Konflikt
`request_resolution:'not_accepted'`. Frühere Sicherheits-/Restore-/Modusgates
bleiben vor der Quittungsprüfung und erhalten diesen Hinweis nicht. Beide
Clients behalten solche unklaren Befehle mit identischem Pfad, Inhalt und
Request-ID; sie erzeugen keine neue Anfrage als vermeintlichen Ersatz.

Nach der grünen Flutter-Vollsuite wurde nur der ausdrückliche Vorschauhinweis
ergänzt, dass neue Aufteilungsanteile noch nicht als Ursprung einer späteren
Erstattung verfügbar sind. Drei Textprüfungen und ein Layout-Abwarten im
Checkbox-Testhelfer begleiten diese Änderung. Die danach betroffenen 31
Widgettests und die Analyse sind grün. Getrennte Quellmanifeste und der genaue
Zwei-Dateien-Diff halten diese Grenze fest; die Vollsuite wurde für diese
Textänderung nicht wiederholt.

Der erste vollständige Browserlauf scheiterte an einem vorhandenen Testhelfer,
der Eingabefelder zählte, bevor der nun asynchron geladene alte Aufteilungseditor
geöffnet war. Der Helfer wartet jetzt auf den tatsächlichen sichtbaren Dialog;
die Assertions bleiben unverändert. Der vollständige Lauf wird wiederholt und
ist noch kein erfolgreicher Abschlussnachweis.

### Zwischenstand nach Wiederverbindung der Cloud-Umgebung

Die Cloud-Umgebung war vorübergehend nicht erreichbar. Nach der Wiederverbindung
wurden das Repository, die Änderungen und die vorhandenen Prüfprotokolle erneut
vorgefunden. Ein lokaler Zwischencommit hält E1b-3b mit ausdrücklich noch offener
Browser-/Paketabnahme fest. Der neue E1b-3c-Entwurf und sein isolierter
Reihenfolgehelfer gehören nicht in diesen Zwischenstand.

Der wiederholte Browserlauf erreichte den neuen Kapazitätsablauf. Dessen
Testbenutzer hatte noch keine globalen Accountingrechte; ausschließlich diese
beiden Fixture-Freigaben wurden ergänzt. Der Produktzugriff hatte korrekt
verweigert. Im nächsten gezielten Lauf endete ein Playwright-Transportabschluss
nicht innerhalb der Frist. Der Test beobachtet nun den tatsächlichen
unveränderten Client-Promise samt Ereignis-ID/Vorschauhash; Zeitgrenze und
Prüfung gegen das Wiederöffnen eines veralteten Dialogs bleiben erhalten.
Dieser erneute Lauf ist noch nicht als bestanden dokumentiert.


## 03.11.2026 – E1b-3b umgesetzt und geprüft

Der abschließende vollständige Browserlauf hat **alle 15 Abläufe bestanden**
(Exit 0). Er umfasst die neue Wiederverwendung und die vorhandenen Bereiche
von Anmeldung und Kundenportal bis Einkauf, Planung, Fotos, Unterschrift und
Kontaktformular. Der Browser prüfte vor Anwendungszugriff Namespace-, PID-,
Netzwerk- und Seccomp-Sandboxing. Die zwölf Dateien seines Quellmanifests
blieben während des Laufs unverändert. Die gesonderte echte HTTPS-/MFA-Prüfung
bleibt der oben angegebene 9/9-Nachweis.

Auch die abschließende **Paketprüfung bestand 15/15 in 2,376 Sekunden**. Sie
importiert das tatsächlich extrahierte Supportarchiv und prüft die aktuellen
API-/Betreiberdateien. Das ersetzt keine Prüfung signierter Windows-/iPhone-
Gerätepakete. Rohprotokolle: `accounting-capacity-browser-full.log` und
`accounting-capacity-native-final.log` unter `work/verification/`.

Zuvor bestand der gezielte Kapazitätsablauf nach den beschriebenen reinen
Testkorrekturen. Ein nachfolgender vollständiger Lauf wurde durch einen
weiteren Cloud-Ausfall unterbrochen; sein unvollständiges Protokoll bleibt als
`accounting-capacity-browser-cloud-interrupted.log` erhalten und zählt nicht
als Erfolg. Nach Wiederverbindung waren der Zwischencommit `79bfc35`, alle
Änderungen und die 32 zuvor gebundenen Prüfprotokolle unverändert vorhanden.
Der nun erfolgreiche vollständige Lauf wurde danach neu gestartet.

Nach den Backend-/HTTP-/PostgreSQL-Prüfungen wurde im Kapazitätsmodul nur eine
zusätzliche Leerzeile am Dateiende entfernt. Der genaue Bytevergleich und der
identische Python-Syntaxbaum sind in
`accounting-capacity-whitespace-boundary.json` festgehalten. Die früheren
Quellhashes bleiben im Nachweis erhalten; Browser- und Paketabschluss verwenden
den bereinigten Stand. Die bereits dokumentierten Grenzen des Flutter-
Vollaufs und der zusammengesetzten PostgreSQL-Prüfung bleiben unverändert.

Die abschließenden Desktop- und 390-Pixel-Aufnahmen wurden visuell geprüft.
Der Dialog bleibt innerhalb der Ansicht und scrollt im Inhalt; Centbeträge
und ausdrückliche Bestätigung sind erkennbar. Der echte Browserablauf prüft
zusätzlich Hinweistext, Bedienung und erfolgreiche Bestätigung. Die
Aufnahmen sind unter `accounting-capacity-browser-previews/` gespeichert.

Der [Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_E1B3B.json) bindet Code, tatsächlich
bestandene Prüfungen, historische Versionsgrenzen und Protokollhashes. Die
Zieldatei wurde erneut bytegleich mit dem Upload verglichen (23.863 Bytes,
unveränderter SHA-256). E1b-3b ist damit im beschriebenen Umfang umgesetzt und
geprüft. Neue C2-Lose sind weiterhin keine auswählbaren Erstattungsursprünge;
das ist die nächste Entwicklung E1b-3c. Vollständige EÜR, Lohn, KI und alle
Gesamtabnahmen A–G bleiben offen. Die Quote bleibt 28/62 ungewichtete Bausteine.

Der abschließende E1b-3b-Stand ist lokal in Commit `36f72a29e6074b8a06d470a59f0c03230037de1d`
gesichert; der Prüfnachweis bindet alle 51 Code-/Vertragsdateien an diesen
Commit. Es wurde nichts gepusht oder produktiv bereitgestellt.


## 03.11.2026 – E1b-3c begonnen

Die Entwicklung setzt unmittelbar auf der abgeschlossenen 3b-Basis
`5a6e22ca278d647b4889243688b04e52b308a5b9` fort. Der
[neue Vertrag](CRM_ERP_EUER_E1B3C_API.md) beschreibt ganze Erstattungsportionen
mit gemischten ursprünglichen und wiederverwendeten Zahlungsanteilen sowie
mindestens zwei weitere vollständige Rücknahme-/Wiederverwendungszyklen.
Neue Financewirkungen oder steuerliche Ergebnisse sind damit nicht verbunden.

Zwei isolierte Grundlagen sind bereits umgesetzt und geprüft:

| Baustein | Nachweis | Rohprotokoll unter `work/verification/` |
| --- | --- | --- |
| Eindeutige gemeinsame Reihenfolge zweier Journalströme | 13/13, 0,025 s; 923 unabhängige tatsächliche Reihenfolgen und 697 begrenzte Kopfkombinationen | `e1b3c-joint-order.log` |
| Versionierte Lots und kumulative Rücknahmen ohne Rundungsreset | 12/12, 0,075 s; 3.731 Vergleiche gegen genaue Bruchrechnung | `e1b3c-return-lots.log` |

Der zweite Baustein erhält die tatsächliche ursprüngliche Lotbasis über den
Wechsel des Erstattungsschreibers. Beim mittleren 39,67-Euro-Lot mit 6,34 Euro
Steuer ergibt die erste Rücknahme von 13,22 Euro genau 2,11 Euro Steuer; die
zweite gleich hohe Rücknahme muss 2,12 Euro ergeben. Ein falscher Neustart
am verbleibenden Rest würde diese Grenze verletzen.

Der [vorläufige 3c-Nachweis](CRM_ERP_PRUEFNACHWEIS_E1B3C.json) bindet diese
begrenzten Ergebnisse und ihre Quellstände. Sie sind keine Abnahme der noch
laufenden Datenbank-, API-, Client- oder Restoreintegration. Deren gemeinsame
Chronologie und vollständige aktuelle Quellenrechte werden getrennt umgesetzt.
Die Gesamtquote und die offenen Gesamtabnahmen ändern sich dadurch nicht.


### Erste 3c-Integration, noch kein abschließender Quellnachweis

Die neue Registrierung und der tatsächliche lokale HTTP-Zugang bestehen
16/16 Fälle in 6,030 Sekunden. Die unabhängigen neuen HTTP-/Restorefälle
bestehen 8/8 in 7,338 Sekunden, die echten HTTPS-/MFA-Abläufe 8/8 in
18,744 Sekunden; die bisherige HTTP-/Restore-Auswahl besteht 67/67 in
26,387 Sekunden. Diese ersten Integrationsläufe liefen während der weiteren
Entwicklung. Sie werden nicht als endgültige Prüfung des späteren Quellstands
geführt; separate Initialprotokolle und ihre Grenzen stehen im 3c-Nachweis.

Der unabhängige Review hat zwei zusätzliche Backendprüfungen angestoßen:
Die alte R1-Kandidatenliste muss die erweiterte vollständige Quellenhülle
berücksichtigen; historische Kapazitätsgates müssen R1-Bezüge auf ihren
beobachteten Sequenzpräfix begrenzen. Der alte Browser-Auswahlweg muss beim
Wiederanzeigen gespeicherter Ursprünge dieselbe Quellenhülle frisch prüfen.
Die entsprechenden Korrekturen und Regressionen gehören in den abschließenden
3c-Nachweis; ein unveränderter alter Antwortinhalt ersetzt diese aktuellen
Rechte- und historischen Integritätsprüfungen nicht.

Die Paketlisten für native Prüfung, Supportarchiv und Windows-Build wurden auf
die neuen Module erweitert und gegeneinander abgeglichen: 46 Backend-/
Abhängigkeitsdateien und acht Betreiberdateien stimmen überein. Dabei wurden
zwei bisher fehlende 3a-/3b-API-Dokumente in der Windows-Build-Kopierliste
nachgetragen. Das zuvor geprüfte Supportarchiv enthielt sie bereits. Dieser
statische Listenabgleich ist keine Prüfung einer gebauten Windows-Anwendung.


## 03.11.2026 – E1b-3c umgesetzt und geprüft

Erstattungen können jetzt ausdrücklich ganze Portionen aus ursprünglichen
C1- und wiederverwendeten C2-Anteilen gemeinsam zurücknehmen. Die neue
R2-Historie erhält die unveränderten ursprünglichen Centgrundlagen, die alte
R1-Historie und erfolgreiche alte Anfragequittungen. Ein chronologischer
Prüfer verbindet beide Journalströme; die aktuelle vollständige Quellenhülle
wird zusätzlich auf Rechte geprüft. Neue Tabellen, H6/Restoreberichtschema 7,
beide Clients und die Paketlisten sind integriert. Zahlungen und offene Posten
werden dadurch nicht ein zweites Mal verändert. Steuerliche Klassifikation
ist weiterhin nicht implementiert.

Der reale Browser- und Flutter-HTTP-Ablauf prüft zwei weitere vollständige
Rücknahme-/Wiederverwendungszyklen: 26,44 Euro ergeben 22,21 Euro netto und
4,23 Euro ausgewiesenen Steueranteil; der nächste Zyklus erhält 39,67 Euro
mit 33,33/6,34 Euro. Diese Beträge sind dokumentarisch und kein Steuerergebnis.

| Abschließende Prüfung | Ergebnis | Protokoll unter `work/verification/` |
| --- | --- | --- |
| Backend vollständig | 609 ausgeführt, 608 bestanden, ein bestehender Windowsfall unter Linux übersprungen; 144,231 s | `accounting-refunds-v2-backend-full.log` |
| Accounting-Domainauswahl | 108/108; 38,545 s | `e1b3c-accounting-domain-final.log` |
| HTTP und Restore | 75/75; 31,328 s | `accounting-refunds-v2-http-restore-final.log` |
| Tatsächliches HTTPS und MFA | 8/8; 20,504 s | `accounting-refunds-v2-https-final.log` |
| PostgreSQL, neue Fälle und historische Regression | 14/14 plus 10/10, ohne Skips; 204,560 s und 77,522 s | `pg-refunds-v2-initial.log`, `pg-refunds-v2-regression.log` |
| Flutter vollständig | 579/579; Analyse ohne Befund | `e1b3c-flutter-full.log`, `e1b3c-flutter-analyze-final.log` |
| Browserlogik mit Node | 135/135 | `accounting-refunds-v2-node.log` |
| Browser vollständig | 16/16 tatsächliche Abläufe, Exit 0 | `accounting-refunds-v2-browser-full.log` |
| Native Paketprüfung | 15/15; 3,453 s | `accounting-refunds-v2-native-final.log` |

Die Auswahlen überschneiden sich; ihre Fallzahlen werden nicht zu einer
Gesamtzahl addiert. Der PostgreSQL-Dateiname „initial“ gehört tatsächlich zum
abschließenden erfolgreichen 14-Fälle-Lauf auf unverändertem Quellstand.
Die 145 Dateien des abschließenden Backend-/Browsermanifests blieben bei beiden
Vollprüfungen unverändert. Weitere Quellmanifeste binden HTTP/PostgreSQL und
Flutter. Eine reine Statusformulierungsänderung im API-/Betreiberdokument
ist getrennt nachgewiesen; die abschließende Paketprüfung verwendet sie bereits.

Der erste Fluttervollauf hatte einen Fehler im neuen HTTP-Testhelfer: Eine
Animation löste während des Klicks die tatsächliche periodische Rechteabfrage
aus; die Anwendung sperrte den Klick korrekt. Der Helfer wartet nun begrenzt
auf das Ende dieser tatsächlichen Abfrage. Der fehlgeschlagene Lauf bleibt
getrennt erhalten. Zusätzlich erhält der Client dokumentarische ausstehende
Befehle auch bei einem ersten 403/404; acht neue Fälle und zwei Kontrollen für
gewöhnliche Operationen prüfen diese Änderung. Der danach vollständig
bestandene Lauf enthält alle 579 Fälle. Der unabhängige Abschlussreview
meldete für diese Änderung keinen offenen Befund.

Der gezielte Browserlauf bestand vor einer abschließenden Absicherung des
alten R1-Dialogs. Bei fehlgeschlagener frischer Autorisierung schließt dieser
jetzt neutral. Der vollständige 16-Abläufe-Lauf prüft zusätzlich den echten
Rechteentzug während einer zweiten Ergebnisseite: keine Wiederanzeige des
Editors und kein finanzieller POST. Weitere Reviewkorrekturen begrenzen
historische Gatebezüge auf den beobachteten Präfix, prüfen kanonische
Zeitstempel neuer Nachweise und erhalten die bisherige Unterscheidung zwischen
fehlender neuer Quelle und beschädigtem gespeichertem Nachweis.

Die Desktop- und 390-Pixel-Aufnahmen des vollständigen Laufs wurden visuell
auf die Dialoganordnung geprüft. Der Browser prüft Bedienbarkeit, exakte
Beträge und Bestätigung zusätzlich automatisiert. Alle Daten sind synthetisch.
Eine signierte Windows-/iPhone-Geräteabnahme oder Produktivbereitstellung ist
damit nicht behauptet. TLS/MFA wird durch den gesonderten echten HTTPS-Lauf
belegt, nicht durch die lokale Browserfixture.

Der [3c-Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_E1B3C.json) hält endgültige
Quellstände, Protokolle und Versionsgrenzen fest. Das Gesamtziel bleibt offen:
28/62 ungewichtete Bausteine sind umgesetzt/getestet; R08.05 bleibt teilweise,
alle sieben Gesamtabnahmen A–G offen. Aus diesem Abschnitt folgt keine
vollständige EÜR, Lohnabrechnung oder Produktionsreife.

Der geprüfte 3c-Implementierungsstand ist lokal in Commit `bef8ec23adbddcde0b619f41b5df88db7d481d59`
gesichert. Die 59 Änderungsquellen und alle 145 Quellen des vollständigen
Prüfmanifests stimmen mit diesem Commit überein. Die Zieldatei ist weiterhin
bytegleich mit dem Upload. Es wurde nichts gepusht oder produktiv bereitgestellt.


## 03.11.2026 – E1b-4a1 begonnen

Auf der abgeschlossenen 3c-Basis `91304fc9eb5cf8c42caa1c75c6b1d5c16ea2a612`
folgt ein ausdrücklich gespeichertes versioniertes Vorbereitungsprofil.
Der [Vertrag](CRM_ERP_EUER_E1B4A1_API.md) begrenzt den Umfang auf erklärte
Stammdaten mit Grund, Nachweisreferenz und unveränderlicher Historie.
Umsatzsteuer, Soll-/Istbesteuerung und Beginn bleiben ohne ausdrückliche Angabe
unbekannt; EÜR begründet keine Istbesteuerung. Sachliche Einordnung einzelner
Geldflüsse folgt separat. Die Gesamtanforderung R08.05 bleibt teilweise.

Die erste lokale HTTP-Prüfung fand eine fehlende strikte Behandlung der neuen
Profilroute: Ein GET-Body wurde wie bei allgemeinen alten Routen verworfen.
Der neue Namespace wird jetzt lokal und online ausdrücklich geprüft. Der
fehlgeschlagene erste 13-Fälle-Lauf bleibt unter
`e1b4a1-registration-local-initial.log` erhalten. Danach bestehen die neue
Registrierung, Profil-HTTP-Fälle und vorhandenen lokalen Accountinggrenzen
zusammen 20/20 in 8,191 Sekunden (`e1b4a1-registration-local-framing.log`).
Dies ist ein erster Integrationsstand, noch keine vollständige Profilabnahme.


### E1b-4a1 umgesetzt, abschließender Browservollauf noch offen

Das eigene Vorbereitungsprofil ist in Backend, Browser und Flutter umgesetzt.
Eine bestätigte Version hält erklärte Angaben, Grund, Nachweisreferenz, Akteur
und Erfassungszeit unveränderlich fest. Vier Steuer-/Beginnangaben dürfen
unbekannt bleiben. Lesen und Vorschau erzeugen keine Version; ein erfolgreich
bestätigter Originalauftrag bleibt auch nach späteren Versionen unverändert
wiederholbar. Das alte Accounting.status, Geldflüsse und sämtliche bisherigen
Zuordnungs-/Komponenten-/Erstattungsnachweise bleiben unverändert. Es entsteht
keine Steuerregel, CashEvent-Einordnung oder fertige EÜR.

| Abgeschlossene Prüfung | Ergebnis | Protokoll unter `work/verification/` |
| --- | --- | --- |
| Backend vollständig | 630 ausgeführt, 629 bestanden, ein bestehender Windowsfall unter Linux übersprungen; 140,025 s | `e1b4a1-backend-full.log` |
| Accounting-Domain | 125 verschiedene Fälle in einer 123-Fälle-Auswahl und zwei ergänzenden Fällen, davon 17 neue Profilfälle | `e1b4a1-accounting-domain-initial.log`, `e1b4a1-profile-old-evidence.log` |
| Registrierung und lokales HTTP | 20/20; 8,191 s | `e1b4a1-registration-local-framing.log` |
| HTTP und Restore | 82/82; 43,233 s | `accounting-profile-http-restore-final.log` |
| Tatsächliches HTTPS und MFA | 6/6; 8,057 s | `accounting-profile-https-final.log` |
| PostgreSQL | 9 neue plus 12 historische Migrations-/Restorefälle, ohne Skips; 54,380 s und 106,718 s | `pg-profile-initial.log`, `pg-profile-regression.log` |
| Flutter vollständig | 649/649; angezeigte Dauer 3:08, Analyse ohne Befund in 6,8 s | `e1b4a1-flutter-full.log`, `e1b4a1-flutter-analyze-final.log` |
| Browserlogik mit Node | 147/147 | `accounting-profile-node.log` |
| Gezielter tatsächlicher Profil-Browserablauf | bestanden, Exit 0 | `accounting-profile-browser-targeted.log` |
| Gezielter tatsächlicher R1-Browserablauf nach Waitkorrektur | bestanden, Exit 0 | `accounting-profile-r1-wait-targeted.log` |
| Native Paketprüfung | 15/15; 3,179 s | `accounting-profile-native-final.log` |

Die Gruppen überschneiden sich und werden nicht zu einer Gesamttestzahl
addiert. Der vollständige Browserlauf ist in diesem Zwischenstand ausdrücklich
noch offen. Vorläufiger [Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_E1B4A1.json).
Die 115 Backendquellen blieben im Vollauf unverändert. Flutter bestätigt zehn
Flutter-/Fixturedateien, dieselben 115 Backendquellen und den aktuellen
API-Vertrag. HTTP/PostgreSQL haben eigene Manifeste. Die ursprüngliche
API-Einleitung wurde ausschließlich auf einen neutralen Vertrags-/Nachweisverweis
aktualisiert; dieser genaue Wortlautunterschied ist separat dokumentiert.
Die Paketprüfung verwendet bereits die aktualisierte Dokumentation.

Anfängliche Flutterläufe scheiterten an der fehlenden Freigabe für lokale
Testsockets und an zwei Testannahmen: Ein einzeiliges Textfeld filtert einen Zeilenumbruch;
ein weiter unten liegender Historienknopf wird erst beim Scrollen gebaut.
Die Tests prüfen nun DEL als tatsächlich eingegebenes Steuerzeichen und
scrollen begrenzt zum echten Knopf. Dafür war keine Produktkorrektur nötig.
Die abschließende vollständige Suite enthält den echten HTTP-Profilablauf mit
Antwortverlust, späterer Version, tatsächlichem Rechteentzug und unveränderten
alten Cash-/OP-Daten. Der unabhängige abschließende Lesereview des Backends
und beider Clients meldet keinen offenen Befund.

Der erste Profil-Browser-Targetlauf versuchte im Testhelfer den Geltungsbereich
der globalen Adminberechtigung auszuwählen. Die vorhandene Rechteoberfläche
sperrt dieses Feld korrekt auf Global. Der Helfer prüft nun den gesperrten
Globalwert; der folgende vollständige Profil-Targetlauf bestand.

Der erste vollständige 17-Abläufe-Versuch scheiterte später an einem vorhandenen
R1-Testwait auf Playwright response.finished(). Der gesicherte Fehlerlauf
`accounting-profile-browser-full-refund-wait-failure.log` zählt nicht als Erfolg.
Die reine Testkorrektur beobachtet stattdessen die echte unveränderte
Client-Promise-Erfüllung nach Verarbeitung der tatsächlichen HTTP-200-Antwort.
Ereignis-ID, Vorschauhash, begrenzte Wartezeit und das Ausbleiben eines erneut
geöffneten Dialogs bleiben geprüft. Gegen das ursprüngliche 150-Dateien-Manifest
unterscheidet sich ausschließlich `web/office/tests/refund-flow.cjs`.
Der anschließende vollständige R1-Targetlauf bestand; danach wurde der gesamte
Browserlauf erneut gestartet. Dessen Ausgang bleibt bis zum tatsächlichen
Abschluss offen.

Die Desktop-/390-Pixel-Aufnahmen des gezielten Profilablaufs wurden visuell
geprüft: unbekannte Angaben sind lesbar, die schmale Ansicht scrollt vertikal
und bleibt innerhalb der Breite. Eine signierte Windows-/iPhone-Geräteabnahme
oder Produktivbereitstellung ist weiterhin nicht nachgewiesen. Gesamtquote
28/62, R08.05 teilweise und alle Gesamtabnahmen A–G bleiben unverändert.


## 03.11.2026 – E1b-4a1 umgesetzt und geprüft

Der abschließende vollständige Browserlauf hat **alle 17 tatsächlichen Abläufe
bestanden**, Exit 0. Er umfasst das neue ausdrücklich gespeicherte
Vorbereitungsprofil und die bisherigen Bereiche einschließlich der mehrfachen
Erstattungs-/Wiederverwendungszyklen, Einkauf, Kalender, Fotos, Unterschrift,
rollenbegrenzter Lagerarbeit und Kontaktformular. Die zuvor korrigierte
R1-Teststelle bestand auch in diesem vollständigen Lauf. Rohprotokoll:
`work/verification/accounting-profile-browser-full.log`.

Die 150 Dateien seines abschließenden Quellmanifests blieben während des Laufs
bytegleich (`accounting-profile-browser-source-check.log`). Zusammen mit den
oben genannten bestandenen Prüfungen — Backend 629 bestanden plus ein
bestehender Windows-Skip, Flutter 649/649 und Analyse ohne Befund, Node 147/147,
HTTP/Restore 82/82, tatsächliches HTTPS/MFA 6/6, PostgreSQL 9+12 und native
Paketprüfung 15/15 — ist der Profilabschnitt im beschriebenen Umfang geprüft.
Die Gruppen überschneiden sich; keine addierte Gesamtfallzahl wird behauptet.
Der lokale Browsertransport ersetzt weiterhin nicht den separat ausgeführten
HTTPS-/MFA-Nachweis oder eine echte native Geräteabnahme.

Der gesicherte Implementierungsstand ist
`df7a4325bc28681b5e677efa6f6a1da56c11ee86`. Alle 50 geänderten Code-/
Vertragsdateien und alle 150 vollständigen Browserprüfquellen wurden zusätzlich
gegen genau diesen Commit geprüft. Der [4a1-Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_E1B4A1.json)
bindet endgültige Ergebnisse, historische Fehlversuche und Versionsgrenzen.
Die Originalzieldatei wurde erneut bytegleich mit dem Upload verglichen;
der abgeschlossene 3c-Prüfnachweis blieb unverändert. Es wurde nichts gepusht
oder produktiv bereitgestellt.

E1b-4a1 ist damit abgeschlossen; die sachliche Einordnung einzelner Geldflüsse
E1b-4a2, steuerliche Klassifikation, Perioden/Korrekturen, Beraterpaket und
vollständige EÜR bleiben offen. Das Vorbereitungsprofil aktiviert keine
Steuerregel. Die Gesamtquote bleibt 28/62 ungewichtete Bausteine, R08.05 bleibt
teilweise, alle Gesamtabnahmen A–G bleiben offen.

## 03.11.2026 – Gesamtziel wieder priorisiert: Kundenauftrag ausführen und abrechnen

Der erneute vollständige Zielabgleich hat die Schwerpunktsetzung korrigiert:
Die bisherigen EÜR-Unterabschnitte sind erhalten und geprüft, schließen jedoch
keinen Gesamtabnahmefall A–G. Der aktive Schwerpunkt ist wieder der früh
nutzbare durchgängige Kundenauftrag. Einzelunternehmen mit EÜR sowie reguläre
Mitarbeiter und Minijobs bleiben verbindlicher Fachumfang. Es wird kein neuer
Fertigstellungsprozentsatz aus Unterabschnitten abgeleitet.

Der [Arbeitsplan Kundenauftrag](CRM_ERP_KUNDENAUFTRAG.md), die Anforderungen und
der Umsetzungsplan sind aktualisiert. Das Original `CRM_ERP_Gesamtziel.txt`
ist erneut bytegleich mit dem Upload verglichen; SHA-256 bleibt
`a4dea28f6de4afd3e36d1549441aad91ce16dad374f56097979cc2d79b07fbf5`.

### Umgesetzt

- Integrierte Offline-Serviceberichte verwenden das bestehende Businessarchiv.
  Entwurf, geprüfter Inhalt, Name und Zeichnung werden im verschlüsselten
  Gerätespeicher gesichert. Eine lokale Unterschrift ist sichtbar von einer
  bestätigten Übertragung getrennt. Historische Core-Protokolle bleiben erhalten.
- Atomarer Import mit festen Kennungen, zwei Archivversionen, einer
  Empfangsbestätigung und unveränderlichem PDF. Originalinhalt und Gerätezeiten
  werden nicht normalisiert; der Serverempfang ist gesondert gekennzeichnet.
- Neue enge Gerätefreigabe nur für die Erfassung und eigene Einzelberichte/PDFs.
  Aktuelle Rechte und Modulfreigabe werden auch bei Wiederholungen und nach der
  PDF-Erzeugung geprüft. Änderungen an Projektname oder Kundenname verhindern den Erstimport;
  bereits bestätigte Wiederholungen behalten ihren historischen Stand.
- Die Flutter→Python-Offline-Reise verbindet Zeiten, Foto, Protokoll, Neustart,
  verlorene Commit-Antwort, identische Wiederholung, PDF-Prüfsumme und erneutes
  Offlineöffnen. Eine zweite echte PostgreSQL-/HTTP-Reise führt von Anfrage und
  Artikelimport über Angebot, Kundenportalannahme, Auftrag und Ausführung bis
  Rechnung sowie vollständiger Zahlung. Die Projekt-ID bleibt dabei gleich.
- Ein vorhandener SQLite-Restorefehler ist korrigiert: Fremdschlüssel werden vor
  dem Widerruf der Sitzungen aktiviert, damit abhängige Gerätefreigaben ebenfalls
  entfernt werden. SQLite- und tatsächlicher PostgreSQL-Dump/Restore erhalten
  Original, PDF, Versionen und Empfangsbestätigung.
- Die [Bedienanleitung](CRM_ERP_OFFLINE_SERVICEBERICHTE.md), das neue Backendmodul
  und die Tests sind in Paketquellen beziehungsweise CI berücksichtigt. Im
  Browser kennzeichnet die Berichtsliste Gerätezeit und Serverempfang getrennt.

### Tatsächlich ausgeführte Abschlussprüfungen

| Prüfung | Ergebnis | Nachweis unter `work/verification/` |
| --- | --- | --- |
| Backend vollständig | 643 ausgeführt, 642 bestanden, 1 bestehender Windows-Skip; 135,186 s | `customer-workflow-backend-full.log` |
| Flutter vollständig | 670 bestanden | `customer-workflow-flutter-full.log` |
| Flutter Analyse | keine Probleme; 6,5 s | `customer-workflow-flutter-analyze.log` |
| JavaScript/Node | 147 bestanden | `customer-workflow-node-authorized.log` |
| Native Paketprüfungen | 15 bestanden; 3,573 s | `customer-workflow-native-final.log` |
| Flutter Repository + echter HTTP-Ablauf | 19 bestanden; Teilmenge der Gesamtsuite | `offline-service-reports-client-final.log` |
| Neue Widgetabläufe | 2 bestanden; Teilmenge der Gesamtsuite | `offline-service-report-widgets.log` |
| HTTP/TLS/Restore und passende Altregression | 37 bestanden; 14,415 s; teilweise in Backend-Gesamtsuite enthalten | `offline-reports-transport-final.log` |
| Anfrage bis vollständige Zahlung, echtes PostgreSQL/HTTP/MFA | 1 bestanden; 2,327 s | `customer-execution-journey-pg.log` |
| Tatsächlicher PostgreSQL-Dump/Restore | 1 bestanden; 4,546 s | `offline-reports-pg-restore-final.log` |

Die Zahlen werden nicht addiert. 78 Backend-Produktquellen sowie 127
Flutter-Quellen/Testdateien sind vor und nach den jeweiligen Gesamtläufen
unverändert geprüft. 29 geänderte Code-/Test-/CI-Dateien, 26 Artefakte und die
Versionsgrenzen sind im [Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_KUNDENAUFTRAG.json)
mit Prüfsummen festgehalten. Die separate interne Quellprüfung meldet nach den
Korrekturen keinen verbleibenden Blocker; sie ersetzt keine unabhängige
Sicherheitsprüfung. Die komplette Browser-17er-Suite wurde für diesen Abschnitt
nicht erneut ausgeführt; JavaScript-Tests und die echte HTTP-/App-Kette sind der
hier tatsächlich ausgeführte Umfang.

Reproduzierbare Hauptbefehle aus dem Repository (Flutter innerhalb `app`):

```bash
PYTHONPATH=backend:backend/online backend/.venv/bin/python -m unittest discover -s backend -p 'test_*.py' -v
flutter analyze --no-pub
flutter test --no-pub --reporter expanded
node --test --test-reporter=tap web/office/tests/*.test.mjs
backend/.venv/bin/python -m unittest discover -s scripts -p test_native_release.py -v
PYTHONPATH=backend:backend/online backend/.venv/bin/python -m unittest online.test_business_offline_reports_api test_business_offline_reports_transport test_business_offline test_plan_access test_backup online.test_business_boundary_review online.test_business_operations_api online.test_business_planning_time_api -v
PYTHONPATH=backend:backend/online backend/.venv/bin/python -m unittest online.test_customer_execution_journey_pg -v
PYTHONPATH=backend:backend/online backend/.venv/bin/python -m unittest online.test_business_offline_reports_restore_pg -v
```

Die PostgreSQL-Befehle verlangen ausdrücklich eine entbehrliche lokale
`SMARTPLAN_TEST_DSN` und die vorhandenen `pg_dump`-/`pg_restore`-Werkzeuge. Sie
setzen das Testschema zurück. Alle Daten waren synthetisch; lokale Socket- und
Kindprozessrechte wurden für diese Testläufe freigegeben. Es wurden keine Nachrichten versandt, keine realen Zahlungen ausgeführt und
keine Anbieter- oder Produktivdaten verändert.

### Fehlversuche und Grenzen

Die neuen Tests fanden den oben behobenen SQLite-Restorefehler und im Client
Fehler bei typisierten Map-Zuweisungen beziehungsweise veränderlichen
Unterschriftslisten. Die eingefrorene Erfassung ist nun gegen spätere Änderungen
an den Editorlisten geschützt. Weitere frühe Fehlläufe betrafen Testannahmen zu
vorhandenen Antwortformaten, fehlende synthetische PG-Anmeldung, einen im
Restoretest fälschlich ersetzten MFA-Verschlüsselungsschlüssel sowie
Widgetausrichtung/Timerbereinigung. Korrigierte Tests sind bestanden; solche
Fehlläufe werden nicht als erfolgreiche Produktprüfungen gezählt.

Ein Node-Erstlauf scheiterte an `EPERM` beim lokalen Zeitzonen-Kindprozess und
bestand nach Freigabe der benötigten Ausführungsrechte. Der erste
Flutter-Analyseaufruf versuchte unnötig einen Paket-Sicherheitsabgleich im
Netzwerk und endete mit Exit 69; ein parallel gestarteter Testlauf wurde vor
Abschluss abgebrochen. Die abschließenden Läufe nutzten mit `--no-pub` die
installierten Abhängigkeiten. Der erste Analyse-Rohlog wurde beim erneuten
Aufruf überschrieben; dafür liegt nur der beobachtete Werkzeugausgang vor.

Das Gesamtziel ist weiterhin nicht erreicht. Alle Abnahmen A–G bleiben offen.
Der Kostenabgleich umfasst gebuchte Materialien und genehmigte Zeiten;
Fremdleistungen, sonstige Kosten und vollständige Wirtschaftlichkeit fehlen.
Echte Windows-/iPhone-Installationen, Updates und Geräteabnahmen sind hier nicht
nachgewiesen. Weitere Dokumentarten, die fachliche Klärung konfliktbehafteter
unterschriebener Erfassungen, vollständige EÜR, Lohn, KI/Regeln und externe
Fach-/Sicherheitsnachweise bleiben im Gesamtplan bestehen.


## 03.11.2026 – Fortsetzung des vollständigen Gesamtziels

Der aktuelle zusammenhängende Integrationsstand und die laufenden Abschlussprüfungen stehen in [CRM_ERP_INTEGRATIONSSTAND_2026-11-03.md](CRM_ERP_INTEGRATIONSSTAND_2026-11-03.md). Bestätigte Unternehmens- und Steuerangaben stehen in [CRM_ERP_ENTSCHEIDUNGEN.md](CRM_ERP_ENTSCHEIDUNGEN.md). Dieser Zwischenstand bedeutet keine Gesamt- oder Produktivfreigabe.


## 03.11.2026 – Fortsetzung über das Vorjournal hinaus

Der aktuelle [Integrationsstand](CRM_ERP_INTEGRATIONSSTAND_2026-11-03.md) dokumentiert die geprüften Kunden-, Personal-, EÜR-, Rechnungs-, Inventur-, Assistenten- und Übersichtsabläufe. Neue Quellen und Grenzen sind in den jeweiligen Fachberichten verlinkt. Sprachbedienung, Lohnkonto-Pflichtangaben, Verkaufschancen und Unternehmensübergabe werden weiterentwickelt. Die Gesamt-Abnahmen A–G bleiben offen; es gab keine produktive Veröffentlichung oder externe Fachübermittlung.


## 03.11.2026 – Weitere gemeinsame Integration

Dateiimport, Unternehmensübergabe, Lohnkonten, Sprachentwürfe und Zusatzfelder
sind in den dokumentierten Grenzen mit echten Client-/HTTP-/Datenbankabläufen
geprüft. Der [aktualisierte Integrationsstand](CRM_ERP_INTEGRATIONSSTAND_2026-11-03.md)
nennt die jeweiligen Nachweise und laufenden Arbeiten: Datenschutzclients,
Lohnzahlungen/EÜR, Service/Reklamationen und belegter Bankabgleich.

Das Abhängigkeitsupdate behebt 43 bekannte Meldungskennungen in zwei Python-
Paketen. Der erneute Python/npm/Dart-Abgleich sowie die Grenzen der Prüfung
stehen im [Sicherheitsnachweis](CRM_ERP_ABHAENGIGKEITEN_SICHERHEIT.md). Tatsächlich
bestanden mit neuer Laufzeit 95 kaufmännische und 67 Planimporttests; der
Node-Zwischenlauf bestand 284 Tests, die Paketprüfung 16. Das unveränderte
Gesamtziel bleibt maßgeblich; keine vollständige Produktivfreigabe.


## 03.11.2026 – zusammenhängende Fachketten und Bedienprüfung

Datenschutzfälle, belegte Lohnzahlungen zur EÜR und Kundenservice sind mit
Backend, beiden Clients und tatsächlichen Browserabläufen geprüft. Zwei
PostgreSQL-Journeys verbinden den Kundenauftrag mit Teil-/Restlieferung,
Offlinebericht, Rechnung/Zahlung, Projektkosten/EÜR, Inventur, Gerät, Wartung,
Service und echter Wiederherstellung. Die konkreten Grenzen bleiben in den
jeweiligen Fachdokumenten ausgewiesen.

Die Browser-Bedienprüfung fand zu schwache Hilfstextkontraste und einen
rückwärts aus dem Dialog entweichenden Tastaturfokus. Beide Fehler wurden
behoben; der Lauf über 18 gerenderte Ansichten besteht. Menschliche und native
Bedienhilfenprüfungen bleiben offen. Das aktualisierte Quellinventar enthält
153 Komponenten; npm wurde nach Aufnahme des axe-Prüfwerkzeugs erneut ohne
bekannte Meldung geprüft.

Bankabgleich, Betriebsmittel und zweite Unternehmensinstanz werden integriert.
Der Finanz-Restore umfasst jetzt Horizont 10/Prüfberichtschema 11; 49 bisherige
Finanz-HTTP-Fälle und neun Lohnzahlungs-Fachfälle bestehen danach. Alte
Prüfberichte werden weiterhin nach ihrem ursprünglichen Umfang validiert.
Die Gesamtfreigabe und der abschließende gemeinsame Lauf stehen aus.


## 03.11.2026 – breite Regression und nächste echte Funktionslücken

950 Backendfälle liefen am integrierten Bank-/Betriebsmittelstand: 949 bestanden,
ein Windows-Jobobjekttest unter Linux ausgelassen. 323 Node-Fälle bestanden.
Die breite Flutterprüfung (835 Tests) hatte acht Fehler: ein leeres Bankdatum
und sieben veraltete Portal-Testbeschriftungen. Die Fehler sind korrigiert,
gezielte Rechte-/Banknachprüfungen bestehen. Der ursprüngliche Lauf bleibt im
Nachweis als fehlgeschlagen erhalten; kein nachträgliches Grünrechnen.

Ein großer gemeinsamer Browserlauf bestand Portal und Finanzketten bis zu den
wiederverwendeten Erstattungsursprüngen, brach aber im Profilteil ab. Die frische
gezielte Prüfung deckte veraltete gestapelte Fehlermeldungen auf. Nach enger
Korrektur besteht der Profilablauf. Der abgebrochene Gesamtlauf ist keine
Gesamtabnahme.

Entwicklung wird konkret fortgesetzt: Lieferantenretouren/Bestellmengenänderungen,
Midijob-Vollmonate und vollständig verkabelte zweite Unternehmensinstanz.
Die weiteren Lohn-Codefälle sind im Lückenplan ausdrücklich benannt und bleiben
Umsetzungsarbeit; externe Fachfreigabe ersetzt diese Arbeit nicht.


## 03.11.2026 – eingefrorene Clients, Retouren-/Provisionierungsgegenprüfung

- Vollständige Node-Regression: 336/336 in 2,466 s; vollständige Flutterregression:
  848/848 aus 98 Suiten in 228,669 s, keine Skips, Analyse ohne Befund (6,2 s).
  Die acht Befunde des früheren 835-Test-Laufs sind behoben und bleiben historisch
  dokumentiert; siehe `CRM_ERP_FLUTTER_GESAMTPRUEFUNG_2026-11-03.md`.
- Lieferantenretouren/Bestelländerungen: eigene Regression 118/118 in 28,617 s,
  unabhängige überlappende Regression 96/96 in 23,397 s einschließlich sieben
  eigener Gegenproben, PostgreSQL 3/3 in 13,732 s. Die Gegenprüfung deckte zwei
  echte Widersprüche manipulierter historischer Quittungen auf; beide werden
  jetzt gegen ursprüngliche normalisierte Eingaben und Journalstände geprüft.
- Provisionierung: vier abschließende bestehende Release-/Restorefälle bestanden
  in 16,194 s; getrennte Zwei-Unternehmens-/UID-Nachweise bleiben konkret in der
  Provisionierungsdokumentation ausgewiesen. Kein Produktivhost verändert.
- Paketprüfung: 16/16 in 4,172 s. Die anschließende reine Aufnahme der finalen
  Retourenanleitung wird noch einmal auf Vollständigkeit geprüft.
- Ein Neustart der Cloud-Umgebung unterbrach den breiten Backend- und
  Browsergesamtlauf. Die unvollständigen Logs bleiben gesondert erhalten;
  beide Prüfungen wurden am identischen eingefrorenen Produktcode neu gestartet.
  Der Projektpfad und die unveränderte Ziel-Dateiprüfsumme sind bestätigt.
- Nächste echte Entwicklungsarbeit: private belegte Lohnfakten, getrennte
  Zeitachsen und Teilmonatsrechner sowie Reisepauschalen mit eigener
  Erstattungsquelle. Quellen-/API-Entwürfe liegen vor; fehlender Code wird nicht
  als externe Abhängigkeit behandelt.


### Gesicherter Entwicklungs-Checkpoint `31c5184`

Der gesamte bisherige Entwicklungsstand ist lokal committed; kein Remote-Push
oder produktiver Rollout wurde ausgeführt. Die vollständige Backendregression
am eingefrorenen Stand besteht mit 989 Fällen: 988 bestanden, allein der
Windows-Jobobjektfall unter Linux ausgelassen (279,212 s). Die vollständige
Paketprüfung einschließlich finaler Retourenanleitung besteht mit 16/16 Fällen
(5,180 s). Das reproduzierte Quellinventar bleibt bytegleich bei 153 Komponenten.
Zusammen mit den bereits dokumentierten 336 Node- und 848 Flutterfällen bildet
dies einen konkreten Entwicklungsnachweis. Der lange gemeinsame Browserlauf
läuft noch; er wird erst nach vollständigem Runnerabschluss als bestanden
gezählt. Die nächste Entwicklung beginnt in eigenen neuen Moduldateien, während
die bereits laufende Browserprüfung ihre eingefrorenen Oberflächen behält.


Der abschließende gemeinsame Browserlauf des Checkpoints hat alle 17 Abläufe
bestanden: tatsächliche MFA-/HTTP-Anmeldung, Rechte-/Modulwechsel, Portal,
Buchführungsketten, Einkauf, Planung, Originaldateien, Signatur, Lagerrolle,
mobile Ansichten und Anfrageformular. Namespace-, PID-, Netzwerk- und
Seccomp-Sandbox wurden vor dem Anwendungszugriff tatsächlich geprüft. Die
Browserdateien blieben bis zum vollständigen Runnerabschluss unverändert;
der Testdienst hatte den Checkpoint bereits vor der folgenden Backendintegration
geladen. Keine Aussage über produktives TLS oder reale Windows-/iPhone-Geräte.


## Ergänzung: Lohnteilmonate und Reisekosten-Finanzintegration

P2-Lohnfakten und P3a-Teilmonate sind im beschriebenen Umfang abgeschlossen:
27 Fakten-/Transport-/Gegenprüfungen und drei echte PostgreSQL-Fälle;
120 Lohnregressionsfälle, drei neue PostgreSQL-Teilmonatsfälle sowie neun
historische PostgreSQL-Fälle nach gezielter Anpassung der aktuellen
Restoreumfang-Erwartungen. Die alten Regelmodule bleiben bytegleich.
Die Client-Abnahme umfasst 51 Node-, 52 Flutterprüfungen, Analyze und einen
echten MFA-/HTTP-Browserablauf einschließlich 390-Pixel-Darstellung.
Diese Zahlen überlappen und sind keine addierbare Gesamtzahl. Nachweise:
[Teilmonate](CRM_ERP_LOHN_TEILMONATE_2026.md),
[Fakten](CRM_ERP_LOHN_FAKTEN_2026.md),
[Clients](CRM_ERP_LOHN_ZEITACHSEN_CLIENTS.md).

Die neue tatsächliche Reisekostenzahlung ist mit EÜR und Bank verbunden:
sechs eigene Kettenfälle und bestehende Lohnzahlung-/Bankregression bestehen
gemeinsam mit **32/32** Prüfungen. Hinzu kommen **49/49** Finanz-HTTP-Prüfungen
und je **5/5** unabhängige öffentliche Quellenprüfungen in Node und Flutter.
Belegt sind Teilzahlungen ohne Vorsteuer, Finanzzugriff ohne Personalquellen,
Periodensperren, dokumentarische Aufhebung ohne erfundene Rückzahlung,
unveränderte alte Exporte und kompletter Restoreumfang11/Bericht12.
Der Gegenversuch fand eine doppelt verwendbare alte Zahlungsreferenz;
der neue Writer sperrt diese nun. Beide Clients wiesen zuvor unmögliche
Kalendertage nicht ab; dieser Fehler ist ebenfalls behoben.
[Testprotokolle und Quellhashes](evidence/travel-finance-integration-2026-11-03.json)
bewahren Umfang und frühere fehlgeschlagene Prüfungen nachvollziehbar.

Weitere Reise-/Auslagen-/Lohnfälle und ihre gesamte Browser-/PostgreSQL-Abnahme
sind weiterhin in Arbeit. P3b/P4 und der reduzierte eigene Mitarbeiterbeleg
werden additiv entwickelt; dieser Zwischenstand ist keine Gesamtfertigstellung.


## 03.11.2026 – Anspruchsregeln, Reiseausgabe und neue Gesamtfälle

- P4-Krankheitsregeln erhalten explizite Versionen für Stundenlohn-Fristbeginn,
  hinzugetretene Ursachen und AU vor Beschäftigungsaufnahme. 109 Fach-, vier
  HTTP- und drei PostgreSQL-Prüfungen einschließlich gemeinsamem Restore der
  gespeicherten Versionen bestehen. Die zusätzliche unabhängige v4-Prüfung
  besteht vier Kalender-/Originalfälle; ihr erster Fehler betraf ausschließlich
  eine geteilte Referenz im Testaufbau.
  [Versionsnachweise](evidence/payroll-sickness-versions-2026-11-03.json),
  [unabhängige Beginnprüfung](evidence/payroll-sickness-start-independent-review-2026-11-03.json).
- Der tatsächliche v5-Lohnabschluss besteht zwei PostgreSQL-Fälle mit MFA/HTTP,
  zwei konkurrierenden Verbindungen, genau einem Abschluss/Steuerrecord,
  Laufzeitrechten, Neustart und Dump/Restore ohne vorausgesetzte Zahlung.
  Ein NULL-Typfehler in der globalen Policyabfrage ist behoben. Der private
  ursprüngliche Auftrag wurde zusätzlich aus den öffentlichen Falldatensätzen
  entfernt; die Integritätsprüfung bindet ihn weiterhin intern an seine Quittung.
  Native und Browser-Gesamtfallintegration werden noch geprüft.
- Die betriebliche Reise-Steuerentscheidung besteht acht Node- und acht
  Flutterfälle sowie den echten Browserablauf über den produktiven Einstieg.
  Vorschau, verlorene Speicherantwort, Originalwiederholung, Korrektur,
  Aufhebung, Historie und 390-Pixel-Ansicht sind enthalten.
- Reiseregel v3 besteht acht unabhängige Gegenfälle und 104 zusammenhängende
  Backend-/HTTP-/Finanzfälle. Die fünf echten PostgreSQL-Fälle sind nach einem
  gefundenen JSON-Downloadfehler grün: archivierte JSON-Anhänge werden jetzt als
  unveränderte Bytes ausgeliefert. Vorheriger 500 und Nachprüfung sind bewahrt.
  [Backendnachweis](CRM_ERP_REISE_V3_PRUEFUNG_2026-11-03.json).
- Der neue native Gesamtfalldialog enthält strukturierte Quellenwahl,
  Profilwechsel, Ansprüche, Reisen und ausdrücklich belegte Steuerentscheidung.
  Die erste gerenderte Prüfung fand doppelte leere Dropdownoptionen; diese sind
  korrigiert. Die abschließende Bedienungs- und Lebenszyklusprüfung läuft.

Diese Prüfgruppen überlappen. Sie werden weder zu einer Gesamtzahl addiert
noch als vollständige Fertigstellung der Software ausgegeben. Noch laufende
Quelländerungen benötigen den anschließenden gemeinsamen Regressionsstand.

## Geprüfter Quellstand 2fdfa9f – 03.11.2026

Der lokale Commit `2fdfa9f37bbbaf9e8b6fe4070be6809fe15b69c3` sichert die isoliert geprüfte Zusammenführung der Lohnquellen, Gesamtfälle und Reise-/Finanzabläufe. Auf genau diesem eingefrorenen Quellstand bestanden 1.484 von 1.485 Backendtests (ein Windows-spezifischer Test unter Linux ausgelassen), 398 Node-Tests und 932 Flutter-Tests; die vollständige Flutter-Analyse meldete keine Probleme. Quelldateien und Protokolle sind mit SHA-256 im Nachweis `docs/evidence/payroll-travel-core-regression-2026-11-03.json` und dem zugehörigen Dateimanifest gebunden.

Der erste Flutter-Start scheiterte an einem fehlenden Testinterpreter-Pfad und wurde abgebrochen; der anschließende vollständige Lauf mit dem vorhandenen verifizierten Interpreter bestand. Spätere globale Jahres-/U-Registrierungen, die neueren P4-Oberflächen sowie Einmalbezug-v6 liegen außerhalb dieses eingefrorenen Nachweises. Sie werden weiter implementiert und gesondert geprüft. Der Commit ist ein lokaler Entwicklungszwischenstand, keine Behauptung eines abgeschlossenen Gesamtziels oder einer Produktivfreigabe.

## Weiterentwicklung am 04.11.2026: Jahresquellen, Nullnetto und Einmalbezüge

Die fünf privaten Jahresquellenarten besitzen Browser- und App-Formulare. Die unabhängige App-Gegenprüfung fand und behob verbliebene Dialoge nach Mitarbeiter-/Sessionwechsel und entzogenem Freigaberecht; zehn gezielte Gegenfälle sind nach dem Fix grün. Die Wiederholungsprüfung der geschützten Browser-Lohnpfade besteht61Tests. P4 und Gesamtfälle wurden zusätzlich gegen spät eintreffende private Fehlertexte abgesichert.

Ein tatsächlicher Nullnettomonat kann jetzt mit Originalbeleg und leerer Zahlungsteilliste dokumentiert werden, ohne einen Geldfluss zu erzeugen. Positive Abführungen bleiben separat zu belegen. Domain-, PostgreSQL- und Clientnachweise liegen unter `CRM_ERP_LOHN_NULLMONAT_PRUEFUNG_2026-11-03.json`; die Browser-Gesamtregression wird getrennt fortgeschrieben.

Die neue Source4-Kette für reguläre Einmalbezüge ist in Entwicklung: kanonische Jahresquellen, geschützte Fallannahme, ein dauerhaft an seinen Lohnlauf gebundener Anspruch, tatsächlicher Zahlungsnachweis, Cash und EÜR. Vier unabhängige private Quellen-/Rechtegegenfälle bestehen. Die globale Registrierung aller drei Tabellen, der Unternehmensübergabe und der Quellpakete besteht48Tests (11,138s). Nachweise: `evidence/payroll-oneoff-private-independent-2026-11-03.json` und `evidence/source4-three-table-registration-2026-11-04.json`. Die vollständige PostgreSQL-/Browser-/App-Abnahme dieser neuen Kette ist damit noch nicht erklärt.

Weiter offen bleiben unter anderem weitere Jahreszuordnungen nach bereits abgerechneten Einmalbezügen, mehrere Boni und unterschiedliche tatsächliche Zuflusstage sowie die im Lohn-Lückenplan ausdrücklich benannten Versicherungs- und Meldefälle. Das Gesamtziel bleibt die vollständige Software; ein geprüfter Teilumfang wird nicht als Gesamtabschluss ausgewiesen.

## Fortsetzung am 04.11.2026: Einmalbezug, Sitzungswechsel und Finanzübernahme

Die zusätzliche PostgreSQL-Integration der bezahlten Source4-Jahresübernahme
besteht vier Fälle in 44,607 Sekunden. Nach echter Sicherung und
Wiederherstellung bleiben die kompakte Jahresbasis, ihre Originalannahme,
Lohnlauf, Zahlungsnachweis, Anspruchsverbrauch und PDFs unverändert.
Der Nachweis bindet seinen genauen Quellstand:
`evidence/payroll-oneoff-pg-annual-integration-2026-11-04.json`.
Weitere Änderungen an der Märzklausel-Korrektur werden gesondert geprüft.

Die unabhängigen nativen Gegenprüfungen fanden private Dialoge und verspätete
Fehler nach Kontextwechsel. P4/Source3 bestehen nach Korrektur 59 gemeinsame
Fälle, v6 sechs zusätzliche Fälle. Der gemeinsame Formulareditor löst seinen
alten Sessionlistener und verwirft einen übernommenen Kontext. Ein weiterer
echter Gegenfall zeigte, dass eine späte Antwort des alten Auftrags A die
Formularwerte eines neuen Auftrags B unter gleichem Schlüssel überschreiben
konnte. Die Sicherung der Formularwerte bindet sich jetzt an Owner, Schlüssel
und ursprüngliche request_id. 18 neue Editorfälle und sechs bestehende
Sessionfälle bestehen gemeinsam; Rot-/Grünbelege stehen unter
`evidence/business-editor-context-2026-11-04.json`.

Die Gegenprüfung außerhalb der Lohnentwicklung benennt drei konkrete
verbleibende Implementierungspakete: belegte Finanzübernahme, Katalogpreise
mit Gültigkeitszeiträumen und vollständigem Browserimport sowie
unternehmensweite Ereignisregeln. Bericht:
`CRM_ERP_GESAMTZIEL_GEGENPRUEFUNG_2026-11-04.md`.
Die Anfangssaldo-Implementierung beginnt in einem isolierten Arbeitsbaum;
sie ist zu diesem Zeitpunkt noch nicht im Hauptrepository integriert oder
abgenommen. Historische Anlagen folgen als eigener Vertrag. Bestehende
Archivimporte werden dabei nicht zu neuen Einnahmen oder Ausgaben erklärt.

### Source4-Clients vor der eingefrorenen Gesamtregression

Browser und Flutter unterstützen Vorschau, Abschluss, Korrektur und exakte
Wiederholung der Source4-Rechnung einschließlich tatsächlich belegter
Zahlung, Lohnkonto und eigener reduzierter Mitarbeiterbelege. Der vollständige
Chromium-Ablauf besteht einschließlich Originalhistorie, PDF/JSON und
390-Pixel-Ansicht. 14 benannte Nodefälle, 56 native Regressionsfälle und die
abschließende unabhängige Hauptansichtsprüfung mit 43 neuen Kontextfällen plus
sieben tatsächlichen Source4-Abläufen bestehen. Die Analyse meldet keine
Befunde. Nachweise: `evidence/payroll-oneoff-clients-2026-11-04.json` und
`evidence/payroll-main-context-review-2026-11-04.json`.

Die unabhängige Prüfung fand drei tatsächliche Hauptansichtsfehler: eine
verspätete Vorschau nach Austausch gegen eine andere erlaubte Sitzung mit
gleicher Generation, einen offenen verschachtelten Editor nach Personen-/
Sitzungswechsel und private Unterfenster nach Entfernung der Hauptansicht
bei erhaltenem Navigator. Der Clientowner korrigierte Kontextbindung und
Unterfensterabbau; unveränderte rote und grüne Protokolle bleiben erhalten.
Backend und Clients sind nun für eine neue eingefrorene Gesamtregression
stabil. Deren Ergebnis ist zu diesem Eintrag noch nicht vorweggenommen.

## Geprüfter gemeinsamer Commit 5d9e7fd – 04.11.2026

`5d9e7fd2cc0f04ef46d25d112549408454c6519a` sichert den gemeinsam geprüften
Source4-Stand. Ergebnis: 1.508 bestandene Backendtests und eine
plattformspezifische Auslassung, 473 JavaScript- und 1.103 Fluttertests,
16 Paketprüfungen und vollständige Flutteranalyse ohne Befund.
Nachweis und Grenzen: [Source4-Gesamtprüfung](CRM_ERP_SOURCE4_GESAMTPRUEFUNG_2026-11-04.md).

Vier Fehler des ersten Backendlaufs waren auf unterschiedliche Testuhren
zurückzuführen; zwei Testdateien wurden berichtigt und ein echter
Tageswechsel-Gegenfall ergänzt. Der Produktcode blieb dabei unverändert.
Der erste Paketlauf benötigte den fehlenden lokalen Testinterpreter-Pfad.
Alle Erst-/Folgelogs und beide Quellmanifestfassungen bleiben erhalten.
Beim Fortschreiben des Hauptbranchs wurden die Inhalte sämtlicher 1.531
vorhandenen Arbeitsdateien per SHA-256 unverändert nachgewiesen; laufende
V7-Arbeit blieb erhalten. Kein Remote-Push oder Produktivrollout erfolgte.

Die Entwicklung geht mit Anfangssalden, Katalogimport und weiteren
Lohn-/Zahlungsfällen weiter. Die hierfür entstehenden separaten Arbeitsstände
sind noch kein Teil dieses überprüften Commits und kein Gesamtabschluss.

## Gemeinsamer Checkpoint am 04.11.2026: Anfangssalden und Katalogoriginale

Die Zusammenführung auf Basis `5d9e7fd` besteht 1.565 von 1.566 Backendtests
(ein Windows-spezifischer Skip), 522 Node- und 1.118 Fluttertests. Analyse ohne
Befund, 16 Paketprüfungen und beide tatsächlichen Browserabläufe sind grün.
Zehn gemeinsame PostgreSQL-Fälle und ein zusätzlicher befüllter Katalog-/Opening-
Restore bestehen. Alle 1.626 eingefrorenen Dateihashes waren nach den Prüfungen
unverändert; Original-Gesamtziel und bestehende Source4-Verträge bleiben erhalten.
[Ergebnisse und Grenzen](CRM_ERP_ANFANGSSALDEN_KATALOG_GESAMTPRUEFUNG_2026-11-04.md).

Behoben wurden ein verbliebener privater Kontoname im Dialogtitel nach
Rechteentzug, späte private Quellen nach Kontextwechsel und die erneute Anwendung
der Einzeleingabegrenze auf bereits berechnete große Kontensummen. Browser und
Flutter prüfen dieselben tatsächlich angenommenen positiven/negativen Grenzfälle.
Der Katalogbaustein erhält unveränderte Originale, serverseitige Vorschau,
Annahmehistorie, begrenzte große Antworten und vollständige Paketregistrierung.

Source5-Backend und dessen sichere Mitarbeiterbelege/Clients, historische lineare
Anlagen, datierte Katalogpreise v2 und die native Kataloghistorie laufen separat
weiter. Ihre Teilnachweise gehören nicht zum neuen eingefrorenen Gesamtstand.
Unternehmensweite Ereignisregeln und verbleibende Lohn-/Steuerfälle sind weiterhin
Implementierungsarbeit. Es wurde keine Produktivmigration oder Gesamtabnahme
behauptet.
