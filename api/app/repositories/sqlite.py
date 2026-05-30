import json
import sqlite3
from datetime import date
from pathlib import Path
from uuid import uuid4

from app.domain.enums import DepositionStatus, WorkflowType
from app.domain.models import WorkflowRun


class SQLiteWorkflowRepository:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)

    def save_selection_run(self, run: WorkflowRun, payload: dict[str, object]) -> None:
        self._ensure_schema()
        payload_json = json.dumps(payload, ensure_ascii=False)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO workflow_runs (
                    id,
                    workflow_type,
                    executed_at,
                    input_summary,
                    output_summary,
                    status,
                    payload_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run.id,
                    run.workflow_type.value,
                    run.executed_at.isoformat(),
                    run.input_summary,
                    run.output_summary,
                    run.status,
                    payload_json,
                ),
            )

    def get_latest_selection_run(self) -> dict[str, object] | None:
        self._ensure_schema()
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM workflow_runs
                WHERE workflow_type = ?
                ORDER BY executed_at DESC, rowid DESC
                LIMIT 1
                """,
                (WorkflowType.SELECTION.value,),
            ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def get_latest_selection_result_for_symbol(self, symbol: str) -> dict[str, object] | None:
        payload = self.get_latest_selection_run()
        if not payload:
            return None
        normalized_symbol = _normalize_symbol(symbol)
        for result in payload.get("results", []):
            if not isinstance(result, dict):
                continue
            stock = result.get("stock", {})
            if (
                isinstance(stock, dict)
                and _normalize_symbol(stock.get("symbol")) == normalized_symbol
            ):
                return result
        return None

    def save_positions(self, positions: list[dict[str, object]]) -> list[dict[str, object]]:
        self._ensure_schema()
        normalized_positions = [
            {
                "symbol": str(position["symbol"]).strip().upper(),
                "quantity": int(position["quantity"]),
                "cost_price": float(position["cost_price"]),
                "holding_days": int(position["holding_days"]),
            }
            for position in positions
        ]

        with sqlite3.connect(self.db_path) as connection:
            connection.execute("DELETE FROM portfolio_positions")
            connection.executemany(
                """
                INSERT INTO portfolio_positions (
                    sort_order,
                    symbol,
                    quantity,
                    cost_price,
                    holding_days
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                [
                    (
                        index,
                        position["symbol"],
                        position["quantity"],
                        position["cost_price"],
                        position["holding_days"],
                    )
                    for index, position in enumerate(normalized_positions)
                ],
            )

        return normalized_positions

    def list_positions(self) -> list[dict[str, object]]:
        self._ensure_schema()
        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT symbol, quantity, cost_price, holding_days
                FROM portfolio_positions
                ORDER BY sort_order ASC
                """
            ).fetchall()

        return [
            {
                "symbol": row[0],
                "quantity": row[1],
                "cost_price": row[2],
                "holding_days": row[3],
            }
            for row in rows
        ]

    def get_position_for_symbol(self, symbol: str) -> dict[str, object] | None:
        normalized_symbol = _normalize_symbol(symbol)
        for position in self.list_positions():
            if _normalize_symbol(position.get("symbol")) == normalized_symbol:
                return position
        return None

    def save_holding_results(
        self, results: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        self._ensure_schema()
        normalized_results = [_jsonable(result) for result in results]
        payload_json = json.dumps(normalized_results, ensure_ascii=False)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO holding_result_snapshots (
                    id,
                    payload_json,
                    updated_at
                )
                VALUES ('latest', ?, datetime('now'))
                ON CONFLICT(id) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    updated_at = datetime('now')
                """,
                (payload_json,),
            )
        return normalized_results

    def list_holding_results(self) -> list[dict[str, object]]:
        self._ensure_schema()
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT payload_json
                FROM holding_result_snapshots
                WHERE id = 'latest'
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return []
        return json.loads(row[0])

    def get_holding_result_for_symbol(self, symbol: str) -> dict[str, object] | None:
        normalized_symbol = _normalize_symbol(symbol)
        for result in self.list_holding_results():
            if not isinstance(result, dict):
                continue
            position = result.get("position", {})
            if (
                isinstance(position, dict)
                and _normalize_symbol(position.get("symbol")) == normalized_symbol
            ):
                return result
        return None

    def save_operation_records(
        self,
        operation_date: date | str,
        records: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        self._ensure_schema()
        operation_date_text = _date_text(operation_date)
        normalized_records = [
            {
                "operation_date": operation_date_text,
                "symbol": str(record["symbol"]).strip().upper(),
                "name": str(record.get("name", "")),
                "source": str(record.get("source", "manual")),
                "system_conclusion": str(record.get("system_conclusion", "")),
                "user_action": str(record["user_action"]),
                "reason": str(record.get("reason", "")),
                "result_summary": str(record.get("result_summary", "")),
            }
            for record in records
        ]

        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "DELETE FROM operation_records WHERE operation_date = ?",
                (operation_date_text,),
            )
            connection.executemany(
                """
                INSERT INTO operation_records (
                    operation_date,
                    sort_order,
                    symbol,
                    name,
                    source,
                    system_conclusion,
                    user_action,
                    reason,
                    result_summary
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        record["operation_date"],
                        index,
                        record["symbol"],
                        record["name"],
                        record["source"],
                        record["system_conclusion"],
                        record["user_action"],
                        record["reason"],
                        record["result_summary"],
                    )
                    for index, record in enumerate(normalized_records)
                ],
            )

        return normalized_records

    def list_operation_records(
        self, operation_date: date | str | None = None
    ) -> list[dict[str, object]]:
        self._ensure_schema()
        parameters: tuple[str, ...] = ()
        where_clause = ""
        if operation_date is not None:
            where_clause = "WHERE operation_date = ?"
            parameters = (_date_text(operation_date),)

        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    operation_date,
                    symbol,
                    name,
                    source,
                    system_conclusion,
                    user_action,
                    reason,
                    result_summary
                FROM operation_records
                {where_clause}
                ORDER BY operation_date ASC, sort_order ASC
                """,
                parameters,
            ).fetchall()

        return [
            {
                "operation_date": row[0],
                "symbol": row[1],
                "name": row[2],
                "source": row[3],
                "system_conclusion": row[4],
                "user_action": row[5],
                "reason": row[6],
                "result_summary": row[7],
            }
            for row in rows
        ]

    def list_operation_records_for_symbol(self, symbol: str) -> list[dict[str, object]]:
        normalized_symbol = _normalize_symbol(symbol)
        return [
            record
            for record in self.list_operation_records()
            if _normalize_symbol(record.get("symbol")) == normalized_symbol
        ]

    def append_operation_record(
        self,
        operation_date: date | str,
        record: dict[str, object],
    ) -> dict[str, object]:
        self._ensure_schema()
        operation_date_text = _date_text(operation_date)
        normalized_record = {
            "operation_date": operation_date_text,
            "symbol": _normalize_symbol(record["symbol"]),
            "name": str(record.get("name", "")),
            "source": str(record.get("source", "manual")),
            "system_conclusion": str(record.get("system_conclusion", "")),
            "user_action": str(record["user_action"]),
            "reason": str(record.get("reason", "")),
            "result_summary": str(record.get("result_summary", "")),
        }
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT COALESCE(MAX(sort_order), -1) + 1
                FROM operation_records
                WHERE operation_date = ?
                """,
                (operation_date_text,),
            ).fetchone()
            sort_order = int(row[0] or 0)
            connection.execute(
                """
                INSERT INTO operation_records (
                    operation_date,
                    sort_order,
                    symbol,
                    name,
                    source,
                    system_conclusion,
                    user_action,
                    reason,
                    result_summary
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_record["operation_date"],
                    sort_order,
                    normalized_record["symbol"],
                    normalized_record["name"],
                    normalized_record["source"],
                    normalized_record["system_conclusion"],
                    normalized_record["user_action"],
                    normalized_record["reason"],
                    normalized_record["result_summary"],
                ),
            )
        return normalized_record

    def save_review_cases(
        self,
        review_date: date | str,
        cases: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        self._ensure_schema()
        review_date_text = _date_text(review_date)
        normalized_cases = [
            _review_case(review_date_text, case)
            for case in cases
        ]

        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                "DELETE FROM review_cases WHERE review_date = ?",
                (review_date_text,),
            )
            connection.executemany(
                """
                INSERT INTO review_cases (
                    id,
                    review_date,
                    sort_order,
                    symbol,
                    name,
                    scenario,
                    system_conclusion,
                    user_action,
                    result_summary,
                    deviation,
                    review_conclusion,
                    key_reason,
                    worth_depositing
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        case["id"],
                        case["review_date"],
                        index,
                        case["symbol"],
                        case["name"],
                        case["scenario"],
                        case["system_conclusion"],
                        case["user_action"],
                        case["result_summary"],
                        case["deviation"],
                        case["review_conclusion"],
                        case["key_reason"],
                        1 if case["worth_depositing"] else 0,
                    )
                    for index, case in enumerate(normalized_cases)
                ],
            )

        return normalized_cases

    def list_review_cases(
        self, review_date: date | str | None = None
    ) -> list[dict[str, object]]:
        self._ensure_schema()
        parameters: tuple[str, ...] = ()
        where_clause = ""
        if review_date is not None:
            where_clause = "WHERE review_date = ?"
            parameters = (_date_text(review_date),)

        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT
                    id,
                    review_date,
                    symbol,
                    name,
                    scenario,
                    system_conclusion,
                    user_action,
                    result_summary,
                    deviation,
                    review_conclusion,
                    key_reason,
                    worth_depositing
                FROM review_cases
                {where_clause}
                ORDER BY review_date ASC, sort_order ASC
                """,
                parameters,
            ).fetchall()

        return [_review_case_from_row(row) for row in rows]

    def get_latest_review_cases(self) -> list[dict[str, object]]:
        self._ensure_schema()
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT review_date
                FROM review_cases
                ORDER BY review_date DESC, rowid DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return []
        return self.list_review_cases(row[0])

    def list_review_cases_for_symbol(self, symbol: str) -> list[dict[str, object]]:
        normalized_symbol = _normalize_symbol(symbol)
        return [
            review_case
            for review_case in self.list_review_cases()
            if _normalize_symbol(review_case.get("symbol")) == normalized_symbol
        ]

    def list_stock_cases(
        self,
        *,
        symbol: str | None = None,
        query: str = "",
        kind: str = "",
        status: str = "",
    ) -> list[dict[str, object]]:
        self._ensure_schema()
        normalized_symbol = _normalize_symbol(symbol) if symbol else ""
        normalized_query = query.strip().lower()
        normalized_kind = kind.strip()
        normalized_status = status.strip()
        cases: list[dict[str, object]] = []

        for review_case in self.list_review_cases():
            item = {
                "id": review_case["id"],
                "item_type": "review_case",
                "symbol": review_case["symbol"],
                "name": review_case["name"],
                "kind": review_case["review_conclusion"],
                "status": "待沉淀" if review_case["worth_depositing"] else "已复盘",
                "title": review_case["review_conclusion"],
                "content": review_case["key_reason"],
                "source": review_case["scenario"],
                "review_case_id": review_case["id"],
                "date": review_case["review_date"],
                "raw": review_case,
            }
            cases.append(item)

        for candidate in self.list_deposition_candidates():
            item = {
                "id": candidate["id"],
                "item_type": "deposition_candidate",
                "symbol": candidate["symbol"],
                "name": "",
                "kind": candidate["kind"],
                "status": candidate["status"],
                "title": candidate["title"],
                "content": candidate["content"],
                "source": candidate["source"],
                "review_case_id": candidate["review_case_id"],
                "date": "",
                "raw": candidate,
            }
            cases.append(item)

        return [
            item
            for item in cases
            if _stock_case_matches(
                item,
                symbol=normalized_symbol,
                query=normalized_query,
                kind=normalized_kind,
                status=normalized_status,
            )
        ]

    def append_review_case(
        self,
        review_date: date | str,
        review_case: dict[str, object],
    ) -> dict[str, object]:
        self._ensure_schema()
        review_date_text = _date_text(review_date)
        normalized_case = _review_case(review_date_text, review_case)
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT COALESCE(MAX(sort_order), -1) + 1
                FROM review_cases
                WHERE review_date = ?
                """,
                (review_date_text,),
            ).fetchone()
            sort_order = int(row[0] or 0)
            connection.execute(
                """
                INSERT INTO review_cases (
                    id,
                    review_date,
                    sort_order,
                    symbol,
                    name,
                    scenario,
                    system_conclusion,
                    user_action,
                    result_summary,
                    deviation,
                    review_conclusion,
                    key_reason,
                    worth_depositing
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    normalized_case["id"],
                    normalized_case["review_date"],
                    sort_order,
                    normalized_case["symbol"],
                    normalized_case["name"],
                    normalized_case["scenario"],
                    normalized_case["system_conclusion"],
                    normalized_case["user_action"],
                    normalized_case["result_summary"],
                    normalized_case["deviation"],
                    normalized_case["review_conclusion"],
                    normalized_case["key_reason"],
                    1 if normalized_case["worth_depositing"] else 0,
                ),
            )
        return normalized_case

    def save_deposition_candidates(
        self, candidates: list[dict[str, object]]
    ) -> list[dict[str, object]]:
        self._ensure_schema()
        normalized_candidates = [_deposition_candidate(candidate) for candidate in candidates]

        with sqlite3.connect(self.db_path) as connection:
            connection.executemany(
                """
                INSERT INTO deposition_candidates (
                    id,
                    symbol,
                    review_case_id,
                    kind,
                    title,
                    content,
                    source,
                    status,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                ON CONFLICT(id) DO UPDATE SET
                    symbol = excluded.symbol,
                    review_case_id = excluded.review_case_id,
                    kind = excluded.kind,
                    title = excluded.title,
                    content = excluded.content,
                    source = excluded.source,
                    status = excluded.status,
                    updated_at = datetime('now')
                """,
                [
                    (
                        candidate["id"],
                        candidate["symbol"],
                        candidate["review_case_id"],
                        candidate["kind"],
                        candidate["title"],
                        candidate["content"],
                        candidate["source"],
                        candidate["status"],
                    )
                    for candidate in normalized_candidates
                ],
            )

        return normalized_candidates

    def list_deposition_candidates(self) -> list[dict[str, object]]:
        self._ensure_schema()
        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT id, symbol, review_case_id, kind, title, content, source, status
                FROM deposition_candidates
                ORDER BY created_at ASC, rowid ASC
                """
            ).fetchall()

        return [_deposition_candidate_from_row(row) for row in rows]

    def list_confirmed_deposition_entries(self) -> list[dict[str, object]]:
        self._ensure_schema()
        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                """
                SELECT id, symbol, review_case_id, kind, title, content, source, status
                FROM deposition_candidates
                WHERE status = ?
                ORDER BY updated_at DESC, created_at DESC, rowid DESC
                """,
                (DepositionStatus.CONFIRMED.value,),
            ).fetchall()

        return [_deposition_candidate_from_row(row) for row in rows]

    def list_deposition_candidates_for_symbol(self, symbol: str) -> list[dict[str, object]]:
        normalized_symbol = _normalize_symbol(symbol)
        return [
            candidate
            for candidate in self.list_deposition_candidates()
            if _normalize_symbol(candidate.get("symbol"))
            == normalized_symbol
            or normalized_symbol in str(candidate.get("source", "")).upper()
        ]

    def save_stock_deposition_candidate(
        self,
        symbol: str,
        candidate: dict[str, object],
    ) -> dict[str, object]:
        normalized_candidate = _deposition_candidate(
            {
                **candidate,
                "id": str(candidate.get("id") or uuid4()),
                "symbol": _normalize_symbol(symbol),
                "review_case_id": str(candidate.get("review_case_id") or ""),
            }
        )
        return self.save_deposition_candidates([normalized_candidate])[0]

    def update_deposition_candidate(
        self, candidate_id: str, updates: dict[str, object]
    ) -> dict[str, object] | None:
        self._ensure_schema()
        allowed_updates = {
            key: value
            for key, value in updates.items()
            if key in {"title", "content", "status"} and value is not None
        }
        if "status" in allowed_updates:
            allowed_updates["status"] = DepositionStatus(str(allowed_updates["status"])).value
        if not allowed_updates:
            return self._get_deposition_candidate(candidate_id)

        assignments = ", ".join(f"{key} = ?" for key in allowed_updates)
        values = [str(value) for value in allowed_updates.values()]
        with sqlite3.connect(self.db_path) as connection:
            cursor = connection.execute(
                f"""
                UPDATE deposition_candidates
                SET {assignments}, updated_at = datetime('now')
                WHERE id = ?
                """,
                (*values, candidate_id),
            )
            if cursor.rowcount == 0:
                return None

        return self._get_deposition_candidate(candidate_id)

    def save_daily_report(self, report: dict[str, object]) -> dict[str, object]:
        self._ensure_schema()
        normalized_report = _daily_report(report)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO daily_reports (
                    report_date,
                    market_summary,
                    selection_summary,
                    holding_summary,
                    review_summary,
                    deposition_summary,
                    report_text,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                ON CONFLICT(report_date) DO UPDATE SET
                    market_summary = excluded.market_summary,
                    selection_summary = excluded.selection_summary,
                    holding_summary = excluded.holding_summary,
                    review_summary = excluded.review_summary,
                    deposition_summary = excluded.deposition_summary,
                    report_text = excluded.report_text,
                    updated_at = datetime('now')
                """,
                (
                    normalized_report["report_date"],
                    normalized_report["market_summary"],
                    normalized_report["selection_summary"],
                    normalized_report["holding_summary"],
                    normalized_report["review_summary"],
                    normalized_report["deposition_summary"],
                    normalized_report["report_text"],
                ),
            )
        return normalized_report

    def get_latest_daily_report(self) -> dict[str, object] | None:
        self._ensure_schema()
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT
                    report_date,
                    market_summary,
                    selection_summary,
                    holding_summary,
                    review_summary,
                    deposition_summary,
                    report_text
                FROM daily_reports
                ORDER BY report_date DESC, updated_at DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return _daily_report_from_row(row)

    def save_research_report(self, report: dict[str, object]) -> dict[str, object]:
        self._ensure_schema()
        normalized_report = _research_report(report)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO stock_research_reports (
                    symbol,
                    name,
                    generated_at,
                    final_decision,
                    final_reason,
                    payload_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                ON CONFLICT(symbol) DO UPDATE SET
                    name = excluded.name,
                    generated_at = excluded.generated_at,
                    final_decision = excluded.final_decision,
                    final_reason = excluded.final_reason,
                    payload_json = excluded.payload_json,
                    updated_at = datetime('now')
                """,
                (
                    normalized_report["symbol"],
                    normalized_report["name"],
                    normalized_report["generated_at"],
                    normalized_report["final_decision"],
                    normalized_report["final_reason"],
                    normalized_report["payload_json"],
                ),
            )
        return normalized_report["payload"]

    def get_latest_research_report(self, symbol: str | None = None) -> dict[str, object] | None:
        self._ensure_schema()
        with sqlite3.connect(self.db_path) as connection:
            if symbol:
                row = connection.execute(
                    """
                    SELECT payload_json
                    FROM stock_research_reports
                    WHERE symbol = ?
                    ORDER BY generated_at DESC, updated_at DESC
                    LIMIT 1
                    """,
                    (symbol,),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT payload_json
                    FROM stock_research_reports
                    ORDER BY generated_at DESC, updated_at DESC
                    LIMIT 1
                    """
                ).fetchone()
        if row is None:
            return None
        return json.loads(row[0])

    def list_research_reports(
        self,
        *,
        symbol: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        self._ensure_schema()
        normalized_symbol = _normalize_symbol(symbol) if symbol else ""
        safe_limit = max(1, min(limit, 200))
        parameters: tuple[object, ...]
        where_clause = ""
        if normalized_symbol:
            where_clause = "WHERE symbol = ?"
            parameters = (normalized_symbol, safe_limit)
        else:
            parameters = (safe_limit,)

        with sqlite3.connect(self.db_path) as connection:
            rows = connection.execute(
                f"""
                SELECT payload_json
                FROM stock_research_reports
                {where_clause}
                ORDER BY generated_at DESC, updated_at DESC
                LIMIT ?
                """,
                parameters,
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    def _get_deposition_candidate(self, candidate_id: str) -> dict[str, object] | None:
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT id, symbol, review_case_id, kind, title, content, source, status
                FROM deposition_candidates
                WHERE id = ?
                """,
                (candidate_id,),
            ).fetchone()
        if row is None:
            return None
        return _deposition_candidate_from_row(row)

    def get_tracking_state(self, symbol: str) -> dict[str, object]:
        self._ensure_schema()
        normalized_symbol = _normalize_symbol(symbol)
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT symbol, status, note, updated_at
                FROM stock_tracking_states
                WHERE symbol = ?
                LIMIT 1
                """,
                (normalized_symbol,),
            ).fetchone()
        if row is None:
            return {
                "symbol": normalized_symbol,
                "status": "观察",
                "note": "",
                "updated_at": "",
            }
        return {
            "symbol": row[0],
            "status": row[1],
            "note": row[2],
            "updated_at": row[3],
        }

    def save_tracking_state(
        self,
        symbol: str,
        status: str,
        note: str = "",
    ) -> dict[str, object]:
        self._ensure_schema()
        normalized_symbol = _normalize_symbol(symbol)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO stock_tracking_states (
                    symbol,
                    status,
                    note,
                    updated_at
                )
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(symbol) DO UPDATE SET
                    status = excluded.status,
                    note = excluded.note,
                    updated_at = datetime('now')
                """,
                (normalized_symbol, status, note),
            )
        return self.get_tracking_state(normalized_symbol)

    def get_strategy_config(self, strategy_id: str) -> dict[str, object] | None:
        self._ensure_schema()
        with sqlite3.connect(self.db_path) as connection:
            row = connection.execute(
                """
                SELECT strategy_id, enabled, params_json, updated_at
                FROM strategy_configs
                WHERE strategy_id = ?
                LIMIT 1
                """,
                (strategy_id,),
            ).fetchone()
        if row is None:
            return None
        return {
            "id": row[0],
            "enabled": bool(row[1]),
            "params": json.loads(row[2]),
            "updated_at": row[3],
        }

    def save_strategy_config(self, config: dict[str, object]) -> dict[str, object]:
        self._ensure_schema()
        strategy_id = str(config["id"])
        enabled = bool(config.get("enabled", True))
        params_json = json.dumps(config.get("params", {}), ensure_ascii=False)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                INSERT INTO strategy_configs (
                    strategy_id,
                    enabled,
                    params_json,
                    updated_at
                )
                VALUES (?, ?, ?, datetime('now'))
                ON CONFLICT(strategy_id) DO UPDATE SET
                    enabled = excluded.enabled,
                    params_json = excluded.params_json,
                    updated_at = datetime('now')
                """,
                (strategy_id, 1 if enabled else 0, params_json),
            )
        saved = self.get_strategy_config(strategy_id)
        return saved or {"id": strategy_id, "enabled": enabled, "params": config.get("params", {})}

    def _ensure_schema(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS workflow_runs (
                    id TEXT PRIMARY KEY,
                    workflow_type TEXT NOT NULL,
                    executed_at TEXT NOT NULL,
                    input_summary TEXT NOT NULL,
                    output_summary TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS portfolio_positions (
                    sort_order INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    cost_price REAL NOT NULL,
                    holding_days INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS holding_result_snapshots (
                    id TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS operation_records (
                    operation_date TEXT NOT NULL,
                    sort_order INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    source TEXT NOT NULL,
                    system_conclusion TEXT NOT NULL,
                    user_action TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    result_summary TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS review_cases (
                    id TEXT NOT NULL DEFAULT '',
                    review_date TEXT NOT NULL,
                    sort_order INTEGER NOT NULL,
                    symbol TEXT NOT NULL,
                    name TEXT NOT NULL,
                    scenario TEXT NOT NULL,
                    system_conclusion TEXT NOT NULL,
                    user_action TEXT NOT NULL,
                    result_summary TEXT NOT NULL,
                    deviation TEXT NOT NULL,
                    review_conclusion TEXT NOT NULL,
                    key_reason TEXT NOT NULL,
                    worth_depositing INTEGER NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS deposition_candidates (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL DEFAULT '',
                    review_case_id TEXT NOT NULL DEFAULT '',
                    kind TEXT NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_tracking_states (
                    symbol TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    note TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS daily_reports (
                    report_date TEXT PRIMARY KEY,
                    market_summary TEXT NOT NULL,
                    selection_summary TEXT NOT NULL,
                    holding_summary TEXT NOT NULL,
                    review_summary TEXT NOT NULL,
                    deposition_summary TEXT NOT NULL,
                    report_text TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            _ensure_column(connection, "review_cases", "id", "TEXT NOT NULL DEFAULT ''")
            _ensure_column(
                connection,
                "deposition_candidates",
                "symbol",
                "TEXT NOT NULL DEFAULT ''",
            )
            _ensure_column(
                connection,
                "deposition_candidates",
                "review_case_id",
                "TEXT NOT NULL DEFAULT ''",
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS stock_research_reports (
                    symbol TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    generated_at TEXT NOT NULL,
                    final_decision TEXT NOT NULL,
                    final_reason TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT (datetime('now')),
                    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS strategy_configs (
                    strategy_id TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL,
                    params_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )


def _date_text(value: date | str) -> str:
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _normalize_symbol(value: object) -> str:
    return str(value or "").strip().upper()


def _ensure_column(
    connection: sqlite3.Connection,
    table_name: str,
    column_name: str,
    definition: str,
) -> None:
    rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    existing_columns = {str(row[1]) for row in rows}
    if column_name not in existing_columns:
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")


def _stock_case_matches(
    item: dict[str, object],
    *,
    symbol: str,
    query: str,
    kind: str,
    status: str,
) -> bool:
    if symbol and _normalize_symbol(item.get("symbol")) != symbol:
        return False
    if kind and kind not in str(item.get("kind", "")):
        return False
    if status and status not in str(item.get("status", "")):
        return False
    if not query:
        return True
    searchable = " ".join(
        str(item.get(key, ""))
        for key in ("symbol", "name", "kind", "status", "title", "content", "source")
    ).lower()
    return query in searchable


def _jsonable(value: object) -> dict[str, object]:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    return dict(value)  # type: ignore[arg-type]


def _deposition_candidate(candidate: dict[str, object]) -> dict[str, object]:
    raw_candidate = (
        candidate.model_dump(mode="json") if hasattr(candidate, "model_dump") else candidate
    )
    return {
        "id": str(raw_candidate["id"]),
        "symbol": _normalize_symbol(raw_candidate.get("symbol")),
        "review_case_id": str(raw_candidate.get("review_case_id", "")),
        "kind": str(raw_candidate["kind"]),
        "title": str(raw_candidate["title"]),
        "content": str(raw_candidate["content"]),
        "source": str(raw_candidate["source"]),
        "status": DepositionStatus(str(raw_candidate["status"])).value,
    }


def _review_case(review_date: str, case: dict[str, object]) -> dict[str, object]:
    raw_case = case.model_dump(mode="json") if hasattr(case, "model_dump") else case
    return {
        "id": str(raw_case.get("id") or uuid4()),
        "review_date": review_date,
        "symbol": _normalize_symbol(raw_case["symbol"]),
        "name": str(raw_case["name"]),
        "scenario": str(raw_case["scenario"]),
        "system_conclusion": str(raw_case["system_conclusion"]),
        "user_action": str(raw_case["user_action"]),
        "result_summary": str(raw_case["result_summary"]),
        "deviation": str(raw_case["deviation"]),
        "review_conclusion": str(raw_case["review_conclusion"]),
        "key_reason": str(raw_case["key_reason"]),
        "worth_depositing": bool(raw_case["worth_depositing"]),
    }


def _review_case_from_row(row: sqlite3.Row | tuple[object, ...]) -> dict[str, object]:
    review_date = str(row[1])
    symbol = str(row[2])
    review_id = str(row[0] or f"{review_date}:{symbol}:{row[9]}")
    return {
        "id": review_id,
        "review_date": row[1],
        "symbol": row[2],
        "name": row[3],
        "scenario": row[4],
        "system_conclusion": row[5],
        "user_action": row[6],
        "result_summary": row[7],
        "deviation": row[8],
        "review_conclusion": row[9],
        "key_reason": row[10],
        "worth_depositing": bool(row[11]),
    }


def _deposition_candidate_from_row(row: sqlite3.Row | tuple[object, ...]) -> dict[str, object]:
    return {
        "id": row[0],
        "symbol": row[1],
        "review_case_id": row[2],
        "kind": row[3],
        "title": row[4],
        "content": row[5],
        "source": row[6],
        "status": row[7],
    }


def _daily_report(report: dict[str, object]) -> dict[str, object]:
    raw_report = report.model_dump(mode="json") if hasattr(report, "model_dump") else report
    return {
        "report_date": _date_text(raw_report["report_date"]),
        "market_summary": str(raw_report["market_summary"]),
        "selection_summary": str(raw_report["selection_summary"]),
        "holding_summary": str(raw_report["holding_summary"]),
        "review_summary": str(raw_report["review_summary"]),
        "deposition_summary": str(raw_report["deposition_summary"]),
        "report_text": str(raw_report.get("report_text", "")),
    }


def _daily_report_from_row(row: sqlite3.Row | tuple[object, ...]) -> dict[str, object]:
    return {
        "report_date": row[0],
        "market_summary": row[1],
        "selection_summary": row[2],
        "holding_summary": row[3],
        "review_summary": row[4],
        "deposition_summary": row[5],
        "report_text": row[6],
    }


def _research_report(report: dict[str, object]) -> dict[str, object]:
    payload = report.model_dump(mode="json") if hasattr(report, "model_dump") else report
    return {
        "symbol": str(payload["symbol"]),
        "name": str(payload["name"]),
        "generated_at": str(payload["generated_at"]),
        "final_decision": str(payload["final_decision"]),
        "final_reason": str(payload["final_reason"]),
        "payload_json": json.dumps(payload, ensure_ascii=False),
        "payload": payload,
    }
