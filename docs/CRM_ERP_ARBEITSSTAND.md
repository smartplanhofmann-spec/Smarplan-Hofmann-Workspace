# Verbindlicher Arbeitsstand für die Fortsetzung

Stand: 08.11.2026. Projekt: `/workspace/Smarplan-Hofmann-Workspace`.
Lokaler Entwicklungsbranch: `codex/finish-20261108`.
Autorisierter Veröffentlichungsbranch: `codex/testupdate-0.7-projects-20261104`.

## Ziel und fachlicher Umfang

Der Nutzer beauftragt am 08.11. erneut die Fertigstellung der gesamten Software
und fragt ausdrücklich nach dem Erhalt des Gesamtziels. Die ursprüngliche
[Gesamtzieldatei](../CRM_ERP_Gesamtziel.txt) ist vollständig erneut gelesen und
unverändert vorhanden: 23.863 Bytes, SHA-256
`a4dea28f6de4afd3e36d1549441aad91ce16dad374f56097979cc2d79b07fbf5`.

Endziel ist die zusammenhängende branchenübergreifende deutsche CRM-/ERP-Lösung
mit Kunden/Vertrieb/Portal, Projekten, Planung, Angeboten/Aufträgen/Rechnungen,
Material/Einkauf/Service/Betriebsmitteln, Zeiten und Dokumentation, eigener
Buchhaltung, deutscher Lohnabrechnung, Assistent/Regeln, geschützter Offlinearbeit,
Windows-/iPhone-/Browseranwendung, Installation/Betrieb und Abnahmen A–G.
Die frühere Projektphase war eine Reihenfolgeentscheidung, keine Streichung
von Buchhaltung oder Lohn aus dem Endziel.

Festgelegt bleiben Einzelunternehmen/EÜR, Regelbesteuerung mit Ist-Versteuerung,
19 % Standard-USt, SKR04, Nettopreise sowie reguläre Beschäftigte und Minijobs.
Weitere Länder und unbesprochene branchenspezifische Spezialprodukte gehören
nicht automatisch zur ersten deutschen Version.

## Wiederhergestellte Quellen und bestätigter Betriebsstand

Die neue Cloud-Umgebung startete mit dem alten sauberen Branch work auf
822fe58. Der neuere komplette Entwicklungsstand war dort noch nicht abgerufen.
Der autorisierte Remote-Testbranch wurde geholt und der letzte Stand 7c06f36
unter dem neuen lokalen Branch wiederhergestellt. Der alte Branch und die
vorhandenen Arbeitskopien bleiben erhalten. Die Wiederherstellung ist keine
neue Entwicklung und keine Serverinstallation.

Der letzte tatsächlich durch den Nutzer bestätigte Serverstand bleibt
`a93cb4d02eab610e5f2a8b07fbd1ee51ae99c3e5`: Updateabschluss, drei Dienste,
Sandbox-/Datenbankbindung und aktiver Sicherungstimer bestätigt. Für das spätere
Browserupdate auf 5880f88 wurde ein Befehl bereitgestellt; sein Ergebnis ist
noch nicht vom Nutzer bestätigt. Eine Statusfrage ist gestellt.

Windows 0.13.0 und der unsignierte iPhone-Prüfbuild sind tatsächlich gebaut.
Der Remote-Lauf auf 5880f88 besteht Windows, Simulator, Flutter, Backend,
Online-API, Update und HTTPS. Der Business-/Browserjob scheitert im Assistenten-
Test an der Annahme eines nach Übersicht weiterhin ausgewählten Projekts.
Der iPhone-Prüfbuild besteht; der signierte Upload bleibt übersprungen.

## Konkrete aktuelle Arbeit

1. **Wiederherstellung/Originalziel:** abgeschlossen und per Hash geprüft.
2. **Browserregressionen:** Assistent, Zusatzfelder und Kundenbereich verwenden
   nach allgemeinen Seiten wieder eine ausdrückliche Projektwahl. Der Assistent
   wählt zudem seine erlaubte Datenbasis erneut, bevor er gezielt Artikel sucht.
   Die neue Navigation wird damit nicht auf ihre frühere globale Wirkung
   zurückgestellt.
3. **Parser-Kompatibilität vor Updates:** Der neue Quellstand prüft einen bereits
   installierten Parser mit künftigem Backendcode, tatsächlicher Dienst-UID,
   NoNewPrivileges, leerer vertraulicher Umgebung und vollständigem Sandboxbericht.
   Fehler liegen vor Wartung, Dienststopp, Journal und Kandidatenvorbereitung.
   Es findet keine automatische Paketänderung statt. Die spätere tatsächliche
   systemd-Startprüfung bleibt zusätzlich bestehen.
4. **Nachweis:** 87 Update-/Recovery-/Operatorfälle, 21 Import-API-Fälle, 860
   Browser-Modultests und gezielte echte MFA-/HTTP-/Chromium-Abläufe bestanden.
   [Aktueller Prüfnachweis](evidence/project-resume-2026-11-08/verification.json).

## Weitere unabhängige Entwicklungsarbeit

- Die neue vollständige CI auf dem aktuellen Quellstand nachprüfen und
  tatsächliche neue Fehler beheben; nicht nur bereits grüne Jobs zählen.
- Weitere benannte Standard-Lohnfälle additiv integrieren. Dazu gehören unter
  anderem Faktorverfahren, individuelle Minijobsteuer, Versicherungsvarianten,
  Minijob-Jahresgrenzen und weitere Leistungen/Sachbezüge. Der
  [Lohn-Lückenplan](CRM_ERP_LOHN_LUECKENPLAN_2026.md) bewahrt auch historische
  Ausgangspunkte; pro Fall den heutigen Code prüfen. Bestehende begrenzte
  Berechnungen bleiben unter ihren gespeicherten Versionen reproduzierbar.
- EÜR-/Abschlussfälle, Auswertungen, Länder-/Regeltrennung und erlaubte
  Unternehmensaktionen gemäß der Anforderungsmatrix weiter vervollständigen.
  Fehlender Code wird nicht als externer Freigabemangel bezeichnet.
- Abnahmen A–G zu einem durchgängigen Lieferumfang verbinden. Lokale Fixtures
  ersetzen keine tatsächliche Windows-/iPhone-Bedienung oder Liveintegration.

Für den nächsten Lohnfall ist der aktuelle PAP 2026 recherchiert. Das
Faktorverfahren benötigt ausdrücklich bestätigte Merkmale, eine genaue
Übernahme der amtlichen Rundungsstellen und neue Regel-/Quellversionen.
Es ist mit dieser Recherche noch nicht implementiert oder freigegeben.

## Tatsächliche externe Voraussetzungen

Für signierte iPhone-Verteilung ist die Verfügbarkeit eines Apple-Developer-
Kontos angefragt. Schlüssel gehören in die vorgesehenen geschützten Einstellungen,
nicht in den Chat. Anbieter/Originalformate und reale Zugänge werden bei den
konkret ausgewählten Schnittstellen benötigt. Fachliche/rechtliche Abnahme,
unabhängiger Sicherheitstest und gegebenenfalls Meldezulassungen bleiben eigene
Nachweise. Diese Punkte stoppen keine davon unabhängige Codearbeit.

Die gesamte Software ist noch nicht als vollständig fertig oder produktiv
freigegeben ausgewiesen. Maßgeblich bleiben alle Anforderungen und Abnahmen
im Originalziel; es wird kein Fertigstellungsprozent aus Dateien oder Testzahlen
abgeleitet.
