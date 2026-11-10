# Offline-Serviceberichte: unverändertes Original und neuer Entwurf

Arbeitsauftrag R11.03/F/G. Ein unterschriebener Gerätebericht kann beim ersten
Import wegen geänderter Projekt-/Kundenbezeichnung mit409 abgelehnt werden.
Bisher bleibt er gesichert, aber die allgemeine Synchronisation überspringt
einen solchen Konflikt dauerhaft. Der bisherige Wiederholen-Knopf löst ihn nicht.

Der additive Diagnoseweg prüft ausschließlich das genaue eingefrorene Kommando
mit aktuellen Projekt-/Dokumentrechten und bestehender enger Gerätefreigabe.
Er unterscheidet bereits bestätigtes Original, wieder passenden Kontext und
geänderte Bezeichnungen. ID-/Nonce-Kollision, manipuliertes Original, fehlende
Rechte oder beschädigtes Archiv werden nicht als kopierbarer Konflikt ausgegeben.
Keine neuen Tabellen, historischen Originaländerungen oder Außenwirkungen.

Browser bleibt der vorhandene verbundene Berichteditor. In der installierbaren
Windows-/iPhone-App zeigt „Konflikt prüfen“ alte und aktuelle Bezeichnungen.
Bereits bestätigte beziehungsweise wieder passende Originale werden mit genau
dem alten Kommando erneut abgeglichen. Bei einer tatsächlichen Kontextänderung
kann ausdrücklich ein neuer lokaler Entwurf angelegt werden. Er übernimmt nur
den Text, bekommt eine neue Dokumentidentität und aktuelle Bezeichnungen und
benötigt eine neue Unterschrift. Original und altes Kommando bleiben verschlüsselt
gesichert und sichtbar als Konflikt; keine falsche Synchronisationsbestätigung.
Ein vorhandener Nachfolgeentwurf wird wieder geöffnet statt nochmals kopiert.
Bei erneutem Serverwechsel vor der Entscheidung muss erneut geprüft werden.

Zu prüfen: unveränderte Server-/Geräteoriginale, verlorene Bestätigung, tatsächliche
HTTP-/MFA-Rechte, Kontextwechsel zwischen Vorschau und Bestätigung, zweifaches
Bestätigen, verschlüsselter Neustart, Speicherausfall, Unternehmens-/Sitzungswechsel,
neue Unterschrift und getrennte Übertragung des neuen Berichts, mobile Bedienung.
Implementierung und Nachweise sind in Arbeit; kein Abschluss von R11.03 oder A–G.

## Gemeinsamer technischer Schlussnachweis

Die Implementierung ist jetzt lokal abgeschlossen.30 gemeinsame Backendfälle
bestehen in28,246s einschließlich tatsächlichem lokalem HTTP, Online-MFA und
wirklichem TLS. Zwei eigene tatsächliche PostgreSQL-/Dump-/Restoreläufe bestehen
in18,974s beziehungsweise20,113s. Die alte Gerätefreigabe ist nach Restore401;
erneute MFA liefert das unveränderte Original, beide Versionen und Original-PDF.
Beide eigenen512MiB-Testcontainer sind nach ID-/Label-/Loopbackprüfung entfernt.

36 gemeinsame native Fälle bestehen in19s. Darin enthalten sind zehn neue
Konfliktfälle, vier tatsächliche Widgetabläufe in Windows-/iOS-Darstellung und
ein voller nativer MFA-/TCP-Ablauf mit wirklicher Kundenumbenennung, neuem
Entwurf, neuer Unterschrift und getrenntem Serveroriginal. Der frühere Bericht
bleibt im verschlüsselten Gerät unverändert als Konflikt; nur das neu signierte
Dokument wird zusätzlich importiert.19 bestehende Offline-Berichtfälle und zwei
bisherige Windows-Widgetfälle bleiben ebenfalls grün. Ein früherer15er-Lauf
ist getrennt erhalten. Keine dieser Darstellungen ist eine reale Geräteabnahme.

30 Paket-/Inventar-/CI-Auswahlfälle bestehen in28,006s; der neue Diagnosebaustein
ist im gemeinsamen nativen Windows-/Supportquellpaket enthalten. Appanalyse
ohne Probleme. Keine neue Laufzeitabhängigkeit, Schemaänderung oder historische
Finanz-/Lohnkernänderung. Die Diagnose ist ausdrücklich im engen Geräteumfang
freigegeben; fehlende Fähigkeiten älterer Server werden nicht als Rechteentzug
fehlinterpretiert. Unbekannte/mehrdeutige JSON-Felder werden zurückgewiesen.
Zusätzlich bestehen32 bisherige Firmenbindungs-, Zwei-Firmen-HTTP-, Offlinezeit-
und Fotofälle in7s. Endgültige Analyse mit Produktthema: keine Probleme,31,5s.

Frühe rote Nachweise bleiben erhalten: falscher Importpfad/Fixtureparameter,
anfänglich fehlende strikte JSON-Decodierung des neuen lokalen Endpunkts,
mehrdeutige Widget-Scrollauswahl, unaufgeräumter Testtimer sowie fehlender reiner
Screenshot-Testimport. Sie werden nicht als erfolgreiche Erstläufe ausgegeben.
Sechs lesbare390px-Bilder mit wirklicher Inter-Schrift und Produktthema sind
gesichert; Dialog, neuer Entwurf und gesperrte Ansicht sind visuell geprüft.

Rohdaten und genaue Grenzen: [Manifest](evidence/offline-report-conflicts-2026-11-10/manifest.json).
Diese Folge ist noch nicht veröffentlicht; eigene Remoteprüfungen folgen erst
nach dem Push. Nicht geschlossen: andere Dokument-/Konfliktarten, Geräte-,
Fach-, Betriebs- und vollständige A–G-Abnahme. Der Gesamtauftrag bleibt offen.


## Veröffentlichung

Produktabcc3510f4d913b1d4e57c30fd2e5283bce2156b ist auf dem autorisierten
Testbranch veröffentlicht und per Remote-Hash bestätigt. Sein eigener wirklicher
Archiv-/MFA-Start besteht1/4,655s. Development42850956041 und unsignierter iPhone-
Lauf42850955774 sind noch aktiv. Kein Liveupdate oder Geräteabschluss.
