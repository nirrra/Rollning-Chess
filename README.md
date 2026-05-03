# Rolling Chess

Rolling Chess is a chess variant played on a horizontal cylinder: files `a` and `h` are connected while ranks remain bounded.

Implementation order:

1. Python rules engine.
2. Local Python backend plus browser UI.
3. Product extensions after the core game is stable.

Run tests:

```powershell
python -m pytest
```

Run the CLI:

```powershell
python -m rolling_chess.cli
```

Run the local browser UI:

```powershell
$env:PYTHONPATH='src'
python -m rolling_chess.web --host 127.0.0.1 --port 8000
```

Then open `http://127.0.0.1:8000/`.
