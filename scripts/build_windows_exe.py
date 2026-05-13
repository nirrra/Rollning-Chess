from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    frontend_dir = project_root / "frontend"
    entrypoint = project_root / "scripts" / "run_windows_launcher.py"
    excluded_modules = [
        "rolling_chess.ai.value_model",
        "torch",
        "matplotlib",
        "IPython",
        "PyQt5",
        "pytest",
        "sphinx",
        "jedi",
        "zmq",
    ]

    if not (frontend_dir / "index.html").is_file():
        raise SystemExit(f"missing frontend assets: {frontend_dir}")

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--name",
        "RollingChess",
        "--paths",
        str(project_root / "src"),
        "--add-data",
        f"{frontend_dir}{os.pathsep}frontend",
        str(entrypoint),
    ]
    for module_name in excluded_modules:
        command.extend(["--exclude-module", module_name])
    return subprocess.call(command, cwd=project_root)


if __name__ == "__main__":
    raise SystemExit(main())
