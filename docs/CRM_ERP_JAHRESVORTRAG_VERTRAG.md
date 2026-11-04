# Belegte Jahreswerte vor dem Softwarebeginn – Vertrag und Umsetzung

Stand 04.11.2026. Dieser neue Umfang wird ausschließlich im isolierten Baum
`/workspace/smartplan-opening-year-values-20261104` entwickelt. Ausgangspunkt ist
Hauptstand 80e051a mit dem exakt eingefrorenen Altpostenbackend; die 1959 Dateihashes
stehen in `work/verification/opening-items-backend-baseline.json`.
Der Backendvertrag ist implementiert und mit echten Quellen, HTTP und PostgreSQL geprüft. Browser-/Nativeintegration und unabhängige Gesamtintegration stehen noch aus.

## Nachgewiesene Lücke

Der erneut ausgeführte R08-Audit ist unter
`work/verification/year-values-baseline-2026-11-04.json` abgelegt. Beim Beginn am
01.11.2026 bleibt eine tatsächlich im August bezahlte Hälfte 59,50 EUR zu Recht nur
Herkunft des Altpostens. Die neue Hälfte am 01.11. ergibt 59,50 EUR EÜR-Ausgabe; die
bekannten Jahresausgaben sind 119 EUR. `partial_period_profile_coverage` bleibt
offen. Ein vollständig bezahlter alter Beleg besitzt keinen offenen Posten und
wird deshalb im Altpostenmodul abgewiesen. Der gewöhnliche EÜR-Weg sperrt neue
Vorgänge vor dem bestätigten Softwarebeginn.

Anfangssalden und Altposten werden unverändert erhalten. Es gibt keine pauschale
Profilrückdatierung und keine erfundene Zahlung am Importtag.

## Amtliche Grundlage und Grenzen

Am 04.11.2026 direkt gelesen:

- [§ 4 Abs. 3/4 EStG](https://www.gesetze-im-internet.de/estg/__4.html): EÜR stellt
  betriebliche Einnahmen und Ausgaben gegenüber; besondere Anlagen-/AfA-Regeln
  bleiben eigenständig.
- [§ 11 Abs. 1/2 EStG](https://www.gesetze-im-internet.de/estg/__11.html): Tatsächliche
  Zufluss-/Abflussjahre bleiben maßgeblich. Ausnahmen werden hier nicht erweitert.
- [§ 146 Abs. 1, 4–6 AO](https://www.gesetze-im-internet.de/ao_1977/__146.html): Einzelne,
  vollständige und geordnete Aufzeichnungen sowie erkennbare Originale/Änderungen
  gelten auch bei entsprechenden freiwilligen Aufzeichnungen.
- [§ 147 Abs. 1/2/6 AO](https://www.gesetze-im-internet.de/ao_1977/__147.html): Belege und
  Aufzeichnungen müssen aufbewahrt und lesbar/auswertbar erhalten werden; ein
  Systemwechsel hebt die Nachweispflichten nicht auf.

Die konkrete Übernahme-API und ihre Kontrollsummen sind daraus abgeleitete
Softwareentscheidungen, keine gesetzlich vorgeschriebene Dateiform oder Freigabe.
Die bereits unabhängig gelesenen USt-Grundlagen und die Trennung von gezahlter
Vorsteuer/EÜR und tatsächlich ausgeübtem Abzug gelten weiterhin nach
[der Altposten-Quellengegenprüfung](CRM_ERP_ALTPOSTEN_QUELLEN_GEGENPRUEFUNG_2026-11-04.md).
Es wird keine neue amtliche Formularzuordnung 2026 behauptet.

## Enger erster Quellenvertrag

Voraussetzung bleibt das fortgeführte Einzelunternehmen mit unveränderter EÜR,
Regelbesteuerung, genehmigter Istbesteuerung und SKR04. Der Vortrag betrifft
belegte Vorgänge desselben Kalenderjahres **vor** `bookkeeping_start`.
Gewöhnliche inländische, vollständig betriebliche19-/7-Prozent-Fälle bleiben von
Anlagen, Lohn, privaten Anteilen, Auslands-/Sonderfällen und Methodenwechseln getrennt.

1. **Kanonischer Altpostenbezug:** Alte Zahlungsanteile und bereits ausgeübte
   Vorsteuer werden aus genau der unveränderten bestätigten Altpostenfassung
   gelesen. Datum, Centwerte, Originale und externe Rechnungsidentität werden
   nicht ein zweites Mal frei eingegeben. Beträge außerhalb des Berichtsjahres
   begründen keine zusätzlichen Werte dieses Jahres.
2. **Vollständig bezahlte externe Altbelege:** Ursprüngliche Rechnung, tatsächliche
   alte Zahlungsanteile und deren schon erfolgte steuerliche Behandlung werden
   ausdrücklich mit Originalen übernommen. Die vollständige Erledigung ist
   belegt; kein erfundener offener Rest wird angelegt. Ein noch offener externer
   Beleg gehört zuerst in den Altpostenweg und wird anschließend kanonisch gebunden.
3. **Perioden-/Journalnachweis:** Ein eigenes Original belegt Zeitraum, ursprüngliche
   Buchungsidentitäten, Konten/Kategorien, Kontrollsummen und Vollständigkeitsprüfung.
   Die exakten übernommenen Werte müssen diese ausdrücklich eingegebenen Summen
   ergeben. Ein Einzelbeleg beweist keine Januar–Oktober-Deckung.

Historische EÜR-Werte und historische USt-Werte behalten ihre getrennten ursprünglichen
Tage/Perioden. Eine im Juni bereits ausgeübte Vorsteuer wird nicht zum neuen Anspruch
im November. Eine im August tatsächlich bezahlte Vorsteuer gehört zur ursprünglichen
EÜR-Zahlung. Frühere tatsächliche Finanzamtszahlungen/-erstattungen dürfen nicht aus
einer Einzelrechnung abgeleitet werden; nicht unterstützte Sachverhalte bleiben offen.

## Journal- und Vollständigkeitsverhalten

Der Vortrag besitzt eine eigene versionierte Quelle und einen ausdrücklichen
EÜR-Übernahmevorgang. Eine eng auf diese geprüfte Quelle begrenzte Übernahme kann
historische Journalwerte vor dem Softwarebeginn aufnehmen. Der gewöhnliche
`cash`-/`input_vat`-Weg behält seine bisherige Datumssperre. Jede übernommene Zeile
bleibt als aus dem Altsystem übernommener Wert mit ursprünglicher Identität erkennbar.

Die Quelle erzeugt **keine** Geldbewegung, Bankkandidaten, neue Geldkontosalden oder
erneuten steuerlichen Anspruch. Die Jahresprojektion zählt belegte alte und neue
Journalwerte einmal. Der laufende Monat zählt keine alten Zahlungen hinzu.
Bereits eingefrorene Berichte und Exportbytes bleiben auf ihrem damaligen Journalstand.

Eine erklärte Teildeckung bleibt Teildeckung. Die bisherige Jahreslücke kann erst
entfallen, wenn der belegte Zeitraum den gesamten Jahresanfang bis unmittelbar vor
dem Start abdeckt, sämtliche Kontrollsummen stimmen und alle bekannten kanonischen
Vorwerte/Überschneidungen geklärt sind. Bekannte alte Anlagen-AfA oder andere noch
nicht unterstützte Vorwerte dürfen nicht still als Null gelten. Der Abschluss bleibt
für solche Fälle gesperrt, solange kein passender Quellenvertrag besteht.

## Korrektur, Rechte und Beständigkeit

Originale, Annahmequittungen und Ereignisse sind append-only. Eine korrigierte
Übernahme wird ausdrücklich neu angenommen; aktive abhängige EÜR-Übernahmen sind
vor Änderung ihrer Quelle gegenzubuchen. Gesperrte betroffene Perioden müssen
vorher begründet geöffnet werden. Die aktuelle Profil-/Quellfassung wird geprüft;
eine exakte alte Annahme bleibt historisch wiederholbar und benötigt weiterhin
aktuelle Rechte, aktivierte Finanzfunktion und Restorefreigabe.

Ursprüngliche externe Buchungsidentitäten und wirtschaftliche Originalanteile
dürfen unter einer zweiten Kennung nicht nochmals verbraucht werden. Vorhandene
eigene Journalwerte im Übernahmezeitraum werden als Überschneidung erkannt;
keine heimliche Doppelzählung durch importierte Kopien. Korrektur alter Altposten-
oder Anlagenbindungen muss abhängige Jahreswerte ausdrücklich berücksichtigen.

Implementierte Module: `business_accounting_year_openings.py`,
`accounting_year_opening_rules.py`, `accounting_year_opening_sources.py`.
Neue Familie: `business_accounting_year_opening_originals`, `_events`, `_requests`.
Finanzhorizont 15/Restorebericht 16 ist für diesen Umfang reserviert. Alte
Horizonte und Freigabequittungen bleiben unverändert überprüfbar.

## Abnahme und Fortschritt

- [x] Isolierter Ausgangsstand und vollständige Hashbasis angelegt.
- [x] Tatsächliche Lücke mit dem bestehenden Audit erneut ausgeführt.
- [x] Aktuelle amtliche Aufzeichnungs-/EÜR-Grundlagen gelesen; enger Vertrag festgehalten.
- [x] Kanonische Quellen, vollständige alte Belege und kontrollierter Zeitraum implementiert.
- [x] 59,50 EUR alt + 59,50 EUR neu ergibt 119 EUR Jahresausgabe, bei nur 59,50 EUR neuer
  Liquiditätsbewegung und unverändertem Anfangssaldo.
- [x] Vollständig bezahlte Altbelege, falsches Jahr, fehlende Deckung, doppelte
  Originalidentität, abweichende Kontrollsummen, Korrekturen, Perioden und Antwortverlust.
- [ ] Alte Exporte unverändert; echter befüllter Restore; unabhängige Gegenprüfung.
- [ ] Stabile API-/Fixtureübergabe und beide Clients mit tatsächlichen Abläufen.

Die nächste getrennte Aufgabe des R08-Audits – ein enges Jahresbelegpaket für den
Steuerberater mit Offlineprüfung – wird durch diesen Vortrag noch nicht als erledigt
bezeichnet.

## Aktueller Nachweis

25 eigene Kernel-/Domain-/Registrierungs-/echte Local- und MFA-HTTP-Prüfungen in16,673s grün; danach zwei zusätzliche echte Nulljournal-/Atomaritätsfälle in1,424s grün. PostgreSQL:3/3 in17,276s grün, darunter zwei konkurrierende Verbindungen, Runtime-ACL/Neustart und tatsächlicher befüllter Dump/Restore16 mit unveränderten Originalen, Quittungen und alten/neuen Exporten.

Bestehende Finanzregression:117/118 grün; der einzige Fehler war die alte Gesamthorizont-Erwartung14 statt15. Der eng angepasste Test und14 weitere unveränderte historische Scopefälle sind anschließend15/15 grün. Weitere aktuelle/historische Finanzprüfung:173/181 zunächst grün; ausschließlich8 veraltete aktuelle Horizont-/Feldmengen, nach enger Testanpassung8/8 grün. Die ursprünglichen roten Logs bleiben erhalten; keine Gesamtprüfung sämtlicher Softwaremodule wird behauptet.

Der genaue Clientvertrag und tatsächlich erzeugte Fixture stehen in [CRM_ERP_JAHRESVORTRAG_API.md](CRM_ERP_JAHRESVORTRAG_API.md). Kein realer Geschäftsbestand, kein echter Bankauftrag und keine Steuermeldung wurde erzeugt.

Vollständiger Backendnachweis: [CRM_ERP_JAHRESVORTRAG_BACKEND_ABNAHME_2026-11-04.md](CRM_ERP_JAHRESVORTRAG_BACKEND_ABNAHME_2026-11-04.md).
