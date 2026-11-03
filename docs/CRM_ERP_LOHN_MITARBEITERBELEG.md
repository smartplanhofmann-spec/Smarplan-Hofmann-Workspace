# Eigener Mitarbeiter-Lohnnachweis – implementierter Stand

Stand: 03.11.2026. Beschäftigte können ihre vorhandenen v1–v4-Lohnwerte,
historischen Fassungen und einen eigenen reduzierten PDF-Beleg in Browser und
Flutter lesen. Interne Vertrags-, Anspruchs-, Profil- und Personaloriginalquellen
werden dabei nicht freigegeben. Der [API-Vertrag](CRM_ERP_LOHN_MITARBEITERBELEG_API.md)
beschreibt die genaue Positivliste und die unveränderten Rohquellen-Rechte.

Der bisherige Einstieg **Lohnberechnung 2026** führt bei Beschäftigten ohne
globale Personalrechte zu **Meine Lohnnachweise**. Personalverantwortliche
können über **Mitarbeiter-Lohnnachweise ansehen** dieselbe reduzierte Projektion
prüfen. Die neueste Fassung wird einmal in der Übersicht angezeigt; ältere
Fassungen bleiben über **Beleghistorie öffnen** erreichbar.

Der Beleg zeigt Brutto, Arbeitnehmerbeiträge, Steuern, Netto und berechneten
Auszahlungsbetrag. Beschäftigungs-, Steuer- und SV-Zeiträume sind getrennt.
Historische unvollständige SV-Berechnungen behalten unbekannte Steuer-/Nettowerte.
Ein berechneter Auszahlungsbetrag wird nicht als tatsächlicher Geldfluss
ausgegeben. Der Beleg beansprucht keine vollständige gesetzliche
Entgeltbescheinigung und keine amtliche Meldung.

## Datenschutz, Historie und Quellenintegrität

Der neue Backendadapter verwendet die vorhandenen intern gehashten Laufarchive
und deren Reproduktionsprüfung. Bei v4 werden die tatsächlich gespeicherten
historischen Faktenquellen und die exakte Periodenrechnung erneut geprüft.
Danach werden nur ausdrücklich freigegebene Felder übernommen, auch in
verschachtelten Objekten. Weder freie Korrekturgründe noch Originalreferenzen,
Vertragsbegründungen, Steueridentitäten oder Anspruchsnotizen verlassen diesen
Adapter.

Der reduzierte PDF-Beleg wird separat und deterministisch aus dieser Projektion
erzeugt. Seine Prüfsumme unterscheidet sich vom internen Lohn-PDF. Historischer
Name und Werte stammen aus den damaligen Quellen. Spätere Namensänderung,
Fallkorrektur oder Modulpausierung verändern frühere Belege nicht.

Eigener Zugang erfordert frische Benutzeraktivität, aktuelle eigene
Mitarbeiterzuordnung und `time.own`; alternativ gelten globale Personalrechte.
PDF für fremde Mitarbeiter erfordert zusätzlich `personnel.export`. Die
PDF-Erzeugung findet außerhalb des Datenbankschlosses statt; danach werden die
aktuellen Rechte erneut geprüft. Eine entzogene Freigabe entfernt die
aktiven Lohnwerte in beiden Oberflächen. Die bisherige private Raw-API bleibt
für reine eigene Mitarbeiterzugänge gesperrt.

## Tatsächlich ausgeführte Prüfungen

| Nachweis | Ergebnis |
|---|---|
| Echte Domänenfälle und lokaler HTTP-Transport | 8/8 bestanden |
| Gesamte Node-Lohnregression einschließlich Mitarbeiterbeleg | 55/55 bestanden |
| Kombinierte Flutter-Lohnregression einschließlich Mitarbeiterbeleg | 56/56 bestanden |
| Flutter-Analyse beider betroffenen Lohnseiten | Keine Befunde |
| Echter Chromium-Workflow `payroll-statements` | Bestanden: Passwort/MFA, eigener v4-Beleg, Raw-Sperren, eigener PDF-Hash, Historie, 390 px und frischer Rechteentzug über eine zweite echte MFA-Sitzung |

Die Domainprüfung verwendet tatsächliche private P2-Fakten, Profile,
Personaloriginale und einen abgeschlossenen v4-Lauf. Sie belegt eigene und
fremde Personenrechte, Rollenentzug, deaktivierte Benutzer, den unmöglichen
Wechsel eines bestehenden Mitarbeiterprofils auf einen anderen Zugang sowie
Rechteentzug während der PDF-Erzeugung. Historische PDF-Bytes bleiben nach
Laufkorrektur, Namensänderung und Modulpausierung exakt gleich.

Der Browserworkflow erzeugt zunächst einen regulären Teilmonat mit tatsächlichen
privaten Quellen. Nach Abmeldung meldet er den Mitarbeiter mit Passwort und MFA
an. Beim Öffnen des Lohnbelegs erfolgt kein Abruf von Raw-Läufen, Profilen oder
Fakten. Direkte Abrufe dieser Quellen liefern weiterhin HTTP 403. Die
Mitarbeiter-PDF-Bytes entsprechen der reduzierten Prüfsumme. Eine zweite,
getrennte Administratoranmeldung entzieht anschließend `time.own`; der erneute
Exportversuch entfernt die zuvor sichtbaren Lohnwerte und der Server verweigert
den weiteren Zugriff.

Die 390-px-Ansicht wurde sichtbar geprüft und kontrolliert zusätzlich, dass
Tabellen innerhalb ihres verfügbaren Bereichs bleiben. Native Widgettests
öffnen den bisherigen Payroll-Einstieg, verweigern im Testdouble sämtliche
Raw-Quellrouten und prüfen das Entfernen der Anzeige bei Rechteentzug.
Die Clientfixture samt PDF stammt aus echten Backendoperationen;
`web/office/tests/payroll_statement_fixture.py` erzeugt sie reproduzierbar.

Während der Gegenprüfung wurden ein falsches Testorakel zur bereits
unveränderlichen Mitarbeiterzuordnung und die dialoggebundene Browserfehleranzeige
beim Rechteentzug berichtigt. Fehlgeschlagene Testanläufe bleiben unter
`work/verification/payroll-statements-*` erhalten; sie werden nicht als bestanden
gezählt. Das frühere Testskript musste außerdem eine neue Administratoranmeldung
verwenden, weil Abmelden die vorherige Sitzung korrekt ungültig macht.

Die [maschinenlesbare Abnahme](CRM_ERP_LOHN_MITARBEITERBELEG_PRUEFUNG_2026-11-03.json)
bindet Dateien, Protokolle und Screenshot. Testzahlen überschneiden sich mit
früheren Lohnregressionen und werden nicht als unabhängige Zusatztests addiert.
Dies ist keine eigenständige PostgreSQL-Abnahme des neuen Projektionsadapters.

## Folgende Arbeit

Die P4-Anspruchsfakten und Source3/v5-Segmentrechnung werden als nächstes in den
privaten Personal-Arbeitsbereich integriert. Der reduzierte Mitarbeiterbeleg
bekommt dafür nur ausdrücklich passende neue Berechnungsfelder, insbesondere
gesonderte Nettoabzüge; private Rohfakten bleiben ausgeschlossen. Der derzeitige
v1–v4-Abschluss behauptet keine bereits geprüfte v5-Unterstützung.
