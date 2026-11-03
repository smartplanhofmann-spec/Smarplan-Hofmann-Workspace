# Kundenauftrag ausführen und abrechnen

Stand: 03.11.2026. Offline-Serviceprotokolle und die nachstehende technische
Auftragskette sind implementiert und im beschriebenen Umfang geprüft.
Maßgeblich bleibt die unveränderte [Zieldatei](../CRM_ERP_Gesamtziel.txt).

## Ziel und Priorität

Ein Mitarbeiter soll einen vorbereiteten Kundenauftrag vor Ort ausführen,
Zeiten und Fotos erfassen, das Serviceprotokoll auch ohne Verbindung
unterschreiben lassen und nach Wiederverbindung dieselben Daten im Büro
weiterverwenden können. Anschließend werden Rechnung und tatsächliche Zahlung
im selben Projekt nachvollzogen.

Dieser Ablauf hat Vorrang vor weiteren einzelnen EÜR-Verfeinerungen.
Einzelunternehmen mit EÜR sowie deutsche Lohnabrechnung für reguläre Mitarbeiter
und Minijobs bleiben verbindlicher Bestandteil des Gesamtziels. Das aktuelle
Arbeitspaket ersetzt diese Anforderungen nicht.

## Vorhandene Grundlage

- Eine Anfrage kann mit Wiederholschutz in Kunde und Projekt überführt werden.
- Artikelimport, Kalkulation, Angebotsportal und interne Auftragsübernahme sind
  vorhanden. Die Projekt-ID bleibt bei der Übernahme erhalten.
- Planung, Offlinezeiten und Fotos, genehmigte Zeitkosten, Materialentnahmen,
  Serviceberichte, Rechnungen und Zahlungszuordnung sind vorhanden.
- Der bestehende PostgreSQL-Ablauftest verbindet viele dieser Funktionen,
  überspringt jedoch die Portalannahme und echte Offline-Erfassung.

Das vom Nutzer bereits getestete ältere Protokoll verwendet `core.reports`.
Die integrierten Serviceberichte und Wartung verwenden
`business_operation_entries`. Neue Offline-Serviceprotokolle erweitern dieses
vorhandene Businessarchiv; ältere Archive werden weder verschoben noch erneut
signiert.

## Arbeit und Abnahme

1. Serviceprotokoll offline im zugeordneten Projekt erstellen, Inhalt vor der
   Unterschrift anzeigen und mit Name, Zeichnung und ausdrücklicher Bestätigung
   unverändert im verschlüsselten Gerätespeicher sichern.
2. App schließen und neu öffnen. Der unterschriebene lokale Stand bleibt
   vorhanden und wird sichtbar als noch nicht synchronisiert bezeichnet.
3. Nach Wiederverbindung denselben Auftrag atomar in das bestehende
   Serviceberichtarchiv übernehmen. Antwortverlust und Wiederholung erzeugen
   weder einen zweiten Bericht noch eine zweite Unterschrift. Gerätezeiten und
   serverseitiger Empfang sind unterscheidbar.
4. Aktuelle Rechte, Modulfreigaben, Projektzuordnung und Integrität auch bei
   Wiederholung prüfen. Konflikte, fehlende Berechtigung oder fehlende Verbindung
   erhalten lokale Daten und zeigen keinen Synchronisationserfolg an.
5. Originalinhalt, unveränderliches PDF und Projektbindung nach Neustart sowie
   Backup/Restore nachweisen. Vorhandene Berichte und Signaturen erhalten.
6. Eine zusammenhängende HTTP-/PostgreSQL-Reise führt von synthetischer Anfrage
   und Katalogimport über Angebot, echte Portalannahme, Auftrag und Ausführung
   bis Rechnung, Teilzahlung und Restzahlung. Gebuchte Material- und genehmigte
   Zeitkosten werden mit ihren Quellen abgestimmt.

## Grenzen der Aussage

Der bestehende Kostenbericht erfasst Materialentnahmen und genehmigte Zeiten;
Fremdleistungen, sonstige Kosten und die vollständige Projektwirtschaftlichkeit
sind damit noch nicht abgenommen. Echte Windows-/iPhone-Installationen, Updates,
Geräteprüfung und weitere Abnahmepunkte bleiben separat offen. Ein HTTP-Test
ersetzt keinen tatsächlichen Offline-App-Test.

Alle sieben Gesamtabnahmen A–G bleiben offen, bis ihre jeweiligen vollständigen
Nachweise vorliegen. Die bislang genannten 28 von 62 Anforderungen sind eine
ungewichtete Bestandsabdeckung, kein Fertigstellungsgrad. Fortschritt wird hier
am benutzbaren Ablauf und den konkret ausgeführten Prüfungen gemessen.

Es werden synthetische Daten und lokale Testdienste verwendet. Dieser Ablauf
versendet keine Nachrichten, Bestellungen, Zahlungen oder Behördenmeldungen.

## Ergebnisse

Die echte Flutter→Python-Prüfung verbindet Offlinezeiten, Foto, Unterschrift,
verschlüsselten Neustart, verlorene Serverantwort, identischen Retry und
prüfsummengeprüftes PDF. Der neue
[PostgreSQL-Ablauftest](../backend/online/test_customer_execution_journey_pg.py)
verbindet Anfrage, Katalogimport, Portalannahme, Auftrag, Ausführung und
vollständige Zahlung. Beide Prüfungen sind erfolgreich ausgeführt.

642 Backendtests bestanden bei einem bestehenden Windows-Skip; 670 Fluttertests,
147 JavaScript-Tests und 15 Paketprüfungen bestanden. Die Flutter-Analyse meldet
keine Probleme. 37 gezielte HTTP-/TLS-/Restoreprüfungen und ein tatsächlicher
PostgreSQL-Dump/Restore sind ebenfalls bestanden; Teilmengen werden nicht zu
einer Gesamtzahl addiert.

[Bedienweg](CRM_ERP_OFFLINE_SERVICEBERICHTE.md),
[Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_KUNDENAUFTRAG.json), tatsächliche Befehle,
Fehlversuche und Grenzen im [Fortschritt](CRM_ERP_FORTSCHRITT.md) sind festgehalten.
Die vollständige Abnahme B bleibt wegen der oben genannten Restumfänge offen.

## Nächster zusammenhängender Schritt

Die Priorität bleibt bei der Alltagstauglichkeit des Kundenauftrags:
Fremdleistungen und sonstige belegte Projektkosten ergänzen und gemeinsam mit
Material, genehmigten Zeiten, Budget, Rechnungsumsatz und tatsächlichen Zahlungen
nachvollziehbar auswerten. Jede Zahl muss zu ihrer Quelle führen; Umsatz,
Geldzufluss und Ergebnis bleiben getrennt. Ungeklärte Kosten oder Steuerangaben
dürfen kein vermeintlich vollständiges Ergebnis erzeugen.

Danach folgt die strukturierte Verbindung von Lieferung, Materialentnahme,
geliefertem Gerät und Wartung aus Abnahme C. Die verbliebenen Buchführungs-,
Lohn-, KI- und Betriebsanforderungen bleiben im Gesamtplan erhalten. Die
technischen Teilnachweise ersetzen keine tatsächliche Nutzer-/Geräteabnahme.
