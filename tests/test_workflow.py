import uuid
from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient

from app.main import create_app


def payload(stay="stay-101", quantity=2, *, pizza=False, additional=False):
    items = [{"kind": "towel", "quantity": quantity}]
    if pizza:
        items.append({"kind": "pizza", "quantity": 1})
    return {"stay_id": stay, "items": items, "allow_additional": additional}


def submit(client, body=None, key=None):
    return client.post(
        "/api/requests",
        json=body or payload(),
        headers={"Idempotency-Key": key or str(uuid.uuid4())},
    )


def receipts(client):
    return client.get("/api/simulator/receipts").json()["receipts"]


def set_mode(client, service, mode):
    assert client.post(f"/api/simulator/{service}/mode", json={"mode": mode}).status_code == 200


def test_guest_confirm_mixed_order(client):
    preview = client.post(
        "/api/interpret",
        json={"stay_id": "stay-101", "text": "Ich hätte gerne zwei Handtücher und eine Pizza."},
    ).json()
    assert preview["ready"] and not preview["questions"]
    assert client.get("/api/orders").json()["orders"] == []
    response = submit(client, {"stay_id": "stay-101", "items": preview["items"]})
    assert response.status_code == 201
    orders = response.json()["orders"]
    assert {(o["service"], o["quantity"], o["status"]) for o in orders} == {
        ("housekeeping", 2, "transmitted"),
        ("kitchen", 1, "transmitted"),
    }
    assert len(receipts(client)) == 2
    for order in orders:
        assert order["events"][0]["status"] == "saved"
        assert order["events"][-1]["status"] == "transmitted"


def test_same_key_replay_and_changed_payload(client):
    key = str(uuid.uuid4())
    first = submit(client, key=key)
    second = submit(client, key=key)
    conflict = submit(client, payload(quantity=4), key)
    assert first.status_code == 201
    assert second.status_code == 200 and second.json()["replayed"]
    assert first.json()["request_id"] == second.json()["request_id"]
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "idempotency_conflict"
    assert len(receipts(client)) == 1


def test_item_order_is_not_a_new_payload(client):
    key = str(uuid.uuid4())
    body = payload(pizza=True)
    submit(client, body, key)
    body["items"].reverse()
    assert submit(client, body, key).status_code == 200
    assert len(receipts(client)) == 2


def test_parallel_same_key_once(client):
    key = str(uuid.uuid4())
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda _: submit(client, key=key), range(16)))
    assert sorted(r.status_code for r in responses) == [200] * 15 + [201]
    assert len({r.json()["request_id"] for r in responses}) == 1
    assert len(client.get("/api/orders").json()["orders"]) == len(receipts(client)) == 1


def test_semantic_duplicate_then_explicit_additional(client):
    submit(client)
    preview = client.post(
        "/api/interpret", json={"stay_id": "stay-101", "text": "2 Handtücher"}
    ).json()
    assert len(preview["conflicts"]) == 1
    blocked = submit(client)
    assert blocked.status_code == 409 and blocked.json()["detail"]["code"] == "open_orders"
    assert submit(client, payload(additional=True)).status_code == 201
    assert sum(r["quantity"] for r in receipts(client)) == 4


def test_parallel_different_keys_semantic_guard(client):
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(lambda _: submit(client), range(12)))
    assert sorted(r.status_code for r in responses) == [201] + [409] * 11
    assert len(receipts(client)) == 1


def test_open_overlap_blocks_whole_mixed_order(client):
    submit(client)
    assert submit(client, payload(pizza=True)).status_code == 409
    assert len(receipts(client)) == 1  # no silent partial acceptance of just the pizza
    assert submit(client, payload(stay="stay-204")).status_code == 201


def test_loss_reconcile_no_duplicate(client):
    set_mode(client, "housekeeping", "lose_response_once")
    key = str(uuid.uuid4())
    order = submit(client, key=key).json()["orders"][0]
    assert order["status"] == "uncertain"
    assert len(receipts(client)) == 1
    assert submit(client, key=key).json()["orders"][0]["status"] == "uncertain"
    result = client.post(f"/api/orders/{order['id']}/reconcile", json={}).json()
    assert result["status"] == "transmitted"
    assert len(receipts(client)) == 1


def test_offline_mixed_outcome_recovery(client):
    set_mode(client, "kitchen", "offline")
    orders = submit(client, payload(pizza=True)).json()["orders"]
    by_service = {o["service"]: o for o in orders}
    assert by_service["housekeeping"]["status"] == "transmitted"
    assert by_service["kitchen"]["status"] == "saved"
    assert by_service["kitchen"]["last_error"]
    assert len(receipts(client)) == 1
    set_mode(client, "kitchen", "normal")
    kitchen = by_service["kitchen"]["id"]
    assert (
        client.post(f"/api/orders/{kitchen}/reconcile", json={}).json()["status"] == "transmitted"
    )
    assert len(receipts(client)) == 2


def test_unknown_stays_and_input_validation(client):
    assert submit(client, payload(stay="unknown")).status_code == 404
    for quantity in [0, -1, 21, 1.5, True, "2"]:
        assert submit(client, payload(quantity=quantity)).status_code == 422
    assert client.post("/api/requests", json=payload()).status_code == 422
    assert submit(client, key="invalid").status_code == 422
    assert len(receipts(client)) == 0


def test_real_progress_and_completed_order_allows_new_request(client):
    order = submit(client).json()["orders"][0]
    url = f"/api/simulator/orders/{order['id']}/advance"
    assert client.post(url, json={"status": "in_progress"}).json()["status"] == "in_progress"
    assert client.post(url, json={"status": "completed"}).json()["status"] == "completed"
    assert client.post(url, json={"status": "completed"}).json()["status"] == "completed"
    assert submit(client).status_code == 201


def test_restart_preserves_uncertain_and_saved(tmp_path):
    key = str(uuid.uuid4())
    with TestClient(create_app(tmp_path)) as first:
        set_mode(first, "housekeeping", "lose_response_once")
        set_mode(first, "kitchen", "offline")
        result = submit(first, payload(pizza=True), key).json()
    with TestClient(create_app(tmp_path)) as second:
        replay = submit(second, payload(pizza=True), key).json()
        assert replay["request_id"] == result["request_id"]
        assert {o["status"] for o in replay["orders"]} == {"saved", "uncertain"}
        assert len(receipts(second)) == 1
        assert second.get("/api/bootstrap").json()["modes"]["kitchen"] == "offline"
        set_mode(second, "kitchen", "normal")
        for order in replay["orders"]:
            second.post(f"/api/orders/{order['id']}/reconcile", json={})
        assert len(receipts(second)) == 2
        assert all(o["status"] == "transmitted" for o in second.get("/api/orders").json()["orders"])


def test_parallel_reconciliation_at_recipient(client):
    set_mode(client, "housekeeping", "offline")
    order = submit(client).json()["orders"][0]
    set_mode(client, "housekeeping", "normal")
    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(
            pool.map(
                lambda _: client.post(f"/api/orders/{order['id']}/reconcile", json={}), range(12)
            )
        )
    assert all(r.status_code == 200 for r in responses)
    assert len(receipts(client)) == 1
    assert client.get("/api/orders").json()["orders"][0]["status"] == "transmitted"


def test_local_demo_guards(client):
    assert client.get("/", headers={"Host": "evil.example"}).status_code == 400
    assert submit(client).status_code == 201
    assert (
        client.post(
            "/api/requests",
            json=payload(),
            headers={"Origin": "https://evil.example", "Idempotency-Key": str(uuid.uuid4())},
        ).status_code
        == 403
    )
    assert client.post("/api/simulator/kitchen/mode", data={"mode": "offline"}).status_code == 415
    page = client.get("/")
    assert page.status_code == 200 and "SIMULATION" in page.text
    assert "frame-ancestors 'none'" in page.headers["Content-Security-Policy"]
