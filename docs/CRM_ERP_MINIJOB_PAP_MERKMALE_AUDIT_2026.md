# Individuell besteuerter Minijob: PAP-Merkmale 2026

Recherche am 09.11.2026, Basis `a7c1e0b34e92f623ed46c36d608958ee732f15c0`.
Dies ist ein Quellen- und Referenzaudit, keine neue produktive Berechnung.

## Ergebnis

Ein enger Fall ist belegbar und mit der vorhandenen XML unabhängig berechenbar:
einzeln ausgeübter gewerblicher Minijob, voller Monat, 500 EUR laufender
steuerpflichtiger Lohn, nachgewiesene beitragsfreie GKV-Familienversicherung,
gültige individuelle ELStAM und dokumentierter RV-Status. Die technische
PAP-Eingabe `PKV=1` darf dabei **keine tatsächliche Privatversicherung** im
Personalprofil erzeugen.

## Primärquelle und gesicherte Regeln

[BMF-Schreiben vom 14.08.2025](https://www.bundesfinanzministerium.de/Content/DE/Downloads/BMF_Schreiben/Steuerarten/Lohnsteuer/2025-08-14-vorsorgepau-lohnsteuerabzugsverfahren.html),
GZ IV C 5 – S 2367/00012/004/033, DOK COO.7005.100.2.12744842.
Die vollständige neunseitige Fassung wurde im
[amtlichen Berliner Rundschreibenarchiv](https://www.berlin.de/politik-und-verwaltung/rundschreiben/download.php/4329937)
gelesen; für Seiten 1, 6 und 9 wurden zusätzlich Seitenbilder angefordert.
Die ausgelesene Titelseite nennt die Anwendung ab 01.01.2026. Die BMF-Direktseite lieferte im Recherchewerkzeug 503.

- Rz. 4, S. 3: maßgeblich ist der Versicherungsstatus am Periodenende.
- Rz. 10–11, S. 4: RV-Teilbetrag bezieht sich auf das jeweilige Dienstverhältnis;
  bei bloßem Arbeitgeber-Pauschalbeitrag entfällt er.
- Rz. 16, S. 6: Ohne KV-Arbeitnehmeranteil im individuell besteuerten Minijob
  entfällt der KV-Teilbetrag. Die ausdrückliche technische Anweisung lautet
  „unter dem Eingangsparameter ‚PKV‘ der Wert ‚1‘ einzugeben“.
- Rz. 17, S. 6: Pflegeversicherung folgt Krankenversicherung.
- Rz. 20–22, S. 7: tatsächliche private Basisbeiträge und steuerfreie Zuschüsse
  beziehungsweise ALV-Pflicht sind eigene Voraussetzungen.
- Rz. 25, S. 8: keine Mindestvorsorgepauschale ab 2026.
- Rz. 28, S. 9: ohne eigene RV-/KV-/PV-Beiträge besondere Lohnsteuertabelle.

Die [Minijob-Zentrale: Versicherungen](https://www.minijob-zentrale.de/DE/die-minijobs/versicherungen),
Abschnitt „Versicherungen im gewerblichen Minijob“, bestätigt fehlende
Minijob-Beiträge zu PV und ALV; der KV-Pauschalbeitrag des Arbeitgebers begründet
keine eigene KV-Mitgliedschaft. Ihre
[RV-Information](https://www.minijob-zentrale.de/DE/die-minijobs/rentenversicherungspflicht)
beschreibt RV-Pflicht und mögliche Befreiung; 500 EUR liegt über der dort
genannten Mindestbeitragsbasis 175 EUR. Die
[Steuerinformation](https://www.minijob-zentrale.de/DE/fuer-gewerbetreibende/abgaben-und-steuern),
Abschnitt „Steuern beim Minijob mit Verdienstgrenze im Gewerbe“, bestätigt die
Wahl individueller Besteuerung nach Lohnsteuerklasse. Die Seiten zeigen kein
eigenes Veröffentlichungsdatum; Abrufdatum ist 09.11.2026, sichtbarer Stand 2026.

## Zuordnung und notwendige persönliche Originale

| PAP | Enger Fall | Bindende Voraussetzung |
| --- | --- | --- |
| `ALV=1` | keine ALV dieses Minijobs | belegte Beschäftigungseinstufung |
| `KRV=1` | RV-befreit | wirksamer Befreiungsnachweis für die Periode |
| `KRV=0` | alternative RV-pflichtige Variante | eigener RV-Anteil tatsächlich geschuldet |
| `PKV=1` | technischer Ausschluss der KV/PV-Pauschale | kein KV-Arbeitnehmeranteil dieses Minijobs; Rz. 16 |
| `PKPV=PKPVAGZ=0` | keine privaten Basisbeiträge/Zuschüsse | hier tatsächlich GKV-familienversichert |
| `KVZ=PVS=PVZ=PVA=0` | in diesem XML-Zweig ohne Rechenwirkung | technische Nullwerte, keine erfundenen persönlichen Pflege-/Kassenmerkmale |

Eine gesetzliche Versicherung oder RV-/ALV-Pflicht aus einer **anderen**
Beschäftigung darf nicht pauschal in den Minijob übernommen werden. Eine solche
Mehrfachbeschäftigung gehört nicht zu diesem engen Kandidaten; ihre Beiträge,
Zusammenrechnung, ELStAM und gültige Krankenversicherung wären gesondert zu
belegen. Auch Familienversicherung ist kein Schluss allein aus 500 EUR Lohn:
erforderlich ist ein gültiger Nachweis der Krankenkasse und der relevanten
weiteren Einkünfte/Beschäftigungen.

Für den Referenzfall zusätzlich ausdrücklich angenommen, vor Produktnutzung
aber durch Originale zu belegen: inländische Beschäftigung, keine weiteren
eigenen Jobs, keine Auslandsversicherung, keine Versorgungs-/Sonderbezüge,
kein Altersentlastungsbetrag, ein voller Monat, keine Freibeträge oder
Hinzurechnungen, keine Kirchensteuer. Steuerklasse I oder V stammt aus ELStAM;
V setzt die passende tatsächliche eheliche Steuerklassenwahl voraus. Die
Berechnung behauptet keine solche Eigenschaft für einen realen Mitarbeiter.

## Tatsächliche unabhängige XML-Ausführung

Die XML hat SHA-256
`63d8981646d139eba2f4dd990c13b43c4fb3883b402a5a40cddf253aa7aa96b4`,
internen Stand 23.10.2025 12:40 und stammt aus dem bereits gepinnten öffentlichen
Spiegel; ein erfolgreicher direkter XML-Download vom BMF wird nicht behauptet.
[BMF-XML-Verzeichnis](https://bmf-steuerrechner.de/interface/pseudocodes.xhtml).
Die unveränderten XML-Ausdrücke wurden durch den vorhandenen separaten
Java-BigDecimal-Generator ausgeführt; kein Anwendungs-Rechenkern wurde geladen.

| Synthetischer voller Monat, 500 EUR | `KRV` | Lohnsteuer | Soli |
| --- | --- | --- | --- |
| Klasse I, RV-befreit | 1 | 0,00 EUR | 0,00 EUR |
| Klasse I, RV-pflichtig | 0 | 0,00 EUR | 0,00 EUR |
| Klasse V, RV-befreit | 1 | 55,16 EUR | 0,00 EUR |
| Klasse V, RV-pflichtig | 0 | 48,66 EUR | 0,00 EUR |

Alle Eingabefelder, Ausgaben, Laufzeit- und Generatorhashes liegen in
[xml-reference.json](evidence/minijob-pap-audit-2026-11-09/xml-reference.json).
Der zusätzliche **ungültige Diagnosefall** `PKV=0/KVZ=2.90/PVZ=1` liefert
47,58 EUR statt 55,16 EUR; er zeigt die materielle Bedeutung der Zuordnung und
ist keine fachliche Freigabe. Es wurden weder Netto/SV-Summen noch Zahlungen
oder amtliche Meldungen erzeugt.

Wiederholung aus dem Projektverzeichnis:

```sh
python docs/evidence/minijob-pap-audit-2026-11-09/reproduce.py --xml /tmp/smartplan-factor-pap-2026.xml
```

## Grenzen der Sicherung

Das Recherchewerkzeug meldete die angeforderten Seitenbilder als
`ImageDisplayed`; seine MCP-Rückgabe lieferte hier nur Text/Platzhalter und
keine prüf- oder speicherbaren PDF-/Bildbytes. Eine separate Pixelprüfung
wird deshalb nicht als erledigt ausgewiesen. Der Executor-Abruf scheiterte zunächst am
Proxyzugang, der genehmigte äußere Abruf danach beim CONNECT mit HTTP 403.
**PDF-SHA unbekannt, kein lokales Original-PDF archiviert.** Der Hash der
Quellenbeobachtung ist ausdrücklich kein PDF-Hash. Die beobachteten URLs,
Fundstellen und Abrufgrenzen stehen in
[sources.json](evidence/minijob-pap-audit-2026-11-09/sources.json).

Die produktive Erweiterung, Originalprüfung sowie fachliche Gesamtfreigabe
bleiben gesonderte Arbeit. Vorhandene Regeln und historische Ergebnisse wurden
nicht verändert.
