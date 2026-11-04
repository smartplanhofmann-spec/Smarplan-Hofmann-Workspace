# Unabhängige frühe Prüfung der Jahresverträge

Stand04.11.2026. Geprüft wurden die vollständigen Vertragsentwürfe
`/workspace/smartplan-opening-year-values-20261104/docs/CRM_ERP_JAHRESVORTRAG_VERTRAG.md`
und `docs/CRM_ERP_JAHRESPAKET_VERTRAG_2026-11-04.md` sowie die genannten bereits
vorhandenen und gerade entstehenden Kernpfade. Beide Pakete waren in Entwicklung,
nicht eingefroren. Diese frühe Prüfung ist keine Gesamtabnahme. Der Reviewer hat
keinen Produktcode und keine Ownertests geändert; konkrete Funde/Grenzfälle wurden
an beide Owner und die Integration gemeldet.

## Jahresvortrag: verbindliche Grenzen der Integration

Die Trennung von historischen Journalwerten, tatsächlichem neuem Geldfluss und
bereits ausgeübtem Vorsteuerrecht ist im Vertrag ausdrücklich richtig angelegt.
`accounting_year_opening_rules.calculate` erhält Zahlungstag und ursprünglichen
Vorsteuerzeitraum getrennt. Der normale Cash-/Vorsteuerannahmeweg darf dadurch
keine Datumssperre verlieren. Der neue historische VATeintrag darf keine neue
Anspruchskennung, Liquiditätsbewegung oder Bankkandidaten erzeugen.

Folgende Fälle sind für die spätere öffentliche Annahme konkret erforderlich:

1. **Belegte Hälften:** Rechnung119EUR, alte Zahlung59,50EUR im August, neuer
   Rest59,50EUR im November; Jahresausgabe119EUR, nur59,50EUR neue Liquidität,
   unveränderter Anfangssaldo. Früher ausgeübte Vorsteuer19EUR erscheint genau
   einmal in ihrem ursprünglichen historischen Zeitraum; November erzeugt sie
   nicht erneut. EÜR-Zahlung der Vorsteuer bleibt nach den echten Zahlungsteilen
   getrennt nachvollziehbar.
2. **Jahresgrenze:** Ein im Jahr2025 entstandenes/ausgeübtes Vorsteuerrecht und
   eine tatsächliche Zahlung2026 erzeugen im Vortrag2026 keine zweite
   Vorsteuerwirkung2025. Quellenbeleg und Jahreswert sind verschieden.
3. **Zeitangabe allein:** Der gelesene Purekernel setzt `complete_prior_period`
   allein bei Zeitraum01.01. bis Start−1Tag, auch bei leeren Quellen/Kontrollsummen.
   Das ist noch kein freigeschalteter Vollständigkeitsfehler, da der neue Resolver
   erst entsteht. Die Integration darf diese geometrische Eigenschaft aber nicht
   ohne eigenständigen Zeitraumjournal-/Nullumsatznachweis und Prüfung aller
   bekannten Altquellen zum Entfernen von `partial_period_profile_coverage`
   verwenden. Bekannte historische AfA/Sonderwerte bleiben offen.
4. **Wirtschaftliches Doppeloriginal:** Der frühe Purekernel prüft Originalhash
   und externe Kennung. Zusätzlich ist die bereits von `normalize_item` gebildete
   wirtschaftliche `original_identity` zu beachten: zweiter Scan mit anderen
   Bytes und neuer Altsystemkennung, aber gleiche Gegenpartei/Rechnungsnummer/
   Rechnungsdatum, darf dieselbe Zahlung nicht nochmals tragen. Prüfung auch
   über zwei Annahmen und die Quellenarten `opening_item`/`closed_trade` hinweg.
   Eine legitime weitere Teilzahlung derselben Rechnung darf umgekehrt nicht
   pauschal als zweite Rechnung verworfen werden.
5. **Deckungskette:** Jan–Mai plus Juli–Oktober schließt Juni nicht. Zwei
   überlappende Teilvorträge brauchen explizite Deckungs-/Verbrauchsprüfung auch
   dann, wenn ihre Geldzeilen zufällig disjunkt sind. Eine als vollständig
   erklärte Quelle darf einen dem System bereits bekannten Altposten nicht
   einfach weglassen.
6. **Korrektur und Altpaket:** Gegenbuchung vor Quellkorrektur, gesperrte Perioden
   zuerst begründet öffnen, aktuelle Quellen/Profilbindung für die neue Annahme.
   Historische alte Annahme und alter Export bleiben dabei unverändert; Replay
   benötigt weiterhin die vorgesehenen aktuellen Rechte/Restorefreigaben.

Die Punkte3–5 wurden als konkrete Grenzen für die noch entstehende Integration
gemeldet, nicht als bestätigte Fehler einer bereits freigegebenen API.

## Jahrespaket: ein tatsächlich reproduzierter früher Fehler

Der tatsächliche temporäre Gegenfall verwendete `YearPackageTests`, seine echte
lokale Datenbank und unveränderte Szenariohelfer: Ausgangsrechnung erzeugen,
tatsächlichen Zahlungseingang als `cash` bestätigen, Jahresexport bestätigen,
`accounting_year_package_v1.build` ausführen. Das korrekte Paket enthielt ein
Rechnungsoriginal und wurde vom unabhängigen Offlinepfad akzeptiert.

Anschließend wurden **nur im Speicher** der `document`-Beweisknoten, seine Links,
die Originaldatei und ihr Manifestdeskriptor entfernt. Die äußeren Datei-/Manifest-
Prüfsummen wurden neu berechnet. Ursprüngliche EÜR-Journalentscheidungen,
Annahmebefehle, Quellpayloads und deren echte Hashes blieben unverändert.
Der frühe Prüfer akzeptierte trotzdem `verified=True, originals=0`.

Damit fehlte eine intrinsische Prüfung der notwendigen Dokument-/Belegverknüpfung
aus dem tatsächlichen `cash_original`-Payload. Nur vorhandene Links abzulaufen
belegt nicht, dass alle erforderlichen Links vorhanden sind. Ein separat
bestätigter, unveränderter äußerer ZIPhash hätte die Manipulation erkannt; das
ersetzt nicht die zusätzlich versprochene interne Vollständigkeitsprüfung.

Der Owner ergänzte die Bindung von Cashoriginalen und dokumentarischen Komponenten
an ihre ausdrücklich benannten Originale/Vorläufer. Der Reviewer wiederholte
**denselben** temporären Gegenfall unverändert:

```text
original_verified= True original_count= 1
STRIPPED_OUTGOING_ORIGINAL_REJECTED= Missing documentary original link
verifier_sha256= 3dcec8ffa0745bcae3097df125bd4cfe11ffdf2606e50b8a4a083a92e2187487
```

Der vorherige negative Lauf wurde tatsächlich ausgeführt und unmittelbar
gemeldet. Sein damaliger Quellhash wurde nicht separat konserviert; daher wird
keine exakte Bindung an einen erfundenen früheren Freeze behauptet. Der Owner
übernimmt den Fall in seine dauerhafte Testdatei. Dies ist eine bestätigte enge
Behebung, kein Abschluss der noch laufenden Paketimplementierung.

## Weitere konkrete Paketabnahmen

- Eingangsbeleg mit damals gebundener Prüfungrev1, späterer Prüfungrev2 und
  Profilkorrektur: erneuter Abruf des alten Exports liefert die damalige
  Belegprüfung und identische Paketbytes, keine heutigen Kopfdaten.
- Korrektur im Jahr2026 eines relevanten Ursprungs aus2025: nur die notwendige
  Ursprungskette aus2025 einschließen; kein ganzes fremdes Jahr. Entfernen eines
  erforderlichen Vorgängers trotz neu gerechneter äußerer Hashes zurückweisen.
- Historische Anlage ohne aktuelle Jahresbuchung, aber ausdrücklich im damaligen
  Report enthalten: ihr Original und tatsächlich gebundene frühere Fassungen
  gehören zur Auswahl; ein später aufgehobener Vortrag verändert den alten
  Prüfstand nicht.
- Ein rekursiv notwendiger Beleg eines anderen Projekts benötigt dessen aktuelle
  Quellfreigabe. Ein Recht nur für den Hauptbeleg reicht nicht. Ungebuchte
  damalige Reportverweise benötigen ebenso die aktuelle Rechteprüfung.
- Öffentliche Lohn-/Reiseprojektion kann Finanzsummen belegen, ohne private
  Personal-/Reiseoriginale einzuschließen. Tatsächliche private Namen/IDs/Dateien
  im Paket prüfen, nicht nur ein gesetztes Datenschutzflag.
- Ein später ergänzter Beleg heilt keine offene Frage im alten Report. Neue
  unbekannte Jahresvortragsquellen dürfen bis zu ihrem eigenen Auswahl-/Prüfvertrag
  kein technisch vollständiges Paket vortäuschen.
- Reihenfolge, ZIPzeit, Benutzer des Abrufs, Uhr, spätere Buchungen und späterer
  Profilkopf ändern keine Bytes einer festen Paketversion. Die ursprünglichen
  Annahmeidentitäten bleiben Bestandteil der historischen Belege.
- Geschlossene Datei- und Beweisknotenliste prüfen: keine fehlenden notwendigen
  Originale, keine unverbundenen Zusatzoriginale, keine doppelten ZIPnamen,
  Pfadtraversierung oder ungeprüften fremden Skripte. Die separate Herkunftsbindung
  ist von der inneren Hashkonsistenz zu unterscheiden.

Es wurden keine Produktionskontakte, Commits, Registryänderungen oder
Finanzmutationen an Benutzerbeständen vorgenommen. Der temporäre Gegenfall
arbeitete ausschließlich mit lokalen synthetischen Fixtures.
