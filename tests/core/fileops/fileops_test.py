"""
Tests for core.fileops.

Run with: pytest tests/core/fileops/fileops_test.py -v
Note: Missing TOML tests.
"""

from pathlib import Path
import pytest
from core.fileops import get_fileops


@pytest.fixture
def fops():
    return get_fileops()


def test_join_returns_path(fops):
    p = fops.join("projects", "examples", "template")
    assert isinstance(p, Path)
    assert str(p).endswith("template")


def test_ensure_dir_creates_nested_folders(tmp_path, fops):
    target = tmp_path / "a" / "b" / "c"
    assert not target.exists()

    result = fops.ensure_dir(target)

    assert result.exists()
    assert result.is_dir()
    assert result == target


def test_ensure_dir_is_idempotent(tmp_path, fops):
    target = tmp_path / "a"
    fops.ensure_dir(target)
    # Second call should not crash or raise an exception
    fops.ensure_dir(target)
    assert target.exists()


def test_project_log_dir_builds_expected_structure(tmp_path, fops):
    log_dir = fops.project_log_dir(tmp_path, "bus_logs")

    assert log_dir == tmp_path / "logs" / "bus_logs"
    assert log_dir.exists()


def test_write_and_read_json_roundtrip(tmp_path, fops):
    path = tmp_path / "config" / "mydrone.json"
    data = {"drone_id": "drone1", "ip": "192.168.10.1", "max_speed_ms": 8.0}

    fops.write_json(path, data)
    loaded = fops.read_json(path)

    assert loaded == data
    assert path.exists()


def test_append_line_writes_jsonl_style(tmp_path, fops):
    path = tmp_path / "logs" / "bus_logs" / "flight.jsonl"

    fops.append_line(path, '{"topic": "cmd.drone1", "action": "forward"}')
    fops.append_line(path, '{"topic": "state.drone1", "battery": 87}')

    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert lines[0] == '{"topic": "cmd.drone1", "action": "forward"}'


def test_platform_name_is_nonempty_string(fops):
    name = fops.platform_name()
    assert isinstance(name, str)
    assert len(name) > 0