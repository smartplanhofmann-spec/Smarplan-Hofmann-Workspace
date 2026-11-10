# Tatsächlich signiertes iPhone-/iPad-Paket 205

Quelle `1fa0bcceb28a822bed9600ad18e33ba54d2c227f` mit Qonto-Eigenkonto-
Lesezugang und Faktor-Einmalbezug V15. Der spätere Offline-Konfliktfix abcc351
und der nachfolgende XML-Bankimport sind darin nicht enthalten.

[Signiertes Paket Smartplan-Office-iOS-205](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42843099650/artifacts/13780314712):
29.912.158 Bytes, Artefakt 13780314712, SHA256 des GitHub-Artefakts
`3c588807c9b0fdede6458828cdbb0420dbee931d63749aaee5610b6a66e3166e`.

Der manuelle Vorbereitungslauf 42843099650 besteht mit dem vollständigen
unsignierten Client und dem tatsächlichen Signierjob 129953336253. Der feste
macOS-Intel-Runner beseitigt die zuvor unbelegte Runner-Zuordnung. Endgültiger
Apple-Export, Codesignatur, konkretes Distributionsteam, eigene Keychain-Gruppe,
Debuggersperre, Version, Quellmanifest und Schlüsselbereinigung bestehen.

`upload_to_testflight=false`: Kein TestFlight-Upload und keine neue reale
Geräteinstallation. Ein signiertes App-Store-IPA allein ist keine eingerichtete
TestFlight-Verteilung. Die vorhandene Apple-Einrichtung wurde verwendet.

Die eigene Development-Prüfung derselben Quelle besteht alle 20 Gruppen;
der automatische unsignierte Release 204 bleibt getrennt erhalten. Der spätere
Offline-Konfliktstand abcc351 besteht inzwischen ebenfalls alle 20 Gruppen und
seinen eigenen unsignierten iPhone-Release 206. Keines dieser Ergebnisse
beweist eine neuere Installation auf dem Kundengerät oder dem Live-Server.

Unveränderte Job- und Artefaktmetadaten:
[Nachweis](evidence/factor-oneoff-2026-11-10/own-signed-iphone-complete-20261110.json).
