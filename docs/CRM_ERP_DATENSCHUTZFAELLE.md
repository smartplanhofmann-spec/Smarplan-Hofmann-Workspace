# Verwaltete Betroffenenanfragen

Stand: 3. November 2026. Implementierter interner Bearbeitungsweg für Auskunft,
Datenexport, Berichtigung und Löschprüfung. Dies ist kein automatischer Nachweis
vollständiger DSGVO-Konformität und keine automatische Löschung aller Daten einer Person.

## Bearbeitung in Browser und Flutter

Unter **Einstellungen → Datenschutzfälle** und im Kontaktbereich können ausdrücklich
berechtigte Bearbeiter einen Fall aufnehmen. `privacy.manage` wird nicht pauschal an
eine Rolle vergeben. Die namentliche Auswahl umfasst tatsächlich lesbare Kontakte,
Mitarbeiter und, für die Geschäftsführung, Benutzer. Der Browser kann die Auswahl
nach Namen eingrenzen; die native Auswahl ist auf die serverseitig begrenzte erste
Treffermenge beschränkt. Umfang, verantwortliche Person, Eingangsdatum, geprüfte
Antwortfrist sowie Zweck und Ende der privaten Fallaufbewahrung sind Pflichtangaben.
Die Anwendung setzt weder eine allgemeingültige gesetzliche Antwortfrist noch eine
pauschale Aufbewahrungsfrist fest.

1. Tatsächlich durchgeführte Identitätsprüfung und deren Nachweis dokumentieren.
   Es werden keine Ausweiskopien angefordert. Eine begründete Ablehnung ist auch
   bei ungeklärter Identität möglich, ohne eine Prüfung vorzutäuschen.
2. Strukturierte Quellen erfassen. Die Anwendung verknüpft bekannte Fremdschlüssel
   und polymorphe Zusatzfelder mit dem Betroffenenanker. Jede Quelle hat einen
   konkreten Primärschlüssel und Inhalts-Hash. Zweck, Schutzbedarf und
   Aufbewahrungsgrund stammen aus `company_export_catalog.py`.
3. Jede Quelle ansehen und begründet entscheiden: unveränderte Auskunft,
   redigierter Auskunftstext, Aufbewahrung, fehlender Personenbezug oder gesonderte
   Anonymisierung des Kontaktstamms. Originaldateien erfordern eine zusätzliche
   ausdrückliche Prüfung auf Daten anderer Personen.
4. Die sieben manuellen Prüfbereiche tatsächlich bearbeiten: Freitext,
   Originaldateien/Fremdpersonen, historische Nachweise und technische Quittungen,
   externe Systeme/lokale Dateien, Empfänger/Kopien, Backups sowie gesetzliche
   Aufbewahrung und Sperren. Offene Prüfungen verhindern einen freigegebenen Export.
5. Eine geprüfte Auswahl als zeitlich verfügbares ZIP bereitstellen, zulässige
   Stammdaten berichtigen oder eine konkrete Kontaktanonymisierung prüfen.
6. Tatsächlich erfolgte Antwort oder Übergabe mit Nachweis erfassen und den Fall
   vollständig, teilweise oder begründet abgelehnt abschließen. Die Anwendung
   versendet dabei keine Nachricht. Fristverlängerungen benötigen einen Nachweis
   der erfolgten Information; sie werden nicht stillschweigend als zulässig gewertet.

Ein Quellenbestand ist auf 1.000 Datensätze und fünf Verknüpfungsschritte begrenzt.
Unbekannte Tabellen werden abgewiesen. Ausgelassene oder nicht zugängliche
Datenarten und die Grenze der Verknüpfungstiefe bleiben ausdrücklich sichtbar.
Freie Namensnennungen, JSON-Snapshots, externe Dateien, Empfänger und Sicherungen
werden dadurch nicht automatisch vollständig zugeordnet. Neue oder geänderte
strukturierte Quellen machen eine erneute Prüfung erforderlich. Ein fehlendes
Quellenrecht wird nicht durch das Fallrecht ersetzt.

## Auskunft, Berichtigung und Löschung

Der Personenexport enthält `subject-data.json`, eine Übergabeinformation und nur
ausdrücklich ausgewählte Originaldateien. Größe und SHA-256 werden in beiden
Clients geprüft; das Archiv und sein unkomprimierter Fachinhalt sind jeweils auf
8 MB begrenzt. Es ist **nicht verschlüsselt**. Die sichere Übergabe bleibt eine
bewusste Aufgabe des Bearbeiters. Passwort-, Schlüssel- und Zugangsspalten des
Exportkatalogs werden auch dann nicht ausgegeben, wenn sie binär gespeichert sind.
`automatic_completeness` und `external_messages_sent` bleiben ausdrücklich falsch.
Die bestehende Kontaktauskunft wird als Fachprüfung einbezogen, ohne deren
ungeprüfte vollständige Nutzlast automatisch in das neue Archiv zu kopieren.

Kontaktberichtigungen verwenden die vorhandene versionierte Stammdatenfunktion.
Für Personal-, Finanz- und andere Fachhistorien ist die jeweilige bestehende
Fachberichtigung mit Quellenbezug erforderlich; der Fallweg überschreibt diese
Historien nicht. Die Kontaktanonymisierung nutzt `foundation.erase_contact` mit
aktueller Revision, unabhängiger Löschprüfung und allen vorhandenen Sperrgründen.
Projekt-, Finanz-, Service-, Zusatzfeld- und sonstige aufzubewahrende Historien
lassen sich nicht durch eine manuelle Freigabe im Fall umgehen. Eine erfolgreiche
Aktion betrifft ausschließlich den Kontaktstamm. Der dokumentierte Fallzweck und
die private Fallaufbewahrung bleiben gesondert bestehen.

## Private Arbeitskopien und Zugriffsgrenzen

Sechs additive Tabellen trennen unveränderliche minimale Fallereignisse,
Exportmetadaten und Löschmarker von tatsächlich löschbaren privaten Fall- und
Export-BLOBs. Alle historischen privaten Fallstände liegen in diesen löschbaren
BLOBs. Die Tabellen liefern keine zusätzliche Verschlüsselung auf Datenbankebene;
Datenträger-, Datenbank- und Sicherungsschutz bleiben Betreiberaufgaben.
Technische Wiederholungsquittungen enthalten ausschließlich Hashes und Referenzen,
keine Originaleingaben oder vollständigen Antwortkopien.

Fallzugriff benötigt das frische Fallrecht, Zuordnung als Ersteller/Verantwortlicher
oder Geschäftsführung und die aktuellen Rechte der betroffenen Person und Quellen.
Projektzuordnung, Kontaktrechte, Personalrechte und Finanzrechte werden erneut
geprüft. Personalexporte verlangen zusätzlich `personnel.export`, auch beim späteren
Download. Bankquellen benötigen gleichzeitig `bank.read`, `accounting.read` und
`finance.read`; eine freie Gegenpartei oder ein Verwendungszweck wird nicht
automatisch als Kontaktverknüpfung gedeutet. Einkaufs- und Retourenquellen verlangen
`inventory.read` und `finance.read` sowie den Zugriff auf das tatsächliche
Bestellprojekt, auch wenn die einzelne Nachweiszeile nur einen Wareneingangs- oder
Retourenschlüssel trägt. Betriebsmittelquellen verlangen zusätzlich die globalen
Rechte `planning.read` und `planning.write`. Unklassifizierte vollständige Rohzeilen bleiben konservativ der
Geschäftsführung vorbehalten; delegierte Bearbeiter sehen diese Grenze.

Private Entwürfe und unbestätigte Aufträge bleiben ausschließlich im Arbeitsspeicher
der Clients. Bei unbekannter Antwort kann die eigene gespeicherte Referenz gelesen
oder genau derselbe Auftrag unverändert wiederholt werden. Fremde oder nicht zum
Fall passende Quittungen bestätigen keinen Auftrag. Abmelden, Schließen,
Sitzungs-/Quellenrechtewechsel und Hintergrundwechsel der nativen App verwerfen
private Inhalte. Verspätete Antworten dürfen geschlossene Ansichten nicht erneut
öffnen oder Downloads nach entzogener Freigabe weiterreichen.

## Aufbewahrungsende und Wiederherstellung

Abgelaufene Exporte sind nicht mehr herunterladbar. Ihre physische Bereinigung ist
eine ausdrückliche Aktion der Geschäftsführung. Fallinhalte können erst nach
Abschluss und Ablauf der dokumentierten Aufbewahrung ohne aktive Sperre bereinigt
werden. Eine Frist allein löst keine automatische physische Löschung aus.

Vor beiden Bereinigungen wird ein außerhalb der Datenbank verwahrter, authentisierter
Privacy-Checkpoint geschrieben. Erst danach werden passende Löschmarker eingefügt
und private BLOBs entfernt. Ohne den unabhängigen Nachweis bleibt die Löschung
gesperrt. Datenbank-Guards verhindern unbestätigtes Löschen, Überschreiben und
Wiedereinfügen bereinigter Inhalte. Unveränderliche minimale Hashnachweise bleiben
zum Abgleich mit Sicherungen erhalten; ihre langfristige organisatorische
Aufbewahrung bedarf einer eigenen Zweckprüfung.

Bei Wiederherstellung eines **älteren** Backups wird der aktuelle unabhängige
Checkpoint angewandt: bereits anonymisierte Kontakte und gelöschte Fall-/Exportkopien
leben nicht wieder auf. Fehlt der erforderliche externe Nachweis, wird die
Wiederherstellung nicht freigegeben. Andere Geschäftsdaten und Finanznachweise
bleiben unverändert. Private Fall- und Export-BLOBs sind absichtlich vom allgemeinen
Unternehmensexport ausgeschlossen; dieser darf die besondere Fallfreigabe und
Ablauffrist nicht umgehen. Minimale Fach-/Löschmetadaten bleiben katalogisiert.

## Nachweise

Gezielte synthetische Abnahme mit aktualisiertem Backend-Prüfstand:

- **19 Domänen-/HTTP-Tests:** tatsächliche MFA, striktes Transportformat,
  Identität, Fristen und manuelle Prüfung, unveränderte Wiederholung, Referenzstatus,
  Quellenänderungen, Kontaktberichtigung/-anonymisierung, Personal- und Bankquellenrechte,
  Bestellprojektbindung und konservative Betriebsmittelquellen,
  Geheimnisausschluss, private Löschung und alte SQLite-Sicherung.
- **1 echter PostgreSQL-/Restore-Test:** eingeschränkte Runtime-Rolle, getrennte
  Ownership, MFA, Neustart, Datenbank-Guards, echtes vorangegangenes `pg_dump`,
  fehlender externer Nachweis, danach Wiederherstellung mit aktuellem Checkpoint;
  private Kopien entfernt, andere Fall- und Finanzdaten unverändert.
- **8 JavaScript-Vertragstests:** RAM-Aufträge, fremde Quittungen, Rechteentzug,
  verspätete Ansichten und hashgeprüfte Downloads.
- **9 Flutter-Tests:** dieselben Auftragsgrenzen, tatsächlicher Identitätsdialog,
  Quellenrechteentzug und Hintergrundwechsel.
- **1 echter Chromium-Ablauf:** namentliche Auswahl, absichtlich verlorene
  Aufnahmeantwort, reine Statusabfrage ohne zweiten POST, Identität, alle Quellen-
  und manuellen Entscheidungen, ZIP-Download/Hash sowie Desktop und 390-Pixel-Ansicht.
- Gezielte Dart-Analyse ohne Befund.

Testdateien: `backend/test_business_privacy_cases.py`,
`backend/online/test_business_privacy_cases_http.py`,
`backend/online/test_business_privacy_cases_pg.py`,
`web/office/tests/privacy-cases.test.mjs`, `web/office/tests/privacy-cases-flow.cjs`,
`app/test/business_privacy_cases_test.dart`. Lokale Laufprotokolle und Screenshots
liegen unter `work/verification/privacy-cases-*`; diese enthalten ausschließlich
synthetische Testpersonen. Keine externe Auskunft oder Nachricht wurde versandt.
