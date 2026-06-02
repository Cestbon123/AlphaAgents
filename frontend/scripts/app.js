/* ── 侧边栏收起展开 ── */
const sideNav = document.querySelector(".side-nav");
const sideNavToggle = document.querySelector(".side-nav-toggle");
if (sideNavToggle && sideNav) {
  sideNavToggle.addEventListener("click", function () {
    const collapsed = sideNav.classList.toggle("is-collapsed");
    var w = collapsed ? "72px" : "200px";
    document.documentElement.style.setProperty("--nav-w", w);
    sideNavToggle.setAttribute("aria-label", collapsed ? "展开侧边栏" : "收起侧边栏");
    setTimeout(function () { window.dispatchEvent(new Event("resize")); }, 200);
  });
}

const dataState = document.querySelector("#data-state");
const updatedAt = document.querySelector("#updated-at");
const syncProgressTitle = document.querySelector("#sync-progress-title");
const syncProgress = document.querySelector("#sync-progress");
const activeStrategyName = document.querySelector("#active-strategy-name");
const activeSymbolStatus = document.querySelector("#active-symbol-status");
const pageTitle = document.querySelector("#page-title");
const pageSubtitle = document.querySelector("#page-subtitle");
const sectorFilterList = document.querySelector("#sector-filter-list");
const selectionResults = document.querySelector("#selection-results");
const selectionPageStatus = document.querySelector("#selection-page-status");
const stockWorkspaceSymbolInput = document.querySelector("#stock-workspace-symbol");
const stockWorkspaceStatus = document.querySelector("#stock-workspace-status");
const agentInsights = document.querySelector("#agent-insights");
const caseLibrary = document.querySelector("#case-library");
const caseSearch = document.querySelector("#case-search");
const linkedCaseTitle = document.querySelector("#linked-case-title");
const researchReportList = document.querySelector("#research-report-list");
const researchReportContent = document.querySelector("#research-report-content");
const strategySummaryText = document.querySelector("#strategy-summary-text");
const strategyList = document.querySelector("#strategy-list");
const strategyDetail = document.querySelector("#strategy-detail");
const strategyAiPrompt = document.querySelector("#strategy-ai-prompt");

let currentSymbol = "000001.SH";
let latestSelectionResults = [];
let latestMarketStocks = [];
let latestReports = [];
let latestStrategies = [];
let activeStrategyId = "zhixing_trend";
let activeSectorType = "";
let activeSectorCode = "";
let activeCaseKind = "";
let latestDashboardRequestId = 0;
let latestMarketStocksRequestId = 0;
let latestDataSyncPayload = null;

const viewTitles = {
  chat: ["AlphaAgents", "对话"],
  strategies: ["选股策略", "Strategy Builder"],
  cases: ["案例库", "Case Library"],
  reports: ["分析报告", "Reports"],
};

const strategyParamMeta = {
  j_max: {
    label: "KDJ J 值上限",
    helper: "数值越低越偏低位，条件越严格。",
    suffix: "",
  },
  amplitude_max_pct: {
    label: "当日振幅上限",
    helper: "限制当天高低点波动，避免过宽震荡。",
    suffix: "%",
  },
  change_min_pct: {
    label: "当日涨跌幅下限",
    helper: "允许的最低跌幅，过低会过滤下跌过深的股票。",
    suffix: "%",
  },
  change_max_pct: {
    label: "当日涨跌幅上限",
    helper: "限制追高，过高会过滤涨幅过大的股票。",
    suffix: "%",
  },
};

const strategyFormulaBlocks = [
  {
    title: "KDJ 超卖程度",
    desc: "J值越低，代表短期越超卖，信号更严格，但候选数量更少。",
    formulas: ["J = 3K − 2D · KDJ(9,3,3)"],
    controls: [
      { label: "J ≤", key: "j_max", suffix: "" },
    ],
    hints: ["严格 10", "标准 15", "宽松 20"],
  },
  {
    title: "趋势线过滤",
    desc: "短期趋势线必须在多空线上方，确保长期趋势仍然向上。",
    formulas: [
      "短期趋势线 = EMA(EMA(C,10),10)",
      "知行多空线 = (MA(C,14)+MA(C,28)+MA(C,57)+MA(C,114))÷4",
    ],
    fixed: true,
  },
  {
    title: "当日振幅",
    desc: "限制盘中波动，排除情绪过强或波动失控的股票。",
    formulas: ["振幅 = (H−L)÷REF(C,1)×100"],
    controls: [
      { label: "≤", key: "amplitude_max_pct", suffix: "%" },
    ],
    hints: ["稳健 3%", "标准 5%", "激进 8%"],
  },
  {
    title: "当日涨跌幅",
    desc: "控制买点位置，不追高，也不接明显破位下跌。",
    formulas: ["涨跌幅 = (C−REF(C,1))÷REF(C,1)×100"],
    controls: [
      { label: "≥", key: "change_min_pct", suffix: "%" },
      { label: "≤", key: "change_max_pct", suffix: "%" },
    ],
    hints: ["低吸", "平衡", "追强"],
  },
  {
    title: "默认排除",
    desc: "自动过滤高风险标的，排除范围固定不可调。",
    formulas: [],
    fixed: true,
  },
];

function asList(value) {
  return Array.isArray(value) ? value : [];
}

function text(value, fallback = "暂无") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return String(value);
}

function clear(element) {
  element?.replaceChildren();
}

function todayText() {
  return new Date().toISOString().slice(0, 10);
}

function setRunFeedback(mode, message) {
  if (syncProgressTitle) {
    syncProgressTitle.textContent = mode;
  }
  if (syncProgress) {
    syncProgress.textContent = message;
  }
}

function beginButtonFeedback(button, loadingLabel) {
  if (!(button instanceof HTMLButtonElement)) {
    return () => {};
  }
  const originalLabel = button.dataset.originalLabel || button.textContent || "";
  button.dataset.originalLabel = originalLabel;
  button.disabled = true;
  button.setAttribute("aria-busy", "true");
  button.classList.remove("is-complete", "is-error");
  button.classList.add("is-loading");
  button.textContent = loadingLabel;

  return (state = "complete", finalLabel = "") => {
    button.disabled = false;
    button.removeAttribute("aria-busy");
    button.classList.remove("is-loading");
    button.classList.add(state === "error" ? "is-error" : "is-complete");
    button.textContent = finalLabel || (state === "error" ? "\u5931\u8d25" : "\u5b8c\u6210");
    window.setTimeout(() => {
      button.classList.remove("is-complete", "is-error");
      button.textContent = originalLabel;
    }, 1400);
  };
}

function setDataState(label) {
  if (dataState) {
    dataState.textContent = label;
  }
}

function setDataDate(payload) {
  const latestTradeDate =
    payload?.market_status?.latest_trade_date || payload?.freshness?.latest_trade_date;
  if (updatedAt) {
    updatedAt.textContent = latestTradeDate || "--";
  }
}

function createEmpty(message) {
  const node = document.createElement("p");
  node.className = "empty-state";
  node.textContent = message;
  return node;
}

function createSummaryCard(label, value) {
  const card = document.createElement("article");
  card.className = "summary-card";
  const labelNode = document.createElement("span");
  labelNode.textContent = label;
  const valueNode = document.createElement("strong");
  valueNode.textContent = text(value, "--");
  card.append(labelNode, valueNode);
  return card;
}

function dataSyncSummary(payload, state = "", message = "") {
  if (state === "syncing") {
    return "\u9636\u6bb5 1/3 \u6b63\u5728\u8bfb\u53d6\u672c\u5730\u901a\u8fbe\u4fe1\u76ee\u5f55...";
  }
  if (state === "failed") {
    return message || "\u540c\u6b65\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u901a\u8fbe\u4fe1\u76ee\u5f55\u548c\u540e\u7aef\u670d\u52a1\u3002";
  }
  const daily = payload?.daily_bars;
  const metadata = payload?.metadata;
  if (daily || metadata) {
    const dailyText = daily?.total_files
      ? "\u65e5\u7ebf " + (daily.imported_files || 0) + "/" + daily.total_files + " \u6587\u4ef6"
      : "\u65e5\u7ebf\u5f85\u540c\u6b65";
    const metadataText = metadata
      ? "\u677f\u5757 " + (metadata.sectors || 0) + " \u4e2a\uff0c\u6210\u5206 " + (metadata.sector_members || 0) + " \u6761"
      : "\u677f\u5757\u5f85\u540c\u6b65";
    return "\u9636\u6bb5 3/3 \u540c\u6b65\u5b8c\u6210 \u00b7 " + dailyText + " \u00b7 " + metadataText;
  }
  const latestTradeDate =
    payload?.market_status?.latest_trade_date || payload?.freshness?.latest_trade_date;
  if (latestTradeDate) {
    return "\u5f53\u524d\u6570\u636e\u65e5\u671f " + latestTradeDate + "\uff0c\u70b9\u51fb\u540c\u6b65\u5237\u65b0\u672c\u5730\u6570\u636e";
  }
  return "\u70b9\u51fb\u540c\u6b65\u672c\u5730\u901a\u8fbe\u4fe1\u6570\u636e";
}

function switchChartSymbol(symbol) {
  window.dispatchEvent(
    new CustomEvent("alphaagents:chart-symbol-selected", {
      detail: { symbol },
    })
  );
}

function resizeMarketChart() {
  requestAnimationFrame(() => {
    window.AlphaAgentsChart?.resize?.();
  });
}

function switchView(viewName) {
  var chatPanel = document.querySelector("#agent-chat");
  if (chatPanel) {
    chatPanel.classList.toggle("is-hidden", viewName !== "chat");
  }
  if (viewName === "chat") {
    document.querySelectorAll("[data-view]").forEach((panel) => {
      panel.classList.remove("is-active");
    });
  } else {
    document.querySelectorAll("[data-view]").forEach((panel) => {
      panel.classList.toggle("is-active", panel.dataset.view === viewName);
    });
  }
  document.querySelectorAll("[data-view-target]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.viewTarget === viewName);
  });
  var titles = viewTitles[viewName] || ["AlphaAgents", ""];
  if (pageTitle) pageTitle.textContent = titles[0];
  if (pageSubtitle) pageSubtitle.textContent = titles[1] || "";
  if (viewName === "strategies") {
    loadStrategies();
  }
  if (viewName === "cases") {
    loadCaseLibrary();
  }
  if (viewName === "reports") {
    loadResearchReports();
  }
}

async function setCurrentSymbol(symbol, options = {}) {
  const nextSymbol = text(symbol, currentSymbol).trim().toUpperCase();
  if (!nextSymbol) {
    return;
  }
  currentSymbol = nextSymbol;
  if (stockWorkspaceSymbolInput) {
    stockWorkspaceSymbolInput.value = nextSymbol;
  }
  if (activeSymbolStatus) {
    activeSymbolStatus.textContent = nextSymbol;
  }
  if (options.syncChart !== false) {
    switchChartSymbol(nextSymbol);
  }
  await loadStockWorkspace(nextSymbol);
}

function renderStockWorkspace(workspace) {
  clear(agentInsights);
  if (!workspace) {
    if (stockWorkspaceStatus) {
      stockWorkspaceStatus.textContent = "当前个股上下文未加载";
    }
    renderAgentInsights(null);
    return;
  }

  currentSymbol = text(workspace.symbol, currentSymbol);
  if (stockWorkspaceStatus) {
    stockWorkspaceStatus.textContent = `${text(workspace.name)} ${currentSymbol}`;
  }
  renderAgentInsights(workspace.latest_research_report);
  loadStockAlerts(currentSymbol);
}


function renderAgentInsights(report) {
  clear(agentInsights);
  if (!agentInsights) {
    return;
  }
  const analysts = asList(report?.analyst_reports).slice(0, 4);
  if (!analysts.length) {
    agentInsights.append(createEmpty("暂无 Agent 洞察，点击生成分析后显示多专家摘要。"));
    return;
  }
  analysts.forEach((analyst) => {
    const card = document.createElement("article");
    card.className = "agent-card";
    const title = document.createElement("h3");
    title.textContent = text(analyst.role);
    const confidence = document.createElement("span");
    confidence.textContent = `置信度 ${Math.round(Number(analyst.confidence || 0) * 100)}%`;
    const summary = document.createElement("p");
    summary.textContent = text(analyst.summary, "");
    card.append(title, confidence, summary);
    agentInsights.append(card);
  });
}


async function loadStockWorkspace(symbol = currentSymbol) {
  try {
    const payload = await window.AlphaAgentsApi.getStockWorkspace(symbol);
    renderStockWorkspace(payload.workspace);
    return payload.workspace;
  } catch (error) {
    setRunFeedback("个股工作台", `读取失败：${error.message}`);
  }
}

async function loadStockAlerts(symbol) {
  var container = document.querySelector("#stock-alerts");
  if (!container) return;
  try {
    var payload = await window.AlphaAgentsApi.getStockAlerts(symbol);
    renderStockAlerts(payload.alerts);
  } catch (error) {
    container.innerHTML = "";
  }
}

function renderStockAlerts(alertsData) {
  var container = document.querySelector("#stock-alerts");
  if (!container) return;
  container.innerHTML = "";
  var alerts = alertsData?.alerts || [];
  var typeColors = {
    ok: "var(--blue)",
    warning: "var(--amber)",
    danger: "var(--red)",
  };
  var typeLabels = {
    ok: "正常",
    warning: "注意",
    danger: "危险",
  };
  alerts.forEach(function (a) {
    var tag = document.createElement("div");
    tag.className = "alert-badge alert-" + (a.type || "");
    var label = document.createElement("span");
    label.className = "alert-badge-type";
    label.textContent = typeLabels[a.type] || "";
    label.style.color = typeColors[a.type] || "var(--muted)";
    var title = document.createElement("span");
    title.className = "alert-badge-title";
    title.textContent = a.title || "";
    var msg = document.createElement("span");
    msg.className = "alert-badge-msg";
    msg.textContent = a.message || "";
    tag.append(label, title, msg);
    container.append(tag);
  });
}

/* ── Agent Chat ── */

var agentSessionId = null;
var agentMessagesEl = null;
var agentInputEl = null;
var agentSkillMenuEl = null;
var agentSelectedSkillEl = null;
var agentSkills = [];
var selectedAgentSkill = null;
var activeAgentSkillIndex = -1;

function initAgentChat() {
  agentMessagesEl = document.querySelector("#agent-messages");
  agentInputEl = document.querySelector("#agent-input");
  agentSkillMenuEl = document.querySelector("#agent-skill-menu");
  agentSelectedSkillEl = document.querySelector("#agent-selected-skill");

  // Load history list and show welcome
  loadAgentHistory();
  if (agentMessagesEl) agentAppendWelcome();

  // New chat button — same as initial page load
  var newChatBtn = document.querySelector("[data-agent-new-chat]");
  if (newChatBtn) {
    newChatBtn.addEventListener("click", function () {
      agentSessionId = null;
      if (agentMessagesEl) agentMessagesEl.innerHTML = "";
      switchView("chat");
      agentAppendWelcome();
      document.querySelectorAll(".history-item").forEach(function (el) {
        el.classList.remove("is-active");
      });
      document.querySelectorAll(".history-row").forEach(function (el) {
        el.classList.remove("is-active");
      });
    });
  }

  var sendBtn = document.querySelector("[data-agent-send]");
  if (sendBtn) {
    sendBtn.addEventListener("click", agentSend);
  }

  if (agentInputEl) {
    agentInputEl.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        hideAgentSkillMenu();
        return;
      }
      if ((e.key === "ArrowDown" || e.key === "ArrowUp") && isAgentSkillMenuOpen()) {
        e.preventDefault();
        moveActiveAgentSkillOption(e.key === "ArrowDown" ? 1 : -1);
        return;
      }
      if (e.key === "Enter" && isAgentSkillMenuOpen()) {
        var activeOption = getActiveAgentSkillOption();
        if (activeOption) {
          e.preventDefault();
          selectAgentSkill(activeOption.dataset.skillId);
          return;
        }
      }
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        agentSend();
      }
    });
    agentInputEl.addEventListener("input", renderAgentSkillMenu);
    agentInputEl.addEventListener("focus", renderAgentSkillMenu);
    document.addEventListener("click", function (event) {
      if (!event.target.closest(".agent-composer")) {
        hideAgentSkillMenu();
      }
    });
  }

  // Quick actions
  document.querySelectorAll("[data-agent-quick]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      if (agentInputEl) {
        agentInputEl.value = btn.textContent.trim();
        agentSend();
      }
    });
  });

  // Chart expand: move chart between right panel and fullscreen overlay
  var chartExpand = document.querySelector("[data-chart-expand]");
  var chartOverlay = document.querySelector("#chart-overlay");
  if (chartExpand && chartOverlay) {
    chartExpand.addEventListener("click", function () {
      var chartEl = document.querySelector("#kline-chart");
      var appShell = document.querySelector(".app-shell");
      if (chartExpand.textContent === "🔍") {
        // Expand: move chart to overlay, show sub-indicators
        chartOverlay.append(chartEl);
        appShell.classList.add("is-chart-expanded");
        chartExpand.textContent = "📉";
        if (window.AlphaAgentsChartExpand) window.AlphaAgentsChartExpand();
      } else {
        // Collapse: move chart back to right panel
        var rpChart = document.querySelector("#rp-chart .rp-section-body");
        if (rpChart) rpChart.prepend(chartEl);
        appShell.classList.remove("is-chart-expanded");
        chartExpand.textContent = "🔍";
      }
      setTimeout(function () { window.dispatchEvent(new Event("resize")); }, 200);
    });
  }

  // Panel resize handle (between chat and right panel)
  var handle = document.querySelector("#panel-resize-handle");
  var rp = document.querySelector("#right-panel");
  if (handle && rp) {
    var dragging = false;
    var startX = 0;
    var startWidth = 0;

    handle.addEventListener("mousedown", function (e) {
      dragging = true;
      startX = e.clientX;
      startWidth = rp.offsetWidth;
      handle.classList.add("is-active");
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      e.preventDefault();
    });

    document.addEventListener("mousemove", function (e) {
      if (!dragging) return;
      var delta = startX - e.clientX;
      var newWidth = Math.max(420, Math.min(900, startWidth + delta));
      rp.style.width = newWidth + "px";
    });

    document.addEventListener("mouseup", function () {
      if (!dragging) return;
      dragging = false;
      handle.classList.remove("is-active");
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      setTimeout(function () { window.dispatchEvent(new Event("resize")); }, 100);
    });

    // Double-click to toggle collapse
    handle.addEventListener("dblclick", function () {
      rp.classList.toggle("is-collapsed");
      setTimeout(function () { window.dispatchEvent(new Event("resize")); }, 300);
    });
  }

  // Section toggle buttons
  document.querySelectorAll("[data-rp-toggle]").forEach(function (btn) {
    btn.addEventListener("click", function () {
      var sectionId = btn.dataset.rpToggle;
      var section = document.querySelector("#rp-" + sectionId);
      if (section) {
        section.classList.toggle("is-collapsed");
        btn.textContent = section.classList.contains("is-collapsed") ? "▶" : "▼";
        if (sectionId === "chart") {
          setTimeout(function () { window.dispatchEvent(new Event("resize")); }, 200);
        }
      }
    });
  });
}

function getAgentSkill(skillId) {
  return agentSkills.find(function (skill) {
    return skill.id === skillId;
  }) || null;
}

function skillMatchesQuery(skill, query) {
  if (!query) return true;
  var normalized = query.toLowerCase();
  return [skill.id, skill.name, skill.description].some(function (value) {
    return String(value || "").toLowerCase().includes(normalized);
  });
}

function isAgentSkillMenuOpen() {
  return !!agentSkillMenuEl && !agentSkillMenuEl.classList.contains("is-hidden");
}

function hideAgentSkillMenu() {
  if (agentSkillMenuEl) {
    agentSkillMenuEl.classList.add("is-hidden");
    agentSkillMenuEl.replaceChildren();
  }
  activeAgentSkillIndex = -1;
}

function getAgentSkillOptions() {
  return Array.from(agentSkillMenuEl?.querySelectorAll(".agent-skill-option") || []);
}

function getActiveAgentSkillOption() {
  return agentSkillMenuEl?.querySelector(".agent-skill-option.is-active") || null;
}

function setActiveAgentSkillOption(index) {
  var options = getAgentSkillOptions();
  if (!options.length) {
    activeAgentSkillIndex = -1;
    return;
  }
  activeAgentSkillIndex = (index + options.length) % options.length;
  options.forEach(function (option, optionIndex) {
    var active = optionIndex === activeAgentSkillIndex;
    option.classList.toggle("is-active", active);
    option.setAttribute("aria-selected", active ? "true" : "false");
    if (active) {
      option.scrollIntoView({ block: "nearest" });
    }
  });
}

function moveActiveAgentSkillOption(offset) {
  setActiveAgentSkillOption(activeAgentSkillIndex + offset);
}

function renderSelectedAgentSkill() {
  if (!agentSelectedSkillEl) return;
  agentSelectedSkillEl.replaceChildren();
  if (!selectedAgentSkill) {
    agentSelectedSkillEl.classList.add("is-hidden");
    return;
  }
  agentSelectedSkillEl.classList.remove("is-hidden");
  var token = document.createElement("span");
  token.className = "agent-skill-token";
  token.textContent = selectedAgentSkill.name;
  var clear = document.createElement("button");
  clear.type = "button";
  clear.setAttribute("aria-label", "清除已选技能");
  clear.textContent = "\u00d7";
  clear.addEventListener("click", function () {
    selectedAgentSkill = null;
    renderSelectedAgentSkill();
    agentInputEl && agentInputEl.focus();
  });
  agentSelectedSkillEl.append(token, clear);
}

function selectAgentSkill(skillId) {
  var skill = getAgentSkill(skillId);
  if (!skill) return;
  selectedAgentSkill = skill;
  if (agentInputEl && agentInputEl.value.trim().startsWith("/")) {
    var content = agentInputEl.value.trimStart().slice(1).trimStart();
    if (content.startsWith(skill.name + " ")) {
      agentInputEl.value = content.slice(skill.name.length).trimStart();
    } else if (content.startsWith(skill.id + " ")) {
      agentInputEl.value = content.slice(skill.id.length).trimStart();
    } else {
      agentInputEl.value = "";
    }
  }
  hideAgentSkillMenu();
  renderSelectedAgentSkill();
  agentInputEl && agentInputEl.focus();
}

function renderAgentSkillMenu() {
  if (!agentInputEl || !agentSkillMenuEl) return;
  var value = agentInputEl.value.trimStart();
  if (!value.startsWith("/")) {
    hideAgentSkillMenu();
    return;
  }
  var query = value.slice(1).trim();
  var matched = agentSkills.filter(function (skill) {
    return skillMatchesQuery(skill, query);
  });
  agentSkillMenuEl.replaceChildren();
  if (!matched.length) {
    agentSkillMenuEl.classList.add("is-hidden");
    return;
  }
  matched.forEach(function (skill) {
    var option = document.createElement("button");
    option.type = "button";
    option.className = "agent-skill-option";
    option.dataset.skillId = skill.id;
    option.setAttribute("role", "option");
    option.setAttribute("aria-selected", "false");
    var name = document.createElement("strong");
    name.textContent = skill.name;
    var desc = document.createElement("span");
    desc.textContent = skill.description;
    option.append(name, desc);
    option.addEventListener("click", function () {
      selectAgentSkill(skill.id);
    });
    agentSkillMenuEl.append(option);
  });
  setActiveAgentSkillOption(0);
  agentSkillMenuEl.classList.remove("is-hidden");
}

function extractSlashSkill(message) {
  if (!message.startsWith("/")) {
    return { skill: null, message };
  }
  var content = message.slice(1).trimStart();
  var matched = agentSkills.find(function (skill) {
    return content === skill.name || content.startsWith(skill.name + " ") ||
      content === skill.id || content.startsWith(skill.id + " ");
  });
  if (!matched) {
    return { skill: null, message };
  }
  return {
    skill: matched,
    message: content.slice(content.startsWith(matched.id) ? matched.id.length : matched.name.length).trimStart(),
  };
}

function agentSend() {
  if (!agentInputEl || !agentMessagesEl) return;
  var message = agentInputEl.value.trim();
  if (!message) return;

  var slashSelection = extractSlashSkill(message);
  var requestedSkill = selectedAgentSkill || slashSelection.skill;
  if (slashSelection.skill) {
    message = slashSelection.message || slashSelection.skill.name;
  }
  if (requestedSkill) {
    agentAppendMsg("skill", "已选择：" + requestedSkill.name);
  }
  agentAppendMsg("user", message);
  agentInputEl.value = "";
  agentInputEl.disabled = true;
  selectedAgentSkill = null;
  renderSelectedAgentSkill();
  hideAgentSkillMenu();

  // Typing indicator
  var typingEl = document.createElement("div");
  typingEl.className = "agent-msg agent-msg-assistant agent-typing";
  typingEl.textContent = "思考中";
  agentMessagesEl.append(typingEl);
  agentMessagesEl.scrollTop = agentMessagesEl.scrollHeight;

  // Stream response
  window.AlphaAgentsApi.agentChat(
    message,
    agentSessionId,
    currentSymbol,
    buildAgentUiContext(),
    requestedSkill?.id || null
  ).then(function (resp) {
    var reader = resp.body.getReader();
    var decoder = new TextDecoder();
    var buffer = "";
    var assistantContent = "";

    function processSSE(text) {
      // Split by double newline (SSE event separator)
      var events = text.split("\n\n");
      var last = events.pop() || "";
      var currentEvent = "";
      var currentData = "";

      events.forEach(function (block) {
        var lines = block.split("\n");
        lines.forEach(function (line) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith("data: ")) {
            currentData = line.slice(6);
          }
        });

        if (!currentData) return;

        var data;
        try { data = JSON.parse(currentData); } catch (e) { return; }

        if (currentEvent === "skill_selected") {
          var skills = data.skills || [];
          if (!requestedSkill) {
            var names = skills.map(function (id) {
              return getAgentSkill(id)?.name || id;
            }).join(" + ");
            agentAppendMsg("skill", "自动路由：" + names);
          }
        } else if (currentEvent === "delta") {
          assistantContent += data.content || "";
          if (typingEl && typingEl.parentNode) {
            typingEl.textContent = assistantContent;
            typingEl.classList.remove("agent-typing");
          }
          agentMessagesEl.scrollTop = agentMessagesEl.scrollHeight;
        } else if (currentEvent === "tool_start") {
          var src = data.data_sources && data.data_sources.length
            ? " → " + data.data_sources.map(function (s) { return {local_market: "行情", workflow: "工作流", agent_memory: "记忆"}[s] || s; }).join("+")
            : "";
          var warn = data.requires_confirmation ? " ⚠️需确认" : "";
          agentAppendMsg("tool", "调用 " + (data.name || "") + src + warn);
        } else if (currentEvent === "tool_result") {
          if (data.result?.requires_confirmation) {
            agentAppendMsg("tool", data.result.message || "该操作需要确认后执行");
          }
          if (data.name === "get_stock_detail" && data.result) {
            var sym = data.result.workspace?.symbol || data.result.alerts?.symbol;
            if (sym) {
              setCurrentSymbol(sym, { syncChart: true });
              var rp = document.querySelector("#right-panel");
              if (rp) rp.classList.remove("is-collapsed");
            }
          }
        } else if (currentEvent === "error") {
          if (typingEl && typingEl.parentNode) typingEl.remove();
          agentInputEl.disabled = false;
          agentAppendMsg("error", data.error || "Agent 对话失败");
        } else if (currentEvent === "evidence") {
          agentAppendMsg("tool", "📋 " + (data.text || "").split("\n- ").slice(0, 3).join(", "));
        } else if (currentEvent === "done") {
          if (typingEl && typingEl.parentNode) typingEl.remove();
          if (assistantContent) {
            agentAppendMsg("assistant", assistantContent);
          }
          assistantContent = "";
          if (data && data.session_id) agentSessionId = data.session_id;
          agentInputEl.disabled = false;
          agentInputEl.focus();
          setTimeout(loadAgentHistory, 500);
        }

        currentEvent = "";
        currentData = "";
      });

      return last;
    }

    function readNext() {
      reader.read().then(function (result) {
        if (result.done) {
          if (buffer) { processSSE(buffer); buffer = ""; }
          agentInputEl.disabled = false;
          agentInputEl.focus();
          if (typingEl && typingEl.parentNode) typingEl.remove();
          if (assistantContent) {
            agentAppendMsg("assistant", assistantContent);
            assistantContent = "";
          }
          return;
        }

        buffer += decoder.decode(result.value, { stream: true });
        buffer = processSSE(buffer);

        readNext();
      }).catch(function () {
        if (typingEl && typingEl.parentNode) typingEl.remove();
        agentInputEl.disabled = false;
        agentAppendMsg("error", "连接中断");
      });
    }

    readNext();
  }).catch(function (err) {
    if (typingEl && typingEl.parentNode) typingEl.remove();
    agentInputEl.disabled = false;
    agentAppendMsg("error", "发送失败: " + (err.message || "网络错误"));
  });
}

function buildAgentUiContext() {
  var rightPanel = document.querySelector("#right-panel");
  var activeSection = "chart";
  document.querySelectorAll("[data-rp-toggle]").forEach(function (btn) {
    var sectionId = btn.dataset.rpToggle;
    var section = document.querySelector("#rp-" + sectionId);
    if (section && !section.classList.contains("is-collapsed")) {
      activeSection = sectionId;
    }
  });
  return {
    current_view: "chat",
    data_hints: {
      right_panel_open: rightPanel ? !rightPanel.classList.contains("is-collapsed") : false,
      active_section: activeSection,
      current_symbol: currentSymbol,
    },
  };
}

function agentAppendWelcome() {
  if (!agentMessagesEl) return;
  var welcome = document.createElement("div");
  welcome.className = "agent-welcome";
  welcome.innerHTML = '<p>👋 我是 AlphaAgents 投研助手。</p><div id="agent-skills-area">加载中...</div>';
  agentMessagesEl.append(welcome);
  // Load skills from backend
  window.AlphaAgentsApi.listAgentSkills().then(function (data) {
    var skills = data.skills || [];
    agentSkills = skills;
    var skillsArea = document.querySelector("#agent-skills-area");
    if (!skillsArea) return;
    var icons = { daily_briefing: "📊", stock_diagnosis: "🔍", strategy_selection: "⚙", history_review: "📋", review_deposition: "📝" };
    var html = '<div class="agent-skill-cards">';
    skills.forEach(function (s) {
      var label = (icons[s.id] || "") + " " + s.name;
      var escapedName = s.name.replace(/'/g, "\\'");
      html += '<div class="agent-skill-card" data-skill-id="' + s.id + '">' +
        '<b>' + label + '</b>' +
        '<span>' + s.description + '</span>' +
        '</div>';
    });
    html += '</div>';
    skillsArea.innerHTML = html;
    // Delegate click to skill cards
    skillsArea.addEventListener("click", function (e) {
      var card = e.target.closest(".agent-skill-card");
      if (!card) return;
      var skillId = card.dataset.skillId;
      selectAgentSkill(skillId);
    });
  }).catch(function () {
    var skillsArea = document.querySelector("#agent-skills-area");
    if (skillsArea) skillsArea.innerHTML = '<p>加载失败</p>';
  });
}

function loadAgentHistory() {
  var list = document.querySelector("#agent-history-list");
  if (!list) return;
  window.AlphaAgentsApi.listAgentSessions().then(function (data) {
    var sessions = data.sessions || [];
    list.innerHTML = "";
    sessions.forEach(function (s) {
      var row = document.createElement("div");
      row.className = "history-row";
      if (s.id === agentSessionId) row.classList.add("is-active");
      var btn = document.createElement("button");
      btn.className = "history-item";
      btn.dataset.sessionId = s.id;
      var label = s.summary || s.started_at || s.id;
      if (label.length > 18) label = label.slice(0, 18) + "...";
      btn.textContent = label;
      btn.title = s.started_at + (s.summary ? " - " + s.summary : "");
      btn.addEventListener("click", function () {
        loadHistorySession(s.id);
      });
      var deleteButton = document.createElement("button");
      deleteButton.className = "history-delete";
      deleteButton.type = "button";
      deleteButton.title = "删除对话";
      deleteButton.setAttribute("aria-label", "删除对话");
      deleteButton.textContent = "\u00d7";
      deleteButton.addEventListener("click", function (event) {
        event.stopPropagation();
        deleteHistorySession(s.id);
      });
      row.append(btn, deleteButton);
      list.append(row);
    });
  }).catch(function () {});
}

function resetAgentChatToWelcome() {
  agentSessionId = null;
  if (agentMessagesEl) {
    agentMessagesEl.innerHTML = "";
    agentAppendWelcome();
  }
  switchView("chat");
}

function deleteHistorySession(sessionId) {
  if (!sessionId) return;
  if (!window.confirm("删除这段对话？")) {
    return;
  }
  window.AlphaAgentsApi.deleteAgentSession(sessionId).then(function () {
    if (sessionId === agentSessionId) {
      resetAgentChatToWelcome();
    }
    loadAgentHistory();
  }).catch(function (error) {
    setRunFeedback("删除对话", error.message || "删除失败");
  });
}

function loadHistorySession(sessionId) {
  agentSessionId = sessionId;
  switchView("chat");
  if (!agentMessagesEl) return;
  agentMessagesEl.innerHTML = "";
  window.AlphaAgentsApi.getAgentSession(sessionId).then(function (data) {
    var msgs = data.messages || [];
    msgs.forEach(function (m) {
      if (m.role === "user" && m.content) {
        agentAppendMsg("user", m.content);
      } else if (m.role === "assistant" && m.content) {
        agentAppendMsg("assistant", m.content);
      } else if (m.role === "tool" && m.tool_name) {
        agentAppendMsg("tool", "工具结果：" + m.tool_name);
      }
    });
    document.querySelectorAll(".history-item").forEach(function (el) {
      el.classList.toggle("is-active", el.dataset.sessionId === sessionId);
    });
    document.querySelectorAll(".history-row").forEach(function (el) {
      el.classList.toggle("is-active", el.querySelector(".history-item")?.dataset.sessionId === sessionId);
    });
    if (!msgs.length) agentAppendWelcome();
  }).catch(function () {
    agentAppendWelcome();
  });
}

function agentAppendMsg(type, text) {
  if (!agentMessagesEl) return;
  var el = document.createElement("div");
  if (type === "skill") {
    el.className = "agent-msg agent-msg-skill";
    var label = document.createElement("span");
    label.className = "agent-skill-token";
    label.textContent = text;
    el.append(label);
  } else if (type === "user") {
    el.className = "agent-msg agent-msg-user";
    el.textContent = text;
  } else if (type === "assistant") {
    el.className = "agent-msg agent-msg-assistant";
    el.textContent = text;
  } else if (type === "tool") {
    el.className = "agent-msg agent-msg-tool";
    el.textContent = text;
  } else if (type === "error") {
    el.className = "agent-msg agent-msg-error";
    el.textContent = text;
  }
  agentMessagesEl.append(el);
  agentMessagesEl.scrollTop = agentMessagesEl.scrollHeight;
}

function formatPct(value) {
  if (value === null || value === undefined || value === "") {
    return "--";
  }
  const numeric = Number(value);
  if (Number.isNaN(numeric)) {
    return text(value);
  }
  return `${numeric > 0 ? "+" : ""}${numeric.toFixed(2)}%`;
}

function renderSectors(sectors) {
  clear(sectorFilterList);
  if (!sectorFilterList) {
    return;
  }

  asList(sectors).forEach((sector) => {
    const item = document.createElement("button");
    item.type = "button";
    item.className = "sector-item";
    item.classList.toggle("is-active", sector.sector_code === activeSectorCode);
    item.dataset.sectorCode = text(sector.sector_code, "");
    const name = document.createElement("strong");
    name.textContent = text(sector.sector_name, "--");
    const meta = document.createElement("span");
    meta.textContent = `${text(sector.sector_type, "板块")} · ${text(sector.member_count, 0)} 只`;
    item.append(name, meta);
    sectorFilterList.append(item);
  });

  if (!asList(sectors).length) {
    sectorFilterList.append(createEmpty("暂无板块元数据，可先同步本地通达信数据后再使用。"));
  }
}

async function loadSectors() {
  try {
    const payload = await window.AlphaAgentsApi.listMarketSectors({
      sector_type: activeSectorType,
      query: "",
      limit: 120,
    });
    renderSectors(payload.sectors);
  } catch (error) {
    renderSectors([]);
    setRunFeedback("板块筛选", `读取失败：${error.message}`);
  }
}

var marketStocksPage = 0;
var marketStocksTotal = 0;
var marketStocksPageSize = 10;

async function loadMarketStocks(page) {
  if (page === undefined) page = marketStocksPage;
  var requestId = ++latestMarketStocksRequestId;
  try {
    var payload = await window.AlphaAgentsApi.listMarketStocks({
      sector_code: activeSectorCode,
      limit: marketStocksPageSize,
      offset: page * marketStocksPageSize,
    });
    if (requestId !== latestMarketStocksRequestId) return;
    marketStocksPage = page;
    marketStocksTotal = payload.total || 0;
    renderSelectionResults(payload.stocks, { mode: "quotes" });
    renderPagination();
  } catch (error) {
    if (requestId !== latestMarketStocksRequestId) return;
    renderSelectionResults([], { mode: "quotes" });
    marketStocksTotal = 0;
    renderPagination();
  }
}

function renderPagination() {
  var status = document.querySelector("#selection-page-status");
  var totalPages = Math.ceil(marketStocksTotal / marketStocksPageSize) || 1;
  if (!status) return;

  const pageLabel = document.createElement("span");
  pageLabel.className = "selection-page-label";
  pageLabel.textContent = "共 " + marketStocksTotal + " 只 · " + (marketStocksPage + 1) + "/" + totalPages;

  const pager = document.createElement("span");
  pager.className = "selection-pager";

  const previousButton = document.createElement("button");
  previousButton.type = "button";
  previousButton.className = "selection-page-btn";
  previousButton.setAttribute("aria-label", "上一页");
  previousButton.textContent = "‹";
  previousButton.disabled = marketStocksPage <= 0;
  previousButton.addEventListener("click", function (event) {
    event.stopPropagation();
    loadMarketStocks(marketStocksPage - 1);
  });

  const nextButton = document.createElement("button");
  nextButton.type = "button";
  nextButton.className = "selection-page-btn";
  nextButton.setAttribute("aria-label", "下一页");
  nextButton.textContent = "›";
  nextButton.disabled = marketStocksPage >= totalPages - 1;
  nextButton.addEventListener("click", function (event) {
    event.stopPropagation();
    loadMarketStocks(marketStocksPage + 1);
  });

  pager.append(previousButton, nextButton);
  status.replaceChildren(pageLabel, pager);
}

window._pageStocks = function (page) {
  loadMarketStocks(page);
};

function stockFromSelection(result) {
  return result.stock || {};
}

function priceTone(value) {
  const normalized = text(value, "");
  return normalized.includes("-") || normalized.includes("放弃") ? "price-down" : "price-up";
}

function renderSelectionResults(results) {
  clear(selectionResults);
  latestSelectionResults = asList(results);
  if (selectionPageStatus) {
    selectionPageStatus.textContent = `共 ${latestSelectionResults.length} 只`;
  }
  if (!selectionResults) {
    return;
  }
  if (!latestSelectionResults.length) {
    selectionResults.append(createEmpty("暂无筛选结果，点击执行选股后刷新。"));
    return;
  }
  latestSelectionResults.slice(0, 12).forEach((result) => {
    const stock = stockFromSelection(result);
    const card = document.createElement("article");
    card.className = "stock-card";
    card.tabIndex = 0;
    card.dataset.chartTarget = text(stock.symbol, "");
    const title = document.createElement("h3");
    title.textContent = `${text(stock.name)} ${text(stock.symbol, "--")}`;
    const price = document.createElement("span");
    price.className = priceTone(result.action);
    price.textContent = text(result.action, "观察");
    const reason = document.createElement("p");
    reason.textContent = text(result.core_reason || result.match_reason, "暂无策略原因");
    card.append(title, price, reason);
    selectionResults.append(card);
  });
}

function renderSelectionResultsTable(results, options = {}) {
  clear(selectionResults);
  const mode = options.mode || "selection";
  latestSelectionResults = asList(results);
  if (mode === "quotes") {
    latestMarketStocks = latestSelectionResults;
  }
  if (selectionPageStatus) {
    selectionPageStatus.textContent = `共 ${latestSelectionResults.length} 只`;
  }
  if (!selectionResults) {
    return;
  }
  if (!latestSelectionResults.length) {
    selectionResults.append(
      createEmpty(
        mode === "quotes"
          ? "暂无股票列表，可切换板块或同步本地通达信数据后刷新。"
          : "暂无筛选结果，点击执行选股后刷新。"
      )
    );
    return;
  }
  const table = document.createElement("table");
  table.innerHTML = `
    <thead>
      <tr>
        <th>股票名称</th>
        <th>现价</th>
        <th>今日涨跌幅</th>
      </tr>
    </thead>
    <tbody></tbody>
  `;
  const body = table.querySelector("tbody");
  latestSelectionResults.forEach(function (result) {
    var stock = mode === "quotes" ? result : stockFromSelection(result);
    const changeValue =
      mode === "quotes" ? stock.change_pct : parseSelectionChangePct(stock.market_summary);
    const row = document.createElement("tr");
    row.tabIndex = 0;
    row.dataset.chartTarget = text(stock.symbol, "");
    row.innerHTML = `
      <td><strong>${text(stock.name)}</strong><span>${text(stock.symbol, "--")}</span></td>
      <td>${text(stock.price ?? stock.close ?? parseSelectionClose(stock.market_summary), "--")}</td>
      <td class="${Number(changeValue) < 0 ? "price-down" : "price-up"}">${formatPct(changeValue)}</td>
    `;
    body?.append(row);
  });
  selectionResults.append(table);
}

function parseSelectionClose(summary) {
  const match = String(summary || "").match(/收盘\s*([0-9.]+)/);
  return match ? match[1] : "";
}

function parseSelectionChangePct(summary) {
  const match = String(summary || "").match(/涨跌幅=([-0-9.]+)%/);
  return match ? Number(match[1]) : null;
}

renderSelectionResults = renderSelectionResultsTable;

async function refreshDashboard(prefix = "后端仪表盘已连接") {
  const requestId = ++latestDashboardRequestId;
  try {
    const dashboard = await window.AlphaAgentsApi.getDashboard();
    if (requestId !== latestDashboardRequestId) {
      return;
    }
    const latestSelection = await window.AlphaAgentsApi.getLatestSelectionRun();
    const selection = latestSelection?.results?.length
      ? latestSelection.results
      : dashboard.selection_results;
    setDataState("后端接口");
    setRunFeedback("系统状态", `${prefix}。当前筛选结果 ${asList(selection).length} 只。`);
  } catch (error) {
    setDataState("后端不可用");
    setRunFeedback("系统状态", `后端暂不可用：${error.message}`);
  }
}

async function runSelection(triggerButton) {
  const finishButton = beginButtonFeedback(triggerButton, "\u9009\u80a1\u4e2d...");
  setRunFeedback("看盘选股", "正在执行选股策略。");
  try {
    const payload = await window.AlphaAgentsApi.runWorkflow("selection");
    renderSelectionResults(payload.results);
    setRunFeedback("看盘选股", `选股完成，返回 ${asList(payload.results).length} 只股票。`);
    finishButton("complete", "选股完成");
  } catch (error) {
    finishButton("error", "选股失败");
    setRunFeedback("看盘选股", `选股失败：${error.message}`);
  }
}

function renderCaseLibrary(cases) {
  clear(caseLibrary);
  if (!caseLibrary) {
    return;
  }
  const normalized = asList(cases);
  if (!normalized.length) {
    caseLibrary.append(createEmpty("暂无案例，先在个股工作台写复盘或沉淀经验。"));
    return;
  }
  normalized.forEach((item) => {
    const card = document.createElement("article");
    card.className = "case-card";
    if (text(item.status, "").includes("失败") || text(item.kind, "").includes("风险")) {
      card.classList.add("is-risk");
    }
    if (text(item.status, "").includes("待") || text(item.kind, "").includes("观察")) {
      card.classList.add("is-watch");
    }
    card.tabIndex = 0;
    card.dataset.chartTarget = text(item.symbol, "");
    const title = document.createElement("h3");
    title.textContent = `${text(item.title)} · ${text(item.symbol, "--")}`;
    const meta = document.createElement("span");
    meta.textContent = `${text(item.kind)} / ${text(item.status)} / ${text(item.date, "无日期")}`;
    const body = document.createElement("p");
    body.textContent = text(item.content || item.source, "暂无摘要");
    card.append(title, meta, body);
    caseLibrary.append(card);
  });
}

async function loadCaseLibrary() {
  try {
    const payload = await window.AlphaAgentsApi.listStockCases({
      query: caseSearch?.value.trim() || "",
      kind: activeCaseKind,
    });
    renderCaseLibrary(payload.cases);
  } catch (error) {
    renderCaseLibrary([]);
    setRunFeedback("案例库", `读取失败：${error.message}`);
  }
}

function reportTitle(report) {
  return `${text(report.name, report.symbol)} 研究报告：${text(report.final_decision, "--")}`;
}

function renderResearchReports(reports) {
  clear(researchReportList);
  latestReports = asList(reports);
  if (!researchReportList) {
    return;
  }
  if (!latestReports.length) {
    researchReportList.append(createEmpty("暂无研究报告，先在个股工作台生成分析。"));
    renderResearchReport(null);
    return;
  }
  latestReports.forEach((report, index) => {
    const item = document.createElement("article");
    item.className = "report-item";
    item.classList.toggle("is-active", index === 0);
    item.tabIndex = 0;
    item.dataset.reportIndex = String(index);
    item.dataset.chartTarget = text(report.symbol, "");
    const title = document.createElement("h3");
    title.textContent = reportTitle(report);
    const meta = document.createElement("div");
    meta.className = "report-meta";
    meta.textContent = `${text(report.generated_at)} · 专家 ${asList(report.analyst_reports).length} 位 · 数据缺口 ${asList(report.data_gaps).length}`;
    item.append(title, meta);
    researchReportList.append(item);
  });
  renderResearchReport(latestReports[0]);
}

function renderResearchReport(report) {
  clear(researchReportContent);
  if (!researchReportContent) {
    return;
  }
  if (!report) {
    researchReportContent.append(createEmpty("选择报告后查看 TradingAgents 风格多专家结论。"));
    return;
  }
  const title = document.createElement("h2");
  title.textContent = reportTitle(report);
  const summary = document.createElement("div");
  summary.className = "report-summary";
  [
    ["最终结论", report.final_decision],
    ["核心理由", report.final_reason],
    ["风险标记", `${asList(report.risk_flags).length} 条`],
    ["数据缺口", `${asList(report.data_gaps).length} 条`],
  ].forEach(([label, value]) => summary.append(createSummaryCard(label, value)));

  const analystGrid = document.createElement("div");
  analystGrid.className = "analyst-grid";
  asList(report.analyst_reports).forEach((analyst) => {
    const card = document.createElement("article");
    card.className = "agent-card";
    const role = document.createElement("h3");
    role.textContent = text(analyst.role);
    const body = document.createElement("p");
    body.textContent = text(analyst.summary, "");
    card.append(role, body);
    analystGrid.append(card);
  });

  const body = document.createElement("pre");
  body.className = "report-body";
  body.textContent = text(report.report_text, "");
  researchReportContent.append(title, summary, analystGrid, body);
}

async function loadResearchReports() {
  try {
    const payload = await window.AlphaAgentsApi.listResearchReports({ limit: 50 });
    renderResearchReports(payload.reports);
  } catch (error) {
    renderResearchReports([]);
    setRunFeedback("分析报告", `读取失败：${error.message}`);
  }
}

function renderStrategies(strategies) {
  latestStrategies = asList(strategies);
  clear(strategyList);
  if (!strategyList) {
    return;
  }
  if (!latestStrategies.length) {
    strategyList.append(createEmpty("暂无选股策略。"));
    renderStrategyDetail(null);
    return;
  }
  latestStrategies.forEach((strategy, index) => {
    const item = document.createElement("article");
    item.className = "strategy-item";
    item.classList.toggle("is-active", strategy.id === activeStrategyId || index === 0);
    item.tabIndex = 0;
    item.dataset.strategyId = text(strategy.id, "");
    const title = document.createElement("h3");
    title.textContent = text(strategy.name);
    const meta = document.createElement("span");
    meta.textContent = `${strategy.enabled ? "已启用" : "已停用"} · ${text(strategy.engine)}`;
    item.append(title, meta);
    strategyList.append(item);
  });
  renderStrategyDetail(
    latestStrategies.find((strategy) => strategy.id === activeStrategyId) || latestStrategies[0]
  );
}

function renderStrategyDetail(strategy) {
  clear(strategyDetail);
  if (!strategyDetail) {
    return;
  }
  if (!strategy) {
    strategyDetail.append(createEmpty("选择一个策略后编辑参数。"));
    return;
  }
  activeStrategyId = strategy.id;
  if (activeStrategyName) {
    activeStrategyName.textContent = strategy.name;
  }
  if (strategySummaryText) {
    strategySummaryText.textContent = strategy.description || strategy.name;
  }

  const p = strategy.params || {};
  var jMax = String(p.j_max ?? 13);
  var ampMax = String(p.amplitude_max_pct ?? 4);
  var chgMin = String(p.change_min_pct ?? -2);
  var chgMax = String(p.change_max_pct ?? 1.8);

  /* ── 启停开关 ── */
  var enabled = document.createElement("label");
  enabled.className = "strategy-enabled";
  enabled.innerHTML = '<input type="checkbox" id="strategy-enabled" ' +
    (strategy.enabled ? 'checked' : '') + ' /> 启用策略';
  strategyDetail.append(enabled);

  /* ── 策略思想 ── */
  var thinkingSec = document.createElement("section");
  thinkingSec.className = "strategy-section strategy-thinking";
  var thinkTitle = document.createElement("h3");
  thinkTitle.textContent = "策略思想";
  var thinkIdea = document.createElement("div");
  thinkIdea.className = "strategy-idea";
  thinkIdea.textContent = "在长期趋势没有走坏时，寻找短期超卖后的低吸机会。";
  var thinkDesc = document.createElement("p");
  thinkDesc.className = "strategy-desc";
  thinkDesc.textContent = text(strategy.description,
    "该策略不是追涨，而是筛选「趋势仍在、短线回调、波动收敛」的股票。" +
    "更适合震荡市和结构性行情，用于发现可能重新启动的候选标的。");
  var thinkFlow = document.createElement("div");
  thinkFlow.className = "thinking-flow";
  [["长期多头", "中长期均线保持向上"],
   ["短线回调", "股价没有大幅上涨"],
   ["KDJ超卖", "J值进入低位区域"],
   ["波动收敛", "当日振幅不能过大"],
   ["候选输出", "进入AI二次筛选"]].forEach(function (pair) {
    var item = document.createElement("div");
    item.className = "thinking-flow-item";
    var b = document.createElement("b");
    b.textContent = pair[0];
    var s = document.createElement("span");
    s.textContent = pair[1];
    item.append(b, s);
    thinkFlow.append(item);
  });
  thinkingSec.append(thinkTitle, thinkIdea, thinkDesc, thinkFlow);
  strategyDetail.append(thinkingSec);

  /* ── AI策略解读 ── */
  var interpSec = document.createElement("section");
  interpSec.className = "strategy-section strategy-interp";
  var interpHeader = document.createElement("div");
  interpHeader.className = "strategy-interp-header";
  var interpTitle = document.createElement("h3");
  interpTitle.textContent = "AI策略解读";
  var riskBadge = document.createElement("span");
  riskBadge.className = "strategy-risk-badge";
  riskBadge.textContent = "风险：中";
  interpHeader.append(interpTitle, riskBadge);
  var interpBody = document.createElement("p");
  interpBody.className = "strategy-desc";
  var jNum = Number(jMax);
  var ampNum = Number(ampMax);
  interpBody.textContent =
    (jNum <= 10 ? "J值阈值较低（≤" + jMax + "），策略等待更充分的短线超卖，" : "") +
    (jNum >= 16 ? "J值阈值较宽松（≤" + jMax + "），入场信号偏早，" : "") +
    (jNum > 10 && jNum < 16 ? "J值阈值适中（≤" + jMax + "），平衡信号数量与质量，" : "") +
    (ampNum <= 3 ? "振幅限制较严，排除剧烈波动。" : "") +
    (ampNum >= 6 ? "振幅容忍度较高，包含更多活跃股。" : "") +
    (ampNum > 3 && ampNum < 6 ? "振幅控制适中，过滤异常波动即可。" : "") +
    "当前参数偏向" + (jNum <= 10 ? "保守埋伏型" : (jNum >= 16 ? "积极进取型" : "均衡型")) + "。";
  interpSec.append(interpHeader, interpBody);
  strategyDetail.append(interpSec);

  /* ── 条件配置 ── */
  var configSec = document.createElement("section");
  configSec.className = "strategy-section";
  var configTitle = document.createElement("h3");
  configTitle.textContent = "条件配置";
  configSec.append(configTitle);

  var blocks = document.createElement("div");
  blocks.className = "strategy-formula-blocks";

  strategyFormulaBlocks.forEach(function (block) {
    var article = document.createElement("article");
    article.className = "formula-block" + (block.fixed ? " is-fixed" : "");

    var header = document.createElement("div");
    header.className = "formula-header";
    var title = document.createElement("strong");
    title.textContent = block.title;
    header.append(title);
    if (block.fixed) {
      var badge = document.createElement("span");
      badge.className = "formula-badge";
      badge.textContent = "固定条件";
      header.append(badge);
    }
    article.append(header);

    if (block.desc) {
      var desc = document.createElement("p");
      desc.className = "formula-desc";
      desc.textContent = block.desc;
      article.append(desc);
    }

    (block.formulas || []).forEach(function (expr) {
      var line = document.createElement("code");
      line.className = "formula-expr";
      line.textContent = expr;
      article.append(line);
    });

    if (block.controls && block.controls.length) {
      var ctrl = document.createElement("div");
      ctrl.className = "formula-controls";
      block.controls.forEach(function (ctl) {
        var ctrlLabel = document.createElement("span");
        ctrlLabel.className = "formula-cond-label";
        ctrlLabel.textContent = ctl.label;
        ctrl.append(ctrlLabel);
        var input = document.createElement("input");
        input.type = "number";
        input.step = "0.1";
        input.value = String(p[ctl.key] ?? "");
        input.dataset.strategyParam = ctl.key;
        ctrl.append(input);
        if (ctl.suffix) {
          var suffix = document.createElement("span");
          suffix.className = "formula-suffix";
          suffix.textContent = ctl.suffix;
          ctrl.append(suffix);
        }
      });
      article.append(ctrl);
    }

    if (block.hints) {
      var hints = document.createElement("div");
      hints.className = "formula-hints";
      block.hints.forEach(function (h) {
        var tag = document.createElement("span");
        tag.textContent = h;
        hints.append(tag);
      });
      article.append(hints);
    }

    blocks.append(article);
  });
  configSec.append(blocks);
  strategyDetail.append(configSec);

  /* ── 通达信公式预览 ── */
  var previewSec = document.createElement("section");
  previewSec.className = "strategy-section";
  var previewTitle = document.createElement("h3");
  previewTitle.textContent = "通达信公式预览";
  var previewCode = document.createElement("code");
  previewCode.className = "formula-code-block";
  previewCode.textContent =
    "J := 3*K - 2*D;\n" +
    "J <= " + jMax + ";\n" +
    "振幅 := (H-L)/REF(C,1)*100 <= " + ampMax + ";\n" +
    "涨跌幅 := (C-REF(C,1))/REF(C,1)*100\n" +
    "  BETWEEN " + chgMin + " AND " + chgMax + ";\n" +
    "排除创业板 / 科创板 / 北交所 / ST;";
  previewSec.append(previewTitle, previewCode);
  strategyDetail.append(previewSec);

  /* ── 执行结果预览 ── */
  var resultSec = document.createElement("section");
  resultSec.className = "strategy-section";
  var resultTitle = document.createElement("h3");
  resultTitle.textContent = "执行结果预览";
  resultSec.append(resultTitle);

  /* 检查是否有选股结果 */
  var results = latestSelectionResults || [];
  if (results.length) {
    var resultList = document.createElement("div");
    resultList.className = "strategy-result-list";
    results.slice(0, 5).forEach(function (r) {
      var item = document.createElement("div");
      item.className = "strategy-result-item";
      var info = document.createElement("div");
      var name = document.createElement("b");
      name.textContent = r.name || r.symbol || r.code || "--";
      var reason = document.createElement("small");
      reason.textContent = r.reason || r.strategy_hits ? (r.strategy_hits || []).join(" / ") : "";
      info.append(name, reason);
      var score = document.createElement("span");
      score.className = "strategy-result-score";
      score.textContent = r.score ? "★".repeat(Math.min(5, Math.round(r.score))) : "";
      item.append(info, score);
      resultList.append(item);
    });
    resultSec.append(resultList);
  } else {
    var emptyHint = document.createElement("p");
    emptyHint.className = "strategy-desc";
    emptyHint.textContent = "暂无执行结果，请先点击顶部「执行选股」查看候选股票。";
    resultSec.append(emptyHint);
  }

  /* AI二次筛选草稿 */
  var draftSec = document.createElement("section");
  draftSec.className = "strategy-section";
  var draftTitle = document.createElement("h3");
  draftTitle.textContent = "AI二次筛选草稿";
  var draftDesc = document.createElement("p");
  draftDesc.className = "strategy-desc";
  draftDesc.textContent =
    "更保守一点：优先保留低位J值、振幅小、涨幅不要太高的主板股票。" +
    "排除：科创板、北交所、ST、明显高位放量回落、短期涨幅过大的标的。";
  draftSec.append(draftTitle, draftDesc);
  strategyDetail.append(draftSec);
}

async function loadStrategies() {
  try {
    const payload = await window.AlphaAgentsApi.listStrategies();
    renderStrategies(payload.strategies);
  } catch (error) {
    renderStrategies([]);
    setRunFeedback("选股策略", `读取失败：${error.message}`);
  }
}

async function saveActiveStrategy(triggerButton) {
  const finishButton = beginButtonFeedback(triggerButton, "\u4fdd\u5b58\u4e2d...");
  const params = {};
  document.querySelectorAll("[data-strategy-param]").forEach((input) => {
    params[input.dataset.strategyParam] = Number(input.value);
  });
  try {
    const payload = await window.AlphaAgentsApi.updateStrategy(activeStrategyId, {
      enabled: Boolean(document.querySelector("#strategy-enabled")?.checked),
      params,
    });
    renderStrategyDetail(payload.strategy);
    await loadStrategies();
    setRunFeedback("选股策略", `${payload.strategy.name} 已保存。`);
    finishButton("complete", "已保存");
  } catch (error) {
    finishButton("error", "保存失败");
    setRunFeedback("选股策略", `保存失败：${error.message}`);
  }
}

async function draftActiveStrategy(triggerButton) {
  const prompt = strategyAiPrompt?.value.trim();
  if (!prompt) {
    setRunFeedback("AI 策略草稿", "请先描述你的选股思路。");
    return;
  }
  const finishButton = beginButtonFeedback(triggerButton, "\u751f\u6210\u4e2d...");
  try {
    const payload = await window.AlphaAgentsApi.draftStrategy(prompt);
    renderStrategyDetail(payload.strategy);
    setRunFeedback("AI 策略草稿", "草稿已生成，确认参数后点击保存策略。");
    finishButton("complete", "已生成");
  } catch (error) {
    finishButton("error", "生成失败");
    setRunFeedback("AI 策略草稿", `生成失败：${error.message}`);
  }
}

async function loadDataSyncStatus() {
  try {
    const payload = await window.AlphaAgentsApi.getDataSyncStatus();
    latestDataSyncPayload = payload;
    setDataDate(payload);
    setRunFeedback("同步进度", dataSyncSummary(payload));
    if (payload?.freshness?.is_fresh) {
      setDataState("数据已最新");
      return;
    }
    setDataState(payload?.status === "failed" ? "同步异常" : "本地数据");
  } catch (error) {
    setDataState("状态未知");
  }
}

async function runDataSync(triggerButton) {
  const finishButton = beginButtonFeedback(triggerButton, "\u540c\u6b65\u4e2d...");
  setRunFeedback("\u540c\u6b65\u8fdb\u5ea6", dataSyncSummary(latestDataSyncPayload, "syncing"));
  try {
    const payload = await window.AlphaAgentsApi.runDataSync();
    latestDataSyncPayload = payload;
    setDataDate(payload);
    setDataState(payload?.status === "failed" ? "\u540c\u6b65\u5f02\u5e38" : "\u540c\u6b65\u5b8c\u6210");
    setRunFeedback("\u540c\u6b65\u8fdb\u5ea6", dataSyncSummary(payload));
    await loadSectors();
    await loadMarketStocks();
    finishButton("complete", "同步完成");
  } catch (error) {
    finishButton("error", "同步失败");
    setDataState("\u540c\u6b65\u5f02\u5e38");
    setRunFeedback("\u540c\u6b65\u8fdb\u5ea6", "\u540c\u6b65\u5931\u8d25\uff1a" + error.message);
  }
}

document.addEventListener("click", (event) => {
  if (!(event.target instanceof Element)) {
    return;
  }
  const clickedButton = event.target.closest("button");

  const viewButton = event.target.closest("[data-view-target]");
  if (viewButton) {
    switchView(viewButton.dataset.viewTarget);
    return;
  }

  if (event.target.closest("[data-sync-run]")) {
    runDataSync(clickedButton);
    return;
  }

  const runButton = event.target.closest("[data-run]");
  if (runButton?.dataset.run === "selection") {
    runSelection(runButton);
    return;
  }

  if (event.target.closest("[data-stock-workspace-load]")) {
    setCurrentSymbol(stockWorkspaceSymbolInput?.value || currentSymbol);
    return;
  }


  const sectorTypeButton = event.target.closest("[data-sector-type]");
  if (sectorTypeButton) {
    activeSectorType = sectorTypeButton.dataset.sectorType || "";
    activeSectorCode = "";
    document.querySelectorAll("[data-sector-type]").forEach((button) => {
      button.classList.toggle("is-active", button === sectorTypeButton);
    });
    loadSectors();
    loadMarketStocks();
    return;
  }

  const sectorItem = event.target.closest("[data-sector-code]");
  if (sectorItem) {
    activeSectorCode = sectorItem.dataset.sectorCode || "";
    document.querySelectorAll("[data-sector-code]").forEach((item) => {
      item.classList.toggle("is-active", item === sectorItem);
    });
    loadMarketStocks();
    return;
  }

  const strategyItem = event.target.closest("[data-strategy-id]");
  if (strategyItem) {
    activeStrategyId = strategyItem.dataset.strategyId || activeStrategyId;
    document.querySelectorAll("[data-strategy-id]").forEach((item) => {
      item.classList.toggle("is-active", item === strategyItem);
    });
    renderStrategyDetail(latestStrategies.find((strategy) => strategy.id === activeStrategyId));
    return;
  }

  if (event.target.closest("[data-strategy-save]")) {
    saveActiveStrategy(clickedButton);
    return;
  }

  if (event.target.closest("[data-strategy-draft]")) {
    draftActiveStrategy(clickedButton);
    return;
  }

  const caseKindButton = event.target.closest("[data-case-kind]");
  if (caseKindButton) {
    activeCaseKind = caseKindButton.dataset.caseKind || "";
    document.querySelectorAll("[data-case-kind]").forEach((button) => {
      button.classList.toggle("is-active", button === caseKindButton);
    });
    loadCaseLibrary();
    return;
  }

  if (event.target.closest("[data-open-market-view]")) {
    switchView("chat");
    var rp = document.querySelector("#right-panel");
    if (rp) rp.classList.remove("is-collapsed");
    setCurrentSymbol(currentSymbol);
    return;
  }

  const reportItem = event.target.closest(".report-item[data-report-index]");
  if (reportItem) {
    const index = Number(reportItem.dataset.reportIndex);
    const report = latestReports[index];
    document.querySelectorAll(".report-item").forEach((item) => item.classList.remove("is-active"));
    reportItem.classList.add("is-active");
    if (report?.symbol) {
      setCurrentSymbol(report.symbol, { syncChart: false });
    }
    renderResearchReport(report);
    return;
  }

  const chartTarget = event.target.closest("[data-chart-target]");
  const symbol = chartTarget?.dataset.chartTarget;
  if (symbol) {
    if (linkedCaseTitle && chartTarget.classList.contains("case-card")) {
      linkedCaseTitle.textContent = `关联走势：${symbol}`;
    }
    setCurrentSymbol(symbol);
  }
});

document.addEventListener("keydown", (event) => {
  if (!(event.target instanceof Element) || !["Enter", " "].includes(event.key)) {
    return;
  }
  const chartTarget = event.target.closest("[data-chart-target]");
  const symbol = chartTarget?.dataset.chartTarget;
  if (symbol) {
    event.preventDefault();
    setCurrentSymbol(symbol);
  }
});

stockWorkspaceSymbolInput?.addEventListener("change", () => {
  setCurrentSymbol(stockWorkspaceSymbolInput.value);
});

caseSearch?.addEventListener("input", () => {
  loadCaseLibrary();
});

loadDataSyncStatus();
refreshDashboard();
loadSectors();
loadMarketStocks();
loadStrategies();
loadStockWorkspace();
loadCaseLibrary();
loadResearchReports();
initAgentChat();
