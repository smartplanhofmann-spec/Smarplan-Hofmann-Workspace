# Korrektur der belegten Assistenten-Kostensumme

Stand 04.11.2026. Dieser enge Nachtrag ist unabhängig von den neuen
Unternehmensereignissen integrierbar.

Ein tatsächlich erfasster und eingeordneter Eingangsbeleg über 100,00 € netto
ergibt in ProjectEconomics `external_service_net=100.00` und `total_net=100.00`.
Der bisherige Assistant-Adapter summierte beide Werte sowie die übrigen
Kategorien. Dadurch wurden 20.000 statt 10.000 Cent als Projektkosten
ausgegeben; eine Regel ab 150,00 € konnte fälschlich anschlagen.

Neue Kostenquellen verwenden die bereits fachlich berechnete `costs.total_net`
genau einmal. Der Herkunftsmarker
`cost_total_basis=project_economics_total_net_v2` unterscheidet sie ausdrücklich
von alten gespeicherten Quellen. Unbekannte Marker werden abgewiesen.

Alte unmarkierte Kontexte und Regelbelege behalten ihre gespeicherten Beträge,
Hashes, JSON-Bytes und ursprünglichen Annahmequittungen. Ihre Verifizierbarkeit
ist keine Behauptung, der damalige doppelte Kostenbetrag sei richtig gewesen.
Der korrigierte aktuelle Quellenhash macht offene alte Pläne `stale`; neue
Pläne erhalten den tatsächlichen Betrag. Es gibt keine stille Neubewertung
oder rückwirkende Änderung eines bereits angenommenen Fachvorgangs.

Der [separate Runtimepatch](evidence/assistant-cost-total-v2-2026-11-04/runtime.patch)
enthält nur `business_assistant_sources.py` sowie die Kostenvalidierung in
`business_assistant.py`. Er enthält keine Company-Event-Gates, Routen,
Registrierungen oder Tabellen. Die vollständige aktuelle Assistant-Datei im
Ereignisarbeitsbaum darf für diesen Nachtrag deshalb **nicht** übernommen werden.

Zusätzlich übernehmen:

- `backend/test_assistant_cost_total_v2.py`
- dieses Dokument und `docs/evidence/assistant-cost-total-v2-2026-11-04/`

[Manifest mit Vor-/Nachhashes](evidence/assistant-cost-total-v2-2026-11-04/manifest.json).
Die gespeicherte alte Quellenimplementierung stammt tatsächlich aus
`4c2f008`, nicht aus einer nachgebildeten Testformel. Der erste echte rote
Kostenfall und der grüne Nachlauf bleiben erhalten. Drei neue und 17 bestehende
Assistanttests bestehen gemeinsam (20/20, 4,946 s), einschließlich realem
Kostenbeleg und unveränderten angenommenen alten Kontext-/Plan-/Requestzeilen.
Die gemeinsame Prüfung im Zielbaum erfolgt bei der Integration.
