"""Durable request coordination. No database transaction spans an adapter call."""

import uuid

from .adapters import PMS, Recipient, ResponseLost, ServiceUnavailable, fingerprint, now
from .db import APP_SCHEMA, Database
from .models import ITEMS, STATUS_LABELS, STATUS_RANK, DomainError, OrderInput


class HotelService:
    def __init__(self, database: Database, pms: PMS, recipient: Recipient):
        self.db, self.pms, self.recipient = database, pms, recipient
        self.db.initialize(APP_SCHEMA)

    @staticmethod
    def _event(con, order_id, status, message):
        con.execute(
            "INSERT INTO events(order_id,status,message,created_at) VALUES (?,?,?,?)",
            (order_id, status, message, now()),
        )

    @staticmethod
    def _conflicts(con, stay_id, kinds):
        return [
            dict(row)
            for row in con.execute(
                "SELECT * FROM orders WHERE stay_id=? AND status != 'completed' "
                "ORDER BY created_at",
                (stay_id,),
            )
            if row["kind"] in kinds
        ]

    def conflicts(self, stay_id: str, kinds: set[str]) -> list[dict]:
        with self.db.connect() as con:
            return self._conflicts(con, stay_id, kinds)

    def save(self, payload: OrderInput, key: str) -> tuple[str, bool]:
        canonical = payload.model_dump()
        canonical["items"] = sorted(canonical["items"], key=lambda item: item["kind"])
        digest = fingerprint(canonical)
        with self.db.connect(write=True) as con:
            existing = con.execute(
                "SELECT * FROM requests WHERE idempotency_key=?", (key,)
            ).fetchone()
            if existing:
                if existing["payload_hash"] != digest:
                    raise DomainError(
                        409,
                        "idempotency_conflict",
                        "Dieser Schlüssel gehört zu einer anderen Bestellung.",
                    )
                return existing["id"], True
            self.pms.require_active(payload.stay_id)
            conflicts = self._conflicts(con, payload.stay_id, {i.kind for i in payload.items})
            if conflicts and not payload.allow_additional:
                raise DomainError(
                    409, "open_orders", "Passende offene Aufträge sind vorhanden.", orders=conflicts
                )
            request_id = str(uuid.uuid4())
            timestamp = now()
            con.execute(
                "INSERT INTO requests VALUES (?,?,?,?,?)",
                (request_id, key, digest, payload.stay_id, timestamp),
            )
            for item in payload.items:
                order_id = str(uuid.uuid4())
                con.execute(
                    "INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        order_id,
                        request_id,
                        payload.stay_id,
                        item.kind,
                        ITEMS[item.kind]["service"],
                        item.quantity,
                        "saved",
                        None,
                        timestamp,
                        timestamp,
                    ),
                )
                self._event(con, order_id, "saved", "Bestätigte Bestellung dauerhaft gespeichert.")
        return request_id, False

    def get_order(self, order_id: str) -> dict:
        with self.db.connect() as con:
            row = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            if not row:
                raise DomainError(404, "unknown_order", "Auftrag nicht gefunden.")
            return dict(row)

    def orders(self, request_id: str | None = None, stay_id: str | None = None) -> list[dict]:
        with self.db.connect(snapshot=True) as con:
            rows = con.execute(
                "SELECT * FROM orders WHERE (? IS NULL OR request_id=?) "
                "AND (? IS NULL OR stay_id=?) ORDER BY created_at DESC, id",
                (request_id, request_id, stay_id, stay_id),
            ).fetchall()
            result = []
            for row in rows:
                order = dict(row)
                order["label"] = ITEMS[row["kind"]]["label"]
                order["status_label"] = STATUS_LABELS[row["status"]]
                order["events"] = [
                    dict(event)
                    for event in con.execute(
                        "SELECT status,message,created_at FROM events WHERE order_id=? ORDER BY id",
                        (row["id"],),
                    )
                ]
                result.append(order)
            return result

    def _observe(self, order_id: str, status: str, message: str, error: str | None = None):
        with self.db.connect(write=True) as con:
            current = con.execute("SELECT * FROM orders WHERE id=?", (order_id,)).fetchone()
            # Late failure responses must not overwrite a confirmed or completed status.
            if STATUS_RANK[status] < STATUS_RANK[current["status"]]:
                return
            if status == current["status"] and error == current["last_error"]:
                return
            con.execute(
                "UPDATE orders SET status=?,last_error=?,updated_at=? WHERE id=?",
                (status, error, now(), order_id),
            )
            self._event(con, order_id, status, message)

    def reconcile(self, order_id: str) -> dict:
        order = self.get_order(order_id)
        attempted_status = order["status"]
        if order["status"] == "completed":
            return order
        try:
            receipt = self.recipient.lookup(order["service"], order_id)
            if receipt:
                self._observe(order_id, receipt["status"], "Status beim Empfänger bestätigt.")
                return self.get_order(order_id)
            if STATUS_RANK[order["status"]] >= STATUS_RANK["transmitted"]:
                raise DomainError(409, "recipient_missing", "Bestätigter Empfängerauftrag fehlt.")
            # Persist uncertainty BEFORE crossing the service boundary (crash recovery).
            self._observe(order_id, "uncertain", "Übergabe gestartet; Empfang noch unbestätigt.")
            attempted_status = "uncertain"
            receipt = self.recipient.submit(order)
            self._observe(order_id, receipt["status"], "Empfänger hat den Auftrag bestätigt.")
        except ServiceUnavailable as error:
            self._observe(order_id, attempted_status, str(error), str(error))
        except ResponseLost as error:
            self._observe(order_id, "uncertain", str(error), str(error))
        return self.get_order(order_id)

    def submit(self, payload: OrderInput, key: str) -> dict:
        request_id, replayed = self.save(payload, key)
        # A technical replay is read-only; explicit reconciliation performs recovery.
        if not replayed:
            for order in self.orders(request_id=request_id):
                self.reconcile(order["id"])
        return {
            "request_id": request_id,
            "replayed": replayed,
            "orders": self.orders(request_id=request_id),
        }
