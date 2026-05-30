from pathlib import Path
from typing import Any

from app.local_data.repository import LocalMarketRepository
from app.local_data.tdx_security import parse_tdx_security_directory
from app.local_data.tdx_day import parse_tdx_day_file, symbol_from_tdx_day_path


def bootstrap_tdx_daily(tdx_root: str | Path, db_path: str | Path) -> dict[str, Any]:
    root = Path(tdx_root)
    repository = LocalMarketRepository(db_path)
    repository.initialize_schema()

    day_files = _iter_day_files(root)
    imported_files = 0
    imported_bars = 0
    imported_security_metadata = 0
    status = "success"
    message = ""

    try:
        imported_security_metadata = repository.upsert_security_metadata(
            parse_tdx_security_directory(root)
        )
        for file_path in day_files:
            symbol = symbol_from_tdx_day_path(file_path)
            bars = parse_tdx_day_file(file_path)
            imported_bars += repository.upsert_daily_bars(symbol, bars)
            imported_files += 1
        if imported_files == 0:
            message = f"No TDX .day files found under {root}"
    except Exception as exc:
        status = "failed"
        message = str(exc)
        raise
    finally:
        repository.record_import_run(
            source="tdx",
            status=status,
            tdx_root=str(root),
            imported_files=imported_files,
            imported_bars=imported_bars,
            message=message or f"security_metadata={imported_security_metadata}",
        )

    return {
        "status": status,
        "tdx_root": str(root),
        "db_path": str(db_path),
        "total_files": len(day_files),
        "imported_files": imported_files,
        "imported_bars": imported_bars,
        "imported_security_metadata": imported_security_metadata,
        "message": message,
    }


def count_tdx_day_files(tdx_root: str | Path) -> int:
    return len(_iter_day_files(Path(tdx_root)))


def _iter_day_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for market in ("sh", "sz", "bj"):
        files.extend(sorted((root / "vipdoc" / market / "lday").glob(f"{market}*.day")))
    return files
