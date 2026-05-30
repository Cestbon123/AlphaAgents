const dataState = document.querySelector("#data-state");
const updatedAt = document.querySelector("#updated-at");
const syncProgressTitle = document.querySelector("#sync-progress-title");
const syncProgress = document.querySelector("#sync-progress");
const activeStrategyName = document.querySelector("#active-strategy-name");
const activeSymbolStatus = document.querySelector("#active-symbol-status");
const pageTitle = document.querySelector("#page-title");
const pageSubtitle = document.querySelector("#page-subtitle");
const sectorSearch = document.querySelector("#sector-search");
const sectorFilterList = document.querySelector("#sector-filter-list");
const selectionResults = document.querySelector("#selection-results");
const selectionPageStatus = document.querySelector("#selection-page-status");
const stockWorkspaceSymbolInput = document.querySelector("#stock-workspace-symbol");
const stockWorkspaceStatus = document.querySelector("#stock-workspace-status");
const agentInsights = document.querySelector("#agent-insights");
const stockOperationAction = document.querySelector("#stock-operation-action");
const stockOperationReason = document.querySelector("#stock-operation-reason");
const stockReviewConclusion = document.querySelector("#stock-review-conclusion");
const stockReviewReason = document.querySelector("#stock-review-reason");
const stockDepositionTitle = document.querySelector("#stock-deposition-title");
const stockDepositionContent = document.querySelector("#stock-deposition-content");
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
  market: ["看盘选股", "Market Screener"],
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

function inferMarketSuffix(code) {
  if (/^(6|688|689)/.test(code)) {
    return "SH";
  }
  if (/^(0|2|3)/.test(code)) {
    return "SZ";
  }
  if (/^(4|8|9)/.test(code)) {
    return "BJ";
  }
  return "";
}

function normalizeSymbolSearch(value) {
  const raw = text(value, "").trim().toUpperCase();
  const match = raw.match(/^(\d{6})(?:\.(SH|SZ|BJ))?$/);
  if (!match) {
    return "";
  }
  const suffix = match[2] || inferMarketSuffix(match[1]);
  return suffix ? `${match[1]}.${suffix}` : "";
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
  document.querySelectorAll("[data-view]").forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.view === viewName);
  });
  document.querySelectorAll("[data-view-target]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.viewTarget === viewName);
  });
  const [title, subtitle] = viewTitles[viewName] || viewTitles.market;
  if (pageTitle) {
    pageTitle.textContent = title;
  }
  if (pageSubtitle) {
    pageSubtitle.textContent = subtitle;
  }
  if (viewName === "market") {
    resizeMarketChart();
  }
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

function showWorkspaceAction(actionName = "analysis") {
  document.querySelectorAll("[data-workspace-action]").forEach((button) => {
    button.classList.toggle("is-active", button.dataset.workspaceAction === actionName);
  });
  document.querySelectorAll("[data-workspace-panel]").forEach((panel) => {
    panel.classList.toggle("is-active", panel.dataset.workspacePanel === actionName);
  });
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
      query: sectorSearch?.value.trim() || "",
      limit: 120,
    });
    renderSectors(payload.sectors);
  } catch (error) {
    renderSectors([]);
    setRunFeedback("板块筛选", `读取失败：${error.message}`);
  }
}

async function loadMarketStocks() {
  const requestId = ++latestMarketStocksRequestId;
  try {
    const payload = await window.AlphaAgentsApi.listMarketStocks({
      sector_code: activeSectorCode,
      limit: 120,
    });
    if (requestId !== latestMarketStocksRequestId) {
      return;
    }
    renderSelectionResults(payload.stocks, { mode: "quotes" });
  } catch (error) {
    if (requestId !== latestMarketStocksRequestId) {
      return;
    }
    renderSelectionResults([], { mode: "quotes" });
    setRunFeedback("股票列表", `读取失败：${error.message}`);
  }
}

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
  latestSelectionResults.slice(0, 120).forEach((result) => {
    const stock = mode === "quotes" ? result : stockFromSelection(result);
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

async function runCurrentStockResearch(triggerButton) {
  const finishButton = beginButtonFeedback(triggerButton, "\u751f\u6210\u4e2d...");
  const symbol = stockWorkspaceSymbolInput?.value.trim() || currentSymbol;
  setRunFeedback("分析报告", `正在生成 ${symbol} 的 TradingAgents 风格报告。`);
  try {
    const payload = await window.AlphaAgentsApi.runStockResearch(symbol);
    renderStockWorkspace(payload.workspace);
    renderResearchReport(payload.report);
    await loadResearchReports();
    switchView("reports");
    setRunFeedback("分析报告", `报告已生成：${text(payload.report?.final_decision, "--")}`);
    finishButton("complete", "已生成");
  } catch (error) {
    finishButton("error", "生成失败");
    setRunFeedback("分析报告", `生成失败：${error.message}`);
  }
}

async function saveCurrentStockOperation(triggerButton) {
  const finishButton = beginButtonFeedback(triggerButton, "\u4fdd\u5b58\u4e2d...");
  const action = stockOperationAction?.value.trim() || "观察";
  const reason = stockOperationReason?.value.trim() || "个股工作台手动记录";
  try {
    const payload = await window.AlphaAgentsApi.saveStockOperation(currentSymbol, {
      operation_date: todayText(),
      user_action: action,
      reason,
      result_summary: reason,
    });
    renderStockWorkspace(payload.workspace);
    setRunFeedback("记录操作", `${currentSymbol} 操作记录已保存。`);
    finishButton("complete", "已保存");
  } catch (error) {
    finishButton("error", "保存失败");
    setRunFeedback("记录操作", `保存失败：${error.message}`);
  }
}

async function saveCurrentStockReview(triggerButton) {
  const finishButton = beginButtonFeedback(triggerButton, "\u4fdd\u5b58\u4e2d...");
  const conclusion = stockReviewConclusion?.value.trim() || "用户主动复盘";
  const keyReason = stockReviewReason?.value.trim() || "围绕当前股票补充复盘原因";
  try {
    const payload = await window.AlphaAgentsApi.saveStockReview(currentSymbol, {
      review_date: todayText(),
      user_action: stockOperationAction?.value.trim() || "观察",
      review_conclusion: conclusion,
      key_reason: keyReason,
      result_summary: keyReason,
      worth_depositing: Boolean(stockDepositionTitle?.value.trim()),
    });
    renderStockWorkspace(payload.workspace);
    await loadCaseLibrary();
    setRunFeedback("写复盘", `${currentSymbol} 复盘已保存。`);
    finishButton("complete", "已保存");
  } catch (error) {
    finishButton("error", "保存失败");
    setRunFeedback("写复盘", `保存失败：${error.message}`);
  }
}

async function saveCurrentStockDeposition(triggerButton) {
  const finishButton = beginButtonFeedback(triggerButton, "\u4fdd\u5b58\u4e2d...");
  const title = stockDepositionTitle?.value.trim() || `${currentSymbol} 复盘沉淀`;
  const content = stockDepositionContent?.value.trim() || "从当前个股工作台手动沉淀。";
  try {
    const payload = await window.AlphaAgentsApi.saveStockDeposition(currentSymbol, {
      kind: "模式识别",
      title,
      content,
      source: `${currentSymbol} 个股工作台`,
    });
    renderStockWorkspace(payload.workspace);
    await loadCaseLibrary();
    setRunFeedback("沉淀经验", `${currentSymbol} 沉淀经验已保存。`);
    finishButton("complete", "已保存");
  } catch (error) {
    finishButton("error", "保存失败");
    setRunFeedback("沉淀经验", `保存失败：${error.message}`);
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
  const enabled = document.createElement("label");
  enabled.className = "strategy-enabled";
  enabled.innerHTML = `<input type="checkbox" id="strategy-enabled" ${strategy.enabled ? "checked" : ""} /> 启用策略`;
  const overview = document.createElement("article");
  overview.className = "strategy-overview";
  overview.innerHTML = `
    <strong>${text(strategy.name)}</strong>
    <span>${text(strategy.description, "结构化选股策略")}</span>
  `;
  const params = document.createElement("div");
  params.className = "strategy-param-grid";
  Object.entries(strategy.params || {}).forEach(([key, value]) => {
    const meta = strategyParamMeta[key] || {
      label: key,
      helper: "策略参数",
      suffix: "",
    };
    const label = document.createElement("label");
    label.className = "strategy-param-card";
    const title = document.createElement("span");
    title.textContent = meta.label;
    const input = document.createElement("input");
    input.type = "number";
    input.step = "0.1";
    input.value = String(value);
    input.dataset.strategyParam = key;
    const helper = document.createElement("small");
    helper.textContent = meta.suffix ? `${meta.helper} 单位：${meta.suffix}` : meta.helper;
    label.append(title, input, helper);
    params.append(label);
  });
  const rules = document.createElement("div");
  rules.className = "strategy-rules";
  const rulesTitle = document.createElement("h3");
  rulesTitle.textContent = "当前策略会检查这些条件";
  rules.append(rulesTitle);
  asList(strategy.rules).forEach((rule) => {
    const item = document.createElement("article");
    item.innerHTML = `<strong>${text(rule.label)}</strong><span>${text(rule.expected)}</span>`;
    rules.append(item);
  });
  strategyDetail.append(overview, enabled, params, rules);
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

  const workspaceActionButton = event.target.closest("[data-workspace-action]");
  if (workspaceActionButton) {
    showWorkspaceAction(workspaceActionButton.dataset.workspaceAction);
    return;
  }

  if (event.target.closest("[data-stock-workspace-load]")) {
    setCurrentSymbol(stockWorkspaceSymbolInput?.value || currentSymbol);
    return;
  }

  if (event.target.closest("[data-stock-research-run]")) {
    runCurrentStockResearch(clickedButton);
    return;
  }

  if (event.target.closest("[data-stock-operation-save]")) {
    saveCurrentStockOperation(clickedButton);
    return;
  }

  if (event.target.closest("[data-stock-review-save]")) {
    saveCurrentStockReview(clickedButton);
    return;
  }

  if (event.target.closest("[data-stock-deposition-save]")) {
    saveCurrentStockDeposition(clickedButton);
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
    switchView("market");
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

sectorSearch?.addEventListener("input", () => {
  loadSectors();
});

sectorSearch?.addEventListener("change", () => {
  const symbol = normalizeSymbolSearch(sectorSearch.value);
  if (symbol) {
    setCurrentSymbol(symbol);
  }
});

sectorSearch?.addEventListener("keydown", (event) => {
  if (event.key !== "Enter") {
    return;
  }
  const symbol = normalizeSymbolSearch(sectorSearch.value);
  if (symbol) {
    event.preventDefault();
    setCurrentSymbol(symbol);
  }
});

showWorkspaceAction("analysis");
loadDataSyncStatus();
refreshDashboard();
loadSectors();
loadMarketStocks();
loadStrategies();
loadStockWorkspace();
loadCaseLibrary();
loadResearchReports();
