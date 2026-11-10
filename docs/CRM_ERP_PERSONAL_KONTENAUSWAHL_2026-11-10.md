# Personalprofile ohne Zugriff auf die Benutzerverwaltung

Der Benutzerkonto-Selektor für Mitarbeiterprofile verwendete bisher in Browser
und App die vollständige Benutzerverwaltung. Diese ist absichtlich dem
Inhaber vorbehalten. Eine berechtigte Personalverantwortliche konnte deshalb
kein Konto auswählen; die native Leseansicht fragte diese Verwaltung sogar
bei reinen Personal-Leserechten unnötig ab.

Codecommit `495ee6312da707fbdd8ca8341117647e1e953c84`, Basis 4f67bf8.
Eigenständig geprüfte Arbeitskopie:
`/workspace/smartplan-employee-account-selection-20261110`.

## Änderung

Der neue lesende Endpunkt `/employees/account-selection` im bestehenden
Business-API benötigt die aktuellen globalen Rechte `personnel.read` und
`personnel.manage`. Er liefert ausschließlich Kennung und E-Mail aktiver
Konten aus derselben Unternehmensdatenbank. Rollen, Passwortdaten, Sitzungen
und andere Verwaltungsfelder bleiben ausgespart. Projektbezogene Freigaben
erlauben keinen globalen Kontenzugriff. Fremdfirmen-/Suchparameter,
Schreibmethoden und mehr als 500 Konten werden abgewiesen; eine abgeschnittene
Liste wird nicht als vollständig ausgegeben. Der Versionsvertrag ist 1,
die Fähigkeitskennung `employee_account_selection_v1`.

Browser und App prüfen die Antwort geschlossen und wählen kein Konto vorab.
Ein bestehendes Profil behält seine Kontobindung; zum Bearbeiten ist kein
erneuter Verzeichnisabruf nötig. Native reine Leser öffnen die vorhandenen
Profile ohne Kontenabfrage. Der neue native Erfassungsdialog prüft seine
Rechte erneut und wird bei Rechte-, Sitzungs- oder Bereichswechsel entfernt.
Ein verspäteter Abruf kann keinen privaten alten Dialog wiederherstellen.
Die ausdrückliche Wiederholung einer verlorenen Antwort verwendet denselben
Auftrag; die bestehende serverseitige Dubletten-/Revisionsprüfung bleibt aktiv.
Die alte Benutzerverwaltung bleibt auch für Personalverantwortliche gesperrt.

Zusätzlich können Berechtigte ein vorhandenes Mitarbeiterprofil weiter
bearbeiten und beenden, nachdem dessen Benutzerzugang gesperrt wurde.
Die bestehende Person und ihre historischen Zeit-/Entgeltbedingungen bleiben
gebunden. Ein neues Profil benötigt weiterhin einen vorhandenen aktiven Zugang;
die Änderung entsperrt weder Benutzer noch bucht sie Profile um.

## Tatsächliche Prüfung

[Vollständige Rohdaten und Prüfsummen](evidence/employee-account-selection-2026-11-10/manifest.json)
enthalten auch die früheren Fehler.

- 28 gemeinsame Fach-/MFA-/HTTP-/Planungs-/CI-Auswahlfälle bestehen in 11,850s.
  Ein tatsächlicher Personalzugang ohne Inhaberrolle bleibt von `/users`
  ausgeschlossen und legt trotzdem genau ein Mitarbeiterprofil an. Sperrung,
  globale gegenüber projektbezogenen Rechten, Originalnonce und Beendigung
  eines Profils nach Zugangssperre werden tatsächlich geprüft.
- Alle 1.098 Browsermodule bestehen in 18,521s. Der erste Gesamtlauf der
  isolierten sparsamen Arbeitskopie scheiterte an fehlenden vorhandenen
  Dokument-Fixtures. Diese wurden unverändert ergänzt; keine Produktprüfung
  oder Testauswahl wurde dafür entfernt.
- Zehn gemeinsame Appfälle bestehen einschließlich Windows-/iOS-Darstellung
  bei 390px, ausdrücklicher Kontowahl, unklarer Antwort, privaten Leserechten,
  verspäteter Antwort, Rechteentzug und vollständigem Sitzungswechsel.
- Der wirkliche Browserablauf mit MFA, einem Personalverantwortlichen ohne
  Benutzerverwaltungsrecht, tatsächlicher Profilanlage, absichtlich verlorener
  Antwort, unveränderter Wiederholung, Kontobindung und Rechteentzug besteht.
  Auch eine während der Übertragung zurückgehaltene alte Kontenliste öffnet
  nach Rechteentzug keinen Dialog. Zwei lesbare mobile Ansichten sind gesichert.
- Appanalyse: keine Probleme, 11,5s. Das tatsächliche vollständige Quellarchiv
  dieses Commits startet mit MFA, sieben Browser-Assets und lokalem Bank-XSD
  erfolgreich; ein Fall in 4,397s.

Der erste MFA-Testaufbau verwechselte einen Rückgabe-Token mit einem
Benutzerdatensatz; er ist korrigiert. Der erste App-Erfassungsnachlauf suchte
nach der verlorenen Antwort noch die ursprüngliche Schaltflächenbeschriftung
statt „Erneut senden“. Die korrigierte Wiederholung ist grün; die erhaltenen
Erstfehler werden dadurch nicht nachträglich als Erfolg ausgegeben.

Keine neue Abhängigkeit, Datenbankschemaänderung oder neue Benutzeranlage
durch den lesenden Endpunkt. Alle 61 historischen Lohnmodule und das originale
Gesamtziel bleiben bytegleich. Die nachstehenden Integrations- und Paketnachweise
gehören zu ihren jeweils genauen Quellen; eine Liveinstallation oder Gesamtabnahme
wird aus lokalen Nachweisen nicht abgeleitet.

## 10.11.2026 – integrierte Personal-Kontenauswahl und abgeschlossene iPhone-Pakete

Die separat geprüfte Personal-Korrektur 495ee63 ist als 56d9925 in das
Hauptprojekt integriert; alle zehn geänderten Dateien sind bytegleich.
Direkt im Hauptprojekt bestehen zusätzlich vier tatsächliche MFA-/HTTP-/
Quellarchivfälle in 6,847s und sieben Appfälle. Personalauswahl, geschützte
Bearbeitung und das Beenden bestehender Profile nach Kontosperre sind damit
konkret geprüft. Kein Zugang zur vollständigen Benutzerverwaltung wurde
für Personalrollen geöffnet. Der neue Stand wird gesondert veröffentlicht
und erhält seine eigene vollständige Plattformprüfung.

Der vorherige veröffentlichte Bankstand 4f67bf8 hat jetzt neben allen 20
Developmentgruppen und 1.997 lokalen Appfällen auch den automatischen
unsignierten iPhone-Release 207 aus 42864818725 bestanden. Der tatsächliche
manuelle Lauf 42864950880 besteht vollständig einschließlich signiertem
iPhone-/iPad-Paket 208, Artefakt 13789192915; Upload false. Der automatische
Push-Lauf und der manuelle Lauf sind unterschiedliche Auslöser. Das signierte
208 enthält den Bankimport und Offline-Konfliktfix, die spätere Personal-
Korrektur jedoch noch nicht. Keine neue Live- oder Geräteinstallation.

## Eigene vollständige Plattformprüfung des integrierten Produktstands

Veröffentlicht ist `29b02c82a12d4aa1dfc97eaa84638d840882612d`. Seine eigene
Development-Prüfung 42872855464 besteht alle 20 Gruppen. Die tatsächlichen
Backendlogs enthalten 2.186 Fälle in 1.565,117s mit drei ausgewiesenen
Auslassungen: zwei separate PostgreSQL-Gegenprüfungen im allgemeinen
Backendjob und die Windows-Prozessbereinigung auf Linux. Die eigenen
PostgreSQL-/Windowsgruppen sind zusätzliche getrennte erfolgreiche Jobs.
Der eigene Flutterjob bestätigt drei separate native PDF-Fälle und 2.001
Hauptfälle. Alle 1.098 Browsermodulfälle und die tatsächlichen Browserabläufe
sind Bestandteil des geprüften Produktumfangs. Beide Windows-Pakete sind
tatsächlich gebaut; der automatische unsignierte iPhone-Release ist 209.
Aktuelle Artefakte und der getrennte signierte Nachweis stehen im
[Lieferstand](CRM_ERP_LIEFERSTAND_AKTUELL.md).

Der zusätzliche lokale Gesamtnachlauf wurde während des Cloud-Ausfalls
unterbrochen. Sein unverändertes Teilprotokoll endet bei 1.229 sichtbaren
Erfolgen, ohne Abschluss-/Exitstatus. Es wird nicht zum vollständigen
Prüferfolg umgedeutet; die vollständigen aktuellen CI-Logs bleiben separat.
Das Geräteprotokoll enthält 28 noch ungeprüfte Fälle einschließlich der
neuen Personal-, XML-Bank- und nativen Offline-Konfliktabläufe. Die
[Serveranleitung](CRM_ERP_SERVERUPDATE_29B02C8_2026-11-10.md) ist vorbereitet,
aber mangels SSH-Zugang in dieser Cloud nicht am Live-System ausgeführt.

Die eigene macOS-Vorprüfung des manuellen iPhone-Builds 210 bestätigt 1.996
Hauptfälle plus drei separate native PDF-Fälle, fünf ausgewiesene Linux-
Integrationsauslassungen und den erfolgreichen tatsächlichen iOS-Gerätebau.
Die fünf plattformbegrenzt ausgelassenen Fälle sind im vollständigen Linux-
Lauf enthalten. Das vollständige macOS-Protokoll bleibt separat erhalten.
Zusätzliche lokale Archivdownloads werden vom Cloud-Proxy vor Empfang der
Bytes mit HTTP403 abgewiesen; die GitHub-Digests sind Metadaten, keine hier
zusätzlich lokal errechneten Archivprüfsummen.

Der aktuelle manuelle iPhone-Lauf 42873343567 ist jetzt vollständig erfolgreich.
Signiertes Paket 210: Artefakt 13794053691, 29.959.338 Bytes, SHA256
bd556ca8b5464b6436ebbd9544831d8013a6e766adf41e838de4d8ee06be4e06.
Der wirkliche Job 130058782187 bestätigt endgültige Distributionssignatur,
Team, Keychain-Berechtigung und Schlüsselbereinigung. TestFlight ist
übersprungen; keine neue Geräteinstallation. Das vollständige Signierlog
ist mit dem genauen Quellstand im Manifest erhalten.
