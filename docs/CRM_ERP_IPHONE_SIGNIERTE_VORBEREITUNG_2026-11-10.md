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
