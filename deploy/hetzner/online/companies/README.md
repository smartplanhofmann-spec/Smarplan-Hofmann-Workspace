# Zusätzliche private Unternehmensinstanz

Dieser additive Weg verändert die vorhandene Installation unter
`/opt/smartplan-online` nicht. Vollständiger Vertrag und Nachweisgrenzen:
[CRM_ERP_PROVISIONIERUNG.md](../../../../docs/CRM_ERP_PROVISIONIERUNG.md).

Beispiel eines **nicht unmittelbar einsatzfähigen** Manifests. Instanz-/Privacy-ID
für jede Firma neu vergeben, tatsächlichen Quellcommit und eigenen Host/Port
eintragen. Keine Zugangsdaten in das Manifest schreiben:

```json
{
  "schema": 1,
  "slug": "alpha",
  "instance_id": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "public_host": "alpha.example.invalid",
  "port": 18871,
  "source_commit": "0000000000000000000000000000000000000000",
  "privacy_installation_id": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
  "plan_import": false
}
```

Voraussetzungen des ausdrücklich gestarteten Betreiberlaufs: Ubuntu/systemd,
lokaler PostgreSQL-Peer-Operator `postgres`, System-Python und ein bereits
vorbereiteter Release unter
`/opt/smartplan-companies/<slug>/releases/<commit>`. Der Release enthält
`app/backend`, `app/web`, `venv/bin/python` mit geprüften gesperrten Abhängigkeiten
und `SOURCE_COMMIT`. Eigentümer des gesamten Baums ist root; fremde Schreibrechte
und unsichere Links sind ausgeschlossen. Der Wrapper installiert keine
Betriebssystempakete und lädt keine unkontrollierten Pakete herunter.

Das Unternehmen erhält gleichnamige Linux-/PostgreSQL-Runtime
`sp_<slug>_run`. Der separate Datenbank-Owner heißt `sp_<slug>_own` und besitzt
keinen Login. Konfiguration, private Dateien, Schlüssel, Sicherungen und
Checkpoint werden nicht zwischen Firmen geteilt.

Mit dem reinen Plan zuerst die abgeleiteten Ressourcen prüfen. Vorbereiten,
Owner-Eingabe, Prüfen und privater Start sind getrennte Aktionen von
`../prepare-company.sh`; Argumente stehen in der verlinkten Dokumentation.
Die versionierten Unit-/Caddy-Vorlagen werden durch
`backend/online/provisioning.py:render` deterministisch erzeugt. Die installierten
Units müssen ihren erzeugten Bytes entsprechen; unbekannte vorhandene Dateien
werden nicht ersetzt.

`start-private` startet ausschließlich die eigene Loopback-API, lokale Sicherung
und gegebenenfalls den bereits installierten Planimport. Der generierte
`Caddyfile.fragment` wird nicht installiert. Keine öffentliche Route, DNS-Zone,
TLS-Ausstellung oder externe Nachricht wird durch diesen Ablauf angelegt.
