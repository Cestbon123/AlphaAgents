# AlphaAgents Agent 能力基线开发文档

## 1. 文档目的

本文档基于 `docs/requirements/agent-capability-baseline.md`，用于指导下一阶段开发。

当前阶段不以新增孤立功能为目标，而是把已有数据、已有页面、已有后端能力统一纳入 Agent 工作流，让 AlphaAgents 从“带聊天框的投研系统”收敛为“能解释自己能力、能正确使用数据、能串联现有功能的投研 Agent”。

本文档解决三个工程问题：

1. Agent 如何识别用户意图，并选择合适的数据和工具。
2. 现有本地数据、a-stock-data、工作流数据和记忆数据如何进入 Chat 回答。
3. 后续新增 AlphaAgents 内部 Skill 时，应该按什么结构接入，而不是继续散落在页面或 prompt 中。

## 2. 开发原则

### 2.1 本阶段原则

- 不新增交易执行能力。
- 不引入新的数据供应商。
- 不重构现有行情、策略、工作流底层实现。
- 不新增复杂页面，只整理现有三栏界面中的 Agent 能力表达。
- 不把 Skill 做成插件市场，先做轻量注册表和清晰契约。
- 所有写入型操作必须先由用户明确确认。
- 所有涉及投研结论的回答必须说明数据依据、数据日期和数据缺口。

### 2.2 工程原则

- 优先复用已有 service、repository、endpoint 和前端组件。
- Agent 层只做编排，不重复实现业务计算。
- Tool 是底层函数能力，Skill 是面向用户意图的工作流说明。
- 数据、策略、推理、提醒、记忆保持分层。
- 每次改造都必须能用测试或静态检查验证。

## 3. 当前现状

### 3.1 后端现状

当前 Agent 相关代码位于：

- `api/app/agent/agent_loop.py`
- `api/app/agent/chat_endpoint.py`
- `api/app/agent/tools.py`
- `api/app/agent/memory_schema.py`
- `api/app/agent/memory_repository.py`
- `api/app/agent/memory_curator.py`

当前已具备：

- `POST /agent/chat` SSE 对话端点。
- `GET /agent/sessions` 会话列表。
- `GET /agent/sessions/{id}` 单会话查看。
- Agent memory 表结构和 FTS5 搜索。
- Agent tools 对已有 API/service 的封装。
- 对话结束后的记忆提取流程。
- 写入型工具确认保护。

当前不足：

- Tool 虽然存在，但缺少面向用户意图的 Skill 注册层。
- Agent 回答没有统一的数据依据输出格式。
- 用户不容易知道“我现在可以让 Agent 做什么”。
- 本地数据、外部缓存、工作流数据、记忆数据之间没有明确的数据选择规则落到代码。
- 前端历史会话、右侧投研面板、K 线联动和 Chat 的关系还需要进一步稳定。

### 3.2 前端现状

当前主要入口位于：

- `frontend/index.html`
- `frontend/scripts/api.js`
- `frontend/scripts/app.js`
- `frontend/scripts/chart.js`
- `frontend/styles/app.css`

当前已具备：

- ChatGPT 风格三栏布局。
- 左侧导航和历史会话列表。
- 中间 Chat 主区域。
- 右侧投研面板，包含 K 线、个股工作台、筛选结果。
- Chat SSE 事件解析。
- 工具结果触发 K 线联动。
- 个股提醒标签展示。

当前不足：

- Chat 中没有清晰展示当前可用 Skill。
- Tool 调用过程和数据来源对用户仍然偏隐形。
- 右侧面板的“当前上下文”还没有统一传回 Agent。
- 历史会话列表更像记录入口，还没有成为投研上下文入口。

## 4. 目标架构

本阶段目标架构分为五层：

```text
用户问题
  ↓
Intent/Skill Router
  ↓
Skill Definition
  ↓
Tool 调用与数据聚合
  ↓
可解释回答 + UI 联动 + 记忆沉淀
```

### 4.1 Intent/Skill Router

职责：

- 根据用户问题、当前页面 symbol、历史上下文，识别用户意图。
- 选择一个或多个内部 Skill。
- 为 Agent loop 提供可用 Skill 说明和工具选择约束。

本阶段不需要复杂模型分类器，可以先采用轻量规则加 LLM 自判断：

- 规则层识别明显股票代码、今日摘要、历史回顾、策略选股、复盘沉淀等场景。
- LLM system prompt 中注入 Skill 清单和使用规则。
- Tool 执行后由 Agent 输出统一数据依据。

### 4.2 Skill Definition

Skill 是 AlphaAgents 内部投研能力说明，不是 Codex 开发技能。

每个 Skill 必须定义：

```python
{
    "id": "stock_diagnosis",
    "name": "个股诊断",
    "description": "围绕单只股票汇总趋势、提醒、工作台记录和历史记忆。",
    "intents": ["帮我看一下 000001", "这只股有没有破位", "还能不能继续观察"],
    "data_sources": ["local_market", "workflow", "agent_memory", "external_cache"],
    "tools": ["get_daily_bars", "get_alerts", "get_workspace", "recall_memory"],
    "output_requirements": ["趋势状态", "风险提醒", "历史判断", "数据依据", "数据缺口"],
    "risk_boundary": "只做投研分析，不输出交易指令。",
}
```

### 4.3 Tool 调用层

Tool 继续放在 `api/app/agent/tools.py`，但需要补齐契约：

- 每个 Tool 声明数据来源。
- 每个 Tool 声明是否写入。
- 每个 Tool 声明是否需要确认。
- 每个 Tool 返回结构中包含 `data_source`、`as_of`、`warnings` 等元信息。

推荐统一返回结构：

```python
{
    "ok": True,
    "data": {},
    "meta": {
        "data_source": "local_market",
        "as_of": "2026-05-29",
        "warnings": [],
    },
}
```

不要求一次性改完全部 Tool，但新改造的 Tool 应逐步向该结构靠拢。

### 4.4 可解释回答层

Agent 最终回答必须包含三类信息：

- 结论：当前判断或摘要。
- 依据：使用了哪些数据、日期、关键字段。
- 边界：数据缺口、不确定性、不能做的事情。

推荐输出结构：

```text
结论：
- ...

依据：
- 本地日线：最新交易日 ...
- 工作流记录：...
- 历史记忆：...

需要注意：
- ...
```

### 4.5 UI 联动层

Chat 不应该孤立存在，应和三栏布局形成闭环：

- 左侧：历史会话和可用 Skill 入口。
- 中间：对话过程、工具调用状态、最终回答。
- 右侧：当前 symbol、K 线、个股工作台、筛选结果。

当 Agent 调用 `get_stock_detail`、`get_daily_bars`、`get_workspace` 等工具时，前端应同步右侧 symbol 和图表上下文。

## 5. 后端开发方案

### 5.1 新增 Skill 注册模块

建议新增：

- `api/app/agent/skills.py`

职责：

- 定义 Skill 数据结构。
- 注册当前基础 Skill。
- 提供 Skill 清单给 system prompt。
- 提供按用户问题和上下文匹配 Skill 的轻量方法。

初始 Skill：

- `daily_briefing`：今日摘要。
- `stock_diagnosis`：个股诊断。
- `strategy_selection`：策略选股。
- `history_review`：历史回顾。
- `review_deposition`：复盘沉淀。

第一版可以只做静态注册表，不需要数据库。

### 5.2 调整 AgentContext

建议在 `AgentContext` 中补充：

- `selected_skills`
- `current_view`
- `data_hints`

用途：

- `selected_skills`：本轮匹配到的 Skill。
- `current_view`：当前页面视图，例如 `chat`、`strategy`、`stock_workspace`。
- `data_hints`：前端传来的当前 symbol、选股结果、右侧面板状态等轻量上下文。

注意：

- 不要把大段 K 线数据直接塞入上下文。
- 大数据仍通过 Tool 查询。
- 前端只传“当前用户正在看什么”，不传完整业务数据。

### 5.3 强化 system prompt

`api/app/agent/agent_loop.py` 中的 system prompt 应从硬编码能力列表，逐步改为：

- 固定角色边界。
- 动态 Skill 清单。
- 当前页面上下文。
- 记忆摘要。
- 输出格式要求。
- 写入确认规则。

推荐拆分函数：

- `_build_system_prompt(context)`
- `_format_skill_prompt(skills)`
- `_format_data_policy_prompt()`
- `_format_output_policy_prompt()`

这样后续调整 Skill 不需要反复改主 prompt。

### 5.4 Tool 元数据改造

`AgentTool` 建议增加字段：

```python
@dataclass
class AgentTool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[..., Any]
    data_sources: tuple[str, ...] = ()
    is_write: bool = False
    requires_confirmation: bool = False
```

同时调整：

- `build_tools_for_llm()`：继续输出 OpenAI function calling 格式。
- `needs_confirmation()`：改为读取 `requires_confirmation`。
- 新增 `get_tool_metadata()`：给 Skill 和前端能力说明使用。

### 5.5 数据依据聚合

建议新增轻量聚合结构：

- `api/app/agent/evidence.py`

职责：

- 从 tool result 中提取 `data_source`、`as_of`、`warnings`。
- 在一个 Agent turn 内聚合数据依据。
- 将依据摘要注入最终回答前的上下文，或作为 SSE `evidence` 事件发给前端。

第一版可以不做复杂对象，只实现：

```python
class EvidenceCollector:
    def add_tool_result(self, tool_name: str, result: dict[str, Any]) -> None: ...
    def to_prompt_text(self) -> str: ...
    def to_event_payload(self) -> dict[str, Any]: ...
```

### 5.6 Chat Endpoint 上下文入参

`POST /agent/chat` 当前入参建议扩展：

```json
{
  "message": "...",
  "session_id": "...",
  "symbol": "000001.SZ",
  "current_view": "chat",
  "data_hints": {
    "right_panel_open": true,
    "active_section": "chart"
  }
}
```

要求：

- `symbol` 继续可选。
- `current_view` 只作为上下文提示，不影响权限。
- `data_hints` 必须限制字段，不能接受任意大对象。
- 后端必须忽略未知字段，避免前后端版本差异导致失败。

### 5.7 会话历史和记忆

当前会话历史已经能保存 tool call 和 tool result。

下一步重点：

- 会话列表展示 title、更新时间、最近 symbol。
- 单次会话恢复时，应恢复消息、tool 调用摘要和当前 symbol。
- `memory_curator` 只沉淀对后续有价值的信息，不保存普通闲聊。
- 记忆结果进入 prompt 时要控制长度和来源说明。

不要做：

- 不要把每轮完整对话都塞入长期记忆。
- 不要让记忆覆盖用户明确的新判断。
- 不要把模型推测当成事实记忆保存。

## 6. 前端开发方案

### 6.1 Chat 能力说明

左侧或 Chat 空状态应展示当前基础 Skill，而不是只展示 quick actions。

建议展示：

- 今日摘要。
- 个股诊断。
- 策略选股。
- 历史回顾。
- 复盘沉淀。

每个 Skill 只展示一句“能问什么”，不要堆实现细节。

### 6.2 SSE 事件展示

当前已有事件：

- `delta`
- `tool_start`
- `tool_result`
- `error`
- `done`

建议补充或规范：

- `skill_selected`：展示本轮识别到的 Skill。
- `evidence`：展示本轮使用的数据依据。
- `requires_confirmation`：展示写入操作确认提示。

界面要求：

- Tool 调用状态用紧凑文本或轻量状态条展示。
- 不把原始 JSON 直接暴露给普通用户。
- 错误信息要可读，保留技术细节到 console。

### 6.3 右侧面板上下文同步

当用户切换股票、点击筛选结果、打开个股工作台时，前端应维护一个统一上下文：

```js
const agentUiContext = {
  currentSymbol,
  currentView,
  rightPanelOpen,
  activeRightPanelSection,
};
```

发送 Chat 时带上该上下文。

注意：

- 不发送完整 K 线数组。
- 不发送完整筛选结果列表。
- 不依赖前端上下文做权限判断。

### 6.4 历史会话列表

历史会话列表应成为“投研上下文入口”。

第一阶段要求：

- 点击会话能恢复消息。
- 当前会话有高亮。
- 显示更新时间。
- 显示最近关联 symbol，若存在。

第二阶段再考虑：

- 按 symbol 过滤会话。
- 按 Skill 类型过滤会话。
- 会话标题自动生成。

### 6.5 UI 风格统一

本阶段 UI 修改只做统一，不做新视觉方向：

- 保持 A 股红涨绿跌语义。
- Chat、历史列表、右侧面板使用一致的字号和间距。
- Skill chip、tool 状态、数据依据块保持小而清晰。
- 避免卡片套卡片。
- 避免大面积装饰性渐变。
- 图表、工作台、筛选结果仍以信息密度和可扫描性优先。

## 7. 数据使用策略

### 7.1 数据源优先级

不同用户问题对应的数据源优先级：

| 用户问题 | 优先数据源 | 辅助数据源 |
| --- | --- | --- |
| 个股走势、破位、趋势 | 本地行情数据 | 工作台记录、记忆 |
| 当前持仓风险 | 工作流持仓 | 本地行情、提醒、记忆 |
| 今日摘要 | 持仓、提醒、日报、选股结果 | 记忆 |
| 策略选股 | 本地行情、策略配置 | 最新选股快照 |
| 历史判断 | Agent 记忆、复盘案例、操作记录 | 当前行情 |
| 基本面、新闻、公告 | a-stock-data/cache | 本地行情、记忆 |

### 7.2 数据缺失处理

Agent 必须明确说明：

- 本地行情库不可用。
- 个股日线不足。
- 外部缓存缺失。
- 未找到持仓或工作台记录。
- 未命中历史记忆。

不允许：

- 用模型常识补充缺失行情。
- 编造新闻、公告、资金流。
- 隐藏关键数据缺口。

### 7.3 数据日期

所有关键数据应尽量带日期：

- 行情：最新交易日。
- 日报：报告日期。
- 复盘：复盘日期。
- 记忆：创建或更新时间。
- 外部缓存：缓存时间或数据日期。

如果源数据没有日期，应在依据中说明“数据未提供日期”。

## 8. 分阶段实施计划

### 8.1 P0：Agent 能力可解释

目标：

- 用户能知道 Agent 有哪些基础 Skill。
- Agent 回答能说明用了哪些数据。
- 写入操作继续保持确认保护。

开发项：

1. 新增 `api/app/agent/skills.py` 静态 Skill 注册表。
2. 在 system prompt 中注入 Skill 清单和输出格式。
3. 给关键 Tool 结果补充 `meta.data_source`、`meta.as_of`、`meta.warnings`。
4. 增加 evidence 聚合，至少在最终回答中要求模型输出“依据”。
5. 前端展示基础 Skill 入口。
6. 前端展示工具调用的简洁状态。

验收：

- 问“你能做什么”时，Agent 用 Skill 视角回答。
- 问单只股票时，会优先查本地行情或工作台，而不是只靠模型回答。
- 回答中包含数据依据和缺口。
- 写入型问题仍先要求确认。

### 8.2 P1：现有功能串联

目标：

- Chat 与右侧投研面板形成稳定上下文闭环。
- 历史会话成为可恢复的投研上下文。
- 今日摘要、个股诊断、策略选股、历史回顾四个 Skill 可稳定触发。

开发项：

1. `POST /agent/chat` 支持 `current_view` 和受限 `data_hints`。
2. 前端维护统一 `agentUiContext`。
3. Tool 调用 `get_daily_bars`、`get_workspace`、`run_selection` 后触发右侧面板同步。
4. 会话列表展示最近 symbol 和更新时间。
5. 会话恢复后同步当前 symbol。
6. 为四个核心 Skill 增加后端单元测试或静态契约测试。

验收：

- 从筛选结果点股票后提问，Agent 知道当前 symbol。
- 从历史会话进入后，能恢复对话并继续追问。
- 跑策略后，Chat 能解释筛选结果和右侧列表。
- 历史回顾能引用记忆或复盘案例，并说明来源。

### 8.3 P2：记忆沉淀质量

目标：

- 记忆只保存有价值的投研信息。
- 用户可以理解 Agent 为什么记住某个结论。
- 复盘沉淀 Skill 成为长期学习入口。

开发项：

1. 调整 `memory_curator` 的保存规则。
2. 为记忆增加类型、symbol、来源会话、置信边界。
3. 前端在保存复盘或沉淀案例时，明确提示写入内容。
4. Chat 回答引用记忆时显示时间和来源。
5. 增加记忆提取测试，覆盖普通闲聊不沉淀、投研判断可沉淀。

验收：

- 闲聊不会污染记忆。
- 个股判断能形成可搜索记忆。
- 历史判断被引用时有日期和来源。
- 用户更新观点后，Agent 不继续强行使用旧观点。

## 9. 测试方案

### 9.1 后端测试

建议新增或扩展：

- `tests/test_agent_skills.py`
- `tests/test_agent_evidence.py`
- `tests/test_agent_loop.py`
- `tests/test_agent_memory.py`

重点覆盖：

- Skill 注册表完整性。
- 每个 Skill 至少有 id、name、description、tools、output_requirements。
- 写入 Tool 必须 requires_confirmation。
- Tool result 能被 evidence collector 提取。
- 历史 tool call 能被正确恢复。
- 数据缺失时返回 warning，不抛出未处理异常。

### 9.2 前端静态测试

继续使用现有静态 JS/HTML 测试方式，覆盖：

- Chat 不使用 `innerHTML` 渲染模型内容。
- `agentChat` 发送 current context。
- SSE error 和 requires_confirmation 能展示。
- 历史会话点击能调用 `getAgentSession`。
- Skill 入口存在且文案清晰。

### 9.3 手工验收脚本

建议每次 Agent 改造后手工验证：

1. 打开页面，确认三栏布局正常。
2. 问“你现在能帮我做什么”。
3. 输入一个股票代码，问“帮我看一下这只股”。
4. 问“今天有什么值得关注”。
5. 问“跑一下当前策略”。
6. 问“我之前怎么看这只股票”。
7. 尝试“帮我保存一条复盘”，确认 Agent 先请求确认。
8. 刷新页面，打开历史会话继续追问。

## 10. 风险与边界

### 10.1 主要风险

- Agent 过度依赖 LLM prompt，导致数据使用不稳定。
- Tool 返回结构不统一，导致回答依据难以聚合。
- 记忆沉淀过多，污染后续判断。
- 前端上下文和后端真实数据不一致。
- 用户误以为 Agent 在给交易指令。

### 10.2 控制方式

- 核心数据必须通过 Tool 获取。
- Tool 元数据逐步标准化。
- 写入操作统一确认。
- 回答模板中固定展示数据依据和缺口。
- 所有涉及交易的表述都限定为观察、风险、复盘、投研辅助。

## 11. 不做事项

本阶段明确不做：

- 自动交易。
- 自动调仓。
- 复杂多 Agent 协作。
- 新数据供应商接入。
- 新的大型页面。
- Skill 插件市场。
- 完整可视化编排器。
- 长周期异步任务调度。

这些事项只有在 Agent 基线稳定后再重新评估。

## 12. 完成定义

本阶段完成标准：

1. 用户能在 Chat 中明确知道 Agent 有哪些基础投研 Skill。
2. Agent 能基于当前 symbol 和用户问题选择合适数据源。
3. 关键回答包含结论、依据、数据缺口和风险边界。
4. 本地行情、工作流数据、Agent 记忆至少在核心场景中被实际使用。
5. Chat、历史会话、右侧投研面板能形成基本闭环。
6. 写入型能力必须经过确认。
7. 后端测试、前端静态检查、JS 语法检查通过。

## 13. 推荐开发顺序

建议按以下顺序推进：

1. 建立 `skills.py` 静态注册表。
2. 将 Skill 清单注入 Agent prompt。
3. 标准化关键 query tools 的返回 meta。
4. 增加 evidence collector。
5. 前端展示 Skill 和数据依据。
6. 扩展 Chat 请求上下文。
7. 串联右侧面板和历史会话。
8. 优化 memory curator。
9. 补齐测试。

这个顺序的核心是先让 Agent “说清楚自己能做什么、用了什么数据”，再逐步增强自动编排。
