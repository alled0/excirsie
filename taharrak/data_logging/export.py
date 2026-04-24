"""JSON-safe export helpers for structured rep records."""

from __future__ import annotations

from dataclasses import asdict

from .schema import FaultRecord, RepRecord, SessionSummary


def fault_record_to_dict(record: FaultRecord) -> dict:
    return asdict(record)


def rep_record_to_dict(record: RepRecord) -> dict:
    payload = asdict(record)
    payload["faults"] = [fault_record_to_dict(FaultRecord(**fault)) if isinstance(fault, dict)
                          else fault_record_to_dict(fault) for fault in record.faults]
    return payload


def session_summary_to_dict(summary: SessionSummary) -> dict:
    payload = asdict(summary)
    payload["records"] = [rep_record_to_dict(record) for record in summary.records]
    return payload
