# Betrieb und Abnahme des Projektpakets 0.12

Dieser Leitfaden beschreibt das vorbereitete Paket. Er bestätigt keine bereits
ausgeführte Installation auf `office.smartplan-hofmann.de`. Cloudprüfungen
verwenden ausschließlich synthetische Konten, Belege und Dateien. Der
[Umsetzungsbericht](BERICHT_HERO_UMSETZUNG.md) grenzt die tatsächlich umgesetzten
Funktionen von offenen Schnittstellen und Geräteabnahmen ab.

## Verbindung und Update

Unter Windows zuerst in PowerShell verbinden:

```powershell
ssh -i "$env:USERPROFILE\.ssh\smartplan_hetzner" root@office.smartplan-hofmann.de
```

Alle folgenden Linuxbefehle gehören in dieses SSH-Fenster. Vor einem Update
Quell-Commit und sauberen Checkout prüfen:

```bash
git -C /opt/smartplan-test status --short --branch
cat /opt/smartplan-online/SOURCE_COMMIT
systemctl is-active smartplan-online.service smartplan-https.service
```

Für die Installation ausschließlich den freigegebenen, vollständig geprüften
Commit verwenden. Keine wechselnde Branchspitze unbeaufsichtigt ausrollen.
Der vorhandene Ablauf `deploy/hetzner/online/update-online.sh` ist für den
bestehenden root-eigenen Checkout `/opt/smartplan-test` vorgesehen. Er verlangt
die bekannte Dienstkonfiguration und genau die bekannte alte oder neue
Caddydatei; unbekannte Anpassungen werden nicht überschrieben.

Der Ablauf erzeugt ein getrenntes Release mit `backend/` und `web/`, installiert
die gesperrten Pythonabhängigkeiten in eine neue virtuelle Umgebung und nimmt
unter gemeinsamer Updatesperre die Schreiber aus dem Dienst. Er bereitet eine
separate Kandidatendatenbank und eine geprüfte Sicherung vor. Der bestehende
Mailbot-Eingang wird in diesem Wartungsfenster durch die HTTPS-Wartungssperre
zurückgewiesen, sodass derselbe Auftrag später wiederholt werden kann.

Die Datenbankeigentümerschaft wird auf die nicht anmeldbare Migrationsrolle
`smartplan-migrator` übertragen. `smartplan-online` behält ausschließlich die
benötigten Laufzeitrechte. Der privilegierte Datenbankoperator arbeitet in
`/var/lib/smartplan-online-operator`, außerhalb des privaten Runtimeverzeichnisses.
Der Datenschutzschlüssel wird dem PostgreSQL-Benutzer nicht zugänglich gemacht.

Die Umschaltung erfolgt erst nach Migrations-, Integritäts-, Datenschutz- und
Bereitschaftsprüfung. Ein Abbruch vor der öffentlichen Freigabe verwendet die
geprüfte bisherige Konfiguration. **Nach öffentlicher Freigabe gibt es keinen
automatischen Rücksprung auf einen älteren Datenbestand:** neue Schreibvorgänge
müssen erhalten bleiben. Bei einem Abbruch das Updatejournal und
`UPDATE_IN_PROGRESS` auswerten; diese Datei nicht blind entfernen.

Nach erfolgreicher Installation:

```bash
systemctl is-active smartplan-online.service smartplan-https.service
curl --fail --silent --show-error --max-time 15 https://office.smartplan-hofmann.de/ready
```

Im Businessmodus meldet `/ready` nach dem [Korrekturpaket 0.12.2](APP_UPDATE_0_12_2.md) Version `0.12.2-online-pilot`, physisches Schema
`7` und `business_suite`. Ein bewusst beibehaltener Rückkehrmodus meldet weiterhin
Schema 7, aber `compatibility_mode: legacy` ohne aktive Business-Schreibfreigabe.
Bei unvollständiger Wiederherstellung ist die Bereitschaft gesperrt.

## Abbruch wegen Archivdateirechten

Die Meldung „Release darf nicht durch Gruppe oder andere Benutzer verändert werden“ wurde beim ersten 0.12-Update durch standardmäßig gruppenschreibbare Git-TAR-Dateirechte ausgelöst. Der [separate Server-Hotfix](HOTFIX_RELEASE_ARCHIVRECHTE.md) setzt die Git-Archivumask ausdrücklich und bindet den Export an den erfassten Commit. Für einen erneuten Versuch den geprüften Hotfix-Commit verwenden; die bestehende Rechteprüfung und erhaltene Sicherungen bleiben unverändert. Das Windows-Paket muss dafür nicht ersetzt werden.

## Abwärtskompatibilität und geänderte Rechte

Die Gmail-Routen, SPIN-Authentifizierung, Nachrichtendaten, Duplikatquittungen und
Anhangsübertragung behalten ihren Vertrag. Bestehende Mailbots benötigen für
diesen unveränderten Vertrag keinen neuen Payload. Der separate SPIX-Projektbot
für Sevdesk-, Kalender- und OneDrive-Metadaten bleibt getrennt.

Bewusste Rechteänderung: Unklassifizierte oder inzwischen veränderte übernommene
Mailoriginale und Projektlinks sieht zunächst nur die Geschäftsführung. Im
Projekt unter **Unterlagenfreigabe** die Originalfassung prüfen und freigeben.
Die Freigabe ist an den tatsächlichen Quellfingerabdruck gebunden. Ein veraltetes
Formular darf keine inzwischen geänderte Quelle freigeben. Angebots- und
Rechnungslinks bleiben mindestens finanziell geschützt; ihre Freigabe als
allgemeine Baustellenunterlage ist gesperrt.

Mitarbeiter benötigen Projektzuweisung und passende Fachrechte. Ein allgemeines
Recht hebt ein projektbezogenes Verbot nicht auf. Rechte werden bei Wiederholungen
und nach externer Verarbeitung erneut geprüft. Verborgene Register ersetzen
keine serverseitige Prüfung. Bereits bewusst als Plan freigegebene Kopien sind
eigenständige operative Unterlagen: Eine spätere Klassifikation des Mailoriginals
zieht diese frühere Planfreigabe nicht automatisch zurück.

## Migration, Rückkehrmodus und Wiederherstellung

Schema 7 ergänzt den bisherigen Datenbestand; Kunden-, Projekt-, Anfrage- und
Anhangskennungen bleiben erhalten. Änderungen erfolgen durch explizite
Installations-/Operatorpfade. HTTP-Anfragen führen keine Datenbank-DDL aus.
Modulversionen und Strukturprüfsummen verhindern stilles Übergehen abweichender
Definitionen. Ein fehlendes Modul wird nicht als unterstützte Funktion ausgegeben.

`down` setzt den aktiven Kompatibilitätsmodus auf `legacy`. Es löscht keine
Fachtabellen, finalen PDFs/XMLs, Nummernstände, Versandquittungen oder ausstehenden
Geräteaufträge. Berechtigte Archivabrufe bleiben möglich. Neue Businessbefehle
und externer Versand bleiben gesperrt, bis ein ausdrückliches `up` erfolgt.
Die physische Storageversion wird nicht auf 6 zurückgesetzt.

Bei einer echten Wiederherstellung aus einer Sicherung gilt zusätzlich:

1. Sitzungen und gefährdete externe Verbindungen werden nach dem vorhandenen
   Restorevertrag zurückgesetzt. Ein unbestätigter Versand gilt als **unklar**,
   niemals automatisch als sicher ungesendet.
2. Der restaurierte Bestand bleibt zunächst gesperrt. Der Runtimebenutzer muss
   mit seinem unabhängigen Datenschutzjournal zwischenzeitliche Löschungen
   erneut anwenden. Ein älteres Backup darf freigegebene Standortdaten oder
   anonymisierte Kontakte nicht wieder offenlegen.
3. Danach bleiben eigene Belegausgabe und Versand gesperrt, bis der privilegierte
   Operator Nummernstände, extern bereits ausgestellte Belege und Versandbelege
   mit einem dauerhaft aufbewahrten Prüfbericht abgeglichen hat. Die Freigabe
   erfasst Prüfer, Zeitpunkt und Berichtshash. Sie setzt keine Nummern zurück.

Eine Restoreprüfung ersetzt keinen fachlichen Abgleich des Sicherungshorizonts.
Root-/Datenbankadministration, Sicherungsaufbewahrung und Nachweise gehören in
die betriebliche Verfahrensdokumentation.

## Unabhängiges Datenschutzjournal

Das Update richtet ein privates, HMAC-geschütztes Journal unter der Identität
`smartplan-online` ein. Die drei Bindungen heißen:

- `SMARTPLAN_PRIVACY_CHECKPOINT_FILE`
- `SMARTPLAN_PRIVACY_CHECKPOINT_KEY_FILE`
- `SMARTPLAN_PRIVACY_INSTALLATION_ID`

Bestehende Bindungen werden geprüft und erhalten. Ein fehlendes Journal bei
bereits vorhandenen Löschankern darf nicht durch ein neues leeres ersetzt werden.
Ohne korrekte Bindung verweigert der Dienst destruktive Kontaktanonymisierung
und Standortfreigabe; es wird kein falscher Löschabschluss gemeldet.
Journal und Schlüssel getrennt vom Datenbankbackup aktuell sichern und im
Wiederherstellungsverfahren berücksichtigen. Sie enthalten keine Klartextkoordinaten.
Die Initialisierung ist ein expliziter Operatorvorgang; kein Browser legt Schlüssel an.

## Eigene Belege und Sevdesk

Die zusätzlichen Funktionen werden nach Anmeldung über die Metadatenliste
`features` angeboten: `billing_contact`, `quote_pricing`, `measurement_transfer`
und `project_timeline`. Das sind Funktionsnachweise, keine Benutzerrechte.
Bei einem älteren Server ohne diese Angaben bleiben die bisherigen Arbeitsabläufe
nutzbar; die zusätzlichen Kontrollen werden nicht als bereits vorhanden ausgegeben.

Im Belegeditor übernimmt ein neuer Entwurf die passende strukturierte
Rechnungsanschrift des Projekts. Bei mehreren Rechnungsadressen ist eine Auswahl
erforderlich. Ein Ansprechpartner wird nur aus eindeutigem Rechnungsbezug oder
bewusster Auswahl übernommen. Freitext wird nicht in eine erfundene PLZ/einen
Ort zerlegt. Bestehende oder manuell bearbeitete Beleganschriften werden nicht
durch spätere CRM-Antworten überschrieben.

**Position kalkulieren** berechnet Material-/Leistungsstückliste, Lohn,
Gemeinkosten und Aufschläge mit Decimalwerten. Der Preis wird erst durch eine
bewusste Übernahme zur Position. Bei unbekannten Kosten wird keine belastbare
Gewinn-/Margenaussage erzeugt. Ein projektbezogenes Finanzrecht erlaubt manuelle
Kalkulation; Livezugriffe auf den globalen Artikel-/Vorlagenkatalog benötigen
zusätzlich dessen globales Finanzleserecht.

Manuell bestätigte Aufmaßmengen können in den Entwurf übernommen werden. Projekt,
Version und Quellhash werden dabei geprüft. Eine veraltete Vorschau muss neu
geladen werden; bereits angenommene Angebotsstände werden nicht nachträglich
aus geändertem Aufmaß oder CRM neu berechnet.

Die Browserplanung bietet Woche, Monat, Jahr und zwei/drei Jahre. Die Balken
verwenden dieselben gespeicherten Projekttermine wie die Projektmappe. Fehlende
Datumswerte bleiben sichtbar ungeplant. Änderungen benötigen das aktuelle
Projektrecht und eine bestätigte Serverantwort. Die Jahresgrafik ist keine
automatische Abhängigkeits-/Kritischer-Pfad-Berechnung.

Sevdesk bleibt zunächst führend. Eigene Rechnungsstellung wird erst nach einem
dokumentierten Ausstellerwechsel aktiviert: Firmendaten, Steuerkennung,
Nummernkreise, Stichtag und Zuständigkeit ausdrücklich festlegen. Keine parallele
Rechnungsausgabe für denselben Auftrag in zwei Systemen.

Produktive eigene Rechnungen erfordern die tatsächlich geprüfte
PostgreSQL-Rollentrennung auf dem Online-Server. Das lokale SQLite-/Windowspaket
kann diese Grenze nicht nachweisen und darf eigene Rechnungsausgabe auch durch
importierte Einstellungen nicht öffnen. Synthetische SQLite-Finanztests verwenden
eine ausdrücklich im Testcode benannte Klasse; die Produktklasse besitzt keinen
ENV- oder HTTP-Testschalter.

Beim Festschreiben werden Positionen, Beträge, Quellen, Nummer und Artefakte
atomar gebunden. Ein Fehler verbraucht keine Ausgabenummer. Nachträgliches Ändern
ist gesperrt; eine Stornierung erzeugt einen eigenen, vollständig an das Original
gebundenen Beleg. Nachträge und Korrekturen erhalten eigene Fassungen.

**Die rechtliche GoBD-Konformität wird durch die technische Umsetzung nicht
bescheinigt. Verfahrensdokumentation, Aufbewahrung, Ausstellerwechsel und
betriebliche Anwendung müssen der Betrieb beziehungsweise Steuerberater prüfen.**
Eine gezeichnete Unterschrift ist eine einfache elektronische Unterschrift und
keine behauptete fortgeschrittene oder qualifizierte Signatur.

## E-Rechnung: lokale Werkzeuge explizit einrichten

Es gibt keinen Download im HTTP-Festschreibungspfad. Ohne geprüfte Werkzeuge
verweigert der Server die betreffende Formatfreigabe, statt eine erfolgreiche
Validierung zu behaupten. Auf dem Server benötigt werden Java 21, Ghostscript
und ein sRGB-ICC-Profil. Nach Verbindung wie oben können sie durch den Operator
über die regulären Ubuntu-Pakete installiert werden:

```bash
apt-get update
apt-get install --yes openjdk-21-jre-headless ghostscript icc-profiles-free
python3 /opt/smartplan-test/scripts/fetch-einvoice-tools.py /opt/smartplan-invoice-tools
```

Das explizite Setup prüft feste SHA-256-Werte für KoSIT 1.6.3, die vollständige
XRechnung-3.0.2-Konfiguration vom 31.08.2026, Mustang 2.26.0 und veraPDF 1.30.3.
Manipulierte vorhandene Dateien werden nicht überschrieben oder ausgeführt.
Downloads und Entpackung sind begrenzt; Archivpfade und Symlinks werden geprüft.
Java/Ghostscript führen nur lokal erzeugte Rechnungsartefakte aus; fremde
Plan-PDFs werden nicht in diese Rechnungsstrecke gegeben.

Die vom Setup ausgegebenen absoluten Pfade in die root-eigene Dienstkonfiguration
übernehmen. Benötigte Variablen:

- `SMARTPLAN_KOSIT_JAVA=/usr/bin/java`
- `SMARTPLAN_KOSIT_JAR` und `SMARTPLAN_KOSIT_SCENARIOS`
- `SMARTPLAN_MUSTANG_JAR` und `SMARTPLAN_VERAPDF_JAR`
- `SMARTPLAN_GHOSTSCRIPT=/usr/bin/gs`
- `SMARTPLAN_SRGB_ICC=/usr/share/color/icc/ghostscript/srgb.icc`

Die Dateirechte müssen der Runtime Lesen/Ausführen erlauben, aber kein Ändern.
Die Software prüft die Tool- und Konfigurationshashes auch bei der Nutzung.
KoSIT-Akzeptanz, eingebettetes Original-XML sowie echte Mustang- und
veraPDF-Prüfberichte sind Voraussetzung der jeweiligen Freigabe. Eine normale
PDF-Datei wird nicht als PDF/A oder ZUGFeRD bezeichnet.

Bezugsquellen und Prüfsummen stehen im
[Setupskript](../scripts/fetch-einvoice-tools.py). Die unveränderten Originalpakete
enthalten ihre eigenen Hinweise/Lizenzen einschließlich Drittkomponenten;
[KoSIT](https://github.com/itplr-kosit/validator),
[XRechnung-Konfiguration](https://github.com/itplr-kosit/validator-configuration-xrechnung),
[Mustang](https://github.com/ZUGFeRD/mustangproject) und
[veraPDF](https://github.com/veraPDF/veraPDF-apps) sind externe Projekte.
JARs werden nicht in dieses Repository kopiert. Eine spätere Weiterverteilung
muss die jeweiligen Lizenz- und Hinweispflichten berücksichtigen.

## Versand, Mahnwesen und öffentliche Anfragen

SMTP ist standardmäßig aus. Zugangsdaten ausschließlich in der geschützten
Dienstkonfiguration beziehungsweise im Secret-Store ablegen:
`SMARTPLAN_SMTP_ENABLED=1`, `SMARTPLAN_SMTP_HOST`, `SMARTPLAN_SMTP_MODE`
(`ssl` Port 465 oder `starttls` Port 587), `SMARTPLAN_SMTP_USERNAME`,
`SMARTPLAN_SMTP_PASSWORD` und `SMARTPLAN_SMTP_FROM`.
Keine Passwörter oder Schlüssel in Chat, Repository, Screenshots oder Befehlsausgaben.

Mahnläufe benötigen eine manuelle Freigabe. Der Vorschlag beziehungsweise eine
PDF-Erzeugung ist noch kein Versandnachweis. Erst ein tatsächlicher SMTP-Ack
führt zum entsprechenden Übergabestatus; auch dieser bestätigt keine Zustellung
ins Empfängerpostfach. Unklare Ergebnisse werden vor Wiederholung abgeglichen.

Das öffentliche Formular liegt unter `/office/contact.html` und verwendet
`/api/v1/intake/contact`. Feste serverseitige Adapterbindung und zugelassene
HTTPS-Herkünfte konfigurieren, keine SPIN-/SPLD-Schlüssel im Browser:
`SMARTPLAN_CONTACT_ADAPTER_ID`, `SMARTPLAN_CONTACT_ALLOWED_ORIGINS` und die am
Adapter benannte geheime ENV-Referenz. Flags `external.website_leads` und
`external.website_form` sind zunächst aus. Die unveränderliche Antwortvorlage
benötigt Geschäftsführungsfreigabe; Antworten zusätzlich `external.lead_autoreply`
und einen kontrollierten Versandworker. Eine angenommene Anfrage mit
`reply_status: pending` bedeutet ausdrücklich keine versendete Antwort.

Für eigene Server-zu-Server-Einlieferung gibt es separat
`/api/v1/intake/leads/{adapter_id}` mit eigenem SPLD-Scope. Die bestehende
Gmail-/SPIN-API wird nicht als allgemeiner öffentlicher Leadschlüssel erweitert.
Granzow und Alexander Bürkle sind Lieferantenprofile. Ohne bestätigtes
Partnerprotokoll werden keine Bestellungen oder Preisabfragen ausgeführt.
DATEV-Prüf-CSV und Lexware-Mapping sind noch keine native EXTF-/Liveübergabe.

## Geräte und Offlineabnahme

Die neue native App benötigt eine ausdrückliche neue Gerätefreigabe für
`time_events` beziehungsweise `field_media`. Alte Plan-/Workspacezugänge erhalten
diese Rechte nicht automatisch. Die serverseitig gespeicherten Scopes und
aktuellen Projektrechte gelten auch beim Wiederholen.

Eigene Zeitereignisse und Fotooriginale mit Notizen werden vor Bestätigung
verschlüsselt dauerhaft gespeichert. Nach Wiederverbindung werden dieselben
Vorgangskennungen wiederholt; Konflikte bleiben zur Klärung erhalten.
Eine siebentägige Anmeldefrist ist keine Frist zur Löschung noch unübertragener
Daten. Appdaten nicht löschen und die App nicht deinstallieren, solange offene
Übertragungen angezeigt werden.

Die Browseroberfläche ist responsiv, aber keine PWA mit dauerhafter
Offlinewarteschlange. Sie hält die Sitzung ausschließlich im Arbeitsspeicher.
Androidgeräte können die Browseroberfläche nutzen; ein gebauter und freigegebener
nativer Androidclient ist in diesem Stand nicht enthalten.
Das vollständige lokale Windowspaket enthält `python-wheels` und einen
ausdrücklich zu startenden Offline-Updater `Python_Umgebung_aktualisieren.cmd`.
App und lokalen Server vorher schließen. Der Updater prüft die gesperrten
Windows-/Python-3.12-Wheels und installiert ohne Internet unter anderem `tzdata`.
Der normale Starter prüft die Zeitzonendaten vor dem Datenbankstart. Ein reines
Source-Support-ZIP ohne Wheels ersetzt dieses Paket nicht. Eine bestehende
0.11-Pythonumgebung wird nicht stillschweigend als vollständig ausgegeben.

Für die betriebliche Abnahme auf echten Geräten: Testprojekt öffnen, Flugmodus
aktivieren, Uhr starten/pausieren/stoppen, Foto mit Notiz aufnehmen, App schließen
und erneut öffnen, Verbindung herstellen und exakt eine Übernahme kontrollieren.
Einen zweiten Mitarbeiter ohne Finanzrecht sowie ein nicht zugewiesenes Projekt
mitprüfen. Diese Hardwareabnahme ersetzt keine Cloud- oder Widgetprüfung.
