# Windows One-Click Launcher Design

## Purpose

Rolling Chess currently starts through a command such as `python -m rolling_chess.web --host 127.0.0.1 --port 8000`, and the user must then open the browser manually. This is fragile for non-developers and for Windows machines where common ports may be occupied or excluded by the OS.

This design adds a Windows-focused local launcher that can be packaged as an `.exe`. The first release targets single-machine play: double-click the executable, let it find a usable local port, start the existing FastAPI backend, and open the default browser to the game.

LAN hosting, embedded WebView, installers, auto-update, code signing, and cross-platform binaries are out of scope for this pass.

## Confirmed Product Decision

The launcher is for Windows single-player/local play. It binds to `127.0.0.1`, not `0.0.0.0`, and opens a browser on the same machine.

## User Flow

1. User downloads or builds `RollingChess.exe`.
2. User double-clicks the executable.
3. The launcher chooses a usable local port.
4. The launcher starts the web app.
5. The launcher waits until `/api/health` responds successfully.
6. The launcher opens `http://127.0.0.1:<port>/` in the default browser.
7. The launcher process remains alive while the game is running.
8. Closing the launcher process stops the local server.

## Architecture

The existing `rolling_chess.web` module remains the FastAPI application owner. It should gain small, testable helpers for port selection and server startup, while preserving the existing `rolling-chess-web` command.

Add a new `rolling_chess.launcher` module for the one-click experience. It should:

- Ask the web module to choose a port.
- Start Uvicorn in the current process.
- Poll the health endpoint before opening the browser.
- Use Python's `webbrowser` module to open the page.
- Print the selected URL for users who prefer copying it manually.

The launcher should avoid GUI framework dependencies. A console window is acceptable for this first exe because it gives users a visible way to stop the server and see the chosen URL.

## Port Selection

The default behavior should be stable on Windows:

- Try the requested port first when a user passes one.
- Otherwise prefer `8000`, then common development ports that are often permitted, including `3000`, `5173`, `8080`, `8100`, `8200`, `8765`, `8888`, `9000`, and `10000`.
- If all preferred ports fail, bind to port `0` temporarily to ask the OS for an available port.
- Treat `EADDRINUSE`, `EACCES`, and Windows socket permission failures as reasons to try the next port.
- Close the probe socket before starting Uvicorn.

This approach cannot guarantee that another process will not take the port between probing and server startup, but it handles the common case and makes failures rare. If startup still fails, the launcher should exit with a clear error.

## Packaging

Use PyInstaller for the first Windows binary. Add a small build script or documented command that:

- Uses the launcher module as the entrypoint.
- Includes the `frontend/` directory as package data available at runtime.
- Produces a binary named `RollingChess.exe`.
- Keeps build outputs out of git.

The frontend directory lookup must work both from a source checkout and from a PyInstaller bundle. In a bundle, the app should resolve assets from `sys._MEIPASS` or equivalent PyInstaller extraction path.

## Tests

Add focused tests for:

- Selecting the requested port when available.
- Falling back when the first candidate is unavailable.
- Raising a clear error when no candidate or OS-assigned port can be obtained.
- Resolving the frontend directory from the normal source tree.
- Launcher health polling/open-browser behavior using injectable functions so tests do not open a real browser.

Manual verification should include starting the launcher, confirming the health endpoint, and confirming the browser loads the game.

## Documentation

README should keep the developer command-line workflow, but add a non-developer section:

- Download or build `RollingChess.exe`.
- Double-click it.
- The game opens automatically in the default browser.
- If the browser does not open, copy the URL shown in the launcher window.

The README should also explain that the app automatically chooses a different local port if `8000` is unavailable.
