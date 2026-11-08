# Steuerklasse IV mit Faktor – additiver Vollmonatsfall 2026

Stand: 08.11.2026. Dieser Lieferabschnitt gehört zu R09.03 des unveränderten
Gesamtziels. Er vervollständigt einen benannten Lohnfall, keine gesamte
Lohnabrechnung und keine produktive Meldezulassung.

## Verhalten und fachliche Grenze

Browser und native App bieten im belegten Lohnprofil jetzt ausdrücklich
**Regulär: Steuerklasse IV mit eingetragenem Faktor · Vollmonat** an. Der
tatsächlich gültige ELStAM-Faktor wird mit genau drei Nachkommastellen aus
dem ausgewählten Personaloriginal erfasst. Die Oberfläche akzeptiert Komma
oder Punkt; API und Archiv verwenden exakten Dezimaltext. Es gibt keine
Vorbelegung, automatische Faktorermittlung oder externe Personenabfrage.

Der neue Umfang benötigt reguläre Beschäftigung, Steuerklasse IV, bestätigte
null Frei-/Hinzurechnungsbeträge, den Faktor-Sachverhalt und die vorhandenen
geprüften Voraussetzungen für gesetzliche Pflichtversicherung und Vollmonat.
Fehlende Quellen, Versicherungs-/Altersfälle und sonstige Sonderfälle bleiben
sichtbar gesperrt. Ein historisches Profil mit bloßem Sonderfallhaken erhält
keinen geschätzten Faktor. Faktor-Teilmonate, Midijobs und Einmalbezüge sind
mit diesem Lieferabschnitt noch nicht freigeschaltet.

Die Vorschau und der private PDF-Beleg nennen den tatsächlichen Faktor.
Bestätigung, Originalwiederholung nach Antwortverlust, Korrekturdifferenzen,
historische PDF/JSON-Belege, Jahresübersicht und der reduzierte Mitarbeiterbeleg
verwenden den neuen Umfang. Belegte tatsächliche Nettozahlungen und gesonderte
Abführungen lassen sich über die bestehende private Zahlungskette in die EÜR
übernehmen. Die Berechnung selbst erzeugt keinen Geldfluss.

## Regeln und überprüfte Quellen

Der unveränderte Standard-Jahreskern liefert die jährliche Steuer und die
kinderbereinigte Maßstabsteuer. Der Faktor wird vor der Abrundung dieser
Jahreswerte auf ganze Euro angewendet. Anschließend folgen Solidaritätsgrenze,
Milderungszone und Periodenverteilung. Die monatliche Kirchensteuer verwendet
die faktorisierte Maßstabsteuer und den bestehenden geprüften Landessatz.
Eine Multiplikation einer fertigen Monatssteuer ist kein zulässiger Ersatz.

Neue Versionen: `bmf_2026_2025_11_12_standard_factor_v1` und
`de_2026_standard_factor_monthly_v8`. Die historischen Standard-, Tages- und
Einmal-PAP-Dateien sind bytegleich erhalten; der
[Hashnachweis](evidence/payroll-factor-2026-11-08/historical-kernel-hashes.json)
bindet sie an den bisherigen Quellstand. Alte Regelstände nehmen keine neuen
Faktorprofile stillschweigend an. Es ist keine Schemamigration erforderlich.

Quellen: [§ 39f EStG](https://www.gesetze-im-internet.de/estg/__39f.html),
[BMF-XML-Verzeichnis](https://www.bmf-steuerrechner.de/interface/pseudocodes.xhtml),
[PAP 2026, Anlage 1](https://www.ihk-muenchen.de/ihk/documents/Recht-Steuern/Steuerrecht/Einkommensteuer/2025-11-12-PAP-2026-anlage-1.pdf).
Die dort identifizierte amtliche XML-URL lieferte im Recherchewerkzeug keinen
lesbaren XML-Inhalt. Die separat geprüfte XML stammt daher ausdrücklich aus
einem [fest gepinnten öffentlichen Spiegel](https://raw.githubusercontent.com/manuelbusch/paprun/cdf564daec7f617d54181eb8b14232e48a59dd7a/tests/data/Lohnsteuer2026.xml),
nicht aus einem behaupteten erfolgreichen Direktabruf beim BMF. SHA-256:
`63d8981646d139eba2f4dd990c13b43c4fb3883b402a5a40cddf253aa7aa96b4`.
Eine zweite öffentliche Kopie besitzt dieselbe Git-Blobkennung.

## Tatsächlich ausgeführte Prüfungen

- 170 eingefrorene Faktorvergleichsfälle aus separat ausgeführten Java-
  Dezimalausdrücken der gepinnten XML, ohne Aufruf des Python-Rechenkerns.
  Ein offline ausführbarer Generator verlangt vor Ausführung genau diesen
  Quelldigest. Sein XML-Runner stimmt zusätzlich mit 207 unabhängig beschafften
  öffentlichen Vergleichswerten überein; das ist kein direkter BMF-API-Test.
- 630 Lohnfälle im breiten Python-Lauf: 619 bestehen dort, elf HTTP-Fälle
  scheitern zunächst ausschließlich am äußeren Socketverbot. Genau dieselben
  elf Fälle bestehen im Nachlauf mit lokalen Sockets. Zusätzlich besteht die
  neue Faktor-Zahlungs-/EÜR-Kette; fünf Profilfälle sind dabei erneut geprüft.
- Sechs reale PostgreSQL-/MFA-/HTTP-Fälle ohne Skip, darunter Faktor-Neustart,
  Originalwiederholung und vollständiger tatsächlicher Backup/Restore.
  Die zunächst falsche Rolle/Eigentümerschaft der neu erstellten Einwegdatenbank
  wurde nur dort korrigiert; der Anwendungsschutz wurde nicht gelockert.
- 306 native Lohnfälle; Analyse ohne Befund. Nach Klarstellung der Sonderfall-
  Beschriftung bestehen die fünf gezielten Faktor-Appfälle erneut.
- 866 Node-Modulfälle und 16 Paketprüfungen. Neue Backendmodule sind in beiden
  Windowspaketen und in deren CI-Kopierliste enthalten.
- Reale Chromium-/MFA-/HTTP-Abläufe für Faktor und bestehenden Midijob. Faktor
  prüft Genauigkeit vor POST, verlorene Antwort, exakt wiederholten Auftrag,
  Faktorkorrektur, Steuervarianz, altes Original-PDF, Jahreswerte, Mitarbeiterbeleg
  und Darstellung bei 390 Pixeln. Chromium bestätigt seine tatsächlichen
  Namespace-/PID-/Netzwerk-/Seccomp-Sandboxes vor dem Zugriff.

Beispiel mit synthetischem Gehalt von 5.000,00 EUR und geprüftem Faktor 0,753:
589,08 EUR Lohnsteuer, 3.323,42 EUR Netto. Bei belegter Korrektur auf 0,900
beträgt das Netto 3.208,34 EUR; die Steuerdifferenz beträgt 115,08 EUR.
Alle Sozialkomponenten bleiben gegenüber dem ursprünglichen Standardfall
gleich. Nach belegter Nettozahlung und sämtlichen gesondert belegten Abführungen
entstehen im geprüften EÜR-Fall 6.192,00 EUR Ausgaben ohne Vorsteuer.

[Maschinenlesbarer Prüfnachweis und Protokolle](evidence/payroll-factor-2026-11-08/verification.json).
Eine neue Serverinstallation, vollständige Remote-CI dieses Faktorstands,
echte Windows-/iPhone-Bedienung und fachliche Freigabe werden damit nicht
vorweggenommen. Weitere benannte Lohn-/EÜR-Fälle und Abnahmen A–G bleiben Arbeit.

## Reproduktion

```sh
python3 scripts/payroll-factor-reference.py --xml /pfad/Lohnsteuer2026.xml --output /tmp/faktor-vergleich.json
PYTHONPATH=backend .venv/bin/python -m unittest discover -s backend -p 'test*payroll*.py' -v
PYTHONPATH=backend:backend/online .venv/bin/python -m unittest online.test_business_payroll_pg -v
```

Der Generator braucht Java 21 für den gesonderten Prüflauf; das Produkt benötigt
weder Java noch Netzwerk für die Faktorberechnung. PostgreSQL verwendet nur
die bestehende geschützte lokale Einweg-Testkonfiguration; ohne diese würde
der normale Runner überspringen. Der hier dokumentierte Lauf hat alle sechs
Fälle tatsächlich ausgeführt. Native Tests verwenden den vorhandenen Clang-
Compiler und Pub-Cache. Browserziel: `SMARTPLAN_BROWSER_WORKFLOW=payroll-factor`.
