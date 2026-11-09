# Projektmeilensteine im Browser

Stand 09.11.2026. Browserkandidat `d7afc14` mit Unicode-Prüfzusatz `92cb5ca`
und CRLF-Erhalt `6afe932`, auf Basis `6a454ca`. Der gemeinsame Datenvertrag steht in
`CRM_ERP_PROJEKTMEILENSTEINE_2026.md`; dieses Dokument beschreibt den Browser.

## Umfang und Bedienung

Gesamtziel §6 verlangt Meilensteine getrennt von Aufgaben und Terminen.
Die neue Registerkarte **Projekte → Projekt öffnen → Meilensteine** zeigt
Projektziele, Status, Fälligkeit, Verantwortliche und gespeicherte Versionen.
Anlegen und Bearbeiten erlauben die drei Zustände **Geplant**, **Erreicht**
und **Entfallen**. „Als erreicht markieren“ und „Wieder planen“ öffnen den
entsprechend vorbelegten Dialog; erst Speichern bestätigt die Änderung.
Ein erreichter Meilenstein ist keine unterschriebene fachliche Abnahme.
Aufgaben, Terminbuchungen und Geldflüsse werden dadurch nicht verändert.

Der eigene Verlauf zeigt alle vollständigen Originalfassungen mit ihrer
Prüfsumme und der damaligen Verantwortlichenkennung. Heutige Teamadressen
werden ausdrücklich als heutige Bezeichnungen verwendet. Für ausgeschiedene
Verantwortliche wird kein historischer Name erfunden oder aus fremden
Stammdaten ergänzt. Eine unveränderte alte Zuordnung bleibt erhalten.

## Vertrag und Schutz vor veralteten Antworten

Der Browser prüft das exakte v1-Schema, kanonische UTF-8-Hashes,
Projekt-/Objekt-/Revisionsbindung, vollständige Historie und unveränderte
Anlageangaben. Titel und Beschreibung behalten ihre ursprünglichen Leerzeichen
und Zeilenumbrüche. Zeichenlimits zählen Unicode-Codepoints; gültige Emojis
werden erhalten, einzelne Surrogate werden ohne Ersatzzeichen abgewiesen.
Bei bloßer Statusänderung bleiben auch CRLF-Originale exakt erhalten, obwohl
HTML ihre Zeilenumbrüche bei der Darstellung normalisiert. Tatsächliche
Textänderungen erzeugen weiterhin eine neue Fassung.

Jeder Zugriff liest projektbezogene Fähigkeiten. `planning.read` erlaubt das
Lesen; Schreiben verlangt zusätzlich `projects.manage`, einen schreibbaren
Betriebsmodus und ein aktives Planungsmodul. Globale Erlaubnisse und
`planning.write` ersetzen diese Projektberechtigungen nicht. Verantwortliche
stammen aus dem frisch gelesenen Projektteam. Vor einer neuen Änderung wird
die vollständige aktuelle Fassung mit dem geöffneten Original verglichen.

Verlorene Antworten behalten die vollständige ursprüngliche Anfrage und
Kennung. Auch bei inzwischen neueren Revisionen wird die alte Quittung geprüft.
Unklare Antworten, fehlende Rechte und lokale Quell-/Hashfehler verwerfen
keine offenen Aufträge. Nur ausdrücklich belegte Nichtannahme darf einen
serverseitigen Revisionskonflikt abschließen. Navigation, Dialogwechsel,
Sitzungswechsel und verspätete Hashprüfung schließen oder öffnen keine
fremde Ansicht. Ein erkannter Rechteentzug entfernt offene Eingabefelder.

Die Karte ist an die neue Feature-/Modulkennung gebunden. Alte Server werden
nicht durch einen obligatorischen zusätzlichen Workspace-Aufruf belastet.
Diese erste Meilensteinfassung arbeitet online; bestehende Offlineaufträge,
deren Cacheformat und Synchronisationskennungen bleiben unverändert.

## Prüfnachweise

- 15 gezielte Modulprüfungen bestehen, darunter echte vom Backend erzeugte
  Originale, Unicode, leerer Termin/Verantwortlicher, Statusfolge,
  manipulierte Quittungen/Historien, eingeschränkte Rechte, exakte
  Wiederholung und verspätete Antworten.
- Der gesamte integrierte Browser-Modulsatz besteht mit **927 Fällen**, ohne
  Skip, in 16,416 Sekunden. Die Prüfbasis `e27360c` verbindet Backend
  `854218f` mit den drei genannten Browsercommits.
- Der tatsächliche Chromiumablauf `project-milestones` besteht mit **Exit 0**:
  echte MFA/HTTP, sechs unveränderte historische Fassungen, Unicode/Spaces/
  LF/CRLF, aktuelle und ausgeschiedene Verantwortliche, projektbezogenes
  Leseverbot trotz globaler Erlaubnis, Schreibentzug, konkurrierende Revision,
  verlorene Anlage-/Änderungsantwort, identische Anfragewiederholung,
  verspätete Antwort nach Navigation und mobile Ansicht mit 390 × 844 Pixel.
  Namespace-, PID-, Netzwerk- und Seccomp-Sandbox sind vor Anwendungszugriff
  verifiziert. Fachserverantworten sind nicht durch Fixtures ersetzt; verlorene
  Antworten betreffen tatsächlich ausgeführte Requests.

[Logs, echte gespeicherte Fassungen, Screenshot und Hashübersicht](evidence/project-milestones-browser-2026-11-09/verification.json)
sind im Repository gespeichert. Der erste echte Browserlauf scheiterte nur an
der Sichtbarkeitsannahme für eine native Select-Option; die Option wird jetzt
auf Vorhandensein geprüft. Keine Wartefrist wurde erhöht, der alte Fehlerlog
bleibt getrennt erhalten. Die unabhängige Prüfung bestätigte die Korrekturen
für Texttreue, Unicode-Grenzen, Anlagebindung und CRLF-Erhalt ohne Restbefund.

Der neue Ablauf ist im Projektblock der Browser-CI eingetragen; das neue Asset
`project-milestones.js` ist im Backendpaket freigegeben. Neue Remote-CI,
Serverinstallation und menschliche Windows-/iPhone-Abnahme bleiben
getrennte Nachweise.
