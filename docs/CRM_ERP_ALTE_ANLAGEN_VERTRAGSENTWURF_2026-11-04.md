# Historische Anlagen: nächstes getrenntes Umsetzungspaket

Stand 04.11.2026. **Entwurf, noch keine implementierte Anlagenübernahme.**
Die belegten Geldkonto-Anfangsbestände haben einen eigenen geprüften Vertrag
(`CRM_ERP_ANFANGSSALDEN_API.md`). Dieser Entwurf bereitet den anschließenden
Anlagenvortrag vor; er ändert keine Buchung, kein Original und keinen Runtimecode.
Die Umsetzung soll auf einem eigenen festen Checkpoint erfolgen, damit die
laufende Clientabnahme der Geldkonto-Anfangsbestände reproduzierbar bleibt.

## Aktuell gelesene Rechtsquellen

Alle drei folgenden amtlichen Einzelnormen wurden am 04.11.2026 direkt gelesen.
Die Folgerungen für das Datenmodell sind eigene technische Ableitungen, keine
Bestätigung konkreter Anlagenwerte oder eines vollständigen Steuerjahres.

| Quelle | Für dieses Paket relevante Aussage |
| --- | --- |
| [EStG §4 Abs.3](https://www.gesetze-im-internet.de/estg/__4.html) | Auch bei EÜR gelten die AfA-Vorschriften. Anlagen sind mit Anschaffungs-/Herstellungsdatum und Kosten beziehungsweise Ersatzwert in einem fortlaufenden Verzeichnis zu führen. |
| [EStG §7 Abs.1–3](https://www.gesetze-im-internet.de/estg/__7.html) | Lineare AfA verteilt die Basis auf die betriebsgewöhnliche Nutzungsdauer; im Anschaffungsjahr gilt die gesetzliche Monatsregel. Degressive Verfahren, bestimmte Elektrofahrzeuge und Methodenwechsel folgen eigenen Regeln. |
| [EStG §9b](https://www.gesetze-im-internet.de/estg/__9b.html) | Abziehbare Vorsteuer gehört nicht zu den Anschaffungs-/Herstellungskosten. Vorsteuerberichtigungen sind ein eigener Vorgang. |

Ein Wechsel der Software ist kein neuer Anschaffungsvorgang. Der vorhandene
AfA-Beginn darf deshalb nicht auf `profile.bookkeeping_start` zurückgesetzt
werden. Ein bisheriger Buchwert darf nicht als neue Anschaffungskosten behandelt
werden. Die Übernahme erzeugt weder eine neue Zahlung noch erneut Vorsteuer
oder sofortigen Aufwand. Eine später ausdrücklich angenommene laufende AfA
ist dagegen eine ergebniswirksame Buchung ohne Geldbewegung.

## Tatsächlicher Ausgangspunkt im Code

`backend/business_accounting_euer.py` unterstützt belegte neue lineare Anlagen:
`_prepare_asset` verlangt einen geprüften Eingangsbeleg und eine Vorsteuerentscheidung;
`_economic`/`_profile_dates` weisen vor dem Buchführungsbeginn liegende Daten ab.
`_prepare_depreciation` berechnet eine Jahres-AfA mittels kumulierter
Cent-Rundung und verweist auf eine aktive Anlagenbuchung. Das ist für alte
Anlagen ohne neue Rechnung kein vorhandener Übernahmepfad.

Die vorhandenen tatsächlichen Integrationspunkte sind:

- `_source_access` und `_validate_source`: eine eigene Anlagenübernahmequelle
  braucht frische Fachrechte und eine unabhängig prüfbare historische Fassung.
- `_ECONOMIC`/`_prepare_*`: laufende AfA aus dem Übernahmebestand als eigener,
  versionierter wirtschaftlicher Quellenfall im bestehenden EÜR-Journal.
- `_catalog`/`_report`: offene Vortragsklärungen, fehlende laufende AfA und
  Anlagenverzeichnis; keine Ergänzung von `cash_movements` aus dem Vortrag.
- `_counter_target`: aktive AfA muss vor einer Änderung ihrer Quellenfassung
  ausdrücklich gegengebucht werden. Eine Ersatzfassung allein darf keine bereits
  wirksame AfA stillschweigend ändern.
- `_ledger`/`_validate_report`/`exported`: alte Quellenstände, Journalpräfixe,
  eingefrorene Berichte und CSV-Hashes müssen unverändert validierbar bleiben.
- `business_schema.py`, `business_api.py`, `business_organization.py`,
  `company_export_catalog.py` und Paketlisten: neue Integritäts-/Restoreversion
  und minimale Fachregistrierungen erst im neuen Implementierungspaket.

## Erforderliche Eingangsdaten

Für jede übernommene Anlage sind eine stabile Anlagenidentität und eine
eindeutige betriebliche Inventarnummer nötig. Mehrere Anlagen können auf
verschiedene Positionen derselben ursprünglichen Anlagenliste verweisen; ein
Dokumenthash allein ist daher keine ausreichende Anlagenidentität.

Eine bestätigte Fassung muss mindestens enthalten:

- Bezeichnung, Anschaffungs-/Herstellungsdatum, ursprünglichen Nutzungs-/AfA-Beginn,
  geprüfte betriebliche Zuordnung und vollständige oder gesondert belegte
  betriebliche Kostenbasis einschließlich der Behandlung abziehbarer Vorsteuer.
- Gewählte und belegte Methode, ursprüngliche Nutzungsdauer, frühere Änderungen
  und gegebenenfalls bereits vollständig verbrauchte Nutzungsdauer. Keine
  automatisch aus Gerätename oder Einkaufspreis geratene Dauer.
- Exakten Übernahmestichtag `profile.bookkeeping_start` vor dessen erster
  Bewegung, Originalnachweis mit SHA-256 und nachvollziehbarer Position/Referenz.
- Bisherige kumulierte AfA, Restbuchwert und ausdrücklich getrennte bereits
  verbuchte AfA des Übernahmejahres. Die Werterelation muss in Cents aufgehen.
- Geprüfte Kontenzuordnung, Profilfassung, Prüfgrund und ausdrücklich bestätigte
  Voraussetzungen des tatsächlich unterstützten Berechnungsverfahrens.

Der erste Rechenpfad soll die unveränderte Fortführung gewöhnlicher linearer
beweglicher Anlagen abdecken. Eine ausdrücklich andere Methode, nicht belegte
Altwerte, frühere Sonderabschreibungen, Abgänge oder Methodenwechsel dürfen
nicht als diese Fallklasse gespeichert werden. Ein solcher Fall bleibt als
belegter Klärfall sichtbar; der Gesamtumfang bleibt offen. Vor Einführung einer
weiteren Fallklasse sind deren Eingangsdaten und Abnahmefälle gesondert zu prüfen.

## Unterjähriger Beginn und Rundung

Bei einem unterjährigen Softwarebeginn ist die bereits im selben Kalenderjahr
verbuchte AfA eine Pflichtangabe mit Originalbindung. Ohne diese Angabe wäre
eine automatische volle Jahres-AfA möglicherweise doppelt. Die Aufnahme muss
den Umfang der übernommenen Historie ausdrücken; fehlende historische AfA
ist kein Nullbetrag.

Die folgende AfA darf nicht allein aus `Restbuchwert / Restlaufzeit` entstehen:
Das würde je nach Altfall einen ungewollten Methodenwechsel oder eine neue
Rundung erzeugen. Die Umsetzung muss die belegte historische Kostenbasis,
ursprüngliche Laufzeit, tatsächlich übernommene kumulierte Beträge und den
verbleibenden Wert zusammenführen. Die letzte Rate darf weder einen negativen
Buchwert erzeugen noch mehr als die belegte noch abschreibbare Basis verbrauchen.
Abweichende frühere Cent-Rundung darf nicht rückwirkend neu berechnet werden.
Die exakte Überleitungsformel wird vor API-Freeze anhand der unten genannten
Grenzfälle festgelegt und unabhängig geprüft.

## Annahme, Rechte und Journal

Eigene unveränderliche Anlagenoriginale vermeiden, dass eine historische
Anlagenliste als neue Eingangsrechnung mit offenem Vorsteuerfall erscheint.
Geldkonto-Originale sind kontogebunden und werden dafür nicht zweckentfremdet.
Lesen/Schreiben soll bestehende Buchführungs-/Finanzrechte verwenden; Bankrechte
sind aus diesem neuen Vertrag nicht automatisch abzuleiten.

Wie beim Geldkonto-Vortrag sind Vorschauhash, aktueller Journalzustand,
Originalannahmequittung, Request-ID, identische Wiederholung, Korrekturfassung
und ausdrückliche Aufhebung nötig. Annahme und Quittung erfolgen atomar.
Originale, frühere Fassungen und angenommene Antworten bleiben prüfbar.
Aktive abhängige AfA und geschlossene betroffene EÜR-Perioden sperren neue
Änderungen bis zur nachvollziehbaren Gegenbuchung beziehungsweise Wiederöffnung.
Modul-/Runtime-/Restoregates gelten auch vor einer Wiederholung.

Die neue Quellen-/Restoreversion muss alte Berichte und alte angenommene
Vorgänge reproduzieren können. Eine wiederhergestellte Instanz benötigt die
gesonderte aktuelle Finanzfreigabe; der Runtimebenutzer darf sie nicht selbst
erteilen. Unternehmensausgaben enthalten nur die fachlich vorgesehenen
Anlagenfelder/Originale, keine technischen Replaydaten als pauschalen Export.

## Konkrete Abnahme vor dem nächsten Paketabschluss

1. Voll belegter Altbestand bei Jahresbeginn: keine Änderung von Geldkonten,
   Umsatzsteuer oder bisherigen EÜR-Postings. Originalbytes unverändert abrufbar.
2. Unterjähriger Beginn mit belegter bisheriger Jahres-AfA: laufende AfA erzeugt
   nur den noch zulässigen Betrag; fehlender historischer Jahreswert verhindert
   eine behauptete vollständige Berechnung.
3. Bereits vollständig abgeschriebene, weiter genutzte Anlage bleibt mit
   belegtem Nullbuchwert im Verzeichnis; keine zusätzliche AfA.
4. Cent-Restlaufzeit, letzte Nutzungsmonate, Monats-/Jahreswechsel und Schaltjahr:
   exakte Summen, keine negative Restbasis, kein neuer AfA-Beginn am Softwarestart.
5. Unpassende Methode, unklarer Vorsteueranteil, widersprechende Wertrelation,
   doppelte Inventaridentität oder falsche Originalposition bleiben klar erkennbar.
6. Angenommene identische Wiederholung nach Antwortverlust, nach neuer Fassung
   und nach Periodenschluss liefert denselben alten Stand; geänderte Request-ID-
   Inhalte, fehlendes Originalreceipt und frisch entzogene Rechte werden abgewiesen.
7. Korrektur mit bereits gebuchter Folge-AfA erfordert deren echte Gegenbuchung;
   alter Export bleibt bytegleich, neuer Export enthält genau die neuen Wirkungen.
8. Gleichzeitige echte PostgreSQL-Verbindungen, SQL-Unveränderlichkeit sowie
   tatsächliches Backup/Restore in ein separates leeres Ziel mit alter/neuer
   Berichtsversion und gesonderter Freigabe bestehen die Integration.
9. Browser und native App verwenden echte angenommene Backendfixtures und
   testen fehlende Werte, Korrekturen, Antwortverlust, Rechtewechsel und Originalabruf.

Diese Fälle sind geplante Prüfungen. Noch keiner davon ist mit einer neuen
historischen Anlagenimplementierung bestanden. Die ausgeführten Geldkonto-
Anfangssaldotests sind getrennt unter `docs/evidence/accounting-openings-*` belegt.
