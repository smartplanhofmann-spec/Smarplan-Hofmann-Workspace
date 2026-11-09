# Individuelle Minijobsteuer: Bestands- und Quellenprüfung

Geprüfte Ausgangsbasis: `a7c1e0b`, 09.11.2026. R09.03 bleibt eine offene
Gesamtanforderung für reguläre Mitarbeiter und gewerbliche Minijobs. Dieses
Audit schränkt den vereinbarten Umfang nicht ein.

Der bisherige Monatsrechner sperrt `minijob_tax=individual` in
`payroll_de_2026.py`; der Periodenrechner übernimmt dieselbe Sperre in
`payroll_periods_2026.py`. Bei 25, 150 und 603 Euro bleiben Netto und
Beitragsausgaben ausdrücklich unbekannt. Die vorhandenen pauschal besteuerten
Vergleichsfälle bleiben berechenbar. Die reproduzierten Ergebnisse und
Quellhashes stehen in
[diesem Nachweis](evidence/minijob-individual-audit-2026.json).

Die vorhandenen Standard-PAP-, Faktor- und Tagesregeln bilden reguläre
SV-Voraussetzungen ab. Der Standard-PAP setzt bei der Vorsorgepauschale unter
anderem reguläre Renten-, Kranken-/Pflege- und Arbeitslosenversicherung an.
Die Minijobsperre einfach zu entfernen wäre daher keine korrekte Umsetzung.
Zusätzlich bindet `business_payroll_accounts.py` bisher jeden Minijob an den
Steuernachweistyp `flat_minijob_evidence`. Individuelle ELStAM-/Bescheinigungs-
quellen und ihre Jahresmerkmale benötigen ebenfalls einen additiven Vertrag.

Die 258 allgemeinen amtlichen Tabellenwerte, 170 unabhängigen Faktorwerte und
200 Periodenwerte sind vorhanden. Die Minijobbeiträge einschließlich
RV-Mindestbeitrag, Arbeitgeber-KV/RV und Umlagen besitzen eigene Referenzen.
Diese bisherigen Steuervektoren belegen jedoch nicht die Minijobzuordnung der
PAP-Merker. Der lokale gepinnte XML-Spiegel hat SHA256
`63d8981646d139eba2f4dd990c13b43c4fb3883b402a5a40cddf253aa7aa96b4`.
Er definiert insbesondere KRV und ALV jeweils mit 0/1; ein KRV-Wert 2 wurde
nicht angenommen. Das XML ist kein nachgewiesener neuer BMF-Direktdownload.

Während dieses Audits lief zunächst nur die lokale Quellenprüfung. Die
anschließende unabhängige Primärrecherche hat eine wichtige Lücke geschlossen:
das BMF-Schreiben vom 14.08.2025, Randnummer 16, weist bei individuell
besteuerten Minijobs ohne Arbeitnehmer-KV ausdrücklich den **technischen**
PAP-Merker `PKV=1` an. Dieser Merker darf nicht als tatsächlicher Wechsel der
Krankenversicherung gespeichert werden. Der separate Quellenprüfstand
`e9a78eb` dokumentiert Fundstelle, eingeschränkten Anwendungsfall und neue
unabhängige XML-Vergleichswerte. Damit ist individuelle Minijobsteuer keine
dauerhafte Quellenblockade; der neue produktive Rechen-, Identitäts-, Jahres-
und Clientvertrag bleibt ein eigener noch umzusetzender Abschnitt.

33 vorhandene Minijob-/PAP-/Faktor-/Periodenprüfungen bestanden im Audit.
Keiner der historischen Rechenkerne wurde verändert. Als parallel bereits
belegbarer Codefall wurde der reine Faktor-Vollmonat mit steuerfreier extern
erstatteter Reise erkannt: der ursprüngliche v5-Gesamtfall blockiert den Faktor,
während derselbe v9-Periodenfall korrekt berechenbar ist. Die konkrete neue
Umsetzung steht in [Faktor und steuerfreie Reise](CRM_ERP_FAKTOR_STEUERFREIE_REISE_2026.md).
