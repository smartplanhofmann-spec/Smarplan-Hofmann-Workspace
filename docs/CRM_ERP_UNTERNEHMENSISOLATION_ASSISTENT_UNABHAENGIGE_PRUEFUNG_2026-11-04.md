# Unabhängige Prüfung: Unternehmensgrenzen bei Suche, Assistent und Sprache

Prüfbaum: `/workspace/smartplan-company-isolation-20261104`, Basis `2e2ed5c`. Stand: 4. November 2026. Abschließend bestehen **21 eigene Prüfungen: drei tatsächliche Zwei-Prozess-HTTP-Fälle, sechs Browser-Vertragsfälle und zwölf native Fälle**. Die statische Analyse der eigenen Darttests meldet keine Probleme. Die sechs konkret gesicherten nativen Fehlerabläufe wurden vom Implementierungsowner behoben und unabhängig nachgeprüft. Der Reviewer änderte keine Produktdateien.

## Tatsächliche Serverfälle

Drei eigene Fälle bestehen gegen zwei gleichzeitig laufende lokale HTTP-Prozesse mit getrennten SQLite-Datenbanken, Hostbindungen, Instanzkennungen und tatsächlicher MFA-Anmeldung. Die bestehende Prozessfixture wird als Modul importiert; ihre bereits geprüften Provisionierungs-, Original-, Ereignis- und Workerfälle werden nicht erneut als eigene Tests gezählt.

Die beiden Anbietertransporte sind ausdrücklich lokale deterministische Testdoubles. Die produktive Konfigurations-, Instanz-, Quellen-, Rechte- und HTTP-Verarbeitung bleibt aktiv. Ein zusätzlicher Testguard verbietet ausgehende HTTPS-Verbindungen. Es gab keine Liveanbieteraufrufe, PostgreSQL-Nutzung, externen Kontakte oder echten Aufnahmen.

- Beide Unternehmen verwenden dieselben synthetischen Chat- und Sprachvorgangskennungen, aber unterschiedliche tatsächliche Projekte, Katalogartikel, Originalimportnachweise und Kontexte. Erfolgreiche Antworten und wiederholte Chatquittungen bleiben an die ausgewählten eigenen Quellen gebunden. Sprachwiederholung wird abgewiesen; ein Statusabruf enthält weder Audiobytes noch Transkript. Fremde Kontext-, Artikel-, Projekt- und Chatreferenzen, ein fremdes Token sowie der falsche Host werden zurückgewiesen. Je Instanz erfolgt genau ein lokaler Chat- und Sprachtransport.
- Nach Entzug von `finance.read` bleibt beim betroffenen Benutzer `assistant.use` erhalten. Dennoch verschwinden unzugängliche Artikel aus der Quellensuche; bereits angenommene Kontexte, persönliche Chatantworten, Chatwiederholungen und Sprachmetadaten verlieren den Zugriff. Ein neuer Sprachauftrag kommt nicht beim Transport an. Die zweite Unternehmensinstanz bleibt unverändert zugänglich.
- Eine nicht zur Datenbankinstanz passende Anbieterfreigabe blockiert sowohl Chat als auch Sprache vor jedem Transport. Sie wird nicht durch ein gültiges Token und eine gültige Fachquelle ersetzt.

Die tatsächliche Antwortfixture `actual-two-company-responses.json` unter `docs/evidence/company-assistant-isolation-independent-2026-11-04/` umfasst 48.745 Bytes und hat SHA-256 `d42e9cbb076aef370abf9c51132cea69cc1ab75e09a580866fb73e1f499f773f`. Sie enthält keine Sitzungstokens, Anbieterzugangsdaten oder Audiobytes. Die transienten Diktatwörter sind rein synthetisch.

## Unabhängige Clientprüfung

Sechs Browser-Vertragsfälle bestehen mit dieser unveränderten tatsächlichen Fixture. Die Reader weisen den Kontext oder die Sprachantwort des anderen Unternehmens auch bei gleicher Sprachvorgangskennung zurück. Zurückgehaltene Antworten der Quellensuche, des Kontexts, des Chats und des Sprachstatus werden beim Sitzungswechsel verworfen. Eine verspätete ursprüngliche Annahme darf einen inzwischen begonnenen Auftrag der neuen Firma unter demselben lokalen UI-Schlüssel nicht löschen. Dies sind JavaScript-Vertrags-/Transporttests, keine erneute vollständige Chromium-Abnahme.

Die native Gegenprüfung hat vor jeder Produktänderung fünf konkrete rote Fälle gesichert:

1. Sichtbare alte Chatdaten bleiben beim Austausch der Parent-Sitzung und des Hosts erhalten.
2. Eine zurückgehaltene alte Quellantwort kann anschließend wieder alte Chatdaten anzeigen.
3. Der private Chat-Originaldialog bleibt nach dem Sitzungswechsel sichtbar.
4. Derselbe Dialog bleibt beim Entfernen seiner Seite auf einem erhaltenen Navigator sichtbar.
5. Ein bereits gestarteter Recorder wird beim Austausch der Parent-Sitzung und des Hosts im Sprachwidget nicht abgebrochen. Es wurde dabei kein Transkriptions-POST ausgeführt; eine Übertragung an einen Anbieter wird nicht behauptet.

Die ursprünglichen beiden Seitenrepros und die erweiterte rote Matrix samt vollständigen damaligen Produktdateien liegen in separaten, unveränderten Belegen. `original-native-expanded-red-manifest.json` hat SHA-256 `da5c6f6a4e0a2d177d936aa41978c228ca318d2f708cd6d4b19b1d02c99de9eb`.

Ein anschließend ausdrücklich geprüfter sechster Ablauf betraf die Rückkehr aus dem Hintergrund während des noch offenen ersten Rechteabrufs. Nach dem Abbruch startete dessen verspätete Antwort neue Fachreads und füllte die zuvor geleerte Chatansicht erneut. Der separate Vorherbeleg `original-native-capabilities-roundtrip-red-manifest.json` hat SHA-256 `4dfd743f2871c40e93dbfb6e171624c12967dcb1a2e08e80cabe7d6f9de7e64a`. Hier wurde keine Unternehmensüberschreitung behauptet; nachgewiesen war die unvollständige Unterbrechung des Ladevorgangs.

Alle sechs ursprünglichen Fehlererwartungen bestehen nach dem Ownerfix. Die insgesamt zwölf nativen Fälle prüfen zusätzlich verspätete Detailantworten und private Fehlermeldungen, einen verspäteten sowie einen verlorenen Kontext-ACK und eine fremde Route oberhalb des eigenen privaten Dialogs. Ein unbekannter Auftrag bleibt ausschließlich in seiner ursprünglichen Sitzung; die neue Firma erhält weder einen daraus übernommenen Kontext noch eine automatische Mutation. Die Sprachprüfung verwendet einen kontrollierten Recorder statt echter Mikrofonhardware. Die beiden ACK-Fälle rufen den Produkt-Commandpfad mit der tatsächlichen bestätigten Quellenauswahl als Vorbedingung direkt auf; sie werden nicht als vollständiger Formularlauf ausgegeben.

Der unabhängige finale Run bindet `business_assistant.dart` mit SHA-256 `e9acc7a54a6d5ff3480631f3c93d99b03150afe30e429531df4202524373f2b2` und `business_speech.dart` mit `c2846687ca7efca56790996ae6408b0f2f7d67792d5f14bef210fb45aa8fc615`. Zwanzig gelesene Runtime-, Fixture- und Testdateien blieben zwischen Snapshot und Abschluss unverändert. Die drei HTTP-Fälle wurden gegen die zwischenzeitlich eng ergänzte gemeinsame Prozessfixture nochmals ausgeführt; dabei blieb die ursprüngliche tatsächliche Antwortfixture bytegleich.

## Reproduzierbarkeit und Abgrenzung

Eigene Dateien: `backend/online/test_company_assistant_isolation_review.py`, `web/office/tests/company-assistant-isolation-independent.test.mjs`, `app/test/business_company_assistant_isolation_review_test.dart`. Die Kernfixture lässt sich gezielt mit `SMARTPLAN_ISOLATION_REVIEW_FIXTURE` beim tatsächlichen HTTP-Test erzeugen; normale Testläufe überschreiben sie nicht. Ein neuer Generatorlauf erzeugt neue IDs und ersetzt keinen historischen Fehlernachweis.

Zwei eigene Harnessfehler bleiben als solche benannt: Der erste HTTPS-Guard ersetzte versehentlich die Verbindungsklasse und störte einen Import; er wurde auf deren `connect`-Methode begrenzt. Eine anfängliche Clienterwartung nahm den freien Modell-Zusammenfassungstext an, obwohl das Backend korrekt eine feste belegbezogene Zusammenfassung erzeugt. Die fachlichen Clienterwartungen prüfen nun die tatsächlichen aufgelösten Originalfakten. Keine Produktänderung war für diese beiden Testkorrekturen erforderlich.

Dieser Nachweis ergänzt die gemeinsame Prozessprüfung. Er ersetzt keine PostgreSQL-Rollenprüfung, getrennte Betriebssystembenutzer, physische Mikrofon-/Geräteabnahme oder produktive Instanzfreigabe.

Der endgültige Handoff steht in `docs/evidence/company-assistant-isolation-independent-2026-11-04/manifest.json`. Er enthält die eigenen Übergabepfade, Hashes der tatsächlich geprüften Dateien, Originalfehlernachweise und die getrennten grünen Abschlussprotokolle. Keine offenen bestätigten Produktbefunde verbleiben innerhalb dieser geprüften Fallgrenzen.
