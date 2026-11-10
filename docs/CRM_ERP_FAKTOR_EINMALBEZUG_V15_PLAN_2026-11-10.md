# Faktor-Einmalbezug: geprüfter Steuerbaustein und aktive Integration

Stand10.11.2026. Dies ist die nächste Entwicklungsarbeit für R09.03/D im
vollständigen Gesamtziel. **Noch kein freigeschalteter Lohnfall V15**, keine
neue Zahlung, Meldung oder Fachfreigabe. Der neue reine Steuerbaustein ist
von einer vollständigen Quellen-/Bedien-/Zahlungsintegration getrennt.

## Bereits tatsächlich geprüft

`backend/payroll_factor_oneoff_2026.py` berechnet STS, SOLZS und BKS für einen
sonstigen Bezug2026 mit ausdrücklich belegtem Faktor der KlasseIV. BKS ist
die Kirchensteuerbemessung, nicht die landesspezifische Kirchensteuer.
Begrenzter Erstumfang: gesetzliche Pflichtversicherung, keine zusätzlichen
Jahresfrei-/Hinzurechnungsbeträge, Alters-/Versorgungs-/Entschädigungsfälle.
Ein tatsächlicher Faktor0.000 bleibt von einem fehlenden Faktor unterschieden.

344 synthetische Grenz-/Zufallsfälle werden unabhängig aus den unveränderten
Dezimalausdrücken der fest gehashten PAP-XML in Java erzeugt. Der Runner
importiert keinen Produktionslohncode. XML-SHA256:
`63d8981646d139eba2f4dd990c13b43c4fb3883b402a5a40cddf253aa7aa96b4`.
Der dokumentierte Spiegel ist an einen festen Commit gebunden; ein direkter
offizieller XML-Download oder eine amtliche Softwarefreigabe wird nicht behauptet.
Alle344 Ausgaben stimmen centgenau überein. Originalfaktor-/Standard- und
Einmalbezugskerne bleiben unverändert. Die neue Quellenprovenienz ist mit
tatsächlichen CRLF-Kopien beider beteiligten Dateien portabel geprüft.

Der Faktor wird auf die unskalierte Jahressteuerdifferenz angewendet, danach
erfolgt die PAP-Abrundung auf volle Euro. Zwei vorher einzeln faktorisierte
Jahressteuerbeträge dürfen nicht voneinander abgezogen werden. Die gesonderte
kinderbereinigte, faktorisierte Jahresbemessung entscheidet über SOLZS.
Laufender Lohn wird nicht nochmals als Einmalbezug versteuert.

Eine zusätzliche tatsächliche API-Gegenprobe bindet einen gespeicherten
V12-Faktor-/P4-Fall an die alte geplante Jahresbasis. Der bestehende V1-Vertrag
verweigert dies ausdrücklich mit409 und verlangt einen eigenen Jahresvorschau-
vertrag. Keine Jahres-, Lohnlauf- oder Cashzeile wird erzeugt. Diese Grenze
bleibt erhalten; ein umetikettierter oder umgerechneter V5-Schattenfall wäre
keine gültige neue Originalquelle.

## Nächste verbindliche Integrationsschritte

1. Explizit versionierte Jahresvorschau für tatsächliche Faktor-Originalfälle.
   Originale Profile, ELStAM-Identitäten, Beschäftigung, P4, Jahresperioden,
   bereits erfolgte Zuflüsse und echte Zukunftsvereinbarungen unverändert
   binden. Alte V1-Originale und ihre Pläne bleiben unverändert nachrechenbar.
   Der erste neue Jahresvertrag unterstützt nur nachgewiesene Fälle; weitere
   Faktor-/Midijob- oder Untermonatsfälle erhalten keine bloße Freigabeflagge.
2. Neue versionierte Einmalbezugszusammensetzung für einen tatsächlichen
   unveränderten Faktor-/P4-Monatsfall, einen eigenen Anspruch und seine
   vollständigen Jahres-/Steuerprognosen. Steuer und SV bleiben getrennt.
   Märzklausel, historische Beitragssätze und vorhandene Jahresbezüge müssen
   aus echten Perioden stammen. Bestehende Brutto-/Netto- und Kirchensteuer-
   Erhaltungsgleichungen sowie frische Originalprüfungen übernehmen.
3. Private Fall-/Vorschau-/Laufwege explizit registrieren. Vorhandene globale
   Anspruchsverbrauchsgrenze muss über alte und neue Regelversionen hinweg
   doppelte Einmalbezüge verhindern. Korrektur und unveränderte Wiederholung
   nach verlorener Antwort dürfen keine zweite Zahlung erzeugen.
4. Jahresbasis, reduzierte Mitarbeiterbelege, Lohnkonto, Zahlungen, Bankabgleich
   und EÜR mit ihren tatsächlichen Quellen verbinden. Neue Regel-/Umfangspaare
   in beiden Beleglesern ausdrücklich ergänzen, unbekannte Paare weiter sperren.
5. Browser und native App mit Originalauswahl, Vorschau und ausdrücklicher
   Bestätigung ergänzen; aktuelle Rechte und verlorene Antworten prüfen.
   Tatsächliche PostgreSQL-/MFA-/Konkurrenz-/CRLF-/volle Restorekette sowie
   gemeinsame Schlussprüfung vor Veröffentlichung abschließen.

Die reine Steuerkomponente erfüllt diese Integrationsschritte noch nicht.
R09.03/D und die Gesamtabnahmen werden dadurch nicht abgeschlossen.
Gewählte Banken/Lieferanten und deren bereits abgeschlossene Codearbeit
bleiben parallel im [aktuellen Arbeitsstand](CRM_ERP_ARBEITSSTAND.md) erhalten.
