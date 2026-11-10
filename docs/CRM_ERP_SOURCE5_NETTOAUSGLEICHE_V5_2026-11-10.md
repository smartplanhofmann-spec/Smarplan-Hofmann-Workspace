# Weitere tatsächliche Nettoausgleiche nach einer Rückzahlung

Stand 10.11.2026. Code und beide Clients integriert; der abschließende tatsächliche
PostgreSQL-/Restorenachweis läuft noch. Noch keine Veröffentlichung oder Gesamtabnahme.
Basis ist der veröffentlichte und remote bestätigte Stand
`936f40f57c769dce515099b4fecc616d05b35280`.

Nach einem vollständig erfüllten V4-Rückzahlungsnachweis kann eine neue belegte
Jahresquelle erneut eine positive, negative oder betragsgleiche Nettodifferenz
ergeben. Der bisherige Vertrag erlaubt diese Folge nicht. V5 ergänzt einen
wiederverwendbaren Vertrag für vollständig belegte V4-/V5-Präfixe; die
historischen V1–V4-Verträge werden nicht erweitert oder umgeschrieben.

- Prüfung Fassung 3 `source5_actual_net_adjustment_review_v1`: sämtliche
  bisherigen Zahlungen/Rückzahlungen und Abführungen ausdrücklich vollständig
  bestätigen und das unveränderte private Original binden.
- Übergang Fassung 3 `source5_net_adjustment_v1`: vorherige Laufrevision,
  tatsächlich letzte erfüllte Zahlungsrevision, vollständige Quell-/Planhashes,
  unveränderten laufenden Fall und ursprünglichen einzelnen Bruttozufluss binden.
  Netto darf das laufende Originalnetto nicht unterschreiten. Tatsächliche
  Abführungen bleiben durch die bestehende frische Abführungsprüfung begrenzt.
- Zahlung Fassung 5 `source5_actual_net_adjustment_v5`: sämtliche alten
  Zahlungsteile und Zuordnungen bilden den exakten vollständigen Präfix.
  Ausschließlich neue tatsächliche Bonusteile dürfen der Nettodifferenz folgen.
  Tag im Jahr 2026, nicht zukünftig und nicht vor dem letzten ursprünglichen
  Zahlungsteil; eindeutige tatsächliche Referenzen und exakte vorzeichenrichtige
  Centbeträge. Kein neues Brutto und keine neue laufende Nettozuordnung.
- Null Nettodifferenz: exakt derselbe alte Präfix, keine neuen Zahlungsteile,
  leere neue Zahlungsindizes, kein neuer Geldfluss. Eine künstliche Nullzahlung
  ist unzulässig. Der separate neue Nachweis belegt die neue erfüllte Laufrevision.
- Browser und App prüfen Quellen/Hashbindung unabhängig und benötigen die frische
  Fähigkeit `payroll_source5_net_adjustments`. Unklare Antworten behalten den
  unveränderten ursprünglichen Auftrag. Historische PDF und Zahlungsbelege bleiben.

Geplante Nachweise: tatsächliche Folge positiv/negativ/null und erneute Folge,
Manipulations-/Datums-/Vorzeichen-/Versionsgrenzen, unabhängige Browser-/App-
Hashprüfung, Bedienung samt verlorener Antwort, tatsächliche PostgreSQL-/MFA-/
EÜR-/Jahres-/Restorekette, Paketierung und gemeinsame Regression. Die erste
Reproduktion ohne V5-Unterstützung scheitert erwartungsgemäß an der neuen
Vollständigkeitsprüfung; der rohe Lauf bleibt erhalten.

Gesamtziel und A–G bleiben offen. Keine Liveinstallation, echte Zahlung,
Übermittlung, signierte Apple-Veröffentlichung oder fachliche Freigabe folgt aus
dieser Codearbeit. Weitere Steuergruppen/Zuordnungswechsel sind eigene Fälle.

## Tatsächlich abgeschlossene lokale Prüfungen

- 48 gemeinsame Backendfälle/396,223s: V5 positiv/negativ/null mit echtem
  angenommenem Präfix, alte positive Verträge, V3-Zahlungstage, V4-Rückzahlungen,
  alte Monatsgruppen und Jahresbasis. Falsche Richtung, Cent, boolescher Betrag,
  alter Präfix, früherer/zukünftiger Tag, künstliches Nullpaar und alte Versionen
  werden abgewiesen. Ein nach einem erfolgreichen Lauf ausdrücklich injizierter
  beschädigter Original-Lesezugriff wird erkannt; die nächste saubere Prüfung
  besteht. Der reale Datenbank-Archivschutz wird dafür nicht abgeschaltet.
- 1.035 vollständige Node-Vertragsfälle/16,321s ohne Skip. Die neuen drei
  Varianten reproduzieren die tatsächlichen Backendhashes unabhängig, ebenso
  die produktiven Eingabebauer und Quittungsprüfung. Ein vorheriger isolierter
  Dateilauf bleibt fehlerhaft: Der lokale Zeitzonentest durfte seine Node-
  Unterprozesse in der Sandbox nicht starten (`EACCES`). Der vollständige
  tatsächlich ausgeführte Nachlauf außerhalb dieser Prozesssperre besteht.
- 1.896 vollständige native Fälle ohne Skip; JSON-Endereignis
  `success:true`, 806.952ms. Neun neue Vertragsfälle sowie neun neue Bedienfälle
  decken positiv/negativ/null, unveränderliche Altteile, frischen Freigabeentzug,
  tatsächliche Laufkorrektur und unveränderte Wiederholung verlorener Antworten
  nach Wiederöffnen ab. Analyse sauber/10,2s; 21 Paket-/Inventarfälle/20,821s.
- Echter Browser mit Test-MFA, tatsächlicher anfänglicher V4-Rückzahlung,
  unabhängiger neuer V5-Vorschau und Nachzahlung, verlorenen Lauf- und Zahlungs-
  antworten sowie exakter Wiederholung beider Originalaufträge. Mobile390-Ansicht
  tatsächlich geprüft und Screenshot angesehen. Keine vorgetäuschte Annahme.

Der erste neue App-Laufkorrekturtest scheitert dreimal an einer fehlenden
Richtungsauswahl, wenn nur die neue V5-Fähigkeit vorhanden ist. Die Auswahl
benötigt jetzt die jeweils eigene tatsächlich vorhandene Fähigkeit; sämtliche
neun Bedienfälle bestehen im Nachlauf/19s. Zwei frühe Backend-Fehler stammen
von einem unzulässigen Testschreibversuch gegen das bereits geschützte Archiv
und einem falsch benannten Testmodul. Der korrigierte 48-Falllauf besteht;
ursprüngliche Rohläufe bleiben erhalten.

Die reine Originalprüfung verwendet einen ausschließlich für einen einzelnen
Lesevorgang gültigen Kontext: erfolgreich geprüfte identische alte Läufe und
identische deterministische Berechnungen werden innerhalb desselben Graphen
wiederverwendet, ihre ursprünglichen Datenbankzeilen weiter verglichen. Kein
Ergebnis überlebt den äußeren Aufruf; Fehler und unvollständige Beweise werden
nicht wiederverwendet. Rechte und private Belege werden weiterhin aktuell
geprüft. Alte Rechenkerne bleiben unverändert. Die erste vollständige Folge
besteht mit 269,732s, der anschließend weiter eingegrenzte Lesegraph mit
72,306s; dies sind beobachtete Läufe unter weiterer Last, kein isolierter
Leistungsbenchmark. Der alte unoptimierte Vergleich wurde ohne Endergebnis
unterbrochen und wird nicht als erfolgreicher Lauf gezählt.

Die echte PostgreSQL-Folge hat V4(-1.400 Cent), V5(+500), V5(-500) und V5(0)
angenommen und ist bereits in der wiederhergestellten Testdatenbank. Ein erster
Vorversuch endet noch vor der Datenbankprüfung an einer falschen statischen
Modulregistrierung, ein zweiter an einer falschen aus einem anderen Fixture
übernommenen Centannahme. Beides korrigiert; der vollständige Nachlauf wird
erst nach seinem tatsächlichen Ende bewertet.

V4 ist in seiner eigenen CI noch nicht vollständig grün: Der tatsächliche
Einkaufsbrowser scheitert bei gleichzeitigen lokalen SQLite-Lesezugriffen;
[Originaldiagnose](evidence/source5-repayment-2026-11-10/publication-browser-failure-936f40f.json).
Die unabhängig nachgestellte und geprüfte Korrektur18b7031 wird vor dem neuen
Veröffentlichungsstand zusammengeführt. Windows, Mac, App, Backend, HTTPS,
Update und unsignierter iPhone-Build des Vorgängers bestehen; Online-API lief
beim letzten Abruf noch. Kein neuer Liveabgleich oder signierter Upload.
