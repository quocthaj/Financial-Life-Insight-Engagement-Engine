"""
pipeline_repository.py

Persistence layer for pipeline runs and audit entries.

Controlled by:
  PERSIST_RUNS=true|false  (default false)

If PERSIST_RUNS=true:
  - create_pipeline_run() inserts a row into Supabase pipeline_runs.
  - save_audit_entries()  inserts rows into Supabase audit_entries.

If PERSIST_RUNS=false (or Supabase unreachable):
  - Both functions are no-ops and return a PersistenceResult indicating skipped/error.

Rules:
  - Never block the agent pipeline on persistence failure.
  - Always return a PersistenceResult.
  - Persistence uses SUPABASE_SERVICE_ROLE_KEY (not anon key) for write access.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────
# Result dataclass
# ─────────────────────────────────────────────────────────────

@dataclass
class PersistenceResult:
    persisted: bool = False
    run_id: Optional[str] = None
    audit_entry_count: int = 0
    error: Optional[str] = None
    skipped_reason: Optional[str] = None


# ─────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────

def _supabase_post(table: str, payload: Dict[str, Any] | List[Dict[str, Any]]) -> None:
    url_base = os.getenv("SUPABASE_URL", "").rstrip("/")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")

    if not url_base or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required for persistence.")

    url = f"{url_base}/rest/v1/{table}"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=url, data=data, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            resp.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase insert error {exc.code} on {table}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Supabase network error on {table}: {exc}") from exc


def _should_persist() -> bool:
    return os.getenv("PERSIST_RUNS", "false").strip().lower() == "true"


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def create_pipeline_run(
    customer_id: str,
    customer_key: str,
    data_source: str,
    final_status: str,
    model_used: Dict[str, Any],
    execution_trace: List[Dict[str, Any]],
    llm_decisions: List[Dict[str, Any]],
    facts_count: int,
    safety_retry_attempts: List[Dict[str, Any]],
    verification: Dict[str, Any],
) -> PersistenceResult:
    """
    Insert one row into pipeline_runs.

    Returns PersistenceResult with run_id if successful.
    """
    if not _should_persist():
        return PersistenceResult(
            persisted=False,
            skipped_reason="PERSIST_RUNS is not enabled.",
        )

    run_id = str(uuid.uuid4())

    accepted_count = 0
    rejected_count = 0
    for item in execution_trace:
        if item.get("step_id") == "evaluate_policy":
            metadata = item.get("metadata", {})
            accepted_count = int(metadata.get("accepted_count", 0) or 0)
            rejected_count = int(metadata.get("rejected_count", 0) or 0)
            break

    payload = {
        "run_id": run_id,
        "customer_id": customer_id,
        "status": final_status,
        "facts_count": facts_count,
        "accepted_count": accepted_count,
        "rejected_count": rejected_count,
        "published_count": accepted_count if final_status == "published" else 0,
        "result_json": json.dumps({
            "customer_key": customer_key,
            "data_source": data_source,
            "model_used": model_used,
            "execution_trace": execution_trace,
            "llm_decisions": llm_decisions,
            "safety_retry_attempts": safety_retry_attempts,
            "verification": verification,
        }),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        _supabase_post("pipeline_runs", payload)
        return PersistenceResult(
            persisted=True,
            run_id=run_id,
        )
    except Exception as exc:
        return PersistenceResult(
            persisted=False,
            error=str(exc),
        )


def save_audit_entries(
    run_id: Optional[str],
    customer_id: str,
    validated_entries: List[Dict[str, Any]],
) -> PersistenceResult:
    """
    Insert audit entries into audit_entries table.

    Links to pipeline_run via run_id if available.
    """
    if not _should_persist():
        return PersistenceResult(
            persisted=False,
            skipped_reason="PERSIST_RUNS is not enabled.",
        )

    if not validated_entries:
        return PersistenceResult(
            persisted=True,
            run_id=run_id,
            audit_entry_count=0,
        )

    rows = []
    for entry in validated_entries:
        row = {
            "trace_id": entry.get("trace_id") or str(uuid.uuid4()),
            "run_id": run_id,
            "customer_id": customer_id,
            "candidate_id": entry.get("candidate_id", "unknown"),
            "candidate_type": entry.get("candidate_type", "unknown"),
            "policy_result": entry.get("policy_result", "unknown"),
            "final_status": entry.get("final_status", "unknown"),
            "model_name": entry.get("model_name", "unknown"),
            "llm_prompt_version": entry.get("llm_prompt_version", "unknown"),
            "generation_mode": entry.get("generation_mode", "unknown"),
            "entry_json": json.dumps(entry),
            "created_at": entry.get("timestamp") or datetime.now(timezone.utc).isoformat(),
        }
        rows.append(row)

    try:
        _supabase_post("audit_entries", rows)
        return PersistenceResult(
            persisted=True,
            run_id=run_id,
            audit_entry_count=len(rows),
        )
    except Exception as exc:
        return PersistenceResult(
            persisted=False,
            run_id=run_id,
            error=str(exc),
        )
