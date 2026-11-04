# Unabhängige Produktprüfung: belegter laufender Jahresvortrag

Geprüft im isolierten Baum `/workspace/smartplan-opening-year-values-20261104`.
Acht tatsächliche Domainfälle bestanden in 4,824 Sekunden. Der Reviewer änderte
keine Produktdateien, Quellfixtures oder bestehenden Tests. Die acht geprüften
Kern-/EÜR-/Altpostendateien sind bytegleich mit dem vorher gebundenen Runtime-
Snapshot und dem Backendhandoff `6c665abc…8221a`; Hashes stehen im Manifest.

Die eigene Datei `backend/test_accounting_year_openings_independent_review.py`
prüft folgende Vorgänge über tatsächlich angenommene Quellen und EÜR-Buchungen:

- Vollständig gedeckter alter Zeitraum beseitigt eine echte neue unklassifizierte
  Zahlung nicht. Erst deren bewusste EÜR-Übernahme ergibt 119,00 Jahresaufwand.
- Tatsächlicher Vorjahres-Vorsteuerabzug wird bei laufender Zahlung nicht erneut
  gebucht. Der andere tatsächlich laufende Junianspruch bleibt am ursprünglichen
  Tag; der Vortrag erzeugt keine Geldbewegung.
- Alte Konten und Originaljournalidentitäten sind exakt gebunden; falsches Konto,
  Kontrollcent und wiederverwendete Zahlungs-/VAT-Identität werden abgewiesen.
- Derselbe wirtschaftliche Rechnungsursprung kann trotz neuem Scan und anderer
  technischer Kennung nicht als angeblich erledigter Fremdbeleg dupliziert werden.
- Eine später ausdrücklich geänderte Altpostenfassung macht die ungebuchte alte
  Jahresfreigabe nicht neu ausführbar. Die ursprüngliche Annahme bleibt erhalten.
- Zwei nacheinander übernommene Teilzeiträume werden nicht automatisch vereinigt.
  Gegenbuchung, neue Revision und früherer Export bleiben nachvollziehbar.
- Ein Nulljournal ist bei bekannten alten Werten gesperrt. Ein tatsächlich
  mögliches explizites Nulljournal verdeckt auch einen später erfassten normalen
  alten Eingangsbeleg nicht; der Jahresbericht wird wieder unvollständig.
- Ein Original eines anderen Jahres und fehlende aktuelle Finanzrechte sperren
  Preview, Wiederholung bzw. Originalabruf. Berechtigter alter Replay bleibt gleich.

Es wurden keine zusätzlichen Produktfehler in diesem engen Stand bestätigt.
Dies ist keine allgemeine steuerliche Vollständigkeits- oder Produktionsfreigabe.
Die ausdrücklich unterstützten gewöhnlichen 19-/7-Prozent-Fälle, fortgeführte
EÜR/Istbesteuerung, unabhängiges Zeitraumjournal und Ausschluss unbekannter
Sonderquellen bleiben die Grenzen des Owners. Dessen PostgreSQL-/Restore-/HTTP-
Nachweise werden hier nicht als eigene erneute Messung gezählt. Der getrennte
Jahresnachweisadapter und seine Offline-Vertrauensgrenzen sind nicht Bestandteil
dieser Produktprüfung. Keine echten Daten, Nachrichten, Zahlungen oder Commits.
