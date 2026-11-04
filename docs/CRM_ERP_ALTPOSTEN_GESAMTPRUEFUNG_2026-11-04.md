# Gemeinsame Altpostenprüfung – 04.11.2026

Die Integration baut auf `13af5bc1147170948c5de8fa9f831a7215974cb5` auf.
Source5, historische Anlagen, Anfangssalden, datierte Katalogpreise und
Unternehmensereignisse bleiben erhalten. Backend, beide Clients, echte
Finanz-PostgreSQL-Fälle und gemeinsame Wiederherstellung sind abschließend
geprüft. Dies ist ein nachgewiesener Teilumfang, keine vollständige
Buchhaltungs- oder Gesamtfreigabe.

## Belegter Umfang

Historische offene Kunden- und Lieferantenrechnungen erhalten eigene
unveränderte Originale, belegte frühere Teilzahlungen, den tatsächlichen
Restbetrag und ausdrücklich ausgeübte frühere Vorsteuer. Eine Übernahme
stellt keine neue Rechnung aus und erzeugt keinen Geldfluss. Erst belegte
spätere Zahlungen werden zu EÜR-, Bank- und Liquiditätsquellen. Frühere
Centanteile bleiben erhalten, statt den letzten Rest neu zu runden.
Bereits früher abgezogene Vorsteuer entsteht nicht nochmals im neuen Jahr.
Korrekturen, Aufhebungen, Historie, Rechte und Periodensperren sind gebunden.

Der native unabhängige Review reproduzierte zwei Originalbindungsfehler:
Ein abgeleiteter Quellenhash konnte ein abweichendes Zahlungskonto oder
abweichendes historisches Vorsteuerdatum behaupten. Beide sind korrigiert.
Der Parser bindet das Konto an das ursprüngliche Zahlungsoriginal und löst
die exakte ursprüngliche Itemfassung auf. Eine spätere unveränderte Annahme
des Postens macht die ältere belegte Zahlung nicht ungültig. 48 gemeinsame
Owner-/Reviewfälle einschließlich tatsächlichem 390px-HTTP bestehen isoliert.

Im Browser wurden verspätete Altposten- und bestehende EÜR-Zahlungsantworten
gegen Dialog-/Kontextwechsel und Rechteentzug abgesichert. Die unabhängigen
ursprünglichen Rotbelege, die enge Korrektur und die echten Korrektur-/
Gegenbuchungsfälle bleiben in ihren gesonderten Nachweisen erhalten.

## Gemeinsamer Merge und finanzielle Version

193 Owner- und Reviewdateien sind über sieben Originalmanifeste gebunden.
Zehn Konfliktdateien wurden additiv aufgelöst. Der unabhängige
[Merge-Review](CRM_ERP_ALTPOSTEN_MERGE_GEGENPRUEFUNG_2026-11-04.md) bestätigt
180 bytegleiche Ownerdateien, alle 193 erwarteten Zusammenführungen und
23 weitere unveränderte Bestandspfadprüfungen. Die native Session bewahrt
sämtliche bisherigen Zeilen; OfficeApi ergänzt genau zwei Altpostenhooks.
Die zuletzt korrigierten Ereignis-Hintergrund- und Erfolgsprüfungen bleiben
bestehen. Quellpakete und CI enthalten dieselben 137 Backend-/159 Betreiberpfade.

Der aktuelle Finanzhorizont steigt additiv auf 14, der Wiederherstellungsbericht
auf 15. Frühere Validatorzweige bleiben unverändert. Aktuelle Restores müssen
die neuen Altpostenoriginale, Ereignisse und Annahmen einschließen; ein alter
kleinerer Nachweis kann diese neue Prüfung nicht ersetzen.

## Abschließend ausgeführte gemeinsame Prüfungen

- Vollständiges Backend: 1.817 ausgeführt, 1.816 bestanden, ein vorhandener
  Windows-spezifischer Fall auf Linux ausgelassen (1.011,457 Sekunden).
- Vollständige Flutter-App: 1.434 bestanden (742,739 Sekunden).
- Tatsächliche Finanz-PostgreSQL-Matrix: 109 unterschiedliche Fälle bestanden
  (1.189,894 Sekunden), einschließlich des gefüllten gemeinsamen Restores.
  Danach verblieb ausschließlich die lokale Testdatenbank ohne Verbindungen.
- 35 Fach-/Transport-/Registrierungsfälle bestanden nach der abschließenden
  reinen Testdiscoverybereinigung (36,359 Sekunden).
- 713 Nodefälle bestanden (9,078 Sekunden); vollständige Flutteranalyse ohne
  Befund (13,937 Sekunden); 16 Paketprüfungen bestanden (15,639 Sekunden).
- 49 bestehende Finanz-HTTP-Fälle bestanden (118,042 Sekunden).
- Sechs eindeutige echte PostgreSQLfälle bestanden zunächst in neun
  Ausführungen (117,203 Sekunden). Drei importierte Fixture-Testmethoden wurden
  versehentlich zusätzlich gesammelt. Der neue Joint-Test importiert nun das
  Helpermodul; dieselbe echte Restoreprüfung besteht erneut in der Finanzmatrix.
- Tatsächliches Chromium/MFA/HTTP: neue Altposten (64,948 Sekunden), bestehender
  Bankabgleich (33,503 Sekunden), vollständige bisherige EÜR (84,127 Sekunden)
  und Unternehmensereignisse (61,978 Sekunden) bestanden. Die Chromium-
  Sandbox blieb aktiviert.

Der [gemeinsame maschinenlesbare Nachweis](evidence/opening-items-integrated-regression-2026-11-04.json)
verbindet Originalprotokolle, Laufzeiten, Quellhashes und den unabhängigen
Merge-Review. [Tatsächliche Browserbilder und HTTP-Nachweis](evidence/opening-items-integrated-browser-2026-11-04/manifest.json)
sind archiviert. Gruppen überlappen und werden nicht zu einer scheinbaren
Zahl unabhängiger Abnahmefälle addiert.

## Testaufbau und Quellbindung

Zwei erst nach der Ownerbasis eingeführte gemeinsame Restoretests wurden
auf den aktuellen Horizont 14/Report 15 angepasst. Ihre historischen kleineren
Vergleichsfälle entfernen die späteren Tabellenfamilien ausdrücklich. Der neue
gefüllte gemeinsame Restore enthält Altpostenrechnung, tatsächliche Zahlung,
EÜR-Einordnung und Originale gleichzeitig mit Source5, Anfangssaldo, Anlage,
V1-/V2-Katalogen, datiertem Angebot und Ereignisfreigaben.

Die Modulimportbereinigung des neuen gemeinsamen PG-Tests änderte ausschließlich
die Testdiscovery. Der erfolgreiche Erstlauf und der vorherige Testtext bleiben
archiviert. Diese reine Online-PG-Datei änderte sich während der vollständigen
Backendprüfung, wird von deren Discovery aber nicht ausgeführt. Der Backendbefehl
selbst endete erfolgreich; der zusätzliche Hashwächter meldete genau diese eine
Testdatei. Der endgültige tatsächliche PG-Nachlauf bindet ihre letzte Fassung.
Sämtliche Produktdateien blieben während aller abschließenden Prüfläufe unverändert;
die gezielten Fach- und Paketprüfungen wurden nach der Importbereinigung wiederholt.

## Grenzen und nächste Schritte

Keine neue vollständige deutsche Buchhaltung, Lohnabrechnung oder technische
Gesamtabnahme wird aus diesem Teilumfang abgeleitet. Historische teilweise,
strittige oder noch nicht ausgeübte Vorsteuer, Regimewechsel, gemischte
Steuergruppen, wirtschaftliche Erstattungen und weitere Sonderfälle sind nicht
pauschal freigegeben. Belegte unterjährige Jahresvorträge und das ergänzende
Original-/Journalpaket entstehen getrennt. Keine produktive Migration,
Zahlung, Nachricht, Behördenmeldung oder Veröffentlichung ist erfolgt.
