from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SHELL_SCRIPT = REPO_ROOT / "scripts" / "start-backend.sh"
DEV_SHELL_SCRIPT = REPO_ROOT / "scripts" / "start-dev.sh"
POWERSHELL_SCRIPT = REPO_ROOT / "scripts" / "start-backend.ps1"
CMD_SCRIPT = REPO_ROOT / "scripts" / "start-backend.cmd"


def test_start_scripts_exist() -> None:
    assert SHELL_SCRIPT.exists()
    assert DEV_SHELL_SCRIPT.exists()
    assert POWERSHELL_SCRIPT.exists()
    assert CMD_SCRIPT.exists()


def test_shell_script_help_exits_successfully() -> None:
    result = subprocess.run(
        ["bash", str(SHELL_SCRIPT), "--help"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = result.stdout + result.stderr
    assert "Usage:" in output
    assert "--host" in output
    assert "--port" in output
    assert "--no-reload" in output


def test_shell_script_has_valid_bash_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(SHELL_SCRIPT)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_dev_shell_script_help_exits_successfully() -> None:
    result = subprocess.run(
        ["bash", str(DEV_SHELL_SCRIPT), "--help"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    output = result.stdout + result.stderr
    assert "Usage:" in output
    assert "--backend-port" in output
    assert "--frontend-port" in output
    assert "--no-reload" in output


def test_dev_shell_script_has_valid_bash_syntax() -> None:
    result = subprocess.run(
        ["bash", "-n", str(DEV_SHELL_SCRIPT)],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_dev_shell_script_starts_backend_and_frontend() -> None:
    content = DEV_SHELL_SCRIPT.read_text(encoding="utf-8")

    assert ".venv/bin/python" in content
    assert "-m uvicorn app.main:app" in content
    assert "--app-dir api" in content
    assert "-m http.server" in content
    assert "--directory \"$FRONTEND_DIR\"" in content
    assert "FRONTEND_PORT=\"${FRONTEND_PORT:-5173}\"" in content
    assert "trap cleanup EXIT INT TERM" in content
    assert "wait -n \"$BACKEND_PID\" \"$FRONTEND_PID\"" in content


def test_powershell_script_delegates_to_wsl() -> None:
    content = POWERSHELL_SCRIPT.read_text(encoding="utf-8")

    assert "wsl.exe" in content
    assert "start-backend.sh" in content
    assert "wsl.localhost" in content
    assert '[Alias("Host")]' in content
    assert "[string]$BackendHost" in content
    assert "[int]$Port" in content
    assert "[switch]$NoReload" in content


def test_powershell_script_handles_help_without_starting_backend() -> None:
    content = POWERSHELL_SCRIPT.read_text(encoding="utf-8")

    assert "[switch]$Help" in content
    assert "if ($Help)" in content
    assert "./scripts/start-backend.sh --help" in content


def test_cmd_script_runs_powershell_with_process_scoped_bypass() -> None:
    content = CMD_SCRIPT.read_text(encoding="utf-8")

    assert "powershell.exe" in content
    assert "-ExecutionPolicy Bypass" in content
    assert "start-backend.ps1" in content
    assert "%*" in content


def test_cmd_script_maps_help_flags_to_powershell_help_switch() -> None:
    content = CMD_SCRIPT.read_text(encoding="utf-8")

    assert '"%~1"=="--help"' in content
    assert '"%~1"=="-h"' in content
    assert "-Help" in content


def test_shell_script_launches_uvicorn_and_checks_virtualenv() -> None:
    content = SHELL_SCRIPT.read_text(encoding="utf-8")

    assert ".venv/bin/python" in content
    assert "if [[ ! -x \"$PYTHON_BIN\" ]]" in content
    assert "-m uvicorn app.main:app" in content
    assert "--app-dir api" in content
