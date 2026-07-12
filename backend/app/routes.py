from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any

from app.models.schemas import CustomerFullProfile, AuditEntry, Observation, Nudge, SafetyResult, Challenge
from app.data.customer_registry import get_all_customers, get_customer_profile, get_customer_features, CUSTOMERS
from app.data.product_catalog import PRODUCT_CATALOG
from app.data.audit_store import load_audit_logs, add_audit_entries, clear_audit_logs

from app.engines.audit_logger import build_audit_entries
from app.agents.financial_mirror_agent import FinancialMirrorAgent

router = APIRouter(prefix="/api")

@router.get("/customers")
def list_customers():
    return get_all_customers()

@router.get("/customers/{customer_id}")
def get_customer(customer_id: str):
    profile = get_customer_profile(customer_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Customer not found")
    return profile

@router.get("/products")
def list_products():
    return PRODUCT_CATALOG

@router.get("/audit-logs")
def list_audit_logs():
    return load_audit_logs()

@router.post("/audit-logs/clear")
def clear_logs():
    clear_audit_logs()
    return {"message": "Audit logs cleared successfully"}

@router.post("/pipeline/run")
def run_pipeline(payload: Dict[str, str]):
    customer_id = payload.get("customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="Missing customer_id in payload")
        
    raw_profile = get_customer_profile(customer_id)
    if not raw_profile:
        raise HTTPException(status_code=404, detail=f"Customer with ID '{customer_id}' not found")
        
    # Map customer_id (e.g. 'cust_00123') to customer key (e.g. 'maria')
    customer_key = customer_id
    if customer_id in CUSTOMERS:
        customer_key = CUSTOMERS[customer_id]["key"]

    agent = FinancialMirrorAgent()
    try:
        run_result = agent.run(customer_key, enable_test_verification=True)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    # Map outputs and challenges to structure expected by build_audit_entries
    outputs_for_audit = []
    
    # 1. safety failed outputs
    for out in run_result.result.get("safety_failed_outputs", []):
        fact_payload = out["fact"]
        fact_id = fact_payload["fact_id"]
        
        # Retrieve mapping details
        fact_type = fact_payload.get("fact_type")
        related_product_id = None
        related_feature = None
        nudge_type = "observation_only"

        if fact_type == "spending_spike":
            related_product_id = "spending_breakdown"
            related_feature = "Spending Breakdown"
            nudge_type = "spending_awareness"
        elif fact_type == "idle_balance":
            related_product_id = None
            related_feature = None
            nudge_type = "observation_only"
        elif fact_type == "dormant_feature":
            scope = fact_payload.get("scope", {})
            related_product_id = scope.get("feature_id")
            related_feature = scope.get("feature_name")
            nudge_type = "educational_exploration"
        elif fact_type == "upcoming_due_reminder":
            related_product_id = "bnpl"
            related_feature = "BNPL"
            nudge_type = "neutral_due_reminder"

        obs_obj = Observation(
            observation_id=f"obs_{fact_id}",
            customer_id=customer_key,
            candidate_id=fact_id,
            based_on_facts=[fact_id],
            text=out["observation"]
        )
        
        nudge_obj = Nudge(
            nudge_id=f"nudge_{fact_id}",
            customer_id=customer_key,
            observation_id=f"obs_{fact_id}",
            related_product_id=related_product_id,
            related_feature=related_feature,
            nudge_type=nudge_type,
            text=out["nudge"],
            passed_safety_check=False,
            safety_notes=f"Safety check failed. Violations: {'; '.join(out.get('safety_violations', []))}"
        )
        obs_safety = SafetyResult(
            checked_item_id=f"obs_{fact_id}",
            item_type="observation",
            passed=False,
            violations=out.get("safety_violations", [])
        )
        nudge_safety = SafetyResult(
            checked_item_id=f"nudge_{fact_id}",
            item_type="nudge",
            passed=False,
            violations=out.get("safety_violations", [])
        )
        
        outputs_for_audit.append({
            "fact_id": fact_id,
            "candidate_id": fact_id,
            "observation": obs_obj,
            "nudge": nudge_obj,
            "observation_safety": obs_safety,
            "nudge_safety": nudge_safety,
            "challenge": None,
        })
        
    # 2. safety passed outputs (which also generated challenges if any)
    challenges_raw = run_result.result.get("challenges", [])
    for out in challenges_raw:
        fact_payload = out["fact"]
        fact_id = fact_payload["fact_id"]
        
        # Retrieve mapping details
        fact_type = fact_payload.get("fact_type")
        related_product_id = None
        related_feature = None
        nudge_type = "observation_only"

        if fact_type == "spending_spike":
            related_product_id = "spending_breakdown"
            related_feature = "Spending Breakdown"
            nudge_type = "spending_awareness"
        elif fact_type == "idle_balance":
            related_product_id = None
            related_feature = None
            nudge_type = "observation_only"
        elif fact_type == "dormant_feature":
            scope = fact_payload.get("scope", {})
            related_product_id = scope.get("feature_id")
            related_feature = scope.get("feature_name")
            nudge_type = "educational_exploration"
        elif fact_type == "upcoming_due_reminder":
            related_product_id = "bnpl"
            related_feature = "BNPL"
            nudge_type = "neutral_due_reminder"

        obs_obj = Observation(
            observation_id=f"obs_{fact_id}",
            customer_id=customer_key,
            candidate_id=fact_id,
            based_on_facts=[fact_id],
            text=out["observation"]
        )
        
        nudge_obj = Nudge(
            nudge_id=f"nudge_{fact_id}",
            customer_id=customer_key,
            observation_id=f"obs_{fact_id}",
            related_product_id=related_product_id,
            related_feature=related_feature,
            nudge_type=nudge_type,
            text=out["nudge"],
            passed_safety_check=True,
            safety_notes="Passed safety check."
        )
        obs_safety = SafetyResult(
            checked_item_id=f"obs_{fact_id}",
            item_type="observation",
            passed=True,
            violations=[]
        )
        nudge_safety = SafetyResult(
            checked_item_id=f"nudge_{fact_id}",
            item_type="nudge",
            passed=True,
            violations=[]
        )
        
        challenge_dict = out.get("challenge")
        challenge_obj = None
        if challenge_dict:
            challenge_obj = Challenge(**challenge_dict)
            
        challenge_safety_title = SafetyResult(**out.get("challenge_safety_title")) if out.get("challenge_safety_title") else None
        challenge_safety_desc = SafetyResult(**out.get("challenge_safety_desc")) if out.get("challenge_safety_desc") else None
        challenge_safety_criteria = SafetyResult(**out.get("challenge_safety_criteria")) if out.get("challenge_safety_criteria") else None
        
        outputs_for_audit.append({
            "fact_id": fact_id,
            "candidate_id": fact_id,
            "observation": obs_obj,
            "nudge": nudge_obj,
            "observation_safety": obs_safety,
            "nudge_safety": nudge_safety,
            "challenge": challenge_obj,
            "challenge_safety_title": challenge_safety_title,
            "challenge_safety_desc": challenge_safety_desc,
            "challenge_safety_criteria": challenge_safety_criteria,
        })

    # Prepare inputs for build_audit_entries
    facts_raw = run_result.result.get("facts", [])
    
    # Decisions mapping: need list of Pydantic objects or dicts
    decisions_raw = []
    from app.models.schemas import PolicyDecision
    for dec in run_result.result.get("policy", {}).get("decisions", []):
        try:
            decisions_raw.append(PolicyDecision(**dec))
        except Exception:
            decisions_raw.append(dec)

    audit_entries_raw = build_audit_entries(
        candidates=facts_raw,
        facts=facts_raw,
        policy_decisions=decisions_raw,
        outputs_with_challenges=outputs_for_audit,
        generation_mode="llm_agent",
        llm_prompt_version=run_result.model_used.get("prompt_version", "unknown"),
        model_name=run_result.model_used.get("model_name", "unknown")
    )

    try:
        validated_entries = [AuditEntry(**entry).model_dump(mode="json") for entry in audit_entries_raw]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to validate audit log schemas: {str(e)}")
        
    add_audit_entries(validated_entries)

    # Reconstruct legacy outputs & challenges for UI backwards-compatibility
    outputs_legacy = []
    for out in run_result.result.get("safety_passed_outputs", []):
        f_id = out["fact"]["fact_id"]
        
        # Retrieve mapping details
        fact_payload = out["fact"]
        fact_type = fact_payload.get("fact_type")
        related_product_id = None
        related_feature = None
        nudge_type = "observation_only"

        if fact_type == "spending_spike":
            related_product_id = "spending_breakdown"
            related_feature = "Spending Breakdown"
            nudge_type = "spending_awareness"
        elif fact_type == "idle_balance":
            related_product_id = None
            related_feature = None
            nudge_type = "observation_only"
        elif fact_type == "dormant_feature":
            scope = fact_payload.get("scope", {})
            related_product_id = scope.get("feature_id")
            related_feature = scope.get("feature_name")
            nudge_type = "educational_exploration"
        elif fact_type == "upcoming_due_reminder":
            related_product_id = "bnpl"
            related_feature = "BNPL"
            nudge_type = "neutral_due_reminder"

        obs_obj = Observation(
            observation_id=f"obs_{f_id}",
            customer_id=customer_key,
            candidate_id=f_id,
            based_on_facts=[f_id],
            text=out["observation"]
        )
        nudge_obj = Nudge(
            nudge_id=f"nudge_{f_id}",
            customer_id=customer_key,
            observation_id=f"obs_{f_id}",
            related_product_id=related_product_id,
            related_feature=related_feature,
            nudge_type=nudge_type,
            text=out["nudge"],
            passed_safety_check=True,
            safety_notes="Passed safety check."
        )
        obs_safety = SafetyResult(
            checked_item_id=f"obs_{f_id}",
            item_type="observation",
            passed=True,
            violations=[]
        )
        nudge_safety = SafetyResult(
            checked_item_id=f"nudge_{f_id}",
            item_type="nudge",
            passed=True,
            violations=[]
        )
        outputs_legacy.append({
            "fact_id": f_id,
            "policy_decision": out["policy_result"],
            "observation": obs_obj,
            "nudge": nudge_obj,
            "observation_safety": obs_safety,
            "nudge_safety": nudge_safety,
        })
    for out in run_result.result.get("safety_failed_outputs", []):
        f_id = out["fact"]["fact_id"]
        
        # Retrieve mapping details
        fact_payload = out["fact"]
        fact_type = fact_payload.get("fact_type")
        related_product_id = None
        related_feature = None
        nudge_type = "observation_only"

        if fact_type == "spending_spike":
            related_product_id = "spending_breakdown"
            related_feature = "Spending Breakdown"
            nudge_type = "spending_awareness"
        elif fact_type == "idle_balance":
            related_product_id = None
            related_feature = None
            nudge_type = "observation_only"
        elif fact_type == "dormant_feature":
            scope = fact_payload.get("scope", {})
            related_product_id = scope.get("feature_id")
            related_feature = scope.get("feature_name")
            nudge_type = "educational_exploration"
        elif fact_type == "upcoming_due_reminder":
            related_product_id = "bnpl"
            related_feature = "BNPL"
            nudge_type = "neutral_due_reminder"

        obs_obj = Observation(
            observation_id=f"obs_{f_id}",
            customer_id=customer_key,
            candidate_id=f_id,
            based_on_facts=[f_id],
            text=out["observation"]
        )
        violations = out.get("safety_violations", [])
        nudge_obj = Nudge(
            nudge_id=f"nudge_{f_id}",
            customer_id=customer_key,
            observation_id=f"obs_{f_id}",
            related_product_id=related_product_id,
            related_feature=related_feature,
            nudge_type=nudge_type,
            text=out["nudge"],
            passed_safety_check=False,
            safety_notes=f"Safety check failed. Violations: {'; '.join(violations)}"
        )
        obs_safety = SafetyResult(
            checked_item_id=f"obs_{f_id}",
            item_type="observation",
            passed=False,
            violations=violations
        )
        nudge_safety = SafetyResult(
            checked_item_id=f"nudge_{f_id}",
            item_type="nudge",
            passed=False,
            violations=violations
        )
        outputs_legacy.append({
            "fact_id": f_id,
            "policy_decision": out["policy_result"],
            "observation": obs_obj,
            "nudge": nudge_obj,
            "observation_safety": obs_safety,
            "nudge_safety": nudge_safety,
        })

    challenges_legacy = []
    for c in run_result.result.get("challenges", []):
        chal = c.get("challenge")
        if chal:
            challenges_legacy.append({
                "based_on_nudge": chal.get("based_on_nudge"),
                "challenge": chal,
                "passed_safety_check": chal.get("passed_safety_check"),
                "safety_violations": {
                    "title": c.get("challenge_safety_title", {}).get("violations", []),
                    "description": c.get("challenge_safety_desc", {}).get("violations", []),
                    "criteria": c.get("challenge_safety_criteria", {}).get("violations", [])
                }
            })

    return {
        "customer_id": customer_id,
        "data_availability": run_result.result.get("data_check"),
        "facts_count": len(facts_raw),
        "facts": facts_raw,
        "policies": run_result.result.get("policy", {}).get("decisions", []),
        "outputs": outputs_legacy,
        "challenges": challenges_legacy,
        "audit_entries": validated_entries,
        # Agent fields
        "agent_goal": run_result.agent_goal,
        "planner_mode": run_result.planner_mode,
        "base_plan": run_result.base_plan,
        "execution_trace": run_result.execution_trace,
        "llm_decisions": run_result.llm_decisions,
        "model_used": run_result.model_used,
        "final_status": run_result.final_status,
        "verification": run_result.verification,
        "result": run_result.result
    }
