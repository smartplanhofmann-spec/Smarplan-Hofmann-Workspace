# Belegte Faktor-Teilmonate 2026

Stand: 09.11.2026. Lieferabschnitt zu R09.03 des unveränderten Gesamtziels.
Die Gesamtanforderung Lohn bleibt offen.

Ein regulärer Mitarbeiter mit belegter Steuerklasse IV und ELStAM-Faktor kann
jetzt auch für einen Teilmonat aus den bestätigten Lohnfakten abgerechnet werden.
Browser und native App zeigen Faktor, Beschäftigungs-, Steuer- und SV-Tage,
Entgeltquote und Teil-Bemessungsgrenzen. Original, Faktorkorrektur, private
Abrechnung, reduzierter eigener Mitarbeiterbeleg und Jahresübersicht verwenden
dieselbe eingefrorene Quellenkette. Die tatsächliche Zahlung bleibt eine
gesonderte belegpflichtige Handlung.

## Fachlicher Umfang

Die neue additive Regel `de_2026_standard_factor_period_v9` verwendet Quelle2:
eine inländische Beschäftigungsepisode, eine Entgeltvereinbarung und ein
verifiziertes Faktor-/Versicherungsprofil. Der tatsächlich eingetragene Faktor
ist exakter Dezimaltext mit drei Nachkommastellen, einschließlich 0,000 und
kleiner als 1. Zusätzliche Frei-/Hinzurechnungsbeträge müssen bestätigt null
sein. Der ausgewählte Profilbeleg bleibt unverändert im Original enthalten.

Der bisherige Periodenplan prüft zuerst die Beschäftigung, Vereinbarung,
Sollzeit, Originalreferenzen, Tage und sämtliche Sperrgründe. Erst danach löst
die neue Regel ausschließlich den ausdrücklich unterstützten Faktor-Sperrgrund
auf. Alter mit erforderlichem Altersentlastungsbetrag, Midijob, weitere
Beschäftigungen, Profil-/Entgeltwechsel, Ansprüche, Reisen und Einmalbezüge
werden hier nicht stillschweigend mitgerechnet. Diese Fälle bleiben konkrete
Codearbeit; v9-Fakten stehen der bisherigen v5-Zusammenrechnung nicht zur Auswahl.

Die neue PAP-Hülle `bmf_2026_standard_factor_period_wrapper_v2` verwendet beim
Teilmonat den belegten Tagesquotienten. Der unverteilte Centrest bleibt sichtbar.
Die jährliche Faktorsteuer wird je Komponente auf den Tages-PAP zurückverteilt
und mit den tatsächlichen Steuertagen multipliziert. Kirchensteuer verwendet
die faktorisierte Maßstabsteuer mit dem belegten Landessatz. Ein voller Monat
stimmt in allen Geldkomponenten mit dem bisherigen Faktor-Vollmonat v8 überein.

Synthetisches Beispiel: Beschäftigung 15.–31.10.2026, Monatsgehalt 5.000,00 EUR,
Quote 17/31, Brutto 2.741,94 EUR, Faktor 0,753: Netto 1.830,39 EUR. Die belegte
Korrektur auf 0,900 ergibt 1.768,85 EUR, eine Steuerdifferenz von 61,54 EUR.
Das ursprüngliche JSON und PDF bleiben bytegleich. Bestätigte Nettozahlung,
gesonderte Abführungen, Bankabgleich und EÜR werden ohne erfundene Zahlung
oder Vorsteuer verbunden.

## Quellen und unveränderte Historie

Die historischen Rechenkerne sind bytegleich erhalten; ihre
[Hashes](evidence/payroll-factor-periods-2026-11-09/historical-kernel-hashes.json)
bleiben verbindlich. Ein alter v4-Faktenfall mit Faktor bleibt unter v4 weiterhin
gesperrt und wird beim Lesen nicht nachträglich zu v9. Es gibt keine
Schemaänderung, keine Umschreibung alter Abrechnungen und keinen Laufzeitabruf
eines Steuerdienstes.

Grundlagen sind die bereits geprüften
[Periodenquellen](CRM_ERP_LOHN_TEILMONATE_GEGENPRUEFUNG_2026.md),
[Faktorquellen](CRM_ERP_LOHN_FAKTOR_2026.md), §39b/§39f EStG und die PAP-XML
2026 mit SHA256
`63d8981646d139eba2f4dd990c13b43c4fb3883b402a5a40cddf253aa7aa96b4`.
Die XML stammt aus dem dort fest gepinnten öffentlichen Spiegel. Der erneute
direkte Abruf von §39f am 09.11. lieferte HTTP403; ein erfolgreicher neuer
amtlicher Direktabruf oder eine amtliche Softwarezulassung wird nicht behauptet.

Neue v9-Quellnachweise kennzeichnen ausdrücklich LF-normalisierte Dateihashes.
Ein tatsächlich heruntergeladenes, per veröffentlichtem Archivdigest und
innerem ZIP-Digest geprüftes Windows-Paket auf 2598c96 liefert 146 nach Abgleich
mit dem Repository verifizierte Pythonquellen. Mit diesen CRLF-Quellen und
dem ebenfalls auf CRLF umgestellten neuen Modul entsteht unter Linux exakt
dasselbe v9-Ergebnis einschließlich Regelhash wie mit LF. Das ist keine
Bedienung auf einem Windowsgerät. Der Abgleich zeigt zugleich unterschiedliche
Metadaten der unveränderten alten v8-Regel; der anschließende [v8-Abgleich](CRM_ERP_LOHN_PLATTFORMHISTORIE_2026.md)
schließt diesen eng begrenzten Fall inzwischen ohne Änderung alter Originale.
Andere rohe Dateihash-Nachweise bei Einmalbezügen/Reisen bleiben zu prüfen.

## Ausgeführte Prüfungen

- 200 separat in Java aus den gepinnten XML-Dezimalausdrücken berechnete
  Monats-/Tagesvektoren, einschließlich Faktorgrenzen, Kirchensteuer,
  Solidaritätszone und Centrest; der Generator importiert den Produktkern nicht.
- Sieben reine neue Kernfälle und sechs neue tatsächliche Fachkettenfälle:
  Quellenbindung, alter v4-Sperrfall, Korrektur/Differenz, unverändertes PDF,
  eigene Mitarbeiterrechte, pausierte Instanz, Zahlungen und EÜR.
- Drei neue tatsächliche PostgreSQL-/MFA-/HTTP-Fälle ohne Skip: Neustart,
  Konkurrenz zweier Verbindungen, Bankabgleich und tatsächlicher Dump/Restore
  mit gesonderter Freigabe der Finanzprüfung. Die drei bisherigen
  Perioden-/Midijob-PG-Fälle bestehen ebenfalls unverändert.
- Alle 879 Browser-Modulfälle und 313 nativen Lohnfälle bestehen. Darin liegen
  fünf neue Browserverträge und sieben native Fälle einschließlich gerenderter
  Faktenauswahl bei 390 und 1.200 Pixeln. Die App-Analyse meldet keinen Befund.
- Tatsächliche Chromium-/MFA-/HTTP-Abläufe für neue Faktor- und bisherige
  Periodenabrechnung: Quelldokumente, zweimal verlorene Antwort mit exakter
  Wiederholung, Originaldownload, private Vorschau, Jahresstand und Mobilbreite.
  Chromium prüft vorab seine Namespace-/PID-/Netzwerk-/Seccomp-Sandboxes.
- 16 Paketfälle; beide Windows-Quelllisten und die CI-Kopierliste enthalten
  das neue Modul. Rohprotokolle der zuerst fehlerhaften Testeinrichtungen
  bleiben neben den bestandenen Nachläufen erhalten.

Der breite Python-Gesamtlauf besteht alle 644 unterschiedlichen Fälle ohne
Skip in 585,966 Sekunden. Prüfzahlen unterschiedlicher Läufe werden nicht addiert, wenn
dieselben Fälle erneut enthalten sind.

[Maschinenlesbarer Nachweis und Protokolle](evidence/payroll-factor-periods-2026-11-09/verification.json).
Neue Remote-CI, tatsächliche Windows-/iPhone-Bedienung, Serverinstallation,
fachliche Abnahme, Meldungen und sämtliche übrigen Lohnfälle sind eigene
Nachweise. Alle Abnahmen A–G des Gesamtziels bleiben maßgeblich.
