# Rolling Chess

Rolling Chess is a chess variant played on a horizontal cylinder: files `a` and `h` are connected while ranks remain bounded.

Implementation order:

1. Python rules engine.
2. Local Python backend plus browser UI.
3. Product extensions after the core game is stable.

Install from the repository root:

```bash
python -m pip install -r requirements.txt
```

Run tests:

```bash
python -m pytest
```

Run the CLI:

```bash
python -m rolling_chess.cli
```

Run the local browser UI:

```bash
python -m rolling_chess.web --host 127.0.0.1 --port 8000
```

Then open `http://127.0.0.1:8000/`.

Run LAN play:

```bash
python -m rolling_chess.web --host 0.0.0.0 --port 8000
```

Then open `http://<host-lan-ip>:8000/` from another device on the same LAN.

There are two ways to start a LAN match:

1. Create a room on the host, then join by room code.
   - On the host page, click `Create LAN Room`.
   - Share the room code shown in the URL or page.
   - On the other device, open `http://<host-lan-ip>:8000/`, enter the room code, and click `Join Room`.

2. Create a room on the host, then share the room link.
   - On the host page, click `Create LAN Room`.
   - Share a link like `http://<host-lan-ip>:8000/room/ABC123`.
   - The other device opens the link, enters a nickname if needed, and joins the room.

Use the host machine's LAN IP, not `127.0.0.1`, for other devices.

If you run without installing the package first, add `src` to `PYTHONPATH`:

```bash
PYTHONPATH=src python -m rolling_chess.web --host 127.0.0.1 --port 8000
```

In PowerShell, use:

```powershell
$env:PYTHONPATH='src'
python -m rolling_chess.web --host 127.0.0.1 --port 8000
```
