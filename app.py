from __future__ import annotations

import os
from typing import Any

import streamlit as st

from frontend.api_client import APIClient, APIClientError


st.set_page_config(page_title="AlertLens", page_icon="🛡️", layout="wide")

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000/api/v1")
POLL_INTERVAL_SECONDS = 0.7
TERMINAL_STATUSES = {"completed", "waiting_human", "failed"}


@st.cache_resource
def get_api_client(base_url: str) -> APIClient:
    return APIClient(base_url)


api = get_api_client(API_BASE_URL)


def init_state() -> None:
    defaults = {
        "current_run_id": None,
        "selected_alert_id": None,
        "terminal_synced_run_id": None,
        "human_submitted": False,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_run_state() -> None:
    for key in (
        "current_run_id",
        "selected_alert_id",
        "terminal_synced_run_id",
        "human_submitted",
    ):
        st.session_state[key] = None if key != "human_submitted" else False


def status_label(status: str) -> str:
    return {
        "ready": "待发送",
        "processing": "处理中",
        "queued": "排队中",
        "collecting_evidence": "获取证据",
        "rule_analyzing": "规则研判",
        "ai_analyzing": "AI 研判",
        "waiting_human": "等待人工",
        "completed": "已完成",
        "failed": "失败",
    }.get(status, status)


def workflow_node_label(node: str) -> str:
    chinese_name = {
        "load_alert": "告警加载",
        "collect_evidence": "证据收集",
        "check_evidence": "证据完整性检查",
        "evaluate_rules": "规则研判",
        "analyze_with_ai": "AI 研判",
        "validate_ai_output": "AI 输出校验",
        "make_decision": "处置决策",
        "persist_result": "结果保存",
    }.get(node)
    return f"{chinese_name}（{node}）" if chinese_name else node


def timeline_status_label(status: str) -> str:
    return {
        "started": "执行中",
        "running": "执行中",
        "completed": "已完成",
        "failed": "失败",
        "skipped": "已跳过",
    }.get(status, status)


def evidence_type_label(evidence_type: str) -> str:
    return {
        "asset_context": "资产上下文",
        "approved_activity": "授权活动",
        "threat_intelligence": "威胁情报",
        "behavior_context": "行为上下文",
    }.get(evidence_type, evidence_type)


def source_label(source: str) -> str:
    return {
        "mock_cmdb": "模拟资产管理系统",
        "mock_work_order": "模拟工单系统",
        "mock_threat_intelligence": "模拟威胁情报平台",
        "mock_edr": "模拟终端检测系统",
    }.get(source, source)


def result_label(value: str) -> str:
    return {
        "HIGH_RISK": "高风险，转人工调查",
        "RULE_CONFIRMED_FP": "规则确认误报",
        "MANUAL_ENRICHMENT": "需要人工补充信息",
        "NEED_AI": "需要 AI 研判",
        "likely_false_positive": "疑似误报",
        "likely_true_positive": "疑似真实攻击",
        "insufficient_evidence": "证据不足",
        "confirm_false_positive": "确认为误报",
        "confirm_true_positive": "确认为真实告警",
        "continue_investigation": "继续调查",
    }.get(value, value)


def content_field_label(field: str) -> str:
    return {
        "host_id": "主机编号",
        "asset_type": "资产类型",
        "department": "所属部门",
        "business_importance": "业务重要性",
        "environment": "运行环境",
        "owner": "负责人",
        "internet_exposed": "是否暴露互联网",
        "task_id": "任务编号",
        "task_type": "任务类型",
        "operator": "操作人员",
        "source_host": "来源主机",
        "allowed_targets": "授权目标范围",
        "start_time": "开始时间",
        "end_time": "结束时间",
        "approved": "是否批准",
        "within_approved_time": "是否在授权时间内",
        "within_target_scope": "目标是否在授权范围内",
        "indicator": "情报指标",
        "indicator_type": "指标类型",
        "malicious": "是否恶意",
        "threat_type": "威胁类型",
        "confidence": "情报置信度",
        "last_seen": "最近发现时间",
        "events": "关联事件",
        "privilege_escalation": "是否存在权限提升",
        "lateral_movement": "是否存在横向移动",
        "data_exfiltration": "是否存在数据外传",
        "payload_download": "是否下载载荷",
    }.get(field, field)


def content_value_label(value: Any) -> Any:
    if isinstance(value, bool):
        return "是" if value else "否"
    if value is None:
        return "无"
    if isinstance(value, str):
        return {
            "security_test_server": "安全测试服务器",
            "employee_workstation": "员工终端",
            "database_server": "数据库服务器",
            "core_business_server": "核心业务服务器",
            "scanner": "扫描器",
            "development_server": "开发服务器",
            "low": "低",
            "medium": "中",
            "high": "高",
            "test": "测试环境",
            "production": "生产环境",
            "development": "开发环境",
            "vulnerability_scan": "漏洞扫描",
            "penetration_test": "渗透测试",
            "integration_test": "集成测试",
            "ip": "IP 地址",
        }.get(value, value)
    return value


def missing_evidence_label(value: str) -> str:
    return {
        "asset_context_not_found": "未找到资产上下文",
        "approved_activity_not_found": "未找到授权活动",
        "threat_intelligence_not_found": "未找到威胁情报",
        "behavior_context_not_found": "未找到行为上下文",
    }.get(value, value)


def severity_badge(severity: str) -> str:
    colors = {
        "critical": "#b91c1c",
        "high": "#dc2626",
        "medium": "#d97706",
        "low": "#2563eb",
    }
    color = colors.get(severity, "#64748b")
    label = {"critical": "严重", "high": "高危", "medium": "中危", "low": "低危"}.get(
        severity, severity
    )
    return (
        f'<span style="background:{color};color:white;padding:2px 8px;'
        f'border-radius:10px;font-size:12px">{label}</span>'
    )


def render_header() -> bool:
    title_col, health_col, reset_col = st.columns([0.62, 0.23, 0.15])
    with title_col:
        st.title("🛡️ AlertLens")
        st.caption("聚合安全证据，通过规则、AI 与人工复核分层研判 SOC 告警。")

    backend_ok = False
    with health_col:
        try:
            health = api.health()
            backend_ok = health.get("status") == "ok"
            st.metric("后端状态", "正常" if backend_ok else "异常")
            ai_mode = {"mock": "模拟模式", "live": "真实模型模式"}.get(
                health.get("ai_mode"), "未知"
            )
            st.caption(f"AI 模式：{ai_mode}")
        except APIClientError as exc:
            st.metric("后端状态", "不可用")
            st.caption(str(exc))

    with reset_col:
        if st.button("一键刷新 / 重置", use_container_width=True, type="secondary"):
            try:
                result = api.reset_demo()
                clear_run_state()
                st.toast(result.get("message", "Demo 已重置"), icon="✅")
                st.rerun()
            except APIClientError as exc:
                st.error(str(exc))
    st.divider()
    return backend_ok


def send_alert(alert_id: str) -> None:
    try:
        run = api.create_run(alert_id)
    except APIClientError as exc:
        st.error(f"发送失败：{exc}")
        return
    st.session_state.current_run_id = run["run_id"]
    st.session_state.selected_alert_id = alert_id
    st.session_state.terminal_synced_run_id = None
    st.session_state.human_submitted = False
    st.rerun()


def render_alerts(alerts: list[dict[str, Any]]) -> None:
    st.subheader("预设告警")
    st.caption("选择一条告警发送到受约束工作流。")
    current_run = st.session_state.current_run_id
    selected = st.session_state.selected_alert_id

    for alert in alerts:
        is_selected = alert["alert_id"] == selected
        with st.container(border=True):
            heading = f"{'▶ 当前运行 · ' if is_selected else ''}{alert['alert_id']}"
            st.markdown(f"**{heading}** &nbsp; {severity_badge(alert['severity'])}", unsafe_allow_html=True)
            st.write(alert["alert_name"])
            st.caption(f"主机：{alert['hostname']}　目标：{alert['dst_ip']}")
            st.caption(f"场景：{alert['demo_scenario']}　状态：{status_label(alert['status'])}")
            disabled = alert["status"] in {"processing", "waiting_human"}
            if st.button(
                "查看当前运行" if is_selected and current_run else "发送告警",
                key=f"send_{alert['alert_id']}",
                disabled=disabled or bool(is_selected and current_run),
                use_container_width=True,
                type="primary" if is_selected else "secondary",
            ):
                send_alert(alert["alert_id"])


def render_timeline(timeline: list[dict[str, Any]]) -> None:
    if not timeline:
        st.info("工作流尚未产生节点记录。")
        return
    rows = [
        {
            "节点": workflow_node_label(event["node"]),
            "状态": timeline_status_label(event["status"]),
            "说明": event["message"],
            "耗时(ms)": event.get("duration_ms"),
        }
        for event in timeline
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)


def render_evidence_package(evidence: dict[str, Any] | None) -> None:
    if not evidence:
        st.info("证据包尚未生成。")
        return
    st.caption(f"所属告警：{evidence['alert_id']}　已获取 {len(evidence.get('items', []))} 类证据")
    for item in evidence.get("items", []):
        title = (
            f"{item['evidence_id']}｜{evidence_type_label(item['evidence_type'])}"
        )
        with st.expander(title, expanded=True):
            source_col, time_col = st.columns(2)
            source_col.write(f"**来源：** {source_label(item['source'])}")
            time_col.write(f"**获取时间：** {item['observed_at']}")
            for field, value in item.get("content", {}).items():
                label = content_field_label(field)
                display_value = content_value_label(value)
                if isinstance(display_value, (dict, list)):
                    st.write(f"**{label}：**")
                    st.json(display_value, expanded=False)
                else:
                    st.write(f"**{label}：** {display_value}")

    missing = evidence.get("missing_evidence", [])
    errors = evidence.get("retrieval_errors", [])
    missing_text = "、".join(missing_evidence_label(item) for item in missing)
    st.write(f"**缺失证据：** {missing_text if missing else '无'}")
    st.write(f"**查询异常：** {'、'.join(errors) if errors else '无'}")
    with st.expander("查看原始证据数据"):
        st.json(evidence, expanded=False)


def render_rule_result(rule: dict[str, Any] | None) -> None:
    if not rule:
        st.info("规则结果尚未生成。")
        return
    matched = rule.get("matched_rule") or {}
    st.write(f"**规则结论：** {result_label(rule['decision'])}")
    st.write(f"**命中规则：** {matched.get('rule_id', '无')}｜{matched.get('rule_name', '无')}")
    st.write(f"**判断原因：** {matched.get('reason', '无')}")
    refs = rule.get("evidence_refs") or matched.get("evidence_refs") or []
    st.write(f"**引用证据：** {'、'.join(refs) if refs else '无'}")
    st.write(f"**需要 AI：** {'是' if rule.get('need_ai') else '否'}")
    st.write(f"**需要人工：** {'是' if rule.get('need_human') else '否'}")
    with st.expander("查看原始规则数据"):
        st.json(rule, expanded=False)


def render_summary(run: dict[str, Any]) -> None:
    rule = run.get("rule_result") or {}
    ai_result = run.get("ai_result")
    decision = run.get("decision") or {}
    mode = run.get("analysis_mode")
    mode_text = {"rule": "规则研判", "ai": "AI 研判", "manual": "人工处置"}.get(mode, "处理中")
    raw_suggested = ai_result.get("suggested_result") if ai_result else rule.get("decision", "尚未生成")
    suggested = result_label(raw_suggested)
    confidence = ai_result.get("confidence", {}).get("total") if ai_result else None

    if rule.get("decision") == "HIGH_RISK":
        st.error("⚠️ 命中高风险否决条件，禁止自动确认误报。")
    elif run["status"] == "failed":
        st.error("工作流执行失败，请检查后端日志。")

    cols = st.columns(4)
    cols[0].metric("研判方式", mode_text)
    cols[1].metric("建议结论", suggested)
    cols[2].metric("AI 置信度", f"{confidence}/100" if confidence is not None else "不适用")
    cols[3].metric("需要人工", "是" if decision.get("need_human") else "否")
    if confidence is not None:
        st.caption("AI 置信度为 Demo 启发式参考值，不是经过校准的概率。")
    elif mode == "rule":
        st.info("本次由确定性规则完成，未调用 AI，置信度不适用。")
    if decision.get("reason"):
        st.write(f"**处置原因：** {decision['reason']}")


def render_ai_analysis(ai_result: dict[str, Any] | None, mode: str | None) -> None:
    if not ai_result:
        if mode == "rule":
            st.info("本次为规则路径，未调用 AI，置信度不适用。")
        else:
            st.info("AI 分析结果尚未生成。")
        return
    st.write(f"**建议结论：** {result_label(ai_result['suggested_result'])}")
    st.write(ai_result.get("summary", ""))
    confidence = ai_result["confidence"]
    confidence_rows = [
        {"分项": "证据完整性", "得分": confidence["evidence_completeness"]},
        {"分项": "支持强度", "得分": confidence["support_strength"]},
        {"分项": "证据一致性", "得分": confidence["evidence_consistency"]},
        {"分项": "结论清晰度", "得分": confidence["conclusion_clarity"]},
    ]
    st.dataframe(confidence_rows, use_container_width=True, hide_index=True)
    st.progress(confidence["total"] / 100, text=f"总分：{confidence['total']}/100")
    st.caption("Demo 启发式参考值，不是校准概率。")
    st.write(f"**评分理由：** {confidence['reason']}")
    st.write("**支持证据引用**")
    if ai_result.get("supporting_evidence"):
        for item in ai_result["supporting_evidence"]:
            st.write(f"- `{item['evidence_id']}`：{item['reason']}")
    else:
        st.caption("无")
    st.write("**冲突证据引用**")
    if ai_result.get("contradicting_evidence"):
        for item in ai_result["contradicting_evidence"]:
            st.write(f"- `{item['evidence_id']}`：{item['reason']}")
    else:
        st.caption("无")
    if ai_result.get("missing_evidence"):
        st.write("**缺失证据：** " + "、".join(ai_result["missing_evidence"]))
    st.write(f"**下一步建议：** {ai_result.get('recommended_action', '')}")


def submit_human(run_id: str, decision: str, comment: str) -> None:
    try:
        api.submit_human_decision(run_id, decision, comment)
        st.session_state.human_submitted = True
        st.session_state.terminal_synced_run_id = None
        st.toast("人工决定已提交", icon="✅")
        st.rerun(scope="app")
    except APIClientError as exc:
        st.error(f"提交失败：{exc}")


def render_human_actions(run: dict[str, Any]) -> None:
    st.warning("该告警需要人工确认。请选择最终操作。")
    with st.form(key=f"human_form_{run['run_id']}"):
        comment = st.text_input("人工备注", placeholder="填写核查依据（可选）")
        columns = st.columns(3)
        actions = [
            ("确认为误报", "confirm_false_positive"),
            ("确认为真实告警", "confirm_true_positive"),
            ("继续调查", "continue_investigation"),
        ]
        selected_action = None
        for column, (label, value) in zip(columns, actions):
            if column.form_submit_button(label, use_container_width=True):
                selected_action = value
        if selected_action:
            submit_human(run["run_id"], selected_action, comment)


def render_run(run: dict[str, Any]) -> None:
    st.subheader("研判过程与结果")
    st.caption(f"运行：{run['run_id']}　状态：{status_label(run['status'])}")
    if run["status"] not in TERMINAL_STATUSES:
        st.info(f"当前阶段：{status_label(run['status'])}，页面每 700ms 自动更新。")
    render_summary(run)

    tabs = st.tabs(["工作流轨迹", "证据包", "规则结果", "AI 分析"])
    with tabs[0]:
        render_timeline(run.get("timeline", []))
    with tabs[1]:
        render_evidence_package(run.get("evidence_package"))
    with tabs[2]:
        render_rule_result(run.get("rule_result"))
    with tabs[3]:
        render_ai_analysis(run.get("ai_result"), run.get("analysis_mode"))

    if run["status"] == "waiting_human":
        render_human_actions(run)
    elif run.get("human_decision"):
        st.success(
            f"人工决定：{result_label(run['human_decision']['decision'])}；"
            f"备注：{run['human_decision'].get('comment') or '无'}"
        )


def load_and_render_run(run_id: str) -> dict[str, Any] | None:
    try:
        run = api.get_run(run_id)
    except APIClientError as exc:
        st.error(f"获取运行失败：{exc}")
        return None
    render_run(run)
    return run


@st.fragment(run_every=POLL_INTERVAL_SECONDS)
def polling_result_panel(run_id: str) -> None:
    run = load_and_render_run(run_id)
    if run and run["status"] in TERMINAL_STATUSES:
        st.session_state.terminal_synced_run_id = run_id
        # 终态时只需进行一次普通整页重跑，使左侧告警状态同步。
        # 不指定 scope，避免不同 Streamlit 版本或首次片段执行阶段
        # 对 fragment 重跑上下文的限制导致 StreamlitAPIException。
        st.rerun()


def result_panel() -> None:
    run_id = st.session_state.current_run_id
    if not run_id:
        st.subheader("研判过程与结果")
        st.info("请从左侧选择并发送一条预设告警。")
        return
    if st.session_state.terminal_synced_run_id == run_id:
        load_and_render_run(run_id)
    else:
        polling_result_panel(run_id)


init_state()
backend_ok = render_header()
left, right = st.columns([0.42, 0.58], gap="large")

with left:
    if backend_ok:
        try:
            render_alerts(api.list_alerts())
        except APIClientError as exc:
            st.error(f"告警加载失败：{exc}")
    else:
        st.warning("后端不可用，启动 Uvicorn 后刷新页面。")

with right:
    result_panel()
