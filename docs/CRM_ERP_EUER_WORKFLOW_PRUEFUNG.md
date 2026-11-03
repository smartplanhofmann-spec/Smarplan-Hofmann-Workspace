# EÜR-Workflow: Implementierung und gezielte Prüfungen

Stand: 03.11.2026. Dieser Bericht betrifft den zusammenhängenden eigenen
Buchführungsworkflow in `business_accounting_euer.py`. Er erklärt weder das
gesamte CRM-/ERP-Gesamtziel noch alle steuerlichen Fallgruppen für abgeschlossen.
Die [API](CRM_ERP_EUER_WORKFLOW_API.md) und die
[amtlichen Regelquellen](CRM_ERP_EUER_REGELQUELLEN_2026.md) bestimmen den Umfang.

## Ausgeführt

| Prüfung | Ergebnis | Nachweis |
| --- | --- | --- |
| Neue EÜR-Domänentests auf echten isolierten SQLite-Datenbanken | **18/18**, 8,864 s | `work/verification/euer-domain-final.log` |
| EÜR- und bestehende Vorjournaltests gemeinsam nach Quellenrollen-Hook | **37/37**, 12,921 s | `work/verification/euer-domain-source-coverage.log`; danach wurde noch die reservierte Zahlungsnachweisrolle in der EÜR-Quellenliste präzisiert, aktuelle EÜR-Tests sind oben separat erneut geprüft |
| Echte PostgreSQL-Runtime, MFA/HTTP, Konkurrenz, Altbestandsmigration und Dump/Restore | **4/4**, 19,948 s | `work/verification/euer-pg-final.log` |

Ausführbare Testmodule:

```
PYTHONPATH=backend:backend/online backend/.venv/bin/python -m unittest test_business_accounting_euer -v
PYTHONPATH=backend:backend/online backend/.venv/bin/python -m unittest online.test_business_accounting_euer_pg -v
```

Der PostgreSQL-Lauf benötigt die schon vorhandene abgesicherte lokale
Wegwerfdatenbank und Testkonfiguration. Der lokale Runner
`work/verification/run-euer-pg.py` liest ausschließlich die vorhandene synthetische
Konfiguration; keine Zugangsdaten werden protokolliert. Kein Bank-/Mail-/DATEV-/
ELSTER-Dienst wurde angesprochen. SQLite-Rechnungsfixtures verwenden den
bestehenden ausdrücklich synthetischen Aussteller; die PostgreSQL-Prüfung
finalisiert echte Testrechnungen über den produktiven Rollen- und API-Pfad.

Vorherige fehlgeschlagene Läufe bleiben unter `work/verification/euer-*`
erhalten: zunächst noch fehlende Modulregistrierung, danach noch nicht
integrierter gemeinsamer Geldnachweis-Guard; beim ersten erweiterten Restoretest
war die eigene Testverbindung noch offen. Es wurden keine fremden Verbindungen
beendet und keine Schutzbedingungen abgeschaltet. Der korrigierte Test schließt
seine eigene Verbindung vor dem echten Restore.

## Fachliche Sollwerte und Quellenabdeckung

| Regel / amtliche Grundlage | Geprüftes Verhalten |
| --- | --- |
| S01/S02/S08: EÜR enthält tatsächliche Umsatzsteuer-Geldwirkung | Eingang119,00 =100,00 Erlös +19,00 vereinnahmte USt; Auszahlung59,50 =50,00 Aufwand +9,50 bezahlte Vorsteuer; vor FA-Zahlung59,50 Überschuss, nach echter FA-Zahlung9,50 genau50,00. Keine Netto-Projektkalkulation als EÜR ausgegeben. |
| S04/S05: Ist-Versteuerung | Exakte vorhandene C1/C2/R1/R2-Steuercents, Umsatzsteuerperiode aus dem bestätigten CashEvent; kein pauschales Herausrechnen von19 % aus unbekannten Bruttowerten. |
| S06/S07: Vorsteuer unabhängig von späterem Abfluss | Leistung/Rechnung15.12.2026 mit9,50 Vorsteuer; Auszahlung20.01.2027 erzeugt erst2027 die59,50 EÜR-Ausgabe, keine zweite Vorsteuer. Vollständig bezahlte abziehbare Vorsteuer muss die bestätigte Originalberechtigung exakt erreichen. |
| S02/S03: Zehn-Tage-Regel | Zahlung08.01.2027, fällig10.01.2027, wiederkehrend und wirtschaftlich2026: EÜR31.12.2026. Septemberfälligkeit, Zahlung11.01. oder fehlende Wiederkehr werden abgewiesen. |
| S09/S10: private und nicht abziehbare Anteile | Quelle59,50:25,00 betriebliches Netto,20,00 abziehbares Netto,4,75 abziehbare Steuer;29,75 privat und5,00 betrieblich nicht abziehbar bleiben sichtbar. Abziehbare Ausgabe24,75; alle Geldcents bleiben erhalten. |
| S07/S13: lineare AfA | Neue belegte Basis100,00, Nutzung abNovember2026,24 Monate:8,33 /50,00 /41,67, Schlussbuchwert0,00. Nur19,00 bezahlte abziehbare Vorsteuer werden beim Erwerb sofort ausgegeben; keine zweite100,00-Nettoausgabe. |
| S14/S15: Rückzahlung und Erfassungskorrektur sind unterscheidbar | Echte gemischte C1/R1/C2/R2-Rückzahlung führt119,00−26,44 =92,56 EÜR-Einnahme und14,77 Ist-USt. Die vier alten Journale bleiben bytegleich. Erfassungskorrektur erzeugt exakte Gegenbuchung und Ersatz; kein neuer Bankvorgang. |
| S15/S16: Geschichte, Sperre und Berichtigung | Eintrag, Quittung und Audit atomar; SQL-UPDATE/DELETE/REPLACE werden blockiert. Gesperrte EÜR-/USt-/Cash-Periode verhindert Korrektur. Begründete Wiederöffnung ist eigenes Ereignis. Neue Prüfung unveränderter Geldbeträge kann nach ausdrücklichen Gegenbuchungen neu eingeordnet werden. |
| S11: Kapital-/Steuergeldbewegungen sind eigene Quellen | Sonderbewegungen teilen Geldkonten und Originalidentität mit vorhandenen CashEvents. Dieselbe NFKC-normalisierte Konto-/Nachweis-ID unter anderem Original wird abgewiesen. Zahlungsnachweise erzeugen keine angeblich offene Lieferantenverbindlichkeit. |
| S17: keine geratenen Konten oder Exportversprechen | Nutzer bestätigt vierstellige SKR04-Zuordnungen samt Grund/Prüfreferenz. Eigenes CSV-/JSON-Prüfpaket mit Journal-/Quellenhashes; keine DATEV-Zertifizierung und keine ungeprüften amtlichen2026-Formularzeilen. |

Die Tabelle nennt geprüfte Regeln, keine vollständige Gesetzesabnahme. Insbesondere
die amtliche2026-Formularstruktur konnte wegen der dokumentierten Abrufprobleme
nicht verifiziert werden; das Produkt exportiert daher eigene Kategorien.

## Integrität, Rechte und tatsächlicher Wiederanlauf

Die PostgreSQL-Abnahme benutzt getrennte Migrations- und eingeschränkte
Runtime-Rollen. Zwei tatsächliche Runtime-Verbindungen bestätigen denselben
Request gleichzeitig: genau ein Journalereignis und eine Quittung entstehen.
Verlorene Antwort und Prozessneustart liefern denselben früheren Eintrag.
Ein sicher nicht angenommener veralteter Request erhält den ausdrücklichen
409-Marker; Rechtefehler bleiben hinsichtlich des früheren Mutationsstatus offen.

Der Migrationsfall startet mit tatsächlich finalisierter Rechnung, archivierten
Originalen, Zahlung, CashEvent und C1-Aufteilung unter einer Registry ohne EÜR.
Die additive Migration läuft zweimal. Fingerprints aller alten Tabellen außer
dem erwarteten neuen Migrationseintrag bleiben gleich. Es wird anschließend
gegen die eingeschränkte Runtime eine EÜR-Buchung samt Prüfpaket erstellt.

Echter Dump und Restore erhalten dieses Journal und den unveränderten Export.
Der Finanzhorizont enthält Schema8 mit eigener EÜR-Tabellenzählung/Prüfsumme;
die Wiederherstellungsfreigabe verlangt Berichtsschema9. Vor unabhängiger
Betreiberfreigabe bleibt auch ein alter erfolgreicher Confirm-Replay gesperrt.
Ein geänderter EÜR-Horizonthash wird abgewiesen. Nach gültigem Abgleich sind
ursprüngliche Antwort und Prüfpaket unverändert wieder verfügbar.

Frische Buchhaltungs-/Finanzrechte werden vor Journal, Quellen, Export und Replay
geprüft. Ein sichtbares Duplikat eines privaten Originals verrät dessen frühere
private Sonderzahlungsbindung nicht. Ein später abgelehntes oder geändertes
Original bleibt als Klärungsfall sichtbar; bestätigte historische Summen werden
nicht heimlich überschrieben. Ohne bestätigten Buchführungsbeginn oder bei nur
teilweise gedecktem Jahr wird kein vollständiger Jahreswert behauptet.

## Ausdrückliche verbleibende Grenzen

* Abschlags-/kumulative/Schlussrechnungskomponenten sind noch nicht durch die
  bestehende dokumentarische Quellenfamilie abgedeckt. Der konkrete nächste
  Arbeitsschritt steht in [Kettenanalyse](CRM_ERP_EUER_KETTEN_ANALYSE.md).
* Keine automatische Reverse-Charge-/Auslands-/steuerfreie Erlösbehandlung,
  §15a-Berichtigung, besondere Privatwertabgabe, Teilanzahlungs-Vorsteuer,
  langfristige Vorauszahlung oder Schuldzinsenbegrenzung.
* AfA umfasst neue ausdrücklich linear gewählte Anlagen mit belegter Basis und
  Nutzungsdauer. Keine historischen Eröffnungswerte, GWG-Wahlrechtsautomatik,
  degressive/Sonder-AfA oder Veräußerungsrechnung.
* Keine automatische Lohnsteuer-/Sozialversicherungsabrechnung und keine
  Übertragung von Payroll-Ergebnissen als vermeintlich tatsächliche Zahlung.
* Einzelne Zahlungsnachweise ersetzen keinen Bank-CSV-Import. Ein Anfangssaldo,
  Bankabgleich und Vollständigkeit realer Unterlagen werden nicht erfunden.
* Ein vollständiger Wert für **erfasste unterstützte Quellen** ist keine Abnahme
  sämtlicher Steuerfälle oder eines echten Unternehmensjahres. Dessen Prüfaussagen
  bleiben ausdrücklich zu bestätigen; Behörden- und Beraterübermittlung erfolgen
  nicht automatisch.

Die beiden Clients werden separat geprüft. Ihre Prüfergebnisse gehören in den
gemeinsamen Projektfortschritt; dieser Backendbericht übernimmt keine noch
laufenden Client- oder Gesamtpaketprüfungen als eigenen Nachweis.
