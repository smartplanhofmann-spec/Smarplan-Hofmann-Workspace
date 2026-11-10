# Aktive RV-Profil- und Lohnbindung

Erhaltener Entwurf vor der Umsetzung. Der inzwischen angeschlossene Umfang und
die tatsächlich abgeschlossenen bzw. noch laufenden Prüfungen stehen im
[Integrationsstand](CRM_ERP_MINIJOB_RV_INTEGRATION_2026-11-10.md). Die nachstehenden
nächsten Schritte sind die damalige Planung, keine aktuelle Behauptung fehlenden
Codes oder abgeschlossener Gesamtfreigabe.

Arbeitskopie/workspace/smartplan-minijob-rv-20261110, Basis4aa0abd.
Der veröffentlichte Produktstand4aa0abd und reine Belegcommit9e6e80f sind
separat vollständig geprüft. Diese neue RV-Entwicklung ist noch nicht fertig
oder veröffentlicht. Der Quellen-/Bestandsplan liegt im Hauptprojekt.

Die reine Zustandskomponente und private append-only Speicherung sind vorhanden.
Nach Anfangsfehlern in Testclock, Annahmehash und der zunächst unvollständigen
Sparse-Arbeitskopie bestehen16Komponenten-/Speicherfälle sowie Unternehmens-/
Datenschutzprüfungen. Die20Paketfälle sind durch19Erfolge im Nachlauf und eine
getrennte erfolgreiche tatsächliche Importwiederholung abgedeckt. Insgesamt
70verschiedene ausgewählte Fälle, kein nachträglich grüner Erstlauf.

## Verbindlicher nächster Anschluss

Die vorhandenen Beitrags- und Steuerformeln bleiben unter ihren bisherigen
Versionen bytegleich. Der neue eigene RV-Vertrag besitztRegel-/Modulhash und
private Tatsachenhistorie. Seine Bindung gehört an das angenommene Profil und
an den tatsächlich verwendeten Profilnachweis im Lohnquellsnapshot; ein neuer
Rechenkern oder eine zusätzliche Source6 ist dafür nicht nötig.

- Optionaler ausdrücklich benannter Profil-Quellenvertrag1 mit
  `rv_lifecycle_source_contract_version:1` und vollständigem
  `rv_lifecycle_ref`. Beide Felder gemeinsam oder keines; keine Versionsannahme.
- Sobald für diese Person ein RV-Lebenslauf aufgenommen ist, benötigen neue
  Minijobprofile den aktuellen bestätigten Verlauf. Erwarteter Status für das
  Wirksamkeitsdatum muss mit dem Profil-Bool übereinstimmen. Offene Verfahren
  erlauben keinen scheinbar abschließenden Status nach dem Kandidatentermin.
- Vor jeder neuen Lohnvorschau/Bestätigung mit Minijobprofil den aktuellen
  RV-Verlauf, den tatsächlichen Lohnmonat und die gebundene Profilquellenversion
  prüfen. Der Nachweis darf nicht nur zum Beginn des Profils passen: Ein
  Mai-Profil mit Befreiung darf den belegten August-Widerruf nicht übergehen.
- Der angenommene Lohnquellsnapshot enthält das ursprüngliche Profil samt
  RV-Referenz. Historische Profil-/Laufprüfung rekonstruiert genau diese
  ursprüngliche RV-Fassung für den damaligen Monat, nicht die heutige Fassung.
  Eine alte angenommene Quittung bleibt unverändert wiederholbar.
- Bei historischen RV-Referenzen muss die tatsächlich passende Annahmezeit
  stimmen. Keine spätere RV-Quelle rückwirkend in einen alten Profil-/Lohnhash
  schreiben. Neue bestätigte Versionen bleiben eigenständige Originale.
- Bestehende alte Profile/Läufe ohne übernommenen RV-Lebenslauf bleiben unter
  ihrem dokumentierten alten Vertrag erhalten. Der neue Weg wird nicht als
  pauschaler Nachweis sämtlicher alter Befreiungsanträge ausgegeben.

## Nächste Implementierungsschritte

1. Für frische Auflösung einer bereits gespeicherten RV-Fassung die aktuelle
   eigene Fassung aus dem erwarteten bisherigen Präfix ausschließen.
   Bei historischem Lesen weiter nur dessen genau gespeicherte Vorfassungen
   binden. `prior_assessment_refs` muss mehrere Revisionen derselben ID erlauben.
2. Neue Profil-/Lohn-Gates und historische Binder additiv inbusiness_payroll.py.
   Zuerst tatsächliche aktuelle Profilanlage und neue Lohnläufe nach Aufnahme,
   zuvor angenommene Lauf-/Profilquittungen und alte Regelkerne erhalten.
3. Tatsächlicher kontrollierter Netto-/Zahlungs-/EÜR-/Jahresablauf, privater
   Mitarbeiterbeleg und negative Referenz-/Zeit-/Statusfälle.
4. Beide Clients: eigener privater RV-Editor, bewusste Originalwahl, vollständiger
   alter Präfix, unveränderte Wiederholung und aktuelle Rechte/Featureprüfung.
   Profilpflege bindet die ausdrücklich gewählte aktuelle RV-Fassung.
5. Eigene HTTP/MFA-, PostgreSQL-/Konkurrenz-/Komplettrestorekette, Paketierung,
   gemeinsame Regression und Veröffentlichung nur auf dem autorisierten Testbranch.

Verwaltungsfristen werden nicht automatisch aus Feiertagen errechnet. Der
Vertrag benötigt die belegte tatsächlich geprüfte Frist und deren Nachweis;
er prüft die Mindestkalendermonatsfolge. Er erfindet aus Zeitablauf weder
Nichtbeanstandung noch eine amtliche Übermittlung. Anfangsbefreiungsverfahren,
Wiederbeginn, parallele Jobs und besondere Renten-/Versorgungsfälle sind nicht
allein durch diese erste Aufhebungsfunktion gelöst. Korrekturen bereits erledigter
Behördenentscheidungen benötigen ihren ausdrücklichen eigenen Fachvertrag.
