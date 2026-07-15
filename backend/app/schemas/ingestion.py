"""Incoming event schemas. Malformed requests are rejected here before any business
processing (validation-first). Different banking systems produce different field names;
these models define the single canonical shape ARGUS accepts.
"""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AuthEventIn(BaseModel):
    customer_ref: str = Field(..., examples=["CUST-00021"])
    account_number: str | None = None
    device_fingerprint: str = Field(..., examples=["dev-abc123"])
    ip_address: str = Field(..., examples=["203.0.113.9"])
    endpoint_ref: str = Field("EP-AUTH-01")
    result: str = Field("success", examples=["success", "failure"])
    method: str = "password"
    city: str | None = None
    country: str | None = None
    event_time: datetime | None = None
    source: str = "api"


class TransactionIn(BaseModel):
    customer_ref: str
    account_number: str
    dest_external: str | None = None
    device_fingerprint: str | None = None
    ip_address: str | None = None
    endpoint_ref: str = "EP-PAY-01"
    amount: float = Field(..., gt=0)
    currency: str = "INR"
    category: str = "transfer"
    channel: str = "mobile"
    event_time: datetime | None = None
    source: str = "api"


class DisclosureIn(BaseModel):
    vuln_ref: str = Field(..., examples=["CVE-2024-0001"])
    disclosure_type: str = Field("cve")
    title: str
    description: str = ""
    severity: str = "high"
    cvss: float | None = None
    affected_endpoint_ref: str
    affected_algorithm: str | None = None
    exposure_window_start: datetime
    exposure_window_end: datetime | None = None
    remediation_deadline: datetime | None = None
    source: str = "api"


class EndpointIn(BaseModel):
    endpoint_ref: str
    name: str
    category: str
    criticality: str = "medium"
    data_sensitivity: str = "pii"
    encryption_profile: str = "TLS1.3-AES256-GCM"


class AnalystActionIn(BaseModel):
    investigation_code: str | None = None
    action: str
    actor: str = "analyst"
    detail: str | None = None
