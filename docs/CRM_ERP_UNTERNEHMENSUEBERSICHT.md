# Unternehmensübersicht

Stand 03.11.2026. Entwicklungsnachweis, keine Produktivfreigabe.

`GET /business/overview/metrics` stellt bestehende Fachquellen zusammen.
Ein optionales `project_id` begrenzt sämtliche Projektwerte auf dieses Projekt;
unternehmensweite EÜR- und Geldkontodaten werden dann nicht eingeblendet.
Die bisherige Projektübersicht `/overview` behält ihren Vertrag.

## Zahlen und Datenbasis

- Offene und überfällige Aufgaben: kanonische Projektaufgaben, Fristen in
  Europe/Berlin. Alle Aufgaben werden gezählt; die Startseite zeigt die ersten
  zwanzig, mit sichtbarem Hinweis auf weitere Einträge.
- Anstehende Termine: kanonischer Einsatzkalender für die nächsten dreißig
  Tage, ohne abgesagte oder beendete Termine und ohne private HR-Angaben.
- Projektzahlen: festgeschriebene Nettoerlöse abzüglich Gutschriften,
  Material-/Arbeits-/eingeordnete Belegkosten, daraus der dokumentierte
  Projektbeitrag. Bei unvollständigen Kostenquellen bleibt der Beitrag leer.
- Kundenzahlungen, Erstattungen, offene Salden und überfällige Forderungen
  bleiben eigene Bruttowerte. Die Oberfläche berechnet daraus keinen Gewinn.
- EÜR des laufenden Jahres: bestätigte Einnahmen/Ausgaben und die
  Vollständigkeitsbewertung des Journals. Unvollständige Quellen erzeugen
  keinen scheinbar abschließenden Überschuss.
- Geldkonten: dokumentierte Bewegungen aus dem gemeinsamen Journal.
  Ohne Anfangsbestände wird kein Kontostand angegeben.

Projektzahlen beziehen sich auf erfasste Vorgänge seit Beginn. Nicht einem
Projekt zugeordnete Gemeinkosten sind nicht Teil eines Projektbeitrags.
EÜR und Geldkonten benötigen gesonderte frische globale Buchhaltungsrechte.
Eine Summe über zugängliche Projekte wird mit ihrer Projektanzahl ausgewiesen;
daraus entsteht keine Aussage über gesperrte Projekte.

Jede Antwort enthält Datenstand, Umfang und einen Hash der Quellenprojektion.
Die Kennzahlen werden serverseitig in Dezimal-/Centwerten zusammengestellt.
Der Datenstand ist keine Vollständigkeitsbescheinigung für noch nicht erfasste
Geschäftsvorfälle. Bei Rechteänderungen wird erneut autorisiert. UI-Quellen
öffnen kanonische Projekte oder die EÜR.

## Prüfung

- 7 Domänenfälle: geprüfte/unvollständige Kosten, fremde Projekte,
  Quellenrechte, Terminstatus, Vorschaugrenzen und Umfang.
- 1 tatsächlicher MFA-/HTTP-Fall: Aufgabensource abrufbar, GET-Framing,
  unbekannte/doppelte Filter abgelehnt, Neustart und identischer Quellenhash.
- 3 Node-Fälle für Betrags-/Umfangsprüfung und tatsächliche Drilldownziele;
  gemeinsam mit 5 Workflow-Wiederholungsfällen: 8 bestanden.
- 3 Flutterfälle für getrennte Beträge, Quellen, unvollständige EÜR und
  390-Pixel-Ansicht. Gemeinsam mit Sitzung, Shell und neuem Schutz gegen eine
  verspätete parallele Antwort: 13 bestanden.
- 1 echter Chromium-/MFA-Ablauf mit Quellendurchstieg, Projektfilter,
  ausgeblendeter globaler EÜR im Projektumfang und mobiler Ansicht bestanden.

Protokolle: `work/verification/company-overview-{domain-http,node,flutter-regression,browser}.log`.
Screenshot: `work/verification/company-overview-screenshots/company-overview-mobile.png`.
Die Rohdateien sind lokale Prüfarbeitsmittel; dieser Bericht hält Ergebnisse
im Repository fest. Reale Windows-/iPhone-Geräteabnahme bleibt offen.
