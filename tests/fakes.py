import os
from pathlib import Path

import pytest


def fake_executable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, script: str) -> None:
    """Puts a stand-in executable first on PATH."""
    exe = tmp_path / "bin" / name
    exe.parent.mkdir(exist_ok=True)
    exe.write_text(f"#!/bin/sh\n{script}\n")
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", f"{exe.parent}{os.pathsep}{os.environ['PATH']}")
