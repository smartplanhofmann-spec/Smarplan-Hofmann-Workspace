# Bestehenden Mail-Bot an Smartplan anschließen

Dieses Paket verwendet den vorhandenen Anfrageeingang von Smartplan Office 0.9.
Ein Server- oder Appupdate und ein eigenes Apps-Script-Projekt sind dafür nicht
nötig. Ob dein bestehender Bot HTTP-Aktionen oder lokale Programme ausführen
kann, muss er selbst prüfen; dieses Paket bestätigt keine Anbieterfunktion.

## Für dich: drei Schritte

1. Öffne in der Online-App als Geschäftsführung **Anfragen → Gmail einrichten**.
   Trage beispielsweise **Mail-Bot** als Bezeichnung und die tatsächliche
   Gmail-Adresse des bereits verbundenen Postfachs ein. Wähle
   **Eingangsschlüssel erstellen → Schlüssel kopieren**. Hinterlege den Schlüssel
   ausschließlich im geschützten Zugangsdatenfeld des Bots; bei einer lokalen
   Ausführung heißt die Umgebungsvariable `SMARTPLAN_INTAKE_TOKEN`. Den Schlüssel
   niemals in den Chat oder in den Arbeitsauftrag einfügen.
2. Übergib dem Bot dieses Paket und den vollständigen Inhalt von
   [BOT_AUFTRAG.md](BOT_AUFTRAG.md) als Auftrag. Die technische Schnittstelle steht
   in [openapi.json](openapi.json). Der Bot soll seine vorhandene Mailanbindung
   verwenden und melden, falls ihm die nötige Ausführungsmöglichkeit fehlt.
3. Lass eine fiktive Testmail aus diesem Postfach übernehmen. Prüfe in Smartplan
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

## Technischer Anschluss für den Bot

Der Auftrag in [BOT_AUFTRAG.md](BOT_AUFTRAG.md) ist direkt kopierbar und enthält
keine geheimen Zugangsdaten. [openapi.json](openapi.json) beschreibt die HTTP-Aktion.
Es gibt genau einen Zielendpunkt:

```text
POST https://office.smartplan-hofmann.de/api/v1/intake/gmail
Content-Type: application/json
Authorization: Bearer <Schlüssel aus dem geschützten Credential-Feld>
```

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
Schlüssel aus `SMARTPLAN_INTAKE_TOKEN`. Alternativ ist
`--token-file /geschützter/pfad` zulässig; die Datei muss privat sein
(unter POSIX Modus `0600`) und darf kein Symlink sein. Der Schlüssel selbst ist
niemals ein Kommandozeilenargument. Die Datei `anfrage.json` enthält Maildaten
und gehört ebenfalls in den geschützten Arbeitsbereich des Bots.

Der Helfer hat keinen frei wählbaren Zielserver und wiederholt keine Übertragung
automatisch. Eine unbestätigte Eingabe bleibt mit identischer Mail-ID und
identischem Inhalt für den nächsten Botlauf erhalten. Ohne HTTP- oder
Programmausführung kann dieses Paket die Mailanbindung des unbekannten Anbieters
nicht ersetzen; der Bot muss das ausdrücklich melden.
