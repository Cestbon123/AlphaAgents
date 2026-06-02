# AlphaAgents Agent 化改造 — 规格文档

## 背景

当前 AlphaAgents 是一个功能完整的盘后投研工作台，具备：
- 通达信本地日线数据同步
- 知行趋势线选股策略（规则筛选 + LLM 评估）
- 个股工作台（K 线 + 提醒 + 操作记录 + 复盘 + 沉淀）
- 每日复盘 / 周复盘 / 结构化日报
- SQLite 持久化所有运行记录

但交互层是一个传统的手动仪表盘——用户在 4 个页面间导航、逐一点击按钮、LLM 仅被用作文本生成器。这不是 agent。

## 目标

将 AlphaAgents 从"手动仪表盘"改造为**对话式 agent 工作台**。LLM 从"文本生成器"升级为"编排决策层"：理解用户意图、调用已有后端能力、整合多来源信息、产出可执行结论。

## 非目标

- **不推倒重来。** 现有数据层、策略层、工作流层保持不变。
- **不做全自动交易或自动下单。** 始终是投研辅助工具。
- **不做在线行情或实时推送。** 保持离线数据 + 盘后分析的定位。
- **不做多用户、多账户、多策略市场。** 单人使用。
- **第一阶段不做复杂 agent 工作流（多 step 自主推理）。** 先用单轮对话 + function calling 验证价值。

---

## 架构设计

### 改造前（当前）

```
用户               前端（HTML/JS）           后端（FastAPI）
 │                   │                       │
 │  点击按钮 ──────→│                       │
 │                   │  fetch() ──────────→│
 │                   │                       │ 执行业务逻辑
 │                   │  ← JSON ────────────│
 │  ← 刷新页面内容 ──│                       │
```

LLM 仅作为业务逻辑中的一步被调用：`POST /workflows/selection/run` 内部调一次 LLM 生成评估文本。

### 改造后（目标）

```
用户                  前端                    后端
 │                     │                        │
 │  自然语言输入 ───→│                        │
 │                     │  POST /agent/chat ──→│
 │                     │    (带历史上下文)       │
 │                     │                        │  ┌─ LLM (编排层) ─┐
 │                     │                        │  │  理解意图       │
 │                     │                        │  │  决策调用工具    │
 │                     │                        │  │  整合结果       │
 │                     │                        │  └────────────────┘
 │                     │                        │     │ tool_choice
 │                     │                        │     ↓
 │                     │                        │  ┌─ 已有 API ────┐
 │                     │                        │  │ 选股 / 行情    │
 │                     │                        │  │ 持仓 / 提醒    │
 │                     │                        │  │ 复盘 / 日报    │
 │                     │                        │  └───────────────┘
 │                     │  ← SSE 流式响 ────────│
 │  ← 打字机效果 ←─│                        │
```

### 关键设计决策

1. **LLM 作为编排层，不替代业务逻辑。** 策略计算、数据查询等确定性操作仍由 Python 业务代码执行。LLM 决策"该调用哪个"、整合结果为自然语言。

2. **agent 不直接写数据库。** 写入操作（记录操作、保存复盘等）走现有 `POST /stocks/{symbol}/operations` 等端点，agent 只做查询和推荐。

3. **复用现有 API 作为 agent tools。** 把现有 FastAPI 端点包装为 LLM function definitions，不另建 agent 数据访问层。

---

## 可复用资产

| 层级 | 现有能力 | agent 中的角色 |
|------|----------|----------------|
| 数据层 | `GET /market/daily-bars` | tool: `get_daily_bars` |
| 数据层 | `GET /stocks/{symbol}/alerts` | tool: `get_alerts` |
| 策略层 | `GET /strategies` / `POST /workflows/selection/run` | tool: `run_selection` |
| 工作流 | `GET /portfolio/positions` | tool: `get_positions` |
| 工作流 | `GET /reports/daily/latest` | tool: `get_daily_report` |
| 工作流 | `GET /review/cases/latest` | tool: `get_review_cases` |
| 工作台 | `GET /stocks/{symbol}/workspace` | tool: `get_workspace` |
| 数据层 | `GET /market/sectors`, `GET /market/stocks` | tool: `search_stocks` |

---

## 已确认决策

| 决策 | 选择 | 说明 |
|------|------|------|
| Q1 入口 | **C: chat-first 主区域** | 看盘选股页改为对话驱动，图表/工作台/选股结果由对话联动弹出，保留直接看盘能力 |
| Q2 深度 | **Level C** | 问答 + 个股联动 + 记忆 + 执行操作 |
| Q3 后端 | **扩 FastAPI** | 新增 `POST /agent/chat` 端点，不拆服务 |
| Q4 存储 | **项目内 SQLite** | `alphaagents.db` 新增 agent 专属表，按 Hermes 设计分层记忆 |

---

## 记忆系统设计（参照 Hermes Agent）

参考 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 的记忆架构——核心思想是 **agent 主动管理记忆，不是被动日志**。分层设计：

### 记忆模型

| 层级 | 表名 | 存储内容 | 生命周期 | 写入方 |
|------|------|----------|----------|--------|
| **用户画像** | `agent_user_profile` | 投资偏好、风险偏好、关注板块、常用参数 | 永久，可演化 | agent 主动更新 |
| **决策记忆** | `agent_decision_memory` | 每次操作/复盘的关键结论（为什么买/卖/观望、结果如何） | 永久 | agent 从操作记录和复盘案例中提取 |
| **股票印象** | `agent_stock_impressions` | 对特定股票的累积判断（"破位已放弃""低位关注中""准备买入"） | 永久，可覆盖 | agent 根据你的操作和复盘更新 |
| **对话历史** | `agent_sessions` + `agent_messages` | 完整对话记录，支持 FTS5 全文搜索 | 保留 90 天 | 自动记录 |

### 设计原则

1. **Agent 主动提取，不被动存储。** 不是把每条消息 dump 进 DB。每次对话结束，agent 回顾对话内容，提取：这次用户表达了什么偏好？做了什么决策？对某只股票的看法改变了吗？

2. **分层召回。** 新对话开始时，agent 按优先级加载记忆：
   - 第一层：用户画像（永久载入 system prompt）
   - 第二层：当前关注的股票印象（按需搜索）
   - 第三层：相关历史决策（FTS5 搜索 + LLM 摘要）

3. **渐进式更新。** 用户说"我现在更喜欢保守一点"——agent 不是追加一条新记录，而是更新画像中的 `risk_preference` 字段。避免记忆膨胀。

4. **可解释。** 每一条决策记忆都带 `source` 字段——来自哪一天的操作记录或复盘案例。agent 引述记忆时可以给出依据。

### 记忆表结构草图

```sql
-- 用户画像：key-value 结构化存储
CREATE TABLE agent_user_profile (
    key TEXT PRIMARY KEY,          -- e.g. 'risk_preference', 'favorite_sectors'
    value TEXT NOT NULL,           -- JSON value
    updated_at TEXT NOT NULL,
    source TEXT                    -- 来自哪次对话
);

-- 决策记忆：每次操作/复盘的关键结论
CREATE TABLE agent_decision_memory (
    id TEXT PRIMARY KEY,
    symbol TEXT,                   -- 关联股票
    decision_date TEXT,            -- 决策日期
    decision_type TEXT,            -- 'buy', 'sell', 'watch', 'skip'
    conclusion TEXT,               -- 核心结论（1-2 句话）
    outcome TEXT,                  -- 后续结果（"涨了5%"/"继续跌"）
    source TEXT,                   -- 'operation_record', 'review_case'
    created_at TEXT NOT NULL
);

-- 股票印象：对单只股票的累积判断
CREATE TABLE agent_stock_impressions (
    symbol TEXT PRIMARY KEY,
    status TEXT,                   -- 'tracking', 'holding', 'broken', 'watching'
    impression TEXT,               -- 当前印象
    last_updated TEXT NOT NULL
);

-- 对话会话
CREATE TABLE agent_sessions (
    id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    summary TEXT                   -- agent 生成的对话摘要
);

-- 对话消息（含 FTS5 索引）
CREATE TABLE agent_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL REFERENCES agent_sessions(id),
    role TEXT NOT NULL,
    content TEXT,
    tool_calls TEXT,
    timestamp REAL NOT NULL
);

CREATE VIRTUAL TABLE agent_messages_fts USING fts5(content);
```

---

## 交互设计

### Chat-first 页面布局

```
┌─────────────────────────────────────────────────────────┐
│  顶部工具栏 [同步数据] [执行选股]                         │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─ Chat 区域 ──────────────────────────────────┐       │
│  │ agent: 📅 2026-05-31 盘前简报                 │       │
│  │ 🔴 000001 破位，收盘 15.10 < 多空线 15.20     │       │
│  │ ✅ 选股产生 8 个候选                            │       │
│  │                                                │       │
│  │ 你: 看看 000001                                 │       │
│  │                                                │       │
│  │ agent: [切换 K 线到 000001]                     │       │
│  │ 000001 今日破位。该股上次你标记「观察中」，      │       │
│  │ 5/20 复盘记录你判断「等待回踩多空线」。          │       │
│  │ 目前走势与你的判断一致，但已跌破支撑。           │       │
│  │                               [标记为重点跟踪]    │       │
│  └────────────────────────────────────────────────┘       │
│                                                         │
│  ┌─ 联动区域（随对话展开）──────────────────────┐        │
│  │  [K 线图 000001]  │  [工作台：提醒 + 操作]   │        │
│  └──────────────────────────────────────────────┘        │
│                                                         │
│  [输入框]                                            [发送]│
└─────────────────────────────────────────────────────────┘
```

### agent 可调用的 tools

| tool 名称 | 对应 API | 作用 |
|-----------|----------|------|
| `get_daily_summary` | 组合查询 | 今日持仓告警 + 选股结果 + 日报摘要 |
| `get_stock_detail` | `/stocks/{symbol}/workspace` + `/stocks/{symbol}/alerts` | 个股完整视图 |
| `search_stocks` | `/market/stocks` + `/market/sectors` | 搜索股票 |
| `run_selection` | `/workflows/selection/run` | 执行选股 |
| `get_positions` | `/portfolio/positions` | 查询持仓 |
| `get_review_history` | `/review/cases/latest` | 查询复盘记录 |
| `get_daily_report` | `/reports/daily/latest` | 查询日报 |
| `update_tracking` | `PATCH /stocks/{symbol}/tracking` | 更新跟踪状态 |
| `record_operation` | `POST /stocks/{symbol}/operations` | 记录操作 |
| `save_review` | `POST /stocks/{symbol}/reviews` | 保存复盘 |
| `recall_memory` | 内部 | 搜索历史决策和股票印象 |
| `update_profile` | 内部 | 更新用户画像 |

### 系统提示词模板

```
你是 AlphaAgents，一个个人 A 股投研助手。

## 你的能力
- 查询行情、选股结果、持仓告警
- 分析个股，读取 K 线指标和工作台数据
- 回顾历史操作和复盘记录
- 记录操作、保存复盘、更新跟踪状态

## 你的记忆
- 用户画像：{profile}
- 当前关注股票印象：{impressions}
- 相关历史决策：{decisions}

## 你的原则
- 给出结论时引用具体数据（收盘价、多空线数值）
- 提到历史判断时给出日期和来源
- 不确定时直接说不知道，不做模糊预测
- 你只辅助投研决策，不代替用户做买卖决定
```

---

## 技术决策与权衡

| 决策 | 选择 | 原因 |
|------|------|------|
| 后端架构 | 扩 FastAPI 单体 | 项目规模小，拆微服务增加运维负担无收益 |
| agent loop | 手动实现（非 LangChain） | 依赖少，透明，好调试 |
| 记忆存储 | SQLite FTS5 | Hermes 验证过的方案，与现有架构一致 |
| 消息传输 | SSE 流式 | 打字机效果，无需 WebSocket |
| LLM function calling | 手动定义 tools JSON | 不依赖框架，和现有 LLM 客户端统一 |
