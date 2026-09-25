from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient

from app.adapters import ServiceUnavailable
from app.main import create_app
from app.models import DomainError, OrderInput
from tests.test_workflow import payload, receipts, submit


def test_repeated_status_action_does_not_skip_processing(client):
    order = submit(client).json()["orders"][0]
    url = f"/api/simulator/orders/{order['id']}/advance"
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(
            pool.map(lambda _: client.post(url, json={"status": "in_progress"}), range(12))
        )
    assert all(r.status_code == 200 and r.json()["status"] == "in_progress" for r in responses)
    assert receipts(client)[0]["status"] == "in_progress"
    assert client.post(url, json={"status": "completed"}).json()["status"] == "completed"
    assert client.post(url, json={"status": "in_progress"}).json()["status"] == "completed"


def test_status_transition_cannot_skip_or_invent_states(client):
    order = submit(client).json()["orders"][0]
    url = f"/api/simulator/orders/{order['id']}/advance"
    assert client.post(url, json={"status": "completed"}).status_code == 409
    assert client.post(url, json={"status": "anything"}).status_code == 422
    assert client.post(url, json={}).status_code == 422
    assert receipts(client)[0]["status"] == "transmitted"


def test_late_failure_cannot_mark_completed_order_for_attention(client, monkeypatch):
    order = submit(client).json()["orders"][0]
    service = client.app.state.service
    simulator = client.app.state.simulator

    def delayed_failure(_service, reference):
        simulator.advance(reference, "in_progress")
        receipt = simulator.advance(reference, "completed")
        service._observe(reference, receipt["status"], "Parallel bestätigter Abschluss.")
        raise ServiceUnavailable("Verspäteter Fehler eines früher gestarteten Abgleichs.")

    monkeypatch.setattr(simulator, "lookup", delayed_failure)
    final = service.reconcile(order["id"])
    assert final["status"] == "completed" and final["last_error"] is None


def test_late_positive_response_cannot_regress_state(client, monkeypatch):
    order = submit(client).json()["orders"][0]
    service = client.app.state.service
    simulator = client.app.state.simulator
    stale = simulator.lookup(order["service"], order["id"])

    def delayed_response(_service, reference):
        simulator.advance(reference, "in_progress")
        receipt = simulator.advance(reference, "completed")
        service._observe(reference, receipt["status"], "Parallel bestätigter Abschluss.")
        return stale

    monkeypatch.setattr(simulator, "lookup", delayed_response)
    assert service.reconcile(order["id"])["status"] == "completed"


def test_order_and_timeline_share_one_snapshot(client, monkeypatch):
    order = submit(client).json()["orders"][0]
    service = client.app.state.service
    connect = service.db.connect
    changed = False

    def between_order_and_timeline(sql):
        nonlocal changed
        if sql.startswith("SELECT status,message") and not changed:
            changed = True
            receipt = client.app.state.simulator.advance(order["id"], "in_progress")
            service._observe(order["id"], receipt["status"], "Änderung während Listenabfrage.")

    @contextmanager
    def interleaved_connect(**kwargs):
        with connect(**kwargs) as con:
            if kwargs.get("snapshot"):
                con.set_trace_callback(between_order_and_timeline)
            yield con

    monkeypatch.setattr(service.db, "connect", interleaved_connect)
    observed = service.orders()[0]
    assert changed
    assert observed["status"] == observed["events"][-1]["status"] == "transmitted"
    assert service.get_order(order["id"])["status"] == "in_progress"


def test_receiver_rejects_changed_content_under_same_reference(client):
    order = submit(client).json()["orders"][0]
    simulator = client.app.state.simulator
    assert simulator.submit(order)["reference"] == order["id"]
    with pytest.raises(DomainError) as error:
        simulator.submit({**order, "quantity": 3})
    assert error.value.detail["code"] == "recipient_conflict"
    assert len(receipts(client)) == 1


def test_crash_after_local_commit_before_delivery(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as first:
        request_id, _ = app.state.service.save(OrderInput(**payload()), "crash-before-delivery")
        assert not receipts(first)
    with TestClient(create_app(tmp_path)) as second:
        order = second.get("/api/orders").json()["orders"][0]
        assert order["request_id"] == request_id and order["status"] == "saved"
        result = second.post(f"/api/orders/{order['id']}/reconcile", json={})
        assert result.json()["status"] == "transmitted" and len(receipts(second)) == 1


def test_crash_after_receiver_commit_before_local_acknowledgement(tmp_path):
    app = create_app(tmp_path)
    with TestClient(app) as first:
        real_submit = app.state.simulator.submit

        def crash(order):
            real_submit(order)
            raise RuntimeError("Abrupt process failure after remote commit")

        app.state.simulator.submit = crash
        with pytest.raises(RuntimeError):
            submit(first)
        assert len(receipts(first)) == 1
    with TestClient(create_app(tmp_path)) as second:
        order = second.get("/api/orders").json()["orders"][0]
        assert order["status"] == "uncertain"
        result = second.post(f"/api/orders/{order['id']}/reconcile", json={})
        assert result.json()["status"] == "transmitted"
        assert len(receipts(second)) == 1
