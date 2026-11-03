# Serviceberichte ohne Verbindung

Stand: 03.11.2026. Diese Anleitung beschreibt den neuen integrierten Ablauf;
der aktuelle Prüfstand steht im [Fortschrittsbericht](CRM_ERP_FORTSCHRITT.md).

## Vorbereiten und erfassen

Mit Verbindung anmelden und das zugeordnete Projekt für die Offlinearbeit
vorbereiten. Der Gerätezugang benötigt eine ausdrückliche Freigabe für
Serviceberichte sowie die aktuellen Lese- und Schreibrechte im Projekt.
Ein älterer Gerätezugang erhält dadurch keine zusätzlichen Rechte; bei Bedarf
erneut mit Verbindung anmelden.

Im Projekt unter der Dokumentation den Bereich **Serviceberichte** öffnen und
**Servicebericht erfassen** wählen. Titel, ausgeführte Leistung und gegebenenfalls
Notizen eingeben. **Entwurf auf diesem Gerät speichern** sichert den Stand im
verschlüsselten Gerätespeicher.

Über **Prüfen und unterschreiben** die angezeigte Fassung mit Projekt und Kunde
prüfen. Namen und Unterschrift erfassen und die Bestätigung ausdrücklich setzen.
**Unterschrift auf diesem Gerät sichern** bewahrt genau diese Fassung. Sie lässt
sich anschließend nicht weiterbearbeiten. Eine Korrektur erfordert einen neuen
Bericht; die vorhandene Unterschrift wird nicht auf veränderten Text übertragen.

## Übertragen und wieder öffnen

Ein auf dem Gerät unterschriebener Bericht ist noch keine bestätigte
Serverarchivierung. Die Liste zeigt den tatsächlichen Übertragungsstand.
Nach Wiederverbindung **Synchronisieren** verwenden. Die ursprüngliche
Erfassung bleibt mit derselben Kennung erhalten, auch nach App-Neustart oder
einer verlorenen Serverantwort.

Erst nach bestätigter Archivierung und geprüfter PDF-Prüfsumme ist das archivierte
PDF auch lokal verfügbar. **Archiviertes PDF öffnen** zeigt diesen unveränderten
Stand. Ein fehlendes PDF wird nicht durch ein neu erzeugtes Ersatzdokument als
erfolgreich synchronisiert ausgegeben.

Im Browser ist der übertragene Bericht im selben Projekt unter den
Serviceberichten mit seinem PDF erreichbar. Gerätezeit der Unterschrift und
Empfangszeit am Server sind getrennt gekennzeichnet. Die Gerätezeit ist eine
Angabe des Geräts, kein unabhängig bestätigter Zeitstempel.

## Wenn die Übertragung wartet

- Ohne Verbindung bleibt die vollständige Erfassung auf dem Gerät gespeichert.
- Bei pausiertem Dokumentmodul wartet die Übertragung auf erneute Aktivierung.
- Bei abgelaufenem Zugang oder entzogenen Rechten ist eine aktuelle Anmeldung
  beziehungsweise Berechtigung erforderlich. Gespeicherte Daten werden deshalb
  nicht gelöscht; fehlende Rechte lassen sich nicht durch Wiederholen umgehen.
- Wenn Projektname oder Kunde seit der Erfassung geändert wurden, wird der
  erstmalige Import angehalten. Die unterschriebene Fassung bleibt unverändert
  und muss fachlich geklärt werden. Eine bereits bestätigte Erfassung bleibt
  auch nach einer späteren Umbenennung identisch wieder abrufbar.
- Bei fehlerhaften Angaben oder einer abweichenden Archivbestätigung wird kein
  Erfolg angezeigt. Das Original bleibt für die Klärung erhalten.

## Umfang und Erhalt vorhandener Daten

Neue Offline-Serviceberichte verwenden das bestehende Businessarchiv, seine
Projektbindung, Versionshistorie und PDF-Prüfung. Die älteren Protokolle im
historischen Protokollreiter bleiben unverändert. Sie werden nicht kopiert oder
erneut unterschrieben.

Fotos werden separat im selben Projekt erfasst. Ihre spätere Übertragung
verändert keinen bereits unterschriebenen Bericht. Dieser Ablauf unterstützt
keine nachträgliche Einbettung von Fotos und keinen automatisch abgeschlossenen
Checklistenlauf. Er versendet keine Dokumente an Kunden oder externe Ablagen.

Die Rechte werden serverseitig bei jeder Übertragung und Wiederholung frisch
geprüft. Offlinefreigaben bleiben zeitlich begrenzt; Geräteschutz und
verschlüsselte lokale Speicherung ersetzen keine reale Geräteabnahme. Die
vollständigen Gesamtabnahmen B, F und G bleiben gesondert nachzuweisen.
