# Unabhängige Jahrespaketprüfung: nachgewiesene Grenze und Korrektur

Das Backendmanifest `e2f228173bb6d0eb3408d1cf48dadf0f7cbfd0e138c19ea3dc8ed8f89f13d069`
bleibt als historischer Kandidat erhalten. Die unabhängige Gegenprüfung erbrachte
drei tatsächliche fehlende Bindungen: eine Vorjahres-Vorsteuerentscheidung,
eine ältere Altpostenrevision und eine frühere echte Teilzahlung ließen sich
entfernen, während Exportoriginal, Report und CSV unverändert blieben. Die
Präfix-/Revisions-/Zahlungskontrollen wurden ergänzt; der erste Nachlauf dieser
drei Fälle zusammen mit den 16 Ownerfällen bestand mit 19/19.

Zwei weitere unabhängige Gegenfälle belegten eine grundsätzliche Grenze: Der
hilfsweise erzeugte `prefix.target_hash` ist ohne ursprüngliches vollständiges
Entry-Payload selbst austauschbar. Ebenso beweist eine passende kumulierte
Zahlungssumme nicht, ob ein ursprünglicher Teilbetrag aufgehoben und durch einen
anderen ersetzt worden war. Das globale Altpostenjournal kann zwischen diesen
Einträgen fremde Posten enthalten. Deren Volljournale und Originale werden nicht
in einen sachlich engeren Jahresnachweis kopiert.

Root hat deshalb ausdrücklich einen begrenzten Prüfvertrag bestätigt: Aufgelöste
Originale, keine behauptete intrinsische Vollständigkeit aller Abhängigkeiten;
verpflichtender separat authentisiert bestätigter Archiv-SHA-256. Der bisherige
CLI-Pflichtparameter gilt nun ebenso für den programmatischen Prüferaufruf.
Manifest und Ergebnis weisen `intrinsic_dependency_closure=false` aus. Fehlender
oder falscher Außenanker scheitert. Ein von der Archivdatei selbst gelieferter
Hash ist kein unabhängiger Vertrauensanker. Der Prüfer kann die Herkunft eines
vom Aufrufer eingesetzten Hashwerts nicht selbst authentisieren; der produktive
Client entnimmt ihn der aktuellen berechtigten API-Metadatenantwort und prüft
diese nach dem Dateiabruf erneut.

Die vorherigen inneren Bindungsprüfungen bleiben erhalten. Der Builder prüft sein
neu erzeugtes Paket lokal mit dessen eigenem Hash, bevor die authentisierte API
denselben Wert veröffentlicht. Diese Konstruktionsprüfung ist ausdrücklich keine
unabhängige Herkunftsprüfung. Die Jahresvollständigkeit im ursprünglichen
EÜR-Bericht bleibt unverändert und wird nicht aus einer erfolgreichen Hashprüfung
abgeleitet.

Die ursprünglichen roten Tests und Protokolle werden unverändert archiviert.
Aktuelle Tests prüfen den neu vereinbarten Vertrauensvertrag getrennt. Der noch
nicht freigegebene synthetische Clientfixturestand erhält dadurch neue ZIP- und
Metadatenhashes, weil der Prüfer selbst im ZIP liegt. EÜR-Exportoriginale,
Quittungen, Belegbytes und die 16 Metadatenfelder werden nicht umgeschrieben.
Nach dem endgültigen Gegenlauf folgen tatsächliche neue Fixtures und getrennte
Browser-/Native-Nachprüfungen. Dieser Nachtrag ist keine Gesamtfreigabe.
