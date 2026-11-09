# Unabhängiger v11-Prüfnachweis

Die Textdateien sind unveränderte lokale Rohprotokolle. Zusammenfassung und
fachliche Einordnung: [Prüfbericht](../../CRM_ERP_MINIJOB_V11_UNABHAENGIGE_PRUEFUNG_2026.md).

- `corrupt-original-before-fix.txt`: bestätigter fehlgeschlagener Gegenbeweis
  auf `7b0b84c`; anschließend behoben durch Autorfix `57423ba`.
- `legacy-identity-fixture-first-failure.txt`: erster fehlerhafter Testaufbau;
  die API lehnte die doppelte Neuanlage der Identitätsquelle korrekt ab.
- `postgres-baseline-four.txt`, `postgres-upgrade-originals-before-fix.txt`
  und `previously-used-original-before-fix.txt`: frühere erfolgreiche enge
  Prüfungen auf dem integrierten Grundstand, keine Nachweise für den späteren Fix.
- `independent-negative-after-fix.txt`: drei zusätzliche fachliche Nachweise
  auf `c5cb370`, der lokalen Übernahme des Autorfixes.
- `crlf-lf-originals.txt`: tatsächliche Quellerzeugung mit CRLF, danach
  unveränderte Originalprüfung und idempotente Wiederholung unter LF.
- `postgres-final-six.txt`: abschließende sechs tatsächliche PostgreSQL-,
  MFA-, HTTP-, Konkurrenz- und Wiederherstellungsfälle nach dem Fix.
- `historical-kernels.json`: tatsächliche SHA-256-Werte der 32 unveränderten
  historischen Kernmodule.

Die drei ergänzenden Testdateien liegen in `backend/`. Der PostgreSQL-Lauf ist
mit dem vorhandenen bewachten lokalen Test-DSN reproduzierbar:

```text
python -m unittest online.test_business_payroll_individual_minijob_pg online.test_minijob_v11_independent_pg -v
python -m unittest test_minijob_v11_independent_review -v
python -m unittest test_minijob_v11_crlf_review -v
```

Die PostgreSQL-Prüfung benötigt `SMARTPLAN_TEST_DSN` für eine eigene synthetische
Testdatenbank sowie passende `pg_dump`-/`pg_restore`-Programme. Die lokalen
Wrapper dieser Prüfung waren an Container, Loopback-Port 32782 und die
erlaubten Datenbanknamen gebunden. Sie sind keine produktiven Skripte.
Die SQLite-Gegenprobe mit absichtlich beschädigter Historie darf ausschließlich
in der vom Test angelegten Wegwerfkopie ausgeführt werden.
