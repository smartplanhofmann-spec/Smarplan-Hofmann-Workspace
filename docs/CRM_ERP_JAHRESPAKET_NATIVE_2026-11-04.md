# Nativer Zugang zum Original-/Journal-Jahresnachweis

Abgeschlossen am 04.11.2026 im isolierten Baum `smartplan-year-review-export-20261104`. Die unabhängige Prüfung und die anschließende Integration werden getrennt dokumentiert.

Die vorhandene EÜR-Journalkarte kennt den bereits bestätigten Exporteintrag mit ID, Originalhash, Jahr und unverändertem bisherigen `smartplan_euer_review_v1`-Artefakt. Der zusätzliche lesende Zugang öffnet das separate `smartplan-year-evidence-v1`-ZIP. Die bisherigen JSON-/CSV-Ausgaben bleiben unverändert.

## Anforderungen und Umsetzung

1. Ein geschlossener Vertrag prüft die ursprüngliche Journalfassung, ihren Eintragshash, Report- und CSV-Hash sowie exakt 16 Metadatenfelder. Export-ID, Exporthash, Jahr, damalige Reportvollständigkeit, Dateiname und Archivpfad bleiben an diese Originalfassung gebunden.
2. Die neue Seite verlangt aktuelle globale Buchhaltungs- und Finanzleserechte, das vorhandene EÜR-Modul und das Jahresnachweisfeature. Die einzelnen enthaltenen Quellen prüft der Server bei jedem Metadaten- und Archivabruf erneut. Öffentliche Lohn-/Reisequellen verlangen ihre ausdrückliche private Originalgrenze auch in den Metadaten.
3. Der erste authentisierte Metadatenabruf bindet die Instanz im aktuellen API-/Sitzungskontext. Der alte Export und BusinessSession besitzen keinen getrennten Instanzanker; dafür wird kein neuer Vertrag erfunden.
4. Die ZIP-Datei wird auf exakte Größe, SHA-256 und ZIP-Kennung geprüft. Anschließend werden dieselben Metadaten erneut unter aktuellen serverseitigen Einzelquellenrechten abgerufen und vollständig verglichen. Die Desktopablage wiederholt dies nach der Dateiauswahl unmittelbar vor dem Schreiben. Der mobile Export verwendet die bestehende temporäre Dateiausgabe mit Kontextprüfung.
5. Sitzungs-, Export-, Rechte- und Hintergrundwechsel verwerfen private alte Daten und verspätete Antworten. Nach Wiederaufnahme oder Wiederherstellung von Rechten ist ein ausdrückliches Neuladen möglich. Ein aktueller Fehler zeigt keine privaten alten Exportdaten.
6. Alle Schritte sind lesend. Eine verlorene Antwort wird erneut gelesen; keine Request-ID, Annahmequittung, Finanzbuchung oder Exportneuberechnung entsteht. Der Bildschirm nennt Hash, Größe und die getrennte Grenze privater Personaloriginale.

API: [CRM_ERP_JAHRESPAKET_API_2026.md](CRM_ERP_JAHRESPAKET_API_2026.md).
Tatsächliche finale Backendfixture: `app/test/fixtures/accounting_year_package_v1.json`, identisch zu `docs/fixtures/accounting_year_package_v1.json`, **719679 Byte**, SHA-256 **a859f2bbbcfab6f890c2968a05aa2fa839299117ae43b8e15e2d7852c82d36a0**. Alle sechs Szenarien wurden unverändert geprüft.

## Nachweise

Der abschließende gemeinsame Lauf besteht aus **49/49 Fällen**: 21 neue Vertrags-/Lifecyclefälle, ein tatsächlicher lokaler HTTP-Widgetablauf bei 390×844 und 27 bestehende EÜR-/Accountingregressionen. Die statische Analyse der drei Runtime- und zwei neuen Testdateien meldet **0 Probleme**.

Der tatsächliche HTTP-Fall öffnet den Zugang über die vorhandene EÜR-Exportkarte, verliert einmal eine bereits gelesene ZIP-Antwort, liest denselben Originalexport erneut, schreibt die geprüfte Datei und prüft sie mit dem eigenständigen Backendprüfer. Dabei wird der separat authentisierte Metadatenhash ausdrücklich per `--sha256` übergeben. Der Prüfer bestätigt `verified=true` und ausdrücklich `intrinsic_dependency_closure=false`. Ein anschließender projektbezogener Finanzleserechteentzug bei weiterhin vorhandenem globalem Finanzleserecht verhindert eine zweite Ablage nach dem Dateiauswahldialog. Es entstehen keine POST-Anfragen im Jahresnachweisablauf.

Weitere Fälle prüfen fremde Export-/Instanzbindungen, manipulierte Hashes und Größen, veränderte Metadaten, ausgelassene private Quellengrenzen, verspätete Antworten und Fehler nach Sitzungs-/Export-/Hintergrundwechsel, stille Rechteverluste und die anschließende ausdrückliche Wiederaufnahme.

Endgültige Logs, Dateihashes und Integrationspatch: [Nachweisverzeichnis](evidence/year-evidence-native-2026-11-04/README.md), insbesondere `manifest.json` und `runtime-freeze.json`. Frühere Zwischenstände vor dem finalen Offlineprüfer bleiben als solche erhalten.

## Aussagegrenzen und Integration

Das Paket enthält die aufgelösten Originale. Sein Hash beweist die Bindung an das authentisiert bezeichnete Archiv, jedoch keine eigenständige Vollständigkeit aller zugrunde liegenden Nachweise. Die Offlineprüfung benötigt den separat aufbewahrten, in der Oberfläche angezeigten Archiv-SHA-256. Die Anzeige einer vollständigen Jahresquelle bezeichnet ausdrücklich die Aussage des ursprünglichen EÜR-Reports. Es wird weder eine amtliche Steuererklärung noch eine DATEV-Zertifizierung behauptet.

Die unabhängige Intrinsikgrenze ist auch im ZIP dokumentiert. Laufzeitcode extrahiert oder startet keine Archivdateien. Betriebssystem-Dateidialoge werden im HTTP-Test durch eine kontrollierte lokale Ablage ersetzt; die tatsächliche Backend-/Dateibyte-/Rechtekette wird ausgeführt. Die allgemeinen mobilen Plattformdialoge wurden nicht auf einem Gerät getestet.

Nur zwei neue Runtime-Dateien und ein enger EÜR-Einstieg wurden geändert. `business_session.dart`, `api.dart`, `mail_attachment_widgets.dart`, Abhängigkeiten und bestehende JSON-/CSV-Ausgabe bleiben gegenüber dem gesicherten Ausgangsstand bytegleich. Root integriert den schmalen EÜR-Patch unter Erhalt der separat eingeführten Altposteneinstiege. Kein Backendedit, keine Produktivkontakte, keine Mainänderung und kein Commit durch diesen Nativeauftrag. Ein späterer Jahresvortragsnachtrag mit Format v2 ist ein eigener Auftrag und gehört nicht zu diesem v1-Nachweis.
