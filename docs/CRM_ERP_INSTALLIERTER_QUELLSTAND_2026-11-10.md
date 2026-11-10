# Installierter Quellstand und vollständige Serverarchive

Aktive Folgearbeit R11.04/R15.02/F/G auf8e6cff5 (Produkt b02c84a).
Der vollständig lokal geprüfte V13-Stand bleibt getrennt erhalten:1934 tatsächliche
Appfälle,1056 Browsermodule,48 Backend-/CRLF-/CI-Fälle und echter PG-Restore.
Keine neue Liveinstallation oder echte Geräteabnahme.

## Tatsächlicher Ausgangspunkt

Der Zustandsendpunkt nennt unverändert0.12.0-online-pilot als bestehende API-
Kompatibilitätskennung. Das ist kein zuverlässiger Auslieferungsstand. Der
bestehende Quellstand in einer Git-Arbeitskopie oder die veränderliche äußere
SOURCE_COMMIT-Datei beweist nicht die gerade von einem Prozess geladene Kopie.
Die erste wirkliche MFA-/HTTP-Anfrage nach einem eigenen Installationsnachweis
scheitert vor der Änderung mit404 (ein Fall/2,037s).

## Begrenzte Implementierung

Beim Vorbereiten einer neuen Serverkopie erzeugt das tatsächliche Standard-
bibliothekswerkzeug online.installation ausschließlich einen eigenen
BUILD_SOURCE.json-Marker im ausgelieferten Onlinepaket. Bestehende Marker
werden nicht überschrieben. Der neue GET /api/v1/business/installation verlangt
Online-MFA-Sitzung und aktuelle globale settings.manage-Berechtigung. Offline-
Zugänge sind gesperrt. Der öffentliche Gesundheitsendpunkt behält seine
Kompatibilitätskennung; dort wird kein Quellstand veröffentlicht.

Jede laufende App liest den Marker beim Start einmal ein. Ein später geänderter
äußerer Marker oder neu gestarteter anderer Prozess ersetzt diese Prozessangabe
nicht. Fehlende, doppelte, zu große, ungültige, verlinkte oder gruppen-/welt-
schreibbare Marker bleiben ausdrücklich unrecorded ohne geratenen Commit.
Es werden keine Pfade, Datenbanknamen, Schlüssel oder Benutzerangaben ausgegeben.
Die Angabe ist der beim Paketieren festgehaltene Quellstand, keine digitale
Signatur oder unabhängige Unversehrtheitsbescheinigung gegen Administratoren.

Browser und App zeigen die Anzeige unter Einstellungen → Version und Support →
Serverstand anzeigen. Eigene Fähigkeit und Rechte werden vor und nach dem Lesen
neu geprüft; die native Anzeige entfernt den Inhalt nach Rechteentzug. Ohne
Serverfähigkeit wird der Endpunkt nicht angefragt. Die Kompatibilitätskennung
und eine App-Buildnummer werden nicht gleichgesetzt.

## Zusätzlich gefundene Archivierungsfehler

Beide Betreiberbefehle archivierten noch HEAD statt des vorher festgehaltenen
Commits. Die tatsächliche Git-/Tar-Gegenprüfung ändert HEAD in einem eigenen
Repository und reproduziert beide Abweichungen. Beide Befehle verwenden jetzt
den ausdrücklich gewählten vollständigen Commit. Die Erstinstallation nahm
außerdem nur backend auf; web fehlte trotz aktivem Browserendpunkt. Sie erhält
nun wie das Update backend und web. Die erneute echte Git-/Tar-Prüfung bestätigt
unveränderte alte Quellbytes, alle Browserdateien und nicht gruppenschreibbare
Rechte. Diese Prüfung führt keine Paketinstallation oder Systemdienste aus.

## Bisher wirklich ausgeführte Prüfungen

- Fünf MFA-/HTTP-/Dateifälle bestehen in2,974s: unbekannter/aufgezeichneter Stand,
  zwei getrennte laufende Apps, spätere Markeränderung, fremde Rolle, aktueller
  Grant-Widerruf, Offline-Zugang, Methoden/Anfragekanäle und echte Dateitypen.
- Acht CI-Gruppenverträge gemeinsam mit diesen Fällen:13 Fälle in4,304s.
  Neuer tatsächlicher Browserablauf und neuer PG-Test sind zusätzlich in den
  vollständigen Gruppenplan aufgenommen; alte Auswahlen bleiben enthalten.
- Zwei unabhängige Browserverträge bestehen. Zehn native Prüfungen einschließlich
  fünf bestehender Länder-/Einstellungsfälle bestehen; erster Lauf scheitert
  an einem fehlenden UI-Import und bleibt erhalten. Aktuelle Analyse sauber25,4s.
- Echter MFA-/Chromiumablauf mit tatsächlich vom Werkzeug geschriebenem Marker,
  unveränderter Kompatibilitätskennung,390px und frisch widerrufenem Supportzugang
  besteht. Keine Paketantwort wird im Browser ersetzt und kein externer Versand
  durchgeführt.
- Reale Archivierung beider korrigierten Betreiberbefehle besteht; beide ersten
  Fehler bleiben erhalten. Der volle isolierte Betreiber-Updateablauf läuft.
- Die echte PG-/Runtime-/MFA-/Restoreprüfung ist aktiv. Der erste Lauf scheitert
  am Test-SQL-Platzhalter; sein eigener Container wird anschließend geprüft
  entfernt. Produktabfragen oder Laufzeitrechte wurden nicht gelockert.

Dieser isolierte Folgestand ist noch nicht veröffentlicht. Ganze App-/Browser-
Nachweise, die vollständigen Betreiber-/Paket-/PG-Prüfungen und der neue eigene
Build-/Auslieferungsnachweis bleiben abzuschließen. Der Gesamtauftrag läuft weiter.


## Tatsächlicher gemeinsamer Zwischenabschluss

1058 Browsermodule ohne Fehler/Skip,35 gemeinsame HTTP-/CI-/Archiv-/Paket-/
Inventarfälle in48,814s, zehn native Einstellungsfälle und saubere Analyse25,4s
bestehen. Der abschließende echte MFA-/Chromium-/390px-/Widerrufsablauf besteht.
Der erste isolierte Betreiberlauf besteht mit88 Fällen in659,471s; nach den
anschließend eingebundenen festen Commit-Assertions läuft die vollständige
Wiederholung am endgültigen unveränderten Stand. Die komplette aktuelle App-
Suite ist ebenfalls aktiv; daraus wird noch kein Abschluss behauptet.

Der echte PostgreSQL-/Runtime-/MFA-/vollständige Restorefall besteht in30,201s.
Fachjournal-Zeilen bleiben beim Lesen unverändert. Ein Wiederherstellen übernimmt
keinen alten Code-Marker; eine neu gestartete App liest ihren eigenen neuen
Paketstand. Die alte Sitzung wird korrekt mit401 abgewiesen, danach wird eine
wirkliche neue MFA-Anmeldung mit frischem TOTP-Zeitfenster verwendet. Frühere
Test-SQL-, Speicher- und Alt-Sitzungs-Erwartungsfehler bleiben erhalten. Alle
vier eigenen PG-Container wurden nach ID-/Aufgabenlabel-/Loopback-Prüfung
entfernt; letzterPort32807. Es wurden nur ignorierte Test-Buildcaches abgeschlossener
Arbeitskopien freigegeben; Quellen, Branches und Nachweise bleiben erhalten.

[Rohe Prüfdateien und genauer Stand](evidence/installation-context-2026-11-10/manifest.json).
Eine zusätzliche Prüfung des tatsächlich eingecheckten vollständigen Git-
Quellarchivs ist vorbereitet und wird nach diesem ersten Corecommit ausgeführt.
Neue Veröffentlichung, eigener Remote-CI-Stand, Liveinstallation und reale
Geräteabnahme bleiben separat. Der Vorgänger b02c84a besteht inzwischen alle20
Development-Jobs, seinen unsignierten iPhone-Build und beide Mailbot-Verträge;
signierter Upload übersprungen. Gesamtauftrag aktiv.


## 10.11.2026 – vollständige Betreiber-/Paket-/Restoreprüfung abgeschlossen

Installationskern **74490271b00a2f14f8a10a30aa69b703dd4c4d98** ist auf8e6cff5
eingecheckt. Der gesamte endgültige unveränderte Betreiberlauf besteht mit88
Fällen in661,167s. Zusätzlich wird genau7449027 tatsächlich als vollständiges
Git-Quellarchiv erzeugt und in einem getrennten Python-Prozess ausgeführt:
echte MFA, eigene unveränderte Paketkennung und fünf erforderliche Browser-
Einstiegsdateien bestehen in4,629s. Eine unbekannte oder falsch datierte
Arbeitskopie wird nicht als installierter Stand ausgegeben.

35 gemeinsame HTTP-/CI-/Git-Tar-/Paket-/Inventarfälle,1058 Browsermodule, zehn
native gemeinsame Einstellungsfälle, saubere Analyse25,4s, beide wirklichen
Browserläufe und der volle PG-/MFA-/Restorefall30,201s sind abgeschlossen.
Der alte Zugang bleibt nach Restore401; eine neue wirkliche MFA-Anmeldung ist
geprüft. Alle eigenen PG-Container sind entfernt. Ein zusätzlicher wirklich
geprüfter tiefer ungültiger Marker bleibt ebenfalls unrecorded; es wurde dafür
keine Produktausnahme oder gelockerte Dateiprüfung eingeführt.
Die komplette aktuelle App-Suite läuft mit über1000 tatsächlichen Fällen ohne
bisherigen Fehler/Skip. [Alle Rohdaten](evidence/installation-context-2026-11-10/manifest.json).

Dieser Zwischenstand wird ausschließlich auf dem autorisierten Testbranch
veröffentlicht, damit seine eigenen unabhängigen Builds beginnen können.
Keine neue Liveinstallation oder echte Geräte-/Fachfreigabe. Der Vorgänger
b02c84a ist mit allen20 Development-Jobs, unsigniertem iPhone-Release und beiden
Mailbot-Vertragsjobs vollständig grün; signierter Upload übersprungen.
Der Gesamtauftrag läuft weiter.

## Vollständige lokale Appprüfung und gezielter Remote-Nachlauf

Die aktuelle gesamte App-Suite besteht mit1939 sichtbaren Fällen, keinem Fehler
und keinem Skip.258 verborgene Ladeeinträge sind ausgeschlossen. Der tatsächliche
Maschinenschluss meldet success:true bei1429392ms, der Runner endet mit0 nach
1436,017s. Unveränderter Rohbericht, Runnerstatus und unabhängige Endzählung sind
im bestehenden Nachweisarchiv gesichert; sämtliche dort verzeichneten Rohhashes
und das Originalziel wurden erneut abgeglichen.

Für den veröffentlichten c4a2d8f bestehen19 von20 Development-Gruppen. Die andere
Gruppe browser-journeys(3) startet noch keinen Produkttest: Der gepinnte amtliche
Rechnungsprüfer kann wegenHTTP403 nicht geladen werden. Erster Rohfehler und
alle19 erfolgreichen Jobzustände bleiben erhalten. GitHub hat die gezielte
Wiederholung von129741200471 angenommen; laufender Ersatzjob129757269510.
Keine Quellenpins, Prüfsummen oder Pflichtprüfungen wurden dafür geändert.
Der eigene unsignierte iPhone-Release ist bei diesem Nachtrag noch aktiv.
Kein neuer Livebetrieb, Apple-Upload oder echte Geräte-/Fachfreigabe.

### Endgültiger Remote-Abschluss

Die gezielte Wiederholung129757269510 ist erfolgreich: Alle13 ausgewählten
wirklichen Browserabläufe enden mitexit0. Keine Auswahl oder Prüfung wurde
entfernt. Der ursprüngliche Werkzeugdownloadfehler bleibt separat erhalten.
Damit bestehen alle20 Development-Gruppen42790149143 am veröffentlichten
c4a2d8f. Auch der eigene unsignierte iPhone-Release42790149399 besteht;
der signierte Upload ist übersprungen. Beide Mailbot-Verträge bestehen.
Das aktuelle tatsächliche Windows-Online-Artefakt13752796971 hat22183211Bytes;
Lokalpaket13753096316, Start/Sicherung13750992870, iPhone-UNSIGNED194
ist13752144091. Nachweisdateien enthalten Quellcommit und Zustand; kein
unsigniertes Artefakt wird als installierbare iPhone-Auslieferung bezeichnet.
