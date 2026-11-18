from collections.abc import Callable
from typing import Any

from backend.models.alert import Alert
from backend.models.evidence import EvidenceItem, EvidencePackage
from backend.services.data_store import JsonDataStore


class EvidenceBuilder:
    """Build a traceable evidence package without inventing absent data."""

    def __init__(self, data_store: JsonDataStore) -> None:
        self.data_store = data_store

    def build(self, alert: Alert) -> EvidencePackage:
        items: list[EvidenceItem] = []
        missing: list[str] = []
        errors: list[str] = []

        queries: list[tuple[str, str, str, Callable[[], dict[str, Any] | None]]] = [
            (
                "EV-001",
                "asset_context",
                "mock_cmdb",
                lambda: self.data_store.find_asset(alert.host_id),
            ),
            (
                "EV-002",
                "approved_activity",
                "mock_work_order",
                lambda: self.data_store.find_approved_task(
                    user=alert.user,
                    host_id=alert.host_id,
                    event_time=alert.alert_time,
                    target_ip=str(alert.dst_ip),
                ),
            ),
            (
                "EV-003",
                "threat_intelligence",
                "mock_threat_intelligence",
                lambda: self.data_store.find_threat_intel(str(alert.dst_ip)),
            ),
            (
                "EV-004",
                "behavior_context",
                "mock_edr",
                lambda: self.data_store.find_related_events(
                    alert_id=alert.alert_id,
                    host_id=alert.host_id,
                    center_time=alert.alert_time,
                    window_minutes=30,
                ),
            ),
        ]

        missing_names = {
            "EV-001": "asset_context_not_found",
            "EV-002": "approved_activity_not_found",
            "EV-003": "threat_intelligence_not_found",
            "EV-004": "behavior_context_not_found",
        }

        for evidence_id, evidence_type, source, query in queries:
            try:
                content = query()
            except Exception as exc:  # Each source fails independently by design.
                errors.append(f"{evidence_type}_retrieval_error: {type(exc).__name__}: {exc}")
                continue
            if content is None:
                missing.append(missing_names[evidence_id])
                continue
            items.append(
                EvidenceItem(
                    evidence_id=evidence_id,
                    evidence_type=evidence_type,
                    source=source,
                    observed_at=alert.alert_time,
                    content=content,
                )
            )

        return EvidencePackage(
            alert_id=alert.alert_id,
            items=items,
            missing_evidence=missing,
            retrieval_errors=errors,
        )
