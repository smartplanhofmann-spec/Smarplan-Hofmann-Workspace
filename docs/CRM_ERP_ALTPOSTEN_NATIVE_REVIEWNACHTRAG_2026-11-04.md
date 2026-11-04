# Native Altposten: unabhängige Originalbindungsprüfung

Nachtrag 04.11.2026 zur ersten eigenen Abnahme. Der bisherige Handoff
`docs/evidence/opening-items-native-2026-11-04/manifest.json` mit SHA-256
`f192a1a870505b3c4497e343df6e0c06f3e81f684466a0e703b5729b421dfed9`
bleibt als damaliger Stand erhalten und ist durch diesen engeren Fix ergänzt.

Der unabhängige Reviewer belegte zwei konkrete Fehler gegen unveränderte echte
Serverquellen: Eine neu gehashte Projektion konnte trotz mitgelieferter
unveränderlicher Zahlung ein anderes Geldkonto behaupten. In der nativen
Quellenansicht konnte eine ebenso neu gehashte Lieferantenprojektion einen
anderen historischen Vorsteuerausübungstag anzeigen, obwohl die ursprüngliche
Rechnung unverändert war. Der vorherige Nachweis und die unveränderten roten
Gegenfälle liegen im unabhängigen `before-manifest.json` unter
`docs/evidence/opening-items-native-independent-2026-11-04/`.

Der neue Source-Vertrag vergleicht die komplette Kontofassung und den Itemkey mit
der unveränderlichen Zahlung. Der neue rein lesende Originalauflöser sucht genau
die referenzierte Zahlungs- und Rechnungsfassung in der unveränderlichen Historie.
Rechnungs-ID/-Hash, Richtung, Kategorie, Satz und vollständige frühere Vorsteuer
müssen exakt passen. Ein aktueller, später erneut bestätigter Rechnungskopf wird
nicht an Stelle der ursprünglich referenzierten Fassung verwendet.

Sowohl die Altposten-Quellenansicht als auch der neue EÜR-Quellenkatalog nutzen
diese Prüfung. Kontext wird zwischen den zusätzlichen Reads geprüft; vor Anzeige
folgt weiterhin die frische Rechteprüfung. Bestehende EÜR-Operationen, gespeicherte
Exporte und sämtliche Session-Hooks sind unverändert.

Eigener abschließender Lauf: **42/42 grün**, bestehend aus den **23 eigenen neuen
Fällen** und **19 gezielten EÜR-/Anlagenregressionen**. Der tatsächliche lokale
390px-HTTP-Ablauf nimmt zusätzlich dieselbe bereits bezahlte Lieferantenrechnung
nochmals unverändert an. Der aktuelle Rechnungskopf wechselt, die vorhandene
Zahlung bleibt an die alte Fassung gebunden und ihre ursprüngliche Vorsteuerquelle
ist weiterhin korrekt lesbar. Analyzer der drei geänderten Produktdateien: **0**.
Die frühere breite Regression **106/106** ist im vorherigen Handoff erhalten;
der neue Nachlauf deckt gezielt die berührten Lesewege ab.

Der unabhängige Reviewer meldete separat **25/25** eigene Fälle grün, darunter
beide ursprünglichen Gegenfälle, positive Quellen beider Richtungen, verspätete
Vorschauen/Quittungen/Fehler, Rechte-/Sitzungs-/Hintergrundwechsel und Originalbytes.
Sein endgültiger kombinierter Nachweis wird in seinem eigenen Evidence-Verzeichnis
geführt; diese Dokumentation ersetzt ihn nicht.

Neuer verbindlicher Native-Handoff:
[evidence/opening-items-native-review-fix-2026-11-04/manifest.json](evidence/opening-items-native-review-fix-2026-11-04/manifest.json).
Der neue vollständige enge Integrationspatch bezieht sich auf dieselben
ursprünglich dokumentierten drei Bestandsdateien. Neuere Company-Events-Hooks im
Root erhalten. Keine Backendänderung, neue Mutation, neue Buchung, Mainänderung
oder Commit durch diesen Reviewfix.
