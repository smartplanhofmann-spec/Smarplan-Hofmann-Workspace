# PR 8 gegen den aktuellen Projektstand

Read-only-Abgleich vom 04.11.2026: lokaler Stand
`c875ea5a221e5d38533bb7d50a1d96b9c455d22f`,
[PR 8](https://github.com/smartplanhofmann-spec/Smarplan-Hofmann-Workspace/pull/8)
mit Head `6371da1ec3641818b158ce3d3e132be674bc397e` und Basis
`6e27f9dad2d04281cd1e3e692c4c4804a65edaf8`.
Der PR ist offen und ungemergt. Seine historischen grünen Tests sind kein
Prüfnachweis für den heutigen lokalen Stand.

**Die wesentlichen Navigationskorrekturen fehlen weiterhin.** Der aktuelle
Quellstand enthält zugleich spätere Katalog-, Kontext- und Offlinefunktionen.
Deshalb die Fehler gezielt im heutigen Code beheben und die alten Dateien nicht
vollständig ersetzen. Der zuständige Navigationsagent hat die kritischen
Fundstellen und ursprünglichen Testfälle erhalten.

## Weiterhin relevante Korrekturen

| Priorität | Fundstelle in c875ea5 | Ergebnis und erforderliche Übernahme |
|---|---|---|
| P0: Fachregister brechen die Projektansicht ab | `app/lib/project_workspace_page.dart:1486,1535,1750` | `projectSections` hat sieben Einträge, die Fachregister verwenden `section >= 7`. Der `IndexedStack` baut zugleich alle `itemSection`-Grundlisten auf; deren `projectSections[section]` ist damit außerhalb der Liste. Titel aus dem jeweiligen `kind` ableiten. Statisch unmittelbar nachvollziehbar; hier nicht erneut in Flutter ausgeführt. |
| P1: Registeridentität bei Rechteänderung | `project_workspace_page.dart:100,229,435,1789` | Nur numerische Auswahl und `visited`-Indizes, keine stabile Fachregisteridentität. Entfällt ein früheres Register, kann ein erlaubter Bereich auf anderen Inhalt zeigen. Auswahl/Besuchsstatus nach Identität erhalten, alte Klick-/Dropdown-Callbacks gegen aktuelle Namen und Grenzen prüfen. |
| P1: Ungesicherte Pläne und äußerer Rückweg | `project_workspace_page.dart:444,1606,1626`; `app/lib/plan_pages.dart:667` | Der Planeditor schützt nur seinen eigenen `leave()`-Weg. Die äußere Projektroute besitzt keinen gemeinsamen Exit-Guard; Import-Rücksprung ersetzt den Plan-Navigator direkt, innerer Pop verwendet direkt `pop()`. Dirty-Editoren und laufende lokale/Online-Speicherung müssen auch offstage erhalten bleiben. Keine doppelten inneren/äußeren Pops. |
| P1: Verwaltung ohne sichtbaren Rückweg | `app/lib/main.dart:531`; `app/lib/home_views.dart:406,687` | Die Basis von PR 8 enthält bereits PR 7. Dessen `onBackToWorkspace` und sichtbares „Zur Übersicht“ fehlen lokal ebenfalls. Den bestehenden Hauptbereich/Filter erhalten, nur die zusätzliche Verwaltungsroute schließen; reine Legacy-Roots bekommen keinen künstlichen Rückweg. |
| P1: Stornogutschrift/Belegeditor | `app/lib/business_documents.dart:17,1007,1987`; `backend/business_documents.py:946` | Client kennt `cancellation`, Backend verwendet `credit_note`. Für bestehende Stornogutschriften fehlen der gebundene Metadateneditor und kanonische Typdarstellung. Backend erlaubt bei deren Bearbeitung nur Titel, Datum, Hinweise und Stornogrund. Positionsdialog hat zudem keine fachlichen Read-/Write-Parameter und prüft im Callback nur `mounted`. PR-Korrekturen gezielt in aktuelle Beleg-/Kataloglogik übertragen. |
| P1: Projekt-Finanzsicht und offene Dialoge | `app/lib/business_finance.dart:47,69,146,331` | Projektbezogene offene Posten laden immer auch das globale Versandjournal. Ein fehlendes globales Recht kann die ganze Projektansicht scheitern lassen. Zahlungseditor ohne Read-/Write-Parameter; Mahnungsbestätigung prüft Rechte nach dem Dialog nicht erneut. Relevant für projektbezogene Belege/Zahlungsanzeige, unabhängig von der zurückgestellten Vollbuchhaltung. |
| P1: Material ohne Projekt/Finanzrecht | `app/lib/business_operations.dart:366,1058`; `backend/business_inventory.py` | Projektgebundener Bereich kehrt vor dem Bereichswähler zurück; Nutzer kann dort ohne Projekt feststecken. Materialauswahl lädt weiterhin den finanzgeschützten `/articles`-Katalog. PRs begrenzter `/inventory/articles`-Endpunkt samt `inventory_article_refs` fehlt. Bewegungseditor unterscheidet Entnahme/Rückgabe/Umlagerung noch nicht mit dem PRs konkretem Payloadaufbau. |
| P2: Aktionsfehler und Dialogrechte | `app/lib/business_widgets.dart:485,659,700`; `business_document_access.dart:55,145` | Generische Öffnen-/Erstellen-Aktionen besitzen keinen sichtbaren Fehler-/Retry-Rahmen; rein lesende Detaildialoge beobachten den Rechteentzug nicht. Editor-Titel bleibt trotz entzogener Sicht sichtbar. Unterlagenfreigabe setzt alte Ladefehler nicht zurück. Die gezielten PR-Korrekturen fehlen. |

## Aktuelle Funktionen erhalten

- Der alte PR hat zehn Fachregisterplätze. Der heutige Stand hat bis zu
  **vierzehn**: zusätzlich `Zusatzfelder`, `Kundenservice`, `Assistent`,
  `Kundenportal`. Die alte feste Slotliste würde diese neuen Bereiche falsch
  zuordnen. Tests müssen die heutigen Fähigkeiten und alle sichtbaren Register
  abdecken, nicht blind die alte Höchstzahl 17 Gesamtregister übernehmen.
- Der heutige `BusinessEditor` besitzt `pendingKey`, `pendingSession`,
  `readAllowed`, Kontextinvalidierung und ursprüngliche Wiederholvorgänge.
  Diese spätere Absicherung fehlt im PR. Kombinierte Lesebedingungen sind heute
  teilweise über `readAllowed` ausdrückbar; die zusätzliche Rechteprüfung des
  PRs ist damit an die heutige API anzupassen, nicht als Ersatz einzuspielen.
- `business_documents.dart` und `business_operations.dart` verwenden heute
  `CatalogPriceFlow`, datierte Preisquellen, ursprüngliche Pending-Commands und
  Generation-/Kontextprüfung. Diese Pfade sind weiterentwickelt und müssen bei
  Positions-, Metadaten- und Dialogänderungen erhalten bleiben.
- Die heutige Projektmappe kann Zeit, Fotos und integrierte Serviceberichte
  anhand vorhandener Offlinefreigaben zugänglich halten. Ihre Bedingungen
  `timeEventsSupported`, `fieldMediaSupported` und `canAccessServiceReports`
  dürfen nicht auf die älteren reinen Servermodulbedingungen zurückfallen.
- Die heutige explizite Belegkonvertierung einschließlich kumulierter und
  Schlussrechnung bleibt erhalten. Ein alter kompletter Belegeditor wäre ein
  Rückschritt, auch wenn einzelne PR-Korrekturen weiterhin fehlen.

## Nachweise und Übernahmereihenfolge

Die [originalen PR-Patches](evidence/project-release-readiness-2026-11-04/pr8-original-patches.json)
enthalten alle 29 geänderten Pfade; zwei PNGs haben laut GitHub keinen Textpatch.
Die [Textdiff-Rekonstruktion](evidence/project-release-readiness-2026-11-04/pr8-text-hunks.patch)
wurde ausschließlich mit `git apply --check` geprüft. Der
[Prüflauf](evidence/project-release-readiness-2026-11-04/pr8-apply-check.txt)
bestätigt Konflikte in den heutigen Beleg-, Finanz-, Operations- und generischen
Widgetdateien sowie Versions-/Dokufeldern. Es wurde nichts angewendet. Ein erster
Rekonstruktionsversuch ohne Added-File-Moduszeilen ist separat dokumentiert.
Die [PR-7-Basiskorrektur](evidence/project-release-readiness-2026-11-04/pr7-parent-original-patches.json)
ist getrennt gespeichert, weil ein reiner PR-8-Patch ihren Rückweg nicht enthält.

Zuerst Registeraufbau, Identität und sichtbaren Verwaltungsrückweg beheben.
Dann Plan-Exit-Guard einschließlich laufender Speicherung und Import-Rücksprung
integrieren. Parallel können die zuständigen Fachagenten Beleg-/Stundenabläufe
prüfen. Generische Dialogänderungen sind gemeinsam abzustimmen, da sie beide
Fachstrecken betreffen. Anschließend die alten Regressionsthemen auf den heutigen
Fähigkeits-/Rechtevertrag übertragen: tatsächliche App-/Projektroute, sichtbarer
Inhalt, mehrmaliger Rückweg, 390px, Rechteänderung, veralteter Callback,
ungesicherter Plan, Speichern ohne Antwort und unveränderte Wiederholung.

Originale Testdateien im PR: `project_business_tabs_navigation_test.dart`,
`project_unsaved_return_test.dart`, `business_home_navigation_audit_test.dart`,
`feature_actions_navigation_test.dart`, `financial_dialog_navigation_test.dart`;
aus PR 7 zusätzlich `workspace_return_navigation_test.dart`. Diese Dateien sind
im geprüften lokalen Stand noch nicht vorhanden. Es wurden hier keine neuen
Produkttests gestartet und keine alten Testzahlen als aktuelle Abnahme übernommen.

## Neuer Kandidat für Windows und iPhone

Ohne Workflowänderung passt etwa `codex/testupdate-0.7-projects-20261104`:
Windows-Release und iOS-Simulator laufen über `checks.yml`; das vorhandene
Branchpräfix erlaubt zusätzlich den unsignierten iPhone-Release. Der Namensanteil
„0.7“ ist nur die bestehende Triggerregel. Ein reiner Doku-Push reicht für den
iPhone-Pfadfilter nicht; ein konkreter App-/Backend-Kandidat erfüllt ihn.
Der [gesonderte CI-Nachweis](evidence/project-release-readiness-2026-11-04/ci-branch-route.json)
enthält genaue Bedingungen und nicht ausgeführte Befehlsbeispiele.

Auf diesem neuen Branch ist signiertes IPA/TestFlight weiterhin gesperrt.
Unverändert führt der Weg nach bestandenen Prüfungen über den bestehenden
Releasebranch mit manuellem Upload-Flag. Soll der neue Kandidatenbranch selbst
signieren, wäre eine separat geprüfte **exakte** zusätzliche Branchbedingung
im Signierjob erforderlich; manuelle Auslösung, Upload-Flag und Abhängigkeit vom
grünen unsignierten Job bleiben erhalten. Keine solche Änderung wurde gemacht.

Normale Connectorwerkzeuge für die spätere Bereitstellung sind `create_blob`,
`create_tree`, `create_commit`, `create_branch` und `update_ref` mit erwarteter
alter SHA. Damit lässt sich ein neuer Branch bearbeiten, ohne den Standardbranch
zu verändern. Der lokale Kandidat fehlt derzeit remote: ein neuer API-Commit kann
eine andere SHA erhalten. Dann vollständige Quellbaum-/Dateihashgleichheit prüfen
und CI am tatsächlichen Remote-Commit bewerten. Besondere Schreibrechte für
Workflowdateien sind noch nicht nachgewiesen. Automatisch entstandene Push-Läufe
beobachten; bei fehlendem Lauf bleibt normaler manueller Dispatch über GitHub-UI
oder funktionierendes `gh`. Das Wiederholen eines alten Jobs baut keinen neuen
Kandidaten. Es wurde weder ein Remote-Objekt noch ein Branch oder Lauf erzeugt.
