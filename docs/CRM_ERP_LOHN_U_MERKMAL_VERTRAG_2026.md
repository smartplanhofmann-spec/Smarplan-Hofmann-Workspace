# U-Merkmal des Lohnkontos – additive Jahresnachweise 2026

Stand03.11.2026. Die V5-Rechnung bewahrt bereits tatsächliche unbezahlte Tage. Das gesetzliche U-Merkmal ist davon getrennt: Der bisherige Blocker `unpaid_statutory_marker_requires_evidence` bleibt bestehen, bis der folgende eigene Nachweis vollständig gebunden und geprüft ist. Der neue Jahresnachweis ändert weder alte Lohnrechnungen noch deren Regel-/Quellenhashes.

## Tatsächlich eingesehene amtliche Quellen

| Quelle | Abruf und Aussage |
|---|---|
| [§41Abs1 EStG](https://www.gesetze-im-internet.de/estg/__41.html) | Amtlicher Suchindex am03.11.2026, Sätze4/5; direkter Vollabruf timeout. Satz5 verlangt fortbestehendes Dienstverhältnis und mindestens fünf aufeinanderfolgende Arbeitstage mit im Wesentlichen weggefallenem Arbeitslohnanspruch. Satz4 nennt gesondert aufzuzeichnende Ersatz-/Zuschussleistungen, die abzugrenzen sind. |
| [§4Abs2Nr2 LStDV](https://www.gesetze-im-internet.de/lstdv/__4.html) | Volltext tatsächlich geöffnet, Zeilen24–34: U ist bei jeder einschlägigen Lohnabrechnung aufzuzeichnen. Absatz2a enthält zusätzlich den gesetzlichen digitalen Prüfexport; dieser wird durch eine interne JSON-Datei nicht als erfüllt behauptet. |
| [LStH2026, Anhang23I](https://lsth.bundesfinanzministerium.de/lsth/2026/B-Anhaenge/Anhang-23/I/inhalt.html) | Amtlicher Suchindex am03.11.2026, Ausfüllhinweise Nr2: Bescheinigt wird die Anzahl der Unterbrechungszeiträume, nicht die Anzahl einzelner Tage oder Monatszeilen. Vollabrufe der BMF-Seiten lieferten503. |
| [LStH2026, §41](https://lsth.bundesfinanzministerium.de/lsth/2026/A-Einkommensteuergesetz/VI-Steuererhebung-36-47/2-Steuerabzug-vom-Arbeitslohn-Lohnsteuer-38-42g/Paragraf-41/inhalt.html) | Amtlicher Suchindex bestätigt die Abgrenzung unter anderem von Kurzarbeitergeld, Arbeitgeberzuschuss zum Mutterschaftsgeld und IfSG-Entschädigung. Die aktuelle gesetzliche Liste einschließlich Qualifizierungsgeld ist maßgeblich; ältere Richtlinienbeispiele ersetzen sie nicht. |

Der Workspace-HTTPS-Proxy verweigerte zunächst den amtlichen Direktabruf. Der anschließend verfügbare autorisierte Web-Connector lieferte die oben bezeichneten echten amtlichen Inhalte. Es wird kein erfolgreicher BMF-Vollabruf behauptet.

## Entscheidung und Grenzen

Fünf unbezahlte Kalendertage reichen nicht. Tatsächliche vertragliche Arbeitstage stammen aus gebundenen P2-Arbeitsplänen, niemals aus fehlenden Projektstunden. Eine arbeitsfreie Unterbrechung zwischen qualifizierenden Arbeitstagen darf nicht automatisch einen neuen Zeitraum erzeugen. Ein tatsächlicher bezahlter Arbeitstag, das belegte Ende des Dienstverhältnisses oder ein einschlägiger Ausnahmezeitraum beendet die betrachtete Folge. Monatsgrenzen erzeugen keinen zweiten U-Eintrag. Für das Jahreskonto wird ein zusammenhängender geprüfter Jahreszeitraum verwendet; ungeklärte Vorjahresrandfälle bleiben ausdrücklich offen.

Der erste freizugebende Zweig umfasst den vollständig weggefallenen Entgeltanspruch. „Im Wesentlichen“ beziehungsweise teilweise verbliebene Bar-/Sachansprüche benötigen eine eigene belegte Beurteilung; hierfür wird kein willkürlicher Prozentgrenzwert erfunden. Pauschal besteuerte Minijobs, rückwirkende Ersatzleistungsänderungen und jahresübergreifende Randfälle erhalten vor Freigabe ihre eigenen Nachweise. Die SV-Monatsfrist aus P4 ist keine U-Frist.

## Quellen- und Befehlsvertrag

Vorgesehen ist ein eigener privater Jahresnachweis `wage_interruption_assessment`, Schlüssel Person/Jahr, mit eigener Regel `de_2026_wage_interruptions_v1` und Quellenvertrag1. Er bindet konkrete aktuelle Laufrevisionen, alle einschlägigen P4-Unterbrechungs-/Krankheitsfakten, Beschäftigungsepisoden, vollständige Tagesarbeitspläne und geschützte Originale. Die neue Quelle enthält einen tatsächlichen `assessment_through`-Tag. Fehlende Randtage oder unbekannte Leistungsfälle werden als unbekannt behandelt.

Jede Tagesentscheidung unterscheidet vertraglichen Arbeitstag, tatsächlichen Anspruchsverlust und leistungsbezogene Ausnahme. Bekannte Nullen sind ausdrücklich bestätigt. Alle gesetzlichen Satz4-Leistungsarten müssen als nicht vorhanden beziehungsweise durch Zeitraum und Original belegt sein; eine leere, ungeprüfte Liste genügt nicht. Bereits im wirklichen Lauf enthaltene Ansprüche müssen zur neuen Beurteilung passen. Eine freie U-Anzahl wird nicht angenommen.

Geplante Routen: `GET /payroll/wage-interruptions/sources?employee_id=…&year=2026`, `GET/POST /payroll/wage-interruptions`, `POST /payroll/wage-interruptions/preview`, `GET /payroll/wage-interruptions/{id}` und `/{id}/history`. Das ist ein Entwurf, keine Aussage bereits vorhandener Registrierung. Vorschau liefert vollständige Quellen, Regel-/Planhash, abgeleitete Zeiträume, Anzahl, Abdeckung und Blocker. Annahme braucht frisches globales `personnel.read` plus `personnel.approve`, aktuelle Originalfassungen und Online/MFA. Originalauftrag und exakte Annahmequittung bleiben privat; Korrektur/Void/replay folgen dem bewährten append-only Vertrag.

## Integration und Abnahme

Das aktuelle Lohnkonto bindet einen verifizierten passenden Jahresnachweis zusätzlich zu den tatsächlichen Lohnläufen. Fehlende, veraltete oder unvollständige Quellen lassen den U-Blocker bestehen. Eine bestätigte Anzahl0 ist von „unbekannt“ verschieden. PDF/CSV/JSON erhalten Zahl und datierte Zeiträume mit ihrem Nachweis, die eigene Mitarbeiterprojektion ausschließlich die erforderliche Zusammenfassung. Keine amtliche Übermittlung oder DLS-Zulassung wird daraus abgeleitet.

Prüffälle: vier gegenüber fünf Arbeitstagen; Wochenende; Feiertag nach tatsächlichem Anspruch; Teilzeit mit wenigen Wochenarbeitstagen; Monatsgrenze nur einmal; echte Wiederaufnahme und zwei Folgen; Ende/Wiedereintritt; fünfter Tag erst im Folgejahr; Satz4-Ausnahme; unbekannter Teilanspruch; Widerspruch zur P4-Quelle; aktuelle Laufkorrektur und unverändertes altes Konto; frischer Rechteentzug vor Erstannahme/Replay; vollständiger PostgreSQL-Neustart/Restore.
