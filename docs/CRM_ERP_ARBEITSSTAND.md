# Verbindlicher aktueller Arbeitsstand

Stand: 10.11.2026. Der Auftrag bleibt die vollständige CRM-/ERP-Software gemäß
Nutzerauftrag und unveränderter `CRM_ERP_Gesamtziel.txt`. Eine abgeschlossene
Etappe verkleinert das Gesamtziel nicht und beendet den Auftrag nicht.

## Projekt und verbindliche Quellen

- Hauptprojekt: `/workspace/Smarplan-Hofmann-Workspace`, Branch
  `codex/finish-20261108`.
- Einzig autorisierter Veröffentlichungsbranch:
  `codex/testupdate-0.7-projects-20261104` im bestehenden Repository.
  Kein Force-Push oder Standardbranchwechsel daraus ableiten.
- Originalziel:23863Bytes, SHA-256
  `a4dea28f6de4afd3e36d1549441aad91ce16dad374f56097979cc2d79b07fbf5`.
  Datei und historische Rechenkerne unverändert erhalten.
- Maßgebliche [Anforderungsmatrix](CRM_ERP_ANFORDERUNGEN.md),
  [Umsetzungsplan](CRM_ERP_UMSETZUNGSPLAN.md),
  [Fortschrittsprotokoll](CRM_ERP_FORTSCHRITT.md) und
  [Benutzerhandbuch](CRM_ERP_BENUTZERHANDBUCH.md).
- Festgelegt: Deutschland/EUR, Einzelunternehmen/EÜR, Regelbesteuerung/Ist,
  Standard19%, SKR04, Nettopreise; reguläre Beschäftigte und gewerbliche Minijobs.
  Die frühere Reihenfolge zuerst Projektbetrieb hat Buchhaltung/Lohn nicht
  aus dem Gesamtziel gestrichen.

## Quellcode, Prüfstand und Installation sind getrennt

| Stand | Tatsächlich bestätigt |
|---|---|
| Aktuell veröffentlichter Quell- und Testbranch | `c4a2d8f4ca969f8faab7bd15c9f7fd838e0e97ba`, veröffentlicht und Remote-Zeiger bestätigt. Installationskern7449027, Schlussnachweise/V13-CI enthalten. |
| Eigene aktuelle CI | Development42790149143 und unsignierter iPhone42790149399 laufen. Mailbot-Verträge42790149124 auf Linux/Windows bereits erfolgreich; kein echter Versand. |
| Letzter vollständig grüner Produktstand | `b02c84ab24cbe3331a92df950e74134138865e52`: alle20 Development42783465222-Jobs, unsignierter iPhone42783465231 und beide Mailbot-Verträge erfolgreich; signierter Upload übersprungen. |
| Letzter vom Nutzer bestätigter Server | `a93cb4d02eab610e5f2a8b07fbd1ee51ae99c3e5` vom05.11.; drei Dienste/Sicherungstimer und kontrollierter Updateabschluss bestätigt. Kein neuer Liveabgleich oder Update ausgeführt. |
| Geräte-/Fach-/Gesamtabnahme | Keine neue echte Windows-/iPhone- oder externe Fach-/Sicherheitsfreigabe aus Cloudtests ableiten. |

Das tatsächliche [Windows-Online-Paket b02c84a](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42783465222/artifacts/13749327057)
ist gebaut (22166950Bytes). Ein unsignierter iPhone-Build ist keine installierbare
signierte Verteilung. Die Backendkennung0.12.0-online-pilot ist eine API-
Kompatibilitätskennung, keine App-/Paketversion.

## Aktive Arbeit: Installationsstand und vollständige Serverarchive

Arbeitskopie `/workspace/smartplan-installation-context-20261110`, Branch
`codex/installation-context-20261110`. Produktcode7449027 und veröffentlichter
Teststand c4a2d8f sind eingecheckt; aktuelle Nachweispflege liegt gegebenenfalls
nur hier.
[Vertrag, Änderungen und Grenzen](CRM_ERP_INSTALLIERTER_QUELLSTAND_2026-11-10.md),
[rohe Nachweise](evidence/installation-context-2026-11-10/manifest.json).

Implementiert und tatsächlich geprüft:

- Eigene beim Paketieren erzeugte, nur gelesene Quellkennung. Pro laufender App
  beim Start eingefroren; fehlender/ungültiger Marker bleibt ausdrücklich
  unerfasst. Aktuelle globale Administrationsrechte und Online-MFA erforderlich.
- Verständliche Supportanzeige in Browser/App; alte Server werden ohne neue
  Fähigkeit nicht angefragt. Widerruf und spätes Ergebnis werden berücksichtigt.
- Beide Betreiberbefehle archivieren den festgelegten Commit. Die Erstinstallation
  enthält nun auch die zuvor fehlenden Browserdateien.
- 1058 gesamte Browser-Vertragstests;35 gemeinsame HTTP-/CI-/Archiv-/Paket-/
  Inventarfälle; zehn native Einstellungsfälle; saubere Analyse25,4s; echter
  MFA-/Chromium-/390px-/Widerrufsablauf.
- 88 vollständige endgültige isolierte Betreiberfälle in661,167s.
  Wirkliches7449027-Gitarchiv in eigenem Interpreter mit MFA, Paketkennung und
  fünf Browser-Einstiegsdateien geprüft (4,629s).
- Echter PG-/Runtime-/MFA-/vollständiger Restorefall30,201s. Alte Sitzung nach
  Restore401, danach tatsächliche neue MFA-Anmeldung. Alle vier eigenen PG-
  Container nach voller ID/Label/Loopback geprüft entfernt; fremde unverändert.

**Noch aktiv:** vollständige aktuelle native Suite, dauerhaft gespeichert unter
`/tmp/installation-context-whole-native-first-20261110.jsonl`; RunnerPID406772.
Schlussstatus `/tmp/installation-context-whole-native-status-20261110.json`.
Nur sichtbare testDone-Fälle zählen; verborgene Ladeeinträge ausschließen.
Bis zur tatsächlichen success:true-Schlussmeldung keinen Vollerfolg behaupten.
Die eigenen aktuellen Remotejobs ebenfalls bis zum wirklichen Abschluss prüfen.

## Abgeschlossener Vorgänger: Faktor, Ansprüche und bereits bezahlte Reisen

[Begrenzter V13-Vertrag](CRM_ERP_FAKTOR_ANSPRUECHE_BEZAHLTE_REISEN_V13_2026-11-10.md)
verbindet unveränderte V12-Lohn- und V10-Reiseoriginale. Bereits gezahlte Reise
wird nicht erneut zum Netto addiert. Vollständige Verwendungshistorie ist vor
Ergänzung eines unbenutzten Altfalles erforderlich; fehlendes Journal gilt nicht
als leerer Bestand. Alte Rechenkerne, Quittungen und Projektstunden bleiben erhalten.

1934 tatsächliche gesamte Appfälle ohne Fehler/Skip,1056 Browsermodule,48
Backend-/CRLF-/CI-Fälle,21 Paketfälle, drei reale Browserabläufe und tatsächliche
PG-/MFA-/Parallelitäts-/EÜR-/Jahres-/volle Restoreketten bestehen. Alle20 eigenen
Remotegruppen und unsignierter iPhone-Release sind erfolgreich.
[Genauer abgeschlossener Nachweis](evidence/factor-claims-paid-travel-2026-11-10/manifest.json).
Die aktuelle App-Gesamtprüfung darf nicht aus diesem Vorgängerwert abgeleitet werden.

## Weiterarbeiten bis zum Gesamtziel

1. Aktuelle native Schlussmeldung und Remotejobs auswerten, tatsächliche Fehler
   beheben und vollständige Nachweise einschließlich aller Vorfehler sichern.
2. Nur tatsächlich überprüfte Ergebnisse in Matrix, Plan, Fortschritt und diese
   aktuelle Zusammenfassung übernehmen. Neue Nachweispushes nicht unnötig so
   auslösen, dass noch benötigte laufende CI durch concurrency abgebrochen wird.
3. Verbleibende Code-/Abnahmepunkte anhand des Gesamtziels weiter abarbeiten.
   Bekannte Lohnfolgefälle stehen im [Lückenplan](CRM_ERP_LOHN_LUECKENPLAN_2026.md)
   und [Source5-Restplan](CRM_ERP_SOURCE5_MEHRFACH_GRUPPEN_RESTPLAN_2026.md).
   Verwendete V10-/V12-Altfälle besitzen noch keinen vollständigen neuen
   Korrekturvertrag. Weitere Steuer-/Faktor-/Einmalbezugsfälle nicht durch
   stillschweigende Freigabe bestehender Sperren ergänzen.
4. Tatsächliche HERO-/sevDesk-Originale, ausgewählte Drittanbieterzugänge,
   signierte iPhone-Verteilung, reale Geräte-/Betriebsabnahme und unabhängige
   Fach-/Sicherheitsprüfung bleiben konkrete externe Nachweise. Vorbereitete
   synthetische Prüfungen oder ein gebautes Programm ersetzen sie nicht.
5. Keine echten Nachrichten, Zahlungen, Meldungen, produktiven Migrationen oder
   öffentlichen Veröffentlichungen aus der Entwicklungsbeauftragung ableiten.
   Testbranch-Veröffentlichung ist bereits ausdrücklich autorisiert.

Das [konkrete externe Abnahmepaket](CRM_ERP_EXTERNER_ABNAHMEAUFTRAG_2026-11-10.md)
ist vorbereitet. Die Benennung zuständiger Fach-/Sicherheitsprüfer ist beim Nutzer
nicht blockierend angefragt; eine Antwort oder Freigabe liegt noch nicht vor.

Die übrigen CRM-/Projekt-/Angebots-/Rechnungs-/Zeit-/Einkaufs-/Service-/EÜR-/
Assistenten-/Offlinebausteine haben abgegrenzte technische Nachweise; die Matrix
führt den vereinbarten Umfang je Anforderung. Keines der offenen A–G wird aus
Testzahlen allein produktiv freigegeben. Es gibt keine belastbare Gesamtprozentzahl.

## Historie und Wiederaufnahme

Alle früheren Momentaufnahmen einschließlich widersprüchlicher damaliger
Zwischenstände bleiben unverändert in der
[Arbeitsstandshistorie bis10.11.](CRM_ERP_ARBEITSSTAND_HISTORIE_BIS_2026-11-10.md).
Für den aktuellen Zustand zuerst dieses Dokument lesen. Das technische
Fortsetzungsregister `/tmp/smartplan-active-integration-20261109.json` nennt
Arbeitskopien, Quellstände, laufende Prüfungen und Rohdateien; es ersetzt keine
im Repository abgeschlossenen Nachweise. Bestehende Branches/Arbeitskopien und
lokale Änderungen erhalten. Keine neuen Agenten ohne ausdrückliche Anweisung.
