# CRM/ERP: Anforderungen und Abnahmestand

Der aktuelle [Projekt-Integrationsstand 0.13.0](CRM_ERP_PROJEKTBETRIEB_INTEGRATION_2026-11-04.md)
verbindet Kunden, Belege, Material, Zeiten und Navigation mit eigenen Prüfnachweisen.
Das [Windowsprogramm 0.13.0](CRM_ERP_PROJEKT_BUILD_FREIGABE_2026-11-04.md) ist
tatsächlich gebaut und geprüft. Ein unsignierter iPhone-Gerätebuild ist ebenfalls erfolgreich; Signierung,
Serverabgleich und Geräteabnahme bleiben als Auslieferungsschritte offen.

**Gesamtbeauftragung erneut bestätigt am 08.11.2026:** Die gesamte Software
gemäß Originalziel fertigstellen. Der zuerst priorisierte Projektbetrieb
bleibt ein Lieferabschnitt; Buchhaltung und Lohn werden nicht aus dem Endziel
gestrichen. Der [zentrale Arbeitsstand](CRM_ERP_ARBEITSSTAND.md) dokumentiert
wiederhergestellten Quellstand, neue Arbeiten und tatsächliche externe
Voraussetzungen. Historische Lohn-/Buchhaltungsnachweise bleiben erhalten.

**Fortsetzung 10.11.2026:** [Source5-Zahlungstage V3](CRM_ERP_SOURCE5_ZAHLUNGSTAGE_V3_2026-11-10.md)
ergänzen für R09/D belegte spätere positive Nettozahlungen im Jahr 2026, ohne
ursprüngliche Bruttoereignisse, frühere Zahlungen oder Reisekosten umzudatieren.
Der neue Vertrag besitzt eigene Backend-, Browser-, App- und tatsächliche
PostgreSQL-/Restoreprüfungen. V1/V2 und historische Rechenmodule bleiben erhalten.
Dies ist ein begrenzter zusätzlicher Prüfumfang; R09 und D bleiben bis zur
vollständigen Fach-/Gesamtabnahme offen. Der [Windows-Nachlauf](CRM_ERP_WINDOWS_PAKETQUELLEN_2026-11-10.md)
bestätigt inzwischen tatsächlich Build, Paketierung und Sicherung/Restore auf
Windows; er ersetzt keine reale Geräteprüfung und keine Gesamtfreigabe.

**Bedienanpassung vom 06.11.2026:** Die [Browser-Projektauswahl](CRM_ERP_BROWSER_PROJEKTAUSWAHL_2026-11-06.md)
erscheint im neuen Quellstand nur in tatsächlich projektbezogenen Bereichen.
Allgemeine Bereiche entfernen den vorherigen Projektkontext auch für
Vorbelegungen und Rechte. Lokale Browserprüfung und Auslieferungsstand sind
getrennt dokumentiert; die neue Serverinstallation ist noch nicht bestätigt.

Stand: 09.11.2026. Quelle ist das unveränderte
[Gesamtziel](../CRM_ERP_Gesamtziel.txt). Die integrierte Basis `4c2f008` und
nachfolgende Änderungen sind im [Fortschritt](CRM_ERP_FORTSCHRITT.md)
mit ihren eigenen Prüfnachweisen dokumentiert. Diese Matrix bewertet den
vereinbarten Produktumfang; alte Prüfpunkte A1–O4 aus dem HERO-Bericht ersetzen
keine der nachstehenden Gesamtabnahmen A–G.

Zusätzlicher geprüfter Teilumfang 10.11.: Die [V4-Netto-Rückzahlung](CRM_ERP_SOURCE5_NETTORUECKZAHLUNG_V4_2026-11-10.md)
erhält frühere positive Zahlungen und führt den wirklichen Rückfluss über
Lohnkonto, EÜR und Jahresbasis. Browser, App, MFA/PostgreSQL und Restore sind
geprüft; betragstreue Originalwiederholung und aktuelle Fachrechte bleiben nötig.
Weitere Ausgleiche auf einem bereits gemischten Rückzahlungspräfix sind noch
Codearbeit. R09/D werden dadurch nicht pauschal abgeschlossen. Der veröffentlichte
V3-Vorgänger 17978f6 ist inzwischen in sämtlichen acht eigenen Development-Jobs
und im unsignierten iPhone-Build erfolgreich; signierte Verteilung, Livebetrieb
und reale Geräte-/Fachabnahme bleiben eigene Nachweise.

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

Die Matrix enthält 62 abgegrenzte Anforderungen. Ihr aktueller Stand wird
an den konkreten Nachweisen je Zeile beurteilt. Ein Prozentwert aus gezählten
Bausteinen wäre kein verlässlicher Anteil am Gesamtaufwand oder an der
Produktivreife. Alle sieben durchgängigen Abnahmen A–G bleiben offen.
Aktuelle integrierte Ergänzungen: [Anfangssalden und Katalogoriginale](CRM_ERP_ANFANGSSALDEN_KATALOG_GESAMTPRUEFUNG_2026-11-04.md), [native Kataloghistorie](CRM_ERP_KATALOG_NATIVE_2026-11-04.md). Der [gemeinsam geprüfte Integrationsstand für Jahresvortrag und V2-Archive](CRM_ERP_JAHRESVORTRAG_GESAMTPRUEFUNG_2026-11-04.md) ergänzt den technisch integrierten Stand mit endgültiger Quellbindung und archivierten Prüfläufen. Ältere Modulnachweise bleiben im [Stand vom 03.11.2026](CRM_ERP_INTEGRATIONSSTAND_2026-11-03.md) nachlesbar.

Die Anforderungen werden anhand der konkreten Nachweise je Zeile bewertet.
Die unterschiedlich großen Zeilen ergeben keine belastbare Gesamtprozentzahl.
Die neuen gemeinsamen
Nachweise für Offlinebindung, Lohnfälle und Browserzeitabrechnung stehen im
[Integrationsbericht vom 09.11.](CRM_ERP_GESAMTINTEGRATION_2026-11-09.md).
[Native Assistenten-/Sprachkorrekturen
und technische Isolationsnachweise](CRM_ERP_UNTERNEHMENSISOLATION_GESAMTPRUEFUNG_2026-11-04.md)
sind inzwischen integriert. Die [native Service-/Betriebsmittelkorrektur](CRM_ERP_SERVICE_BETRIEBSMITTEL_GESAMTPRUEFUNG_2026-11-04.md)
ist ebenfalls mit eigenen Nachweisen integriert. Private Lohnvergleichs-/
Quellenpakete, produktive Isolations- und Gesamtabnahmen bleiben offen.

| ID | Zielabschnitt und abgegrenzte Anforderung | Status | Beleg und fehlender Nachweis bzw. nächster Umfang |
|---|---|---|---|
| R01.01 | 1: Zusammenhängende branchenübergreifende Unternehmenssoftware ersetzt HERO und sevDesk | offen | Zusammenhängende CRM-/Projekt-/Einkaufs-/Service-, Kundenportal-, Wirtschaftlichkeits-, Personal-/Lohn-, Assistenten- und EÜR-Abläufe sind vorhanden und abgegrenzt geprüft. Bankabgleich, Betriebsmittel, Einkaufsänderungen und isolierte Unternehmensbereitstellung besitzen eigene Nachweise. Historische offene Finanzposten und unternehmensweite Ereignisregeln sind mit beiden Clients abgegrenzt integriert. Das ergänzende Jahresoriginalpaket ist mit beiden Clients abgegrenzt integriert. Belegte Jahreswerte und V2-Archivanschluss sind im aktuellen [Integrationsstand technisch integriert](CRM_ERP_JAHRESVORTRAG_GESAMTPRUEFUNG_2026-11-04.md); weitere Lohn-/Steuerfälle und Betriebsnachweise werden vervollständigt. Erst A–G plus externe Nachweise schließen das Ziel. |
| R01.02 | 1: Gemeinsame Daten statt doppelter Erfassung | implementiert | Kanonische Kunden-/Projekt-IDs; Übernahme in Belegsnapshots in [Foundation](../backend/business_foundation.py) und [Documents](../backend/business_documents.py). Neue Module und externe Migration noch nicht vollständig verbunden. |
| R02.01 | 2: Projektstand, Architektur, Datenhaltung und Tests aufnehmen | implementiert | [Bestandsaufnahme](CRM_ERP_BESTANDSAUFNAHME.md); Quellprüfung des vorhandenen Businessstands, historische und neue Nachweise getrennt. |
| R02.02 | 2: Funktionierende Bestandteile/Daten erhalten, kontrolliert migrieren | implementiert | [Schemajournal](../backend/business_schema.py) und [Release](../backend/online/release.py); additiver Rückkehrmodus, Integritäts-/Restoreprüfungen vorhanden. Jede neue Schemaänderung erneut prüfen. |
| R02.03 | 2: Protokoll speichern, wiederöffnen, Projektzuordnung, Export und unterschriebenen Stand schützen | getestet | Legacy-Protokollkette in [Integritätstests](../backend/test_report_integrity.py) und [PostgreSQL-Prüfung](../backend/online/test_report_integrity_pg.py): Neustart, unverändertes PDF, Projekt-/Inhaltshash, fehlendes Archiv, Rechteentzug und identischer Signatur-Retry. Keine QES oder vollständige Absicherung gegen Datenbankadministratoren; Offline-Protokollkette separat offen. |
| R03.01 | 3: Branchenneutraler Kern mit anpassbaren Artikeln, Leistungen, Vorlagen und Abläufen | implementiert | Versionierte Kataloge/Vorlagen, eigene Projektstatus und freie Projektanlage. [Zusatzfelder](CRM_ERP_ZUSATZFELDER.md) für Kontakte, Projekte und Geräte mit Text/Zahl/Datum/Auswahl/Bool, Pflichtangaben, archivierten Auswahlwerten, Rechteprüfung und unveränderter Historie sind durchgängig getestet. Beliebige weitere Entitäten, Formeländerungen an Kern-/Steuerfeldern und branchenübergreifende Praxisabnahme werden damit nicht behauptet. |
| R03.02 | 3: Unternehmensbedarf erfassen und passende Module vorschlagen | getestet | [Unternehmensmodul](../backend/business_organization.py), [Anleitung](CRM_ERP_MODULE.md), Domain-/HTTP-/UI-Tests: Bedarf, automatische Vorschläge nach Mitarbeiteranlage, manuelle Wahl und Neustart. Steuerberaterbedarf ist eine Angabe, keine eingerichtete Verbindung. |
| R03.03 | 3: Sichtbarkeit, fachliche Aktivierung und Rechte getrennt; manuelle Korrektur ohne Datenlöschung | getestet | Fünf optionale Fachbereiche mit getrennter Navigation/Aktivierung; serverseitige Schreibsperre einschließlich Adapterwege; historische Lesezugriffe und berechtigter Zugang zu ausgeblendeten Bereichen; Offlinezeiten warten bei423 und synchronisieren nach Reaktivierung ohne Duplikat. [Prüfergebnisse](CRM_ERP_FORTSCHRITT.md). |
| R03.04 | 3: Unternehmensisolation aller Daten, Dateien, Suche, KI-Kontexte und Jobs | offen | Feste [Instanzbindung](CRM_ERP_INSTANZEN.md) mit zwei synthetischen MFA-/HTTP-Instanzen, eigenem Storage-Marker, Schlüssel-/Hostprüfung und Planimport-Worker-Grenze geprüft. [Additive Provisionierung](CRM_ERP_PROVISIONIERUNG.md) mit getrennten PostgreSQL-Rollen, Ablagen und Prozessen: drei tatsächliche Zweifirmen-/MFA-/Restorefälle, ein Test mit getrennten Linux-UIDs, 29 Domain-/Guardfälle und vier bestehende Release-/Restorefälle bestanden. Vollständige produktive Hostinstallation, Schlüsselrotation und Betriebsabnahme bleiben separat. Aktuelle Zwei-Firmen-HTTP-/Parsernachweise und native Kontextkorrekturen sind [gemeinsam geprüft](CRM_ERP_UNTERNEHMENSISOLATION_GESAMTPRUEFUNG_2026-11-04.md); produktive und externe Sicherheitsnachweise bleiben offen. |
| R03.05 | 3: Deutsche Erstversion, Erweiterbarkeit von Ländern/Währungen/Regelwerken | offen | EUR und deutsche Beleg-/Zeitfunktionen vorhanden; keine vollständige Trennung von Länder-, Steuer-, Lohn- und Meldewerken. AT/CH-Fachumsetzung bleibt außerhalb der ersten Version. Das neue [fachbereichsgebundene Länder-/Währungsrouting für Rechnungsaussteller](CRM_ERP_AUSSTELLER_LAENDERGRENZE_2026-11-09.md) schließt eine tatsächliche Fremdland-Freigabelücke und zeigt den Umfang in beiden Clients. Andere Steuer-, Lohn- und Meldewerke sind damit nicht vollständig getrennt. |
| R04.01 | 4: Ruhige konsistente Desktop-/Mobiloberfläche | implementiert | [Browser](../web/office/office.js), [Flutter-Shell](../app/lib/business_shell.dart), [Design](../app/lib/design.dart); tatsächliche Bedienbarkeit und vollständige Modulabdeckung über G prüfen. |
| R04.02 | 4: Zentrale Unternehmensübersicht mit belegbaren Kennzahlen und Drilldown | getestet | [Unternehmensübersicht](CRM_ERP_UNTERNEHMENSUEBERSICHT.md): Aufgaben/Termine, Rechnungsumsatz, Kosten, Zahlungen, offene Salden und EÜR aus frischen Fachquellen. Browser-/Flutter-Drilldown, private Bereiche, mobile Darstellung, fehlende Anfangsbestände und unvollständige Zahlen geprüft. Erfasste Daten sind kein Nachweis vollständiger betrieblicher Erfassung.  Zusatzprüfung des [gemeinsamen EÜR-Leseabschnitts](CRM_ERP_UEBERSICHT_LESEKETTE_2026.md): identische Originalwerte, frische Quellen und Rechte, reale PG-/Restorewege; alle 17 vollständigen lokalen Browserabläufe bestehen. |
| R04.03 | 4: Tastatur, Touch, Fokus, Kontraste, Lade-/Leer-/Fehler-/Offlinezustände | offen | [Browserprüfung](CRM_ERP_BEDIENBARKEIT.md) über 18 gerenderte Ansichten mit axe 4.14.0, Dialogtastatur und mobilen Überlaufprüfungen bestanden; Kontrast-/Fokusfehler behoben. Sämtliche Fachdialoge, menschliche Screenreader-/Zoomabnahme und tatsächliche Windows-/iPhone-Prüfung fehlen noch. |
| R05.01 | 5: Kunden, Ansprechpartner, Lieferanten, Anfragen, Notizen und Wiedervorlagen | implementiert | [Foundation](../backend/business_foundation.py), [Inquiries](../backend/inquiries.py), [CRM-Tests](../backend/test_business_foundation.py). Vertriebschancen und explizite Aktivitäten sind separat ergänzt (R05.02); reale kanalübergreifende Kommunikation bleibt abhängig von konkreten Anschlüssen. |
| R05.02 | 5: Vertriebschancen und durchgängiger Kommunikationsverlauf | getestet | [Vertriebschancen](CRM_ERP_VERTRIEB.md): Kunde/Anfrage, Phase, Prognose, Wiedervorlage, Aktivitäten/Korrekturen und kanonische Übernahme. Neuer [gemeinsamer Kunden-/Projektverlauf](CRM_ERP_KOMMUNIKATIONSVERLAUF.md) aus sechs bestehenden Fachquellen mit Quellrechten, Originalen, Snapshotseiten, Suche/Filtern, Browser und nativer App; tatsächliche PostgreSQL-/MFA-/Restoreprüfung. Vollständige externe Kanalintegration und reale Geräte-/Betriebsabnahme bleiben offen. |
| R05.03 | 5: Angebote aus Artikeln/Leistungen/Zeiten mit Preisen, Versionen, Rabatten, Steuern und Vorlagen | getestet | [Documents](../backend/business_documents.py), [Pricing](../backend/business_pricing.py), [Kalkulationstests](../backend/business_tests/test_pricing_measurements.py), [Zeitabrechnung](../backend/business_tests/test_time_billing.py). Die zuvor fehlende [Browserauswahl freigegebener Projektzeiten](CRM_ERP_ZEITABRECHNUNG_BROWSER_2026.md) ist jetzt ergänzt. Stundenpreis, Zeit-/Steuerbindung, freie und Katalogpositionen, unveränderte Wiederholung, Quellenänderung und Doppelabrechnungsschutz sind im tatsächlichen PG-/MFA-/Chromiumablauf bis zur ausgestellten Rechnung und PDF geprüft; der [zweite gemeinsame Integrationslauf](CRM_ERP_ZEITABRECHNUNG_INTEGRATION_2026-11-09.md) bestätigt beide Zeitbindungen und Integritätsprüfer. Die frühere pauschale Browserstatusangabe wurde korrigiert und durch tatsächliche Nachweise ersetzt. |
| R05.04 | 5: Angebot annehmen/ablehnen und kontrolliert in Auftrag/Projekt übernehmen | getestet | [Angebotsportal](CRM_ERP_PORTAL.md) implementiert unveränderliche Annahme/Ablehnung und ausdrückliche interne Übernahme in genau einen Auftragsbestätigungsentwurf. Tests prüfen Wiederholung, Konkurrenz, Rechteentzug und Rollback. Das kanonische Projekt entsteht bereits aus der Anfrage; es bleibt bei der Annahme erhalten. Die zusammenhängende [technische B/C-Kette](CRM_ERP_KUNDENAUFTRAG.md) ist einschließlich Kosten, EÜR, Service und Restore bestanden; reale Geräte-/Fachabnahme bleibt gesondert. |
| R05.05 | 5: Kundenportal mit isolierten Angeboten, Dateiaustausch und freigegebenen Projektinformationen | getestet | [Angebotsportal](CRM_ERP_PORTAL.md) und [Kundenarbeitsbereich](CRM_ERP_KUNDENARBEITSBEREICH.md): getrennte Projektzugänge, ausdrücklich veröffentlichte Infos/Originale, geschützter Kundenupload, interne Klassifizierung/Übernahme und Widerruf. Domain/HTTP, zwei Firmen, PostgreSQL/Restore, Browser und Flutter geprüft; produktiver TLS-Betrieb/Zustellung gesondert. |
| R06.01 | 6: Projektaufgaben, Meilensteine, Termine, Ressourcen, Budgets, Dokumente/Fotos/Berichte | implementiert | [Workspace](../backend/project_workspace.py), [Planning](../backend/business_planning.py), [Operations](../backend/business_operations.py), [Inventory](../backend/business_inventory.py). Die [Browser-Projektaufgaben](CRM_ERP_PROJEKTAUFGABEN_BROWSER_2026.md) sind einschließlich Bearbeitung, Zuständigkeit, unveränderter Historie, Konflikten und verlorenen Antworten integriert und geprüft. Die eigenständigen [Projektmeilensteine](CRM_ERP_PROJEKTMEILENSTEINE_GESAMTPRUEFUNG_2026-11-09.md) sind nun in Backend, Browser und App integriert und mit tatsächlicher PostgreSQL-Migration, Konkurrenz und Restore geprüft. Frühere Aufgaben-/Terminoriginale bleiben unverändert. Neue Remote-/Geräteabnahme bleibt separat. |
| R06.02 | 6: Arbeitszeiten und Materialkosten direkt dem Projekt zuordnen | implementiert | [Time](../backend/business_time.py), `BusinessInventory.cost_report`; freigegebene Zeiten und gebuchte Entnahmen mit Quellen. Die [belegte Materialrückgabe](CRM_ERP_MATERIALRUECKGABE_INTEGRATION_2026-11-09.md) vermindert den historischen Projektkostenbezug und erhöht den Bestand, ohne einen Geldfluss zu erfinden. |
| R06.03 | 6: Fremdleistungen, sonstige Kosten, Erlöse, vollständiger Soll-Ist-/Rentabilitätsvergleich | getestet | [Projektwirtschaftlichkeit](CRM_ERP_PROJEKTWIRTSCHAFTLICHKEIT_CLIENTS.md): freigegebene Zeit/Material, geprüfte Fremdleistungen/Maschinen/sonstige Kosten, Budget/Nachträge, Belegerlöse und Zahlungen mit Quellen/Historie. Doppelte Originalkosten und veraltete Einordnungen werden erkannt. Keine automatische Aufteilung eines Originals auf mehrere Projekte; Projektnettoergebnis ist kein steuerlicher Unternehmensgewinn. |
| R06.04 | 6: Durchgängiger Ablauf Anfrage bis Nachbetreuung | getestet | [Auftragskette B/C](CRM_ERP_KUNDENAUFTRAG.md) verbindet synthetische Anfrage, Katalog, Portalannahme, Auftrag, Teil-/Restlieferung, Ausführung, Rechnung/Zahlung, belegte Projektkosten/EÜR, Inventur, Gerätewartung und Kundenservice in echtem PostgreSQL/HTTP einschließlich Dump/Restore. App-Offlinereise separat tatsächlich geprüft; vollständige reale Geräte-/Fachabnahme B bleibt offen. Die [geschützte unbestätigte Projektanlage](CRM_ERP_PROJEKTANLAGE_NEUSTART_2026.md) erhält jetzt den identischen Auftrag über vollständigen App-Neuaufbau und erneute Anmeldung; tatsächliche Geräteabnahme bleibt separat. Die [gemeinsam geprüfte Browserzeitabrechnung](CRM_ERP_ZEITABRECHNUNG_INTEGRATION_2026-11-09.md) verbindet freigegebene Zeiten mit Rechnung und PDF einschließlich tatsächlicher PostgreSQL-Bindungen und Wiederholungsschutz. |
| R07.01 | 7: Lagerorte, Artikelbewegungen, Reservierungen, Entnahmen und Rückgaben | getestet | [Inventory](../backend/business_inventory.py), [Inventartests](../backend/test_business_inventory.py). Die konkret fehlenden Browser-/App-Rückgaben sind [gemeinsam integriert](CRM_ERP_MATERIALRUECKGABE_INTEGRATION_2026-11-09.md): ursprüngliche Entnahme, zulässige Restmenge, historischer Preis, Teil-/Vollrückgabe, exakter ursprünglicher Retry, Bestand und Projektkosten. Vier echte PostgreSQL-/Konkurrenz-/Restorefälle, drei SQLite-/HTTP-Fälle und vollständiger Browserablauf einschließlich Lagerrolle ohne Finanzrechte bestehen. Gemeinsamer Nachlauf: 980 Browsermodul-, 41 native Fälle, Analyse ohne Befund. Die native App erhält offene Rückgabeaufträge auf gebundenen Servern nun im [verschlüsselten Originaljournal](CRM_ERP_ONLINEAUFTRAEGE_NEUSTART_2026-11-09.md) über Prozessneustarts. Browserpersistenz, Offline-Materialrückgabe und reale Geräteabnahme bleiben offen. Auch der [Browser erhält offene Rückgabeoriginale über Neuladen und erneute MFA](CRM_ERP_BROWSER_ORIGINALJOURNAL_VERTRAG_2026-11-09.md); frische Projektfreigabe und geprüfte Originalquittung bleiben erforderlich. |
| R07.02 | 7: Bestellungen, Lieferstatus, Teil-/Restwareneingänge und Projektkosten konsistent verknüpfen | getestet | Abgegrenzte [Einkaufskette](CRM_ERP_EINKAUF.md): preisfreie Katalogsuche für Lagerrollen, interne Freigabe, dokumentierte externe Bestellung, positionsgebundene Teil-/Restlieferung, Lagerjournal und gewichtete Entnahmekosten. Aktuelle [Prüfergebnisse](CRM_ERP_FORTSCHRITT.md) und [Review](CRM_ERP_EINKAUF_REVIEW.md). Original-Lieferschein und strukturierte Geräteherkunft sind inzwischen [ergänzt und geprüft](CRM_ERP_GERAETEHERKUNFT.md). [Lieferantenretouren und belegte Bestellmengenänderungen](CRM_ERP_EINKAUF_RETOUREN.md) sind ergänzt: eigene Lagerabgänge, Lieferpositions-/Reservierungs-/Gerätegrenzen und unveränderte historische Originale. 118 Fach-/Integrationsfälle, 96 überlappende unabhängige Regressionen und drei tatsächliche PostgreSQL-Fälle bestanden. Direkte Lieferantenschnittstellen bleiben abhängig vom verifizierten Anbieterweg. |
| R07.03 | 7: Inventur und nachvollziehbare Bestandskorrektur | getestet | [Inventur](CRM_ERP_INVENTUR.md): Zählung gegen gebundenen Lagerstand, begründete/bewertete Differenz, frische Freigabe, Bestand und historische Korrektur. Zwischenbewegungen/Reservierungen, Rechte, PostgreSQL/Restore und beide Clients geprüft. |
| R07.04 | 7: Lieferantenkataloge mit Vorschau, Fehlern, Dubletten und bestätigter Übernahme | teilweise; Gesamtanforderung offen | Originaldateien, SHA-256-Bindung, verbindliche Servervorschau, ausdrückliche Annahme, unveränderliche Historie und exakte Wiederholung sind in [Browser/Backend](CRM_ERP_ANFANGSSALDEN_KATALOG_GESAMTPRUEFUNG_2026-11-04.md) sowie [App](CRM_ERP_KATALOG_NATIVE_2026-11-04.md) geprüft. Datierte Einkaufs-/Verkaufspreise mit exakter Preisbasis, ausdrücklicher Stichtagswahl und unveränderter alter Angebotsbindung sind mit beiden Clients und den Beleg-/Bestellverbrauchern [gemeinsam geprüft](CRM_ERP_KATALOG_V2_GESAMTPRUEFUNG_2026-11-04.md). Konkrete Lieferantenformate bleiben jeweils zu verifizieren. |
| R07.05 | 7: Konkrete direkte Lieferantenschnittstellen | extern_blockiert | Verifizierter Vertrag/Format, tatsächliche Zugänge und Partnerabnahme fehlen; Auswahl im aktuellen Gesamtziel noch offen. Vorhandene Profilnamen sind kein Zugang. |
| R07.06 | 7: Geräte, Wartungsverträge, wiederkehrende Einsätze und Historie | implementiert | [Maintenance](../backend/business_maintenance.py), [Wartungstests](../backend/test_business_maintenance.py); Fahrzeuge/Werkzeuge zusätzlich als Planungsressourcen. |
| R07.07 | 7: Vollständiger Service-/Reklamationsablauf und Betriebsmittelverwaltung | offen | [Kundenservice](CRM_ERP_SERVICE_CLIENTS.md) mit Eingang, Zuständigkeit, Wiedervorlage, Disposition, signiertem Bericht, Lösung und Wiedereröffnung in beiden Clients getestet. [Betriebsmittel](CRM_ERP_BETRIEBSMITTEL_CLIENTS.md) mit kanonischer Identität, Prüfnachweisen, Ausgabe/Rückgabe, Korrektur und Nutzungssperren sind in Domain, HTTP, PostgreSQL/Restore und beiden Clients geprüft. Reale betriebliche Geräte-/Prüfnachweise bleiben gesondert. Native Sitzungs-/Dialog-/Wiederholungsgrenzen sind mit 35 Fällen und zwei tatsächlichen HTTP-Abläufen [ergänzt und geprüft](CRM_ERP_SERVICE_BETRIEBSMITTEL_GESAMTPRUEFUNG_2026-11-04.md). Der [Browser-Wartungsvertragseditor](CRM_ERP_WARTUNGSVERTRAEGE_BROWSER_2026.md) ergänzt Bearbeitung, Pause und Wiederaufnahme mit unveränderten Altbesuchen. Das [native Service-Anlagejournal](CRM_ERP_SERVICE_ANLAGEJOURNAL_2026.md) erhält die ursprüngliche Request-ID bei angenommenem POST und vollständigem App-Neustart; 24 gezielte und 45 bestehende Fälle bestehen. Gemeinsame Gesamt-App-/Geräteprüfung bleibt gesondert. |
| R08.01 | 8: Eigene Ausgangsbelege, Abschlag/Schluss, gebundene Korrekturen, OP und Mahnungen | implementiert | [Documents](../backend/business_documents.py), [Finance](../backend/business_finance.py), [Finanzreview](../backend/business_tests/test_finance_review.py). Produktive Ausgabe verlangt geschützten PostgreSQL-Dienst und bewussten Ausstellerwechsel. Die [Aussteller-Ländergrenze](CRM_ERP_AUSSTELLER_LAENDERGRENZE_2026-11-09.md) prüft Deutschland/EUR vor neuer Ausstellung und erneut nach dem Rendern. Zwei tatsächliche PostgreSQL-Fälle, unveränderte Archive, MFA und beide Clients sind geprüft; ein unterstütztes Land ist keine Ausstellerfreigabe. |
| R08.02 | 8: Manuelle Zahlungszuordnung einschließlich Teilbeträgen und Erstattungen | implementiert | `Finance.record_payment`, appendierte Zuordnungen und stabile Quellenreferenz; [Finanztests](../backend/business_tests/test_finance.py). Überzahlung/Rückabwicklung anhand konkreter Fälle erneut prüfen. |
| R08.03 | 8: Bankabgleich und benötigte Bankverbindung | offen | Eigener [belegter Bankabgleich](CRM_ERP_BANKABGLEICH_API.md) mit striktem CSV-Original, Salden, Teilzuordnungen, Korrekturen, unveränderlichen Berichten und EÜR-Periodenbindung: 17 Fach- und drei tatsächliche PostgreSQL-/MFA-/Parallelitäts-/Restore-Fälle bestanden. [Browser-/Flutterclients](CRM_ERP_BANKABGLEICH_CLIENTS.md) bestehen mit je elf Tests und echtem MFA-/HTTP-Browserablauf einschließlich Nullaktivitätsauszug, unklarer Antwort und historischen Originalen. Automatischer Feed benötigt einen ausgewählten Provider und dessen tatsächlichen Vertrag/Zugang. |
| R08.04 | 8: Eingangsbelege, Originale und nachvollziehbarer Review | getestet | [Projektbelegablauf](CRM_ERP_PROJEKTWIRTSCHAFTLICHKEIT_CLIENTS.md): Upload/Originalprüfung, Erfassung, Review, Kosteneinordnung/Korrektur und geschützte Wiederholung in Browser/Flutter über echten Transport. E-Rechnungseingang bleibt gesondert validiert; keine universelle OCR. |
| R08.05 | 8: Eigene EÜR/Doppik mit Konten, Steuern, Perioden, Abschluss und Ergebnisrechnung | teilweise; Gesamtanforderung offen | Festgelegt: Einzelunternehmen/EÜR, Regelbesteuerung Ist, Standard19%, SKR04, Netto; [Entscheidungen](CRM_ERP_ENTSCHEIDUNGEN.md). Das [eigene Journal](CRM_ERP_EUER_WORKFLOW_API.md) verbindet bestehende Geldflüsse und exakte Beleganteile mit geprüfter steuerlicher Einordnung, Vorsteuerzeitpunkt, Privatanteilen, Steuer-/Kapitalbewegungen, linearer AfA, Gegenbuchung/Berichtigung, Periodensperren und Jahresprüfpaket. [Fach-/PG-/Restore-Nachweis](CRM_ERP_EUER_WORKFLOW_PRUEFUNG.md), [Flutter](CRM_ERP_EUER_CLIENTS.md), [Browser](CRM_ERP_EUER_BROWSER.md). Abschlags-/kumulierte Schlussrechnungskomponenten sind [ergänzt und geprüft](CRM_ERP_EUER_KETTEN_ANALYSE.md). Die [Lohnzahlungsbrücke](CRM_ERP_LOHNZAHLUNGEN_EUER_CLIENTS.md) ist durchgängig geprüft; der [Bankabgleich einschließlich EÜR-Periodenbindung](CRM_ERP_BANK_EUER_INTEGRATION_PRUEFUNG.md) ist geprüft; belegte Bank-/Kassen-Anfangssalden einschließlich unbekannter und explizit nuller Werte sind [gemeinsam geprüft](CRM_ERP_ANFANGSSALDEN_KATALOG_GESAMTPRUEFUNG_2026-11-04.md). Historische lineare Anlagen einschließlich belegt fortgeführter AfA sind [gemeinsam geprüft](CRM_ERP_ANLAGEN_GESAMTPRUEFUNG_2026-11-04.md). Historische offene Kunden-/Lieferantenposten einschließlich früherer Centanteile, bereits ausgeübter Vorsteuer und späterer tatsächlicher Zahlungen sind mit beiden Clients [gemeinsam geprüft](CRM_ERP_ALTPOSTEN_GESAMTPRUEFUNG_2026-11-04.md). Belegte unterjährige Jahresvorträge sind mit beiden Clients und V2-Archivanschluss im [Integrationsstand gemeinsam geprüft](CRM_ERP_JAHRESVORTRAG_GESAMTPRUEFUNG_2026-11-04.md): ursprüngliche Journalwerte, alte Centanteile und Vorsteuerzeitpunkte bleiben erhalten; kein neuer Geldfluss oder Vorsteueranspruch. Weitere steuerliche Fälle, Gesamtbuchhaltung und Fachabnahme bleiben offen; keine amtliche Erklärung oder vollständige fachliche Freigabe. Doppik ist nicht Teil der vereinbarten ersten EÜR-Version. Die [Kilometer-Zahlungskette](CRM_ERP_KILOMETER_GESAMTINTEGRATION_2026-11-09.md) weist tatsächliche Auszahlung und Rückzahlung getrennt in der EÜR nach; eine reine Streckenkorrektur verändert alte Geldflüsse nicht. |
| R08.06 | 8: E-Rechnungserzeugung, genaue Geld-/Steuerrechnung und unveränderliche Archive | implementiert | Decimal-/Snapshot-/Archivlogik, KoSIT-/Mustang-/veraPDF-Anbindung und [E-Rechnungstests](../backend/business_tests/test_einvoice.py). Aktuelle gesetzliche Profile und konkrete Geschäftsfälle separat validieren. |
| R08.07 | 8: Steuerberaterübergabe, optionaler DATEV-/Behördenweg und Jahresabschluss | offen | Eigenes unveränderliches EÜR-Jahresprüfpaket mit Journal, Quellenmanifest, CSV/JSON und Prüfsummen vorhanden. Das zusätzliche ZIP mit aufgelösten Originalen und beiden Clients ist [gemeinsam geprüft](CRM_ERP_JAHRESPAKET_GESAMTPRUEFUNG_2026-11-04.md); der [V2-Anschluss für belegte Jahresvorträge](CRM_ERP_JAHRESVORTRAG_GESAMTPRUEFUNG_2026-11-04.md) ist im Integrationsstand technisch integriert und erhält alte V1-Archive unverändert. Ein separat vertrauenswürdiger Archivhash bleibt nötig, kein intrinsischer Vollständigkeitsbeweis aller historischen Abhängigkeiten. Kein als DATEV-Import ausgegebenes Eigenformat, keine Behördenübermittlung oder gesonderte fachliche Jahresfreigabe. [Workflow](CRM_ERP_EUER_WORKFLOW_API.md). |
| R08.08 | 8: Fachliche Abnahme, Aufbewahrung/Verfahrensdokumentation und produktiver Ausstellerwechsel | extern_blockiert | Zuständige Fachprüfung und betriebliche Freigabe für benannte Fälle fehlen; Entwicklung und synthetische Tests bleiben möglich. |
| R09.01 | 9: Mitarbeiterprofile, Arbeitszeitmodelle, Zeitkonto und Abwesenheiten | implementiert | [Planning](../backend/business_planning.py), [Time](../backend/business_time.py); serverseitige Personalrechte vorhanden. Native Personalpflege und sämtliche Spezialfälle nicht vollständig. |
| R09.02 | 9: Personalunterlagen und Reisekosten | teilweise; Gesamtanforderung offen | [Personalworkflow](CRM_ERP_PERSONAL_WORKFLOW.md) mit geschützten Originalakten, Entgeltvereinbarungen und belegten Auslagen sowie [Reise-v3](CRM_ERP_REISE_V3_VERTRAG_2026.md) mit Inland-/Auslandspauschalen, Mischreisen, Boden-Zeitzonen, tatsächlicher Zahlung und Lohn-/EÜR-Übergabe sind abgegrenzt integriert und geprüft. Historische Regelversionen bleiben erhalten. Der [exakte v2/v3-Plattformabgleich](CRM_ERP_REISEN_PLATTFORMHISTORIE_2026.md) erhält alte Windows-/Linux-Reiseoriginale einschließlich Zahlungen, Bank/EÜR und tatsächlichem PG-Restore. Die [enge Kilometererstattung im privaten Pkw](CRM_ERP_KILOMETER_GESAMTINTEGRATION_2026-11-09.md) ist jetzt mit beiden Clients integriert: tatsächliche Streckenoriginale, unabhängige Freigabe, Erstattung/Korrektur/Rückzahlung, private Historie und EÜR. Ein unabhängig bestätigter Teilbeleg-Doppelanspruch ist vor Veröffentlichung pro Original-SHA gesperrt; alte Bündel und eigene Korrekturen bleiben erhalten. Die native App erhält offene Kilometeraufträge auf gebundenen Servern nun im [geschützten Originaljournal](CRM_ERP_ONLINEAUFTRAEGE_NEUSTART_2026-11-09.md) über Prozessneustarts. Die [Browserpersistenz der offenen Kilometeroriginale](CRM_ERP_BROWSER_ORIGINALJOURNAL_VERTRAG_2026-11-09.md) ist ebenfalls integriert und mit tatsächlichem Neuladen und erneuter MFA geprüft. Weitere Fremdwährungs-, Unternehmer- und Mischreisefälle sowie vollständige Fachabnahme bleiben offen. |
| R09.03 | 9: Reproduzierbare deutsche Lohnabrechnung für vereinbarte Fälle | teilweise; Gesamtanforderung offen | Die versionierten Voll-/Teilmonate, Midijobs, belegten Entgelt-/SV-Zeitachsen, Anspruchsbausteine und Reiseübergabe sowie v6/Source4-Einmalbezüge sind mit ihren Mitarbeiterbelegen, Zahlungen, Lohnkonten und Jahresquellen abgegrenzt geprüft: [Source4-Integration](CRM_ERP_LOHN_EINMALBEZUG_CLIENTS.md), [Lückenplan](CRM_ERP_LOHN_LUECKENPLAN_2026.md). Die additive Source5-Kette für getrennte tatsächliche Zahlungstage und reduzierte Mitarbeiterbelege ist [gemeinsam geprüft](CRM_ERP_SOURCE5_GESAMTPRUEFUNG_2026-11-04.md). Der [reguläre Faktor-Vollmonat v8](CRM_ERP_LOHN_FAKTOR_2026.md) ist inzwischen mit beiden Clients, originaler Historie, tatsächlichem PG-Restore und Zahlungs-/EÜR-Kette geprüft. Der [belegte reguläre Faktor-Teilmonat v9](CRM_ERP_LOHN_FAKTOR_TEILMONATE_2026.md) ergänzt Quelle2 mit beiden Clients, Original/Korrektur sowie tatsächlicher PG-/Restore-/Bank-/EÜR-Kette. Die [alte Faktor-Vollmonatshistorie](CRM_ERP_LOHN_PLATTFORMHISTORIE_2026.md) wird jetzt ohne Originaländerung zwischen LF-/CRLF-Quellen exakt nachgerechnet; echte PG-/Restorefälle bestehen. Mehrere tatsächliche Steuergruppen, weitere Source5-Korrekturen mit geändertem Brutto oder steuerlicher/SV-Zuordnung, Faktor-Ansprüche/-Einmalbezüge und Midijobs mit Faktor, weitere Versicherungs-/Leistungsfälle, weitere plattformabhängige Quellmetadaten bei Einmalbezügen sowie fachliche Freigabe und Meldung bleiben offen.  Der [v6/v7-Plattformabgleich](CRM_ERP_LOHN_EINMALBEZUG_PLATTFORMHISTORIE_2026.md) erhält alte Windows-/Linux-Originale und v1-Zahlungspläne einschließlich Jahres-/EÜR-/Restorekette; Der [positive Einzel-Korrekturvertrag](CRM_ERP_SOURCE5_POSITIVE_KORREKTUR_2026.md) ist inzwischen mit Browser/App sowie tatsächlicher PostgreSQL-/Jahres-/EÜR-/Restorekette integriert; er verlangt unverändertes Brutto/Ereignis und ursprünglichen Zahlungstag sowie belegte Vollständigkeit. Weitere Lohnfälle und Gesamtabnahme bleiben offen. Die [V3-/V4-/V5-Folgeausgleiche](CRM_ERP_SOURCE5_NETTOAUSGLEICHE_V5_2026-11-10.md) mit späteren tatsächlichen Zahlungen, Rückzahlungen und erneut positiven/negativen/null Differenzen sind mit Browser/App und vollständiger tatsächlicher PG-/EÜR-/Jahres-/Restorekette lokal gemeinsam geprüft; alte Präfixe und Bruttozuordnung bleiben erhalten. Der neue [Faktor-/Reisefall](CRM_ERP_FAKTOR_REISE_CLIENTS_2026.md) ist mit nachgewiesener steuerfreier Erstattung, unverändertem Nettolohn, beiden Clients sowie [PostgreSQL-/Restore-/CRLF-Nachweisen](CRM_ERP_FAKTOR_REISE_PG_PRUEFUNG_2026.md) integriert. Der eng begrenzte [individuelle Minijob V11](CRM_ERP_MINIJOB_INDIVIDUELL_V11_2026.md) ist mit Primär-/XML-Referenzen und [beiden Clients](CRM_ERP_MINIJOB_V11_CLIENTS_2026.md) integriert. [Sechs unabhängige PG-/MFA-/HTTP-/Restorefälle](CRM_ERP_MINIJOB_V11_UNABHAENGIGE_PRUEFUNG_2026.md), Grenzfälle und ursprüngliche CRLF-Belege sind geprüft; ein dabei gefundener Altbelegvalidierungsfehler ist behoben. Weitere genannte Fallgruppen und die fachliche Gesamtabnahme bleiben offen. |
| R09.04 | 9: Lohnreferenzfälle und produktive Meldeverfahren | extern_blockiert | Fachlich geprüfte Referenzen, notwendige Zugänge/Systemprüfungen/Dienstleister und Freigaben noch zu bestimmen. Entwicklungssimulation ist keine Zulassung. |
| R10.01 | 10: Zentraler und funktionsbezogener KI-Assistent mit Sprachbedienung | getestet | [Quellgebundener Assistent](CRM_ERP_ASSISTENT.md) und [Clients](CRM_ERP_ASSISTENT_CLIENTS.md) zentral/projektbezogen, konfigurierbarer Modelladapter sowie ausdrücklich gestarteter [Sprachentwurf](CRM_ERP_SPRACHE.md) in Browser/Flutter implementiert und abgegrenzt geprüft. Reale Geräte und tatsächlicher Anbieterbetrieb/Datenfreigabe bleiben gesondert offen. |
| R10.02 | 10: Unternehmensregeln mit Auslöser/Bedingung, automatisch/freizugebend/verboten | teilweise; Gesamtanforderung offen | Projektbezogene Regeln, konkrete Aktionspläne, Automatik/Freigabe/Verbot und erneute Prüfung direkt vor Dokument-/Mahnversand sind [geprüft](CRM_ERP_ASSISTENT.md). Unternehmensweite Regeln und kanonische Ereignisläufe sind mit Browser, App, Worker, bestehenden Projektverboten, Originalquittungen und Restore [gemeinsam geprüft](CRM_ERP_EREIGNISSE_GESAMTPRUEFUNG_2026-11-04.md). Datierte Artikel ohne ausdrückliche Preiswahl sind bereits bei der Vorbereitung gesperrt. [Codegegenprüfung](CRM_ERP_GESAMTZIEL_GEGENPRUEFUNG_2026-11-04.md). Neue Bestell-/Zahlungsadapter bleiben ohne freigegebene Implementierung wirkungslos. |
| R10.03 | 10: Rechte, Datenbasis, Audit und Wiederholungsschutz für KI-Aktionen | getestet | Frische Rechte-/Projekt-/Quellenbindung, belegbare Serverfakten und Katalogpreise, Manipulationsprüfung, Ausführungsquittung, Wiederholungs- und Restore-Schutz im beschriebenen Aktionsumfang; [Backend](CRM_ERP_ASSISTENT.md), [Clients](CRM_ERP_ASSISTENT_CLIENTS.md). Reale Anbieterabnahme und vollständige Abnahme E bleiben offen. |
| R11.01 | 11: Browser und native Windows-/iPhone-Quellen | implementiert | [Browser](../web/office/README.md), [App](../app/lib/main.dart), bestehende Plattform-/Buildgerüste. Installierbarkeit nicht aus Quellcode ableiten. |
| R11.02 | 11: Geschützte Offlinezeiten, Fotos und vorbereitete Projektarbeit | implementiert | [Business-Outbox](../app/lib/business_offline.dart), [Vault](../app/lib/offline_vault.dart), [Offline-API](../backend/business_api.py). Die [Offline-Firmenbindung V2](CRM_ERP_OFFLINE_FIRMENBINDUNG_V2_2026.md) trennt Server/API/Firma/Konto, Token und Warteschlangen und sperrt ungebundene V1-Zugriffe in gebundenen Instanzen. 186 gemeinsame native Fälle, zwei ergänzende tatsächliche HTTP-Fälle, 93 Backendfälle und fünf PostgreSQL-/Restorefälle bestehen. Alte V1-Bestände bleiben unverändert gesichert; vollständige Altbestandsmigration und reale Geräteabnahme bleiben offen. Der [bedienbare native Originalabgleich alter Planaufträge](CRM_ERP_OFFLINE_ALTBELEGE_NATIVE_2026-11-09.md) prüft ausschließlich Hashmetadaten und tatsächliche Serveroriginale; er erhält den alten Gerätebestand und gibt keine neuen Schreibaufträge frei. Der [lesende Zeitereignisabgleich](CRM_ERP_OFFLINE_ALTZEITEN_2026-11-09.md) prüft jetzt zusätzlich den historischen Kern bei vollständig erhaltener alter Mitarbeiter-/Kategoriebasis. 64 native, 81 Backend- und fünf tatsächliche PostgreSQL-/Restorefälle bestehen. Fehlende Basis wird nicht aus heutigen Profilen ergänzt; vollständige Übernahme und weitere Altwarteschlangen bleiben offen. |
| R11.03 | 11: Offlineberichte/Protokolle mit vollständigem synchronisiertem Ablauf | offen | Integrierte [Offline-Serviceprotokolle](CRM_ERP_OFFLINE_SERVICEBERICHTE.md) mit verschlüsseltem Neustart, identischer Wiederholung, unverändertem Archiv/PDF und echten HTTP-/Restoreprüfungen umgesetzt und geprüft. Historische Protokolle, weitere Dokumentarten, fachliche Konfliktklärung und reale Geräteabnahme nicht damit insgesamt geschlossen. |
| R11.04 | 11: Gemeinsamer Serverkern, Backup/Restore, Update und Betriebsanleitungen | implementiert | [Betrieb](BETRIEB_BUSINESS_UPDATE.md), [Release](../backend/online/release.py), [Restore](../backend/online/restore.py). Neuer Gesamtumfang benötigt erweiterte Abnahme F. |
| R11.05 | 11: Neue Kundenunternehmen einrichten, exportieren und geordnet verlassen | implementiert | Modulkonfiguration und feste Instanzbindung sowie [Facharchiv und Übergabeprüfung](CRM_ERP_UNTERNEHMENSEXPORT.md) vorhanden und mit tatsächlichem ZIP/Prüfer, Originalen, PostgreSQL/Restore und beiden Clients getestet. [Zusätzliche Unternehmensprovisionierung](CRM_ERP_PROVISIONIERUNG.md) ist lokal mit getrennten Rollen, Ablagen, UID-Grenzen und Wiederherstellung geprüft. Tatsächliche Hostinstallation, echte Übergabe und autorisierte Stilllegung bleiben gesondert offen. |
| R11.06 | 11: Tatsächliche Windows-/iPhone-Installation, Updates, Gerätefunktionen und Verteilung | extern_blockiert | [Windows 0.13.0 tatsächlich kompiliert und paketgeprüft](CRM_ERP_PROJEKT_BUILD_FREIGABE_2026-11-04.md); Online-EXE-Artefakt verfügbar. iPhone-Gerätebuild 168 unsigniert erfolgreich. Der Nutzer bestätigt den [tatsächlichen kontrollierten Serverupdate-Abschluss](CRM_ERP_SERVERUPDATE_ABSCHLUSS_0_13.md) auf a93cb4d: drei Dienste und Sicherungstimer aktiv, aktuelle Sandbox und Prozess-/Datenbankzuordnung geprüft, Aktivierungsmarker entfernt. Installierbare iPhone-Verteilung und vollständige Geräte-/Bedienabnahme fehlen. [20 ungeprüfte Gerätefälle](CRM_ERP_KUNDENTEST_PROTOKOLL_0_13.csv) sind vorbereitet. Cloud-/Simulatorprüfungen ersetzen diese Abnahme nicht. Keine neuen kostenpflichtigen Dienste implizit bestellen. |
| R12.01 | 12: Erweiterbare Import-/Exportadapter und vorhandene Providergrenzen | implementiert | [Adapters](../backend/business_adapters.py), [Integrationsvertrag](../backend/online/INTEGRATIONEN.md). Nur konkret unterstützte Profile bewerten. |
| R12.02 | 12: HERO-/sevDesk-Migration mit Vorschau, Zuordnung, Dubletten, Fehlern und Gesamtabgleich | implementiert | [Kontrollierter Dateiimport](CRM_ERP_DATEIMIGRATION.md) mit eigenem ausdrücklich benanntem CSV-/JSON-Format, unveränderten Originalen, Vorschau, Zuordnungen, Dubletten, bestätigter Übernahme und Betragsabgleich ist in Backend/PG/Restore/Browser/Flutter getestet. Historische Belege erzeugen keine neuen Rechnungen oder Zahlungen. Tatsächliche HERO-/sevDesk-Exportdateien und deren vollständiger Abgleich fehlen weiter; keine erfundene Herstellerkompatibilität. |
| R12.03 | 12: Verifizierte offizielle Export-/API-Wege und Testzugänge | extern_blockiert | Je ausgewähltem Anbieter tatsächlichen Exportumfang, Authentifizierung und Zugänge belegen; keine API-Funktionen erfinden. |
| R13.01 | 13: Frische Identitäts-/Rollen-/Projekt-/Dokumentrechte, Online-MFA und enge Gerätescopes | implementiert | [Auth](../backend/online/auth.py), [Foundation](../backend/business_foundation.py), [Boundarytests](../backend/online/test_business_boundary_review.py). Unternehmenszugehörigkeit siehe R03.04. |
| R13.02 | 13: Eingabe-/Uploadprüfung, verschlüsselte Offlinehaltung und Restore-Schutz | implementiert | Bestehende Hash-/Größen-/Dateiprüfungen, Vault und Privacy-Checkpoints. Kein Beleg absoluter Sicherheit. |
| R13.03 | 13: Vollständige Sicherheitsanalyse, Abhängigkeiten, Schwachstellenpflege und Vorfallsverfahren | implementiert | [Komponenten-/Sicherheitsnachweis](CRM_ERP_ABHAENGIGKEITEN_SICHERHEIT.md): aktuelle Python/npm/Dart-Abgleiche, behobene Meldungen, reproduzierbares Quellinventar und Pflege-/Vorfallsverfahren. Vollständige Binär-/OS-/Lizenzanalyse, konkrete Betriebszuständigkeit und unabhängiger Sicherheitstest bleiben offen. |
| R13.04 | 13: Datenschutzrechte und Aufbewahrung über alle Datenarten/Backups/Empfänger | offen | [Fallverfahren](CRM_ERP_DATENSCHUTZFAELLE.md) für Auskunft/Export/Berichtigung/Löschprüfung: private Arbeitskopien, Quelleninventar, explizite Prüfung, begrenzte Exporte und unabhängige Bereinigungsnachweise. 17 Fach-/MFA-/HTTP-Fälle, tatsächlicher PostgreSQL-/Altbackup-Restore, acht Node-/neun Flutterfälle und echter Browser bestanden. Betroffenenprüfung über unstrukturierte Daten, externe Empfänger und betriebliche Fristen bleibt erforderlich. |
| R13.05 | 13: Aktuelle offizielle Anforderungen zu DSGVO, Steuer/E-Rechnung, Lohn, Signatur, KI-Verordnung und CRA | implementiert | [Aktuelle Quellen- und Nachweisliste](CRM_ERP_KONFORMITAET_QUELLEN.md) für DSGVO, GoBD/E-Rechnung, Lohn-/Meldeverfahren, Signatur, KI-Verordnung und CRA mit Abrufgrenzen und verbleibenden Pflichten. Keine Rechts-/Behörden-/Produktivfreigabe; konkrete Hersteller-/Betreiberrolle und Einzelfälle weiter prüfen. |
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
| B | offen | Kunde → Katalog → Angebot → Portalannahme → Auftrag/Projekt → Einsatz → Offlinezeiten/Fotos → Protokoll → Sync → Rechnung → Zahlung; Kosten/Erlöse und Wiederholung prüfen | [PostgreSQL-Journey](../backend/online/test_business_journey_pg.py), Kalkulation, Zeiten, Fotos und Belege vorhanden. Getrennte Portalannahme und interne Übernahme ergänzen den Ablauf im bestehenden Projekt; [Portal-PG-Prüfung](../backend/online/test_postgres_portal_integration.py). Die neue [technische Auftragskette](CRM_ERP_KUNDENAUFTRAG.md) umfasst Portalannahme, unveränderte Projekt-ID, Offline-Serviceprotokolle und vollständige Zahlung. Echte Flutter-Offlineprüfung sowie PostgreSQL-Ablauf/Restore bestanden. Die ergänzte B/C-Kette umfasst belegte vollständige Projektkosten, EÜR, Inventur, Gerät, Wartung und Service mit unveränderten Exporten nach echtem Restore. Reale Geräte-/Fachabnahme bleibt offen. |
| C | offen | Projektbedarf bestellen; Teil- und Restlieferung gegen Bestellposition buchen; Bestand/Entnahme/Kosten abstimmen; Wartung für das Gerät mit Historie anlegen | [HTTP-Teilablauf](../backend/online/test_purchasing_journey.py) prüft dokumentierte externe Bestellung, Teil-/Restlieferung, Bestand, gewichtete Projektkosten, Gerätewartung mit signiertem Bericht und Neustart. Die [strukturierte Geräteherkunft](CRM_ERP_GERAETEHERKUNFT.md) verbindet inzwischen Original-Lieferschein, Bestell-/Wareneingangs- und Entnahmeposition mit Gerät und Wartung; Mengen-/Retourenschutz, Clients und tatsächlicher Restore sind geprüft. Tatsächliche externe Bestellauslösung und Transferketten bleiben gesondert offen. Vollständige Abnahme C bleibt offen. |
| D | offen | Mitarbeiter, Zeiten, Abwesenheit und Reisekosten verarbeiten; fachliche Lohnreferenzen; nachvollziehbare Korrektur; Export-/Meldestatus prüfen | Mitarbeiter/Zeit/Abwesenheit und begründete Korrekturen vorhanden. Belegte EUR-Reisekosten samt Fremdfreigabe, Erstattung/Korrektur und historischer Monatsvorbereitung sind [implementiert und geprüft](CRM_ERP_PERSONAL_WORKFLOW.md). Begrenztes Lohnrechenwerk mit amtlichen PAP-Referenzwerten und tatsächlichen PostgreSQL-/Restoreprüfungen ergänzt. Lohnkonten und belegte Lohnzahlungsbrücke zur EÜR sind ergänzt und durchgängig geprüft; weitere Standard-/Sonderfälle und vollständige externe Fach-/Meldenachweise bleiben offen. |
| E | offen | KI nennt belegbare Datenbasis, plant Aktion; Regel erzwingt Automatik/Freigabe/Ablehnung; Manipulation, fremde Daten, Rechteentzug und Wiederholung prüfen | [Assistent](CRM_ERP_ASSISTENT.md) und [Clients](CRM_ERP_ASSISTENT_CLIENTS.md) sind im beschriebenen Umfang geprüft: Quellen, Regelvorrang, konkrete Freigabe, echte Versandgates, MFA, Wiederholung und Restore. Ausdrückliche Sprachentwürfe sind mit synthetischem Mikrofon und Anbietertransport geprüft; realer Anbieterbetrieb und weitere ausführende Adapter fehlen. |
| F | offen | Beide vorgesehenen Betriebsvarianten installieren/aktualisieren, Backup wiederherstellen, Daten/Beziehungen abgleichen; Offlinekonflikt, Abbruch und fehlenden Providerzugang prüfen | Release-/Restore-/Privacyverfahren und Teiltests vorhanden. Historische Faktor- und v2/v3-Reiseoriginale besitzen eng begrenzte exakte LF-/CRLF-Prüfungen mit tatsächlichem PG-Restore ohne Originaländerung. Vollständige neue Produktdaten sowie reale Betriebs-/Geräteverfahren erneut abnehmen. |
| G | offen | Wichtigste Abläufe im Browser, unter Windows und auf iPhone bedienen; lesbare Navigation/Fokus/Touch und ehrliche Speicher-/Sync-/Fehler-/Leer-/Rechtestände prüfen | Browser-/Flutteroberflächen und Fachtests vorhanden. 18 gerenderte Browseransichten, Tastaturfokus und mobile Darstellung sind geprüft; vollständige menschliche und reale Geräteabnahme bleibt offen. |

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


## 10.11.2026 – weitere Nettoausgleiche nach Rückzahlungen

R09.03/D: [V5-Folgekorrekturen](CRM_ERP_SOURCE5_NETTOAUSGLEICHE_V5_2026-11-10.md)
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
