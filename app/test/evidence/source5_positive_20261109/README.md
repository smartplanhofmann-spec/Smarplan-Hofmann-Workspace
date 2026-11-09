# Native positive Source5-Korrektur

Die gemeinsame Fixture `app/test/fixtures/source5_positive_corrections.json`
enthält echte angenommene Originale aus dem isolierten Backend-Workflow:
erste v1-Zahlung, danach zwei positive v2-Korrekturen mit 1.000 und 2.900 Cent
zusätzlichem Netto. Die Widget-Tests verwenden diese Originale mit einem
kontrollierten Transportadapter; sie sind kein Live-Server- oder Gerätetest.

Der abschließende Satz besteht aus 22 Tests: fünf neue Vertragsfälle, sechs
neue Widgetfälle und elf bisherige v1-/Source5-Fälle. Alle bestehen ohne Skip.
Die abschließende App-Analyse ist ohne Befund. Befehle und Quellhashes stehen
in `verification.json`, exakte Rohprotokolle komprimiert neben dieser Datei.

Geprüft sind die vollständige Original-/Plan-/Übergangshashbindung, explizite
nicht vorbelegte Vollständigkeitsbestätigungen mit Personaloriginal,
unveränderte alte Zahlungs- und Zuordnungspräfixe, positive neue Beträge,
belegter Zuflusstag, frische Rechte und Featuregrenzen. Verlorene Antworten
behalten denselben Pending-Auftrag. Verspätete Antworten nach Schließen der
Zahlungsansicht, des Korrekturgrunddialogs oder des Reviewdialogs öffnen keinen
geschlossenen Editor erneut.

Die ersten fehlgeschlagenen Läufe bleiben erhalten. Sie fanden einen falschen
Nullable-Zugriff, zwei Testablaufprobleme bei verschachtelten Dialogen und
einem noch nicht gerenderten Wiederholknopf sowie lokale Formularvalidierung,
die irrtümlich als unbestätigte Serverantwort behandelt wurde. Die unabhängige
Codegegenprüfung fand außerdem fehlende Routengrenzen nach späten Leseantworten
und den zunächst optionalen Vorschauhash. Diese Punkte sind korrigiert und
mit eigenen Negativfällen erneut geprüft. Die Nachprüfung meldet keine weitere
konkrete Lücke.

V1-Originale und ihre Vertragsform bleiben erhalten. Die Erweiterung versendet
keine Überweisung und gibt weder Netto-Rückforderungen noch geänderte
Bruttoereignisse, andere Zuflusstage oder überzahlte Abführungen frei.
