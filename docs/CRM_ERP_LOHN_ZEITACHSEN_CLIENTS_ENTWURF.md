# Lohnzeitachsen und Teilmonate – Bedien- und Clientvertrag

**Historischer Entwurf:** Die Umsetzung und tatsächlich ausgeführten Prüfungen
stehen inzwischen in [Clientabnahme P2/P3a](CRM_ERP_LOHN_ZEITACHSEN_CLIENTS.md).
Der endgültige Vertrag ist [Lohnzeitachsen-API](CRM_ERP_LOHN_ZEITACHSEN_API.md).
Die nachfolgenden Planformulierungen bleiben als damaliger Entwurfsstand erhalten.

Stand 03.11.2026. Dieser Entwurf beschreibt die nächste Erweiterung; er ist kein
Nachweis einer bereits vorhandenen Funktion. Der derzeitige Bank-/Midijobstand
bleibt während der gemeinsamen Abschlussprüfung unverändert. Grundlage ist der
[fachliche P2/P3-Entwurf](CRM_ERP_LOHN_ZEITACHSEN_TEILMONATE_ENTWURF.md).

## Einstieg und Sichtbarkeit

Die bestehende Mitarbeiteransicht unter **Personal → Personalakte, Reisen und
Lohnvorbereitung → Lohnberechnung 2026** erhält für ausdrücklich berechtigte
Personalverantwortliche den Einstieg **Lohnzeitachsen und Teilmonate**. Die neue
Ansicht erfordert aktuelle globale Personal-Leserechte und die neue
Serverfähigkeit. Eine bloße eigene Zeiterfassungsberechtigung öffnet keine
privaten Vertrags-, Anspruchs- oder Krankheitsnachweise. Bestehende historische
Lohnansichten behalten ihre bisherigen Leseregeln.

Browser und Flutter verwenden dieselben fachlichen Schritte und Bezeichnungen.
Ein Mitarbeiterwechsel, Sitzungswechsel oder Rechteentzug entfernt die privaten
aktiven Ansichten und unverbindlichen Vorschauen. Späte Antworten öffnen keine
bereits geschlossene oder gewechselte Ansicht erneut. Die bestehenden
Personaloriginale, Entgeltvereinbarungen, Monatsvorbereitungen und
Lohnkontonachweise bleiben die einzigen kanonischen Quellen.

## Drei belegte Eingabeabläufe

| Ablauf | Ausdrückliche Eingaben | Anzeige und Grenzen |
|---|---|---|
| Beschäftigung und Entgelt | Tatsächlicher Beschäftigungszeitraum, gültige Entgeltvereinbarung(en), belegte Teilentgeltmethode, Originale und Vertragsgrund | Der Personalstamm wird angezeigt und auf Widerspruch geprüft. Kein automatisch angenommener Beginn, kein Standardquotient von 30 Tagen und kein frei eingegebener Wunschbruttobetrag. |
| Datierter Arbeitsplan | Einzelne tatsächliche Solltage mit Sollzeit, Arbeitsort/Feiertagsregion, Original und begründeter Abweichung | Zeit wird als ganze Sekunden übermittelt. Ein Solltag wird weder zur geleisteten Projektarbeit noch automatisch zum bezahlten Urlaubs-/Krankheitstag. Keine ungeprüfte Wochenend-/Feiertagsvorbelegung. |
| Monatsfall und Periodenprüfung | Monat, bestätigte Beschäftigungs-/Arbeitsplanfassungen, vorhandene HR-Vorbereitung, Profile/Identitätsnachweise, LZZ-Einordnung und belegte Anspruchs-/Unterbrechungsfälle | Vorschau berechnet Entgeltquote, Steuerzeitraum und SV-Tage getrennt. Fehlende oder nicht unterstützte Fälle erhalten konkrete Gründe; Bestätigung kann keine fachliche Sperre umgehen. |

Alle Quellen werden mit Mitarbeiter, Fassung und Hash gebunden. Auswahlfelder
beginnen mit einer leeren ausdrücklichen Auswahl. Korrekturformulare dürfen den
vorherigen belegten Wert zeigen, müssen aber einen neuen Korrekturgrund und die
aktuelle Quellenprüfung verlangen. Ein fehlendes Datum bleibt leer; es wird
nicht durch das heutige Datum ersetzt.

## Prüfen, festhalten und berechnen

1. Die Personalverantwortlichen wählen die Originale und vorhandenen Quellen.
2. **Periodenplan prüfen** ruft den unverbindlichen Serverplan auf. Dieser Schritt
   speichert weder einen Lohnfall noch eine Auszahlung.
3. Die Vorschau gliedert sich in **Beschäftigung**, **Entgeltanspruch**,
   **Steuerzeitraum**, **Sozialversicherung** und **Offene Nachweise**. Beträge
   zeigen EUR und exakte Cent; Quotienten nennen Zähler, Nenner und Grundlage.
   Steuerliche Tage, SV-Tage und Arbeitstage werden niemals unter einer
   gemeinsamen unbeschrifteten Tageszahl zusammengefasst.
4. **Geprüften Fallnachweis festhalten** bestätigt genau diese Quellen und diesen
   Planhash. `can_confirm` und aktuelle Freigaberechte entscheiden über die
   Schaltfläche. Ein festhaltbarer, noch nicht berechenbarer Fall zeigt weiterhin
   seine Blocker und bietet keinen freigeschalteten Lohnabschluss.
5. **Lohn aus diesem Fall berechnen** verwendet ausschließlich die bestätigte
   Faktenreferenz. Die neue Lohnvorschau und deren ausdrücklicher Abschluss
   bleiben getrennte Schritte. Berechnung erzeugt keine Zahlung oder Meldung.

Vorläufig abgestimmter neuer Payroll-Eingabesatz:

```json
{
  "source_schema_version": 2,
  "employee_id": "kanonische Mitarbeiter-ID",
  "period_case_ref": {
    "id": "bestätigte Fakten-ID",
    "revision": 1,
    "content_hash": "SHA-256 der bestätigten Fassung"
  }
}
```

Die Clients ergänzen keine Bruttosumme, Profilfassung oder frei gewählte
SV-/Steuertage zu diesem Eingabesatz. Der Server löst sie aus dem gebundenen
Fallplan auf. Die vorhandene vollständige v1-Monatseingabe und ihre historischen
Ansichten bleiben unverändert verwendbar.

Neue geplante Rechenfälle sind `regular_standard_period`,
`regular_transition_period` und `commercial_minijob_period_flat_tax` unter
`de_2026_periods_pap_v4`. Konkrete Ausgabeobjekte und endgültige Namen werden
zusammen mit dem Backendvertrag eingefroren, bevor die Clients implementiert
werden. Die bestehenden Summenfelder bleiben für Lohnkonto/Jahr/Korrektur
vergleichbar; die zusätzliche Periodenansicht erklärt Tages-PAP, Eingangsrest,
Teil-BBG und die getrennten Beitragsgrundlagen. Ein nicht ermitteltes Netto bleibt
**Nicht ermittelt** und wird nicht als 0,00 EUR angezeigt.

## Historie, Originale und unklare Antworten

Fakten zeigen ihre aktuelle Fassung, Vorgänger und den Korrekturgrund. Historische
Fassungen und zugehörige Lohn-PDF/JSON bleiben über ihre gespeicherten Quellen
prüfbar. Die aktuelle Stammdatenlage ersetzt keine frühere Quellenfassung. Die
Originalansicht prüft vor dem Öffnen erneut die Personalrechte sowie
Mitarbeiterbezug und den Hash der tatsächlich gelieferten Bytes.

Ein unbestätigter Schreibaufruf erhält einen eigenen neutral bezeichneten
Wartestatus. Derselbe Auftrag wird mit denselben ursprünglichen Werten und
derselben Anfragekennung wiederholt. Die Ansicht bietet keine zweite
Bestätigung mit neuen Werten an, solange der Ausgang unklar ist. Vor einer
Wiederholung werden aktuelle Fähigkeiten und Mitarbeiterzugang erneut geprüft;
eine bereits bestätigte ältere Fassung wird nicht durch Vergleich mit der heute
neuesten Revision verworfen. Falsche Mitarbeiter-/Quell-/Antwortbindungen lassen
den ursprünglichen Auftrag bestehen. Auch unklare Transportfehler, ein
Sitzungswechsel und eine zwischenzeitliche Modulabschaltung dürfen nicht als
Bestätigung einer neuen Faktfassung dargestellt werden.

Vorgeschlagen ist ein eigener Befehlsbereich `payroll-facts-<employee_id>` für
`/payroll/facts`; normale Lohnabschlüsse bleiben beim vorhandenen
`payroll-run-<employee_id>`. Die Root-Integration übernimmt die gemeinsamen
BusinessSession-/OfficeApi-Wiederholungsgrenzen. Die Clients speichern keine
privaten Fakten in Browser-LocalStorage und erzeugen keine neue Offlinewarteschlange.

## Noch festzulegender konkreter API-Vertrag

Vor Produktcode werden mit den Backendverantwortlichen exakt festgelegt:

- vollständige `details`-Formate der drei Faktenarten einschließlich aller
  Referenzen, Status- und Korrekturfälle;
- Quellenroute oder vorhandene kanonische Quellrouten mit aktuellen Fähigkeiten,
  Mitarbeiterbindung und einheitlichen Referenzen;
- Anfrage und Antwort von `/payroll/periods/preview` sowie Bestätigung eines
  gebundenen Plans und vollständige unveränderliche Quittungsansicht;
- Detail-/Historienantworten, Originalreferenzen, Module-/Featurebezeichnungen
  sowie Rechte für neue Befehle gegenüber angenommenen Wiederholungen;
- `period_details` und Quellenstruktur der v4-Rechnung, Umgang mit gesperrten
  P4/P5-Fällen sowie Korrekturdifferenzen und Jahres-/Lohnkontoanzeige.

Die Validierung prüft insbesondere Mitarbeiter, Monat, Quellenreferenzen,
Plan-/Inhaltshash, Revision, Vorgänger und ausdrücklich bestätigten Umfang. Sie
implementiert kein zweites Steuerrechenwerk in JavaScript oder Dart.

## Geplante nachweisbare Prüfung

| Gruppe | Erforderlicher tatsächlicher Nachweis |
|---|---|
| Formulare | Leere Datums-/Methodenauswahl; fremdes Original; ungültige Sollzeit; Korrekturgrund; keine versteckte Bruttovorbelegung |
| Vorschau | Quellen-/Mitarbeiter-/Monatsbindung, geänderte Quelle, verspätete Antwort nach Navigation, Blocker trotz bestätigtem Nachweis |
| Abrechnung | Eintritt/Austritt und Februar, Minijob-/Midijob-Teilmonat, getrennte Steuer-/SV-Tage, Quellen-v2, unveränderte v1/v2/v3-Läufe |
| Historie | Korrektur, unverändertes altes PDF/JSON, wirksame Jahresfassung, tatsächliche frühere Zahlung bleibt erhalten |
| Wiederholung | Verlorene angenommene Antwort, exakt ein Datensatz, gleiche ursprüngliche Anfrage, frischer Rechteentzug, falsche Quittung bleibt offen |
| Oberfläche | Tatsächlicher MFA-/HTTP-Chromiumablauf mit 390-px-Ansicht und Originaldownload; Flutter-Widget-/HTTPfälle und Analyse; Tastatur/Fokus und lesbare Fehlermeldungen |

Die derzeit abgeschlossenen 848 Flutter- und 336 Node-Fälle betreffen den
vorherigen eingefrorenen Produktstand. Sie sind kein Prüfergebnis dieses
Entwurfs und werden nach der Umsetzung durch passende neue Fälle und die
bestehenden Lohnregressionen ergänzt.
