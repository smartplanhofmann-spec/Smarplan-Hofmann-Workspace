# CRM/ERP: Bestandsaufnahme zum Gesamtziel

Stand: 02.11.2026. Maßgeblich ist das unverändert gespeicherte
[CRM_ERP_Gesamtziel.txt](../CRM_ERP_Gesamtziel.txt). Diese Aufnahme bewertet den
vorhandenen Quellstand `420c4c7700d7543a725d787d48eef8bdb2319152`, nicht den
unbekannten aktuellen Stand eines produktiven Servers. Weitere Änderungen und
neu ausgeführte Prüfungen werden im [Fortschritt](CRM_ERP_FORTSCHRITT.md) erfasst.

## Ausgangspunkt und Aussagegrenzen

Das Hauptrepository liegt unter `/workspace/Smarplan-Hofmann-Workspace`.
`smartplan-backend-review`, `smartplan-business-completion`,
`smartplan-business-suite` und `smartplan-hero-phase0` sind verknüpfte
Arbeitskopien dieses Repositorys. Der zunächst sichtbare ältere Hauptstand
`822fe58` enthielt die späteren Businessmodule noch nicht. Für die Fortsetzung
wurde der bereits vorhandene Entwicklungsstand bis `420c4c7` übernommen; die
nachfolgend beschriebenen Businessfunktionen wurden nicht erst durch diese
Bestandsaufnahme entwickelt.

Die native Versionsdatei nennt **0.12.0**. Die Business-Speicherversion ist **7**;
Versionsnamen der App, der Bestands-API und des Datenbankschemas sind getrennte
Angaben. Sie beweisen weder eine Installation noch eine Freigabe.

Die aktuelle Zielvorgabe sagt ausdrücklich: Der Nutzer hat bisher nur ein
digital unterschreibbares Protokoll geprüft. Ältere Dokumente enthalten darüber
hinausgehende Test- und Betriebsangaben. Diese bleiben als historische
Aufzeichnungen erhalten, werden für das neue Gesamtziel aber nicht als aktuelle
Nutzerabnahme übernommen. Auch die vorhandene Zeichnung einer Unterschrift ist
kein Nachweis einer qualifizierten elektronischen Signatur.

Diese Aufnahme beruht auf Quelltext, Schemas, Routen und Testdefinitionen.
Vorhandene historische grüne Testberichte werden als solche gekennzeichnet.
Ein Dateiname, ein Navigationspunkt oder ein vorhandener Test allein beweist
weder korrektes Laufzeitverhalten noch einen vollständig erfüllten Ablauf.
Neu ausgeführte Tests mit Umgebung, Ergebnis und Auslassungen stehen getrennt
im Fortschrittsbericht.

## Architektur und Datenhaltung

| Bereich | Vorhandene Umsetzung | Bedeutung für die Weiterentwicklung |
|---|---|---|
| Gemeinsamer Kern | Python-Domänenmodule; `Office` in [core.py](../backend/core.py), Businessrouting in [business_api.py](../backend/business_api.py) | Kunden, Projekt-IDs und bestehende APIs erhalten; Fachfunktionen erweitern statt neu beginnen. |
| Server | Flask/HTTPS-Prüfung und PostgreSQL über [online/web.py](../backend/online/web.py) und [online/store.py](../backend/online/store.py) | Bestehender gemeinsamer Produktkern für Serverbetrieb; kein belegter Mandantenrouter. |
| Lokaler Betrieb | Python/SQLite und Windows-Startpfad in [windows_office.py](../backend/windows_office.py) | Gemeinsame Domäne, aber nicht dieselbe Sicherheits-/Betriebsfreigabe wie PostgreSQL. Eigene Finanzfestschreibung ist produktiv an den geschützten PostgreSQL-Dienst gebunden. |
| Schema | Explizite Businessregistry, Prüfsummen und Integritätsprüfungen in [business_schema.py](../backend/business_schema.py); Speicherversion 7 | Additive Migration, Prüfjournal und bestehende Restoreverfahren weiterverwenden. Ein Rückkehrmodus deaktiviert Schreiber, löscht keine Geschäftsdaten. |
| Native App | Flutter/Dart, bestehende Windows- und iOS-Projekte; [business_shell.dart](../app/lib/business_shell.dart) | Große Teile der täglichen Abläufe vorhanden; tatsächliche Geräteinstallation, Updates und Spezialeditoren getrennt nachweisen. |
| Browser | Eigenständige responsive Oberfläche in [web/office](../web/office/README.md), `/office/` | Bereits eine Browseranwendung; kein Flutter-Webbuild und keine belegte Offline-PWA. |
| Offline | Verschlüsselte Appdaten und Warteschlangen in [offline_vault.dart](../app/lib/offline_vault.dart), [offline_workspace.dart](../app/lib/offline_workspace.dart), [business_offline.dart](../app/lib/business_offline.dart) | Vorbereitete Projektarbeit sowie eigene Zeiten/Fotos sind vorhanden. Offline-Protokollsignatur und alle Spezialfunktionen sind damit nicht abgenommen. |
| Berechtigungen | Rollen/Projektzuweisungen plus explizite Grants/Denies und Dokumentklassen in [business_foundation.py](../backend/business_foundation.py) | Grundlage für Fachrechte. Eine Rolle `owner` gehört bisher zur gesamten Installation; eine zweite Firma in derselben Datenbank ist nicht sicher abgebildet. |

Der untersuchte Datenbestand im Code ist auf eine Installation ausgerichtet.
Benutzer, Kunden, Projekte, globale Kataloge und Einstellungen besitzen keine
durchgängige Unternehmenszuordnung. Projekttrennung ist keine Mandantentrennung.
Ein gemeinsamer Kundenbetrieb mit mehreren Firmen darf daher nicht aus den
vorhandenen Projektberechtigungen abgeleitet werden. Die erste technische
Etappe bindet eine Installation ausdrücklich an ein Unternehmen; eine spätere
Mehrfirmenplattform benötigt zusätzlich eine nachweisbare Trennung von Daten,
Dateien, Suchindizes, KI-Kontexten und Hintergrundaufträgen.

## Fachlicher Bestand und verbleibende Lücken

| Zielbereich | Im Quelltext vorhandener Kern | Grenze gegenüber dem neuen Gesamtziel |
|---|---|---|
| Einrichtung und Module | Business-Capabilities, Featureflags und Fachrechte; Kontaktdaten und Ausstellereinstellungen | Unternehmensbedarf, manuell korrigierbare Modulvorschläge sowie getrennte Sichtbarkeit/geschäftliche Aktivierung fehlen im Ausgangsstand. |
| Kunden und Eingang | Kunden/Lieferanten/Partner mit Ansprechpartnern und Adressen; Anfragen, Wiedervorlagen, Mailoriginale; bestätigte atomare Übernahme in Kunde/Projekt | Kein vollständiges branchenneutrales Verkaufschancenmodell und keine lückenlose Kommunikationschronik für jeden Kanal. |
| Angebote und Auftrag | Artikel/Leistungen, Vorlagen, Decimal-Kalkulation, Rabatte/Steuern, Versionen, Umwandlung in Auftragsbestätigung und Rechnungsentwurf | Kein isoliertes Kundenportal mit Annahme/Ablehnung und Dateiaustausch. Eine interne Belegumwandlung ist keine Portalannahme. |
| Projekte | Aufgaben, Termine, Meilenstein-/Statuspflege, Ressourcen, Jahresansicht, Budgets, Fotos, Berichte, Aufmaß und Signaturen | Vollständiger Soll-Ist-Vergleich aller Kostenarten sowie eindeutig belegte Unternehmenskennzahlen fehlen. |
| Kosten | Gebuchte Materialentnahmen/Rückgaben und freigegebene Zeiten mit historischen Kostensätzen; Kalkulationsnachweise | `cost_report` berücksichtigt Material und Lohn. Maschinen-, Fremdleistungs- und Gemeinkostenvollrechnung sowie vollständige Erlös-/Rentabilitätsrechnung sind noch offen. |
| Einkauf/Lager | Artikel, Lagerorte, appendierte Bewegungen, Reservierungen, Teilentnahmen, Rückgaben, Nachbestellvorschläge | `save_order` speichert nur `draft`/`approved` und meldet `delivery_status=not_sent`. Bestellpositionsgebundene Teil-/Restlieferungen, Lieferstatus und Inventur fehlen. |
| Service/Betriebsmittel | Ressourcen, Anlagen/Geräte, Wartungsverträge, wiederkehrende Einsätze und Historie | Kein vollständiger Reklamations-/Kundenserviceablauf; Fahrzeug-/Werkzeugverwaltung nur im belegten Ressourcen-/Wartungsumfang. |
| Rechnungen/Zahlungen | Ausgangsbelege, Abschläge/kumulierte/Schlussrechnung, gebundenes Storno, Archiv, manuelle Zahlungen/Erstattungen, OP und Mahnfreigaben | Kein Bankfeed und keine vollständige eigene Buchhaltung. Ausstellerwechsel, tatsächlicher Versand und Datenübernahme sind gesonderte Betriebsentscheidungen. |
| E-Rechnung | UBL/CII-Verarbeitung und Schnittstellen zu KoSIT, Mustang und veraPDF; begrenzter Eingang mit Review | Profil-/Werkzeugkonfiguration und aktuelle fachliche Prüfung erforderlich. Ein erfolgreicher Formatvalidator ist keine allgemeine steuerliche oder GoBD-Freigabe. |
| Buchhaltung | Belege, Zahlungszuordnung, Originale und Prüfexporte als Bausteine | Kontenplan/Buchungssätze, Perioden, EÜR/Doppik, Abschlüsse und Unternehmens-GuV sind nicht umgesetzt. |
| Personal | Benutzergebundene Mitarbeiterprofile, Soll-/Kostensätze, Arbeitszeiten, Tagesfreigaben, Korrekturen, Zeitkonto, Abwesenheiten | Personalunterlagen, Reisekosten und Lohnabrechnung fehlen; Stundenexport ist keine Lohnberechnung. Fachlich unterstützte Beschäftigungsfälle und Meldungen sind offen. |
| KI und Regeln | Begrenzte freigegebene Eingangsantworten, Versandfreigaben und wiederholsichere Outboxes | Kein allgemeiner KI-Assistent, keine Sprachbedienung und keine unternehmensbezogene Regelengine für automatische/freizugebende/verbotene Aktionen. |
| Schnittstellen | Bestehende Gmail-/Botverträge, gewählte Sevdesk-/Google-/OneDrive-Metadaten, lokale Import-/Exportprofile | Keine vollständige HERO-/sevDesk-Migration mit Gesamtabgleich; DATEV-Prüf-CSV ist kein nativ abgenommener DATEV-Übertragungsweg. Lieferantenprofile belegen keinen Livezugang. |
| Datenschutz/Betrieb | Dokumentklassen, Kontaktprüfung, unabhängige Privacy-Checkpoints, Backup/Restoregates, getrennte PostgreSQL-Laufzeitrechte | Vollständige Auskunft/Export über alle Quellen, Aufbewahrungs- und Rechtsnachweise, unabhängiger Sicherheitstest und Geräteabnahme fehlen für den neuen Produktumfang. |

Wesentliche Quellbelege sind [Foundation](../backend/business_foundation.py),
[Belege](../backend/business_documents.py), [Kalkulation](../backend/business_pricing.py),
[Finanzen](../backend/business_finance.py), [E-Rechnungen](../backend/business_einvoice.py),
[Planung](../backend/business_planning.py), [Zeiten](../backend/business_time.py),
[Dokumentation](../backend/business_operations.py), [Lager](../backend/business_inventory.py),
[Wartung](../backend/business_maintenance.py) und [Adapter](../backend/business_adapters.py).

## Vorhandene Tests und erforderliche neue Abnahme

Der [historische Umsetzungsbericht](BERICHT_HERO_UMSETZUNG.md) nennt zahlreiche
synthetische Prüfläufe des damaligen Pakets. Sie sind keine aktuelle Ausführung
und nicht mit den neuen Abnahmefällen A–G gleichzusetzen. Insbesondere sind die
dortigen IDs A1–O4 eine andere Prüfliste als die neue
[Anforderungsmatrix](CRM_ERP_ANFORDERUNGEN.md).

| Prüfbereich | Vorhandene ausführbare Referenzen | Noch nicht durch ihre bloße Existenz nachgewiesen |
|---|---|---|
| Gemeinsamer Ablauf | [PostgreSQL-/Flask-Journey](../backend/online/test_business_journey_pg.py) | Vollständiger Fall B einschließlich Portal, Offline-Protokoll und unternehmensweiter Buchführung. Der Test nutzt synthetische Daten und eine ausdrücklich entbehrliche Datenbank. |
| Geld, Belege, Rechnungen | [Fachtests](../backend/business_tests/test_documents.py), [Finanzreview](../backend/business_tests/test_finance_review.py), [Validatoren](../backend/business_tests/test_einvoice.py) | Unterstützte steuerliche Fallgruppen, produktive Ausstellerfreigabe, gesamte eigene Buchhaltung und Lohnabrechnung. |
| Rechte | [Boundarytests](../backend/online/test_business_boundary_review.py), [Dokumentzugriff](../backend/online/test_business_document_access_api.py) | Unternehmensisolation; bisherige Fälle prüfen Rollen/Projekte innerhalb einer Installation. |
| Zeiten und Planung | [Zeittests](../backend/test_business_time.py), [Planung](../backend/test_business_planning.py), [echte PostgreSQL-Fälle](../backend/online/test_business_planning_time_pg.py) | Personal-/Lohnabnahme und praktische Offlinebedienung auf Windows/iPhone. |
| Einkauf/Service | [Inventar](../backend/test_business_inventory.py), [Wartung](../backend/test_business_maintenance.py) | Durchgängiger Fall C mit Bestellpositionsbezug und Teil-/Restlieferungen. |
| Sicherung/Migration | [Schema](../backend/test_business_schema.py), [Release](../backend/online/test_release_business.py), [Restore-Outbox](../backend/business_tests/test_restore_outbox.py) | Wiederherstellung der späteren vollständigen Produktdaten auf den vorgesehenen Betriebsvarianten. |
| Oberfläche | [Browser-E2E](../web/office/tests/e2e.cjs), [App-Tests](../app/test) | Echte Installation/Updates, Tastatur-/Touch-Abnahme, Gerätefunktionen und alle Abläufe von Fall G. |

## Konsequenz für die Fortsetzung

Der vorhandene Kern wird erhalten. Die nächste Etappe prüft den übernommenen
Stand erneut, macht Firmenbedarf und Modulvorschläge explizit, trennt
Sichtbarkeit von Aktivierung/Rechten und schützt die vorhandene
Protokollkette. Danach werden die fehlenden Teile der durchgängigen Abläufe
ergänzt. Der [Umsetzungsplan](CRM_ERP_UMSETZUNGSPLAN.md) legt Reihenfolge und
Prüfgrenzen fest; die [Anforderungsmatrix](CRM_ERP_ANFORDERUNGEN.md) hält das
vollständige Endziel offen.

Externe Abhängigkeiten blockieren nur die jeweils abhängige Abnahme: reale
Geräte-/Signierwege, konkrete Bank-/Lieferanten-/Meldezugänge, fachliche
Rechnungs-/Lohnprüfung, unabhängiger Sicherheitstest und rechtliche
Betriebsnachweise. Sie sind kein Grund, unabhängige Fachfunktionen unerledigt
zu lassen. Es wurden für diese Aufnahme keine echten Nachrichten, Zahlungen,
Bestellungen, Meldungen oder produktiven Migrationen ausgelöst.
