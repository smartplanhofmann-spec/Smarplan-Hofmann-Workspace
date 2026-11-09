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

`POST /business/offline/recovery/lookup` ist ausschließlich ein lesender Aufruf
mit frischer normaler Anmeldung. Er akzeptiert keine Geräteanmeldung, keine
Queryparameter, keine doppelten JSON-Schlüssel und höchstens 1.000.000 Bytes.

```text
{schema_version:1, nonce:<32hex>, kind:"plan_write", project_id:<32hex>,
 plan_id:null|<32hex>, command_json:<JSON-Text des exakten ursprünglichen Planauftrags>}
```

Der innere JSON-Text wird begrenzt und streng geparst; doppelte Schlüssel und
NaN/Infinity sind unzulässig. Der äußere Abgleich enthält dadurch nur Zeichenketten,
Kennungen und eine ganze Versionszahl. Unterschiede der Floatdarstellung zwischen
Python und Dart verändern seinen Korrelationshash nicht. Der historische
`request_hash` bleibt unverändert nach dem damaligen Python-Vertrag; der Client
prüft ihn nicht durch eine abweichende Float-Neuformatierung.

Ein positiver Vergleich liefert `schema_version:1`, dieselbe `nonce`, den
SHA-256-`lookup_hash` der vollständigen kanonischen äußeren Anfrage, aktuelle `binding`,
`kind`, `project_id`, ursprüngliche `plan_id`, `request_id`, `request_hash`
und `original` als unveränderte angenommene Antwort. Verglichen werden die
eigene gespeicherte Planquittung und die genau zugehörige archivierte Planfassung.
Aktuelle umbenannte Projekte oder neuere Fassungen ersetzen kein Original.

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

Die abschließenden Nachläufe am 09.11.2026:

| Prüfung | Ergebnis | Umfang |
| --- | --- | --- |
| Neue Speicher- und Onlinefälle | 20/20 | Additive Migration, SQLite-Backup/Restore, Grantablauf, zwei unabhängig gebundene Firmen mit gleichen IDs, Flask-HTTP-Grenze mit MFA, GET/POST/PUT, kopierte Sitzungen, privater Export, strenger lesender Originalabgleich |
| Lokaler TCP-Server | 1/1 | Tatsächliche Verbindung zum verpackten lokalen Server, Discovery, fehlender/richtiger Ursprungsheader, idempotente Planannahme, Originalabgleich und Widerruf |
| Bestehende betroffene Regressionen | 52/52 | Gerätezugänge, Offlineberichte, lokale HTTP-Rahmung, Projektmappe, Instanzisolation sowie tatsächliches vertrauenswürdiges TLS mit MFA, V2-Bericht und PDF |
| Schema, Fähigkeiten und Router | 25/25 | Bestehende Registry-, Modul- und Pfadverträge |
| Native Paketquellen | 16/16 | Einschließlich tatsächlich erstelltem Supportarchiv und importiertem verpacktem Backend; kein Windows-Build |

Die numerischen Originalfälle verwenden den unveränderten vorhandenen
Planschreiber: ganze Koordinaten, `1.0`, `-0.0`, kleine Exponenten und spätere
Fassungen. Dieselbe Zahl in anderer JSON-Notation bleibt abgleichbar. Ein
geänderter Zahlentyp oder ein geändertes Nullvorzeichen kann keine manipulierte
historische Fassung als Original bestätigen.

Unabhängige Prüfung fand eine zunächst fehlende Laufzeitkontrolle gegenüber
einer inkonsistent verlängerten Sitzungszeile; der Fehler ist behoben und durch
einen Regressionstest belegt. Fehlgeschlagene Erstläufe bleiben gesondert erhalten:
zunächst fehlende Python-Importpfade, der bewusst gesperrte V1-Zugang im zuvor
gebundenen TLS-Test, eine korrigierte Fehlercodeannahme und die unzutreffende
HTTP-200-Annahme beim lokalen Replay (der bestehende Vertrag erhält HTTP 201).

Rohprotokolle, Hashes und geprüfte Quellhashes stehen unter
[`evidence/offline-instance-binding-2026-11-09`](evidence/offline-instance-binding-2026-11-09/verification.json).
Die gemeinsame, tatsächlich erzeugte Vertragsfixture ist
[`offline_binding_v2.json`](../app/test/fixtures/offline_binding_v2.json), SHA-256
`2a31cd4c282ac30f36ca4b7e691d6ec9714be7ce8ebbad8b32a239d8e3cfd5d1`.
Ihr Generator ist [`generate-offline-binding-fixture.py`](../scripts/generate-offline-binding-fixture.py).

Native Integration, PostgreSQL mit Betriebsrollen, Browserintegration und echte
Windows-/iPhone-Geräteprüfungen werden getrennt fortgeschrieben. Diese
Backendnachweise verwenden ausschließlich synthetische Firmen und Daten und
behaupten weder Geräteabnahme noch vollständige Migration alter Offlinearbeit.
