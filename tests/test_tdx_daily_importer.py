import struct
import subprocess
import sys

from app.local_data.importer import bootstrap_tdx_daily
from app.local_data.repository import LocalMarketRepository


def _record() -> bytes:
    return struct.pack("<IIIIIfII", 20260506, 100, 200, 50, 150, 123.0, 456, 0)


def test_bootstrap_imports_tdx_day_files_and_records_import_run(tmp_path):
    tdx_root = tmp_path / "new_tdx_mock"
    lday = tdx_root / "vipdoc" / "sz" / "lday"
    lday.mkdir(parents=True)
    (lday / "sz000001.day").write_bytes(_record())
    db_path = tmp_path / "alphaagents.db"

    summary = bootstrap_tdx_daily(tdx_root=tdx_root, db_path=db_path)

    repository = LocalMarketRepository(db_path)
    bars = repository.get_daily_bars("000001.SZ", limit=10)
    status = repository.status()
    assert summary["status"] == "success"
    assert summary["total_files"] == 1
    assert summary["imported_files"] == 1
    assert summary["imported_bars"] == 1
    assert bars[0]["time"] == "2026-05-06"
    assert bars[0]["close"] == 1.5
    assert status["latest_import_run"]["status"] == "success"


def test_import_tdx_daily_status_handles_uninitialized_db(tmp_path):
    db_path = tmp_path / "alphaagents.db"
    db_path.write_bytes(b"")

    result = subprocess.run(
        [sys.executable, "scripts/import-tdx-daily.py", "status", "--db", str(db_path)],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert '"bar_count": 0' in result.stdout
    assert "uninitialized" in result.stdout
