# Angebotsannahme und Kundenportal: Plan und Abgrenzung

Stand: 02.11.2026. Ursprüngliche Quellprüfung auf Basis `64bdc26`.
Die folgenden Planungsabschnitte erhalten diese damalige Bestandsaufnahme;
sie sind für sich kein Implementierungs- oder Abnahmenachweis. Der inzwischen
entwickelte Umfang steht in [CRM_ERP_PORTAL.md](CRM_ERP_PORTAL.md),
ausgeführte Prüfungen im [Fortschrittsbericht](CRM_ERP_FORTSCHRITT.md) und im
ergänzten Nachweisabschnitt unten. Der Plan konkretisiert
R05.04/R05.05 und einen Teil von Abnahme B aus
[CRM_ERP_Gesamtziel.txt](../CRM_ERP_Gesamtziel.txt). Die Nutzerentscheidungen
**Einzelunternehmen mit EÜR** sowie **reguläre Mitarbeiter und Minijobs** bleiben
bestehen; sie werden durch diesen unabhängigen Portalabschnitt nicht geändert.

## Vorhandene Grundlage und Modellgrenze

| Vorhandener Baustein | Tatsächlicher Vertrag und Folge |
| --- | --- |
| `backend/business_documents.py:61`, `:794` | Jeder kaufmännische Beleg benötigt bereits ein Projekt. `project_id` ist NOT NULL; `create()` übernimmt dessen Kundenbindung. Ein Angebot ohne Projekt ist derzeit nicht modelliert. |
| `backend/business_documents.py:825` | `convert()` kann ein Angebot in einen Auftragsbestätigungsentwurf umwandeln. Es verwendet dasselbe Projekt und erzeugt weder ein neues Projekt noch einen Annahmenachweis. Neue Request-IDs können weitere Umwandlungen erzeugen. |
| `backend/business_documents.py:112`, `:935`, `:1286` | Finale Belege und Archive sind unveränderlich. Nummern, Inhalts-/PDF-Hashes und Versionshistorie werden geprüft. Der bestehende Dokumentstatus kennt nur `draft` und `final`. |
| `backend/business_documents.py:979` | Die vorhandene einfache Unterschrift wird durch einen internen Benutzer mit Dokument-/Finanzrechten erfasst. Sie ist keine Kundenidentität und kein eigenständiger Annahme-/Ablehnungsprozess. |
| `backend/business_documents.py:623`, `:929`, `:1168` | Die interne JSON-Darstellung enthält auch Einstandspreise, Kalkulations-/Aufmaß-/Zeitquellen und Ausstellereinstellungen. Das generierte Original-PDF enthält verkaufsseitige Belegwerte. Interne JSON-Antworten dürfen nicht unverändert an Kunden gelangen. |
| `backend/core.py:45`, `:459`; `backend/online/web.py:357` | Es gibt ausschließlich interne Rollen. Allgemeine API-Routen authentifizieren mit Office-Sitzungen und internen Projektzuweisungen. Eine weitere interne Benutzerrolle ist kein ausreichend enges Kundenportal. |
| `backend/inquiries.py:491`, `backend/core.py:474` | Anfrageübernahme und Projektanlage existieren, sind aber keine Angebotsannahme. Die Anfrageübernahme erzeugt das Projekt bereits vor dem heutigen Angebot. |
| `backend/online/web.py:157`, `:177`; `deploy/hetzner/online/Caddyfile:22` | Fester HTTPS-Host, strenge Header und eine ausdrückliche Browserdatei-Liste sind vorhanden. `/office/*` und `/api/v1/*` werden bereits durch den Online-Dienst geführt. |
| `backend/online/restore.py:67`, `:86` | Der Restore kennt derzeit nur die vorhandenen Fachmodule und eine feste Liste von Sitzungstabellen. Neue Portalzugänge müssen ausdrücklich in die Wiederherstellungsbereinigung aufgenommen werden. |

Der erste Ablauf verwendet deshalb ein bestehendes Kundenprojekt, veröffentlicht
ein finales Angebot, dokumentiert die Kundenerklärung und erzeugt nach einer
gesonderten internen Bestätigung genau einen Auftragsbestätigungsentwurf im
selben Projekt. Die finale Projektbindung des Angebots wird nicht geändert.

Der wörtliche Ablauf „erst Angebot, danach neues Projekt erzeugen“ bleibt eine
eigene Modellaufgabe. Dafür wären ein vorgelagerter Verkaufsvorgang oder ein
ausdrücklich gestalteter Übergang vom Angebotsprojekt zum Ausführungsprojekt
nötig. Ein zweites Projekt oder eine neue Projektkennung darf nicht unbemerkt
als Nebenwirkung der Kundenentscheidung entstehen. Der erste Portalabschnitt
wird deshalb nicht als vollständige Abnahme B bezeichnet.

## Erster zusammenhängender Funktionsumfang

1. Ein berechtigter interner Benutzer prüft ein **finales Angebot**, dessen
   Kundenzuordnung, Empfänger, Original-PDF und zeitliche Gültigkeit. Er gibt
   diese konkrete Fassung ausdrücklich für einen Kundenportalzugang frei.
2. Der Zugriff gilt für genau dieses Angebot und den ausgewählten
   Kundenprincipal. Ein manuell weiterzugebender Zugangslink wird erzeugt;
   die Anwendung versendet keine E-Mail und behauptet keinen Versand.
3. Der Kunde öffnet eine eigenständige Browserseite, sieht die freigegebenen
   Verkaufswerte und kann das unveränderte Original-PDF herunterladen.
4. **Annehmen** und **Ablehnen** sind getrennte ausdrückliche Aktionen. Für die
   Annahme werden konkrete Angebotsfassung, Gesamtbetrag, erklärter Name und
   eine eindeutige Bestätigung angezeigt beziehungsweise erfasst. Seitenaufruf,
   Download und Anmeldung erzeugen keine Entscheidung.
5. Eine unveränderliche Erklärung hält Angebotshashes, Kundenprincipal,
   Wortlautversion der Erklärung, Entscheidung und Serverzeit fest. Die
   Oberfläche bestätigt die gespeicherte Erklärung, keine Zahlung und keine
   qualifizierte elektronische Signatur.
6. Intern sind Erklärung und Quelle einsehbar. Eine eigene Aktion übernimmt
   das angenommene Angebot in einen Auftragsbestätigungsentwurf. Sie stellt
   keine Rechnung aus, sendet nichts und bucht keine Zahlung.
7. Ein berechtigter interner Benutzer kann Portalzugänge widerrufen. Bereits
   dokumentierte Entscheidungen und Belegarchive bleiben erhalten.

Noch nicht in diesem Abschnitt: allgemeiner Kundenaccount mit selbständiger
Wiederherstellung, ein Kundenverzeichnis aller Projekte, freier Dateiaustausch,
Projektfortschrittsfreigaben, externe Identitätsprüfung und ein Signaturdienst.
Das erste Portal ist ausdrücklich auf freigegebene Angebote beschränkt.

## Identität, Zugang und Geheimnisse

Eigene **Kundenprincipals, Freigaben und Sitzungen** werden additiv modelliert.
Sie gehören nicht in `users`, `assignments`, `sessions` oder die internen
Office-/Offline-Tokenwege. Ein Kundenprincipal verweist auf den bestehenden
Kunden und beschreibt den vorgesehenen Empfänger. Er beweist noch keine
amtlich oder anderweitig extern verifizierte Identität.

Für diesen ersten Umfang ist ein geheimer, auf genau ein Angebot begrenzter
Zugangslink vorgesehen. Der Server erzeugt mindestens 32 kryptografisch
zufällige Bytes; in der Datenbank liegt ausschließlich dessen Hash. Der
Link trägt das Geheimnis im URL-Fragment, nicht in Pfad oder Query. Die
Portal-JavaScript-Datei entfernt das Fragment sofort aus der Browserhistorie
und übermittelt es nur im JSON-Body an den eigenen Server. Keine Geheimnisse
in Audittexten, Referrern, Fehlermeldungen oder Ergebnisbelegen speichern.

Der Link wird bei seiner Erstellung einmal angezeigt. Ein wiederholter
identischer Erstellungsauftrag liefert denselben Freigabebeleg, aber kein
erneut auslesbares Geheimnis. Bei verlorener Erstellungsantwort wird die
vorhandene Freigabe sichtbar gemacht und ausdrücklich widerrufen/ersetzt.
Ein Retry darf keinen zweiten unbemerkten Zugang erzeugen.

Der Zugangslink ist bis Ablauf oder Widerruf erneut nutzbar, um eine kurze
Portalsitzung zu öffnen. Er ist daher **kein einmaliger Aktivierungscode**.
Vorgeschlagene erste Grenzen: sieben Tage Freigabedauer, maximal 30 Tage nach
ausdrücklicher Wahl, 30 Minuten Sitzungsdauer und begrenzte gleichzeitige
Sitzungen je Freigabe. Der genaue öffentliche Vertrag wird in Tests fixiert.
Die Einladung kann erneut geöffnet werden, falls eine Sitzungsantwort verloren
geht; eine Anmeldung selbst hat keine kaufmännische Wirkung.

Portal-Sitzungstokens erhalten einen eigenen Präfix und werden nur an
`/api/v1/portal/*` akzeptiert. Sie liegen im Browser nur im Arbeitsspeicher.
Interne Bearer, Offline-Gerätezugänge und Portaltokens dürfen wechselseitig
keinen Zugang eröffnen. Kein Cookie und keine implizite Wiederverwendung einer
Office-Sitzung. Schreibende Portalrouten verlangen JSON und den exakten
konfigurierten HTTPS-Origin; CORS wird nicht für fremde Seiten geöffnet.

Jeder Zugriff prüft frisch: Sitzung, Ablauf, Principalstatus, Freigabestatus,
Kundenbindung, vorhandenen/aktiven Kunden, gegebenenfalls dessen Löschstatus,
Projekt-/Kundenbindung der Quelle und beide Archivhashes. Eine Änderung des
Projektkunden sperrt eine alte Freigabe bis zur internen Klärung. Widerruf
wirkt auch auf bestehende Sitzungen und Wiederholungsantworten.

Anmeldung und Entscheidungen erhalten begrenzte Datenbank-Ratenzähler; diese
werden auch bei fehlgeschlagenen Versuchen wirksam und haben kurze
Aufbewahrungszeiten. Fehlermeldungen dürfen keine fremden Kundendaten oder
vorhandenen Angebotskennungen verraten. Die feste Unternehmensinstanz wird
weiterverwendet; ein vom Client gesendetes Unternehmen schaltet keine Datenbank
oder Berechtigungsdomäne um.

Der Besitz eines Zugangslinks und ein eingegebener Name dokumentieren die
Zugangsnutzung und eine Erklärung. Sie belegen keine extern verifizierte
Vertretungsberechtigung, keine QES und nicht automatisch sämtliche rechtlichen
Voraussetzungen eines Vertrags. Fachliche Formulierungen, Pflichtinformationen
und der zugelassene produktive Anwendungsfall brauchen vor Freigabe eine
gesonderte Prüfung. Entwicklung und synthetische Tests sind davon unabhängig.

## Additives Datenmodell

Ein neues Modul `business_portal` erhält eine eigene registrierte Migration.
Die festgeschriebenen DDL-Definitionen vorhandener Module bleiben unverändert.

| Neue Datengruppe | Wesentliche Bindung und Zweck |
| --- | --- |
| Principals | ID, bestehende Kunden-ID, Empfängerbezeichnung, Aktivstatus/Revision und interner Ersteller; keine Office-Rolle |
| Angebotsfreigaben | Principal, Angebot, Projekt/Kunde, finale Revision, Inhalts-/PDF-Hash, öffentliche Positivlisten-Darstellung, Ablauf, Geheimnishash und Ersteller |
| Widerrufe | Unveränderlicher Widerruf je Freigabe mit internem Akteur, Zeitpunkt und Grund; keine Löschung der ursprünglichen Freigabe |
| Portalsitzungen | Tokenhash, Freigabe/Principal, Ausgabe-/Ablaufzeit; nur vergängliche Authentifizierungsdaten |
| Kundenentscheidungen | Höchstens eine abschließende Entscheidung je Angebot, gebunden an freigegebene Hashes, Principal, erklärten Namen, Erklärungsversion und Serverzeit |
| Übernahmen | Höchstens eine Portalübernahme je angenommenem Angebot, mit Entscheidungs-ID, Auftragsbestätigungsentwurf und bestehendem Projekt |
| Wiederholungsbelege | Interne Aufträge an Benutzer-ID, Kundenerklärungen an Principal/Freigabe gebunden; Payloadfingerabdruck und Ergebnisreferenz ohne Geheimnis |
| Missbrauchsbegrenzung | Kleine kurzlebige Ratenzähler; keine dauerhafte vollständige IP-Historie |

Freigaben, Widerrufe, Entscheidungen, Übernahmen und ihre Ergebnisbelege sind
anhängende Historie. Die PostgreSQL-Laufzeitrolle erhält hierfür nur
SELECT/INSERT. Schutztrigger müssen auf SQLite neben UPDATE/DELETE auch
`INSERT OR REPLACE` über alle eindeutigen Schlüssel abweisen. Sitzungen und
Ratenzähler bleiben gezielt bereinigbar. Integritätsprüfungen gleichen Quellen,
Hashes, Kundenbindungen und Übernahmeziele ab. Kundenereignisse bekommen eigene
Principalnachweise; `Office.audit()` wird nicht mit einem erfundenen internen
Benutzer oder einem Owner-Ersatz aufgerufen.

`accepted`/`declined` liegen ausschließlich in der neuen Entscheidungshistorie.
Der Status des ursprünglichen kaufmännischen Belegs bleibt `final`.
Annahmeänderungen oder neue Verhandlungen benötigen einen ausdrücklich neuen
fachlichen Vorgang; keine versteckte Umschaltung einer bestehenden Erklärung.

## API und Rechte

Die folgenden Pfade sind der vorgeschlagene neue Vertrag, keine vorhandenen
Endpunkte. Interne Pfade liegen unter `/api/v1/business`, Kundenpfade unter
`/api/v1/portal` und werden vor dem allgemeinen Office-Dispatcher behandelt.

| Methode und relativer Pfad | Berechtigung und Wirkung |
| --- | --- |
| `POST /portal/grants` intern | Neues enges Recht `portal.manage` plus `finance.read` im Quellprojekt; finale Quelle, Empfänger und Ablauf ausdrücklich bestätigen; Link nur einmal zurückgeben |
| `GET /portal/grants?offer_id=…` intern | Dieselben Quellrechte; Freigabemetadaten, Status und Entscheidung ohne Geheimnisse |
| `POST /portal/grants/{id}/revoke` intern | Frische `portal.manage`-/Quellrechte; idempotenter Widerruf, auch bei deaktiviertem Fachmodul erreichbar |
| `POST /portal/offers/{id}/adopt` intern | `portal.manage`, `finance.write` und `projects.manage` im Quellprojekt; angenommene Hashfassung ausdrücklich in einen Entwurf übernehmen |
| `POST /sessions` öffentlich | Freigabe-ID und Geheimnis prüfen, begrenzte Portalsitzung öffnen; kein Office-Bearer |
| `POST /logout` Kunde | Portalsitzung beenden |
| `GET /offer` Kunde | Ausschließlich das durch die Sitzung freigegebene Angebot als Positivlisten-Darstellung |
| `GET /offer/pdf` Kunde | Ausschließlich dessen bytegleiches, nochmals geprüftes Original-PDF als Download |
| `POST /offer/decision` Kunde | `request_id`, Inhalts-/PDF-Hash, Entscheidung, erklärter Name und ausdrückliche Bestätigung; keine frei wählbare Projekt-/Kunden-ID |

Das neue Recht ist ohne Defaultfreigabe für Mitarbeiter in beiden internen
Rechteoberflächen aufzunehmen; Owner bleiben wie bisher über die zentrale
Berechtigungsliste berechtigt. Interne Rechte werden auch vor Wiederholungen
neu geprüft. Der Dispatcher akzeptiert nur bekannte Felder und Methoden.

Die Kundendarstellung wird serverseitig aus einer ausdrücklichen Positivliste
erzeugt: Belegnummer/-titel/-datum, freigegebene Empfänger-/Ausstellerangaben,
Einleitung/Bedingungen, Beschreibungen, Mengen/Einheiten, Verkaufspreise,
Rabatte/Steuern und Netto-/Bruttosummen. Keine Kosten, Margen, Stundensätze der
Mitarbeiter, Artikel-/Aufmaß-/Zeitquellsnapshots, Vorlagenquellen, internen
Einstellungen oder fremden Referenzen. `Documents.get()` darf nicht mit einem
synthetischen privilegierten Akteur als Kunden-API verwendet werden.

Neue öffentliche Freigaben und Entscheidungen beachten die aktive Business-
Konfiguration und das Dokumentmodul. Die Prüfung für Kunden muss ohne
internen Benutzer erfolgen; die bestehende `require_active()`-Funktion setzt
einen solchen voraus. Ein kleiner getrennter Modulzustandsprüfer kann von
beiden Authentifizierungswegen genutzt werden. Widerrufe bleiben als
Sicherheitsaktion möglich. Die vorhandene Restore-/Finanzfreigabe darf durch
Portalveröffentlichung oder spätere interne Übernahme nicht umgangen werden.

## Wiederholung, Konkurrenz und Übernahme

- Gleiche Anfrage-ID und gleicher Inhalt liefern nach frischer
  Zugangsprüfung denselben Entscheidungs- beziehungsweise Übernahmebeleg.
  Geänderter Inhalt unter derselben ID erzeugt 409.
- Ein eindeutiger Datenbankschlüssel je Angebotsentscheidung verhindert
  konkurrierende Annahme und Ablehnung. Eine neue Anfrage-ID darf keine zweite
  oder widersprechende Erklärung erzeugen.
- Die interne Übernahme verwendet `Documents.convert()` mit dem tatsächlichen
  berechtigten internen Akteur innerhalb derselben Transaktion wie der neue
  Übernahmebeleg. Nur `target_kind=order_confirmation`; Ergebnis bleibt Entwurf.
- Vorher bestehende manuelle Auftragsbestätigungen aus derselben Quelle müssen
  erkannt werden. Ohne geprüfte ausdrückliche Verknüpfung wird kein weiterer
  Entwurf erzeugt. Ein möglicherweise bereits bearbeiteter Entwurf wird nicht
  still als unverändertes Annahmeergebnis übernommen.
- Fehler bei Zielbeleg, Audit oder Ergebnisbeleg rollen die gesamte Übernahme
  zurück. Der Originalbeleg und dessen Archivbytes bleiben unverändert.
- Die Entscheidung erzeugt selbst keine Rechnung, Zahlung, Terminbelegung,
  Materialbestellung oder ausgehende Nachricht.

## Clients, Betrieb und Wiederherstellung

Die erste Kundenseite kann als `web/office/portal.html` mit eigenem
`portal.js` die vorhandene Browser-CSP und Proxyroute verwenden. Die neue
Datei muss in die ausdrückliche Assetliste von `online.web` aufgenommen werden.
Sie lädt keine interne Office-Shell, keine internen Metadaten und keine
externen Ressourcen. Ein neuer Pfad `/portal/` wäre dagegen zusätzlich in
Proxy und Tests einzutragen; die erste Umsetzung braucht diese Änderung nicht.

Browser und Flutter erhalten im bestehenden **finalen Angebotsdetail** die
internen Aktionen Freigabe, Linkanzeige, Widerruf, Entscheidungsnachweis und
Übernahme. Geeignete Einstiegspunkte sind `web/office/office.js:753` und
`app/lib/business_documents.dart:1430`. Die Verfügbarkeit muss echte
Online-Portalunterstützung anzeigen; ein lokaler Backendprozess darf nicht
allein aufgrund einer vorhandenen Moduldatei einen erreichbaren Kundenlink
behaupten. Fehlende Funktion auf einem älteren Server bleibt verständlich.

Nach einem Disaster-Restore werden **alle wiederhergestellten Portalzugänge
widerrufen und Portalsitzungen gelöscht**, während Entscheidungen und
Belegarchive erhalten bleiben. Ein älteres Backup darf einen inzwischen
widerrufenen Link nicht reaktivieren. Die neue Bereinigung gehört ausdrücklich
in Online- und vorhandene lokale Restorewege. Veröffentlichung nach einem
Restore bleibt an den bestehenden Betreiberabgleich gebunden. Eine normale
additive Softwaremigration ist kein Disaster-Restore und entzieht nicht
unbemerkt alle gültigen Zugänge.

Das Modul ist in Schema-/API-Registry, eingeschränkten Laufzeitrechten,
Quellpaketlisten, CI und Dokumentmodulsteuerung zu registrieren. Ein neues
Portal erzeugt keine produktive Bereitstellung oder Freigabe; getestet wird
zuerst ausschließlich mit zwei synthetischen Kunden und Unternehmensinstanzen.

## Erforderliche Nachweise des ersten Abschnitts

1. **Quelle und Migration:** gefüllte Schema-7-Datenbank migrieren; alte
   Projekt-/Kundenkennungen, finale Angebote/Rechnungen, PDF/XML, Nummern und
   vorhandene Signaturen unverändert; wiederholte Migration stabil.
2. **Datenbegrenzung:** zwei Kunden mit mehreren Projekten/Angeboten; fremde IDs,
   Suche, Downloads und manipulierte Quellen ablehnen. JSON und PDF enthalten
   keine internen Kalkulations-/Personalwerte. Unveröffentlichte Angebote und
   sonstige Projektdokumente bleiben unzugänglich.
3. **Auth-Grenzen:** Portal-/Office-/Offline-Token gegenseitig unbrauchbar;
   falscher Host/Origin, unbekannte/abgelaufene/widerrufene Freigabe, deaktivierter
   Principal oder Kunde, geänderte Kundenbindung und manipulierte Archivhashes
   scheitern. Ratenlimits bleiben nach Fehlversuchen wirksam.
4. **Erklärung:** Annahme und Ablehnung jeweils gegen exakte Quelle; stale Hash,
   doppelte neue Anfrage-ID, geänderter Retry, Antwortverlust, Neustart und zwei
   konkurrierende Entscheidungen erzeugen keine doppelte fachliche Wirkung.
5. **Interne Übernahme:** ausdrückliche Übernahme genau einmal, frischer
   Rechteentzug, bestehender manueller Zielbeleg und Fehler nach erstem
   Schreibschritt; kein Rechnungsabschluss, Versand oder Zahlungsvermerk.
6. **Restore:** alter Zugang wird nach tatsächlicher Wiederherstellung
   unbrauchbar; bestehende Annahmen bleiben nachweisbar; kein Neuversand oder
   automatisches Wiederaufnehmen von offenen Verpflichtungen.
7. **Echter Dienst und Clients:** PostgreSQL mit getrennter Laufzeitrolle,
   HTTPS/CSP/Header, Kundenbrowser bei Desktop und 390 px, interne Browser-/
   Flutteraktionen, verloren gegangene Antworten, Tastatur/Fokus und klare
   Leer-/Fehler-/Ablaufzustände. Kein externer Nachrichtenversand im Test.

Damit wird die bisher fehlende Angebotsentscheidung nachvollziehbar ergänzt.
Die vollständige Kundenidentität, Dateiaustausch und freigegebene
Projektinformationen bleiben R05.05-Arbeitspakete. Offline-Protokollkette,
vollständige Kosten-/Finanzabstimmung und tatsächliche Zielgeräte fehlen
weiterhin für die gesamte Abnahme B/G. Es ist kein Anbieterzugang für diesen
ersten Entwicklungsabschnitt erforderlich; externe Identitäts-, Rechts- und
Betriebsnachweise betreffen die spätere Produktivfreigabe.

## Nachgewiesene HTTP- und Restoregrenzen am 02.11.2026

Der separate Adapter `backend/online/portal.py` ist vor dem internen Dispatcher
eingebunden. Öffentliche POST-Anfragen verlangen den exakten konfigurierten
HTTPS-Origin und ein UTF-8-JSON-Objekt mit genau den vorgesehenen Feldern.
Doppelte JSON-Felder, nicht endliche Zahlen, komprimierte Inhalte, zusätzliche
Queryparameter und GET-Inhalte werden abgewiesen. Die maximale Eingabe ist
16 KiB. Portal- und Office-Zugangsdaten sind gegenseitig unbrauchbar; die
bestehenden HTTPS-, Host-, CSP-, No-store- und Asset-Whitelist-Grenzen gelten
auch für das Portal.

Je vertrauenswürdigem Proxy-Client und festem 60-Sekunden-Fenster gelten
120 öffentliche Anfragen insgesamt, höchstens 10 Sitzungsöffnungen und
30 Entscheidungsversuche. Die Zählertransaktion wird vor JSON-, Origin- und
Zugangsprüfung abgeschlossen. Gespeichert werden ausschließlich HMAC-SHA256-
Zählerschlüssel, deren Schlüssel aus dem vorhandenen Vault-Schlüssel abgeleitet
wird; die Zählertabelle enthält keine IP-Adresse und kein Portalgeheimnis.
Die Peeradresse stammt aus der vorhandenen Konfiguration für genau einen
vertrauenswürdigen Proxy. Ein veraltetes, noch nicht migriertes Modulregister
liefert 503, eine reine Legacyinstallation 404; Anfragen führen keine DDL aus.

Beide Disaster-Restorewege rufen den transaktionalen Portal-Sanitizer auf.
Der echte SQLite-Restoretest verwendet ein Backup vor einem späteren Widerruf:
alte Einladung und Kundensitzung funktionieren nach Wiederherstellung nicht,
Angebot, Nummern, archiviertes Original-PDF, erklärte Annahme und intern
erzeugter Auftragsentwurf bleiben erhalten. Ein absichtlich scheiternder
Sanitizer entfernt nur das neue Restoreziel; Quelle und Sicherung bleiben
unverändert. Das ist ein Restore-Nachweis, keine Identitätsprüfung oder QES.

Die zusätzlichen Fälle stehen in `backend/online/test_portal_http.py`.
Der gemeinsame Lauf mit unabhängigen Portalreisen, realer synthetischer TLS-
Verbindung, Instanzisolation, Intake, Backup, Kunden, Offlinezugängen und
Schema-Regressionen bestand **59 Tests**. Das Protokoll liegt unter
`work/verification/portal-http.log`. Die bestehenden Browser-Unitprüfungen
einschließlich der neuen Portaloberfläche bestanden **72 Tests**
(`work/verification/portal-browser-unit-regression.log`). PostgreSQL-
Rollenprüfung, tatsächlicher Browserablauf und vollständige Abnahmen B/G
sind gesonderte Nachweise.
