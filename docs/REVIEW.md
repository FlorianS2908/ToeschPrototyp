# Double Review · 25.09.2026

## Prüfstand und Verfahren

Scope und Kriterien: [PLAN.md](PLAN.md), A01–A15. Ausgangsstand: leeres Repository.
Branch: `feature/hotelservice-prototype`. Zwei zeitlich und methodisch getrennte
Selbstreviews; keine Behauptung zweier unabhängiger menschlicher Prüfer.

Prüfstand 1: SHA-256 des sortierten Dateimanifests
`e1968a93f12598ab369698aaa90af7deaa1bda798cddd5aafd7d234486f96bb2`.
Der Manifest-Snapshot umfasst Anwendung, Tests, Startdateien und Dokumentation;
Umgebung, Laufzeitdaten und generierte Prüfbilder sind ausgeschlossen.
Dateimanifeste: [Stufe 1](review-snapshots/stage-1.json) und
[Stufe 2](review-snapshots/stage-2.json). Sie halten Dateihashes der jeweiligen
Prüfstände fest; die abschließende Git-Revision enthält den korrigierten Stand.

## 1. Anforderungsreview

Methode: Kriterien gegen API-Tests, manuell gelesenen Code, echten Chromium-Ablauf,
Startskript und Dokumentation prüfen. Erstbefunde vor Korrekturen erfasst.
Erster Python-Lauf: 34 Tests bestanden. Browserablauf erreichte den echten
Prozessneustart und reproduzierte dort R1-01.

| ID | Prio | Evidenz / Auswirkung | Gewählte Korrektur | Status |
|---|---|---|---|---|
| R1-01 | P1 | `browser_smoke.cjs`: erster Durchlauf erfolgreich, Wiederstart auf demselben Port scheitert unter Linux mit `Address already in use`. Socket in `run.py` setzte keine Wiederverwendungsoption. | POSIX: `SO_REUSEADDR`; Windows: `SO_EXCLUSIVEADDRUSE`. Port vor Start halten, fremden belegten Port weiterhin ablehnen. | Geschlossen: Browserneustart + belegter-Port-Test bestanden |
| R1-02 | P2 | Austauschadapter mit negativer Menge als Dict liefert beim Interpretationsendpunkt HTTP 500; zugesagte Vertragsvalidierung fehlte. | Pydantic-Validierung direkt an der Adaptergrenze, definierter HTTP-502-Fehler, leeres Ergebnis mit konkreter Rückfrage. | Geschlossen: drei Adaptertests in `test_boundaries.py` |
| R1-03 | P3 | Optionaler Chromium-Test verwendet eine `waitForFunction`-Implementierung mit eval; strikte CSP blockiert die Testhilfe. Anwendung selbst arbeitet. | Testhilfe fragt Locatorzustände ab; Schutzrichtlinie der Anwendung unverändert. | Geschlossen: vollständiger Chromium-Ablauf bestanden |

Abwägung: Portwechsel würde den Fehler nur umgehen; plattformspezifische
Socketoptionen beheben den Neustart. Adapterfehler sollen früh kontrolliert
abgewiesen werden, statt fehlerhafte Ergebnisse weiterzureichen. Die CSP wird
nicht für Testwerkzeuge gelockert.

Regression nach erster Korrekturstufe: **43 Python-Tests bestanden**, echter
Chromium-Durchlauf einschließlich Prozessneustart bestanden, keine JavaScriptfehler.

## 2. Analytisches Review

Prüfstand 2, nach erster Korrekturstufe: Manifest-SHA-256
`5d636c04a2f74da203d4d12c092ed043c047568390116c91ffb092a999d61168`.

Methode: Commit-Grenzen und Absturzfenster schrittweise durchgehen; konkurrierende
Rückmeldungen deterministisch einschieben; gleiche Statusaktionen mehrfach
parallel ausführen; Datenbank-Snapshot und Schichtengrenzen lesen. Zusätzlich
Wartbarkeit, Dupletten, Browser-Wiederaufnahme und Start-/Testkopplung prüfen.
Das wiederholt nicht lediglich die Gastabläufe aus Review 1.

| ID | Prio | Evidenz / Auswirkung | Analyse und Korrekturplan | Status |
|---|---|---|---|---|
| R2-01 | P2 | Zweimal derselbe Aufruf von `advance` ergab erst `in_progress`, dann `completed`; Körper wurde nicht als Zielzustand ausgewertet. | Expliziter validierter Zielstatus; monotone, idempotente Übergänge im Empfänger, UI sendet diesen Zielstatus. Sprung direkt zu erledigt ablehnen. | Geschlossen: 12 parallele identische Aufrufe bleiben in Bearbeitung; UI-Bearbeitung/Abschluss geprüft |
| R2-02 | P2 | Reproduziert: während Lookup wird Abschluss bestätigt; danach trifft früherer Verbindungsfehler ein. `completed` erhielt fälschlich `last_error`. | Fehler mit dem Zustand beim gestarteten Versuch verknüpfen; Rangvergleich verwirft inzwischen veraltete Fehler. | Geschlossen: verspäteter Fehler und verspätete positive Rückmeldung können Abschluss nicht zurückstufen/markieren |
| R2-03 | P2 | `orders()` las Auftragszeile und Ereignisse in separaten Autocommit-Snapshots. Dazwischen konnte ein neuer Status sichtbar werden. | Expliziter SQLite-Lesesnapshot über die gesamte Antwort; WAL lässt parallele Schreiber zu. | Geschlossen: deterministisch eingeschobenes Update liefert konsistent alte Zeile + alten Verlauf, nächste Abfrage sieht Fortschritt |
| R2-04 | P3 | Erste CSS-Version war überwiegend in einer Zeile; schlecht wartbar und schwer punktgenau zu reviewen. | HTML, CSS, JavaScript und Browsertest mit Prettier formatieren; keine Buildpflicht für Anwender. | Geschlossen: lesbare Dateien, Syntax-/Formatkontrolle bestanden |

Abwägung: Browserbuttons zu sperren allein schützt keine parallelen API-Aufrufe;
der Empfänger muss die Statusaktion idempotent umsetzen. Fehlertexte pauschal zu
unterdrücken würde echte Ausfälle verbergen; stattdessen wird nur ein veralteter
Versuch verworfen. Alle Abfragen per Schreibsperre zu serialisieren wäre unnötig;
ein Lesesnapshot genügt für konsistente Zeile und Historie.

Zusätzliche Integritätsnachweise: geänderter Inhalt unter derselben Empfängerreferenz
wird abgewiesen; Prozessfehler nach lokalem Commit sowie nach Empfängercommit
lassen sich mit derselben Referenz ohne Doppelannahme wiederaufnehmen. Laufzeitdaten
und Testdaten bleiben getrennt. Keine automatische Retry-Schleife oder externe Wirkung.

Regression nach zweiter Korrekturstufe: **51 Python-Tests bestanden**; vollständiger
Chromium-Ablauf mit Statusfortschaltung und echtem Neustart bestanden, keine JS-Fehler.

## Verbleibende Grenzen

- **L01 / P2, Prüfgrenze:** Kein Windows-Rechner in dieser Umgebung. `Start.cmd`
  statisch geprüft; enthaltene Python-/pip-/pytest-Schritte und `run.py` unter Linux
  ausgeführt. Nativer Windows-Doppelklick ist noch vom Anwender zu bestätigen.
- **L02 / P3, akzeptiert:** Starlette gibt für seinen weiterhin funktionierenden
  TestClient mit `httpx` einen Deprecation-Hinweis aus. 51 Tests bestanden; betrifft
  das Testwerkzeug, nicht den Serverbetrieb. Ein künftiges Dependency-Update kann
  den Wechsel auf `httpx2` vornehmen.
- Begrenzte Grammatik, simulierte Schnittstellen, lokale Rollenfreiheit und manueller
  Wiederanlauf sind vereinbarte Produktgrenzen, keine verschwiegenen Implementierungen.

## Schlussreview

Das Schlussgate prüft den korrigierten Stand schreibgeschützt gegen beide Register
und die ursprünglichen Kriterien. Nachweise:

| Kriterien | Nachweis | Ergebnis |
|---|---|---|
| A01–A04 | Python-Parser-/API-Tests, Desktop-/Mobilansicht, Chromium-Bestätigung/Rückfrage | Bestanden |
| A05–A08 | Parallele Schlüsselwiederholungen, geänderter Inhalt, offene Artikel, Zusatzbestellung, unabhängige Empfängerannahme | Bestanden |
| A09–A12 | Antwortverlust, Teilfehler, beide Absturzfenster, echter Neustart, monotone Statusmeldungen und Lesesnapshot | Bestanden |
| A13 | CMD statisch geprüft; Pakete, Tests, Portbelegung und `run.py` ausgeführt | Unter Linux bestanden; nativer Windows-Check offen (L01) |
| A14 | README, Plan, Architektur, Vorführskript, zwei Befundregister und Tests vorhanden | Bestanden |
| A15 | Abschließender Commit/Push auf Feature-Branch; Remote-SHA gesondert vergleichen | Auslieferung folgt dem bestandenen technischen Gate |

Prüfbefehle: `python -m pytest -q` (**51 bestanden**), `python -m ruff check .`,
`python -m ruff format --check .`, `python -m pip check`, JavaScript-Syntaxprüfung
und optionaler `node tests/browser_smoke.cjs` (Chromium, Desktop 1440 px / mobil
390 px, kein horizontaler Überlauf). Versionsabgleich mit den Requirements erfolgreich.

**Technisches Schlussurteil: Go für die lokale Demo und den Repository-Push.**
Keine offenen P0/P1-Befunde; alle bestätigten Produktfehler im Scope geschlossen.
L01 und L02 bleiben transparent. Dieses technische Urteil ersetzt keine separate
formale Nutzerabnahme und behauptet keinen bereits durchgeführten Windows-Test.
Branch/Commit und Remote-Verifikation werden bei der Auslieferung mitgeteilt.
