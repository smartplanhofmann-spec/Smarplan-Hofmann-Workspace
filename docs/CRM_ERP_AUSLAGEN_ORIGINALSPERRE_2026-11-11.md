# Auslagenoriginale über Mitarbeiter hinweg schützen

Stand: 11.11.2026. Fortsetzung des vollständigen Gesamtauftrags, Anforderungen
R09 und unveränderte `CRM_ERP_Gesamtziel.txt`. Basis ist der vollständig
technisch geprüfte Funktionsstand ab6b615; diese zusätzliche Korrektur erhält
einen eigenen Quell- und Prüfnachweis.

## Reproduzierter Fehler und Änderung

Die bisherige Einreichungssperre verglich identische Belegbytes nur innerhalb
eines Mitarbeiterprofils. Ein bereits vollständig mit 49,87 EUR erstattetes
Original konnte ein zweiter Mitarbeiter unter neuer Datei-ID erneut einreichen.
Der tatsächliche Gegenfall am bisherigen Code schlägt fehl, weil die erwartete
409-Ablehnung ausbleibt. Dieser rote Nachweis bleibt erhalten.

Die interne Prüfung vergleicht jetzt die SHA256 der vollständigen Originale
über alle Mitarbeiter derselben Unternehmensdatenbank. Sie läuft vor neuer
Einreichung, Freigabe und Erstattungsbestätigung innerhalb derselben
Schreibtransaktion. SQLite serialisiert unabhängige Verbindungen mit
`BEGIN IMMEDIATE`; PostgreSQL verwendet den vorhandenen datenbankbezogenen
Transaktions-Lock. Nur eine konkurrierende Einreichung wird angenommen.
Die Fehlermeldung verrät keine fremden Mitarbeiter-, Antrags-, Datei- oder
Betragsdaten. Die lesenden Personalrouten bleiben auf ihre bisherigen Rechte
und Mitarbeiter eingeschränkt.

Aktive Bindungen sind eingereichte, freigegebene und erstattete Anträge.
Zurückgewiesene Anträge und vollständig tatsächlich zurückgezahlte Anträge
geben das Original frei. Eine Geldrückzahlung bleibt ausdrücklich zu bestätigen;
der neue Prüfablauf erzeugt keine Überweisung und erfindet keine Rückzahlung.
Die zusätzliche Reiseabrechnung prüft vor neuer Freigabe ebenfalls aktive
alte Doppelanträge. Ihre bestehenden Bindungen verhindern weiterhin Änderungen
am bereits verwendeten Auslagenoriginal.

## Alte Konflikte nachvollziehbar auflösen

Unter **Personal → Mitarbeiter → Personalakte, Reisen und Lohnvorbereitung →
Reisen und Auslagen** ergänzt **Freigabe zurücknehmen** eine eigene Aktion
für noch nicht erstattete Freigaben. Sie benötigt aktuelle Personalprüfrechte,
eine andere Person als Mitarbeiter und Einreicher, die aktuelle Fassung sowie
einen Prüfvermerk. Eine neue zurückgewiesene Fassung verweist auf die frühere
Freigabe; ihre Entscheidung trägt ausdrücklich `operation=withdraw-approval`.
Ein alter ungültiger Übergang ohne dieses Merkmal bleibt ungültig.

Eine bereits ausgeführte Erstattung lässt sich damit nicht aufheben. Für sie
bleibt die bestätigte vollständige tatsächliche Rückzahlung erforderlich.
An eine Reiseabrechnung gebundene Originale sind dort ausdrücklich zu korrigieren.
Frühere Entscheidungen, Originale, Monats-PDFs, Zahlungen und angenommene
Vorgangsquittungen werden weder überschrieben noch nachträglich neu bewertet.
Die unveränderte Wiederholung eines bereits angenommenen Auftrags liefert
nach aktueller Rechteprüfung weiterhin genau seine frühere Quittung.

Browser und native App zeigen die neue Aktion nur bei der zusätzlichen
Serverfähigkeit `personnel_expense_originals_v2`. Ältere Server zeigen diese
Aktion nicht. Ausstehende Appantworten behalten ihren ursprünglichen Auftrag
auch nach Rechteentzug und späterer erneuter Freigabe.

Die Sperre betrifft bytegleiche vollständige Originale. Sie ist keine
Bilderkennung unterschiedlicher Scans und keine Freigabe, denselben ganzen
Beleg beliebig zwischen Mitarbeitern aufzuteilen. Solche Fälle benötigen
weiterhin eine ausdrückliche fachliche Prüfung.

## Tatsächlicher Nachweis und Auslieferung

- Roter ursprünglicher Gegenfall: ein Fall, erwartete 409 bleibt aus.
- Finale betroffene Backend-/Reise-/CI-Auswahl: 80 Fälle erfolgreich.
- Finale PostgreSQL-/MFA-/HTTP-/Konkurrenz-/Komplettrestore-Auswahl: drei Fälle
  erfolgreich, ausschließlich eigene synthetische Loopback-Datenbank.
- Native Personal-Widgetprüfung: zwölf Fälle erfolgreich; gesamte Appanalyse
  ohne Befund. Drei neue Fälle prüfen Rücknahme/Wiederholung, Eigenprüfung
  und ältere Server.
- Vollständige finale Browsermodulprüfung: 1.120 Fälle erfolgreich, ohne Skip.
- Finaler tatsächlicher Browserlauf mit aktivierter Namespace-/PID-/Netzwerk-/
  Seccomp-Isolation besteht Rücknahme, erneute Einreichung/Freigabe, Erstattung/Rückzahlung,
  Monatsoriginale und verlorene Antwort mit unveränderter Wiederholung.
- Die unveränderte ursprüngliche Fehlerprobe besteht am finalen Code mit
  einem Fall. Originalziel und sämtliche 64 bisherigen Lohnmodule bleiben
  gegen ab6b615 bytegleich.

Der erste PG-Restorelauf stoppte korrekt wegen einer noch offenen eigenen
Testverbindung. Nach geordnetem Schließen bestehen alle drei Fälle. Frühere
Flutter-Vorläufe dokumentieren einen lokalen Testaufbaufehler und eine falsche
Erwartung an die serverseitige Ablehnung bei Rechteentzug; beides ist korrigiert.
Socket-/Unterprozessbeschränkungen der Cloud und der erfolgreich verwendete
eigene Cache bleiben ebenfalls als getrennte Vorläufe erhalten.

Rohlogs und Quellbindung stehen unter
[`evidence/expense-originals-2026-11-11/`](evidence/expense-originals-2026-11-11/).
Die neue gemeinsame Remoteprüfung und ihre Paketierung sind ein gesonderter
Nachlauf. Der ältere RV-Liefernachweis wird dadurch nicht auf neuen Code
übertragen. Neue Serverinstallation, reale Geräteprüfung, Fach-/Sicherheits-
und Gesamtabnahme A–G werden daraus nicht abgeleitet.

## TestFlight-Freigabe bleibt getrennt

Die automatische Freigabeprüfung hat den aus „Ok. Mach fertig“ abgeleiteten
TestFlight-Start abgelehnt: Die Formulierung autorisiert die Übermittlung des
konkreten signierten App-Pakets an Apple nicht ausdrücklich genug. Der ganze
abgelehnte Start wurde nicht ausgeführt. Eine neue konkrete Uploadfrage nennt
Smartplan Office, `de.smartplanhofmann.office`, Apple TestFlight und ab6b615;
eine passende ausdrückliche Antwort liegt bisher nicht vor.

`upload_to_testflight` bleibt false. Diese Auslagenkorrektur verändert den
Funktionsstand; eine spätere Zustimmung zu ab6b615 darf nicht still auf den
neuen Code übertragen werden. Entwicklung und interne Prüfungen laufen weiter.
