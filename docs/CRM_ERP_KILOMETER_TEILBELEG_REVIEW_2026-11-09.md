# Unabhängiger Review überlappender Kilometeroriginale

Auf dem Backendstand ae0c851, integriert als c96ea0c, reserviert die neue
Kilometerfunktion zunächst nur die gesamte Menge ihrer Streckenoriginale.
Die bereits beanspruchte Menge `{X}` und eine neue Menge `{X,Y}` haben
verschiedene Bündelhashes. Das erneute Verwenden des tatsächlich selben
Originalteils X wird dadurch nicht erkannt.

Zwei unabhängige Fälle führen echte Uploads, ursprüngliche Fahrt,
Einreichung und unabhängige Freigabe aus. Die Domäne nimmt beide zweiten
Abrechnungen tatsächlich an: dieselbe Person an einem anderen Tag sowie
eine zweite Person mit kopiertem Original und neuem zweitem Streckennachweis.
Es werden ausschließlich synthetische Daten und keine Zahlungen verwendet.

Der [permanente Reviewtest](../backend/test_mileage_proof_overlap_review.py)
prüft die spätere tatsächliche Ablehnung in `approve()`, unveränderte
Abrechnungsanzahl, fehlende Geldwirkung und einen Blocker ohne fremde
Quellenreferenz. Sein erster Lauf scheitert zweimal in 2,445 Sekunden am
tatsächlich akzeptierten Doppeloriginal. Die Quelle ist noch nicht veröffentlicht.

[Unveränderte Vorherbelege](evidence/mileage-overlap-review-2026-11-09/before.json).
Der enge Folgefix soll jedes tatsächliche Original unabhängig von weiteren
Belegen schützen, erhaltene alte Bündeloriginale mitprüfen und die eigene
Korrekturkette zulassen. Ein erfolgreicher Nachlauf steht noch aus.
