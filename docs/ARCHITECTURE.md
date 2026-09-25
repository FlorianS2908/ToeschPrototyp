# Architektur und Zuverlässigkeitsgrenzen

## Datenfluss

Browser → FastAPI → validierter Vertrag → HotelService → Empfänger-Port.
Interpretation und Vorschau speichern noch keine Bestellung. Nach Bestätigung
speichert eine SQLite-Transaktion Anfrage, einzelne Aufträge und erste Ereignisse.
Die anschließenden Empfängeraufrufe erfolgen außerhalb dieser Transaktion.

| Schicht | Verantwortung | Austauschstelle |
|---|---|---|
| Browser | Auswahl, Vorschau, Bestätigung, Wiederholung mit unverändertem Schlüssel | REST |
| Interpreter | Strukturierte Artikel oder Rückfragen; keine Bestellbefugnis | `Interpreter.interpret` |
| PMS | Gültiger Aufenthalt statt bloßer Zimmernummer | `PMS.stays`, `PMS.require_active` |
| Koordinator | Atomare fachliche Entscheidungen und Auftragsverlauf | `HotelService` |
| Empfänger | Einmalige Annahme je Referenz; verlässlicher Statusabgleich | `Recipient.lookup`, `Recipient.submit` |
| Simulatorsteuerung | Fehlermodus und explizite Bearbeitungsschritte | Separate Demo-Endpunkte |

PMS ist eine statische Liste fiktiver aktiver Aufenthalte. Die beiden Empfänger
teilen eine eigene SQLite-Datei, aber getrennte Servicenamen und Referenzen. Das
bildet **getrennte Commit-Grenzen** ab; es sind keine separaten HTTP-Prozesse.
Ein echtes LLM lässt sich über `create_app(interpreter=...)` einsetzen. Es muss
strukturierte `Interpretation`-Ergebnisse liefern; Bestellentscheidung und
Idempotenz bleiben außerhalb des Modells. Für reale Empfänger den Port im
Composition Root ersetzen; Demo-Steuerung dann entfernen bzw. separat konfigurieren.

## Technische Wiederholung

Der Browser erzeugt eine UUID pro bestätigter Sendung. Vor dem HTTP-Aufruf speichert
er Schlüssel und vollständigen Inhalt in sessionStorage. Nach Netzfehler/5xx bleibt
die Sendung für eine identische Wiederholung erhalten. Eine neue Sendung ist bis
zur Klärung gesperrt. HTTP-4xx sind definitive Ablehnungen ohne neue Anlage.

Im Backend schützt `UNIQUE(idempotency_key)` die Anfrage. Der Inhaltshash umfasst
Aufenthalt, sortierte Positionen und Zusatzbestätigungs-Flag. Gleicher Schlüssel +
gleicher Inhalt liefert dieselbe Anfrage; anderer Inhalt ergibt HTTP 409. Die
Antwort enthält den **aktuellen** Stand der Aufträge und ist daher kein Byte-für-Byte-
Cache der ursprünglichen Antwort.

`BEGIN IMMEDIATE` serialisiert „prüfen und anlegen“ auch zwischen unabhängigen
SQLite-Verbindungen/Prozessen. Eine Wiederholung wird vor der Prüfung auf offene
Bestellungen erkannt. Ein paralleler Replay kann den Zwischenstand „gespeichert“
sehen; er startet keine zweite Übermittlung.

Jeder Teilauftrag erhält eine stabile UUID. Der Empfänger nutzt diese Referenz als
Primärschlüssel und prüft zusätzlich einen Inhaltshash. Ein wiederholter Aufruf
erzeugt keine zweite Annahme; abweichender Inhalt wird abgelehnt. Der Schutz gilt
innerhalb der Lebensdauer der beiden Datenbanken; Schlüssel werden nicht automatisch gelöscht.

## Wiederholter Wunsch und Teilfehler

Für denselben Aufenthalt blockiert ein bereits offener gleicher Artikel eine neue
Bestellung, auch bei anderer Menge. Bei gemischten Wünschen blockiert ein Konflikt
die **gesamte** neue Anfrage. Nur nach ausdrücklicher Bestätigung werden alle
angezeigten Positionen zusätzlich angelegt. Das ist eine konservative fachliche
Regel für diese kleine Demo, keine allgemeine semantische Ähnlichkeitssuche.

Prüfung auf offene Bestellungen und Anlage laufen in einer Transaktion. Erledigte
Aufträge und andere Aufenthalte blockieren neue Wünsche nicht. Die Vorschau kann
veralten; deshalb wiederholt das Backend diese Prüfung beim Bestätigen.

Housekeeping und Küche werden einzeln verarbeitet. Ausfall der Küche hebt einen
angenommenen Handtuchauftrag nicht auf. „Gespeichert“ und ein Fehlertext zeigen die
noch nicht erfolgte Küchenübergabe. Es gibt keine verteilte Gesamttransaktion und
keine automatische Kompensation.

## Antwortverlust, Absturz und Abgleich

Vor dem Empfängeraufruf wird „unklar“ persistiert. Der Empfänger committet unabhängig.
Beim Fehlermodus Antwortverlust erfolgt dieser Commit **vor** dem simulierten Timeout.
Ein Neustart lädt deshalb den offenen Auftrag einschließlich derselben Referenz.

Abgleich zuerst per Referenz: Bei Fund wird der bestätigte Zustand übernommen.
Nur bei verlässlich negativem Ergebnis wird mit derselben Referenz übermittelt.
Ist der Dienst nicht erreichbar, bleibt der bisherige Zustand erhalten. Bestätigte
Bearbeitungsstände dürfen durch verspätete niedrigere Zustände nicht zurückgesetzt werden.
Auch verspätete Fehler werden am bei Aufrufbeginn bekannten Zustand eingeordnet;
ein inzwischen bestätigter höherer Zustand wird nicht nachträglich als fehlerhaft markiert.
Auftragsliste und Ereignisverlauf werden innerhalb desselben SQLite-Lesesnapshots gelesen.
Simulatoraktionen geben einen Zielstatus vor, statt blind einen Schritt weiterzuschalten:
Wiederholtes „in Bearbeitung“ kann deshalb nicht versehentlich „erledigt“ auslösen.

Eine produktive API muss verbindlich festlegen, ob ein negatives Lookup vollständig
ist und wie lange Idempotenzreferenzen erhalten bleiben. Bei unklarer Antwort oder
eventuell verzögertem Status darf daraus keine Exactly-once-Garantie abgeleitet werden.
Ohne Idempotenzvertrag des externen Systems kann dieser Prototyp Doppelwirkungen
in jenem System nicht ausschließen.

## API-Übersicht

| Methode | Pfad | Zweck |
|---|---|---|
| GET | `/api/health` | Lokaler Bereitschaftstest |
| GET | `/api/bootstrap` | Demoaufenthalte, Artikel, Fehlermodi |
| POST | `/api/interpret` | Text → Positionen/Rückfragen; keine Anlage |
| POST | `/api/requests` | Bestätigte Anlage; UUID-Header `Idempotency-Key` erforderlich |
| GET | `/api/orders?stay_id=stay-101` | Gespeicherte Aufträge und Ereignisse; Filter optional |
| POST | `/api/orders/{id}/reconcile` | Empfänger abfragen, ggf. identisch erneut übermitteln |
| POST | `/api/simulator/{service}/mode` | `normal`, `offline`, `lose_response_once` |
| POST | `/api/simulator/orders/{id}/advance` | Simulierten Bearbeitungsstand fortschreiben |
| GET | `/api/simulator/receipts` | Tatsächliche Simulatorannahmen für die Vorführung |

`advance` benötigt `{"status":"in_progress"}` bzw. `{"status":"completed"}`.
Überspringen der Bearbeitung wird abgelehnt; wiederholte oder verspätete Zielzustände
liefern den aktuellen Stand zurück, ohne weitere Fortschaltung oder Rückstufung.

## Bewusste Grenzen

Lokaler Einzelplatzbetrieb; kein Rollen-/Login-System, keine echten Daten,
keine automatische Abarbeitung, keine verteilte Queue, keine Hochverfügbarkeit.
Langsame echte APIs benötigen begrenzte Timeouts, Retry-/Backoff-Strategie,
Authentifizierung und einen Hintergrundworker. SQLite-Dateien auf lokalem Laufwerk
verwenden; keine Datenbank auf Netzwerkfreigaben. Das Schema hat noch keine
Migrationshistorie. Für dieses Erstprojekt wird beim Start idempotent initialisiert.

Tests mit FastAPI-TestClient verwenden einen Context Manager, damit der Lifespan
pro Testinstanz korrekt startet und endet. Referenz:
https://fastapi.tiangolo.com/advanced/testing-events/
