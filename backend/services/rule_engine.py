from typing import Any

from backend.models.alert import Alert
from backend.models.evidence import EvidencePackage
from backend.models.rule import MatchedRule, RuleResult


class RuleEngine:
    """Evaluate deterministic rules in security-first priority order."""

    def evaluate(self, alert: Alert, evidence: EvidencePackage) -> RuleResult:
        by_type = {item.evidence_type: item for item in evidence.items}
        asset = self._content(by_type, "asset_context")
        task = self._content(by_type, "approved_activity")
        intel = self._content(by_type, "threat_intelligence")
        behavior = self._content(by_type, "behavior_context")

        # 1. High-risk vetoes always precede authorization-based confirmation.
        if behavior and behavior.get("lateral_movement") is True:
            return self._hit(
                "R-001", "横向移动否决", "行为上下文发现横向移动迹象",
                "HIGH_RISK", ["EV-004"], need_ai=False, need_human=True,
            )
        if behavior and behavior.get("data_exfiltration") is True:
            return self._hit(
                "R-003", "数据外传否决", "行为上下文发现数据外传迹象",
                "HIGH_RISK", ["EV-004"], need_ai=False, need_human=True,
            )
        if (
            asset
            and asset.get("business_importance") == "high"
            and intel
            and intel.get("malicious") is True
        ):
            return self._hit(
                "R-005", "核心资产恶意通信", "高重要性核心资产连接已知恶意目标",
                "HIGH_RISK", ["EV-001", "EV-003"], need_ai=False, need_human=True,
            )

        # 2. Data quality rules prevent inference from absent critical context.
        if any(not getattr(alert, name, None) for name in ("host_id", "alert_time", "dst_ip")):
            return self._hit(
                "R-201", "关键告警字段缺失", "host_id、alert_time 或 dst_ip 存在缺失",
                "MANUAL_ENRICHMENT", [], need_ai=False, need_human=True,
            )
        if asset is None and behavior is None:
            return self._hit(
                "R-202", "关键证据缺失", "资产信息和行为上下文均未查询到",
                "MANUAL_ENRICHMENT", [], need_ai=False, need_human=True,
            )

        approved = bool(
            task
            and task.get("approved") is True
            and task.get("within_approved_time") is True
            and task.get("within_target_scope") is True
        )
        malicious = bool(intel and intel.get("malicious") is True)
        behavior_conflict = bool(
            behavior
            and any(
                behavior.get(field) is True
                for field in ("privilege_escalation", "payload_download")
            )
        )

        # 3. Explicit false positive requires every authorization condition and no conflict.
        if (
            asset
            and asset.get("asset_type") in {"security_test_server", "scanner"}
            and approved
            and not malicious
            and not behavior_conflict
        ):
            return self._hit(
                "R-101", "授权扫描确认",
                "测试或扫描资产在审批时间和目标范围内活动，且不存在高风险或恶意情报冲突",
                "RULE_CONFIRMED_FP", ["EV-001", "EV-002", "EV-004"],
                need_ai=False, need_human=False,
            )

        # 4. AI-entry rules only explain unresolved or conflicting evidence.
        if approved and (malicious or behavior_conflict):
            refs = ["EV-002"]
            if malicious:
                refs.append("EV-003")
            if behavior_conflict:
                refs.append("EV-004")
            return self._hit(
                "R-302", "证据冲突", "有效授权与恶意情报或异常行为证据同时存在",
                "NEED_AI", refs, need_ai=True, need_human=False,
            )
        if not approved and malicious:
            return self._hit(
                "R-301", "未授权的恶意通信", "未找到有效授权且目标命中恶意情报",
                "NEED_AI", ["EV-003"], need_ai=True, need_human=False,
            )
        return self._hit(
            "R-399", "默认规则", "现有确定性证据无法得出终止结论",
            "NEED_AI", [item.evidence_id for item in evidence.items],
            need_ai=True, need_human=False,
        )

    @staticmethod
    def _content(by_type: dict[str, Any], evidence_type: str) -> dict[str, Any] | None:
        item = by_type.get(evidence_type)
        return item.content if item else None

    @staticmethod
    def _hit(
        rule_id: str,
        rule_name: str,
        reason: str,
        decision: str,
        refs: list[str],
        *,
        need_ai: bool,
        need_human: bool,
    ) -> RuleResult:
        matched = MatchedRule(
            rule_id=rule_id,
            rule_name=rule_name,
            reason=reason,
            evidence_refs=refs,
        )
        return RuleResult(
            decision=decision,
            matched_rule=matched,
            evidence_refs=refs,
            need_ai=need_ai,
            need_human=need_human,
        )
