# Belegte Einkaufsänderungen und Retouren: Clients

Stand: 03.11.2026. Umgesetzter interner Ablauf zu R07.02. Der stabile Vertrag steht
in [CRM_ERP_EINKAUF_RETOUREN_API.md](CRM_ERP_EINKAUF_RETOUREN_API.md), der ursprüngliche
Befund und die Lager-/Kostenabgrenzung in
[CRM_ERP_EINKAUF_RETOUREN_ENTWURF.md](CRM_ERP_EINKAUF_RETOUREN_ENTWURF.md).

## Tatsächlich bedienbarer Ablauf

Browser und Flutter ergänzen die bestehende Bestellansicht um **Belegte
Mengenänderungen und Retouren**. Bestellvorschlag, Freigabe, externe
Bestelldokumentation und Wareneingang bleiben die vorhandenen kanonischen Wege.
Die neue Ansicht zeigt je ursprünglicher Position getrennt:

- ursprünglich bestellte und aktuell freigegebene kumulierte Gesamtmenge;
- tatsächlich brutto empfangene, zurückgesendete und behaltene Menge;
- weiterhin freigegebene Restliefermenge.

PDF-, PNG-, JPEG- und XML-Originale bis 2 MiB werden ausdrücklich an dieser
Bestellung gespeichert. SHA-256 und Bytezahl werden vor Erfolg und Download
geprüft. Originalbytes benötigen aktuelle Finanzleserechte. Auch ohne dieses
Recht bleiben erlaubte operative Mengen und auswählbare Belegmetadaten verfügbar;
Finanzwerte werden nicht aus alten Antworten rekonstruiert.

**Mengenänderung:** Art, externe Referenz, tatsächliches Datum, Begründung und
Original wählen und alle bisherigen Positionen ausdrücklich mit ihrer neuen
kumulierten Bruttolieferfreigabe angeben. Die Vorschau zeigt empfangene, bisher
freigegebene, neu vereinbarte und anschließend offene Mengen. Eine ausdrücklich
vereinbarte Ersatzlieferung erhöht diese Freigabe. Eine Reststornierung setzt sie
auf die schon empfangene Bruttomenge. Der native Bestellstatus zeigt anschließend
**Restmenge storniert**, nicht „vollständig geliefert“.

**Lieferantenretoure:** Eine tatsächliche Menge aus einer konkret bezeichneten
Wareneingangsposition wählen. Die Oberfläche zeigt schon retournierten und
an Geräte gebundenen Anteil, Herkunftskapazität sowie freien Lagerbestand.
Referenz, tatsächliches Rücksendedatum, Grund und Original sind erforderlich.
Die frische Vorschau enthält Lagerbezug, Rücksendemenge und – bei Finanzfreigabe –
den gewichteten auszubuchenden Lagerwert. Die Bestätigung dokumentiert die
wirkliche physische Rücksendung und bucht sie im vorhandenen Lagerjournal aus.
Sie erfindet keine Projektentnahme und keine automatische Chargenzuordnung.

Beide Aktionen benötigen nach ihrer Vorschau eine ausdrückliche Bestätigung.
Der Vorschauhash bindet unveränderte Eingaben, Bestell-/Liefer-/Änderungs-/
Retourenfassungen sowie den aktuellen Quellenhash. Weder Retoure noch Änderung
erzeugt eine Lieferantenkommunikation, Gutschrift, Zahlung, Erstattung oder
EÜR-Buchung. Eine Retoure allein erzeugt auch keine zusätzliche Lieferfreigabe.

Der vorhandene Wareneingang sendet die aktuelle `expected_amendment_revision`,
sobald der Server sie ausweist. Dadurch kann eine neue Lieferung die belegte
Mengenfreigabe nicht mit einer veralteten Bestellung umgehen. Historische
Wareneingänge, Originale und ursprüngliche Quittungen bleiben unverändert.

## Rechte, Quittungen und Wiederaufnahme

Der konkrete Bestellbezug bestimmt die Projektberechtigung. Beide Clients lesen
vor Wiederholung eines offenen Auftrags den kanonischen Bestellstand und dessen
Projekt frisch. Mengenvereinbarungen benötigen `inventory.write` und
`finance.approve`; Retouren und Originaluploads `inventory.write` und
`finance.write`, jeweils zusätzlich zum Leserecht. Neue Fachaktionen benötigen
ein aktives Materialmodul. Ein schon angenommener Originalauftrag wird unter
frischen Rechten aus der unveränderlichen Serverquittung bestätigt, auch nach
einer späteren Moduldeaktivierung oder eigenen Bestandsänderung.

Offene Aufträge behalten Pfad, Werte, Vorschauhash und Request-ID. Die
ursprüngliche Datei kann nach unbekannter Antwort nicht ausgetauscht werden.
Ein erneut geöffneter Dialog zeigt Referenz, Datum und ursprüngliche Mengen;
Base64-Dateiinhalt wird nicht als Formulartext ausgegeben. Ein Sitzungswechsel
während des Berechtigungsabrufs kann keine alten Werte unter neuer Identität
senden. Ein sicher nicht angenommener Auftrag wird nur bei entsprechendem
Servernachweis freigegeben.

Der Erfolgsvalidator prüft Bestellidentität, alte Quellenfassungen, neue
aktionsbezogene Revision, Beleghash, Vorschauhash und konkrete operative Mengen.
Eine Originalquittung darf nach Verlust von `finance.read` weiterhin preisfrei
bestätigt werden, wenn die erforderlichen Aktionsrechte noch bestehen. Eine
fälschlich als preisfrei bezeichnete Antwort mit Finanzfeldern wird abgewiesen.

## Prüfungen

| Nachweis | Ergebnis / Inhalt |
| --- | --- |
| Neue Node-Verträge | 6/6: exakte Dezimaltexte, keine Rundung, konkrete Lieferposition, vollständige Änderungen, Vorschau-/Quittungsbindung, Preisredaktion, verlorene Antwort, Rechte-/Loginwechsel und Änderungsrevision im Wareneingang |
| Node mit bestehendem Einkauf | 17/17 bestanden |
| Neue Flutter-Prüfungen | 6/6: exakte Mengen und Quellen, Originalquittung, globale/projektbezogene Wiederholung nach Rechte-, Preis- und Modulumstellung, echtes Retourenformular bis Vorschau/Bestätigung und verlorener Antwort |
| Flutter mit bestehendem Einkauf | 24/24 bestanden |
| Analyse | Neue Seite, bestehende Einkaufseite und neuer Test ohne Befund |
| Tatsächlicher Browserablauf | 1/1 bestanden: Owner-MFA/HTTP, Originalupload, Retoure, identische Quittung nach absichtlich verlorener Antwort, Ersatzfreigabe, nativer versionsgebundener Eingang, Reststornierung, bytegleicher Download und unveränderliche ursprüngliche Lieferung |

Der Browserfall verwendet 10 ursprünglich bestellte Stück, 6 empfangene Stück
und eine tatsächliche Retoure von 2 Stück: 4 behalten, weiterhin 4 offen. Eine
belegte Ersatzfreigabe erhöht die Gesamtfreigabe auf 12 und die offene Menge auf
6. Eine weitere echte Lieferung von 2 Stück bindet die neue Änderungsrevision;
eine anschließende belegte Reststornierung setzt die Freigabe auf 8: 8 brutto
empfangen, 2 retourniert, 6 behalten, 0 offen. Die erste Lieferung bleibt byte-
beziehungsweise feldgleich. Die Retourenquittung ist bei Wiederholung identisch
und es existiert weiterhin genau eine Retoure.

Desktop- und 390-Pixel-Ansicht wurden visuell geprüft. Mengentabellen behalten
lesbare Spalten und Zahlen und können innerhalb der Tabelle seitlich gescrollt
werden; die Seite selbst läuft nicht horizontal über. Der Browser läuft mit
aktiver Namespace-, PID-, Netzwerk- und Seccomp-Sandbox. Es wurden ausschließlich
synthetische Daten verwendet, keine Lieferanten angeschrieben und keine echten
Warenbewegungen oder Zahlungen ausgelöst.

Permanente Tests: `web/office/tests/purchase-changes.test.mjs`,
`web/office/tests/purchase-changes-flow.cjs`,
`app/test/business_purchase_changes_test.dart`; gemeinsame synthetische
Quell-/Vorschau-/Quittungsfixture `app/test/fixtures/purchase_changes.json`.
Logs und Screenshots: `work/verification/purchase-changes-*`.
Eine tatsächliche Windows-/iPhone-Geräteabnahme ist damit nicht behauptet.


### Wiederholung gegen den endgültigen Retouren-Backendstand

Nach den beiden unabhängigen Integritätskorrekturen wurde derselbe tatsächliche
MFA-/HTTP-Browserablauf am 03.11.2026 erneut vollständig ausgeführt und bestanden
(1/1, Prozessende 0). Die historische Quittung wird nun serverseitig gegen die
ursprünglichen Fachquellen und Journalpräfixe rekonstruiert; der bereits
vorhandene Clientablauf bestätigt weiterhin genau eine Retoure nach verlorener
Antwort, die gebundene Ersatzlieferung und die unveränderte erste Lieferung.
Es waren dafür keine weiteren Clientänderungen nötig.

Abschlussprotokoll: `work/verification/purchase-changes-browser-final.log`.
SHA-256 des Protokolls: `56ce76ced67873fd8699139a3709bf03607f69850fdac211c4677e140703ebbd`.
Synthetische Ansichten liegen unter
`work/verification/purchase-changes-browser-final-previews/`.
Der zuvor bestandene Gesamtlauf mit 848 Fluttertests wurde nicht wiederholt;
sein eigener eingefrorener Prüfsnapshot bleibt maßgeblich.
