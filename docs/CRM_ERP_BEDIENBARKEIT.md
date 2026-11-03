# Bedienbarkeit und Barrierefreiheit – tatsächliche Browserprüfung

Stand: 3. November 2026. Die lokale Chromium-Abnahme prüft 18 tatsächlich
gerenderte Ansichten mit echten HTTP-/MFA-Sitzungen und synthetischen Daten.
Die Browser-Sandbox bleibt eingeschaltet. Verwendet wird axe-core 4.14.0 mit
den Regeln WCAG 2 A/AA, 2.1 AA und 2.2 AA.

Geprüft wurden die Anmeldung, zwölf Hauptbereiche, der Kontaktdialog und auf
390 × 844 Pixeln die Übersicht, Kontakte, Finanzen und Einstellungen. Der
abschließende Lauf fand keine automatisiert feststellbaren Regelverletzungen.
Die mobilen Ansichten hatten keinen horizontalen Überlauf. Vier vorwärts und
rückwärts ausgeführte Tab-Schritte blieben im Dialog; Escape schloss ihn und
gab den Fokus an die auslösende Schaltfläche zurück.

Die erste Prüfung fand zu schwache Hilfstextkontraste und einen rückwärts aus
dem Dialog entweichenden Tastaturfokus. Die gemeinsame Textfarbe wurde
abgedunkelt. Die Fokussteuerung berücksichtigt jetzt nur sichtbare, aktive
Eingabeelemente und fängt auch einen Start auf dem Dialogcontainer ab.
Die Finanznavigation besitzt eine beschriftete Gruppensemantik.

Der vollständige maschinenlesbare Nachweis steht in
[accessibility-2026-11-03.json](evidence/accessibility-2026-11-03.json).
`web/office/tests/accessibility-flow.cjs` ist als eigener Ablauf in der CI
eingebunden. Alle von axe als nicht abschließend entscheidbar markierten
Selektoren bleiben im Nachweis erhalten, darunter dekorative Navigationszeichen,
ein Browserformularfeld und eine beschriftete Gruppe. Diese Einträge werden
nicht als automatisch bestandene Einzelprüfungen ausgegeben.

Dieser Stichprobenlauf ist keine vollständige WCAG-Konformitätsbescheinigung.
Ausstehend sind insbesondere eine menschliche Screenreader-Abnahme, sämtliche
Fachdialoge, Zoom und hohe Kontraste sowie die tatsächlichen Windows-/iPhone-
Bedienhilfen. Die einzelnen Fachabläufe besitzen ergänzende Funktionsprüfungen;
deren Erfolg ersetzt diese Bedienhilfenprüfungen nicht.


## Ergänzender Fehlerzustandsablauf

Der tatsächliche Profil-Browserlauf fand nach geändertem Recht und anschließend
pausiertem Finanzmodul zwei gleichzeitig angezeigte Actionfehlermeldungen. Die
alte Rechtefehlermeldung konnte damit einen inzwischen überholten Zustand
anzeigen. Die gemeinsame Fehleranzeige ersetzt nun nur ihre vorherige flüchtige
Meldung am selben Ziel. Fachliche Warnungen und unbestätigte Aufträge bleiben
separat erhalten. Der komplette gezielte Profilablauf besteht danach mit echten
Rechtewechseln, Modulpause, ursprünglicher Quittung und unveränderten Geldquellen;
Protokollhash im gemeinsamen Integrationsnachweis.
