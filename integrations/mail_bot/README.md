# Bestehenden Mail-Bot an Smartplan anschließen

Dieses Paket verbindet den vorhandenen Mail-Bot mit Smartplan. Der Mailtext-Eingang
ist seit Office 0.9 vorhanden. Für die neuen Originalanhänge ist das freigegebene
Serverupdate 0.10 mit Schema 5 und der Fähigkeit `mail_attachments` erforderlich;
dieses Paket installiert oder aktualisiert keinen Server. Ein eigenes
Apps-Script-Projekt ist nicht nötig. Ob dein bestehender Bot Originalanhänge lesen
und HTTP-Aktionen oder lokale Programme ausführen kann, muss er selbst prüfen;
dieses Paket bestätigt keine Anbieterfunktion.

## Für dich: drei Schritte

1. Übergib dem Bot dieses Paket und den vollständigen Inhalt von
   [BOT_AUFTRAG.md](BOT_AUFTRAG.md) als Auftrag. Die technische Schnittstelle steht
   in [openapi.json](openapi.json). Der Bot prüft zuerst seine vorhandene
   Mailanbindung einschließlich vollständiger Originalanhänge und die nötige
   HTTP- oder Programmausführung. Er soll eine
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
3. Lass nach bestätigter Bereitstellung dieser Bindung eine fiktive Testmail mit
   einem kleinen Anhang übernehmen. Prüfe in Smartplan unter **Anfragen** Absender,
   Text und Originaldatei. Erst Mailtext- und vollständige Anhangsquittung zusammen
   bestätigen die Verarbeitung. Ein erneuter Lauf darf weder eine zweite Anfrage
   noch doppelte Dateien anlegen. Danach kann der Bot passende Anfrage-Mails nach
   den vereinbarten Regeln selbstständig einliefern. Kunden-/Projektzuordnung und
   Übernahme eines Anhangs in die Planverarbeitung bleiben bewusste Schritte in
   Smartplan.

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
Authentifizierungsbindung prüfen, ohne den Wert offenzulegen. HTTP `201` mit
gültigem `received` bestätigt nur den Mailtext. Für Dateien ist zusätzlich die
vollständige `complete`-Anhangsquittung nötig.

## Technischer Anschluss für den Bot

Der Auftrag in [BOT_AUFTRAG.md](BOT_AUFTRAG.md) ist direkt kopierbar und enthält
keine geheimen Zugangsdaten. [openapi.json](openapi.json) beschreibt die HTTP-Aktion.
Der Zielhost ist fest; zuerst wird ausschließlich der Mailtext eingeliefert:

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

## Originalanhänge für den Bot

Nach dem Mailtext folgen drei zusätzliche Aktionen auf demselben HTTPS-Host:

```text
POST /api/v1/intake/gmail/attachments
PUT  /api/v1/intake/gmail/attachments/{id}/chunks/{index}
POST /api/v1/intake/gmail/attachments/{id}/complete
```

Der erste Aufruf kündigt die vollständige unveränderliche Dateiliste an und
liefert vorhandene Uploadabschnitte zurück. Originaldateien werden binär in
Abschnitten von 256 KiB übertragen; jeder Dateiabschluss prüft Größe und SHA256.
Danach wird dasselbe Gesamtmanifest erneut abgefragt. Erst `status: complete`
mit allen passenden Dateien und Zählern bestätigt den vollständigen Vorgang.
Bewusst gelöschte Anhänge bleiben gelöscht. `attachments: []` bestätigt nur eine
nach vollständiger Prüfung tatsächlich anhanglose Mail.

Grenzen: höchstens 30 Dateien, 20 MiB pro Datei, 60 MiB pro Mail und 2 GiB global
reservierter Anhangspeicher. Der Server begrenzt Anhangsoperationen auf 600 pro
Minute und Zugang. Bei Quoten- oder Verbindungsfehlern bleiben Originale und
Warteschlange erhalten; keine stillen Auslassungen und keine schnellen Retries.

Die Dateien gehen als Originalbytes aus der vorhandenen Gmail-Anbindung direkt
an Hetzner. Sie werden nicht in Chats, externe KI-Dienste, OCR-/Konvertierungsdienste
oder andere Ablagen übertragen. Der Bot führt keine Datei aus. Die geschützte
Planverarbeitung erfolgt erst nach ausdrücklicher Übernahme in Smartplan.

Bereits früher bestätigte Mailtexte können ihre Anhänge nachträglich erhalten:
gezielt dieselbe native Mail-ID und dasselbe Postfach verwenden. Den alten
Bearbeitungsstand nicht löschen und den Mailtext nicht erneut posten, um andere
Textnormalisierungen und Identitätskonflikte zu vermeiden. Fehlen Anhangbytes
oder native Anhang-IDs im Mailwerkzeug, muss der Bot das konkret melden.

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

Für Anhänge gibt es den separaten stdlib-Helfer [send_attachments.py](send_attachments.py):

```bash
python3 send_attachments.py --manifest anhaenge.json --check
python3 send_attachments.py --manifest anhaenge.json --send
```

Das private lokale Manifest enthält `source_account`, `source_id` und
`attachments: [{source_attachment_id, filename, media_type, path}]`. `path`
verweist auf die privat bereitgestellten Originaldateien und wird nie übertragen.
Relative Pfade gelten relativ zur Manifestdatei. Größe und SHA256 berechnet der
Helfer begrenzt aus den echten Dateien. Manifest und Originale müssen reguläre
private Dateien sein (unter POSIX nur für den eigenen Benutzer zugänglich);
Symlinks und Spezialdateien sind nicht erlaubt. `--check` arbeitet ohne Netz und
ohne Schlüssel. `--send` verwendet denselben geschützten Schlüsselkanal wie der
Texthelfer, setzt fehlende Abschnitte fort und verändert oder löscht keine Quellen.
Ein älterer Server ohne Anhang-API führt zu `pending`, nicht zu Erfolg.

Der Helfer hat keinen frei wählbaren Zielserver und wiederholt keine Übertragung
automatisch. Eine unbestätigte Eingabe bleibt mit identischer Mail-ID und
identischem Inhalt für den nächsten Botlauf erhalten. Ohne HTTP- oder
Programmausführung kann dieses Paket die Mailanbindung des unbekannten Anbieters
nicht ersetzen; der Bot muss das ausdrücklich melden.

HTTP `401` kann unter anderem eine fehlende Secret-Bindung, einen falschen Wert,
einen abgelaufenen oder widerrufenen Schlüssel bedeuten. Es beweist keine
bestimmte Ursache oder Schlüssellänge. Zuerst die sichere Bereitstellung prüfen;
den Schlüssel nicht zur Diagnose anzeigen oder ohne Befund ersetzen.
