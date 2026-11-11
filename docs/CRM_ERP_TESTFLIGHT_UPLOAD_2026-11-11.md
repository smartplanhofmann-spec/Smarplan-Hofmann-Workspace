# Ausdrücklich freigegebener TestFlight-Upload

Stand: 11.11.2026, Upload von Apple angenommen um 14:25:35 Uhr Europe/Berlin.

Der Nutzer hat die konkrete Frage zum Upload von Smartplan Office,
Bundle-ID `de.smartplanhofmann.office`, Funktionsstand `4bb5071`, geprüftem
signiertem Paket 220 und einem neuen Build mit identischem Programmcode
ausdrücklich mit „Ja, diesen Funktionsstand an Apple TestFlight hochladen“
beantwortet. Der genaue Wortlaut und die Abgrenzung der Freigabe stehen in
[authorization.json](evidence/testflight-upload-2026-11-11/authorization.json).

## Tatsächlicher Auftrag und Quellbindung

Der vorhandene Workflow `ios-testflight.yml` wurde mit
`prepare_signed_ipa=true` und `upload_to_testflight=true` auf dem autorisierten
Testbranch `codex/testupdate-0.7-projects-20261104` gestartet:

- [Lauf 43019931541](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/43019931541), Laufnummer 91.
- Start am 11.11.2026 um 13:23:36 Uhr Europe/Berlin
  (`2026-11-11T12:23:36Z`).
- Tatsächliche Workflowquelle `e9bdb46c9679e52944d6614e7b731c41d7dfa94e`.
- Freigegebene Produktquelle `4bb5071891344a38f640d8ae43ec240c1f95e61e`.

Ein tatsächlicher Git-Objektvergleich bestätigt identische Bäume für `app`,
`backend`, `web`, `scripts`, `.github` und `deploy`. Alle Änderungen dazwischen
betreffen Dokumentation. Die unveränderte Originalzieldatei behält ihre
23.863 Bytes und SHA256
`a4dea28f6de4afd3e36d1549441aad91ce16dad374f56097979cc2d79b07fbf5`.
Der frühere signierte Vorbereitungsnachweis bleibt ausdrücklich bei Upload false.

## Tatsächliches Ergebnis

Die eigene Vorprüfung 130520300731 ist vollständig erfolgreich:
2.031 Apphauptfälle mit fünf ausgewiesenen Linux-Auslassungen, drei native
PDF-Fälle, Codeanalyse, tatsächlicher iOS-Gerätebau und Paket-/Manifestprüfung.
Die tatsächlich erzeugte Buildnummer ist **221**, Appversion **0.13.0**.
Das unsignierte Artefakt 13855909165 ist kein installierbares iPhone-Paket.
Seine GitHub-Metadaten nennen 15.123.862 Bytes und äußere Artefakt-SHA256
`a6bccd8fadf8c1784a598a53760d9130fb08e675335eb58767e3f35304d91021`.

Auch der signierte Auslieferungsjob 130539182159 und der gesamte Lauf sind
erfolgreich abgeschlossen. Beide Apple-Exporte, finale Codesignatur,
Team-/Keychain-/Debugger-Prüfung, tatsächlicher Upload und Bereinigung des
temporären API-Schlüssels sind erfolgreich. Beide Auslieferungsschalter sind
im tatsächlichen Jobprotokoll true.

Apple bestätigt im Uploadprotokoll am 11.11.2026 um **14:25:35 Uhr**
Europe/Berlin (`2026-11-11T13:25:35Z`):

> UPLOAD SUCCEEDED with no errors
>
> Delivery UUID: 67e7fe99-4cad-41fc-83f9-e89da98777eb

Das [signierte Paket 0.13.0 / Build 221](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/43019931541/artifacts/13860365797)
hat Artefaktkennung 13860365797, 30.029.391 Bytes und GitHub-Metadaten-SHA256
`40e004775cfb1d59ec1b696ee64652a98c2bbc9cc77c684a0c4e48d32bab4222`.
Diese Prüfsumme bezeichnet das äußere GitHub-Artefakt-ZIP; dieses wurde hier
nicht erneut lokal heruntergeladen. Der Workflow selbst prüft das exportierte
IPA und legt dessen Manifest sowie SHA256 vor dem Upload ab.

## Anschließende Prüfung

Apples Verarbeitung, tatsächliche Verfügbarkeit für die bestehende Testgruppe
und Installation auf einem echten iPhone sind noch nicht beobachtet.
Der Uploadnachweis setzt keinen dieser Zustände auf erfolgreich.
Nach der Verarbeitung in der vorhandenen TestFlight-App bei Smartplan Office
nach Version 0.13.0 / Build 221 sehen und gegebenenfalls aktualisieren.
Falls der Build nicht automatisch in der bestehenden Gruppe „Smartplan intern“
erscheint, die Buildzuordnung im vorhandenen App-Store-Connect-Eintrag prüfen.
Keine neue Apple-Mitgliedschaft, App-ID oder Testergruppe ist dafür nötig.

Der neue [Ergebnisbeleg](evidence/testflight-upload-2026-11-11/result.json)
und das eigene Prüfskript binden Freigabe, Quellvergleich, beide erfolgreichen
Jobs, Apple-Annahme und Artefaktkennungen zusammen. Die frühere Vorbereitung
220 bleibt unverändert ohne Upload. Alle 37 vorbereiteten echten Gerätefälle
und die Gesamtabnahmen bleiben offen; der Server wurde hier nicht aktualisiert.

Die Rohbelege werden unter
[`docs/evidence/testflight-upload-2026-11-11/`](evidence/testflight-upload-2026-11-11/)
geführt. Der Vorgang autorisiert weder eine App-Store-Veröffentlichung noch
Tester-Einladungen, echte Geschäftsnachrichten, Zahlungen oder Meldungen.
