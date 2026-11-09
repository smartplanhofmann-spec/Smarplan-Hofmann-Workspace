# Gemeinsame Integration am 09.11.2026

Der geprüfte Produktkandidat 487977a verbindet die zuvor getrennten
Erweiterungen. Nachweiscommits danach verändern diese Produktdateien nicht.
Das gesamte ursprüngliche CRM-/ERP-Ziel ist damit noch nicht abgenommen.

## Tatsächlich integrierter Umfang

- Projektmeilensteine mit Verantwortlichen, Termin, manuellem Status und Historie.
- An Firma und Konto gebundene Offlinezugänge V2; alte Dateien bleiben erhalten.
- Verschlüsselter, neustartfester Anlageauftrag für manuelle Servicefälle.
- Wartungsverträge im Browser bearbeiten, pausieren und reaktivieren.
- Faktor-Vollmonat V10 mit bereits erstatteten steuerfreien Reisen ohne erneute
  Addition der Erstattung zum Nettolohn.
- Individuell besteuerter enger Minijobfall V11 mit privaten Nachweisen, beiden
  Clients und ausdrücklicher Übernahme geeigneter ungenutzter Altvorgänge.
- Freigegebene Projektstunden in Browserbelege übernehmen; Ursprung,
  Wiederholungsschutz und einmalige endgültige Abrechnung bleiben gebunden.

Die fachlichen Grenzen und Originalnachweise stehen in den verlinkten
Einzeldokumenten des [aktuellen Arbeitsstands](CRM_ERP_ARBEITSSTAND.md).

## Gemeinsame Prüfungen

| Prüfung | Tatsächliches Ergebnis |
| --- | --- |
| Alle Browsermodultests auf 487977a | 972 bestanden, 0 fehlgeschlagen, 0 übersprungen, 25,519 Sekunden |
| Acht betroffene native Testsuiten auf 487977a | 48 bestanden, 0 fehlgeschlagen, 0 übersprungen, 36 Sekunden |
| Echter nativer PDF-Renderer auf 281ced9 | Drei Fälle bestanden: Seitenwechsel, extrem große Seite mit begrenztem Bitmap und beschädigtes Original mit geprüftem Speichern |
| V10, V11, positive Source5-Korrekturen und Paketprüfungen auf 487977a | 46 bestanden, 302,710 Sekunden |
| Echte PostgreSQL-/MFA-/Chromium-Zeitabrechnung auf 487977a | Rechnung, zwei Zeitbindungen, PDF, Rechte, Wiederholung, Quellenänderung und Doppelabrechnungsschutz bestanden |
| Historische Rechenmodule | Alle 32 Module und ursprüngliche Zahlungsarithmetik bytegleich zur Basis af98278 |
| Ursprüngliches Gesamtziel | Unverändert, 23.863 Bytes, SHA-256 `a4dea28f6de4afd3e36d1549441aad91ce16dad374f56097979cc2d79b07fbf5` |

[Vollständige Rohprotokolle und Metadaten](evidence/final-assembly-2026-11-09/checks-so-far.json),
[gemeinsamer PostgreSQL-/Browsernachweis](CRM_ERP_ZEITABRECHNUNG_INTEGRATION_2026-11-09.md),
[unveränderte Originale](evidence/final-assembly-2026-11-09/preserved-originals.json).

## Vollständiger App-Lauf und Fehlerbehandlung

Der vorherige vollständige Lauf auf d4df2f5 endet nach 38:31 Minuten mit
1.746 bestandenen und vier fehlgeschlagenen Fällen, ohne Skip. Er ist kein
grüner Gesamtnachweis. Zwei ältere Service-Testdateien enthielten insgesamt
drei nicht zusammenpassende Firmen-/Storagebindungen. Die Testaufbauten sind
korrigiert und alle drei realen HTTP-Fälle separat bestanden; die produktive
Instanzprüfung bleibt unverändert streng.

Der Offene-Posten-Widgettest überschreitet sein fünfminütiges Zeitlimit.
Sein Helfer lässt beim Warten auf echte IO unnötig künstliche Zeit vergehen
und wartet beim Export nicht auf den tatsächlichen Dateirückruf. Diese
Testursache wird getrennt behoben und mit unveränderten Fachassertionen
geprüft. Ein erneuter vollständiger Gesamtlauf ist noch nachzuweisen.

Die alten CI-Fehler auf 3859a1c sind ebenfalls gezielt behoben. Der alte
Remote-Lauf bleibt mit sechs erfolgreichen und zwei fehlgeschlagenen
Development-Jobs sowie fehlgeschlagenem unsigniertem iPhone-Lauf dokumentiert.
Ein neuer Remote-Lauf muss den neuen Kandidaten selbst prüfen.

## Verbleibende Arbeit

Die Materialrückgabe ist noch nicht durchgängig bedienbar: Im Browser fehlt
die Aktion, in der App fehlt die Bindung an die Originalentnahme. Beide Clients
werden ergänzt, damit Originalpreis, Restmenge, Bestand und Projektkosten
konsistent bleiben. Der vorhandene Backendvertrag wird weiterverwendet.

Als weiterer konkreter Alltagsfall wird die belegte Kilometererstattung für
rein dienstliche Inlandsfahrten im privaten Pkw ausgearbeitet. Gegenwärtig
tragen Personal- und Reiseoberflächen nur Belegauslagen; ein ungenutzter
Kilometer-Richtwert allein ist kein nutzbarer Ablauf. Gemischte/private Fahrten,
Arbeitswege, Dienstwagen und Doppelabrechnung werden nicht stillschweigend
mitgerechnet.

Weitere Lohn-/Steuerfallgruppen, Altbestandsofflineübernahme und die vollständigen
Abnahmen A–G bleiben in der Anforderungsmatrix offen. Reale Serverinstallation,
Gerätebedienung, Signierung und externe Fach-/Anbieterfreigaben sind eigene
Nachweise. Der letzte vom Nutzer bestätigte Serverstand bleibt A93.
