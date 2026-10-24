# Bestehenden Mail-Bot an Smartplan anschließen

Dieses Paket verwendet den vorhandenen Anfrageeingang von Smartplan Office 0.9.
Ein Server- oder Appupdate und ein eigenes Apps-Script-Projekt sind dafür nicht
nötig. Ob dein bestehender Bot HTTP-Aktionen oder lokale Programme ausführen
kann, muss er selbst prüfen; dieses Paket bestätigt keine Anbieterfunktion.

## Für dich: drei Schritte

1. Übergib dem Bot dieses Paket und den vollständigen Inhalt von
   [BOT_AUFTRAG.md](BOT_AUFTRAG.md) als Auftrag. Die technische Schnittstelle steht
   in [openapi.json](openapi.json). Der Bot prüft zuerst seine vorhandene
   Mailanbindung und die nötige HTTP- oder Programmausführung. Er soll eine
   fehlende Fähigkeit konkret melden, bevor ein Zugangsschlüssel benötigt wird.
2. Ist ein Schlüssel bereits sicher hinterlegt, lass zuerst die vorhandene
   geschützte Bindung an `office.smartplan-hofmann.de` prüfen, ohne den Wert
   anzuzeigen oder blind erneut zu kopieren. Falls noch kein Zugang eingerichtet
   ist: Öffne in der Online-App als Geschäftsführung **Anfragen → Gmail einrichten**.
   Trage beispielsweise **Mail-Bot** als Bezeichnung und die tatsächliche
   Gmail-Adresse des bereits verbundenen Postfachs ein. Wähle
   **Eingangsschlüssel erstellen → Schlüssel kopieren**. Hinterlege ihn
   ausschließlich im geschützten Zugangsdatenfeld des Bots; bei lokaler Ausführung
   heißt die Umgebungsvariable `SMARTPLAN_INTAKE_TOKEN`. Den Schlüssel niemals in
   den Chat oder in den Arbeitsauftrag einfügen.
3. Lass nach bestätigter Bereitstellung dieser Bindung eine fiktive Testmail aus
   diesem Postfach über denselben festen Endpunkt übernehmen. Prüfe in Smartplan
   unter **Anfragen** Absender, Betreff und Text. Ein erneuter Botlauf mit derselben
   Mail darf keinen zweiten Eintrag erzeugen. Erst die bestätigte Übernahme zählt
   als Erfolg; danach kann der Bot die dafür freigegebenen Anfrage-Mails selbstständig
   einliefern. Die abschließende Kunden- und Projektzuordnung bleibt in Smartplan.

Unter **Gmail einrichten → Vorbereitete Postfächer** erscheint nach der ersten
bestätigten Übernahme **Nachrichtenübernahme bestätigt**. Ein erstellter Schlüssel
allein bestätigt noch keinen funktionierenden Botanschluss. Die in der App
erstellten Schlüssel sind 90 Tage gültig; dort sind Ablauf und
**Zugang widerrufen** sichtbar. Bereits gespeicherte Anfragen bleiben beim Widerruf
erhalten.

Eine Anzeige wie „Sicher hinterlegt, wird deinem Bot nie angezeigt“ kann bedeuten,
dass die Plattform den Wert absichtlich verbirgt. Sichtbare Masken, Platzhalter
oder deren Zeichenanzahl beweisen weder einen richtigen noch einen falschen
Schlüssel. Der sechsstellige Authenticator-Code dient der App-Anmeldung und ist
kein Eingangsschlüssel; aus einer maskierten Anzeige lässt sich diese Verwechslung
aber nicht ableiten. Der Bot soll die Secret-Metadaten und die tatsächliche
Authentifizierungsbindung prüfen, ohne den Wert offenzulegen. Erfolg belegt erst
die gültige `received`-Bestätigung mit HTTP `201`.

## Technischer Anschluss für den Bot

Der Auftrag in [BOT_AUFTRAG.md](BOT_AUFTRAG.md) ist direkt kopierbar und enthält
keine geheimen Zugangsdaten. [openapi.json](openapi.json) beschreibt die HTTP-Aktion.
Es gibt genau einen Zielendpunkt:

```text
POST https://office.smartplan-hofmann.de/api/v1/intake/gmail
Content-Type: application/json
Authorization: Bearer <Schlüssel aus dem geschützten Credential-Feld>
```

Bevorzugt setzt die native HTTPS-Aktion der Botplattform den Bearer-Header über
ihre geschützte Authentifizierungsbindung. Der Bot benötigt dafür keinen lesbaren
Klartext des Schlüssels. Der Name `SMARTPLAN_INTAKE_TOKEN` und das feste Ziel
`office.smartplan-hofmann.de` müssen zur vorgesehenen Secret-Referenz passen.
Ein sichtbarer Platzhalter darf nicht als Headerwert kopiert werden.

`source_account` ist das gebundene Empfängerpostfach, nicht die Absenderadresse.
`source_id` ist die unveränderte native Gmail-Nachrichten-ID. Der Eingang übernimmt
eine Nachricht als neue Anfrage; er gibt weder allgemeine Fach-API-Rechte noch
Kunden-, Projekt- oder Finanzabrufe frei. Passende Kunden werden innerhalb von
Smartplan vorgeschlagen.

Falls der Bot Programme ausführen kann, steht zusätzlich
[send_inquiry.py](send_inquiry.py) bereit. Aus dem entpackten Paketverzeichnis:

```bash
python3 send_inquiry.py --input anfrage.json --check
python3 send_inquiry.py --input anfrage.json --send
```

`--check` prüft die Eingabe ohne Netzwerk und ohne Schlüssel. `--send` liest den
zur Laufzeit sicher bereitgestellten Wert aus `SMARTPLAN_INTAKE_TOKEN`, nicht
eine im Chat sichtbare Maske. Alternativ ist
`--token-file /geschützter/pfad` zulässig; die Datei muss privat sein
(unter POSIX Modus `0600`) und darf kein Symlink sein. Der Schlüssel selbst ist
niemals ein Kommandozeilenargument. Die Datei `anfrage.json` enthält Maildaten
und gehört ebenfalls in den geschützten Arbeitsbereich des Bots.

Der Helfer hat keinen frei wählbaren Zielserver und wiederholt keine Übertragung
automatisch. Eine unbestätigte Eingabe bleibt mit identischer Mail-ID und
identischem Inhalt für den nächsten Botlauf erhalten. Ohne HTTP- oder
Programmausführung kann dieses Paket die Mailanbindung des unbekannten Anbieters
nicht ersetzen; der Bot muss das ausdrücklich melden.

HTTP `401` kann unter anderem eine fehlende Secret-Bindung, einen falschen Wert,
einen abgelaufenen oder widerrufenen Schlüssel bedeuten. Es beweist keine
bestimmte Ursache oder Schlüssellänge. Zuerst die sichere Bereitstellung prüfen;
den Schlüssel nicht zur Diagnose anzeigen oder ohne Befund ersetzen.
