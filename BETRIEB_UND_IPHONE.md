# Nächste Stufe: gemeinsame Daten auf Windows und iPhone

Stand: 20. Oktober 2026. Vorbereitung, keine Buchung oder erfolgte Bereitstellung.

## Ausgangslage und Ziel

Die Windows-App, Starter, Sicherung und Wiederherstellung sind auf dem Nutzer-PC
geprüft. Es gibt noch keinen eigenen Server und kein Hosting. Der Nutzer hat
Windows und ein iPhone; ein Mac ist nicht vorhanden. Der aktuelle iOS-Simulator-
Build läuft auf dem macOS-Rechner der GitHub-CI.

Ziel der nächsten Stufe ist eine gemeinsame Testdatenbasis: Ein in Windows
angelegtes Projekt kann auf einem berechtigten iPhone geöffnet und ein dort
erstellter Bericht anschließend unter Windows gelesen werden. Für diesen
ersten Test werden fiktive Daten verwendet; die Übernahme des echten Windows-
Datenbestands erfolgt erst nach einem getrennt geprüften Migrationslauf.

## Empfohlener Betriebsweg

Ein kleiner verwalteter Betrieb mit EU-Datenstandort, eigener HTTPS-Adresse,
PostgreSQL, dauerhaftem Speicher und getrennten Sicherungen. Das passt zu einem
Nutzer ohne vorhandene Serververwaltung. Die konkrete Anbieterwahl bleibt offen,
bis monatlicher Kostenrahmen, Nutzerzahl und notwendige Vertragsanforderungen
bekannt sind. Preis und enthaltene Leistungen müssen vor einer Buchung anhand
des aktuellen Angebots geprüft werden. Es liegt noch kein geprüftes Angebot vor.

Das bestehende Microsoft-365-Family-Konto bleibt als Dokumentablage vorgesehen.
Die gemeinsame Datenbank wird durch das Backend verwaltet. Ein OneDrive-App-Ordner
stellt weder die gemeinsame Datenbank noch deren vollständige Sicherung bereit.

## Lieferpakete vor der ersten Bereitstellung

| Paket | Konkretes Ergebnis | Nachweis |
| --- | --- | --- |
| Produktions-API und Datenhaltung | Versionierte API, PostgreSQL-Schema, Migrationen und Transaktionen; bestehende Rechte bleiben pro Abruf wirksam | Die bisherigen Rechte-/Signaturfälle bestehen auch gegen PostgreSQL; parallele Änderungen verlieren keine bestätigten Daten |
| Datenübernahme | Werkzeug für eine überprüfte Kopie der lokalen Sicherung, einschließlich Konten, Projekten, Zuordnungen, Berichten und PDF-Bytes | Anzahl und Beziehungen stimmen; signierte PDFs sind byteidentisch; alte Sitzungen werden nicht übernommen; Quelldaten bleiben erhalten |
| Anmeldung und Konfiguration | Festgelegte Anmeldung mit MFA für den gemeinsamen Betrieb; sichere Bereitstellung von Schlüsseln; getrennte Testkonfiguration | Berechtigter Zugriff auf zwei Geräten; Rechteentzug und Sperrung greifen; kein Standardkonto oder Schlüssel im Repository |
| Betriebspaket | Start-/Releaseanweisungen, HTTPS, persistente Daten, Gesundheitsprüfung, geschützte Protokolle und Wiederanlauf | Neustart erhält Daten; Gesundheitsprüfung belegt Datenbankzugriff; unangemeldete Fachabrufe bleiben gesperrt |
| Online-Sicherung | Automatische Datenbanksicherung und Wiederherstellung an einem getrennten Ziel | Wiederherstellung in einer neuen Testinstanz mit identischen unterschriebenen PDF-Dateien |
| OneDrive Personal | Registrierte Microsoft-App, passende Callback-Adresse, geschützter Tokenspeicher und tatsächlicher Upload | Ein freigegebener unterschriebener Bericht ist im eigenen App-Ordner vorhanden; erneute Anmeldung und Fehler sind geprüft |
| iPhone-Testpaket | Eigene Bundle-ID, Signierung und gewählter Testverteilungsweg; HTTPS-Adresse als App-Konfiguration | Installation und kompletter Projekt-/Berichts-/PDF-Ablauf auf dem echten iPhone |

Die vorhandene `Office`-Klasse ist an SQLite gebunden. Für PostgreSQL müssen
insbesondere SQL-Platzhalter, Schema-/Schreiboperationen, Verbindungen und
Transaktionen angepasst werden. Eine neue Verbindungsadresse allein genügt nicht.
Der heutige Python-Standardbibliothekserver bleibt als lokaler Pilot verwendbar;
ein öffentlicher Betrieb erhält eine dafür geeignete API-Laufzeit.

## iPhone-Verteilung

Ein Simulator-Build ist keine installierbare iPhone-App. Mit dem vorhandenen
Windows-PC ist ein eigener lokaler Xcode-Build nicht möglich. Der vorhandene
macOS-CI-Build kann als technische Grundlage dienen; Zertifikate, Provisionierung,
eigene App-Kennung und die Apple-Verteilung müssen separat eingerichtet werden.
Für TestFlight oder eine reguläre Verteilung ist der passende Apple-Developer-
Zugang mit dessen aktuellen Bedingungen und Kosten zu prüfen. Ein Zugang wurde
bislang weder vorausgesetzt noch beantragt. Zertifikate und private Schlüssel
werden ausschließlich über geeignete sichere Einstellungen bereitgestellt.

Die reguläre Geräteabnahme erfolgt erst, wenn die App das gemeinsame HTTPS-
Backend erreichen kann. Die Adresse `127.0.0.1` der jetzigen Windows-App verweist
auf jedem Gerät auf dieses Gerät selbst.

## Noch benötigte Angaben

1. Monatlicher Planungsrahmen für Hosting sowie Zahl der ersten Nutzer und Geräte.
2. Vorhandene eigene Domain beziehungsweise administrativer Zugriff darauf;
   ein Anbieter-Testhostname kann für den ersten Test ausreichend sein.
3. Vorhandener Apple-Developer-Zugang und gewünschter erster iPhone-Testweg.
4. Zugang zur Microsoft-Appregistrierung für das bestehende Family-Konto.

Diese Angaben werden schrittweise geklärt. Der Kostenrahmen ist zuerst relevant.
Passwörter, Tokens, private Schlüssel und Zertifikate gehören nicht in den Chat.
Ohne konkrete Freigabe werden weder Hosting gebucht noch Apple-Mitgliedschaften
abgeschlossen oder Microsoft-Konten verbunden.

## Abnahme der nächsten Stufe

1. Windows meldet sich an der neuen Testadresse an und legt ein Projekt an.
2. Ein zugewiesener iPhone-Nutzer öffnet es; ein unberechtigter Nutzer erhält keinen Zugriff.
3. Der berechtigte Nutzer erstellt einen Bericht und zeichnet selbst eine Testunterschrift.
4. Windows öffnet das identische PDF; ein Entzug des Projektzugriffs sperrt weitere Abrufe.
5. Nach einem Neustart sind die Daten weiterhin vorhanden.
6. Eine getrennte Wiederherstellung und der reale OneDrive-Upload werden nachgewiesen.

Erst diese Nachweise bestätigen gemeinsamen Gerätebetrieb. Die weiteren Module
aus `UMSETZUNGSPLAN.md` bleiben davon getrennte Entwicklungsaufgaben.
