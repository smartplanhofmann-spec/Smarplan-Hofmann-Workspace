# Kilometererstattung: Backend- und Originalnachweis

Stand 09.11.2026, isolierte Arbeitskopie `smartplan-private-car-backend-20261109`
auf `487977a`. Anforderung R09.02, Originalziel §9 und Abnahme D. Der konkrete
[enge Vertrag](CRM_ERP_KILOMETERERSTATTUNG_VERTRAG_2026.md) beschreibt Grenzen,
amtliche Grundlagen, exakte JSON-Felder und die ausdrückliche neue V4-Wahl.
Dies ist keine vollständige Reisekosten-, Lohn- oder Produktivfreigabe.

Der neue reine Kern und der private Businessadapter verwenden die vorhandenen
append-only Reise-, Abrechnungs-, Quittungs- und tatsächlichen Geldtabellen.
Es gibt kein zweites Geldjournal und keine Änderung bestehender Reise-Kerne.
Alle 32 historischen Rechenmodule und das 23.863-Byte-Gesamtziel sind gegen ihre
vorhandenen Hashes unverändert. Beide neuen Python-Module stehen konsistent in
den drei bestehenden Paketdateilisten; der tatsächliche Paketimport prüft sie.

## Tatsächliche Ergebnisse

| Nachweis | Ergebnis |
| --- | --- |
| Gemeinsame reine/Fach-/MFA-/HTTP-/v3-/V10-Regression | 52/52, 46,622 s |
| PostgreSQL auf dem endgültigen Produktcode: Originale, Bank/EÜR, Unternehmensarchiv, Dump/Restore und Konkurrenz | 2/2, 66,603 s |
| Zusätzlicher alter v3-MFA-/ACL-/Neustartfall im vorherigen gemeinsamen PG-Lauf | gemeinsam 3/3, 66,116 s |
| EÜR-Nachlauf mit erweiterten Assertions zur echten Rückzahlung | 1/1, 1,309 s; bereits enthaltenes Szenario erneut geprüft |
| Native Paketprüfungen | 16/16, 27,415 s |
| Tatsächlicher Import des endgültigen Supportarchivs mit beiden neuen Modulen | 1/1, 3,871 s; vorhandenen Paketfall erneut geprüft |
| Historische Kerne | 32/32 bytegleich |

Nur synthetische lokale Daten und ein eigener PostgreSQL-16.15-Container
`smartplan-mileage-pg-20261109` auf `127.0.0.1:32783` wurden benutzt.
`pg_dump`/`pg_restore` waren an genau diesen Container und die beiden erlaubten
Prüfdatenbanken gebunden. Der Container wurde nach den Prüfungen entfernt.
Keine Kundeninstanz, externe Zahlung oder produktive Meldung wurde ausgeführt.

## Beweiskette

Eine echte eigene Mitarbeiterfahrt mit privaten Fahrzeug-/Streckenoriginalen
wird als Entwurf gespeichert, mit identischem Auftrag wiederholt und eingereicht.
Eine andere Person prüft die gebundenen Originale und bestätigt die Vorschau.
100.000 Meter ergeben einmalig 3.000 Cent; kein M-Merkmal, Sachbezug oder
zusätzlicher Nettolohn entsteht. Zwei belegte Transfers von 10 und 20 EUR
erzeugen genau 30 EUR bestätigte EÜR-Ausgaben und passende Bankzuordnungen.

Eine begründete Korrektur auf 50.000 Meter weist 15 EUR Überzahlung aus und
erhält die ursprüngliche 30-EUR-Zahlung, deren Quittung und das alte PDF.
Die EÜR bleibt ebenfalls bei 30 EUR. Erst eine tatsächlich belegte Rückzahlung
von 15 EUR und deren ausdrückliche Einordnung vermindern die Ausgabe auf 15 EUR.
Die Anwendung führt keine Überweisung aus und schreibt kein früheres Netto um.

Gegenproben prüfen Pendel-/Dienstwagen-/Auslands-/Misch-/falsche Personen- und
Stättenfälle, Meter-/Bool-/Unicode-/Offsetgrenzen, fehlende Erklärungen,
Rechteentzug vor Originalwiederholung und unveränderte historische Quellen.
Ein gleiches Streckenoriginal kann auch nach tatsächlichem erneutem Upload in
eine andere Personalakte nicht ein zweites Mal abgerechnet werden. Der dabei
angezeigte Blocker enthält keinen fremden Personen-/Abrechnungsbezug.

Die neue V4-Auswahl ist von v3 getrennt. Alte Standardreisen funktionieren
weiter; V4-Fahrten gelangen weder in die v3-Vorgeschichte noch in alte
Payroll-Reise-/Zahlungsauswahlen. Explizite Verwendung im bisherigen Lohnadapter
wird mit 409 abgewiesen. Der unveränderte Standard-v3-Fall ist zusätzlich über
tatsächliche MFA, Laufzeit-ACLs und Neustart geprüft.

Der PostgreSQL-Test prüft getrennte konkurrierende Abschlüsse und parallele
Wiederholung derselben Zahlung. Ein Abschluss gewinnt, der konkurrierende
andere wird abgewiesen; die Zahlungswiederholung liefert eine einzige identische
Quittung. Das vollständige Unternehmens-ZIP enthält die privaten Originale
und bestehenden Reisetabellen. Nach tatsächlichem Dump/Restore bleiben ZIP,
Abrechnungs-/Zahlungsquittungen, PDF und EÜR-Ergebnis erhalten.

## Erhaltene Fehlversuche und Liefergrenze

Die ersten zusätzlichen Testaufbauten verwendeten einen falschen EÜR-
Operationsnamen beziehungsweise noch kein ausdrücklich datiertes EÜR-Profil.
Die API lehnte beides ab. Ein erster PG-Aufbau enthielt eine unnötige zweite
MFA-Anmeldung mit einer falschen Enrollmentannahme; entfernt wurde nur diese
Testzeile. Die erste Paketprüfung fand die bestehende virtuelle Umgebung in
der neuen Arbeitskopie nicht; der Nachlauf verwendet die vorhandene geprüfte
Venv über einen lokalen, nicht versionierten Link. Kein Produktguard wurde
dafür gelockert. Diese Fehlerprotokolle bleiben unverändert erhalten.

Die neuen Testablagen werden vor der Storage-Bindung kanonisiert, damit
macOS-`/var`-Symlinks keine unzulässigen Testpfade erzeugen. Produktionsprüfungen
für Pfade, Sperren und Ownership bleiben aktiv; es gibt keinen `fcntl`-Mock.

Gemeinsame echte Clientfixture:
`app/test/fixtures/private_car_mileage.json`, SHA-256
`30c0d2388a83458259d7cd8c1d98caf69cf08cf8e5396ba36ec9b02ba6aac71b`.
Der Generator verwendet tatsächliche Fachaufrufe und Quittungsabrufe ohne
Rechen- oder Annahmepatches. Browser-/App-Bedienung, gemeinsame Integration und
Auslieferung sind gesonderte Arbeit. Rohprotokolle, Quellenmanifest und Hashes:
`docs/evidence/private-car-mileage-backend-2026-11-09/`.
