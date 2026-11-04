# Gesamtziel: unabhängige Gegenprüfung außerhalb Lohn und Reisen

Stand: 04.11.2026. Untersucht wurde der aktuelle Arbeitsbaum in
`/workspace/Smarplan-Hofmann-Workspace`, ausgehend vom lokalen Commit
`2fdfa9f37bbbaf9e8b6fe4070be6809fe15b69c3`. Parallel laufende Lohnänderungen sind
nicht Gegenstand dieses Berichts. Die unveränderte Zieldatei wurde vollständig
gelesen; ihre Anforderungen wurden mit Runtime, Routen und vorhandenen
Abnahmefällen verglichen. Dokumenttexte wurden nicht als neue Arbeitsaufträge
ausgeführt.

Die drei empfohlenen nächsten Pakete sind **belegte Finanzübernahme zum
Buchführungsbeginn**, **vollständiger Katalogimport mit Preisgültigkeit in beiden
Clients** und **unternehmensweite, ereignisgesteuerte Regeln**. Alle drei haben
eigenständige lokale Implementierungsarbeit; fehlende produktive Zugänge
verhindern ihre Entwicklung nicht. Die Reihenfolge bewertet ihren Nutzen für
den Wechsel eines bestehenden Betriebs zur eigenen Software, nicht einen
behaupteten Prozentanteil am Gesamtziel.

## Abgleich mit den Abnahmen A–G

| Abnahme | Konkrete vorhandene Grundlage | Noch nicht dadurch erledigt |
| --- | --- | --- |
| A – Einrichtung/Rechte | Modulbedarf, manuelle Auswahl, getrennte Sichtbarkeit/Aktivierung/Rechte; feste Unternehmensinstanz und additive Mehrinstanz-Provisionierung einschließlich Tests mit getrennten Rollen/UIDs | Produktive Hosteinrichtung und Schlüsselbetrieb; neue Module müssen dieselben Grenzen einhalten. Eine gemeinsame Datenbank wird nicht als Mandantentrennung behauptet. |
| B – Anfrage bis Zahlung | `test_customer_execution_journey_pg.py`, `test_customer_finance_service_journey_pg.py` verbinden tatsächliche Domänen-/HTTP-Wege; `offline_service_report_backend_integration_test.dart` verbindet echte verschlüsselte Flutter-Erfassung mit Backend, Neustart und verlorener Antwort | Browser-Katalogübernahme ist noch nicht ausführbar. Finanzübernahme vorhandener Anfangsbestände und reale Windows-/iPhone-Abnahme bleiben offen. |
| C – Einkauf bis Service | Bestellpositionen, Teil-/Restlieferung, Entnahme, Original-/Geräteherkunft, Inventur und Service samt signiertem Bericht sind in der erweiterten B/C-Reise verbunden | Zeitabhängige Lieferantenpreise und erkennbare Importabweichungen sind nur teilweise abgebildet. Bestehende Mengenidentität ist bereits geschützt. |
| D – Personal/Abrechnung | Eigenständige laufende Lohn-/Reiseentwicklung mit eigenen Nachweisen | Bewusst nicht erneut bewertet; dieser Bericht ersetzt keine D-Abnahme. |
| E – KI/Regeln | Quellengebundene Pläne, automatische Ausführung eines vorbereiteten Plans, Freigabe/Verbot, native Versandgates, Quittungen und Restore-Sperren | Unternehmensweiter Regelumfang und selbst ausgelöste, deduplizierte Ereignisverarbeitung fehlen. Echte Bestell-/Bankadapter bleiben getrennte Anbieterarbeit. |
| F – Betrieb/Restore | Gemeinsamer Kern, Paket-/Release-/Restoreverfahren, fachliche Übergabe und lokale Provisionierungsnachweise | Neue Finanz-/Katalog-/Regelquellen benötigen eigene Restore-Nachweise; tatsächlicher Zielhost und Geräteverteilung sind gesondert zu prüfen. |
| G – Bedienbarkeit | Browser und Flutter, gerenderte WCAG-Stichproben, mobile Prüfungen und Fachabläufe | Der Browser besitzt nur Adapterstatus; vollständige menschliche Bedienprüfung sowie reale Windows-/iPhone-Prüfung fehlen weiterhin. |

Vorhandene Tests und frühere Protokolle sind hier **Referenzen**. In dieser
Gegenprüfung wurden keine Produkt- oder Gerätetests neu ausgeführt. Weder ihre
Dateiexistenz noch ältere grüne Zahlen sind eine aktuelle Gesamtabnahme.

## 1. Finanzübernahme eines bestehenden Einzelunternehmens

**Anforderung:** Gesamtziel 1, 8 und 12 verlangt Ablösung der bestehenden
Software, nachvollziehbare Liquidität sowie kontrollierte Datenübernahme. Der
bestätigte Umfang ist Einzelunternehmen/EÜR mit Ist-Versteuerung. Ein vorhandener
Betrieb beginnt am Umstiegsstichtag nicht mit erfundenen Nullbeständen.

**Aktueller Codebefund:**

- `backend/business_accounting_euer.py::_catalog` liefert je Konto ausdrücklich
  `opening_balance=None`, `balance=None`; Quellenbestand und Bericht setzen
  `opening_balances_available=False`. Browser- und Appdarstellung behandeln
  diese Werte korrekt als nicht erfasst. Es fehlt ein kanonischer Vorgang zum
  Bestätigen des Eröffnungsstands, nicht nur die Anzeige.
- Der Bankabgleich besitzt bereits echte Auszugsanfangs-/Endsalden und prüft
  deren rechnerische und zeitliche Kontinuität in
  `business_bank_reconciliation.py::preview_import` beziehungsweise der
  Berichtsaufbereitung. Diese Quellen sollen weiterverwendet werden; ein neuer
  pauschaler Banksaldo wäre unnötige Doppelerfassung.
- `EuerAccounting._prepare_asset` und `_prepare_depreciation` unterstützen neue
  lineare Anlagen. `_economic` prüft deren Datum über `_profile_dates` gegen
  den bestätigten Buchführungsbeginn. Ein vor diesem Datum angeschafftes
  Anlagegut besitzt keinen eigenen Übernahmevertrag mit ursprünglichen
  Anschaffungskosten, bereits erfolgter Abschreibung und belegtem Restbuchwert.
  Die Einschränkung steht auch ausdrücklich in `_LIMITATIONS`.
- `business_migrations.py::KINDS` enthält nur `contact`, `project`, `document`.
  Übernommene Originaldokumente bleiben bewusst `financial_effects=False`.
  Dieser sichere Archivimport darf für Eröffnungswerte nicht stillschweigend zu
  einer neuen Zahlung oder Rechnung umgedeutet werden.

**Kleinster vollständiger nächster Umfang:** Ein neues, ausdrücklich bestätigtes
Finanzübernahmepaket bindet den Buchführungsstichtag, vorhandenes Geldkonto,
Originalbeleg und Quittung. Es übernimmt Geldkonto-Anfangssalden sowie zunächst
belegte historische lineare Anlagen. Der Kontostand wird aus belegtem Anfang
und den tatsächlich vorhandenen späteren Geldbewegungen ermittelt; Anfangssaldo
und übernommene Anschaffungskosten sind keine neue EÜR-Einnahme/-Ausgabe und keine
neue Vorsteuer. Historische Anlagen übernehmen die bestätigte ursprüngliche
Basis, Inbetriebnahme, Nutzungsdauer, bereits berücksichtigte AfA und Restwert.
Abweichungen zu einer rein linearen Historie bleiben als eigener offener Fall
erkennbar. Berichtigung, Periodensperre, unveränderte alte Exporte und
Wiederherstellungsfreigabe gehören zum ersten Paket.

**Betroffene Stellen:** Neues abgegrenztes Fachmodul statt Änderung der alten
EÜR-Regel; `business_accounting_euer.py` für die zusätzliche Quellen-/Berichtssicht,
`business_bank_reconciliation.py` für belegte Auszugsreferenzen,
`business_migrations.py` nur für explizite Originalreferenzen;
`app/lib/business_accounting_euer.dart`, `web/office/accounting-euer.js`,
Unternehmensübersicht, globale API-/Schema-/Export-/Restore-Registrierung.

**Abnahme:** Synthetischer Umstieg zum 01.01.2026 mit 1.000,00 EUR belegtem
Kontostand, 119,00 EUR tatsächlichem Eingang und 59,50 EUR tatsächlichem Abgang
ergibt 1.059,50 EUR Kontostand; die 1.000,00 EUR erzeugen keinen Umsatz und keinen
EÜR-Ertrag. Ein bereits 2025 angeschafftes lineares Anlagegut behält seine
belegte Vorjahres-AfA und wird nur mit dem zutreffenden 2026-Anteil fortgeführt.
Doppelter Originalimport, gleicher Auftrag nach Antwortverlust, konkurrierende
Eröffnung, widersprüchlicher Auszugsanschluss, fehlender Restwert, spätere
Berichtigung und echter PostgreSQL-Restore benötigen unabhängige Fälle.

**Abgrenzung:** Offene Alt-Forderungen/-Verbindlichkeiten und deren spätere
Ist-Versteuerung sind ein anschließender eigener Übernahmevertrag, der bereits
bei der Paketstruktur berücksichtigt werden muss. GWG, Veräußerung,
degressive/Sonder-AfA und weitere steuerliche Fälle bleiben tatsächliche
Codearbeit. Vor deren Umsetzung sind aktuelle amtliche Regeln und erwartete
Fachwerte separat zu prüfen. Echte Anfangsdaten und fachliche Betriebsfreigabe
sind spätere notwendige Eingaben, keine Voraussetzung für synthetische
Implementierung und Tests.

## 2. Katalogübernahme mit Preisgültigkeit und vollständiger Browserbedienung

**Anforderung:** Gesamtziel 7 nennt ausdrücklich Preisgültigkeit,
Einheitenabweichungen, Importfehler und nachvollziehbare Aktualisierung;
Abnahmen B/C/G verlangen einen benutzbaren Ablauf in den vorgesehenen Clients.

**Aktueller Codebefund:**

- `business_adapters.py::parse_catalog` akzeptiert im eigenen CSV-v1 exakt
  `code;name;unit;cost_price_net;unit_price_net;tax_rate`. Gültig-ab/-bis,
  Lieferantenpreisrevision und zeitlich auswählbarer Preis sind nicht Teil des
  Vertrags. DATANORM ist ausdrücklich nur ein begrenztes A14-Neuanlageprofil.
- `import_data` friert Zeilen, Hashes und aktuelle Zielrevisionen ein.
  `apply_catalog` prüft Konkurrenz und schreibt aktuelle Artikelrevisionen.
  Diese vorhandenen Schutzmaßnahmen sind keine Lücke. Ohne Gültigkeitsmodell
  kann ein zukünftiger Preis aber nur sofort als aktueller Artikelpreis
  übernommen oder außerhalb des Systems zurückgehalten werden.
- `Documents._require_stock_identity` verhindert schon heute Änderungen von
  Einheit/Artikelart nach Lagerhistorie oder freigegebener Bestellung. Die
  Behauptung einer ungeschützten Bestandsumdeutung wäre daher falsch. Es fehlt
  vor allem die verständliche Differenz-/Konfliktauflösung vor Übernahme sowie
  ein ausdrücklicher neuer Artikel bei tatsächlich anderer Mengeneinheit.
- `app/lib/business_adapters.dart` bietet Dateiübernahme, Vorschau und
  Übernahmebestätigung. `web/office/office.js::adapterDialog` zeigt dagegen nur
  eine Statusliste; dort existiert kein ausführbarer Katalogdateiimport.

**Kleinster vollständiger nächster Umfang:** Additiver eigener CSV-v2-Vertrag
mit belegter Preisgültigkeit; v1 bleibt unverändert les-/wiederholbar.
Versionierte Preisquellen werden getrennt von Lageridentität gespeichert.
Vorschau zeigt Neuanlage, unverändert, Preisänderung, Gültigkeitsüberschneidung,
Namens-/Einheitsabweichung und den betroffenen Artikel. Übernahme bindet exakt
diese Entscheidungen und Quellenrevisionen. Beide Clients erhalten dieselbe
Datei-/Vorschau-/Bestätigungs-/Historienkette. Angebot/Bestellung bindet die am
ausdrücklich gewählten Stichtag gültige Preisrevision; vorhandene Belege bleiben
unverändert. Kein stiller Rückfall auf einen abgelaufenen Preis.

**Betroffene Stellen:** `business_adapters.py`, `business_documents.py`
(Artikel-/Preisquelle), `business_pricing.py`, `business_purchasing.py`, eigener
Browser-Katalogbaustein statt bloßer Statusliste, `business_adapters.dart` und
die beiden Artikel-/Belegeditoren. Neue Preisquellen müssen in Export,
Integritätsprüfung und Restore aufgenommen werden.

**Abnahme:** Preis 10,00 EUR bis 30.11. und 12,00 EUR ab 01.12.; Novemberangebot
bleibt nach Dezemberimport auf der ursprünglichen Revision. Überlappende
Zeiträume, Preis ohne eindeutige Gültigkeit, bereits veraltete Vorschau und
Einheitenwechsel ST → Packung bei Bestand werden verständlich erkannt.
Neuer Artikel mit ausdrücklich anderer Lageridentität ist möglich, eine
stille Umrechnung nicht. Derselbe bestätigte Import nach verlorenem ACK erzeugt
keine zweite Preisrevision. Echter Browserablauf mit Datei, Vorschau,
Korrektur, 390-px-Ansicht und eingeschränkter Rolle ergänzt den vorhandenen
nativen Weg. Aktuelle Lieferanten-/DATANORM-Verträge bleiben separate Erweiterung;
der lokale CSV-Vertrag benötigt keinen produktiven Anbieterzugang.

## 3. Unternehmensweite Regeln und belegte Ereignisverarbeitung

**Anforderung:** Gesamtziel 10 verlangt Unternehmensregeln mit Auslöser,
Bedingung, betroffenen Vorgängen, Zuständigkeit und zulässiger Aktion. Die
vorhandene automatische Ausführung eines vorbereiteten Plans erfüllt einen
wichtigen Teil; sie deckt noch keine selbst ausgelöste Unternehmensregel ab.

**Aktueller Codebefund:**

- `business_assistant_rules`, `contexts` und `plans` verlangen ein konkretes
  `project_id NOT NULL`. `Assistant._rules` selektiert genau dieses Projekt;
  die GET-Routen für Regeln/Pläne/Chats verlangen `project_id`. Eine einmalige
  unternehmensweite Regel für bestehende und künftige Projekte fehlt.
- Die Auslöser `payment.overdue`, `task.overdue` und `cost.threshold` werden
  durch `_evaluated_policy` bei der Plan-/Chatvorbereitung geprüft.
  `create_plan` und der Chatabschluss können dann `_automatic` aufrufen.
  Ein Ereignis-/Zeitplan-Worker für diese Auslöser ist nicht registriert.
- Native Versandgates, erneute Rechteprüfung, Planhash-Freigabe und gebundene
  Ausführungsquittung sind bereits implementiert. Sie sollen von neuen
  Auslösern wiederverwendet und nicht durch einen zweiten Versandweg ersetzt
  werden. `supplier.order` und `payment.execute` bleiben ausdrücklich
  `adapter_blocked`, solange der echte ausführende Vertrag fehlt.

**Kleinster vollständiger nächster Umfang:** Additiver Regelvertrag mit
Unternehmensgeltung und ausdrücklich ausgewählten Projekt-/Vorgangsfiltern.
Regelkonflikte erhalten eine dokumentierte Vorrangregel; bestehende Verbote
dürfen nicht durch eine breitere Automatik aufgehoben werden. Ein begrenzter
lokaler Worker leitet aus kanonischen Fälligkeiten/Fristen konkrete Ereignisse
ab, speichert Ereignisidentität und Quellstand und erzeugt daraus bestehende
Aktionspläne. Zunächst sind interne Aufgaben und Freigabevorlagen ohne
Außenwirkung ausreichend; konfiguriertes Auto darf diese internen Aktionen
ausführen. Externe Aktionen bleiben am bestehenden Gate und an ihren konkreten
Freigaben gebunden. Der Trigger benötigt kein Sprachmodell und keinen
kostenpflichtigen Modellaufruf.

**Betroffene Stellen:** Neue Ereignis-/Regelmodulversion,
`business_assistant.py::_rules`, `_evaluated_policy`, `_insert_plan`,
`create_plan`, `business_assistant_sources.py`, eigener Worker unter
`backend/online`, Betriebs-/Timerkonfiguration, `web/office/assistant.js`,
`app/lib/business_assistant.dart`; Schema/Export/Restore und Instanzgrenzen.

**Abnahme:** Eine am 10.11. fällige synthetische Rechnung erzeugt am 11.11.
genau eine zuständige Aufgabe. Zwei konkurrierende Worker, Neustart und
Wiederholung erzeugen kein Duplikat. Zahlung vor Claim, Rechteentzug,
Regeländerung, gesperrtes Modul und Restore verhindern eine veraltete Aktion.
Eine unternehmensweite Regel gilt auch für ein später angelegtes freigegebenes
Projekt, verrät aber keine Daten eines ausgeschlossenen Projekts oder der
zweiten Firma. Freigabe und Verbot gewinnen wie dokumentiert; manipulativer
Dokumenttext ändert weder Trigger noch Aktion. Zeit-/Kalendergrenzen und die
betriebliche Zeitzone werden ausdrücklich getestet.

**Annahme:** Die Erweiterung zu selbst ausgelösten Regeln ist eine konkrete
Auslegung des gewünschten Automatisierungsumfangs, keine Behauptung, dass die
bisherige Plan-Automatik funktionslos wäre. Die genaue Auswahl erlaubter
produktiver Regeln bleibt konfigurierbar; dieser Entwicklungsplan aktiviert
keinen unbeaufsichtigten Versand.

## Weitere Befunde und bewusste Nichtbehauptungen

Eine gemeinsame Kunden-/Projekt-Kommunikationschronik bleibt ein sinnvoller
weiterer Baustein: `business_sales.py::activities` ist an eine Verkaufschance
gebunden, `inquiries.py` verwaltet eingehende Anfragen, die Kontaktansicht bietet
separate Chancen-/Servicewege. Ein vollständig kanalübergreifender Verlauf ist
damit nicht belegt. Seine Lesesicht könnte vorhandene Quellen ohne neue
Providerzugänge verbinden; tatsächliche Gmail-/WhatsApp-/Kalenderverbindungen
benötigen weiterhin ihre jeweiligen bestätigten Verträge.

Nicht erneut als fehlend bewertet wurden die inzwischen vorhandenen
Portalannahmen, Bestellteilmengen, Geräteherkunft, Inventur, Servicekorrekturen,
Offline-Serviceprotokolle, Rechnungsketten, EÜR-Geldflussbindung, Bankabgleiche,
Unternehmensexporte und Provisionierung. Mehrere Aussagen der Bestandsaufnahme
vom 02.11. beschreiben den Ausgangsstand und sind für diese Bereiche überholt.

Tatsächliche Geräteinstallation, Anbieterzugänge, unabhängiger Sicherheitstest,
fachliche Steuer-/Lohnprüfung und produktive Freigaben bleiben eigene Nachweise.
Die hier gefundenen drei Implementierungspakete dürfen nicht pauschal unter
diesen externen Abhängigkeiten abgelegt werden.
