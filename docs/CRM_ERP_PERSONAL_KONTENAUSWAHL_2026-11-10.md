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
Gesamtziel bleiben bytegleich. Die Integration und ihre eigene Paketprüfung
werden getrennt nachgetragen; keine Liveinstallation oder Gesamtabnahme wird
aus diesen lokalen Nachweisen abgeleitet.
