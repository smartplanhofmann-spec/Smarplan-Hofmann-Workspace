# CRM/ERP – Fortschritt und Testergebnisse

Die Abschnitte sind chronologisch. Der aktuelle Prüfstand steht unter
**03.11.2026 – E1b-3a umgesetzt und geprüft** am Ende dieser Datei.
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
