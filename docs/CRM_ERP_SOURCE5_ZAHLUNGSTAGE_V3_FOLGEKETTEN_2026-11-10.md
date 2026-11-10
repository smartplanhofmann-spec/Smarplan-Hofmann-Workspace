# Source5 V3: spätere Bonuspräfixe und ursprünglicher Jahreszufluss

Der anschließende echte Rückzahlungs-/Reiseablauf zeigte, dass weitere
Verbraucher die vollständig belegten späteren Bonuszahlungen noch wie neue
Reisezahlungen oder einen neuen Bruttozufluss behandelten. Die folgenden
Korrekturen vervollständigen den bereits versionierten V3-Fall. Neue
Lohnsteuerformeln oder Bruttoereignisse werden nicht eingeführt.

Die allgemeine Reisemonatsprüfung erhält nun aus dem bereits vollständig
aufgelösten V3-Zahlungsplan sämtliche reinen Bonusindizes. Dazu gehören auch
zuvor validierte V3-Bonusteile innerhalb des unveränderten Präfixes. Laufende
Zahlungs-/Reiseteile behalten ihre Datumsprüfung. Jeder vorherige Ursprung und
seine damalige Zulässigkeit werden zuvor unverändert rekonstruiert. Ein bloß
umgewidmeter oder retimierter alter Transfer wird nicht dadurch freigegeben.

Die Jahresprojektion erkennt ausdrücklich Zahlungsfassung 3. Ihre vollständige
Source5-/Präfixprüfung erfolgt vor der Projektion; zusätzlich bleibt mindestens
ein positiver Bonuszahlungsnachweis am ursprünglichen Bruttoereignistag nötig.
Alle späteren Nettofakten müssen bis zum Jahresstichtag belegt sein. Sie
ersetzen weder Bruttozufluss noch Anspruch oder SV-Zuordnung. Der ursprüngliche
Bonus wird genau einmal fortgeschrieben. Alte Zahlungsfassungen 1/2 behalten
unverändert ihre Datumsregel und Ergebnisse. Das kompakte Referenzformat bleibt
inhaltlich gleich; der neue Zahlungsfall ist an seiner ausdrücklichen
Zahlungsfassung erkennbar. Die 32 historischen 2026-Kerne werden nicht verändert.

Der neue tatsächliche PostgreSQL-/MFA-Folgefall erhält einen Lohnlauf mit
Reiseanteil, verbucht eine zusätzliche Bonuszahlung am 01.11. und eine weitere
am 02.11., erhält den ganzen Präfix und schreibt anschließend genau 500 EUR
ursprünglichen Bonus einmal in die Jahresbasis fort. Dieser Nachlauf besteht
in 101,856 Sekunden. Sein vorheriger Teilablauf ohne Jahreserweiterung besteht
in 65,954 Sekunden. 32 bestehende Backendfälle in 253,597 Sekunden und
15 historische Jahresfälle in 6,899 Sekunden bestehen ebenfalls.

Die native Zusammenfassung benennt den ursprünglichen Bruttozufluss und den
separat tatsächlich belegten zulässigen Nettozahlungstag; sie behauptet nicht
mehr pauschal dieselben Tage. Acht vorhandene V2-/V3-Bedienfälle bestehen.
Der vollständige 1.872-Fälle-Appnachweis gehört weiterhin zum ursprünglichen
Produktstand 17978f6. [Quellhashes und eigene Rohläufe](evidence/source5-payment-dates-prefix-2026-11-10/manifest.json).
Diese Nachprüfung ist keine neue Liveinstallation oder Gesamtfreigabe.
