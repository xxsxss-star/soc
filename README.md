# AlertLens：SOC 告警误报分层研判 Demo

AlertLens 将原始告警与资产信息、授权任务、威胁情报和行为上下文组合成可追溯的标准化证据包，再通过确定性规则、受约束 AI 分析和人工复核完成分层研判。

系统明确限制模型的能力边界：AI 只负责分析复杂证据并给出建议，结果还要经过结构校验、证据引用校验和决策路由；高风险告警、证据缺失以及低置信度结果均由人工处理。

## 系统组成

| 服务 | 技术 | 作用 | 公网暴露 |
|---|---|---|---|
| `backend` | FastAPI + LangGraph | 证据聚合、规则研判、AI 分析和决策路由 | 否 |
| `frontend` | Streamlit | 告警研判演示界面 | 否 |
| `nginx` | Nginx | 统一公网入口、反向代理和静态讲解页 | `80` |

部署后的访问关系：

```text
浏览器
  ↓ HTTP 80
Nginx
  ├─ /        → Streamlit :8501
  └─ /report  → report.html

Streamlit
  └─ Docker 内部网络 → FastAPI :8000
```

## 云服务器部署

### 1. 服务器准备

推荐使用 Linux 云服务器，最低建议配置为 2 核 CPU、2 GB 内存。服务器需要安装：

- Git
- Docker Engine
- Docker Compose 插件（使用 `docker compose` 命令）

确认安装成功：

```bash
git --version
docker --version
docker compose version
```

云服务器安全组需要开放：

| 端口 | 用途 |
|---|---|
| `22` | SSH 登录 |
| `80` | Web 访问 |
| `443` | 后续配置 HTTPS 时使用 |

不需要向公网开放 `8000` 和 `8501`，它们只用于 Docker 容器内部通信。

### 2. 从 GitHub 克隆项目

```bash
git clone https://github.com/xxsxss-star/soc.git
cd soc
```

确认部署文件存在：

```bash
ls Dockerfile compose.yaml nginx.conf .env.production.example
```

### 3. 创建生产环境配置

从模板复制配置文件：

```bash
cp .env.production.example .env.production
```

默认使用 Mock AI，不需要 API Key，可以直接部署：

```dotenv
APP_ENV=production
AI_MODE=mock
AI_FALSE_POSITIVE_THRESHOLD=85
DEMO_NODE_DELAY_MS=0
DATA_DIR=/app/data
```

如果需要使用真实 OpenAI-compatible 模型，编辑配置：

```bash
nano .env.production
```

填写：

```dotenv
APP_ENV=production

AI_MODE=live
OPENAI_API_KEY=你的API密钥
OPENAI_BASE_URL=https://你的接口地址/v1
OPENAI_MODEL=你的模型名称
AI_TIMEOUT_SECONDS=15
AI_MAX_RETRIES=1

AI_FALSE_POSITIVE_THRESHOLD=85
DEMO_NODE_DELAY_MS=0
DATA_DIR=/app/data
```

`.env.production` 包含密钥，已经被 `.dockerignore` 和 `.gitignore` 排除，不要手动提交到 Git。

### 4. 构建并启动

```bash
docker compose up -d --build
```

第一次构建需要下载 Python、Nginx 和项目依赖，耗时取决于服务器网络。构建完成后检查容器：

```bash
docker compose ps
```

正常情况下，`backend` 和 `frontend` 应显示为 `healthy`，`nginx` 应显示为 `Up`。

### 5. 访问系统

假设服务器公网 IP 为 `1.2.3.4`：

- 告警研判系统：<http://1.2.3.4/>
- 项目讲解页面：<http://1.2.3.4/report>

如果无法访问，先确认云平台安全组和服务器防火墙已经允许 TCP `80`。

### 6. 查看日志

查看全部服务日志：

```bash
docker compose logs -f
```

分别查看服务日志：

```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f nginx
```

按 `Ctrl+C` 只会退出日志查看，不会停止容器。

### 7. 停止和重新启动

停止服务但保留容器：

```bash
docker compose stop
```

重新启动：

```bash
docker compose start
```

停止并删除容器和网络：

```bash
docker compose down
```

`docker compose down` 不会删除 Git 项目文件，但当前 Demo 的运行记录保存在进程内存中，容器停止或重建后会清空。

### 8. 修改环境变量后生效

编辑 `.env.production` 后无需重新构建镜像，重新创建容器即可：

```bash
docker compose up -d --force-recreate
```

如果修改了源代码、`requirements.txt` 或 `Dockerfile`，需要重新构建：

```bash
docker compose up -d --build
```

### 9. 从 GitHub 更新部署

```bash
cd soc
git pull
docker compose up -d --build
```

更新后检查：

```bash
docker compose ps
docker compose logs --tail=100 backend frontend nginx
```

## 常见部署问题

### 构建 Python 依赖很慢

如果 `pip install` 长时间没有进展，可以先按 `Ctrl+C` 取消构建，再在 `Dockerfile` 中为两条 pip 命令增加可访问的镜像源，然后重新执行：

```bash
docker compose up -d --build
```

已经完成的 Docker 层通常会被缓存。

### `port is already allocated`

说明服务器的 `80` 端口已被其他程序占用：

```bash
ss -lntp | grep ':80'
```

需要停止已有 Web 服务，或者把 `compose.yaml` 中 Nginx 的端口映射从 `80:80` 改为其他端口，例如 `8080:80`。

### 后端或前端一直不健康

```bash
docker compose ps
docker compose logs --tail=200 backend
docker compose logs --tail=200 frontend
```

重点检查 `.env.production`、模型配置、数据目录以及容器是否能访问模型接口。

### 修改 API Key 后仍使用旧配置

仅执行 `docker compose restart` 不一定会重新读取 Compose 的环境文件。应执行：

```bash
docker compose up -d --force-recreate
```

## Windows 本地运行

### 环境要求

- Windows PowerShell
- Python 3.11 或更高版本
- 默认使用本地 Mock AI，不需要 API Key

### 首次安装

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

### 一键启动

```powershell
.\run_demo.ps1
```

启动后访问：

- Streamlit：<http://127.0.0.1:8501>
- FastAPI 文档：<http://127.0.0.1:8000/docs>

关闭前端终端后，脚本会同时关闭它启动的后端进程。

### 分别启动

后端：

```powershell
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

前端：

```powershell
$env:API_BASE_URL = "http://127.0.0.1:8000/api/v1"
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

## AI 模式

稳定演示使用：

```dotenv
AI_MODE=mock
```

真实模型模式：

```dotenv
AI_MODE=live
OPENAI_API_KEY=...
OPENAI_BASE_URL=...
OPENAI_MODEL=...
AI_TIMEOUT_SECONDS=15
AI_MAX_RETRIES=1
```

Live 调用失败不会自动切换为 Mock 结论，而是安全转入人工确认。

## 页面操作

1. 从左侧选择预设告警并点击“发送告警”；
2. 右侧展示 Workflow 节点、规则结果和证据引用；
3. 规则路径直接显示命中规则，并标明未调用 AI；
4. AI 路径展示建议结论、四项置信度、支持证据与缺失证据；
5. `waiting_human` 状态可选择确认误报、确认真实告警或继续调查；
6. 点击“一键刷新 / 重置”清空运行状态并恢复模拟告警。

推荐演示案例：

- `ALT-001`：授权扫描，规则确认误报；
- `ALT-002`：横向移动，高风险否决；
- `ALT-008`：AI 高置信疑似误报；
- `ALT-009`：AI 低置信疑似误报，等待人工确认。

## 测试

Windows：

```powershell
.\.venv\Scripts\python.exe -m compileall -q backend frontend tests app.py
.\.venv\Scripts\python.exe -m pytest -q
```

Linux：

```bash
python -m compileall -q backend frontend tests app.py
python -m pytest -q
```

## Demo 边界与已知限制

- 数据来自本地 JSON，不连接真实 SOC、CMDB、EDR 或威胁情报平台；
- AI 置信度是 Demo 启发式参考分，不是经过真实样本校准的准确率；
- 运行记录和人工决定保存在单进程内存中，服务重启后清空；
- 当前没有认证、数据库或跨进程任务队列；
- Demo 不执行封禁、隔离、关单等不可逆安全操作；
- 当前部署不能横向扩展多个后端副本，否则不同进程间无法共享运行状态。

复试现场的讲解顺序和推荐案例见 [DEMO_GUIDE.md](DEMO_GUIDE.md)。
