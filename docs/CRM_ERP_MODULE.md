# Unternehmensbedarf und Module

Stand: 02.11.2026. Die neue Funktion ergänzt die bestehende Business-Suite.

## Nutzung

Unter **Einstellungen → Unternehmensbedarf und Module** kann ein Benutzer mit
dem Recht `settings.manage` den Bedarf an Personal, Material/Lager, Projektarbeit,
Finanzen und Steuerberaterzusammenarbeit erfassen. Die Auswahl beauftragt keine
externen Dienste und aktiviert keine Rechnungs-, Bank- oder Versandfreigabe.

Personal wird bei automatischer Auswahl vorgeschlagen, wenn Mitarbeiter
benötigt werden oder mindestens ein aktiver Mitarbeiter mit aktivem Zugang
vorhanden ist. Ein Betrieb ohne Mitarbeiter sieht den Personalbereich nicht in
der normalen Navigation. Das Entfernen aus der Navigation löscht weder
Mitarbeiter noch frühere Zeit- oder Abwesenheitsdaten.

Pro Bereich gibt es zwei getrennte Entscheidungen:

- **Automatisch / Immer anzeigen / Ausblenden** betrifft die Navigation.
  Eine manuelle Wahl bleibt auch bei späteren Mitarbeiteränderungen bestehen.
- **Fachlich aktiv** erlaubt neue Vorgänge, soweit die Benutzerrechte dies
  zulassen. Bei Deaktivierung bleiben berechtigte Lesezugriffe und historische
  Daten erhalten. Konfiguration und erneute Aktivierung bleiben erreichbar.

Benutzerrechte und Projektzuweisungen gelten zusätzlich. Das Einblenden eines
Bereichs erteilt keine Berechtigung. Berechtigte Nutzer erreichen ausgeblendete
Bereiche auf ausdrücklichen Wunsch über die weiteren Bereiche; Administratoren
können sie außerdem aus der Modulkonfiguration öffnen.

Für bestehende Installationen bleiben die Bereiche zunächst fachlich aktiv.
Die Automatik vereinfacht die Navigation, verändert aber keine gespeicherten
Fachvorgänge. Die Bedarfsfrage zum Steuerberater ist gespeichert; eine konkrete
DATEV-/Steuerberaterverbindung wird dadurch noch nicht eingerichtet.

## Gleichzeitige Änderungen und Offlinezeiten

Speichern verwendet eine Versionsnummer und eine feste Vorgangs-ID. Eine
veraltete Version kann keine neuere Wahl überschreiben. Eine unklare Antwort
kann mit demselben unveränderten Auftrag wiederholt werden. Jede bestätigte
Konfigurationsänderung bleibt mit Benutzer und Zeitpunkt in der Historie.

Neue serverseitige Fachbefehle an deaktivierte Bereiche erhalten den temporären
Status `423`. Ausstehende Offlinezeiten bleiben geschützt auf dem Gerät und
warten auf erneute Aktivierung. Bereits bestätigte identische Zeitereignisse
werden nach erneuter Rechte-/Inhaltsprüfung weiter quittiert; Synchronisation
erzeugt dadurch keine zusätzlichen Zeitereignisse. Ein vor der Deaktivierung
bereits zugelassener Vorgang kann noch abschließen.

Die Aktivierungssperre gilt an der gemeinsamen Business-HTTP-Grenze, inklusive
Katalogübernahme und Angebotserzeugung über Adapter. Lokale administrative
Python-Aufrufe sind kein öffentliches API und müssen vom Betreiber kontrolliert
bleiben. Bestehende Legacy-Projektfunktionen gehören weiter zum gemeinsamen
Kern; die fünf optionalen Bereiche sind Personal, Material/Lager, Einsatzplanung,
kaufmännische Belege und Finanzen.

## Datenhaltung und Migration

Das additive Modul `business_organization` speichert Einstellungen,
Konfigurationshistorie und Wiederholungsbelege in eigenen Tabellen. Bestehende
Modul-DDL, Geschäftsobjekte und signierte Dokumente werden nicht umgeschrieben.
PostgreSQL benötigt vor dem Start des neuen Codes die ausdrückliche Migration
und Aktualisierung der Laufzeitrechte über den bestehenden Updateprozess.
Obwohl die Speicherversion weiterhin 7 heißt, muss das neue Modul im
Migrationsjournal vorhanden sein. HTTP-Anfragen führen keine Migration aus.

Der Windows-Quellpaketumfang enthält beide neuen Basismodule. Ältere Clients
bleiben mit ihren bisherigen Funktionen nutzbar; die neue Navigation setzt
die vom Server angebotene Funktion `organization_modules` voraus. Die
Unternehmenskonfiguration ersetzt keine Mandantentrennung; dazu siehe
[Unternehmensinstanzen](CRM_ERP_INSTANZEN.md).

## Reproduzierbare Nachweise

`backend/test_business_organization.py` prüft Vorschläge, manuelle Wahl,
Berechtigungen, Wiederholung, Versionskonflikt, Rollback, historische Lesbarkeit,
Adaptergrenzen, Offlinezeit-Replay und die Migration einer gefüllten bisherigen
Schema-7-Datenbank mit unverändertem unterschriebenem PDF.
`backend/online/test_organization_http.py` prüft echte HTTP-Abläufe.
Flutter- und Browserprüfungen ergänzen Navigation und Bedienzustände.
Aktuelle Laufzahlen und Grenzen stehen im
[Fortschrittsbericht](CRM_ERP_FORTSCHRITT.md).
