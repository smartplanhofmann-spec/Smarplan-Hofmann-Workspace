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
- Der PostgreSQL-Ablauftest verbindet diese Funktionen einschließlich echter
  Portalannahme und Annahme eines unveränderten Offline-Auftrags. Die tatsächliche
  verschlüsselte Flutter-Erfassung wird separat geprüft.

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

Der einfache Kostenbericht erfasst Materialentnahmen und genehmigte Zeiten.
Die erweiterte Projektwirtschaftlichkeit ergänzt belegte Fremdleistungen und
weitere Kosten, Budget, Erlös, tatsächliche Zahlungen und ihre Quellen. Der
zusammenhängende technische B/C-Nachweis wird unten gesondert geführt.
Echte Windows-/iPhone-Installationen, Updates, Geräteprüfung und weitere
Abnahmepunkte bleiben separat offen. Ein HTTP-Test ersetzt keinen tatsächlichen
Offline-App-Test.

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

Beim damaligen abgegrenzten Kundenauftrag-Prüfstand bestanden 642 Backendtests
bei einem bestehenden Windows-Skip; 670 Fluttertests,
147 JavaScript-Tests und 15 Paketprüfungen bestanden. Die Flutter-Analyse meldet
keine Probleme. 37 gezielte HTTP-/TLS-/Restoreprüfungen und ein tatsächlicher
PostgreSQL-Dump/Restore sind ebenfalls bestanden; Teilmengen werden nicht zu
einer Gesamtzahl addiert.

[Bedienweg](CRM_ERP_OFFLINE_SERVICEBERICHTE.md),
[Prüfnachweis](CRM_ERP_PRUEFNACHWEIS_KUNDENAUFTRAG.json), tatsächliche Befehle,
Fehlversuche und Grenzen im [Fortschritt](CRM_ERP_FORTSCHRITT.md) sind festgehalten.
Diese historischen Prüfzahlen werden nicht mit späteren Modulläufen addiert.
Die vollständige Nutzer-/Geräteabnahme B bleibt separat offen.

## Ergänzter technischer Umfang B/C

Die ursprüngliche Reise verwendet nun eine bestätigte Projektbestellung mit
Teil- und Restlieferung. Materialentnahme, angenommener Auftrag, Rechnung und
Zahlungen verbleiben im selben Projekt. Der ergänzende
[PostgreSQL-Ablauftest](../backend/online/test_customer_finance_service_journey_pg.py)
verbindet diese Quellen mit ausdrücklich eingeordneten Eingangsbelegen,
Budget und vollständiger Wirtschaftlichkeit für die erfassten Quellen.
Ein noch ungeklärter Beleg führt zu einem offenen Prüfpunkt und keinem
vermeintlich vollständigen Ergebnis.

Die Brücke zur EÜR nutzt dieselben Teil-/Restzahlungen und separat belegten
Lieferantenauszahlungen. Die steuerliche und betriebliche Sicht werden auf ihre
jeweilige Grundlage abgestimmt: genehmigte Zeitkosten sind kein belegter
Lohnabfluss; vereinnahmte Umsatzsteuer ist keine bereits abgeführte Steuer.

Für ein tatsächlich geliefertes und entnommenes Gerät verbindet derselbe Test
Lieferscheinoriginal, Seriennummer, Inventur, Wartungsvertrag, vorhandenen
Wartungstermin, Servicefall und unterschriebenen Wartungsbericht. Diese
Verknüpfungen dürfen weder eine zweite Materialentnahme noch zusätzliche
Projektkosten oder Geldflüsse erzeugen.

Die verbleibenden Buchführungs-, Lohn-, KI- und Betriebsanforderungen bleiben
im Gesamtplan erhalten. Die technischen Nachweise ersetzen keine tatsächliche
Nutzer-/Geräteabnahme.

## Zusammenhängender technischer Nachweis vom 03.11.2026

Beide PostgreSQL-Journeys bestanden abschließend **2/2 in 33,139 s ohne Skip**
auf der geprüften Umgebung mit cryptography 50/Pillow 13. Der vollständige
Rechennachweis des synthetischen Kundenauftrags lautet:

| Größe | Betrag | Gebundene Grundlage |
|---|---:|---|
| Projektbudget | 100,00 € netto | Bestätigte Budgetfassung |
| Material | 25,00 € netto | Zwei Lieferungen à ein Stück zu 12,50 €, eine Projektentnahme |
| Arbeitszeitkosten | 17,50 € netto | Genehmigte 30 Minuten mit historischem Stundensatz 35,00 € |
| Fremdleistung | 20,00 € netto | Geprüftes Original und bestätigte Kosteneinordnung |
| Weitere Projektkosten | 10,00 € netto | Eigenes geprüftes Original und bestätigte Kosteneinordnung |
| Gesamte Projektkosten | 72,50 € netto | Die vier vorgenannten Kostenquellen; Lagerbeleg nicht nochmals addiert |
| Rechnungsumsatz | 100,00 € netto | Rechnung aus dem im Portal angenommenen Auftrag |
| Projektbeitrag / Budgetrest | 27,50 € netto | 100,00 € minus 72,50 € |
| Kundenzahlungen | 119,00 € brutto | Belegte Teilzahlung 10,00 € und Restzahlung 109,00 € |
| Lieferantenauszahlungen | 65,45 € brutto | Belegte Zahlungen 29,75 €, 23,80 € und 11,90 € |
| Geldsaldo / EÜR-Überschuss | 53,55 € | Tatsächlich vereinnahmte 119,00 € minus tatsächlich ausgegebene 65,45 € |
| Umsatzsteuersaldo | 8,55 € | Vereinnahmte 19,00 € minus belegte Vorsteuer 10,45 € |

Die Differenz von 26,05 € zwischen Projektbeitrag und EÜR-Überschuss besteht in
diesem Fall aus 17,50 € Zeitkosten ohne dokumentierte Lohnzahlung und 8,55 €
Umsatzsteuersaldo ohne dokumentierte Steuerabführung. Für diese beiden Positionen
erzeugt der Test keine erfundene Zahlung. Der Bestand enthält genau fünf
Geldereignisse, ein Projekt und ein daraus abgeleitetes Gerät.

Eine bestätigte Inventur des danach leeren Lagerplatzes, die Geräteübernahme
und ihre Wartung verändern die Projektkosten und EÜR-Zahlen nicht. Alle
Kennzahlen werden auf konkrete Materialbewegungen, Zeitfreigaben,
Belegeinordnungen, Rechnungen und Zahlungsereignisse zurückgeführt.

Nach einem echten `pg_dump`/Restore werden alte Sitzungen zurückgewiesen und
Geldzahlen bis zum getrennten Finanzabgleich als ungeklärt gekennzeichnet.
Die Runtime-Rolle kann den Abgleich nicht freigeben (403); auch der Operator
kann dies bei noch aktiver Runtime-Verbindung nicht (409). Erst nach deren
Schließung und dokumentierter Operatorfreigabe stimmen Wirtschaftlichkeit,
Live-EÜR, gespeicherter Export, Geräte-/Servicehistorie und alle sieben
geprüften Originaldownloads unverändert mit dem Vorzustand überein.

Die fünf anfänglichen Fehler betrafen Testannahmen: HTTP-Erstellstatus 201,
verpflichtende Servicetriage, ausschließliche Operatorfreigabe, notwendiger
Stillstand vor dieser Freigabe und die zusätzliche Journalrevision durch den
Exportvorgang. Der Test wurde an diese bestehenden Verträge angepasst; es war
keine Produktionskorrektur erforderlich. Die Runtime-/Stillstandsgrenzen
werden jetzt ausdrücklich als Ablehnungsfälle geprüft.

Maschinenlesbarer Nachweis:
[CRM_ERP_PRUEFNACHWEIS_KUNDENAUFTRAG_BC_2026-11-03.json](CRM_ERP_PRUEFNACHWEIS_KUNDENAUFTRAG_BC_2026-11-03.json).
Dies ist eine zusammenhängende technische HTTP-/Datenbankprüfung. Eine erneute
durchgängige Browserbedienung, echte Offline-Geräteerfassung, Installation und
Nutzerabnahme auf Windows/iPhone sind keine Behauptung dieses Nachweises.
