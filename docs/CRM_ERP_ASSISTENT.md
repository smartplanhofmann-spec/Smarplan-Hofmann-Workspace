# Assistent: Fachquellen, Regeln und nachvollziehbare Aktionen

Stand: 03.11.2026. Implementierter Fachkern für Gesamtziel Abschnitt 10 und
Abnahme E. Die Bedienoberflächen verwenden dieselbe API und dieselben
Fachaktionen. Eine freigegebene produktive KI-Anbindung, Sprachaufnahme und
vollständige externe Abnahme E werden dadurch nicht behauptet.

## Unterstützter Ablauf

1. Ein berechtigter Nutzer öffnet ein Projekt und wählt ausdrücklich bis zu acht
   Fachquellen aus. Verfügbar sind Projektstand, Aufgaben, offene Posten,
   erfasste Projektkosten, projektbezogene Kommunikation, Belege, freigegebene
   Mahnungen, Bestellungen und aktive Katalogartikel. Personal- und Lohndaten
   gehören nicht zum Quellenkatalog. Suche und Seitenwechsel erreichen auch
   Einträge außerhalb der ersten 100 Treffer.
2. Der Server friert Quelle, Projekt, Unternehmensinstanz, Zeitpunkt und
   SHA-256-Nachweise in einem unveränderlichen Kontext ein. Bei jedem späteren
   Lesen oder Ausführen gelten die aktuellen Rechte auf sämtliche Quellen.
3. Auch ohne Modellzugang lassen sich konkrete Aufgaben, Angebotsentwürfe und
   Versandpläne anhand dieser Quellen vorbereiten. Bei eingerichtetem Anbieter
   bestätigt der Nutzer die Weitergabe seiner Nachricht und genau der
   ausgewählten Fachquellen vor jedem neuen Chat-Aufruf.
4. Modellantworten dürfen ausschließlich vorhandene Quellen und deren Felder
   auswählen. Zahlen und andere Einzelangaben werden aus den geprüften
   serverseitigen Werten dargestellt. Freier Modelltext wird nicht als
   wirtschaftlicher Tatsachenbericht übernommen. Ein Angebotsentwurf verwendet
   ausschließlich ausgewählte Artikelrevisionen mit den hinterlegten Preisen,
   Steuersätzen und Einheiten; das Modell darf keine Preise einsetzen.
5. Eine versionierte Projektregel entscheidet zwischen automatisch, Freigabe
   und verboten. Der Server ermittelt relevante Tatsachen unabhängig davon,
   welche Quellen das Modell ausgewählt hat. Verbot gewinnt; unbekannte
   Voraussetzungen, widersprüchliche Zuständigkeit oder fehlende passende
   Erlaubnis sperren die Aktion. Der konkrete Plan zeigt Quellen, Parameter,
   Regelversionen, zuständige Person und Ergebnis.
6. Eine erforderliche Freigabe bindet den exakten Plan-Hash. Vor der Ausführung
   werden Quellen, Rechte, Zuständigkeit, Regelstand und betroffener Fachbereich
   erneut geprüft. Danach läuft die vorhandene Fachfunktion mit einer eigenen,
   dauerhaft gebundenen Vorgangs-ID. Ein Retry liest deren ursprüngliches
   Ergebnis und löst keinen weiteren Versand aus.

`task.create` erzeugt eine tatsächliche Aufgabe. `offer.draft` erzeugt einen
Angebotsentwurf. `document.email` und `dunning.email` verwenden die bestehenden
Versandvorschauen, archivierten PDFs und Versandquittungen. Ein eingerichteter
SMTP-Transport und sämtliche bestehenden Finanzfreigaben bleiben erforderlich.
`supplier.order` und `payment.execute` sind als überprüfbare Planarten bekannt,
bleiben mangels ausführendem Bestell-/Bankadapter gesperrt; sie erzeugen keine
behaupteten Zahlungen oder externen Bestellungen.

## Regel- und Sicherheitsgrenzen

- `assistant.use` öffnet den Assistenten; `assistant.approve` erlaubt die
  Freigabe. Regeln benötigen zusätzlich `settings.manage`. Fachaktionen und
  Quellen benötigen jeweils ihre bestehenden Projekt-/Dokument-/Finanzrechte.
  Die zuständige Person muss aktiv sein und selbst die erforderlichen Rechte
  besitzen. Ein Modell erhält weder Benutzeridentität noch Sonderrechte.
- Auslöser sind `manual`, `payment.overdue`, `task.overdue`, `cost.threshold`.
  Bedingungen prüfen bekannte Salden, Fälligkeit, überfällige Aufgaben und
  vollständige erfasste Kosten. Ihre Tatsachen werden aktuell aus den
  Fachmodulen berechnet. Diese Auslöser werden bei der Planvorbereitung
  ausgewertet; es gibt derzeit keinen unbeaufsichtigten Zeitplaner, der
  selbstständig Projekte durchsucht und neue Außenaktionen startet.
- Konfigurierte Regeln für manuellen Dokument-/Mahnversand greifen auch beim
  direkten Aufruf der ursprünglichen Versandfunktion. Ein Request-Flag kann
  keinen Plan ersetzen. Die native Funktion prüft vor dem Versand-Claim und
  unmittelbar vor Transportbeginn. Bereits bekannte Quittungen bleiben
  lesbar, ohne dabei erneut einen Transport auszuführen.
- Eingehende E-Mails und Dokumenttexte bleiben nicht vertrauenswürdige Daten.
  Sie dürfen weder Regeln ändern noch fremde Daten, Personalquellen,
  beliebige URLs, SQL oder Modellwerkzeuge freischalten.
- Kontext, Regelversionen, Pläne, Entscheidungen, Ausführungsnachweise,
  Ergebnisse und Anfragen werden nur angehängt. PostgreSQL trennt Laufzeit-
  und Migrationsrechte und schützt diese Tabellen zusätzlich durch Trigger.
- Ein Workerabbruch nach Annahme eines Modellaufrufs bleibt `unconfirmed`.
  Derselbe Request ruft das Modell nicht erneut auf. Nach Restore wird ein
  offener Aufruf als unterbrochen dokumentiert; mögliche Anbieterkosten werden
  ausdrücklich als ungeklärt bezeichnet. Offene Aktionspläne werden dauerhaft
  gesperrt und müssen neu vorbereitet werden. Erfolgreiche Nachweise bleiben
  unverändert erhalten. Das Restore-Verfahren führt keine Außenaktionen aus.

## API und Anbieterbetrieb

Die interne API liegt unter `/business/assistant`:

| Pfad | Funktion |
| --- | --- |
| `status?project_id=…` | Aktuelle Verfügbarkeit, Fähigkeiten und Grenzen; Projekt optional |
| `sources?project_id=…&q=…&offset=…` | Aktuell lesbare Quellen; Suche max. 200 Zeichen, Seiten zu 100, `next_offset` oder `null` |
| `contexts`, `contexts/{id}` | Kontext ausdrücklich speichern und mit aktuellem Quellenstatus lesen |
| `rules?project_id=…`, `rules/{id}/history` | Regeln versionieren, aktuellen Stand und Historie lesen |
| `plans?project_id=…`, `plans/{id}` | Konkrete Aktionspläne vorbereiten und Nachweise lesen |
| `plans/{id}/approve`, `/reject`, `/execute` | Hashgebundene Entscheidung und Ausführung |
| `chat?project_id=…`, `chat/{id}` | Persönliche quellgebundene Chats mit Ergebnis- und Abbruchstatus |

Schreibbefehle verwenden UUID-Vorgangs-IDs und exakte zulässige Felder. Ein
geänderter Inhalt mit derselben ID wird abgewiesen. Nur nachweislich nicht
angenommene Konflikte tragen `request_resolution=not_accepted`; unklare oder
bereits angenommene Versuche behalten ihren ursprünglichen Befehl. Die
Quellensuche zählt ausschließlich autorisierte Treffer, auch bei Seitenwechsel.

Der optionale Adapter spricht einen begrenzten OpenAI-kompatiblen
Chat-Completions-JSON-Vertrag. Die Installation aktiviert ihn nicht. Der
Betreiber muss folgende Variablen für die konkrete Unternehmensinstanz setzen:

```text
SMARTPLAN_ASSISTANT_ENABLED
SMARTPLAN_ASSISTANT_INSTANCE_ID
SMARTPLAN_ASSISTANT_ENDPOINT
SMARTPLAN_ASSISTANT_MODEL
SMARTPLAN_ASSISTANT_API_KEY
SMARTPLAN_ASSISTANT_DATA_TRANSFER_APPROVED
```

Der Endpunkt muss HTTPS mit Standardport und Pfad `/v1/chat/completions`
verwenden. Private Zieladressen, Weiterleitungen, unerwartete Modellwerkzeuge,
doppelte JSON-Schlüssel, nicht endliche Zahlen, unvollständige oder übergroße
Antworten werden abgewiesen. Zertifikat- und Hostnamenprüfung bleiben aktiv.
Ein konfigurierter HTTPS-/ALL-/HTTP-Proxy wird verwendet; `NO_PROXY` umgeht ihn
nicht. Ungeeignete Proxyarten führen zum Abbruch statt zu einem direkten
Fallback. Es gibt keine automatische Wiederholung kostenpflichtiger Aufrufe.
Zugangsdaten erscheinen weder in öffentlichen Konfigurationen noch Fehlermeldungen.

Anbieterwahl, erlaubte Datenflüsse, Vertrag/Auftragsverarbeitung, Kosten und
produktive Zugangsdaten sind noch nicht eingerichtet oder extern geprüft.
Die Prüfungen unten kontaktierten keinen Modellanbieter und keinen Empfänger.
Sprachaufnahme bleibt derzeit ausdrücklich nicht verfügbar.

## Nachweise dieses Integrationsstands

| Prüffläche | Ergebnis |
| --- | --- |
| Fachkern, Providervertrag, SQLite-Restore und echte HTTP/MFA-Grenze | 27 Tests bestanden; `backend/test_business_assistant.py`, `backend/test_business_assistant_provider.py`, `backend/online/test_assistant_http.py`; Log `work/verification/assistant-resume-unit-http.log` |
| PostgreSQL mit getrenntem Runtime-Login, MFA, frischen Rechten, SQL-ACL und unveränderlichen Triggern | Bestandteil der vier bestandenen Tests in `backend/online/test_assistant_pg.py` |
| Echter Mahnablauf durch beide native Versandgates | Freigabe → Claim → ein synthetischer Transport → Quittung; wiederholte Requests und späteres Verbot lösen keinen weiteren Versand aus |
| Regelwechsel zwischen Versandgates | `sending` → `failed`, Nachweis `authorization_changed_before_io`, kein Transport |
| Tatsächlicher PostgreSQL-Backup/Restore | Erfolgreiche Aktion und Quittung erhalten; freigegebener offener Plan gesperrt; Quell-Datenbank unverändert |
| PostgreSQL-Gesamtlauf | 4/4 bestanden in 12,144 Sekunden; Log `work/verification/assistant-pg.log` |
| Neue Quellenbedienung | 105 Katalogartikel über Suche/Seiten erreichbar; fremde Artikeltitel und Trefferzahlen bleiben verborgen; strikte Queryprüfung |

Der erste wiederaufgenommene Domainlauf fand einen unvollständig eingerichteten
synthetischen Versandtransport in einem Test. Die Fixture wurde berichtigt;
der Produktionsschutz wurde dafür nicht gelockert. Ein Modell-Crash und
Rechteentzug während einer laufenden Antwort sind nun zusätzlich abgedeckt.
Browser-/Flutterabnahmen stehen in der gesonderten Clientdokumentation.

Diese Nachweise belegen den beschriebenen Umfang. Sie ersetzen weder eine
unabhängige Sicherheitsprüfung noch die reale Anbieter-, Geräte- oder
Gesamtabnahme des vollständigen CRM-/ERP-Ziels.

## Bedienoberflächen

Zentrale und projektbezogene Navigation, Quellensuche mit Seitenwechsel,
belegte Antwortansicht, versionierter Regeleditor, konkrete Freigaben und
unveränderliche Wiederholung sind in beiden Clients beschrieben und geprüft:
[Clientablauf und Testnachweise](CRM_ERP_ASSISTENT_CLIENTS.md).
