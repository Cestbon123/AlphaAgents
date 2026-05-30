# TDX 本地日线数据源设计

## 背景
AlphaAgents 一期 MVP 需要先从 mock 数据切换到可持续更新的 A 股本地数据源。当前已验证通达信金融终端（量化模拟）可用，`D:\new_tdx_mock\vipdoc` 下已经下载了 `.day` 日线文件，并能解析出 `2026-05-06` 的有效 OHLCV 数据。

本设计采用“离线导入优先”的方式：通达信负责下载原始行情文件，AlphaAgents 负责导入、校验和读取本地数据仓。系统运行时不直接依赖通达信终端在线。

## 目标
- 首次接入时，从通达信 `.day` 文件批量导入历史日线数据。
- 每天盘后由用户手动下载通达信日线数据，再手动运行增量导入。
- AlphaAgents 后端通过本地数据仓读取行情和股票基础信息，替换当前 mock 行情数据。
- 保留 mock 数据源作为兜底，避免本地数据缺失时工作台无法启动。
- 全流程保持投研、复盘和决策辅助边界，不调用任何账户、下单或交易执行函数。

## 非目标
- 不在一期开启盘中实时行情订阅。
- 不接入通达信账户、持仓查询、委托、下单、撤单等交易能力。
- 不做自动定时下载，日线下载和导入由用户手动触发。
- 不在第一版做全市场复杂选股引擎，只先支持可配置股票池或已导入股票范围。
- 不把通达信安装路径硬编码到代码中。

## 推荐方案
采用两层本地数据结构：

1. 通达信原始数据目录：`TDX_ROOT/vipdoc/{sh,sz,bj}/lday/*.day`
2. AlphaAgents 本地 SQLite 数据仓：默认位于项目工作区的 `data/alphaagents.db`

通达信目录只作为只读原始来源。AlphaAgents 的工作流只读取 SQLite，不直接扫描 `.day` 文件。这样可以让解析、校验、去重和查询边界清晰，也方便后续替换为其他数据源。

`.day` 文件只包含日线行情，不包含完整股票名称、行业和板块关系。第一版必须保证 `market_daily` 可独立导入；`stock_info` 和 `sector_members` 可以在导入时通过 TdxQuant 只读接口补充，也可以暂时使用兜底信息，不得阻塞行情数据落库。

## 配置
新增数据源配置，优先使用环境变量，后续可迁移到配置文件：

- `ALPHAAGENTS_DATA_PROVIDER`：`mock` 或 `local`，默认先保持 `mock`
- `ALPHAAGENTS_TDX_ROOT`：通达信安装根目录，例如 `D:\new_tdx_mock`
- `ALPHAAGENTS_DATA_DB`：SQLite 文件路径，默认 `data/alphaagents.db`
- `ALPHAAGENTS_STOCK_POOL`：可选股票池，逗号分隔，例如 `000001.SZ,300750.SZ,600519.SH`

实现中不得把用户本机路径写死进业务代码。脚本可以在帮助文本中展示示例路径。

## 数据模型
SQLite 第一版包含以下表。

### `market_daily`
日线行情主表。

字段：
- `symbol`：标准证券代码，例如 `000001.SZ`
- `trade_date`：交易日期，格式 `YYYY-MM-DD`
- `open`：开盘价
- `high`：最高价
- `low`：最低价
- `close`：收盘价
- `amount`：成交额
- `volume`：成交量
- `source`：来源，固定为 `tdx_day`
- `updated_at`：导入时间

唯一约束：`symbol + trade_date`

### `stock_info`
股票基础信息和轻量基本面信息。该表是增强信息，不是日线导入的硬依赖。

字段：
- `symbol`
- `name`
- `market`：`SH`、`SZ`、`BJ`
- `board`：行业或板块摘要
- `fundamental_summary`：由通达信基础字段拼出的简要描述
- `raw_json`：原始字段 JSON，便于后续扩展
- `updated_at`

唯一约束：`symbol`

### `sector_members`
板块成分关系。该表是增强信息，不是日线导入的硬依赖。

字段：
- `sector_code`
- `sector_name`
- `symbol`
- `source`
- `updated_at`

唯一约束：`sector_code + symbol`

### `import_runs`
导入记录。

字段：
- `id`
- `started_at`
- `finished_at`
- `mode`：`bootstrap`、`daily`、`status`
- `tdx_root`
- `db_path`
- `file_count`
- `row_count`
- `min_trade_date`
- `max_trade_date`
- `status`
- `message`

## `.day` 文件解析规则
通达信日线 `.day` 文件按 32 字节一条记录解析：

- `date`：整数日期，形如 `20260506`
- `open`、`high`、`low`、`close`：整数价格，除以 100
- `amount`：浮点成交额
- `volume`：整数成交量
- `reserved`：保留字段，第一版不入库

文件名转标准代码：
- `vipdoc/sh/lday/sh600519.day` -> `600519.SH`
- `vipdoc/sz/lday/sz300750.day` -> `300750.SZ`
- `vipdoc/bj/lday/bj920992.day` -> `920992.BJ`

解析器需要跳过空文件、长度不是 32 字节整数倍的异常文件，并在导入报告中列出异常数量。

## 导入命令
新增命令行脚本，建议路径为 `scripts/import-tdx-daily.py`。

模式：
- `bootstrap`：首次批量导入全部 `.day` 文件。
- `daily`：增量导入，只更新 SQLite 中缺失或较新的日期记录。
- `status`：只读取本地数据仓，展示最新日期、股票数量、记录数量和最近一次导入状态。

示例：

```bash
.venv/bin/python scripts/import-tdx-daily.py bootstrap --tdx-root "/mnt/d/new_tdx_mock" --db data/alphaagents.db
.venv/bin/python scripts/import-tdx-daily.py daily --tdx-root "/mnt/d/new_tdx_mock" --db data/alphaagents.db
.venv/bin/python scripts/import-tdx-daily.py status --db data/alphaagents.db
```

Windows PowerShell 可通过 WSL 或 Windows Python 调用，但项目内推荐的正式数据仓落在 WSL 工作区。

## 后端读取方式
新增 `LocalDataProvider`，职责和当前 `MockBrokerDataProvider` 对齐：

- `get_candidate_symbols()`：从配置股票池读取；若未配置，则从 `market_daily` 中选择最近交易日有数据的样例股票。
- `get_stock_contexts(symbols)`：从 `stock_info` 和 `market_daily` 拼出 `StockContext`。
- `get_positions()`：第一版继续使用手工维护或 mock 持仓，不从通达信账户读取。

`StockContext` 的字段映射：
- `symbol`、`name`：来自 `stock_info`
- `board`：来自 `stock_info.board`
- `market_summary`：由最近若干日涨跌幅、成交量变化和最新收盘价生成
- `fundamental_summary`：来自 `stock_info.fundamental_summary`
- `board_heat_summary`：第一版可用板块名称和板块成员状态生成轻量摘要
- `strategy_hits`：由简单策略规则生成，例如趋势回踩、主线回流、龙头修复
- `profile_summary`：由最新行情和基础信息生成短句

## 前端和工作流影响
前端无需直接读取 SQLite。现有按钮仍调用后端 workflow API：

- 执行选股
- 执行持股分析
- 执行每日复盘
- 执行每周复盘

变化只发生在后端数据 provider。工作台可以新增一个数据状态展示项，显示当前 provider、最新交易日和最近导入时间。

## 错误处理
- `ALPHAAGENTS_DATA_PROVIDER=local` 但 SQLite 不存在：后端启动不失败，工作流返回清晰错误，并提示先运行导入命令。
- 通达信目录不存在：导入命令失败并输出路径检查建议。
- `.day` 文件损坏：跳过该文件，导入结束时报告异常文件数量和路径样例。
- 某只股票缺少 `stock_info`：允许仅用代码展示，基础信息摘要使用兜底文案。
- 本地数据过旧：`status` 命令和前端数据状态都提示最新交易日。

## 测试策略
单元测试：
- `.day` 二进制解析：构造 1-2 条记录，验证日期、价格、成交额、成交量。
- 文件名转 symbol：覆盖 `sh`、`sz`、`bj`。
- SQLite upsert：重复导入同一天不会产生重复记录。
- `LocalDataProvider.get_stock_contexts()`：给定样例库能生成完整 `StockContext`。

集成测试：
- 用临时目录放置小型 `.day` 样例文件，运行 `bootstrap`，验证 SQLite 表和导入报告。
- 先导入旧数据，再追加新日期，运行 `daily`，验证只增加缺失记录。
- `ALPHAAGENTS_DATA_PROVIDER=local` 时，选股 workflow 能从本地数据源返回结果。

手动验证：
- 用当前 `D:\new_tdx_mock\vipdoc` 数据导入。
- `status` 显示最近交易日为 `2026-05-06`。
- 前端执行选股后能看到真实股票代码和行情摘要。

## 实施顺序
1. 增加 `.day` 解析器和测试。
2. 增加 SQLite schema、repository 和 `market_daily` upsert 测试。
3. 增加 `scripts/import-tdx-daily.py` 的 `bootstrap`、`daily`、`status`，先保证日线可落库。
4. 增加可选元数据补充：能连接 TdxQuant 时写入 `stock_info` 和 `sector_members`，不能连接时跳过并报告。
5. 增加 `LocalDataProvider`，先支持股票池和行情摘要。
6. 增加配置开关，让 workflow service 可选择 `mock` 或 `local` provider。
7. 在前端 dashboard 增加数据源状态展示。
8. 补充 README 或 docs 中的手动下载和导入说明。

## 决策记录
- 选 SQLite 作为项目内数据仓，而不是让后端直接扫描 `.day` 文件。
- 第一版只导入日线、股票基础信息、板块成分，不处理分时、Tick 或实时订阅。
- 第一版不读取通达信账户持仓，持仓仍由项目内手工维护或 mock 数据提供。
- 第一版保留 mock provider，降低本地数据接入失败时的开发阻塞。

## 成功标准
- 可以从通达信 `.day` 文件导入至少沪深北三地日线数据。
- 本地 SQLite 中可以查询 `000001.SZ`、`300750.SZ`、`600519.SH` 的 `2026-05-06` 日线。
- 后端切到 `local` provider 后，选股 workflow 不依赖 mock broker 数据。
- 全量测试通过，且导入脚本有清晰的 status 输出。
- 项目没有任何交易执行能力接入。
