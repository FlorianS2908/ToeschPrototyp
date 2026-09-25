import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import run
from app.main import create_app


class StubInterpreter:
    def __init__(self, result):
        self.result = result

    def interpret(self, text):
        return self.result


def test_invalid_adapter_output_is_rejected(tmp_path):
    adapter = StubInterpreter({"items": [{"kind": "towel", "quantity": -5}], "questions": []})
    with TestClient(create_app(tmp_path, adapter)) as client:
        response = client.post("/api/interpret", json={"stay_id": "stay-101", "text": "hello"})
        assert response.status_code == 502
        assert response.json()["detail"]["code"] == "invalid_interpretation"
        assert client.get("/api/orders").json()["orders"] == []


def test_empty_adapter_result_has_actionable_question(tmp_path):
    with TestClient(
        create_app(tmp_path, StubInterpreter({"items": [], "questions": []}))
    ) as client:
        result = client.post("/api/interpret", json={"stay_id": "stay-101", "text": "hello"}).json()
        assert not result["ready"] and result["questions"]


def test_adapter_can_be_replaced_without_changing_service(tmp_path):
    adapter = StubInterpreter({"items": [{"kind": "pizza", "quantity": 2}], "questions": []})
    with TestClient(create_app(tmp_path, adapter)) as client:
        result = client.post("/api/interpret", json={"stay_id": "stay-101", "text": "anything"})
        assert result.json()["items"] == [{"kind": "pizza", "quantity": 2}]
        assert client.get("/api/orders").json()["orders"] == []


@pytest.mark.parametrize("port", ["0", "1023", "65536", "invalid"])
def test_runner_rejects_invalid_port(tmp_path, monkeypatch, port):
    monkeypatch.setenv("HOTEL_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("HOTEL_PORT", port)
    with pytest.raises(ValueError):
        run.configuration()


def test_runner_configuration_is_portable(tmp_path, monkeypatch):
    directory = tmp_path / "Hotel Demo mit Leerzeichen"
    monkeypatch.setenv("HOTEL_DATA_DIR", str(directory))
    monkeypatch.setenv("HOTEL_PORT", "8123")
    assert run.configuration() == (Path(directory), 8123)


def test_runner_does_not_take_an_occupied_port(tmp_path, monkeypatch, capsys):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        monkeypatch.setenv("HOTEL_DATA_DIR", str(tmp_path))
        monkeypatch.setenv("HOTEL_PORT", str(listener.getsockname()[1]))
        assert run.main() == 1
        assert "Start fehlgeschlagen" in capsys.readouterr().err
