# Unternehmensinstanzen: erster technischer Trennungsschritt

Stand: 02.11.2026. Implementiert und mit synthetischen SQLite-/HTTP-Fällen sowie
PostgreSQL-Laufzeitrollen geprüft; keine Freigabe für einen öffentlichen Mehrkundenbetrieb.

## Betriebsmodell

Jedes Unternehmen erhält einen eigenen Dienstprozess, eine eigene Datenbank,
einen eigenen privaten Ablagepfad, eigene Schlüssel und einen eigenen festen
HTTPS-Host. Hintergrundarbeiter benutzen dieselbe Unternehmenskonfiguration.
Ein Request kann weder Unternehmen noch Datenbank auswählen. Unterschiedliche
Firmen gehören nicht in dieselbe Datenbank oder denselben Python-Prozess.

Die optionale feste Bindung verknüpft eine Instanz-ID mit Host, Datenbank,
Serverablage und dem Fingerabdruck des Vault-Schlüssels. Die Datenbank enthält
eine unveränderliche Identitätszeile; die private Ablage enthält
`.smartplan-instance.json`. Beim HTTP-Start werden beide ausschließlich gelesen.
Fehlende oder widersprüchliche Bindungen verhindern den Start. Weitere
Dateischreibvorgänge prüfen den Marker erneut. Der Planimport-Worker prüft die
DB-Identität gegen seine feste Instanz-ID und seinen Host vor dem ersten Auftrag.

Die erste gebundene Betriebsform erlaubt als Dokumentziel nur `server` oder
`none`. Die getrennte Berechtigung externer OneDrive-/WebDAV-Ziele ist noch nicht
nachgewiesen. Ungebundene bestehende Installationen behalten ihre bisherigen
Ablagefunktionen; sie gelten dadurch nicht als geprüfte Mehrkundeninstallation.

## Kontrollierte Einrichtung und Migration

1. Bestehende Datenbank und Dateien sichern; Wiederherstellung separat prüfen.
   Dienste für die Umstellung anhalten. Kein produktiver Datenumzug erfolgt
   automatisch.
2. Über den bestehenden Migrationsablauf das neue additive Modul
   `business_instance` installieren. Bestehende IDs, Sitzungen, Berichte und PDFs
   werden nicht umgeschrieben. In PostgreSQL erhält der Laufzeitbenutzer nur
   `SELECT` auf `business_instance_identity`; die Bindung benötigt den
   Migrations-/Betreiberzugang.
3. Eine zufällige dauerhafte Instanz-ID mit 32 kleinen Hexzeichen vergeben.
   `SMARTPLAN_INSTANCE_ID`, `SMARTPLAN_PUBLIC_HOST`,
   `SMARTPLAN_DATABASE_DSN`, `SMARTPLAN_VAULT_KEY_FILE` und
   `SMARTPLAN_STORAGE_CONFIG_FILE` in der geschützten Dienstkonfiguration
   eintragen. Die Storage-Konfiguration benötigt `server.path` als absoluten
   eigenen Pfad. Keine Geheimnisse in Kommandozeilenargumenten oder Git ablegen.
4. Das Ablageverzeichnis muss dem Dienstbenutzer gehören und Modus `0700`
   besitzen. Die Bindung als Dienstbenutzer mit Migrations-DB-Zugang ausführen
   (damit auch der Marker diesem Benutzer gehört). Im Backend-Verzeichnis:

   ```sh
   python -m online.instance bind
   ```

5. Mit der regulären Laufzeit-DB-Konfiguration prüfen:

   ```sh
   python -m online.instance check
   ```

6. API und Planimport-Worker mit derselben festen Instanz-ID/Host-Konfiguration
   starten. Neue Unternehmen benötigen unabhängige Ressourcen und Schlüssel.

Der HTTP-Start bindet niemals stillschweigend. Ohne Instanzkonfiguration und ohne
gebundene DB bleibt die bisherige Installation kompatibel. Eine bereits
gebundene DB kann die Prüfung nicht durch Weglassen von `SMARTPLAN_INSTANCE_ID`
abschalten. Wiederholung der identischen Bindung ist erlaubt; Umbenennung,
Schlüsselwechsel oder Wechsel des Ablagepfads sind noch kein implementierter
Migrationsablauf und werden abgelehnt.

Die Ablagemarkierung wird vor der DB-Zeile reserviert. Ein Abbruch kann deshalb
eine Reservierung hinterlassen. Derselbe vollständige Bindungsauftrag kann eine
gültige Reservierung fertigstellen. Eine teilweise geschriebene oder fremde
Markierung wird nicht überschrieben und benötigt Betreiberprüfung.

## Nachweise und offene Grenzen

`backend/online/test_instance_isolation.py` prüft zwei unabhängige Testdatenbanken
mit echten HTTP-Handlern, MFA und Sitzungen: fremde Sitzungen, MFA-Challenges,
Objekte und Offline-Zugänge, getrennte Listen/PDF-Ablagen, eingeschränkte Rolle,
falsche Hosts/Schlüssel/DB/Ablagen, Marker-Manipulation, unveränderte Bestandsdaten
und Altkompatibilität. Ein absichtlich gemeinsam konfigurierter Ablagepfad wird
abgelehnt. Tests benötigen keine echten Konten oder externen Dienste.

`backend/online/test_organization_pg.py` ergänzt echte PostgreSQL-Prüfungen:
Bindung durch den Migrationsbenutzer, ausschließlich lesende Laufzeitrechte,
Neustart und Ablehnung falscher Konfiguration. Das ist noch kein vollständiger
Nachweis zweier produktiver Server-/Datenbankbereiche.

Noch offen: vollständige Mehrfirmenabnahme mit getrennten Datenbanken,
vollständige Prozess-/Container- und Worker-Isolation, Backup-/Restore-Abnahme
der Bindung, Provisionierung, geordnete Host-/Schlüsselrotation sowie getrennte
Connector-, Suchindex- und KI-Kontexte. Die vorhandene Datenschutz-Checkpoint-
Konfiguration bleibt pro Prozess fest und benötigt je Unternehmen eigene Pfade,
Schlüssel und Installations-ID. Ein Betreiber mit Kontrolle über beide
Datenbanken/Dateisysteme kann weiterhin Ressourcen kopieren; die Bindung ersetzt
keine Betriebssystem- oder PostgreSQL-Zugriffstrennung.

Diese Tests bestätigen keine rechtliche Konformität und ersetzen weder
unabhängige Sicherheitsprüfung noch die übrigen Abnahmefälle im Gesamtziel.
