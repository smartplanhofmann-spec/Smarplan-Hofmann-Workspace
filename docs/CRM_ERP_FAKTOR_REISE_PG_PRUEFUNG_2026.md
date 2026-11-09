# Unabhängige Faktor-/Reiseprüfung mit PostgreSQL

Geprüft wird ausschließlich der neue Source3-Vertrag
`de_2026_factor_taxfree_travel_month_v10`, Quellenvertragsversion 2.
Ein vollständiger v9-Faktormonat bleibt die Lohnbasis; eine vollständig bereits
erstattete steuerfreie Reise erhöht weder Brutto noch Netto. M-Merkmal,
steuerpflichtige oder pauschale Reisebestandteile, unvollständige Zahlungen,
andere Personen und unbewiesene Quellen bleiben ausgeschlossen.

Die isolierte Prüfbranch basiert auf dem kombinierten Stand `ffb5010` und den
Backendkorrekturen `7db66f1` (ungültige Details und Bonusabgrenzung) sowie
`35f94e4` (vollständige Jahresprojektion). Die lokale Übernahme dieser beiden
Korrekturen heißt `4749317` beziehungsweise `4022b30`. Die unabhängige Prüfung
ändert keinen Produktcode.

## Tatsächliche Nachweise

- Eigene PostgreSQL-16-Instanz, getrennte Betreiber-/Anwendungsrollen, echte
  MFA-Anmeldung und HTTP-Aufrufe. Der neue Container verwendet ausschließlich
  die Loopback-Adresse und wurde nicht mit anderen laufenden Arbeiten geteilt.
- Vollständiger v9-Faktorperiodenfall, anschließend V10 als explizite neue
  Lohnrevision und danach belegte Faktorkorrektur von 0,753 auf 0,900.
  Die ursprünglichen 14 Euro Reisekosten sind als genau eine bereits ausgeführte
  Erstattung belegt und bleiben getrennt. Die Cent- und Beitragsfelder des ersten V10-Laufs entsprechen
  vollständig dem ursprünglichen v9-Lauf; das Netto beträgt 3.323,42 Euro.
  Die Faktorkorrektur ergibt 3.208,34 Euro Netto und −115,08 Euro Differenz.
- Tatsächliche Lohnzahlungsfassung und Jahresbasis mit fertig angenommenem
  V10-Lauf, `current_calculation_case_ref=null`: laufendes Steuerbrutto und
  Rentenversicherungsbasis jeweils 500.000 Cent. Die Reise wird kein zweites
  Mal als Lohnzahlung angerechnet.
- Tatsächlicher `pg_dump`/`pg_restore` in eine neue leere Testdatenbank,
  vollständige Wiederherstellungs- und Finanzfreigabe, danach unveränderte
  ursprüngliche Lohn-/Fallquittungen, PDFs, Reisegeldquelle und Jahresbasis.
- Ungültige Details, gefälschter Quellhash, fehlende Zahlung, fremde Person,
  anderer Monat, tatsächlicher M-Reisebeleg und echte Rückzahlung werden
  geprüft. Ein aktueller geänderter Zahlungsstand sperrt neue Verwendung,
  ohne das historische Originalreplay umzuschreiben.
- Eine eigene CRLF-Codekopie erzeugt über die unveränderten Backenddienste
  echte v9-/V10-Originale und ein PDF. Die LF-Codebasis validiert anschließend
  genau diese Daten und übernimmt das PDF bytegleich. Es werden keine
  Provenancehashes von Hand ersetzt. Diese Prüfung betrifft den tatsächlichen
  Zeilenendenwechsel; eine Windows-Geräteabnahme ist damit nicht behauptet.

Die nachgetragenen Ergebnisse und vollständigen Logs liegen unter
[`evidence/factor-travel-pg-review-2026-11-09`](evidence/factor-travel-pg-review-2026-11-09).

Vier PostgreSQL-Szenarien sind in getrennten Läufen bestanden: zwei Gegenproben
für Quellen und Zahlungspräfix, der vollständige Faktor-/Jahresbasis-/Restorefall
(70,942 Sekunden) und der frische Entzug von Finanz- und Personalrechten
(22,856 Sekunden). Der CRLF-Originalfall besteht separat in 6,636 Sekunden.
Der Anwendungsbenutzer `smartplan-online` darf die vier geprüften Lohnfall-,
Lohnlauf-, Reisezahlungs- und Reisegeldflusstabellen nicht direkt ändern.
43 bereits vorhandene `payroll_*.py`-Dateien sind bytegleich zur Basis
`a7c1e0b`; die Prüfung verändert keinen Rechenkern.

Der Zwischenlauf mit beiden erfolgreichen Gegenproben enthält noch den
anfänglichen `pg_dump`-Infrastrukturfehler und wird ausdrücklich nicht als
vollständig erfolgreicher Lauf ausgegeben. Die folgenden Einzelprotokolle
belegen dessen abgeschlossenen Restore sowie den zusätzlichen Rechtefall.
Die eigene PostgreSQL-16.15-Testinstanz und ihre Restore-Datenbank sind entfernt.

## Befunde und erhaltene erste Fehlläufe

Ein echter HTTP-Befund wurde vor seiner Korrektur reproduziert:
`details=null` führte auf der Ausgangsfassung zu HTTP 500 statt 400.
`7db66f1` prüft die Objektform vor der Mitgliedschaftsabfrage; die Gegenprüfung
umfasst Null, Zahl, Bool, Liste und String bei Vorschau und Speicherung.

Der erste eigene Quellenaufbau versuchte, einen bestehenden Minijob-
Identitätsbeleg auf einen anderen Profilursprung umzuschreiben. Die API wies
das korrekt ab. Der Aufbau legt nun eine neue unveränderliche Identitätsquelle
je Profil an. Weitere anfängliche Prüfannahmen erwarteten 409 statt der
korrekten 400 bei leerer Quellenliste beziehungsweise 404 für eine fremde
Personalquelle. Diese Fehlläufe bleiben dokumentiert.

Der erste Restore-Anlauf erreichte Jahresbasis und Integritätsprüfung, konnte
jedoch mangels `pg_dump` im Prozesspfad noch keine Sicherung ausführen. Der
Nachlauf verwendet eigene streng auf den Testcontainer, Port und die beiden
Testdatenbanken begrenzte Werkzeugadapter; keine Adapter anderer laufender
PostgreSQL-Prüfungen wurden wiederverwendet.

Die zwischenzeitlich gemeldete mögliche v9-Zeilenenden-Inkompatibilität hat
sich in der tatsächlichen CRLF-Originalprüfung nicht bestätigt. Ebenso ist
die bestehende Sperre einer M-Reisezahlung vor der erforderlichen Lohn-
Verarbeitung ein erwartetes Verhalten und wurde nicht umgangen.

Keine echten Mitarbeiterdaten, Bankaufrufe, Zahlungen, Meldungen oder
Kundenserver wurden verwendet. Veröffentlichung, Geräteabnahme und
steuerliche Produktivfreigabe sind keine Ergebnisse dieses Testpakets.
