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

## Vorhandenen Serverstand lesen

Diese Befehle sind für die bestehende SSH-Konsole des Servers vorbereitet;
in dieser Cloud wurde damit kein Serverzugriff ausgeführt. Sie lesen nur
Dienststatus, ausgecheckten und tatsächlich installierten Quellstand sowie den
öffentlichen Zustandsendpunkt. Sie installieren, migrieren und starten nichts.

```bash
systemctl show smartplan-online.service smartplan-https.service --property=Id --property=ActiveState --property=SubState
git -C /opt/smartplan-test rev-parse HEAD
python3 - <<'PY'
from pathlib import Path
import re
try:
    value = Path('/opt/smartplan-online/SOURCE_COMMIT').read_text().strip()
except OSError:
    value = ''
print('Installierter Quellstand:', value if re.fullmatch('[0-9a-f]{40}', value) else 'nicht feststellbar')
PY
curl --fail --silent --show-error --max-time 15 https://office.smartplan-hofmann.de/health
```

Die vorhandene Backend-Kompatibilitätskennung `0.12.0-online-pilot` und Schema 7
sind keine App-Buildnummer und belegen für sich kein aktuelles Serverupdate.
Der installierte Quellstand ist deshalb separat zu vergleichen. Ein git pull
allein ersetzt die laufende Serverkopie nicht. Die Erstinstallation und
Aktivierung der bestehenden Anlage werden nicht wiederholt; das spätere Update
verwendet den vorhandenen geprüften Ablauf für eine getrennte Datenbankkopie.
Die obigen Befehle lesen keine Passwörter, Token oder service.env-Datei.

## Bestätigter Serverstand am 05.11.2026 und Quellvorbereitung

Die vom Nutzer übermittelten SSH-Ausgaben bestätigen Checkout und installierten
Stand `6371da1ec3641818b158ce3d3e132be674bc397e`, einen sauberen detached HEAD,
aktive API-/HTTPS-Dienste, Datenbank ok im Businessmodus und etwa 33 GB freien
Speicher. [Erfasster Status](evidence/project-browser-navigation-2026-11-05/server-observed-status.json).

Der bereits tatsächlich gebaute Folgequellstand ist
`a93cb4d02eab610e5f2a8b07fbd1ee51ae99c3e5`. Sämtliche Server-, Windows-,
iPhone-, Simulator-, Linux-App-, Update- und HTTPS-Jobs sind erfolgreich.
Der Browserjob hatte einen reproduzierten und lokal korrigierten Testhelfer-
Zeitablauf; eine grüne Remote-Gesamtprüfung wird nicht vorweggenommen.
Die einzige folgende Codeänderung betrifft diesen Helfer; Produktquellen
bleiben bytegleich. Diese Vorbereitung stellt ausschließlich den festen
Quellstand im Checkout bereit. Die separate installierte Serverkopie wird
durch den vorhandenen Updateablauf mit Sicherung, Kandidatendatenbank und
Wartungsfenster umgeschaltet.

Im bereits verbundenen SSH-Fenster:

```bash
cd /opt/smartplan-test &&
git fetch origin codex/testupdate-0.7-projects-20261104 &&
git switch --detach a93cb4d02eab610e5f2a8b07fbd1ee51ae99c3e5 &&
git status --short --branch
```

Bei diesem Stand verbleibt der Server bis zur ausdrücklichen koordinierten
Umschaltung auf seiner zuvor installierten Version. Vor einer Umschaltung
unbekannte lokale Änderungen oder einen fehlgeschlagenen Quellabruf zuerst
prüfen; keine Dateien blind verwerfen. Der Cloud-Assistent hat auf dem Server
keinen dieser Befehle selbst ausgeführt.

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
