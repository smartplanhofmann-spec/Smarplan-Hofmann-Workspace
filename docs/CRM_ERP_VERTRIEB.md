# Verkaufschancen und Vertriebspipeline

Stand: 03.11.2026. Umsetzung des Chancen-/Aktivitätsablaufs aus Gesamtziel
Abschnitt 5. Bestehende Kontakte, Ansprechpartner, Anfragen, Projekte, Kataloge
und Belege bleiben die kanonischen Datensätze.

## Bedienung und fachlicher Ablauf

Die Kontaktübersicht öffnet **Vertriebspipeline**. Jeder Kontakt öffnet seine
**Verkaufschancen**; im Browser lässt sich eine Anfrage direkt als Quelle für
eine neue Chance wählen. Die native Anlage bietet denselben Anfragebezug in
der Kundenauswahl.

1. Bestehenden Kunden/Interessenten und optional eine Anfrage auswählen. Eine
   Chance enthält Titel, Ansprechpartner, Verantwortlichen, Notizen,
   Netto-Erwartungswert in EUR, ausdrücklich angegebene Wahrscheinlichkeit,
   Wiedervorlage und erwarteten Abschlusstermin. Der Kunde muss aktiv sein;
   Ansprechpartner müssen zu diesem Kontakt gehören.
2. Phasen sind Neu, Qualifiziert, Angebot, Verhandlung, Gewonnen und Verloren.
   Gewonnen benötigt 100 %, verloren 0 % und jeweils einen Abschlussgrund.
   Die Phase ist eine dokumentierte Vertriebsentscheidung. Sie behauptet
   weder eine Portalannahme noch Zahlung oder Umsatzbuchung.
3. Die Pipeline zeigt offene Chancen, ihre erwarteten Nettowerte, gewichtete
   Prognose und überfällige Wiedervorlagen. Gewonnene/verlorene Chancen zählen
   nicht mehr zu offenen Prognosen. Pro Chance wird der Erwartungswert mit
   ihrer Wahrscheinlichkeit multipliziert und auf Cent gerundet; danach
   werden ausschließlich die sichtbaren gefilterten Chancen summiert.
4. Notizen, Telefonate, dokumentierte E-Mails und Besprechungen bilden einen
   separaten Aktivitätsverlauf. Eine Korrektur ergänzt einen Nachfolgeeintrag
   mit Begründung und erhält das Original. Eine dokumentierte E-Mail löst
   keinen Versand aus. Zukünftige Termine gehören in die Wiedervorlage.
5. Eine ausdrückliche Projektübernahme bindet die aktuelle Chancenrevision
   und den Hash ihrer Kunden-/Anfragequelle. Eine bereits übernommene Anfrage
   verwendet ihr bestehendes Projekt. Eine offene Anfrage verwendet den
   bestehenden Konvertierungsweg; ohne Anfrage kann ein passendes vorhandenes
   Projekt gewählt oder ein neues kanonisches Projekt erstellt werden.
6. Das verknüpfte Projekt kann genau einen initialen Angebotsentwurf aus der
   Chance erhalten. Der Benutzer wählt aktuelle Artikel/Leistungen, Mengen,
   Titel und Gültigkeit. Preise, Steuersätze und Einheiten stammen aus den
   bestätigten Katalogrevisionen. Die vollständige Rechnungsanschrift stammt
   aus der bestehenden Kontaktkarte. Ein Vertriebs-Erwartungswert wird niemals
   in eine Angebotsposition umgedeutet.
7. Das Angebot wird anschließend im vorhandenen Belegeditor weiterbearbeitet.
   Angebotsannahme, Kundenportal und Auftragsübernahme folgen den bestehenden
   Fachabläufen. Die Chancenübernahme selbst finalisiert und versendet nichts.

Die native Oberfläche unterstützt die Auswahl mehrerer Katalogpositionen mit
jeweils eigener Menge. Im Browser können Positionen hinzugefügt und entfernt
werden. Desktop- und mobile Ansichten wurden geprüft; mobile Phasen und
Kontaktaktionen werden untereinander angeordnet.

## Konsistenz, Rechte und Wiederholung

- Der bestehende Kunden-/Anfragebezug einer Chance bleibt unverändert; eine
  Anfrage kann höchstens einer Chance zugeordnet sein. Jede Änderung erhält
  eine neue Fassung. Parallele Bearbeitung benötigt die aktuelle Revision.
- Projektanlage, Anfragekonvertierung, Übernahmeverknüpfung und Quittung werden
  gemeinsam bestätigt. Ein Abbruch rollt alle Teile zurück. Eine verlorene
  Antwort wird mit der ursprünglichen Vorgangs-ID wiederholt und erzeugt
  weder ein zweites Projekt noch ein zweites Angebot.
- Eine Chance benötigt aktuelle `contacts.read` beziehungsweise
  `contacts.write` sowie die vorhandenen Rechte auf ihren konkreten Kontakt,
  ihre Anfrage und ihre verknüpften Projekte. Die zuständige Person muss
  aktiv sein und den Kontakt lesen dürfen. Es werden keine neuen globalen
  Kontakt-/Anfragerechte aus dem Chancenbezug abgeleitet.
- Projektanlage bleibt entsprechend dem bestehenden Kern auf die
  Geschäftsführung mit `projects.manage` begrenzt. Angebote verlangen
  zusätzlich `finance.read`, `finance.write` und den aktiven Belegbereich.
  Pausen, Lesemodus und Rechteentzug werden serverseitig erneut geprüft.
- Offene Clientbefehle liegen ausschließlich in der angemeldeten Sitzung.
  Netzwerkfehler, Rechteentzug, unklare Konflikte und Überlastung verwerfen
  die ursprüngliche Anfrage nicht. Wiederholungen prüfen frische Rechte und
  die ursprüngliche Kunden-/Chancenidentität. Nur nachweislich nicht
  angenommene Konflikte dürfen den offenen Versuch auflösen.
- Die fünf Tabellen `business_sales_opportunities`, `business_sales_versions`,
  `business_sales_activities`, `business_sales_adoptions` und
  `business_sales_requests` sind nur ergänzbar. PostgreSQL-Laufzeitrechte und
  Datenbanktrigger schützen sie; die Integritätsprüfung verbindet Quittungen
  mit ihren tatsächlichen unveränderlichen Ergebniszeilen und prüft
  Übernahmequellen, Kunden-/Projekt-/Angebotsbindung sowie Korrekturketten.

Historische Kunden-/Ansprechpartnerstände und Notizen sind personenbezogene
Daten. Die Kontaktlöschprüfung nennt Verkaufschancen deshalb ausdrücklich als
Prüfbedarf, auch wenn noch kein Projekt besteht. Dieser Stand führt keine
automatische Löschung historischer Daten durch und behauptet keine vollständige
Anonymisierung. Export-/Aufbewahrungsverfahren müssen diese Datenarten erfassen.

## API und Nachweise

| API unter `/business/sales` | Funktion |
| --- | --- |
| `options?customer_id=…` | Aktuell erlaubte Kontakte, Ansprechpartner und Zuständigkeiten |
| `opportunities` GET/POST | Pipeline mit `q`, `stage`, `customer_id`; Chance anlegen/versionieren |
| `opportunities/{id}` | Aktueller Stand, frische Quellenprüfung und bestehende Verknüpfungen |
| `opportunities/{id}/history` | Unveränderliche Chancenfassungen |
| `opportunities/{id}/activities` GET/POST | Aktivitäten und begründete Korrekturen |
| `opportunities/{id}/project` POST | Genau eine bestätigte kanonische Projektverknüpfung |
| `opportunities/{id}/offer` POST | Genau ein initialer Angebotsentwurf aus Katalogpositionen |

| Prüfung | Ergebnis |
| --- | --- |
| Fachkern | 11/11 Tests in `backend/test_business_sales.py`: Prognose, Bindungen, Historie, Korrektur, Anfrage→Projekt→Angebot, Wiederholung, atomarer Abbruch, Rechte, Quellenänderung, Manipulation und Löschblockade |
| PostgreSQL mit echtem MFA/HTTP | 2/2 Tests in `backend/online/test_business_sales_pg.py`: vollständige Kette, zwei parallele Quittungsabrufe, Rechte, Runtime-/Migrator-Guards, Neustart und tatsächlicher Backup/Restore |
| Browser-Modultests | 5/5 in `web/office/tests/sales.test.mjs`: Centwerte, bewusste Abschlussentscheidung, Katalogpreise, frische Wiederholungsrechte und exakte Wiederholung nach Antwortverlust |
| Native Oberfläche | 6/6 in `app/test/business_sales_test.dart`: Prognose, tatsächliche Formularänderung, Rechteentzug während Antwortverlust, Lesemodus, verworfene verspätete Antworten und Öffnen des verknüpften Projekts ausschließlich aus der frisch autorisierten kanonischen Projektsammlung |
| Echter Chromium-Ablauf | Anfrage/Kunde/Ansprechpartner→Chance→Aktivität/Korrektur→Projekt trotz verlorener Antwort genau einmal→Katalogangebot→Fassungen; lesbare mobile Pipeline und echte Namespace-/PID-/Netzwerk-/Seccomp-Isolation |
| Flutter-Analyse | Ohne Befunde im geprüften Integrationsstand |

Logs liegen unter `work/verification/sales-{domain,pg,node,flutter-tests,browser}.log`,
Analyse unter `sales-flutter-analyze.log`. Der Browserlauf ist reproduzierbar mit
`SMARTPLAN_BROWSER_WORKFLOW=sales node web/office/tests/e2e.cjs`; synthetische
Screenshots und HTTP-Befehle liegen unter `work/verification/sales-browser/`.
Die ersten UI-Prüfungen fanden eine falsche Browser-Pending-Abfrage und zu enge
mobile Spalten; beide wurden korrigiert. Testfixture-Probleme mit Flutter-Timer-
Bereinigung und einem zu früh geprüften Dialog wurden ebenfalls behoben.

Es gab keine externen Nachrichten, Anbieteraufrufe oder produktive Migrationen.
Die Prüfungen ersetzen keine reale Windows-/iPhone- oder vollständige
CRM-/ERP-Abnahme. Vertriebserwartungen bleiben ausdrücklich von Finanzbuchungen
und tatsächlichen Auftrags-/Zahlungsnachweisen getrennt.
