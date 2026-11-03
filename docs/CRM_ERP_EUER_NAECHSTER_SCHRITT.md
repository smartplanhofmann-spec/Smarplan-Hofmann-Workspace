# Nächster Schritt: Vorbereitungsprofil und sachliche Einordnung

Stand: 03.11.2026. **Gesamtentwurf für Profil und sachliche Einordnung.**
Der Profilteil wird gesondert in [E1b-4a1](CRM_ERP_EUER_E1B4A1_API.md) umgesetzt
und geprüft; die sachliche Einordnung bleibt der anschließende Abschnitt
E1b-4a2. Der vollständige Umfang dieses Entwurfs ist noch nicht implementiert.
Dieser Vorschlag gehört weder zur Implementierung noch zum Prüfnachweis von
E1b-3c. Grundlage sind [EÜR-Plan](CRM_ERP_EUER_PLAN.md),
[E1b-Gesamtentwurf](CRM_ERP_EUER_E1B_ENTWURF.md) und die inzwischen vorhandenen
dokumentarischen Quellen-, Cent- und Rücknahmenachweise. Der endgültige
3c-Abschlussstand wird bei einem späteren Implementierungsvertrag als Basis
gebunden; dieser Entwurf verändert ihn nicht.

## Empfehlung und nutzbares Ergebnis

Als nächsten kleinen Abschnitt **E1b-4a: versioniertes Vorbereitungsprofil
mit sachlicher Einordnung** umsetzen. In Browser und Flutter sieht der
berechtigte Anwender die festgehaltenen Grundlagen seiner EÜR-Vorbereitung,
offene Angaben und eine Liste noch ungeprüfter Geldflüsse. Er kann einen
Geldfluss mit Begründung sachlich einordnen und später erkennen, auf welchem
Profil- und Quellenstand diese Aussage beruhte.

Bestätigt sind Einzelunternehmen und EÜR. **Umsatzsteuerstatus, Soll-/Ist-
besteuerung und deren Gültigkeit bleiben unbekannt.** EÜR und vorhandene
Rechnungssteuersätze beantworten diese Fragen nicht. Buchhaltungsbeginn und
Übernahmevollständigkeit bleiben ebenfalls offen. Die Entwicklung dieses
Abschnitts benötigt keine vorweggenommene Antwort; eine Steuerfallgruppe wird
erst nach ausdrücklicher Klärung und eigenem Regel-/Referenzvertrag umgesetzt.

## Eng begrenzter fachlicher Umfang

- Ein eigenes, anhängendes Profiljournal hält Unternehmens-/Buchführungsform,
  bekannte bzw. unbekannte Steuerangaben, ausdrücklich angegebene Gültigkeit,
  Nachweisreferenz, Grund, Akteur und Erfassungszeit fest. Erfassungszeit und
  fachliche Gültigkeit sind getrennt; unbekannter Beginn bleibt leer.
  Unternehmensweit niemals durch Migration ein reales Steuerprofil anlegen.
  Bestätigte Angaben können im Editor vorgeschlagen werden, werden aber erst
  mit ausdrücklicher Bestätigung als neue Profilversion gespeichert.
- Der erste Produktumfang speichert einen **unvollständigen Vorbereitungsstand**.
  Es gibt noch keine Aktivierung einer steuerlichen Regel. Etwaige später
  ausdrücklich angegebene Steuermerkmale bleiben erklärte Stammdaten, bis ein
  gesondert implementierter fachlicher Vertrag ihre Verwendung erlaubt.
- Eine sachliche Einordnung bezieht sich auf genau einen vorhandenen ganzen
  CashEvent: `customer_payment`, `supplier_payment`, `customer_refund` oder
  ausdrücklich `unresolved`, jeweils mit Begründung. Die Quelle begrenzt die
  zulässige Kennung; eine Erstattung wird dadurch keine Einnahme. Keine frei
  editierbaren Geldbeträge, Gewinnkategorien oder automatischen Vorschläge als
  bereits bestätigte Einordnung. Unzugeordnete Teile und fehlende Komponenten
  bleiben neben dieser Aussage sichtbar ungeklärt.
- Jeder Einordnungsstand bindet Profilversion, unveränderten Quellenhash und
  die tatsächlich betrachteten Zuordnungs-/C1-/C2-/R1-/R2-Nachweise. Das ist
  eine neue Lesesicht; E1a-Antworten behalten insbesondere ihr damaliges
  `classification_status:'unclassified'`. Keine alten Proofs oder DTOs ändern.
- Nach späteren Quellenzuordnungen oder einem neuen Profil zeigt die aktuelle
  Sicht „Stand erneut prüfen“. Historische Aussagen bleiben lesbar. Eine
  neue sachliche Version ersetzt nur die aktuelle Vorbereitungssicht; sie ist
  keine Gegenbuchung und verändert keine bereits bestätigten Geld-/Centstände.
  Steuerliche Korrektur und Periodenverwaltung bleiben E1c.

Die Oberfläche trennt „sachlich eingeordnet“, „Quellen/Anteile noch ungeklärt“
und „Steuerbehandlung offen“. `tax_status:'unconfigured'` sowie
`tax_result_available:false` bleiben erhalten. Es entstehen keine
Gewinnsumme, abziehbare Vorsteuer, Steuerperiode oder fertige Anlage EÜR.
Eine bloße Wiederholung des automatisch vorhandenen Quellentyps reicht als
Nutzerergebnis nicht: sichtbar sein müssen Prüfgrund, gebundener Stand,
Änderungshinweis und die verbleibenden Klärungspunkte.

## Technischer Zuschnitt vor Beginn festzulegen

Ein additives Modul mit getrennten unveränderlichen Profil- und
Einordnungsversionen sowie Anfragequittungen; eigene Quellen-/Profil-/
Revisionshashes. GETs schreiben nichts. Vorschau und Bestätigung binden den
erwarteten Stand; Profile konkurrieren unter einem gemeinsamen Schreiblock,
Einordnungen zusätzlich je CashEvent. Exaktes erfolgreiches Replay bleibt vor
heutiger Profil-/Kandidatenprüfung möglich, nach frischer Autorisierung und
historischer Integritätsprüfung. Die bereits eingeführte begrenzte
`not_accepted`-Kennzeichnung und Pendingbehandlung wiederverwenden.

Profiländerungen benötigen `accounting.admin`; Einordnungen
`accounting.prepare` und volle Finanz-/Quellrechte. Die gemeinsame aktuelle
Quellenhülle einschließlich historisch getragener Rücknahmen verwenden;
kein zweiter rekursiver Autorisierungsgraph. Fremde Beträge und Quellen nicht
über die Klärungsliste offenlegen. Modus-, MFA-, Runtime- und Restoregrenzen
gelten auch hier. Neue Tabellen benötigen eigenen Integritäts-/Restorehorizont;
die feste bisherige H6-/Berichtschema-7-Bedeutung bleibt historisch erhalten.
Konkrete DTOs, Tabellen, Folgehorizont und Profilgültigkeitsregeln werden erst
im eigenen API-Vertrag festgelegt, nicht aus diesem Entwurf implementiert.

## Gezielte Abnahmefälle

1. Leerer Bestand/migrierter Altbestand: keine Steuerannahme oder automatische
   Klassifikation. Einzelunternehmen/EÜR mit unbekannter Umsatzsteuer lässt
   sich ausdrücklich festhalten; keine Istbesteuerung wird ergänzt.
2. Einnahme, Lieferantenauszahlung und gemischte R1/R2-Erstattung sachlich
   einordnen: alle Zahlungen, OP, Komponenten und alten Antworten bytegleich;
   unbekannte Teilbeträge und Steuerfragen bleiben sichtbar offen.
3. Profil-/Zuordnungsänderung zwischen Vorschau und Bestätigung: Konflikt ohne
   Teilwirkung. Bereits gespeicherte Aussage bleibt historisch identisch;
   erneute Prüfung erzeugt eine neue Version statt stiller Umdeutung.
4. Antwortverlust, erster 403/404 und unmarkierter 409 erhalten den Befehl;
   identischer Retry liefert exakt die alte Antwort. Zwei echte PG-Verbindungen
   können denselben Profil-/Einordnungsstand nicht widersprüchlich bestätigen.
5. Widerruf eines mittelbar getragenen Quellrechts versteckt die ganze
   betroffene Einordnung samt History/Replay. Preview erzeugt keine Zeile;
   Fehler zwischen Version, Quittung und Audit rollen vollständig zurück.
6. Additive Migration, SQLite-/PG-Unveränderlichkeit, beschädigte Versionskette
   trotz neu berechneter Hashes, Teilinstallation und Restore prüfen. Beide
   Clients führen Profil/Einordnung über echte HTTP-Strecke vor; synthetische
   Steuerprofile bleiben ausschließlich Testdaten.

Erst danach folgen fachliche Klassifikation für ausdrücklich geklärte
Steuerfälle, E1c-Korrektur/Periodensperren und E1d-Beraterpaket. Keine
Steuerübermittlung, Bankanbindung oder externe Nachricht ist Teil dieses
Entwurfs. Auch nach E1b-4a bleibt die vollständige EÜR offen.
