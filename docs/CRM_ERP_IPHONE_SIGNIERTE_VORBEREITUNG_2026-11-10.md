# Signiertes iPhone-Paket getrennt vom TestFlight-Upload

Stand10.11.2026. Auftrag bleibt das vollständige unveränderte Gesamtziel.
Arbeitskopie `/workspace/smartplan-ios-signed-preparation-20261110`,
Basis e5ce894. Der Client ist0.13.0+130; Bundle-ID und bestehende Apple-
Einrichtung bleiben erhalten. Kein neuer Apple-Beitritt oder App-Eintrag nötig:
Der Nutzer hat die per TestFlight installierte0.5.1/Build108 bereits bestätigt.

## Tatsächlich gefundene Auslieferungslücke

Der vorhandene Workflow gestattet den signierten Job nur auf dem alten Branch
codex/smartplan-office-0.2 und verbindet ihn zwingend mit einem Upload. Damit
fehlt auf dem ausschließlich autorisierten aktuellen Testbranch die Möglichkeit,
ein signiertes Paket vorher getrennt vorzubereiten. Die beiden ersten Tests
gegen die tatsächlichen Workflow-Bedingungen zeigen diesen Fehler rot.

## Änderung

Der manuelle boolesche Eingang `prepare_signed_ipa` ist standardmäßigfalse.
Der bestehende `upload_to_testflight` bleibt standardmäßigfalse. Der signierte
Job benötigt einen manuellen Start, mindestens eine ausdrückliche Auswahl und
einen von genau zwei bestehenden freigegebenen Branches: bisherigen Releasebranch
oder exakten autorisierten codex/testupdate-0.7-projects-20261104. Ähnlich
benannte andere Testbranches sind nicht freigegeben. Push/PR und ein normaler
manueller Start wählen keine Signierung aus.

Ein zusätzlicher lokal ausgeführter Guard verlangt genau true/false für beide
Eingaben, den manuellen Anlass, einen freigegebenen Branch und den vollständigen
kleingeschriebenen40stelligen Quellcommit. Er läuft nach Checkout vor Prüfung
der Apple-Einrichtung. Seine Entscheidung wird ohne Geheimniswerte im Artefakt
gesichert. Sie bezeichnet signed_only oder ausdrücklich upload.

Die vorhandene Codesignaturprüfung, Team-/Keychain-Entitlements, Quellmanifest,
IPA-Prüfsumme und Schlüsselbereinigung bleiben erforderlich. Das signierte
Artefakt wird vor dem Upload gesichert. Der eigentliche Upload-Schritt besitzt
zusätzlich seine eigene ausdrückliche Bedingung `inputs.upload_to_testflight`.
Es werden keine neuen Abhängigkeiten oder realen Geschäftsdaten eingeführt.

## Tatsächliche lokale Prüfung

[33 gemeinsame Fälle](evidence/ios-signed-preparation-2026-11-10/manifest.json)
bestehen in26,174s: sechs neue Auslieferungsfälle,19
vorhandene native Paketfälle und acht CI-Verträge. Die echten Workflow-Ausdrücke
werden mit48 Kombinationen aus Anlass, Branch, Vorbereitung und Upload
ausgewertet und mit dem tatsächlich aufrufbaren Python-Guard verglichen.
Zusätzliche Gegenproben betreffen mehrdeutige Eingaben, Fremdbranches, ungültige
Commits, fehlende Auswahl, Reihenfolge und den wirklichen CLI-Aufruf.

Der erste gemeinsame Lauf enthält zwei erhaltene Testaufbaufehler: ein zu kurz
gelesener YAML-Eingabeblock und die noch nicht verbundene bestehende virtuelle
Backendumgebung der neuen Arbeitskopie. Nur Testleser/Umgebung wurden korrigiert;
kein Paketvertrag wurde dafür gelockert. Die vorherigen roten Auslieferungs-
Gegenproben bleiben ebenfalls erhalten.

## Grenzen und nächster wirklicher Nachweis

Noch kein neuer tatsächlicher signierter Export, kein TestFlight-Upload und
keine neue echte iPhone-Abnahme. Der Versuch, ausschließlich GitHub-Secret-Namen
abzufragen, wurde von der GitHub-Integration mitHTTP403 verweigert. Dies beweist
keine fehlenden Apple-Secrets; Werte wurden nicht angefragt. Die Vorbereitung
verwendet dieselben vier vorhandenen Secret-Namen. Ein wirklicher signierter
Vorbereitungslauf muss aus seinem eigenen Ergebnis beurteilt werden.

Vor einem echten Upload sind die bestehende Exportkonformitätsangabe und die
tatsächliche Verschlüsselungsnutzung abzugleichen. Ein lokaler Workflow-Test
ersetzt weder Apple-Signierung noch echte Geräte-/Fach-/Gesamtabnahme.


## Tatsächlicher erster Apple-Lauf und Keychain-Reparatur

Run42796610215 an deebe20 bestätigt die vorhandene Apple-Einrichtung. Der
vollständige unsignierte Client besteht, das wirkliche Archiv und der signierte
Apple-Export gelingen. Erst die anschließende Paketprüfung scheitert am fehlenden
Keychain-Entitlement. Das fehlerhafte Paket wird weder als Artefakt freigegeben
noch zu TestFlight hochgeladen. Der unabhängige Development-Lauf42796495383
besteht alle20 Gruppen. Rohdaten einschließlich vollständigem ersten Fehlerlog
bleiben im verlinkten Nachweisarchiv erhalten.

Die leere bisherige Quellgruppe wird durch genau
`$(AppIdentifierPrefix)$(PRODUCT_BUNDLE_IDENTIFIER)` ersetzt. Das unsignierte
Archiv enthält jedoch keine Signatur, aus der Xcode zusätzliche Berechtigungen
beim Export erhalten kann. Der neue Ablauf verwendet deshalb zunächst einen
privaten temporären Apple-Export, verifiziert dessen Signatur und liest sein
wirkliches App-Store-Profil. Ein kleiner lokaler Guard verlangt konkrete eigene
App-Kennung, erwartetes Team, tatsächlichen App-ID-Präfix, erlaubte eigene
Keychain-Gruppe, gültiges App-Store-Profil und ausdrückliche Debuggersperre.
Ein alter App-ID-Präfix darf vom Team abweichen und wird niemals erraten.

Die bereits von Apple signierten verschachtelten Frameworks bleiben erhalten.
Nur das temporäre Hauptarchiv erhält die validierten Entitlements mittels
Ad-hoc-Signatur. Anschließend exportiert Xcode dieses Archiv erneut mit der
bestehenden Apple-Distributionssignierung. Erst dieses endgültige IPA darf
Artefakt werden; dessen Codesignatur, tatsächliches Distributionsteam,
Distribution-Autorität, konkrete eigene Keychain-Gruppe und explizite
Debuggersperre sind erneut Pflicht. Kein temporäres Paket ist veröffentlichbar.
Die bestehende zusätzliche Auswahl für TestFlight bleibt unverändertfalse.

39 gemeinsame lokale Paket-, Auslieferungs- und CI-Fälle bestehen in33,283s;
alle22 tatsächlichen Shellblöcke und YAML sind syntaktisch geprüft. Darunter
sind reale Plist-/CLI-Aufrufe, abweichender alter App-ID-Präfix, abgelaufenes
oder fremdes Profil, falsche Gruppe, zusätzliche Freigaben, fehlende Debugger-
sperre, Ausgabedateischutz und tatsächliche Workflow-Reihenfolge. Ein früherer
30-Fälle-Lauf bleibt getrennt erhalten. Der Parser fehlt in der Projektvenv;
der Operator-Syntaxcheck benutzt den vorhandenen Systemparser, ohne die App-
Abhängigkeiten zu ändern. Die tatsächliche macOS-Gegenprobe der Reparatur steht
aus und wird nicht aus lokalen Tests abgeleitet.

Primärquellen: [Apple TN2415](https://developer.apple.com/library/archive/technotes/tn2415/_index.html)
und [Keychain-Konfiguration](https://developer.apple.com/documentation/xcode/configuring-keychain-sharing).
Der Mechanismus wird zusätzlich durch den öffentlichen
[Tauri-Fehlerbericht](https://github.com/tauri-apps/tauri/issues/15663) beschrieben;
dies ersetzt den eigenen tatsächlichen macOS-Nachweis nicht.
