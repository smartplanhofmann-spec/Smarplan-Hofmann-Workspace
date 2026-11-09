# Katalogabnahme mit der aktuellen Originalklärung

Der abgeschlossene Business-/Browserjob 129288306110 auf 8273852 scheitert
nach vorher bestandenen Fach- und Browserabschnitten im Katalogpreisablauf.
Er erwartet während einer noch offenen Belegantwort sofort einen zweiten
neuen Belegdialog. Die aktuelle Anwendung zeigt dafür ausdrücklich
**Belegantwort klären**. Damit wird keine andere Eingabe unter derselben offenen
Vorgangskennung angelegt. Die Stundenübernahme hat diese gemeinsame
Originalklärung im Belegdialog eingeführt; der Katalogtest verwendete noch
die frühere Bedienfolge.

Die unveränderte Testannahme ist auf dem gemeinsamen Materialstand ec90a8b
mit echter Anmeldung und tatsächlichem Backend erneut fehlgeschlagen. Die
Korrektur verändert ausschließlich die Abnahme, keinen Produktguard:

1. Der Server nimmt das Novemberangebot mit belegtem Katalogpreis an; seine
   Antwort wird tatsächlich zurückgehalten.
2. Nach Schließen und erneutem Öffnen erscheint die Originalklärung ohne
   bearbeitbaren zweiten Titel.
3. Die verspätete angenommene Antwort darf diesen neuen Klärungsdialog weder
   schließen noch Inhalt oder Fokus verändern.
4. Nach bestätigtem Original ist ein neuer Belegentwurf wieder erreichbar.
   Der Server enthält genau ein ursprüngliches Novemberangebot.
5. Preisrevision, alter Beleg, Originaldatei, Dezembergrenze, Einkaufsbasis,
   ursprüngliche Lost-ACK-Prüfungen und mobile Darstellung bleiben geprüft.

Ein zwischenzeitlicher angepasster Lauf mit zusätzlichem Seitenwechsel blieb
in einer unbeschränkten Harness-Wartebedingung hängen und wurde ausschließlich
an seinen eigenen Testprozessen beendet. Er ist als unvollständig/cancelled
gesichert und gilt nicht als Erfolg. Der endgültige Nachweis verwendet den
anderen Dialog auf derselben Seite, begrenzte Antwortbarrieren und die
vorhandene garantierte Freigabe der gehaltenen Antwort im Cleanup.

Der vollständige tatsächliche Chromium-/MFA-/HTTP-Katalogworkflow besteht.
[Rohprotokolle, Screenshots und Quellhash](evidence/catalog-pending-review-2026-11-09/verification.json).
Die ursprünglichen CI- und lokalen Fehlversuche bleiben getrennt erhalten.
Der frühere Gesamtjob wird dadurch nicht nachträglich grün; eine neue
Remoteprüfung des korrigierten Gesamtstands steht noch aus.
