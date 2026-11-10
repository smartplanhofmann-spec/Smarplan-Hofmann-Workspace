# V16: tatsächliche interne Prüfungen

Produktquelle4aa0abd6d313fcc5d693606dbef1c7193afb0729. Basissnapshot13c6663.
Der [Fachvertrag](../../CRM_ERP_FAKTOR_MIDIJOB_TEILMONAT_V16_2026-11-10.md)
beschreibt den begrenzten unterstützten Umfang. `manifest.json` bindet die
Rohdateien und nennt aktive Gesamtläufe ausdrücklich noch nicht bestanden.

Alle `.txt.gz` sind verlustfrei komprimierte Originalausgaben. Die Zuordnung,
die SHA256 der ursprünglichen Bytes und die Gzip-Dateien stehen in
`compressed-raw-log-map.json`; die Dekomprimierung wurde bytegleich geprüft.
Kein gescheiterter Erstlauf wurde nachträglich in einen Erfolg umgeschrieben.

## Erhaltene Erstbefunde

- `baseline-v14-partial-observation`: V14 verweigert den tatsächlichen Teilmonat;
  der neue Quellenvertrag7 ist im Basissnapshot noch unbekannt.
- `pure-kernel-first`: doppelte Schlüssel in der synthetischen Testhilfsfunktion,
  anschließend korrigiert; `pure-kernel-second` enthält den eigenen Erfolg.
- `domain-and-old-v14-first/second/third`: zuerst unvollständige PDF-/Quellen-
  Kompatibilitätsfelder und danach fehlende ausdrückliche 30-Tage-Auswahl.
  Der neue Vertrag verlangt diese Auswahl, statt sie stillschweigend zu setzen.
- `domain-and-old-v14-fourth`: ein Jahreslückenbeleg überschneidet den bereits
  repräsentierten Lohnmonat. Diese tatsächlich richtige Sperre bleibt bestehen;
  die Testdaten belegen anschließend nur die vorher nicht repräsentierten Monate.
- `backend-joint-boundaries`: eine Testbehauptung griff auf `tax_parameters.LZZ`
  statt das vorhandene `period_details.tax_periods[].lzz` zu. Der getrennte
  zweite Lauf besteht mit24gemeinsamen Fällen.
- `domain-exit-first/second`: der Versuch, den ursprünglichen Beschäftigungsbeginn
  einer Faktenrevision zu ändern, wird richtig abgewiesen; danach falscher
  Aufruf einer nicht vorhandenen `revision`-Option der Test-API. Der dritte
  Lauf bindet einen wirklichen Austritt, bewahrt die bisherige Fassung über
  den tatsächlichen History-Vertrag und besteht.
- `client-fixture-generation`: zuerst falscher PDF-Abfrageaufruf. Der zweite
  Lauf und die anschließend vollständig fallgebundene Fassung sind getrennt
  erhalten; die heutige Clientfixture enthält echte angenommene API-Datensätze.
- `native-generic-before-preview-guard`: zunächst nicht vorhandener Fehlerhelfer
  im neuen Seitenzweig. Der nächste Lauf reproduziert die tatsächliche native
  Vorschauhashlücke. `native-joint-after-preview-fix` war trotz seines damaligen
  Dateinamens noch rot: der geplante Edit war davor nicht angewandt worden.
  Erst `native-joint-preview-fixed` enthält18erfolgreiche gemeinsame Fälle.
- `native-analyze-first`: ein unnötiger Import. Der zweite Lauf ist ohne Befund.
- `browser-ui-first`: der erwartete Testtext entsprach nicht der tatsächlichen
  neuen Umfangsbezeichnung. Der zweite neue und der bisherige V14-Ablauf bestehen.
- `browser-contract-all-final`: trotz des damaligen Dateinamens1Fehler unter
  1.109Fällen, ausschließlich Sandbox-EPERM beim Start des Zeitzonenprozesses.
  `browser-contract-all-permitted` besteht mitallen1.109Fällen unter den nötigen
  Prozessrechten. Der frühere1.106er-Lauf war ebenfalls vollständig erfolgreich.

## Tatsächliche Nachweise

Die Referenzgeneratoren verwenden getrennte Java-PAP-Ausführungen und eigene
rationale Beitragsarithmetik.300Sollwertzeilen stehen zusätzlich in CSV;
alle Beträge sind Ganzzahlen inCent. Eigene Originalgrafen, Hashmanipulationen,
verlorene Antwort, frische Rechte und beschränkte Mitarbeiterbelege werden
in beiden Clients geprüft. Die beiden tatsächlichen Browserabläufe und die
PostgreSQL-/MFA-/Konkurrenz-/Cash-/EÜR-/Jahres-/CRLF-/Komplettrestorefolge sind
getrennte Rohbelege. Der eigene PostgreSQL-Container ist nach Prüfung seiner
exakten ID, Aufgabenmarkierung und Loopbackbindung entfernt.

`frozen-v16-runtime-check.py.txt` prüft den fest benannten Commit in einem
separaten entpackten Archiv, einschließlich MFA, neuer Fähigkeit, vier neuen
Browserdateien und tatsächlichem Fall, Lohnlauf, PDF und unveränderter
Wiederholung. Sein archivierter Lauf besteht.61historische Lohnmodule und
das Gesamtziel sind gegen den Basissnapshot bytegleich.

31reale Gerätefälle bleiben ungeprüft; die bisherigen28Protokollzeilen sind
bytegleich. Signierte Vorbereitung, TestFlight-Verteilung, Serverinstallation
und unabhängige Fach-/Sicherheitsabnahme sind eigene Zustände. Es wurden keine
echten Nachrichten, Zahlungen oder Meldungen erzeugt.


## Abschließender aktueller Stand

Alle20eigenen Development-Gruppen bestehen. Vollständiger eigener CI-Backendlauf:
2.199Fälle in1.611,192s mit3Auslassungen. Linux-App2.020Haupt- und3PDF-Fälle;
Windows1.975App-/81portable Backendfälle und reale Paketierung. Automatischer
iPhone-Release211 und signierte Vorbereitung212 mit tatsächlicher Signatur-/
Team-/Keychain-Prüfung sowie Schlüsselbereinigung erfolgreich, Upload ausgelassen.

Der vollständige lokale App-Lauf besteht2.023Fälle. Der zusätzliche lokale
Backendaufruf bleibt wegen4Importfehlern durch den Testaufruf rot:2.178erfasste
Fälle in2.774,929s,3Auslassungen. Die korrigierte Auswahl der4Module plus der
später ergänzte Austrittsfall besteht mit25Fällen in24,747s. Die4Fehlerplatzhalter
werden im kombinierten lokalen Abdeckungsnachweis durch die wirklichen Fälle
ersetzt; die vollständige eigene CI ist ein getrennter Einzelaufruf. Kein
Fehlerlauf wird nachträglich überschrieben oder als Erfolg umgedeutet.

Der erste interne Belegleser erwartete das vom Connector nicht ausgegebene
`head_sha` direkt in jedem normalisierten Job. Er scheiterte an dieser eigenen
Erwartung. Der korrigierte Leser bindet jede tatsächliche `run_id` an den
separat beobachteten Workflow-Quellcommit. Alter Leser, leere Standardausgabe,
Fehlergrund und nachfolgender tatsächlicher Befund sind erhalten.

Das Quellenarchiv und sämtliche61historischen Lohnmodule sind weiterhin
bytegleich.31reale Gerätefälle, neue Serverinstallation, TestFlight-Verteilung
und unabhängige Fach-/Sicherheitsabnahme bleiben separate offene Nachweise.
Die neue RV-Lebenslaufarbeit liegt in einer eigenen Arbeitskopie und ist
kein Bestandteil dieser bereits geprüften4aa0abd-Pakete.
