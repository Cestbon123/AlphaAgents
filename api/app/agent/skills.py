"""AlphaAgents internal Skill registry.

Each Skill is a combination of existing tools organized around a user intent.
Skills are NOT Codex skills — they are AlphaAgents investment research capabilities.
"""

from __future__ import annotations

from dataclasses import dataclass

# ── Skill model ──

@dataclass(frozen=True)
class AgentSkill:
    """A named investment research capability that combines tools around a user intent."""

    id: str
    name: str
    description: str                          # one-line for user display
    intents: tuple[str, ...] = ()             # example user questions
    data_sources: tuple[str, ...] = ()        # local_market/workflow/agent_memory/external_cache
    tools: tuple[str, ...] = ()               # tool names from tools.py
    output_requirements: tuple[str, ...] = () # what the answer must cover
    risk_boundary: str = "只做投研分析，不输出交易指令。"  # standard boundary
    is_write: bool = False
    requires_confirmation: bool = False


# ── Base Skills ──

SKILL_DAILY_BRIEFING = AgentSkill(
    id="daily_briefing",
    name="今日摘要",
    description="汇总持仓风险、选股结果、日报和异常提醒。",
    intents=(
        "今天有什么值得关注",
        "今天持仓有没有风险",
        "今天选股结果怎么样",
    ),
    data_sources=("workflow", "local_market", "agent_memory"),
    tools=("get_daily_summary", "get_positions", "get_review_history"),
    output_requirements=(
        "持仓告警摘要",
        "新候选机会",
        "需要复盘的异常点",
        "数据缺口说明",
    ),
)

SKILL_STOCK_DIAGNOSIS = AgentSkill(
    id="stock_diagnosis",
    name="个股诊断",
    description="综合 K 线指标、提醒、历史记忆、估值、资金流等数据分析单只股票。",
    intents=(
        "帮我看一下",
        "有没有破位",
        "还能不能继续观察",
        "这只股现在什么情况",
    ),
    data_sources=("local_market", "workflow", "agent_memory", "external_cache"),
    tools=("get_stock_detail", "recall_memory", "get_fundamentals"),
    output_requirements=(
        "当前趋势状态（破位/趋势转弱/趋势保持）",
        "关键指标数值（收盘、多空线、短期趋势线）",
        "风险提醒",
        "与历史判断的关联",
        "数据依据（行情日期、工作台状态、记忆命中数）",
        "数据缺口说明",
        "后续观察点",
    ),
)

SKILL_STRATEGY_SELECTION = AgentSkill(
    id="strategy_selection",
    name="策略选股",
    description="运行当前知行趋势策略，解释筛选逻辑和命中原因。",
    intents=(
        "跑一下策略",
        "当前策略为什么选出这些股票",
        "策略条件是不是太宽",
    ),
    data_sources=("local_market", "workflow"),
    tools=("run_selection", "get_daily_summary"),
    output_requirements=(
        "当前策略条件摘要",
        "选股结果数量和典型命中",
        "典型命中原因和排除原因",
        "数据是否充足",
    ),
)

SKILL_HISTORY_REVIEW = AgentSkill(
    id="history_review",
    name="历史回顾",
    description="回顾过去对某只股票的判断、复盘结论和操作记录。",
    intents=(
        "我之前为什么放弃",
        "上次复盘这个票是什么结论",
        "我最近经常错过什么类型的机会",
    ),
    data_sources=("agent_memory", "workflow"),
    tools=("recall_memory", "get_review_history"),
    output_requirements=(
        "历史判断摘要",
        "时间和来源",
        "当时依据概要",
        "当前状态是否发生变化",
    ),
)

SKILL_REVIEW_DEPOSITION = AgentSkill(
    id="review_deposition",
    name="复盘沉淀",
    description="生成待确认的操作记录、复盘案例或更新股票印象。",
    intents=(
        "帮我记录这次复盘",
        "把这个判断沉淀成案例",
        "更新一下我对这只股票的印象",
    ),
    data_sources=("workflow", "agent_memory"),
    tools=("record_operation", "save_review", "update_tracking", "update_profile"),
    output_requirements=(
        "先输出待确认内容",
        "用户确认后再执行写入",
        "写入后说明保存位置",
    ),
    is_write=True,
    requires_confirmation=True,
)

# ── Registry ──

ALL_SKILLS: tuple[AgentSkill, ...] = (
    SKILL_DAILY_BRIEFING,
    SKILL_STOCK_DIAGNOSIS,
    SKILL_STRATEGY_SELECTION,
    SKILL_HISTORY_REVIEW,
    SKILL_REVIEW_DEPOSITION,
)


def get_skill(id: str) -> AgentSkill | None:
    for s in ALL_SKILLS:
        if s.id == id:
            return s
    return None


def get_skills_for_display() -> list[dict[str, str]]:
    """Return a lightweight list suitable for frontend and user-facing prompts."""
    return [
        {"id": s.id, "name": s.name, "description": s.description}
        for s in ALL_SKILLS
    ]


def select_skills(
    message: str, symbol: str | None = None, current_view: str | None = None
) -> list[str]:
    """Lightweight intent-based skill selector. Returns matched skill IDs."""
    msg = message.strip()
    selected = []

    # Rule-based matching
    stock_keywords = ("帮我看", "看一下", "这只", "那个票", "有没有破位", "还能不能")
    if symbol or any(kw in msg for kw in stock_keywords):
        selected.append("stock_diagnosis")

    if any(kw in msg for kw in ("今天", "今日", "最近", "有什么", "值得关注", "持仓", "风险")):
        selected.append("daily_briefing")

    if any(kw in msg for kw in ("策略", "选股", "跑一下", "筛选")):
        selected.append("strategy_selection")

    if any(kw in msg for kw in ("之前", "上次", "过去", "历史", "为什么", "那个时候", "当时")):
        selected.append("history_review")

    if any(kw in msg for kw in ("记录", "保存", "复盘", "沉淀", "更新一下")):
        selected.append("review_deposition")

    # If nothing matched, default to daily_briefing
    if not selected:
        selected.append("daily_briefing")

    return selected


def build_skill_prompt(selected_skills: list[str] | None = None) -> str:
    """Build a prompt section listing available skills for the system prompt."""
    skills_to_show = ALL_SKILLS
    if selected_skills:
        skills_to_show = tuple(s for s in ALL_SKILLS if s.id in selected_skills)

    lines = ["## 你可以使用以下技能帮助用户\n"]
    for i, s in enumerate(skills_to_show, 1):
        lines.append(f"{i}. **{s.name}**：{s.description}")
        if s.intents:
            examples = "、".join(f'"{x}"' for x in s.intents[:3])
            lines.append(f"   用户可以这样问：{examples}")
        lines.append(f"   使用工具：{'、'.join(s.tools)}")
        lines.append(f"   数据来源：{'、'.join(s.data_sources)}")
        if s.requires_confirmation:
            lines.append("   ⚠️ 写入型技能，必须先生成预览等用户确认后再执行")
        lines.append("")
    return "\n".join(lines)
