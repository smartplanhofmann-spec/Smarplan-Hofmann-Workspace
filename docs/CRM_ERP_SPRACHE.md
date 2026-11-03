# Sprache als bearbeitbarer Assistentenentwurf

Stand: 03.11.2026. Sprache ist eine ausdrücklich gestartete Eingabehilfe. Sie sendet keine Chatnachricht und führt keine fachliche Aktion aus. Unternehmensregeln, Quellenwahl, Datenweitergabe und die Freigabe konkreter Aktionen bleiben im [Assistentenablauf](CRM_ERP_ASSISTENT.md).

## Bedienung und Datenschutz

Bei eingerichteter Spracherkennung öffnet **Sprache aufnehmen** einen eigenen Dialog. Erst das Gedrückthalten der Aufnahmetaste beziehungsweise der Leertaste/Eingabetaste fordert die Mikrofonfreigabe an und startet eine Aufnahme. Loslassen beendet sie, spätestens nach 60 Sekunden. Für assistive Bedienung steht zusätzlich eine ausdrücklich auslösbare Start-/Stopp-Aktion mit derselben Zeitgrenze zur Verfügung. Wird während einer noch offenen Betriebssystemfreigabe losgelassen, startet eine später erteilte Berechtigung keine Aufnahme im Hintergrund.

Audio bleibt ausschließlich im Arbeitsspeicher. Der Browser verwendet `MediaRecorder`, prüft die Aufnahme lokal und normalisiert sie auf Mono-PCM16 mit 16 kHz. Die native App verwendet einen PCM-Stream; sie erzeugt keinen Dateipfad. Vor der Übertragung müssen Nutzer die Datenweitergabe an den angezeigten Sprachanbieter ausdrücklich bestätigen. Die Antwort erscheint als bearbeitbarer Textentwurf. Erst **Textentwurf übernehmen** übergibt sie an den Assistenten; das spätere Absenden der Frage ist eine gesonderte Aktion.

Abbruch, Schließen, Hintergrundwechsel, verlorene Quellenrechte und ein Sitzungswechsel stoppen die Aufnahme und verwerfen Audio beziehungsweise Entwurf. Laufende Netzwerkantworten einer verworfenen Ansicht werden nicht mehr angezeigt. Ein bereits ausdrücklich bestätigter Anbieteraufruf lässt sich nach seinem Start möglicherweise nicht zurückrufen.

Unbestätigte Sprachaufrufe werden niemals durch den gewöhnlichen Änderungs-Replay wiederholt. Die Oberfläche verwirft Audio nach dem einen Übertragungsversuch und bietet ausschließlich eine Abfrage des dokumentierten Status an. Der Server speichert weder Audio noch Transkript; deshalb kann ein verlorener Antworttext auch bei dokumentiertem Erfolg nicht nachträglich rekonstruiert werden. Ein neuer Versuch benötigt eine neue, ausdrücklich gestartete Aufnahme.

## Verifizierte Aufnahmebibliothek

`record` ist exakt auf Version **7.1.2** festgelegt. Der Paketvertrag bestätigt PCM16-Streaming über AVFoundation unter iOS und MediaFoundation unter Windows; beide sind die vorgesehenen nativen Ziele. Die aufgelösten Implementierungen stehen unverändert in `app/pubspec.lock` (`record_ios` 2.1.1, `record_windows` 2.3.0). Nur die acht neuen Pakete der record-Familie wurden ergänzt. Die iOS-Mikrofonbeschreibung erklärt Aufnahme und separate Übertragungsbestätigung; Hintergrund-Audio wurde nicht aktiviert.

Referenz: [record 7.1.2 auf pub.dev](https://pub.dev/packages/record/versions/7.1.2), Paket-README und Quellvertrag `AudioRecorder.startStream`, `RecordConfig`, `setOnConfigChanged`. Eine von der Plattform abweichend gelieferte Samplerate oder Kanalzahl führt zum Abbruch; unbestätigte Daten werden nicht als korrektes WAV deklariert.

## Konfiguration des Betriebs

Die folgenden Werte werden ausschließlich auf dem Server eingerichtet. Kein API-Schlüssel gelangt an Browser oder App. Das Installieren des Moduls aktiviert keinen Anbieter.

| Variable | Erforderlicher Inhalt |
| --- | --- |
| `SMARTPLAN_ASSISTANT_SPEECH_ENABLED` | `1` nach ausdrücklicher Einrichtung |
| `SMARTPLAN_ASSISTANT_SPEECH_DATA_TRANSFER_APPROVED` | `1` nach Freigabe des konkreten Anbieters und der Datenweitergabe |
| `SMARTPLAN_ASSISTANT_SPEECH_INSTANCE_ID` | Kennung genau dieser Unternehmensinstanz |
| `SMARTPLAN_ASSISTANT_SPEECH_ENDPOINT` | Freigegebener HTTPS-Endpunkt mit dem exakten Pfad `/v1/audio/transcriptions` |
| `SMARTPLAN_ASSISTANT_SPEECH_MODEL` | Tatsächlich beim gewählten Anbieter freigegebene Modellkennung |
| `SMARTPLAN_ASSISTANT_SPEECH_API_KEY` | Geschützter serverseitiger Schlüssel |

Der geprüfte HTTP-Vertrag stammt aus dem [offiziellen OpenAI-Python-SDK, Audio-Transcriptions-Ressource](https://github.com/openai/openai-python/blob/main/src/openai/resources/audio/transcriptions.py): Multipart-POST mit `file`, `model`, `language=de` und `response_format=json`, Antwortfeld `text`. Es wird keine konkrete verfügbare Modellkennung erfunden. Ein kompatibler Anbieter muss diesen Vertrag tatsächlich unterstützen.

Die separate Sprachanbindung prüft Unternehmensbindung, explizite Anbieterfreigabe, HTTPS/TLS, öffentliche Zieladressen, konfigurierte Proxyvorgaben, Antwortgröße und Zeitlimits. Redirects und automatische Anbieterwiederholungen werden nicht akzeptiert. Die Aufnahme muss kanonisches WAV mit 44-Byte-Kopf, einem Kanal, PCM16LE, 16 kHz und höchstens 1.920.044 Bytes sein. Die größere HTTP-Bodygrenze gilt ausschließlich für diesen Endpunkt; andere Fachendpunkte behalten ihre bisherige Grenze.

## API und Quittungen

- `GET /business/assistant/speech/status?project_id=...`: aktuelle Projektberechtigung, konkreter Konfigurationsbedarf oder freigegebener Anbieter und Aufnahmegrenzen.
- `POST /business/assistant/speech/transcribe`: ausschließlich `request_id`, `context_id`, `data_transfer_confirmed:true`, `audio_base64`. Der Server prüft aktuelle Quellen und Rechte vor und nach dem einen Anbieteraufruf.
- `GET /business/assistant/speech/requests/{request_id}`: nur eigene Metadaten unter aktuellen Kontextrechten. Kein Audio, kein Transkript, keine neue Anbieteranforderung.

Ein unveränderlicher Metadaten-Claim wird vor dem Anbieteraufruf gespeichert. Ein gesonderter unveränderlicher Abschluss protokolliert Erfolg, Fehlschlag oder Unterbrechung. Die ursprüngliche Kennung kann keinen zweiten Anbieteraufruf auslösen. Die Clientantwort muss Kennung, Projekt, Kontext und dessen Hash sowie die Kennzeichen `audio_persisted:false`, `transcript_persisted:false`, `retry_automatically:false` bestätigen.

## Abnahmegrenzen

Die lokalen Prüfungen verwenden synthetische Aufnahmen und einen ausdrücklich nur in der Testfixture eingesetzten Sprachtransport. Sie nehmen keine tatsächliche Spracherkennungsqualität, kein produktives Anbieterabonnement und keine Mikrofonaufnahme auf einem realen iPhone oder Windows-Gerät ab. Diese Zielgeräte- und Anbieterprüfung bleibt eine konkrete externe Abnahme. Ohne eingerichteten Anbieter bleibt die Texteingabe verfügbar und es wird keine Sprachfunktion vorgetäuscht.


## Clientnachweise vom 03.11.2026

- Flutter: **16/16** gezielte Tests für Sprache und Assistent, davon acht Sprachfälle. Nachgewiesen sind PCM/WAV-Grenzen, ausstehende Mikrofonfreigabe mit Abbruch, Freigabe vor Übertragung, bearbeitbarer Entwurf ohne Chatversand, maximale Aufnahmedauer, Rechte-/Hintergrundwechsel und ausschließlich lesender Statusabruf nach verlorener Antwort. Eine verspätete Antwort nach Hintergrundwechsel und Rückkehr kann den verworfenen Text nicht wiederherstellen.
- Browser-Vertrag: **17/17** Node-Tests für Sprache und Assistent, einschließlich Berechtigungsabbruch, Track-Freigabe, RAM-Löschung, hartem Zeitlimit, verspätetem Decodergebnis und strikter Antwortbindung.
- Echter Chromium-Ablauf: **1/1** mit aktivem Namespace-/PID-/Netzwerk-/Seccomp-Sandbox, synthetischem Mikrofon, echtem MediaRecorder, realem MFA/HTTP und ausschließlich testlokalem Sprachtransport. Getrennte Übertragungsbestätigung, manuelle Textbearbeitung, kein Chatversand, verlorene Antwort mit zwei reinen Statusabrufen, Escape und simuliertes Tab-Verbergen sowie fehlende Browserpersistenz sind geprüft. Die Testaufzeichnung speichert nur Kennungen, Hash und Größe; keine Audiodaten.
- `flutter analyze` für die beiden Clients und ihre Tests: **keine Befunde**. Desktopansicht des bearbeitbaren Sprachentwurfs visuell geprüft.

Reproduzierbare Tests: `app/test/business_speech_test.dart`, `app/test/business_assistant_test.dart`, `web/office/tests/speech.test.mjs`, `web/office/tests/assistant.test.mjs` und `SMARTPLAN_BROWSER_WORKFLOW=speech node web/office/tests/e2e.cjs` mit den dokumentierten Testwerkzeugen. Lokale Protokolle: `work/verification/speech-flutter.log`, `speech-browser-contract.log`, `speech-analyze.log`, `speech-browser.log`; Screenshot und rein technische HTTP-Metadaten unter `work/verification/speech-browser-previews/`. Diese Arbeitsartefakte sind ignoriert; der geprüfte Umfang bleibt hier im Repository dokumentiert.

## Backend und Wiederherstellung

`business_assistant_speech.py` hält ausschließlich Metadaten in zwei eigenen, nur ergänzbaren Tabellen. Der Aufrufnachweis bindet Nutzer, Unternehmensinstanz, Projekt, freigegebenen Kontext samt Hash, Audiohash, Größe, Anbieterkennung und Zeitpunkt. Der Abschluss enthält ausschließlich Status, einen festen Fehlercode, die Information über einen möglichen Anbieteraufruf und den Zeitpunkt. Audio, Antworttext und API-Schlüssel stehen weder in diesen Tabellen noch im Audit oder im normalen Änderungsjournal. Ausgewählte Fachquellen werden nicht mit der Audioaufnahme an den Sprachanbieter übertragen.

Vor der Übertragung sowie vor Herausgabe des Texts werden aktuelle Identität, Quellenrechte, unveränderter Kontext, Anbieterfreigabe und Unternehmensbindung erneut geprüft. Auch ein Quellenrechteentzug bei weiterhin erlaubter Assistentennutzung verhindert die Antwort. Ein zwischenzeitlich abgeschlossener oder nach Wiederherstellung unterbrochener Aufruf kann keine verspätete Antwort mehr herausgeben.

Die Wiederherstellung ergänzt für einen offenen Aufruf genau einen Abschluss `interrupted`; vorhandene Abschlüsse und Aufrufnachweise bleiben unverändert. Es werden keine Audioübertragung und keine Rekonstruktion eines Texts gestartet. Die separate bestehende Freigabe nach einer Finanzwiederherstellung bleibt wirksam. Inventur-, Projekt- und Finanzdaten erhalten durch Sprachverarbeitung keine Fachbuchungen.

Backendnachweise vom 03.11.2026:

- **18/18** Domänen-, Anbietervertrags- und Online-HTTP-Tests: Metadaten statt Audio-/Textspeicherung, explizite Freigabe, fremde Projekte, aktuelle Rechte und Quellenstände, Anbieterwechsel/-entzug, wiederholte Kennung während einer laufenden Antwort, unbekannte Antwort, Unterbrechung und verspätete Antwort nach Wiederherstellung. Der Transport prüft Multipart, öffentliche Adressen, verpflichtenden Proxy auch bei `NO_PROXY=*`, Redirect-Verweigerung und begrenzte, eindeutige JSON-Antworten ausschließlich mit synthetischen Verbindungen.
- **1/1** echter lokaler HTTP-Test: vollständige 60-Sekunden-Aufnahme mit über 1 MB Nutzlast; ausschließlich der Sprachendpunkt erlaubt bis 2.600.000 Bytes. Übergröße, doppelte JSON-Schlüssel, nicht endliche Zahlen, Schreibfilter und GET-Anfragekörper werden abgelehnt. Dieser Test wurde zusätzlich mit den aktualisierten Abhängigkeiten `cryptography 50` und `Pillow 13` ausgeführt. Früh aus Headern erkennbare Fehler verwenden kleine Testkörper, damit ein vom Server vorzeitig geschlossener Socket die fachliche HTTP-Antwort nicht verdeckt.
- **1/1** echter PostgreSQL-Lauf mit aktualisierten Abhängigkeiten in **3,866 s**: Betreiberbindung an genau eine Unternehmensinstanz mit privatem Ablagemarker, echte MFA/HTTP-Verarbeitung einer vollständigen 60-Sekunden-Aufnahme, konkurrierender Wiederholungsversuch über eine zweite DB-Verbindung, eingeschränkte Laufzeitrechte und unveränderliche Datenbank-Guards. Nach Neustart bleibt jede Kennung gegen erneute Anbieteraufrufe gesperrt. Ein tatsächliches `pg_dump`/Restore in eine getrennte leere Testdatenbank widerruft alte Sitzungen und ergänzt beim offenen Aufruf `interrupted`. Vorhandene Abschlüsse, sämtliche Aufrufnachweise, Projekte, Rechnungsarchiv, Rechnungsnummern sowie Zahlungs- und Finanzquellen bleiben unverändert; erneute Sprachübertragung bleibt durch die bestehende Wiederherstellungsfreigabe gesperrt. Der Test prüft auch die vollständige Business-Integrität und Laufzeitsicherheit.

Reproduzierbar über `backend/test_business_assistant_speech.py`, `backend/online/test_assistant_speech_http.py`, `backend/test_business_assistant_speech_transport.py` und `backend/online/test_assistant_speech_pg.py`. Lokale Protokolle: `work/verification/assistant-speech-domain-http.log`, `assistant-speech-local-updated-deps.log` und `assistant-speech-pg.log`. Der PostgreSQL-Lauf setzt ausschließlich die vorhandene, streng geprüfte lokale Wegwerf-Testdatenbank voraus und nutzt keine Kunden- oder Produktivdaten.
