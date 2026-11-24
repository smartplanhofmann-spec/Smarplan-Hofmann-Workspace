# Smartplan Office · Bedienungsanleitung für das GrokBot-Testteam

**Ausgabe vom 24. November 2026 · Produktstand `4bb5071` · iPhone 0.13.0 (221)**

[PDF zum Weitergeben](SMARTPLAN_BEDIENUNGSANLEITUNG.pdf) · [Prüfprotokoll für das Team](GROKBOT_PRUEFPROTOKOLL.csv) · [Synthetische Testdateien](testdaten/)

## Einstieg und Testvorbereitung

**Für wen und für welchen Stand**

Diese Anleitung ist für das GrokBot-Testteam. Sie führt vom ersten Login bis zur Übergabe eines Unternehmensarchivs. Jede Übung nennt Rolle, Oberfläche, Handgriffe, Soll-Ergebnis und eine Gegenprobe. Der Server smartplan-test wurde am 24.11.2026 auf 4bb5071891344a38f640d8ae43ec240c1f95e61e aktualisiert. Apple hat den Upload von Smartplan Office 0.13.0, Build 221, angenommen. Das Team prüft die Verfügbarkeit in seiner TestFlight-Gruppe und die Installation auf dem eigenen Gerät.

**In 15 Minuten zum ersten Befund**

Startet im Browser unter https://office.smartplan-hofmann.de/office/. Öffnet ein zugewiesenes Testprojekt, notiert seine Kennung und stempelt eine kurze Sitzung über Personal → Personal & Zeiten → Zeit starten. Pausiert, setzt fort, stoppt und ladet die Seite neu. Erwartet wird eine Sitzung für dieses Projekt. Danach öffnet eine zweite berechtigte Person die Mappe auf Windows oder iPhone. Für den vollständigen Kundenauftrag folgen die Fälle 05, 08, 10, 12–16, 18–19, 22, 24–26.

**Was das Team vor dem Start braucht**

Lasst euch eine ausdrücklich für Testbuchungen eingerichtete, isolierte Firma zuweisen. Für die Trennungsprüfung braucht ihr eine zweite synthetische Firma. Nutzt separate Testkonten für Administration, Büro/Projektleitung, Montage A und B, prüfberechtigte Personalverwaltung, Lager/Einkauf, Buchhaltung und Datenschutz. Der Kunde testet den Portalzugang im privaten Browserfenster. Freigaben durch eine andere Person mit getrenntem Konto durchführen. Fach-, Betreiber- und Gerätetests den Personen mit tatsächlichem Zugang zuordnen.

**Testdaten für einen gemeinsamen Lauf**

Gebt dem Lauf ein Kürzel wie GB-2411-T1. Kunde: GrokBot Musterbau + Kürzel, fiktive vollständige deutsche Rechnungsanschrift. Projekt: Montageprüfung + Kürzel. Kontaktmail und Empfänger ausschließlich im freigegebenen Testpostfach. Leistung: 2 × 50,00 € netto, 19 % USt. Lagerartikel: 3 × 10,00 € Einstand. Dateibelege: ein selbst erstelltes Testfoto, ein zweitseitiger Musterplan, ein Muster-Lieferschein und ein Auslagenoriginal. Zur Dublettenprüfung exakt dieselbe Datei verwenden. Keine echten Kunden-, Mitarbeiter-, Bank- oder Authenticator-Daten in GrokBot oder das Prüfprotokoll kopieren.

**Tests aufteilen und Ergebnisse festhalten**

Jeder Tester arbeitet mit einer Kopie von GROKBOT_PRUEFPROTOKOLL.csv. Pro Fall und tatsächlich verwendetem Client eine Zeile führen. Für einen zweiten Gerätetyp die Zeile duplizieren. Die 37 bestehenden gerätespezifischen Fälle sind zusätzlich mit Kennung GP-01 bis GP-37 enthalten. Ein Tabellenprogramm kann die Datei als UTF-8 mit Semikolon öffnen. Vor dem Start Rolle, Version, Projektkennung und Testkürzel ergänzen. Danach beobachteten Wert, Zeitpunkt, Beleg und Ergebnis eintragen. Die mitgelieferte Vorlage enthält ausschließlich ungeprüfte Fälle.

**Was als Ergebnis zählt**

Bestanden: Soll-Ergebnis und Gegenprobe wurden im vorgesehenen Testkontext beobachtet. Fehler: konkrete Abweichung mit reproduzierbaren Schritten. Blockiert: Zugang, Gerät, Testfixture, Prüfer, Testanbieter oder isolierte Kopie fehlt. Nicht anwendbar: der Fall gehört nachweislich nicht zu dieser Betriebsvariante. Bei mehreren Prüfungen Teilergebnis im Ist-Feld nennen und den fehlenden Anteil offen lassen. Ein Bot ohne echtes iPhone kann den iPhone-Gerätetest einer Person zuweisen. Automatisierte Prüfläufe, unabhängige Fachfreigabe und echte Geräteabnahme erhalten jeweils eigene Nachweise.

**Wenn eine Antwort auf Speichern ausbleibt**

Notiert Zeitpunkt, Konto, Projekt, Vorgangskennung und beobachteten Status. Sucht das Original oder seine Quittung im selben Kontext. Nutzt die angebotene Prüfung oder Wiederholung des unveränderten ursprünglichen Auftrags. Prüft anschließend Anzahl und Betrag. Für Bankimporte, Belege, Personalakten und Zeitfreigaben ist eine neu angelegte Ersatzbuchung kein verlässlicher Nachweis.

**Dateien und Ausdrucke**

Das Team erhält dieses Handbuch als PDF und als durchsuchbare Repository-Fassung, die leere Ergebnistabelle sowie drei Muster-CSV und einen Musterkontoauszug im XML-Format. Sämtliche Finanzvorgänge sind Testjournal-Einträge in der isolierten Firma. Eine Nachricht versenden, einen Einkauf auslösen, Geld überweisen, an Behörden melden oder eine aktive Datenbank überschreiben gehört nicht zu diesen Übungen. Wenn ein solcher externer Schritt angezeigt wird, den sichtbaren Status dokumentieren.

**Windows-Pakete sichern**

Die GitHub-Downloads der beiden Windows-Pakete laufen am 25.11.2026 gegen 07:14 Uhr deutscher Zeit ab (lokal 07:13:44, online 07:14:52). Bewahrt das heruntergeladene ZIP mitsamt Manifest auf. Ist es abgelaufen, benötigt das Team ein geprüftes Paket derselben Produktquelle. TestFlight hat einen eigenen Verfügbarkeitsstatus.

## Wegweiser

- [Zugänge, Geräte und Navigation](#kapitel-1) · Fälle 01–04
- [Anfrage, Vertrieb, Katalog und Kundenportal](#kapitel-2) · Fälle 05–09
- [Projektmappe, Planung, Pläne und Baustellendokumentation](#kapitel-3) · Fälle 10–12
- [Arbeitszeit und Offlinearbeit](#kapitel-4) · Fälle 13–17
- [Einkauf, Lager, Geräte und Service](#kapitel-5) · Fälle 18–21
- [Rechnung, Projektkosten und Buchhaltung](#kapitel-6) · Fälle 22–26
- [Personal, Reisen und Lohn 2026](#kapitel-7) · Fälle 27–31
- [Assistent, Sprache, Kommunikation und Regeln](#kapitel-8) · Fälle 32–34
- [Importe, Lieferanten und Bankverbindungen](#kapitel-9) · Fälle 35–37
- [Datenschutz, Betrieb und Bedienbarkeit](#kapitel-10) · Fälle 38–42
- [Durchgängige Abnahmen A–G](#abnahmen)
- [Testdaten und Übergabe](#testdaten)

<a id="kapitel-1"></a>

## Zugänge, Geräte und Navigation

Beginnt mit einem Zugang pro Rolle. Für Vergleiche zwischen Geräten verwenden alle denselben Online-Testmandanten und dieselbe Projektkennung.

### 01 · Online im Browser anmelden

**Oberfläche:** Browser · **Rolle:** Büro / Administration

**So geht es:** Öffnet https://office.smartplan-hofmann.de/office/, meldet euch mit eurem persönlichen Testkonto, Passwort und Authenticator-Code an. Unter Einstellungen → Version und Support → Serverstand anzeigen liest die Administration den installierten Commit. Öffnet Übersicht, Kontakte, Projekte und dann wieder Übersicht.

**Daran erkennt ihr das Ergebnis:** Der installierte Commit beginnt mit 4bb5071. Übersicht zeigt berechtigte Aufgaben, Termine und Kennzahlen. In allgemeiner Übersicht und Kontakte gibt es keinen globalen Projektwähler. In Projekte öffnet ihr die Projektmappe, unter Dokumente grenzt der Projektfilter die Belege ein.

**Gegenprobe / Besonderheit:** Ladet die Seite neu und öffnet die Quelle einer Kennzahl. Fehlende Grundlagen müssen erkennbar sein. Bei leerem Personalbereich prüft Rolle, Modul und Mitarbeiterprofil.

### 02 · Windows- und iPhone-Zugang einrichten

**Oberfläche:** Windows, iPhone · **Rolle:** Gerätetester

**So geht es:** Windows: Online-Paket aus dem Lieferstand laden, ZIP vollständig in einen eigenen Ordner entpacken und smartplan_office.exe starten. iPhone: TestFlight öffnen, Smartplan Office 0.13.0 (221) auswählen, installieren bzw. aktualisieren. Auf beiden Geräten mit dem zugewiesenen Testkonto anmelden und dasselbe Projekt öffnen.

**Daran erkennt ihr das Ergebnis:** Projektkennung und freigegebene Mappe stimmen mit dem Browser überein. Haltet tatsächliche Windows-Version/Paketstand und TestFlight-Build im Protokoll fest.

**Gegenprobe / Besonderheit:** Ist 221 nicht angeboten, prüft die vorhandene Testgruppe in App Store Connect. Protokolliert Geräteverfügbarkeit als blockiert. Nutzt für den gemeinsamen Ablauf das Windows-Online-Paket; die lokale Windows-Variante hat einen eigenen Datenbestand (Fall 40).

### 03 · Rollen, Unternehmensbedarf und Zusatzfelder einrichten

**Oberfläche:** Browser · **Rolle:** Administration + Monteur

**So geht es:** In der isolierten Testfirma unter Einstellungen → Unternehmensbedarf und Module den Bedarf vor und nach Anlage eines Mitarbeiters vergleichen. Sichtbarkeit und fachliche Aktivierung einzeln ändern. Unter Benutzerrechte → Freigaben ansehen / ändern das Testprojekt zuweisen. Unter Zusatzfelder → Zusatzfelder verwalten ein Auswahlfeld „Prüfklasse“ mit A/B für Kontakte definieren; an einem Testkontakt A speichern.

**Daran erkennt ihr das Ergebnis:** Modulvorschlag, Sichtbarkeit, Schreibberechtigung und Projektzuordnung wirken getrennt. Der zugewiesene Mitarbeiter sieht sein Projekt. Wird A archiviert, bleibt sein alter Wert nachvollziehbar; für einen neuen Kontakt stehen nur gültige Werte zur Verfügung.

**Gegenprobe / Besonderheit:** In getrennten Sitzungen mit eingeschränktem Konto und einer zweiten Testfirma die jeweils erlaubten Ansichten öffnen. Fremdes Projekt, Personaloriginal und fremde Kundenakte bleiben unzugänglich. Entzug der Testzuweisung wirkt beim erneuten Öffnen. Ausgangskonfiguration wiederherstellen.

### 04 · Aussteller, Vorlagen und Projektstatus prüfen

**Oberfläche:** Browser · **Rolle:** Administration

**So geht es:** Unter Einstellungen → Aussteller & Briefpapier nur im isolierten Mandanten eine fiktive Adresse und Fußzeile für Testbelege hinterlegen. Länderumfang der Rechnungsstellung prüfen. Falls für einen Ablauf benötigt, deutschen Testaussteller getrennt freigeben. Unter Projektstatus einen Teststatus anlegen, im Projekt wählen und speichern.

**Daran erkennt ihr das Ergebnis:** Ein neuer Testentwurf verwendet die vorgesehenen Ausstellerdaten. Das PDF eines früheren ausgestellten Belegs behält die damalige Anschrift. Der Teststatus erscheint nach erneutem Öffnen des Projekts.

**Gegenprobe / Besonderheit:** Fehlen Testaussteller, Rechte oder Freigabe, bleibt der Nummern-/Ausstellungstest blockiert. Deutschland, EUR, Netto, 19 %, Ist-Versteuerung, SKR04 und EÜR sind das vereinbarte Testprofil. Einen abweichenden Umsatzsteuersatz nur mit eigens dafür vorgesehenem Referenzfall prüfen.

<a id="kapitel-2"></a>

## Anfrage, Vertrieb, Katalog und Kundenportal

Das Büro legt den Kunden einmal an. Das Team verwendet dessen Kennung für Anfrage, Angebot, Portal und Projekt.

### 05 · Anfrage in Kundenprojekt übernehmen

**Oberfläche:** Browser · **Rolle:** Büro

**So geht es:** Unter Anfragen einen vorhandenen synthetischen Eingang öffnen. Für einen Test des öffentlichen Formulars /office/contact.html ausschließlich den eingerichteten Testeingang ohne echten Antwortversand verwenden. Daten prüfen, passenden bestehenden Kunden wählen oder unter Kontakte einen Testkunden mit Ansprechpartner und vollständiger Rechnungsanschrift anlegen. Anfrage dem kanonischen Projekt zuordnen.

**Daran erkennt ihr das Ergebnis:** Eingangsquittung, Kunde und Projekt sind auffindbar. Eine Person mit Projektzugriff öffnet dieselbe Kennung in einem zweiten Client und sieht die korrekte Anschrift.

**Gegenprobe / Besonderheit:** Bei gleichem Namen anhand Kennung und Anschrift unterscheiden. Ein vorhandener Kunde darf durch Projektanlage oder erneute Übernahme nicht doppelt entstehen.

### 06 · Verkaufschance und Kommunikationsverlauf pflegen

**Oberfläche:** Browser, Windows, iPhone · **Rolle:** Vertrieb

**So geht es:** In Kontakte die Kundenkarte und die Vertriebspipeline bzw. Verkaufschancen öffnen. Eine offene Chance über 1.000 € netto mit 40 % Wahrscheinlichkeit anlegen. Fiktiven Anruf protokollieren, eine Wiedervorlage setzen und die Notiz mit Begründung korrigieren. In Kontakte → Kommunikationsverlauf oder Projektmappe → Kommunikation nach dem Vorgang suchen.

**Daran erkennt ihr das Ergebnis:** Die offene Chance zählt mit 400 € gewichtet. Originalnotiz, Korrektur, Zuständigkeit und Wiedervorlage sind erkennbar. Die Übernahme in ein Projekt bzw. einen Angebotsentwurf ist dem ursprünglichen Fall zugeordnet.

**Gegenprobe / Besonderheit:** Mit eingeschränktem Testkonto erneut suchen. Private oder nicht freigegebene Quellen dürfen nicht über den Verlauf sichtbar werden. Ein Gesprächsvermerk ist kein Versandbeleg.

### 07 · Lieferantenartikel übernehmen und Preisstand vergleichen

**Oberfläche:** Browser, Windows, iPhone · **Rolle:** Einkauf

**So geht es:** Im Browser Einstellungen → Externe Verbindungen → Lieferantenkataloge und Adapter öffnen. Eine Testquelle im Format catalog_csv_v1 wählen und katalog.csv aus dem Testpaket laden. Vorschau prüfen und ausdrücklich übernehmen. Artikel SYN-17 unter der Quelle erneut öffnen. Für datierte Preise den getrennten Bereich Datierte Katalogpreise und einen dafür vorgesehenen Preisfall verwenden.

**Daran erkennt ihr das Ergebnis:** Das Muster enthält 12,50 € Einstand, 20,00 € Nettoverkauf und 19 % USt. Vor der Übernahme bleibt der Artikelbestand unverändert. Originaldatei und Importhistorie sind zugänglich.

**Gegenprobe / Besonderheit:** Dieselbe Datei erneut prüfen. Eine spätere Preisänderung darf einen bereits gespeicherten Angebotsstand nicht verändern. Bei DATANORM das unterstützte Profil, Skalierung, Steuer und Zielpreis prüfen. Lieferantenprofile stehen in Fall 37.

### 08 · Angebot kalkulieren, annehmen und in Auftrag übernehmen

**Oberfläche:** Browser, Windows, iPhone · **Rolle:** Büro + Testkunde

**So geht es:** In Dokumente das Musterprojekt wählen. Angebot mit zwei Einheiten einer Leistung zu je 50,00 € netto und 19 % USt speichern. Prüft Mengen, Anschriften, Einzelpreis, Steuer und Gesamtbetrag. Die geprüfte Fassung für den Testkunden freigeben, den Angebotslink in einem privaten Browserfenster öffnen und annehmen. Intern die angenommene Fassung in die Auftragsbestätigung übernehmen.

**Daran erkennt ihr das Ergebnis:** 100,00 € netto + 19,00 € USt = 119,00 € brutto. Kunde, Projekt, Positionen und angenommene Angebotsfassung stimmen im Auftrag überein. Eine überarbeitete Fassung lässt die frühere lesbar.

**Gegenprobe / Besonderheit:** Mit einem eigenen zweiten Angebot die Ablehnung prüfen. Es entsteht daraus kein angenommener Auftrag. Die Links nur im zugewiesenen Kundentestfenster öffnen.

### 09 · Kundenbereich und Originaldateien bedienen

**Oberfläche:** Browser · **Rolle:** Büro + Testkunde

**So geht es:** Unter Dokumente → Kundenbereich einen kurzen Projekttext und genau ein Testoriginal ausdrücklich veröffentlichen. Projektzugang freigeben, für den Testempfänger Upload zulassen. Im separaten Kundenfenster Text und Original öffnen und eine kleine synthetische PDF einreichen. Im Kundenposteingang das Original prüfen und geschützt übernehmen.

**Daran erkennt ihr das Ergebnis:** Der Kunde sieht nur freigegebene Inhalte seines Projekts. Die intern übernommene Datei erscheint erst durch eine eigene Freigabe wieder öffentlich. Der Projektzugang ist getrennt von der Angebotsannahme.

**Gegenprobe / Besonderheit:** Eine zweite interne Datei und ein anderes Testprojekt bleiben unsichtbar. Widerruft den Testzugang mit Begründung und ladet die Kundenansicht neu. Der Zugriff muss enden.

<a id="kapitel-3"></a>

## Projektmappe, Planung, Pläne und Baustellendokumentation

Büro und Monteur arbeiten mit derselben Projekt-ID. Das Original eines Fotos, Plans oder unterschriebenen Berichts dient beim Vergleich als Referenz.

### 10 · Projektaufgaben, Meilensteine und Einsatz planen

**Oberfläche:** Browser, Windows, iPhone · **Rolle:** Projektleitung

**So geht es:** Unter Projekte die Mappe öffnen. Aufgabe, Teammitglied, Fälligkeit und einen Meilenstein zuordnen. Meilenstein auf erreicht setzen und Verlauf öffnen. Unter Einsatzplanung einen Termin mit Testmitarbeiter und Ressource einplanen; im zweiten Zugang Zeitraum und Projekt prüfen.

**Daran erkennt ihr das Ergebnis:** Beide Zugänge zeigen denselben Termin. Früherer und neuer Meilensteinstatus bleiben nachvollziehbar. Projektbudget und Rechnung ändern sich durch den Meilenstein nicht.

**Gegenprobe / Besonderheit:** Plant in einem zweiten Testprojekt dieselbe Ressource für dieselbe Zeit. Prüft die Konfliktmeldung, wählt anschließend einen freien Zeitpunkt.

### 11 · Plan importieren, bearbeiten und wieder öffnen

**Oberfläche:** Browser, Windows, iPhone · **Rolle:** Projektleitung / Montage

**So geht es:** In der Planansicht der Projektmappe eine kleine unterstützte Musterzeichnung importieren. Bei angebotenem PDF-Import die Vorschau und das Importergebnis prüfen. Plan öffnen, ein unterstütztes Planelement bzw. eine Markierung ergänzen, speichern, schließen und erneut öffnen. Einmal mit ungespeicherter Änderung zu einem anderen Projekt wechseln.

**Daran erkennt ihr das Ergebnis:** Plan und Bearbeitung gehören zum ursprünglichen Projekt und sind nach dem Speichern wieder da. Beim Verlassen ungespeicherter Arbeit gibt es eine verständliche Entscheidung. Das zweite Projekt erhält keine Kopie durch die Navigation.

**Gegenprobe / Besonderheit:** Eine ungültige Testdatei auswählen. Die Oberfläche muss den Fehler anzeigen, ohne ein fertiges Importergebnis zu behaupten. Laufende Aufträge bis zur Quittung verfolgen.

### 12 · Foto, Aufmaß und unterschriebenen Bericht prüfen

**Oberfläche:** Browser, Windows, iPhone · **Rolle:** Montage + Projektleitung

**So geht es:** Unter Fotos & Doku das beschriftete Testfoto hochladen, eine Markierung speichern und Original sowie Markierung neu öffnen. Einen gemessenen Beispielwert mit Einheit im Aufmaß eintragen. Bericht für dieses Projekt anlegen, Teilnehmer und Inhalt prüfen, mit Testnamen unterschreiben, speichern und PDF öffnen. Zweiter berechtigter Zugang öffnet denselben Bericht.

**Daran erkennt ihr das Ergebnis:** Originalfoto bleibt abrufbar. Aufmaß verwendet den eingegebenen Messwert. PDF zeigt Projekt, Inhalt, Testnamen und Unterschrift auch nach dem Neustart. Eine Korrektur ist als neuer Nachweis nachvollziehbar.

**Gegenprobe / Besonderheit:** Auf dem iPhone die Signaturfläche testen: ersten Strich, Neu zeichnen, Abbrechen und Fertig. Abbruch darf keine fertige Unterschrift übernehmen. Vergleicht die PDF aus zwei Zugängen, wenn beide Originaldateien herunterladbar sind auch die Dateiprüfsumme.

<a id="kapitel-4"></a>

## Arbeitszeit und Offlinearbeit

Für Stempelbuchungen braucht das Benutzerkonto ein aktives Mitarbeiterprofil, Zugriff auf das Projekt und die entsprechenden Modulrechte. Eine lokale Speicherung und die Annahme durch den Server sind zwei getrennt sichtbare Schritte.

### 13 · Arbeitszeit finden, stempeln und freigeben

**Oberfläche:** Browser, Windows, iPhone · **Rolle:** Mitarbeiter + Zeitprüfer

**So geht es:** Browser: Personal → Personal & Zeiten → Zeit starten. Projekt ausdrücklich wählen und mit Zeitereignis speichern bestätigen. Windows/iPhone: Projekt öffnen → Arbeitszeit; bei schmalem Fenster über Projektbereich. Starten, pausieren, fortsetzen und stoppen. Uhrzeiten notieren, neu laden, anschließend als Prüfer den Arbeitstag und die Projektzuordnung kontrollieren und freigeben.

**Daran erkennt ihr das Ergebnis:** Eine Sitzung enthält die vier Ereignisse, die richtige Projektkennung und eine Nettoarbeitszeit ohne die Pause. Eine begründete Zeitkorrektur bleibt mit ursprünglicher Erfassung und Freigabeverlauf sichtbar.

**Gegenprobe / Besonderheit:** Fehlt Zeit starten, prüft Mitarbeiterprofil, Projektzuordnung, Modulaktivierung und persönliche Rechte. Als Mitarbeiter testweise eine fremde Zeit öffnen; sie darf ohne passende Rechte nicht einsehbar sein.

### 14 · Freigegebene Stunden in einen Entwurf übernehmen

**Oberfläche:** Browser · **Rolle:** Büro

**So geht es:** Für diesen separaten Fall im Testprojekt eine abrechenbare, freigegebene Stunde vorbereiten. In einem neuen Angebots- oder Rechnungsentwurf Freigegebene Arbeitszeiten übernehmen wählen; 50,00 € netto je Stunde und 19 % USt ausdrücklich eintragen. Position und Quelle prüfen, Entwurf speichern und wieder öffnen.

**Daran erkennt ihr das Ergebnis:** Die Stunde ergibt 50,00 € netto und 59,50 € brutto. Andere Projektzeiten fehlen zu Recht. Nach endgültiger Abrechnung ist dieselbe Zeit für eine zweite Rechnung gesperrt.

**Gegenprobe / Besonderheit:** Ändert sich die Quelle vor dem Speichern, Auswahl neu laden und erneut prüfen. Führt diese Übung in einem eigenen Entwurf aus, damit die 119,00-€-Rechnung aus Fall 08 unverändert bleibt.

### 15 · Offlinezeit und Planänderung synchronisieren

**Oberfläche:** Windows, iPhone · **Rolle:** Montage + zweiter Zugang

**So geht es:** Mit dem Online-Client das zugewiesene Projekt für Offlinearbeit vorbereiten und auf dem Gerät öffnen. Verbindung trennen (iPhone: Flugmodus, WLAN aus). Zeit mit Start/Pause/Fortsetzen/Stopp aufnehmen. App schließen, offline neu öffnen und entsperren. Wieder verbinden, synchronisieren und im Browser prüfen. Separat einen Plan auf Gerät A offline und auf B online bearbeiten.

**Daran erkennt ihr das Ergebnis:** Vor der Verbindung steht die Erfassung aus. Nach der Synchronisation erscheint genau eine Sitzung mit den notierten Zeiten. Beim Plankonflikt bleiben die Fassungen unterscheidbar; Lokale Kopie behalten erhält die Bearbeitung von B.

**Gegenprobe / Besonderheit:** Geräteentsperrung einmal abbrechen. Geschützte Daten bleiben gesperrt. Ist die Serverantwort unklar, denselben ursprünglichen Auftrag prüfen und seine Quittung abgleichen. Ein zweiter Versuch darf keine zusätzliche Buchung erzeugen.

### 16 · Offline-Servicebericht unterschreiben und Konflikt klären

**Oberfläche:** Windows, iPhone · **Rolle:** Montage + Büro

**So geht es:** Im vorbereiteten Projekt Serviceberichte → Servicebericht erfassen öffnen. Titel und Leistung ergänzen, Entwurf auf diesem Gerät speichern → Prüfen und unterschreiben. Mit Testnamen signieren, Unterschrift auf diesem Gerät sichern. Online Synchronisieren, Archiviertes PDF öffnen und im zweiten Zugang vergleichen.

**Daran erkennt ihr das Ergebnis:** Das PDF hat den richtigen Kunden, Text und die Unterschrift. Wiederholte Synchronisation erzeugt genau ein Archivoriginal.

**Gegenprobe / Besonderheit:** Zweiter Durchgang: Während A offline unterschreibt, ändert B die Bezeichnung des Testkunden oder Projekts. Auf A Konflikt prüfen. Der übernommene Folgeentwurf besitzt aktuellen Kontext und leere Signatur. Die ursprüngliche Fassung bleibt erhalten. Zweimalige Bestätigung öffnet denselben Folgeentwurf.

### 17 · Älteren Gerätebestand zuordnen

**Oberfläche:** Windows, iPhone · **Rolle:** Gerätetester

**So geht es:** Nur mit ausdrücklich bereitgestelltem alten synthetischen Gerätebestand: Alte Offline-Aufträge prüfen → Gerätebestand prüfen, entsperren. Je nach Typ Ursprüngliche Annahme prüfen, Ursprüngliches Zeitereignis prüfen oder Ursprüngliches Protokoll prüfen. Historische Firma, Konto und Projekt mit der Quittung vergleichen.

**Daran erkennt ihr das Ergebnis:** Passender Treffer zeigt das bestätigte Original. Ohne eindeutige Bindung bleibt der Altauftrag ungeklärt erhalten. Der Abgleich startet keinen Timer und erzeugt kein Dokument.

**Gegenprobe / Besonderheit:** Ohne Altbestand als blockiert protokollieren. Keine Übernahme in eine andere Firma und keine vollständige Altbestandsmigration als bestanden werten.

<a id="kapitel-5"></a>

## Einkauf, Lager, Geräte und Service

Für die Mengenprüfung einen leeren Testlagerort und einen eigenen Lagerartikel mit 10,00 € Einstand verwenden. SYN-17 aus der Katalogübung hat einen anderen Einstand.

### 18 · Bestellvorschlag, Teil- und Restlieferung buchen

**Oberfläche:** Browser, Windows, iPhone · **Rolle:** Einkauf + Lager

**So geht es:** Unter Material einen Bedarf von drei Stück für das Projekt bei einem Testlieferanten erfassen. Bestellvorschlag prüfen und freigeben. Mit einer simulierten Bestellreferenz den Bestellstand dokumentieren; Wareneingang mit Musterschein zuerst zwei Stück, später ein Stück buchen. Jeweils Bestellhistorie und Bestand neu öffnen.

**Daran erkennt ihr das Ergebnis:** Nach der Teillieferung sind zwei Stück empfangen, eines offen. Nach der Restlieferung stehen drei Stück im Lager und null offen. Die Testreferenz und beide Eingangsbelege sind unterscheidbar.

**Gegenprobe / Besonderheit:** Eine Überlieferung versuchen. Sie wird abgewiesen. Bei Rücksendung oder Reststorno die ursprüngliche Position, Grund und Vorschau prüfen; bereits empfangene Mengen bleiben nachvollziehbar.

### 19 · Reservierung, Entnahme, Rückgabe und Inventur

**Oberfläche:** Browser, Windows, iPhone · **Rolle:** Lager + freigabeberechtigte Person

**So geht es:** Im Projekt Material vormerken/reservieren und verfügbare Menge prüfen. Zwei Stück aus Fall 18 auf das Projekt entnehmen. Unter Material zurückgeben die ursprüngliche Entnahme und das Ziellager wählen, ein Stück bestätigen. Danach für denselben Lagerort eine Inventur öffnen, ein Stück statt zwei zählen und Differenz mit Grund zur Freigabe vorlegen.

**Daran erkennt ihr das Ergebnis:** Nach Entnahme: 1 Stück Lager, 20 € Projektmaterial. Nach Rückgabe: 2 Stück Lager, 10 € Projektmaterial. Inventur: Soll 2, Ist 1. Erst nach Freigabe der Differenz steht der Bestand auf 1.

**Gegenprobe / Besonderheit:** Mehr als die Restmenge zurückzugeben wird gesperrt. Bei Antwortverlust Ursprüngliche Rückgabe erneut prüfen. Ändert sich der Lagerstand seit der Zählung, muss die Freigabe neu geprüft werden.

### 20 · Geräteherkunft, Wartungsvertrag und Betriebsmittel

**Oberfläche:** Browser, Windows, iPhone · **Rolle:** Serviceplanung + Lager

**So geht es:** Für ein separates Testgerät Original-Lieferschein in Fotos & Doku hinterlegen, Wareneingang und Entnahme passend erfassen. In Wartung → Lieferungen und Geräte (App: Anlagen) Seriennummer und Herkunft bestätigen. Vertrag und Besuch anlegen, Vertrag im Browser pausieren und wieder aktivieren. Separat ein Firmenwerkzeug unter Einsatzplanung → Betriebsmittel und Nachweise an einen Mitarbeiter ausgeben und mit Schadensvermerk zurücknehmen.

**Daran erkennt ihr das Ergebnis:** Die Kundenanlage zeigt Lieferschein, Seriennummer und Besuch. Während der Vertragspause entsteht kein weiterer planmäßiger Einsatz, alte Besuche bleiben sichtbar. Das Firmenwerkzeug hat eine eigene Übergabe- und Prüfhistorie.

**Gegenprobe / Besonderheit:** Doppelte Seriennummer/Herkunft oder zweite gleichzeitige Werkzeugausgabe prüfen. Defekt bzw. fehlende Freigabe muss in der Verfügbarkeit erkennbar sein.

### 21 · Reklamation disponieren, lösen und wieder öffnen

**Oberfläche:** Browser, Windows, iPhone · **Rolle:** Serviceleitung + Montage

**So geht es:** Unter Kundenservice eine Reklamation für den Musterkunden anlegen. Projekt, Gerät, Priorität, Zuständigkeit und Wiedervorlage setzen. Mit Serviceeinsatz disponieren einen freien Termin wählen. Unterzeichneten Bericht zuordnen, Lösung beschreiben und über Status und Lösung abschließen. Begründet wieder öffnen.

**Daran erkennt ihr das Ergebnis:** Serviceakte verbindet Kunden, Einsatz, Gerät und unterschriebenes Original. Frühere Lösung und Abschlussgrund bleiben nach der Wiedereröffnung sichtbar.

**Gegenprobe / Besonderheit:** Einen unpassenden Bericht aus einem anderen Projekt kontrollieren. Ein fremdes Projektoriginal darf nicht als passender Nachweis erscheinen.

<a id="kapitel-6"></a>

## Rechnung, Projektkosten und Buchhaltung

Die Zahlen der 119,00-€-Rechnung liefern eine durchgehende Kontrolle. Für Belegketten, Lohn und weitere Geschäftsfälle jeweils eigene Testoriginale verwenden.

### 22 · Rechnung ausstellen, Teilzahlung und Rest verbuchen

**Oberfläche:** Browser, Windows online, iPhone · **Rolle:** Büro + Buchhaltung

**So geht es:** Den angenommenen Auftrag aus Fall 08 in einen Rechnungsentwurf übernehmen. Käufer, Aussteller, Projekt, Leistungsangaben und Beträge prüfen. Im für Belegausstellung eingerichteten Testunternehmen ausstellen, Nummer notieren und PDF im zweiten Zugang öffnen. Im Testjournal zwei simulierte Zahlungen über 60,00 € und 59,00 € an unterschiedlichen Testreferenzen zuordnen.

**Daran erkennt ihr das Ergebnis:** Nummer und Original bleiben gleich. Der offene Posten sinkt von 119,00 € auf 59,00 €, anschließend auf 0,00 €. Das Ausstellen allein ist noch kein Zahlungseingang.

**Gegenprobe / Besonderheit:** Prüft vor einer Wiederholung den ursprünglichen Beleg. Lasst eine separate fällige Testrechnung offen, erstellt eine Mahnvorschau ohne Versand und vergleicht Restbetrag und Fälligkeit.

### 23 · Abschlag, Schlussrechnung und E-Rechnungsprüfung

**Oberfläche:** Browser, Windows online, iPhone · **Rolle:** Buchhaltung

**So geht es:** Mit separatem Testauftrag eine Abschlagsrechnung und belegte Anzahlung erfassen. In der Schlussrechnung die zugehörigen Vorbelege und Zahlungen auswählen. Anschließend eine begründete Belegkorrektur im vorgesehenen Belegfluss prüfen. Bei eingerichteten Validatoren XRechnung (UBL-XML) und ZUGFeRD EN 16931 (PDF mit eingebettetem XML) aus einem freigegebenen Testfall öffnen und Prüfergebnis festhalten.

**Daran erkennt ihr das Ergebnis:** Die Schlussrechnung rechnet die Vorbelege genau einmal an. Korrektur zeigt Bezug zum früheren Original. Nummer, Beträge und Parteien stimmen zwischen Anzeige, Archiv und elektronischem Beleg überein.

**Gegenprobe / Besonderheit:** Fehlende Pflichtangaben oder fehlender Prüfer dürfen nicht als bestandene Formatvalidierung gelten. Vergleicht strukturierten Inhalt und Prüfbericht, nicht nur die PDF-Ansicht.

### 24 · Projektbudget und tatsächliche Kosten auswerten

**Oberfläche:** Browser, Windows online, iPhone · **Rolle:** Projektleitung + Buchhaltung

**So geht es:** Unter Kalkulation → Projekt-Eingangsbelege ein separates Testoriginal prüfen, Netto + Steuer mit Brutto abgleichen und den Nettobetrag vollständig einordnen. Budget und freigegebenen Nachtrag erfassen. Quellen für genehmigte bewertete Arbeitszeit, Material aus Fall 19, Fremdleistung, sonstige Kosten, Rechnung und Zahlungen öffnen.

**Daran erkennt ihr das Ergebnis:** Nach Rückgabe aus Fall 19 beträgt der Materialanteil 10,00 €. Bei vollständig bezahltem Fall 22 sind Erlös netto 100,00 € und Zahlung brutto 119,00 € unterscheidbar. Fehlende Bewertung einer Zeit oder unvollständige Belegzuordnung ist erkennbar.

**Gegenprobe / Besonderheit:** Lagerbeschaffung, die schon über eine Entnahme ins Projekt einging, nicht nochmals als Projektaufwand einordnen. Drilldown und Übersicht mit dem Original vergleichen.

### 25 · Kontoauszug prüfen und mit Geldflüssen abgleichen

**Oberfläche:** Browser, Windows online, iPhone · **Rolle:** Buchhaltung

**So geht es:** Unter Finanzen → Bankabgleich ein synthetisches EUR-Geldkonto anbinden. Für bank.csv ein separates Beispielkonto und einen schon belegten Testzahlungseingang über 119,00 € verwenden; Zeitraum November 2026, Anfang 0,00 €, Ende 119,00 €, Semikolon. Vorschau und Vollständigkeit prüfen, bestätigen. Die Auszugszeile zuerst mit 100,00 €, danach insgesamt mit 119,00 € dem bestehenden Geldfluss zuordnen. Für das XML-Beispiel eigenes Testkonto und Oktober verwenden (Dateien im Testpaket).

**Daran erkennt ihr das Ergebnis:** Der ungeklärte Rest dieser CSV-Zeile sinkt von 19,00 € auf 0,00 €. Die Zuordnung erzeugt keinen zusätzlichen Geldfluss. Unter Kontoauszüge und Abgleich öffnen → Originalen XML-Auszug prüfen erscheinen beim XML Anfang 100 €, +125 €, −25 €, Ende 200 €. Nach getrennten Bestätigungen stimmt das heruntergeladene Original bytegenau mit der Eingabe überein.

**Gegenprobe / Besonderheit:** CSV erneut prüfen und separat falschen Endsaldo angeben. Erwartet werden Dubletten- bzw. Saldenhinweis ohne zweite Transaktion. Ein Monatsbericht mit offener Zuordnung bleibt als unvollständig erkennbar.

### 26 · Eigene EÜR, AfA, Perioden und Jahrespaket

**Oberfläche:** Browser, Windows online, iPhone · **Rolle:** Buchhaltung + Fachprüfer

**So geht es:** Finanzen → EÜR-Vorbereitung → Eigene EÜR öffnen (App: Eigene EÜR: Quellen bis Jahresausgabe). Geldflüsse vorbereiten, Beleganteile aus Fall 22 prüfen, steuerliche Einordnung vorschauen und festschreiben. Beim Eingangsbeleg Leistung, Rechnungseingang, Vorsteuerrecht und Zahlung gesondert prüfen. Mit eigenem Testanlagegut Basis, Nutzungsbeginn und lineare AfA kontrollieren. Einen vollständigen Testmonat schließen, Änderung begründet wieder öffnen und Jahresprüfpaket mit Originalen exportieren.

**Daran erkennt ihr das Ergebnis:** Zusammen ergeben die zwei vollständig zugeordneten Kundenzahlungen im Musterfall 100,00 € Erlös und 19,00 € vereinnahmte USt. Korrekturen erhalten Original und Gegenbuchung. Wieder geöffnete Perioden und neue Jahresfassung bleiben von der früheren Ausgabe unterscheidbar.

**Gegenprobe / Besonderheit:** Ungeklärte Quelle oder unvollständiger Kontoabgleich muss beim Abschluss sichtbar sein. Historische Geld-/Kassensalden, Anlagen und Altposten nur mit eigenen belegten Anfangswerten übernehmen. Unbekannt ist kein Nullsaldo. Das Jahrespaket ist kein Nachweis einer DATEV- oder Behördenübermittlung.

<a id="kapitel-7"></a>

## Personal, Reisen und Lohn 2026

Für private Unterlagen Testmitarbeiter A und B sowie eine prüfberechtigte dritte Person verwenden. Die Zahlen der Referenzfälle hängen am angegebenen Jahr und an allen Profilmerkmalen.

### 27 · Personalprofil, Abwesenheit und Monatsvorbereitung

**Oberfläche:** Browser, Windows online, iPhone · **Rolle:** Personalverwaltung + Mitarbeiter

**So geht es:** Browser: Personal → Mitarbeiterprofil anlegen; App: Personal → Mitarbeiter → Neu anlegen. Ein vorhandenes aktives Testkonto zuordnen, Arbeitsmodell, Beschäftigung und Gültigkeit mit synthetischen Unterlagen pflegen. Zeit aus Fall 13 und einen separat dokumentierten Urlaubs-/Abwesenheitstag prüfen. In der Personalakte die Monatsvorbereitung öffnen, Vorschau und fehlende Unterlagen prüfen, danach bestätigen.

**Daran erkennt ihr das Ergebnis:** Konto, Mitarbeiterprofil, Zeitkonto und fachliche Akte bleiben eindeutig zugeordnet. Abwesenheit erscheint im richtigen Zeitraum. Der Bezug zum freigegebenen Arbeitstag und die aktuelle Monatsfassung bleiben nachvollziehbar.

**Gegenprobe / Besonderheit:** Personalverwaltung nur mit Personalrechten testen. Sie kann ein zugelassenes aktives Konto für das Profil wählen, ohne die vollständige Benutzerverwaltung zu erhalten. Ein Lesekonto kann keine Profiländerung speichern.

### 28 · Reise, Auslage, Freigabe und Erstattung

**Oberfläche:** Browser, Windows online, iPhone · **Rolle:** Zwei Testmitarbeiter + unabhängiger Prüfer

**So geht es:** Unter Personal → Mitarbeiter → Personalakte, Reisen und Lohnvorbereitung → Reisen und Auslagen reicht A ein Musteroriginal über 49,87 € ein. B versucht dasselbe Original bytegleich. Der Prüfer gibt A frei und verwendet vor einer Erstattung Freigabe zurücknehmen mit Begründung. B reicht das freigegebene Original erneut ein. Separater Fall: Private Pkw-Kilometererstattung für dienstliche Inlandsfahrt im privaten Pkw mit Zeiten, Start, Ziel und Streckenoriginalen erfassen.

**Daran erkennt ihr das Ergebnis:** Doppeleinreichung innerhalb derselben Firma ist gesperrt, ohne fremde Privatdaten zu zeigen. Der Freigabeverlauf bleibt nach der Rücknahme sichtbar. Reiseanspruch, belegte Auszahlung und eventuelle Rückzahlung haben verschiedene Nachweise.

**Gegenprobe / Besonderheit:** Person A kann den eigenen Antrag nicht freigeben. Einen bereits erstatteten Antrag kann man nicht wie eine unbezahlte Freigabe zurücknehmen. Nach unklarer Antwort auf eine Zahlung zuerst Status des ursprünglichen Auftrags prüfen.

### 29 · Reguläre Lohnabrechnung mit Referenz vergleichen

**Oberfläche:** Browser, Windows online, iPhone · **Rolle:** Lohnfachprüfer

**So geht es:** Personalakte → Lohnberechnung 2026 öffnen. Den vorbereiteten Vollmonat Oktober 2026 und das Musterprofil aus payroll_workflow.json verwenden: 5.000 € brutto, Bundesland Hessen, StKl I, geb. 01.02.1990, pflichtversichert, keine Kinder, keine Kirchensteuer, KV-Zusatz 2,90 %, Monatsfreibetrag und Hinzurechnung je 0 €, Jahresbasis 60.000 €, U1 2,10 %, U2 0,44 %. Die gültigen Testoriginale für den vollen Monat auswählen. Vorschau mit upgraded_regular_preview vergleichen, dann Testfassung bestätigen.

**Daran erkennt ihr das Ergebnis:** Für genau diese Referenz: Lohnsteuer 782,41 €, Arbeitnehmer-SV 1.087,50 €, Netto 3.130,09 €. Historisches PDF und JSON stimmen mit der bestätigten Fassung überein. Reine SV-Vorschau lässt Steuer/Netto offen.

**Gegenprobe / Besonderheit:** Eine fehlende private Grundlage darf kein scheinbar endgültiges Netto liefern. Eine spätere Korrektur erzeugt eine nachvollziehbare neue Fassung. Mitarbeiteransicht zeigt nur die eigene freigegebene Abrechnung, keine fremden Steueroriginale.

### 30 · Gewerblichen Minijob und Sonderfälle prüfen

**Oberfläche:** Browser, Windows online, iPhone · **Rolle:** Lohnfachprüfer

**So geht es:** Mit eigener synthetischer Personalakte den Oktober-Vollmonat 2026 über 603,00 € erfassen, Arbeitgeber-Pauschsteuer wählen, RV-Pflicht belegen. Vorschau mit preview in payroll_workflow.json vergleichen. Separat gültige dokumentierte RV-Befreiung wie in corrected_preview prüfen. Für einen Änderungsfall Minijob-RV und Aufhebungsantrag prüfen öffnen und Verfahrensstand sowie wirksamen Zeitpunkt belegen.

**Daran erkennt ihr das Ergebnis:** Referenz RV-pflichtig: 581,29 € netto. Referenz mit wirksamer RV-Befreiung: 603,00 € netto. Ein offener RV-Verfahrensstand bleibt sichtbar und darf nicht als nachgewiesene Freistellung einfließen.

**Gegenprobe / Besonderheit:** Für Eintritt/Austritt, Krankheit, Feiertag, Urlaub, Einmalbezug, Midijob/Faktor und Teilmonat jeweils einen passenden Referenzdatensatz verwenden. Bei nicht belegten gleichzeitigen Fallgruppen Ergebnis offen lassen. Der Faktor-/Midijob-Teilmonat und geänderte RV-Nachweise besitzen eigene gerätespezifische Prüfreihen im Geräteprotokoll.

### 31 · Lohnkonto, Abführungen und Übergabe an die Buchhaltung

**Oberfläche:** Browser, Windows online, iPhone · **Rolle:** Lohn + Buchhaltung

**So geht es:** Lohnkonto, Monatsoriginal und Jahresübersicht öffnen. Im eigenen Testkonto die freigegebene Mitarbeiterabrechnung prüfen. Unter Belegte Lohnzahlungen eine simulierte, bereits erfolgte Teilauszahlung mit Datum, Betrag, Konto und Musterbeleg erfassen. Beiträge, Steuerabführung und Reisekostenzahlung mit getrennten Originalen prüfen. In EÜR-Vorbereitung die aggregierte Quelle öffnen.

**Daran erkennt ihr das Ergebnis:** Jahresübersicht kennzeichnet fehlende Monate, zählt je Monat die wirksame Fassung und bewahrt frühere Abrechnungen. Die Buchhaltung erkennt den belegten Geldfluss ohne private ELStAM- oder Personaldateien.

**Gegenprobe / Besonderheit:** Berechnung allein erzeugt keine Zahlung. Produktive ELStAM-Abrufe, Behördenmeldungen, Auszahlungen und unabhängige Lohnfreigabe separat als externe Abnahme führen.

<a id="kapitel-8"></a>

## Assistent, Sprache, Kommunikation und Regeln

Für diesen Abschnitt ein eigenes Testprojekt mit Aufgabe „Montage prüfen“ verwenden. Prüft interne Entwürfe und belegte Quellen. Echter Nachrichtenversand gehört nicht zum Teamlauf.

### 32 · Belegbare Antwort und interne Aktion prüfen

**Oberfläche:** Browser, Windows online, iPhone · **Rolle:** Projektleitung + Prüfer

**So geht es:** Unter Assistent das Testprojekt wählen. Aufgabe und Artikel suchen, die Quellen öffnen und ausdrücklich auswählen. Bei eingerichtetem Testanbieter die Frage „Wie heißt die ausgewählte Aufgabe?“ stellen und nur die freigegebene Weitergabe der Testdaten bestätigen. Einen internen Aufgabenentwurf vorbereiten und Quellen, Zuständigkeit sowie Parameter prüfen.

**Daran erkennt ihr das Ergebnis:** Antwort und Referenz stimmen mit dem geöffneten Original überein. Ein Entwurf ändert vor der vorgesehenen Freigabe keine Projektakte. Ohne Testanbieter ist der Online-Modellteil als blockiert zu erfassen, die Quellenansicht lässt sich separat prüfen.

**Gegenprobe / Besonderheit:** Mit eingeschränktem Konto wiederholen. Vertrauliche Inhalte, fremde Firma und nicht freigegebene Daten dürfen nicht als Quelle erscheinen. Ein Anweisungstext in einer fiktiven Kundenanfrage bleibt Dokumentinhalt.

### 33 · Automatik, Freigabe und Verbot unterscheiden

**Oberfläche:** Browser, Windows online, iPhone · **Rolle:** Regelverwaltung + Prüfer

**So geht es:** Im Testprojekt je eine versionierte Regel für eine unterstützte interne Aktion prüfen: Freigabe erforderlich, automatisch erlaubt und verboten. Pro Variante einen eigenen Vorgang verwenden. Bei Freigabe den konkreten Plan prüfen und genehmigen. Unter Assistent → Unternehmensereignisse öffnen die Unterlagen zum Ereignis lesen.

**Daran erkennt ihr das Ergebnis:** Bei Freigabe entsteht eine Aufgabe erst nach Bestätigung; bei erlaubter Automatik entsteht sie einmal; beim Verbot entsteht keine. Quellen, angewendete Regelversion, Zuständigkeit und Ergebnis stimmen.

**Gegenprobe / Besonderheit:** Vor der Freigabe die Berechtigung oder Testregel verändern. Beim Ausführen muss der aktuelle Stand geprüft werden. Wiederholung erzeugt keine zweite Aufgabe. Automatischen Mail- oder Zahlungsversand in diesem Test nicht aktivieren.

### 34 · Sprachentwurf aufnehmen und korrigieren

**Oberfläche:** Browser, Windows online, iPhone · **Rolle:** Gerätetester

**So geht es:** Bei eingerichtetem Testanbieter Sprache aufnehmen öffnen. Mikrofon erlauben, die Aufnahmetaste halten, „Prüfaufgabe für die Testfirma“ sprechen und loslassen. Ersten Durchgang abbrechen. Zweiten Durchgang zur erkennbar benannten Weitergabe bestätigen, Transkript ändern und Textentwurf übernehmen.

**Daran erkennt ihr das Ergebnis:** Abbruch beendet die Aufnahme. Übernommener Text bleibt bearbeitbar. Erst gesondertes Absenden stellt die Frage; es entsteht durch die Aufnahme kein Geschäftsvorgang.

**Gegenprobe / Besonderheit:** Mikrofonberechtigung einmal ablehnen bzw. die Aufnahmeansicht verlassen. Fehlt Testanbieter oder Mikrofon, das konkrete Hindernis festhalten.

<a id="kapitel-9"></a>

## Importe, Lieferanten und Bankverbindungen

Dateiverarbeitung ist ohne echte Zugangsdaten testbar. Für direkte Anbieterwege benötigt das Team eine ausdrücklich bereitgestellte Testverbindung.

### 35 · Kontakt und historische Bestände importieren

**Oberfläche:** Browser, Windows online, iPhone · **Rolle:** Datenverantwortlicher

**So geht es:** Unter Einstellungen → Kontrollierter Dateiimport ein Paket mit eindeutiger Testquelle und Quellkonto anlegen. kontakt.csv als UTF-8 mit Semikolon laden. Entität Kontakt (contact) wählen, quelle → source_id und anzeige → name zuordnen. Vorschau prüfen, bei neuer Quelle Neuanlage bewusst wählen und bestätigen. Bericht und Kontaktliste vergleichen.

**Daran erkennt ihr das Ergebnis:** Genau ein Kontakt „GrokBot Importkunde 001“ entsteht. Bei identischem Quellkonto und unveränderten Daten erkennt ein zweites Paket die bereits übernommene Quelle. Projekte über customer_source_id mit dem richtigen Kontakt verbinden; historische Rechnungen bleiben Archivoriginale.

**Gegenprobe / Besonderheit:** Eine Kopie mit leerer Quellkennung separat prüfen. Fehler oder ungeklärte Dublette muss vor der Übernahme erkennbar sein. Für echte HERO-/sevdesk-Exporte bleibt die formatspezifische Zuordnung erforderlich.

### 36 · Banken und externe Arbeitsdienste prüfen

**Oberfläche:** Browser, Windows online, iPhone · **Rolle:** Buchhaltung / Integrationsverwaltung

**So geht es:** Finanzen → Bankabgleich → Qonto-Umsatzänderungen lesen öffnen. Mit eingerichtetem Test-Lesezugang höchstens 31 Tage UTC-Änderungszeitraum wählen (Enddatum exklusiv); Status und Herkunft vergleichen. Bei fehlendem Zugang die Einrichtungsanzeige erfassen. Kreissparkasse Rottweil: separater camt.053-Dateitest nach Fall 25. Amex Business: vorhandene Testdatei bzw. Freigabe dokumentieren.

**Daran erkennt ihr das Ergebnis:** Qonto-Leseansicht erzeugt weder Zahlung noch Buchung. Ein erfolgreicher Dateiimport belegt die Verarbeitung genau dieses Formats. Bei den eingerichteten Testadaptern für Kalender, Dateien und Belege sind Auswahl, Projektbezug, Vorschau und Bestätigung nachvollziehbar.

**Gegenprobe / Besonderheit:** Google Kalender, OneDrive oder sevdesk nur bei freigegebener Testverbindung prüfen. Ohne Testzugang die Grenze protokollieren. Keine Fremdkonten anbinden oder bestehende echte Anbindungen trennen.

### 37 · Lieferantenwege und Posteingang abgrenzen

**Oberfläche:** Browser · **Rolle:** Einkauf / Büro

**So geht es:** Granzow, Alexander Bürkle, Loxone und Voltus als getrennte Anbieter protokollieren. Mit bereitgestellter Musterdatei Importweg, Artikel, Einheiten, Vorschau und Preisstand anhand Fall 07 prüfen. Separate Shop-/IDS-/Abruffunktion nur mit passendem Testvertrag testen. Bei eingerichtetem Testpostfach ausschließlich fiktive Anfragen/Anhänge öffnen, freigegebene Anhänge dem richtigen Kundenprojekt zuordnen und PDF-Vorschau mit dem Original vergleichen.

**Daran erkennt ihr das Ergebnis:** Die Oberfläche unterscheidet Quelldatei, Einrichtung und tatsächlichen externen Abruf. Ein Anhang erscheint nur für berechtigte Projektpersonen. Eine historische Übernahme sendet keine neue Anfrage.

**Gegenprobe / Besonderheit:** Die fehlenden direkten Anbieterabnahmen einzeln als blockiert führen. Die Loxone-Netzwerkfreigabe ist zurückgestellt. Ein CSV-Test oder ein sichtbarer Anbietername belegt keinen funktionierenden Live-Shop.

<a id="kapitel-10"></a>

## Datenschutz, Betrieb und Bedienbarkeit

Für Wiederherstellung und Firmenwechsel stellt der Betreiber eine isolierte Kopie bereit. Die installierte Smartplan-Instanz kann für die normalen Fachabläufe online bleiben.

### 38 · Datenschutzauskunft und Berichtigung

**Oberfläche:** Browser, Windows online, iPhone · **Rolle:** Datenschutzverantwortlicher

**So geht es:** In Einstellungen → Datenschutzfälle für den synthetischen Testkontakt Umfang, Prüfgrund, Verantwortlichen und Eingang erfassen. Identität im Testfall prüfen, Quellen einzeln zuordnen, Aufbewahrung und Daten Dritter beurteilen. Einen fremden Mustertext bei der Freigabe redigieren. Begründete Berichtigung durchführen, Historie öffnen und freigegebenen Export ansehen.

**Daran erkennt ihr das Ergebnis:** Solange die erforderlichen Prüfungen offen sind, ist der Export nicht freigegeben. Das freigegebene Paket enthält nur zugelassene Inhalte. Rechte und Berichtigung sind nachvollziehbar.

**Gegenprobe / Besonderheit:** Normales Mitarbeiterkonto darf die private Fallakte nicht lesen. Für die Bereinigung und deren Verhalten nach Restore nur eine Wegwerfkopie mit Testdaten verwenden.

### 39 · Unternehmensexport und geordnete Übergabe

**Oberfläche:** Browser, Windows online, iPhone · **Rolle:** Geschäftsführung + Betrieb

**So geht es:** Unter Einstellungen → Unternehmensübergabe die gebundene Testinstanz und das Inventar prüfen. Auslassungen kontrollieren, Grund und die geforderten Bestätigungen eingeben. Archiv herunterladen, Größe und SHA-256 mit den separat festgehaltenen Angaben vergleichen. Mitgelieferten Prüfer gemäß seiner README in der Testumgebung ausführen. Ausstiegsprüfung mit einem offenen Punkt speichern und neu öffnen.

**Daran erkennt ihr das Ergebnis:** Prüfergebnis, Originale, Quellen und fehlende Inhalte stimmen mit Inventar und Freigabe überein. Der offene Übergabepunkt bleibt offen. Das Exportieren löst keine Stilllegung aus.

**Gegenprobe / Besonderheit:** Ohne feste Testinstanzbindung den angezeigten Grund erfassen. Für einen Anspruch auf tatsächliche Fremdsystemübernahme ist ein eigener Import- und Abgleichnachweis erforderlich.

### 40 · Lokales Windows starten und sichern

**Oberfläche:** Windows lokal · **Rolle:** Windows-Betreuer

**So geht es:** Das vollständige Windows-Paket in einen eigenen Ordner entpacken. START_HIER.txt lesen, bei Bedarf bei geschlossener App Python_Umgebung_aktualisieren.cmd ausführen und Starten.cmd öffnen. In einem lokalen Testbestand ein Testprojekt mit signiertem PDF speichern. Bei geschlossener App Sicherung_erstellen.cmd nutzen; SQLite-Datei und zugehörige Prüfsumme gemeinsam aufbewahren. Späteren Testeintrag anlegen. In der dafür bereitgestellten lokalen Testkopie App/Starter schließen, Sicherung_wiederherstellen.cmd ausführen und neu anmelden.

**Daran erkennt ihr das Ergebnis:** Projektkennung und früheres PDF sind im ausgewählten Sicherungsstand vorhanden. Der erst später angelegte Testeintrag fehlt. Die lokale Datenbank ist von der gemeinsamen Onlineinstanz unterscheidbar.

**Gegenprobe / Besonderheit:** Online-Planimport und eigene Rechnungsausstellung mit dem Online-Client prüfen. Die lokale Windows-Sicherung ersetzt kein PostgreSQL-Serverbackup.

### 41 · Onlinebetrieb und Wiederherstellung abnehmen

**Oberfläche:** Browser + isolierte Serverkopie · **Rolle:** Betreiber + Fachprüfer

**So geht es:** Den dokumentierten Updatebeleg für 4bb5071 lesen und https://office.smartplan-hofmann.de/ready aufrufen. In einer vom Betreiber bereitgestellten separaten Restore-Umgebung die fachliche Stichprobe vor/nach Wiederherstellung vergleichen: Kunden- und Projektkennung, eine Zeitfreigabe, Originalplan/Foto, unterschriebenes PDF, Zahlungsquittung und Berechtigungen.

**Daran erkennt ihr das Ergebnis:** Der bestätigte Updatebeleg vom 24.11. nennt drei aktive Dienste und Server/Datenbank ok. Für den eigenen Restorefall stimmen die geprüften Kennungen, Originalbytes, Geldflüsse und Zugriffsgrenzen nach Wiederherstellung überein.

**Gegenprobe / Besonderheit:** Bei fehlender separater Kopie als blockiert erfassen. Restore, Zugangsschlüssel und Datenschutzjournal bleiben Betreiberaufgaben. Ein grünes /ready allein ist kein bestandener Restoretest.

### 42 · Bedienbarkeit, Rechtewechsel und Sitzungsende

**Oberfläche:** Browser, Windows, iPhone · **Rolle:** Alle Rollen

**So geht es:** Im Browser per Tastatur durch Kunde, Projekt, Zeit und Bericht navigieren, einen Dialog öffnen, Fokus und Schließen prüfen. Im schmalen Fenster und auf echtem iPhone Hoch-/Querformat, Touch, lesbare Meldungen und Signaturfläche benutzen. Je Client leere Liste, fehlendes Pflichtfeld, Speichern und erneutes Öffnen beobachten. Nach Test abmelden und eingeschränkten Zugang anmelden.

**Daran erkennt ihr das Ergebnis:** Fokus und nächste Aktion sind erkennbar. Fehler nennen betroffene Eingabe, lokale Speicherung und Synchronisation sind unterscheidbar. Das neue Konto sieht seine eigenen Inhalte; alte private Anzeigen verschwinden.

**Gegenprobe / Besonderheit:** Im zweiten Testunternehmen nur die normale Suche, Projektliste, berechtigte Dokumentansicht und Assistentenquellen prüfen. Fremde Testergebnisse bleiben getrennt. Eine unabhängige Fach-, Rechts- oder Sicherheitsprüfung wird durch diesen Bedienlauf nicht ersetzt.

<a id="abnahmen"></a>

## Durchgängige Abnahmen A–G

Verwendet für jede Abnahme eine Laufkennung, zusammengehörende Originale und die Kennungen aus den einzelnen Übungen. Macht bei Ausstattung oder Berechtigung fehlende Teilprüfungen kenntlich.

| Abnahme | Übungen | Beleg für den Abschluss |
| --- | --- | --- |
| A · Einrichtung und Rechte | 01, 03–04, 27, 38, 42 | Mitarbeiterbedarf, persönliche Rechte und Sichtbarkeit getrennt zeigen. Mit zwei Testfirmen und getrennten Sitzungen dieselbe Suche wiederholen. |
| B · Anfrage bis Zahlung | 05, 07–16, 18–19, 22, 24–26 | Eine Kunden-/Projekt-ID durch alle Belege verfolgen. Offlinezeit, Foto und PDF gegen zweite Sitzung prüfen; 119 € über zwei Zahlungen vollständig ausgleichen. |
| C · Einkauf bis Service | 18–21, 24 | Drei Stück erhalten, zwei entnehmen, eines zurückgeben. Geräteherkunft, Wartungsbesuch und Reklamationshistorie am Original abgleichen. |
| D · Personal und Abrechnung | 13–14, 27–31 | Arbeitszeit, Abwesenheit und Reise mit gültiger Beschäftigung abrechnen. Netto mit identischem Referenzprofil vergleichen. Historie, Jahresstand und Geldfluss prüfen. |
| E · Assistent und Regeln | 32–34, 42 | Berechtigte Quelle nennen, Entwurf prüfen und Freigabe, automatische interne Aktion und Verbot getrennt belegen. Bei Wiederholung auf genau einen Vorgang prüfen. |
| F · Betrieb und Wiederherstellung | 02, 15–17, 36–41 | Online- und lokale Installation unterscheiden. Restore nur in isolierter Kopie; Projektkennung, Originale, Rechte und Zahlungsquittung vergleichen. |
| G · Bedienbarkeit | 01–02, 10–16, 42 und GP-01–37 | Dieselben Tagesabläufe im Browser, auf Windows und einem echten iPhone einzeln bewerten. Auch Fokus, leere Ansichten, Konflikte und fehlende Rechte dokumentieren. |

<a id="testdaten"></a>

## Testdateien, Protokoll und Übergabe

- [kontakt.csv](testdaten/kontakt.csv) — Neutraler Kontaktimport (Fall 35). Semikolon, UTF-8. Quellkennung GB-C-001 auf source_id und Anzeigetext auf name abbilden.
- [katalog.csv](testdaten/katalog.csv) — Lieferantenkatalog V1 (Fall 07). Artikel SYN-17, Einstand 12,50 €, Verkauf netto 20,00 €, Steuer 19 %.
- [bank.csv](testdaten/bank.csv) — Musterkontoauszug November 2026 (Fall 25). Eine Zeile +119,00 €, Anfang 0,00 €, Ende 119,00 €. Zur Kontrolle einen eigenen Testgeldfluss mit gleichem Datum und Betrag vorbereiten.
- [bank-oktober.xml](testdaten/bank-oktober.xml) — Original aus der geprüften camt.053.001.08-Testfixture (Fall 25). Eigenes Musterkonto mit Test-IBAN DE89370400440532013000 im isolierten Unternehmen verwenden. Oktober 2026, Anfang 100 €, +125 €, −25 €, Ende 200 €. SHA-256 der unveränderten XML-Datei: 3590917fa5ea7386368dce11f68db18251a6daf91a8e40f4a59bebc576305524.

Muster für einen Fehlereintrag: GB-2411-T1 · Fall 13 · Browser · Rolle Montage A · Projekt <Test-ID> · Schritte: starten, pausieren, fortsetzen, stoppen, neu laden · Soll: eine Sitzung · Ist: <tatsächliche Anzahl und Dauer> · Nachweis: <bereinigter Screenshot/Belegkennung> · Wiederholung: <gleich/abweichend> · Status: <Ergebnis>. Für Abweichungen bei Geldbeträgen die Einzelposition und den Unterschied in Cent angeben.

Für die Übergabe alle Ergebnisse nach Rolle und Gerät zusammenführen, Fehlereinträge mit Fall-ID und Beleg verknüpfen, blockierte Anbieter-/Gerätefälle mit benötigtem Zugang benennen und den Verantwortlichen für den Nachtest eintragen. Für die sieben Gesamtabnahmen die Originalbelege entlang derselben Projektkette vergleichen. Eine bestandene Einzelübung genügt nicht als produktive Gesamtfreigabe.

## Bedienwege, Downloads und Referenzen

- [Smartplan Office im Browser](https://office.smartplan-hofmann.de/office/)
- [Windows für den Online-Test](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42968922844/artifacts/13832954008)
- [Windows mit lokalem Backend](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42968922844/artifacts/13833098535)
- [Bestätigter Serverstand und Pakete](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/blob/d645e70f0db5320c7ab4fdc05a98f4a87dae2251/docs/CRM_ERP_LIEFERSTAND_AKTUELL.md)
- [Geräteprotokoll mit 37 Detailfällen](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/blob/d645e70f0db5320c7ab4fdc05a98f4a87dae2251/docs/CRM_ERP_KUNDENTEST_PROTOKOLL_0_13.csv)
- [Bedienwege und vertiefende Lohnfälle](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/blob/d645e70f0db5320c7ab4fdc05a98f4a87dae2251/docs/CRM_ERP_BENUTZERHANDBUCH.md)
- [Anforderungsmatrix und offene Abnahmen](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/blob/d645e70f0db5320c7ab4fdc05a98f4a87dae2251/docs/CRM_ERP_ANFORDERUNGEN.md)
- [Referenzwerte für Lohn (JSON)](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/blob/d645e70f0db5320c7ab4fdc05a98f4a87dae2251/app/test/fixtures/payroll_workflow.json)
- [Bankauszugsformat und Zuordnungsregeln](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/blob/d645e70f0db5320c7ab4fdc05a98f4a87dae2251/docs/CRM_ERP_BANKABGLEICH_API.md)
- [Kontrollierter Dateiimport](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/blob/d645e70f0db5320c7ab4fdc05a98f4a87dae2251/docs/CRM_ERP_DATEIMIGRATION.md)
- [Betriebsverfahren für Sicherung und Restore](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/blob/d645e70f0db5320c7ab4fdc05a98f4a87dae2251/docs/BETRIEB_BUSINESS_UPDATE.md)
