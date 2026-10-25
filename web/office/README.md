# Smartplan Office im Browser

Die responsive Onlineoberfläche verwendet dieselbe authentifizierte `/api/v1`-API und denselben Projektbestand wie die nativen Clients. Einstieg: `/office/`. Zehn Hauptbereiche führen in die gemeinsame Projektmappe; Finanz-/Personalaktionen bleiben von eigenen Rechten abhängig. Die Oberfläche enthält keine fremden Skripte, Fonts, Tracker oder Kundendaten.

Passwort und MFA werden über die echte Onlineanmeldung geprüft. Bearer und unbestätigte Vorgänge bleiben ausschließlich im Arbeitsspeicher. Abmelden und Seitenwechsel aus dem Dokument löschen Sitzung und gerenderte Daten. Unklare Antworten können mit **derselben** Vorgangskennung ausdrücklich wiederholt werden; geänderte Inhalte ersetzen eine unbestätigte Operation nicht still. Die Browseroberfläche ist **keine PWA und besitzt keine dauerhafte Offlinewarteschlange**. Für dauerhafte Offlinearbeit bleibt die native App vorgesehen.

Fotooriginale werden in begrenzten, SHA-geprüften Blöcken hochgeladen. Galerievorschauen werden im Browser verkleinert, Originale getrennt heruntergeladen und Markierungen separat gespeichert. Die Galerie zeigt höchstens zwölf Dateien pro Seite. PDF-, Finanz- und Personaldateien unterliegen auch bei Metadaten und Wiederholungen der serverseitigen Klassifikation. Aufmaß nutzt manuell bestätigte metrische Werte; aus Fotos werden keine Maße erfunden. Eine gezeichnete Unterschrift ist keine qualifizierte elektronische Signatur.

## Lokale Prüfungen

```bash
npm ci --prefix web/office
npx --prefix web/office playwright install --with-deps chromium
node --test web/office/tests/client.test.mjs
SMARTPLAN_BROWSER_TEST_PYTHON=/pfad/zum/online-venv/bin/python SMARTPLAN_CHROMIUM_BINARY='' \
  node web/office/tests/e2e.cjs
```

Der Pythonruntime benötigt die bestehenden Backend-/Online-Lockabhängigkeiten. Playwright 1.62.1 ist im Lockfile gepinnt. Der Test selbst lädt keine Pakete nach. Ohne Browseroverride wird ein vorhandenes `/usr/bin/chromium` genutzt, sonst der installierte Playwrightbrowser; `SMARTPLAN_CHROMIUM_BINARY=''` wählt ausdrücklich den gepinnten Playwrightbrowser. Ein nichtleerer Override wählt einen konkreten Browserpfad. Optional: `SMARTPLAN_BROWSER_SCREENSHOT_DIR` für synthetische Prüfbilder. Der Test startet einen neuen privaten SQLite-Bestand auf Loopback und entfernt ihn samt Prozess nach dem Lauf. Die Prüfung verwendet echte Password-/MFA-/Recovery- und Fachrouten, keine injizierte Sitzung und keine Providerverbindung. Chromium läuft mit aktivierter Sandbox; Seitenanfragen an andere Origins werden abgewiesen.

Die reine Testtransporthülle bildet auf Loopback den HTTPS-Proxyvertrag nach. Dieser Funktionslauf ist **kein TLS-Nachweis**; die bestehende echte Caddy-/TLS-Suite bleibt zusätzlich erforderlich. Er prüft Anmeldung, alle zehn Bereiche, Kalenderumplanung per Formular und Drag-and-drop, Text-/Rechtegrenzen, Fotooriginal, Aufmaßsignatur/PDF, Abmelden, 390-Pixel-Darstellung und das öffentliche Formular nach verlorener Quittung. Backendtests prüfen zusätzlich Transaktionen, Concurrent-Reservierung, Finanzrechteentzug, SHA-/Signaturintegrität und Wartungskalender.

## Betriebsgrenzen

Die hier vorbereitete Oberfläche ist kein Beleg für ein Serverupdate, produktive Provideranbindung oder Geräteabnahme. Versandaufträge und Bestellvorschläge werden nicht als zugestellt behauptet. Der serverseitig gesperrte Ausstellerwechsel muss ausdrücklich konfiguriert werden; bestehende Sevdesk-Führung wird nicht durch einen Browseraufruf ersetzt. Erweiterte Formate und Freigaben sind nur nutzbar, wenn der Server sie tatsächlich aktiviert und bestätigt.

## Öffentliches Anfrageformular

`/office/contact.html` lädt ausschließlich `contact.js` und das gemeinsame Stylesheet, ohne Anmeldung oder Office-Bearer. Es sendet kurze Klartextanfragen mit stabiler `request_id`, Honeypot und Hinweisversion an `/api/v1/intake/contact`. Maximal 6.000 Nachrichtzeichen und ein zusätzlicher UTF-8-Byteguard passen unter das öffentliche 32-KiB-Limit. Ohne laufendes Skript bleibt der Submit gesperrt; ein Formularfallback verwendet POST, niemals personenbezogene Daten in einer GET-Adresse.

Die Annahme muss serverseitig mit einer festen Quelle, einem geschützten Schlüsselverweis, ausdrücklich bestätigten HTTPS-Origins und den entsprechenden Feature-Flags freigeschaltet werden. Das HTML enthält keinen Quellenschlüssel. Eine 201-Quittung bestätigt nur den Eingang; eine ausstehende Antwort wird ausdrücklich nicht als versendet oder zugestellt behauptet. Der kurze Formularhinweis ersetzt keine betriebliche Datenschutzprüfung.

Der öffentliche Chromiumfall verwendet einen synthetisch freigegebenen Adapter und eine genehmigte Antwortvorlage ohne SMTP-Transport. Er verliert absichtlich die erste bereits gespeicherte Quittung, wiederholt exakt dieselbe Anfrage und prüft einen einzigen echten Inboxeintrag mit weiterhin ausstehender Antwort. Dafür bildet ausschließlich die Testhülle die exakt passende HTTP-Loopback-Origin auf ihre Test-HTTPS-Origin ab. Produktive TLS- und Origin-Grenzen werden mit diesem Funktionsfall nicht abgenommen.
