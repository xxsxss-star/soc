# SOC 告警误报分层研判 Demo 方案

## 1. 文档目的

本文档用于定义复试作品的产品目标、数据结构、证据来源、处理流程、评分机制、演示范围和效果验证方法，作为后续 Demo 开发与复试讲解的依据。

作品暂定名称：**AlertLens——面向 SOC 分析师的可解释告警初筛助手**。

一句话介绍：

> 将分散的告警和上下文组装为可追溯的证据包，通过确定性规则、AI 证据分析和人工复核三层机制，帮助 SOC 分析师更快、更安全地识别疑似误报。

---

## 2. 背景与问题定义

安全运营中心（SOC）每天会产生大量安全告警，其中包含重复告警、信息不足的告警和误报。分析师需要在资产系统、终端日志、威胁情报、授权任务和历史工单之间反复查询，才能判断某条告警是否值得继续调查。

本作品不尝试解决所有 SOC 告警问题，而是聚焦以下具体问题：

> 在信息分散、告警数量较多的情况下，如何帮助一线 SOC 分析师快速判断一条告警是否为疑似误报，并获得可核查的判断依据与下一步建议。

### 2.1 目标用户

- 一线 SOC 告警分析师；
- 负责初步分类、调查和处置安全告警的安全运营人员。

### 2.2 用户痛点

- 原始告警字段有限，无法直接判断是否误报；
- 研判证据分散，人工查询耗时；
- 单纯依靠固定规则难以处理复杂上下文；
- 单纯依靠大模型存在幻觉、结果不稳定和分数不可解释的问题；
- 错误地把真实攻击关闭为误报，风险远高于多调查一条告警。

### 2.3 方案目标

- 自动聚合告警研判所需的上下文证据；
- 使用确定性规则快速处理明确场景；
- 使用 AI 对复杂证据进行归纳、冲突分析和建议生成；
- 使用可拆解的评分机制进行分级路由；
- 对高风险和证据不足的告警保留人工决策权；
- 让每个结论都能追溯到具体证据。

### 2.4 非目标

- 不搭建完整 SIEM、EDR 或 SOC 平台；
- 不宣称能够自动识别所有误报；
- 不使用 AI 自报的“置信度”直接决定是否关单；
- 不在 Demo 中训练生产级安全分类模型；
- 不把模拟数据上的结果描述为真实生产效果；
- 不让大模型直接执行不可逆的安全处置动作。

---

## 3. 核心设计原则

### 3.1 告警不等于证据完整

告警通常只能说明“检测到了什么”，不能单独证明它是真实攻击或误报。研判输入应由以下内容共同构成：

> 原始告警 + 资产上下文 + 授权活动 + 威胁情报 + 行为上下文

考虑本项目只是一个 4 小时左右的 Demo，第一版只保留以上四类补充证据，不接入历史研判结果。历史案例检索可作为后续扩展能力，不进入本次实现范围。

### 3.2 确定性判断与概率性分析分离

- 规则层负责可明确验证的事实；
- AI 层负责归纳复杂上下文、解释矛盾和生成建议；
- 处置层根据规则、评分、安全否决条件和人工意见作出最终决策。

### 3.3 AI 只能依据输入证据

AI 的每一项判断必须引用证据编号。输入中不存在的信息不得作为事实使用；证据不足时必须明确输出“无法判断”以及缺失的信息。

### 3.4 高风险条件优先

即使命中白名单或 AI 以较高置信度判断为疑似误报，只要出现提权、横向移动、数据外传、核心资产受影响等高风险条件，就不得直接确认误报。

### 3.5 全程可审计

系统需要保留：

- 命中的规则；
- 使用的证据；
- AI 输出；
- AI 置信度分项；
- 最终处置人和处置结果。

---

## 4. 总体处理流程

```text
用户在左侧点击“发送告警”
        │
        ▼
告警进入后端 Workflow，初始化运行状态
        │
        ▼
根据 host_id、user、dst_ip、alert_id 和时间窗口
查询本地模拟数据并生成标准化证据包
        │
        ▼
规则研判节点
   ├─ 命中明确误报规则：规则直接确认
   ├─ 命中高风险规则：转高优先级人工调查
   └─ 规则不能确定：进入 AI 研判
        │
        ▼
AI 基于证据输出结论、置信度、理由和建议
        │
        ▼
后端校验 AI 输出和证据引用
        │
        ▼
处置决策节点
   ├─ 疑似误报 + 高置信度 + 无否决项：确认误报
   ├─ 疑似误报但置信度不足：人工确认
   ├─ 证据不足或冲突：人工补充研判
   └─ 疑似真实攻击或命中高风险项：高优先级人工调查
        │
        ▼
右侧展示完整研判过程与最终结果
```

规则直接确认和 AI 高置信度确认都只表示 Demo 中的状态变化。真实生产环境中是否允许自动关闭，需要结合组织策略和经过真实数据校准的阈值决定。

## 4.1 Agent Workflow 设计

本项目使用 **Workflow 型 Agent**，而不是让大模型自由决定下一步做什么。每个节点职责固定，节点之间通过条件边连接。这样既能体现 Agent 编排能力，又能保证安全场景中的流程可控、结果可复现。

### Workflow 状态

一次告警研判共用一个状态对象：

```json
{
  "run_id": "RUN-001",
  "alert": {},
  "evidence_package": {},
  "matched_rules": [],
  "high_risk_veto": false,
  "analysis_mode": null,
  "ai_result": null,
  "final_action": null,
  "status": "received",
  "timeline": []
}
```

### Workflow 节点

| 节点 | 输入 | 主要工作 | 输出/下一步 |
|---|---|---|---|
| 1. 接收告警 | 用户点击发送的告警 | 生成 `run_id`，把告警状态改为处理中 | 进入证据获取节点 |
| 2. 证据获取 | 原始告警 | 按关联键查询四个本地模拟数据源 | 生成证据包 |
| 3. 证据完整性检查 | 证据包 | 检查必要字段、缺失证据和关联失败 | 标记缺失项，继续规则研判 |
| 4. 规则研判 | 告警和证据包 | 按优先级执行高风险、明确误报和转 AI 规则 | 直接结束或进入 AI 节点 |
| 5. AI 研判 | 证据包 | 输出建议结论、分项置信度、证据引用和建议 | 进入 AI 输出校验 |
| 6. AI 输出校验 | AI 结果、证据包 | 校验 JSON、枚举值和证据编号 | 合法则进入决策；失败则转人工 |
| 7. 处置决策 | 规则结果、AI 结果、否决项 | 判断确认误报、人工确认或优先调查 | 生成最终结果 |
| 8. 结果展示 | 完整状态 | 在右侧展示节点轨迹、模式、结论和理由 | 等待下一个告警 |

### 条件路由

```text
规则研判
  ├─ HIGH_RISK               → 高优先级人工调查 → 结束
  ├─ RULE_CONFIRMED_FP       → 规则确认误报     → 结束
  └─ NEED_AI                 → AI研判
                                 ├─ 输出无效/证据不足 → 人工确认
                                 ├─ 疑似误报且置信度≥85 → 确认误报
                                 ├─ 疑似误报且置信度<85 → 人工确认
                                 └─ 疑似真实攻击 → 高优先级人工调查
```

Workflow 的每次节点执行都写入 `timeline`，右侧页面可以依次显示“证据获取完成 → 规则未命中 → AI 研判完成 → 等待人工确认”，便于现场演示 Agent 的工作过程。

---

## 5. 数据设计

## 5.1 原始告警格式

Demo 内部使用统一 JSON 格式表示不同来源的告警：

```json
{
  "alert_id": "ALT-20261118-001",
  "alert_time": "2026-11-18T10:21:32+08:00",
  "alert_type": "malicious_ip_connection",
  "alert_name": "终端访问恶意 IP",
  "severity": "high",
  "source": "EDR",
  "src_ip": "10.10.2.15",
  "src_port": 51324,
  "dst_ip": "203.0.113.25",
  "dst_port": 443,
  "protocol": "TCP",
  "host_id": "HOST-025",
  "hostname": "DEV-PC-025",
  "user": "zhangsan",
  "process": {
    "name": "python.exe",
    "path": "C:\\Python311\\python.exe",
    "command_line": "python.exe vulnerability_scan.py",
    "parent_process": "powershell.exe"
  },
  "detection": {
    "rule_id": "EDR-C2-101",
    "rule_name": "已知恶意 IP 通信",
    "matched_field": "dst_ip",
    "matched_value": "203.0.113.25"
  },
  "raw_log": "..."
}
```

字段分组如下：

| 字段组 | 主要内容 | 用途 |
|---|---|---|
| 基本信息 | 编号、时间、名称、严重程度、来源 | 告警展示与排序 |
| 网络信息 | 源/目标 IP、端口、协议 | 网络行为分析 |
| 主体信息 | 主机、用户、资产编号 | 关联资产和身份上下文 |
| 行为信息 | 进程、命令行、父进程 | 判断行为是否符合预期 |
| 检测信息 | 检测规则、命中字段和值 | 解释告警为何产生 |

## 5.2 证据来源

第一版只保留四类证据源，全部使用本地 JSON 文件模拟。这样既能支撑规则和 AI 研判，也不会把 Demo 做成复杂的数据集成项目。

| 证据源 | Demo 文件 | 查询依据 | 解决的问题 |
|---|---|---|---|
| 资产上下文 | `assets.json` | `host_id` | 这是什么主机，是否为核心或测试资产 |
| 授权活动 | `approved_tasks.json` | `user + host_id + alert_time` | 该行为是否经过审批、是否在授权范围 |
| 威胁情报 | `threat_intel.json` | `dst_ip` | 目标地址是否有恶意记录 |
| 行为上下文 | `related_events.json` | `alert_id` 或 `host_id + 时间窗口` | 告警前后是否出现高风险行为 |

### 5.2.1 资产上下文

用于回答“行为发生在什么资产上”。

真实环境可能来自 CMDB、EDR、云资产平台或主机台账。Demo 使用 `assets.json` 模拟。

```json
{
  "host_id": "HOST-025",
  "asset_type": "security_test_server",
  "department": "安全部",
  "business_importance": "low",
  "environment": "test",
  "owner": "lisi",
  "internet_exposed": false
}
```

### 5.2.2 授权活动与白名单

用于回答“该行为是否经过批准、是否发生在授权范围内”。

真实环境可能来自漏洞扫描任务、渗透测试授权单、变更工单、发布记录和白名单系统。Demo 使用 `approved_tasks.json` 模拟。

```json
{
  "task_id": "TASK-008",
  "task_type": "vulnerability_scan",
  "operator": "zhangsan",
  "source_host": "HOST-025",
  "allowed_targets": ["10.20.0.0/16"],
  "start_time": "2026-11-18T09:00:00+08:00",
  "end_time": "2026-11-18T12:00:00+08:00",
  "approved": true
}
```

### 5.2.3 威胁情报

用于回答“目标 IP、域名或文件是否具有已知风险”。

真实环境可能来自企业威胁情报平台或公开情报服务。Demo 使用 `threat_intel.json` 模拟。

```json
{
  "indicator": "203.0.113.25",
  "indicator_type": "ip",
  "malicious": true,
  "threat_type": "C2",
  "confidence": 85,
  "source": "mock_threat_intelligence",
  "last_seen": "2026-11-17"
}
```

威胁情报命中只是证据之一，不能单独作为最终结论，因为情报可能过期、IP 可能被重新分配，也可能是安全人员的授权测试行为。

### 5.2.4 行为上下文

用于回答“告警前后还发生了什么”。

真实环境可能来自 EDR 进程树、防火墙、流量日志、DNS 日志、操作系统审计日志和身份认证日志。Demo 使用 `related_events.json` 模拟。

```json
{
  "alert_id": "ALT-20261118-001",
  "events": [
    {
      "time": "2026-11-18T10:20:51+08:00",
      "event": "powershell.exe 启动 python.exe"
    },
    {
      "time": "2026-11-18T10:21:32+08:00",
      "event": "python.exe 连接目标 IP"
    }
  ],
  "privilege_escalation": false,
  "lateral_movement": false,
  "data_exfiltration": false,
  "payload_download": false
}
```

## 5.3 标准化证据包

后端根据告警中的主机、用户、IP 和时间检索各数据源，形成统一证据包，再交给规则与 AI 使用。证据包不是预先手工绑定在告警上的结果，而是在用户点击“发送告警”之后，由 Workflow 的证据获取节点实时组装。

```json
{
  "alert": {
    "alert_id": "ALT-20261118-001",
    "alert_type": "malicious_ip_connection",
    "severity": "high",
    "host_id": "HOST-025",
    "dst_ip": "203.0.113.25",
    "process_name": "python.exe"
  },
  "evidence": [
    {
      "evidence_id": "EV-001",
      "type": "asset_context",
      "source": "mock_cmdb",
      "observed_at": "2026-11-18T10:21:35+08:00",
      "content": {
        "asset_type": "security_test_server",
        "environment": "test",
        "business_importance": "low"
      }
    },
    {
      "evidence_id": "EV-002",
      "type": "approved_activity",
      "source": "mock_work_order",
      "observed_at": "2026-11-18T10:21:36+08:00",
      "content": {
        "matched": true,
        "task_id": "TASK-008",
        "within_approved_time": true,
        "within_target_scope": true
      }
    },
    {
      "evidence_id": "EV-003",
      "type": "threat_intelligence",
      "source": "mock_threat_intelligence",
      "observed_at": "2026-11-18T10:21:37+08:00",
      "content": {
        "malicious": true,
        "threat_type": "C2",
        "confidence": 85
      }
    },
    {
      "evidence_id": "EV-004",
      "type": "behavior_context",
      "source": "mock_edr",
      "observed_at": "2026-11-18T10:21:38+08:00",
      "content": {
        "privilege_escalation": false,
        "lateral_movement": false,
        "data_exfiltration": false
      }
    }
  ],
  "missing_evidence": [
    "完整进程树",
    "目标 IP 近 30 天信誉变化"
  ]
}
```

为支持可追溯性，每条证据至少包含：

- `evidence_id`：唯一编号；
- `type`：证据类型；
- `source`：证据来源；
- `observed_at`：获取时间；
- `content`：标准化后的证据内容。

## 5.4 证据包的具体获取过程

Demo 不连接真实 SOC 系统，证据获取过程由 `evidence_builder.py` 模拟真实查询行为：

1. 从用户发送的告警中读取 `host_id`、`user`、`dst_ip`、`alert_id` 和 `alert_time`；
2. 使用 `host_id` 在 `assets.json` 中查询资产；
3. 使用 `user + host_id` 查询授权任务，再判断 `alert_time` 是否处于任务时间窗口、`dst_ip` 是否处于授权目标范围；
4. 使用 `dst_ip` 在 `threat_intel.json` 中查询威胁情报；
5. 使用 `alert_id` 查询关联事件；若无直接记录，再使用 `host_id` 查询告警前后 30 分钟的行为；
6. 将查询结果转换为统一的 `evidence` 数组，为每条证据分配 `evidence_id`；
7. 没有查询到的内容不伪造，写入 `missing_evidence`；
8. 将证据包传给规则节点，规则无法确定时再传给 AI。

核心伪代码：

```python
def build_evidence_package(alert, data_store):
    asset = data_store.find_asset(alert["host_id"])
    task = data_store.find_approved_task(
        user=alert["user"],
        host_id=alert["host_id"],
        event_time=alert["alert_time"],
        target_ip=alert["dst_ip"],
    )
    intel = data_store.find_threat_intel(alert["dst_ip"])
    events = data_store.find_related_events(
        alert_id=alert["alert_id"],
        host_id=alert["host_id"],
        center_time=alert["alert_time"],
        window_minutes=30,
    )

    return normalize_evidence(alert, asset, task, intel, events)
```

### Demo 与真实系统的对应关系

| Demo 查询 | 真实环境可能替换为 |
|---|---|
| 读取 `assets.json` | 调用 CMDB/资产平台接口 |
| 读取 `approved_tasks.json` | 调用工单、变更或扫描任务接口 |
| 读取 `threat_intel.json` | 调用威胁情报平台接口 |
| 读取 `related_events.json` | 查询 EDR、SIEM、流量或审计日志 |

因此，Demo 的重点不是假装已经接入真实数据，而是展示：告警进入后，Agent 如何按明确关联键收集、标准化并使用证据。

---

## 6. 第一层：确定性规则

规则层处理可以用明确条件验证的场景，强调速度、稳定性和可解释性。规则按固定优先级执行：**高风险规则 > 数据质量规则 > 明确误报规则 > 转 AI 规则**。

## 6.1 Demo 规则清单

| 规则ID | 规则名称 | 具体条件 | 输出 | 是否进入 AI |
|---|---|---|---|---|
| R-001 | 横向移动否决 | `lateral_movement == true` | 高风险人工调查 | 否 |
| R-002 | 提权行为否决 | `privilege_escalation == true` | 高风险人工调查 | 否 |
| R-003 | 数据外传否决 | `data_exfiltration == true` | 高风险人工调查 | 否 |
| R-004 | 可疑载荷否决 | `payload_download == true` 且目标命中恶意情报 | 高风险人工调查 | 否 |
| R-005 | 核心资产恶意通信 | `business_importance == high` 且 `threat_intel.malicious == true` | 高风险人工调查 | 否 |
| R-101 | 授权扫描确认 | 测试/扫描资产 + 有效审批 + 时间和目标均在授权范围 + 无 R-001～R-005 | 规则确认误报 | 否 |
| R-102 | 明确可信目标 | 目标在企业可信白名单 + 进程在允许列表 + 无高风险行为 | 规则确认误报 | 否 |
| R-201 | 关键告警字段缺失 | `host_id`、`alert_time`、`dst_ip` 任一缺失 | 人工补充信息 | 否 |
| R-202 | 关键证据缺失 | 资产信息和行为上下文均未查到 | 人工补充信息 | 否 |
| R-301 | 未授权的恶意通信 | 无有效审批且目标命中恶意情报 | 转 AI 深入解释 | 是 |
| R-302 | 证据冲突 | 存在有效审批，但同时目标命中恶意情报或行为超出预期 | 转 AI 分析冲突 | 是 |
| R-399 | 默认规则 | 未命中其他终止规则 | 转 AI 研判 | 是 |

第一版至少实现 R-001、R-003、R-005、R-101、R-201、R-301、R-302 和 R-399，其他规则可按开发时间补充。

## 6.2 规则执行顺序

```python
def evaluate_rules(alert, evidence):
    # 1. 高风险条件优先，避免白名单掩盖真实攻击
    if evidence.behavior.lateral_movement:
        return hit("R-001", "HIGH_RISK")
    if evidence.behavior.privilege_escalation:
        return hit("R-002", "HIGH_RISK")
    if evidence.behavior.data_exfiltration:
        return hit("R-003", "HIGH_RISK")
    if evidence.asset.business_importance == "high" and evidence.intel.malicious:
        return hit("R-005", "HIGH_RISK")

    # 2. 关键数据不足时，不调用 AI 猜测
    if missing_required_alert_fields(alert):
        return hit("R-201", "MANUAL_ENRICHMENT")
    if evidence.asset is None and evidence.behavior is None:
        return hit("R-202", "MANUAL_ENRICHMENT")

    # 3. 只有严格满足全部条件，规则才能直接确认误报
    if (
        evidence.asset.asset_type in ["security_test_server", "scanner"]
        and evidence.task.approved
        and evidence.task.within_approved_time
        and evidence.task.within_target_scope
    ):
        return hit("R-101", "RULE_CONFIRMED_FP")

    # 4. 其余情况交给 AI 解释
    if evidence.task.approved and evidence.intel.malicious:
        return hit("R-302", "NEED_AI")
    if not evidence.task.approved and evidence.intel.malicious:
        return hit("R-301", "NEED_AI")
    return hit("R-399", "NEED_AI")
```

## 6.3 规则结果格式

```json
{
  "decision": "RULE_CONFIRMED_FP",
  "matched_rule": {
    "rule_id": "R-101",
    "rule_name": "授权扫描确认",
    "reason": "测试主机在有效审批的时间和目标范围内执行扫描，且未发现高风险行为",
    "evidence_refs": ["EV-001", "EV-002", "EV-004"]
  },
  "need_ai": false,
  "need_human": false
}
```

规则直接确认时，右侧显示“研判方式：规则研判”和具体命中规则，不显示 AI 置信度；未命中终止规则时，状态显示“规则无法确认，进入 AI 研判”。

---

## 7. 第二层：AI 证据研判

规则无法明确处理的告警进入 AI 层。AI 不负责直接关闭告警，主要完成：

- 汇总支持误报的证据；
- 汇总支持真实攻击的证据；
- 识别证据冲突；
- 指出缺失证据；
- 给出下一步核查建议；
- 生成面向分析师的简明解释；
- 按统一标准给出本次结论的参考置信度。

## 7.1 AI 输入约束

AI 仅接收标准化证据包和规定的任务说明。核心提示词约束如下：

```text
你是 SOC 告警研判助手。

只能依据输入证据进行分析，不得补充输入中不存在的事实。
每项判断必须引用 evidence_id。
请分别列出：
1. 支持误报的证据；
2. 支持真实攻击的证据；
3. 缺失或冲突的证据；
4. 建议的下一步操作。

你不能直接决定关闭告警。
证据不足时必须输出 insufficient_evidence。
请严格按照指定 JSON 格式输出。
```

## 7.2 AI 输出格式

```json
{
  "suggested_result": "likely_false_positive",
  "confidence": {
    "evidence_completeness": 20,
    "support_strength": 22,
    "evidence_consistency": 18,
    "conclusion_clarity": 20,
    "total": 80,
    "reason": "授权活动证据较强，但恶意情报与授权行为存在冲突"
  },
  "supporting_evidence": [
    {
      "evidence_id": "EV-001",
      "reason": "该主机属于安全测试资产"
    },
    {
      "evidence_id": "EV-002",
      "reason": "行为处于已授权任务的时间与目标范围内"
    }
  ],
  "contradicting_evidence": [
    {
      "evidence_id": "EV-003",
      "reason": "目标 IP 被高置信威胁情报标记为 C2"
    }
  ],
  "missing_evidence": [
    "完整进程树"
  ],
  "recommended_action": "核实扫描脚本和目标范围后再关闭",
  "summary": "更可能是授权安全测试，但目标 IP 风险较高且进程证据不完整，建议人工核验"
}
```

## 7.3 AI 输出校验

后端应执行最小校验：

- JSON 能否解析；
- 枚举值是否合法；
- 引用的 `evidence_id` 是否真实存在；
- 是否引用了输入中不存在的事实；
- 必填字段是否完整。

校验失败时，不使用该结论自动处置，直接转人工并显示“AI 输出不可用”。

---

## 8. AI 研判置信度

## 8.1 置信度定义

AI 输出两个不同概念：

- `suggested_result`：AI 建议结论，包括 `likely_false_positive`、`likely_true_positive` 和 `insufficient_evidence`；
- `confidence.total`：AI 对当前建议结论的参考置信度，范围为 0～100。

置信度不是“误报分数”。例如，AI 可以以 90 分置信度判断“更可能是真实攻击”，也可以以 90 分置信度判断“更可能是误报”。因此页面必须同时展示结论和置信度，不能只显示一个数字。

该置信度是为了 Demo 路由和解释而设计的启发式分数，没有经过真实生产数据校准，不能等同于统计概率。

## 8.2 置信度分项标准

| 分项 | 范围 | 判断标准 |
|---|---:|---|
| 证据完整度 | 0～25 | 资产、授权、情报和行为证据是否齐全 |
| 支持强度 | 0～25 | 引用证据对当前结论的支持是否直接、充分 |
| 证据一致性 | 0～25 | 不同证据是否相互一致；存在冲突则降低 |
| 结论清晰度 | 0～25 | 是否能够形成明确结论，而非大量依赖假设 |

`total` 必须等于四项之和。后端负责验证相加结果、各项范围和证据引用是否合法。

## 8.3 置信度使用边界

- 置信度只在 AI 研判路径中显示，规则研判显示“不适用”；
- AI 结论为 `likely_false_positive` 且置信度达到 85，才可能确认误报；
- 即使置信度达到 100，只要命中高风险否决项，也必须转人工调查；
- AI 结论为 `insufficient_evidence` 时，无论置信度多少都转人工；
- AI 结论为 `likely_true_positive` 时，进入高优先级人工调查，不自动执行安全处置；
- 置信度低代表 AI 对当前结论把握不足，不代表告警必然是真实攻击。

页面旁固定显示：“AI 置信度为 Demo 启发式参考值，不代表经过生产数据校准的真实概率。”

---

## 9. 第三层：处置决策与人工确认

处置决策同时读取四项信息：规则结果、AI 建议结论、AI 置信度和高风险否决项。

| 研判来源 | 结论与条件 | 最终动作 | 是否需要人工 |
|---|---|---|---|
| 规则 | 命中 R-101/R-102 明确误报规则 | 规则确认误报 | 否 |
| 规则 | 命中 R-001～R-005 高风险规则 | 高优先级调查 | 是 |
| AI | 疑似误报，置信度 ≥ 85，无否决项，证据完整 | AI 高置信度确认误报 | 否 |
| AI | 疑似误报，但置信度 < 85 | 等待人工确认 | 是 |
| AI | 证据不足、证据冲突或输出校验失败 | 等待人工补充研判 | 是 |
| AI | 疑似真实攻击 | 高优先级调查 | 是 |

决策伪代码：

```python
if rule_result == "RULE_CONFIRMED_FP":
    action = "confirm_false_positive_by_rule"
elif has_high_risk_veto:
    action = "high_priority_manual_investigation"
elif ai_result.invalid or ai_result.verdict == "insufficient_evidence":
    action = "manual_review"
elif ai_result.verdict == "likely_false_positive" and ai_result.confidence >= 85:
    action = "confirm_false_positive_by_ai"
elif ai_result.verdict == "likely_false_positive":
    action = "manual_review"
else:
    action = "high_priority_manual_investigation"
```

人工复核提供三个操作：

- 确认为误报；
- 确认为真实告警；
- 证据不足，继续调查。

操作后记录分析师、时间、结论、理由及是否接受 AI 建议。Demo 只在当前会话中保存结果；点击“一键刷新/重置”后恢复所有预设告警，不实现在线学习。

---

## 10. 产品交互设计

## 10.1 页面布局

页面固定分为左右两块，左侧负责发送预设告警，右侧负责展示当前告警的后端研判过程与结果。

### 左侧：预设告警与操作区

- 页面顶部提供“一键刷新/重置”按钮；
- 下方展示 8～10 条预设告警卡片；
- 每张卡片显示告警名称、严重程度、来源、主机、目标 IP 和演示场景标签；
- 每张卡片提供“发送告警”按钮；
- 点击后，该告警进入后端 Workflow，并将按钮状态依次更新为“处理中”和“已完成”；
- 一次只处理一条告警，避免演示过程中多个任务并发导致页面混乱；
- 已处理告警仍保留在左侧，方便切换查看；
- 点击“一键刷新/重置”后，清空运行状态和人工操作结果，恢复所有告警为“待发送”。

左侧卡片示意：

```text
┌─────────────────────────────┐
│ 高危 | 终端访问恶意 IP      │
│ HOST-025 → 203.0.113.25     │
│ 场景：授权扫描              │
│ 状态：待发送                │
│                 [发送告警]  │
└─────────────────────────────┘
```

### 右侧：研判结果

右侧按照研判顺序展示：

1. **运行状态**：待处理、证据获取中、规则研判中、AI 研判中、等待人工、已完成；
2. **Workflow 时间线**：展示每个已执行节点和节点结果；
3. **原始告警**：展示当前发送的告警；
4. **获取到的证据**：资产、授权任务、威胁情报、行为上下文和缺失证据；
5. **研判方式**：明确显示“规则研判”或“AI 研判”；
6. **研判结论**：规则确认误报、AI 疑似误报、证据不足或疑似真实攻击；
7. **命中规则**：规则路径显示规则编号、名称、条件和证据引用；
8. **AI 置信度**：AI 路径显示总分和四个分项，规则路径显示“不适用”；
9. **AI 分析**：支持结论的证据、反对证据、缺失证据和建议；
10. **是否需要人工**：显示“是/否”和具体原因；
11. **人工操作**：需要人工时显示“确认为误报”“确认为真实告警”“继续调查”三个按钮。

右侧顶部使用统一结果摘要：

```text
研判方式：AI研判
建议结论：疑似误报
AI置信度：72/100
是否需要人工：是
原因：置信度未达到85，且威胁情报与授权任务存在冲突
```

## 10.2 关键交互体验

- 点击“发送告警”后，右侧从空状态开始显示当前 Workflow 的执行结果；
- 显示告警为什么被规则直接确认，或者为什么继续进入 AI；
- 点击 AI 判断中的证据编号，可定位到对应证据；
- 展开 AI 置信度，查看四个分项和评分理由；
- 对高风险否决条件进行醒目标记；
- 证据不足时不展示武断结论；
- 人工按钮只在 `need_human == true` 时出现；
- “一键刷新/重置”恢复初始演示状态，但不修改磁盘中的预设数据。

## 10.3 一键刷新/重置逻辑

重置按钮执行以下操作：

```python
def reset_demo():
    session_state.runs = {}
    session_state.selected_alert_id = None
    session_state.current_result = None
    session_state.manual_decisions = {}
    session_state.alert_status = {
        alert_id: "ready" for alert_id in preset_alert_ids
    }
```

该功能只重置内存中的演示状态，不删除或重写 JSON 数据，因此可以反复演示同一套告警。

---

## 11. Demo 数据集设计

## 11.1 数据来源说明

考虑题目建议实际投入不超过 4 小时，本 Demo 使用人工构造的模拟数据，不接入真实企业 SOC 数据源。

建议说明：

> 模拟数据依据典型 SOC 初筛过程构造，用于验证证据聚合、分层路由和人机协同交互，不用于证明模型在真实生产环境中的识别准确率。

## 11.2 案例数量

准备 8～10 条案例即可：

| 案例类型 | 建议数量 | 目的 |
|---|---:|---|
| 规则可直接识别的明确误报 | 3 | 展示确定性快速处理 |
| AI 分析后的疑似误报 | 2 | 展示复杂证据归纳 |
| 需要人工确认的模糊案例 | 2 | 展示人机协同 |
| 高风险否决案例 | 2 | 展示安全边界 |
| 证据缺失或冲突案例 | 1～2 | 展示拒绝武断判断 |

## 11.3 推荐案例

### 案例 A：授权漏洞扫描

- 测试主机；
- 有有效审批任务；
- 时间和目标均在授权范围内；
- 无后续高危行为；
- 预期：规则直接处理或得到高误报评分。

### 案例 B：扫描行为超出授权范围

- 主机和人员均属于安全团队；
- 但扫描目标不在审批范围；
- 预期：高风险否决或转人工调查。

### 案例 C：恶意 IP 通信但证据矛盾

- 目标命中威胁情报；
- 主机为测试设备且存在授权任务；
- 缺少完整进程树；
- 预期：AI 汇总冲突证据，进入人工复核。

### 案例 D：白名单主机出现横向移动

- 主机属于白名单扫描器；
- 同时发现凭据使用异常和横向移动；
- 预期：高风险否决，禁止自动关闭。

### 案例 E：证据不足

- 只有源 IP、目标 IP 和告警名称；
- 缺少资产、进程和授权记录；
- 预期：输出证据不足并建议补充信息。

---

## 12. 技术实现建议

## 12.1 最小技术栈

- 前端与交互：Streamlit；
- 业务逻辑：Python；
- 数据：本地 JSON 文件；
- AI：兼容 OpenAI 接口的大模型，或在无密钥时使用固定 Mock 响应；
- 状态保存：内存或本地 SQLite，可根据时间选择。

选择 Streamlit 的原因是可以在较短时间内完成告警列表、详情、评分展示和人工操作，不需要单独搭建前后端工程。

## 12.2 建议目录结构

```text
soc/
├─ app.py
├─ README.md
├─ requirements.txt
├─ data/
│  ├─ alerts.json
│  ├─ assets.json
│  ├─ approved_tasks.json
│  ├─ threat_intel.json
│  └─ related_events.json
├─ src/
│  ├─ workflow.py
│  ├─ data_store.py
│  ├─ evidence_builder.py
│  ├─ rule_engine.py
│  ├─ ai_analyzer.py
│  ├─ ai_validator.py
│  └─ decision_router.py
└─ tests/
   └─ test_decisions.py
```

## 12.3 模块职责

| 模块 | 职责 |
|---|---|
| `workflow` | 定义 Agent 节点、条件路由和共享状态 |
| `data_store` | 加载四个本地模拟证据源并提供查询方法 |
| `evidence_builder` | 按关联键查询数据，生成标准化证据包 |
| `rule_engine` | 执行确定性规则和高风险否决规则 |
| `ai_analyzer` | 构建提示词、调用模型、校验结构化输出 |
| `ai_validator` | 校验 AI JSON、置信度分项和证据引用 |
| `decision_router` | 根据否决项、证据质量、评分和阈值决定路由 |
| `app` | 实现左右双栏页面、发送告警、人工处置和一键重置 |

---

## 13. 效果验证方案

## 13.1 验证问题

方案是否有效，不只看分类结果，还要回答：

- 是否减少分析师查询和整理证据的时间；
- 是否让判断依据更清晰；
- 是否避免在高风险场景下自动关闭告警；
- 是否能在证据不足时拒绝武断判断；
- AI 输出是否真实引用了输入证据。

## 13.2 建议指标

| 指标 | 含义 |
|---|---|
| 平均初筛时间 | 处理单条告警所需时间 |
| 处置准确率 | 最终处置与预设标签一致的比例 |
| 高风险错误关闭数 | 真实高风险告警被误关的数量，目标为 0 |
| 自动处置覆盖率 | 无需人工处理的告警比例 |
| 人工复核率 | 进入人工确认的告警比例 |
| 证据引用有效率 | AI 引用的证据编号真实存在的比例 |
| 解释完整率 | 是否同时给出支持、反对、缺失证据和建议 |

## 13.3 对照方式

可让测试者分别采用两种方式处理同一批告警：

1. 只查看原始告警；
2. 使用本 Demo 查看聚合证据、规则结果、AI 分析和评分。

记录两种方式的处理时间和判断结果。由于样本量小，最终只能描述为 Demo 验证结果，不能外推为生产性能。

## 13.4 建议成功标准

- 所有高风险否决案例均未被自动关闭；
- 所有证据缺失案例均进入人工处理；
- AI 引用的证据编号有效率为 100%；
- 使用辅助页面后的平均初筛时间低于只查看原始告警；
- 用户能够通过页面说明“为什么给出该建议”。

---

## 14. 复试演示脚本

建议将 10～15 分钟安排如下：

### 14.1 问题与用户（1～2 分钟）

- SOC 分析师面对大量告警；
- 真正耗时的不只是阅读告警，而是补充上下文并判断是否需要继续调查；
- 作品聚焦“疑似误报的可解释初筛”。

### 14.2 方案说明（2 分钟）

- 原始告警与上下文证据分离；
- 规则、AI 和人工三层协作；
- AI 只负责证据分析，不直接控制关单；
- 评分由后端根据证据计算，不使用 AI 自报置信度。

### 14.3 现场演示（5～7 分钟）

建议依次演示：

1. 授权扫描：规则快速识别明确误报；
2. 证据冲突：AI 列出支持和反对证据，转人工复核；
3. 白名单主机横向移动：高风险条件一票否决；
4. 证据不足：系统拒绝武断判断并提示需要补充的信息。

### 14.4 效果与边界（2 分钟）

- 展示处理时间或案例通过情况；
- 说明数据为模拟数据；
- 说明阈值和权重尚未经过生产数据校准；
- 说明真实落地需要接入 SIEM、EDR、CMDB、威胁情报和工单系统。

### 14.5 总结表达

> 我没有让大模型自由决定处置流程，而是使用固定 Workflow 编排证据获取、规则研判、AI 研判、输出校验和处置决策。确定性场景由规则处理，复杂场景由 AI 基于证据给出结论、参考置信度和建议；高风险条件始终优先，必要时转人工确认。

---

## 15. 4 小时实现范围

题目建议实际投入不超过 4 小时，因此优先保证一条完整链路可演示。

### 第 1 小时：数据与规则

- 准备 8～10 条模拟告警；
- 准备资产、授权任务、威胁情报和行为上下文；
- 实现证据组装；
- 实现少量核心规则和高风险否决规则。

### 第 2 小时：规则、Workflow 与路由

- 实现具体规则和优先级；
- 实现 Workflow 状态与条件路由；
- 实现证据获取、规则研判和处置决策节点；
- 验证规则、否决项和 AI 入口条件。

### 第 3 小时：AI 与界面

- 接入大模型或 Mock AI；
- 固定结论、置信度、证据引用和建议的结构化输出；
- 实现左侧预设告警、右侧研判结果的双栏页面；
- 添加发送告警、人工处置和一键重置按钮。

### 第 4 小时：测试与演示准备

- 验证 4 类关键案例；
- 修复明显问题；
- 编写本地运行说明；
- 准备 10～15 分钟讲解顺序；
- 记录实际投入时间和未完成项。

若时间不足，优先级如下：

1. 完整的告警—证据—规则—AI置信度—处置链路；
2. 高风险否决和证据不足处理；
3. AI 结构化分析；
4. 界面美化、持久化和扩展功能。

---

## 16. 风险与应对

| 风险 | 影响 | 应对方式 |
|---|---|---|
| AI 幻觉 | 引用不存在的事实 | 只输入证据包，强制引用证据编号，后端校验 |
| AI 输出不稳定 | 页面或流程无法继续 | 使用 JSON 结构化输出，失败后转人工，可提供 Mock 回退 |
| AI置信度被误解为真实概率 | 面试官质疑可信度 | 展示四项评分依据，并明确其为未校准的 Demo 启发式分数 |
| 白名单被滥用 | 真实攻击被自动关闭 | 设置高风险一票否决和授权范围校验 |
| 证据缺失 | AI 武断判断 | 进入人工复核并提示缺失字段 |
| 模拟数据过于理想化 | 效果缺乏说服力 | 增加证据冲突、越权行为和数据缺失案例 |
| 时间不足 | Demo 不完整 | 保证一条端到端链路，减少案例数量和界面美化 |

---

## 17. 预期交付物

- 一个可本地运行的交互式 Demo；
- 模拟告警及上下文数据；
- 本地启动说明；
- AI 工具和使用方式说明；
- 具体规则、AI置信度与决策边界说明；
- 简单效果验证结果；
- 实际投入时间、已完成项和未完成项说明。

作品提交名称按要求设置为：**复试作品+姓名**。

---

## 18. 第一版实现基线

根据当前讨论，第一版按以下范围实现：

- 只深入实现“恶意 IP 通信”一种告警类型；
- 只保留资产、授权活动、威胁情报和行为上下文四类证据源；
- 证据源使用本地 JSON 模拟，由 Workflow 的证据获取节点按关联键实时组装证据包；
- 使用固定 Workflow 编排接收告警、获取证据、规则研判、AI 研判、输出校验和处置决策；
- 规则严格命中时可直接确认误报；
- AI 判断为疑似误报、置信度不低于 85、证据完整且无否决项时，可在 Demo 中确认误报；
- 其他 AI 结果进入人工确认或高优先级调查；
- 页面采用左右双栏：左侧发送预设告警，右侧展示研判过程与结果；
- 提供一键刷新/重置，恢复所有演示状态；
- 使用 8～10 条经过设计的案例；
- 同时支持真实 AI 和 Mock 回退，保证现场演示稳定；
- 运行和人工处置状态只保存在当前会话，不接入 SQLite；
- 使用小规模案例验证时间、规则路径和解释完整性，不宣称生产准确率。
