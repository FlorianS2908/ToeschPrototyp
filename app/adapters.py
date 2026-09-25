"""Replaceable PMS and recipient ports. This implementation performs no network calls."""

import hashlib
import json
from datetime import UTC, datetime
from typing import Protocol

from .db import RECEIVER_SCHEMA, Database
from .models import STATUS_RANK, DomainError, FaultMode, ServiceName


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="milliseconds")


def fingerprint(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


class PMS(Protocol):
    def stays(self) -> list[dict]: ...
    def require_active(self, stay_id: str) -> dict: ...


class PMSimulator:
    demo_stays = (
        {"id": "stay-101", "room": "101", "label": "Zimmer 101 · Demoaufenthalt A"},
        {"id": "stay-204", "room": "204", "label": "Zimmer 204 · Demoaufenthalt B"},
        {"id": "stay-305", "room": "305", "label": "Zimmer 305 · Demoaufenthalt C"},
    )

    def stays(self) -> list[dict]:
        return [dict(stay) for stay in self.demo_stays]

    def require_active(self, stay_id: str) -> dict:
        for stay in self.stays():
            if stay["id"] == stay_id:
                return stay
        raise DomainError(404, "unknown_stay", "Dieser Demoaufenthalt existiert nicht.")


class ServiceUnavailable(Exception):
    """Simulator guarantees that submit has not written anything in this failure case."""


class ResponseLost(Exception):
    """Caller cannot know whether the recipient has accepted the request."""


class Recipient(Protocol):
    def lookup(self, service: str, reference: str) -> dict | None: ...
    def submit(self, order: dict) -> dict: ...


class RecipientSimulator:
    def __init__(self, database: Database):
        self.db = database
        self.db.initialize(RECEIVER_SCHEMA)

    def modes(self) -> dict:
        with self.db.connect() as con:
            return {row["service"]: row["mode"] for row in con.execute("SELECT * FROM modes")}

    def set_mode(self, service: ServiceName, mode: FaultMode):
        with self.db.connect(write=True) as con:
            con.execute("UPDATE modes SET mode=? WHERE service=?", (mode, service))

    @staticmethod
    def _available(con, service):
        row = con.execute("SELECT mode FROM modes WHERE service=?", (service,)).fetchone()
        if not row:
            raise DomainError(404, "unknown_service", "Unbekannter Empfängerdienst.")
        if row["mode"] == "offline":
            raise ServiceUnavailable("Der simulierte Dienst ist nicht erreichbar.")
        return row["mode"]

    def lookup(self, service: str, reference: str) -> dict | None:
        with self.db.connect() as con:
            self._available(con, service)
            row = con.execute(
                "SELECT * FROM receipts WHERE reference=? AND service=?", (reference, service)
            ).fetchone()
            return dict(row) if row else None

    def submit(self, order: dict) -> dict:
        payload = {key: order[key] for key in ("stay_id", "kind", "quantity", "service")}
        digest = fingerprint(payload)
        lost = False
        with self.db.connect(write=True) as con:
            mode = self._available(con, order["service"])
            existing = con.execute(
                "SELECT * FROM receipts WHERE reference=?", (order["id"],)
            ).fetchone()
            if existing:
                if existing["payload_hash"] != digest:
                    raise DomainError(
                        409, "recipient_conflict", "Empfängerreferenz widersprüchlich."
                    )
                return dict(existing)
            con.execute(
                "INSERT INTO receipts VALUES (?,?,?,?,?,?,?,?)",
                (
                    order["id"],
                    order["service"],
                    digest,
                    order["stay_id"],
                    order["kind"],
                    order["quantity"],
                    "transmitted",
                    now(),
                ),
            )
            receipt = dict(
                con.execute("SELECT * FROM receipts WHERE reference=?", (order["id"],)).fetchone()
            )
            if mode == "lose_response_once":
                con.execute("UPDATE modes SET mode='normal' WHERE service=?", (order["service"],))
                lost = True
        # Commit precedes the failure: a separate database models the remote side effect.
        if lost:
            raise ResponseLost("Rückmeldung verloren. Annahme erst nach Statusabgleich bekannt.")
        return receipt

    def advance(self, reference: str, target: str) -> dict:
        with self.db.connect(write=True) as con:
            row = con.execute("SELECT * FROM receipts WHERE reference=?", (reference,)).fetchone()
            if not row:
                raise DomainError(
                    409, "not_received", "Beim Empfänger noch kein Auftrag vorhanden."
                )
            self._available(con, row["service"])
            if target not in {"in_progress", "completed"}:
                raise DomainError(422, "invalid_transition", "Ungültiger Bearbeitungsstand.")
            if STATUS_RANK[target] <= STATUS_RANK[row["status"]]:
                return dict(row)
            if row["status"] == "transmitted" and target == "completed":
                raise DomainError(409, "invalid_transition", "Zuerst die Bearbeitung starten.")
            con.execute("UPDATE receipts SET status=? WHERE reference=?", (target, reference))
            return dict(
                con.execute("SELECT * FROM receipts WHERE reference=?", (reference,)).fetchone()
            )

    def receipts(self) -> list[dict]:
        with self.db.connect() as con:
            return [dict(row) for row in con.execute("SELECT * FROM receipts ORDER BY created_at")]
