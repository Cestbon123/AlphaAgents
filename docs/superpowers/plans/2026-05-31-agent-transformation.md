# AlphaAgents Agent 化改造 — 实施计划

> **Goal:** 将 AlphaAgents 从"手动仪表盘"改造为"对话式 agent 工作台"
> **Architecture:** 在现有 FastAPI + SQLite + 纯前端基础上，新增 Agent 编排层
> **Tech Stack:** FastAPI、SQLite（FTS5）、Python（手动 agent loop）、原生 HTML/CSS/JS、SSE 流式
> **规格文档:** `docs/superpowers/specs/2026-05-31-agent-transformation.md`

---

### Task 1: 记忆系统数据库

**Files:**
- Create: `api/app/agent/__init__.py`
- Create: `api/app/agent/memory_schema.py`
- Create: `tests/test_agent_memory.py`

实现 Agent 记忆系统的 SQLite 数据库和基本读写操作。

- [ ] **Step 1: 创建数据库 schema**

在 `memory_schema.py` 中定义：
- `agent_user_profile` — 用户画像表（key-value 结构，支持画像演化）
- `agent_decision_memory` — 决策记忆表（关联 symbol/date/type/conclusion/outcome/source）
- `agent_stock_impressions` — 股票印象表（关联 symbol/status/impression）
- `agent_sessions` + `agent_messages` — 对话记录表
- `agent_messages_fts` — FTS5 全文搜索虚拟表
- 数据库文件路径：`data/alphaagents.db`（复用现有行情库）

默认数据库初始化时自动建表。

- [ ] **Step 2: 实现 MemoryRepository 读写方法**

```python
class AgentMemoryRepository:
    # 用户画像
    def get_profile(self) -> dict
    def update_profile(self, key: str, value: str) -> None

    # 决策记忆
    def add_decision(self, decision: dict) -> str
    def search_decisions(self, query: str, limit: int = 5) -> list[dict]
    def get_decisions_for_symbol(self, symbol: str) -> list[dict]

    # 股票印象
    def get_impression(self, symbol: str) -> dict | None
    def upsert_impression(self, symbol: str, status: str, impression: str) -> None
    def get_all_impressions(self) -> list[dict]

    # 会话
    def create_session(self) -> str
    def add_message(self, session_id: str, role: str, content: str, tool_calls: str | None) -> None
    def get_session_messages(self, session_id: str) -> list[dict]
    def search_sessions(self, query: str, limit: int = 5) -> list[dict]
    def close_session(self, session_id: str, summary: str) -> None
```

- [ ] **Step 3: 编写测试**

验证：
- 表创建成功，schema 版本正确
- 用户画像读写正常
- 决策记忆插入和按 symbol 查询
- 股票印象 upsert 逻辑（覆盖旧值）
- 对话消息 FTS5 搜索命中中文关键词
- 关闭会话后 summary 正确保存

---

### Task 2: Agent Tools 层

**Files:**
- Create: `api/app/agent/tools.py`
- Create: `tests/test_agent_tools.py`

将现有 FastAPI 端点包装为 LLM function calling 格式的 tools，同时添加 agent 内部工具。

- [ ] **Step 1: 定义 tool 接口**

```python
@dataclass
class AgentTool:
    name: str
    description: str
    parameters: dict  # JSON Schema
    handler: Callable  # async function
```

- [ ] **Step 2: 实现查询类 tools**

| tool | 功能 | 调用 |
|------|------|------|
| `get_daily_summary` | 今日持仓告警 + 选股候选数 + 日报摘要 | 组合内部调用 |
| `get_stock_detail` | 个股 K 线指标 + 工作台数据 + 提醒 | `/stocks/{symbol}/workspace` + `/stocks/{symbol}/alerts` |
| `search_stocks` | 按代码/名称搜索股票 | `/market/stocks` |
| `get_positions` | 当前持仓列表 | `/portfolio/positions` |
| `get_review_history` | 最近复盘案例 | `/review/cases/latest` |
| `get_daily_report` | 最新结构化日报 | `/reports/daily/latest` |
| `run_selection` | 执行选股工作流 | `/workflows/selection/run` |
| `recall_memory` | 搜索历史决策 + 股票印象 | `AgentMemoryRepository` |

- [ ] **Step 3: 实现写入类 tools**

| tool | 功能 | 调用 |
|------|------|------|
| `update_tracking` | 更新股票跟踪状态 | `PATCH /stocks/{symbol}/tracking` |
| `record_operation` | 记录操作 | `POST /stocks/{symbol}/operations` |
| `save_review` | 保存复盘 | `POST /stocks/{symbol}/reviews` |
| `update_profile` | 更新用户画像 | `AgentMemoryRepository.update_profile` |

- [ ] **Step 4: 生成 LLM function definitions**

实现 `build_tools_for_llm()` 方法，将 `AgentTool` 列表转为 OpenAI function calling 格式的 JSON array。

- [ ] **Step 5: 编写测试**

验证：
- 每个 tool 正确映射到对应 API 调用
- `get_daily_summary` 聚合逻辑正确
- `recall_memory` 返回相关历史决策
- tools JSON schema 被 LLM API 接受

---

### Task 3: Agent Loop + Chat 端点

**Files:**
- Create: `api/app/agent/agent_loop.py`
- Create: `api/app/agent/chat_endpoint.py`
- Modify: `api/app/api/router.py`
- Create: `tests/test_agent_loop.py`

实现 agent 的核心编排逻辑和 SSE 流式端点。

- [ ] **Step 1: 实现 AgentLoop**

```python
class AgentLoop:
    def __init__(self, tools: list[AgentTool], memory: AgentMemoryRepository)
    
    async def run(self, user_input: str, session_id: str, 
                  profile: dict, context: dict) -> AsyncGenerator[str]:
        """执行一轮 agent 对话，yield SSE 事件"""
```

流程：
1. 构建系统提示词（注入用户画像 + 当前上下文）
2. 加载最近 N 条对话消息
3. 调用 LLM（带 function calling）
4. 如果 LLM 返回 tool_choice：
   - 执行 tool handler
   - 将 tool 结果追加到消息
   - 回到步骤 3（最多 5 轮）
5. 以 SSE 格式 yield 最终回复文本
6. 持久化消息到 agent_messages

- [ ] **Step 2: SSE 事件格式**

```
event: message
data: {"delta": "文本片段"}

event: tool_call
data: {"name": "get_stock_detail", "arguments": {...}}

event: tool_result
data: {"name": "get_stock_detail", "result": {...}}

event: done
data: {"session_id": "xxx"}
```

- [ ] **Step 3: 实现 Chat 端点**

```python
@router.post("/agent/chat")
async def agent_chat(
    body: AgentChatRequest,  # { session_id?, message, symbol? }
    service: AgentServiceDependency,
) -> StreamingResponse:
```

- 首次对话自动创建 session
- 查找已有 session 或新建
- 注入 current_symbol 上下文（如果前端传了）
- 返回 `StreamingResponse(content=agent_loop.run(...), media_type="text/event-stream")`

- [ ] **Step 4: 注册路由**

在 `api/app/api/router.py` 中注册 agent 路由。

- [ ] **Step 5: 管理上下文窗口**

- 加载 session 最近 20 条消息
- 如果 token 超限，用 LLM 压缩旧消息为摘要
- 在系统提示词中注入压缩后的摘要

- [ ] **Step 6: 编写测试**

验证：
- agent 能调用 tool 并整合结果
- SSE 事件流格式正确
- 多轮对话上下文中消息正确追加
- 工具调用失败时 agent 优雅降级
- session 关闭后 summary 正确

---

### Task 4: 前端 Chat Panel

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/scripts/app.js`
- Modify: `frontend/styles/app.css`
- Create: `tests/test_agent_chat_frontend.py`

在看盘选股页面实现 chat-first 布局。

- [ ] **Step 1: HTML 布局改造**

看盘选股页改为上下分栏：
- 上半区：Chat 面板（对话 + 输入框）
- 下半区：联动区域（K 线图 / 工作台，对话中触发后展开）
- 右上角保留「同步数据」「执行选股」快捷按钮

Chat 面板结构：
```html
<section id="agent-chat" class="agent-chat-panel">
  <div id="agent-messages" class="agent-messages"></div>
  <div class="agent-input-row">
    <input id="agent-input" placeholder="问 AlphaAgents 任何问题..." />
    <button data-agent-send>发送</button>
  </div>
</section>
```

- [ ] **Step 2: 消息渲染**

- 用户消息：右对齐，深色气泡
- agent 消息：左对齐，支持 Markdown 渲染
- 打字机效果：SSE 流式追加文字
- tool_call 卡片：内联展示 "正在查询 XXX..."
- tool_result 折叠：可展开查看原始结果
- agent 建议操作按钮："标记为重点跟踪""记录为观望"

- [ ] **Step 3: 前端联动**

当 agent 调用了 `get_stock_detail(symbol)`：
1. 自动切换 K 线图到该股票
2. 同步加载工作台面板
3. 在聊天区下方展开联动区域

```javascript
// 监听 SSE tool_call 事件
eventSource.addEventListener('tool_call', (e) => {
  const { name, arguments: args } = JSON.parse(e.data);
  if (name === 'get_stock_detail' && args.symbol) {
    switchChartSymbol(args.symbol);  // 已有
    loadStockWorkspace(args.symbol);  // 已有
    showLinkedArea();  // 展开联动区域
  }
});
```

- [ ] **Step 4: CSS 样式**

- Chat 面板：`max-height: 50vh`，overflow-y 滚动
- 消息气泡：深色背景 `#1d293b`，圆角
- agent 消息：左侧 accent 细线（绿色）
- tool_call 卡片：扁平边框
- 联动区域：可折叠，slide 过渡动画
- 响应式：窄屏全高 chat

- [ ] **Step 5: 欢迎语 + quick actions**

首次加载时 agent 自动发送欢迎消息：
```
📅 2026-05-31 盘前简报
🔴 000001 破位 | 🔴 000003 趋势转弱
✅ 选股产生 8 个候选
```

下方可选 quick actions 按钮：
- 「今天有什么值得关注的？」
- 「帮我复盘本周操作」
- 「看看持仓情况」

- [ ] **Step 6: 前端测试**

验证：
- SSE 连接建立和断开
- 消息追加和滚动到底部
- 打字机效果
- 股票联动切换
- quick action 按钮触发

---

### Task 5: 记忆自动管理

**Files:**
- Create: `api/app/agent/memory_curator.py`
- Create: `tests/test_memory_curator.py`

实现 agent 对话结束后自动提取和更新记忆。

- [ ] **Step 1: 决策提取**

对话结束后，调用 LLM 分析本轮对话，提取：
- 用户做了什么决策？（买/卖/跟/放弃）
- 对哪只股票的判断改变了？
- 用户表达了什么偏好？

将提取结果写入 `agent_decision_memory` 和 `agent_stock_impressions`。

```python
async def curate_session_memory(session_id: str, messages: list[dict]) -> None:
    """分析对话内容，提取并持久化关键记忆"""
```

- [ ] **Step 2: 画像演化**

不追加、只更新。例如用户说"我现在更喜欢保守一点"：
- LLM 生成更新指令：`update_profile("risk_preference", "conservative")`
- 覆盖而非追加，避免画像膨胀

- [ ] **Step 3: 定时整理**

每次对话结束时：
1. 提取决策 → 写入 decision_memory
2. 检查是否需要更新印象 → 写入 stock_impressions
3. 检查是否需要更新画像 → 写入 user_profile

- [ ] **Step 4: 编写测试**

验证：
- 从模拟对话中正确提取决策
- 画像更新逻辑（覆盖旧值）
- 印象覆盖（"低位关注"→"破位放弃"）

---

### Task 6: 集成验证与收尾

**Files:**
- Modify: `docs/project-status.md`
- Modify: `README.md`

- [ ] **Step 1: 端到端测试**

手动测试完整流程：
1. 启动后端 + 前端
2. 打开页面，agent 自动发送欢迎消息
3. 输入"今天有什么？"
4. agent 调用 tools 整合信息
5. 输入"看看 000001"
6. K 线和工作台自动联动
7. 点击"标记为重点跟踪"按钮
8. 关闭对话，检查记忆是否正确提取

- [ ] **Step 2: 清理与文档**

- 更新 `docs/project-status.md`：记录 agent 化改造完成状态
- 更新 `docs/versions/v0.1.1.md`：收尾本次分支改动

- [ ] **Step 3: 性能验证**

- 对话响应时间 < 3 秒
- SSE 首字节延迟 < 500ms
- FTS5 搜索 10 万条消息 < 50ms
