from collections import Counter

from app.domain.enums import SelectionAction
from app.domain.models import OperationRecord, ReviewCase, SelectionResult
from app.repositories.memory import InMemoryAlphaAgentsRepository


class ReviewWorkflow:
    def __init__(self, repository: InMemoryAlphaAgentsRepository) -> None:
        self._repository = repository

    def run_daily_review(
        self,
        selection_results: list[SelectionResult] | None = None,
        operation_records: list[OperationRecord] | None = None,
    ) -> list[ReviewCase]:
        cases: list[ReviewCase] = []
        results = selection_results or self._repository.list_selection_results()
        operations = {
            _normalize_symbol(record.symbol): record
            for record in operation_records or []
        }

        for result in results:
            operation = operations.get(_normalize_symbol(result.stock.symbol))
            deviation = _deviation(result, operation)
            result_summary = (
                operation.result_summary
                if operation and operation.result_summary
                else result.core_reason
            )
            key_reason = operation.reason if operation and operation.reason else result.core_reason
            cases.append(
                ReviewCase(
                    symbol=result.stock.symbol,
                    name=operation.name if operation and operation.name else result.stock.name,
                    scenario="候选股",
                    system_conclusion=result.action.value,
                    user_action=operation.user_action if operation else "待用户复盘确认",
                    result_summary=result_summary,
                    deviation=deviation,
                    review_conclusion=_review_conclusion(result, operation),
                    key_reason=key_reason,
                    worth_depositing=_worth_depositing(result, operation, deviation),
                )
            )
        return cases

    def run_weekly_review(self) -> list[str]:
        cases = self.run_daily_review()
        return [
            f"本周可沉淀案例 {sum(1 for case in cases if case.worth_depositing)} 条",
            "专家判断有效性需要结合实际操作结果持续校验",
        ]
    @staticmethod
    def summarize_weekly_cases(cases: list[dict[str, object]]) -> dict[str, object]:
        deviation_counts = Counter(str(case.get("deviation", "")) for case in cases)
        conclusion_counts = Counter(str(case.get("review_conclusion", "")) for case in cases)
        depositable_cases = [case for case in cases if bool(case.get("worth_depositing"))]
        key_cases = sorted(
            depositable_cases or cases,
            key=lambda case: (
                str(case.get("review_date", "")),
                str(case.get("symbol", "")),
            ),
            reverse=True,
        )[:5]
        return {
            "case_count": len(cases),
            "depositable_count": len(depositable_cases),
            "deviation_counts": dict(deviation_counts),
            "conclusion_counts": dict(conclusion_counts),
            "key_cases": key_cases,
        }

    @staticmethod
    def weekly_summary_lines(summary: dict[str, object]) -> list[str]:
        deviation_counts = summary.get("deviation_counts", {})
        if isinstance(deviation_counts, dict) and deviation_counts:
            deviations = "，".join(
                f"{name} {count} 条" for name, count in deviation_counts.items()
            )
        else:
            deviations = "暂无偏差"
        case_count = summary.get("case_count", 0)
        depositable_count = summary.get("depositable_count", 0)
        return [
            f"本周复盘案例 {case_count} 条，可沉淀 {depositable_count} 条",
            f"偏差分布：{deviations}",
        ]


def _normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper()


def _deviation(result: SelectionResult, operation: OperationRecord | None) -> str:
    if operation is None:
        return "待用户复盘确认"

    user_action = operation.user_action
    if result.action == SelectionAction.BUY and "未" in user_action and "买" in user_action:
        return "该买未买"
    if result.action == SelectionAction.DROP and "买" in user_action and "未" not in user_action:
        return "逆系统结论操作"
    return "按系统执行"


def _review_conclusion(result: SelectionResult, operation: OperationRecord | None) -> str:
    if operation is None:
        return "待确认案例"
    if (
        result.action == SelectionAction.BUY
        and "未" in operation.user_action
        and "买" in operation.user_action
    ):
        return "错过机会"
    if result.action == SelectionAction.BUY:
        return "成功案例"
    return "观察案例"


def _worth_depositing(
    result: SelectionResult,
    operation: OperationRecord | None,
    deviation: str,
) -> bool:
    if result.action == SelectionAction.BUY:
        return True
    return operation is not None and deviation != "按系统执行"
