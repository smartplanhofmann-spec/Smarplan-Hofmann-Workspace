# U-Merkmal im Lohnkonto: Bedienung und Clientnachweise

Stand 03.11.2026. Der Browser öffnet die private Jahresprüfung unter
**Personalakte → Lohnberechnung 2026 → U-Merkmal im Lohnkonto prüfen**.
Maßgeblich bleibt der [fachliche Vertrag](CRM_ERP_LOHN_U_MERKMAL_VERTRAG_2026.md).
Diese Anleitung dokumentiert den tatsächlich geprüften Browserstand. Der
[native Prüfbericht](CRM_ERP_LOHN_U_MERKMAL_NATIVE_PRUEFUNG_2026-11-03.md)
dokumentiert zusätzlich zehn bestandene Flutterfälle und die Analyse von drei Dateien.

## Tatsächlichen Jahresstand vorbereiten

**U-Jahresnachweis 2026 erstellen** verlangt das ausdrücklich gewählte Jahr und
den tatsächlichen Prüfungstag. Ausgewählt werden alle einschlägigen
Beschäftigungsfassungen, tatsächlichen Lohnläufe, vollständigen vertraglichen
Tagesarbeitspläne, bestätigten Anspruchsbausteine und geschützten Personaloriginale.
Arbeitstage und Anspruchsverlust werden daraus unveränderlich abgeleitet.
Es gibt weder eine frei eingebbare U-Anzahl noch frei erfundene Tagesentscheidungen.
Fehlende Projektstunden begründen keinen unbezahlten Tag.

Jede der acht gesetzlichen Ausnahmeleistungsarten wird einzeln und ausdrücklich
als **nach Originalprüfung nicht vorhanden** oder **durch tatsächliche Zeiträume
belegt** beurteilt. Die Auswahl startet jeweils ungeprüft. Für vorhandene
Leistungen führt **Belegten Leistungszeitraum hinzufügen** zu Leistungsart,
tatsächlichem Beginn und Ende sowie zu den Originalen genau dieses Zeitraums.
Widersprüchliche Angaben, überlappende ungeklärte Zeiträume oder fehlende
Originale verhindern die Vorschau. Bei einer Korrektur werden alle acht Arten
erneut ausdrücklich geprüft.

## Ableitung prüfen und getrennt bestätigen

**Vorschau aus Originalquellen erstellen** zeigt die abgeleiteten
Unterbrechungszeiträume, die belegten Arbeitstage und die Anzahl U.
**Tatsächliche Tagesherleitung** öffnet je Monat eine schreibgeschützte Tabelle
mit vertraglichem Arbeitstag, tatsächlichem Lohnanspruch und gesetzlicher
Ausnahme. Die Tagesquellen sind an die exakten ursprünglichen Lauf-, Plan- und
Dateifassungen gebunden.

Unbekannt bleibt ausdrücklich **Anzahl U noch ungeklärt**; es wird keine
bestätigte Null angenommen. Ein noch unvollständiger Prüfstand kann als solcher
festgehalten werden und bleibt für die abschließende Anzahl gesperrt.
**Geprüften Jahresstand festhalten** verlangt eine zusätzliche Bestätigung der
konkreten Vorschau. Erst ein aktueller, vollständiger aktiver Jahresnachweis kann
die entsprechende Lücke im Lohnkonto schließen. Gesetzliche Ausnahmeleistungen
können weitere Pflichtbeträge erfordern; eine bestätigte U0 ersetzt diese
separaten Nachweise nicht.

Die ursprüngliche Speicherantwort kann bereits angenommen sein, auch wenn sie
im Client fehlt. Erneutes Bestätigen verwendet dann unverändert denselben
privaten Auftrag und dieselbe Nonce. Korrektur und Aufhebung erzeugen neue
Fassungen; frühere Jahresnachweise und Lohnläufe bleiben erhalten. Auch die aktuelle
aufgehobene Fassung kann über **Jahresnachweis korrigieren** erneut belegt
aktiviert werden; alle acht Ausnahmearten werden dabei erneut geprüft. Manuelles
Schließen, Abmeldung oder Mitarbeiterwechsel verwerfen private Entwurfsdaten.

## Ausgeführte Browserprüfung

Sieben Node-Vertragstests und ein vollständiger echter Chromium-Ablauf bestanden.
Der Browser erzeugt die benötigten Beschäftigungs-, Arbeitsplan-, P4- und
Source3-Lohnnachweise per echter lokaler HTTP-API nach MFA-Anmeldung. Er prüft
fünf Arbeitstage über ein Wochenende als U1, die getrennte Bestätigung, den
Originaldownload, identischen Wiederholungsauftrag nach verlorener angenommener
Antwort, das tatsächliche Jahreskonto sowie eine belegte Qualifizierungsgeld-
Ausnahme mit U0 und weiterhin offener Pflichtbetragsprüfung. Korrektur,
Aufhebung und unveränderte Historie sind Bestandteil desselben Laufs.
Schließen/Wiederöffnen und eine simulierte Änderung des Mitarbeiterkontexts
prüfen die private Bereinigung; die 390-Pixel-Ansicht wurde visuell geprüft.

Alle Daten sind synthetisch und lokal. Der Nachweis behauptet weder amtliche
Übermittlung, DLS-Zulassung noch Produktiv-TLS oder reale Geräteabnahme.
Teilansprüche, pauschal besteuerte Minijobs und Vorjahresrandfälle behalten ihre
ausdrücklichen fachlichen Blocker.

Dauerhafte Logs, genaue Prüfbefehle, Grenzen und Dateiprüfsummen:
[`evidence/payroll-wage-interruptions-browser-2026-11-03.json`](evidence/payroll-wage-interruptions-browser-2026-11-03.json).

## Unabhängige Wiederholungs- und Bereinigungsprüfung

Ein zusätzlicher echter Browserlauf nach der gezielten Entwurfsbereinigung
bestand einschließlich Wiederaufnahme eines aufgehobenen Jahresstands als
aktive Fassung 4. Die ursprüngliche U1-Fassung und die aufgehobene Fassung
blieben unverändert. Interne U-Formularschritte erhalten den aktuellen Entwurf;
Schließen und Mitarbeiterwechsel löschen ihn.

Die unabhängige tatsächliche OfficeApi-Prüfung deckt sechs getrennte Lohnpfade
ab. Der gemeinsame Nachlauf bestand mit **61 Fällen**: 28 neue Gegenprüfungen,
neun vorhandene Sessionfälle und 24 betroffene Vertragstests. Die neuen Fälle
prüfen aktuelle Freigaberechte bei weiter bestehendem Leserecht, fremde
Personen/Jahre, falsche Quittungen, unpassende Vorgangsschlüssel sowie identische
Originalaufträge trotz späterer Quellenrevision und pausiertem Modul.

Zwei echte negative Kontrollen fanden eine ignorierte fehlende Autorisierung
bei unpassenden Schlüsseln; die zentrale Absicherung verlangt jetzt ein
explizites erfolgreiches Prüfergebnis. Drei ältere Modulprüfungen wurden an
diesen Erfolgsvertrag angepasst. Rote Ausgangsläufe, die getrennte Korrektur
eines eigenen P4-Testaufbaus und der grüne gemeinsame Nachlauf sind erhalten:
[`evidence/payroll-protected-session-review-2026-11-03.json`](evidence/payroll-protected-session-review-2026-11-03.json).
Dies belegt die Clientabsicherung; daraus wird keine vorherige Umgehung der
serverseitigen Rechteprüfung behauptet.
