# Ausdrücklich freigegebener TestFlight-Upload

Stand: 11.11.2026, laufender Auslieferungsvorgang.

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

## Ergebnisgrenzen

Die eigene Vorprüfung 130520300731 ist vollständig erfolgreich:
2.031 Apphauptfälle mit fünf ausgewiesenen Linux-Auslassungen, drei native
PDF-Fälle, Codeanalyse, tatsächlicher iOS-Gerätebau und Paket-/Manifestprüfung.
Die tatsächlich erzeugte Buildnummer ist **221**, Appversion **0.13.0**.
Das unsignierte Artefakt 13855909165 ist kein installierbares iPhone-Paket.
Seine GitHub-Metadaten nennen 15.123.862 Bytes und äußere Artefakt-SHA256
`a6bccd8fadf8c1784a598a53760d9130fb08e675335eb58767e3f35304d91021`.

Der signierte Auslieferungsjob 130539182159 läuft. Der Upload ist noch nicht
erfolgreich bestätigt. Signatur, Apple-Annahme und Schlüsselbereinigung werden
aus den tatsächlichen Ergebnissen dieses Laufs übernommen. Apple-Verarbeitung,
Freischaltung für Tester und Installation auf einem echten Gerät sind
anschließende getrennte Nachweise. Ein erfolgreicher Upload allein belegt
diese Schritte nicht.

Die Rohbelege werden unter
[`docs/evidence/testflight-upload-2026-11-11/`](evidence/testflight-upload-2026-11-11/)
geführt. Der Vorgang autorisiert weder eine App-Store-Veröffentlichung noch
Tester-Einladungen, echte Geschäftsnachrichten, Zahlungen oder Meldungen.
