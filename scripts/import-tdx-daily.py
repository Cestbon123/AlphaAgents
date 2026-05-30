#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPO_ROOT / "api"
if str(API_ROOT) not in sys.path:
    sys.path.insert(0, str(API_ROOT))

from app.local_data.importer import bootstrap_tdx_daily  # noqa: E402
from app.local_data.repository import LocalMarketRepository  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Import local TDX daily bars into SQLite.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap_parser = subparsers.add_parser("bootstrap", help="Import vipdoc daily .day files.")
    bootstrap_parser.add_argument("--tdx-root", required=True)
    bootstrap_parser.add_argument("--db", default="data/alphaagents.db")

    status_parser = subparsers.add_parser("status", help="Show local market data status.")
    status_parser.add_argument("--db", default="data/alphaagents.db")

    args = parser.parse_args()

    if args.command == "bootstrap":
        result = bootstrap_tdx_daily(tdx_root=args.tdx_root, db_path=args.db)
    else:
        result = LocalMarketRepository(args.db).status()

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
