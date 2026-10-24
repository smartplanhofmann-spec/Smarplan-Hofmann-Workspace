# Gmail-Eingang vorbereiten

Dieser Anschluss ist vorbereitet und mit synthetischen Gmail-/HTTPS-Antworten
geprüft. Eine echte Google-Anmeldung, zeitgesteuerte Übernahme und Liveabnahme
sind noch offen. Es wurden keine Nutzerpostfächer verbunden. Google-/Workspace-
Vorgaben können eine Freigabe durch den Administrator verlangen.

1. In Gmail das Label **Smartplan-Anfragen** anlegen und eine fiktive Testmail
   damit versehen. Später kann ein eigener Gmail-Filter dieses Label zuweisen.
2. Im eigenen Google-Konto ein eigenständiges Apps-Script-Projekt erstellen.
   `SmartplanGmail.gs` übernehmen und im sichtbaren Projektmanifest die Datei
   `appsscript.json` verwenden. Der erweiterte Dienst **Gmail API v1** muss
   aktiviert sein. Eine eigene OAuth-Webanwendung oder ein Mailversand wird
   dafür nicht eingerichtet; die Google-Autorisierung des Skripts bleibt nötig.
3. In Smartplan als Geschäftsführung einen Gmail-Importtoken mit dem tatsächlichen
   Gmail-Postfach erstellen. Er wird nur einmal angezeigt. Nicht in Quellcode,
   Chats oder Ausführungsprotokolle kopieren. In den **Script Properties** setzen:

   | Eigenschaft | Wert |
   | --- | --- |
   | `SMARTPLAN_INTAKE_URL` | `https://office.smartplan-hofmann.de/api/v1/intake/gmail` |
   | `SMARTPLAN_IMPORT_TOKEN` | Einmal angezeigter `SPIN_…`-Importtoken |
   | `SMARTPLAN_SOURCE_ACCOUNT` | Primäre Gmail-Adresse des angemeldeten Kontos |
   | `SMARTPLAN_LABEL` | Optional; Standard `Smartplan-Anfragen` |
   | `SMARTPLAN_BATCH_SIZE` | Optional; 1–20, Standard 20 |

   Zugriff auf Skriptprojekt und Properties nur den verantwortlichen Personen geben.

4. `smartplanGmailImport` einmal manuell ausführen und die angezeigten **Readonly-
   Gmail-** und HTTPS-Berechtigungen prüfen/erteilen. Erst eine tatsächlich
   übernommene Nachricht setzt `SMARTPLAN_LAST_SUCCESS_AT` und serverseitig
   `last_used_at`. Ein erstellter Token allein bedeutet keine aktive Verbindung.
5. Die fiktive Nachricht in Smartplan kontrollieren: Postfach, Absender, Betreff,
   Text und Eingangszeit stimmen; es entsteht eine neue Anfrage ohne Auftrag,
   Kundenzuordnung oder Finanzaktion. Dieselbe Nachricht erneut ausführen:
   Es darf keine zweite Anfrage entstehen.
6. Erst danach im Apps-Script-Editor einen Zeittrigger für `smartplanGmailImport`
   anlegen, beispielsweise alle fünf Minuten. Trigger laufen im Konto ihres
   Erstellers. Es werden höchstens 20 Nachrichten pro Lauf bearbeitet.

Das Skript liest nur über das konfigurierte Label ausgewählte Nachrichten. Es
versendet, verschiebt oder verändert keine Mails und markiert sie nicht als gelesen.
Anhänge werden weder geladen noch übertragen. HTML wird nicht ausgeführt; bei
fehlendem Textteil steht ein ausdrücklicher Prüfhinweis in der Anfrage. Lange
Texte werden sichtbar gekürzt; das vollständige Original bleibt in Gmail.

Ein kleiner lokaler Cursor enthält nur Nachrichten-IDs und Fortschritt. Nach
verlorener HTTPS-Bestätigung wird wiederholt; Smartplan dedupliziert nach Gmail-
Postfach und Nachrichten-ID. Ein abgelaufener/widerrufener Token stoppt die
Übernahme. Unterbrochene Seiten werden fortgesetzt; danach beginnt ein neuer
Readonly-Durchlauf. Ausführungsprotokolle enthalten nur Zähler, keine Mailtexte
oder Tokens.

Bei verlorenem Token-Ausgabedialog die Verbindungenliste prüfen und den
unbekannten/neuen Zugang widerrufen. Zum Wechsel einen neuen Token desselben
Postfachs in den Script Properties setzen. Zum Abschalten Token in Smartplan
widerrufen und Zeittrigger im Google-Konto entfernen. Ein Rollenentzug oder eine
Deaktivierung des ausstellenden Owners sperrt seine Importtokens ebenfalls.

Das Backend benötigt seine Schema-4-Integration und die Intake-/Owner-Routen;
das Skript ist kein Ersatz für deren Bereitstellung. Gmail, Google Kalender,
WhatsApp Business, Dropbox und Sevdesk bleiben getrennte Anschlüsse.
