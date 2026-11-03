# Kundenarbeitsbereich: Projektinformationen und Dateiaustausch

Stand: 03.11.2026. Ergänzung zu R03.03 und Gesamtziel Abschnitt 3. Der bestehende Angebotszugang bleibt auf das konkrete Angebot begrenzt. Projektinformationen und Dateiaustausch benötigen einen gesondert erstellten Projektzugang. Die [Browseranleitung](KUNDENBEREICH_BROWSER.md) beschreibt die Bedienung; die native Projektansicht verwendet denselben Fachkern.

## Vollständiger unterstützter Ablauf

1. Ein intern berechtigter Mitarbeiter veröffentlicht ausdrücklich einen eigenen Kundentext mit Titel, Status und optionalem Zeitraum. Die Version ist an Projekt und aktuellen Kunden gebunden; parallele Änderungen benötigen die weiterhin aktuelle Ausgangsversion. Interne Projekttexte, Kalkulationen oder Personaldaten werden nicht automatisch veröffentlicht.
2. Er erstellt einen eigenen Zugang für einen benannten Empfänger mit E-Mail, Dauer und ausdrücklicher Uploadwahl. Der geheime Link erscheint einmal. Es wird keine Nachricht versendet; Besitz des gezielt weitergegebenen Links ist die Zugangsvoraussetzung, keine extern verifizierte Identität.
3. Der Kunde sieht die freigegebenen Informationen und Projektdateien. Er kann bei erlaubtem Upload eine unterstützte Originaldatei mit Hinweis einreichen. Dieser Eingang erzeugt zunächst weder internes Projektdokument noch Veröffentlichung.
4. Ein berechtigter Mitarbeiter prüft das eingegangene Original und übernimmt es ausdrücklich mit gewählter interner Zugriffsklasse. Vorgabe ist geschützt; die anderen Klassen folgen den bestehenden Projekt-, Finanz- und Personalrechten. Die Übernahme erzeugt atomar ein fertiges Original im bestehenden Medienmodul.
5. Die Übernahme und die spätere Kundenfreigabe sind getrennte Entscheidungen. Eine ausgewählte Projektdatei, ein unterschriebener Servicebericht oder ein finaler Kundenbeleg kann ausdrücklich mit geprüftem SHA-256 freigegeben werden. Der veröffentlichte Stand enthält unveränderte Originalbytes und einen eigenen Kundentitel.
6. Zugänge und einzelne Dateien können mit Grund widerrufen werden. Der aktuelle Zugriff endet; bestehende Nachweise und Originale bleiben erhalten. Bereits heruntergeladene Kopien bleiben beim Empfänger.

## Rechte und Datenbindung

- Interne Verwaltung verlangt aktuelle `portal.manage` und `documents.read` im konkreten Projekt. Quellvorschau, veröffentlichte interne Kopien und bereits angenommene Eingänge beachten zusätzlich die aktuellen Rechte der ursprünglichen internen Datei. Finanzbelege benötigen `finance.read`.
- Die Übernahme verlangt `documents.write` und `documents.classify`; Finanz- und Personalklassen zusätzlich das jeweilige Schreibrecht. Personaldateien und Belegfotos für Ausgaben werden nicht als veröffentlichbare Quelle angeboten.
- Kunden verwenden ausschließlich die separaten Tokenfamilien `SPCI_` und `SPCT_`. Angebots-, Mitarbeiter-, Import- oder Offlinezugänge werden weder akzeptiert noch erweitert. Der Kunde sieht nur freigegebene Dateien seines Projekts/Kunden und eigene Eingänge seines konkreten Zugangs.
- Kundenwechsel, inaktiver oder gelöschter Kontakt, abgelaufener/widerrufener Zugang und fremdes Projekt sperren den Zugriff bei jeder Anfrage. Eine andere Unternehmensdatenbank akzeptiert diese Links und Sitzungen nicht.
- Dokumentpause und Rückkehr-/Lesemodus verhindern neue Veröffentlichungen und Übernahmen. Berechtigte Sicherheitswiderrufe bleiben möglich. Nach Restore bleibt zusätzlich die bestehende betriebliche Abstimmungsfreigabe erforderlich.

## Technischer Vertrag und Grenzen

Die Fach-API liegt unter `/business/customer-workspace`: projektgefilterte Übersicht, `grants`, `publications`, `files`, `grants/{id}/revoke`, `files/{id}/revoke`, `uploads/{id}/accept` sowie berechtigte Originalabrufe. Die öffentliche API `/api/v1/customer-workspace` bietet ausschließlich `sessions`, `logout`, `workspace`, `uploads` und Originalabrufe für `files/{id}/content` beziehungsweise eigene `uploads/{id}/content`.

Unterstützte Eingänge sind PDF, JPEG, PNG und WebP bis 4 MiB; höchstens 20 Eingänge und 20 MiB je Zugang. Die HTTP-JSON-Grenze beträgt 6 MiB inklusive Base64. Veröffentlichte Originale sind auf 20 MiB begrenzt; pro Projekt/Kunde dürfen 200 Dateien gleichzeitig veröffentlicht sein. Die Quellenauswahl enthält jeweils die letzten 100 Medien, Serviceberichte und finalen Kundenbelege, soweit der Mitarbeiter sie lesen darf. Ein Zugang gilt 1–30 Tage, eine Sitzung höchstens 30 Minuten; es gibt höchstens fünf gleichzeitige Sitzungen je Zugang und zehn aktive Zugänge je Projekt. Verbindliche serverseitige Limits bleiben bei wiederholten Anfragen wirksam.

Originale werden anhand von MIME-Typ, Dateiformat, Größe und SHA-256 geprüft. Dateinamen enthalten keine Pfade; öffentliche Downloads werden als Anhang und ohne Cache ausgeliefert. Eindeutiges JSON, genaue Feld-/Methoden-/Pfadregeln, eigene Tokenfamilien, gleichbleibender Origin und dauerhaft gezählte begrenzte Zugriffsversuche bilden den öffentlichen Transport. Die Clients prüfen die zurückgelieferten Originale nochmals vor Vorschau oder Export.

Jede Änderung hat eine unveränderte Vorgangs-ID und einen inhaltlich gebundenen Ergebnisbeleg. Einladungsgeheimnisse werden nur gehasht gespeichert und niemals im wiederholten Ergebnis ausgegeben. Ein verlorenes Upload- oder Übernahmeergebnis kann mit exakt derselben Anfrage bestätigt werden; abweichende Daten mit derselben ID werden abgewiesen. Die Rückgabe wird auch bei Wiederholung erst nach erneuter Berechtigungs- und Zustandsprüfung zugänglich.

## Historie und Wiederherstellung

`backend/business_customer_workspace.py` ergänzt eigene Tabellen für Zugänge, Widerrufe, Veröffentlichungen, eingefrorene Freigabeoriginale, Kundeneingänge, Übernahmen und Ergebnisbelege. PostgreSQL-Runtime-Rechte erlauben für Historientabellen nur SELECT/INSERT. Datenbanktrigger schützen zusätzlich vor UPDATE/DELETE; SQLite schützt auch vor ersetzenden Inserts. Sitzungen dürfen gelöscht werden.

Die semantische Integritätsprüfung verbindet Ergebnisbelege mit Originalanfragen und unveränderlichen Zielobjekten, Versionsfolgen, Kundenbindungen, Quellbytes und ursprünglicher Übernahmeklassifikation. Ein neu berechneter Hash allein macht manipulierte Zusatzfelder oder einen anderen Ergebnisbeleg nicht gültig.

Eine normale Migration erhält Zugänge und Geschichte. Ein Disaster-Restore widerruft sämtliche Projektzugänge, entfernt Sitzungen und erhält Originale, Veröffentlichungen, Übernahmen und Ergebnisbelege. Alte Einladungen und Kundensitzungen aus dem Backup öffnen keinen wiederhergestellten Datenbestand. Derselbe Ablauf wurde tatsächlich für SQLite und PostgreSQL geprüft.

## Aktuelle Prüfnachweise

| Prüffläche | Ergebnis und Nachweis |
| --- | --- |
| Neuer Fachkern und echte HTTP/MFA-Grenze | 18 Tests bestanden: `backend/test_business_customer_workspace.py`, `backend/online/test_customer_workspace_http.py`; Log `work/verification/customer-workspace-domain-http.log` |
| PostgreSQL-Runtime, ACL/Trigger, Migration und tatsächlicher Backup/Restore | 2 Tests bestanden: `backend/online/test_customer_workspace_pg.py`; Log `work/verification/customer-workspace-postgres.log` |
| Bestehendes Angebotsportal einschließlich lokalem TLS | 38 Regressionstests bestanden; Log `work/verification/customer-workspace-existing-portal-regression-network.log` |
| Browser | 21 gezielte Modultests, 188 Browser-Modultests sowie echter Chromium-Gesamtablauf mit MFA, Originaldateien, verlorenen Antworten, Übernahme, Widerruf und 390-px-Ansichten bestanden; siehe Browseranleitung |
| Native Bedienung | 8 neue Widgettests bestanden, gemeinsam mit dem vorhandenen Angebotsportal 18/18: Antwortverlust, Rechteentzug, Widerruf bei Pause/Lesemodus, falsche Originalprüfsumme/-größe und abweichende Bestätigung der Zugriffsklasse. `app/lib/business_customer_workspace.dart` ist mit Dart formatiert und ohne Analyze-Befund; Tests in `app/test/business_customer_workspace_test.dart`, Log `work/verification/customer-workspace-flutter-widget.log` |

Die Logdateien erhalten auch die ersten fehlgeschlagenen lokalen Versuche: PostgreSQL-Verbindung und TLS-Socket waren zunächst durch die Ausführungssandbox gesperrt. Nach begrenzter lokaler Netzfreigabe wurden die betroffenen realen Tests erfolgreich ausgeführt. Es wurde kein externer Empfänger kontaktiert.

Diese Nachweise decken den beschriebenen Kundenarbeitsbereich ab. Produktiver Domain-/TLS-/Proxybetrieb, tatsächlich weitergegebene Kundenlinks, echte Windows-/iPhone-Geräte und der übrige Gesamtzielumfang bleiben eigenständige Abnahmen. Sie werden durch lokale Prüfungen oder diesen Dokumentstand nicht als erledigt erklärt.
