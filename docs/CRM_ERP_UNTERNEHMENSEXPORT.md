# Unternehmensexport und vorbereiteter Ausstieg

Stand: 03.11.2026. R11.05 ergänzt die vorhandene Instanzbindung und
Datenbanksicherung um einen portablen Fachexport sowie eine dokumentierte
Ausstiegsprüfung. Implementierung:
[API und unveränderliche Nachweise](../backend/business_company_handover.py),
[Dateninventar](../backend/company_export_catalog.py),
[Archiverstellung](../backend/company_export_archive.py),
[unabhängiger Prüfer](../backend/company_export_verify.py).

Eine aktive Geschäftsführung kann für ihre bereits durch den Operator an
Datenbank, Host, Ablage und Schlüssel gebundene Unternehmensinstanz einen
vollständigen Export der klassifizierten Datenbank-Fachdaten erzeugen. Der Export
enthält auch sensible Personal- und Lohndaten sowie noch nicht übernommene
Kundendateien in Quarantäne. Grund, Unternehmensbindung und die Kenntnis dieses
Umfangs müssen ausdrücklich bestätigt werden. Es gibt keinen Projektfilter, keine
Freigabe für Projektbenutzer und keinen Export über einen Offlinezugang.

Jede Bestandsabfrage, Erstellung, Wiederholung, Prüfung und jeder Download prüft
die aktuelle aktive Owner-Rolle und Instanzbindung auf dem Server. Zwei Firmen
verwenden getrennte gebundene Datenbanken/Prozesse; ein Client kann seine Firma
nicht durch einen Requestparameter wechseln. Eine ungebundene Installation zeigt
den fehlenden Operatorschritt und erstellt kein Archiv.

## Archiv und Dateninventar

Der explizite Katalog umfasst aktuell **268 bekannte Tabellen**, darunter 207
einschließbare Fachtabellen und 61 bewusst ausgeschlossene Tabellen.
Die tatsächlich vorhandenen Tabellen und Spalten werden gegen diesen Katalog
geprüft. Unbekannte Tabellen, neue ungeprüfte Spalten oder unverständliche
Beziehungen sperren die Erstellung; es entsteht kein stillschweigend unvollständiger
Export. Bereits gespeicherte Archive bleiben ohne Neuerstellung abrufbar.

Das ZIP enthält:

- `manifest.json`: Format- und Katalogversion, Kataloghash, feste Instanz- und
  Exportkennung, Ersteller, Zeitpunkt, Grund, Snapshotverfahren, Grenzen,
  Dateninventar, tatsächliche Spalten/Primärschlüssel/Fremdschlüssel, Zeilenanzahlen,
  Dateiliste und SHA-256-Prüfsummen;
- `data/*.jsonl`: UTF-8-Datensätze einschließlich Fachhistorien, Auditnachweisen,
  historischen Kontakt-/Personensnapshots, Rechnungs-/Buchungsbeziehungen,
  Lohnkonten, Vertriebschancen, Inventuren, individuellen Felddefinitionen/-werten,
  Migrationszuordnungen/-abgleichen, tatsächlichen Lohnzahlungen,
  Servicefällen, Bankauszügen/-abgleichen, Betriebsmittelübergaben/-rückgaben,
  Prüfbelegen und KI-/Sprachanfragenachweisen;
- `files/`: unveränderte Binäroriginale, unter anderem Rechnungs-PDF/XML,
  Eingangsbelege, unterschriebene Protokolle, Kunden- und Personaldokumente sowie
  hochgeladene CRM-/Finanzexportoriginale aus dem Übernahmewerkzeug;
  die Datensätze enthalten Dateiverweis, Größe und Hash statt der Binärspalte;
- `originals/`: zusätzlich vollständig zusammengesetzte Plan- und
  Anfrageanhänge aus ihren gespeicherten Abschnitten. Unfertige oder bereits
  gelöschte Uploads sind ausdrücklich als unvollständig gekennzeichnet;
- `README.txt` und `verify_archive.py`: Leseanleitung und identischer unabhängiger
  Standardbibliothek-Prüfer. Keine Verbindung zur laufenden Anwendung ist zur
  Inhaltsprüfung erforderlich.

JSON-Nutzdaten in Datenbank-Textfeldern bleiben unveränderte Zeichenketten.
Binäroriginale werden gegen ihre vorhandenen Quellprüfsummen geprüft. Das Archiv
bewahrt Fachhistorien und Beziehungen, führt aber keine Ereignisse erneut aus.
Frühere Exportnachweise werden mitexportiert, deren ZIP-Binärdaten werden nicht
rekursiv in jedes Folgearchiv eingebettet.

Jeder Katalogeintrag dokumentiert maschinenlesbar `purpose`, `category`,
`personal_data`, `sensitive`, `access`, `retention_basis`, `retention_days`,
ausgeschlossene Spalten und den Ausschlussgrund. `sensitive` kennzeichnet einen
erhöhten Schutzbedarf, keine abschließende Einordnung nach Art. 9 DSGVO.
Es wird keine pauschale Löschfrist erfunden; `retention_days` ist grundsätzlich
`null` und die konkrete Aufbewahrung braucht eine fallbezogene Prüfung.

Eine gesonderte maschinenlesbare `retention_rule` dokumentiert für
`business_payroll_account_events` und die im Lohnkonto referenzierten bezahlten
Läufe aus `business_payroll_events` die belegte Regel nach
[§ 41 Absatz 1 Satz 9 EStG](https://www.gesetze-im-internet.de/estg/__41.html):
Aufbewahrung bis zum Ende des sechsten Kalenderjahres nach der letzten
eingetragenen Lohnzahlung. Letzte Zahlung 2026 bedeutet beispielsweise
Aufbewahrung bis einschließlich 31.12.2032. Import-/Erstellungsdatum lösen diese
Frist nicht aus. Ergänzende Unterlagen nach Satz 10, weitere Pflichten und
Aufbewahrungssperren sind gesondert zuzuordnen. Die Regel wird nicht pauschal auf
unbezahlte Berechnungen oder Personaldateien übertragen. Technische
`business_payroll_account_requests` enthalten ebenfalls personenbezogene
Ergebnissnapshots, bleiben jedoch wegen ihrer technischen Replayfunktion vom
Fachexport ausgeschlossen und im Inventar ausdrücklich beschrieben.

## Bewusste Grenzen und Aufbewahrung

Passwort-/Saltwerte, MFA-, OAuth-, Sitzungs- und Geräteschlüssel, Portalzugangsgeheimnisse,
verschlüsselte Providerkonfiguration/-zugangsdaten, interne Schlüsselverweise und
technische Wiederholungsquittungen sind ausgeschlossen. Datenschutzanfragen und
Sprachanfragen sind Fachnachweise und werden trotz ihres Tabellennamens
`*_requests` eingeschlossen. Freitext kann vom Nutzer selbst eingegebene vertrauliche
Angaben enthalten; der Ausschluss von Systemgeheimnissen ist keine Erkennung
beliebiger Geheimnisse innerhalb von Geschäftsdokumenten.

Private Arbeitsinhalte und Personenexport-BLOBs aus Datenschutzfällen sind
ebenfalls ausdrücklich ausgeschlossen. Ihre fallbezogene Berechtigung,
Aufbewahrungsentscheidung und Ablauffrist darf kein zusätzlicher Firmenexport
umgehen. Minimale Fall-/Export-/Purge-Metadaten mit Hashes und Fristen bleiben
exportiert; sie enthalten keine Subjekt-ID, Klarnamen oder Antwortinhalte.

Das Manifest benennt `database_restore_supported: false`,
`technical_request_replay_included: false`,
`authentication_credentials_included: false` und
`external_only_files_downloaded: false`. Es gibt keinen automatischen Reimport
dieses Fachexports in eine laufende Datenbank. Für einen originalgetreuen
Wiederanlauf bleiben das bestehende geprüfte Datenbank-Backup, seine Schlüssel
und das dokumentierte Wiederherstellungsverfahren notwendig.

Dateien, die ausschließlich bei einem externen Anbieter liegen und nur durch
einen Verweis repräsentiert sind, werden nicht automatisch heruntergeladen.
Gespeicherte kanonische Datenbankoriginale werden eingeschlossen. Der Export
ruft keinen externen Anbieter auf und übermittelt nichts an Empfänger.

Die geprüften Obergrenzen sind **256 MiB unkomprimierte Quelldaten**, **128 MiB
ZIP**, **250.000 exportierte Datensätze** und **50.000 Archivdateien** zuzüglich
Manifest. Ein Überschreiten führt zum Abbruch ohne gespeichertes Teilarchiv.
Für größere Bestände ist ein gesonderter geprüfter Exportweg erforderlich;
eine unbegrenzte Eignung für beliebig große Unternehmen ist nicht nachgewiesen.

Das heruntergeladene ZIP ist unverschlüsselt und enthält sensible Daten. Es
gehört in eine geschützte Ablage mit berechtigtem Empfängerkreis. Verschlüsselung
einer Übergabe und Empfängerfreigabe bleiben dokumentierte Operatorschritte.
Die Serverkopie ist ein unveränderlicher Nachweis im bestehenden geschützten
Datenbankspeicher. Eine Archivlöschung oder automatische Aufbewahrungsbereinigung
ist hier nicht implementiert.

## Snapshot, Wiederholung und erneutes Öffnen

SQLite verwendet eine unmittelbare Schreibtransaktion. PostgreSQL erwirbt die
anwendungsweite prozessübergreifende Schreibsperre **vor** dem Beginn des
`REPEATABLE READ`-Snapshots. Dadurch wirkt ein während des Wartens abgeschlossener
Rollenentzug bereits auf die Exportprüfung. Tabelleninventar, Originale, Archiv,
Quittung und Auditnachweis entstehen atomar; ein Fehler hinterlässt keinen
Teilauftrag. Laufzeitrollen dürfen die drei neuen Nachweistabellen nur lesen und
ergänzen. Bestehende Fachschemas werden durch die additive Migration nicht geändert.

Ein wiederholter identischer Auftrag erhält dasselbe gespeicherte Ergebnis und
dieselben Archivbytes. Eine andere Nutzung derselben Vorgangskennung bleibt ein
Konflikt. Nur nach negativem Quittungsnachweis unter derselben Sperre markiert der
Server fachliche Konflikte ausdrücklich mit `request_resolution: not_accepted`.
Fehlende Rechte, fremde Instanz und widersprüchliche Vorgangskennung liefern diese
Freigabe zum Verwerfen eines ausstehenden Auftrags nicht.

Vor dem Öffnen ist der SHA-256 des ZIP mit der separat gespeicherten Smartplan-
Quittung zu vergleichen. Die unabhängige Prüfung kann mit dem Prüfer aus der
vertrauenswürdigen Softwareinstallation erfolgen:

```sh
python backend/company_export_verify.py unternehmen.zip --instance-id INSTANZ-ID
```

Der mitgelieferte identische Prüfer darf erst nach der Herkunftsprüfung verwendet
werden; Skripte aus fremden ZIP-Dateien sind nicht automatisch vertrauenswürdig.
Der Prüfer liest ausschließlich die ZIP-Datei. Er entpackt nichts, führt keine
Archivdatei aus, öffnet keine Datenbank und benötigt keine Drittanbieterpakete.
Er prüft Dateiliste, sichere Pfade, Größen, Hashes, eindeutige JSON-Felder,
Instanzbindung, Inventar/Zeilenschemas, Originalzuordnungen und Zeilenanzahlen.
Eine erfolgreiche interne Inhaltsprüfung ist keine elektronische Signatur,
steuerliche Fachfreigabe oder Fremdherkunftsbestätigung.

## Geordneter Ausstieg

Die Übersicht führt Benutzer, Portalempfänger, Offlinezugänge, Eingangszugänge
und Integrationszustände ohne deren Geheimnisse auf. Gespeicherte Korrespondenz,
Portalveröffentlichungen und zusätzliche Empfänger bei Providern müssen in der
Übergabeprüfung berücksichtigt werden; die Übersicht behauptet keine vollständige
Liveinventur fremder Systeme.

Eine versionierte Prüfung benennt ein konkretes Archiv samt Hash, Grund,
Nachweise und Verantwortliche. Alle sieben Einzelbestätigungen beginnen
unbestätigt: Export geöffnet, Aufbewahrung geprüft, Empfängerübergabe bestätigt,
Providerwiderrufe geprüft, lokale Zugänge geprüft, Backupplan geprüft und
Betriebsabschaltung geprüft. Änderungen ergänzen die vorherige Prüfung und
überschreiben sie nicht. Der Status lautet `in_progress` oder bei sieben
Bestätigungen `ready_for_operator_review`. Beide sind dokumentierte Angaben des
Prüfenden (`attested_only: true`).

Dabei werden weder produktive Daten gelöscht noch Benutzer deaktiviert,
Sitzungen/Portalzugänge widerrufen, Provider verändert oder Dienste abgeschaltet.
`deletion_executed` und `revocations_executed` bleiben `false`. Tatsächliche
Übergabe, Zugangswiderrufe, Aufbewahrungsentscheidung und spätere Stilllegung
benötigen den gesonderten abgestimmten Operatorablauf.

## API

Alle Pfade unter `/business/company-handover` sind ausschließlich für die aktive
Geschäftsführung erreichbar. Zusätzliche Query-/JSON-Felder werden abgewiesen.

| Methode/Pfad | Ergebnis |
| --- | --- |
| `GET /` | Bindung, Bereitschaft, Sperrgründe, Kataloghash, Dateninventar, Exportliste, letzte Prüfung und Zugangsübersicht |
| `GET /inventory` | Maschinenlesbares Dateninventar und Sperrgründe |
| `POST /exports` | Neues unveränderliches Archiv nach ausdrücklicher Bestätigung |
| `GET /exports/{id}` | Gespeicherte Metadaten und vollständiges Manifest |
| `GET /exports/{id}/archive` | Unverändertes ZIP nach erneuter Rechte-/Integritätsprüfung |
| `GET /exports/{id}/verify` | Serverprüfung des gespeicherten Archivs, ohne Zustandsänderung |
| `POST /exit-reviews` | Versionierte Checkliste mit konkretem Archivhash und Nachweisen |

## Nachweise

- [Domain](../backend/test_business_company_handover.py): **14 Tests bestanden**,
  4,817 s. Originale einschließlich Quarantäne/privater Personaldateien und
  unveränderter Migrationsdateien, echte
  Planabschnitte, ausdrückliche Geheimnisausschlüsse, unbekannte Schemas,
  Rechte-/Instanztrennung, konkurrierende Quittungen, atomarer Abbruch,
  unveränderte Zugänge beim Ausstieg, manipulierte Archive und Quittungen sowie
  unabhängiger `python -I`-Prüfer ohne App-/Datenbankzugriff.
- [HTTP](../backend/online/test_company_handover_http.py): **2 Tests bestanden**,
  1,027 s. Zwei echte gebundene Firmen mit MFA-Sitzungen, ZIP-Binärantwort,
  exakte Wiederholung, fremde Sitzung/Instanz, Offlinezugang, unbekannte Felder,
  doppelte JSON-Schlüssel und Rollenentzug.
- [PostgreSQL](../backend/online/test_business_company_handover_pg.py):
  abschließender Lauf **2 Tests bestanden**, 10,267 s. Additive Migration ohne
  Änderung vorheriger Datensätze, echte HTTP/MFA, operative Datenbankrechte,
  bytegleiche PDF-Originale, Neustart, echter `pg_dump`/Restore und zwei getrennte
  konkurrierende Verbindungen. Ein tatsächlich auf der Schreibsperre wartender
  Export wird nach zwischenzeitlichem Rollenentzug abgewiesen. Die zusätzliche
  Archivzuordnungs-/Quittungshärtung ist in diesem Abschlusslauf enthalten.

Browser- und Flutterbedienung einschließlich Downloadprüfung sind integriert;
die konkreten Clientnachweise folgen im nächsten Abschnitt.

Nach der Ergänzung von Privacy-, Lohnzahlungs-, Service- und Bankkatalog wurden
die Domain-/HTTP-Nachweise erneut ausgeführt: **17/17 bestanden in 7,220 s** auf
der geprüften Umgebung mit cryptography 50/Pillow 13. Der zusätzliche Bankfall
prüft unveränderte Originalbytes, `file_sha256`, die vertrauliche Klassifikation
und den Ausschluss technischer Quittungen. Eine geänderte Originaldatei sperrt
den Export. Dieser Ergänzungslauf ersetzt keine neue Bankworkflow-Abnahme.

Nach Aufnahme der acht Betriebsmitteltabellen bestanden abschließend **20/20
Tests in 6,953 s**: 18 Export-Domain-/HTTP-Fälle und zwei unabhängige
Bank-/EÜR-Integrationsprüfungen. Der zusätzliche Betriebsmittelfall vergleicht
alle acht tatsächlichen DDL-Spaltenlisten mit dem Inventar und prüft unveränderte
persönliche Originalbytes sowie die Ablehnung eines falschen Quellhashs.
Die FK-basierten Betroffenenanker bleiben erhalten; JSON-Notizen, Fremdpersonen
und Originale benötigen weiterhin eine ausdrückliche fallbezogene Prüfung.
Die Ergebnisse sind eine überlappende Aktualisierung der oben genannten Läufe.

## Bedienung in Browser und nativer App

Unter **Einstellungen → Unternehmensübergabe** laden beide Clients die aktuelle
Geschäftsführungsrolle, globale Funktionsfreigabe und gebundene Firmeninstanz neu.
Ein unbekannter Tabellenkatalog oder eine fehlende Operatorbindung wird als
Sperrgrund gezeigt; die Oberfläche erfindet keine Bindung. Bestände erscheinen
zusammengefasst, Tabellen mit Zweck, Auslassungen und Aufbewahrungsgrundlage erst
nach Aufklappen. Hinterlegte Lohnkonto-Fristregeln zeigen ihren sachlichen
Geltungsbereich und ihr Beispiel, ohne daraus eine Frist für alle Personalakten
abzuleiten. Benutzer, Portal-, Import-, Anbieter- und Offlinezugänge können
separat eingesehen werden.

Die Archivbestellung erfordert einen Grund und zwei ausdrücklich gesetzte
Bestätigungen einschließlich sensibler Personal-/Finanzdaten. Die separate
Ausstiegsprüfung beginnt bei jeder neuen Fassung mit sieben offenen Punkten;
ein unvollständiger Prüfstand kann dokumentiert werden. Auch bei vollständig
bestätigter Checkliste steht die Operatorprüfung aus. Es wird kein Versand,
Widerruf, Löschen oder Abschalten als ausgeführt dargestellt.

Offene Aufträge behalten den Originalinhalt, die ursprüngliche Instanz und
Vorgangskennung ausschließlich in der authentifizierten Sitzung. Wiederholungen
laden die aktuelle Rolle und Bindung erneut. Rollenentzug und Instanzwechsel
lassen keine neue Bestellung zu und verbrauchen den offenen Auftrag nicht. Ein
bereits angenommener Export bleibt trotz später prüfbedürftigem Tabellenkatalog
wiederholbar. Explizite serverseitige `not_accepted`-Konflikte erlauben nach neuer
Bestandsaufnahme einen neuen Auftrag. Quittungen müssen zum unveränderten
Katalog, Grund, Auftraggeber beziehungsweise Archivhash, Prüfstand und erwarteter
Fassung passen.

Downloads lesen historische Metadaten und die gesonderte Serverprüfung, prüfen
ZIP-Signatur, exakte Bytezahl und SHA-256 und prüfen danach die Geschäftsführung
und Firmenbindung erneut. 128 MiB gelten nur für diesen Downloadpfad; allgemeine
Downloadgrenzen wurden nicht erhöht. Im nativen Dateidialog wird die aktuelle
Sitzung vor der tatsächlichen Ausgabe nochmals geprüft. Der enthaltene
`verify_archive.py` bleibt für die unabhängige Prüfung außerhalb der App verfügbar.

Clientnachweise vom 03.11.2026:

- `web/office/tests/company-handover.test.mjs`: **7/7 bestanden**. Explizite
  Bestätigungen, offene Prüfpunkte, gebundene Quittungen, verlorene Antwort mit
  bytegleicher Wiederholung, Rechte-/Instanzwechsel, inzwischen gesperrter Katalog,
  manipulierte Archivdatei und Rechteentzug während eines Downloads.
- `app/test/business_company_handover_test.dart`: **9/9 bestanden**. Native
  Formulare starten unbestätigt, Nicht-Geschäftsführer sehen keine Bestände,
  ursprüngliche Archiv-/Prüfaufträge bleiben bei Wiederholung unverändert,
  Archivprüfung bindet Größe, Prüfsumme und Instanz. Ein bereits geöffnetes
  sensibles Inventar wird bei geänderter Zugriffsgeneration ausgeblendet.
- `flutter analyze --no-pub`: **ohne Befund** nach Integration beider Clients.
- Reproduzierbare Browserstrecke: `SMARTPLAN_BROWSER_WORKFLOW=company-handover
  node web/office/tests/e2e.cjs`. Sie verwendet eine eigens operatorgebundene
  temporäre Datenbank und Serverablage, echte MFA sowie Namespace-/Seccomp-Sandbox.
  **Vollständig bestanden**: Inventar/Auslassungen, explizite sensible Bestätigung,
  verlorene Export- und Prüfantwort mit identischer Wiederholung, echter ZIP-Download
  mit SHA/Größenprüfung und mitgeliefertem `python -I`-Prüfer, bewusst unvollständiger
  Prüfstand und neue vollständige Fassung, unverändertes historisches Archiv,
  Nicht-Inhaber mit HTTP 403 sowie Desktop und mobile Ansicht. Sämtliche
  Benutzer, Nachweise und Prüfbestätigungen waren synthetisch.
