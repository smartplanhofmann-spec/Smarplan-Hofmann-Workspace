# Konkretes Paket für Fach-, Sicherheits- und Geräteabnahme

Dieses Paket bereitet die im Gesamtziel vorgesehenen gesonderten Nachweise vor.
Es beauftragt niemanden, versendet keine Daten und erteilt keine Produktivfreigabe.
Alle nachstehenden Beispiele verwenden kontrollierte synthetische Daten.

## Genau zu prüfender Stand

- Produkt b02c84ab24cbe3331a92df950e74134138865e52 besteht alle 20 eigenen
  Development-Jobs, Windows und unsignierten iPhone-Release. Signierte Verteilung
  fehlt. [V13-Nachweise](evidence/factor-claims-paid-travel-2026-11-10/manifest.json).
- Aktueller Testbranch c4a2d8f4ca969f8faab7bd15c9f7fd838e0e97ba ergänzt den
  gelesenen Installationsstand und vollständige eingefrorene Serverarchive.
  Seine eigene vollständige App-Suite und Remote-CI laufen beim Anlegen dieses
  Pakets noch. [Aktueller Arbeitsstand](CRM_ERP_ARBEITSSTAND.md).
- Letzte bestätigte Serverinstallation ist A93 vom 05.11.2026. Ein späterer
  Quell- oder Appstand beweist keinen Serverwechsel. Ein Update ist ein eigener
  kontrollierter Betriebsablauf; die folgende Abnahme führt es nicht aus.

## Fachliche EÜR-Prüfung

Vereinbart: deutsches Einzelunternehmen, EÜR, Regelbesteuerung/Ist, SKR04,
Standard 19 %, Nettopreise. Bitte den unterstützten dokumentierten Umfang prüfen:

1. Beleg- und Steueranteile bei Teilzahlungen, Überzahlungen, Rückzahlungen,
   Abschlägen, kumulativen Rechnungen und Schlussrechnung. Voller Vertragsumsatz,
   zusätzlich berechneter Anteil und tatsächlicher Geldfluss bleiben getrennt.
2. Eingangsoriginal, Einordnung, Privatanteile und Zeitpunkt des Vorsteuerabzugs;
   belegte Anfangssalden, offene Altposten, Jahresvortrag und lineare Anlagen.
3. Nettoentgelt, gesonderte Abführungen und tatsächliche Reiseerstattungen nur
   einmal in der EÜR; vollständiger Quellenabgleich nach Restore und Jahreswechsel.
4. Periodensperren, Berichtigung/Gegenbuchung und Jahresprüfpaket einschließlich
   Originalen. Ein internes Paket wird nicht als DATEV-Format oder eingereichte
   Steuererklärung ausgegeben.

Quellen: [EÜR-Workflow](CRM_ERP_EUER_WORKFLOW_API.md),
[Rechnungsketten](CRM_ERP_EUER_KETTEN_ANALYSE.md),
[Jahreswerte/Archive](CRM_ERP_JAHRESVORTRAG_GESAMTPRUEFUNG_2026-11-04.md),
[Lohnzahlungsbrücke](CRM_ERP_LOHNZAHLUNGEN_EUER_CLIENTS.md).
Die bestehenden reproduzierbaren Domain-/PG-/MFA-/Restorefälle sind verlinkt;
bestandene Entwicklungstests sind noch kein unabhängiger Fachvermerk.

## Fachliche Lohnprüfung

Unterstützungsumfang und tatsächlich erkannte Sperren anhand des
[Lückenplans](CRM_ERP_LOHN_LUECKENPLAN_2026.md) und der versionierten
[Lohnbedienung](CRM_ERP_LOHN_CLIENTS.md) beurteilen. Der neue kontrollierte
Faktor-/Anspruchs-/Reisefall besitzt folgende tatsächlich erzeugte Werte:

| Fall Oktober 2026 | Brutto | Lohnsteuer | AN-SV | Netto/Auszahlung | Bereits getrennt gezahlte Reise |
|---|---:|---:|---:|---:|---:|
| Monatsentgelt 5.000 Euro, fünf belegte unbezahlte Tage, Faktor 0,753 | 4.193,55 | 430,91 | 912,10 | 2.850,54 | 14,00 |
| Stundenfeiertag, keine tatsächliche Projektarbeit, eigener belegter P4-Anspruch | 3.200,00 | 253,91 | 696,00 | 2.250,09 | 14,00 |
| Ausdrückliche Ergänzung des unbenutzten ursprünglichen Monats-/P4-Falles | 4.193,55 | 430,91 | 912,10 | 2.850,54 | 14,00 |

Beträge in Euro. Vollständige tatsächlich akzeptierte Profile, Identität,
Beschäftigung, Originalquellen, Eingaben, Pläne, Quittungen und private Belege:
[Originalpakete](../app/test/fixtures/payroll_factor_claim_travel.json).
Im ersten Fall ergeben echte Nettozahlung plus echte getrennte Reisezahlung
2.864,54 Euro belegte EÜR-Ausgaben, keine Vorsteuer und 4.193,55 Euro laufendes
Jahressteuerbrutto. Es entstehen dafür keine zusätzlichen Projektstunden.
Die Reise wird nicht erneut zum Netto addiert.

Zusätzlich die ausdrücklich noch ungeklärte Steuergruppenentscheidung
prüfen: [Source5-Restplan](CRM_ERP_SOURCE5_MEHRFACH_GRUPPEN_RESTPLAN_2026.md).
Beim dokumentierten unabhängigen PAP-Sensitivitätsfall mit 87.500 Euro
Jahresbasis und zwei Bezügen zu je 2.500 Euro ergeben getrennte und gemeinsame
Aufrufe unterschiedliche Solibeträge (52,36 gegenüber 104,72 Euro). Bitte eine
verifizierte einschlägige Fundstelle oder dokumentierte Fachauskunft mit
vollständigen unabhängigen Sollwerten liefern. Die bloße Rechendifferenz ist
keine begründete Gruppenregel. Der ungeklärte Zweig bleibt gesperrt.

Meldewege, Systemprüfungen, Qualifikationen/Zugänge und reale Übermittlung sind
separat zu prüfen. Es liegt keine behauptete amtliche Systemzulassung vor.

## Unabhängiger Sicherheitstest

Prüfziel ist ein ausdrücklich freigegebener isolierter Testbetrieb mit dem
festgehaltenen Quellstand. Schwerpunkte aus dem Gesamtziel:

- Firmen-/Datei-/Such-/KI-/Workertrennung und aktuelle Rollen-/Projektrechte,
  einschließlich widerrufener Berechtigung, fremder Kennungen und Originalexporte.
- MFA/Sitzungen/Wiederherstellung, unklare Antworten und unveränderte Wiederholung;
  alte Sitzungen bleiben nach Restore gesperrt.
- Upload-/Parsergrenzen, Offline-V2-Firmen-/Kontobindung, verschlüsselte Speicherung
  und Quarantäne alter ungebundener Bestände.
- Angehängte Finanz-/Lohnhistorien, Operator-/Runtime-Rechte, Backups, tatsächliche
  Wiederherstellung und Fehler vor/nach der Aktivierungsgrenze.
- Assistentenregeln und Manipulationsversuche in fremden Dokumenten; ohne
  konfigurierte Erlaubnis keine automatische Außenwirkung.

Vorhandene interne Nachweise, Komponentenübersicht und Einordnung:
[Sicherheits-/Abhängigkeitsstand](CRM_ERP_ABHAENGIGKEITEN_SICHERHEIT.md),
[Unternehmensisolation](CRM_ERP_UNTERNEHMENSISOLATION_GESAMTPRUEFUNG_2026-11-04.md),
[offizielle Anforderungen](CRM_ERP_KONFORMITAET_QUELLEN.md).
Diese Unterlagen ersetzen keinen unabhängigen Test und keine Nachprüfung.

## Reale Geräte- und Betriebsabnahme

[20 konkrete Gerätefälle](CRM_ERP_KUNDENTEST_PROTOKOLL_0_13.csv) und
[Projekt-Testfolge](CRM_ERP_KUNDENTEST_PROJEKTBETRIEB_0_13.md) sind vorbereitet.
Vor Beginn Paketcommit, tatsächlich installierten Serverstand und Firmeninstanz
abgleichen. Windowsprogramm vollständig entpacken. Für iPhone wird eine
signierte installierbare Verteilung benötigt; der unsignierte Build genügt nicht.
Offlineerfassung, Wiederverbindung, ursprüngliche Wiederholung, PDF/Unterschrift,
Zeiten, Material, Rechnung und Zahlung auf den tatsächlichen Geräten prüfen.

## Rückmeldung festhalten

Pro Befund sind Quell-/Paketstand, unterstützter Fall, Originaleingaben,
unabhängiges erwartetes Ergebnis, tatsächlich beobachtetes Verhalten, Datum,
zuständige prüfende Person und Umfang/Ergebnis der Nachprüfung festzuhalten.
Eine Freigabe nennt den tatsächlich beurteilten Einsatzumfang. Unbekannte
Quellen oder nicht geprüfte Fälle werden nicht als bestätigt markiert.
