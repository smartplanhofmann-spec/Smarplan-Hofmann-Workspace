# Unabhängige native Jahresquellenprüfung

Die zusätzliche Prüfung bestand mit **10 von 10 Fällen**; die gezielte Analyse
der Jahresquellenseite, Formulare und Gegenprüfungsdatei meldete bei drei Dateien
keine Befunde. Es handelt sich um Flutter-Hostprüfungen mit synthetischem
Transport und tatsächlichen unveränderlichen Fachfixtures.

Der erste Lauf reproduzierte drei Fehler: Ein privater Korrekturdialog blieb
bei Mitarbeiterwechsel offen; ein Entzug der Freigabeberechtigung bei weiter
bestehendem Leserecht beendete den Dialog nicht; eine bereits ausstehende
Vorschau konnte anschließend den überholten Schreibablauf wieder anzeigen.
Der Produktowner ergänzte den Kontextwechsel einschließlich Sessionlistener,
Entwurfs- und Dialogbereinigung sowie einen ausdrücklich erkannten Übergang
beim Freigabeverlust. Frühere Antworten können den neuen Kontext nicht öffnen
oder dessen laufenden Vorgang entsperren.

Die unabhängigen Gegenfälle prüfen zusätzlich Sessionersatz, verspätete
Originalfreigabe nach Hintergrundwechsel und die tatsächliche
`repeatPayrollAnnualBasisCommand`-Methode. Falsche Person, unbekannte Jahresart,
fremder Quellenkatalog und ausgetauschte Quittung mit falscher Person, Art oder
Jahr werden verworfen. Der ursprüngliche Auftrag und seine Nonce bleiben
unverändert erhalten, bis die ursprüngliche richtige Quittung geprüft ist.

Zwei ergänzte Kontextfälle erweiterten den ersten Lauf von acht auf zehn
Prüfungen. Die 27 Prüfungen des Produktowners sind separat; dessen gemeinsamer
Regressionslauf meldet 37. Diese Zahlen werden nicht als 47 verschiedene Tests
addiert. Eine reale Geräteabnahme oder amtliche Lohnübermittlung ist damit
nicht behauptet. Der Download-Gegenfall hält die Freigabe vor Aufruf des
Downloadcallbacks an und behauptet keine nachträgliche Rücknahme bereits
abgerufener Dateien.

Rot- und Grünprotokolle, genaue Befehle und Dateiprüfsummen:
[evidence/payroll-annual-native-review-2026-11-03.json](evidence/payroll-annual-native-review-2026-11-03.json).
