from pathlib import Path

HTML = Path("frontend/index.html")
APP = Path("frontend/scripts/app.js")
API = Path("frontend/scripts/api.js")
CSS = Path("frontend/styles/app.css")
CHART = Path("frontend/scripts/chart.js")
NO_CARD_GUIDE = Path("docs/frontend-design/no-card-baseline.md")


def test_frontend_has_four_entry_stock_centric_navigation():
    html = HTML.read_text(encoding="utf-8")
    script = APP.read_text(encoding="utf-8")

    assert 'data-view-target="market"' in html
    assert 'data-view-target="strategies"' in html
    assert 'data-view-target="cases"' in html
    assert 'data-view-target="reports"' in html
    assert "看盘选股" in html
    assert "案例库" in html
    assert "分析报告" in html
    assert "复盘" not in _side_nav_slice(html)
    assert "沉淀" not in _side_nav_slice(html)
    assert "设置" not in _side_nav_slice(html)
    assert _side_nav_slice(html).count('class="nav-item') == 4
    assert "switchView" in script
    assert "viewTitles" in script
    assert "resizeMarketChart" in script
    assert "window.AlphaAgentsChart?.resize?.()" in script


def test_market_view_embeds_stock_workspace_and_actions():
    html = HTML.read_text(encoding="utf-8")
    script = APP.read_text(encoding="utf-8")

    assert 'data-view="market"' in html
    assert 'id="stock-workspace-symbol"' not in html
    assert "data-stock-workspace-load" not in html
    assert 'id="stock-workspace-content"' not in html
    assert 'id="agent-insights"' in html
    assert 'id="stock-timeline"' not in html
    assert 'class="timeline-panel"' not in html
    assert "workspace-subsection" not in html
    assert 'data-workspace-action="analysis"' in html
    assert 'data-workspace-action="operation"' in html
    assert 'data-workspace-action="review"' in html
    assert 'data-workspace-action="deposition"' in html
    assert 'data-workspace-panel="analysis"' in html
    assert "data-stock-research-run" in html
    assert "data-stock-operation-save" in html
    assert "data-stock-review-save" in html
    assert "data-stock-deposition-save" in html
    assert "let currentSymbol" in script
    assert "setCurrentSymbol" in script
    assert "loadStockWorkspace" in script
    assert "showWorkspaceAction" in script
    assert "beginButtonFeedback" in script


def test_market_view_uses_sector_filters_and_stock_list():
    html = HTML.read_text(encoding="utf-8")
    script = APP.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")

    assert 'id="sector-search"' in html
    assert 'id="sector-filter-list"' in html
    assert "market-command-bar" in html
    assert 'data-sector-type=' in html
    assert 'class="stock-list-table"' in html
    assert 'id="active-symbol-status"' in html
    assert 'id="sync-progress"' in html
    assert 'id="global-symbol-search"' not in html
    assert "normalizeSymbolSearch" in script
    assert "total_files" in script
    assert "renderSelectionResultsTable" in script
    assert "listMarketSectors" in api
    assert "listMarketStocks" in api
    assert "/market/sectors" in api
    assert "/market/stocks" in api


def test_market_sector_filter_results_are_not_overwritten_by_stale_requests():
    script = APP.read_text(encoding="utf-8")
    refresh_block = script[
        script.index("async function refreshDashboard") : script.index("async function runSelection")
    ]

    assert "latestMarketStocksRequestId" in script
    assert "requestId !== latestMarketStocksRequestId" in script
    assert "renderSelectionResults(selection)" not in refresh_block
    assert "renderSelectionResults([])" not in refresh_block


def test_strategies_view_configures_selection_strategy():
    html = HTML.read_text(encoding="utf-8")
    script = APP.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")

    assert 'data-view="strategies"' in html
    assert 'id="strategy-list"' in html
    assert 'id="strategy-detail"' in html
    assert 'id="strategy-ai-prompt"' in html
    assert "data-strategy-save" in html
    assert "data-strategy-draft" in html
    assert "listStrategies" in api
    assert "updateStrategy" in api
    assert "draftStrategy" in api
    assert "/strategies/draft" in api
    assert "strategyParamMeta" in script
    assert "strategy-param-card" in script
    assert "loadStrategies" in script
    assert "saveActiveStrategy" in script
    assert "draftActiveStrategy" in script


def test_cases_view_is_management_view_bound_to_symbols():
    html = HTML.read_text(encoding="utf-8")
    script = APP.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")

    assert 'data-view="cases"' in html
    assert 'id="case-library"' in html
    assert 'data-case-kind="风险提醒"' in html
    assert "打开个股工作台" in html
    assert "renderCaseLibrary" in script
    assert "listStockCases" in api
    assert "/stocks/cases/list" in api
    assert "dataset.chartTarget" in script


def test_reports_view_only_uses_generated_research_reports():
    html = HTML.read_text(encoding="utf-8")
    script = APP.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")
    combined = "\n".join([html, script, api])

    assert 'data-view="reports"' in html
    assert 'id="research-report-list"' in html
    assert 'id="research-report-content"' in html
    assert "TradingAgents" in html or "TradingAgents" in script
    assert "listResearchReports" in api
    assert "/reports/research" in api
    assert "runDailyReport" not in api
    assert "getLatestDailyReport" not in api
    assert "runResearchReport" not in api
    assert "getLatestResearchReport" not in api
    assert "renderResearchReports" in script
    assert "renderResearchReport" in script
    assert "财报文件" not in combined
    assert "新闻文件" not in combined
    assert "公开报告" not in combined
    assert "外部研报" not in combined


def test_frontend_uses_lucide_style_local_svg_icons_without_cdn():
    html = HTML.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")

    assert '<symbol id="icon-search-check"' in html
    assert '<symbol id="icon-sliders"' in html
    assert '<symbol id="icon-library"' in html
    assert '<symbol id="icon-file-text"' in html
    assert "icon-settings" not in html
    assert "stroke-linecap: round" in css
    assert "stroke-linejoin: round" in css
    assert "button.is-loading" in css
    assert "button.is-complete" in css
    assert "button.is-error" in css
    assert "cdn" not in html.lower()
    assert "unpkg.com" not in html.lower()
    assert "shadcn" not in html.lower()
    assert "tailwind" not in html.lower()


def test_frontend_uses_divider_first_no_card_visual_baseline():
    html = HTML.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    guide = NO_CARD_GUIDE.read_text(encoding="utf-8")

    assert "./styles/app.css?v=20260529-2" in html
    assert "Divider-first visual baseline" in css
    assert "Final no-card baseline" in css
    assert ".summary-card" in css
    assert ".case-card" in css
    assert ".status-strip.is-compact.market-command-bar" in css
    assert "width: min(300px, 28vw)" in css
    assert "border-bottom: 1px solid var(--line)" in css
    assert "background: transparent !important" in css
    assert "默认不使用卡片式容器" in guide
    assert "分割线样式" in guide


def test_frontend_keeps_local_klinecharts_contract():
    html = HTML.read_text(encoding="utf-8")
    script = CHART.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")

    assert "./vendor/klinecharts/klinecharts.min.js" in html
    assert 'id="kline-chart"' in html
    assert 'id="chart-status"' in html
    assert 'id="active-symbol-status" class="visually-hidden"' in html
    assert "本地日线 /" not in html
    assert "VOL/MACD/KDJ" not in html
    assert "data-chart-symbol" in html
    assert "klinecharts.init" in script
    assert "chart.applyNewData" in script
    assert "SHORT_TERM_BRICK" in script
    assert "ZHIXING_WASH_SHORT" in script
    assert "indicator_pane_short_term_brick" in script
    assert "indicator_pane_zhixing_wash_short" in script
    assert "const PANE_HEIGHTS" in script
    assert "const DEFAULT_SYMBOL = \"000001.SH\"" in script
    assert "const DEFAULT_INDICATOR_PANES" in script
    assert "ensureDefaultIndicators();" in script
    assert "defaultIndicatorsCreated" in script
    assert "setChartStatus(`${name}${symbol}`)" in script
    assert "本地日线 /" not in script
    assert "resizeVisibleChart" in script
    assert "chartContainer.clientWidth <= 0" in script
    assert "resize: () => requestAnimationFrame(resizeVisibleChart)" in script
    assert "./scripts/chart.js?v=20260529-1" in html
    assert "height: 1280px" in css
    assert "min-height: 1280px" in css


def test_frontend_actions_call_stock_scoped_apis():
    script = APP.read_text(encoding="utf-8")
    api = API.read_text(encoding="utf-8")

    assert "window.AlphaAgentsApi.getStockWorkspace" in script
    assert "window.AlphaAgentsApi.runStockResearch" in script
    assert "window.AlphaAgentsApi.saveStockOperation" in script
    assert "window.AlphaAgentsApi.saveStockReview" in script
    assert "window.AlphaAgentsApi.saveStockDeposition" in script
    assert "/stocks/${encodeURIComponent(symbol)}/workspace" in api
    assert "/stocks/${encodeURIComponent(symbol)}/reviews" in api
    assert "/stocks/${encodeURIComponent(symbol)}/depositions" in api
    assert "getPortfolioPositions" not in api
    assert "savePortfolioPositions" not in api
    assert "getLatestReviewCases" not in api
    assert "getDepositionCandidates" not in api


def test_frontend_files_do_not_add_trade_execution_tokens():
    combined = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (HTML, API, APP, CHART, CSS)
    )
    forbidden_trade_tokens = (
        "executeTrade",
        "placeOrder",
        "submitOrder",
        "cancelOrder",
        "brokerOrder",
        "tradeExecution",
        "下单",
        "撤单",
        "委托",
    )

    for token in forbidden_trade_tokens:
        assert token not in combined


def test_top_status_replaces_bottom_run_output():
    html = HTML.read_text(encoding="utf-8")

    assert 'class="top-status"' in html
    assert 'id="data-state"' in html
    assert 'id="sync-progress-title"' in html
    assert 'id="sync-progress"' in html
    assert 'class="run-dock"' not in html


def test_status_strip_shows_market_data_date_instead_of_render_time():
    html = HTML.read_text(encoding="utf-8")
    script = APP.read_text(encoding="utf-8")

    assert "数据日期" in html
    assert 'id="updated-at"' in html
    assert "function setDataDate" in script
    assert "market_status?.latest_trade_date" in script
    assert "freshness?.latest_trade_date" in script
    assert "./scripts/app.js?v=20260529-1" in html
    assert "toLocaleString" not in script


def _side_nav_slice(html: str) -> str:
    start = html.index('<aside class="side-nav"')
    end = html.index("</aside>", start)
    return html[start:end]
