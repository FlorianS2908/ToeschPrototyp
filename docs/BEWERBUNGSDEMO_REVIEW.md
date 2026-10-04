# Bewerbungsdemo – Analyse und Review

Stand: 04.10.2026. Scope: lokaler, synthetischer Demonstrationsablauf; keine Produktivintegration.
Branch: `codex/bewerbungsdemo-2026-10-04`. Ausgangsstand ist vor Änderungen gesichert.

## 1. Analyse und schreibgeschütztes Planreview

| ID | Priorität | Belegter Befund | Korrektur | Status |
|---|---|---|---|---|
| S-R1 | P2 | Reset benötigt manuelles Umbenennen des Datenordners | Separater Demo-Start mit Sicherung/Reset ausschließlich des Demo-Datenpfads. | behoben |
| S-R2 | P2 | Kein kontinuierlicher plattformübergreifender Nachweis | Bestehende Tests, Browser-Smoke und Windows-CI für den isolierten Branch. | behoben |

Planreview: Der Umfang ist für eine Bewerbungsdemo ausreichend. Bestehende Fachlogik bleibt führend; kein neues Vollprodukt. Die Tests unterscheiden lokale/automatisierte Nachweise von noch ausstehenden nativen Windows- und Live-API-Nachweisen.

## 2. Implementierung

Neuer isolierter Sitzungsstarter mit Start_Demo.cmd; jede Vorführung erhält einen eigenen Ordner. Frühere Sitzungen und Arbeitsdaten bleiben erhalten. Windows-/Linux-CI ergänzt.

## 3. Implementierungsreview und direkte Korrekturen

| ID | Prio | Befund | Korrektur / Nachweis |
|---|---|---|---|
| S-I1 | P2 | Reset darf vorhandene Daten nicht löschen | Neue Sitzung statt Löschen; Regressionstest erhält Arbeits- und Altdaten. |

Die aufgeführten Befunde wurden in diesem Feature-Branch korrigiert. Keine offenen P0/P1-Befunde im vereinbarten lokalen Demo-Ablauf nach aktuellem Review.

## 4. Testlauf und Restgrenzen

52 Pytests und Ruff bestanden. Echter Chromium-Lauf: Bestätigung, Replay, semantische Dublette, Antwortverlust, Teilausfall, Wiederanlauf, Statuswechsel, Mobilansicht und Prozessneustart bestanden.

Windows-CI wird auf dem Feature-Branch geprüft. Hotel-/PMS-Dienste sind lokale Simulatoren.

Umgebung: Linux, Python 3.12.14, Node 24.19.0, Chromium 153.0.8010.0.
Teststand: 04.10.2026. Keine produktiven Zugangsdaten oder externen Aktionen im Demo-Lauf.

## 5. Vorführung

Start und kurzer Ablauf stehen im README. Für eine neue Vorführung zurücksetzen beziehungsweise neu starten. GitHub-Sichtbarkeit und Bewerbungsversand bleiben getrennte Entscheidungen.
