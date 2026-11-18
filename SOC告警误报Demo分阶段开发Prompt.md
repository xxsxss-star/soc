# SOC 告警误报 Demo 分阶段开发 Prompt

## 使用方式

在另一个 Codex 窗口中打开工作目录：

```text
E:\codebase\soc
```

然后按照顺序逐个发送下面的 Prompt。每个阶段完成并检查结果后，再发送下一阶段。

两个核心设计文档：

- `SOC告警误报分层研判方案.md`
- `SOC告警误报分层研判Demo实现方案.md`

约束：

- 不要一次发送全部阶段；
- 每个阶段只完成规定范围；
- 每个阶段完成后必须运行对应验证；
- 若实现方案与实际依赖版本冲突，可以做最小必要调整，但必须说明；
- 不得为了让测试通过而删除关键规则、AI校验或安全边界；
- 不要自动提交 Git，除非明确要求；
- 后续阶段开始前先检查前一阶段已有实现，不重复创建同类代码。

---

## 阶段一：工程骨架、数据模型与模拟数据

```text
你现在需要在当前工作目录 E:\codebase\soc 中实现 SOC 告警误报分层研判 Demo 的第一阶段。

开始前请完整阅读：
1. SOC告警误报分层研判方案.md
2. SOC告警误报分层研判Demo实现方案.md

本阶段目标：搭建可运行的 Python 工程骨架，完成核心 Pydantic 数据模型、本地 JSON 模拟数据和 JsonDataStore。不要实现规则、AI、Workflow、API 或 Streamlit 页面。

具体任务：

1. 检查当前目录已有文件，保留已有内容，不覆盖用户修改。
2. 创建实现方案中规定的基础目录和 __init__.py。
3. 创建 requirements.txt 和 .env.example：
   - 使用 Python 3.11+；
   - 包含后续需要的 FastAPI、Uvicorn、Streamlit、LangGraph、Pydantic v2、pydantic-settings、OpenAI SDK、httpx、pytest；
   - 依赖版本应选择彼此兼容的当前已安装版本或可稳定安装版本。
4. 实现以下数据模型：
   - Alert、ProcessInfo、DetectionInfo；
   - EvidenceItem、EvidencePackage；
   - MatchedRule、RuleResult；
   - ConfidenceBreakdown、EvidenceReason、AIAnalysisResult；
   - TimelineEvent、DecisionResult、RunRecord；
   - 必要的 API 请求响应模型。
5. 在 data/ 下创建 8～10 条“恶意 IP 通信”预设告警，以及四类证据数据：
   - alerts.json；
   - assets.json；
   - approved_tasks.json；
   - threat_intel.json；
   - related_events.json。
6. 案例至少覆盖：
   - 授权扫描明确误报；
   - 横向移动高风险；
   - 数据外传高风险；
   - 核心资产访问恶意 IP；
   - 有授权但存在恶意情报冲突；
   - 无授权且命中恶意情报；
   - 关键字段或证据缺失；
   - AI 高置信度疑似误报；
   - AI 低置信度需要人工。
7. demo_scenario 只允许用于前端案例标签，不得作为规则或 AI 输入。
8. 实现 JsonDataStore：
   - 启动时加载并通过 Pydantic 校验 JSON；
   - 提供 list_alerts、get_alert、find_asset、find_approved_task、find_threat_intel、find_related_events；
   - 授权任务查询必须判断用户、主机、时间窗口和目标范围；
   - 行为上下文优先按 alert_id 查询，可支持 host_id 和时间窗口回退。
9. 编写本阶段测试：
   - 所有 JSON 都能成功加载；
   - 告警 ID 唯一；
   - 正确查询四类证据；
   - 授权时间和目标范围判断正确；
   - 找不到数据时返回 None；
   - demo_scenario 不会进入证据模型。

实现原则：

- 使用 apply_patch 修改文件；
- 模型字段和枚举尽量与实现方案一致；
- 不连接真实外部系统；
- 不调用大模型；
- 数据必须能够支持后续所有规则分支，不能只创建同一种理想案例。

完成后请执行：

1. Python 语法编译检查；
2. 本阶段 pytest；
3. 用一个简短脚本加载全部告警并打印数量。

最终回复必须包含：

- 创建/修改的文件；
- 模拟案例列表及每个案例用于验证什么；
- 实际执行的验证命令和结果；
- 尚未实现的内容；
- 如果存在与方案不同的调整，说明原因。

本阶段完成后停止，不要继续实现规则、Workflow、API 或页面。
```

---

## 阶段二：证据包、规则引擎与处置决策

```text
继续在 E:\codebase\soc 中完成第二阶段。开始前先检查第一阶段代码和测试结果，并重新阅读：

1. SOC告警误报分层研判方案.md
2. SOC告警误报分层研判Demo实现方案.md

本阶段只实现 EvidenceBuilder、RuleEngine 和 DecisionRouter，以及对应测试。不要实现 LangGraph、真实/Mock AI、FastAPI 或 Streamlit。

具体任务：

1. 实现 EvidenceBuilder：
   - 输入一条 Alert；
   - 按 host_id、user、dst_ip、alert_id 和告警时间查询 JsonDataStore；
   - 输出 EvidencePackage；
   - EV-001 固定为资产、EV-002 为授权活动、EV-003 为威胁情报、EV-004 为行为上下文；
   - 未查询到的数据写入 missing_evidence；
   - 查询异常写入 retrieval_errors；
   - 不得伪造缺失证据；
   - 不得把 demo_scenario 写入证据包。
2. 实现 RuleEngine，严格按照以下优先级：
   - 高风险否决规则；
   - 数据质量规则；
   - 明确误报规则；
   - AI入口规则。
3. 至少实现以下规则：
   - R-001 横向移动；
   - R-003 数据外传；
   - R-005 核心资产且目标命中恶意情报；
   - R-101 测试/扫描资产 + 有效授权 + 时间和目标均在范围内 + 无高风险行为；
   - R-201 关键告警字段缺失；
   - R-202 资产与行为证据均缺失；
   - R-301 无有效授权且目标命中恶意情报；
   - R-302 有授权但存在恶意情报或行为冲突；
   - R-399 默认进入 AI。
4. RuleResult 必须包含：
   - decision；
   - matched_rule；
   - evidence_refs；
   - need_ai；
   - need_human。
5. 实现 DecisionRouter，但 AI 部分使用构造的 AIAnalysisResult 测试，不调用模型：
   - RULE_CONFIRMED_FP → 规则确认误报，无需人工；
   - HIGH_RISK → 高优先级人工调查；
   - MANUAL_ENRICHMENT → 人工补充信息；
   - AI 输出无效 → 人工确认；
   - AI insufficient_evidence → 人工确认；
   - AI likely_true_positive → 高优先级人工调查；
   - AI likely_false_positive 且置信度 >= 85 → AI确认误报；
   - AI likely_false_positive 且置信度 < 85 → 人工确认。
6. 将阈值放到配置中，不要散落硬编码。
7. 编写测试覆盖：
   - 高风险规则优先于 R-101；
   - R-101 必须满足全部条件；
   - R-302 能进入 AI；
   - R-399 默认进入 AI；
   - 缺失证据不会被误判为明确误报；
   - AI 置信度 84 和 85 的边界；
   - AI 真实攻击结论不能自动处置。

完成后运行语法检查和全部现有 pytest。

最终回复必须列出：

- 实现的规则及准确条件；
- 每个模拟案例实际命中了哪条规则；
- 测试命令和结果；
- 是否发现数据与规则不匹配并如何修正；
- 尚未实现的内容。

本阶段完成后停止，不要继续实现 AI、LangGraph、API 或页面。
```

---

## 阶段三：AI分析、输出校验与LangGraph Workflow

```text
继续在 E:\codebase\soc 中完成第三阶段。开始前检查前两阶段实现，完整阅读两个设计文档，严格复用已有数据模型、EvidenceBuilder、RuleEngine 和 DecisionRouter。

本阶段目标：实现 Mock/Live AI 分析器、AI 输出校验和完整 LangGraph Workflow。不要实现 FastAPI 和 Streamlit。

具体任务：

1. 实现 AIAnalyzer Protocol：
   - analyze(alert, evidence) -> AIAnalysisResult。
2. 实现 MockAIAnalyzer：
   - 根据 alert_id 返回预设的结构化结果；
   - 覆盖高置信度疑似误报、低置信度疑似误报、疑似真实攻击、证据不足和非法输出测试场景；
   - Mock 结果也必须经过同一个 AIValidator，不能绕过校验。
3. 实现 LiveAIAnalyzer：
   - 使用 OpenAI-compatible SDK；
   - 从环境变量读取 base_url、api_key、model、timeout；
   - 使用 Pydantic 结构化输出或可靠 JSON Schema；
   - System Prompt 明确要求只根据 evidence_id 分析；
   - 不将 demo_scenario、预设标签或最终答案发送给模型；
   - 最多重试一次，失败后返回可识别错误，不偷偷切换为 Mock 结论。
4. 实现 AIValidator：
   - 校验 Pydantic Schema；
   - 四个置信度分项均在 0～25；
   - 四项之和必须等于 total；
   - 所有引用的 evidence_id 必须存在；
   - suggested_result 必须为合法枚举；
   - 不合法时记录错误并转人工。
5. 创建 WorkflowState、TimelineEvent 和节点函数：
   - load_alert；
   - collect_evidence；
   - check_evidence；
   - evaluate_rules；
   - analyze_with_ai；
   - validate_ai_output；
   - make_decision；
   - persist_result。
6. 使用 LangGraph StateGraph 构建固定 Workflow：
   - 规则为 RULE_CONFIRMED_FP、HIGH_RISK 或 MANUAL_ENRICHMENT 时跳过 AI；
   - 只有 NEED_AI 才进入 AI 节点；
   - AI 校验后统一进入处置决策；
   - 每个节点写入 timeline；
   - 节点异常不得导致未捕获崩溃，最终状态应为 failed 或 waiting_human。
7. 实现可配置 DEMO_NODE_DELAY_MS：
   - demo 模式用于展示节点进度；
   - 测试中设为 0。
8. 编写 Workflow 测试：
   - 规则确认路径不调用 AI；
   - 高风险路径不调用 AI；
   - NEED_AI 路径调用 AI；
   - AI 高置信度误报路径；
   - AI 低置信度人工确认路径；
   - AI 真实攻击路径；
   - AI 证据不足路径；
   - AI 引用不存在证据路径；
   - AI 超时或异常路径；
   - timeline 节点顺序正确。

实现时优先适配当前实际安装的 LangGraph API。如果实现方案中的伪代码与实际版本不一致，使用正确 API，并在最终回复中说明差异。

完成后运行语法检查和全部 pytest。

最终回复必须包含：

- Workflow 实际节点和条件边；
- 一条规则路径与一条 AI 路径的状态流转；
- Mock 和 Live 模式切换方式；
- AI 校验项；
- 测试命令和结果；
- 尚未实现的内容。

本阶段完成后停止，不要实现 FastAPI 或 Streamlit。
```

---

## 阶段四：FastAPI、后台任务与运行状态

```text
继续在 E:\codebase\soc 中完成第四阶段。先检查现有 Workflow 是否通过测试。本阶段只实现 FastAPI、RunRepository、后台运行和 API 测试，不实现 Streamlit 页面。

参考 SOC告警误报分层研判Demo实现方案.md 中的 REST API 设计，但要以当前实际模型为准保持接口一致。

具体任务：

1. 实现线程安全的内存 RunRepository：
   - create；
   - get；
   - update；
   - find_active_by_alert；
   - clear；
   - 使用 RLock 或等效方式保护共享状态。
2. 实现 RunService：
   - 创建 run_id；
   - 初始化 queued 状态；
   - 后台执行 Workflow；
   - 在节点运行期间更新 Repository；
   - 保存 timeline、evidence、rule_result、ai_result 和 decision；
   - 捕获 Workflow 异常并置为 failed。
3. 实现以下接口，统一前缀 /api/v1：
   - GET /alerts；
   - POST /runs；
   - GET /runs/{run_id}；
   - POST /runs/{run_id}/human-decision；
   - POST /demo/reset；
   - GET /health。
4. POST /runs：
   - 告警不存在返回 404；
   - 同一告警存在活动运行返回 409；
   - 成功返回 202、run_id 和 poll_url；
   - 不阻塞等待整个 Workflow 完成。
5. GET /runs/{run_id}：
   - 返回当前状态、时间线和已经生成的中间结果；
   - 完成后返回规则/AI结果和最终决策。
6. human-decision：
   - 只允许 waiting_human 状态；
   - 支持 confirm_false_positive、confirm_true_positive、continue_investigation；
   - 保存 comment 和提交时间；
   - 重复提交返回 409。
7. reset：
   - 清空运行记录和人工决定；
   - 恢复告警为 ready；
   - 不修改 data/*.json。
8. health：
   - 返回服务状态、AI模式、数据加载状态和告警数量；
   - 不泄露 API key。
9. 使用统一错误结构：code、message、details。
10. 编写 API 测试覆盖 200/202/404/409、后台完成、人工操作和重置。

注意：

- 如果 FastAPI BackgroundTasks 与 Workflow 状态更新不适合测试，可以封装 Executor，但不要引入 Celery、Redis等超出 Demo 范围的组件；
- 真实 AI 不应成为 API 测试依赖，测试使用 Mock 模式；
- 不要在接口层复制规则或决策逻辑。

完成后：

1. 运行语法检查；
2. 运行全部 pytest；
3. 本地启动 Uvicorn；
4. 使用 TestClient 或 HTTP 请求依次验证 alerts、runs、poll、human-decision、reset、health。

最终回复必须包含：

- 接口清单；
- 每个接口的实际状态码；
- 后台任务和状态更新方式；
- 验证命令与结果；
- 尚未实现的内容。

本阶段完成后停止，不要实现 Streamlit 页面。
```

---

## 阶段五：Streamlit双栏页面与演示交互

```text
继续在 E:\codebase\soc 中完成第五阶段。开始前确认 FastAPI 接口与测试通过。本阶段实现 Streamlit 页面、前端 API 客户端、轮询、人工确认和一键重置，不修改核心规则与 Workflow，除非发现明确接口缺陷。

页面目标：

- 左侧展示预设告警并逐条发送；
- 右侧展示当前 Workflow 的过程和结果；
- 清楚显示本次是规则研判还是 AI 研判；
- AI 路径显示建议结论、四项置信度、证据引用和是否需要人工；
- 支持一键刷新/重置。

具体任务：

1. 实现前端 API Client：
   - list_alerts；
   - create_run；
   - get_run；
   - submit_human_decision；
   - reset_demo；
   - health。
2. 使用 st.set_page_config(layout="wide")。
3. 页面头部：
   - 产品名称和一句话说明；
   - 当前 AI 模式；
   - 后端健康状态；
   - 一键刷新/重置按钮。
4. 左侧告警区：
   - 展示 8～10 张告警卡片；
   - 显示严重程度、名称、主机、目标 IP、场景标签和状态；
   - 每张卡片提供发送按钮；
   - 活动运行期间禁止再次发送同一告警；
   - 一次只突出展示一个当前运行。
5. 右侧结果区：
   - 未选择时显示空状态；
   - 显示 queued、证据获取、规则研判、AI研判、等待人工、完成和失败状态；
   - 使用摘要卡显示研判方式、建议结论、AI置信度、是否需要人工及原因；
   - 使用 Tab/Expander 展示 Workflow轨迹、证据包、规则结果和AI分析；
   - 规则路径明确显示“未调用AI，置信度不适用”；
   - 高风险否决使用醒目样式；
   - AI置信度旁显示“Demo启发式参考值，不是校准概率”。
6. 需要人工时显示三个按钮：
   - 确认为误报；
   - 确认为真实告警；
   - 继续调查。
7. 实现轮询：
   - 每 500～800ms 查询当前 run；
   - 完成、等待人工或失败后停止；
   - 不要无限循环阻塞页面；
   - 如果 Streamlit版本不支持可靠自动刷新，使用可维护的替代方式并说明。
8. 一键重置：
   - 调用后端 reset；
   - 清空 session_state 中的 run_id、选择项和人工状态；
   - 页面恢复所有告警待发送；
   - 不修改 JSON 文件。
9. 增加合理的空状态、加载状态、错误提示；不要追求复杂视觉效果。
10. 添加 run_demo.ps1 和 README 启动说明，确保 PowerShell 下可运行。

验证要求：

1. 启动后端和前端；
2. 演示一条规则确认误报；
3. 演示一条高风险否决；
4. 演示一条 AI 低置信度等待人工；
5. 提交一次人工结果；
6. 点击重置并确认状态恢复；
7. 运行全部自动测试。

最终回复必须包含：

- 页面结构和交互说明；
- 实际验证过的案例；
- 启动命令；
- 测试结果；
- 已知限制。

本阶段完成后停止，不要做与演示无关的大规模重构或界面美化。
```

---

## 阶段六：整体验收、修复与复试交付

```text
现在对 E:\codebase\soc 中的 SOC 告警误报分层研判 Demo 做最终验收和必要修复。

开始前完整阅读：

1. SOC告警误报分层研判方案.md
2. SOC告警误报分层研判Demo实现方案.md
3. 当前 README.md

本阶段目标是验证、修复和整理交付，不增加新的产品范围。

请依次完成：

1. 检查当前目录和 git diff，区分已有用户内容与本项目实现，不覆盖无关文件。
2. 执行全量语法检查和 pytest。
3. 启动 FastAPI 和 Streamlit，完成端到端验证。
4. 至少验证以下路径：
   - R-101 规则确认误报，不调用AI；
   - 高风险规则否决，需要人工调查；
   - R-302 进入AI，高置信度疑似误报；
   - R-302 进入AI，低置信度等待人工；
   - AI疑似真实攻击；
   - 证据不足；
   - AI输出非法或不可用；
   - 人工提交结果；
   - 一键重置。
5. 检查安全边界：
   - 高风险规则优先于误报规则；
   - 规则路径不调用AI；
   - AI不能访问demo_scenario；
   - AI引用不存在证据时必须转人工；
   - 置信度低不应直接等同于真实攻击；
   - AI真实攻击结论只进入人工调查，不执行外部处置。
6. 检查前端展示：
   - 规则/AI研判方式明确；
   - AI置信度及其限制说明明确；
   - 是否需要人工和原因明确；
   - Workflow时间线完整；
   - 重置后所有状态恢复。
7. 检查 README：
   - 环境要求；
   - 安装命令；
   - .env配置；
   - Mock和Live模式；
   - 后端、前端和一键启动方式；
   - 演示顺序；
   - 模拟数据声明；
   - 已知限制。
8. 生成一份简短的 DEMO_GUIDE.md：
   - 10～15分钟讲解顺序；
   - 推荐演示的4条告警；
   - 每条告警应看到的关键结果；
   - 可能被问到的问题及简短回答；
   - 实际投入时间和未完成项留出填写位置。
9. 只修复验收发现的问题，不引入Redis、数据库、认证、部署平台或其他新范围。

最终回复必须包含：

- 最终实现摘要；
- 全部验证命令和结果；
- 端到端验证案例及实际输出；
- 仍存在的限制或风险；
- 本地启动步骤；
- 适合复试现场的演示顺序；
- 重要文件路径。

如果任何核心路径没有真正验证，不要声称项目已经完成，要明确指出阻塞点。
```

---

## 可选：出现中断后的恢复 Prompt

如果另一个窗口中途停止，使用下面的 Prompt 恢复：

```text
请继续处理 E:\codebase\soc 中尚未完成的 SOC 告警误报分层研判 Demo。

不要从头重写。先执行以下检查：

1. 阅读 SOC告警误报分层研判方案.md；
2. 阅读 SOC告警误报分层研判Demo实现方案.md；
3. 检查现有目录、git diff、测试和 README；
4. 总结当前已经完成到哪个阶段；
5. 找出当前阶段尚未满足的验收项；
6. 只完成当前阶段剩余工作并运行验证。

请保留已有实现和用户修改。不要自动跳到下一阶段。完成后说明修改文件、验证结果、剩余任务和下一阶段建议。
```
