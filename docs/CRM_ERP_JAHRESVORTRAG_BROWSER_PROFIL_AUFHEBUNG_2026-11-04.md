# Historischen Jahresvortrag trotz fehlendem heutigem Startdatum aufheben

Dieser enge Browsernachtrag ergänzt den unverändert erhaltenen Handoff
`year-values-browser-2026-11-04/manifest.json` (SHA-256 `7307bc17…`). Die
ursprüngliche unabhängige Gegenprüfung `d4a11801…` bleibt ebenfalls unverändert.

Die zusätzliche tatsächliche Backendfixture belegt: Ein Jahresvortrag wurde
angenommen und in die EÜR übernommen. Vor der EÜR-Gegenbuchung war seine
Aufhebung mit 409 gesperrt. Nach der ausdrücklich angenommenen Gegenbuchung
und dem Wegfall des heutigen Profilstartdatums erlaubte der Server die
ursprüngliche historische Aufhebung. Die Browserdetailansicht bot diesen Weg
zuvor nicht an. Der separate rote Gegenbeleg bleibt archiviert.

Die Oberfläche bietet jetzt die Aufhebung einer vorhandenen aktiven
Originalfassung unter aktuellen Lese-, Schreib- und Finanzmodulrechten
getrennt von neuen Übernahmen an. Die Ausnahme ist an Jahr, Originalkennung,
Fassung und Inhaltshash gebunden. Das vollständige Originalpayload und sein
ursprünglicher Profilbezug werden übernommen; ausschließlich der Status wird
`void`. Der aktuelle Journalstand und eine ausdrücklich eingegebene Begründung
bleiben erforderlich. Die tatsächliche Servervorschau prüft weiterhin
Schreibfreigabe, Folgebuchungen und Periodensperren. Vor jeder neuen Anfrage
wird die unveränderte aktive Originalfassung erneut geprüft.

Neue oder berichtigte aktive Übernahmen benötigen unverändert das heutige
vollständige Profil und `can_prepare`. Der Nachtrag erlaubt keine freien
Aufhebungsdaten, keine neue Geldbewegung, keinen neuen Vorsteueranspruch und
keine automatische EÜR-Gegenbuchung. Bereits angenommene verlorene
Bestätigungen werden mit exakt demselben Auftrag wiederholt.

Die abschließenden fokussierten Tests bestehen **64/64 Fälle**: 27 eigene und
37 unabhängige, darunter sieben neue historische Aufhebungsfälle. Sie prüfen
auch aktuelle Rechte nach Öffnen des Dialogs, Modulabschaltung, veränderte
Originalfassung und unveränderte Wiederholung bei weiterhin fehlendem Profil.
Der separate echte Chromium-/MFA-/HTTP-Nachtrag führt zunächst den unveränderten
vollständigen Jahresvortragsablauf aus und prüft anschließend den tatsächlichen
Profilwechsel, gesperrte aktive Entwürfe, historische Aufhebung und verlorene
Bestätigungsantwort. Fünf unveränderliche Jahresfassungen bleiben lesbar.

Produktänderungen betreffen ausschließlich `accounting-year-values-contract.js`
und `accounting-year-values.js`. Backend, Nativeclient und die bereits
zusammengeführten Office-/EÜR-Dateien bleiben unverändert. Nachweise,
Vorher-/Nachherhashes und genaue Dateien stehen in
`docs/evidence/year-values-browser-profile-void-2026-11-04/manifest.json`.
