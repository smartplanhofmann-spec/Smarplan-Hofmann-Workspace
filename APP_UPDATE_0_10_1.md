# App 0.10.1 – Vorschau und klarere Oberfläche

Die Originalanhänge kommen inzwischen in Smartplan an. Dieses gemeinsame
App-Update ergänzt ihre direkte Vorschau und überarbeitet die als unübersichtlich
empfundene Oberfläche. Maßgeblich ist die Nutzerentscheidung: an Apple angelehnt,
ruhig und zeitgemäß, mit etwas Lebendigkeit und wenigen gezielten Farbakzenten.

## Arbeitsoberfläche

- Sichtbare, beschriftete Hauptnavigation auf kleinen Geräten; klare Trennung
  zwischen täglicher Projektarbeit und Verwaltung am Desktop.
- Ruhige weiße Flächen auf warmem Hellgrau, mehr Abstand und eine einheitliche
  Typografie. Blau kennzeichnet wichtige Aktionen und die aktuelle Auswahl.
  Semantische Farben bleiben tatsächlichen Hinweisen und Zuständen vorbehalten.
- Eine übersichtliche Projektliste mit gut erkennbaren Projektnamen und Kunden.
  Suche, Ansicht und Aktionen erhalten eine klare Reihenfolge.
- Die Projektmappe beginnt bei den offenen Aufgaben und nächsten Terminen.
  Auf breiten Fenstern stehen die beiden Bereiche nebeneinander; auf dem Handy
  bleiben die wichtigsten Aktionen und ersten Aufgaben schnell erreichbar.
- Der Anfrageeingang hebt Betreff, Absender und nächsten Schritt hervor.
  Neue Anfrage, Mailimport und technische Einrichtung haben unterschiedliche
  Gewichtung. Zähler stammen aus den tatsächlichen Anfragen.

Die Gestaltung fügt keine simulierten Geschäftszahlen hinzu und verändert keine
Rollen, Freigaben oder fachlichen Abläufe.

## Anhänge

Die [Anhangvorschau](ANHANGVORSCHAU.md) gehört zu demselben App-Paket:
PDF-Seiten, JPEG-/PNG-Bilder, Zoom und eine Rückkehr zur Anfrage beziehungsweise
zum Projekt. Originaldateien bleiben ausdrücklich speicherbar beziehungsweise
teilbar. Nicht unterstützte oder beschädigte Dateien erhalten einen verständlichen
Hinweis mit Dateiausgabe.

## Installation und Abnahme

Die neue **Online-App 0.10.1** vollständig in einen neuen Ordner entpacken und
die bisherige App vorher schließen. Die vorhandenen App-Daten und ausstehenden
Offline-Eingaben behalten. Der vorhandene Anhangserver 0.10/Schema 5 und der
bestehende Bot liefern die benötigten Daten; es gibt für dieses App-Update keine
zusätzliche Serverinstallation oder neue Botkonfiguration.

Prüfungen betreffen Zugriffswiderruf, verifizierte Originalbytes, PDF-/Bildanzeige,
Seitenwechsel, unpassende Dateitypen, typische Arbeitsabläufe und Layout bei
Telefon-/Tablet-/Desktopbreiten. Native Builds und Paketmanifeste müssen exakt
zum ausgelieferten Quellcommit passen. Die tatsächliche Windows- und mobile
Gerätebedienung wird anschließend mit dem Nutzer geprüft.
