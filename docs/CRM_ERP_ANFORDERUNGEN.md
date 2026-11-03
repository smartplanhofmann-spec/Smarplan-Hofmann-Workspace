# CRM/ERP: Anforderungen und Abnahmestand

Stand: 03.11.2026. Quelle ist ausschließlich das aktuelle
[Gesamtziel](../CRM_ERP_Gesamtziel.txt); technische Bestandsbelege beziehen sich
auf der integrierten Basis `420c4c7700d7543a725d787d48eef8bdb2319152` und den im
[Fortschritt](CRM_ERP_FORTSCHRITT.md) dokumentierten Änderungen vom 02.–03.11.2026. Diese Matrix erweitert den
bisherigen Produktumfang. Alte Prüfpunkte A1–O4 aus dem HERO-Bericht sind keine
Ersatzabnahme für die nachstehenden Fälle A–G.

## Status und Nachweise

- `offen`: Der konkret genannte Umfang fehlt oder ist nur teilweise vorhanden.
- `implementiert`: Der abgegrenzte Umfang ist im Quelltext vorhanden; aktuelle
  erfolgreiche Prüfung und produktive Freigabe werden damit nicht behauptet.
- `getestet`: Ein reproduzierbarer aktueller Prüflauf für genau diesen Umfang
  ist mit Quellstand, Umgebung, Ergebnis und Auslassungen verlinkt.
- `extern_blockiert`: Der genannte Nachweis benötigt einen noch fehlenden
  externen Zugang, eine Fachprüfung, Geräteprüfung oder eine ausdrückliche
  Betriebsfreigabe. Unabhängige Implementierung wird weitergeführt.
- `produktiv_freigegeben`: Die fachlichen, technischen und externen Nachweise
  liegen für einen benannten Produktivumfang vor und die Freigabe ist belegt.

`implementiert` bewertet hier einen begrenzten Baustein, nie automatisch ein
gesamtes Modul. Vorhandene Testdateien sind Referenzen, keine aktuellen
Testergebnisse. Historische Testzahlen stehen im
[Umsetzungsbericht](BERICHT_HERO_UMSETZUNG.md); neue Läufe und Änderungen im
[Fortschritt](CRM_ERP_FORTSCHRITT.md). In dieser Ausgangsmatrix ist kein
Gesamtmodul produktiv freigegeben. Die einzige aktuelle Nutzerprüfung laut
Zielvorgabe betrifft ein digital unterschriebenes Protokoll und erfüllt auch
dessen vollständige Ablaufabnahme noch nicht.

## Zielabschnitte 1–15

Zählstand 03.11.2026: 62 abgegrenzte Anforderungen, davon 24 `implementiert`,
4 `getestet`, 27 `offen`, 1 ausdrücklich teilweise und 6 `extern_blockiert`.
28/62 entsprechen **45,2 % ungewichteter Bausteinabdeckung**, einschließlich
vorhandenem Bestandsquellcode. Das ist kein gemessener Anteil am Gesamtaufwand
oder an der Produktivreife: Anforderungen unterscheiden sich stark im Umfang
und enthalten teils ausdrücklich genannte Restarbeiten. Alle sieben
durchgängigen Abnahmen A–G sind weiterhin offen.

| ID | Zielabschnitt und abgegrenzte Anforderung | Status | Beleg und fehlender Nachweis bzw. nächster Umfang |
|---|---|---|---|
| R01.01 | 1: Zusammenhängende branchenübergreifende Unternehmenssoftware ersetzt HERO und sevDesk | offen | CRM-/Projekt-/Businesskern und erster Angebotsportalabschnitt vorhanden; eigene Buchhaltung, Lohn, vollständiges Portal, KI und weitere Abläufe fehlen. Erst A–G plus externe Nachweise schließen das Ziel. |
| R01.02 | 1: Gemeinsame Daten statt doppelter Erfassung | implementiert | Kanonische Kunden-/Projekt-IDs; Übernahme in Belegsnapshots in [Foundation](../backend/business_foundation.py) und [Documents](../backend/business_documents.py). Neue Module und externe Migration noch nicht vollständig verbunden. |
| R02.01 | 2: Projektstand, Architektur, Datenhaltung und Tests aufnehmen | implementiert | [Bestandsaufnahme](CRM_ERP_BESTANDSAUFNAHME.md); Quellprüfung des vorhandenen Businessstands, historische und neue Nachweise getrennt. |
| R02.02 | 2: Funktionierende Bestandteile/Daten erhalten, kontrolliert migrieren | implementiert | [Schemajournal](../backend/business_schema.py) und [Release](../backend/online/release.py); additiver Rückkehrmodus, Integritäts-/Restoreprüfungen vorhanden. Jede neue Schemaänderung erneut prüfen. |
| R02.03 | 2: Protokoll speichern, wiederöffnen, Projektzuordnung, Export und unterschriebenen Stand schützen | getestet | Legacy-Protokollkette in [Integritätstests](../backend/test_report_integrity.py) und [PostgreSQL-Prüfung](../backend/online/test_report_integrity_pg.py): Neustart, unverändertes PDF, Projekt-/Inhaltshash, fehlendes Archiv, Rechteentzug und identischer Signatur-Retry. Keine QES oder vollständige Absicherung gegen Datenbankadministratoren; Offline-Protokollkette separat offen. |
| R03.01 | 3: Branchenneutraler Kern mit anpassbaren Artikeln, Leistungen, Vorlagen und Abläufen | implementiert | Versionierte Kataloge/Vorlagen, eigene Projektstatus und freie Projektanlage. Beliebige Custom-Felder/Workflows und branchenübergreifende Praxisprüfung noch nicht enthalten. |
| R03.02 | 3: Unternehmensbedarf erfassen und passende Module vorschlagen | getestet | [Unternehmensmodul](../backend/business_organization.py), [Anleitung](CRM_ERP_MODULE.md), Domain-/HTTP-/UI-Tests: Bedarf, automatische Vorschläge nach Mitarbeiteranlage, manuelle Wahl und Neustart. Steuerberaterbedarf ist eine Angabe, keine eingerichtete Verbindung. |
| R03.03 | 3: Sichtbarkeit, fachliche Aktivierung und Rechte getrennt; manuelle Korrektur ohne Datenlöschung | getestet | Fünf optionale Fachbereiche mit getrennter Navigation/Aktivierung; serverseitige Schreibsperre einschließlich Adapterwege; historische Lesezugriffe und berechtigter Zugang zu ausgeblendeten Bereichen; Offlinezeiten warten bei423 und synchronisieren nach Reaktivierung ohne Duplikat. [Prüfergebnisse](CRM_ERP_FORTSCHRITT.md). |
| R03.04 | 3: Unternehmensisolation aller Daten, Dateien, Suche, KI-Kontexte und Jobs | offen | Erste feste [Instanzbindung](CRM_ERP_INSTANZEN.md) mit zwei synthetischen MFA-/HTTP-Instanzen, eigenem Storage-Marker, Schlüssel-/Hostprüfung und Planimport-Worker-Grenze geprüft. Vollständige Infrastruktur-, Connector-, Suchindex- und künftige KI-Isolation sowie Provisionierung/Rotation weiter offen. |
| R03.05 | 3: Deutsche Erstversion, Erweiterbarkeit von Ländern/Währungen/Regelwerken | offen | EUR und deutsche Beleg-/Zeitfunktionen vorhanden; keine vollständige Trennung von Länder-, Steuer-, Lohn- und Meldewerken. AT/CH-Fachumsetzung bleibt außerhalb der ersten Version. |
| R04.01 | 4: Ruhige konsistente Desktop-/Mobiloberfläche | implementiert | [Browser](../web/office/office.js), [Flutter-Shell](../app/lib/business_shell.dart), [Design](../app/lib/design.dart); tatsächliche Bedienbarkeit und vollständige Modulabdeckung über G prüfen. |
| R04.02 | 4: Zentrale Unternehmensübersicht mit belegbaren Kennzahlen und Drilldown | offen | Projekt-/OP-/Zeitansichten vorhanden. Keine vollständige Unternehmensübersicht für Liquidität, Ergebnis und alle Aufgaben mit einheitlichem Datenstand. |
| R04.03 | 4: Tastatur, Touch, Fokus, Kontraste, Lade-/Leer-/Fehler-/Offlinezustände | offen | Einzelne UI-/Widget-/Browsertests vorhanden; systematische Prüfung der wichtigsten Abläufe auf allen Zielplattformen fehlt. |
| R05.01 | 5: Kunden, Ansprechpartner, Lieferanten, Anfragen, Notizen und Wiedervorlagen | implementiert | [Foundation](../backend/business_foundation.py), [Inquiries](../backend/inquiries.py), [CRM-Tests](../backend/test_business_foundation.py). Vollständige Vertriebschancen und Kommunikationshistorie nicht umfasst. |
| R05.02 | 5: Vertriebschancen und durchgängiger Kommunikationsverlauf | offen | Eingang und Projektfeed vorhanden; vollständiges Chancenmodell und kanalübergreifender Verlauf fehlen. |
| R05.03 | 5: Angebote aus Artikeln/Leistungen/Zeiten mit Preisen, Versionen, Rabatten, Steuern und Vorlagen | implementiert | [Documents](../backend/business_documents.py), [Pricing](../backend/business_pricing.py), [Kalkulationstests](../backend/business_tests/test_pricing_measurements.py), [Zeitabrechnung](../backend/business_tests/test_time_billing.py). |
| R05.04 | 5: Angebot annehmen/ablehnen und kontrolliert in Auftrag/Projekt übernehmen | offen | [Angebotsportal](CRM_ERP_PORTAL.md) implementiert unveränderliche Annahme/Ablehnung und ausdrückliche interne Übernahme in genau einen Auftragsbestätigungsentwurf. Tests prüfen Wiederholung, Konkurrenz, Rechteentzug und Rollback. Angebote benötigen im bestehenden Modell bereits ein Projekt; nachgelagerte Projektanlage bleibt offen. |
| R05.05 | 5: Kundenportal mit isolierten Angeboten, Dateiaustausch und freigegebenen Projektinformationen | offen | Eigene Kundenprincipals, Freigaben, Sitzungen, Angebotsansicht/PDF und Kundenerklärungen im [ersten Portalabschnitt](CRM_ERP_PORTAL.md) implementiert. Kunden-/Firmentrennung und Restore werden geprüft. Allgemeine Kundenkonten, Dateiaustausch und Projektfreigaben fehlen weiterhin. |
| R06.01 | 6: Projektaufgaben, Termine, Ressourcen, Budgets, Dokumente/Fotos/Berichte | implementiert | [Workspace](../backend/project_workspace.py), [Planning](../backend/business_planning.py), [Operations](../backend/business_operations.py), [Inventory](../backend/business_inventory.py). |
| R06.02 | 6: Arbeitszeiten und Materialkosten direkt dem Projekt zuordnen | implementiert | [Time](../backend/business_time.py), `BusinessInventory.cost_report`; freigegebene Zeiten und gebuchte Entnahmen mit Quellen. |
| R06.03 | 6: Fremdleistungen, sonstige Kosten, Erlöse, vollständiger Soll-Ist-/Rentabilitätsvergleich | offen | Material/Lohn sind nur ein Teil der tatsächlichen Kosten. Unternehmensgewinn und Zahlungseingang werden nicht aus Projektbelegsummen gleichgesetzt. |
| R06.04 | 6: Durchgängiger Ablauf Anfrage bis Nachbetreuung | offen | [Journeytest](../backend/online/test_business_journey_pg.py) prüft einen engeren synthetischen Ablauf; B vollständig ergänzen. |
| R07.01 | 7: Lagerorte, Artikelbewegungen, Reservierungen, Entnahmen und Rückgaben | implementiert | [Inventory](../backend/business_inventory.py), [Inventartests](../backend/test_business_inventory.py); historischen Kostenbezug erhalten. |
| R07.02 | 7: Bestellungen, Lieferstatus, Teil-/Restwareneingänge und Projektkosten konsistent verknüpfen | getestet | Abgegrenzte [Einkaufskette](CRM_ERP_EINKAUF.md): preisfreie Katalogsuche für Lagerrollen, interne Freigabe, dokumentierte externe Bestellung, positionsgebundene Teil-/Restlieferung, Lagerjournal und gewichtete Entnahmekosten. Aktuelle [Prüfergebnisse](CRM_ERP_FORTSCHRITT.md) und [Review](CRM_ERP_EINKAUF_REVIEW.md). Lieferantenschnittstelle, Original-Lieferscheinverknüpfung, Retouren und Bestelländerungen bleiben offen. |
| R07.03 | 7: Inventur und nachvollziehbare Bestandskorrektur | offen | Bewegungsjournal allein ersetzt keinen Zähl-/Differenz-/Freigabeprozess. |
| R07.04 | 7: Lieferantenkataloge mit Vorschau, Fehlern, Dubletten und bestätigter Übernahme | implementiert | Begrenzte lokale Profile in [Adapters](../backend/business_adapters.py), [Adaptertests](../backend/test_business_adapters.py). Preisgültigkeit und Einheitenabweichungen je konkretem Format noch vollständig prüfen. |
| R07.05 | 7: Konkrete direkte Lieferantenschnittstellen | extern_blockiert | Verifizierter Vertrag/Format, tatsächliche Zugänge und Partnerabnahme fehlen; Auswahl im aktuellen Gesamtziel noch offen. Vorhandene Profilnamen sind kein Zugang. |
| R07.06 | 7: Geräte, Wartungsverträge, wiederkehrende Einsätze und Historie | implementiert | [Maintenance](../backend/business_maintenance.py), [Wartungstests](../backend/test_business_maintenance.py); Fahrzeuge/Werkzeuge zusätzlich als Planungsressourcen. |
| R07.07 | 7: Vollständiger Service-/Reklamationsablauf und Betriebsmittelverwaltung | offen | Einzelne Mängel-/Wartungsfunktionen vorhanden; vollständiger Kundenservice und sämtliche erforderlichen Betriebsmitteldaten nicht belegt. |
| R08.01 | 8: Eigene Ausgangsbelege, Abschlag/Schluss, gebundene Korrekturen, OP und Mahnungen | implementiert | [Documents](../backend/business_documents.py), [Finance](../backend/business_finance.py), [Finanzreview](../backend/business_tests/test_finance_review.py). Produktive Ausgabe verlangt geschützten PostgreSQL-Dienst und bewussten Ausstellerwechsel. |
| R08.02 | 8: Manuelle Zahlungszuordnung einschließlich Teilbeträgen und Erstattungen | implementiert | `Finance.record_payment`, appendierte Zuordnungen und stabile Quellenreferenz; [Finanztests](../backend/business_tests/test_finance.py). Überzahlung/Rückabwicklung anhand konkreter Fälle erneut prüfen. |
| R08.03 | 8: Bankabgleich und benötigte Bankverbindung | offen | Kein vollständiger Bankfeed/Abgleich. Provider noch auszuwählen; Zugang/Produktivabnahme später separat. |
| R08.04 | 8: Eingangsbelege, Originale und nachvollziehbarer Review | implementiert | `Finance.capture_receipt/review_receipt`, [E-Rechnungsmodul](../backend/business_einvoice.py). Keine universelle OCR und noch kein Buchungssatz. |
| R08.05 | 8: Eigene EÜR/Doppik mit Konten, Steuern, Perioden, Abschluss und Ergebnisrechnung | teilweise; Gesamtanforderung offen | Nutzerentscheidung 02.11.2026: erste vollständige Version für Einzelunternehmen mit EÜR. E1a ergänzt [Geldkonten und belegtes EUR-Vorjournal](CRM_ERP_EUER_BETRIEB.md), Quellenbindung, Wiederholungsschutz und Restoreabgleich. E1b-1 ergänzt geprüfte zusätzliche Rechnungszuordnungen mit gemeinsamer OP-/Zahlungsprojektion und erweitertem Restoreabgleich. E1b-2 ergänzt dokumentarische Netto-/ausgewiesene Steueranteile mit gemeinsamen Gruppenresten und exakter Centrechnung. Noch keine Steuerberechnung oder vollständige EÜR; Umsatzsteuerstatus separat offen. [Erstattungsursprünge E1b-3a](CRM_ERP_EUER_E1B3A_API.md) sind implementiert und [geprüft](CRM_ERP_PRUEFNACHWEIS_E1B3A.json); ganze bestehende Erstattungszuordnungen erhalten ausdrückliche Ursprünge und deren genaue Netto-/Steuercents, ohne Gruppenreste freizugeben oder OP doppelt zu verändern. [Restkapazitätsabschnitte E1b-3b](CRM_ERP_EUER_E1B3B_API.md) sind implementiert und im beschriebenen Umfang geprüft, siehe [Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_E1B3B.json). Erstattungsursprünge für neue Komponentenlose bleiben bis E1b-3c ungeklärt. Perioden/Korrekturen und Beraterpaket folgen im [Journalplan](CRM_ERP_EUER_PLAN.md). Doppik/weitere Rechtsformen separat planen. |
| R08.06 | 8: E-Rechnungserzeugung, genaue Geld-/Steuerrechnung und unveränderliche Archive | implementiert | Decimal-/Snapshot-/Archivlogik, KoSIT-/Mustang-/veraPDF-Anbindung und [E-Rechnungstests](../backend/business_tests/test_einvoice.py). Aktuelle gesetzliche Profile und konkrete Geschäftsfälle separat validieren. |
| R08.07 | 8: Steuerberaterübergabe, optionaler DATEV-/Behördenweg und Jahresabschluss | offen | Prüf-CSV und Artefaktexport vorhanden; kein nativ abgenommener DATEV-Import, keine Behördenübermittlung und kein vollständiger Jahresabschluss. |
| R08.08 | 8: Fachliche Abnahme, Aufbewahrung/Verfahrensdokumentation und produktiver Ausstellerwechsel | extern_blockiert | Zuständige Fachprüfung und betriebliche Freigabe für benannte Fälle fehlen; Entwicklung und synthetische Tests bleiben möglich. |
| R09.01 | 9: Mitarbeiterprofile, Arbeitszeitmodelle, Zeitkonto und Abwesenheiten | implementiert | [Planning](../backend/business_planning.py), [Time](../backend/business_time.py); serverseitige Personalrechte vorhanden. Native Personalpflege und sämtliche Spezialfälle nicht vollständig. |
| R09.02 | 9: Personalunterlagen und Reisekosten | offen | Keine vollständige Personalakten-/Reisekostenfunktion. |
| R09.03 | 9: Deutsche Lohnabrechnung mit Fallgrenzen, Historie, Korrektur und Dokumenten | offen | Nutzerentscheidung 02.11.2026: reguläre Mitarbeiter und Minijobs. Stunden-/Kostensätze und Zeitexport sind keine Payroll. Reproduzierbares Regelwerk, Jahresversion, fachliche Referenzfälle und Erkennung nicht unterstützter Fälle fehlen. |
| R09.04 | 9: Lohnreferenzfälle und produktive Meldeverfahren | extern_blockiert | Fachlich geprüfte Referenzen, notwendige Zugänge/Systemprüfungen/Dienstleister und Freigaben noch zu bestimmen. Entwicklungssimulation ist keine Zulassung. |
| R10.01 | 10: Zentraler und funktionsbezogener KI-Assistent mit Sprachbedienung | offen | Kein allgemeiner Assistent und keine Sprachintegration im untersuchten Kern. Anbieter, Kosten und Datenverarbeitung noch festzulegen. |
| R10.02 | 10: Unternehmensregeln mit Auslöser/Bedingung, automatisch/freizugebend/verboten | offen | Begrenzte Versandfreigaben und Antwortvorlagen existieren; keine allgemeine serverseitige Regelengine. |
| R10.03 | 10: Rechte, Datenbasis, Audit und Wiederholungsschutz für KI-Aktionen | offen | Wiederholsichere Fach-APIs sind Bausteine. KI-Werkzeuge, Kontextisolation und Manipulationsfälle nach E fehlen. |
| R11.01 | 11: Browser und native Windows-/iPhone-Quellen | implementiert | [Browser](../web/office/README.md), [App](../app/lib/main.dart), bestehende Plattform-/Buildgerüste. Installierbarkeit nicht aus Quellcode ableiten. |
| R11.02 | 11: Geschützte Offlinezeiten, Fotos und vorbereitete Projektarbeit | implementiert | [Business-Outbox](../app/lib/business_offline.dart), [Vault](../app/lib/offline_vault.dart), [Offline-API](../backend/business_api.py). Gerätetokenrechte, Konflikte und verlorene Antworten erneut prüfen. |
| R11.03 | 11: Offlineberichte/Protokolle mit vollständigem synchronisiertem Ablauf | offen | Online-Signatur und Teile der Offlineprojektmappe vorhanden; durchgängige Offline-Protokollkette nicht nachgewiesen. |
| R11.04 | 11: Gemeinsamer Serverkern, Backup/Restore, Update und Betriebsanleitungen | implementiert | [Betrieb](BETRIEB_BUSINESS_UPDATE.md), [Release](../backend/online/release.py), [Restore](../backend/online/restore.py). Neuer Gesamtumfang benötigt erweiterte Abnahme F. |
| R11.05 | 11: Neue Kundenunternehmen einrichten, exportieren und geordnet verlassen | offen | Kein vollständiger Unternehmenseinrichtungs-/Gesamtexport-/Ausstiegsprozess. |
| R11.06 | 11: Tatsächliche Windows-/iPhone-Installation, Updates, Gerätefunktionen und Verteilung | extern_blockiert | Reale Zielgeräte und verfügbare Signier-/Verteilwege prüfen. Cloud-/Simulatorprüfungen ersetzen diese Abnahme nicht. Keine neuen kostenpflichtigen Dienste implizit bestellen. |
| R12.01 | 12: Erweiterbare Import-/Exportadapter und vorhandene Providergrenzen | implementiert | [Adapters](../backend/business_adapters.py), [Integrationsvertrag](../backend/online/INTEGRATIONEN.md). Nur konkret unterstützte Profile bewerten. |
| R12.02 | 12: HERO-/sevDesk-Migration mit Vorschau, Zuordnung, Dubletten, Fehlern und Gesamtabgleich | offen | Bestehende lesende Verknüpfungen sind keine vollständige Datenmigration. Originalsysteme bis erfolgreichem Abgleich erhalten. |
| R12.03 | 12: Verifizierte offizielle Export-/API-Wege und Testzugänge | extern_blockiert | Je ausgewähltem Anbieter tatsächlichen Exportumfang, Authentifizierung und Zugänge belegen; keine API-Funktionen erfinden. |
| R13.01 | 13: Frische Identitäts-/Rollen-/Projekt-/Dokumentrechte, Online-MFA und enge Gerätescopes | implementiert | [Auth](../backend/online/auth.py), [Foundation](../backend/business_foundation.py), [Boundarytests](../backend/online/test_business_boundary_review.py). Unternehmenszugehörigkeit siehe R03.04. |
| R13.02 | 13: Eingabe-/Uploadprüfung, verschlüsselte Offlinehaltung und Restore-Schutz | implementiert | Bestehende Hash-/Größen-/Dateiprüfungen, Vault und Privacy-Checkpoints. Kein Beleg absoluter Sicherheit. |
| R13.03 | 13: Vollständige Sicherheitsanalyse, Abhängigkeiten, Schwachstellenpflege und Vorfallsverfahren | offen | Einzelne technische Schutzmaßnahmen/Lockdateien vorhanden; aktuelle produktweite Nachweisliste und vollständiger Prozess fehlen. |
| R13.04 | 13: Datenschutzrechte und Aufbewahrung über alle Datenarten/Backups/Empfänger | offen | Kontaktprüfung, Teil-Exporte und Lösch-Checkpoint sind Bausteine. Gesamtinventar, Fristen, Auskunft/Export und zulässige Löschung weiterführen. |
| R13.05 | 13: Aktuelle offizielle Anforderungen zu DSGVO, Steuer/E-Rechnung, Lohn, Signatur, KI-Verordnung und CRA | offen | Geltungsbereich und Quellenstand je Produktfunktion ermitteln; historische Providerquellen ersetzen diese Prüfung nicht. |
| R13.06 | 13: Unabhängiger Sicherheitstest, Fach-/Rechts-/Betriebsnachweise | extern_blockiert | Unabhängige Prüfung und Nachprüfung sowie zuständige fachliche/rechtliche Freigaben fehlen; interne Tests können sie vorbereiten. |
| R14.01 | 14: Vollständige reproduzierbare Abnahme A–G | offen | Siehe nächste Tabelle. Vorhandene Teiltests nicht als Gesamtabschluss zählen. |
| R15.01 | 15: Priorisierter Plan, Entscheidungen, Tests und nächste Schritte im Repo | implementiert | [Bestand](CRM_ERP_BESTANDSAUFNAHME.md), diese Matrix, [Plan](CRM_ERP_UMSETZUNGSPLAN.md), [Fortschritt](CRM_ERP_FORTSCHRITT.md); nach jedem Abschnitt aktualisieren. |
| R15.02 | 15: Vollständiger Lieferumfang aus Quellcode, Installation, Migration, Nutzung, Ergebnissen und Grenzen | offen | Bestehende Dokumente weiterverwenden; vollständiges Ziel erst nach den genannten Endnachweisen erreicht. |

## Durchgängige Abnahmefälle A–G

Alle Fälle bleiben insgesamt `offen`. Die Testschritte sind Abnahmeziele, keine
Beschreibung bereits erfolgreich ausgeführter Prüfläufe.

| ID | Status | Reproduzierbar nachzuweisender Ablauf | Vorhandene Grundlage und fehlende Teile |
|---|---|---|---|
| A | offen | Einzelunternehmen ohne Personalansicht einrichten; Mitarbeiter ergänzen; Vorschlag korrigieren; zweite Firma und eingeschränkte Rolle über UI/API/Suche/Export/Dateien/Jobs abweisen | Bedarfs-/Modulmodell, manuelle Wahl, historische Lesbarkeit und erste Zwei-Instanzen-HTTP-/Dateiprüfungen umgesetzt und getestet. Umfassende produktive Prozess-/DB-Rollen-/Worker-/Such-/KI-Kontexttrennung weiter offen; noch keine vollständige Abnahme A. |
| B | offen | Kunde → Katalog → Angebot → Portalannahme → Auftrag/Projekt → Einsatz → Offlinezeiten/Fotos → Protokoll → Sync → Rechnung → Zahlung; Kosten/Erlöse und Wiederholung prüfen | [PostgreSQL-Journey](../backend/online/test_business_journey_pg.py), Kalkulation, Zeiten, Fotos und Belege vorhanden. Getrennte Portalannahme und interne Übernahme ergänzen den Ablauf im bestehenden Projekt; [Portal-PG-Prüfung](../backend/online/test_postgres_portal_integration.py). Projektanlage nach Annahme, Offline-Protokollkette und vollständige Kosten-/Finanzabstimmung bleiben offen. |
| C | offen | Projektbedarf bestellen; Teil- und Restlieferung gegen Bestellposition buchen; Bestand/Entnahme/Kosten abstimmen; Wartung für das Gerät mit Historie anlegen | [HTTP-Teilablauf](../backend/online/test_purchasing_journey.py) prüft dokumentierte externe Bestellung, Teil-/Restlieferung, Bestand, gewichtete Projektkosten, Gerätewartung mit signiertem Bericht und Neustart. Tatsächliche Bestellauslösung und strukturierte Gerätebindung an Bestell-/Entnahmeposition fehlen; die derzeitige Gerätezuordnung nutzt Projekt und Notizreferenz. Vollständige Abnahme C bleibt offen. |
| D | offen | Mitarbeiter, Zeiten, Abwesenheit und Reisekosten verarbeiten; fachliche Lohnreferenzen; nachvollziehbare Korrektur; Export-/Meldestatus prüfen | Mitarbeiter/Zeit/Abwesenheit und begründete Korrekturen vorhanden. Reisekosten, Payroll und externe Fach-/Meldenachweise fehlen. |
| E | offen | KI nennt belegbare Datenbasis, plant Aktion; Regel erzwingt Automatik/Freigabe/Ablehnung; Manipulation, fremde Daten, Rechteentzug und Wiederholung prüfen | Fachrechte und Receipts vorhanden; KI-Assistent, Regelengine und KI-spezifische Trennung/Tests fehlen. |
| F | offen | Beide vorgesehenen Betriebsvarianten installieren/aktualisieren, Backup wiederherstellen, Daten/Beziehungen abgleichen; Offlinekonflikt, Abbruch und fehlenden Providerzugang prüfen | Release-/Restore-/Privacyverfahren und Teiltests vorhanden. Vollständige neue Produktdaten sowie reale Betriebs-/Geräteverfahren erneut abnehmen. |
| G | offen | Wichtigste Abläufe im Browser, unter Windows und auf iPhone bedienen; lesbare Navigation/Fokus/Touch und ehrliche Speicher-/Sync-/Fehler-/Leer-/Rechtestände prüfen | Browser-/Flutteroberflächen und Tests vorhanden. Vollständige Fachoberflächen, reale Geräte und systematische Bedienabnahme fehlen. |

## Echte Abhängigkeiten und offene Entscheidungen

Die Implementierung wird an unabhängigen Teilen fortgesetzt, auch wenn einzelne
externe Nachweise fehlen. Folgende Entscheidungen sind vor der jeweils
abhängigen produktiven Nutzung erforderlich:

| Bezug | Noch festzulegen oder nachzuweisen |
|---|---|
| R03/R04 | Endgültiger Produktname, Branding und Akzentfarbe; neutrale großzügige Gestaltung ist bereits vorgegeben. |
| R07/R12 | Konkrete Lieferanten, Katalogformate und direkte Schnittstellen; historische Profile sind Vorschläge. |
| R08/R09 | Festgelegt: Einzelunternehmen mit EÜR; reguläre Mitarbeiter und Minijobs. Noch zu konkretisieren: Steuer-/Abrechnungsfälle innerhalb dieses Umfangs, zuständige Fachprüfung und Meldewege. |
| R08/R12 | Zuerst benötigte Bank-, Kalender-, E-Mail- und Ablageanbieter; tatsächliche Zugänge und Testumgebungen. |
| R10 | KI-Anbieter, zulässige Datenflüsse, Kosten und Sprachverarbeitung; keine ungefragte externe Übertragung. |
| R11 | App-Verteilung, verfügbare Zielgeräte, Serverbetrieb/Hosting, Wiederanlaufziele und Verantwortliche. |
| R13 | Unabhängiger Sicherheitstest, anwendbare Rechtsnachweise, Auftragsverarbeitung und gegebenenfalls Folgenabschätzung. |
| R15 | Verkaufs-/Preismodell und externe Verpflichtungen vor deren Umsetzung. |

Echte Zahlungen, Nachrichten, Bestellungen, Meldungen, produktive Migrationen und
öffentliche Veröffentlichungen folgen nicht automatisch aus diesem Ziel.
Entwicklungstests verwenden kontrollierte synthetische Daten. Die vorhandene
Finanzsperre und der dokumentierte Ausstellerwechsel bleiben bis zur
ausdrücklich autorisierten Betriebsumstellung erhalten.
