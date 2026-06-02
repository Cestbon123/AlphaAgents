# Agent 对话历史管理 — 实施计划

> **Goal:** 在 Agent Chat Panel 内实现对话历史列表、恢复、搜索、新建功能
> **Architecture:** 扩展 `/agent/sessions` 端点 + 前端历史侧边栏
> **Tech Stack:** FastAPI、SQLite、原生 HTML/CSS/JS
> **规格文档:** `docs/superpowers/specs/2026-05-31-agent-history-management.md`

---

### Task 1: 后端历史列表端点

**Files:**
- Modify: `api/app/agent/chat_endpoint.py`
- Modify: `tests/test_agent_memory.py`

- [ ] **Step 1: 添加 GET /agent/sessions**

返回最近 50 个 session 的摘要列表，每个含 `id`, `started_at`, `summary`, `message_count`。

```python
@router.get("/sessions")
def list_sessions(limit: int = 50):
    memory = AgentMemoryRepository(get_settings().data_db)
    try:
        rows = memory.list_sessions(limit=limit)
        return {"sessions": rows}
    finally:
        memory.close()
```

- [ ] **Step 2: Repository 添加 list_sessions**

```python
def list_sessions(self, limit: int = 50) -> list[dict]:
    rows = self.conn.execute(
        """SELECT id, started_at, summary,
                  (SELECT COUNT(*) FROM agent_messages WHERE session_id = s.id) as message_count
           FROM agent_sessions s
           ORDER BY started_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    return [dict(r) for r in rows]
```

- [ ] **Step 3: 添加搜索端点 GET /agent/sessions/search**

```python
@router.get("/sessions/search")
def search_sessions(q: str = "", limit: int = 20):
    memory = AgentMemoryRepository(...)
    results = memory.search_sessions(q, limit)
    return {"results": results}
```

- [ ] **Step 4: 测试**

验证列表端点、搜索端点返回正确数据。

---

### Task 2: 前端历史侧边栏

**Files:**
- Modify: `frontend/index.html`
- Modify: `frontend/scripts/app.js`
- Modify: `frontend/scripts/api.js`
- Modify: `frontend/styles/app.css`

- [ ] **Step 1: HTML 结构**

在 `#agent-chat` 内添加头部栏和历史侧边栏：

```html
<div class="agent-chat-header">
  <span class="agent-chat-title">💬 对话</span>
  <span class="agent-chat-meta" id="agent-chat-meta"></span>
  <div class="agent-chat-actions">
    <button data-agent-history-toggle title="历史对话">📋</button>
    <button data-agent-new-chat title="新建对话">➕</button>
  </div>
</div>

<aside class="agent-history-panel" id="agent-history-panel" style="display:none">
  <div class="agent-history-search">
    <input id="agent-history-search" placeholder="搜索历史..." />
  </div>
  <div class="agent-history-list" id="agent-history-list"></div>
</aside>
```

- [ ] **Step 2: API 函数**

```javascript
listSessions(limit = 50) → GET /agent/sessions
searchSessions(q, limit = 20) → GET /agent/sessions/search?q=...
```

- [ ] **Step 3: 渲染逻辑**

- 点击「📋」→ 加载对话列表 + 显示侧边栏
- 点击对话卡片 → 加载消息 + 关闭侧边栏
- 点击「➕」→ 清空聊天 + 新 session
- 搜索框输入 → 防抖搜索
- 页面初始化 → 加载最近对话（如果存在）

- [ ] **Step 4: 消息恢复**

```javascript
function loadHistorySession(sessionId) {
  // 1. 获取该 session 的所有消息
  // 2. 清空聊天区
  // 3. 逐条渲染历史消息
  // 4. 设置 agentSessionId = sessionId
  // 5. 关闭侧边栏
  // 6. 更新头部 meta 信息
}
```

- [ ] **Step 5: CSS 样式**

- 历史侧边栏：右侧滑出，宽度 280px，暗色背景
- 对话卡片：下划线分割，hover 高亮
- 搜索框：紧凑样式
- 头部栏：flex 布局，按钮靠右
- 自适应窄屏

---

### Task 3: 集成验证

**Files:**
- Modify: `docs/versions/v0.1.1.md`

- [ ] **Step 1: 端到端测试**

1. 新对话 → 创建 session
2. 对话后刷新 → 自动加载最近对话
3. 点击「📋」→ 列表显示
4. 点击历史对话 → 消息恢复
5. 点击「➕」→ 新建空白对话
6. 搜索历史 → 匹配结果出现

- [ ] **Step 2: 更新文档**

记录到 `docs/versions/v0.1.1.md`。
