# Altposten: tatsächliche HTTP- und Dateivorgänge im App-Test abwarten

Ausgangsstand ist `d4df2f5`. Der unveränderte Altposten-Widgettest überschritt
im vollständigen App-Lauf seine Fünf-Minuten-Grenze. Derselbe Fehler wurde in
einer eigenen Arbeitskopie reproduziert: Nach 231 Warteabschnitten brach der
Test nach fünf Minuten ab. Die instrumentierten HTTP-Anfragen waren bis dahin
beantwortet; die längste dauerte 7.822 Millisekunden. Ein festhängender einzelner
Endpunkt wurde nicht nachgewiesen.

Die Änderung betrifft ausschließlich
`app/test/business_accounting_open_items_http_widget_test.dart`:

- Echte HTTP- und Dateiarbeit bekommt Zeit außerhalb von FakeAsync. Während
  dieser Arbeit und in ruhigen Frames wird die künstliche Uhr nicht vorgestellt.
  Nur tatsächlich geplante Animationsframes erhalten einen Zeitfortschritt.
- Der Test zählt JSON- und Originalbyte-Anfragen. Er beobachtet außerdem den
  vorhandenen Beschäftigtzustand der Altpostenseite: Ihr Ladebalken kann im
  nur bei Bedarf aufgebauten Scrollbereich außerhalb der vorhandenen Widgets liegen.
- Erst zwei ruhige Frames ohne laufende Arbeit erlauben die Fortsetzung. Ein
  einzelner Warteabschnitt hat eine echte Zeitgrenze von 40 Sekunden, anstelle
  einer durch Layoutkosten unbestimmten Anzahl von Pump-Schritten.
- Beim Originalexport wird zusätzlich genau ein tatsächlich abgeschlossener
  Downloadcallback abgewartet, bevor derselbe ursprüngliche Bytevergleich folgt.

Alle 38 `expect`-Aufrufe und die gesamte Fachfolge bleiben erhalten: Originale,
Centaufteilung, zwei Restzahlungen, verlorene Antworten mit identischem Replay,
EÜR-Zuordnung und Gegenbuchung, Berichtigungen, Originalhistorie, Aufhebung,
erneute Profilprüfung und frischer Rechteentzug. Das Gesamtbudget bleibt bei
fünf Minuten. Produktcode, Serverendpunkte und fachliche Rechteprüfungen wurden
nicht geändert.

## Tatsächliche Ergebnisse und Grenzen

Der finale vollständige Lauf besteht mit `1/1` nach **2:54 Minuten**. Das Rohlog
enthält 371 abgeschlossene JSON-/Originalbyte-Anfragen; die längste dauerte
1.042 Millisekunden. Vier periodische Metadatenaktualisierungen liefen während
der weiterhin notwendigen Animationszeit. Es wird weder behauptet, dass der
Timer abgeschaltet sei, noch dass er allein den ursprünglichen Timeout erklärt.

Während der Untersuchung endete der große parallel laufende App-Test. Die
dadurch gesunkene CPU-Last ist eine zusätzliche Ursache kürzerer Laufzeiten;
die Zeitdifferenz ist kein isolierter Leistungsnachweis des neuen Helfers.

Ein erster Helferversuch wartete nur auf sichtbare Ladeanzeigen und JSON und
lief dadurch vor dem Originalexport weiter. Dieser Versuch scheiterte nach
1:29 Minuten am unveränderten Bytevergleich und ist ausdrücklich kein Erfolg.
Ein Typisierungsfehler des Testhelfers und ein bewusst vorzeitig beendeter Lauf
mit noch fehlender Idle-Anpassung bleiben ebenfalls als solche erhalten. Der
erste anschließend vollständig bestandene Lauf benötigte 2:37 Minuten; der
finale Stand wurde danach nochmals vollständig ausgeführt.

[Maschinenlesbarer Nachweis und sämtliche Rohprotokolle](evidence/open-items-widget-wait-2026-11-09/verification.json)
enthalten die jeweiligen Dateihashes und Ergebnisse. Die optionale Variable
`SMARTPLAN_TEST_TRACE_OPEN_ITEMS=1` schaltet lediglich Methode, Pfad, Dauer,
Aufrufursprung und Wartezähler im Test ein. Zugangstoken und Dokumentinhalte
werden nicht protokolliert. Ohne die Variable bleibt der reguläre Testlauf ruhig.
