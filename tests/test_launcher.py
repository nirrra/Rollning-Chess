from __future__ import annotations

import socket
import sys

import pytest

from rolling_chess import launcher, web


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def test_select_port_prefers_requested_port_when_available():
    port = _free_port()

    assert web.select_port(requested_port=port, candidates=()) == port


def test_select_port_falls_back_when_requested_port_is_unavailable():
    fallback_port = _free_port()
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as blocked:
        blocked.bind(("127.0.0.1", 0))
        blocked.listen()
        blocked_port = int(blocked.getsockname()[1])

        selected_port = web.select_port(
            requested_port=blocked_port,
            candidates=(fallback_port,),
        )

    assert selected_port == fallback_port


def test_select_port_raises_when_probe_never_succeeds(monkeypatch):
    monkeypatch.setattr(web, "_probe_port", lambda _host, _port: None)

    with pytest.raises(web.PortSelectionError, match="could not find an available port"):
        web.select_port(candidates=())


def test_default_frontend_dir_prefers_pyinstaller_bundle(monkeypatch, tmp_path):
    frontend_dir = tmp_path / "frontend"
    frontend_dir.mkdir()
    (frontend_dir / "index.html").write_text("<!doctype html>", encoding="utf-8")
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)

    assert web._default_frontend_dir() == frontend_dir


def test_default_frontend_dir_finds_source_frontend():
    frontend_dir = web._default_frontend_dir()

    assert frontend_dir.name == "frontend"
    assert (frontend_dir / "index.html").is_file()


def test_open_browser_when_ready_checks_health_before_opening():
    checked_urls: list[str] = []
    opened_urls: list[str] = []

    def health_checker(url: str, timeout_seconds: float) -> None:
        checked_urls.append(url)
        assert timeout_seconds == 3.0

    def browser_open(url: str) -> bool:
        opened_urls.append(url)
        return True

    launcher.open_browser_when_ready(
        "http://127.0.0.1:3000",
        timeout_seconds=3.0,
        health_checker=health_checker,
        browser_open=browser_open,
    )

    assert checked_urls == ["http://127.0.0.1:3000/api/health"]
    assert opened_urls == ["http://127.0.0.1:3000/"]


def test_wait_for_health_retries_until_success(monkeypatch):
    calls = 0
    sleeps: list[float] = []

    class Response:
        def getcode(self) -> int:
            return 200

        def close(self) -> None:
            return None

    def urlopen(_url: str, timeout: int) -> Response:
        nonlocal calls
        calls += 1
        assert timeout == 1
        if calls == 1:
            raise OSError("not ready")
        return Response()

    monkeypatch.setattr(launcher.time, "sleep", lambda seconds: sleeps.append(seconds))

    launcher.wait_for_health(
        "http://127.0.0.1:3000/api/health",
        timeout_seconds=5,
        interval_seconds=0.25,
        urlopen=urlopen,
    )

    assert calls == 2
    assert sleeps == [0.25]
