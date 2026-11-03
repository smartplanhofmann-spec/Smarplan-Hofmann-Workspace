# Tatsächliche Lohnzahlungen im Geldjournal und in der EÜR

Stand 03.11.2026. Die additive Brücke übernimmt ausdrücklich bestätigte,
bereits belegte Zahlungen aus dem Lohnkonto und separat nachgewiesene
Abführungen. Sie erzeugt weder eine Banküberweisung noch aus einer
Lohnberechnung automatisch eine Ausgabe. Der konkrete API-Vertrag steht in
[CRM_ERP_LOHNZAHLUNGEN_EUER_API.md](CRM_ERP_LOHNZAHLUNGEN_EUER_API.md).

## Unterstützter Zahlungsfall

Der Umfang gilt für das Einzelunternehmen mit EÜR und die vollständig
unterstützten regulären Beschäftigungs- und Minijobfälle des Rechenwerks 2026.
Die Quellen sind aktuelle, vollständig gebundene Lohnläufe beziehungsweise
belegte Monatsvorträge und die zugehörigen Originale.

Nettozahlungsteile werden mit tatsächlich belegtem Datum, Vorzeichen, Betrag
und Referenz übernommen. Negative tatsächliche Arbeitnehmerzahlungsteile
vermindern die Ausgabe. Abführungen benötigen ein gesondert ausgewähltes
Personaloriginal, tatsächlichen Zahlungstag, Referenz und Gesamtbetrag sowie
eine ausdrückliche Aufteilung auf Arbeitnehmersteuern, Arbeitnehmer-SV,
Arbeitgeber-SV, Arbeitgeberumlagen und Arbeitgeberpauschalsteuer. Berechnete
Beträge bilden nur die überprüfbare Obergrenze. Bereits bestätigte Anteile
werden berücksichtigt; die Oberfläche darf keine Zahlung aus diesen Grenzen
vorbelegen.

Ein synthetischer regulärer Lauf mit 5.000,00 € Brutto führt bei nachgewiesenen
3.130,09 € Netto und 3.061,91 € tatsächlich abgeführten Anteilen zu 6.192,00 €
Ausgaben. Brutto und die darin enthaltenen Arbeitnehmerabzüge werden nicht
zusätzlich zur Nettozahlung doppelt gezählt. Der belegte Minijobfall ergibt
581,29 € Netto plus 209,66 € Abführungen, insgesamt 790,95 €.

## Private Nachweise und allgemeine Finanzsicht

Vier neue unveränderliche Tabellen speichern Batch-Fassungen, reservierte
Bankreferenzen, reservierte Nettozahlungsteile und exakte Wiederholquittungen.
Vorhandene Lohn-, Geldjournal- und Rechnungsquellenschemas bleiben unverändert.
Private Quellen, Originale und Nachweiskorrekturen benötigen zusätzlich aktuelle
Personalrechte. Import und Wiederholung prüfen außerdem Finanzrechte,
Modulfreigaben, Finanz-Restorestatus und die feste Unternehmensinstanz.

Die öffentliche Quelle `payroll_cash` enthält je Batch nur nach Geldkonto,
Zahltag und Richtung zusammengefasste Beträge und Kategorien sowie opaque
Quellenhashes. Beschäftigtenkennung, Name, Steuer-ID, private Dateikennung,
Originaldateiname und rohe Zahlungsreferenz werden nicht übernommen.
Allgemeine EÜR-Leser und -Bearbeiter benötigen für diese Quellen keine
Personalrechte. Finanzbeträge bleiben dennoch vertrauliche Unternehmensdaten;
aus kleinen Aggregaten kann sich wirtschaftlicher Kontext ergeben.

Die EÜR-Einordnung ist ein eigener bestätigter Vorgang mit aktuellem
Journalstand, exaktem Quellensnapshot und ausdrücklich geprüften SKR04-Konten.
Es entsteht keine Umsatz- oder Vorsteuer. Noch nicht eingeordnete tatsächliche
Zahlungen erscheinen bereits im Geldflussbestand und als offener Prüfpunkt.

## Korrekturen und Dubletten

Eine nachträglich geänderte Berechnung verändert keine bereits belegte Zahlung.
Im geprüften Minijobfall erzeugt die Berechnungskorrektur von 581,29 € auf
603,00 € zunächst keine zusätzliche Ausgabe. Erst ein neuer belegter
Zahlungsteil über 21,71 € erhöht die bestätigten Ausgaben auf 603,00 €.

Falsches Zahlungsdatum oder ein irrtümlich erfasster Zahlungsvorgang werden mit
eigener Nachweisfassung und privatem Korrekturoriginal ersetzt beziehungsweise
zurückgenommen. Bereits vorhandene EÜR-Einordnungen benötigen anschließend eine
ausdrückliche Gegen-/Ersatzbuchung. Alte Quellen, Exporte und Quittungen bleiben
unverändert. Eine Rücknahme des Nachweises ist keine behauptete Rückzahlung.

Nettozahlungsteile und normalisierte Bankreferenzen bleiben auch nach
Nachweiskorrektur reserviert. Identische neue Vorgänge, abweichende Inhalte
unter derselben Vorgangskennung, Wiederverwendung vorhandener Geldjournal-
oder externer EÜR-Nachweise und Abführungen oberhalb ihrer gebundenen Kapazität
werden abgewiesen. Geschlossene EÜR-Perioden sperren Änderungen der betroffenen
alten und neuen Zahlungsdaten.

## Wiederherstellung und Export

Der mit der Lohnzahlungsbrücke eingeführte Gesamthorizont 9 und Finanzprüfbericht
10 erfassen alle vier privaten
Tabellen mit exakten Anzahlen und Inhaltsprüfsummen. Die Prüfung rekonstruiert
Quellen, Originale, Batch-Ketten, Geldprojektion, Reservierungen und Quittungen.
Neue Restores müssen diesen Umfang ausdrücklich prüfen und freigeben. Das
anschließend ergänzte Bankmodul erweitert den aktuellen Vollstand auf Horizont
10 / Bericht 11; die Lohnzahlungsnachweise bleiben darin unverändert enthalten.
Ein früher bereits bestätigter Bericht 9 bleibt nach einem additiven Upgrade
unverändert wiederholbar; er bestätigt keinen neuen Restore mit Lohnzahlungen.

Der Unternehmens-Gesamtexport inventarisiert die drei Fachtabellen als sensible
Personal-/Finanznachweise. Technische Replayquittungen bleiben nach der
allgemeinen Exportregel ausgeschlossen; Fachhistorien, Zahlteile und
Originaldateien bleiben nachvollziehbar. Der portable Export ist kein
verlustfreier Datenbank-Restore.

## Technische Nachweise

Alle folgenden Läufe wurden am 03.11.2026 vor der additiven Bankerweiterung
ausgeführt. Testdaten, Personen,
Bankreferenzen und Originaldateien sind synthetisch.

| Nachweis | Ergebnis | Inhalt |
|---|---:|---|
| `backend/test_business_payroll_cash.py` | 9/9, 3,099 s | Minijob und regulärer Lohn, negative Arbeitnehmerzahlung, Korrektur ohne erfundenen Geldfluss, Quelle/Rechte ohne Personalzugriff, Dubletten, Reservierungen, Periodensperren, atomarer Fehler und Replay, historische/neue Restore-Schemas |
| `backend/online/test_business_payroll_cash_http.py` | 2/2, 0,954 s | Echte HTTP-/MFA-Sitzung, private Originale, Vorschau/Bestätigung, allgemeine EÜR ohne Personalrechte, strikte Bodies/Queries, falsche Instanz, Offline-/Rollenwechsel |
| `backend/online/test_business_payroll_cash_pg.py` | 3/3, 21,540 s | PostgreSQL, echte HTTP/MFA, Runtime-ACL, getrennte konkurrierende Verbindungen, Neustart, realer Dump/Restore, Quittungen/Exporte unverändert, neues Freigabeschema und alter bestätigter Bericht |
| Bestehende `backend/test_business_accounting_euer.py` | 18/18, 9,831 s | Vorhandene EÜR-Buchungs-, Beleg-, Steuer-, Korrektur- und Exportfälle bleiben gültig |

Die PostgreSQL-Fälle wurden ohne Skip mit Schema-/Runtime-Rollentrennung und
temporärem echten Restoreziel ausgeführt. Aufzeichnungen liegen lokal unter
`work/verification/payroll-cash-{domain,http,pg,euer-regression}.log`; die
reproduzierbaren Testdateien sind Bestandteil des Repositorys. Clientnachweise
stehen in [CRM_ERP_LOHNZAHLUNGEN_EUER_CLIENTS.md](CRM_ERP_LOHNZAHLUNGEN_EUER_CLIENTS.md).

## Fachliche Quellen und bewusste Grenzen

Am 03.11.2026 wurden [§ 11 EStG](https://www.gesetze-im-internet.de/estg/__11.html)
und die offizielle
[ELSTER-Hilfe zur Anlage EÜR 2025](https://www.elster.de/elsterweb/helpGlobal?themaGlobal=help_euer_ufa_77_2025)
geprüft. § 11 ordnet Ausgaben grundsätzlich dem Zahlungsjahr zu und enthält
Ausnahmen für regelmäßig wiederkehrende Ausgaben. Die ELSTER-Hilfe beschreibt
Personalausgaben einschließlich abgeführter Lohnsteuer und weiterer
Arbeitgeberkosten. Die Hilfe 2025 belegt die fachliche Zerlegung, keine
amtliche Formularzeile 2026.

Diese Brücke unterstützt tatsächliche Zahlungen im Jahr 2026 ab dem zugehörigen
Abrechnungsmonat. Jahreswechsel-/Zehntagesfälle, steuerfreie Zusatzbezüge,
Reiseauslagen, Unfallversicherung, Erstattungen von Krankenkassen/Behörden und
nicht unterstützte Lohnsonderfälle sind nicht Teil dieses Zahlungsadapters.
Sie werden nicht aus Berechnungen erzeugt. Es gibt keine amtliche
ELSTER-/SV-Meldung, keine Bankübertragung und keine behauptete externe
fachliche oder gerätespezifische Nutzerabnahme.
