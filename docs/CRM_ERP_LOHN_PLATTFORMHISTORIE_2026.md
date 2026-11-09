# Faktor-Vollmonat: unveränderte Originale zwischen Windows und Linux

Stand: 09.11.2026. Ergänzung zu R09.03 und zum Wiederherstellungsbetrieb.

Ein bereits auf Windows erfasster Faktor-Vollmonat v8 kann nach dem Wechsel
auf Linux jetzt wieder vollständig geprüft und verwendet werden. Ebenso ist
die umgekehrte Prüfung von LF-Originalen mit CRLF-Programmquellen getestet.
Originales JSON, ursprünglicher Regel-/PAP-Hash, Quittung und PDF bleiben
unverändert. Eine anschließende neue Faktorkorrektur verwendet den aktuellen
Regelstand und weist die tatsächliche Differenz zum erhaltenen Original aus.

## Ursache und begrenzte Korrektur

Die unveränderte alte Faktor-PAP-Regel bindet zwei rohe Programmdateihashes
in ihren Quellnachweis ein. Das tatsächlich veröffentlichte Windowspaket enthält
CRLF-Zeilenenden, das Linux-Repository LF. Dadurch unterscheiden sich die
Regel-/PAP-Hashes trotz identischer Fachberechnung. Die bisherige vollständige
Gleichheitsprüfung lehnte das alte Ergebnis beim Plattformwechsel deshalb ab.

Der neue reine Prüfer berechnet zuerst sämtliche Quellen, Beträge und
Abrechnungsmerkmale mit der installierten Regel erneut. Falls nur die Metadaten
abweichen, leitet er die vier möglichen LF-/CRLF-Kombinationen der beiden
tatsächlich installierten vertrauenswürdigen unveränderten Kerneldateien ab.
Je Kombination berechnet er sowohl den PAP-Hash als auch den davon abhängigen
v8-Regelhash vollständig neu. Nur ein exakt zusammengehörendes Paar und ein
ansonsten vollständig identisches Ergebnis werden angenommen. Unbekannte
Hashes, vermischte Paare, geänderte Faktoren, zusätzliche Felder und ein Cent
Abweichung bleiben Fehler. Archivwerte liefern keine ausführbaren Quellen.

Der Prüfer ist ausschließlich auf vollständige reguläre Faktor-Vollmonate v8
mit Quelle1 begrenzt. Er verändert keine globalen Rechenregeln, benötigt keine
Unterprozesse im Produkt und führt keine Netzwerk-/Datenbankänderung aus.
Frische Rechte-, Mandanten-, Originaldatei-, Referenz-, Umschlag- und PDF-Prüfungen
bleiben an ihren bestehenden Stellen erhalten. Vorschauen und neue Abrechnungen
werden weiterhin unverändert mit der nativen installierten Regel erzeugt.
Es ist keine Migration erforderlich.

Die neue Faktor-Teilmonatsregel v9 ist bereits ausdrücklich LF-normalisiert
und benötigt diesen historischen Sonderabgleich nicht. Andere alte Dateihash-
Nachweise bei Einmalbezügen sind gesonderte noch zu prüfende Kompatibilitätsfälle.
Der anschließende [v2/v3-Reiseabgleich](CRM_ERP_REISEN_PLATTFORMHISTORIE_2026.md)
erhält inzwischen auch die alten Boden-/Misch-/Transportnachweise. Die normale alte
v4-Tages-PAP-Metadatei enthält keine rohen Dateihashes; ihre Inhalte werden
aus dieser v8-Korrektur nicht pauschal als fehlerhaft eingestuft.

## Tatsächliche Nachweise

Fünf neue Fachkettenfälle führen die vertrauenswürdigen Produktionsquellen in
einem isolierten Pythonprozess mit CRLF aus und nehmen das Ergebnis über die
unveränderte Vorschau-/Bestätigungskette als Original an. Nach Rückkehr zur
LF-Anwendung bestehen die vollständige Datenbankintegrität, Originalquittung,
eigener reduzierter Mitarbeiterbeleg, private Exportrechte, Jahreskonto,
Faktorkorrektur und tatsächliche Zahlungs-/Abführungsquellen. Gegenproben
verwerfen erfundene Hashes, getrennt richtige, aber nicht zusammengehörige
Metadatenpaare sowie veränderte Beträge/Faktoren.

Zwei tatsächliche PostgreSQL-/MFA-/HTTP-Fälle übernehmen CRLF-Originale und
prüfen sie anschließend unter LF, einschließlich Anwendungsneustart und
tatsächlichem Dump/Restore. Alle geschützten Tabellenfingerabdrücke, alten
PDFs und Quittungen bleiben erhalten. Der ausschließlich für diese Prüfung
angelegte Datenbankcontainer ist anschließend entfernt.

Ein separat heruntergeladenes Windows-Supportpaket des vollständig grünen
Produktstands 2598c96 ist gegen veröffentlichten Archivdigest, inneren Digest
und alle 146 enthaltenen Pythonquellen geprüft. Die alte tatsächlich
veröffentlichte v8-Berechnung daraus besteht den neuen Abgleich. v9 bleibt
einschließlich aller Metadaten identisch. Die Ausführung dieser Paketquellen
erfolgt auf Linux; ein tatsächlicher Windows-Gerätetest wird nicht behauptet.

16 Paketfälle bestehen mit dem neuen Modul in beiden Windows-Quelllisten und
der CI-Kopierliste. Die zuerst falschen Klassennamen/Erwartungen in den neuen
Testeinrichtungen und der zuerst direkte statt vollständige Dispatcheraufruf
im Paketvergleich bleiben als fehlgeschlagene Rohprotokolle erhalten.
Alle 649 unterschiedlichen Python-Lohnfälle bestehen ohne Skip in 617,953
Sekunden. 32 versionierte Rechenmodule sind gegenüber 877266a bytegleich.
Als 3025747 auf dem autorisierten Testbranch veröffentlicht; die eigene neue
Remote-CI ist beim ersten Abruf ausstehend. Die Gesamtsoftware, fachliche Lohnfreigabe und
Abnahmen A–G sind damit weiterhin nicht vollständig abgeschlossen.

[Maschinenlesbarer Nachweis und Rohprotokolle](evidence/payroll-provenance-2026-11-09/verification.json).
