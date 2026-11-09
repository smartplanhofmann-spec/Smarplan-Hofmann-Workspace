# Deutsche Rechnungsstellung: Ausstellerland und Währung ausdrücklich prüfen

Die erste Version ist für Deutschland vereinbart. Eine Gegenprobe zeigte,
dass die bisherige Rechnungsfreigabe auch einen Aussteller in Österreich,
der Schweiz oder den USA akzeptierte. Die ISO-Validierung der Anschrift war
keine Prüfung des tatsächlich implementierten steuerlichen Landesumfangs.
Die korrekte synthetische Gegenprobe scheitert am alten Code in allen drei
Ländern; eine neue serverseitige Prüfung schließt genau diese Lücke.

`business_country_rules.py` enthält einen unveränderlichen, expliziten
Regelpaketkatalog nach Fachbereich, Ausstellerland und Währung. Der aktuelle
Schlüssel ist `commercial_invoice / DE / EUR`, Vertragskennung
`de_commercial_invoice_eur_v1`, Währungsskala 2. Metadaten besitzen einen
kanonischen Pakethash. Es gibt keine Länderaliase, sprachabhängige Auswahl,
dynamische Imports oder stillen Rückfall auf das deutsche Paket. Eine spätere
Ländererweiterung benötigt einen eigenen implementierten und geprüften Vertrag.
Dieses Routing verändert keine bestehenden Beleg-/Rechenhashes und behauptet
keine vollständige Trennung sämtlicher Steuer-, Lohn- oder Meldewerke.

Bei der Vorbereitung einer neuen Rechnung, Abschlags-/Schlussrechnung oder
Stornogutschrift wird das aktuelle Ausstellerland zusammen mit der tatsächlichen
Belegwährung geprüft. Nicht unterstützte Kombinationen bleiben Entwürfe.
Direkt vor Abschluss erfolgt die vorhandene vollständige Neuvorbereitung:
Ein Länderwechsel während des Renderns blockiert den alten Kandidaten vor
Nummernvergabe und Archivschreiben. Deutsche Aussteller mit ausländischen
Kundenanschriften werden nicht pauschal gesperrt; die Kundenanschrift wählt
keinen Ausstellervertrag aus. Die bestehenden Steuerfallprüfungen gelten weiter.

Bereits festgeschriebene Originale, PDFs und ursprüngliche Abschlussquittungen
werden weder neu klassifiziert noch geändert. Auch nach einer Einstellungs-
änderung bleiben ihr Abruf und die exakte ursprüngliche Wiederholung möglich.
Ein solches Wiederholen stellt keinen neuen Beleg aus. Einstellungen und
historische Anschriften anderer Länder dürfen weiterhin erhalten werden;
die Länderprüfung steht vor einer neuen eigenen Rechnungsausstellung.

## Bedienung und Berechtigungen

Mit Feature `commercial_country_scope` stellt
`GET /api/v1/business/commercial/rule-scope` den aktuellen Länderumfang dar.
Der Endpunkt verlangt frisches `settings.manage`, erlaubt keine Suchfilter,
Schreibmethode oder ignorierten GET-Inhalt und ist für beide Offline-Tokenarten
gesperrt. Die Antwort bindet die aktuelle Einstellungsrevision, das gespeicherte
Ausstellerland, EUR und das ausdrücklich ausgewählte Paket oder `null`.

Browser und Windows-/iPhone-App zeigen unter Einstellungen **Länderumfang der
Rechnungsstellung**. Veraltete Einstellungsrevision, widersprüchliche Länder,
fehlende Antwort oder unbekannte Paketversion führen zur Aufforderung,
neu zu laden. Ein älterer Server ohne Feature wird nicht nach dem neuen
Endpunkt gefragt. Ein unterstütztes Land ist ausdrücklich keine Aussteller-
freigabe: Umstiegsdatum, eigene Ausgabe, Steuerfall, Rechte und Belegprüfung
gelten unabhängig weiter. Die Ansicht aktiviert keine Ausgabe und sendet nichts.

## Ausgeführte Nachweise

- 26 Fach-/Archiv-/HTTP-Fälle bestehen, einschließlich tatsächlicher MFA,
  frischer Rechte, zweier Firmen, Offlineverweigerung, Nummernschutz und
  unveränderter ursprünglicher Quittungen.
- Zwei tatsächliche PostgreSQL-Fälle mit der eingeschränkten produktiven
  Runtime bestehen: keine Nummer/kein Archiv für AT/CH, erster deutscher Beleg
  mit Nummer 1, identisches PDF und Originalretry nach Länderwechsel sowie
  geändertes Ausstellerland zwischen tatsächlichem Rendern und Abschluss.
- 1.020 Browsermodulfälle und der wirkliche Chromium-/MFA-Ablauf DE → AT → DE
  bestehen. Er verwendet normale API-Operationen und unveränderte Antworten;
  keine Länderantwort wird vorgetäuscht. Die Browsersandbox bleibt aktiv.
- 17 betroffene native Fälle bestehen, darunter Einstellungen, Rechteentzug,
  fehlendes Feature, geänderte Revision und die 390px-Ansicht des gesperrten
  Ausstellers. Vollständige Appanalyse ohne Befund (15,9 s).
- 16 Paket- und zwei Quellinventarfälle bestehen. Beide expliziten nativen
  Paketlisten enthalten das neue Modul; das wirklich entpackte Backend wird
  importiert. Es gibt keine Datenbankmigration oder Änderung alter SQL-Hashes.

Die erste Gegenprobe benötigte eine Korrektur ihres synthetischen SQLite-
Aufbaus; die produktive SQLite-Ausgabesperre wurde nicht gelockert. Eine spätere
Testannahme verwechselte das voreingestellte unterstützte Land mit einer
tatsächlich eingeschalteten Ausgabe und wurde korrigiert. Zwei Widgetvorläufe
räumten ihren Sitzungs-Timer zu spät beziehungsweise die Sitzung zu früh auf.
Diese Fehl-/Aufbauläufe bleiben erhalten, ebenso die echte rote Ländergegenprobe.
[Quellbindung, Rohläufe und Browserbelege](evidence/commercial-country-scope-2026-11-09/manifest.json).

Diese Änderung ergänzt R03.05/R08.01. Fremde Länder/Währungen sind damit nicht
implementiert; weitere Regeltrennung, Fachprüfung, Geräteabnahme und eine neue
Liveinstallation bleiben getrennte Aufgaben. Der zuletzt vom Nutzer bestätigte
Serverstand bleibt A93. Gesamtsoftware und Abnahmen A–G sind weiterhin offen.
