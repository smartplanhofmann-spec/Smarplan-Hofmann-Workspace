# Projektanlage mit ursprünglicher Wiederholungsquittung

Die direkte Projektanlage kann eine bereits gespeicherte Antwort verlieren.
Der bisherige Server ignorierte die vom Browser gesendete `request_id`; ein
erneuter Versuch konnte dadurch ein zweites Projekt erzeugen.

`Office.add_project` bindet jetzt eine angegebene 32-Hex-Vorgangskennung an den
ursprünglichen Namen, Kundentext und die Kundenkennung. Ein identischer Auftrag
liefert dieselbe Projektkennung. Abweichende Originalfelder unter derselben
Kennung werden mit 409 abgewiesen. Auch vor einer Wiederholung werden der aktive
Benutzer und dessen aktuelle Eigentümerrolle geprüft.

Projekt, gegebenenfalls neuer Kunde, Audit und Quittung werden gemeinsam
gespeichert. Die vorhandene Foundation-Quittungstabelle wird wiederverwendet;
die Speicherversion bleibt 7. Verschachtelte SQLite-Vorgänge verwenden einen
Savepoint und schließen keine äußere Transaktion vorzeitig ab. PostgreSQL nutzt
die vorhandene Transaktions-/Advisory-Sperre. Die Quittung speichert den Hash des
Auftrags und die Projektkennung, keine zusätzliche Kopie der Kundenanschrift.

Die lokalen und Online-HTTP-Routen reichen `request_id` durch. Das zusätzliche
Feature `project_creation_receipts` kennzeichnet den neuen Vertrag. Ältere
Clients ohne Vorgangskennung können weiterhin ausdrücklich neue Projekte
anlegen. Schema 6 besitzt die neue Quittungsgrundlage nicht; ein alter Server
darf deshalb nicht als wiederholungssicher behandelt werden.

Der Browser verwendet seine bestehende Warteschlange für unveränderte offene
Antworten. Die native App erhält den Originalauftrag beim Schließen und erneuten
Öffnen des Dialogs; vor einem Retry prüft sie das ursprünglich vorhandene und
frisch bestätigte Feature. Bei einem Altserver bietet sie nach einer unklaren
Antwort die Prüfung des Projektbestands an. Die native Projektwarteschlange
bleibt derzeit auf den laufenden App-Prozess begrenzt; die dauerhafte
Offline-Warteschlange für Arbeitszeiten ist davon unabhängig.

## Abgegrenzte Nachweise

- Neun Ownerfälle und 23 bestehende Kunden-/Anfragefälle bestanden im
  [32er-Lauf](evidence/project-creation-replay-2026-11-04/backend-first.txt).
- Die [Gegenprüfung](CRM_ERP_PROJEKTANLAGE_GEGENPRUEFUNG_2026-11-04.md) bestätigt
  Rohparameterbindung, aktuelle Benutzersperre, echte Sicherung/Wiederherstellung
  und zwei tatsächliche PostgreSQL-Fälle mit unabhängigen Verbindungen und
  vollständigem Rollback. Der zusätzliche SQLite-/HTTP-Lauf enthält dieselben
  neun Ownerfälle und drei neue Gegenproben, keine zwölf zusätzlichen Fälle.
- Die [native Prüfung](CRM_ERP_PROJEKTANLAGE_NATIVE_WIEDERHOLUNG_2026-11-04.md)
  enthält 15 neue Clientfälle und bestehende Regressionen.
- Der [gemeinsame Browserlauf](evidence/project-integrated-2026-11-04/browser/manifest.json)
  verwirft eine echte 201-Antwort erst nach der Serverannahme. Der unveränderte
  Retry liefert dieselbe Kennung ohne zusätzliches Projekt oder zusätzlichen
  Kunden. Dieser Browserlauf verwendet synthetisches SQLite mit echtem HTTP;
  die separate PostgreSQL-Gegenprüfung prüft echte Datenbanktransaktionen.

Die Prüfungen erzeugen keine Produktivprojekte und führen keine Migration des
bestehenden Kundensystems aus. Windows-/iPhone-Installation und gemeinsamer
Produktivserverstand benötigen eigene Auslieferungsnachweise.
