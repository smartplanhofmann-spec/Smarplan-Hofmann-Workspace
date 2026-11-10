# Aktueller Lieferstand

Stand 10.11.2026. Projekt: `/workspace/Smarplan-Hofmann-Workspace`.
Das unveränderte Gesamtziel bleibt maßgeblich. Diese Seite trennt einen
geprüften Lieferstand von der vollständigen Produktivfreigabe.

## Bereits vollständig zentral geprüfter Stand

Quelle `4f67bf8ba68c09c2ed77651b76d3487b85b32465` auf dem autorisierten
Testbranch. Alle 20 Developmentgruppen erfolgreich; lokal 1.997 Appfälle,
Browser-/PostgreSQL-/MFA-/Restoreabläufe und Paketprüfung erfolgreich.
CRM, Projekte, Angebote/Rechnungen, Zeiten, Material, Service und die
abgegrenzt dokumentierten Finanz-/Personalabläufe sind im gemeinsamen Kern.
Neu enthalten sind die native Offline-Berichtsklärung und der geprüfte
CAMT.053.001.08-Originalimport in Browser und App.

| Paket | Tatsächlicher Nachweis |
|---|---|
| [Windows mit lokalem Backend](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42864815919/artifacts/13788890572) | 40.629.752 Bytes; tatsächlicher Windowsbau einschließlich XML-Parser/Schema |
| [Windows für den Onlineserver](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42864815919/artifacts/13788027574) | 22.255.008 Bytes; getrenntes Onlinepaket |
| [Signiertes iPhone-/iPad-Paket 208](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/actions/runs/42864950880/artifacts/13789192915) | 29.954.759 Bytes; manuelle Vorbereitung erfolgreich, TestFlight-Upload false |

Das signierte App-Store-IPA ist allein noch keine TestFlight-Verteilung oder
Geräteinstallation. Der letzte vom Nutzer bestätigte Serverstand bleibt
`a93cb4d02eab610e5f2a8b07fbd1ee51ae99c3e5` vom 05.11. Eine Aktualisierung
des Quellbranches verändert diese Installation nicht automatisch.

## Neue integrierte Korrektur

Die [Personal-Kontenauswahl](CRM_ERP_PERSONAL_KONTENAUSWAHL_2026-11-10.md)
ist als `56d9925840a6890ca9c4fc128b47909d75765c8d` integriert und im
Hauptprojekt zusätzlich mit echter Anmeldung, Quellarchiv und App geprüft.
Personalverantwortliche benötigen für ein Mitarbeiterprofil keinen Zugang
zur vollständigen Benutzerverwaltung. Ein vorhandenes Profil kann auch nach
Sperrung seines Benutzerzugangs korrekt beendet werden. Diese spätere
Korrektur ist in den oben genannten älteren Paketen noch nicht enthalten;
ihre Veröffentlichung und eigene vollständige Paketprüfung folgen separat.

## Was die vollständige Gesamtfreigabe noch benötigt

Die konkreten offenen Punkte stehen in der
[Anforderungsmatrix](CRM_ERP_ANFORDERUNGEN.md) und im
[Arbeitsstand](CRM_ERP_ARBEITSSTAND.md). Dazu gehören weiterhin direkte
Anbieterzugänge und echte Bank-/Lieferantendaten, benannte noch nicht
unterstützte Lohnfälle und Meldeverfahren, weitere Offline-/Altbestandsfälle,
aktuelle Server- und tatsächliche Geräteprüfung sowie die unabhängigen
Fach-, Sicherheits- und Datenschutznachweise. Entwicklungstests schließen
diese Punkte nicht pauschal. Die spätere Loxone-Einrichtung bleibt wie vom
Nutzer festgelegt zurückgestellt. Es ist noch keine vollständige
Produktivfreigabe der gesamten Software dokumentiert.
