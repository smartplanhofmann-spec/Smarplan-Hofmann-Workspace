# Geschützte Browseroriginale über Neuladen und erneute Anmeldung

Die abgegrenzte Erweiterung zu R07.01/R09.02/R11 ist implementiert und lokal
geprüft: Offene Materialrückgaben sowie private Pkw-Kilometeraufträge bleiben
im selben Browserprofil auch nach vollständigem Neuladen und erneuter
MFA-Anmeldung erhalten. Die native Wiederaufnahme einschließlich schreibfreier
Altbestandserkennung bleibt unverändert vorhanden. Ein automatisches erneutes
Senden nach dem Start findet nicht statt.

Vor dem fachlichen POST wird das vollständige bestätigte Original samt
ursprünglicher Vorgangskennung als AES-GCM-256-Chiffretext in IndexedDB
gespeichert. Der atomare Schreibvergleich erlaubt bei konkurrierenden
Vorbereitungen genau ein Original pro Konto, Fachart und Projekt/Mitarbeiter.
Ein fehlgeschlagener Schreibvorgang gibt keinen fachlichen POST frei. Der
gespeicherte Umschlag enthält nur Version, Suchbezug, Firmenbindung, zufällige
Revision, Nonce und Chiffretext; keine privaten Befehlsfelder, Zugangsdaten
oder dauerhaft verwendbaren Entschlüsselungsschlüssel.

Der ausschließlich online verfügbare GET-Endpunkt
`/api/v1/business/client-original-key` leitet mit HKDF-SHA256 einen getrennten
Schlüssel aus dem bestehenden Servergeheimnis und dem vollständigen Bezug ab.
Der Serverhauptschlüssel wird nicht ausgegeben. Jede Lese-, Wiederholungs- und
Abschlussprüfung verlangt die aktuelle MFA-Sitzung, bestätigte Instanzbindung
und frische Fachleserechte. Offlinezugänge erhalten keinen Schlüssel. Die
Antwort ist `no-store`; der Browser importiert den Schlüssel als nicht
exportierbaren Arbeitsspeicherschlüssel und hält ihn nicht im lokalen Journal.

Die Bindung enthält Instanz, Host, API-Version, Konto, Auftragsart und konkretes
Projekt beziehungsweise Mitarbeiter. Eine globale Lagerfreigabe ersetzt keine
entzogene Projektzuordnung. Eine fremde Firma unter demselben Host kann ein
erhaltenes Original weder lesen noch durch einen Ersatzauftrag umgehen. Auch
wenn ein älterer Server die neue Fähigkeit nicht mehr meldet, prüft der Client
den bisherigen Browserbestand schreibfrei. Erhaltene oder beschädigte
Chiffretexte bleiben gesperrt erhalten. Tatsächlich leere Altbestände erlauben
weiter den alten RAM-Ablauf ohne erfundene Firmenbindung.

Nach Wiederanmeldung öffnet die Materialrückgabe das gespeicherte Original.
Die unveränderte Wiederholung verwendet dieselbe Kennung und prüft Bewegung,
Originalentnahme und historische Bewertung. Bei Kilometeraufträgen wird zuerst
der private ursprüngliche Status gelesen. Fahrt-/Einreichungsdetails, Quellen,
Vorgängerhash und vollständige damalige Rechenherleitung werden nach einem
Neustart ebenso streng geprüft wie zuvor über den Laufzeitvalidator. Eine
bloß selbstkonsistente, aber ausgetauschte Quittung reicht nicht aus.

Erst die geprüfte ursprüngliche Serverbestätigung entfernt den exakt passenden
lokalen Auftrag. Nur die ausdrückliche Nichtannahme des ursprünglichen POST
erlaubt einen separaten Abbruch; ein späterer fehlgeschlagener GET kann eine
bereits angenommene Buchung nicht zur Nichtannahme umdeuten. Dieser zusätzliche
Grenzfall wurde im neuen Browsercode rot reproduziert und korrigiert. Private
Ansichten leeren ihren Arbeitsspeicher weiterhin beim Verlassen; der
verschlüsselte noch ungeklärte Auftrag wird dadurch nicht gelöscht.

Die Prüfung umfasst alle 1.017 Browsermodulfälle, die gezielten Schlüssel-/
Rechte-/MFA-Backendfälle sowie die tatsächlichen Chromium-Abläufe
`material-return-restart` und `private-car-mileage-restart`. Beide sind in CI
registriert. Material: angenommene Rückgabe mit verlorener Antwort, komplettes
Neuladen, tatsächliche erneute MFA, identischer Originalauftrag, eine Bewegung,
historische Preise, Restmengen, preisfreie Lagerrolle und 390px. Zusätzlich
prüft echtes IndexedDB zwei konkurrierende Schreibvorgänge, Firmenwechsel,
fehlende Serverfähigkeit und unverändert erhaltene beschädigte Daten.
Kilometer: Neustart getrennt bei Fahrt, fremder Freigabe und tatsächlicher
Auszahlung; jeder angenommene Auftrag wird ausschließlich über seinen Status
geklärt, ohne zweiten POST. Die spätere 100km/30EUR-zu-50km/15EUR-Korrektur
erhält die erste Zahlung und führt erst nach tatsächlicher Rückzahlung zur
EÜR-Korrektur. Alte Historien/PDFs und mobile Ansicht bleiben geprüft.

38 betroffene native Fälle und die bestehenden 16 Paket-/Importprüfungen
bestehen ebenfalls. Die getrennte [Reisezeitpunktkorrektur](CRM_ERP_REISEZEITPUNKT_2026-11-09.md)
erhält die strenge historische Validierung und besteht ihre tatsächliche
PostgreSQL-/Restorekette. [Quellbindung, Ergebnisse, erste Fehler und Rohläufe](evidence/browser-original-restart-2026-11-09/manifest.json).

Der Umfang setzt einen erreichbaren gebundenen Server, dieselbe berechtigte
Anmeldung und erhaltenen Browserspeicher voraus. Er überträgt Aufträge nicht
auf andere Geräte und macht den Browser nicht offline buchungsfähig.
Entfernte Browserdaten oder verlorene Servergeheimnisse werden nicht durch
neue private Eingaben rekonstruiert; ursprüngliche Serverjournale bleiben die
fachliche Quelle. Weitere allgemeine Browseraufträge besitzen dadurch noch
keine Neustartpersistenz. Gesamt-Abnahmen A–G, weitere Lohnfälle, vollständige
Altbestandübernahme und reale Geräte-/Serverauslieferung bleiben gesondert offen.
