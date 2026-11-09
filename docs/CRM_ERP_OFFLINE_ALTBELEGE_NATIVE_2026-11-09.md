# Alte native Planaufträge einzeln lesend abgleichen

Die Erweiterung zu R11.02/R11.03 verbindet den bestehenden Hash-Abgleich mit
einer bedienbaren Windows-/iPhone-Ansicht. In der Navigation steht **Alte
Offline-Aufträge prüfen**. Nach aktueller Firmenanmeldung wählt der Benutzer
**Gerätebestand prüfen** und entsperrt das Gerät. Zunächst erscheinen nur
nummerierte Planaufträge und ihr Prüfstatus, keine unbewiesenen alten Titel,
Zeichnungen, Projektkennungen oder sonstigen privaten Cacheangaben.

**Ursprüngliche Annahme prüfen** sendet ausschließlich die sieben bereits
definierten Hash-/Kennungsfelder an den lesenden Recovery-Endpunkt. Titel,
Wände, Snapshot, Zeiten, Fotos oder vollständige Originalbefehle werden nicht
übertragen. Eine passende Serverquittung wird zusätzlich streng gegen den
separat zurückbehaltenen lokalen Originalauftrag geprüft. Erst dann erscheint
der Titel des aktuell autorisierten, geprüften Serveroriginals. Eine erneute
Prüfung entfernt diese Anzeige vorher; Ablehnung oder falsche Originale geben
keinen Titel frei.

Ein Treffer bestätigt ausschließlich die damalige Annahme dieses einzelnen
Auftrags. Fehlender Treffer, fehlende Rechte, ungültige Antwort oder verlorene
Verbindung bedeuten **Annahme ungeklärt**, niemals bestätigte Nichtannahme.
Der Ablauf erstellt keine Schreibfreigabe und sendet keinen alten Plan erneut.
Nicht vollständig vorbereitete, beschädigte oder derzeit nicht exakt
Python-kompatibel hashbare Zahlendarstellungen bleiben ausdrücklich ungeklärt.
Weitere alte Warteschlangen werden nur als erhaltene Anzahl ausgewiesen.

Der tatsächliche historische V1-Aufbau wurde gegen den gepinnten Quellstand
`7b54dddfeb85bdef718bf4c76d369b0f673a5ede` geprüft. Diese Dateien besitzen
`cache_schema:1`, aber kein `server`-Feld. Der Server-/API-/Kontobezug lag im
verschlüsselten Geräteverzeichnis. Ein erster neuer Leser verlangte ein
zusätzlich erfundenes Serverfeld und wies echte V1-Formate zurück. Die
Gegenprobe mit dem historischen Format reproduziert diesen Fehler sowohl im
Dateispeicher- als auch im tatsächlichen HTTP-Fall. Die Korrektur verlangt
jetzt das tatsächliche Schema 1; ein optional vorhandener widersprüchlicher
Host wird weiterhin gesperrt. Diese alte Verzeichnisbindung beweist keine
Firmenzugehörigkeit. Sie erlaubt nur den begrenzten lesenden Hash-Abgleich.

Vor jeder Prüfung werden Identität und aktuelle Instanzbindung neu gelesen.
Ein geänderter Firmenbezug oder zwischenzeitlich veränderter Gerätebestand
blockiert die Abfrage. Ein Zugangswechsel leert den Arbeitsspeicher sofort;
verspätete Antworten werden verworfen. Beim Verlassen oder Pausieren der App
wird der gelesene private Arbeitsspeicher ebenfalls verworfen. Die kurzzeitige
Inaktivität während der ausdrücklich gestarteten Geräteentsperrung bricht
diese nicht selbst ab; ein echtes Pausieren verwirft die Ansicht weiterhin.

Die alten verschlüsselten Dateien, vorherigen Commits, Schlüssel, Token,
Auswahl und Warteschlangen werden niemals umgeschrieben oder gelöscht. Ein
fehlender Schlüssel, beschädigter jüngster Commit oder unvollständiger
Speicherdateiname führt nicht zu einer Rückkehr auf ältere Daten. Ein fehlender
Altbestand erzeugt keine Datei und keinen neuen Geräteschlüssel. Der neue
Ablauf speichert auch keine dauerhafte Ersatzzuständigkeit oder pauschale
Cachezuordnung; beim erneuten Öffnen wird wieder aktuell geprüft.

Alle 43 betroffenen nativen Fälle bestehen; die vollständige Appanalyse ist
ohne Befund (15,5 s). Die gezielte gemeinsame Prüfung umfasst Controller, echte verschlüsselte
Dateien und geschützte Speicher-Schnittstelle, 390px-Navigation und Ansicht,
Geräteentsperrung, App-Lebenszyklus, Rechte-/Zugangswechsel, V2-Abgrenzung und
den tatsächlichen MFA-/HTTP-Ablauf gegen zwei unabhängig gebundene Firmen mit
gleichen Benutzer-/Projektkennungen. Firma A bestätigt ihren Originalplan;
Firma B erhält keine Zeichnung oder Titelübertragung und keinen neuen Plan.
Alle alten Dateien und Gerätespeichereinträge bleiben bytegleich.
[Unveränderte Rohläufe, historische Quelle und endgültige Quellhashes](evidence/offline-legacy-recovery-native-2026-11-09/manifest.json).

Das schließt die bedienbare Einzelprüfung bereits angenommener alter
Planaufträge. Es ist keine vollständige V1-Migration. Unbewiesene Pläne,
weitere Zahlenfälle, Fotos, Zeitereignisse, Importe, Projektmappenänderungen
und Berichte benötigen ihre eigenen Abgleiche beziehungsweise geschützte
Konfliktklärung. Reale Betriebssystementsperrung, Geräteinstallation und
Kundenabnahme bleiben getrennte Auslieferungsnachweise. Der zuletzt vom Nutzer
bestätigte Server bleibt A93; ein neuer Serverstand wird hier nicht behauptet.
