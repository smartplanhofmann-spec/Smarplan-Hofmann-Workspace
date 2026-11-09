# Native Offline-Firmenbindung V2 – 09.11.2026

Auftrag: Gesamtziel weiter umsetzen; Offlinepläne, Arbeitsbereich, Zeiten,
Fotos und unterschriebene Serviceberichte dürfen bei einem Firmenwechsel
unter derselben Serveradresse keine Originale oder Aufträge vermischen.

Basis: `e5e313b35bcc55ad419247ff67d6ff2ebcb553cf`, ergänzt um den
Windows-Testcleanup `13b6477` (lokal `7b54ddd`). Backendvertrag:
`fced12211bd6998e8fce1739d325416e2af5100e` plus Hash-only-Korrektur
`b0635c6983bbf6a6ae621c4fe4a310feb1fa3e88`. Tatsächlich gemeinsam
geprüfter Backendstand: `4ebf012810913c1d7ea42cf588e964760ff45182`
(einschließlich gebundener V1-Ausstellungssperre).

## Implementierter Umfang

- Frisch authentifizierte Erkennung über `/offline/context`; Offlinebeginn nur
  bei bestätigtem `bound_v2`. Fehlende, ungebundene oder fehlerhafte Antworten
  eröffnen keinen alten Cache. Onlinebetrieb bleibt möglich.
- V2-Grant und alle Offlineaufrufe binden Server, API-Version, tatsächliche
  Firmeninstanz und Benutzer. Token und Bindingheader werden vor Netzwerk-I/O
  gemeinsam festgehalten. Eigene Schlüssel-, Token- und Auswahl-Namensräume;
  gespeicherte Queue-Herkunft wird vor Verwendung geprüft.
- Unterbrochene Anmeldung, verspätete Antworten und Dateischreibvorgänge
  veröffentlichen keine Daten in einer späteren Firma. Abmeldung schließt
  den sichtbaren Zustand auch bei Schreibfehlern; nur der ausdrücklich
  abgemeldete V2-Token wird entfernt. Fehler werden weitergegeben.
- Legacy-V1-Dateien, Schlüssel und Token bleiben unverändert gesichert.
  Keine automatische Migration, Umbenennung, Zuordnung oder Wiederholung.
- Additive Hash-only-Hilfsfunktionen prüfen einen einzelnen historischen
  Planauftrag lokal und einen tatsächlichen Quittungsnachweis. Zulässig sind
  nur nachgewiesene Python/Dart-Zahlendarstellungen: Integer oder integrale
  Double-Koordinaten innerhalb ±10000, einschließlich typgetreuem `-0.0`.
  Andere Zahlen bleiben gesperrt. Kein produktiver automatischer Recovery-
  Aufrufer und keine neue Wiederherstellungsoberfläche.

## Nachweisgrenzen

Die echte MFA-/HTTP-Prüfung schaltet zwei synthetische gebundene Unternehmen
mit gleicher Adresse, Benutzer-ID und Projekt-ID um. Angenommene Plan- und
Medienantworten werden gezielt verzögert. Sie prüft getrennte Originale,
unveränderte Request-IDs und die spätere Fortsetzung ausschließlich in A.
Eine zusätzliche Prüfung verwendet `OfflineDevice` selbst mit dem
schlüsselgenauen Secure-Storage-Testadapter und echten AES-Dateien.

Die PDF-Härtung prüft den zuvor festgehaltenen Vault nach einer asynchronen
Hashgrenze erneut. Der Test hält die Hash-Future ausdrücklich an. Das ist
eine kontrollierte Verzögerungsvariante; ein entsprechender Datenabfluss
mit der aktuell synchron rechnenden nativen DartSha256-Implementierung
wurde nicht nachgewiesen.

Die gemeinsame unveränderte Backendfixture hat SHA-256
`92ad11ff24c9eb5a7ee84bd17f94854a620a1a7fc2f1562f2a6e7af69c39db64`.
Das Gesamtziel bleibt unverändert mit SHA-256
`a4dea28f6de4afd3e36d1549441aad91ce16dad374f56097979cc2d79b07fbf5`.

## Testprotokolle

Der gemeinsame Abschlusslauf der 21 betroffenen Dateien besteht mit
**186/186 Tests ohne Skip** in 181 Sekunden. Der anschließende echte
HTTP-Ergänzungslauf für Modulpausen sowie unterschriebene Serviceberichte
besteht mit **2/2 Tests** in 5 Sekunden. Zusammen sind 23 betroffene Testdateien
geprüft; die zwei ergänzenden Dateien ändern nur Backendpfad und Cleanup.
Die abschließende Appanalyse ist ohne Befund (24,5 Sekunden).
[Maschinenlesbarer Abschluss](result.json) · [Protokoll-Hashes](logs.json).

Die gzip-Dateien enthalten die vollständigen jeweiligen Konsolenausgaben. Frühere
Fehlschläge bleiben erhalten: alte V1-Testfixtures, ein fehlender frischer
`/me`-Fixturezweig, fehlende Testimports und FakeAsync-Aufbauten mit einer
echten Verzeichnisabfrage in einem ansonsten speicherbasierten Vault.
Bei tatsächlich dateibasierten Widgets mussten außerdem die Initialisierung
und der beobachtete Abschluss über die richtigen Testzonen erfolgen; bloßes
`pumpAndSettle` oder ein in der anderen Zone erwartetes `idle` war kein
verlässlicher Nachweis einer beendeten Dateischreiboperation.
Aufgegebene Diagnose-/Wiederholungsläufe wurden gezielt beendet; dabei
auftretende Flutter-Sink-/Listener-Abbruchfehler sind keine bestandenen Tests.

Keine Veröffentlichung, Installation auf dem Kundenserver oder manuelle
Geräteabnahme Bestandteil dieses lokalen Nachweises.
