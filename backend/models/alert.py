from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, IPvAnyAddress


class ProcessInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    path: str | None = None
    command_line: str | None = None
    parent_process: str | None = None


class DetectionInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rule_id: str
    rule_name: str
    matched_field: str
    matched_value: str


class Alert(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alert_id: str
    alert_time: datetime
    alert_type: Literal["malicious_ip_connection"]
    alert_name: str
    severity: Literal["low", "medium", "high", "critical"]
    source: str
    src_ip: IPvAnyAddress
    src_port: int | None = Field(default=None, ge=0, le=65535)
    dst_ip: IPvAnyAddress
    dst_port: int | None = Field(default=None, ge=0, le=65535)
    protocol: str | None = None
    host_id: str
    hostname: str
    user: str
    process: ProcessInfo | None = None
    detection: DetectionInfo
    raw_log: str | None = None
    demo_scenario: str
