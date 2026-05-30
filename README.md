# AlphaAgents

个人投研助手，用于盘后复盘、选股分析和决策辅助，不涉及交易执行。

## 开发环境建议

推荐把日常开发放到 `WSL2 + Ubuntu` 里做，这样后续迁到云服务器时，Python、依赖安装、路径和脚本行为都会更接近线上环境。

当前仓库已经补好了这些开发基线：

- `pyproject.toml`：统一依赖与开发工具
- `.env.example`：环境变量模板
- `api/app`：最小 FastAPI 入口与健康检查
- `Makefile`：WSL/Linux 常用命令
- `scripts/dev.ps1`：Windows 本地兜底启动脚本

## 推荐流程：WSL / Linux

1. 安装 WSL 和 Ubuntu

```powershell
wsl --install -d Ubuntu
```

2. 在 WSL 里把仓库放到 Linux 文件系统，例如：

```bash
mkdir -p ~/workspace
cd ~/workspace
git clone <your-repo-url> alphaagents
cd alphaagents
```

3. 创建虚拟环境并安装依赖

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
cp .env.example .env
```

4. 启动开发服务

```bash
make dev
```

5. 验证接口

```bash
curl http://127.0.0.1:8000/api/v1/health
```

## Windows 临时开发

在 WSL 还没装好之前，可以先用当前 Windows Python 验证骨架：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
Copy-Item .env.example .env
.\scripts\dev.ps1
```

## 常用命令

WSL / Linux:

```bash
make dev
make test
make lint
```

Windows:

```powershell
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m ruff check .
```
