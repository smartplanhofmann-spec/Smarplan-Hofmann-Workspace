# Erster gemeinsamer Projekttest mit Version 0.13.0

Ziel ist ein gemeinsames Testprojekt in Browser, Windows und iPhone: Kunde,
Angebot, Auftrag, Arbeitszeit, Dokumentation und Rechnung. Lohnabrechnung und
Buchhaltung gehören nicht zu dieser Testphase.

## Vor dem Termin

- Aktuellen Serverstand und Kompatibilität prüfen. Der zuletzt dokumentierte
  reale Serverstand vom 24.10. ist kein Nachweis des heutigen Betriebsstands.
- Ein getrenntes Testkonto und fiktive Kundendaten verwenden. Für Stunden ein
  aktives Mitarbeiterprofil mit Zugriff auf das Testprojekt einrichten.
- Windows: das tatsächlich gebaute Artefakt
  `Smartplan-Office-Windows-Online-Pilot` vollständig in einen neuen Ordner
  entpacken und `smartplan_office.exe` öffnen. Die angezeigte Version muss
  0.13.0 sein. Ein Quell-/Support-ZIP ersetzt dieses Programm nicht.
- Browser: `https://office.smartplan-hofmann.de/office/` öffnen.
- iPhone: die ausdrücklich bereitgestellte aktuelle TestFlight-Version
  installieren. Ein erfolgreicher unsignierter Prüfbuild lässt sich noch nicht
  wie eine fertige iPhone-App installieren. Die bisherige 0.5.1 ist kein Test
  der neuen Projekt-/Stundenfunktionen.
- Buildkennung und Quellstand sowie verwendete Geräte im Testprotokoll
  notieren. Alle drei Zugänge müssen dieselbe Unternehmensinstanz verwenden.

## Gemeinsame Bedienfolge

1. **Kunde und Projekt:** Im Browser einen Testkunden mit vollständiger
   Rechnungsadresse anlegen. Aus der Kundenkarte ein Projekt beginnen. In
   Windows und auf dem iPhone dasselbe Projekt öffnen. Kundenbezug und Adresse
   müssen übereinstimmen; in der Kundenliste darf keine Dublette entstehen.
2. **Angebot und Auftrag:** Eine Leistung mit Menge 1 und Nettopreis 100,00 EUR
   sowie 19 % Umsatzsteuer erfassen. Angebot prüfen: 19,00 EUR Steuer,
   119,00 EUR brutto. Die vorgesehene Annahme-/Auftragsfolge im selben Projekt
   durchgehen und das gespeicherte Dokument erneut öffnen.
3. **Projektmappe:** Aufgabe und Termin erfassen, einen Plan öffnen und
   bearbeiten, Foto oder Unterlage zuordnen. Die Daten in einem zweiten Zugang
   neu laden. Beim Verlassen eines ungespeicherten Plans muss die Rückfrage
   erscheinen; Abbrechen erhält die Bearbeitung.
4. **Zeit im Browser:** Zugeordnete Zeit starten, pausieren, fortsetzen und
   stoppen. Projektbezug und Dauer prüfen. Den angezeigten Arbeitstag bewusst
   freigeben; eine begründete Korrektur muss Original und Historie erhalten.
5. **Zeit auf dem iPhone:** Das Projekt zunächst online öffnen und die
   vorgesehene Offline-Gerätefreigabe erteilen. Verbindung unterbrechen, Zeit
   aufnehmen und die App erneut öffnen. Nach Wiederverbindung muss der Vorgang
   genau einmal übertragen werden. Danach im Browser vergleichen.
6. **Dokumentation:** Einen Testbericht mit Foto und Testunterschrift speichern.
   Das gespeicherte Original erneut öffnen und exportieren. Die Projektkennung
   und der unterschriebene Inhalt müssen erhalten bleiben.
7. **Rechnung:** Rechnungsentwurf im selben Projekt erstellen. Empfänger,
   Positionen und Gesamtbetrag prüfen. Tatsächliche Ausstellung und Nummernkreis
   ausschließlich im dafür eingerichteten Testbetrieb prüfen; im bestehenden
   Betrieb ist dafür die bewusste Ausstellerumstellung erforderlich. Das
   archivierte PDF muss anschließend in einem zweiten Zugang abrufbar sein.

## Ergebnis festhalten

Für jeden Schritt Gerät, Benutzerrolle, Uhrzeit, Projektkennung, erwartetes und
tatsächliches Ergebnis notieren. Bei einem Fehler die konkrete Aktion und die
angezeigte Meldung sichern. Eine unklare Antwort über den angebotenen
unveränderten Wiederholungsweg prüfen. Offene lokale Daten durch Entfernen der
App oder Löschen ihrer Daten nicht verlieren.

Die [ausfüllbare CSV-Vorlage](CRM_ERP_KUNDENTEST_PROTOKOLL_0_13.csv) enthält
20 noch ungeprüfte Gerätefälle für Browser, Windows und iPhone. Sie nutzt
Semikolonspalten und UTF-8 mit BOM zum Öffnen in deutschem Excel. Build und
Serverquellstand bleiben bis zum tatsächlichen Test leer; lokale/CI-Ergebnisse
werden dort nicht als Geräteabnahme eingetragen.

Die endgültige Abnahme erfolgt anhand dieser tatsächlichen Gerätefolge. Die
[lokalen Integrationsnachweise](CRM_ERP_PROJEKTBETRIEB_INTEGRATION_2026-11-04.md)
und [aktuellen Buildnachweise](CRM_ERP_PROJEKT_BUILD_FREIGABE_2026-11-04.md)
sind die Vorbereitung dafür.
