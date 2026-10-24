# Smartplan 0.11 – Sevdesk, Google Kalender und OneDrive

Die Anhangvorschau und das überarbeitete Design aus 0.10.1 wurden vom Nutzer als
funktionierend bestätigt. Der nächste zusammenhängende Schritt verknüpft die
bestehenden Büroprogramme mit der Projektmappe. Maßgebliche Korrektur vom
25. Oktober 2026: **OneDrive, kein Dropbox**. Google Kalender und OneDrive sind
bereits mit dem vorhandenen Mailbot verbunden. Diese Verbindungen werden genutzt.

## Zusammenhängender Arbeitsablauf

1. Unter **Integrationen** verbindet die Geschäftsführung Sevdesk über dessen
   API-Zugang. Smartplan prüft den Zugang und speichert ihn verschlüsselt auf Hetzner.
2. Im Projekt wird der richtige Sevdesk-Kontakt gewählt. Angebote und Rechnungen
   werden einzeln ausdrücklich diesem Projekt zugeordnet. Es werden nicht alle
   Vorgänge eines Kunden automatisch einer seiner mehreren Baustellen zugerechnet.
3. Google Kalender und OneDrive verwenden vorzugsweise den vorhandenen Bot.
   Smartplan stellt dafür einen eigenen begrenzten **SPIX-Projektbotzugang** aus.
   Der vorhandene SPIN-Maileingang und die Liste bestätigter Mails bleiben erhalten.
4. Der Bot übernimmt Leseaufträge im bereits vorhandenen Fünfminutenjob. Ein
   zusätzlicher paralleler Job und neue Microsoft-/Google-Appregistrierungen sind
   für diesen Weg nicht erforderlich. Ein Schlüssel allein gilt noch nicht als
   bestätigte Anbieteranbindung: Erst ein gültiger Kontokatalog aktiviert sie.
5. Die Geschäftsführung wählt Kalender und konkrete Termine sowie einen
   OneDrive-Ordner mit dessen tatsächlicher Laufwerk-ID. Ist eine Auswahl noch
   nicht eingetroffen, zeigt Smartplan den ausstehenden Abruf und einen erneuten
   Ladeweg. Fehlender Zugriff wird nicht als erfolgreiche leere Auswahl ausgegeben.
6. Die Projektmappe zeigt die bestätigten Sevdesk-Vorgänge, gewählten externen
   Termine und OneDrive-Unterlagen. OneDrive-Dateien werden bewusst über ihre
   ursprüngliche Microsoft-Browseradresse geöffnet; es werden keine öffentlichen
   Freigaben oder temporären Downloadlinks erzeugt.

Sevdesk bleibt für Angebote, Rechnungen und deren kaufmännischen Status führend.
Das Paket erstellt oder versendet dort keine Dokumente und erfindet keine Zahlung.
Der Kalenderabruf legt keine Termine oder Einladungen an. OneDrive-Metadaten
verändern, verschieben oder analysieren keine Dateien. Die vorhandene separate
OneDrive-AppFolder-Berichtsablage bleibt erhalten.

## Bestätigter Stand und Aktualisierung

Die App zeigt den letzten tatsächlich bestätigten Abrufzeitpunkt. Ein Klick auf
Aktualisieren oder ein vorgemerkter Botauftrag erzeugt keinen neuen Erfolgszeitpunkt.
Beim Öffnen und bei Rückkehr zur App werden bestätigte Projektzuordnungen nach
Bedarf aktualisiert; automatische Abrufversuche sind je Anbieter auf einen Versuch
pro fünf Minuten begrenzt. Der erste bestätigte Stand bleibt währenddessen nutzbar.
Fehler und ausstehende Daten bleiben erkennbar.

Anfragen sowie externe Integrationen benötigen Online-Anmeldung. Vorhandene
verschlüsselte Offline-Projektmappen, Aufgaben, Termine und Planquellen behalten
ihren Ablauf und ihre Siebentagefreigabe; diese ist keine Löschfrist.

## Rechte, Schlüssel und Wiederholungen

- Verbindungen, Kontowechsel und Projektzuordnungen verwaltet die Geschäftsführung.
- Finanzdaten sind ausschließlich für berechtigte Geschäftsführungs-/Buchhaltungsrollen
  sichtbar; zusätzlich gilt die aktuelle Projektfreigabe.
- Kalender-/OneDrive-Metadaten sind auf die ausdrücklich gewählte Projektquelle
  begrenzt. Der Projektbotzugang erlaubt weder allgemeine Kunden-/Finanzabrufe
  noch Anmeldung, Mailzustellung oder Provideränderungen.
- Schlüssel und OAuth-Geheimnisse werden ausschließlich geschützt in der App oder
  im Credential-Feld des Bots eingegeben, niemals im Chat. Der SPIX-Zugang ist
  90 Tage gültig. Seine Rotation bewahrt bestätigte Zuordnungen desselben Kontos.
- Wiederholte Bestätigungen erzeugen keine Doppelzuordnung. Verspätete Ergebnisse
  aus abgelösten Konten, Projektzuordnungen oder Schlüsselaufträgen werden verworfen.
- Kontowechsel, Rollenverlust und Abmeldung werden nach externen Abrufen nochmals
  geprüft. Anbieteranfragen halten währenddessen keine globale Bürotransaktion offen.

## Bereitstellung und tatsächliche Abnahme

Das Paket benötigt Server **0.11.0-online-pilot**, Datenbankschema **6** und die
Fähigkeit **business_integrations** sowie die neue Online-App 0.11.0.
[Updateanleitung](deploy/hetzner/online/UPDATE_0_11.md) und
[Projektbot-Anschlusspaket](integrations/project_bot/README.md) gehören zusammen.
Die sieben neuen Tabellen werden im bestehenden geschützten Kandidatenablauf
migriert. Es wird kein zusätzlicher Serverdienst installiert.

Cloudprüfungen verwenden ausschließlich synthetische Daten und ersetzte Provider-I/O.
Echte PostgreSQL-Migration, Wiederherstellung, HTTPS und native Builds werden
getrennt geprüft. Die Verbindung zu den tatsächlichen Benutzerkonten und die erste
reale Botlieferung erfolgen anschließend beim Nutzer. Sevdesk-API-Dokumentation
war aus der Cloud nicht zugänglich; die konservative Leseimplementierung und ihre
Quellgrenzen sind in den [Quellen](backend/online/INTEGRATIONEN_QUELLEN.md) offengelegt.

Der alternative direkte Google-OAuth-Weg ist unter erweiterter Einrichtung
vorbereitet. Er benötigt einen passenden eigenen OAuth-Client. Googles externer
Testmodus liefert bei Kalenderscopes nur sieben Tage gültige Refresh Tokens;
diese Anbieterregel ist unabhängig von Smartplans Offlinefreigabe. Für den vom
Nutzer gewählten vorhandenen Bot ist diese zusätzliche Registrierung nicht nötig.
