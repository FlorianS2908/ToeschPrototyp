from pathlib import Path

import demo


def test_demo_sessions_are_isolated_and_preserve_existing_data(tmp_path, monkeypatch):
    monkeypatch.setattr(demo, "__file__", str(tmp_path / "demo.py"))
    existing = tmp_path / "data"
    existing.mkdir()
    (existing / "keep.txt").write_text("keep")
    first = demo.configure_demo()
    (first / "staydesk.sqlite").write_text("prior demo")
    second = demo.configure_demo()
    assert first != second
    assert first.parent == second.parent == tmp_path / ".demo"
    assert (first / "staydesk.sqlite").read_text() == "prior demo"
    assert (existing / "keep.txt").read_text() == "keep"
    assert Path(demo.os.environ["HOTEL_DATA_DIR"]) == second
