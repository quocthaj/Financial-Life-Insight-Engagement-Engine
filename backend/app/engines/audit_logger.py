from datetime import datetime
from typing import Any, Dict, List, Optional


def _find_policy_decision(
    candidate_id: str, policy_decisions: List[Any]
) -> Optional[Any]:
    for decision in policy_decisions:
        if getattr(decision, "candidate_id", None) == candidate_id or (
            isinstance(decision, dict) and decision.get("candidate_id") == candidate_id
        ):
            return decision
    return None


def _find_output(
    candidate_id: str, outputs_with_challenges: List[Dict[str, Any]]
) -> Optional[Dict[str, Any]]:
    for out in outputs_with_challenges:
        if (
            out.get("candidate_id") == candidate_id
            or out.get("fact_id") == candidate_id
        ):
            return out
    return None


def build_audit_entries(
    candidates: List[Dict[str, Any]],
    facts: List[Dict[str, Any]],
    policy_decisions: List[Any],
    outputs_with_challenges: List[Dict[str, Any]],
    generation_mode: str = "template",
    llm_prompt_version: str = "template_v1",
    model_name: str = "none_template_generator",
) -> List[Dict[str, Any]]:
    """
    Builds audit trace entries for all candidates processed through the pipeline.
    """
    entries = []

    # Map fact_id to fact dictionary for quick lookup as evidence
    facts_map = {f["fact_id"]: f for f in facts}

    for cand in candidates:
        # Support both real candidates and MVP facts acting as candidates
        candidate_id = cand.get("candidate_id") or cand.get("fact_id")
        customer_id = cand.get("customer_id")
        candidate_type = cand.get("pattern_type") or cand.get("fact_type")
        candidate_desc = cand.get("description")

        based_on_facts = cand.get("based_on_facts") or [candidate_id]

        policy_dec = _find_policy_decision(candidate_id, policy_decisions)
        output_item = _find_output(candidate_id, outputs_with_challenges)

        # Policy details
        policy_result = "unknown"
        policy_rules = []
        policy_reasons = []

        if policy_dec:
            policy_result = getattr(policy_dec, "decision", "unknown")
            policy_rules = getattr(policy_dec, "rule_ids_triggered", [])
            policy_reasons = getattr(policy_dec, "reasons", [])

        # Initialize output fields
        obs_text = None
        nudge_text = None
        obs_safety_passed = None
        obs_safety_violations = []
        nudge_safety_passed = None
        nudge_safety_violations = []

        chal_title = None
        chal_desc = None
        chal_criteria = None
        chal_safety_passed = None
        chal_safety_violations = []

        final_status = "rejected_by_policy" if policy_result == "rejected" else "unknown"

        if output_item:
            obs = output_item.get("observation")
            nudge = output_item.get("nudge")
            obs_safety = output_item.get("observation_safety")
            nudge_safety = output_item.get("nudge_safety")

            challenge = output_item.get("challenge")

            if obs:
                obs_text = obs.text
            if nudge:
                nudge_text = nudge.text
            if obs_safety:
                obs_safety_passed = obs_safety.passed
                obs_safety_violations = obs_safety.violations
            if nudge_safety:
                nudge_safety_passed = nudge_safety.passed
                nudge_safety_violations = nudge_safety.violations

            if challenge:
                chal_title = challenge.title
                chal_desc = challenge.description
                chal_criteria = challenge.criteria
                chal_safety_passed = challenge.passed_safety_check

                for key in [
                    "challenge_safety_title",
                    "challenge_safety_desc",
                    "challenge_safety_criteria",
                ]:
                    safety = output_item.get(key)
                    if safety:
                        chal_safety_violations.extend(safety.violations)

            # Compute final status
            all_passed = (
                obs_safety_passed is True
                and nudge_safety_passed is True
                and chal_safety_passed is True
            )
            final_status = "published" if all_passed else "blocked_by_safety"

        # Resolve associated facts for audit evidence
        associated_facts = []
        for fid in based_on_facts:
            if fid in facts_map:
                associated_facts.append(facts_map[fid])

        entry = {
            "trace_id": f"trace_{candidate_id}",
            "customer_id": customer_id,
            "candidate_id": candidate_id,
            "candidate_type": candidate_type,
            "candidate_description": candidate_desc,
            "based_on_facts": based_on_facts,
            "facts": associated_facts,
            "policy_result": policy_result,
            "policy_rule_ids_triggered": policy_rules,
            "policy_reasons": policy_reasons,
            "observation_text": obs_text,
            "nudge_text": nudge_text,
            "observation_safety_passed": obs_safety_passed,
            "observation_safety_violations": obs_safety_violations,
            "nudge_safety_passed": nudge_safety_passed,
            "nudge_safety_violations": nudge_safety_violations,
            "challenge_title": chal_title,
            "challenge_description": chal_desc,
            "challenge_criteria": chal_criteria,
            "challenge_safety_passed": chal_safety_passed,
            "challenge_safety_violations": chal_safety_violations,
            "generation_mode": generation_mode,
            "llm_prompt_version": llm_prompt_version,
            "model_name": model_name,
            "final_status": final_status,
            "timestamp": datetime.utcnow().isoformat() + "Z",
        }
        entries.append(entry)

    return entries
