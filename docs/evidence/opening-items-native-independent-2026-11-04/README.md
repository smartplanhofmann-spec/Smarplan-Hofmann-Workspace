# Unabhängige native Altpostenprüfung

Abgeschlossen04.11.2026 im isolierten Altpostenbaum. **25 eigene Fälle und die
23 Ownerfälle bestehen gemeinsam:48/48**, einschließlich der tatsächlichen
lokalen HTTP-/MFA-Strecke bei390px. Die eigene Testdatei hat0 Analysebefunde.
Dies ist eine gezielte native Abnahme, keine Vollständigkeitsbehauptung für das
gesamte CRM/ERP. Keine Produktdatei, Commit oder PostgreSQL-Instanz durch den
Reviewer verändert; Produktfixes stammen ausschließlich vom Clientowner.

## Tatsächlich gefundene und behobene Fehler

Der erste Lauf gegen die exakt geprüften fünf Runtimehashes des ursprünglichen
Ownerfreezes hatte4 erfolgreiche und2 fehlgeschlagene Fälle. Rotlog, damalige
eigene Testdatei und beide betroffenen neuen Produktdateien sind unter `before-*`
erhalten; `before-manifest.json` bindet sämtliche damaligen Runtimehashes.

1. **Fremdes Geldkonto trotz originaler Zahlungsquittung:** Eine echte
   `receivable_prior_parts`-Quelle wurde nur in
   `cash_movements[0].account.id` geändert; ihr abgeleiteter Sourcehash wurde neu
   berechnet. Die tatsächlich übergebene unveränderte Zahlungsquittung enthielt
   weiterhin das ursprüngliche Geldkonto. `openItemSource(..., payment:...)`
   akzeptierte dennoch das fremde Konto.
2. **Geänderter früherer Vorsteuer-Ausübungstag in der tatsächlichen Seite:**
   Originaler Lieferantenaltposten und Zahlungsquittung blieben unverändert.
   Nur `source.prior_input_vat.deducted_on` wurde von10.12.2025 auf11.12.2025
   geändert und der abgeleitete Sourcehash neu berechnet. Die Seite zeigte
   trotzdem die als originalgebunden bezeichnete Geld-/EÜR-Quelle.

Der enge Ownerfix vergleicht das vollständige ursprüngliche Geldkonto und bindet
Zahlung sowie Altposten über die tatsächlich referenzierten unveränderlichen
Historienfassungen. Der heutige Itemkopf wird nicht ersatzweise verwendet.
Dasselbe Verfahren schützt den EÜR-Quellenkatalog; Kontextwechsel werden
zwischen den zusätzlichen lesenden Historienabfragen geprüft.

Beide ursprünglichen negativen Sachverhalte wurden unverändert wiederholt.
Der VATtest verlangt nun zusätzlich die konkrete Meldung über die veränderte
ursprüngliche Rechnung/Vorsteuer, sodass ein falscher Test-Historiestub den Fall
nicht versehentlich erfüllt. Positive eigene Fälle prüfen beide Zahlungsrichtungen
und den gültigen alten Lieferantenbezug mit ausdrücklich0,00EUR neuem
Vorsteuerabzug. Der tatsächliche Owner-HTTP-Fall bestätigt zusätzlich: Ein später
erneut angenommener Itemkopf macht den weiter korrekt gebundenen früheren
Zahlungs-/Vorsteuerbezug nicht ungültig.

## Eigene Gegenfälle und Aussagegrenzen

Die eigene Datei `app/test/business_accounting_open_items_independent_review_test.dart`
enthält25 Fälle. Sie verwendet die unveränderte echte Backend-UI-Fixture und
einen echten `BusinessSession`. Gehaltene Antworten werden kontrolliert zugestellt;
der ursprüngliche bezahlte Journalpräfix für den Voidfall wird ausschließlich
aus den tatsächlichen Fixtureevents rekonstruiert und separat validiert.

- Historische Centaufteilung und alter Vorsteuer-Ausübungstag werden auch bei
  neu berechnetem Vorschauhash geprüft; die beiden beschriebenen Quellfehler
  sowie positive Konten-/Vorsteuerbindungen sind abgedeckt.
- Sechs tatsächliche Voidvorschauen werden über Read-/Write-/Modul-/Generation-/
  Hintergrund-/Elternsessionwechsel gehalten. Keine späte Vorschau erscheint,
  kein ungeprüfter Folge-POST entsteht.
- Sechs echte Void-ACK-/Fehlerfälle prüfen Hintergrund, Session und Schreibentzug.
  Alte Antworten bleiben bei ihrer ursprünglichen Session; ein neuer privater
  Entwurf bleibt erhalten und der abgelöste Sessionlistener beeinflusst ihn nicht.
  Ungewisse Fehler behalten ihren ursprünglichen Pendingauftrag.
- Drei gehaltene Originaldownloads dürfen nach Read-/Hintergrund-/Sessionwechsel
  keine Datei exportieren. Gleich große veränderte Bytes scheitern am Originalhash.
- Leere Dateien und5MiB+1Byte werden vor einem Upload abgewiesen. Ein nach
  Schreibentzug zurückkehrender Dateidialog erzeugt weder POST noch Pendingauftrag.

Die tatsächliche kombinierte HTTP-Strecke bestätigt zusätzlich Originalupload,
Altübernahme und EÜR nach jeweils verlorener Serverantwort, unveränderte Wiederholung,
beide Rechnungsrichtungen, zwei getrennte Cent-Restzahlungen, Kontoberichtigung,
Gegenbuchung, Zahlungskorrektur/Aufhebung, alte Vorsteuer ohne zweiten Anspruch,
belegte Liquidität, Originaldownload und echten Rechteentzug. Es gab keine
Produktivkontakte oder externen Zahlungen.

Vier anfängliche zusätzliche Downloadtestfehler lagen ausschließlich im eigenen
Scrollhelper: Ein lazy aufgebauter Finder wurde zu früh mit `.first` beziehungsweise
als mehrdeutiger Finder aufgelöst. Der Helper wartet jetzt auf vorhandene Elemente
und wählt erst dann das erste. Diese Testkorrektur erforderte keinen Produktfix.
Sie ist von den zwei konservierten echten Source-Bindungsfehlern getrennt.

## Endstand und Nachweise

- `own-final.txt`:25/25,11s.
- `combined-final.txt`:48/48,1min23s, einschließlich echter lokaler HTTP-Strecke.
- `analysis.txt`:0 Befunde,5,2s.
- Ursprünglicher Ownerhandoff bleibt unverändert:
  `docs/evidence/opening-items-native-2026-11-04/manifest.json`, SHA256
  `f192a1a870505b3c4497e343df6e0c06f3e81f684466a0e703b5729b421dfed9`.
- Tatsächlich final geprüfter additiver Ownerhandoff:
  `docs/evidence/opening-items-native-review-fix-2026-11-04/manifest.json`, SHA256
  `5246bc7b4d10194fcfeec5484a54bf131afb1639a5cf64b217fb94ab162d6c69`.

Das eigene `manifest.json` enthält exakte Runtime-, Test-, Fixture- und
Artefakthashes. Die frühere breite106er-Regression und der42er-Fixlauf sind
Ownernachweise; sie werden hier nicht als unabhängig erneut vollständig
ausgeführt ausgegeben. Alle zuvor eingefrorenen SV-/Steuerartefakte blieben
unverändert. Es bestehen keine offenen bestätigten Befunde aus diesem Review.
