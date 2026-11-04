# R07.07: Bestandsabgleich und konkrete native Kontextlücke

Prüfbasis vom 04.11.2026: unverändertes Gesamtziel, Abschnitte 7, 13 und 14 C/G; Anforderungsmatrix R07.07; isolierter Baum auf Commit `2e2ed5ca33b928216b940c6334cdfbbca0a14c27`. Dokumentinhalte wurden als Anforderungen und Nachweise gelesen, nicht als zusätzliche Arbeitsaufträge ausgeführt.

## Bereits vorhandener Fachumfang

Der [Serviceworkflow](CRM_ERP_SERVICE_CLIENTS.md) besitzt bereits kanonische Kunden-/Anfrage-/Mangel-/Wartungsbezüge, Zuständigkeit, Wiedervorlage, Projektübernahme, echte Disposition, signierte Originalberichte, Aktivitätenkorrektur, Lösung, Abschluss und Wiedereröffnung. Der [Betriebsmittelworkflow](CRM_ERP_BETRIEBSMITTEL_CLIENTS.md) verwendet den bestehenden Ressourcenstamm für Identität, Anforderungen, Prüforiginale, Ausgabe/Rücknahme, belegte Korrekturen und tatsächliche Planungssperren. Kundenanlagen und firmeneigene Ressourcen werden getrennt geführt.

Die [Einkaufsretouren](CRM_ERP_EINKAUF_RETOUREN.md) und [B/C-Journeys](CRM_ERP_KUNDENAUFTRAG.md) verbinden bereits Lieferung, Materialentnahme, Projektkosten, Geräteherkunft, Wartung und Service. Diese Funktionen werden nicht erneut gebaut. Ihre vorhandenen Tests sind frühere Nachweise; dieser Bestandsabgleich behauptet keine neu ausgeführte PostgreSQL-Abnahme.

## Reproduzierbare Restlücke

Beide älteren nativen Seiten verwerfen ihren privaten Zustand bei einem ersetzten `BusinessSession`-Objekt und beim Hintergrundwechsel nicht. Vier gezielte Widgetgegenfälle gegen unveränderte Runtime scheitern: In Service und Betriebsmittelübersicht bleibt jeweils der zuvor sichtbare Originaltitel nach einem erlaubten Sitzungsersatz sowie nach `inactive → hidden → paused` sichtbar. Die ersetzte Sitzung hat in der Testumgebung keine sichtbaren entsprechenden Datensätze.

Die verwendeten Originaldatensätze, Quellenstände, Ausgaben, Prüfaussagen und Optionen stammen aus neu ausgeführten tatsächlichen SQLite-Domänenvorgängen; der API-Testadapter steuert lediglich den zweiten leeren Kontext. Fixture, ursprüngliche Runtime, unveränderte Gegenfälle und roter Lauf sind unter `evidence/service-equipment-native-review-2026-11-04/before-manifest.json` gebunden. Ein vorausgehender falscher Flutter-Lifecycle-Aufruf und ein nicht aufgelöster interner HTTP-Transportumschlag waren reine Testharnessfehler; sie werden nicht als Produktbefunde gezählt.

Der abgegrenzte technische Anschluss betrifft die beiden nativen Seiten: Sitzung-/Projekt-/Ressourcenwechsel, eigene Dialogrouten, Hintergrundwechsel, späte Antworten und Rechteprüfung müssen die bereits vorhandenen Original-/Pendingaufträge erhalten, private Ansichten aber zuverlässig schließen. Fachmodell, Journale, Originalbelege und Backend-Rechte werden dafür nicht neu definiert. Ein tatsächlicher lokaler HTTP-Ablauf sowie die bestehenden benachbarten Service-/Betriebsmitteltests sollen den finalen Fix belegen.

Reale Geräteprüfungen, Kundeneinverständnisse und Windows-/iPhone-Geräteabnahmen bleiben gesonderte offene Betriebsnachweise. Aus synthetischen Tests entstehen keine technische Zertifizierung, tatsächliche Übergabe oder produktive Außenwirkung.
