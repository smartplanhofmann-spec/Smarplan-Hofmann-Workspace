# Erhaltene Originalaufträge bei älteren Servermetadaten

Unabhängige Fortsetzung der [nativen Neustartwiederaufnahme](CRM_ERP_ONLINEAUFTRAEGE_NEUSTART_2026-11-09.md).
Im veröffentlichten Ausgangsstand 29f526d gab eine fehlende Serverfähigkeit
`project_creation_journal` den bisherigen RAM-Ablauf frei, ohne einen bereits
gespeicherten geschützten Auftrag zu suchen. Bei einem späteren älteren
Serverstand konnte deshalb ein neues Original mit neuer Request-ID entstehen.

Die echte MFA-/TCP-/HTTP-Gegenprobe bestätigt den Fehler: Nach tatsächlich
angenommener Rückgabe, verlorener Antwort und vollständiger Appneuerstellung
ohne die neue Servermetadatenfähigkeit wurde eine weitere Lagerbewegung
angenommen. Die erwartete Sperre blieb aus. Der rote ursprüngliche Rohbeleg
bleibt erhalten; ein allgemeiner vermeintlicher Serverfehler wird nicht behauptet.

`OnlineCommandJournal.requireNoPending` sucht jetzt auch ohne diese Fähigkeit
schreibfrei nach dem ursprünglichen Namespace für API, Konto, Art und Projekt
beziehungsweise Mitarbeiter. Ein fehlender Schlüssel, ein beschädigter oder
unaufgelöster jüngster Stand und jedes nichtleere Original blockieren neue
Aufträge. Private Inhalte werden dabei weder ausgegeben noch einer unbekannten
aktuellen Firma zugeordnet. Es wird kein Ersatzschlüssel angelegt.

Ein frisches Gerät ohne diesen Bestand und ein nachweislich entschlüsselter
leerer, bereits abgeschlossener Zustand erlauben weiterhin den begrenzten
alten RAM-Ablauf. Die Metadaten eines neueren Servers allein werden nicht als
Nachweis für das Verschwinden eines alten Originalauftrags behandelt.

Nach Rückkehr der ursprünglichen Serverfreigabe ist dasselbe Original wieder
erreichbar. Material wird identisch wiederholt, Kilometer werden zuerst über
die unveränderte private Quittung geklärt. Es entsteht keine zweite Zahlung.
Die Zugriffssicherung wird nicht wegen eines lokalen Speicherfehlers gelockert.

Reine alte Unitfixtures erklären nun ausdrücklich ein leeres Testgerät ohne
persistente Originale; sie umgehen keinen produktiven Speicherfehler.
Tatsächliche verschlüsselte Dateien, Schlüsselverlust, kaputte neueste
Snapshots und der ursprüngliche HTTP-Fehler werden separat geprüft.

Der gemeinsame Nachlauf besteht alle 95 betroffenen nativen Fälle ohne Fehler
oder Skip, einschließlich der unveränderten echten negativen HTTP-Gegenprobe
und des privaten Kilometerauftrags. Fortschrittslog: 43 Sekunden. Die gesamte
Appanalyse ist ohne Befund in 20,9 Sekunden. Vorherige vier Fehler inkonsistenter
leerer Unitfixtures bleiben erhalten; die produktive Erkennung wurde zu ihrer
Behebung nicht gelockert. Backend, historische Rechenmodule und tatsächliche
Zahlungsarithmetik sind in diesem Folgefix unverändert.

[Rohbelege, konkrete Ergebnisse und Quellhashes](evidence/native-journal-downgrade-2026-11-09/verification.json).
Browserintegration und echte Geräte-/Serverabnahme bleiben getrennte Aufgaben.
