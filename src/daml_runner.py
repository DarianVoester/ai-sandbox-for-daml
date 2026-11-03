"""Führt `daml build` / `daml test` isoliert aus und wertet die Ausgabe aus."""
import os
import re
import shutil
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import settings

_run_lock = threading.Lock()

_TEST_LINE = re.compile(r"^(?P<file>\S+\.daml):(?P<name>[A-Za-z_][\w']*): (?P<status>.+)$")
_CONTRACTS = re.compile(r"(\d+) active contracts")
_TRANSACTIONS = re.compile(r"(\d+) transactions")


@dataclass
class RunResult:
    command: str
    returncode: int | None
    output: str
    duration: float
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and self.returncode == 0


def _env() -> dict:
    env = os.environ.copy()
    daml_bin = str(Path.home() / ".daml" / "bin")
    env["PATH"] = daml_bin + os.pathsep + env.get("PATH", "")
    return env


def daml_executable() -> str | None:
    return shutil.which("daml", path=_env()["PATH"])


def daml_available() -> bool:
    return daml_executable() is not None


def sdk_version() -> str:
    try:
        match = re.search(r"^sdk-version:\s*(\S+)", settings.DAML_YAML.read_text(encoding="utf-8"), re.M)
        return match.group(1) if match else "unknown"
    except OSError:
        return "unknown"


def read_source() -> str:
    return settings.DAML_FILE.read_text(encoding="utf-8") if settings.DAML_FILE.exists() else ""


def write_source(text: str) -> None:
    settings.DAML_FILE.parent.mkdir(parents=True, exist_ok=True)
    settings.DAML_FILE.write_text(text, encoding="utf-8")


def run(command: str) -> RunResult:
    """Startet `daml <command>` (build|test) ohne Shell und mit Timeout."""
    if command not in settings.DAML_TIMEOUTS:
        raise ValueError(f"Unsupported daml command: {command}")
    exe = daml_executable()
    if exe is None:
        return RunResult(command, None, "", 0.0, error="'daml' binary not found in PATH.")
    if not _run_lock.acquire(blocking=False):
        return RunResult(command, None, "", 0.0, error="Another daml run is already in progress.")

    timeout = settings.DAML_TIMEOUTS[command]
    start = time.time()
    try:
        proc = subprocess.run(
            [exe, command],
            cwd=str(settings.WORKSPACE_DIR),
            env=_env(),
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        output = (proc.stdout + "\n" + proc.stderr).strip()
        return RunResult(command, proc.returncode, output, time.time() - start)
    except subprocess.TimeoutExpired:
        return RunResult(command, None, "", time.time() - start,
                         error=f"Timed out after {timeout}s while running 'daml {command}'.")
    except OSError as e:
        return RunResult(command, None, "", time.time() - start, error=str(e))
    finally:
        _run_lock.release()


def split_coverage(output: str) -> tuple[str, str]:
    """Trennt die eigentliche Ausgabe vom Coverage-Report."""
    main, sep, coverage = output.partition(settings.COVERAGE_MARKER)
    return main.strip(), (sep + coverage).strip() if sep else ""


def parse_test_summary(output: str) -> list[dict]:
    """Liest die Zeilen `file:script: ok, N active contracts, M transactions.` aus."""
    section = output.split(settings.TEST_SUMMARY_MARKER, 1)[-1] if settings.TEST_SUMMARY_MARKER in output else output
    rows = []
    for line in section.splitlines():
        match = _TEST_LINE.match(line.strip())
        if not match:
            continue
        status = match.group("status")
        contracts = _CONTRACTS.search(status)
        transactions = _TRANSACTIONS.search(status)
        rows.append({
            "Script": f"{match.group('file')}:{match.group('name')}",
            "Result": "ok" if status.startswith("ok") else status.rstrip("."),
            "Active contracts": int(contracts.group(1)) if contracts else None,
            "Transactions": int(transactions.group(1)) if transactions else None,
        })
    return rows


def trim_for_prompt(output: str) -> str:
    """Entfernt den Coverage-Report und begrenzt die Länge für den LLM-Prompt."""
    main, _ = split_coverage(output)
    if len(main) > settings.MAX_OUTPUT_CHARS:
        main = main[: settings.MAX_OUTPUT_CHARS] + "\n... [truncated]"
    return main
