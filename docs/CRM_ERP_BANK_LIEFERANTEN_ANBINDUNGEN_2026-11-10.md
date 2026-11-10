# Gewählte Banken und Lieferanten – Vertrag und Umsetzungsstand

Direkte Nutzerentscheidung vom10.11.2026: **Qonto, Sparkasse, Amex** sowie
**Granzow, Alexander Bürkle, Loxone, Voltus**. Diese Entscheidung ersetzt die
bisher offene Auswahl. Das Original `CRM_ERP_Gesamtziel.txt` bleibt unverändert.
R07.05, R08.03 und R12.03 bleiben bis zu ihren tatsächlichen Gesamtnachweisen offen.
Genaue Sparkasse und Amex Business/Corporate sind noch angefragt. Zugangsdaten
gehören ausschließlich in geschützte Server-/Umgebungseinstellungen.

| Anbieter | Tatsächlich geprüfte offizielle Quelle | Aktueller Umfang / verbleibender Schritt |
|---|---|---|
| Qonto | [V2-Organisation](https://docs.qonto.com/api-reference/business-api/organization-accounts/organizations/retrieve-the-authenticated-organization-and-list-bank-accounts), [Transaktionen](https://docs.qonto.com/api-reference/business-api/transactions-statements/transactions/list-transactions), [Pagination](https://docs.qonto.com/api-reference/business-api/introduction/pagination), [Migrationsfrist15.11.](https://docs.qonto.com/guides/migrations/deprecated-organization-endpoints), [API-Key-Vertrag](https://docs.qonto.com/guides/authentication/api-key) | Serverseitiger Leseabschnitt mit beiden Clients. Eigener API-Key-Zugang additiv zum Betreiber-OAuth-Token; Geheimnis nur im privaten Serverfile. Echter Zugang und Providerabnahme fehlen. |
| Sparkasse | Sparkasseninstitut und tatsächlicher Zugangsweg noch zu bestimmen | Bank-/Institutsname abwarten; konkreten FinTS-/EBICS-/lizenzierten Kontoinformationsweg samt Vertrag prüfen. Keine gemeinsame erfundene Sparkassen-API. |
| Amex | [Offizielles Open-Banking-Angebot](https://developer.americanexpress.com/open-banking) | Account-/Transaction-Zugang nennt regulierte AISPs, ausgewählte Produkte/Emittenten und gesonderten Spezifikationszugang. Das belegt keinen frei nutzbaren deutschen Zugang. Business/Corporate und tatsächlicher Vertrag fehlen. |
| Granzow | [Schnittstellenangebot](https://www.granzow.de/schnittstellenloesungen) | UGL, IDS, OCI und DatanormOnline2.0 werden angeboten. Echte Vertragsversion, Partnerendpunkt, Einwilligung und Testzugang separat prüfen. Vorhandenes begrenztes CSV-/A14-Profil ist keine vollständige IDS-/UGL-Anbindung. |
| Alexander Bürkle | [Offizielle Integrationspartner](https://web.alexander-buerkle.com/de/ganzheitliche-loesungen/ecommerce-schnittstellen/ecommerce-schnittstellen-partner/integrationspartner) | IDS/OCI/cXML und EDI-Angebote recherchiert; tatsächliches Format und Partnerfreigabe fehlen. |
| Loxone | [Offizielle Downloads](https://www.loxone.com/dede/support/downloads/) | EUR-/CHF-CSV-Preislisten sowie DATANORM4/5 einschließlich kundenindividueller Preise angeboten. Tatsächlichen Dateivertrag prüfen; keine Miniserver-Geräte-API als Lieferantenanbindung ausgeben. |
| Voltus | [Offizielle IDS-Einrichtung](https://service.voltus.de/hc/de/articles/52144613596817-Einrichtung-IDS-Schnittstelle) | IDS2.5 unter `https://www.voltus.de/ids-connect` und B2B-Geschäftskonto ausdrücklich dokumentiert. Vollständiger IDS-Vertrag, Rückkanal und kontrollierter Partnerzugang noch umzusetzen/abzunehmen. |

## Neuer Qonto-Lesevertrag

`backend/online/integration_qonto.py` und `bank_feeds_service.py` verwenden
ausnahmslos GET an `https://thirdparty.qonto.com/v2/organization` und
`/v2/transactions`. Keine veraltete slug-basierte Organisation. Keine frei
wählbaren URLs, Weiterleitungen, Zahlungen, Bestellungen oder Finanzschreibwege.
Die vorhandene Transportfrist gilt gemeinsam für Kontoabruf und Seiten.

Das ausdrücklich konfigurierte Unternehmen muss mit Qontos tatsächlicher
Organisation übereinstimmen. Genau eine aktive EUR-IBAN muss zur bestehenden,
aktuellen Smartplan-Bankbindung passen. Soweit Qonto Konten-IDs liefert, müssen
diese übereinstimmen; die offizielle Organisationsbeispielantwort ohne Konto-ID
wird über die dokumentierte IBAN-Auswahl unterstützt. Fremde und extern
verbundene Kontoumsätze werden nicht übernommen.

Gelesen werden **Umsatzänderungen nach `updated_at`**, mit allen vier ausdrücklich
angeforderten Status pending/completed/declined/reversed. Ein Zeitraum ist aus
UTC-Zeitpunkten einschließlich Beginn und ausschließlich Ende definiert,
höchstens31 Tage. Eine von Qonto einschließlich gelieferte exakte Endgrenze
wird herausgefiltert. Das ist kein Buchungs-/Valutazeitraum. Reversed erzeugt
keinen erfundenen Rückzahlungsbeleg. Auch früher gebuchte Umsätze können später
geändert werden; die Oberfläche erklärt diesen Unterschied.

Maximal1000 Datensätze in100er-Seiten; jede Seite höchstens2MiB, gemeinsamer
Abruf höchstens8MiB. Fehlende, widersprüchliche, doppelte oder während des
Abrufs geänderte Seitenzählungen werden abgewiesen. Keine Teilmenge wird als
vollständig ausgegeben. Centwerte sind echte begrenzte Ganzzahlen; zusätzlich
gelieferte Dezimalwerte müssen exakt übereinstimmen. Keine Float-Rundung,
USt-Ableitung aus Kategorien oder erfundene Valutatage. Nur ausdrücklich
benötigte Text-/Identitätsfelder werden an Clients weitergegeben.

Aktueller Saldo vor/nach Abruf ist eine Anbieterbeobachtung, kein belegter
Auszugsanfangs-/Endsaldo. Der Vertrag trägt ausdrücklich
`complete_statement:false`, `atomic_snapshot:false`, `financial_changes:false`.
Die vorhandenen CSV-Originale, Zahlungen, Bankzuordnungen und EÜR-Prüfstände
bleiben erhalten. Dieser Leseabschnitt speichert keinen unveränderlichen
Provideroriginalbestand und besitzt noch keine Feed-zu-Auszug-Übernahme.

Authentifizierung und globale Bank-/Finanz-/Buchführungsleserechte werden vor
und nach der Anbieterkommunikation frisch geprüft. Kein SQL-/Office-Lock bleibt
während der Anbieterkommunikation gehalten. Abmeldung, Rechteentzug,
Zugangsdatenwechsel, Kontorevision oder geänderte Bankbindung verwerfen das
Ergebnis. Offline-Berechtigungen erlauben diesen neuen Bankabruf nicht.

## Bedienung und Betreiberkonfiguration

Nach Aktualisierung des Servers erscheint unter **Finanzen → Bankabgleich →
Qonto-Umsatzänderungen lesen** die neue Ansicht in Browser und nativer App.
Ohne serverseitige Einrichtung wird dies ausdrücklich angezeigt. Bestehender
CSV-Bankabgleich bleibt verfügbar. Zeitraum wählen, Umsätze lesen, Status
beachten; aus dieser Ansicht wird keine Buchung erstellt.

Geschützte Serverkonfiguration:

- `SMARTPLAN_QONTO_ORGANIZATION_ID`: tatsächliche Qonto-Organisations-UUID.
- `SMARTPLAN_QONTO_ACCOUNT_ID`: bestehende kanonische Smartplan-Geldkonto-ID,
  mit aktuell bestätigter aktiver Bankbindung/IBAN.
- `SMARTPLAN_QONTO_TOKEN_FILE`: absoluter Pfad zu einem regulären privaten
  File mit dem OAuth-Access-Token bzw. dem Secret-Key im ausdrücklichen
  Eigenkonto-Modus; keine Symlinks, keine Gruppen-/Fremdrechte,
  Eigentümer Dienstbenutzer oder root. Inhalt wird pro Abruf erneut gelesen.
- `SMARTPLAN_QONTO_AUTH_MODE`: `own_account_api_key` für das eigene Unternehmen
  oder `oauth_access_token` für einen vorhandenen Betreiber-OAuth-Token.
  Ohne Angabe bleibt aus Kompatibilitätsgründen der veröffentlichte OAuth-Modus.
  Der Modus wird niemals aus einem Geheimnis geraten.
- `SMARTPLAN_QONTO_LOGIN`: ausschließlich im Eigenkonto-Key-Modus der tatsächliche
  Qonto-Organisations-Sign-in. Im OAuth-Modus muss diese Angabe leer bleiben.

Beide Authentifizierungsverträge sind primär belegt. Im Eigenkonto-Modus lautet
der Header exakt `Authorization: sign-in:secret-key`, ohne Bearer/Basic und ohne
Base64. Im OAuth-Modus bleibt `Bearer access-token` mit `organization.read`.
Der Eigenkonto-Key ist für die Automatisierung des eigenen Qonto-Unternehmens
gedacht. Eine Integration im Auftrag fremder Kunden benötigt laut Qonto OAuth;
diese Begrenzung wird nicht durch ein Key-Profil umgangen. Der erfolgreiche
Abruf muss in beiden Modi weiterhin Organisations-UUID und gebundene IBAN
bestätigen. Ein ungeprüfter Gleichheitsvertrag zwischen Sign-in und einem
Organisationsfeld wird nicht erfunden. Schlüsselwechsel oder Anmeldungsart-/
Sign-in-Wechsel während des Abrufs verwerfen das Ergebnis.

OAuth-Einwilligungs-/Token-Erneuerungsflow und Sandbox werden in dieser Version
nicht angeboten. Abgelaufene Freigaben werden sichtbar abgewiesen. Eine
automatische OAuth-Erneuerung ist kein vorgetäuschter Bestandteil des Key-Zugangs.
Keine Geheimnisse in Repository,
Browserdaten, Befehlsausgaben, Fehlermeldungen oder Chat eingeben.

Die aktuelle Cloud hat keine Bankgeheimnisse und erlaubt die neuen Provider-
Zielhosts nicht. Es wurde kein echter Bankabruf, Lieferantenversand, Kauf,
Liveupdate oder TestFlight-Upload ausgelöst. Kontrollierte Providerantworten
sind ausschließlich ausdrücklich ausgewählte Testfixtures.

## Prüfnachweis und nächste Arbeit

Rohdaten und unveränderte Erstfehler stehen unter
`docs/evidence/qonto-readonly-2026-11-10/manifest.json`.
Die getrennten tatsächlichen Ergebnisse werden erst nach jeweiligem Abschluss
eingetragen. Vorhandene erfolgreiche V14-Gesamtprüfungen beziehen sich auf91fa18b,
nicht automatisch auf den neuen Qonto-Quellstand.

Danach: echter Qonto-Einwilligungs-/Erneuerungsweg und Providerabnahme,
nachgewiesener Auszugs-/Originalimport in den bestehenden Bankabgleich;
instituts-/produktgebundene Sparkassen-/Amex-Verträge; vollständiger
Lieferantenvertrag und additive Katalog-/IDS-Übernahme für die gewählten
Lieferanten. Bestellungen und echte Meldungen bleiben ausdrückliche Vorgänge.
Verbleibende Buchhaltungs-/Lohn-, Geräte-, Betriebs- und Fachabnahmen aus dem
Gesamtziel werden dadurch nicht entfernt oder pauschal erledigt gemeldet.
