from __future__ import annotations

from datetime import UTC, datetime

from app.domain.models import (
    ResearchAnalystReport,
    ResearchDecision,
    StockResearchContext,
    StockResearchReport,
)
from app.llm.client import LLMUnavailable, OpenAICompatibleClient
from app.workflows.research_prompts import (
    analyst_prompt,
    bear_prompt,
    bull_prompt,
    manager_prompt,
    risk_prompt,
)


class ResearchWorkflow:
    roles = [
        "技术分析专家",
        "资金面专家",
        "题材板块专家",
        "消息公告专家",
        "基本面专家",
        "多方研究员",
        "空方研究员",
        "风险审查员",
        "研究经理",
    ]

    def __init__(self, llm_client: OpenAICompatibleClient | None = None) -> None:
        self.llm_client = llm_client

    def run(self, context: StockResearchContext) -> StockResearchReport:
        if self.llm_client and self.llm_client.is_configured:
            try:
                return self._run_llm(context)
            except LLMUnavailable as exc:
                context.data_gaps = _unique(context.data_gaps + [f"llm: {exc}"])

        return self._run_deterministic_fallback(context)

    def _run_llm(self, context: StockResearchContext) -> StockResearchReport:
        if self.llm_client is None:
            raise LLMUnavailable("LLM client is not initialized")

        analyst_reports: list[ResearchAnalystReport] = []
        for role in self.roles[:5]:
            prompt = analyst_prompt(role, context)
            report_text = self.llm_client.complete(prompt)
            analyst_reports.append(_llm_report(role, prompt, report_text, context.data_gaps))

        prompt = bull_prompt(context, analyst_reports)
        report_text = self.llm_client.complete(prompt)
        analyst_reports.append(_llm_report("多方研究员", prompt, report_text, []))

        prompt = bear_prompt(context, analyst_reports)
        report_text = self.llm_client.complete(prompt)
        analyst_reports.append(_llm_report("空方研究员", prompt, report_text, context.data_gaps))

        prompt = risk_prompt(context, analyst_reports)
        report_text = self.llm_client.complete(prompt)
        analyst_reports.append(_llm_report("风险审查员", prompt, report_text, context.data_gaps))

        prompt = manager_prompt(context, analyst_reports)
        manager_text = self.llm_client.complete(prompt)
        manager = _llm_report("研究经理", prompt, manager_text, context.data_gaps)
        analyst_reports.append(manager)

        report = StockResearchReport(
            symbol=context.symbol,
            name=context.name,
            generated_at=datetime.now(UTC),
            context=context,
            analyst_reports=analyst_reports,
            final_decision=_decision_from_text(manager_text),
            final_reason=_first_sentence(manager_text),
            generation_mode="llm_tradingagents_style",
            risk_flags=_collect_risks(context, analyst_reports),
            data_gaps=_collect_gaps(context, analyst_reports),
        )
        report.report_text = _render_llm_report_text(report)
        return report

    def _run_deterministic_fallback(self, context: StockResearchContext) -> StockResearchReport:
        analyst_reports = [
            self._technical_analyst(context),
            self._funds_analyst(context),
            self._theme_analyst(context),
            self._news_analyst(context),
            self._fundamental_analyst(context),
        ]
        analyst_reports.append(self._bull_researcher(context, analyst_reports))
        analyst_reports.append(self._bear_researcher(context, analyst_reports))
        analyst_reports.append(self._risk_reviewer(context, analyst_reports))
        manager = self._research_manager(context, analyst_reports)
        analyst_reports.append(manager)

        report = StockResearchReport(
            symbol=context.symbol,
            name=context.name,
            generated_at=datetime.now(UTC),
            context=context,
            analyst_reports=analyst_reports,
            final_decision=_decision_from_manager(manager),
            final_reason=manager.summary,
            generation_mode="deterministic_fallback",
            risk_flags=_collect_risks(context, analyst_reports),
            data_gaps=_collect_gaps(context, analyst_reports),
        )
        report.report_text = _render_report_text(report)
        return report

    def _technical_analyst(self, context: StockResearchContext) -> ResearchAnalystReport:
        prompt = analyst_prompt("技术分析专家", context)
        bullish: list[str] = []
        bearish: list[str] = []
        if (
            "命中知行趋势线候选条件" in context.technical_summary
            and "未命中知行趋势线候选条件" not in context.technical_summary
        ):
            bullish.append("知行趋势线条件形成共振")
        if context.change_pct is not None and context.change_pct > 3:
            bullish.append("最近交易日涨幅偏强")
        if context.change_pct is not None and context.change_pct < -3:
            bearish.append("最近交易日回撤较大")
        if not bullish:
            bearish.append("技术面暂未给出强确认")
        summary = (
            f"{context.technical_summary}。本地规则回退只能做指标归纳，"
            "若要生成 TradingAgents 风格深度技术报告，请配置 LLM。"
        )
        return ResearchAnalystReport(
            role="技术分析专家",
            summary=summary,
            report_text=_fallback_analyst_text(
                "技术分析专家", summary, [context.technical_summary], bullish, bearish
            ),
            prompt=prompt,
            evidence=[context.technical_summary],
            bullish_points=bullish,
            bearish_points=bearish,
            confidence=0.62 if bullish else 0.42,
            data_gaps=[gap for gap in context.data_gaps if "daily" in gap],
        )

    def _funds_analyst(self, context: StockResearchContext) -> ResearchAnalystReport:
        prompt = analyst_prompt("资金面专家", context)
        flow = context.supplement.money_flow
        main_inflow = flow.get("main_net_inflow")
        bullish: list[str] = []
        bearish: list[str] = []
        if isinstance(main_inflow, int | float) and main_inflow > 0:
            bullish.append(f"主力资金净流入 {main_inflow:.0f}")
        elif isinstance(main_inflow, int | float) and main_inflow < 0:
            bearish.append(f"主力资金净流出 {abs(main_inflow):.0f}")
        if context.supplement.dragon_tiger:
            bullish.append("存在龙虎榜席位记录，可继续拆解席位质量")
        if not bullish and not bearish:
            bearish.append("资金流与龙虎榜数据不足，无法确认短线承接")
        evidence = _dict_evidence(flow, ["trade_date", "main_net_inflow"]) + [
            f"龙虎榜记录 {len(context.supplement.dragon_tiger)} 条"
        ]
        summary = (
            "资金面分析重点看主力净流、席位质量和放量承接，"
            "目前证据强度取决于补充数据是否可用。"
        )
        return ResearchAnalystReport(
            role="资金面专家",
            summary=summary,
            report_text=_fallback_analyst_text("资金面专家", summary, evidence, bullish, bearish),
            prompt=prompt,
            evidence=evidence,
            bullish_points=bullish,
            bearish_points=bearish,
            confidence=0.68 if bullish else 0.32,
            data_gaps=[gap for gap in context.data_gaps if "money_flow" in gap or "dragon" in gap],
        )

    def _theme_analyst(self, context: StockResearchContext) -> ResearchAnalystReport:
        prompt = analyst_prompt("题材板块专家", context)
        sector_names = [str(item.get("sector_name", "")) for item in context.sectors]
        bullish = [f"题材/板块标签：{'、'.join(sector_names[:5])}"] if sector_names else []
        bearish = [] if bullish else ["题材归因不足，难以判断主线强度"]
        summary = "题材板块分析用于判断个股是否处于可持续主线，以及板块是否能解释价格行为。"
        return ResearchAnalystReport(
            role="题材板块专家",
            summary=summary,
            report_text=_fallback_analyst_text(
                "题材板块专家", summary, bullish or ["暂无可用题材标签"], bullish, bearish
            ),
            prompt=prompt,
            evidence=bullish or ["暂无可用题材标签"],
            bullish_points=bullish,
            bearish_points=bearish,
            confidence=0.65 if bullish else 0.3,
            data_gaps=[gap for gap in context.data_gaps if "sector" in gap],
        )

    def _news_analyst(self, context: StockResearchContext) -> ResearchAnalystReport:
        prompt = analyst_prompt("消息公告专家", context)
        news_count = len(context.supplement.news)
        announcement_count = len(context.supplement.announcements)
        evidence = [f"新闻 {news_count} 条", f"公告 {announcement_count} 条"]
        bullish = ["存在可进一步阅读的消息材料"] if news_count or announcement_count else []
        bearish = [] if bullish else ["缺少近期消息材料，消息面无法支持结论"]
        summary = "消息公告分析用于寻找催化、风险提示和事实变化；缺数据时应降低所有消息面结论权重。"
        return ResearchAnalystReport(
            role="消息公告专家",
            summary=summary,
            report_text=_fallback_analyst_text("消息公告专家", summary, evidence, bullish, bearish),
            prompt=prompt,
            evidence=evidence,
            bullish_points=bullish,
            bearish_points=bearish,
            confidence=0.58 if bullish else 0.28,
            data_gaps=[
                gap for gap in context.data_gaps if "announcements" in gap or "news" in gap
            ],
        )

    def _fundamental_analyst(self, context: StockResearchContext) -> ResearchAnalystReport:
        prompt = analyst_prompt("基本面专家", context)
        valuation = context.supplement.valuation
        evidence = _dict_evidence(valuation, ["pe_ttm", "pb", "market_cap", "turnover_rate"])
        risk_flags: list[str] = []
        pe = valuation.get("pe_ttm")
        if isinstance(pe, int | float) and pe > 80:
            risk_flags.append("估值偏高")
        bullish = [] if risk_flags else ["暂无估值异常风险标记"]
        bearish = risk_flags or ["财务深度数据不足，不能形成基本面强结论"]
        summary = "基本面分析当前只覆盖估值、市值、换手等轻量字段，财报质量和盈利趋势仍需补充。"
        return ResearchAnalystReport(
            role="基本面专家",
            summary=summary,
            report_text=_fallback_analyst_text(
                "基本面专家", summary, evidence or ["估值数据缺失"], bullish, bearish
            ),
            prompt=prompt,
            evidence=evidence or ["估值数据缺失"],
            bullish_points=bullish,
            bearish_points=bearish,
            risk_flags=risk_flags,
            confidence=0.55 if valuation else 0.25,
            data_gaps=[gap for gap in context.data_gaps if "valuation" in gap],
        )

    def _bull_researcher(
        self, context: StockResearchContext, reports: list[ResearchAnalystReport]
    ) -> ResearchAnalystReport:
        prompt = bull_prompt(context, reports)
        points = [point for report in reports for point in report.bullish_points]
        summary = f"多方观点聚焦 {context.name} 的技术、资金、题材正反馈，并尝试反驳空方担忧。"
        return ResearchAnalystReport(
            role="多方研究员",
            summary=summary,
            report_text=_fallback_analyst_text("多方研究员", summary, points[:6], points[:6], []),
            prompt=prompt,
            evidence=points[:6],
            bullish_points=points[:6],
            confidence=min(0.85, 0.35 + len(points) * 0.08),
        )

    def _bear_researcher(
        self, context: StockResearchContext, reports: list[ResearchAnalystReport]
    ) -> ResearchAnalystReport:
        prompt = bear_prompt(context, reports)
        points = [point for report in reports for point in report.bearish_points]
        summary = f"空方观点聚焦 {context.name} 的反证、数据缺口和可能的误判来源。"
        return ResearchAnalystReport(
            role="空方研究员",
            summary=summary,
            report_text=_fallback_analyst_text("空方研究员", summary, points[:6], [], points[:6]),
            prompt=prompt,
            evidence=points[:6],
            bearish_points=points[:6],
            confidence=min(0.85, 0.35 + len(points) * 0.08),
            data_gaps=context.data_gaps,
        )

    def _risk_reviewer(
        self, context: StockResearchContext, reports: list[ResearchAnalystReport]
    ) -> ResearchAnalystReport:
        prompt = risk_prompt(context, reports)
        risk_flags = _unique([flag for report in reports for flag in report.risk_flags])
        risk_flags = _unique(risk_flags + context.risk_flags)
        summary = "风险审查确认报告仅作为研究辅助，并标记数据缺口、证据不足和越界风险。"
        return ResearchAnalystReport(
            role="风险审查员",
            summary=summary,
            report_text=_fallback_analyst_text(
                "风险审查员", summary, risk_flags + context.data_gaps[:8], [], risk_flags
            ),
            prompt=prompt,
            evidence=risk_flags + context.data_gaps[:8],
            bearish_points=risk_flags,
            risk_flags=risk_flags,
            confidence=0.7,
            data_gaps=context.data_gaps,
        )

    def _research_manager(
        self, context: StockResearchContext, reports: list[ResearchAnalystReport]
    ) -> ResearchAnalystReport:
        prompt = manager_prompt(context, reports)
        bullish_count = sum(len(report.bullish_points) for report in reports)
        bearish_count = sum(len(report.bearish_points) for report in reports)
        if bullish_count >= 5 and bearish_count <= 2:
            summary = "正向证据较多，建议纳入重点跟踪池，等待后续复盘确认。"
        elif bullish_count >= 3:
            summary = "存在部分正向证据，但反证和数据缺口仍需观察。"
        elif bullish_count >= 1:
            summary = "证据强度不足，适合暂不跟踪或仅做低频观察。"
        else:
            summary = "缺少有效正向证据，建议放弃本轮研究跟踪。"
        evidence = [f"正向证据 {bullish_count} 条", f"反向证据 {bearish_count} 条"]
        return ResearchAnalystReport(
            role="研究经理",
            summary=summary,
            report_text=_fallback_analyst_text("研究经理", summary, evidence, [], []),
            prompt=prompt,
            evidence=evidence,
            confidence=0.74,
            data_gaps=context.data_gaps,
        )


def _llm_report(
    role: str,
    prompt: str,
    report_text: str,
    data_gaps: list[str],
) -> ResearchAnalystReport:
    return ResearchAnalystReport(
        role=role,
        summary=_first_sentence(report_text),
        report_text=report_text,
        prompt=prompt,
        evidence=[_first_sentence(report_text)],
        confidence=0.8,
        data_gaps=data_gaps,
    )


def _decision_from_manager(manager: ResearchAnalystReport) -> ResearchDecision:
    return _decision_from_text(manager.summary)


def _decision_from_text(text: str) -> ResearchDecision:
    for decision in ("重点跟踪", "观察", "暂不跟踪", "放弃"):
        if decision in text:
            return decision  # type: ignore[return-value]
    return "观察"


def _render_llm_report_text(report: StockResearchReport) -> str:
    lines = [
        f"# {report.name}（{report.symbol}）TradingAgents 风格多专家研究报告",
        "",
        f"生成模式：{report.generation_mode}",
        f"最终结论：{report.final_decision}",
        f"核心理由：{report.final_reason}",
        "",
    ]
    for analyst in report.analyst_reports:
        lines.extend([f"## {analyst.role}", analyst.report_text or analyst.summary, ""])
    lines.extend(_risk_footer(report))
    return "\n".join(lines)


def _render_report_text(report: StockResearchReport) -> str:
    lines = [
        f"# {report.name}（{report.symbol}）多专家研究报告",
        "",
        "生成模式：本地规则回退（未启用 LLM，报告不是 TradingAgents 原项目级别的模型分析）",
        f"结论：{report.final_decision}",
        f"理由：{report.final_reason}",
        "",
        "## 专家意见",
    ]
    for analyst in report.analyst_reports:
        lines.extend([f"### {analyst.role}", analyst.report_text or analyst.summary, ""])
    lines.extend(_risk_footer(report))
    return "\n".join(lines)


def _risk_footer(report: StockResearchReport) -> list[str]:
    return [
        "## 风险与边界",
        f"风险：{'；'.join(report.risk_flags) if report.risk_flags else '暂无明确风险标记'}",
        f"数据缺口：{'；'.join(report.data_gaps) if report.data_gaps else '暂无'}",
        "",
        "说明：本报告仅用于投研、复盘、分析和决策辅助，不构成交易指令。",
    ]


def _fallback_analyst_text(
    role: str,
    summary: str,
    evidence: list[str],
    bullish: list[str],
    bearish: list[str],
) -> str:
    return "\n".join(
        [
            f"**{role}结论**：{summary}",
            "",
            f"- 证据：{'；'.join(evidence) if evidence else '无'}",
            f"- 正向：{'；'.join(bullish) if bullish else '无'}",
            f"- 反向：{'；'.join(bearish) if bearish else '无'}",
            "",
            "| 观察点 | 证据 | 解释 | 风险 |",
            "| --- | --- | --- | --- |",
            (
                f"| {role} | {'；'.join(evidence[:2]) if evidence else '无'} | "
                "本地规则归纳 | 需要 LLM 与补充数据增强 |"
            ),
        ]
    )


def _collect_risks(
    context: StockResearchContext, reports: list[ResearchAnalystReport]
) -> list[str]:
    return _unique([flag for report in reports for flag in report.risk_flags] + context.risk_flags)


def _collect_gaps(
    context: StockResearchContext, reports: list[ResearchAnalystReport]
) -> list[str]:
    return _unique([gap for report in reports for gap in report.data_gaps] + context.data_gaps)


def _dict_evidence(payload: dict[str, object], keys: list[str]) -> list[str]:
    return [
        f"{key}={payload[key]}"
        for key in keys
        if key in payload and payload[key] not in (None, "")
    ]


def _first_sentence(text: str) -> str:
    for line in text.splitlines():
        cleaned = line.strip().lstrip("#").strip()
        if cleaned:
            return cleaned[:240]
    return ""


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))
