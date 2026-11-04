# Jahresbasis – unabhängige begrenzte Gegenprüfung

Stand 03.11.2026. Geprüft wurden `payroll_annual_basis_2026.py` und
`business_payroll_annual_basis.py` anhand eigener tatsächlicher Fachbefehle,
geschützter Quellen und historischer Annahmequittungen. Vier zusätzliche Fälle
bestanden nach einem bestätigten und vom Modulverantwortlichen behobenen
Befund in 1,358 Sekunden. Es gab keine Produktänderung durch den Reviewer.

## Bestätigter und geschlossener Befund

Ein bereits gespeicherter Bonus von 500 EUR mit Zufluss am 15.01.2026 und
SV-Zuordnung zu Dezember 2025 durfte die SV-Luft 2026 nicht verbrauchen. Er
gehörte aber zum steuerlichen Jahreslohn 2026. Die Oktober-Steuervorschau
akzeptierte zunächst das Weglassen seiner zusätzlichen Quellreferenz und
lieferte 7.000 statt 7.500 EUR. Mit ausdrücklich gebundener Referenz lieferte
derselbe tatsächlich ausgeführte Fachfall den korrekten höheren Betrag.

Dieser Erstbefund wurde vor dem Fix als direkter Fachversuch beobachtet; er
wird nicht nachträglich als vorheriger fehlgeschlagener unittest ausgegeben.
Der anschließend ergänzte eigene Regressionstest verlangt bei ausgelassener
bekannter Quelle HTTP-/Fachstatus 409. Der Fix ergänzt keine stillen Quellen:
Der Anwender muss alle bekannten aktiven steuerlichen Zuflüsse außerhalb der
bereits ausgewählten SV-Jahresbasis ausdrücklich binden. Historische
Rekonstruktion bleibt auf den damals angenommenen Quellen beschränkt.

## Zusätzliche Gegenfälle

- Eine tatsächliche Dezember-2025-Periode mit 1.000 EUR laufender Basis und
  500 EUR früherem Einmalbezug ergibt aus den monatlichen 2025-Grenzen
  5.512,50 EUR KV bzw. 8.050 EUR RV Restluft von 4.012,50 bzw. 6.550 EUR.
  Der Bonus behält dabei Steuerjahr 2026 und SV-Jahr 2025.
- Ein nachträglich erfasstes Original verlangt eine neue aktuelle Jahresbasis.
  Die bereits angenommene frühere Quittung und ihre damalige Restluft bleiben
  unverändert; eine neue Fassung bindet den tatsächlichen zusätzlichen Bezug.
- Laufender Dezemberlohn mit Zufluss am 21. Januar bleibt im vorherigen
  Steuerjahr und wird nicht nochmals als zusätzlicher laufender Steuerbezug
  des neuen Jahres akzeptiert.

Rechtliche Bezugspunkte sind [§39b EStG](https://www.gesetze-im-internet.de/estg/__39b.html),
[§23a SGB IV](https://www.gesetze-im-internet.de/sgb_4/__23a.html), die bereits im
[Einmalbezugsquellenbericht](CRM_ERP_LOHN_EINMALBEZUEGE_2026_ENTWURF.md)
dokumentierten tatsächlichen 2025-Grenzen sowie die dort getrennt behandelte
LStR-R39b.2-Zuordnung des laufenden Vorjahreslohns.

Die Gegenprüfung ist auf diese Quellen- und Jahresgrenzenfälle begrenzt und
ist keine vollständige v6-, Browser-, native oder Produktivabnahme. Log,
Dateihashes und Erstbeobachtung stehen in
[Evidence](evidence/payroll-annual-independent-review-2026-11-03.json).
