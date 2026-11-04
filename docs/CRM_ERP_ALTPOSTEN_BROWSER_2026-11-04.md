# Belegte Altposten im Browser

Arbeitsstand 04.11.2026 im isolierten Baum `/workspace/smartplan-opening-items-20261104`.
Die Browserintegration wird gegen den [tatsächlichen API-Vertrag](CRM_ERP_ALTPOSTEN_API.md)
und die drei vom Backend erzeugten Originalabläufe entwickelt. Keine Änderung des
Gesamtziels und keine Fertigmeldung der gesamten Software.

## Anforderungen und Umsetzung

- Externe, noch nicht lokal erfasste offene Rechnungen werden aus unveränderten
  Originalen übernommen. Die Übernahme erzeugt keine Rechnung, Zahlung oder Steuerbuchung.
- Originalnetto, Originalsteuer und Brutto, alte Teilzahlungen und getrennte
  verbleibende Netto-/Steuer-/Bruttowerte bleiben nachvollziehbar. Keine historische
  Zahlung wird als Null angenommen; auch eine leere alte Zahlungsliste verlangt
  ausdrückliche Erklärung und Stichtagsnachweis.
- Verbindlichkeiten verlangen die belegte vollständige tatsächliche frühere
  Ausübung des Vorsteuerabzugs. Die spätere Zahlung erzeugt keine zweite Vorsteuer.
- Eigene tatsächliche Zahlungsnachweise führen zu Geldbewegungen; EÜR-Einordnung
  und Bankzuordnung bleiben ausdrücklich getrennte Vorgänge.
- Fälschliche Erfassungen können mit neuen Fassungen aufgehoben und berichtigt
  werden. Dies bildet keine wirtschaftliche Rückzahlung ab. Aktive EÜR-/Bankfolgen
  müssen vorher nachvollziehbar aufgehoben werden.
- Die ursprünglichen Datei- und Ereignishashes, Vorschau, Profil, vollständiger
  ursprünglicher Auftrag und Revisionsfolge werden vor Verwendung geprüft.
  Verlorene Antworten behalten ihre unveränderten Aufträge; fremde Quittungen
  können keine eigene offene Operation abschließen.
- Sitzung, Ansicht, Dialoggeneration und aktuelle globale Finanzrechte schützen
  auch verspätete Antworten und Fehler. Downloads prüfen Originalbytes erneut.

## Aktueller Teststand

Die drei tatsächlichen Backendabläufe werden einschließlich direkt erzeugter
Vorschauen und Kontobelegen gelesen. Der endgültige gemeinsame Stand besteht
**644/644 benannte Node-Tests**, ohne übersprungene Fälle. Darin enthalten sind
21 eigene neue Altpostenfälle, 30 unabhängige Altpostengegenfälle und 15 separate
unabhängige Gegenfälle zum bestehenden EÜR-Zahlungsweg.

Der tatsächliche Chromium/MFA/HTTP-Ablauf ist grün: Originalupload und drei
verlorene Antworten mit exakter Wiederholung, Forderung mit historischen
Centanteilen, Verbindlichkeit mit tatsächlich früher ausgeübter Vorsteuer,
Teilzahlungen, Aufhebung/Korrektur und drei historische Zahlungsfassungen,
spätere EÜR ohne zweiten Vorsteuerabzug, Bankzuordnung ohne neuen Geldfluss,
Originaldownload mit Byteprüfung und 390px. Der Ablauf verwendet eine
Unicode-Kennung (`ＭAẞE-ΟΣ-01` → `masse-οσ-01`) gegen den tatsächlichen Server.

Eine verzögerte echte Altpostenvorschau nach Dialogschluss wird verworfen.
Die tatsächliche EÜR-Vorschau und eine bereits angenommene EÜR-Bestätigung
verändern einen inzwischen geöffneten unbeteiligten Dialog nicht. Eine gültige
Originalquittung löst trotzdem ihren Auftrag und den neutralen Pendingzähler auf.
Ein tatsächlicher Entzug von `finance.read` während eines Originaldownloads
neutralisiert den privaten Dialogtitel und Inhalt; keine Datei wird heruntergeladen.
Der bestehende vollständige Bankabgleich besteht ebenfalls seinen echten Browserablauf.
Beide Browserläufe bestätigen die Namespace-, PID-, Netzwerk- und Seccomp-Sandbox.

Der [unabhängige Altpostenreview](CRM_ERP_ALTPOSTEN_BROWSER_GEGENPRUEFUNG_2026-11-04.md)
reproduzierte elf konkrete EÜR-Ablaufvarianten: späte Anfangs-/Vorschau-/
Annahmeantworten, verspätete 403, exakte Pending-Wiederholung und entzogene
Leserechte nach dem Quellabruf. Diese Fälle sind nach gezielten Kontext- und
Rechteprüfungen grün.

Der [getrennte Bestandsreview](CRM_ERP_EUER_BESTAND_BROWSER_GEGENPRUEFUNG_2026-11-04.md)
reproduzierte acht entsprechende Fehler bei einer tatsächlich bestehenden
`cash`-Quelle ohne Altpostenregistrierung. Die Guards gelten jetzt auch für diese
Operation und dieselbe Quelle bei Berichtigung/Gegenbuchung. Die tatsächlichen
Originalpostings und Belege bleiben unverändert. Bei `reverse` bleibt `effect=null`;
der Kontextschutz einer offenen Gegenbuchung folgt ihrem ursprünglich bekannten
Quelltyp und ihrer unveränderten Vorgangskennung, auch nach Leeren des Editors.
Er erfindet weder eine Quelle noch eine neue Buchungswirkung.

[Abschlussmanifest mit SHA-256](evidence/opening-items-browser-2026-11-04.json)
und [dauerhafte Logs/Artefakte](evidence/opening-items-browser-2026-11-04/README.md)
binden den geprüften Stand. Frühere rote Läufe und die unveränderten unabhängigen
Nachweise bleiben erhalten. Die Prüfung verwendet lokale synthetische Originale;
es erfolgten keine externe Zahlung, kein Versand und kein Produktivkontakt.

## Zuständigkeit und Grenzen

Browserowner `finish_v6_clients`, Backendowner `finish_v6_backend`, Nativeowner
separat durch Root. Globale Browserhooks werden erst durch Root mit dem aktuellen
Hauptstand zusammengeführt. Ein eigener neuer Dialogzähler ist nicht erforderlich;
der vorhandene Zähler wird für Altposten mitverwendet. Keine Commits,
Produktivkontakte oder echten Außenaktionen durch diesen Scope.

Unterstützter Umfang und offene fachliche Fälle stehen im API-Vertrag. Insbesondere
werden nicht ausgeübte Altvorsteuer, andere Steuer-/Rundungsgruppen, Rückzahlungen,
Gutschriften, Skonti oder vollständige Altjahreswerte nicht still ersetzt.
