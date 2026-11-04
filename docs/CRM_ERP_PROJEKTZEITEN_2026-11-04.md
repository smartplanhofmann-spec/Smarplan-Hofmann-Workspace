# Projektzeiten: Aufnahme, Umsetzung und Nachweise

Stand: 4. November 2026. Basis `c875ea5a221e5d38533bb7d50a1d96b9c455d22f`; isolierter Arbeitsbaum `/workspace/smartplan-project-time-20261104`. Dieser Abschnitt folgt der Priorität Projektbetrieb mit Angeboten, Rechnungen und Stunden. Lohnabrechnung und Buchhaltung werden hier nicht erweitert. Die Originalanforderungen in `CRM_ERP_Gesamtziel.txt` bleiben unverändert.

## Bestandsaufnahme und ausgeführter Plan

Vorhanden waren die projektbezogene Stempeluhr mit Start/Pause/Fortsetzen/Stopp, serverseitige Mitarbeiter- und Projektrechte, Tagesfreigabe, unveränderliche Korrekturen, Stundenexport und eine verschlüsselte Offline-Warteschlange in Flutter. Die Browserfassung arbeitet online und meldet diese Grenze ausdrücklich. Vorhandene Tests belegen unter anderem wiederholte Übertragung, Gerätekonflikte und den Bezug freigegebener Stunden zu Rechnungsquellen.

Vier konkrete Lücken wurden bearbeitet:

1. **Gemischte Server- und Offline-Erfassung:** Wurde eine auf einem anderen Gerät begonnene Zeit auf dem Mobilgerät zwischengespeichert und dort offline fortgesetzt, enthielt die lokale Ereigniskette nur die neuen Aktionen. Die angezeigte Dauer ließ dadurch bereits bestätigte Arbeit weg. Die Fortsetzung übernimmt jetzt die vorhandenen Serverereignisse, bevor sie neue Aktionen anhängt. Ein verschlüsseltes Schließen/Wiederöffnen und spätere Übertragung erhalten die vollständige Kette. Die Original-Startaktion wird nicht erneut versendet.
2. **Korrektur erreichbar machen:** Browser und Flutter bieten zu einem bestätigten Zeitnachweis jetzt Originalereignisse und Korrekturverlauf. Eine Person mit `time.approve` kann eine freigegebene Einzelzeit mit Datum, vorzeichenbehafteter Minutenänderung, Begründung und ausdrücklicher Bestätigung korrigieren. Die bestehende serverseitige Korrektur wird verwendet; die Stempelereignisse werden nicht überschrieben. Bei unklarer Antwort bleibt derselbe Auftrag mit derselben Request-ID erhalten. Flutter kann ihn innerhalb derselben Sitzung auch nach Schließen und Wiederöffnen des Dialogs erneut senden.
3. **Arbeitstag und Projekt eindeutig anzeigen:** Die API liefert die tatsächlichen `work_dates` und `approved_work_dates` aus den bestehenden Segmenten und Tagesfreigaben. Die Gerätezeitzone entscheidet nicht, welchen Arbeitstag man korrigiert. Zeitlisten finden über Mitternacht reichende Schichten auch über ihren Folgetag. Die Projektzuordnung steht in Browser und Flutter am Nachweis; das globale Flutter-Zeitkonto zeigt sie zusätzlich an der Einzelkarte.
4. **Zahlen und Rechte in der Oberfläche:** Die Browser-Monatskarte zeigt Nettoarbeitszeit nach Pausen und Korrekturen. Originaldauer und Korrekturen bleiben im Detail getrennt sichtbar, auch bei vorhandenen Korrekturen unter einer Minute. Flutter zeigt den Stunden-CSV-Export nur mit dem serverseitig verlangten `personnel.read`. Entzogene Leserechte entfernen geöffnete Zeitdetails beziehungsweise fremde Zeitkontodaten.

## Bedienung im geprüften Umfang

Im Browser unter **Personal & Zeiten** die Zeit im richtigen Projekt starten und später pausieren oder beenden. Nach Prüfung den Arbeitstag freigeben. **Zeiteintrag prüfen** öffnet Projekt, Original und Verlauf; **Freigegebene Zeit korrigieren** ist nur bei entsprechender Berechtigung und Tagesfreigabe verfügbar.

In Flutter erfasst **Arbeitszeit** in der Projektmappe die eigenen Zeiten. Bei gültiger zuvor erteilter Offline-Freigabe werden Aktionen zuerst verschlüsselt lokal gesichert. **Auf diesem Gerät gesichert**, **Synchronisiert**, eine vorübergehend deaktivierte Funktion und ein Konflikt bleiben unterscheidbar. Bestätigte Einzelzeiten können zum Nachweis geöffnet werden. Das globale **Zeitkonto** enthält ebenfalls die einzelnen Nachweise und, soweit berechtigt, die Mitarbeiterauswahl und Tagesfreigabe. Eine Zeitkorrektur benötigt eine Verbindung und wird nicht als Offline-Buchung vorgemerkt.

## Anforderungen und Status

| Anforderung aus dem Gesamtziel | Status dieses Abschnitts | Nachweis / Grenze |
| --- | --- | --- |
| Projektbezogene Arbeitszeit erfassen | implementiert und gezielt getestet | Vorhandene Ereignisschnittstelle und echte Browser-/Flutter-Abläufe |
| Offline erfassen, nach Wiederverbindung ohne Duplikat senden | implementiert und gezielt getestet in Flutter | Verschlüsseltes Wiederöffnen, Antwortverlust und gemischte Ereigniskette; Browser bleibt online |
| Freigabe und nachvollziehbare Korrektur | implementiert und gezielt getestet | Vorhandene Serverkorrektur jetzt in beiden Oberflächen erreichbar |
| Projekt- und Rollenrechte | gezielt getestet | Techniker liest eigenen Verlauf, Korrektur direkt und in der Oberfläche gesperrt; entzogene Rechte und Lesemodus |
| Verständliche Kosten-/Stundenbasis | gezielt getestet im Stundenumfang | Netto-Monatswert, unveränderte Originalzeit, getrennte Korrekturhistorie und bestehende Rechnungsquellentests |
| Installierte Windows-/iPhone-Anwendung | weiterhin extern zu prüfen | Gemeinsamer Flutter-Code und mobile Widgetansicht geprüft; keine Installation auf diesen Betriebssystemen in diesem Abschnitt |

## Prüfungen und Reproduktion

Die abschließenden Protokolle stehen in `docs/evidence/project-time-2026-11-04/`; Browsernachweise einschließlich Bildschirmansichten liegen getrennt in `docs/evidence/project-time-browser-2026-11-04/`. Der abschließende Gesamtmanifest bindet die geprüften Quellen und Nachweise.

- **20/20 Backendtests**: Zeitereignisse, Rechte, Teilfreigabe über Mitternacht, Folgetagfilter, bestätigte Rechnungsquellen und bestehender HTTP-Vertrag; 11,024 Sekunden.
- **14/14 Fluttertests**: vier neue Dialog-/Rechtefälle, bestehende Stempeluhr, verschlüsselte Offline-Erfassung und zwei echte HTTP-Integrationsfälle einschließlich Moduldeaktivierung; neun Sekunden laut Testprotokoll.
- **5/5 neue Browser-Vertragstests** und **ein realer Chromium-Ablauf** mit MFA, HTTP/SQLite, Projektzuordnung, Tagesfreigabe, Korrektur, Antwortverlust, eingeschränkter Rolle und mobiler Darstellung. Der letzte Nachlauf verwendet den endgültigen Backendstand.
- **853/853 Tests der vorhandenen Node-Gesamtsuite** bestehen einschließlich der fünf neuen Browser-Vertragstests; 18,443 Sekunden. Diese Gesamtzahl wird nicht zusätzlich zur Teilmenge gezählt.
- Statische Dartanalyse der sieben geänderten Flutterquellen/-tests: keine Befunde. `git diff --check`: keine Befunde.

Backend aus dem Repository:

```sh
PYTHONPATH=backend:backend/online:backend/business_tests \
  /tmp/smartplan-backend-verified/bin/python -m unittest -v \
  test_business_time test_time_billing test_business_planning_time_api
```

Flutter aus `app`:

```sh
PATH=/workspace/toolchains/clang-19/bin:$PATH \
PUB_CACHE=/workspace/toolchains/pub-cache \
SMARTPLAN_TEST_PYTHON=/tmp/smartplan-backend-verified/bin/python \
  /workspace/toolchains/flutter/bin/flutter test --no-pub \
  test/business_time_details_test.dart test/business_time_widget_test.dart \
  test/business_offline_time_test.dart test/business_backend_integration_test.dart \
  test/business_module_pause_integration_test.dart --reporter expanded
```

Der neue Offlinefall scheitert vor der Korrektur nachweislich am fehlenden bestätigten Start; derselbe Fall besteht danach. Der erste neue Dialogtestlauf hatte ausschließlich Testaufbaufehler: Der Finder erwartete eine Checkbox statt des vorhandenen Schalters, und Sitzungs-Timer wurden erst nach der Widgetprüfung aufgeräumt. Test und ursprünglicher Fehlerlauf bleiben erhalten. Eine frühere Umgebungsprobe konnte ohne Socketfreigabe keinen lokalen Flutter-Testserver starten; die geprüften Läufe verwenden die freigegebene lokale Testumgebung. Die vorhandene PDFium-Bibliothek derselben Paketversion wurde aus dem lokalen Buildcache übernommen; es wurde kein Ersatz für Produktcode eingebaut.

Auch der erste zusätzliche Node-Gesamtlauf war durch die äußere Testumgebung eingeschränkt: Der unveränderte Zeitzonentest konnte seinen Unterprozess nicht ausführen (`spawnSync ... EPERM`). Derselbe vollständige Lauf mit der erlaubten lokalen Socket-/Prozessnutzung besteht; kein Anwendungscode wurde dafür angepasst. Beide Protokolle bleiben erhalten.

## Verbleibende Grenzen

Dieser Abschnitt ist kein Nachweis, dass das gesamte CRM/ERP fertig oder bereits produktiv freigegeben ist. Es gab keine Veröffentlichung, keine Mainänderung und keinen PostgreSQL-Lauf. Die Browserfassung hat weiterhin keine dauerhafte Offline-Warteschlange. Flutter-Konflikte erhalten die gesicherten Aktionen und stoppen automatische Wiederholung; eine allgemeine Zusammenführung widersprüchlicher Geräteeingaben ist hier nicht hinzugekommen. Eine nachträgliche Änderung des Projekts eines bestehenden Zeitnachweises und die freie Nachbuchung abgeschlossener Schichten in der mobilen Oberfläche sind nicht Bestandteil dieser Änderung. Die Installation und Bedienung auf einem realen Windows-Gerät und iPhone sowie der gemeinsame Kundentest bleiben getrennte Abnahmen.
