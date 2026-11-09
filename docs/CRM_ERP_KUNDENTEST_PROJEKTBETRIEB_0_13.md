# Erster gemeinsamer Projekttest mit Version 0.13.0

**Einordnung vom 09.11.2026:** Die folgenden Server- und Paketnachweise beziehen
sich auf den tatsächlich bestätigten A93-Stand vom 05.11. Die neue gemeinsame
Entwicklung 8273852 ist inzwischen auf dem Testbranch veröffentlicht und wird
erneut geprüft; ihre Serverinstallation und Geräteabnahme sind noch nicht
bestätigt. Die neue Browserübernahme freigegebener Stunden, Meilensteine und
weitere Ergänzungen sind erst nach einem passenden kontrollierten Update
verfügbar. [Aktueller Stand](CRM_ERP_ARBEITSSTAND.md),
[Bedienung der neuen Zeitübernahme](CRM_ERP_BENUTZERHANDBUCH.md#zeiterfassung-finden-und-zeiten-abrechnen).

Ziel ist ein gemeinsames Testprojekt in Browser, Windows und iPhone: Kunde,
Angebot, Auftrag, Arbeitszeit, Dokumentation und Rechnung. Lohnabrechnung und
Buchhaltung gehören nicht zu dieser Testphase.

Der Serverupdate-Abschluss auf a93cb4d ist am 05.11.2026 tatsächlich bestätigt:
API, HTTPS und Planimport sowie Sicherungstimer aktiv, aktuelle Sandbox und
Prozess-/Datenbankbindung geprüft, Aktivierungsmarker entfernt.
[Servernachweis](evidence/project-update-forward-2026-11-05/observed-update-completion-success.json).
Der erste tatsächliche Bedienlauf kann jetzt in Browser und Windows beginnen.
Für iPhone fehlt weiterhin die signierte, installierbare Verteilung; der
unsignierte Prüfbuild ist keine installierbare App. Gerätefälle bleiben bis
zum tatsächlichen Durchlauf ungeprüft.

## Vor dem Termin

- Der bestätigte Serverstand ist a93cb4d vom 05.11.2026. Bei späteren
  Änderungen den tatsächlich installierten Quellstand erneut vergleichen.
- Ein getrenntes Testkonto und fiktive Kundendaten verwenden. Für Stunden ein
  aktives Mitarbeiterprofil mit Zugriff auf das Testprojekt einrichten.
- Windows: das tatsächlich gebaute Artefakt
  [Windows-Online-Paket 0.13.0](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/41944665296/artifacts/13379710379) vollständig in einen neuen Ordner
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
systemctl show smartplan-online.service smartplan-https.service smartplan-plan-import.service smartplan-online-backup.timer --property=Id --property=ActiveState --property=SubState
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
curl --fail --silent --show-error --max-time 15 https://office.smartplan-hofmann.de/ready
```

Die vorhandene Backend-Kompatibilitätskennung `0.12.0-online-pilot` und Schema 7
sind keine App-Buildnummer und belegen für sich kein aktuelles Serverupdate.
Der installierte Quellstand ist deshalb separat zu vergleichen. Ein git pull
allein ersetzt die laufende Serverkopie nicht. Die Erstinstallation und
Aktivierung der bestehenden Anlage werden nicht wiederholt; das spätere Update
verwendet den vorhandenen geprüften Ablauf für eine getrennte Datenbankkopie.
Die obigen Befehle lesen keine Passwörter, Token oder service.env-Datei.

## Bestätigter Serverstand am 05.11.2026

Installiert und kontrolliert abgeschlossen ist
`a93cb4d02eab610e5f2a8b07fbd1ee51ae99c3e5`. Dieser Stand passt zum oben
verlinkten tatsächlich gebauten Windows-Paket. Die früheren SSH-Ausgaben mit
6371da1e und die Quellvorbereitung sind im Serverupdate-Verlauf erhalten.
Sie sind kein aktueller Arbeitsauftrag. Für den Kundentest ist keine weitere
Serverumstellung nötig. Der Cloud-Assistent hat den Server nicht direkt bedient.

## Zeiterfassung finden und den eigenen Zugang zuordnen

Die Menünamen unterscheiden sich im aktuellen A93-Stand:

- Browser: Hauptmenü **Personal**, Überschrift **Personal & Zeiten**, Schaltfläche
  **Zeit starten**. Im Dialog **Zeiterfassung** das Projekt wählen und mit
  **Zeitereignis speichern** beginnen. Laufende Zeit später über
  **Laufende Zeit öffnen** pausieren oder beenden.
- Windows-App: Ein konkretes Projekt öffnen und dort **Arbeitszeit** wählen.
  Bei schmalem Fenster steht der Eintrag im Auswahlfeld **Projektbereich**;
  im breiten Fenster in der horizontalen Bereichsleiste.
- Fehlt im Browser **Zeit starten**, unter **Personal → Mitarbeiterprofil anlegen**
  das eigene angemeldete **Benutzerkonto** zuordnen und das Profil aktiv lassen.
  Ein vorhandenes Profil zuerst prüfen statt ein zweites anzulegen. Auch die
  Geschäftsführung benötigt für ihre eigenen Stempelzeiten eine solche Zuordnung.
  Mitarbeiterverwaltung setzt die passende Geschäftsführungs-/Personalberechtigung
  voraus; andere Benutzer können sich diese nicht selbst geben.

Fehlt bereits das gesamte Menü **Personal** oder der Projektbereich
**Arbeitszeit**, sind Unternehmensmodul, Sichtbarkeit und Berechtigung zu prüfen.
Das ist von einer fehlenden Mitarbeiterzuordnung zu unterscheiden. Ohne
tatsächliche Bildschirm-/Kontodaten wird keine dieser Ursachen für einen
konkreten Zugang behauptet. Die obigen Wege sind im vorhandenen Quellstand
nachgelesen, noch keine zusätzliche echte Geräteabnahme.

## Gemeinsame Bedienfolge

1. **Kunde und Projekt:** Im Browser einen Testkunden mit vollständiger
   Rechnungsadresse anlegen. Aus der Kundenkarte ein Projekt beginnen. In
   Windows dasselbe Projekt öffnen, nach signierter Verteilung auch auf dem
   iPhone. Kundenbezug und Adresse
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
5. **Zeit in Windows, später auf dem iPhone:** Das Projekt zunächst online öffnen und die
   vorgesehene Offline-Gerätefreigabe erteilen. Verbindung unterbrechen, Zeit
   aufnehmen und die App erneut öffnen. Nach Wiederverbindung muss der Vorgang
   genau einmal übertragen werden. Danach im Browser vergleichen. Den
   vollständigen Fall nach signierter Verteilung zusätzlich auf dem iPhone
   wiederholen; ein Windows-Erfolg gilt nicht als iPhone-Abnahme.
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
