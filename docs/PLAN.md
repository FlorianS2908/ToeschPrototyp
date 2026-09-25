# Analyse, Plan und Planreview

Auftrag vom 25.09.2026: lokale Hotelservice-Arbeitsprobe für das Fachgespräch,
Python/FastAPI/SQLite, Windows-Start einschließlich Installation und Tests.
Ziel: FlorianS2908/ToeschPrototyp, Branch `feature/hotelservice-prototype`, Modus 3.
Ausgangslage: Repository ohne Commits oder Dateien. Kein bestehender Code zu migrieren.

## Scope und Kriterien (vor dem Double Review eingefroren)

| ID | Anforderung / Nachweis |
|---|---|
| A01 | Gast wählt Demoaufenthalt, gibt Wunsch ein und bestätigt Positionen. |
| A02 | Handtücher → Housekeeping; Pizza Margherita → Küche; getrennte Statusverläufe. |
| A03 | Unbekannte Texte oder fehlende Mengen erzeugen Rückfragen und keine Bestellung. |
| A04 | Regelparser, PMS und Empfänger sind sichtbar als Simulatoren gekennzeichnet. |
| A05 | Gleicher Schlüssel + gleicher Inhalt erzeugt unter Parallelzugriff nur einen Auftrag. |
| A06 | Gleicher Schlüssel + anderer Inhalt wird mit HTTP 409 abgelehnt. |
| A07 | Passende offene Artikel werden auch unter Parallelzugriff erkannt; Zusatzbestellung explizit. |
| A08 | Empfänger deduplizieren unabhängig vom Koordinator mit eigener persistenter Speicherung. |
| A09 | Antwortverlust bleibt unklar; Abgleich benutzt dieselbe Auftragsreferenz. |
| A10 | Dienstausfall und gemischte Ergebnisse sind getrennt nachvollziehbar. |
| A11 | Neustart erhält Aufträge, Ereignisse, Empfängerannahmen und Fehlermodi. |
| A12 | Zustände gespeichert, unklar, übermittelt, in Bearbeitung, erledigt werden ehrlich angezeigt. |
| A13 | CMD prüft Python, installiert Abhängigkeiten, prüft Setup und Tests, startet und öffnet Browser. |
| A14 | README, Architektur, Vorführskript, Tests und getrennte Reviewregister sind vorhanden. |
| A15 | Geprüfter Stand wird auf GitHub gesichert und am Remote verifiziert. |

## Entscheidungen und Planreview

| ID | Risiko im ursprünglichen Plan | Entscheidung |
|---|---|---|
| P01 | Nur lokale Idempotenz verhindert keine doppelte externe Ausführung. | Eigene Empfänger-Datenbank, einzigartige Referenz + Inhaltshash, transaktionale Annahme. |
| P02 | Prozessabbruch nach Empfängerannahme könnte fälschlich als Nichtannahme gelten. | Vor dem Aufruf „unklar“ speichern; anschließend nur bestätigte Zustände übernehmen. |
| P03 | Semantische Duplikatprüfung nur in der Vorschau hat ein Zeitfenster für Parallelaufrufe. | Prüfung und Anlegen gemeinsam in `BEGIN IMMEDIATE`; Zusatzbestellung als explizites Flag. |
| P04 | Parser könnte unbekannte Teile still ignorieren. | Vollständige begrenzte Grammatik; jeder unbekannte Teil blockiert die gesamte Bestätigung. |
| P05 | Lokale Demo könnte mit produktiver Schnittstelle verwechselt werden. | Sichtbare Simulationskennzeichnung und dokumentierte Adapter-Ports. |
| P06 | Ein Browser-Neuladen könnte nach Antwortverlust einen neuen Schlüssel erzeugen. | Noch nicht quittierte Sendung vor dem Aufruf in sessionStorage sichern und wiederverwenden. |

Planreview: ausführbar mit diesen Konkretisierungen. Umfang bewusst ohne Anmeldung,
Zahlungen, echte PMS-/Küchen-APIs, echtes LLM oder produktives Hosting. Alle Gäste sind fiktiv.
Lokaler Einzelplatzbetrieb; keine Behauptung verteilter Exactly-once-Garantien.

## Umsetzung und Prüfreihenfolge

1. Validierte Verträge, persistente Koordination und Empfängeradapter.
2. Wiederholungen, Fehlersteuerung und Abgleich.
3. Browseroberfläche mit Bestätigung, Rückfragen, Duplikatdialog und Betriebsübersicht.
4. Tests, CMD-Start, README und Vorführablauf.
5. Anforderungsreview → bestätigte Fehler beheben → Regression.
6. Analytisches Review (Integrität, Parallelität, Interaktionen, Modularität) → Korrekturen.
7. Schreibgeschütztes Schlussreview; erst danach Git-Commit/Push und Remote-Verifikation.

Kein Merge und kein Deployment Teil dieses Auftrags. Das leere Repository erhält seinen
ersten Branch durch den ausdrücklich beauftragten Push.
