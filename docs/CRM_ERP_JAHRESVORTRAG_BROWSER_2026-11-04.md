# Belegte Jahreswerte vor Softwarebeginn im Browser

Arbeitsbeginn 04.11.2026, ausschließlich
`/workspace/smartplan-opening-year-values-20261104`. Grundlage ist der
[tatsächliche API-Vertrag](CRM_ERP_JAHRESVORTRAG_API.md), Backendhandoff
`docs/evidence/year-values-backend-2026-11-04/manifest.json` (SHA-256
`6c665abc663964c27dff1a38baf61a895d064904a7aa3957079e14e84db8221a`)
und die tatsächlich angenommene Fixture
`docs/fixtures/accounting_year_values_v1.json` (SHA-256
`441f0665a27dd304f229dbf604c09f5463013c636c222c47cf8f581e3b7eb5d5`).

## Plan und feste Anforderungen

1. Geschützten Quellvertrag, Originalprüfsummen, zusammenhängenden früheren
   Zeitraum und unveränderte Profil-/Jahresbindung lesen. Kein fehlender Bestand
   wird zu einem Nulljournal. Vollständigkeit des gewählten Teilzeitraums und
   vollständige Deckung bis Softwarebeginn bleiben verschiedene Aussagen.
2. Aktuelle unveränderte Altposten als kanonische Quellen auswählen oder
   tatsächlich vollständig erledigte externe Belege samt Originalen, alten
   Zahlungs- und Vorsteueridentitäten erfassen. Ausdrückliche Kontrollsummen und
   eigenständigen Journalnachweis verlangen, keine berechneten Geldflüsse oder
   neuen Vorsteueransprüche erfinden.
3. Originalupload, Vorschau und ausdrücklich bestätigte Annahme mit exakten
   ursprünglichen Aufträgen unterstützen. Verlorene Antworten behalten ihre
   Vorgangskennung und ihre originale Vorschau, auch nach Journalfortschritt.
4. Historische Fassungen, Originaldownloads, kontrolliertes Void und neue
   Berichtigung bereitstellen. Vor Quellenänderung muss eine aktive EÜR-
   Übernahme ausdrücklich gegengebucht werden; die Oberfläche behauptet keine
   automatische Aufhebung ihrer Folgewirkungen.
5. Separaten EÜR-Vorgang `opening_year_values` mit verifizierten Originalzeilen
   anbinden. Alte Tage, ausgeübte Vorsteuer und Quellenidentität erhalten;
   Berichte und Exporte früherer Fassungen unverändert weiter lesen.
6. Aktuelle Rechte sowie Sitzung, Ansicht, konkrete Dialogphase und Hintergrund
   bei jedem Datei-/Hash-/Vorschau-/Annahmeweg prüfen. Echte Backendfixtures,
   negative Quittungs-/Wiederholungsfälle und Chromium/MFA/HTTP nachweisen.

## Implementierter Bedienvertrag und Zuständigkeit

Browserowner `finish_v6_clients`, Backendowner `finish_v6_backend`, unabhängiger
Backendreview `overall_completion_review`; Native separat. Gemeinsame Hooks
werden von Root additiv mit Altposten, Company Events, Katalog-V2, Source5 und
Anlagen zusammengeführt. Keine Änderung im eingefrorenen Altpostenbaum.

Der bereits fertig geprüfte `accounting-open-items-contract.js` wird für die
kanonischen Quellfassungen unverändert als Lesedependenz übernommen, SHA-256
`01abeaa8b778108dc22e75522f7fb6e9799ce015f8e90509e5c01c9c5087b4c1`.
Er wurde nicht für den Jahresvortrag umgeschrieben. Neue Produktmodule heißen
`accounting-year-values-contract.js` und `accounting-year-values.js`.
Ausgangshashes stehen in `work/verification/year-values-browser-baseline.json`.

Der Browserbereich ist von der EÜR-Vorbereitung, der eigenen EÜR und den
Einstellungen erreichbar. Neue Vorgänge beginnen mit leeren tatsächlichen
Daten, Kontrollsummen und Bestätigungen. Ein kanonischer Altposten wird mit
seiner unveränderten Fassung gewählt; ein vollständig bezahlter externer Beleg
benötigt eigene Rechnungs-, Zahlungs- und Vorsteueroriginale. Das frühere
Zeitraumjournal ist ein eigenständiges Original mit anderen Bytes.

Vorschau und verbindliche Annahme sind getrennt. Die Annahme legt den
Originalnachweis fest; erst die gesonderte EÜR-Übernahme kopiert seine alten
Journalzeilen. Im überprüften Lieferantenfall bleiben die ursprünglichen
59,50 Euro Zahlung im August und die 19 Euro ausgeübte Vorsteuer im Juni. Es
entsteht keine neue Geldbewegung. Ein späterer vollständig bezahlter Altbeleg
erzeugt ebenfalls keinen fiktiven offenen Posten und keine neue Auszahlung.

Eine aktive EÜR-Übernahme muss vor Quellenkorrektur ausdrücklich gegengebucht
werden. Historie, partielle Berichtigung und unveränderte Aufhebung sind eigene
sichtbare Wege. Ein Teilzeitraum bleibt als solcher gekennzeichnet. Ein
unvollständiges aktuelles Profil bleibt lesbar; neue Eingaben werden erst bei
passendem bestätigtem Profil angeboten. Eine bereits angenommene, aber noch
unbestätigte Quittung bleibt auch nach Wegfall des aktuellen Startdatums exakt
wiederholbar, solange die aktuellen Rechte und Serverfreigaben bestehen.

Originaldownloads prüfen Größe und SHA-256 der tatsächlichen Bytes sowie
aktuelle Rechte vor und nach dem Abruf. Altpostenoriginale verlangen zusätzlich
ihren eigenen aktuellen Quellzugang. Fremde Quittungen lösen keinen offenen
Auftrag auf. Sitzungs-, Dialog-, Ansichts- und Hintergrundwechsel verwerfen
späte Inhalte. Der echte Hintergrundhandler invalidiert auch einen bereits
begonnenen EÜR-Einstieg, wenn noch kein Dialog existiert.

## Prüfung und behobene Gegenfälle

Die dauerhaft gespeicherten Originalfixtures wurden nicht verändert. Zwei
zusätzliche eigenständig erzeugte UI-Fixtures enthalten tatsächliche
Serverzustände einschließlich Konten, Journal, Quelloriginalbytes und
unvollständiger Profile; ihr Generator wird separat versioniert.

Der unabhängige Review reproduzierte drei Readerwidersprüche: abgeleitete
Zahlungstage oder Cents konnten den unveränderten Originalquellen widersprechen;
die öffentliche EÜR-Quelle konnte kopierte Cents und Postings widersprüchlich
zeigen. Die Reader vergleichen jetzt Originalhistorie, kopierte Zeilen und
Journalpostings genau. Zwei weitere Fälle betrafen späte initiale EÜR-Antworten
nach Hintergrund und Rückkehr. Eine dauerhaft erhöhte Kontextgeneration
unterdrückt sowohl den alten Editor als auch dessen späten Fehler.

Der erste echte Browserlauf fand zusätzlich einen nicht aktualisierten Zähler
für unbestätigte Uploadantworten. Der Zähler wird nun auch beim Fehlerausgang
aktualisiert, ohne den Originalauftrag zu ändern. Spätere rote Browserläufe
betrafen ausschließlich die Teststeuerung: zu frühes Lesen einer asynchron neu
angelegten Kontrollzeile, einen falschen Panel-Selektor und eine gehaltene
Vorschau trotz fachlich korrekt gesperrter Korrektur vor EÜR-Gegenbuchung. Diese
Läufe sind als begrenzte Zwischenstände erhalten und kein positiver Nachweis.

Der vollständige neue Chromium-/MFA-/HTTP-Ablauf besteht Originalupload und
Downloadhash, beide Lost-ACK-Wiederholungen, Quellenauswahl, Kontrollsummen,
Annahme, getrennte EÜR, explizite Gegenbuchung, Teilkorrektur, Aufhebung,
vollständig erledigten Altbeleg, vier unveränderliche Fassungen und 390-Pixel-
Ansicht. Die gehaltene EÜR-Originalantwort wurde zusätzlich über den echten
Office-Hintergrundhandler verworfen; der Hintergrundzustand wurde im Browser
gezielt ausgelöst. Der unveränderte bestehende EÜR-Browserablauf ist ebenfalls
grün: normale Geldflüsse, Vorsteuer, Korrektur, AfA, Gegenbuchung,
Periodensperren und originale JSON-/CSV-Ausgaben.

Abschließend bestehen **57/57 fokussierte Nodefälle** (27 eigene, 30
unabhängige) sowie **635/635 tatsächlich benannte Tests** der gesamten Browser-
Nodesuite dieses isolierten Stands, ohne Fehler, Abbruch oder Überspringen.
Beide echten Chromium-/MFA-/HTTP-Abläufe sind grün. Syntaxprüfungen der vier
Produktmodule und der beiden Python-Fixtureprogramme sind ebenfalls ohne
Befund. Der Integrationspatch wurde auf seinen ausdrücklich benannten Basen
angewandt und reproduziert beide fertigen gemeinsamen Dateien bytegenau.

Dateihashes, Logkopien, Browserartefakte und die finale unabhängige Gegenprüfung
stehen in `docs/evidence/year-values-browser-2026-11-04/manifest.json`. Diese
Dokumentation behauptet keine produktive Auslieferung, keinen vollständigen
Gesamtsoftwareabschluss und keine amtliche Steuerdatei.

## Integrationsgrenze

Der enge EÜR-Patch basiert auf dem unveränderten finalen Altpostenreader
`f467b2725f6c207552627c8d94711c0dbe0d5d77341779749480382e22f3e0e5`.
Root integriert ihn additiv. Insbesondere die neueren Jahrespaket-V1-
Exportintent-/Hintergrundschutzfunktionen dürfen nicht durch diese ältere
Gesamtdatei ersetzt werden. Die neue private EÜR-Kontextgeneration und deren
Hintergrundhook ergänzen den vorhandenen Exportintent. Der unveränderte
Altpostencontract ist nur eine Lesedependenz.
