# Wartungsverträge im Browser bearbeiten

Der Browser konnte bestehende Wartungsverträge anzeigen und neue anlegen,
aber keine laufende Serie pausieren oder bearbeiten. Der neue Einstieg steht
unter **Projekte → Projekt öffnen → Wartung → Wartungsvertrag bearbeiten**.
Anlage, Vertragsbezeichnung, erste Fälligkeit, Intervall, Aktivierung und
Vertragshinweise werden aus dem frisch gelesenen Vertrag übernommen.

**Aktiv** ausschalten und **Änderungen speichern** pausiert den Vertrag.
Erneutes Aktivieren setzt die vorhandene Serie fort. Bereits geplante Einsätze,
abgeschlossene Besuche, ursprüngliche Vertragsstände und verknüpfte Nachweise
bleiben erhalten. Pausieren storniert keine bestehenden Termine. Nach erzeugten
Besuchen erlaubt das unveränderte Backend einen Wechsel von Anlage, Anker oder
Intervall ausschließlich über einen neuen Vertrag. Titel, Hinweise und
Aktivierung bleiben bearbeitbar. Vorhandene Originaldateiverweise werden bei
einer Änderung unverändert mitgeführt.

Die Oberfläche verwendet die vorhandenen Vertragsendpunkte und deren Revision.
Bei einer zwischenzeitlichen Änderung weist der Server die veraltete Fassung
zurück. **Aktuellen Stand laden** öffnet die inzwischen gespeicherten Werte;
dieser Lesevorgang schreibt nichts.

## Unbestätigte Antworten und Rechte

Eine verlorene Antwort hält denselben Pfad, Inhalt und dieselbe Request-ID im
Arbeitsspeicher fest. Die gesperrte Ansicht zeigt den Originalauftrag und bietet
**Ursprüngliche Antwort erneut prüfen** an. Vor jedem erneuten POST werden die
aktuellen Projektrechte und der kanonische Vertrag gelesen. Eine unbestätigte
Antwort wird bei Rechteverlust oder einem nicht eindeutig abgelehnten Konflikt
der Wiederholung erhalten. Ein bestätigter Originalbeleg muss Vertragskennung,
Projekt, nächste Revision und alle bearbeiteten Werte einschließlich
Originaldateiverweisen bestätigen.

Ein während der Rechteprüfung geschlossener oder ersetzter Dialog darf keinen
weiteren POST auslösen. Eine später bestätigte Antwort darf einen inzwischen
anderen Dialog nicht schließen. Hat ein anderes Fenster im selben Client den
ursprünglichen Auftrag bereits bestätigt, lädt ein noch gesperrter Editor nur
den aktuellen Stand; sein Wiederholen-Knopf darf daraus keine neue Änderung
machen. Ein Sitzungswechsel entfernt private Ansichten und Sitzungsaufträge.
Eine dauerhafte Wartungsvertragswarteschlange über einen vollständigen
Browserneustart ist nicht Bestandteil dieses Abschnitts.

## Nachprüfung am 09.11.2026

- Elf neue Node-Fälle prüfen vollständige Eingaben und Belege, falsche
  Vertrags-/Projektkennung, aktuelle Rechte, Lesemodus, identische Wiederholung,
  unklaren Moduskonflikt, Sitzungswechsel und verspätete Antworten nach
  geschlossenem oder ersetztem Editor.
- Der echte Chromium-Ablauf verwendet lokale MFA und HTTP mit einer synthetischen
  Anlage, einem vorhandenen Vertrag und einem bereits geplanten Besuch. Eine
  tatsächlich angenommene Pause verliert absichtlich ihre Antwort. Ihre
  Wiederholung bestätigt dieselbe Revision ohne zweite Wirkung. In der Pause
  entstehen keine weiteren Besuche; nach Reaktivierung entsteht genau die
  nächste Fälligkeit. Wiederholte Planung erzeugt keine Duplikate. Der alte
  Besuch wird vollständig mit seinem ursprünglichen JSON verglichen.
- Derselbe Browserlauf prüft einen echten parallelen Schreiber, veraltete
  Revision, erneutes Laden ohne POST und den Editor bei mobiler Breite.
- Vier vorhandene Wartungs-Domainfälle bestehen: Kalendermonats-/Schaltjahranker,
  Wiederholung, Pausierung, Rechteverlust und Abschluss über signierten Bericht.

Die unabhängige Prüfung reproduzierte zwei Fehler der ersten lokalen Fassung:
ein ersetzter gesperrter Editor konnte nach späterer Bestätigung unbeabsichtigt
neu schreiben; ein Moduskonflikt bei der Wiederholung konnte den Originalauftrag
verwerfen. Beide Gegenfälle sind als Regressionstests enthalten und behoben.

Permanente Prüfdateien:
`web/office/tests/maintenance-contracts.test.mjs` und
`web/office/tests/maintenance-contract-flow.cjs`.
Der gezielte Browserablauf wird auch im vorhandenen CI-Job aufgerufen.
Die vollständige Browsermodulprüfung besteht mit **938/938 Fällen** ohne Skip
in 44,951 Sekunden. Der abschließende echte Browserlauf nach beiden
Reviewkorrekturen besteht ebenfalls. Die vier vorhandenen Domainfälle bestehen
in 5,913 Sekunden. Ausgangsstand dieses Abschnitts ist `a7c1e0b`.

Lokale Protokolle: `/tmp/maintenance-contract-browser-regression-final2-20261109.txt`,
`/tmp/maintenance-contract-browser-e2e-after-review-20261109.log` und
`/tmp/maintenance-contract-domain-regression-20261109.txt`. Die ersten
Laufzeitfehler betrafen gesperrte lokale Unterprozesse beziehungsweise Sockets;
der abschließende Lauf verwendet die zugelassene lokale Testumgebung.
Der rot reproduzierte Editor-Gegenfall bleibt separat unter
`/tmp/maintenance-contract-replacement-red-20261109.txt` erhalten.

Der Root-Nachlauf auf dem gemeinsamen Meilenstein-/Offline-Backend besteht
ebenfalls: 938 Browsermodulfälle in 16,473 Sekunden und derselbe tatsächliche
Chromium-Ablauf. Protokolle, Originalquittungen und das Mobilbild sind dauerhaft
im Repository gesichert: [Integrationsnachweis](evidence/offline-binding-integration-2026-11-09/maintenance-integration.json).

Es wurden keine Wartungsregeln, Datenbanktabellen, Kundenverträge oder echten
Termine geändert. Die zusätzliche Backendzeile erlaubt nur die Auslieferung
des neuen Browsermoduls. Reale Geräte-/Bedienabnahme und die noch offenen
Gesamtnachweise zu R07.07 bleiben gesondert erforderlich.
