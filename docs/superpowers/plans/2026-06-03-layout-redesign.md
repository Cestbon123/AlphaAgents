# AlphaAgents 页面布局重构 — 实施计划

> **Goal:** 将页面改为左导航+对话列表 / 中 Chat 主区域 / 右可拉收投研面板的三栏布局
> **Architecture:** CSS Grid 三栏，原生 JS 控制显隐和拖拽
> **Tech Stack:** 原生 HTML/CSS/JS
> **规格文档:** `docs/superpowers/specs/2026-06-03-layout-redesign.md`
> **原则:** Karpathy Guidelines — 精确修改，只改必要的文件，保持项目现有风格

---

### Task 1: CSS Grid 三栏布局

**Files:** `frontend/styles/app.css`, `frontend/index.html`

- [ ] **Step 1: 修改 .app-shell 为三栏 Grid**

将 `grid-template-columns: 72px 1fr` 改为 `240px 1fr 0px`（右侧默认宽度 0，收起状态）。

- [ ] **Step 2: 拆分左侧栏**

左侧栏分为上半部分（导航按钮）和下半部分（对话历史列表），中间用 `border-top` 分割。

- [ ] **Step 3: 中间主区域为 Chat**

Chat 面板占满主区域。老页面（策略/案例/报告）放在主区域的 view-panel 中，通过导航按钮切换显示。

- [ ] **Step 4: 右侧面板骨架**

新的 `#right-panel` 替代当前 `#agent-linked`，包含三个区域：K 线、工作台、筛选结果。

- [ ] **验证：** 页面打开显示三栏骨架，右侧默认不可见

---

### Task 2: 右侧面板滑入滑出

**Files:** `frontend/styles/app.css`, `frontend/scripts/app.js`

- [ ] **Step 1: CSS transition**

右侧面板 `width: 0 → 380px`，加 `transition: width 200ms ease`。滑出时 `.app-shell` 的第三列宽度同步变化。

- [ ] **Step 2: 拉手按钮**

主区域右边缘固定一个 8px 宽的竖条拉手，hover 时高亮。点击切换右侧面板显隐。

- [ ] **Step 3: 关闭按钮**

右侧面板顶部 `✕` 关闭按钮。

- [ ] **Step 4: JS 显隐控制**

`toggleRightPanel()` 函数切换 CSS class，同时更新 Grid 列宽。

- [ ] **验证：** 点击拉手 → 面板滑出（380px），再点 ✕ → 滑回

---

### Task 3: 右侧面板三区域可折叠

**Files:** `frontend/scripts/app.js`, `frontend/styles/app.css`

- [ ] **Step 1: 每个区域加标题栏**

```
┌─ K 线 ▼ ─────────── [🔍] ─┐
│                            │
│   (图表内容)                │
└────────────────────────────┘
┌─ 个股工作台 ▼ ──────────────┐
│   (提醒+操作tab)            │
└────────────────────────────┘
┌─ 筛选结果 ▶ ────────────────┐
│   (折叠隐藏)                │
└────────────────────────────┘
```

- [ ] **Step 2: 折叠/展开 JS**

点击 `▼` → 区域内容 `display:none`，`▼` 变为 `▶`。

- [ ] **Step 3: 保持图表区域**

K 线区域需要有最小高度（min-height: 300px），折叠时完全隐藏。

- [ ] **验证：** 点击每个区域的标题栏 → 折叠/展开切换正常

---

### Task 4: 图表放大模式

**Files:** `frontend/scripts/app.js`, `frontend/styles/app.css`

- [ ] **Step 1: 放大按钮**

K 线标题栏右侧 `[🔍]` 按钮。点击 → K 线从右侧面板移到主区域，覆盖 Chat。

- [ ] **Step 2: CSS 放大模式**

`.app-shell.is-chart-expanded` → 右侧面板宽度 0，主区域显示全屏 K 线。

- [ ] **Step 3: 收回按钮**

放大后 K 线标题栏变为 `[📉 收回]`，点击恢复三栏。

- [ ] **Step 4: JS 切换**

`expandChart()` → 隐藏 Chat 消息区，在 K 线容器显示图表。图表 resize 触发。

- [ ] **验证：** 放大 → K 线全屏，收回 → 恢复三栏，图表尺寸正确

---

### Task 5: 左侧对话历史列表 + 新对话

**Files:** `frontend/scripts/app.js`, `frontend/styles/app.css`, `frontend/index.html`

- [ ] **Step 1: 对话列表 HTML**

左侧栏下半部分：`#agent-history-list` 容器 + `[+ 新对话]` 按钮。

- [ ] **Step 2: 加载和渲染**

页面初始化时调用 `GET /agent/sessions` 获取最近 50 条对话，渲染为列表。每条显示：第一条用户消息（截断 15 字）+ 日期。

- [ ] **Step 3: 切换对话**

点击对话 → 调用 `GET /agent/sessions/{id}` 加载消息，渲染到 Chat 区，设置 `agentSessionId`。

- [ ] **Step 4: 新对话**

点击 `[+]` → 清空 Chat 区 + 清空 `agentSessionId` + 在列表顶部加一条空白项。

- [ ] **验证：** 列表显示历史对话，点击恢复，新建正常

---

### Task 6: 老页面按钮 + 搜索框迁移

**Files:** `frontend/scripts/app.js`, `frontend/index.html`, `frontend/styles/app.css`

- [ ] **Step 1: 搜索框移到顶部栏**

顶部栏加搜索框 `<input id="global-search">`，替代当前 `.market-search-strip`。

- [ ] **Step 2: 导航按钮切换主区域**

点击 `⚙策略` → 主区域 Chat 隐藏，显示策略编辑面板。点击 `💬Chat` → 切回聊天。案例库和报告同理。

- [ ] **Step 3: 移除旧 Tab 导航**

当前 4 个 `data-view-target` 按钮保留在左侧 nav，`view-panel` 从独立 Tab 切换改为在主区域的 content 区切换。

- [ ] **Step 4: 快速操作按钮移到顶部**

"同步数据""执行选股"保持在顶部栏。

- [ ] **验证：** 搜索股票正常，切换页面正常，快速操作正常

---

### Task 7: 集成验证与清理

- [ ] **Step 1: 端到端测试**

验证完整流程：打开页面 → 看到三栏 → 聊天 → 右侧滑出显示 K 线和工作台 → 放大图表 → 收回 → 切换对话历史 → 新对话。

- [ ] **Step 2: 窄屏适配**

≤760px 时侧边栏收为顶栏，右侧面板变为底部弹出。

- [ ] **Step 3: 清理**

删除不再使用的 CSS 和 JS（`market-command-bar`、旧的 `view-panel` 切换逻辑等）。

- [ ] **Step 4: 文档更新**

`docs/versions/v0.1.1.md`。
