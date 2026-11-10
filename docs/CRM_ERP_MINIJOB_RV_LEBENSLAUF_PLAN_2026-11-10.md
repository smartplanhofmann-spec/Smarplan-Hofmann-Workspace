# Minijob-Rentenversicherung: tatsächlicher Restumfang

Erhaltener Bestandsbefund10.11.2026 auf4aa0abd. Der nachfolgende neue
Entwicklungsstand ist davon getrennt und noch kein vollständiger Produktweg. Der V16-Teilmonat und seine laufende Gesamtprüfung sind
davon getrennt. Dieser Befund ist keine Änderung historischer Profile.

## Reproduzierter Codebefund

Die aktuelle Profil-API nimmt in einer synthetischen durchgehenden Beschäftigung
nacheinander Profile abAugust mit Befreiung, abSeptember ohne Befreiung und
abOktober erneut mit Befreiung an. Sie verlangt Original und Bestätigung,
führt aber keinen eigenen verknüpften Antrags-/Melde-/Aufhebungslebenslauf.
Die [drei tatsächlichen Antworten](evidence/minijob-rv-lifecycle-2026-11-10/baseline-profile-state-observation.json)
enthalten IDs, Revisionen und Originalhashes. Daraus wird nicht abgeleitet,
dass jede reale Berichtigung oder jeder Beschäftigungsverlauf rechtswidrig wäre.
Eine Korrektur falscher Stammdaten und ein tatsächlicher Statuswechsel sind
fachlich verschiedene Vorgänge und brauchen unterscheidbare Nachweise.

## Direkt gelesene Grundlage

[§6SGBVI](https://www.gesetze-im-internet.de/sgb_6/__6.html), insbesondereAbs.1b,
3,4und6, ist vollständig unmittelbar lesbar. Die Befreiung benötigt den Antrag
beim Arbeitgeber; Meldezugang und Widerspruchsverfahren bestimmen ihre Wirkung.
Die Aufhebung ist auf Antrag einmalig möglich, wirkt zum Folgemonat und bindet
für die Dauer der Beschäftigungen. Die reine Umstellung eines Profil-Bools
bildet diese gesetzlichen Tatsachen nicht vollständig ab.

Die [Minijob-Zentrale](https://www.minijob-zentrale.de/DE/die-minijobs/befreiung_rentenversicherungspflicht)
beschreibt getrennt Antragseingang, Meldung, Widerspruch und Wirkung. Sie nennt
für den gewerblichen Beitragsgruppenwechsel die Abmeldung32undAnmeldung12.
Diese Codes sind keine tatsächlich übermittelte Meldung oder technische
Zulassung der Software.

Die unmittelbar gelesenen [Richtlinien05.01.2026](https://www.minijob-zentrale.de/SharedDocs/Downloads/DE/Rundschreiben/Geringfuegigkeitsrichtlinien-2026.pdf?__blob=publicationFile),
B2.2.4.1/.4/.6/.7 aufDruckseiten34–40, erläutern Fristen, gemeinsame Wirkung,
Bindung und Bestandskraft. Unterbrechung oder kurzer Wiederbeginn beim selben
Arbeitgeber beweisen allein kein neues freies Wahlrecht. Die Regelung zur
Aufhebung gilt ab01.07.2026. Eine heutige Zustimmung darf keine historische
Nichtbeanstandung oder rückwirkende Antragswirkung erfinden. Der ergänzende
DRV-GRA-Abruf läuft in einen Timeout; dafür wird kein gelesener Inhalt behauptet.

## Konkreter nächster Implementierungsvertrag

1. Eigener additiver, strikt typisierter Tatsachenvertrag für genau eine
   belegte durchgehende gewerbliche Minijobbeschäftigung; anfänglich ohne
   parallele Minijobs, Altfall vor2013, Altersrenten-/Versorgungsfälle oder
   ungeklärten Wiederbeginn. Zusätzliche Fälle erhalten eigene Entscheidungen.
2. Getrennte unveränderliche Originale für bestehenden Befreiungsstatus,
   tatsächlich eingegangenen Aufhebungsantrag, tatsächlichen Meldungseingang
   und festgestellten Behörden-/Nichtbeanstandungsstand. Offene oder
   widersprüchliche Angaben bleiben sichtbar unentschieden.
3. Wirkungsbeginn aus belegten Tatsachen bestimmen, einmalige Aufhebung
   über die vollständige bekannte Historie prüfen und einen erneuten Wechsel
   nicht allein durch ein neues Profil oder eine neue ID erlauben.
4. Einen neuen ausdrücklich gebundenen Quellen-/Lohnvertrag anschließen;
   ursprüngliche Profile und Laufversionen nicht umschreiben. Berichtigungen
   nur mit eigenem Grund und erhaltenem ursprünglichem Tatsachenstand.
5. Beide Clients mit bewusster Originalwahl, Vorschau, frischem Personalrecht,
   identischer Wiederholung und privatem Mitarbeiterbeleg. Tatsächliche
   PG-/Konkurrenz-/Zahlungs-/EÜR-/Jahres-/Restorefolge vollständig nachweisen.
6. Unabhängige Grenzfälle für Monats-/Jahreswechsel, Antrags- und Meldedaten,
   offene/beanstandete Meldung, zweite Aufhebung, fremdes Original und alte
   Quittungen. Kein neuer End-to-End- oder Rechtsfreigabestatus aus einem
   isolierten Datumshelfer ableiten.

Die Programmierung dieses Vertrages benötigt keine echten Mitarbeiterdaten
oder produktive Meldung. Reale Meldetransporte und unabhängige fachliche
Freigaben bleiben gesonderte Schritte. Kein Antrag, keine Meldung und keine
Zahlung wurde für diesen Befund versandt oder erzeugt.


## Tatsächliche begonnene Umsetzung nach dem Quellenbefund

Eigene Arbeitskopie `/workspace/smartplan-minijob-rv-20261110`, Branch
`codex/minijob-rv-lifecycle-20261110`, Basis4aa0abd. Die neue eingefroren
versionierbare Zustandskomponente und private append-only Speicherung sind
implementiert, aber noch nicht veröffentlicht. Sie binden den ursprünglichen
Befreiungsnachweis, tatsächlichen Antrag, Meldungszugang, ausdrücklich geprüfte
Widerspruchsfrist und festgestellten Verfahrensstand. Die Software berechnet
die Verwaltungsfrist einschließlich örtlicher Feiertage nicht automatisch;
sie verlangt deren tatsächlichen begründeten Nachweis und prüft die minimale
Kalendermonats-/Datumsfolge. Zeitablauf allein erzeugt keine Behördenentscheidung.

Eine erhaltene ursprüngliche Antragstellung kann nicht durch eine neue ID,
eine ausgelassene frühere Fassung oder die Rückkehr zum leeren Antrag
verschwinden. Alle bisherigen Fassungen bleiben gebunden. Die ausdrückliche
spätere Prüfung eines unveränderten Originalstatus kann ergänzt werden;
ein erledigter gesetzlicher Vorgang wird nicht durch ein neues Bool widerrufen.

15erste Komponenten-/Speicherfälle bestehen. Eine zusätzliche Prüfbestätigungs-
folge erweitert den Komponentenvertrag auf10Fälle plus6Speicherfälle. Der
anschließende gemeinsame Unternehmens-/Datenschutz-/Paketabschnitt erfasst
70Fälle. Sein erster Lauf hat14Paketfehler wegen in der eigenen Sparse-
Arbeitskopie fehlender Betrieb-/iPhone-Dateien. Die unveränderten Dateien sind
gezielt aus ihrem HEAD materialisiert. Der20er-Paketnachlauf hat zunächst einen
fehlenden lokalen Backendinterpreter; nach Verknüpfung des vorhandenen eigenen
Interpreters besteht die tatsächliche Paketimportprüfung separat.70verschiedene
Fälle sind damit gemeinsam abgedeckt; die ersten roten Aufrufe bleiben rot.
[Code-/Rohbelege und tatsächliche Grenzen](evidence/minijob-rv-lifecycle-2026-11-10/storage-stage-status.json).

Noch offen: tatsächliche Profilbindung und Schreibschutz nach Übernahme des
Lebenslaufs, vollständiger versionierter Lohn-/Zahlungs-/EÜR-/Jahresanschluss,
beide Clients mit frischem Rechteentzug und Wiederholung sowie echte PG-/
Konkurrenz-/Komplettrestorefolge. Dieser Speicherabschnitt ist kein fertiges
Lohnmodul und gehört nicht zu den bereits geprüften4aa0abd-Paketen.
