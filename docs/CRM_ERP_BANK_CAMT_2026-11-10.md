# Standardisierter Bankauszugsimport CAMT.053

R08.03/R12.01/B/F: Nach dem veröffentlichten Offline-Konfliktfix abcc351 wird
der bisherige eigene CSV-Auszug um einen ausdrücklich versionierten XML-Weg
ergänzt. Keine reale Bankverbindung, Zahlung oder Herstellerzulassung daraus
ableiten. Kreissparkasse Rottweil ist gewählt; eine echte Beispieldatei liegt
noch nicht vor. Die anderen gewählten Banken und Lieferanten bleiben erhalten.

## Verifizierte Ausgangsquellen

Das [offizielle ISO-Archiv](https://www.iso20022.org/catalogue-messages/iso-20022-messages-archive?page=1)
führt camt.053.001.08 als BankToCustomerStatementV08 und verweist auf
https://www.iso20022.org/message/12736/download. Der direkte Cloudabruf liefert403;
die Webquelle kann den binären Download nicht als Text darstellen. Keine
Direktbeschaffung oder amtliche Freigabe wird behauptet.

Das vollständige Schema ist aus dem ausdrücklich bezeichneten Genkgo-MIT-Spiegel
unter Commit56e047d1599854ca34db0ccabce15230fcdd3f16 beschafft:
assets/camt.053.001.08.xsd,106.100 unveränderte Bytes einschließlich CRLF,
Git-Blob0d29c71b369e3948c60ad59984dd437aa47f8d8b, SHA256
c3cfac080dc31476bde7444b05d00e1b23558d5e44529e58d0ad562e6013873d.
Die zugehörige MIT-Lizenz ist mitbeschafft. Das Schema enthält keine externen
Import-/Include-Abhängigkeiten. Haupt-/Nachrichtenname und Namespace stimmen
mit der offiziellen Archivdefinition überein; ein offizieller Datei-Hash ist
nicht verfügbar. Keine beliebige Schema-URL aus einer Importdatei wird geladen.

## Implementierter enger Vertrag

Ein vollständiger Auszug für genau eine EUR-IBAN. Gebuchte Kontobewegungen,
ausdrücklich belegte Periode, gebuchter Anfangs-/Endsaldo, stabile Bankreferenzen,
Prüfsumme des unveränderten XML-Originals und die vollständige Übernahmevorschau.
Keine vorgemerkten Bewegungen, fehlenden/mehrdeutigen Salden, gemischten Konten,
Währungen oder unvollständigen Seiten als vollständigen Auszug ausgeben.
Sammelbuchungen bleiben reale Bankbewegungen; keine erfundenen Einzelzahlungen.

Sicherer Parser mit deaktivierten Entitäten, DTD, Netzwerk und fremden Schemata,
begrenztem Dokumentumfang und fest versionierter lokaler XSD-Prüfung. Bisherige
CSV-Originale, Hashes, Quittungen, Zuordnungen und Restoreprüfungen bleiben unter
dem alten Vertrag. Neue Methode mit eigener Fähigkeitskennung, beiden Clients,
exakter Wiederholung und frischen Bank-/Finanz-/Buchführungsrechten. Auszugsimport
erzeugt weiterhin keine tatsächliche Zahlung oder Steuerentscheidung.

Die neue Fähigkeitskennung ist `bank_camt_v1`; die drei neuen Endpunkte sind
`/bank/camt/inspect`, `/bank/camt/preview` und `/bank/camt/statements` unter dem
bestehenden Business-API-Präfix. Die erste Prüfung schreibt nichts. Aus dem
Original gelesene Kontodaten, Periode, Referenz und Salden werden angezeigt;
die Vollständigkeitsbestätigung ist zunächst nicht angekreuzt. Erst danach
folgen Übernahmevorschau und eine zweite ausdrückliche Bestätigung. Eine
bereits angenommene Übernahme wird bei verlorener Antwort mit exakt derselben
Vorgangs-ID wiederholt. Frischer Rechte- oder Fähigkeitsentzug sperrt auch
diesen Wiederholungsweg. Browser und App prüfen die vollständige Vorschau
zusätzlich unabhängig gegen ihren kanonischen SHA256-Hash.

Das unveränderte XML wird mit Formatvertrag, Schemahash, exakten Quellzeilen,
Bankreferenzen und Originalperioden archiviert. Originaldownload und Restore
prüfen die Projektion erneut aus den Bytes. Bekannte Bankidentitäten werden
nicht wegen eines anderen Dateinamens oder einer neuen Auszugsreferenz doppelt
angelegt. Eine erkannte inhaltsgleiche Bewegung mit anderer Identität benötigt
weiterhin den bestehenden begründeten Nachweis. Es entstehen keine neuen
Tabellen und keine Änderungen an historischen Lohn-/Reisekernen.

## Tatsächlich ausgeführte Prüfungen

[Rohdaten und Prüfsummen](evidence/bank-camt-2026-11-10/manifest.json) bewahren
auch alle frühen Fehler getrennt auf.

- 49 gemeinsame Format-, Fach-, Paket-, Komponentenlisten- und CI-Auswahlfälle
  bestehen in47,806s. Gegenproben prüfen Schemawechsel, DTD/Entitäten/fremde
  Ressourcen, falsche Codierung, Teilseiten, ausstehende Buchungen, mehrdeutige
  Salden, Fremdwährungen, Rundungsbedarf und veränderte Originaldaten.
- Drei tatsächliche PostgreSQL-/MFA-/HTTP-Fälle bestehen zuletzt in81,839s:
  eingeschränkte Datenbankrechte, gleichzeitige Übernahme, Rechteentzug,
  vorhandener Geldfluss, vollständiger Dump/Restore mit erneutem MFA und
  erhaltenen Originalbytes/Quittungen. Eigene begrenzte Testcontainer wurden
  nach Prüfung ihrer exakten Identität entfernt. Der frühere grüne Lauf mit
  drei Fällen in65,048s bleibt separat erhalten.
- Alle1.095 Browsermodulfälle bestehen in19,712s. Ein wirklicher Browserablauf
  mit MFA, Dateiauswahl, beiden Bestätigungen, absichtlich verlorener Antwort,
  entzogener Formatfreigabe, identischer Wiederholung, XML-Download,119,00€
  vorhandenem Zahlungseingang und vollständigem Monatsabgleich besteht.
  Eine Technikerrolle erhält keinen Originalzugriff;390px bleiben bedienbar.
- 22 gemeinsame Appfälle bestehen, darunter Windows-/iOS-Darstellung bei390px,
  unabhängige Vertragsprüfung, Wiederholung und privater Rechteentzug. Ein
  zusätzlicher nativer Test gegen einen wirklichen temporären HTTP-Server
  besteht mit identischer Wiederholung und exaktem XML-Originaldownload.
- Abschließende Appanalyse: keine Probleme,27,3s. Die vollständige neue App-
  und eigene Remoteprüfung werden im Arbeitsstand separat nachgetragen.

Die zunächst fehlende Browser-Assetfreigabe ist korrigiert. Frühere Appfehler
betreffen den Testdateipfad, eine fehlende Testbindung sowie das Aufräumen des
Sitzungstimers; spätere Erfolge ändern diese Rohfehler nicht. Die erste gesamte
Node-Prüfung wurde durch das Unterprozessverbot der Sandbox abgebrochen; die
vollständige Wiederholung mit erlaubten lokalen Prozessen besteht.

## Verbleibende Format- und Betriebsgrenzen

Unterstützt wird ausschließlich camt.053.001.08 mit UTF-8, genau einem EUR-
IBAN-Auszug, vollständigen Kalendertagen und gebuchten Anfangs-/Endsalden an
den jeweiligen Periodengrenzen. Bankcode-Untergruppensummen, andere Versionen,
Teilseiten, unvollständige Zeiträume und gemischte Konten/Währungen werden
ausdrücklich abgewiesen. Sammelbuchungen bleiben die reale Kontobewegung.
Eine echte Datei der Kreissparkasse Rottweil und reale Providerzugänge fehlen;
die kontrollierten Prüfungen sind keine bestätigte Anbieterkompatibilität oder
direkte Bankanbindung. R08.03 und die Gesamtabnahmen bleiben deshalb offen.
Loxones spätere Einrichtung wird durch diesen Abschnitt nicht vorgezogen.

Neue Laufzeitabhängigkeit ist ausschließlich das festgelegte `lxml==6.1.3`
in allen drei Backendlisten. Die Komponentenliste ist reproduzierbar erneuert;
die veröffentlichten CPython3.12-Wheels für Windowsx64, Linuxx64/ARM64 und
Macx64 wurden gegen PyPI-Metadaten geprüft. Windowspakete müssen Parser,
lokales Schema und beiliegende Quellenlizenz enthalten und bestehen dafür die
wirkliche Paketprüfung; ein plattformfremder Lauf ersetzt den Windowsbau nicht.

Zusätzliche Übergabeprüfung: Ein tatsächliches portables Unternehmens-ZIP
enthält das vollständige XML bytegleich samt ursprünglicher Bankprojektion;
ein Fall besteht in 0,979s. Die verschärfte Paketprüfung lädt das lokale XSD
aus dem tatsächlich entpackten Windows-Quellpaket. Ihr erster Versuch deckt die
noch fehlende neue Abhängigkeit in der zweiten lokalen Testvenv auf; diese
ist nun gemäß demselben festen Lock eingerichtet. Das ist kein Windowsbau.

## Eingefrorener Quellstand und Paketressourcen

Der Codecommit c52d2072db09b4d1b4b31ce1477c4ad7100955b1 startet tatsächlich
aus seinem eigenen vollständigen Backend-/Browserarchiv: MFA, sieben echte
Browserdateien einschließlich beider XML-Module und das lokale festgelegte XSD
bestehen in 3,496s. Das tatsächlich entpackte Windows-Quellpaket lädt den
Parser und genau sein beigefügtes Schema; neun gemeinsame Paket-/CI-Fälle
bestehen in 3,238s. Die native Gesamtprüfung läuft noch. Die unveränderten
CRLF-/Lizenzbytes erhalten eine auf diese Fremdquellen begrenzte Git-
Whitespaceausnahme; kein Schema- oder Originalhash wird dafür geändert.

## Eigene Plattformprüfung des veröffentlichten XML-Bankstands

Development 42864815919 an 4f67bf8 besteht alle 20 Gruppen. Damit sind
auch der tatsächliche Windowsbau mit XML-Parser und Schema, die neuen
PostgreSQL-/MFA-/Restorefälle sowie der neue Browser-Bankablauf im eigenen
veröffentlichten Gesamtstand bestätigt. Windows-Komplettpaket: Artefakt
13788890572, 40.629.752 Bytes, SHA256
4eb01d0fe4d42e01e292d80abe33ab50ad0ec1436146de6d9ae05d8a3fc6d729.
Windows-Onlinepaket: Artefakt 13788027574, 22.255.008 Bytes, SHA256
e3805783925bb4577965f91b3e0472a67465c44bec582e26b4ebfaaa68e4864b.
Der getrennte manuelle iPhone-Lauf 42864950880 ist noch aktiv; daraus wird
noch kein signiertes Paket abgeleitet. Upload bleibt false. Neue
Personal-Kontenauswahl wird getrennt geprüft und ist noch nicht veröffentlicht.
