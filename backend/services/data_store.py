from __future__ import annotations

import ipaddress
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress, TypeAdapter, ValidationError

from backend.models.alert import Alert


class AssetRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    host_id: str
    asset_type: str
    department: str
    business_importance: Literal["low", "medium", "high"]
    environment: Literal["test", "development", "production"]
    owner: str
    internet_exposed: bool


class ApprovedTaskRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    task_id: str
    task_type: str
    operator: str
    source_host: str
    allowed_targets: list[str]
    start_time: datetime
    end_time: datetime
    approved: bool


class ThreatIntelRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    indicator: IPvAnyAddress
    indicator_type: Literal["ip"]
    malicious: bool
    threat_type: str
    confidence: int = Field(ge=0, le=100)
    source: str
    last_seen: datetime


class RelatedEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    time: datetime
    event: str


class RelatedEventsRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    alert_id: str | None = None
    host_id: str
    events: list[RelatedEvent] = Field(default_factory=list)
    privilege_escalation: bool = False
    lateral_movement: bool = False
    data_exfiltration: bool = False
    payload_download: bool = False


class JsonDataStore:
    """Eagerly loads and validates all local Demo JSON files."""

    def __init__(self, data_dir: str | Path = "data") -> None:
        self.data_dir = Path(data_dir)
        self._alerts = self._load("alerts.json", list[Alert])
        self._assets = self._load("assets.json", list[AssetRecord])
        self._approved_tasks = self._load("approved_tasks.json", list[ApprovedTaskRecord])
        self._threat_intel = self._load("threat_intel.json", list[ThreatIntelRecord])
        self._related_events = self._load("related_events.json", list[RelatedEventsRecord])

        alert_ids = [alert.alert_id for alert in self._alerts]
        if len(alert_ids) != len(set(alert_ids)):
            raise ValueError("alerts.json contains duplicate alert_id values")

    def _load(self, filename: str, model_type: Any) -> list[Any]:
        path = self.data_dir / filename
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            return TypeAdapter(model_type).validate_python(payload)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"required data file not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in {path}: {exc}") from exc
        except ValidationError as exc:
            raise ValueError(f"schema validation failed for {path}: {exc}") from exc

    def list_alerts(self) -> list[Alert]:
        return list(self._alerts)

    def get_alert(self, alert_id: str) -> Alert | None:
        return next((item for item in self._alerts if item.alert_id == alert_id), None)

    def find_asset(self, host_id: str) -> dict[str, Any] | None:
        item = next((asset for asset in self._assets if asset.host_id == host_id), None)
        return item.model_dump(mode="json") if item else None

    def find_approved_task(
        self,
        user: str,
        host_id: str,
        event_time: datetime,
        target_ip: str,
    ) -> dict[str, Any] | None:
        target = ipaddress.ip_address(str(target_ip))
        for task in self._approved_tasks:
            if not task.approved or task.operator != user or task.source_host != host_id:
                continue
            within_time = task.start_time <= event_time <= task.end_time
            within_scope = any(
                target in ipaddress.ip_network(network, strict=False)
                for network in task.allowed_targets
            )
            if within_time and within_scope:
                result = task.model_dump(mode="json")
                result.update(within_approved_time=True, within_target_scope=True)
                return result
        return None

    def find_threat_intel(self, indicator: str) -> dict[str, Any] | None:
        item = next(
            (intel for intel in self._threat_intel if str(intel.indicator) == str(indicator)),
            None,
        )
        return item.model_dump(mode="json") if item else None

    def find_related_events(
        self,
        alert_id: str,
        host_id: str,
        center_time: datetime,
        window_minutes: int = 30,
    ) -> dict[str, Any] | None:
        direct = next(
            (record for record in self._related_events if record.alert_id == alert_id),
            None,
        )
        if direct:
            return direct.model_dump(mode="json")

        start = center_time - timedelta(minutes=window_minutes)
        end = center_time + timedelta(minutes=window_minutes)
        fallback = next(
            (
                record
                for record in self._related_events
                if record.host_id == host_id
                and any(start <= event.time <= end for event in record.events)
            ),
            None,
        )
        return fallback.model_dump(mode="json") if fallback else None
