from pathlib import Path

REQUIREMENTS_PATH = Path("docs/requirements/stock-centric-v2.md")
FRONTEND_GUIDELINES_PATH = Path("docs/frontend-design/stock-centric-ui-guidelines.md")


def test_stock_centric_requirements_document_exists_and_locks_product_direction():
    content = REQUIREMENTS_PATH.read_text(encoding="utf-8")

    assert "看盘选股" in content
    assert "选股策略" in content
    assert "案例库" in content
    assert "分析报告" in content
    assert "currentSymbol" in content
    assert "StockWorkspace" in content
    assert "复盘和沉淀不再作为主导航入口" in content
    assert "TradingAgents" in content
    assert "DeepSeek" in content
    assert "TradingAgents/DeepSeek 个股研究报告" in content
    assert "不展示财报文件、新闻文件、券商研报文件或外部公开报告库" in content
    assert "不提供交易执行、下单、撤单或券商委托能力" in content
    assert "日报/周报" not in content


def test_frontend_design_guidelines_exist_and_lock_implementation_choices():
    content = FRONTEND_GUIDELINES_PATH.read_text(encoding="utf-8")

    assert "原生 HTML/CSS/JS" in content
    assert "KLineCharts" in content
    assert "Lucide 风格" in content
    assert "本地 SVG symbol sprite" in content
    assert "自研轻量 CSS/JS" in content
    assert "侧边导航" in content
    assert "股票列表" in content
    assert "报告列表项" in content
    assert "案例卡片" in content
    assert "时间线" in content
    assert "不使用 CDN" in content
    assert "不使用 React、shadcn/ui、Tailwind" in content
    assert "设置/账户" not in content


def test_frontend_design_guidelines_keep_four_page_information_architecture():
    content = FRONTEND_GUIDELINES_PATH.read_text(encoding="utf-8")

    assert "### 看盘选股" in content
    assert "### 选股策略" in content
    assert "### 案例库" in content
    assert "### 分析报告" in content
    assert "点击任何股票卡片或列表项都调用统一 `setCurrentSymbol(symbol)`" in content
    assert "不展示财报文件、新闻文件或外部公开报告文件入口" in content
    assert "综合研报" not in content
    assert "导出报告" not in content
    assert "不把复盘和沉淀放回主导航" in content
