# Belegte Lohnansprüche bei regulärem Faktor-Monat

Additiver implementierter Codeabschnitt auf dem veröffentlichten gemeinsamen Stand
`b31028aa1f1639cf74b6d52ccd4e11e1d55b78b9`. Der gesamte Auftrag bleibt aktiv.

Der vorhandene Faktor-/Periodenfall v9 und der belegte P4-Anspruch ließen sich
vor dieser Erweiterung nicht gemeinsam abrechnen. Die erste tatsächliche Reproduktion mit
ursprünglichem Faktor0,753, vollem Beschäftigungsmonat und fünf separat belegten
unbezahlten Kalendertagen scheiterte am noch unbekannten Regel-/Quellenvertrag.
Bei 5.000,00 EUR Monatsentgelt und belegter Kalendertagsmethode sind 26/31 des
Monats geschuldet: einmal gerundet 4.193,55 EUR. Genehmigte Projektzeiten sind
unverändert und werden nicht als bezahlte Ausfallzeiten hochgesetzt.

Implementierter additiver Vertrag:

- Regel `de_2026_factor_claims_month_v12`, Quellenvertrag4 und Scope
  `regular_standard_factor_claims_month`; ausdrückliche neue Serverfähigkeit.
- Ein inländisches reguläres Beschäftigungsverhältnis mit einem tatsächlichen
  vollständigen Steuer-/SV-Monat und einem unveränderten Faktorprofil Klasse IV.
  P4-Originale bestimmen das tatsächlich geschuldete Brutto. Alle aktuellen
  Anspruchsquellen müssen vollständig gebunden sein; Identität, Beschäftigung,
  Profil und Quellen bleiben die wirklichen angenommenen Originale.
- Der alte v5-Anspruchsplaner wird ausschließlich als strukturelle Teilrechnung
  verwendet. Seine alten historischen Verträge werden nicht erweitert. Der
  neue Gesamtplan bindet wieder den tatsächlichen v12-Quellenhash und die neue
  Regel; es werden keine geänderten historischen Profile gespeichert.
- Steuer/SV beruhen auf dem tatsächlichen Anspruchsbrutto und dem belegten
  Faktor. Bestehende Faktor-v8-/v9-Zahlenwege werden verglichen; zusätzliche
  unabhängige PAP-XML-Referenzfälle verwenden die unveränderten amtlichen
  Dezimalausdrücke und einen vorab festgelegten vollständigen XML-Hash.
- Wechsel-/Teilperioden, Midijob/Faktor, Einmalbezüge oder gleichzeitige weitere
  Reiselohnbestandteile werden nicht durch Aufheben alter Sperren zugelassen.
  Bereits separat geprüfte Fälle und alle 32 alten Rechenmodule bleiben erhalten.

Backend, beide Clients, neue vollständige Quellen-/Plan-/Vorschauhashprüfung,
frische eigene Funktionsfreigabe, beide verlorenen Antworten, private Belege,
Zahlung/EÜR/Jahresbasis und tatsächliche PostgreSQL-Wiederherstellung sind
implementiert und gezielt geprüft. Die vollständige Appprüfung besteht nach Korrektur des lokalen
Python-Testpfads mit1.905 Fällen ohne Fehler oder Skip in732.859ms. Veröffentlichung, eigene CI,
Serverinstallation, Geräte- und fachliche/amtliche Freigaben bleiben gesondert.
Diese Erweiterung allein ist kein Abschluss des Gesamtziels.

## Primärquellen und erste tatsächliche Gegenprüfungen

[§39f EStG](https://www.gesetze-im-internet.de/estg/__39f.html) wurde am10.11.
gelesen: Der eingetragene Faktor wird bei Klasse IV angewendet; die Software
leitet ihn nicht selbst aus geschätzten Haushaltseinkünften ab. Sieben neue
unabhängige Vektoren laufen mit den unveränderten amtlichen PAP-XML-
Dezimalausdrücken in Java, nach Prüfung des XML-SHA
63d8981646d139eba2f4dd990c13b43c4fb3883b402a5a40cddf253aa7aa96b4.
Der Code des Produktkerns wird dafür nicht aufgerufen. 4.193,55 EUR ergeben im
kontrollierten Profil bei Faktor0,753 exakt430,91 EUR Lohnsteuer.

Eine erste Gegenprüfung verlangt irrtümlich identische Pflegebeiträge aus zwei
verschiedenen bisherigen Rundungsmethoden und scheitert an einem Cent.
[BVV§2](https://www.gesetze-im-internet.de/beitrvv/__2.html) und die tatsächliche
[GKV-Primärquelle31.03.2025, Abschnitt3.3, Seite12](https://www.gkv-spitzenverband.de/media/dokumente/pflegeversicherung/grundprinzipien/2025-03-31_GH_Beitragssatzdifferenzierung_sPV.pdf#page=13)
bestätigen, dass hier Ein- und Zweischrittmethode zulässig sind. V12 bindet
ausdrücklich dieselbe Zweischrittmethode wie der vorhandene Anspruchsplaner.
Bei4.193,55 EUR: Arbeitnehmer-PV75,48+25,16=100,64 EUR, gesamte Arbeitnehmer-
SV912,10 EUR und Netto2.850,54 EUR. Der frühere v8-Einschrittwert bleibt als
historisches Original erhalten. Es handelt sich nicht um eine nachträgliche
Änderung alter Abrechnungen. Der tatsächliche Faktor-/P4-/Lohnlauf besteht
nach dieser expliziten Methodenbindung mit einem Fall/0,837s; Clients und
vollständige Geld-/Jahres-/Restorenachweise bleiben in Arbeit.


## Tatsächliche gemeinsame Prüfungen

- 55 gemeinsame Backendfälle bestehen in53,715s. Darunter sieben neue tatsächliche
  Fälle: fünf unbezahlte Kalendertage, drei weitere aus Originalen gebildete
  Anspruchsbruttos gegen den separaten PAP-XML-/Java-Vergleich, echter
  Stundenlohn-Feiertagsanspruch, gesperrter tatsächlicher Teilmonat, veralteter/
  ausgelassener Anspruch, private Mitarbeiterabrechnung sowie Zahlung/EÜR/Jahr.
  Der Feiertag03.10.2026 ist gegen den bestehenden tatsächlichen deutschen
  Feiertagskalender und den gebundenen Sollplan geprüft. 3.200,00 EUR sind
  ausschließlich belegte Ausfallvergütung bei0 tatsächlich gearbeiteten Stunden;
  der unabhängige XML-Sollwert ist253,91 EUR Lohnsteuer.
- 1.041 gesamte Browsermodulfälle bestehen ohne Skip in13.886,372ms.
  Neue Original-/Plan-/Quittungshashes, falsche Anspruchsquellen, private Historie,
  beide tatsächlichen Anspruchsarten, Funktions-/Rechteentzug und unveränderte
  Bestätigungswiederholung sind enthalten.
- Neun neue native Vertrags-/Bedienfälle bestehen; zusätzlich29 gemeinsame
  Faktor-/Rechte-/Ansichtsprüfungen. Die vollständige aktuelle Analyse ist
  sauber12,4s. Der erste gesamte App-Lauf hatte1.902 Fälle mit26 Fehlern:
  mehrere echte HTTP-Prüfungen liefen vor Einrichtung des lokalen Python-Links.
  Der korrigierte vollständige Lauf wird eigenständig nachgewiesen; der erste
  Lauf wird ausdrücklich nicht als erfolgreich geführt.
- Ein tatsächlicher PostgreSQL-/MFA-Fall besteht in25,979s: originale
  Vollmonats-/Faktor-/P4-Quellen, zwei gleichzeitige Runtime-Lohnbestätigungen,
  exakte HTTP-Wiederholung, neue Identität für die neue Profilrevision,
  eigenständige CRLF-Kernausführung, private Rolle, erneute echte MFA,
  Zahlung2850,54 EUR, EÜR, Jahresbasis sowie vollständiges pg_dump/pg_restore.
  Danach stimmen Case-, Lauf-, Zahlungs-, Cash-, Jahresquittungen und das
  ursprüngliche PDF weiterhin exakt. Die eigene anhand ID/Label/Loopback-Port
  geprüfte Wegwerfdatenbank wurde anschließend entfernt; fremde Container
  blieben unverändert.
- 21 Paket-/Inventarprüfungen bestehen in20,079s. Der neue Rechenkern ist im
  kanonischen Backend-Inventar vorhanden. Der ursprüngliche Testpfadfehler
  bleibt als vorheriger fehlgeschlagener Paketlauf erhalten.
- Das Gesamtziel bleibt unverändert23863 Bytes/SHA
  a4dea28f6de4afd3e36d1549441aad91ce16dad374f56097979cc2d79b07fbf5;
  sämtliche32 bisherigen Rechenmodule sind bytegleich.

Weitere Faktor-Teilperioden mit Ansprüchen, gleichzeitige Anspruchs-/Reisefälle,
Faktor-Midijob, Faktor-Einmalbezüge, zusätzliche Steuergruppen sowie die übrigen
fachlichen und technischen Gesamtabnahmen bleiben eigene offene Anforderungen.
Die vorhandene V10-Reise- und V11-Minijobfreigabe ist weiterhin unabhängig.
Keine tatsächliche Zahlung, amtliche Meldung oder neue Liveinstallation wurde
ausgelöst. Der Gesamtauftrag läuft nach dieser Etappe weiter.


## Vollständiger Schlussnachweis

Der korrigierte ganze App-Lauf besteht mit1.905 Fällen ohne Fehler oder Skip,
Schlussereignis success:true in732.859ms. Der erste fehlgeschlagene Lauf bleibt
unverändert erhalten. Die beiden echten Browserläufe bestehen auf dem mit
cb7ff63 zusammengeführten Produktcode erneut. [Manifest und56 Rohnachweise](evidence/factor-claims-2026-11-10/manifest.json)
führen die einzelnen aktuellen und vorherigen Ergebnisse getrennt.
Der Gesamtauftrag läuft mit dem nächsten Offline-Protokollabschnitt weiter.
