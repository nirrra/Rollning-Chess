from __future__ import annotations

import argparse
import threading
import time
import urllib.error
import urllib.request
import webbrowser
from collections.abc import Callable

import uvicorn

from .web import DEFAULT_WEB_HOST, create_app, local_url, select_port

DEFAULT_HEALTH_TIMEOUT_SECONDS = 15.0
DEFAULT_HEALTH_INTERVAL_SECONDS = 0.2

UrlOpen = Callable[..., object]
BrowserOpen = Callable[[str], object]
HealthChecker = Callable[[str, float], None]


class LauncherError(RuntimeError):
    """Raised when the one-click launcher cannot start the local app."""


def wait_for_health(
    health_url: str,
    timeout_seconds: float = DEFAULT_HEALTH_TIMEOUT_SECONDS,
    interval_seconds: float = DEFAULT_HEALTH_INTERVAL_SECONDS,
    urlopen: UrlOpen = urllib.request.urlopen,
) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: BaseException | None = None

    while time.monotonic() < deadline:
        try:
            response = urlopen(health_url, timeout=1)
            try:
                status_code = getattr(response, "getcode", lambda: 200)()
                if 200 <= int(status_code) < 300:
                    return
            finally:
                close = getattr(response, "close", None)
                if close:
                    close()
        except (OSError, urllib.error.URLError) as exc:
            last_error = exc
        time.sleep(interval_seconds)

    detail = f": {last_error}" if last_error else ""
    raise LauncherError(f"server did not become ready at {health_url}{detail}")


def open_browser_when_ready(
    base_url: str,
    timeout_seconds: float = DEFAULT_HEALTH_TIMEOUT_SECONDS,
    health_checker: HealthChecker = wait_for_health,
    browser_open: BrowserOpen = webbrowser.open,
) -> None:
    normalized_url = base_url.rstrip("/") + "/"
    health_url = normalized_url + "api/health"
    health_checker(health_url, timeout_seconds)
    browser_open(normalized_url)


def run_launcher(
    host: str = DEFAULT_WEB_HOST,
    requested_port: int | None = None,
    open_browser: bool = True,
) -> int:
    port = select_port(host, requested_port)
    url = local_url(host, port)

    config = uvicorn.Config(create_app(), host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, name="rolling-chess-web", daemon=True)

    print(f"Starting Rolling Chess at {url}", flush=True)
    server_thread.start()

    try:
        if open_browser:
            open_browser_when_ready(url)
        else:
            wait_for_health(url.rstrip("/") + "/api/health")
            print(f"Rolling Chess is ready at {url}", flush=True)

        while server_thread.is_alive():
            server_thread.join(timeout=0.5)
    except KeyboardInterrupt:
        print("Stopping Rolling Chess...", flush=True)
    finally:
        server.should_exit = True
        server_thread.join(timeout=5)

    return port


def main() -> None:
    parser = argparse.ArgumentParser(description="Start Rolling Chess and open it in a browser.")
    parser.add_argument("--host", default=DEFAULT_WEB_HOST)
    parser.add_argument("--port", type=int, default=None, help="Preferred local port.")
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Start the server without opening the default browser.",
    )
    args = parser.parse_args()
    run_launcher(host=args.host, requested_port=args.port, open_browser=not args.no_browser)


if __name__ == "__main__":
    main()
