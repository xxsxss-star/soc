# AlertLens：SOC 告警误报分层研判 Demo

AlertLens 将原始告警与资产、授权任务、威胁情报和行为上下文组合成可追溯证据包，通过确定性规则、受约束 AI 分析和人工复核完成分层研判。

## 环境要求

- Windows PowerShell
- Python 3.11 或更高版本
- 默认使用本地 Mock AI，不需要 API Key

## 首次安装

在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

如果系统的 `python` 不是 Python 3.11+，请将第一条命令替换为本机对应解释器路径。

## `.env` 配置

- `AI_MODE=mock|live`：演示模式或真实模型模式。
- `OPENAI_API_KEY`、`OPENAI_BASE_URL`、`OPENAI_MODEL`：仅 Live 模式需要；密钥不要提交到仓库。
- `AI_TIMEOUT_SECONDS`、`AI_MAX_RETRIES`：Live 调用超时和重试次数，失败后转人工，不自动切换 Mock。
- `AI_FALSE_POSITIVE_THRESHOLD`：AI 疑似误报自动确认阈值，默认 85。
- `DEMO_NODE_DELAY_MS`：节点展示延迟；测试建议设为 0。
- `DATA_DIR`：本地模拟 JSON 目录，默认 `./data`。
- `API_BASE_URL`：前端访问后端的地址，默认 `http://127.0.0.1:8000/api/v1`。

## 一键启动

```powershell
.\run_demo.ps1
```

启动后访问：

- Streamlit：<http://127.0.0.1:8501>
- FastAPI 文档：<http://127.0.0.1:8000/docs>

关闭前端终端后，脚本会同时关闭它启动的后端进程。

## 分别启动

打开两个 PowerShell 窗口，均进入项目根目录。

窗口一：

```powershell
$env:PYTHONPATH = (Get-Location).Path
.\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

窗口二：

```powershell
$env:API_BASE_URL = "http://127.0.0.1:8000/api/v1"
.\.venv\Scripts\python.exe -m streamlit run app.py --server.address 127.0.0.1 --server.port 8501
```

## AI 模式

稳定演示使用：

```dotenv
AI_MODE=mock
```

真实模型模式需要在 `.env` 中配置：

```dotenv
AI_MODE=live
OPENAI_API_KEY=...
OPENAI_BASE_URL=...
OPENAI_MODEL=...
AI_TIMEOUT_SECONDS=15
AI_MAX_RETRIES=1
```

Live 调用失败不会偷偷切换为 Mock，而是安全转人工确认。

## 页面操作

1. 从左侧选择一条预设告警并点击“发送告警”；
2. 右侧每 700ms 更新 Workflow 轨迹；
3. 规则路径直接显示命中规则，并说明未调用 AI；
4. AI 路径展示建议结论、四项置信度、证据引用与后续建议；
5. `waiting_human` 状态可选择确认误报、确认真实告警或继续调查；
6. 点击“一键刷新 / 重置”清空运行状态并恢复全部告警。

推荐演示案例：

- `ALT-001`：规则确认授权扫描误报；
- `ALT-002`：横向移动高风险否决；
- `ALT-009`：AI 低置信度，等待人工确认。

## 测试

```powershell
.\.venv\Scripts\python.exe -m compileall -q backend frontend tests app.py
.\.venv\Scripts\python.exe -m pytest -q
```

## Demo 边界

- 数据来自本地 JSON，不连接真实 SOC、CMDB、EDR 或威胁情报平台；
- AI 置信度是 Demo 启发式参考值，不是经过真实样本校准的概率；
- 运行状态保存在单进程内存中，服务重启后清空；
- Demo 不执行封禁、隔离或关单等不可逆安全操作。

## 已知限制

- 运行记录和人工决定仅保存在单进程内存中，服务重启或重置后清空。
- Mock 结果和阈值只用于演示分支，不代表生产识别准确率；AI 置信度不是校准概率。
- Live 模式需要可访问的 OpenAI-compatible 服务，失败时安全转人工，不保证离线可用。
- 当前没有认证、数据库、跨进程任务队列或真实外部处置能力。

复试现场的 10～15 分钟顺序、四条推荐告警和问答见 [DEMO_GUIDE.md](DEMO_GUIDE.md)。
