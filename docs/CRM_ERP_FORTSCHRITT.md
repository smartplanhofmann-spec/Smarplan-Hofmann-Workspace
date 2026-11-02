# CRM/ERP – Fortschritt und Testergebnisse

Die Abschnitte sind chronologisch. Der aktuelle Entwicklungsschritt steht unter
**Einkauf und positionsgebundene Wareneingänge** weiter unten. Die Ergebnisse
des ersten Abschnitts gehören zum lokalen Commit `14fe4c9`.

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
