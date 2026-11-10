# Source5-Zahlungstage V3 – laufende Implementierung

Noch nicht veröffentlicht. Dieser Abschnitt schließt tatsächliche spätere
positive Nettozahlungen zu einem bereits angenommenen positiven Source5-
Korrekturlauf. Er erzeugt weder einen neuen Bruttozufluss noch eine allgemeine
steuerliche Korrekturfreigabe. Die bestehenden Fach-/Quellenprüfungen des
Korrekturlaufs und seine Vollständigkeitserklärung gelten unverändert weiter.

Der neue Eingabezweig trägt `payment_source_schema_version:3`. Die bisherigen
Zahlungsfelder, der ursprüngliche Lauf und die vollständigen geordneten alten
Zahlungen/Nettozuordnungen bleiben erhalten. Jeder neue Teil muss ausschließlich
die positive Zusatzschuld erfüllen, seinen wirklichen Transferreferenzbeleg
besitzen und im unterstützten Kalenderjahr 2026 tatsächlich geflossen sein.
Sein Tag darf weder zukünftig sein noch vor dem ursprünglichen Bruttoereignis
oder dem letzten bereits vollständig belegten Zahlungstag liegen. Negative
Rückzahlungen, neue Bruttoereignisse und Transfers 2027 werden nicht freigegeben.

Der Ergebnisplan behält alle V2-Felder, verwendet `schema_version:3`,
`contract:source5_positive_net_correction_v3` und zusätzlich
`settlement_date_basis:actual_positive_transfer_2026`. Der Hash bindet den
vollständigen Plan einschließlich der wirklichen Zahlungstage und des neuen
Merkmals. Die Nebenwirkungsflags bleiben false: Der Plan beweist erfasste
Vorgänge und führt keine Überweisung aus. Die Geldflussübernahme wählt allein
die zusätzlichen Indizes und verwendet genau deren tatsächliche Tage.

Der ursprüngliche Bonus kann beispielsweise am 31.10. zugeflossen sein;
eine nachgewiesene zusätzliche Nettozahlung am 02.11. bleibt ein Geldfluss am
02.11. und ersetzt kein Bruttoereignis des Oktobers. Ein zweiter späterer
Korrekturlauf erhält den gesamten früheren V3-Präfix. Ein Rückfall auf V2 wird
dann verweigert. Ursprüngliche V1-/V2-Pläne, Quittungen und PDFs behalten
ihre bisherigen Inhalte und Hashes; ihre alten Datumsgrenzen werden nicht
umdefiniert. Die 32 historischen Rechenmodule und die ganze alte Datei
`payroll_multiple_payments.py` werden nicht verändert.

Das neue Feature heißt `payroll_source5_payment_dates` im Lohnkontomodul.
Neue Oberflächen verwenden den neuen Zahlungszweig nur nach dessen aktueller
Freigabe. Vorherige Originalaufträge und Wiederholungen behalten ihre eigene
Version. Unterstützung eines späteren Zahlungstags ist keine neue Berechtigung;
private Akten, frische Fachrechte, aktiver Korrekturlauf, frühere tatsächliche
Zahlung und Abführungsgrenzen bleiben erforderlich.

Prüfstand 10.11.2026: 32 Backendfälle bestehen in 233,275 Sekunden, darunter
alle drei neuen Datums-/Folgekorrekturketten, neun historische positive
Korrekturfälle und 20 Gesamtfall-/Reiseregressionen. 1.023 Browsermodultests
bestehen ohne Auslassung; 16 neue/historische App-Vertrags- und Bedienfälle
bestehen, einschließlich unveränderter Wiederholung nach Schließen/Neuladen,
frischem Freigabeentzug und tatsächlicher V3-Ergebnisanzeige bei 390 Pixeln.
Die native Analyse ist ohne Befund. Die abschließende vollständige App-Suite
wird getrennt protokolliert. 21 Paket-/Inventarfälle bestehen mit dem tatsächlichen
CLI-Kopierweg und Supportarchiv. Die gemeinsame Fixture enthält zwei wirklich
vom Fachkern angenommene aufeinanderfolgende V3-Originale; ihr Generator
verwendet kontrollierte Fachfixtures, keine echte MFA. Die Clients berechnen
die vollständigen Zahlungsplanhashes unabhängig in JavaScript und Dart nach.

Der tatsächliche Chromium-/MFA-/HTTP-Bedienablauf besteht für den neuen
November-Zahlungstag und gesondert für den alten V2-Zweig. Er korrigiert einen
wirklichen privaten Vorarbeitgebernachweis, verlangt ausdrückliche vollständige
Prüfung von Zahlungen und Abführungen, erhält zwei alte Zahlungsteile und
verliert tatsächlich die bereits angenommenen Lauf-/Zahlungsantworten.
Unveränderte Aufträge erhalten danach dieselben Originale. Die V3-Anzeige nennt
getrennt ursprünglichen Bruttozufluss und wirkliche zusätzliche Zahlungstage.
Es werden keine angenommenen Finanzantworten simuliert; nur ihre Zustellung
wird für die Wiederholungsprüfung unterbrochen. Der Browser prüft die mobile
Darstellung; tatsächliche Gerätedistribution bleibt separat.

Die echte gebundene PostgreSQL-Kette verwendet MFA, getrennte Produktionsrollen,
private Belege, einen unabhängig unter CRLF erzeugten historischen Ausgangslauf,
Geldfluss am 02.11., EÜR, unzulässigen Techniker-/Offlinezugriff und tatsächliches
pg_dump/pg_restore. Lauf-/Zahlungs-/Geldflussquittungen, alter PDF-Inhalt und
EÜR-Summen bleiben nach freigegebener Wiederherstellung gleich. Der gemeinsame
abschließende Lauf besteht mit zwei Fällen in 207,040 Sekunden,
einschließlich zweier echter konkurrierender Schreiber, nachträglichem
Rollenentzug und erneuter MFA. Ein zusätzlicher Nachlauf des ergänzten
MFA-Testhelfers besteht in 39,149 Sekunden: Er verwendet den wirklich zuerst
eingerichteten Schlüssel und wartet bei Bedarf auf das nächste reale
Zeitfenster. Die serverseitige Einmaligkeit der MFA-Codes wird nicht verändert. Es werden
nur die eigene bewachte
Loopback-Wegwerfdatenbank und synthetische Dateien verwendet.

Der PostgreSQL-Vorlauf deckte eine weitere echte Grenze auf: Die allgemeine
Reiseprüfung verweigerte bisher jeden späteren Monat, auch wenn ausschließlich
ein positiver Bonusunterschied bezahlt wird. Der neue Ausnahmeparameter wird
nur aus einem vollständig aufgelösten V3-Plan und ausschließlich für dessen
zusätzliche Nettoindizes gewonnen. Der vollständige frühere Reisezahlungspräfix
bleibt vor der Ausnahme nachgerechnet und unverändert. Andere Reise-, V1-/V2-,
Einmalbezugs- und Standardzahlungsverträge behalten ihre bisherigen Datumsgrenzen.
Ein späterer geänderter Reisekostenbetrag wird dadurch nicht freigegeben.

Die vollständigen Vorläufe bleiben erhalten: zunächst fehlende V3-Unterstützung,
eine numerisch statt textuell eingegebene historische PDF-Revision, eine
versehentlich doppelte neue Transferreferenz, ein fehlendes Fixture-Bestätigungsfeld,
ein Dart-Testsyntaxfehler, der echte Reisemonatskonflikt und eine zunächst fehlende
V3-Ergebniskarte. Zwei Sandbox-Vorläufe scheiterten an fehlenden lokalen Ports
bzw. dem Zeitzonen-Unterprozess; die zugelassenen Nachläufe bestehen. Die
Wiederholungs-/Original-/Reisegrenzen wurden für diese Fehler nicht abgeschwächt.
Auch die später falsch erwartete gleichzeitige Sichtbarkeit zweier Karten im
kleinen App-Viewport und der neue PG-Test mit ungültigem Rollenname bleiben
als Testvorläufe erhalten. Ebenso bleibt der zunächst nur für Erstanmeldung
geeignete MFA-Testhelfer als fehlgeschlagener Vorlauf erhalten. Die Ergebnisanzeige wird tatsächlich erscrollt;
Rollenentzug verwendet die vorhandene gültige Technikerrolle.

Diese Änderung setzt einen bereits unter dem bestehenden engen Vertrag
angenommenen positiven Korrekturlauf voraus. Sie ist keine neue Auslegung von
§39b/§41c EStG und keine pauschale nachträgliche Steuerkorrekturberechtigung.
Zusätzliche Bruttoereignisse, mehrere Bonusgruppen, Netto-Rückforderungen,
Jahreswechsel, weitere steuerliche Korrekturfälle und ihre Fachabnahme bleiben
aktive gesonderte Arbeit. Die allgemeine Software-/Lohnfreigabe, signierte
Verteilung und reale Betriebs-/Geräteabnahme werden nicht aus diesem
Zahlungsdatumsnachweis abgeleitet. Keine Liveinstallation oder echte Überweisung.

Der ausschließlich eigene PostgreSQL-Container wurde nach den Prüfungen anhand vollständiger Kennung und Aufgabenmarkierung bestätigt und entfernt. Andere Container und Dienste wurden nicht verändert.
