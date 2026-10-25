# Umsetzungsbericht Smartplan Business Suite 0.12

Stand: 25.10.2026, Arbeitszweig `feat/project-business-suite`. Grundlage sind die freigegebene [Gap-Analyse](GAP_ANALYSE_HERO.md), die [Zielarchitektur](ZIELARCHITEKTUR.md) und alle 98 Prüfpunkte A1–O4. Die Quellstände sind durch Conventional Commits und die unten aufgeführten Meilenstein-PRs nachvollziehbar; Paketmanifeste nennen den tatsächlich gebauten Commit.

Das Paket verbindet Anfragen, Kunden, Projekte, Belege, Planung, eigene Zeiten, Dokumentation, Material und Wartung. Es ist **keine vollständige HERO-Parität** und keine rechtliche Zertifizierung. Die Statusangaben beziehen sich auf tatsächlich vorhandenen Code und die unten genannten Prüfungen; eine Anbieter-, Geräte- oder Betriebsfreigabe folgt daraus nicht automatisch.

**Umgesetzt** bedeutet: Der beschriebene Kernablauf ist implementiert und durch die genannten synthetischen Fach-/Integrationstests belegt. **Teilweise** bedeutet: Eine nutzbare Teilfunktion existiert, ein ausdrücklich genannter Bestandteil oder eine erforderliche Abnahme fehlt. **Offen** bedeutet: Für den geforderten Umfang liegt keine fertige Funktion vor; ein Konfigurationsfeld oder Prüfprofil ersetzt sie nicht. Server-, Browser- und native Oberfläche werden getrennt bewertet.

## Prozess und Produktgrenzen

Der Arbeitsablauf bleibt flexibel. Anfrage, Rückruf, Unterlagen/Aufmaß, Angebot, Zusage, Termin, Anzahlung, Material und Ausführung sind keine erzwungene Reihenfolge. Projektstatus, Aufgaben und Meilensteine erfinden weder Zusagen noch Zahlungseingänge. Gmail/WhatsApp können weiterhin Ausgangspunkt sein; eine offizielle WhatsApp-Business-API wurde damit nicht angebunden.

Sevdesk bleibt zunächst führender Aussteller. Eigene Rechnungen benötigen einen ausdrücklich bestätigten Ausstellerwechsel mit Stichtag, vollständige Unternehmensdaten und die geschützte PostgreSQL-Betriebsumgebung. **SQLite darf eigene Finanzbelege nicht aktivieren oder ausstellen**, auch nicht durch importierte aktivierte Einstellungen. Entwürfe, operative Funktionen und ausdrücklich synthetische Tests sind davon zu unterscheiden. Eine Rechnung darf nicht parallel unkoordiniert in Sevdesk und Smartplan ausgestellt werden.

Die neue native App heißt 0.12.0+120. Sie erweitert die bestehende Projektmappe um Fachregister und einen gemeinsamen Business-Einstieg. Die responsive Browseroberfläche unter `/office/` ist ein separates Produktartefakt; sie ist kein Flutter-Webbuild und keine freigegebene Offline-PWA. Ein Android-Ziel und dessen SDK-/Geräteabnahme fehlen.

## Prüfstand und getrennte Betriebsabnahmen

Die Zahlen sind voneinander abgegrenzte Prüfläufe; sie werden nicht als Summe einzigartiger Tests oder als vollständige Produktionsabnahme ausgegeben.

| Bereich | Belegter Stand bei Erstellung dieses Berichts |
|---|---|
| Gmail vor Produktänderungen | 116 synthetische Bestand-/HTTP-Verträge grün; Tests zuerst in Commit `6564104`. Öffentliche Lieferverträge bleiben erhalten. |
| PostgreSQL/Migration/Release | 79 Schema-/Privacy-/Releasefälle zunächst grün; nach abschließender Mahnfassung und ACL-Härtung 58 Release-/Setup-/PostgreSQL-Fälle erneut grün (keine Skips). Historische 1–6→7-Migrationen, Up/Down, Restore und wirksame Tabellen-/Spaltenrechte geprüft. |
| Gesamte Online-API | Root meldet 254 Fälle grün; neun gesonderte Sandbox-Opt-in-Fälle werden zusätzlich in ihrer vorgesehenen CI-Umgebung geprüft. |
| Planung/Zeit | 27 SQLite-/MFA-/Flask-Fälle grün, drei echte PostgreSQL-Fälle grün. Belegt sind unter anderem zwei Geräte/Officeinstanzen, DST, Replays, Freigaben und ältere Restores. |
| Neue API-Grenzen | Elf Boundaryfälle plus vier Root-ACL-Fälle. Der abschließende Rootlauf berücksichtigt die neue PostgreSQL-only-Finanzgrenze: Der SQLite-Archiv-/Downfall verwendet ein echtes Angebot statt einer produktiven Rechnung. Abschließender Lauf nach der Produktivgrenze: elf Boundaryfälle grün; zusätzlich vier Root-ACL-Fälle grün. |
| Unabhängiger Finanzreview | Zehn Fälle grün, einschließlich echter KoSIT-Prüfung kumulierter Rechnung, Schlussrechnung und gebundener Stornierung. SQLite-Fachfixtures verwenden für Finanztests ausdrücklich eine synthetische Testklasse; die Produktionssperre wird separat geprüft. |
| Commercial/SMTP/E-Rechnung gesamt | Abschließender Lauf: 74/74 grün in 82,024 Sekunden. Teilzahlung nach Mahnfreigabe erzeugt eine erneut freizugebende Fassung derselben Stufe; alte PDFs bleiben unverändert. Nachgewiesene Annahme derselben Versandoperation bleibt monoton. Die zuvor roten Erholungsfälle sind abgesichert. Echte lokale TLS-SMTP-Senke und offizielle Validatoren, keine Erfolgsmocks für Konformität. |
| Neue Dokumentation/Material/Wartung | 38 Fach-/HTTP-Fälle grün; enthalten sind drei echte Flaskabläufe. |
| Native App | 52/52 gezielte Business-/Bestandsfälle grün, einschließlich Dart→Flask, echter AES-/Neustart-/Kamera-Widgetwege und drei nativer PDF-Fälle. Analyzer ohne Befund und drei Rendererfälle grün. Zusätzlich vollständige App-Suite mit 279 Fällen, separate drei echte PDF-Rendererfälle und vollständiger Analyzer grün. Echte Geräteabnahme bleibt getrennt. |
| Browser | Sechs echte Chromium-Abläufe und 20 JavaScript-Prüfungen grün, einschließlich Kalender-Drag und öffentlichem Formular mit verlorenem HTTP-201-ACK. Sandbox aktiv; kein TLS-Nachweis durch den Loopback-Testtransport. |
| Neues Kontaktformular/Antwort | 30 Adapterfälle einschließlich zehn Formular-/Antwortfällen, 28 Foundationfälle und 116 Gmail-/Bestandsverträge zusammen grün; zusätzlich drei echte HTTPS-Flask-Kontaktfälle und vier ACL-Fälle grün. Optionale Antwort-Units und Worker bleiben ohne bewusste Einrichtung ausgeschaltet. |
| Paket-/Werkzeugaufbau | 14 Paket- und fünf Fetchprüfungen grün; tatsächlicher Source-ZIP-Import und ein vollständiges 13,5-MB-Offlinepaket mit allen sieben gesperrten Windows-Wheels geprüft. Lokale Dateipins stimmen mit KoSIT/Mustang/veraPDF-Laufzeitpins überein. Die verpflichtende Windows-CI-Probe aktualisiert eine neue private Pythonumgebung zweimal aus den Wheels und prüft Sperre, fehlendes Wheel und unveränderte Daten-/Konfigurationssentinels. Ihr tatsächliches CI-Ergebnis sowie native Windows-/iOS-Artefakte und echte Geräte werden separat bewertet. |

Aktuelle Einzelbelege stehen unter anderem in [Boundarytests][tBound], [Release-/PG-Tests][tRelease], [Finanz-Peerreview][tPeer], [E-Rechnungstests][tE], [SMTP-Tests][tSMTP], [echtem Dart→Flask-Test][tDartApi] und [Browser-E2E][tBrowser]. GitHub-CI und reale Geräte sind eigene Abnahmegrenzen. Lokale grüne Läufe werden nicht als bereits ausgeführte Serverinstallation oder native Gerätefreigabe ausgegeben.

Zusätzlich ein zusammenhängender realer PostgreSQL-/Flask-Journey: MFA → Gmail mit Originalanhang → Kunde/Projekt → Termin/Zeitfreigabe → unterschriebener Bericht → Angebot/AB/Rechnung → Teilzahlung → Archiv-/Exporthash, grün mit echter geschützter Runtime und ohne synthetische Ausgabepolicy. Quelle: [Journeytest](../backend/online/test_business_journey_pg.py).

Backend-Gesamtlauf: 325 Fälle grün, eine vorgesehene plattformspezifische Auslassung. Operatorablauf: 60 echte Bash-/Dateisystem-/Lock-/Trap-Fälle im netzlosen Docker grün, einschließlich optionaler Antwort-Worker und Abbruch nach öffentlicher Freigabe. Die folgenden Tabellen bewerten weiterhin den fachlichen Umfang und ersetzen diese Grenzen nicht.

## Alle 98 Prüfpunkte

Nach den abgeschlossenen Formular-/Workerprüfungen: **37 umgesetzt, 50 teilweise, 11 offen**. Teilweise und offen sind mit konkretem Grund ausgewiesen; eine vorbereitete Profilauswahl gilt nicht als Anbindung.

Die Quellenkürzel sind am Ende dieses Dokuments auf konkrete Dateien verlinkt. Hinter dem Quellenlink steht der relevante Einstieg/Symbolname; die Testlinks nennen die tatsächlichen Prüfdateien.

### A – Anfrage und Auftragseingang

| ID | Anforderung | Status | Tatsächlicher Umfang, Grenze und Quelle/Test |
|---|---|---|---|
| A1 | Lead-API/eigenes Websiteformular, Anfragen im Projektkontext | umgesetzt | Dedizierter schlüsselgeschützter Servereingang und öffentliches Formular mit Origin-/Ratelimit-/Honeypotprüfungen erzeugen echte, deduplizierte Anfragen. Kontakt/Projektübernahme bleibt bewusst bestätigbar; Formular, unveränderte Wiederholung nach verlorenem ACK und begrenzter Worker sind geprüft; Aktivierung und SMTP-Zugang sind Betriebsaufgaben. [BA] `receive_lead/receive_form`; [Kontakt-HTTPtests][tContact], [Adaptertests][tA], [Browser-E2E][tBrowser]. |
| A2 | Automatische Antwort mit nächsten Schritten | umgesetzt | Freigegebene, versionierte Antwortvorlage und feste Outbox; Annahme erst nach echter SMTP-Quittung, `unknown` sperrt blindes Wiederholen. Worker und optionale Timer-/Service-Units sind implementiert und standardmäßig aus; keine ungefragte Kundenmail versendet. [BA] `approve_reply_template/deliver_reply`; [Adaptertests][tA], [SMTP][tSMTP]. |
| A3 | Kontaktdaten/Ausgangssituation/Anliegen ohne Abschreiben | teilweise | Gmail-/Lead-/Formulardaten werden mit Herkunft und Originaltext übernommen; bekannte Kontakte werden vorgeschlagen. Kein allgemeines KI-Auslesen beliebiger Nachrichten oder automatische ungeprüfte Kunden-/Projektentscheidung. [BA] `_lead`, [MAIL] `Inquiries.convert`; [Intakeverträge][tIntake], [Adaptertests][tA]. |
| A4 | Aroundhome/TapTapHome automatisch anlegen/zuweisen | offen | Die Partnerprofile sind sichtbar als nicht unterstützt und nicht aktivierbar. Offizieller Versions-/Authentifizierungsvertrag, Feldmapping, Mitarbeiterregeln und Sandbox fehlen. [BA] `PROFILES/save`; [Adaptertests][tA] prüfen Ablehnung unsupported Enablement. |
| A5 | Telefonischen Auftrag schnell erfassen | teilweise | Manuelle Anfrage/Telefonquelle mit Kontakt-/Anliegenfeldern und bestätigter Übernahme in ein Projekt; kein gesondert gemessener kompakter Telefon-Schnellauftrag, keine Telefonanlage oder Aufzeichnung. [MAIL] `Inquiries.create/convert`, [UI-Inbox]; [Workspace-HTTP][tWorkspace], [Intakeverträge][tIntake]. |
| A6 | Bestehender Gmail-Intake einschließlich Anhängen | umgesetzt | Bestehender Body-/Manifest-/Chunk-/Receiptvertrag, Konto-/Ownerbindung, Wiederholung und Originalbytes bleiben erhalten. Neue Sichtbarkeitsfreigabe betrifft Teamzugriff, nicht die Botantwort. [MAIL], [Anhänge]; [Intakeverträge][tIntake], [Anhang-HTTP][tAttachments]. |

### B – Projekt als Arbeitsmappe

| ID | Anforderung | Status | Tatsächlicher Umfang, Grenze und Quelle/Test |
|---|---|---|---|
| B1 | Zentrale Projektmappe mit Dokumenten | teilweise | Gemeinsame Projekt-ID verbindet Fachregister, Originale, Belege, Pläne, Aufgaben und Berichte. Kein vollständiger einheitlicher DMS-/ZIP-Export aller Artefakte; Sichtbarkeit bleibt kategorisiert. [BF] `project`, [UI-Projekt], [BO] `export_project`; [Root-ACL][tACL], [Operations][tO]. |
| B2 | Übersicht/Suche/individuelle Pipeline | umgesetzt | Suchbare Projektliste, eigene versionierte Status mit Farbe/Reihenfolge und frei änderbare Zuordnung; gemeinsame Beschreibung bleibt kanonisch. Kein vorgeschriebener Prozessablauf. [BF] `statuses/save_status/pipeline/save_project`; [Foundationtests][tBF], [native Shelltests][tShell]. |
| B3 | Statusmeldung im Feed und Push | teilweise | Projektfeed speichert echte Änderungen mit Finanz-/HR-Sichtbarkeit; keine Zustellung über APNs/FCM oder Pushgeräteabnahme. [BF] `event/feed`; [Foundationtests][tBF], [native Sessiontests][tSession]. |
| B4 | Aufgaben verteilen/abarbeiten/Fortschritt | umgesetzt | Zuständigkeit nur aktives Projektmitglied, Fälligkeit/Priorität/Status, offene/erledigte Zähler und versionierte Updates. [PW] `save_item/dashboard`; [Workspace-Unit][tPW], [Workspace-HTTP][tWorkspace]. |
| B5 | Auftragsbestätigung aus Angebot | umgesetzt | Explizite Belegumwandlung erhält Preis-/Empfängersnapshot und Vorgängerbezug. [BD] `convert`; [Belegtests][tD], [native Belegtests][tNativeD]. |
| B6 | Mitarbeiter einem Projekt zuweisen | umgesetzt | Bestehende Zuweisung bleibt maßgeblich; frische Rollen-/Projektprüfung auf Fach-, Original- und Replaypfaden. [BF] `require_permission`, [Core] `Office.assign/project`; [Foundationtests][tBF], [Boundary][tBound]. |
| B7 | Projekt-Messenger mit Notizen/Nachrichten/Bildern | teilweise | Projektfeed und Notizen mit Referenzen sowie getrennte Fotodokumentation/Galerie; kein vollwertiger Chat mit Lesebestätigungen, Bildversand im Chat oder Push. [BF] `post_message/feed`, [BO] `list_media`; [Foundationtests][tBF], [Operations][tO]. |

### C – Kontakte und Lieferanten

| ID | Anforderung | Status | Tatsächlicher Umfang, Grenze und Quelle/Test |
|---|---|---|---|
| C1 | Kundenkartei/Datenübernahme in Projekt und Belege | teilweise | Bestehende Kunden-IDs, mehrere Ansprechpartner/Anschriften und Empfängersnapshots werden verwendet; Ausstellerbriefkopf ist bewusste Unternehmenseinstellung und kein Kundendatensatz. Kein universeller Briefeditor. [BF] `save_contact`, [BD] `_payload`; [Foundation][tBF], [Belegtests][tD]. |
| C2 | Mobiles CRM | teilweise | Native Kontaktliste/-editor mit relationalen Unterobjekten, Suche, Revisionen und eingeschränkter Export-/Löschprüfung; keine CRM-Offlinequeue oder vollständige Kommunikationschronik. [UI-CRM], [BF] `contacts/save_contact`; [native Workflows][tNativeW], [Foundation][tBF]. |
| C3 | Lieferantenverwaltung | teilweise | Kontaktarten `supplier` mit Ansprechpartnern/Adressen und getrennte Lieferantenherkunft bei Materialimporten. Keine vollständigen Einkaufskonditionen oder Lieferantenportale. [BF] `CONTACT_KINDS/save_contact`, [BA] `SUPPLIERS`; [Foundation][tBF], [Adapter][tA]. |

### D – Angebote und Dokumente

| ID | Anforderung | Status | Tatsächlicher Umfang, Grenze und Quelle/Test |
|---|---|---|---|
| D1 | Angebote aus Vorlagen, Artikel/Leistungen, Drag-and-drop, Summen | teilweise | Echte Vorlagen-/Artikelübernahme und exakte Decimal-Summen/Steuern; Positionen manuell sortierbar. Kein vollständig belegter Artikel-Drag-and-drop-Katalog wie beim Vorbild. [BD] `create/_positions/calculate_positions`, [UI-Belege]; [Belegtests][tD], [native Belege][tNativeD]. |
| D2 | Eigene Beleg-/Mahnvorlagen und Textbausteine | umgesetzt | Eigene versionierte Sammlung für Kostenvoranschläge, Angebote, Rechnungen, Auftragsbestätigungen und Lieferscheine; Textbausteine und getrennte konfigurierbare Mahntexte. Kein öffentlicher Vorlagenmarktplatz behauptet. [BD] `save_template/save_text_block`, [FZ] `save_settings`; [Belegtests][tD], [Finanztests][tF]. |
| D3 | Eigenes Briefpapier/Logo/Branding | teilweise | Ausstellerdaten, begrenztes Bildlogo, Fußtext und PDF-Briefkopf sind serverseitig implementiert. Kein freier Briefpapierdesigner; native Logoauswahl nicht vollständig abgebildet. [BD] `_settings/render_pdf`; [Belegtests][tD], [native Belegtests][tNativeD]. |
| D4 | Aufmaß/Lieferschein/Zahlungserinnerung mobil | teilweise | Mobile manuelle Aufmaße und Beleg-/Mahnabläufe existieren; einzelne Spezialeditoren/Originalprüfungen sind eher im Browser/API verfügbar. [BO] `save_entry`, [BD] `convert`, [FZ] `propose`; [Operations-HTTP][tOpsApi], [native Workflows][tNativeW]. |
| D5 | E-Mail-Versand und PDF-Download | umgesetzt | Belege und genehmigte Mahnungen: Vorschau, explizite Freigabe, operationgebundene Outbox, TLS-SMTP und Original-PDF/XML. SMTP-Annahme belegt keinen Empfang/Lesen beim Kunden; Betriebskonfiguration erforderlich. [BD] `send_mail`, [FZ] `deliver`, [SMTP]; [SMTPtests][tSMTP], [Finanz-Peerreview][tPeer]. |
| D6 | Unterschrift für Angebot/Lieferschein/Aufmaß/Bericht; eIDAS-Stufen | teilweise | Fassungs-/hashgebundene gezeichnete einfache Unterschrift mit Name/Zeit und gesondertem PDF. Keine fortgeschrittene/qualifizierte Signatur, Identitätsprüfung oder eIDAS-Zertifizierung. Finanzbelege erfordern zusätzlich Finanzleserecht. [BD] `sign`, [BO] `sign_entry`; [Belegtests][tD], [Operations][tO], [Peerreview][tPeer]. |
| D7 | Dokumentenverwaltung/Versionen/Archiv/Suche/Export | teilweise | Belegsuche, immutable finale Artefakte, Versionen, geschützte Downloads und operativer JSON-Export. Kein vollständiger unternehmensweiter DMS-Export aller Originale als ein Paket. [BD] `list/archive`, [BO] `export_project`; [Belegtests][tD], [Operations][tO], [Release][tRelease]. |

### E – Kalkulation

| ID | Anforderung | Status | Tatsächlicher Umfang, Grenze und Quelle/Test |
|---|---|---|---|
| E1 | Artikel/Leistungen/Preise pflegen | umgesetzt | Versionierte Artikel und Leistungsbestandteile, exakte Preisstrings; bestätigte Importübernahme statt stiller Überschreibung. [BD] `save_article`, [BA] `apply_catalog`; [Belegtests][tD], [Adaptertests][tA]. |
| E2 | Gewerke-LV mit Material/Lohn/Maschine | teilweise | Eigene Leistungen aus Material/Lohn/Maschinenbestandteilen; kein geliefertes gewerkspezifisches, rechtlich gepflegtes Standard-LV. [BD] `save_article/_positions`; [Belegtests][tD]. |
| E3 | EK/Aufschläge/Stundensätze/Gemeinkosten/netto-brutto | teilweise | Explizite EK-/VK-/Stundensätze und positionsbezogene Netto-/Steuerberechnung vorhanden; kein automatischer EK-Aufschlags-/Gemeinkostenrechner oder vollständiges Tarifmodell. EK bleibt finanzberechtigt, VK für Zeitübernahme wird ausdrücklich eingegeben. [BD] `save_article/calculate_positions`, [BT] `approved_costs`; [Belegtests][tD], [Zeitabrechnung][tBilling]. |
| E4 | Marge/Gewinn/Angebotskalkulation | teilweise | Angebotskosten-/Preissnapshots und Material-/Lohnunterscheidung als Kalkulationsbasis. Kein vollständiger Unternehmensgewinn/GuV oder bestätigte Vollkostenrechnung. [BD] `calculate_positions`, [BI] `cost_report`; [Belegtests][tD], [Inventartests][tI]. |
| E5 | Nachkalkulation/Soll-Ist im Projekt | teilweise | Bestätigte Materialbewegungen und freigegebene Zeiten mit historischem Satz fließen ein. Fehlende Sätze markieren Kosten unvollständig und verhindern erfundenes Restbudget; Maschinen-/Gemeinkostenvollrechnung fehlt. [BI] `cost_report`, [BT] `approved_costs`; [Inventartests][tI]. |
| E6 | Nachtragskalkulation | teilweise | Unveränderter Nachtragsvorschlag, gesonderte Finanzfreigabe und Budgetwirkung; noch kein vollständiger positionsweiser Nachtrags-/Auftrags-/Rechnungsallokationsprozess. [BI] `add_change_order/approve_change_order`; [Inventartests][tI]. |
| E7 | Budgetplanung | teilweise | Versionierte Baseline für Material/Lohn/Maschine/Sonstiges und freigegebene Nachträge. Keine Forecast-/Warnschwellen- oder Cashflowplanung. [BI] `save_budget/cost_report`; [Inventartests][tI]. |

### F – Rechnungen und Rechnungsdaten

| ID | Anforderung | Status | Tatsächlicher Umfang, Grenze und Quelle/Test |
|---|---|---|---|
| F1 | Angebot/Auftrag/AB in Rechnung umwandeln | umgesetzt | Bewusste Umwandlung in Rechnungsentwurf mit übernommenem Snapshot; Ausgabe erst nach eigenem PG-Aussteller-/Cutover-/Restoregate. [BD] `convert/prepare_finalization`; [Belegtests][tD], [Commercial-HTTP][tCommercial]. |
| F2 | XRechnung/ZUGFeRD erstellen | umgesetzt | UBL XRechnung mit echtem KoSIT; ZUGFeRD EN16931 als PDF/A-3B mit Mustang, extrahierter identischer XML und echter veraPDF-Prüfung. Pflichtdaten/konkrete Profile/Toolkonfiguration erforderlich; keine allgemeine Unterstützung jedes Profils behauptet. [BE] `build_xrechnung/build_zugferd/validate_pdfa3`; [offizielle Validatortests][tE], [Peerreview][tPeer]. |
| F3 | E-Rechnungseingang/Upload/Datenerfassung/automatisches Auslesen | teilweise | Original-PDF/Foto/XML bleibt erhalten; unterstützte UBL-/CII-Fakten werden als manuell zu prüfender Vorschlag gelesen, Review appendiert. Kein allgemeines PDF-/Bild-OCR oder automatisches ZUGFeRD-PDF-Auslesen; native Vollprüfung nicht fertig. [FZ] `capture_receipt/review_receipt`, [BE] `inspect_invoice`; [Finanztests][tF], [Commercial-HTTP][tCommercial]. |
| F4 | Material/Lohn/Umsatzsteuer getrennt ausweisen | umgesetzt | Positionsarten, getrennte Summen und Steuergruppen mit exakter Rundung im Snapshot/PDF/XML. [BD] `calculate_positions/render_pdf`; [Belegtests][tD], [E-Rechnung][tE]. |
| F5 | Freigegebene Zeiten in Rechnung übernehmen | umgesetzt | Explizite Quellenauswahl und VK-Stundensatz; Sekundenmenge/Basis3600, Hash-/Revisionsprüfung vor Ausgabe und Schutz gegen doppelte Finalabrechnung. Kein HR-/EK-Leck im Quell-DTO. [BT] `approved_billable`, [BD] `time_sources/_time_snapshot`; [Zeitabrechnung][tBilling], [Zeittests][tT], [E-Rechnung][tE]. |
| F6 | Abschlag/Schluss/kumulierte Rechnung | umgesetzt | Vorbelegkette reduziert bereits berechnete Haftung, erfindet keine Zahlung. Volles gebundenes Storno erhält Originalbeträge; abweichende freie Gutschrift wird abgelehnt. [BD] `_prior_snapshot/cancel/finalize`; [Belegtests][tD], [Peerreview][tPeer], [E-Rechnung][tE]. |
| F7 | Zahlungs-QR auf Rechnung | umgesetzt | Begrenzter EPC/GiroCode aus validierter IBAN/Betrag/Referenz. Zahlungsanweisung ist keine Zahlungsbestätigung und kein Onlinezahlungsanbieter. [BD] `epc_payload/render_pdf`; [Belegtests][tD]. |
| F8 | GoBD-Bausteine/Festschreibung/Storno/Nummern/Hash/Versionen | teilweise | Technisch: Nummern-CAS, unveränderliche finale Archive/Versionen, Hashprüfung, appendierte Korrektur und getrennte PG-Besitzer-/Laufzeitrollen. Keine GoBD-Zertifizierung; Verfahrensdokumentation, Aufbewahrung, Kontierung und Steuerberaterfreigabe bleiben Betriebsaufgaben. [BD] `finalize/guard_statements`, [BS] `require_runtime_security`; [Belegtests][tD], [PG-Release][tRelease]. |
| F9 | Daten/Belege an Steuerberater übergeben | teilweise | Ausgewählte originale Artefakte und explizit kontiertes Prüf-CSV mit Steuergruppen/Herkunft verfügbar. Kein nativ abgenommener DATEV-Import oder Steuerberaterkanal. [BA] `export_data`, [BD] `archive`; [Adaptertests][tA]. |

### G – Offene Posten und Zahlungsprozesse

| ID | Anforderung | Status | Tatsächlicher Umfang, Grenze und Quelle/Test |
|---|---|---|---|
| G1 | Sortierbare OP-Liste/Teilzahlung/Fälligkeit/Mahnung/Notiz | umgesetzt | Reale Zuordnungen, offene Beträge, Fristen, letzte/nächste Mahnstufe und versionierte Notiz; keine Anzeige erfundener Zahlungseingänge. [FZ] `open_items/note`; [Finanztests][tF], [native Finanzen][tNativeF]. |
| G2 | Bis sechs Mahnstufen mit Vorlagen/Intervallen/Karenztag | teilweise | Konfigurierbar bis drei Erinnerungen und drei Mahnungen mit Text/Betreff, Abstand und Gebühren-/Zinswerten; deaktivierbare kurze Stufenfolge. Ein gesonderter Karenztag neben dem Intervall fehlt. Betrieb prüft rechtliche Zulässigkeit. [FZ] `_rules/save_settings`; [Finanztests][tF], [native Workflows][tNativeW]. |
| G3 | Mahnstufe nach Erstellung erhöhen | umgesetzt | Erst genehmigtes, gebundenes Mahn-PDF erzeugt die nächste Stufe; Vorschau allein erhöht nichts. [FZ] `propose/approve`; [Finanztests][tF]. |
| G4 | Vorschlagslauf/Empfängerprüfung/manuelle Versandfreigabe | umgesetzt | Zahlung/Regeln/Empfänger/Briefkopf werden frisch geprüft; Freigabe und tatsächliche Zustellung sind getrennt, unklarer Versand blockiert Wiederholung. [FZ] `propose/approve/deliver`; [Finanztests][tF], [SMTP][tSMTP]. |
| G5 | Zahlungseingang/Abgleich/Onlinezahlung | teilweise | Manuelle bestätigte Eingänge/Erstattungen und exakte Teilzuordnungen mit stabiler Quellen-ID. Kein Bankfeed oder Kunden-Zahlungsanbieter; GiroCode ersetzt diese nicht. [FZ] `record_payment/payments`; [Finanztests][tF], [Peerreview][tPeer]. |
| G6 | Belege mobil erfassen | teilweise | Geschützter Foto-/Datei-Upload und serverseitige Eingangsbelegprüfung, Originalhash und appendierte Reviewfassung. Native vollständige Belegreview noch nicht durchgängig; keine OCR-Zusage. [FZ] `capture_receipt`, [BO] `verified_receipt_media`; [Finanztests][tF], [Operations][tO]. |
| G7 | Finanzübersicht | teilweise | Projektbezogene OP-/Zahlungs-/Kostenübersicht mit echten Quellen; keine vollständige Buchhaltung, Bilanz/GuV oder Livebankübersicht. [FZ] `open_items/payments`, [BI] `cost_report`; [Finanztests][tF], [Inventar][tI]. |

### H – Planung und Ressourcen

| ID | Anforderung | Status | Tatsächlicher Umfang, Grenze und Quelle/Test |
|---|---|---|---|
| H1 | Einzel-/Serientermine mit Mitarbeitern | umgesetzt | Endliche tägliche/wöchentliche/monatliche Serie, lokale Uhrzeit über DST, stabile Vorkommen und einzelne Ausnahmen. Höchstens365 Vorkommen/fünf Jahre, kein unendlicher RRULE-/„alle künftigen“-Editor. [BP] `save_appointment`; [Planung][tP], [Planungs-HTTP][tPlanApi]. |
| H2 | Plantafel Woche/Monat/gefilterte Tage/individuell | teilweise | Native Wochenansicht und serverseitige Datum-/Mitarbeiter-/Projektfilter. Keine vollständige Monats-/individuelle Mehrbereichsplantafel. [UI-Planung], [BP] `calendar`; [native Planung][tNativeP], [Planung][tP]. |
| H3 | Planänderung per Drag-and-drop | umgesetzt | Tatsächliches LongPress-Drag auf einen Tag und Formularänderung nutzen dieselbe Revision; Kollision/409 erzeugt keine optimistische Scheinbuchung. [UI-Planung] `moveToDay`, [BP] `save_appointment`; [native Planung][tNativeP], [Planungs-HTTP][tPlanApi]. |
| H4 | Fahrzeuge/Maschinen/Werkzeuge planen | umgesetzt | Reale Ressourcenstammdaten, Terminbindung und Überschneidungsprüfung; keine automatische Einsatzoptimierung. [BP] `save_resource/_conflicts`; [Planung][tP]. |
| H5 | Urlaub/Abwesenheit in Plantafel | umgesetzt | Genehmigte Sperrzeiträume verhindern normale Buchung; Kalender zeigt nur „nicht verfügbar“, keinen medizinischen Grund. [BP] `approve_absence/calendar`; [Planung][tP]. |
| H6 | Grafische Jahres-/Langfristprojektplanung | offen | API kann begrenzte längere Zeiträume lesen; eine Jahres-/Ganttoberfläche samt Abhängigkeiten ist nicht vorhanden. [BP] `calendar`, [UI-Planung] zeigt Wochenansicht; [native Planung][tNativeP] ist kein Jahres-Gantt-Nachweis. |
| H7 | Mobile Plantafel mit Echtzeitsync | teilweise | Projekt- und Mitarbeiterkalender lesen dieselben kanonischen Termine; Aktualisierung/Abgleich vorhanden. Keine SSE/WebSocket-/Pushzustellung oder garantierte Echtzeit im Hintergrund. [BP] `calendar`, [UI-Planung]; [Planungs-HTTP][tPlanApi], [native Session][tSession]. |
| H8 | Werkzeugverfügbarkeit/QR/NFC optional | teilweise | Werkzeugressourcen und Konflikte sind vorhanden; QR-/NFC-Hardware und Kamera-Decodierung nicht umgesetzt/abgenommen. [BP] `resources`, [BI] `lookup`; [Planung][tP], [Inventar][tI]. |

### I – Mitarbeiter, Zeiten und Abwesenheit

| ID | Anforderung | Status | Tatsächlicher Umfang, Grenze und Quelle/Test |
|---|---|---|---|
| I1 | Projektstempeluhr Start/Pause/Ende | umgesetzt | Start/Pause/Fortsetzen/Stopp als sequenzierte, revisionsgebundene Ereignisse; genau eine aktive Erfassung pro Mitarbeiter. [BT] `event`; [Zeit][tT], [Planungs-HTTP][tPlanApi], [native Zeit][tNativeT]. |
| I2 | Push-Erinnerung zu Uhrzeit | offen | `reminder_time` ist nur Betriebskonfiguration. Kein APNs/FCM-/OS-Adapter, keine Geräteempfänger und kein Zustellnachweis. [BT] `save_rule`; [Zeit][tT] belegt Regeln, keine Pushzustellung. |
| I3 | Online/offline/Überstunden/automatische Pause | umgesetzt | Dauerhafte verschlüsselte Queue, stabile IDs, Konflikte bleiben erhalten; UTC-Dauer/DST und einmaliger Tagespausenabzug über Projekte hinweg. [BT] `event/_day`, [UI-Offline]; [Zeit][tT], [Offlinezeit][tOfflineT], [Dart→Flask][tDartApi]. |
| I4 | Tages-/Wochen-/Monats-/Jahresauswertung | teilweise | Tageswerte und Summen frei gewählter begrenzter Von/Bis-Zeiträume; Zeitkonto/CSV. Keine vollständige separate Jahresgrafik/Payrollauswertung. [BT] `summary/export_csv`, [UI-Zeitkonto]; [Zeit][tT], [native Workflows][tNativeW]. |
| I5 | Optionaler Start-/Stoppstandort und Löschung | teilweise | Serververtrag standardmäßig aus, nur Start/Stopp, kein Tracking; Freigabe purgt Koordinaten/Hash nach unabhängigem Checkpoint, auch gegen älteren Restore. Die native App erfasst derzeit ausdrücklich keinen Standort; tatsächliche optionale Geräteaufnahme und rechtliche Betriebsfreigabe fehlen. [BT] `event/approve_day/reapply_privacy_checkpoint`, [BS], [UI-Zeit]; [Zeit][tT], [Privacytests][tPrivacy]. |
| I6 | Arbeitstag genehmigen | umgesetzt | Explizite Tagesversion, keine laufende Session; Originalfreigabe bleibt erhalten, begründete Korrektur appendiert. [BT] `approve_day/correct_entry`; [Zeit][tT], [native Workflows][tNativeW]. |
| I7 | Zeitkategorien/Zuschläge | umgesetzt | Eigene aktive Kategorien mit exakt gespeichertem Prozentsatz; Satz beim Start eingefroren. Keine Tarif-/Lohnabrechnungszusage. [BT] `save_category/event`; [Zeit][tT], [PG-Planung][tPlanPg]. |
| I8 | Arbeitszeitkonto | umgesetzt | Sollmodell/Abwesenheitsgutschrift, Ist-/Pausen-/Korrekturwerte, begründete Überträge und Kontosaldo. Keine automatische Lohnabrechnung. [BT] `summary/adjust_account`; [Zeit][tT], [native Workflows][tNativeW]. |
| I9 | Abwesenheit/Urlaubsanträge | umgesetzt | Eigene Anträge, versionierte Freigabe/Ablehnung/Stornierung und private Gründe außerhalb des normalen Kalenders. [BP] `save_absence/approve_absence`; [Planung][tP]. |
| I10 | Dienstpläne | teilweise | Schicht ist serverseitig derselbe kanonische Mitarbeitertermin mit Ressourcen-/Konfliktprüfung. Kein vollständiger eigener nativer Schichtplaneditor oder Rotations-/Tarifplaner. [BP] `save_shift`, [UI-Planung]; [Planung][tP]. |
| I11 | Personalstamm/Stundenexport für Lohnvorbereitung | teilweise | Benutzergebundene Mitarbeiterprofile, historische Soll-/Kostensätze und CSV freigegebener Stunden. Native Personalpflege nicht vollständig; kein zertifiziertes Payrollformat und keine Lohnabrechnung. [BP] `save_employee`, [BT] `export_csv`; [Zeit][tT], [Boundary][tBound]. |
| I12 | Mitarbeiterverfügbarkeit | umgesetzt | Belegungen, genehmigte Abwesenheit und Ressourcenüberschneidung werden tatsächlich geprüft; Override benötigt eigenes Recht und Begründung. [BP] `_conflicts/save_appointment`; [Planung][tP], [Boundary][tBound]. |

### J – Baustellendokumentation

| ID | Anforderung | Status | Tatsächlicher Umfang, Grenze und Quelle/Test |
|---|---|---|---|
| J1 | Fotos/Notizen/Markierungen | umgesetzt | Hashgeprüfte Originaluploads, getrennte Beschriftung/normalisierte Annotationen; neue enge Offline-Fotofreigabe nur eigene operative JPEG/PNG. Native vollständiger Markierungseditor und echte Kamerageräte separat prüfen. [BO] `new_media/annotate_media`, [UI-Medien], [UI-Offline]; [Operations][tO], [Offlinefotos][tOfflineM], [Boundary][tBound]. |
| J2 | Projektbildergalerie | umgesetzt | Echte projektbezogene Galerie mit begrenzter Vorschau/Paginierung und Originaldownload; keine globale Fotosuche. [BO] `list_media`, [Browser]; [Operations-HTTP][tOpsApi], [Browser-E2E][tBrowser]. |
| J3 | Bautagesbericht mit Vorlagen/Artikeln/Zeiten | teilweise | Strukturierter Bericht, öffentliche eingefrorene Artikelrevisionen und explizite genehmigte Zeitquellen ohne Gehaltsdaten. Kein vollständiger Tagebuchvorlagen-/Drag-and-drop-Editor. [BO] `_entry_body`, [BT] `approved_work`; [Inventar][tI], [Operations][tO]. |
| J4 | Bautagebuch/Logbuch mit Export | teilweise | Reale versionierte Einträge, History und JSON-Projektexport; PDFs/Originale getrennt. Kein vollständiger PDF-/ZIP-Gesamtexport aller Dokumente. [BO] `save_entry/export_project`; [Operations][tO]. |
| J5 | Mängelmanagement | teilweise | Status, Frist, zugewiesener Mitarbeiter, Ortstext, Medien, Revision und Abschlussnachweis. Planpins/Benachrichtigungen fehlen. [BO] `_entry_body` für `defect`; [Operations][tO]. |
| J6 | Dokumentation mailen/herunterladen | teilweise | Geschützte Original-/signierte PDF-Downloads funktionieren. Der neue operative Dokumentationskern besitzt keinen allgemeinen Mailversand für alle Dokuarten; Beleg-/Mahnversand aus D5 ist getrennt. [BO] `media_source/entry_pdf`; [Operations][tO], [Operations-HTTP][tOpsApi]. |

### K – Aufmaß

| ID | Anforderung | Status | Tatsächlicher Umfang, Grenze und Quelle/Test |
|---|---|---|---|
| K1 | Mobiles digitales Aufmaß | umgesetzt | Manuelle metrische Positionen mit Decimal-, Einheiten- und begrenzter AST-Formelprüfung in Browser/nativer Oberfläche. Keine automatische Foto-/Maßstabs-/CAD-Erkennung. [BO] `evaluate_measurement/save_entry`; [Operations][tO], [native Workflows][tNativeW]. |
| K2 | Aufmaß in Kalkulation übernehmen | offen | Berechnete Mengen sind abrufbar; ein vollständiger quellengebundener Übernahme-/Allokations-/Doppelabrechnungspfad in Kalkulationspositionen fehlt. [BO] `evaluate_measurement`, [BD] `_positions`; [Operations][tO] belegt Aufmaß, nicht diese noch fehlende Kette. |
| K3 | Aufmaß digital unterschreiben | umgesetzt | Name, UTC-Zeit, Contenthash/Revision und eingefrorenes PDF; einfache gezeichnete Signatur, keine qualifizierte Identitätsprüfung. [BO] `sign_entry/entry_pdf`; [Operations][tO], [Operations-HTTP][tOpsApi]. |

### L – Lager und Einkauf

| ID | Anforderung | Status | Tatsächlicher Umfang, Grenze und Quelle/Test |
|---|---|---|---|
| L1 | Bestände/Entnahmen/Lagerbewegungen | umgesetzt | Appendiertes Bewegungsjournal für Zugang/Entnahme/Rückgabe/Transfer mit historischer Bewertung, Reservierungsschutz und atomaren Wiederholungen. Eine Inventurzähl-/Korrekturmaske fehlt. [BI] `move/_post_move/balance`; [Inventar][tI], [Operations-HTTP][tOpsApi]. |
| L2 | Lagerartikel mit Dokumenten | teilweise | Gemeinsamer versionierter Artikelstamm und Lagerbezug vorhanden; eigene Artikeldokumentbindung fehlt. [BD] `save_article`, [BI] `_article`; [Belegtests][tD], [Inventar][tI]. |
| L3 | Lieferantenmanagement | teilweise | Lieferantenkontaktstamm und Herkunft von Importartikeln; keine vollständigen Preis-/Lieferkonditionen. [BF] `save_contact`, [BA] `SUPPLIERS/apply_catalog`; [Foundation][tBF], [Adapter][tA]. |
| L4 | QR-/Barcode scannen und abhaken | teilweise | Exakter Code-Lookup und bewusstes Kommissionieren vorhanden. Keine Kameradecodierung, QR-/NFC-Hardwareintegration oder Geräteabnahme; Codeeingabe ist kein Kamerascan. [BI] `lookup/pick`; [Inventar][tI]. |
| L5 | Auftragskommissionierung | teilweise | Projektreservierungen, Teilentnahmen, Rückgabe und Freigabe sind implementiert; vollständige Auftragspositionsallokation fehlt. [BI] `reserve/pick/release_reservation`; [Inventar][tI]. |
| L6 | Großhändlernachbestellung/aktuelle Preise | teilweise | Lokale Nachbestellvorschläge und freizugebender Bestellentwurf mit ehrlichem `not_sent`. Granzow/Alexander Bürkle sind unbestätigte Partnerprofile; kein Livepreisabruf oder Bestellversand. [BI] `reorder_suggestions/save_order`, [BA] `SUPPLIERS`; [Inventar][tI], [Adapter][tA]. |

### M – Checklisten und Wartung

| ID | Anforderung | Status | Tatsächlicher Umfang, Grenze und Quelle/Test |
|---|---|---|---|
| M1 | Techniker-/Einarbeitungschecklisten und Servicebericht | umgesetzt | Versionierte Vorlage, Pflichtantworten, eingefrorener Durchlauf und quellengebundener Servicebericht mit Signatur/PDF. Kein vorgefülltes fachlich zertifiziertes Einarbeitungspaket. [BO] `save_checklist/answer_checklist/report_from_checklist`; [Operations][tO], [Operations-HTTP][tOpsApi], [native Workflows][tNativeW]. |
| M2 | Wartung/Vertrag/Erinnerung/Anlagenhistorie | teilweise | Anlagen, Vertragsanhangreferenzen, sichere Tages-/Monatsintervalle, deduplizierte Fälligkeiten, Verlauf und Abschluss nur mit passendem signiertem Bericht. Keine automatische externe Reminder-/Cronzustellung. [BM] `save_contract/schedule_due/complete_visit`; [Wartung][tM], [Operations-HTTP][tOpsApi]. |

### N – Austauschformate und Anbieteradapter

| ID | Anforderung | Status | Tatsächlicher Umfang, Grenze und Quelle/Test |
|---|---|---|---|
| N1 | Datanorm | teilweise | Begrenztes CP850-A14-A-Neuanlagenprüfprofil, Rohpreis/Basis erhalten, bestätigte Preisrolle und Artikelübernahme. Keine vollständige DATANORM-Version/Rabatt-/Änderungs-/Löschsatzunterstützung. [BA] `parse_catalog/apply_catalog`; [Adaptertests][tA]. |
| N2 | IDS Connect | offen | Profil absichtlich nicht aktivierbar; Anbieter-/Authentifizierungs-/Versionsvertrag und echte Partnerabnahme fehlen. [BA] `PROFILES/save`; [Adaptertests][tA]. |
| N3 | UGL | offen | Kein freigegebener Partnerparser/-versand; keines der vorhandenen CSV-Prüfprofile wird als UGL ausgegeben. [BA] `PROFILES`; [Adaptertests][tA]. |
| N4 | OCI | offen | Kein authentifizierter OCI-Katalog-/Rücksprungvertrag implementiert. [BA] `PROFILES`; [Adaptertests][tA] prüfen Unsupported-Grenze. |
| N5 | SHK Connect | offen | Anbieterprotokoll und Sandbox nicht bestätigt; kein behaupteter Liveanschluss. [BA] `PROFILES`; [Adaptertests][tA]. |
| N6 | GAEB Import/Export für gesamten Belegprozess | teilweise | XML-DA83 3.2/3.3 Positions-/Mengeninspektion, begrenzter Roundtrip und ausdrücklich bepreister Angebotsentwurf. Komplexe Alternativ-/Referenzpositionen und unbekannte kommerzielle Felder bleiben als unsupported_semantics inspizierbar; Preisangebot und verkürzter Prüfexport werden nachweislich abgewiesen. Keine offizielle XSD-Abnahme oder vollständige X84-/Rechnungs-/Nachtragskette. [BA] `inspect_gaeb/create_offer_from_inspection/export_data`; [Adaptertests][tA]. |
| N7 | DATEV Export/Synchronisation | teilweise | Eigenes Steuerberater-Prüf-CSV mit expliziten Konten/Steuerschlüsseln und Herkunft. Kein DATEV-EXTF, keine native Importfreigabe und keine Synchronisation. [BA] `export_data` Profil `datev_review_csv_v1`; [Adaptertests][tA]. |
| N8 | Lexware Office/Rechnungsübergabe/Zahlungsüberwachung | teilweise | Lokales Review-JSON mit Kontaktzuordnung und ausgewähltem Zahlungssnapshot. Keine Lexware-API-Zustellung oder Livezahlungsüberwachung. [BA] `export_data` Profil `lexware_review_json_v1`; [Adaptertests][tA]. |
| N9 | Aroundhome | offen | Kein offizieller Anbieterzugang; generisches Website-Leadprofil ist kein Aroundhome-Anschluss. [BA] `PROFILES`; [Adaptertests][tA]. |
| N10 | TapTapHome | offen | Kein freigegebener Protokoll-/Quellen-/Authentifizierungsvertrag oder echter End-to-End-Anschluss. [BA] `PROFILES`; [Adaptertests][tA]. |
| N11 | Lead-API | umgesetzt | Dedizierte Lieferung mit stabilem Fremdschlüssel, Scope/Rate/Ownerprüfung und minimalem Receipt erzeugt echte Inboxdaten. Kein allgemeiner Officezugang und keine automatische ungeprüfte Projektfreigabe. [BA] `receive_lead`, [Web]; [Adaptertests][tA], [Kontakt-HTTP][tContact]. |

### O – Plattform, Datenschutz und optionale Automationen

| ID | Anforderung | Status | Tatsächlicher Umfang, Grenze und Quelle/Test |
|---|---|---|---|
| O1 | Cloud/Echtzeit/PC/Smartphone/Tablet/Web/iOS/Android | teilweise | Online-API, responsiver Browser und Flutterquellen für Windows/iPhone/iPad; neue enge Offlinezeiten/-fotos. Keine Android-SDK-/Target-/Gerätefreigabe, kein Flutter-Web/PWA-Offline und keine garantierte Push-Echtzeit. [Web], [Browser], [UI-Shell]; [Browser-E2E][tBrowser], [Dart→Flask][tDartApi], [Pakettests][tPackage]. |
| O2 | Datenschutz/Sicherheit/Rechte | teilweise | Frische Rollen-/Projekt-/Feldrechte, private Finanz-/HR-Pfade, enge DB-belegte Gerätebereiche, Quellfreigabe, unabhängige Privacy-Replays und Restoregates technisch geprüft. Rechtliche DSGVO-/GoBD- und Betriebsfreigabe bleibt offen. [BF] `require_permission`, [BS], [API]; [Boundary][tBound], [Privacy][tPrivacy], [Release][tRelease]. |
| O3 | Mobile Aufträge/Doku/Zeit/Signatur/Kunden | teilweise | Native Kernabläufe sind vorhanden, einschließlich echter Offlinezeit-/Fotodateien und Kamera-Widgetweg. Nicht sämtliche Personal-/Eingangsbeleg-/Händler-/Spezialimporteditoren sind nativ vollständig; echte Geräteabnahme steht aus. [UI-Shell], [UI-Projekt], [UI-Offline]; [native Workflows][tNativeW], [Offlinefotos][tOfflineM], [Dart→Flask][tDartApi]. |
| O4 | Optionale Automationen zuletzt | offen | Generische Kundenterminerinnerung, Rechnung nach Abschluss und KI-Telefonannahme sind nicht aktiviert. Keine Hintergrundausgabe von Rechnungen/Bestellungen. Eng begrenzte ausdrücklich freigegebene A2-Eingangsantwort ist separat beschrieben. [BA] `deliver_reply`, [BS] Featureflags; [Adaptertests][tA], [Schema][tSchema]. |

## Migration, Down und Wiederherstellung

Die kanonische PostgreSQL-Storageversion ist **7**. Die neun Businessmodule haben explizite idempotente Schemaexports, Checksummen, Integritätsprüfungen und feste Registry. Ein HTTP-Fachaufruf migriert keine Datenbank. SQLite-Startup und PostgreSQL-Operatorpfad sind getrennt; `PRAGMA user_version` ist nicht die PostgreSQL-Schemaversion.

`up → up → down → down → up` darf IDs, alte Originalbytes, Nummernstände, Festschreibungen, Audit und Receipts nicht verlieren. **Down** bedeutet: Businessschreiber aus, weiter vorhandene lesbare Archive und kompatible Bestandsfunktionen; kein `DROP TABLE`, kein Nummernreset und kein Zurückdatieren des tatsächlichen Storageversionsmarkers. Ausgestellte Daten bleiben kanonisch. Read-Capabilities sind von aktiven Schreib-Capabilities getrennt. Belegt in [Schema][tSchema] und [echter PG-Abnahme][tRelease].

PostgreSQL trennt Migrationseigentümer und Laufzeitrolle. Die Laufzeit darf weder DDL noch Guards abschalten, finale Archive überschreiben oder Nummernzähler zurücksetzen. Produktions-Finanzausgabe verlangt frischen Rollen-/Ownershipnachweis; eine Superuserverbindung mit bloßem `SET ROLE` ist keine Abnahme. Der Archive-Hash wird beim Lesen geprüft. SQLite-Trigger werden nicht als gleichwertige produktive Finanzsicherheit vermarktet.

Datenschutzentscheidungen werden vor Löschung in einem separat geschützten HMAC-Checkpointjournal dauerhaft verankert. Das Journal enthält Subjecthashes statt Kontakt-/Koordinatpayload. Eine ältere Datenbankwiederherstellung wird vor Verwendung gegen die neueren Entscheidungen abgeglichen. Fehlende/unsichere Bindung blockiert den Start bzw. die Löschung; es wird kein erfolgreiches Löschen behauptet. Dieser POSIX-Serverpfad wird unter Windows nicht sicherheitstechnisch simuliert.

Ein Disasterrestore widerruft alte Zugänge und behandelt nicht bestätigten Versand konservativ als `unknown`; er startet keine Mail erneut. Zusätzlich bleibt eigene Finanzausgabe durch `financial_reconciliation_required` gesperrt, bis ein privilegierter Abgleich **dieser konkreten Restore-ID**, Nummernhorizonte und externen Versand-/Belegstände belegt ist. Der Abgleich verändert keine archivierten Rechnungsbytes. Details: [BS] `privacy_restore_guard/require_financial_release/reconcile_financial_restore`, [Restore], [Restore-Outbox-Tests][tRestoreOutbox], [PG-Release][tRelease].

## Bewusste Verhaltensänderungen und Rechte

Diese Punkte müssen beim Update kommuniziert und praktisch getestet werden; der alte Gmail-Liefervertrag wird dafür nicht erweitert oder gebrochen.

- **BREAKING für bisherige Teamansichten:** Unbekannte bestehende Projektlinks und Mailoriginale sind zunächst nur für Owner sichtbar. Auch ein zugewiesener Accountant erhält ein unklassifiziertes Original nicht automatisch. Owner prüft und klassifiziert die konkrete Quelle mit erwarteter Revision und Quellfingerprint; ein alter Freigabedialog darf eine geänderte URL nicht freigeben.
- Angebots-/Rechnungslinks haben ein finanzielles Mindestniveau. Sie können nicht allgemein operativ freigegeben werden. Gleiches gilt für private Originale: Listen, Zähler, Suche, Download, Replay und Export dürfen Finanz-/HR-Grenzen nicht umgehen.
- Eine **bereits bewusst erzeugte operative Plankopie** ist gemäß freigegebenem Vertrag eine eigene Freigabe. Eine spätere Financialklassifikation des Mailoriginals sperrt Original und neue Übernahmeversuche, widerruft diese frühere unabhängige Plankopie jedoch nicht automatisch. Dies ist getestet und vor einer Weitergabe personenbezogener Dokumente bewusst zu berücksichtigen.
- Manager und Technician erhalten keine Finanz-/HR-Standardrechte. Accountant ist nicht automatisch Personalverwalter. Nichtowner benötigen weiterhin die aktuelle Projektzuweisung; Einzelgrants und Denies ersetzen sie nicht. Globaler Deny hat Vorrang, projektbezogene Denies werden auch bei Kalender-/Zeit-DTOs berücksichtigt.
- Neue Gerätebereiche `time_events` und `field_media` müssen ausdrücklich mit einem in der Datenbank belegten Grant ausgestellt sein. Ein Tokenpräfix allein reicht nicht. Alte Plan-/Workspace-Tokens erhalten keine neuen Rechte. Ein Owner-Gerätetoken erbt keine Finanz-/HR-Vollansicht; der Fotobereich erlaubt nur eigene operative JPEG/PNG, keine fremde Galerie oder Finanzbelege.
- Sieben Tage Offlineberechtigung löschen keine bereits gespeicherten Eingaben. Konflikte bleiben zur Klärung lokal erhalten; keine Scheinbestätigung und keine standortbasierte Dauerverfolgung. Ein unerreichbares Gerät kann nicht als aus der Ferne sicher gelöscht bezeichnet werden.
- Finanzfestschreibung ist produktiv ausschließlich auf der geschützten PostgreSQL-Installation möglich. Sevdesk ist weiterhin Standard; Aussteller-/Nummern-/Stichtagswechsel und fachliche Freigaben sind bewusste Betriebsentscheidungen.

## Betriebs- und Rechtsabnahme vor echten Daten

Die folgende Liste nennt noch zu bestätigende Betriebspflichten. Sie behauptet keine bereits erfolgte DSGVO-/GoBD-/Steuerberaterfreigabe.

| Bereich | Erforderliche Entscheidung bzw. tatsächlicher Nachweis |
|---|---|
| Verantwortlichkeit | Verantwortlicher Betrieb, Datenschutzkontakt, Zwecke/Rechtsgrundlagen und Verzeichnis der Verarbeitungstätigkeiten festlegen. |
| Auftragsverarbeitung | Hetzner, Google, Microsoft/OneDrive, Sevdesk sowie sonstige tatsächlich eingesetzte Anbieter/Unterauftragnehmer und Übermittlungswege prüfen; AV-Verträge und Datenschutzhinweise aktualisieren. Keine automatische externe KI-Verarbeitung von Planoriginalen aktivieren. |
| Informationspflichten/Übermittlung | Informationen für Kunden, Anfragende und Beschäftigte, erforderliche Rechtsgrundlagen/Einwilligungen und ggf. Drittland-/Unterauftragnehmerprüfung festlegen. Ein Providername oder EU-Server allein ersetzt diese Prüfung nicht. |
| Datenminimierung | Rollen, Projektzuweisung, Dokumentklassen, Exportberechtigte und eingeschränkte Gerätescopes mit echten Betriebsrollen abnehmen; HR-/Finanzdaten nicht in allgemeine Fotos/Planquellen kopieren. |
| Betroffenenrechte | Auskunft ist ein expliziter Prüfexport mit benannten Grenzen. Löschung verbundener Kontakte darf wegen Originalen/Belegen/History blockieren; keine pauschale Voll-Löschbestätigung. Aufbewahrung und Sperrung mit Rechtsgrund prüfen. |
| Fristen/Berichtigung/Übertragbarkeit | Zuständigkeit und Fristen für Auskunft, Berichtigung, Einschränkung, Widerspruch und ggf. Datenübertragbarkeit festlegen; Identität und vollständige Quellensuche prüfen. Auch externe Mail-/Cloudbestände und lokale Geräte berücksichtigen. |
| Lösch-/Aufbewahrungskonzept | Fristen je Dokumentklasse, Anhänge, History, Exporte, Logs, lokale Caches und Backups dokumentieren; gesetzliche Aufbewahrung und datensparsame Sperrung unterscheiden. Wiederherstellung darf bestätigte Löschentscheidungen nicht aufheben. |
| Standort | Arbeitgeber-/Beschäftigteninformation und erforderliche Freigabe klären; Standard aus, nur Start/Stopp. Löschzeitpunkt und Restore-Replay testen; keine Behauptung sofortiger Entfernung aus allen historischen Backupmedien. |
| Beschäftigtenschutz/Folgenabschätzung | Ggf. Mitbestimmung und Erforderlichkeit der Beschäftigtendatenverarbeitung prüfen; Risiko-/DSFA-Schwelle einschließlich optionaler Standortfunktion bewerten. Technische Konfiguration ist keine arbeitsrechtliche Freigabe. |
| Unabhängiges Journal | Private Checkpointdatei, Schlüssel, Installationsbindung und getrennte Sicherung/Schutz vor Rückrollen einrichten. Fehlkonfiguration muss geschlossen scheitern. |
| Authentifizierung/Geräte | MFA-/Recovery-Verfahren, Kontensperrung, Geräteverlust, Keychain/Credentialstore/AES-Vault und Siebentagesfrist auf echten Geräten prüfen. Passwort-/Rollenwechsel und Projektentzug dürfen keine alten Replays freischalten. |
| Backup/Restore | Getrennte verschlüsselte Sicherung, Vault-/Checkpointschlüssel, Aufbewahrungsplan, Zuständigkeit, Wiederanlauf/RPO/RTO und regelmäßige echte Wiederherstellung dokumentieren. Restore-Finanzabgleich vor erneuter Ausgabe durchführen. |
| Sicherheitsvorfälle/TOM | Technische und organisatorische Maßnahmen, Schlüsselzugriffe/-wechsel, Patchen, Zugriffsprüfung, Vorfallsbewertung sowie gesetzliche Melde-/Benachrichtigungsprozesse und Verantwortliche dokumentieren und üben. |
| GoBD-Verfahrensdokumentation | Nummernkreise, Cutover von Sevdesk, Aussteller, Kontierung, Zeitbezug, Festschreibung, Storno, Exporte, Berechtigung, Protokollierung und Aufbewahrungsfristen durch Betrieb/Steuerberater bestätigen. Keine Rechtszertifizierung aus Hash/Trigger ableiten. |
| Steuerliche Inhalte | Steuersätze/-befreiungsgründe, Rechnungspflichtangaben, Abschlags-/Schlussrechnungslogik, Gutschrift/Storno und Beratermapping fachlich abnehmen. Prüf-CSV ist kein automatisch DATEV-konformer Export. |
| E-Rechnungsbetrieb | Java, KoSIT/XRechnung-Konfiguration, Mustang, veraPDF, Ghostscript und ICC-Profil mit festen Pins installieren; fehlende Tools blockieren die betreffende Ausgabe. Keine Werkzeugdownloads während einer Kundenanfrage. |
| Mail | Tatsächlichen Sender, TLS, Zugang, Zuständigkeit, erlaubte Antwortvorlage und Versandfreigabe einrichten. SMTP-Annahme/`unknown`/manuelle Nachweisprüfung unterscheiden; keine blinden Wiederholungen. |
| Anbieter/Hardware | Kein Livezugang allein aus einem Profilnamen ableiten. IDS/UGL/OCI/SHK/Portale/Großhändler/Lexware/DATEV und Kamera-/Barcode-/NFC-Geräte getrennt abnehmen. |
| Clients/Verteilung | Echte Windows-, iPhone- und iPadprüfungen, Kamerarechte, Uploadabbruch, Offline-Neustart und Gerätesperre durchführen. Windows-EXE/Paket bleiben unsigniert; SmartScreen-/Codesignierung ist offen. Ein unsignierter iOS-Build ist keine installierbare TestFlightfreigabe. |
| Lokales Windows | Bestehende Pythonumgebung benötigt aktualisierte Abhängigkeiten einschließlich `tzdata`; bloßes Ersetzen der EXE installiert sie nicht. Lokales SQLitepaket ist keine Alternative zur PG-Finanzausgabe. |
| Beobachtung/Änderungen | Fehlermeldungen, Aufbewahrung, Monitoring/Alarmierung, begrenzte Logdaten, Update-/Downverantwortung und Endanwenderhinweise festlegen. Phase10-Automationen bleiben aus. |

## PRs, Freigaben und nächste Nachweise

| Paket | Stand/Link |
|---|---|
| Phase0 Gap-Analyse/Zielarchitektur | [PR #2](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/pull/2), gemergt; Reviewbasis `99cee2`. |
| Gmail-/Intake-Vertragstests zuerst | [PR #3](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/pull/3), gemergt nach vollständig grünen GitHub-Prüfungen; Testcommit `6564104`, Merge `c0f7a4177b8f101147d656845fbbf48f62b1c81e`. |
| Backend/Migration/Businessdienste/Browser | [PR #4](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/pull/4). Bezieht die beschriebenen Kompatibilitäts-/Rechteänderungen ausdrücklich ein. |
| Native App/Offline | Separater PR auf Basis des Backend-Meilensteins; Link wird unmittelbar nach Anlage ergänzt. Die nativen UI-/Offlinequellen sind von Server-/Browsernachweisen getrennt. |
| Betriebsleitfaden | [Betrieb und Update](BETRIEB_BUSINESS_UPDATE.md), einschließlich SSH-Verbindung, Rollentrennung, Wiederherstellung und Werkzeug-/Versandvoraussetzungen. Dieser Bericht ersetzt keine Server-/Anbietereinrichtung. |

Vor dem produktiven Einsatz stehen der finale gemeinsame CI-Lauf am tatsächlichen Commit, die aufgeführten Plattform-/Betriebsabnahmen und die offene fachliche/rechtliche Prüfung. Für die erste Testeinführung können synthetische Anfrage→Projekt→Planung→Zeit→Dokumentationsabläufe genutzt werden; eigene echte Finanzbelege und Kundenmails werden erst im bewusst eingerichteten Betrieb freigegeben.

## Quellen und Testdateien

[BF]: ../backend/business_foundation.py
[BD]: ../backend/business_documents.py
[FZ]: ../backend/business_finance.py
[BE]: ../backend/business_einvoice.py
[SMTP]: ../backend/business_delivery.py
[BP]: ../backend/business_planning.py
[BT]: ../backend/business_time.py
[BO]: ../backend/business_operations.py
[BI]: ../backend/business_inventory.py
[BM]: ../backend/business_maintenance.py
[BA]: ../backend/business_adapters.py
[BS]: ../backend/business_schema.py
[API]: ../backend/business_api.py
[Web]: ../backend/online/web.py
[Core]: ../backend/core.py
[Restore]: ../backend/online/restore.py
[PW]: ../backend/project_workspace.py
[MAIL]: ../backend/inquiries.py
[Anhänge]: ../backend/inquiry_attachments.py
[Browser]: ../web/office/office.js
[UI-Inbox]: ../app/lib/inquiry_pages.dart
[UI-Projekt]: ../app/lib/project_workspace_page.dart
[UI-CRM]: ../app/lib/business_contacts.dart
[UI-Belege]: ../app/lib/business_documents.dart
[UI-Planung]: ../app/lib/business_planning.dart
[UI-Zeitkonto]: ../app/lib/business_workflows.dart
[UI-Zeit]: ../app/lib/business_time.dart
[UI-Medien]: ../app/lib/business_media.dart
[UI-Offline]: ../app/lib/business_offline.dart
[UI-Shell]: ../app/lib/business_shell.dart
[tBF]: ../backend/test_business_foundation.py
[tD]: ../backend/business_tests/test_documents.py
[tF]: ../backend/business_tests/test_finance.py
[tE]: ../backend/business_tests/test_einvoice.py
[tSMTP]: ../backend/business_tests/test_delivery.py
[tBilling]: ../backend/business_tests/test_time_billing.py
[tPeer]: ../backend/business_tests/test_finance_review.py
[tRestoreOutbox]: ../backend/business_tests/test_restore_outbox.py
[tCommercial]: ../backend/business_tests/test_commercial_http.py
[tP]: ../backend/test_business_planning.py
[tT]: ../backend/test_business_time.py
[tO]: ../backend/test_business_operations.py
[tI]: ../backend/test_business_inventory.py
[tM]: ../backend/test_business_maintenance.py
[tA]: ../backend/test_business_adapters.py
[tSchema]: ../backend/test_business_schema.py
[tPrivacy]: ../backend/test_business_privacy_checkpoint.py
[tRelease]: ../backend/online/test_release_business.py
[tPlanApi]: ../backend/online/test_business_planning_time_api.py
[tPlanPg]: ../backend/online/test_business_planning_time_pg.py
[tBound]: ../backend/online/test_business_boundary_review.py
[tACL]: ../backend/online/test_business_document_access_api.py
[tIntake]: ../backend/online/test_business_intake_contract.py
[tContact]: ../backend/online/test_business_contact_api.py
[tOpsApi]: ../backend/online/test_business_operations_api.py
[tWorkspace]: ../backend/online/test_workspace_api.py
[tAttachments]: ../backend/online/test_inquiry_attachments_api.py
[tPW]: ../backend/test_project_workspace.py
[tNativeD]: ../app/test/business_documents_widget_test.dart
[tNativeP]: ../app/test/business_planning_widget_test.dart
[tNativeT]: ../app/test/business_time_widget_test.dart
[tNativeF]: ../app/test/business_finance_widget_test.dart
[tNativeW]: ../app/test/business_workflows_widget_test.dart
[tOfflineT]: ../app/test/business_offline_time_test.dart
[tOfflineM]: ../app/test/business_offline_media_test.dart
[tShell]: ../app/test/business_shell_widget_test.dart
[tSession]: ../app/test/business_session_test.dart
[tDartApi]: ../app/test/business_backend_integration_test.dart
[tBrowser]: ../web/office/tests/e2e.cjs
[tPackage]: ../scripts/test_native_release.py
