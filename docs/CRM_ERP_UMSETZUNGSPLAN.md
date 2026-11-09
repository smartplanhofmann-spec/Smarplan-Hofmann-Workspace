# CRM/ERP – laufender Umsetzungsplan

Der aktuelle [Projekt-Integrationsstand 0.13.0](CRM_ERP_PROJEKTBETRIEB_INTEGRATION_2026-11-04.md)
verbindet Kunden, Belege, Material, Zeiten und Navigation mit eigenen Prüfnachweisen.
Das [Windowsprogramm 0.13.0](CRM_ERP_PROJEKT_BUILD_FREIGABE_2026-11-04.md) ist
tatsächlich gebaut und geprüft. Ein unsignierter iPhone-Gerätebuild ist ebenfalls erfolgreich; Signierung,
Serverabgleich und Geräteabnahme bleiben als Auslieferungsschritte offen.

**Erneute Gesamtbeauftragung vom 08.11.2026:** Die gesamte vereinbarte Software
fertigstellen. Projektbetrieb und Auslieferung bleiben zuerst zu schließen;
die bisher zurückgestellten Buchhaltungs-/Lohnaufgaben bleiben anschließend
aktive Codearbeit im Gesamtumfang. Der [zentrale Arbeitsstand](CRM_ERP_ARBEITSSTAND.md)
verbindet diese Fortsetzung mit dem bisherigen Projektphasenplan. Historische
Lohn-/Buchhaltungsnachweise bleiben erhalten.

Stand: 09.11.2026. Maßgeblich bleiben das unveränderte
[Gesamtziel](../CRM_ERP_Gesamtziel.txt) und die
[Anforderungsmatrix](CRM_ERP_ANFORDERUNGEN.md). Projekt:
`/workspace/Smarplan-Hofmann-Workspace`, lokaler Branch `codex/finish-20261108`,
Veröffentlichungsziel `codex/testupdate-0.7-projects-20261104`.

## Verbindlicher fachlicher Rahmen

Einzelunternehmen mit EÜR, Regelbesteuerung, Ist-Versteuerung, 19 %
Standard-Umsatzsteuer, SKR04 und Nettopreise. Personalumfang: reguläre
Beschäftigte und Minijobs. Gültigkeitsbeginn, echte Personen-/Steuerdaten und
Anfangsbestände bleiben ausdrückliche Eingaben. Einzelne geprüfte Lohnfälle
ersetzen keine vollständige Fachabnahme aller Beschäftigungsfälle.

Vorhandene Flutter-/Browseroberflächen, Python-Kern, PostgreSQL-Onlinedienst
und begrenzte lokale SQLite-Variante werden weiterentwickelt. Kanonische
Kunden-/Projektkennungen, unterschriebene Archive, Quittungen und bestehende
Daten bleiben erhalten. Die ursprüngliche Bestandsaufnahme und früheren
Entwicklungsschritte stehen im Fortschrittsbericht, nicht als aktuelle
Restarbeiten in diesem Plan.

## Bereits belegte Entwicklungsabschnitte

| Abschnitt | Abgegrenztes Ergebnis | Aktueller Nachweis |
| --- | --- | --- |
| Bestand/Unternehmensgrundlage | Vorhandenen Quellstand konsolidiert, Bedarf/Module, Sichtbarkeit/Aktivierung/Rechte, feste Instanzbindung | Bestandsaufnahme, Modul-/Instanzdokumentation |
| Kundenauftrag | Anfrage/Katalog/Angebot/Portalannahme/kanonischer Auftrag, Offline-Serviceprotokoll, Rechnung und Zahlung | `CRM_ERP_KUNDENAUFTRAG.md`, `CRM_ERP_OFFLINE_SERVICEBERICHTE.md` |
| Projektkosten und Übersicht | Geprüfte Originalkosten, Zeit/Material, Budget/Nachträge, getrennte Erlöse/Zahlungen, nachvollziehbare Kennzahlen | `CRM_ERP_PROJEKTWIRTSCHAFTLICHKEIT_CLIENTS.md`, `CRM_ERP_UNTERNEHMENSUEBERSICHT.md` |
| Einkauf/Geräte/Inventur | Teil-/Restlieferung, Original-Lieferschein, Entnahme/Geräteherkunft, Wartung, Zählung und Bestandskorrektur | `CRM_ERP_EINKAUF.md`, `CRM_ERP_GERAETEHERKUNFT.md`, `CRM_ERP_INVENTUR.md` |
| Kundenbereich und Vertrieb | Isolierte freigegebene Informationen/Originale/Uploads; Chancen, Aktivitäten, Wiedervorlagen und Projekt-/Angebotsübernahme | `CRM_ERP_KUNDENARBEITSBEREICH.md`, `CRM_ERP_VERTRIEB.md` |
| Gemeinsamer Kommunikationsverlauf | Aus sechs vorhandenen Fachquellen am kanonischen Kunden/Projekt, mit Quellrechten, Original/Korrektur, Suche, Filtern und gebundenen Verlaufsseiten in Browser/App | [Kommunikationsverlauf](CRM_ERP_KOMMUNIKATIONSVERLAUF.md), tatsächliche PG-/MFA-/Restore- und Browserprüfung |
| EÜR | Quellen-/Geldjournal, exakte Komponenten, Erstattungen, steuerliche Einordnung, AfA, Gegenbuchung, Perioden und Jahresprüfpaket; Abschlags-/Schlussketten | `CRM_ERP_EUER_WORKFLOW_PRUEFUNG.md`, `CRM_ERP_EUER_KETTEN_ANALYSE.md` |
| Unterjährige Jahresvorträge und V2-Archiv | Belegte alte Journal-/Steuerwerte, neue Restzahlungen und beide Clients im Integrationsstand integriert; V1-Originale erhalten, gemeinsamer Restore 15/16 | [Root-Gesamtprüfung](CRM_ERP_JAHRESVORTRAG_GESAMTPRUEFUNG_2026-11-04.md), [121 unterschiedliche Finanz-PG-Fälle](CRM_ERP_JAHRESVORTRAG_FINANZ_PG_2026-11-04.md) |
| Personal/Lohn | Private Originalakten, Auslagen/Fremdfreigabe/Erstattung, Monatsvorbereitung, begrenzte 2026-Lohnfälle, Lohnkonten/Zahlungsteile/Vorträge/Jahresausgabe | `CRM_ERP_PERSONAL_WORKFLOW.md`, `CRM_ERP_LOHN_RECHENWERK_2026.md`, `CRM_ERP_LOHN_CLIENTS.md` |
| Assistent und Sprache | Berechtigte Quellen, belegbare Antworten/Entwürfe, Regeln/Freigaben, native Versandgates, ausdrücklich gestartete Sprachentwürfe | `CRM_ERP_ASSISTENT.md`, `CRM_ERP_ASSISTENT_CLIENTS.md`, `CRM_ERP_SPRACHE.md` |
| Migration/Übergabe | Kontrollierter neutraler Dateiimport mit Originalen/Abgleich; portables Unternehmensarchiv mit eigenem Prüfer und expliziter Übergabeprüfung | `CRM_ERP_DATEIMIGRATION.md`, `CRM_ERP_DATEIIMPORT.md`, `CRM_ERP_UNTERNEHMENSEXPORT.md` |
| Anpassbarkeit | Fünf typisierte Zusatzfeldarten für Kontakte/Projekte/Geräte, Pflichtangaben und unveränderte Historie | `CRM_ERP_ZUSATZFELDER.md` |
| Datenschutzfälle | Identität/Quellenprüfung, begrenzter Export, kanonische Berichtigung und Bereinigung mit unabhängigem Restore-Checkpoint | `CRM_ERP_DATENSCHUTZFAELLE.md` |
| Lohnzahlungen/EÜR | Belegte tatsächliche Zahlungsteile und Abführungen; private Originale und aggregierte Finanzquelle | `CRM_ERP_LOHNZAHLUNGEN_EUER_CLIENTS.md` |
| Bankabgleich | Originalauszüge, bestehende Geldbewegungen, Teilzuordnung, Korrekturen, unveränderliche Berichte und EÜR-Periodenbindung in beiden Clients | `CRM_ERP_BANKABGLEICH_CLIENTS.md`, `CRM_ERP_BANK_EUER_INTEGRATION_PRUEFUNG.md` |
| Betriebsmittel | Kanonische Ressourcen, Prüfnachweise, Ausgabe/Rückgabe, Nutzungssperren und historische Korrektur | `CRM_ERP_BETRIEBSMITTEL_CLIENTS.md` |
| Midijob 2026 | Explizite belegte Prognose, getrennte Bemessungsgrundlagen, PV-Korrektur, historische Lohnkonten und Zahlungskette | `CRM_ERP_LOHN_MIDIJOB_2026.md`, `CRM_ERP_LOHN_MIDIJOB_CLIENTS.md` |
| Kundenservice | Anfrage/Reklamation/Wartung, Disposition, signierter Bericht, Lösung, Abschluss und Wiedereröffnung | `CRM_ERP_SERVICE_CLIENTS.md` |
| Browserbedienung | Gerenderte WCAG-Stichproben, korrigierte Kontraste, Tastaturdialog und mobile Ansichten | `CRM_ERP_BEDIENBARKEIT.md` |
| Sicherheit/Quellen | Aktualisierte Python-Pins, aktuelle Meldungsabgleiche, reproduzierbares Quellinventar, Pflege-/Vorfallsablauf und aktuelle fachliche Nachweisliste | `CRM_ERP_ABHAENGIGKEITEN_SICHERHEIT.md`, `CRM_ERP_KONFORMITAET_QUELLEN.md` |

Testzahlen, konkrete Grenzen und laufende Integration stehen im
[Integrationsstand](CRM_ERP_INTEGRATIONSSTAND_2026-11-03.md). Keine Tabellenzeile
ist allein eine Produktivfreigabe oder eine abgeschlossene Gesamtabnahme A–G.

Die native Kataloghistorie und Originalübernahme sind nach dem gemeinsamen
Anfangssaldo-/Browserstand fertig integriert: 1.163 Fluttertests und Analyse
ohne Befund; [aktueller Nachweis](CRM_ERP_KATALOG_NATIVE_2026-11-04.md).

## Aktive Arbeitspakete

1. Wiederhergestellten Gesamtstand und Originalziel sichern; umgesetzt.
2. Offene CI-/Browserregressionen der ausdrücklichen Projekt-/Quellenauswahl
   schließen; Assistent, Zusatzfelder und Kundenbereich gezielt nachgeprüft.
   Der veröffentlichte Produktstand f747311 besteht inzwischen alle acht
   Development-Jobs und den unsignierten iPhone-Build 171.
3. Parser-Kompatibilität vor Wartung und Datenbankumstellung prüfen; im neuen
   Operatorcode umgesetzt und mit 87 Fällen nachgeprüft. Liveinstallation separat.
4. Aktuellen Auslieferungs-/Gerätestand abgleichen. Serverantwort und Verfügbarkeit
   des Apple-Developer-Kontos sind angefragt; keine Schlüssel im Chat.
   Das Windows-Online-Archiv auf f747311 ist tatsächlich heruntergeladen,
   sein veröffentlichter Digest und alle 248 Dateihashes sind geprüft.
   Der gemeinsame Kommunikationsverlauf ist mit abschließenden Kunden-/
   Filterkorrekturen als 2598c96 veröffentlicht. 1.632 Appfälle, 19 gezielte
   PDF-/HTTP-/Ladefälle, 874 Browsermodule und echte MFA-/PG-/Restorewege
   sind getrennt belegt; alle acht CI-Jobs und iPhone-Build173 bestehen
   [inzwischen](evidence/payroll-factor-periods-2026-11-09/ci-baseline.json).
5. Weitere konkret benannte Lohn-/EÜR- und Länder-/Regelfälle additiv entwickeln.
   Der [belegte reguläre Faktor-Teilmonat](CRM_ERP_LOHN_FAKTOR_TEILMONATE_2026.md)
   ist als neue v9-Regel mit beiden Clients und tatsächlicher PG-/Restore-/
   Bank-/EÜR-Kette integriert, ohne Änderung der bisherigen Rechenkerne.
   Die [alte v8-Faktorhistorie](CRM_ERP_LOHN_PLATTFORMHISTORIE_2026.md)
   besitzt jetzt einen eng begrenzten exakten Windows-/Linux-Abgleich; fünf
   Fachketten-, zwei echte PG-/Restorefälle und alle 649 Python-Lohnfälle bestehen.
   Als 3025747 veröffentlicht; eigene Remote-CI ausstehend. Weitere rohe Dateihash-Nachweise
   bei Einmalbezügen und Reisen vollständig prüfen. Fälle mit Ansprüchen, Reisen, Übergangsbereich
   oder Einmalbezügen bleiben in ihren eigenen noch auszuarbeitenden Zweigen.
   Der [reguläre Faktor-Vollmonat](CRM_ERP_LOHN_FAKTOR_2026.md) ist jetzt mit
   beiden Clients, tatsächlichem PG-Restore, Zahlungen/EÜR und unabhängigen
   XML-Werten integriert. Individuelle Minijobsteuer und weitere Versicherungs-/
   Faktor-Spezialfälle bleiben Codearbeit. Historische PAP-Kerne sind bytegleich;
   keine Berechnung aus unvollständigen Quellen erfinden.
6. Durchgängige Abnahmen A–G und vollständige Lieferung gemäß Anforderungsmatrix
   verbinden. Fehlender Code bleibt Codearbeit; externe Freigaben bleiben
   zusätzliche Nachweise. [Zentraler Arbeitsstand](CRM_ERP_ARBEITSSTAND.md).

## Bisheriger Projektphasenblock

1. Kunden-/Projektanlage und vollständige Rechnungsanschrift in beiden Clients.
2. Durchgängige Angebote, Aufträge und tatsächliche Rechnungsausstellung.
3. Stunden mit Freigabe/Korrektur sowie zuverlässiger App-Offlinesynchronisation.
4. Sichere Projektregister, Planbearbeitung und Rücknavigation.
5. Gemeinsame Regressionen und aktuelle Windows-/iPhone-Builds mit Serverabgleich.

Die Quellkorrekturen der Pakete 1–4 sind im Projektstand 0.13.0 integriert und
automatisch geprüft; ihre gemeinsame Geräteabnahme bleibt Bestandteil von 5.
Der Windows-Teil von 5 ist mit tatsächlichen lokalen und Online-Releasepaketen,
1.593 Windows-Appfällen, drei PDF-Engine-Fällen und 79 Backendfällen ohne Skip
belegt. Die korrigierte macOS-Prüfung und der unsignierte iPhone-Build 168
sind ebenfalls erfolgreich. Offen bleiben die installierbare signierte Verteilung,
der nachgewiesene Serverabgleich und die gemeinsame Gerätefolge. [Nur lesende Serverbefehle und Geräteprotokoll](CRM_ERP_KUNDENTEST_PROJEKTBETRIEB_0_13.md)
sind vorbereitet. Der Serverstand A93 wurde inzwischen tatsächlich bestätigt;
die spätere Browseranpassung auf 5880f88 und neuere Änderungen sind ohne
weitere Nutzerausgabe noch nicht als installiert nachgewiesen.

Prüffälle, konkrete Lücken und Grenzen stehen im
[aktuellen Phasenplan](CRM_ERP_PROJEKTPHASE_2026-11-04.md).

## Bisherige Reihenfolge – durch die Projektphase zurückgestellt

1. **Weitere Einmalbezugsfälle fertigstellen.** Die private Jahresquellen-API
   besitzt Browser- und App-Formulare. Source4/v6 verbindet einen belegten
   Anspruch mit laufender v5-Rechnung, Steuerprognose, SV-Jahresbasis,
   Anspruchsverbrauch, Lohnlauf, Lohnkonto und tatsächlich belegter Zahlung.
   PostgreSQL-/Restore-, Client- und gemeinsame Prüfungen bestehen. Auch der
   reduzierte Mitarbeiterbeleg und die Übernahme bereits gezahlter Boni in
   spätere Jahresbasen sind integriert. Mehrere Boni desselben Monats und
   unterschiedliche Zahlungstage werden über additive V7-/Source5-Verträge
   behandelt. Der begrenzte vollständige Originalbonus mit getrennten
   tatsächlichen Transfers ist [gemeinsam geprüft](CRM_ERP_SOURCE5_GESAMTPRUEFUNG_2026-11-04.md);
   die tatsächliche Mehrfachsteuerberechnung wird separat weiterentwickelt.
   Ungeklärte Steuergruppen liefern ausdrücklich kein Endnetto.
2. **Unterbrechungen und Nullnetto vervollständigen.** Das belegte U-Merkmal und
   ein Zahlungsnachweis ohne geschuldete Nettozahlung sind implementiert und
   gezielt geprüft. Tatsächliche Leistungsbeträge, Jahresüberträge und weitere
   Versicherungsfälle bleiben im [Lückenplan](CRM_ERP_LOHN_LUECKENPLAN_2026.md).
   Eine leere Nettozahlung erzeugt keinen Geldfluss; geschuldete Abführungen
   bleiben gesondert nachzuweisen.
3. **Gemeinsame Integration weiter absichern.** Auf `c7dbab0` sind Anfangssalden
   in beiden Clients sowie Katalogoriginale/Browserimport zusammengeführt.
   Die neue vollständige Prüfung besteht 1.565 Backendtests bei einer
   plattformspezifischen Auslassung, 522 Node- und 1.118 Fluttertests,
   vollständige Flutter-Analyse und 16 Paketprüfungen. Tatsächliche gemeinsame
   PostgreSQL-/Restore- und Browserabläufe sind geprüft; siehe
   [Gesamtnachweis](CRM_ERP_ANFANGSSALDEN_KATALOG_GESAMTPRUEFUNG_2026-11-04.md).
   Source5 ist inzwischen mit beiden Clients auf `4c2f008` zusammengeführt:
   1.626 Backendfälle bei einem Windows-Skip, 555 Node- und 1.208 Flutterfälle
   sowie 16 Paketprüfungen bestehen. Die historische lineare Anlagenübernahme
   ist anschließend auf `8858db4` mit beiden Clients, 107 PostgreSQL-Fällen und
   zusätzlichem gemeinsamem Restore geprüft. Preis-v2 und der Assistenten-Kostenfix
   sind anschließend auf `80e051a` mit 1.737 Backendfällen bei einem Windows-Skip,
   1.312 App- und 610 Browsermodulfällen sowie vier PostgreSQL-Fällen geprüft.
4. **Verbleibende Gesamtanforderungen am Code prüfen und schließen.** Die
   Abnahmefälle A–G bleiben der Maßstab. Parallel zur Lohnintegration werden
   konkrete Lücken der übrigen Module mit tatsächlichem Code und vorhandenen
   Tests abgeglichen; historische Planpunkte allein gelten nicht als Beleg
   fehlender Funktionen. Die [Gegenprüfung vom 04.11.2026](CRM_ERP_GESAMTZIEL_GEGENPRUEFUNG_2026-11-04.md)
   priorisiert belegte Finanzübernahme, Katalogpreisgültigkeit/Browserimport
   und unternehmensweite Ereignisregeln. Anfangssalden und Katalogoriginale
   sind unter `c7dbab0` und `4c2f008` integriert. Historische lineare Anlagen
   sind [gemeinsam geprüft](CRM_ERP_ANLAGEN_GESAMTPRUEFUNG_2026-11-04.md).
   Die zeitgebundenen Preise sind [gemeinsam geprüft](CRM_ERP_KATALOG_V2_GESAMTPRUEFUNG_2026-11-04.md). Belegte
   historische offene Posten sind mit ihren tatsächlichen Zahlungswegen
   zu EÜR, Bankabgleich und Liquidität [gemeinsam geprüft](CRM_ERP_ALTPOSTEN_GESAMTPRUEFUNG_2026-11-04.md). Die unternehmensweiten Ereignisregeln sind mit beiden Clients,
   Instanzworker und gemeinsamem Restore [geprüft](CRM_ERP_EREIGNISSE_GESAMTPRUEFUNG_2026-11-04.md).
   Die gemeinsame Altpostenintegration erhält diese Regeln und die datierten
   Preise: 1.816 Backendfälle bei einem Windows-Skip, 1.434 App-, 713 Node- und
   109 eindeutige PostgreSQLfälle bestehen. Das ergänzende Original-/Journalpaket
   ist anschließend [gemeinsam geprüft](CRM_ERP_JAHRESPAKET_GESAMTPRUEFUNG_2026-11-04.md):
   84 betroffene Backend-, 401 Buchhaltungs-App-, 762 Node- und drei PG-Fälle.
   Unterjährige Jahresvorträge und der V2-Archivanschluss sind jetzt mit beiden
   Clients im [Integrationsstand auf `2e2ed5c`](CRM_ERP_JAHRESVORTRAG_GESAMTPRUEFUNG_2026-11-04.md)
   technisch integriert: 1.899 Backendfälle bei einem Windows-Skip, 1.542 App-,
   842 Node- und 16 Paketfälle bestehen; Analyse ohne Befund. 121 unterschiedliche
   Finanz-PG-Fälle sind nach vier gezielten Testfixture-Nachprüfungen bestanden.
   Fünf tatsächliche Browserabläufe und der zusätzliche mobile CSS-Nachlauf
   bestehen. Endgültige Quellen und Prüfläufe sind im Gesamtnachweis gebunden.
   Finanzhorizont 15/Bericht 16, 144 Backend- und 209 Betreiberpfade.
5. **Parallele Arbeitsstände erst nach eigenen Nachweisen integrieren.**
   Die [native Assistenten-/Sprachkorrektur und technischen Isolationsnachweise](CRM_ERP_UNTERNEHMENSISOLATION_GESAMTPRUEFUNG_2026-11-04.md)
   sind integriert; produktive Host- und Sicherheitsabnahme bleiben offen.
   Die [native Service-/Betriebsmittelkorrektur](CRM_ERP_SERVICE_BETRIEBSMITTEL_GESAMTPRUEFUNG_2026-11-04.md)
   ist ebenfalls mit 35 Fällen und Analyse integriert. Private Lohnvergleichs-,
   SV-Gruppen- und Quellenpakete liegen noch getrennt vor. Ihre Integration und
   weitere tatsächliche Fach-/Betriebsnachweise bleiben spätere Schritte;
   die aktuelle Projektphase hat Vorrang.

Die v5-Zusammenrechnung mehrerer belegter Entgelt-/SV-Abschnitte mit
Anspruchsbausteinen und Reise-Lohnübergabe sowie der eigene v5-Mitarbeiterbeleg
sind inzwischen geprüft. Reise-v3 ergänzt Mischreisen und Boden-Zeitzonen;
die erhaltenen alten Regelversionen bleiben reproduzierbar. Weitere benannte
Lohn-/Steuerfälle bleiben Entwicklungsarbeit und werden nicht wegen fehlenden
Codes zu externen Hindernissen umgedeutet.

## Noch offener Zielumfang

Die Anforderungsstatus bleiben unverändert: 40 von 62 Zeilen implementiert oder
getestet, fünf teilweise, elf offen und sechs extern blockiert. 64,5 % (etwa
65 %) ist lediglich die ungewichtete Zeilenzählung, keine Fertigstellungs- oder
Zeitquote. Gesamtbuchhaltung und alle Abnahmen A–G bleiben offen.

Nach dem Abschluss der Projektphase bleiben die konkreten Steuer-/Lohnfälle,
vollständige menschliche und gerätebezogene Bedienprüfung und die
vollständigen technischen Abnahmen A–G abgearbeitet. Dabei werden vorhandene
Teilnachweise verbunden und Lücken gezielt ergänzt. Neue Anbieter-/Dateiformate
werden nur mit verifiziertem Vertrag implementiert; ein neutraler Import gilt
nicht als Herstellerabnahme.

Die externen Nachweise umfassen reale Windows-/iPhone-Geräte und Verteilung,
betriebliche Anfangsdaten/Freigaben, unabhängige Sicherheitsprüfung, fachliche
Lohn-/Steuerprüfung und notwendige Meldezulassungen sowie tatsächliche ausgewählte
Providerzugänge. Fehlender unabhängiger Code wird nicht als extern blockiert
bezeichnet. Unabhängige Entwicklung läuft weiter.

## Arbeitsregeln und Abschlusskriterium

Aktuelle Betriebsfortsetzung vom 05.11.2026: Der Nutzer hat Parserreparatur
und [kontrollierten Updateabschluss](CRM_ERP_SERVERUPDATE_ABSCHLUSS_0_13.md)
auf dem tatsächlichen Server ausgeführt. Sandbox, drei Dienste, Prozess-/
Datenbankbindung und aktiver Sicherungstimer sind bestätigt; der offene
Aktivierungsmarker ist entfernt. Als nächster Schritt folgt die vorbereitete
Browser-/Windows-Kundenstrecke. Die allgemeine
Parser-Kompatibilität vor zukünftigen API-Updates wird anschließend im
Operatorablauf abgesichert. Signierte iPhone-Verteilung und tatsächliche
Geräteabnahmen bleiben offen; Lohn und Gesamtbuchhaltung bleiben zurückgestellt.

Bedienrückmeldung und Anpassungsauftrag vom 06.11.2026: Die
[Browser-Projektauswahl](CRM_ERP_BROWSER_PROJEKTAUSWAHL_2026-11-06.md) ist im
Quellstand bereichsabhängig umgesetzt. Allgemeine Bereiche entfernen auch
den bisherigen Projektkontext; die Projektmappe und echte Filter sind
unterschiedlich beschriftet. Globale und projektbezogene Rechte bleiben
getrennt, einschließlich ausgeblendeter Bereiche. Die Prüfung umfasst echte
Browser-/MFA-/HTTP-Abläufe und die serverseitige Ablehnung einer gesperrten
Projektzeit. Auslieferung auf den laufenden Server und die tatsächliche
Bedienbestätigung des Nutzers bleiben separat nachzuweisen.

Neue Module werden additiv migriert. Historische Schema-/Quittungsformate bleiben
prüfbar; aktuelle Restores verlangen den vollständigen installierten Umfang.
Fehlende Bestände oder ungeprüfte Quellen werden nicht als Null, Gewinn oder
Erfolg angezeigt. Tests verwenden synthetische Daten und entbehrliche lokale
Dienste. Echte Zahlungen, Nachrichten, Bestellungen, Meldungen, produktive
Migrationen, Remote-Push und öffentliche Bereitstellung werden dadurch nicht
automatisch autorisiert.

Anforderungen, Entscheidungen, Quelländerungen und tatsächlich ausgeführte
Prüfungen werden im Repository dokumentiert. Fertigstellung setzt den benannten
Funktionsumfang, durchgängige Abnahmen, Installation/Betrieb und erforderliche
externe Nachweise voraus. Es wird kein Fertigstellungsprozentsatz aus der Zahl
der Dateien oder Einzeltests abgeleitet.
