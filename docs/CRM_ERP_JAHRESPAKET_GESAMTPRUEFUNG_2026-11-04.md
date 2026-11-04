# Jahrespaket mit Originalen – gemeinsame Prüfung vom 04.11.2026

Die Integration auf `ad354261e13145eb8b96cb942ec3fdad47bba3f1` ergänzt den
unveränderlichen EÜR-Jahresexport um ein lesendes ZIP mit den aufgelösten
Originalbelegen, Journalentscheidungen, Quellen und Prüfdateien. Browser und
App bieten den gespeicherten Export als Ausgangspunkt. Historische offene
Posten, Anlagen, Source5, datierte Katalogpreise und Ereignisregeln bleiben erhalten.

## Tatsächlich geprüfter Umfang

- 84 betroffene Backend-, Original-, HTTP-/MFA- und bestehende EÜR-/Altpostenfälle
  bestanden (88,964 Sekunden einschließlich Start).
- 401 Buchhaltungs-/Exportfälle der nativen App bestanden (265,940 Sekunden).
- Alle 762 Nodefälle bestanden (17,544 Sekunden); vollständige App-Analyse
  ohne Befund (26,925 Sekunden); 16 Paketprüfungen bestanden (22,389 Sekunden).
- Drei tatsächliche PostgreSQLfälle bestanden (49,425 Sekunden): Rechnung und
  Teilzahlung mit Wiederöffnung, alter Lieferantenposten mit Dump/Restore und
  der befüllte gemeinsame Restore sämtlicher oben genannter Module. Das ZIP und
  seine Metadaten bleiben vor und nach der ausdrücklichen Restorefreigabe bytegleich.
- Vier tatsächliche Chromiumabläufe mit aktiver Sandbox bestanden: Jahrespaket
  (32,235 Sekunden), bisherige EÜR (50,386), Altposten (59,087) und Ereignisse (36,514).
  Die neue 390px-Ansicht und der getrennt geprüfte Archivhash sind archiviert.

Der [maschinelle Gesamtnachweis](evidence/year-package-integrated-regression-2026-11-04.json)
bindet sämtliche Protokolle und endgültigen Quellen. Der vollständige Backend-/
App-/Finanzmatrixlauf des unmittelbaren Ausgangsstands ist im
[Altpostenbericht](CRM_ERP_ALTPOSTEN_GESAMTPRUEFUNG_2026-11-04.md) dokumentiert;
für diesen rein lesenden Nachtrag wurden die betroffenen Fach- und Apppfade
erneut geprüft. Überlappende Gruppen werden nicht addiert. Alle während der
abschließenden Prüfungen erfassten Quelldateien blieben unverändert.

## Erhaltene Originale und Rechte

Der Download prüft aktuelle globale und projektbezogene Quellrechte auch nach
dem Abruf des ZIPs. Exportwechsel, Hintergrundwechsel, verspätete Antworten,
veränderte Bytes und entzogene Rechte führen zu keinem Dateiexport. Die native
Dateiausgabe wurde im tatsächlichen lokalen Dateipfad sowie mit kontrolliertem
Desktop-Dateidialog geprüft; reale Windows-/iPhone-Geräte bleiben gesondert.

Die unabhängige Prüfung reproduzierte zuvor fehlende innere Abhängigkeitsbindungen
alter Archive. Die endgültige Grenze wird ausdrücklich angezeigt: Die Prüfung
verlangt einen separat vertrauenswürdig gesicherten SHA-256-Wert des ZIPs.
Ein selbst neu berechneter Hash beweist weder Herkunft noch Vollständigkeit.
`intrinsic_dependency_closure=false` bleibt ausdrücklich erhalten. Die im alten
EÜR-Export dokumentierte Jahresvollständigkeit wird dadurch nicht nachträglich
verbessert. Private Personaloriginale werden nicht in das Finanzpaket gezogen.

## Zusammenführung

191 eingefrorene Owner-/Reviewdateien sind einzeln gebunden. Sieben geteilte
Dateien wurden additiv zusammengeführt. Die native EÜR ergänzt genau 15 Zeilen;
die bisherigen Altposten-, Ereignis-, Session- und Hintergrundgrenzen bleiben
erhalten. Der [unabhängige Mergecheck](evidence/year-package-merge-independent-2026-11-04.json)
hat keinen Befund. Beide Quellpakete und Windows-CI enthalten dieselben
139 Backend- und 178 Betreiberpfade.

Eine fehlende Fortsetzungsverknüpfung bei der Vorbereitung der CI-Zeilen und ein
falsch aufgebauter statischer Dictionaryeintrag wurden bereits bei der lokalen
Merge-/Syntaxprüfung erkannt und vor Beginn sämtlicher Fachtests korrigiert.
Die abschließenden Teststände enthalten diese korrigierten Einträge.

Keine neue Tabelle oder Migration: Finanzhorizont 14 und Wiederherstellungsbericht
15 bleiben unverändert. Die lokale Testdatenbank wurde anschließend ohne weitere
Verbindungen geprüft. Keine produktive Migration, Zahlung, Meldung oder externe
Übermittlung ist erfolgt.

Unterjährige Jahresvorträge und ihr gesonderter V2-Archivanschluss folgen als
eigenes Paket. Steuerberater-/DATEV-/Behördenwege, fachlicher Jahresabschluss,
Gesamtabnahmen A–G und externe Betriebsnachweise bleiben offen.
