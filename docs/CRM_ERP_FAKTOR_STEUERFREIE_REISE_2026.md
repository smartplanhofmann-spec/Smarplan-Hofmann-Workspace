# Faktor-Vollmonat mit bereits erstatteter steuerfreier Reise

Neuer abgegrenzter Source3-Vertrag:
`de_2026_factor_taxfree_travel_month_v10`, Quellenvertragsversion 2 und Umfang
`regular_standard_factor_taxfree_travel_month`. Die bisherigen v5-Gesamtfälle,
v8-/v9-Faktorregeln, PAP-Kerne und Zahlungsverträge bleiben unverändert.

Der Fall verbindet genau einen belegten v9-Faktorperiodenfall für den ganzen
Kalendermonat mit mindestens einer tatsächlichen Reiseabrechnung und deren
vollständig ausgeführter steuerfreier Erstattung. Beschäftigung, Entgelt,
Profil und Identität müssen aus demselben unveränderten v9-Fall stammen. Die
Berechnung vergleicht sämtliche Cent- und Beitragsfelder außerdem mit dem
vorhandenen v8-Vollmonat. Es wird keine neue Steuerformel verwendet.

Die Reise wird über die bestehenden Original-, Klassifizierungs- und
Auszahlungsprüfer nachgerechnet. Ein neues Flag oder ein eingetragener
Nullbetrag kann diese Prüfung nicht ersetzen. Neue Details ergänzen die
expliziten `travel_payment_refs` zu den bisherigen `travel_settlement_refs`.
Der neue private Quellenadapter bindet jede ursprüngliche Zahlungsfassung,
ihren unveränderten Reisegeldflusshash und den vollständigen zugehörigen
Zahlungsstand. Rückzahlungen, Korrekturen und Aufhebungen dürfen nicht fehlen.
Neue Verwendung benötigt die aktuellen Fassungen; historische Belege behalten
ihren ursprünglichen Zahlungsstand. Kontodaten werden dafür nicht in die
Quellenauswahl oder Zahlungszusammenfassung übernommen.

Das bereits ausgezahlte steuerfreie Geld erhöht weder Brutto noch Netto.
Im synthetischen Referenzfall bleiben bei 5.000 Euro Monatsbrutto und Faktor
0,753 genau 589,08 Euro Lohnsteuer und 3.323,42 Euro Netto. Die bereits
erstatteten 14 Euro Reise stehen separat daneben. Bei belegter Faktorkorrektur
auf 0,900 beträgt das Netto 3.208,34 Euro; ursprüngliche Rechnung, Quittungen,
Reise und Reisezahlung bleiben erhalten.

Dieser erste Fall enthält ausdrücklich **kein M-Merkmal** und keine
steuerpflichtigen, pauschal besteuerten oder unbaren Reisebestandteile.
Solche Originale werden gesperrt. Ihre Bescheinigungs- und Verarbeitungswirkung
wird nicht als null ausgegeben. Ansprüche, Bonus, Teilmonat, Profilwechsel,
andere Personen/Monate, unvollständige Erstattung und bloß übernommene
Altzahlungen bleiben ebenfalls gesonderte Fälle.

Die private Monatsakte nutzt weiterhin `kind=calculation_case` und die
vorhandenen Endpunkte. Der Lohnlauf bleibt äußerlich Source3. Die neue
Regel-/Quellenpaarung wird ausdrücklich gewählt; eine alte Fallakte wird nicht
heimlich auf den neuen Vertrag umgestellt. Browser und App erhalten dafür
einen getrennten Einstieg. Die Integrations- und PostgreSQLnachweise werden
auf den endgültigen gemeinsamen Quellenstand bezogen.

Die tatsächlichen Backend-Gegenfälle stehen in
`backend/test_payroll_factor_taxfree_travel.py`. Der Clientfixture-Generator
`scripts/generate-payroll-factor-travel-fixture.py` erzeugt Daten durch echte
Original-, Reise-, Zahlungs-, Monatsfall- und Lohnservices. Er ruft weder
Anbieter noch Bank an. Amtliche Meldung und produktive Zulassung werden nicht
behauptet.

Backend-Prüfstand vor der unabhängigen Integration: 40 gezielte bestehende und
neue Fach-/Workflowfälle bestehen, darunter sieben neue V10-Fälle. Tatsächliche
Reisezahlungen, ursprüngliche v9-/v8-Beträge, Faktorkorrektur mit alten PDF-/JSON-
Originalen, Zahlungspräfix nach Rückzahlung, Rechte und gesperrte M-/Steuerfälle
wurden geprüft. Alle 32 zuvor archivierten Rechenkerne sind bytegleich.
Clientintegration und unabhängiger PostgreSQL-/Restorelauf folgen getrennt.
