# Belegter Minijob-RV-Verlauf und Abrechnungsbindung

Entwicklungsstand 10.11.2026, Basis `4aa0abd`. Der erste Kandidat `51c404b`
ist auf dem Testbranch veröffentlicht, jedoch wegen der nachstehend belegten
Altbelegregressionen nicht freigegeben. Die Korrektur und der größere tatsächliche
Originalkatalog sind getrennt nachgeprüft. Der vollständige Erstlauf bleibt rot;
seine erfolgreichen gezielten Nachläufe ändern daran nichts. Die ausgelieferten
V16-Pakete bleiben getrennte Nachweise.

## Tatsächlich angeschlossener Umfang

Die eigene Regel `de_2026_minijob_rv_revocation_v1` verarbeitet einen bereits
belegten Befreiungsstatus und dessen einmalige Aufhebung für einen einzigen,
durchgehenden gewerblichen Minijob nach 2012. Der Aufhebungsantrag muss ab
01.07.2026 tatsächlich beim Arbeitgeber eingegangen sein. Antragsform, Original,
Meldungseingang, geprüfte Widerspruchsfrist und tatsächlicher Verfahrensstand
sind getrennte Angaben. Der gesamte bekannte Revisionspräfix bleibt gebunden.
Ein bekannter Antrag kann weder durch eine neue ID noch durch eine ausgelassene
alte Fassung verschwinden. Widersprüchliche Sonderfälle im ursprünglichen Profil
werden durch neue Bestätigungshäkchen nicht überstimmt.

Die Regel verlangt den tatsächlichen Nachweis der geprüften Frist einschließlich
anwendbarer Feiertage. Sie berechnet keine Verwaltungsfrist automatisch und
erzeugt aus bloßem Zeitablauf keinen Nichtwiderspruch. Ein offenes oder beanstandetes
Verfahren bleibt nach dem möglichen Wirkungsbeginn ungeklärt. Die Prüfung
erzeugt kein Profil, keine Meldung und keine Zahlung.

Zwei neue private Tabellen bewahren Originale und Annahmequittungen append-only.
Die Runtime besitzt dafür ausschließlich SELECT/INSERT; ursprüngliche Zeilen
sind zusätzlich gegen UPDATE/DELETE geschützt. Personal-Lese- und Freigaberechte
werden vor Quellenzugriff und unveränderter Wiederholung aktuell geprüft.

## Profil, Lohn und Geldfolge

Neue Minijobprofile nach Aufnahme eines RV-Verlaufs benötigen ausdrücklich beide
Profilfelder `rv_lifecycle_source_contract_version: 1` und `rv_lifecycle_ref`
mit ID, Revision und Originalhash. Das neue Profil muss zum belegten Status
seines Wirksamkeitsmonats passen. Das ursprüngliche Befreiungsprofil kann in
diesem ersten Vertrag nicht nachträglich überschrieben werden.

Vor einer neuen Lohnvorschau oder Bestätigung prüft das System zusätzlich den
tatsächlichen **Abrechnungsmonat** und alle darin tatsächlich verwendeten Profile.
Eine im Mai gültige Befreiung darf eine im August wirksame Aufhebung nicht
übergehen. Ein neuer RV-Prüfstand verlangt eine neue ausdrückliche Profilbindung.
Ein gemischter Wechsel in eine andere Beschäftigungsart wird mit diesem Vertrag
nicht freigeschaltet.

Historische Profile, Läufe und PDFs behalten ihre ursprüngliche RV-Referenz und
Annahmezeit. Spätere Prüfstände werden nicht rückwirkend eingesetzt. Die bisherigen
Beitrags- und Steuerformeln bleiben unverändert; ein neuer finanzieller Rechenkern
oder eine Source6 ist für diese Tatsachenbindung nicht nötig.

Der tatsächliche synthetische Ablauf prüft bei 603,00 EUR Brutto den Wechsel
von 603,00 EUR Netto bei Befreiung zu 581,29 EUR Netto und 21,71 EUR
Arbeitnehmerbeiträgen nach belegter Aufhebung. Frühere Laufversionen und PDFs
bleiben unverändert. Tatsächliche Zahlungsnachweise, separate Abführung, EÜR und
Lohnkonto ergeben zusammen 790,95 EUR belegte Ausgaben; eine Auszahlung wird
dabei weder erfunden noch erneut erzeugt. Der Kalenderjahresstand bleibt bei
fehlenden Monaten ausdrücklich unvollständig.

Der eigene Mitarbeiterbeleg zeigt die berechneten Beträge und besitzt eine
geprüfte PDF-Prüfsumme. Private RV-Anträge, Nachweis-IDs und Verfahrensunterlagen
werden nicht in diesen Beleg oder öffentliche EÜR-Quellen übernommen.

## Bedienung und Nachweise

Browser und App öffnen den privaten RV-Verlauf aus der Lohnansicht. Formulare
verlangen die bewusste Wahl der Originale, zeigen die unverbindliche Wirkung und
benötigen anschließend eine eigene Bestätigung. Die Profilpflege bietet den
aktuellen RV-Nachweis ausdrücklich zur Auswahl an. Eine verlorene Antwort wird
mit demselben vollständigen Auftrag und derselben Vorgangskennung geklärt.
Unpassende Annahmeantworten dürfen diesen offenen Auftrag nicht löschen.
Rechteentzug schließt die private Ansicht und ihre geöffneten Eingabeformulare.

Tatsächlich abgeschlossene lokale Nachweise:

- 25 neue reine Regel-, Speicher- und tatsächliche Profil-/Lohnfälle, darunter
  unveränderte CRLF-Regelreproduktion und ein trotz neu berechnetem Umschlaghash
  abgewiesener manipulierter Profilstatus.
- 58 gemeinsam ausgewählte Backend-/bisherige Lohn-/CI-Vertragsfälle; die danach
  ergänzten CRLF-/Manipulationsfälle besitzen den getrennten 25er-Nachweis.
- 37 gemeinsame Appfälle, darunter die neuen Formulare auf 390/1.100 Pixeln,
  unveränderte Wiederholung nach Bereichspause und frische Rechteprüfung.
  Die App-Analyse meldet keine Befunde.
- 1.116 vollständige Browser-Modulfälle. Der tatsächliche Chromium-Ablauf
  bestätigt MFA/HTTP, bewusste Originalwahl auf Mobilbreite, verlorene Antwort,
  wirkliche Profilpflege, berechnete Abrechnung, Historie und Rechteentzug.
- Endgültige PostgreSQL-Folge mit zwei konkurrierenden Annahmen, MFA/HTTP,
  Profil, Lauf, Zahlung, privatem Beleg, unveränderter späterer Wiederholung und
  vollständigem Datenbank-Restore: erfolgreich in 42,624 Sekunden. Der eigene
  Container ist anhand ID, Label und Loopback-Port geprüft entfernt.
- 22 Paket-/Archivfälle. Der darin enthaltene eingefrorene Archivlauf bezieht
  sich noch auf HEAD `4aa0abd`; der neue Kandidat benötigt nach seinem Commit
  einen eigenen eingefrorenen Nachlauf und seine eigene Remoteprüfung.

Erstfehler und Aufbaugrenzen bleiben im
[Entwicklungsnachweis](evidence/minijob-rv-lifecycle-2026-11-10/implementation-stage.json)
erhalten. Die anfangs volle Cloud-Arbeitsplatte verhinderte die Paketkonfiguration;
die anschließende Analyse ohne diese Konfiguration ist kein gültiger Produktbefund.
Die eigene Arbeitskopie wurde mit Prüfung aller 2.335 Dateien/Verzeichnisse/Links
nach `/tmp/smartplan-minijob-rv-20261110` verlagert und mit Git repariert.
Der alte Pfad bleibt als Kompatibilitätslink erreichbar. Fremde Arbeitskopien
und vorhandene Projektdateien wurden nicht gelöscht.

## Ergänzte Auswahl- und Fristprüfung

Eine Profil- oder RV-Auswahl bindet jetzt ausdrücklich ID, Revision und Hash
der tatsächlich angezeigten Fassung. Eine neue RV-Fassung bei bereits geöffnetem
Profilformular darf diese Auswahl nicht unbemerkt ersetzen. Der tatsächliche
Browserfall nimmt eine zweite Nachweisfassung während des offenen Formulars an,
weist die alte Auswahl vor der Profilanlage zurück und verlangt das erneute
Prüfen der neuen Fassung. Die RV-Vorschau verwendet die beim Öffnen ausgewählten
Quellen; aktuelle Serverprüfungen weisen einen inzwischen geänderten Stand ab.

Eine tatsächlich geprüfte, noch zukünftige Widerspruchsfrist darf im offenen
Verfahren gespeichert werden. Sie ist kein bereits eingetretenes Ereignis und
keine abgeschlossene Nichtbeanstandung. Zukünftige tatsächliche Antrags-, Melde-
oder Behördenereignisse bleiben unzulässig.

Der ergänzte Nachlauf besteht 39 gemeinsame Appfälle, neun neue Browserverträge
und alle 1.118 Browser-Modulfälle. Der neue wirkliche Browserablauf mit dieser
Auswahländerung besteht ebenfalls; die App-Analyse meldet keine Befunde.
Ein erster App-Nachlauf enthielt einen verbliebenen lokalen Variablennamen;
ein zweiter einen noch auf bloße ID statt konkreter Fassung gesetzten Testwert.
Beide roten Nachläufe bleiben erhalten, der dritte gemeinsame Nachlauf besteht.

Der vorher begonnene gesamte App-Lauf besteht 2.033 Fälle in 16:53. Die beiden
ergänzten Fälle und die Auswahländerung besitzen den gesonderten Nachlauf;
der Gesamtlauf ist kein eingefrorener Vollnachweis dieses späteren Kandidaten.
Der neue eingefrorene Archiv- und eigene CI-Nachweis müssen dessen endgültige
Commitkennung verwenden.

## Korrektur nach dem vollständigen Backend-Erstlauf

Der ganze lokale Erstlauf erfasst 2.224 Fälle in 2.066,372 Sekunden und endet
mit einer Fehlprüfung, drei Fehlern und drei ausgewiesenen Auslassungen. Zwei
Aufbaufehler betreffen ursprünglich nicht materialisierte unveränderte Beleg-
bzw. Gmail-Skriptdateien in der eigenen Sparse-Arbeitskopie. Diese sind ergänzt.

Zwei tatsächliche Regressionen betreffen die alte reine Umschlagprüfung eines
hashkonsistenten, aber inhaltlich beschädigten Lohnoriginals. Die zusätzliche
RV-Prüfung verlangte dort schon einen Quellenkörper, obwohl bestehende fachliche
Altbelegprüfer diesen beschädigten Körper erst anschließend und vor jeder
weiteren Verwendung ausdrücklich zurückweisen. Die zusätzliche Prüfung greift
jetzt nur bei einer tatsächlich vorhandenen RV-Profilbindung. Bindungen in
verschachtelten Monatsprofilen werden ebenfalls erkannt. Beschädigte Altbelege
werden dadurch weder repariert noch als Beweis einer Nichtverwendung behandelt.
Die bisherigen fachlichen Upgrade-/Integritätsprüfungen sperren sie weiterhin.

Eine weitere tatsächliche Gegenprobe erzeugt über die Personalakten-API 100
zusätzliche Originale: Der aktuelle Dateikatalog enthält 101 Dateien, während
der RV-Nachweis unverändert genau ein ursprüngliches Original bindet. Beide
Clients verwechselten zunächst die Grenze des früheren RV-Präfixes mit dieser
Dateiliste. Die jeweiligen Grenzen werden jetzt getrennt geprüft. Die neue
Vorführung stammt aus echten kontrollierten Speicherantworten und enthält
keine echten Mitarbeiterdaten.

Die Altlohn-/Gmail-/Anlage-/RV-Gegenprüfung besteht 41 Fälle. Ein zusätzlicher
41er-Lauf der RV-Regeln, tatsächlichen großen Akte und bisherigen Minijob-
Altbelegprüfungen besteht ebenfalls. Der aktuelle gemeinsame App-Nachlauf
besteht 40 Fälle, der ganze Browser-Modullauf 1.119 Fälle und der wirkliche
Browserablauf ebenfalls. Die App-Analyse meldet keine Befunde. Die nachfolgende echte PostgreSQL-Prüfung
besteht alle drei RV-/Altbeleg-/Restorefälle in 68,797 Sekunden, der eigene
Testcontainer ist anhand ID/Label/Port entfernt. Der eigene vollständige
Nachfolgekandidat wird getrennt ausgewiesen; der erste Kandidat wird nicht
rückwirkend als vollständig bestanden dargestellt.

## Verbleibende Grenzen

Anfangsbefreiungsverfahren, Wiederbeginn, parallele Minijobs, besondere Renten- und
Versorgungsfälle sowie Berichtigungen bereits abgeschlossener Behördenentscheidungen
benötigen eigene fachliche Verträge. Dieser Abschnitt ersetzt keine produktive
Meldung, externe Lohnfachprüfung, Gesamtfreigabe oder reale Geräteabnahme.
R09.03 und die Gesamtabnahmen A–G bleiben offen. Es wurden keine echte Zahlung,
Meldung oder Nachricht ausgelöst und weder Serverinstallation noch TestFlight-
Veröffentlichung vorgenommen.
