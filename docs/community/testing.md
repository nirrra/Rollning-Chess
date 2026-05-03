# Testing Process

Rolling Chess uses tests as the guardrail for rule correctness and community contributions.

## Local Checks

Run all checks before opening a pull request:

```powershell
python -m pytest
python -m compileall -q src tests
node --check frontend/src/main.js
```

## Test Layers

### Engine Tests

Engine tests live in `tests/test_board.py`, `tests/test_piece_moves.py`, `tests/test_special_moves.py`, and `tests/test_check_and_mate.py`.

Engine changes should test:

- Normal behavior.
- `a`/`h` wrapping behavior.
- Blocked and unblocked sliding paths when relevant.
- Check legality if the move can affect king safety.

### Web API Tests

Web API tests live in `tests/test_web_api.py`.

API changes should test:

- Endpoint status code.
- Response JSON shape.
- Error behavior.
- State transition after valid and invalid moves.

### Frontend Checks

The current frontend has no build step. At minimum, run:

```powershell
node --check frontend/src/main.js
```

For UI behavior changes, include manual verification steps in the pull request.

## CI

GitHub Actions runs:

- Python 3.11 and 3.12.
- Editable install.
- Pytest.
- Python compile check.
- Frontend JavaScript syntax check.

CI must pass before merge.

## Adding Rule Tests

Prefer short constructed positions:

```python
state = position({"e1": "K", "e8": "k", "a5": "P", "h6": "r"})
assert "a5h6" in move_texts(state)
```

Avoid long game sequences unless the behavior specifically depends on move history, such as castling rights or en passant.

