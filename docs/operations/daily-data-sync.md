# 本地通达信数据日常同步

## 适用范围

本文说明 AlphaAgents 如何从本机通达信目录同步本地数据。当前产品链路只使用本地通达信文件和项目 SQLite，不接入 TdxQuant 运行时；TdxQuant 相关脚本仅作为后续技术储备保留。

本项目只用于投研、复盘、分析和决策辅助，不执行交易。

## 当前同步内容

- 日线行情：读取 `vipdoc/{sh,sz,bj}/lday/*.day`。
- 股票名称：读取 `T0002/hq_cache/{shs,szs,bjs}.tnf`。
- 行业与细分行业：读取 `T0002/hq_cache/tdxhy.cfg`，并用 `tdxzs3.cfg`/`tdxzs.cfg` 映射名称。
- 地区/板块/概念元数据：读取 `tdxzs3.cfg`/`tdxzs.cfg`。
- 概念/题材成分股：读取 `T0002/hq_cache/infoharbor_block.dat`。

## 前置条件

- 通达信客户端已打开、已登录，并完成最新日线和板块资料下载。
- WSL 可以访问通达信目录，例如：`/mnt/d/new_tdx_mock`。
- 后端启动时配置 `ALPHAAGENTS_TDX_ROOT` 指向通达信根目录。

## 统一同步 API

```bash
curl -X POST http://127.0.0.1:8000/api/v1/data-sync/run
```

查看当前同步状态：

```bash
curl http://127.0.0.1:8000/api/v1/data-sync/status
```

返回结果包含：

- `freshness.current_time`：系统核对时使用的北京时间。
- `freshness.expected_latest_trade_date`：按当前时间推算出的预期最新交易日。
- `freshness.latest_trade_date`：本地数据库实际最新交易日。
- `freshness.is_fresh`：本地数据是否达到预期。
- `progress`：日线、本地行业/板块/概念元数据、数据新鲜度核对阶段。

后端启动示例：

```bash
ALPHAAGENTS_DATA_DB=data/alphaagents-full-verify.db \
ALPHAAGENTS_WORKFLOW_DB=data/alphaagents-workflows.db \
ALPHAAGENTS_TDX_ROOT=/mnt/d/new_tdx_mock \
ALPHAAGENTS_SELECTION_DATA_SOURCE=local \
.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

## 注意事项

- `/api/v1/market/daily-bars` 固定读取本地 SQLite 日线数据。
- 同步逻辑按 `symbol + trade_date` 幂等写入，可重复执行。
- 如果通达信本地数据没有更新，同步后的 `latest_trade_date` 不会变化。
- 如果板块资料为空，先在通达信客户端刷新行情/板块资料，再重新同步。
