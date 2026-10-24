# Smartplan Office 0.10 – Mailanhänge bis zur Projektmappe

Der bestehende Mailbot übernimmt Nachrichten erfolgreich in Smartplan. Der Nutzer
hat bei einer weiteren Mail festgestellt, dass ihre Anhänge fehlen. Der bisherige
0.9-Eingang hat ausschließlich Mailtexte übernommen. Das neue Paket ergänzt den
gesamten Weg: Originaldatei beim Bot, fortsetzbarer Upload, verifizierte Speicherung
auf Hetzner, Anzeige in der Anfrage und Übergabe in die Projektmappe.

## Zusammenhängender Ablauf

1. Der Bot übernimmt den unveränderten Nachrichtentext wie bisher. HTTP 201
   bestätigt zunächst diesen Text, noch nicht sämtliche Anhänge.
2. Er ermittelt die tatsächlichen MIME-Anhänge und holt ihre Originalbytes über
   seine vorhandene Mailanbindung. Anhänge werden dabei weder ausgeführt noch
   durch externe KI-, OCR- oder CAD-Dienste ausgewertet.
3. Ein unveränderliches Gesamtmanifest nennt ursprüngliche Dateikennungen,
   Dateinamen, MIME-Typ, Größe und SHA-256. Auch eine tatsächlich anhanglose
   Nachricht wird ausdrücklich mit einer leeren Liste bestätigt.
4. Fehlende 256-KiB-Abschnitte werden übertragen. Bereits bestätigte Abschnitte
   lassen sich nach einem Abbruch wiederverwenden. Geänderte Originale oder
   uneindeutige Quittungen werden als Fehler behandelt.
5. Erst die Bestätigung aller Originaldateien schließt die Übernahme ab. Fehlende
   oder teilweise übertragene Anhänge bleiben in Smartplan erkennbar.
6. Nach der Kunden-/Projektübernahme erscheinen die Dateien im Bereich
   **Dokumente** der Projektmappe. Es entsteht keine zweite Originaldatei.
7. PDF, JPEG und PNG können ausdrücklich als Planquelle übernommen werden.
   Diese Kopie durchläuft den bereits vorhandenen geschützten Hetzner-Import.
   PDF-Seite und Titel sind wählbar. E-Mail-Original und Planquelle besitzen
   getrennte Löschvorgänge.

## Nachträge und vorhandene Zugänge

Bereits übernommene Mails können ihre Anhänge nachträglich erhalten. Die Zuordnung
verwendet Quellpostfach und ursprüngliche Gmail-Nachrichten-ID; der Mailtext muss
dafür nicht erneut gepostet oder verändert werden. Die vorhandenen Bestätigungen
und der laufende Fünfminutenjob bleiben Grundlage des Bots. Ein zweiter paralleler
Job und ein Zurücksetzen der bisherigen Nachrichtenliste sind nicht erforderlich.

Bestehende aktive SPIN-Zugänge gelten weiter für ihr gebundenes Postfach und ihren
aktiven Besitzer. Sie erlauben die Einlieferung und deren Uploadstatus; allgemeine
Kunden-/Projektabrufe und Dateidownloads bleiben ausgeschlossen. Geheime Werte
werden ausschließlich über die geschützte Bot-Bindung verwendet. Eine sichtbare
Maskierung ist kein Nachweis für die Gültigkeit des tatsächlichen Schlüssels.

## Bedienung und Speicherung

- In der Anfrage stehen Anhänge vor dem Mailtext, mit Dateiname, Größe und Status.
  Gespeicherte Dateien sind herunterladbar; unvollständige Dateien werden nicht als
  fertig ausgegeben. Größe und SHA werden vor dem Speichern/Teilen geprüft.
- Windows verwendet den Speicherdialog. iPhone/iPad verwenden die native
  Teilen-/Speichern-Ausgabe; reale Geräteabnahme steht weiterhin gesondert aus.
- Anfrageanhänge sind online verfügbar. Bereits vorhandene Offline-Projektmappen
  und Planquellen behalten ihren bisherigen verschlüsselten Ablauf.
- Berechtigte Projektmitglieder können zugeordnete Dateien lesen. Die
  Geschäftsführung kann Originalanhänge nach Bestätigung entfernen. Aktive
  Originalbytes werden gelöscht; eine Löschmarkierung verhindert Wiederbelebung
  durch einen verspäteten Bot. Historische Betriebssicherungen werden dabei nicht
  rückwirkend verändert.
- Pro Datei gelten 20 MiB, pro Mail 60 MiB und 30 Dateien. Aktive und reservierte
  Dateien teilen sich ein Pilotkontingent von 2 GiB. Dateigrößen, Prüfsummen und
  Kontingente werden vor beziehungsweise während der Speicherung geprüft.

Das Paket betrifft den bestehenden Gmail-Boteingang. Der separate EML-Import
behält seine ausdrücklich angezeigte Beschränkung auf Anhangmetadaten. DWG/DXF
können als Originaldateien gespeichert werden; daraus folgt weiterhin keine
automatische CAD-Konvertierung.

## Bereitstellung und Abnahme

Version 0.10.0 benötigt PostgreSQL-Schema 5 und die Fähigkeit **mail_attachments**.
Der geschützte [Serverupdateablauf](deploy/hetzner/online/UPDATE_0_10.md) klont die
bisherige Datenbank und migriert die Kopie. Der vorhandene Importdienst und seine
Parserabhängigkeiten benötigen keine neue Erstinstallation.

Das [Bot-Anschlusspaket](integrations/mail_bot/README.md) enthält den bisherigen
Texthelfer und einen eigenen Anhanghelfer. Der bereits eingerichtete Bot muss
dieses Paket und seinen Arbeitsauftrag übernehmen. Originaldateien bleiben bis
zur tatsächlichen Empfangsbestätigung erhalten.

Zur Abnahme gehören eine neue und eine bereits übernommene Mail mit PDF/Bild,
unterbrochener Upload, Wiederholung, Projektübergabe, Download, Plankopie und
beide Löschrichtungen. Fachliche Erkennungsqualität, Windows-Herausgebersignierung
und tatsächliche mobile Geräteprüfung bleiben gesonderte Aufgaben.
