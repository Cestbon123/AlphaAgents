#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from app.local_data.repository import LocalMarketRepository  # noqa: E402
from app.local_data.tdxquant_metadata import import_tdxquant_metadata  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import TdxQuant metadata JSON into the AlphaAgents local SQLite DB."
    )
    parser.add_argument("--input", required=True)
    parser.add_argument("--db", required=True)
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    repository = LocalMarketRepository(args.db)
    report = import_tdxquant_metadata(payload, repository)
    repository.record_import_run(
        source="tdxquant_metadata",
        status="success",
        tdx_root=str(payload.get("tdx_pyplugins", "")),
        imported_files=1,
        imported_bars=0,
        message=json.dumps(report, ensure_ascii=False),
    )
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
