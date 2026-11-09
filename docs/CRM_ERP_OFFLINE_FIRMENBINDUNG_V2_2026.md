# Offline-Firmenbindung V2

Vertrag vom 09.11.2026. Die bestätigte V1-Lücke betrifft zwei verschiedene
Firmen mit derselben Serveradresse sowie übereinstimmenden Benutzer- und
Projektkennungen. Eine neue Anmeldung durfte bisher einen alten lokalen
Auftrag mit dem neuen Token übertragen. Neue V2-Caches und Anfragen erhalten
deshalb eine ausdrückliche Instanz- und Kontobindung.

## Discovery und Freigabe

`GET /offline/context` benötigt eine frische normale Online-Anmeldung und
liefert `{schema_version:2, mode, binding}`. `mode` ist `bound_v2` mit
`binding:{schema_version:1,instance_id,account_id}` oder ausdrücklich
`unbound_legacy` mit `binding:null`. Ein fehlgeschlagener Aufruf, HTTP404 oder
eine unbekannte Antwort darf nicht als ungebundener Server interpretiert werden.

Neue leere POST-Endpunkte sind `/offline/access/v2` und
`/business/offline/access/v2`. Sie benötigen eine tatsächlich gebundene
Unternehmensinstanz und normale aktuelle Online-Rechte. Der vorhandene
Geräteumfang bleibt erhalten. Die Antwort enthält `schema_version:2`, Token,
Ausstellungs-/Ablaufzeit, bestehende Fähigkeiten und die oben genannte Bindung.
Die Tokenpräfixe sind `offline_workspace_v2_` und `offline_business_v2_`.

Eine zusätzliche serverseitige Tabelle bindet Tokenhash, Instanz und Konto.
Diese privaten Authentifizierungsdaten gehören nicht in einen neutralen
Unternehmensexport. Ablauf, Widerruf und geänderte Zugangsdaten bleiben wirksam.
Bestehende V1-Quittungen und fachliche Nutzlasten werden nicht verändert.
Auch eine nachträglich verlängerte Sitzung darf die unveränderliche
Grantlaufzeit nicht verlängern: Ausstellungszeit, höchstens sieben Tage Laufzeit,
aktueller Ablauf und identisches Sitzungsablaufdatum werden bei jedem Zugriff
geprüft. Der V2-Credentialhash enthält zusätzlich die tatsächliche Instanz;
kopierte Sitzungs- und Grantzeilen lassen sich nicht mit einem neuen Header
einer anderen Firma zuordnen.

## Jede Offlineanfrage bleibt an ihren gespeicherten Ursprung gebunden

V2-Anfragen einschließlich Lesen, JSON-Schreiben, Binärabschnitten und Downloads
verwenden den Header:

```text
X-Smartplan-Offline-Binding: <instance_id>:<account_id>
```

Beide Kennungen sind genau 32 kleingeschriebene Hexzeichen. Der Server prüft
sie gegen seine tatsächliche Instanz, den authentifizierten Benutzer und den
gespeicherten V2-Grant. Die App muss den Header aus der beim Erfassen dauerhaft
gesicherten Herkunft verwenden, nicht nachträglich aus der nächsten Anmeldung.
Es wird kein Herkunftsfeld in bestehende Fachnutzlasten eingefügt; ihre Hashes
und identischen Wiederholungsaufträge bleiben erhalten.

Auf einem gebundenen Server sind alle V1-Offlinetokenzugriffe gesperrt, auch
GET. Ein bloßer sicherer Widerruf ist ausgenommen. Die alte Benutzerkennung
und der bisherige Credentialhash belegen keine Firmenzugehörigkeit. Normale
Onlineanfragen bleiben unverändert. Ein V2-Fehler erlaubt keinen V1-Fallback.

Auch die Neuausstellung über die bisherigen V1-Endpunkte ist bei gebundener
Instanz gesperrt. Die gemeinsame Vergabefunktion weist sie mit HTTP409 zurück,
bevor sie Sitzungen bereinigt, neue Token erzeugt oder Auditzeilen schreibt.
Damit kann eine ältere App nicht erst einen neuen Token erhalten und dabei
ihren alten Cache einer anderen Firma überschreiben. Bereits vorhandene
V1-Sitzungen und lokale Originale bleiben erhalten; ausdrücklich ungebundene
Legacy-Server behalten ihren bisherigen Vergabevertrag.

## Lokaler Speicher und V1-Bestand

Der native V2-Speicher, sein geschützter Schlüssel, Token und Auswahlindex sind
nach Server, API-Version, Instanz und Benutzer getrennt. Die neue native
Offlinefunktion wird nur im Modus `bound_v2` aktiviert; `unbound_legacy` erklärt
den Zustand und lässt den Onlinebetrieb weiterlaufen, öffnet aber keinen neuen
nativen V1-Cache. Ein Wechsel darf keine
alten Ansichten, Entwürfe oder Warteschlangen in die neue Firma übernehmen.

Vorhandene V1-Dateien, Schlüssel und Token werden weder gelöscht noch durch
einen neuen Grant überschrieben. Ihre unbewiesene Herkunft wird nicht aus
übereinstimmenden Kennungen oder einer erfolgreichen neuen Anmeldung abgeleitet.
Sie bleiben gesichert und von automatischer Anzeige/Übertragung im neuen
Firmenkontext ausgeschlossen. Das ist keine vollständige Altdatenmigration.

## Begrenzter lesender Abgleich bereits angenommener V1-Planaufträge

Sicherheitskorrektur vor Veröffentlichung: Der erste Entwurf dieses Abgleichs
übertrug `command_json`. Dadurch hätten Inhalte eines alten Auftrags aus Firma A
bereits Firma B erreicht, bevor deren Herkunft feststand. Ein anschließender
HTTP404 hätte das nicht verhindert. Dieser unveröffentlichte Vertrag ist
verworfen; auch ein ausdrücklich mitgesendeter alter Auftrag wird abgewiesen.

`POST /business/offline/recovery/lookup` ist ausschließlich ein lesender Aufruf
mit frischer normaler Anmeldung. Er akzeptiert keine Geräteanmeldung, keine
Queryparameter, keine doppelten JSON-Schlüssel und höchstens 4.096 Bytes.
Der exakte Request enthält ausschließlich folgende Metadaten:

```text
{schema_version:2, nonce:<32hex>, kind:"plan_write", project_id:<32hex>,
 plan_id:null|<32hex>, request_id:<32hex>, request_hash:<64hex>}
```

Alle Kennungen und der SHA-256-Wert sind kleingeschrieben hexadezimal. Weitere
Felder, insbesondere Titel, Wände, `command` oder `command_json`, sind unzulässig.
Es gibt keinen Inhalts-Fallback bei fehlendem Treffer. Der Hash ist exakt der
ursprüngliche Python-Hash von `{project_id,plan_id,data:<alter Auftrag>}`;
Herkunft oder Hash dürfen nicht aus einem neuen Token hergeleitet werden.

Ein positiver Vergleich liefert exakt `schema_version:2`, dieselbe `nonce`, den
SHA-256-`lookup_hash` der vollständigen kanonischen Metadatenanfrage, aktuelle
`binding`, `kind`, `project_id`, ursprüngliche `plan_id`, `request_id`, denselben
`request_hash` und `original` als angenommene Antwort. Der Server prüft die eigene
Planquittung mit diesem Hash sowie die genau zugehörige archivierte Planfassung.
Aktuelle umbenannte Projekte oder neuere Fassungen ersetzen kein Original.

Der Server kann aus einem Hash allein die damaligen Eingabewerte nicht
rekonstruieren. Deshalb muss die App anschließend `original` streng und lokal
gegen den unveränderten zurückbehaltenen Auftrag prüfen: einschließlich
Plantitel nach der vorhandenen Normalisierung, Wänden mit Zahlentyp und
Nullvorzeichen, Projekt, Ersteller und ursprünglicher Ergebnisrevision. Auch
Nonce, Antwortschema, Kontobindung und Korrelationshash müssen passen. Erst dann
ist dieser einzelne Auftrag als bereits angenommen bestätigt. Eine bloße
Hashgleichheit oder ein erfolgreicher HTTP-Status reicht nicht.

Die erste native Hashableitung bleibt auf ihre belegte Teilmenge beschränkt:
ganze Koordinaten sowie ganzzahlige Doubles im ausdrücklich geprüften Bereich,
einschließlich `-0.0`. Nicht zuverlässig Python-kompatibel darstellbare Zahlen
bleiben lokal ungeklärt; es erfolgt dann nicht einmal ein Probeaufruf. Der
Backendtest mit Exponenten oder Bruchwerten verwendet den tatsächlichen alten
Python-Hash und ist kein Nachweis einer nativen Float-Kanonisierung.

Nicht gefunden, beschädigt oder gelöscht bedeutet keine bestätigte
Nichtannahme. Solche Antworten enthalten niemals `request_resolution:not_accepted`
und erlauben keine neue Sendung. Ein Treffer bestätigt nur diesen einzelnen
bereits angenommenen Auftrag, niemals die Herkunft oder Vollständigkeit des
gesamten V1-Caches. Unbelegte weitere Pläne, Fotos, Zeitereignisse, Importe oder
Berichte bleiben geschützt erhalten und benötigen einen gesonderten Abgleich.

## Nachweise

Der Backendabschnitt ist implementiert. Die additive Migration erhält frühere
Modulprüfsummen, V1-Sitzungen und Planoriginale. Ein tatsächliches SQLite-Backup
mit Wiederherstellung erhält die Planfassung und widerruft Gerätezugänge durch
die bestehende Sitzungsbereinigung samt neuer abhängiger Grantzeilen.

Die ursprünglichen Nachläufe auf `fced122` am 09.11.2026 (vor der
Hash-only-Korrektur) bleiben als historische Nachweise erhalten:

| Prüfung | Ergebnis | Umfang |
| --- | --- | --- |
| Neue Speicher- und Onlinefälle | 20/20 | Additive Migration, SQLite-Backup/Restore, Grantablauf, zwei unabhängig gebundene Firmen mit gleichen IDs, Flask-HTTP-Grenze mit MFA, GET/POST/PUT, kopierte Sitzungen, privater Export, strenger lesender Originalabgleich |
| Lokaler TCP-Server | 1/1 | Tatsächliche Verbindung zum verpackten lokalen Server, Discovery, fehlender/richtiger Ursprungsheader, idempotente Planannahme, Originalabgleich und Widerruf |
| Bestehende betroffene Regressionen | 52/52 | Gerätezugänge, Offlineberichte, lokale HTTP-Rahmung, Projektmappe, Instanzisolation sowie tatsächliches vertrauenswürdiges TLS mit MFA, V2-Bericht und PDF |
| Schema, Fähigkeiten und Router | 25/25 | Bestehende Registry-, Modul- und Pfadverträge |
| Native Paketquellen | 16/16 | Einschließlich tatsächlich erstelltem Supportarchiv und importiertem verpacktem Backend; kein Windows-Build |

Die korrigierten Backendfälle verwenden den unveränderten vorhandenen
Planschreiber: ganze Koordinaten, `1.0`, `-0.0`, kleine Exponenten und spätere
Fassungen. Sie senden nur dessen ursprünglichen Hash und vergleichen Quittung
mit archivierter Fassung. Ein geändertes Nullvorzeichen zwischen diesen beiden
Serverbelegen wird erkannt. Der zusätzliche Vergleich mit dem lokalen Auftrag
bleibt Aufgabe des Clients und wird dadurch nicht ersetzt.

Unabhängige Prüfung fand eine zunächst fehlende Laufzeitkontrolle gegenüber
einer inkonsistent verlängerten Sitzungszeile; der Fehler ist behoben und durch
einen Regressionstest belegt. Fehlgeschlagene Erstläufe bleiben gesondert erhalten:
zunächst fehlende Python-Importpfade, der bewusst gesperrte V1-Zugang im zuvor
gebundenen TLS-Test, eine korrigierte Fehlercodeannahme und die unzutreffende
HTTP-200-Annahme beim lokalen Replay (der bestehende Vertrag erhält HTTP 201).

Historische Rohprotokolle, Hashes und geprüfte Quellhashes stehen unter
[`evidence/offline-instance-binding-2026-11-09`](evidence/offline-instance-binding-2026-11-09/verification.json).
Die gemeinsame, tatsächlich erzeugte Vertragsfixture ist
[`offline_binding_v2.json`](../app/test/fixtures/offline_binding_v2.json), SHA-256
`92ad11ff24c9eb5a7ee84bd17f94854a620a1a7fc2f1562f2a6e7af69c39db64`.
`retained_command` liegt nur lokal; `lookup_command` enthält keine Inhalte.
`unproven_retained_commands` enthält ausdrücklich nicht übertragbare Floatfälle.
Ihr Generator ist [`generate-offline-binding-fixture.py`](../scripts/generate-offline-binding-fixture.py).

Native Integration, PostgreSQL mit Betriebsrollen, Browserintegration und echte
Windows-/iPhone-Geräteprüfungen werden getrennt fortgeschrieben. Diese
Backendnachweise verwenden ausschließlich synthetische Firmen und Daten und
behaupten weder Geräteabnahme noch vollständige Migration alter Offlinearbeit.

## Nachweis der Sicherheitskorrektur

Die Hash-only-Korrektur wurde mit 21 Speicher-/Flask-MFA-/lokalen TCP-Fällen
geprüft. Dazu gehören die vollständige Ablehnung des alten Inhaltsvertrags auf
beiden Firmen, Fremdkonto-/Fremdfirmenfälle, 4.096-Byte-Grenze, strikte Metadaten,
Archivvergleich, Ablauf/Widerruf und der ursprüngliche SQLite-Restorefall.
Zwei voneinander unabhängige Codeprüfungen meldeten für den korrigierten
Serververtrag keine weiteren konkreten Befunde. Die vorherige positive Prüfung
des Inhaltsvertrags war kein Nachweis der Vertraulichkeit des Clienttransports.

Zusätzlich wird der PostgreSQL-Triggerfunktionsname an die bestehende
Ownership-Konvention angepasst (`business_offline_instance_grant_immutable`),
ohne die zulässigen Namen der Betriebsrolle zu erweitern. Der konkrete vorherige
Setupfehler und der PostgreSQL-Nachlauf werden durch die Integration separat
dokumentiert.

Neue Rohprotokolle und Quellhashes werden unter
[`offline-recovery-hash-only-2026-11-09`](evidence/offline-recovery-hash-only-2026-11-09/verification.json)
gesichert. Die bisherigen Nachweise werden nicht überschrieben.

Der ergänzte V1-Ausstellungsstopp besteht gemeinsam mit den vorherigen Fällen
22/22 Speicher-, Flask-MFA- und tatsächliche TCP-Prüfungen in 21,830 Sekunden.
Beide alten Vergaberouten erhalten sämtliche vorherigen Sitzungszeilen; normale
Onlinezugriffe und die explizit ungebundene V1-Vergabe bleiben erfolgreich.
Die unabhängige Codeprüfung bestätigt die zentrale Abdeckung aller produktiven
Vergabepfade. PostgreSQL wird mit derselben zusätzlichen Ablehnung separat
erneut geprüft. [Zusatznachweis](evidence/offline-binding-integration-2026-11-09/v1-issuance-guard.json).
