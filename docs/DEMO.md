# Fünf Minuten im Fachgespräch

## Vorbereitung

`Start.cmd` vor dem Gespräch einmal vollständig durchlaufen lassen. Internet wird
für die erste Paketinstallation gebraucht. Danach lokalen Start und Beispielsatz
proben. Für einen frischen Stand Server beenden, `data` umbenennen, Browser-Tab
schließen und neu starten. Ausreichend Zeit für den ersten Paketdownload einplanen.

## 0:00–0:40 – Problem und Grenzen

„Die Arbeitsprobe verarbeitet bestätigte Hotelservice-Wünsche. Zwei Handtücher
gehen an Housekeeping, eine Pizza an die Küche. Die Schnittstellen und die
Textauswertung sind hier Simulatoren. Im Mittelpunkt steht die zuverlässige
Auftragsverarbeitung, auch wenn eine Rückmeldung fehlt.“

## 0:40–1:30 – Erfolgreiche Bestellung

Zimmer 101 → Beispiel **2 Handtücher + 1 Pizza** → **Wunsch prüfen** → bestätigen.
Beide Karten erklären: Menge, Empfänger, Status und Verlauf. Eine Empfangsbestätigung
heißt „Übermittelt“, noch nicht „Erledigt“. Bei Housekeeping über die Simulator-
Schaltfläche die Bearbeitung starten, aber den Auftrag zunächst offen lassen.

## 1:30–2:20 – Zwei unterschiedliche Wiederholungen

Unten **Letzte Bestellung erneut senden**. Anzahl bleibt 2. „Das ist eine technische
Wiederholung mit demselben Schlüssel; das Backend gibt die vorhandene Anfrage zurück.“

Oben erneut **2 Handtücher** prüfen. „Ein neuer Wunsch mit neuem Schlüssel ist ein
anderer Fall. Hier prüfen wir offene Artikel zum Aufenthalt und lassen bewusst
zwischen Status ansehen und Zusatzbestellung entscheiden.“ Bei Bedarf den Haken
setzen und die zusätzlichen zwei Handtücher anlegen; die ursprünglichen bleiben bestehen.

## 2:20–3:15 – Auftrag angenommen, Antwort verloren

Housekeeping auf **Nächste Annahme: Antwort verlieren** setzen. Zimmer 204 →
**2 Handtücher** → prüfen → bestätigen. Karte: **Rückmeldung unklar**. Kennzahl
„Beim Empfänger“ ist trotzdem gestiegen, denn diese Demoanzeige kann die simulierte
Empfängerdatenbank direkt ansehen. Der Koordinator hat noch keine Bestätigung.

**Abgleichen / erneut übermitteln** an der Karte: jetzt „Übermittelt“, weiterhin
nur eine Empfängerannahme. „Wir verwenden dieselbe Referenz und prüfen zuerst den
vorhandenen Auftrag. Bei erneutem Senden schützt auch der Empfänger vor Duplikaten.“

## 3:15–4:00 – Ein Dienst fällt aus

Küche auf **Dienst nicht erreichbar**. Zimmer 305 → gemischtes Beispiel → bestätigen.
Housekeeping ist übermittelt, Küche bleibt gespeichert mit Fehlerhinweis. Küche auf
**Normal erreichbar**, Küchenauftrag **Abgleichen / erneut übermitteln**. Danach
die Bearbeitungsschritte simulieren. Keine Stornierung des erfolgreichen Handtuchauftrags.

## 4:00–5:00 – Code einordnen

- `service.py`, `save`: Inhaltshash, Transaktion, Idempotenz und fachliche Prüfung.
- `service.py`, `reconcile`: unklaren Zustand vor Übergabe speichern und Status abgleichen.
- `adapters.py`, `submit`: eigene Empfängertransaktion, Referenz und Antwortverlust nach Commit.
- `interpreter.py`, `Interpreter`: austauschbarer Anschluss für ein LLM.
- `tests/`: Parallelaufrufe, Antwortverlust, Neustart und ungültige Eingaben.

„Das Modell dürfte später strukturierte Vorschläge erzeugen. Fachliche Validierung,
Bestätigung, Berechtigungen und Schutz vor Doppelwirkungen bleiben Anwendungscode.“

Bei Zeitreserve: Server mit Strg+C beenden, `Start.cmd` erneut öffnen und erhaltene
Aufträge zeigen. Der Testlauf verändert den Demostand nicht.

## Gute Anschlussfragen

- Welche PMS- und operativen Systeme werden angebunden?
- Bieten die Empfänger Idempotenzschlüssel und Statusabfragen per Referenz?
- Wie wird ein Gast sicher einem aktiven Aufenthalt zugeordnet?
- Welche Vorgänge müssen Menschen bestätigen?
- Welche Anforderungen gibt es an Datenschutz, Monitoring und Eskalation?
