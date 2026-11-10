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

Fortsetzung 10.11.: Der tatsächliche Windows-Pack-/Build-/Sicherungsnachlauf auf
d083ed4 besteht. Zwei zusätzliche veraltete bzw. mitternachtsabhängige Prüfungen
sind korrigiert und lokal nachgeprüft. [Source5-Zahlungstage V3](CRM_ERP_SOURCE5_ZAHLUNGSTAGE_V3_2026-11-10.md)
ergänzen danach belegte positive Nettozahlungen an späteren tatsächlichen Tagen,
mit vollständigem Originalpräfix, aktueller Fachfreigabe und unverändertem
Bruttozufluss. Gesamtprüfung und neuer eigener Remote-Nachlauf gehören zum
Abschluss dieses Abschnitts. Anschließend werden verbleibende Code- und
Abnahmepunkte des Gesamtziels unmittelbar weiter bearbeitet.

Stand: 09.11.2026. Maßgeblich bleiben das unveränderte
[Gesamtziel](../CRM_ERP_Gesamtziel.txt) und die
[Anforderungsmatrix](CRM_ERP_ANFORDERUNGEN.md). Projekt:
`/workspace/Smarplan-Hofmann-Workspace`, lokaler Branch `codex/finish-20261108`,
Veröffentlichungsziel `codex/testupdate-0.7-projects-20261104`.

## Verbindlicher fachlicher Rahmen

Ergänzung vom 09.11.: Die [Browser-Wiederaufnahme von Material- und privaten
Kilometeroriginalen](CRM_ERP_BROWSER_ORIGINALJOURNAL_VERTRAG_2026-11-09.md)
ist integriert. 1.017 Browsermodul-, 65 betroffene Backend-, 38 betroffene
native und 16 Paketfälle bestehen; tatsächliche Browser-Neuanmeldung sowie
IndexedDB-Konkurrenz werden geprüft. Die [Reiseeinreichung am Sekundenwechsel](CRM_ERP_REISEZEITPUNKT_2026-11-09.md)
ist korrigiert; ihre vier tatsächlichen PostgreSQL-/Restorefälle bestehen.
Weitere Codearbeit bleibt insbesondere die geschützte Übernahme ungebundener
Offline-Altbestände und die benannten zusätzlichen Lohnfälle. Gesamtabnahmen,
Serverauslieferung und reale Geräteprüfung werden getrennt abgeschlossen.

Aktueller Lieferabschnitt vom 09.11.: Projektmeilensteine, Offlinebindung V2,
Serviceanlagejournal, Wartungsverträge, Faktor-/Reisefall V10, Minijob V11 und
Browserzeitabrechnung sind im [gemeinsamen Kandidaten](CRM_ERP_GESAMTINTEGRATION_2026-11-09.md)
integriert. 972 Browsermodul-, 48 gezielte native und 46 Backend-/Paketfälle
bestehen; der echte PostgreSQL-Rechnungsablauf ist ebenfalls geprüft.
Vier Fehler des vollständigen App-Vorlaufs sind gezielt behoben und geprüft.
Die neue vollständige Appprüfung besteht mit 1.770 Fällen. Der Testbranch
ist als 8273852 veröffentlicht. Seine beiden nachgewiesenen Testaufbaufehler
sind [lokal korrigiert und gezielt grün](CRM_ERP_CI_OFFLINE_FIXTURES_2026-11-09.md);
die eigene neue Remoteprüfung des aktuellen Gesamtstands steht noch aus.
Die [Materialrückgabe in beiden Clients](CRM_ERP_MATERIALRUECKGABE_INTEGRATION_2026-11-09.md)
ist inzwischen mit tatsächlichen Quellen integriert und gemeinsam geprüft.
Die [belegte Kilometererstattung](CRM_ERP_KILOMETER_GESAMTINTEGRATION_2026-11-09.md)
für rein dienstliche Mitarbeiterfahrten im privaten Pkw ist inzwischen mit
beiden Clients, tatsächlicher Geld-/EÜR-Kette und geschlossenem Doppelbeleg-
Review integriert. Historische Planabschnitte
weiter unten sind keine Rücknahme dieser abgeschlossenen Erweiterungen.

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

Die [Aussteller-Ländergrenze](CRM_ERP_AUSSTELLER_LAENDERGRENZE_2026-11-09.md)
ist als eigenes explizites Länder-/Währungsrouting für neue Rechnungen
implementiert und in beiden Clients sichtbar. Die rote Fremdland-Gegenprobe,
26 Backend-, zwei tatsächliche PostgreSQL-, 1.020 Browsermodul- und 17 native
Fälle sowie der echte Browserablauf sind dokumentiert. Weitere Regeltrennung
bleibt Aufgabe; fremde Länder werden nicht still freigeschaltet.

Der [lesende Abgleich alter Zeitereigniskerne](CRM_ERP_OFFLINE_ALTZEITEN_2026-11-09.md)
ist jetzt mit tatsächlicher alter Mitarbeiterbasis, neuer enger Metadatenroute
und nativer Bedienung integriert. 81 Backend-, 64 native und fünf tatsächliche
PostgreSQL-/Restorefälle bestehen; vollständige Appanalyse ohne Befund.
Nicht vollständig belegte Zeiten und vollständige Altdatenübernahme bleiben
eigenständige Arbeit. Es gibt keine Freigabe zum erneuten Senden alter Zeiten.

Ergänzt ist die [bedienbare lesende Einzelprüfung alter nativer Planaufträge](CRM_ERP_OFFLINE_ALTBELEGE_NATIVE_2026-11-09.md).
Sie erhält den ursprünglichen Gerätebestand vollständig und verbindet den
bestehenden Hash-Endpunkt mit Navigation, Geräteentsperrung und aktueller
Firmen-/Quittungsprüfung. Weitere alte Warteschlangen und vollständige
Übernahme werden dadurch nicht als erledigt ausgewiesen.

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

## Fortlaufende Abschlussarbeit ab 10.11.2026

Aktueller Nachtrag: Installationskennung, feste Commitarchive und vollständige
Serverpakete sind lokal abgeschlossen, einschließlich1939 aktueller Appfälle.
Alle20 Remotegruppen und der eigene unsignierte iPhone-Release bestehen nach
gezielter unveränderter Wiederholung des vor Testbeginn extern gescheiterten
Downloads. Der signierte iPhone-Vorbereitungsweg ist lokal mit33 gemeinsamen
Fällen geprüft und vom ausdrücklich gewählten TestFlight-Upload getrennt.
Seine Veröffentlichung und wirkliche signierte Vorbereitung folgen;
verbleibende Code-/Fach-/Betriebsarbeiten am Gesamtziel bleiben aktiv.

1. Tatsächliche Windows-Auslieferung mit gemeinsamem Quellenstaging korrigieren;
   lokale 21 Paket-/Inventarfälle bestehen, eigene neue Remoteprüfung folgt.
2. Spätere tatsächliche positive Source5-Nettozahlungen mit unverändertem
   Bruttoereignis, eigenem versioniertem Zahlungsplan und beiden Clients
   schließen; alte Originale und Geldflüsse unverändert erhalten.
3. Weitere belegte Lohnkorrektur-/Gruppenfälle und geschützte Offline-Übernahme
   anhand ihrer konkreten noch offenen Verträge weiter vervollständigen.
4. Durchgängige technische A–G-Nachweise und konkrete Lieferartefakte am letzten
   gemeinsamen Quellstand fertigstellen. Fach-/Geräte-/Betriebsfreigaben bleiben
   echte getrennte Nachweise; keine fehlende Codearbeit als extern blockiert zählen.

## Aktive Arbeitspakete ab dem gemeinsamen Kilometerstand

1. Der gemeinsam geprüfte Stand 19ec4e9 ist auf dem autorisierten Testbranch
   veröffentlicht. Seine eigene Development-/Windows-/iPhone-CI ist beendet:
   Alle acht Jobs von Development42670555279 und der unsignierte iPhone-Build
   von iPhone42670554193 bestehen; signierter Upload nicht angefordert.
   Frühere Fehl- und Erfolgsstände bleiben ihren tatsächlichen Quellen zugeordnet.
2. Online-Restaufgaben mit reproduzierbarem Nutzen weiter schließen: insbesondere
   weitere konkret benannte Lohn-/Steuerfälle und vorbereitete Länder-/Regeltrennung.
   Die Browserpersistenz unbestätigter Material-/privater Reiseaufträge ist
   inzwischen implementiert und tatsächlich mit erneuter MFA geprüft.
   Die native Wiederaufnahme auf gebundenen Servern ist inzwischen im
   [geschützten Originaljournal](CRM_ERP_ONLINEAUFTRAEGE_NEUSTART_2026-11-09.md)
   implementiert und wird mit eigenen aktuellen Nachweisen geführt.
   Die dokumentierten Fremdwährungs-/Unternehmer-/Mischreisefälle bleiben eigene
   Fach-/Codeaufgaben. Keine fehlende Implementierung als extern blockiert zählen.
3. Geschützte Übernahme alter ungebundener Offlinebestände und weitere Offline-
   Dokumentarten vervollständigen, ohne Originale einer neuen Firma ungeprüft
   zuzuordnen. Ganze technische Abnahmen A–G bleiben getrennte Endnachweise.
4. Konkrete Geräte-/Server-/Signierungs-, unabhängige Sicherheits- und fachliche
   Freigaben für den tatsächlich unterstützten Produktivumfang nachweisen.
   Provider-/Meldezugänge und echte Betriebsdaten nur im autorisierten Verfahren.

## Vorangegangene Arbeitspakete und erhaltene Nachweise

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
   Als 3025747 veröffentlicht; sieben Remote-Jobs bestehen, Browser-Testfehler
   im aktuellen Nachfolger korrigiert. Der [v2/v3-Reiseabgleich](CRM_ERP_REISEN_PLATTFORMHISTORIE_2026.md)
   besteht sieben Fachketten-, drei echte PG-/Restorefälle sowie alle 687
   Python-Lohn-/Reise-, 24 native Reise- und 881 Browsermodulfälle.
   eef1927/ef1259c besteht alle acht Development-Jobs und den unsignierten
   iPhone-Build. Die zusätzliche [Übersichtskorrektur](CRM_ERP_UEBERSICHT_LESEKETTE_2026.md)
   besteht 29 Fach-/HTTP-, vier tatsächliche PG-/Restore- und alle 17
   vollständigen Browserabläufe. Der [v6/v7-Einmalbezugsabgleich](CRM_ERP_LOHN_EINMALBEZUG_PLATTFORMHISTORIE_2026.md)
   ist als 894ecdd integriert und veröffentlicht; 694 unterschiedliche Fälle
   bestehen über Sammellauf und gezielte Socket-Wiederholung. Die eigene neue
   Remote-CI wird nach den zwei bestätigten Testhelferfehlern korrigiert; alte Fehlprotokolle bleiben unverändert erhalten. Fälle mit Ansprüchen, Reisen, Übergangsbereich
   oder Einmalbezügen bleiben in ihren eigenen noch auszuarbeitenden Zweigen.
   Der [reguläre Faktor-Vollmonat](CRM_ERP_LOHN_FAKTOR_2026.md) ist jetzt mit
   beiden Clients, tatsächlichem PG-Restore, Zahlungen/EÜR und unabhängigen
   XML-Werten integriert. Individuelle Minijobsteuer und weitere Versicherungs-/
   Faktor-Spezialfälle bleiben Codearbeit. Historische PAP-Kerne sind bytegleich;
   keine Berechnung aus unvollständigen Quellen erfinden.
6. Durchgängige Abnahmen A–G und vollständige Lieferung gemäß Anforderungsmatrix
   verbinden. Fehlender Code bleibt Codearbeit; externe Freigaben bleiben
   zusätzliche Nachweise. [Zentraler Arbeitsstand](CRM_ERP_ARBEITSSTAND.md).

### Nächste konkrete Codepakete nach der laufenden Gesamtprüfung

1. **Historische Einmalbezüge v6/v7 zwischen Windows/Linux:** implementiert und
   in den Hauptstand übernommen. Exakter Abgleich der bekannten LF-/CRLF-
   Metadaten, Originalfälle, Jahresquellen, Quittungen/PDFs, tatsächliche
   Zahlung/EÜR, vier echte PG-/Restorefälle und tatsächliche Windows-Paket-
   rechnung sind belegt. 884 Browsermodule, 31 ausgewählte App- und 16
   Paketprüfungen bestehen; historische Regeln und v1-Zahlungsarithmetik sind
   bytegleich. Die 694 unterschiedlichen Fälle sind über den Sammellauf und elf gezielte
   Socket-Wiederholungen erfolgreich geprüft; der erste Lauf bleibt Exit 1.
   894ecdd ist veröffentlicht, seine eigene Remote-CI fand einen mobilen Anmelde-Testfehler und eine falsche native Dateispeicher-Warteannahme; gezielte Korrekturen laufen. [Umfang und Grenze](CRM_ERP_LOHN_EINMALBEZUG_PLATTFORMHISTORIE_2026.md).
2. **Bereits bezahlte Source5-Folgekorrekturen:** Der neue begrenzte
   [positive Einzelvertrag](CRM_ERP_SOURCE5_POSITIVE_KORREKTUR_2026.md) ist mit
   Backend/Browser/App integriert. Alte Zahlungsteile bleiben exakt erhalten;
   expliziter Vollständigkeitsnachweis und Abführungsgrenzen sind Pflicht.
   Vier echte PostgreSQL-Fälle plus finaler Jahres-/Restorefall, 902 Browser-
   module, 23 ausgewählte native und 16 Paketfälle bestehen. Der breite
   Lohn-/Reisesammellauf besteht mit allen 713 Fällen ohne Skip; die neue
   Remoteprüfung steht aus.
   Negative Korrekturen, andere tatsächliche Zahlungstage und mehrere
   Steuergruppen bleiben eigene Aufgaben. Der
   [Gruppenplan](CRM_ERP_SOURCE5_MEHRFACH_GRUPPEN_RESTPLAN_2026.md) dokumentiert
   die tatsächlich fehlende Steuer-Gruppierungsreferenz; bestehende Sperren
   werden nicht als fertige Umsetzung bewertet.
3. **Weitere ausdrücklich benannte Lohnfälle:** Faktor mit Ansprüchen, Reisen,
   Übergangsbereich und Einmalbezügen; individuelle Minijobsteuer,
   Versicherungs-/Alters-/Leistungsfälle und Minijob-Jahresgrenzen. Bestehende
   Sperren sind kein fertiges Gesamtmodul. Neue Regeln brauchen belegte
   Eingaben und unabhängige Vergleichsfälle; historische Rechenkerne bleiben
   unter ihrer ursprünglichen Version erhalten.
4. **Weitere Reise- und Buchhaltungsfälle:** Fremdwährungs-/Kilometerfälle
   gemäß R09.02 und die übrigen offenen EÜR-/Abschluss-/Regeltrennungsfälle
   gemäß R08/R03.05 vervollständigen. Umfang jeweils zuerst an tatsächlichen
   Codegrenzen und den festgelegten deutschen Einzelunternehmen-/EÜR-Fällen
   prüfen. Keine unspezifischen Spezialfälle als bereits vereinbart erfinden.

Parallel bleiben die vollständige Geräte-/Offlinefolge A–G, neue tatsächliche
Serverinstallation, gewählte Originalformate/Anbieterzugänge und unabhängige
Fach-/Sicherheitsnachweise eigene Lieferaufgaben. Der aktuelle Auftrag erteilt
keinen echten Zahlungs-, Nachrichten-, Melde- oder signierten Uploadauftrag.

### Aktuelle Projektbedienung

- **Dauerhafte Projektanlage:** Die bisher nur im Arbeitsspeicher gehaltene
  unbestätigte Anlage wird vor dem ersten POST geschützt abgelegt und nach
  Neustart mit exakt demselben Auftrag wieder aufgenommen. Vorhandene
  verschlüsselte Vault-/Geräteschlüssel werden verwendet; eigene Instanz- und
  Benutzerbindung, frische Rechte und geprüfte Quittungen bleiben erforderlich.
  [Implementiert und geprüft](CRM_ERP_PROJEKTANLAGE_NEUSTART_2026.md), einschließlich
  echten HTTP-/MFA-App-Neuaufbaus und separatem PostgreSQL-/Restoreanschluss.
- **Browser-Projektaufgaben:** [Implementiert und geprüft](CRM_ERP_PROJEKTAUFGABEN_BROWSER_2026.md): Bearbeiten, Zuständigkeit, Statuswechsel und
  unveränderter Verlauf. Die ungültige Priorität `low` ist entfernt.
  Konflikte, verlorene Antworten, Rechteentzug und geschlossene Ansichten
  sind in echten HTTP-/Browserabläufen geprüft; die gemeinsame Endprüfung
  mit Projektjournal und nativen Originalfällen besteht.
- Explizite [Projektmeilensteine](CRM_ERP_PROJEKTMEILENSTEINE_GESAMTPRUEFUNG_2026-11-09.md) sind additiv mit Backend, Browser und nativer App integriert und lokal geprüft. Bisherige Aufgaben-/Termindaten bleiben unverändert.
- Priorisiert läuft die bestätigte Offline-Firmenisolationskorrektur: neue
  gebundene V2-Grants, getrennte Instanzspeicher und unveränderte Erhaltung
  unklarer V1-Aufträge. Negative Altbestandsabgleiche geben keine neue Sendung frei.

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

Die Anforderungsmatrix bewertet jede Zeile anhand ihrer konkreten Nachweise.
Diese unterschiedlich großen Zeilen werden nicht in eine Gesamtprozentzahl
umgerechnet. Gesamtbuchhaltung und alle Abnahmen A–G bleiben offen.

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


## 10.11.2026 – Fortsetzung nach grüner V3-Veröffentlichung

17978f6 besteht acht Development-Jobs und den unsignierten iPhone-Build.
b437f2c vervollständigt geprüfte spätere Bonuspräfixe und ihre einmalige
Jahreszuordnung. [V4-Rückzahlungen](CRM_ERP_SOURCE5_NETTORUECKZAHLUNG_V4_2026-11-10.md)
sind durch beide Clients, EÜR, Jahresbasis und echte PG-Wiederherstellung geprüft.
Die tatsächliche zusätzliche Konkurrenz-/HTTP-Sperrprüfung besteht nach gezielter
Status423-Behandlung ohne Erhöhung der Zeitgrenzen oder falschen Annahmestatus.
Nach Code-/Nachweissicherung und eigener Veröffentlichung werden wiederholte
positive, negative und betragsgleiche Ausgleiche auf einem gemischten V4-Präfix
additiv geschlossen. Weitere Gesamtanforderungen und Abnahmen bleiben erhalten.


## 10.11.2026 – weitere Nettoausgleiche nach Rückzahlungen

Nächster Codeabschnitt: [V5-Folgekorrekturen](CRM_ERP_SOURCE5_NETTOAUSGLEICHE_V5_2026-11-10.md)
werden auf dem veröffentlichten Stand936f40f entwickelt. V4 ist abgeschlossen
und veröffentlicht, seine eigene CI läuft; V5 und die Gesamtabnahme bleiben
offen. Wiederholte positive/negative/null Differenz bei vollständigem gemischtem
Präfix, tatsächliche Geld-/EÜR-/Jahresketten, beide Clients und Nachweise abarbeiten.


Fortschreibung V5: positive/negative/null Folgeausgleiche sind auf7b7b3b0
mit beiden Clients, tatsächlichem PostgreSQL/EÜR/Jahres-/Restorefall und
der geprüften SQLite-Lesekorrektur gemeinsam lokal abgeschlossen. Eigene
neue Veröffentlichung/CI und Gesamt-/Fachabnahme bleiben getrennt.
Nächster offener Codepunkt sind die belegten Lohnansprüche im Faktorfall.


## 10.11.2026 – echte Anmeldeantwort im Belegrestbetragsbrowser

Der veröffentlichte V5-/SQLite-Stand b31028a besteht Backend, Flutter, Windows,
Mac, HTTPS und Update. Sein Browserjob129627935331 in42755194933 scheitert
später im Belegrestbetragsablauf: Chromium hat den Antwortkörper der
Fähigkeiten während des echten Anmelde-Seitenwechsels verworfen. Die
Einkaufsreparatur wird dadurch nicht als erneut fehlgeschlagen umgedeutet.
Die Beobachtung liest jetzt den tatsächlichen Antwortkörper vor dessen
unveränderter Weitergabe. Kein DTO-Ersatz, kein gelockerter fachlicher Test,
keine verlängerte Zeitgrenze. Der gesamte gezielte Browser besteht mit
Teil-/Restbeträgen, Centbindung, zwei verlorenen Antworten, Rechteentzug,
Altbelegen und Mobilansicht.
[Fehler und tatsächlicher Nachweis](evidence/capacity-login-response-2026-11-10/manifest.json).
Eigene Folge-CI bleibt erforderlich; keine Serverinstallation. Der Gesamtauftrag
läuft weiter, der Faktor-/Anspruchsvertrag V12 wird separat weiterentwickelt.


## 10.11.2026 – belegte Lohnansprüche im vollständigen Faktor-Monat

R09.03/D: Der neue additive [Faktor-/Anspruchsvertrag V12](CRM_ERP_FAKTOR_ANSPRUECHE_V12_2026-11-10.md)
ist in Backend, Browser und App integriert. Tatsächliche unbezahlte Kalenderzeit
und belegter Stundenlohn-Feiertag erreichen die Lohnberechnung ohne erfundene
Projektarbeit. 55 gemeinsame Backend-,1041 ganze Browser-, neun neue native und
21 Paketfälle, saubere Analyse sowie echter PG-/MFA-/Konkurrenz-/EÜR-/Jahres-/
CRLF-/Restorenachweis bestehen. Der vollständige App-Lauf wird nach einem
lokalen Testpfadfehler eigenständig wiederholt. Alte Fehler bleiben erhalten.
Weitere Faktor-/Teilperioden-/Reise-/Einmalbezugs-/Gruppenfälle und A–G bleiben
offen. Veröffentlichung und tatsächlicher Server-/Gerätestand werden getrennt
geführt. Auf dem autorisierten Testbranch ist inzwischen die separat geprüfte
Anmeldeantwort-Korrektur cb7ff63199757da72959a8b52161b6eff62e0117 veröffentlicht;
ihre eigene Development-CI42758607318 läuft. Keine neue Liveinstallation.
Nach Fertigstellung des aktuellen Nachweises wird das Gesamtziel weiter
abgearbeitet; eine abgeschlossene Einzeletappe beendet den Auftrag nicht.


## 10.11.2026 – V12 gemeinsam technisch abgeschlossen, Gesamtauftrag fortgesetzt

Der vollständige korrigierte App-Lauf besteht mit **1.905 Fällen ohne Fehler
oder Skip** in732.859ms. Die tatsächliche Schlussmeldung lautet success:true.
Der erste1902er-Lauf bleibt mit seinen26 Fehlern im Rohnachweis erhalten.
55 Backend-,1041 Browsermodul-, neun neue App- und21 Paketfälle, saubere
Analyse12,4s sowie der tatsächliche PG-/MFA-/Konkurrenz-/EÜR-/Jahres-/CRLF-/
Restorefall25,979s bestehen. Beide echten Browserabläufe bestehen nach
Zusammenführung mit der Anmeldeantwort-Korrektur erneut. 1.103 Python-/Dart-/
JavaScriptdateien sind gegenüber dem vorherigen geprüften Faktorcode bytegleich;
die zusätzlich integrierte CJS-Testbeobachtung ist gesondert tatsächlich geprüft.
[56 rohe Prüfdateien, vollständige App-Protokolle und Manifest](evidence/factor-claims-2026-11-10/manifest.json).

Produktcode d1f5ba1562a084127466d1f2fd3d9da6671e0dab auf Basis cb7ff63;
Veröffentlichung, eigene CI und tatsächlicher Live-/Gerätestand bleiben
getrennte Nachweise. Der ganze Auftrag läuft weiter. Der nächste konkret
begonnene Abschnitt ist der ausschließlich lesende Abgleich bereits archivierter
alter Offline-Serviceprotokolle: vier tatsächliche MFA-/HTTP-Fälle bestehen im
separaten Arbeitsverzeichnis /workspace/smartplan-legacy-service-recovery-20261110.
Alte Texte oder Unterschriften werden dabei nicht neu übertragen, neue Firmen
nicht aus einer alten ungebundenen Adresse abgeleitet und Altaufträge nicht als
neue Dokumente wiederholt. Diese Folgeentwicklung ist noch nicht veröffentlicht.


## 10.11.2026 – aktive Altprotokollfolge nach V12

R11.03/B/F/G: [Lesender Abgleich alter Serviceprotokolle](CRM_ERP_ALTBERICHT_ABGLEICH_2026-11-10.md)
wird auf d1f5ba1 umgesetzt. Die erste tatsächliche Reproduktion ist404; der
neue begrenzte Backendvertrag besteht danach mit vier echten MFA-/HTTP-Fällen.
Native Quellbindung und Bedienung, ursprüngliche Signatur-/PDF-Prüfung und
weitere gemeinsame Nachweise bleiben aktive Arbeit. Kein alter Text oder
Signaturzug wird hochgeladen, keine Quarantäne automatisch freigegeben und
keine Warteschlange geändert. Der Gesamtauftrag bleibt aktiv.


## 10.11.2026 – gemeinsame Altprotokollprüfung

[Lesender Altprotokollabgleich](CRM_ERP_ALTBERICHT_ABGLEICH_2026-11-10.md):58
Backendfälle,29 native Altbestandsfälle, zusätzlicher echter Zwei-Firmen-/MFA-/
TCP-/PDF-/Dateiabgleich, drei neue und sechs bestehende echte PostgreSQL-/
Restorefälle sowie21 Paketprüfungen und saubere Analyse bestehen. Erste
Test-I/O-/Scroll-/Importfehler bleiben erhalten; Produktwächter wurden nicht
gelockert. Eigene Wegwerfdatenbank nach verifiziertem Abschluss entfernt.
Der vollständige aktuelle App-Lauf bleibt noch aktiv. V12 ist als799c144
veröffentlicht, seine eigene Development42762857917 und iPhone42762857879
laufen; keine neue Serverinstallation oder Geräteabnahme. Der Gesamtauftrag
geht nach dieser Etappe weiter, insbesondere andere Offline-Dokumentarten,
weitere vereinbarte Regel-/Lohn-/EÜR-Fälle und technische Gesamtintegration.


## 10.11.2026 – Altprotokollabgleich gemeinsam technisch abgeschlossen

Der tatsächliche vollständige App-Lauf besteht mit1.915 Fällen ohne Fehler
oder Skip in771.908ms, success:true. 58 gemeinsame Backend-,29 native
Altbestands-, ein zusätzlicher tatsächlicher nativer MFA-/TCP-/Zweifirmen-/
PDF-/Dateifall, drei neue plus sechs bisherige echte PostgreSQL-/Restorefälle,
21 Paketfälle und saubere Analyse8,3s bestehen. Alle33 bisherigen Lohnkerne
(einschließlich V12) und das unveränderte Gesamtziel bleiben bytegleich.
1.199 Laufzeit-/Testquelldateien vor und nach Rebase identisch. Eigene
PostgreSQL-Instanz nach ID-/Label-/Portprüfung entfernt; fremde unverändert.
[27 rohe Prüfdateien samt Vorfehlern](evidence/legacy-service-recovery-2026-11-10/manifest.json),
[genauer Vertrag und Grenzen](CRM_ERP_ALTBERICHT_ABGLEICH_2026-11-10.md).

Produktcode aa2ab3651ddc5cadc3c9c75f9df7fd477eee0226 auf veröffentlichtem799c144.
Noch kein neuer Push oder Server-/Geräteabnahme. Der tatsächliche Vorgänger-
CI-Abruf zeigt sechs erfolgreiche und zwei noch laufende Development-Jobs;
unsignierter iPhone-Auftrag ebenfalls noch aktiv. Ganze A–G-Abnahmen bleiben
offen. Als nächste technische Folge werden die langen automatischen
Gesamtprüfungen auf unabhängige Gruppen verteilt, mit vollständiger Erhaltung
aller bisherigen Prüfaufrufe und getrennten Artefakten. Kein Teilabschluss
beendet den Auftrag; weitere Offline-/Fachfälle bleiben im Gesamtplan.


## 10.11.2026 – vollständige Prüfgruppen in Arbeit

A–G/technische Integration: [Vollständige Prüfgruppen](CRM_ERP_GESAMTPRUEFUNG_GRUPPEN_2026-11-10.md)
verteilen alle bisherigen Onlineauswahlen (aktuell154 Datei-/Modulaufrufe) auf
sechs unabhängige PostgreSQL-Gruppen. Alle69 bisherigen echten Browserabläufe
bleiben erhalten; neun vorhandene bisher fehlende Zielabläufe ergänzen die
zentrale Auswahl auf78. Kommerzielle Backend- und Browsermodulprüfungen bleiben
zusätzlich verpflichtend. Sieben tatsächliche Auswahl-/Fehler-/Prozessverträge,
25 echte MFA-/HTTP-Fälle,1041 Browsermodulfälle und21 Paket-/Inventarfälle
bestehen; YAML und Erhaltung der übrigen Jobs sind geprüft. Erste YAML-/lokale
venv-Aufbaufehler bleiben als solche erhalten. Die sechs vollständigen lokalen
Browsergruppen sind noch aktiv. Nicht veröffentlicht; keine Live-/Geräteabnahme.
Weitere verbleibende Fach-/Offline-Codearbeit folgt unmittelbar danach.


## 10.11.2026 – gemeinsame Dialogbedienung und vollständige Prüfgruppen

Produktcode13fa17d74b21c2a18a7c140794fec3ca8a0eed5b verbindet den fertigen
Altprotokollabgleich, vollständige disjunkte CI-Auswahlen und die Korrektur der
Dialog-/Tabellenbedienung.19 Fachdialoge und alle zwölf Hauptansichten bestehen
in vier Modi mit124 gerenderten Zuständen,76 Tastatur-/Hintergrund-/Fokusrückgaben,
tatsächlichem horizontalem Tastaturscrollen, null automatischen Verletzungen,
null Dokument-/Dialogüberlauf und null Fachschreibzugriffen. Vier frühe Befunde
plus ein zusätzlicher eigener Kalenderbefund bleiben als rote Vorläufe erhalten.
1041 Browsermodulfälle, acht Auswahl-/Fehler-/Prozessverträge,25 tatsächliche
MFA-/HTTP-, drei PG-/Restore- und zwei frische HTTPS-/MFA-/PDF-/Worker-/TLS-Fälle
bestehen. Alle33 historischen Lohnkerne und das Gesamtziel bleiben bytegleich.
[49 rohe Prüfnachweise und genauer Teilumfang](evidence/complete-browser-accessibility-2026-11-10/manifest.json).

Die gesamte aktuelle79er-Browsergruppe läuft noch in sechs eigenen dauerhaften
Prozessen; sie wird nicht vorzeitig als bestanden ausgegeben. Der Vorgänger799c144
ist inzwischen tatsächlich vollständig grün: alle acht Development-Jobs von
42762857917 und der unsignierte iPhone-Build42762857879 bestehen. Signierter
TestFlight-Upload übersprungen. Eigene neue Remote-CI, Serverinstallation,
Geräte-/Fach-/Sicherheitsprüfung und ganze A–G-Abnahme bleiben eigene Nachweise.
Der Gesamtauftrag läuft nach diesem technischen Abschnitt weiter.


## 10.11.2026 –79 Browserauswahlen und20 aktuelle Developmentjobs abgeschlossen

[Gemeinsamer Schlussnachweis](CRM_ERP_GESAMTPRUEFUNG_ABSCHLUSS_2026-11-10.md):
Alle79 ausgewählten tatsächlichen Browserabläufe sind abgeschlossen:77 im
Erstlauf, zwei mit ausdrücklich erhaltenem Erstfehler und wirklicher
Wiederholung (eigene DiskFull-Fixture51,584s; reale Source4-Antwortbytes62,806s).
151 rohe Prüfdateien,124 gerenderte Zustände,76 Fokus-/Tastaturfälle, echte
Screenshots,1041 Browsermodulfälle sowie tatsächliche PG-/Restore-/Runtime-
Nachweise sind gesichert. Der veröffentlichte eb74fb5 besteht alle20 eigenen
Development42771773498-Jobs; Windowsartefakte sind anhand wirklicher IDs
verzeichnet. Unsignierter iPhone42771773315-Lauf noch aktiv, keine neue
Live-/Geräteabnahme. Die lokale zusätzliche Source4-Testbeobachtung und dieser
Schlussnachweis sind noch nicht neu veröffentlicht; Runtimeprodukt unverändert.
Der Gesamtauftrag wird unmittelbar mit der additiven Faktor-/P4-/bezahlten-
Reiseverbindung fortgesetzt. Kein Teilabschluss beendet den Auftrag.


## 10.11.2026 – eb74fb5 auch im eigenen iPhone-Nachlauf grün

Alle20 Development42771773498-Jobs und der eigene unsignierte iPhone-
Releasejob129681002071 von42771773315 sind tatsächlich erfolgreich.
Signierter Upload129698183203 übersprungen. eb74fb52a40b8baf25eced4caf1b51a7bc1d9101
ist der neue letzte vollständig grüne gemeinsame Produktstand. Der ursprüngliche
noch laufende Abruf bleibt als Verlauf erhalten. [Abgeschlossener Abruf](evidence/complete-browser-accessibility-2026-11-10/published-ci-all-complete.json).
79 lokale eindeutige Browserabläufe mit zwei getrennt erhaltenen ersten Fehlern
und erfolgreichen Wiederholungen sind abgeschlossen. Die zusätzliche lokale
Source4-Testbeobachtung und Schlussbelege werden als eigener Nachweisstand auf
dem autorisierten Testbranch veröffentlicht. Keine neue Live-/Geräteabnahme.
Die unvollständige V13-Folgeentwicklung bleibt isoliert; Gesamtauftrag läuft weiter.


## 10.11.2026 – Faktor-/P4-/bezahlte-Reise-Verbindung begonnen

R09.02/R09.03/D: [V13-Vertragsarbeit](CRM_ERP_FAKTOR_ANSPRUECHE_BEZAHLTE_REISEN_V13_2026-11-10.md)
schließt die tatsächliche400-Lücke beim gemeinsamen vollständigen Faktor-/P4-
Monat und bereits erstatteter steuerfreier Reise. Vier neue Backendfälle
bestehen mit echtem Source3-Lauf:419355 Anspruchsbrutto,285054 Netto und1400
bereits getrennt gezahlte Reise, unveränderte ursprüngliche500000-Basis und
alle33 historischen Kerne. Äußerer Quellhash bindet beide expliziten unveränderten
V12-/V10-Projektionen; Reisekosten werden nicht erneut zum Lohn addiert.
Unbenutzte Fallübergänge, beide Clients, volle tatsächliche Geld-/EÜR-/Jahres-/
PG-/Restore-/Paketnachweise sind aktive Codearbeit. Noch nicht veröffentlicht.
Die Gesamtintegration des veröffentlichten eb74fb5 wird unabhängig fortgesetzt;
kein Teilabschluss beendet den Auftrag.


## 10.11.2026 – V13:38 Backend- und je neun unabhängige Clientverträge

[Vertragsstand](CRM_ERP_FAKTOR_ANSPRUECHE_BEZAHLTE_REISEN_V13_2026-11-10.md):
38 gemeinsame tatsächliche Backendfälle bestehen in38,036s; echte getrennte
Netto-/Reisezahlung2864,54 Euro EÜR und419355 Cent Jahresbrutto, private Belege,
unbenutzte V10-/V12-Ergänzung und verwendeter Altfallwächter sind geprüft.
Der echte Stundenfeiertag ohne Arbeit enthält eine ausdrückliche vollständige
P4-/SV-Erfüllung ausschließlich der alten Nullentgeltprüfung; sämtliche anderen
Sperren bleiben bestehen. Neun Node- und neun native Prüfungen an drei wirklich
akzeptierten vollständigen Paketen bestehen unabhängig über kanonische Hashes.
Beide sichtbaren Bedienoberflächen, HTTP-/PG-/Restore-/Paket-/Schlussnachweise
bleiben in Arbeit. Nicht veröffentlicht; aktueller Testbranch798cc61-Nachlauf
wird getrennt dokumentiert. Der ganze Auftrag bleibt aktiv.


## 10.11.2026 – V13: sichtbare Clients und echte vollständige Geld-/Restorekette

Der [gemeinsame Faktor-/P4-/bezahlte-Reisevertrag](CRM_ERP_FAKTOR_ANSPRUECHE_BEZAHLTE_REISEN_V13_2026-11-10.md)
ist jetzt in Browser und App einschließlich Vorschau, privaten Originalen,
frischer eigener Fähigkeit, erster Schreibsperre und unveränderter Wiederholung
angebunden. Alle1056 Browsermodulfälle bestehen ohne Fehler oder Skip;38
native gemeinsame Fälle sowie alle drei echten ursprünglichen Formularpakete
(Monat, Stundenfeiertag ohne Arbeit, ausdrücklich unbenutzte V12-Ergänzung)
bestehen. Der echte MFA-/Chromiumablauf prüft beide verlorenen Antworten,
unverändertes PDF, private Ausgabe,390px und unveränderte Reisezahlung.
Der neue tatsächliche PostgreSQL-/MFA-/Parallelitäts-/CRLF-/EÜR-/Jahres-/volle
Dump-Restorefall besteht in84,476s; getrennt2850,54 Euro Netto plus14,00 Euro
Reise ergeben2864,54 Euro belegte EÜR-Ausgaben und keine Vorsteuer.21 Paket-
und Inventarfälle bestehen in33,598s; acht CI-Gruppenverträge und der echte
CRLF-Rücktransport bestehen ebenfalls. Eigene Testdatenbank nach voller ID,
Aufgabenlabel und Loopback-Port32802 geprüft entfernt; fremde unverändert.

Erste Fehler der Testeinrichtung bleiben als Rohdaten erhalten: fehlende feste
Firmenbindung, abweichende sichtbare Text-Erwartung, falscher Testimport,
noch laufende Scrollanimation, falscher Inventarmodulname, gesperrter Node-
Unterprozess und falscher PostgreSQL-Testbesitzer. Keine Produktwächter oder
historischen Rechenkerne gelockert. Vollständige aktuelle App-Suite nach sauberer
Analyse ist noch aktiv, V13 noch nicht veröffentlicht. Bereits verwendete
V10-/V12-Altfälle benötigen weiter ihren vollständigen Korrekturvertrag.

Der bestätigte veröffentlichte Vorgänger798cc61 besteht inzwischen alle20
Development42778059773-Jobs; der eigene unsignierte iPhone-Produktbuild eb74fb5
bleibt erfolgreich, signierter Upload übersprungen. Kein neuer Live-/Gerätestand.
Der Gesamtauftrag läuft über diese Etappe hinaus weiter.


## 10.11.2026 – V13 lokal vollständig geprüft und als Teststand veröffentlicht

Produktcode **b02c84ab24cbe3331a92df950e74134138865e52** ist auf dem autorisierten
Testbranch veröffentlicht und per Remote-Zeiger bestätigt. Die komplette aktuelle
Appprüfung besteht mit **1934 tatsächlichen Fällen**, ohne Fehler oder Skip:
1344,294s Runnerzeit, maschinenlesbarer Abschluss success:true bei1339826ms.
257 verborgene Ladeeinträge sind nicht in1934 enthalten. Die zuvor berichteten
Zwischenzähler des Testwerkzeugs enthielten auch Ladeeinträge; ausschließlich
dieser endgültige Fachfallzähler ist der vollständige App-Nachweis.

1056 vollständige Browsermodule,48 gemeinsame Backend-/CRLF-/CI-Fälle,21
Paket-/Inventarfälle, drei echte MFA-/Chromiumabläufe und der neue tatsächliche
PostgreSQL-/Altfall-/Parallelitäts-/Geld-/EÜR-/Jahres-/vollständige Restorefall
bestehen. [Manifest mit vollständigen Rohdaten](evidence/factor-claims-paid-travel-2026-11-10/manifest.json).
Der erste rote Analyse-/Formular-/Testeinrichtungsstand bleibt erhalten. Alle
37 anhand des Dateimusters erfassten bisherigen2025-/2026-Lohnquelldateien und
das unveränderte Gesamtziel sind gegen798cc61 bytegleich.

Eigene Development42783465222:16 Jobs erfolgreich, vier noch aktiv. iPhone
42783465231 unsigniert noch aktiv; beide Mailbot-Vertragsprüfungen42783465489
auf Linux/Windows erfolgreich. Kein tatsächlicher Mailversand. Neue signierte
Verteilung, Liveinstallation und echte Geräte-/Fach-/Gesamtabnahme fehlen weiter.
Verwendete V10-/V12-Fälle, weitere fachliche Lohn-/Steuerkombinationen und die
übrigen Gesamtanforderungen bleiben offen. Der Auftrag läuft weiter. Separat
begonnen ist die ausschließlich lesende Installationskennung mit festem
Paketnachweis; fünf echte MFA-/Datei-/Rechtefälle bestehen im isolierten
Arbeitsverzeichnis /workspace/smartplan-installation-context-20261110.


## 10.11.2026 – installierter Quellstand und vollständige Serverarchive

R11.04/R15.02/F/G: [Installationsnachweis](CRM_ERP_INSTALLIERTER_QUELLSTAND_2026-11-10.md)
ist isoliert begonnen. Echter vorheriger MFA-/HTTP404 ist reproduziert; fünf
neue HTTP-/Dateifälle, zwei Browserverträge, zehn native gemeinsame Prüfungen,
saubere Analyse25,4s und echter MFA-/Chromium-/390px-/Rechteentzug bestehen.
Die zwei wirklichen Git-/Tar-Gegenprüfungen bestätigen eine zusätzliche Lücke:
Archivierung von HEAD konnte vom zuvor ausgewählten Stand abweichen. Beide
Betreiberbefehle archivieren jetzt den festgelegten Commit; die Erstinstallation
enthält nun auch die zuvor fehlenden Browserdateien. Der Paketmarker ist nur
lesbar und pro Prozess eingefroren; unbekannter Stand wird nicht geraten.
Volle Betreiber-/PG-/Restore-/Paket- und Schlussnachweise laufen; noch nicht
veröffentlicht, keine neue Serverinstallation. V13 bleibt lokal vollständig
geprüft und als Produkt b02c84a veröffentlicht; alle20 eigenen Development-Jobs und sein unsignierter iPhone-Build bestehen; signierter Upload übersprungen.


## 10.11.2026 – vollständige Betreiber-/Paket-/Restoreprüfung abgeschlossen

Installationskern **74490271b00a2f14f8a10a30aa69b703dd4c4d98** ist auf8e6cff5
eingecheckt. Der gesamte endgültige unveränderte Betreiberlauf besteht mit88
Fällen in661,167s. Zusätzlich wird genau7449027 tatsächlich als vollständiges
Git-Quellarchiv erzeugt und in einem getrennten Python-Prozess ausgeführt:
echte MFA, eigene unveränderte Paketkennung und fünf erforderliche Browser-
Einstiegsdateien bestehen in4,629s. Eine unbekannte oder falsch datierte
Arbeitskopie wird nicht als installierter Stand ausgegeben.

35 gemeinsame HTTP-/CI-/Git-Tar-/Paket-/Inventarfälle,1058 Browsermodule, zehn
native gemeinsame Einstellungsfälle, saubere Analyse25,4s, beide wirklichen
Browserläufe und der volle PG-/MFA-/Restorefall30,201s sind abgeschlossen.
Der alte Zugang bleibt nach Restore401; eine neue wirkliche MFA-Anmeldung ist
geprüft. Alle eigenen PG-Container sind entfernt. Ein zusätzlicher wirklich
geprüfter tiefer ungültiger Marker bleibt ebenfalls unrecorded; es wurde dafür
keine Produktausnahme oder gelockerte Dateiprüfung eingeführt.
Die komplette aktuelle App-Suite läuft mit über1000 tatsächlichen Fällen ohne
bisherigen Fehler/Skip. [Alle Rohdaten](evidence/installation-context-2026-11-10/manifest.json).

Dieser Zwischenstand wird ausschließlich auf dem autorisierten Testbranch
veröffentlicht, damit seine eigenen unabhängigen Builds beginnen können.
Keine neue Liveinstallation oder echte Geräte-/Fachfreigabe. Der Vorgänger
b02c84a ist mit allen20 Development-Jobs, unsigniertem iPhone-Release und beiden
Mailbot-Vertragsjobs vollständig grün; signierter Upload übersprungen.
Der Gesamtauftrag läuft weiter.


## 10.11.2026 – echter Apple-Export eingegrenzt, Keychain-Reparatur lokal geprüft

R11.06: Development42796495383 an deebe20 besteht alle20 Gruppen. Der wirkliche
manuelle iPhone-Lauf42796610215 besteht den unsignierten Client, archiviert und
exportiert mit Apple erfolgreich. Die Schlussprüfung weist ein fehlendes
Keychain-Entitlement nach; kein signiertes Artefakt und kein TestFlight-Upload.
Der vollständige Erstfehler bleibt erhalten, bestehende Apple-Einrichtung ist
bestätigt. Keine zusätzlichen Mitgliedschaften oder Geheimniswerte angefragt.

Die [konkrete Reparatur](CRM_ERP_IPHONE_SIGNIERTE_VORBEREITUNG_2026-11-10.md)
erhält ausschließlich die eigene profilgestützte Gruppe über eine temporäre
Archivsignatur und einen erneuten endgültigen Apple-Export. Schlussprüfungen
sind verschärft, nicht gelockert.39 lokale Paket-/Auslieferungs-/CI-Fälle in
33,283s sowie YAML/22 Shellblöcke bestehen. Neue echte macOS-Prüfung bleibt
erforderlich. Faktor-/Midijob V14 und die gefundene Mitarbeiterbeleg-Leserlücke
bleiben separat gesicherte aktive Codearbeit; Gesamtauftrag und A–G sind offen.


## 10.11.2026 – Keychain-Reparatur veröffentlicht, echte Gegenprobe angenommen

40d8fcf5571e8edc898e2e20b1cf7fe36e52149e ist ausschließlich auf dem autorisierten
Testbranch veröffentlicht und dessen Remote-Zeiger bestätigt. GitHub nimmt den
manuellen signierten Vorbereitungslauf42806142665 mitprepare_signed_ipa=true und
upload_to_testflight=false wirklich an. Die vollständige App-Voraussetzung läuft;
kein endgültiges repariertes IPA bestätigt. Development42806104268 läuft separat.
Der doppelte gleichbranchige Pushlauf42806103960 ist durch bestehende concurrency
ersetzt; kein Produktfehler. Bereits abgeschlossene Erstfehler/20 Erfolge sowie
neue konkrete Laufkennungen bleiben im Auslieferungsnachweis erhalten.


## 10.11.2026 – Faktor-Midijob und Mitarbeiterbeleg-Leser integriert, App-Gesamtlauf aktiv

R09.03/D: e70b135 implementiert den ausdrücklich belegten v14-Faktor-Midijob
und korrigiert die Ablehnung tatsächlicher neuerer reduzierter Mitarbeiterbelege
in beiden Clients. Historische Lohnmodule, Projektor und Original-PDFs bleiben
unverändert. Die [gezielten Nachweise](CRM_ERP_FAKTOR_MIDIJOB_V14_2026-11-10.md)
umfassen1077 Browsermodule, wirklichen MFA-Browser mit zwei verlorenen Antworten
und eigenem Mitarbeiter-PDF/JSON,58 gemeinsame Backend-/CI-/Paketfälle sowie
echte vollständige PostgreSQL-/EÜR-/Jahres-/CRLF-/Restorekette54,205s und alte401/
neueMFA. Nach lokaler Integration der getrennten Keychain-Reparatur13b9092
bestehen33 Paket-/Auslieferungs-/Inventarfälle39,748s. Der vollständige App-Lauf
ist um11:34:42UTC gestartet; noch kein Schlussresultat. Kein neuer V14-Push oder
Liveupdate, laufenden tatsächlichen signierten iPhone-Nachlauf nicht abbrechen.


## 10.11.2026 – gesamter V14-Client grün und echte signierte iPhone-Reparatur abgeschlossen

1961 sichtbare Appfälle bestehen ohne Fehler/Skip;260 verborgene Ladeeinträge
sind ausgeschlossen. Echter success:true-Schluss1437145ms, Runnerexit0 nach
1446,014s an13b9092. App-/Backendruntime seit Start unverändert.153-Komponenten-
Inventar stimmt exakt mit dem eingecheckten überein. Der vollständige Backendlauf
mit2133 entdeckten Fällen bleibt aktiv. Kein neuer V14-Push oder Liveupdate.

Die tatsächliche mobile Sichtprüfung findet und korrigiert den bestehenden
Arrayindex-/Zeitflagfehler für reine Lohndaten;17 gezielte Vertragsfälle und der
erneute echte Mitarbeiter-/MFA-/PDF-/JSON-/390px-/Widerrufsablauf bestehen.
Altes Bild und neue visuelle Gegenprobe sind getrennt erhalten. Ein zusätzlicher
roter/grüner Workflowtest trennt künftig normale und ausdrücklich signierte
Läufe;12 gezielte Fälle und YAML/22 Shellblöcke bestehen, Uploadguard bleibt.

Separater tatsächlicher Auslieferungsnachweis an40d8fcf: Development42806104268
alle20 Gruppen erfolgreich. Manueller iPhone42806142665 beide Jobs erfolgreich,
finale Keychain-/Team-/Distributionsprüfung und Schlüsselbereinigung erfolgreich.
Signiertes Paket198: Artefakt13762109533,29866901Bytes; TestFlight-Uploadskipped.
Das Paket enthält noch keinen V14-Client und beweist keine Geräteabnahme. Der
öffentliche Serverabruf erhält Cloud-403; beobachtete eingeschränkte Freigabe
enthält die Domain nicht. Kein bestätigter neuer Ursprungstand oder Liveupdate.


## 10.11.2026 – V14 veröffentlicht, vollständiger Backend-Lauf erfolgreich, Anbieter gewählt

Veröffentlicht und Remote-Zeiger bestätigt:91fa18bf5290ef7f411c7c7d9f722bb78e3dd954.
Der vollständige Backend-Lauf an13b9092 endet12:32:14UTC mit2133 Fällen:
2130 erfolgreich, drei ausdrücklich übersprungen, keine Fehler;2757,214s.
Zwei PG-Projekt-Gegenprüfungen ohne Test-DSN und die Linux-fremde Windows-
Prozessbereinigung sind die Auslassungen. App-/Backendruntime ist zum geprüften
Stand bytegleich. Vollständiger aktueller App-Lauf1961 ohne Fehler/Skip liegt vor.
Rohbericht, Status und Runner sind mit unveränderten früheren Fehlern archiviert.

Eigene91fa-Prüfung: Development42814265700, unsignierter iPhone42814265712
und ausdrücklich signierter Vorbereitungslauf42816832390 laufen. Mailbot
42814265743 ist erfolgreich. TestFlight-Upload bleibtfalse; kein Liveupdate
oder neue Geräteabnahme.

Der Nutzer wählt Qonto, Sparkasse, Amex sowie Granzow, Alexander Bürkle, Loxone
und Voltus. R07.05/R08.03/R12.03 erhalten diese konkrete Entscheidung. Genaue
Sparkasse und Amex-Produkt sind noch angefragt; kein Geheimnis im Chat. Nächste
Implementierung ist eine serverseitige lesende Qonto-Anbindung nach offiziellem
V2-Vertrag, mit exakten Originalbeträgen und ohne erfundene Auszugssalden oder
automatische Buchung. Anbieterzugänge, Cloud-Zielhostfreigaben und reale
Partnerabnahme werden davon getrennt geführt; der Gesamtauftrag bleibt aktiv.


## 10.11.2026 – ausgewählte Anbieter dokumentiert und Qonto mit beiden Clients umgesetzt

Produkt01c368f902c8dc5c9d6c1834616cfad2fd7ffd55 ergänzt den
[Qonto-Leseabschnitt und gewählte Anbieter](CRM_ERP_BANK_LIEFERANTEN_ANBINDUNGEN_2026-11-10.md). Der neue Weg liest V2-Organisation und
Umsatzänderungen genau einer bestehenden aktiven Bankbindung. Centwerte und
belegte Identität bleiben exakt; alle vier Status werden getrennt angezeigt.
Frische Rechte/Zugangsdaten/Kontorevisionen werden beidseitig von IO geprüft.
Keine Zahlung, Bestellung, Buchung, erfundener Auszug oder Provider-Liveabruf.

59 gemeinsame Backend-/Transport-/CI-/Paketfälle37,742s,1081 gesamte
Browsermodulfälle25,098s und15 native Bank-/Qonto-Fälle bestehen; Appanalyse
sauber16,3s. Wirklicher MFA-/Browser-/390px-/Abmeldeablauf besteht. Tatsächliche
getrennte PG-Runtime, Cash-/Bankoriginale unverändert, voller Dump/Restore,
alterToken401 und neue tatsächliche MFA bestehen33,452s.41 Rohdateien samt
unveränderten Vorfehlern sind im neuen Manifest geprüft.57 Lohnmodule,
Originalziel und Abhängigkeitsinventar153 bleiben unverändert. Ein zusätzlicher
nach Commit ausgeführter Quellarchivfall sowie zwei Inventarfälle bestehen.

Der erste PG-Volumeversuch scheitert vor Tests am Speicherplatz und sein erster
Cleanup-Guard an fehlenden Ports des bereits gestoppten Containers. Exakte
ID/Task/konfigurierte Loopbackbindung wurden separat geprüft und allein dieser
Container entfernt. Bounded512MiB-Tmpfs-Wiederholung erfolgreich und ebenfalls
genau geprüft entfernt. Andere Vorfehler (Importe, Testrollen, Worktree-Aufbau,
fehlender statischer Modulpfad, abweichendes synthetisches Zeitfenster) bleiben
erhalten; Produktprüfungen wurden dafür nicht gelockert.

An91fa18b sind inzwischen alle20 eigenen Development-Gruppen42814265700
und der unsignierte iPhone42814265712 erfolgreich. Windows-Artefakte sind
vorhanden. Manuelle signierte Vorbereitung42816832390 läuft separat,
Uploadfalse. Diese Gesamtprüfung enthält noch keinen Qonto-Code. Neuer
Qonto-Kandidat wird ausschließlich für den autorisierten Testbranch vorbereitet.

Echte Zugänge, OAuth-Einwilligung/Erneuerung, nachgewiesener Auszugsimport,
konkrete Sparkasse/Amex-Produkt und Lieferantenverträge bleiben offen. Loxone
bietet offizielle CSV/DATANORM-Dateien, deren tatsächliches Schema noch nicht
gelesen werden konnte. Alle Gesamtziel-Abnahmen und übrigen Lohn-/Buchhaltungs-
Restarbeiten bleiben bestehen; keine neue Liveinstallation oder Geräteabnahme.


## 10.11.2026 – Eigenkonto-Key abgeschlossen, ca14 veröffentlicht, Apple-Netzwerkfehler erhalten

Qonto-Kandidatca14af3822aac0706c2acf80bdb568cc5f29afbb ist auf dem autorisierten
Testbranch veröffentlicht und Remote-Zeiger bestätigt. Eigene Development-
Prüfung42821768166 und unsignierter iPhone42821768001 laufen; Mailbot
42821768083 erfolgreich, kein echter Versand.

Additiv lokal67b99d3: offizieller Qonto-Eigenkonto-Key-Vertrag, ausdrücklicher
Modus und Betreiberdatei; Header exakt Sign-in:Secret-Key. Fünf neue Fälle
sind zuerst tatsächlich rot, danach43 gemeinsame Fälle10,469s erfolgreich.
Beide tatsächlichen getrennten PG-Runtime-/MFA-/Cash-/Bankoriginal-/Dump-/
Restorefälle bestehen41,810s. Neuer realer Browserablauf mit exaktem Key-Header,
vier Status,390px und Abmeldung besteht. App- und Browserproduktcode bleiben
bytegleich zu ca14. Eigener Quellarchivfall besteht; keine echte Bankverbindung.
Zusatz bleibt lokal, bis die aktuelle vollständige ca14-Prüfung abgeschlossen ist.

Manuelle signierte V14-Vorbereitung42816832390: unsignierter Client erfolgreich;
Job129847153231 scheitert im temporären Apple-Export mit tatsächlichem
Netzwerkabbruch und anschließend fehlendem Profil. Vollständiger Erstfehler
erhalten; vorhandene frühere Apple-Signierung198 bleibt eigener positiver
Nachweis. Genau der fehlgeschlagene Job ist mit unveränderten Quellen erneut
ausgelöst und angenommen; neuer Signierjob129852986325 läuft. Uploadfalse.

Loxones offizielle CSV-Weiterleitung kann nun als tatsächlicher HTTPS-Abruf
geprüft werden: normaler Sandboxaufruf ohne Proxyverbindung, gleiche öffentliche
URL mit regulärer Ausführungsfreigabe403 von Envoy. Der aktuelle erzwungene
Netzplan erlaubt pim.loxone.com nicht. Der Nutzer ist um diese Hostergänzung
in den Einstellungen gebeten; keine Geheimnisse angefragt, keine Netzsperre
umgangen. Alle16 neuen Rohdateien sind im Eigenkonto-Manifest erhalten.
Gesamtziel, fehlende Fach-/Geräte-/Betriebsabnahmen und übrige Codearbeit
bleiben ausdrücklich bestehen.


## 10.11.2026 – signierter V14-iPhone-Nachlauf200 erfolgreich

Unveränderter Quellstand91fa18b, manueller Lauf42816832390, wiederholter
Signierjob129852986325 erfolgreich. Zwei tatsächliche Apple-Exporte sowie
finale Team-/Signatur-/Keychain-Prüfungen und Bereinigung erfolgreich.
Smartplan-Office-iOS-200: Artefakt13769975157,29898645Bytes; TestFlight
übersprungen. EnthältV14 und korrigierte Mitarbeiterbelege, noch kein Qonto.
Vollständige Erfolg-/Job-/Artefaktrohdaten und erster Netzwerkfehler erhalten.
Keine neue Geräte-/Server-/Fachabnahme daraus ableiten.


## 10.11.2026 – Qonto-Vorläufer vollständig grün, Eigenkonto-Key zur Veröffentlichung

Eigene Development42821768166 anca14af3 besteht alle20 Gruppen, einschließlich
Windows, kompletter App, Backend, tatsächlicher Online-/Browser-, HTTPS-/
Update-/Restoreprüfungen. Kein Fremdstand als Nachweis übernommen. Der lokal
geprüfte Eigenkonto-Key67b99d3 wird danach ausschließlich auf dem autorisierten
Testbranch veröffentlicht; keine laufende notwendige Prüfung dafür verdrängt.
Eigenkonto-Code43 gemeinsame Fälle und zwei tatsächliche PG-/MFA-/Restorefälle
plus echter Browser sind separat nachgewiesen; Clientruntime seitca14 bytegleich.
Der neue eigene Remote-Nachlauf ist nach tatsächlichem Push getrennt zu prüfen.
