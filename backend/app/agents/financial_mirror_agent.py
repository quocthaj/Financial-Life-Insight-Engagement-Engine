import os
from dataclasses import dataclass, asdict, field
from typing import Any, Dict, List, Optional

from app.engines.llm_client import LLMClient
from app.data.customer_data_provider import get_customer_data_provider, CustomerDataProvider
from app.data.pipeline_repository import create_pipeline_run, save_audit_entries
from app.agents.persona_verification import verify_against_persona_registry
from app.models.schemas import CustomerFullProfile, Nudge
from app.engines.data_checker import check_data_availability
from app.engines.fact_pattern_engine import generate_facts
from app.engines.policy_engine import evaluate_policies
from app.engines.safety_engine import validate_observation, validate_nudge
from app.engines.engagement_engine import generate_challenges
from app.engines.audit_logger import build_audit_entries


@dataclass
class AgentPlanStep:
    step_id: str
    tool: str
    purpose: str
    status: str = "pending"
    condition: Optional[str] = None


@dataclass
class AgentTraceItem:
    step_id: str
    tool: str
    status: str
    summary: str
    decision: str
    next_action: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentRunResult:
    agent_goal: str
    planner_mode: str
    base_plan: List[Dict[str, Any]]
    execution_trace: List[Dict[str, Any]]
    llm_decisions: List[Dict[str, Any]]
    model_used: Dict[str, Any]
    final_status: str
    verification: Dict[str, Any]
    result: Dict[str, Any]


class FinancialMirrorAgent:
    """
    Governed Dynamic Agent for Financial Mirror.

    Responsibilities:
    - Build a safe base plan.
    - Call engines as tools.
    - Use LLM only for constrained action selection and safe wording.
    - Apply deterministic Policy/Safety/Audit gates.
    - Return an execution trace visible to the UI.
    """

    def __init__(
        self,
        llm_client: Optional[LLMClient] = None,
        data_provider: Optional[CustomerDataProvider] = None,
    ) -> None:
        self.llm_client = llm_client or LLMClient()
        self.data_provider = data_provider or get_customer_data_provider()
        self.planner_mode = "governed_dynamic_llm_assisted"

    def load_customer_data(self, customer_key: str) -> Dict[str, Any]:
        allow_fallback = os.getenv("ALLOW_MOCK_FALLBACK", "false").strip().lower() == "true"
        fallback_used = False

        customer_profile = self.data_provider.get_customer_profile(customer_key)
        source = self.data_provider.source

        if customer_profile is None and allow_fallback and source != "mock":
            # Fall back to mock if Supabase has no data for this key
            from app.data.customer_data_provider import MockCustomerDataProvider
            mock_provider = MockCustomerDataProvider()
            customer_profile = mock_provider.get_customer_profile(customer_key)
            available_features = mock_provider.get_customer_features(customer_key)
            fallback_used = True
            source = "mock"
        else:
            available_features = self.data_provider.get_customer_features(customer_key)

        return {
            "customer_key": customer_key,
            "customer_profile": customer_profile,
            "available_features": available_features,
            "source": source,
            "fallback_used": fallback_used,
        }

    def _model_used(self) -> Dict[str, Any]:
        return {
            "provider": self.llm_client.provider,
            "model_name": self.llm_client.model_name,
            "prompt_version": self.llm_client.prompt_version,
            "llm_used": self.llm_client.provider != "mock",
        }

    def _loaded_customer_result(self, loaded_customer: Dict[str, Any]) -> Dict[str, Any]:
        customer_profile = loaded_customer.get("customer_profile") or {}
        profile = customer_profile.get("profile", {})
        return {
            "customer_key": loaded_customer["customer_key"],
            "customer_id": profile.get("customer_id", loaded_customer["customer_key"]),
            "available_features": loaded_customer["available_features"],
            "source": loaded_customer.get("source", "mock"),
            "fallback_used": loaded_customer.get("fallback_used", False),
        }

    def _persist_run(
        self,
        customer_key: str,
        loaded_customer: Dict[str, Any],
        actual_outcome: str,
        model_used: Dict[str, Any],
        execution_trace: List[AgentTraceItem],
        llm_decisions: List[Dict[str, Any]],
        facts: List[Any],
        policy_results: List[Any],
        outputs_for_audit: List[Dict[str, Any]],
        safety_retry_attempts: List[Dict[str, Any]],
        verification: Dict[str, Any],
    ) -> Dict[str, Any]:
        customer_profile = loaded_customer.get("customer_profile") or {}
        profile = customer_profile.get("profile", {})
        customer_id = profile.get("customer_id", customer_key)
        trace_list = [asdict(item) for item in execution_trace]
        fact_dicts = [
            fact.model_dump(mode="json") if hasattr(fact, "model_dump") else fact
            for fact in facts
        ]

        persist_run_result = create_pipeline_run(
            customer_id=customer_id,
            customer_key=customer_key,
            data_source=loaded_customer.get("source", "mock"),
            final_status=actual_outcome,
            model_used=model_used,
            execution_trace=trace_list,
            llm_decisions=llm_decisions,
            facts_count=len(fact_dicts),
            safety_retry_attempts=safety_retry_attempts,
            verification=verification,
        )

        audit_result = None
        if fact_dicts:
            audit_entries = build_audit_entries(
                candidates=fact_dicts,
                facts=fact_dicts,
                policy_decisions=policy_results,
                outputs_with_challenges=outputs_for_audit,
                generation_mode="llm_agent",
                llm_prompt_version=model_used.get("prompt_version", "unknown"),
                model_name=model_used.get("model_name", "unknown"),
            )
            for entry in audit_entries:
                entry["final_status"] = actual_outcome
            audit_result = save_audit_entries(
                run_id=persist_run_result.run_id,
                customer_id=customer_id,
                validated_entries=audit_entries,
            )

        error = persist_run_result.error
        if audit_result and audit_result.error:
            error = "; ".join([part for part in [error, audit_result.error] if part])

        return {
            "persisted": persist_run_result.persisted and (audit_result.persisted if audit_result else True),
            "run_id": persist_run_result.run_id,
            "error": error,
            "skipped_reason": persist_run_result.skipped_reason,
            "audit_entry_count": audit_result.audit_entry_count if audit_result else 0,
        }

    def build_base_plan(self) -> List[AgentPlanStep]:
        return [
            AgentPlanStep(
                step_id="load_customer_data",
                tool="customer_loader",
                purpose="Load customer profile and behavioral data.",
            ),
            AgentPlanStep(
                step_id="check_data_availability",
                tool="data_checker",
                purpose="Validate available data groups before insight generation.",
            ),
            AgentPlanStep(
                step_id="detect_facts",
                tool="fact_pattern_engine",
                purpose="Detect evidence-backed behavioral facts.",
            ),
            AgentPlanStep(
                step_id="evaluate_policy",
                tool="policy_engine",
                purpose="Apply eligibility, product-scope, and non-advisory policy gates.",
            ),
            AgentPlanStep(
                step_id="select_next_action_after_policy",
                tool="llm_action_selector",
                purpose="Select next action from governed candidate actions.",
                condition="policy_evaluated",
            ),
            AgentPlanStep(
                step_id="generate_wording",
                tool="llm_wording_generator",
                purpose="Generate non-advisory observation and nudge for policy-approved facts.",
                condition="policy_has_accepted_candidates",
            ),
            AgentPlanStep(
                step_id="safety_check",
                tool="safety_engine",
                purpose="Validate generated wording against non-advisory safety rules.",
            ),
            AgentPlanStep(
                step_id="generate_challenge",
                tool="engagement_engine",
                purpose="Generate behavior-adaptive challenge only after safe nudge.",
                condition="nudge_passed_safety",
            ),
            AgentPlanStep(
                step_id="write_audit",
                tool="audit_logger",
                purpose="Record decisions, rejections, safety results, and model metadata.",
            ),
            AgentPlanStep(
                step_id="finalize",
                tool="agent_core",
                purpose="Finalize run and return results.",
            ),
        ]

    def run(self, customer_key: str, enable_test_verification: bool = False) -> AgentRunResult:
        """
        Governed agentic run pipeline.
        """
        goal = f"Generate a safe non-advisory Financial Mirror for persona '{customer_key}'."
        base_plan = self.build_base_plan()
        execution_trace: List[AgentTraceItem] = []
        llm_decisions: List[Dict[str, Any]] = []

        execution_trace.append(
            AgentTraceItem(
                step_id="initialize_agent",
                tool="financial_mirror_agent",
                status="completed",
                summary="Built governed dynamic base plan.",
                decision="Continue to customer loading.",
                next_action="load_customer_data",
                metadata={
                    "customer_key": customer_key,
                    "planner_mode": self.planner_mode,
                },
            )
        )

        loaded_customer = self.load_customer_data(customer_key)
        customer_profile = loaded_customer["customer_profile"]
        if customer_profile is None:
            raise ValueError(f"Customer '{customer_key}' not found in {loaded_customer.get('source', 'mock')} data source.")

        display_name = (
            customer_profile.get("profile", {}).get("display_name")
            or customer_profile.get("display_name")
            or customer_key
        )

        execution_trace.append(
            AgentTraceItem(
                step_id="load_customer_data",
                tool="customer_data_provider",
                status="completed",
                summary=f"Loaded persona data for {display_name} from {loaded_customer.get('source', 'mock')}.",
                decision="Continue to data availability check.",
                next_action="check_data_availability",
                metadata={
                    "customer_key": customer_key,
                    "customer_id": customer_profile.get("profile", {}).get("customer_id", customer_key),
                    "data_source": loaded_customer.get("source", "mock"),
                    "fallback_used": loaded_customer.get("fallback_used", False),
                    "available_features_count": len(loaded_customer.get("available_features", [])),
                },
            )
        )

        customer_profile_model = CustomerFullProfile(**customer_profile)
        data_check_result = check_data_availability(customer_profile_model)

        execution_trace.append(
            AgentTraceItem(
                step_id="check_data_availability",
                tool="data_checker",
                status="completed",
                summary=(
                    f"Available groups: {data_check_result.available_data_groups}; "
                    f"Missing groups: {data_check_result.missing_data_groups}"
                ),
                decision=(
                    "Continue to fact detection."
                    if data_check_result.can_generate_financial_observations
                    else "Data is insufficient for financial observation generation."
                ),
                next_action=(
                    "detect_facts"
                    if data_check_result.can_generate_financial_observations
                    else "write_audit"
                ),
                metadata={
                    "can_generate_financial_observations": data_check_result.can_generate_financial_observations,
                    "can_generate_product_nudges": data_check_result.can_generate_product_nudges,
                    "notes": data_check_result.notes,
                },
            )
        )

        if not data_check_result.can_generate_financial_observations:
            actual_outcome = "no_facts"
            execution_trace.append(
                AgentTraceItem(
                    step_id="write_audit",
                    tool="audit_logger",
                    status="completed",
                    summary="No facts were generated because required data groups are missing.",
                    decision="Finalize run and record insufficient data in audit log.",
                    next_action="finalize",
                    metadata={
                        "reason": "insufficient_data",
                        "missing_data_groups": data_check_result.missing_data_groups,
                    },
                )
            )

            execution_trace.append(
                AgentTraceItem(
                    step_id="finalize",
                    tool="agent_core",
                    status="completed",
                    summary=f"Run finalized with status {actual_outcome}.",
                    decision="Finalize agent run.",
                    next_action="verify_against_persona_registry" if enable_test_verification else "end",
                )
            )

            verification = {
                "enabled": False,
                "expected_outcome": None,
                "actual_outcome": actual_outcome,
                "match": None,
            }
            if enable_test_verification:
                verification = verify_against_persona_registry(customer_key, actual_outcome)
                execution_trace.append(
                    AgentTraceItem(
                        step_id="verify_against_persona_registry",
                        tool="persona_verification",
                        status="completed",
                        summary="Compared actual outcome against demo persona registry.",
                        decision=(
                            "Verification matched expected outcome."
                            if verification["match"]
                            else "Verification mismatch detected."
                        ),
                        next_action="end",
                        metadata=verification,
                    )
                )

            return AgentRunResult(
                agent_goal=goal,
                planner_mode=self.planner_mode,
                base_plan=[asdict(step) for step in base_plan],
                execution_trace=[asdict(item) for item in execution_trace],
                llm_decisions=llm_decisions,
                model_used=self._model_used(),
                final_status=actual_outcome,
                verification=verification,
                result={
                    "loaded_customer": self._loaded_customer_result(loaded_customer),
                    "data_check": data_check_result.model_dump(mode="json"),
                    "facts": [],
                    "policy": {
                        "accepted_count": 0,
                        "rejected_count": 0,
                        "rejection_rules": [],
                        "rejection_reasons": [],
                        "decisions": [],
                    },
                },
            )

        facts = generate_facts(
            customer_data=customer_profile_model,
            available_features=loaded_customer["available_features"],
        )

        facts_count = len(facts)

        execution_trace.append(
            AgentTraceItem(
                step_id="detect_facts",
                tool="fact_pattern_engine",
                status="completed",
                summary=f"Detected {facts_count} evidence-backed fact(s).",
                decision=(
                    "Continue to policy evaluation."
                    if facts_count > 0
                    else "No facts detected. Stop before policy and output generation."
                ),
                next_action=(
                    "evaluate_policy"
                    if facts_count > 0
                    else "write_audit"
                ),
                metadata={
                    "facts_count": facts_count,
                    "fact_types": [
                        (fact.get("fact_type") if isinstance(fact, dict) else getattr(fact, "fact_type", None)) or
                        (fact.get("type") if isinstance(fact, dict) else getattr(fact, "type", None))
                        for fact in facts
                    ],
                },
            )
        )

        if facts_count == 0:
            actual_outcome = "no_facts"

            execution_trace.append(
                AgentTraceItem(
                    step_id="write_audit",
                    tool="audit_logger",
                    status="completed",
                    summary="No facts were detected from available data.",
                    decision="Finalize run and record no facts in audit log.",
                    next_action="finalize",
                    metadata={
                        "reason": "no_detected_facts",
                    },
                )
            )

            execution_trace.append(
                AgentTraceItem(
                    step_id="finalize",
                    tool="agent_core",
                    status="completed",
                    summary=f"Run finalized with status {actual_outcome}.",
                    decision="Finalize agent run.",
                    next_action="verify_against_persona_registry" if enable_test_verification else "end",
                )
            )

            verification = {
                "enabled": False,
                "expected_outcome": None,
                "actual_outcome": actual_outcome,
                "match": None,
            }
            if enable_test_verification:
                verification = verify_against_persona_registry(customer_key, actual_outcome)
                execution_trace.append(
                    AgentTraceItem(
                        step_id="verify_against_persona_registry",
                        tool="persona_verification",
                        status="completed",
                        summary="Compared actual outcome against demo persona registry.",
                        decision=(
                            "Verification matched expected outcome."
                            if verification["match"]
                            else "Verification mismatch detected."
                        ),
                        next_action="end",
                        metadata=verification,
                    )
                )

            return AgentRunResult(
                agent_goal=goal,
                planner_mode=self.planner_mode,
                base_plan=[asdict(step) for step in base_plan],
                execution_trace=[asdict(item) for item in execution_trace],
                llm_decisions=llm_decisions,
                model_used=self._model_used(),
                final_status=actual_outcome,
                verification=verification,
                result={
                    "loaded_customer": self._loaded_customer_result(loaded_customer),
                    "data_check": data_check_result.model_dump(mode="json"),
                    "facts": [],
                    "policy": {
                        "accepted_count": 0,
                        "rejected_count": 0,
                        "rejection_rules": [],
                        "rejection_reasons": [],
                        "decisions": [],
                    },
                },
            )

        policy_results = evaluate_policies(
            facts=facts,
            customer=customer_profile_model,
        )

        accepted_policy_results = [
            result for result in policy_results
            if getattr(result, "decision", None) == "accepted"
            or getattr(result, "policy_result", None) == "accepted"
            or getattr(result, "allowed", False) is True
        ]

        rejected_policy_results = [
            result for result in policy_results
            if result not in accepted_policy_results
        ]

        accepted_count = len(accepted_policy_results)
        rejected_count = len(rejected_policy_results)

        rejection_rules = []
        rejection_reasons = []
        for result in rejected_policy_results:
            rules = getattr(result, "rule_ids_triggered", None) or getattr(result, "rule_id", None)
            if isinstance(rules, list):
                rejection_rules.extend(rules)
            elif rules:
                rejection_rules.append(rules)

            reasons = getattr(result, "reasons", None) or getattr(result, "reason", None)
            if isinstance(reasons, list):
                rejection_reasons.extend(reasons)
            elif reasons:
                rejection_reasons.append(reasons)

        execution_trace.append(
            AgentTraceItem(
                step_id="evaluate_policy",
                tool="policy_engine",
                status="completed",
                summary=f"Policy accepted {accepted_count} candidate(s), rejected {rejected_count} candidate(s).",
                decision=(
                    "Continue to LLM action selection for approved candidates."
                    if accepted_count > 0
                    else "All candidates rejected by policy. Skip output and challenge generation."
                ),
                next_action=(
                    "select_next_action_after_policy"
                    if accepted_count > 0
                    else "write_audit"
                ),
                metadata={
                    "accepted_count": accepted_count,
                    "rejected_count": rejected_count,
                    "rejection_rules": sorted(list(set(rejection_rules))),
                    "rejection_reasons": sorted(list(set(rejection_reasons))),
                },
            )
        )

        if accepted_count == 0:
            actual_outcome = "rejected_by_policy"

            execution_trace.append(
                AgentTraceItem(
                    step_id="write_audit",
                    tool="audit_logger",
                    status="completed",
                    summary="All candidates were rejected by policy.",
                    decision="Finalize run and record policy rejection in audit log.",
                    next_action="finalize",
                    metadata={
                        "rejection_rules": sorted(list(set(rejection_rules))),
                        "rejection_reasons": sorted(list(set(rejection_reasons))),
                    },
                )
            )

            execution_trace.append(
                AgentTraceItem(
                    step_id="finalize",
                    tool="agent_core",
                    status="completed",
                    summary=f"Run finalized with status {actual_outcome}.",
                    decision="Finalize agent run.",
                    next_action="verify_against_persona_registry" if enable_test_verification else "end",
                )
            )

            verification = {
                "enabled": False,
                "expected_outcome": None,
                "actual_outcome": actual_outcome,
                "match": None,
            }
            if enable_test_verification:
                verification = verify_against_persona_registry(customer_key, actual_outcome)
                execution_trace.append(
                    AgentTraceItem(
                        step_id="verify_against_persona_registry",
                        tool="persona_verification",
                        status="completed",
                        summary="Compared actual outcome against demo persona registry.",
                        decision=(
                            "Verification matched expected outcome."
                            if verification["match"]
                            else "Verification mismatch detected."
                        ),
                        next_action="end",
                        metadata=verification,
                    )
                )

            return AgentRunResult(
                agent_goal=goal,
                planner_mode=self.planner_mode,
                base_plan=[asdict(step) for step in base_plan],
                execution_trace=[asdict(item) for item in execution_trace],
                llm_decisions=llm_decisions,
                model_used=self._model_used(),
                final_status=actual_outcome,
                verification=verification,
                result={
                    "loaded_customer": self._loaded_customer_result(loaded_customer),
                    "data_check": data_check_result.model_dump(mode="json"),
                    "facts": [
                        fact.model_dump(mode="json") if hasattr(fact, "model_dump") else fact
                        for fact in facts
                    ],
                    "policy": {
                        "accepted_count": accepted_count,
                        "rejected_count": rejected_count,
                        "rejection_rules": sorted(list(set(rejection_rules))),
                        "rejection_reasons": sorted(list(set(rejection_reasons))),
                        "decisions": [
                            dec.model_dump(mode="json") if hasattr(dec, "model_dump") else dec
                            for dec in policy_results
                        ],
                    },
                },
            )

        # =====================================================
        # Step 7: LLM Action Selector after policy acceptance
        # =====================================================

        candidate_actions = [
            "generate_non_advisory_wording",
            "write_audit_without_user_output",
        ]

        constraints = [
            "Only select actions from candidate_actions.",
            "Only generate wording for policy-approved facts.",
            "Do not generate a challenge before Safety Gate 1 passes.",
            "Do not provide personalized financial advice.",
            "Policy and Safety gates cannot be bypassed.",
        ]

        llm_action_result = self.llm_client.select_action(
            goal=goal,
            current_state={
                "stage": "policy_evaluated",
                "customer_key": customer_key,
                "facts_count": facts_count,
                "accepted_policy_count": accepted_count,
                "rejected_policy_count": rejected_count,
                "rejection_rules": sorted(list(set(rejection_rules))),
            },
            candidate_actions=candidate_actions,
            constraints=constraints,
        )

        selected_action = None
        llm_reason = None

        if llm_action_result.parsed_json:
            selected_action = llm_action_result.parsed_json.get("selected_action")
            llm_reason = llm_action_result.parsed_json.get("reason")

        is_valid_llm_action = selected_action in candidate_actions

        llm_decisions.append(
            {
                "purpose": llm_action_result.purpose,
                "provider": llm_action_result.provider,
                "model_name": llm_action_result.model_name,
                "prompt_version": llm_action_result.prompt_version,
                "llm_used": llm_action_result.llm_used,
                "candidate_actions": candidate_actions,
                "selected_action": selected_action,
                "valid": is_valid_llm_action,
                "reason": llm_reason,
            }
        )

        execution_trace.append(
            AgentTraceItem(
                step_id="select_next_action_after_policy",
                tool="llm_action_selector",
                status="completed" if is_valid_llm_action else "failed",
                summary=f"LLM selected action: {selected_action}",
                decision=(
                    llm_reason
                    if is_valid_llm_action
                    else "LLM selected an invalid action. Falling back to audit-only safe path."
                ),
                next_action=(
                    selected_action
                    if is_valid_llm_action
                    else "write_audit"
                ),
                metadata={
                    "candidate_actions": candidate_actions,
                    "selected_action": selected_action,
                    "valid": is_valid_llm_action,
                    "provider": llm_action_result.provider,
                    "model_name": llm_action_result.model_name,
                    "prompt_version": llm_action_result.prompt_version,
                    "llm_used": llm_action_result.llm_used,
                },
            )
        )

        if not is_valid_llm_action:
            actual_outcome = "failed"

            execution_trace.append(
                AgentTraceItem(
                    step_id="write_audit",
                    tool="audit_logger",
                    status="completed",
                    summary="Invalid LLM action was blocked by the agent validator.",
                    decision="Finalize as failed because the LLM selected an action outside the governed candidate list.",
                    next_action="finalize",
                    metadata={
                        "selected_action": selected_action,
                        "candidate_actions": candidate_actions,
                    },
                )
            )

            execution_trace.append(
                AgentTraceItem(
                    step_id="finalize",
                    tool="agent_core",
                    status="completed",
                    summary=f"Agent finalized with status: {actual_outcome}.",
                    decision="Finalize agent run.",
                    next_action="verify_against_persona_registry" if enable_test_verification else "end",
                )
            )

            verification = {
                "enabled": False,
                "expected_outcome": None,
                "actual_outcome": actual_outcome,
                "match": None,
            }
            if enable_test_verification:
                verification = verify_against_persona_registry(customer_key, actual_outcome)
                execution_trace.append(
                    AgentTraceItem(
                        step_id="verify_against_persona_registry",
                        tool="persona_verification",
                        status="completed",
                        summary="Compared actual outcome against demo persona registry.",
                        decision=(
                            "Verification matched expected outcome."
                            if verification["match"]
                            else "Verification mismatch detected."
                        ),
                        next_action="end",
                        metadata=verification,
                    )
                )

            return AgentRunResult(
                agent_goal=goal,
                planner_mode=self.planner_mode,
                base_plan=[asdict(step) for step in base_plan],
                execution_trace=[asdict(item) for item in execution_trace],
                llm_decisions=llm_decisions,
                model_used=self._model_used(),
                final_status=actual_outcome,
                verification=verification,
                result={
                    "loaded_customer": self._loaded_customer_result(loaded_customer),
                    "data_check": data_check_result.model_dump(mode="json"),
                    "facts": [
                        fact.model_dump(mode="json") if hasattr(fact, "model_dump") else fact
                        for fact in facts
                    ],
                    "policy": {
                        "accepted_count": accepted_count,
                        "rejected_count": rejected_count,
                        "rejection_rules": sorted(list(set(rejection_rules))),
                        "rejection_reasons": sorted(list(set(rejection_reasons))),
                    },
                    "llm_action": {
                        "candidate_actions": candidate_actions,
                        "selected_action": selected_action,
                        "valid": is_valid_llm_action,
                    },
                },
            )

        if selected_action == "write_audit_without_user_output":
            actual_outcome = "partial"

            execution_trace.append(
                AgentTraceItem(
                    step_id="write_audit",
                    tool="audit_logger",
                    status="completed",
                    summary="LLM selected audit-only path after policy acceptance.",
                    decision="Finalize as partial because no user-facing wording was generated.",
                    next_action="finalize",
                    metadata={
                        "reason": llm_reason,
                    },
                )
            )

            execution_trace.append(
                AgentTraceItem(
                    step_id="finalize",
                    tool="agent_core",
                    status="completed",
                    summary=f"Agent finalized with status: {actual_outcome}.",
                    decision="Finalize agent run.",
                    next_action="verify_against_persona_registry" if enable_test_verification else "end",
                )
            )

            verification = {
                "enabled": False,
                "expected_outcome": None,
                "actual_outcome": actual_outcome,
                "match": None,
            }
            if enable_test_verification:
                verification = verify_against_persona_registry(customer_key, actual_outcome)
                execution_trace.append(
                    AgentTraceItem(
                        step_id="verify_against_persona_registry",
                        tool="persona_verification",
                        status="completed",
                        summary="Compared actual outcome against demo persona registry.",
                        decision=(
                            "Verification matched expected outcome."
                            if verification["match"]
                            else "Verification mismatch detected."
                        ),
                        next_action="end",
                        metadata=verification,
                    )
                )

            return AgentRunResult(
                agent_goal=goal,
                planner_mode=self.planner_mode,
                base_plan=[asdict(step) for step in base_plan],
                execution_trace=[asdict(item) for item in execution_trace],
                llm_decisions=llm_decisions,
                model_used=self._model_used(),
                final_status=actual_outcome,
                verification=verification,
                result={
                    "loaded_customer": self._loaded_customer_result(loaded_customer),
                    "data_check": data_check_result.model_dump(mode="json"),
                    "facts": [
                        fact.model_dump(mode="json") if hasattr(fact, "model_dump") else fact
                        for fact in facts
                    ],
                    "policy": {
                        "accepted_count": accepted_count,
                        "rejected_count": rejected_count,
                        "rejection_rules": sorted(list(set(rejection_rules))),
                        "rejection_reasons": sorted(list(set(rejection_reasons))),
                    },
                    "llm_action": {
                        "candidate_actions": candidate_actions,
                        "selected_action": selected_action,
                        "valid": is_valid_llm_action,
                        "reason": llm_reason,
                    },
                },
            )

        # =====================================================
        # Step 8: LLM Wording Generator
        # =====================================================

        generated_outputs = []

        if selected_action == "generate_non_advisory_wording":
            for fact, policy_result in zip(facts, accepted_policy_results):
                fact_payload = (
                    fact.model_dump(mode="json")
                    if hasattr(fact, "model_dump")
                    else fact
                )

                policy_payload = (
                    policy_result.model_dump(mode="json")
                    if hasattr(policy_result, "model_dump")
                    else policy_result
                )

                llm_wording_result = self.llm_client.generate_non_advisory_output(
                    fact=fact_payload,
                    policy_result=policy_payload,
                    product_context={},
                    previous_violations=[],
                )

                observation = None
                nudge = None

                if llm_wording_result.parsed_json:
                    observation = llm_wording_result.parsed_json.get("observation")
                    nudge = llm_wording_result.parsed_json.get("nudge")

                generated_outputs.append(
                    {
                        "fact": fact_payload,
                        "policy_result": policy_payload,
                        "observation": observation,
                        "nudge": nudge,
                        "llm": {
                            "purpose": llm_wording_result.purpose,
                            "provider": llm_wording_result.provider,
                            "model_name": llm_wording_result.model_name,
                            "prompt_version": llm_wording_result.prompt_version,
                            "llm_used": llm_wording_result.llm_used,
                        },
                    }
                )

            execution_trace.append(
                AgentTraceItem(
                    step_id="generate_wording",
                    tool="llm_wording_generator",
                    status="completed",
                    summary=f"Generated wording for {len(generated_outputs)} policy-approved candidate(s).",
                    decision="Continue to Safety Gate 1 before any user-facing output is published.",
                    next_action="safety_check",
                    metadata={
                        "generated_count": len(generated_outputs),
                        "provider": self.llm_client.provider,
                        "model_name": self.llm_client.model_name,
                        "prompt_version": self.llm_client.prompt_version,
                        "llm_used": self.llm_client.provider != "mock",
                    },
                )
            )

        # =====================================================
        # Step 9: Safety Gate 1 & Safety Rewrite Retry Loop
        # =====================================================

        safety_passed_outputs = []
        safety_failed_outputs = []
        safety_retry_attempts = []

        if selected_action == "generate_non_advisory_wording":
            for out in generated_outputs:
                fact_id = out["fact"].get("fact_id", "unknown_fact")
                obs_res = validate_observation(fact_id, out["observation"] or "")
                nudge_res = validate_nudge(fact_id, out["nudge"] or "")

                passed = obs_res.passed and nudge_res.passed
                violations = []
                if not obs_res.passed:
                    violations.extend(obs_res.violations)
                if not nudge_res.passed:
                    violations.extend(nudge_res.violations)

                if passed:
                    safety_passed_outputs.append(out)
                else:
                    # Unsafe wording: Trigger Safety Rewrite Retry
                    rewrite_result = self.llm_client.rewrite_after_safety_failure(
                        unsafe_observation=out["observation"] or "",
                        unsafe_nudge=out["nudge"] or "",
                        safety_violations=violations,
                        fact=out["fact"],
                        policy_result=out["policy_result"],
                    )

                    attempt_record = {
                        "attempt": 1,
                        "original_observation": out["observation"] or "",
                        "original_nudge": out["nudge"] or "",
                        "rewritten_observation": rewrite_result.parsed_json.get("observation") if rewrite_result.parsed_json else "",
                        "rewritten_nudge": rewrite_result.parsed_json.get("nudge") if rewrite_result.parsed_json else "",
                        "safety_violations": violations,
                        "llm": {
                            "provider": rewrite_result.provider,
                            "model_name": rewrite_result.model_name,
                            "prompt_version": rewrite_result.prompt_version,
                            "llm_used": rewrite_result.llm_used,
                            "purpose": rewrite_result.purpose,
                        },
                        "status": "failed",
                    }
                    safety_retry_attempts.append(attempt_record)

                    # Validate the rewritten observation & nudge
                    rewritten_obs = attempt_record["rewritten_observation"]
                    rewritten_ndg = attempt_record["rewritten_nudge"]

                    obs_res_retry = validate_observation(fact_id, rewritten_obs)
                    nudge_res_retry = validate_nudge(fact_id, rewritten_ndg)

                    passed_retry = obs_res_retry.passed and nudge_res_retry.passed
                    violations_retry = []
                    if not obs_res_retry.passed:
                        violations_retry.extend(obs_res_retry.violations)
                    if not nudge_res_retry.passed:
                        violations_retry.extend(nudge_res_retry.violations)

                    if passed_retry:
                        attempt_record["status"] = "recovered"
                        recovered_out = {
                            "fact": out["fact"],
                            "policy_result": out["policy_result"],
                            "observation": rewritten_obs,
                            "nudge": rewritten_ndg,
                            "llm": attempt_record["llm"],
                        }
                        safety_passed_outputs.append(recovered_out)
                    else:
                        attempt_record["status"] = "failed"
                        failed_item = {
                            "fact": out["fact"],
                            "policy_result": out["policy_result"],
                            "observation": rewritten_obs,
                            "nudge": rewritten_ndg,
                            "llm": attempt_record["llm"],
                            "safety_violations": violations_retry,
                        }
                        safety_failed_outputs.append(failed_item)

            passed_count = len(safety_passed_outputs)
            failed_count = len(safety_failed_outputs)
            any_failed = failed_count > 0

            execution_trace.append(
                AgentTraceItem(
                    step_id="safety_check",
                    tool="safety_engine",
                    status="completed",
                    summary=f"Safety checked {len(generated_outputs)} generated output(s): {passed_count} passed, {failed_count} failed.",
                    decision=(
                        "Continue to engagement generation."
                        if not any_failed
                        else "Unsafe generated wording detected. Block user-facing output."
                    ),
                    next_action=(
                        "generate_challenge"
                        if not any_failed
                        else "write_audit"
                    ),
                    metadata={
                        "checked_count": len(generated_outputs),
                        "passed_count": passed_count,
                        "failed_count": failed_count,
                    },
                )
            )

            # Record retry execution trace item if rewrite happened
            if len(safety_retry_attempts) > 0:
                any_retry_failed = any(att["status"] == "failed" for att in safety_retry_attempts)
                retry_summary = f"Attempted safety rewrite for {len(safety_retry_attempts)} unsafe generated output(s)."
                retry_decision = (
                    "Unsafe wording was rewritten and passed Safety Gate."
                    if not any_retry_failed
                    else "Safety rewrite failed; block user-facing output."
                )
                retry_next_action = "generate_challenge" if not any_retry_failed else "write_audit"

                execution_trace.append(
                    AgentTraceItem(
                        step_id="safety_rewrite_retry",
                        tool="llm_safety_rewriter",
                        status="completed",
                        summary=retry_summary,
                        decision=retry_decision,
                        next_action=retry_next_action,
                        metadata={
                            "retry_attempts": safety_retry_attempts,
                        },
                    )
                )

            if any_failed:
                actual_outcome = "blocked_by_safety"

                execution_trace.append(
                    AgentTraceItem(
                        step_id="write_audit",
                        tool="audit_logger",
                        status="completed",
                        summary="Unsafe output detected. Blocking publication.",
                        decision="Finalize as blocked_by_safety and skip challenge steps.",
                        next_action="finalize",
                        metadata={
                            "reason": "safety_gate_violation",
                            "failed_outputs": safety_failed_outputs,
                        },
                    )
                )

                execution_trace.append(
                    AgentTraceItem(
                        step_id="finalize",
                        tool="agent_core",
                        status="completed",
                        summary=f"Agent finalized with status: {actual_outcome}.",
                        decision="Finalize agent run.",
                        next_action="verify_against_persona_registry" if enable_test_verification else "end",
                    )
                )

                verification = {
                    "enabled": False,
                    "expected_outcome": None,
                    "actual_outcome": actual_outcome,
                    "match": None,
                }
                if enable_test_verification:
                    verification = verify_against_persona_registry(customer_key, actual_outcome)
                    execution_trace.append(
                        AgentTraceItem(
                            step_id="verify_against_persona_registry",
                            tool="persona_verification",
                            status="completed",
                            summary="Compared actual outcome against demo persona registry.",
                            decision=(
                                "Verification matched expected outcome."
                                if verification["match"]
                                else "Verification mismatch detected."
                            ),
                            next_action="end",
                            metadata=verification,
                        )
                    )

                return AgentRunResult(
                    agent_goal=goal,
                    planner_mode=self.planner_mode,
                    base_plan=[asdict(step) for step in base_plan],
                    execution_trace=[asdict(item) for item in execution_trace],
                    llm_decisions=llm_decisions,
                    model_used=self._model_used(),
                    final_status=actual_outcome,
                    verification=verification,
                    result={
                        "loaded_customer": self._loaded_customer_result(loaded_customer),
                        "data_check": data_check_result.model_dump(mode="json"),
                        "facts": [
                            fact.model_dump(mode="json") if hasattr(fact, "model_dump") else fact
                            for fact in facts
                        ],
                        "policy": {
                            "accepted_count": accepted_count,
                            "rejected_count": rejected_count,
                            "rejection_rules": sorted(list(set(rejection_rules))),
                            "rejection_reasons": sorted(list(set(rejection_reasons))),
                            "decisions": [
                                dec.model_dump(mode="json") if hasattr(dec, "model_dump") else dec
                                for dec in policy_results
                            ],
                        },
                        "llm_action": {
                            "candidate_actions": candidate_actions,
                            "selected_action": selected_action,
                            "valid": is_valid_llm_action,
                            "reason": llm_reason,
                        },
                        "generated_outputs": generated_outputs,
                        "safety_retry_attempts": safety_retry_attempts,
                        "safety_passed_outputs": safety_passed_outputs,
                        "safety_failed_outputs": safety_failed_outputs,
                    },
                )

        # =====================================================
        # Step 10: Engagement Engine / Challenge Generation
        # =====================================================

        challenges_outputs = []

        if selected_action == "generate_non_advisory_wording":
            outputs_for_engagement = []
            for out in safety_passed_outputs:
                fact_payload = out["fact"]
                fact_id = fact_payload.get("fact_id", "unknown_fact")
                
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

                nudge_obj = Nudge(
                    nudge_id=f"nudge_{fact_id}",
                    customer_id=customer_key,
                    observation_id=f"obs_{fact_id}",
                    related_product_id=related_product_id,
                    related_feature=related_feature,
                    nudge_type=nudge_type,
                    text=out["nudge"] or "",
                    passed_safety_check=True,
                    safety_notes="Passed safety check.",
                )

                outputs_for_engagement.append({
                    "nudge": nudge_obj,
                    "fact": fact_payload,
                    "policy_result": out["policy_result"],
                    "observation": out["observation"],
                })

            challenges_raw = generate_challenges(
                outputs=outputs_for_engagement,
                customer=customer_profile_model,
            )

            # Safety Gate 2 check for challenges and build outputs
            any_challenge_failed_safety = False
            for item in challenges_raw:
                chal = item.get("challenge")
                if chal and not chal.passed_safety_check:
                    any_challenge_failed_safety = True

                chal_dict = None
                if chal:
                    chal_dict = chal.model_dump(mode="json") if hasattr(chal, "model_dump") else chal

                challenges_outputs.append({
                    "fact": item.get("fact"),
                    "policy_result": item.get("policy_result"),
                    "observation": item.get("observation"),
                    "nudge": item.get("nudge").text if hasattr(item.get("nudge"), "text") else item.get("nudge"),
                    "challenge": chal_dict,
                    "challenge_safety_title": item.get("challenge_safety_title").model_dump(mode="json") if hasattr(item.get("challenge_safety_title"), "model_dump") else item.get("challenge_safety_title"),
                    "challenge_safety_desc": item.get("challenge_safety_desc").model_dump(mode="json") if hasattr(item.get("challenge_safety_desc"), "model_dump") else item.get("challenge_safety_desc"),
                    "challenge_safety_criteria": item.get("challenge_safety_criteria").model_dump(mode="json") if hasattr(item.get("challenge_safety_criteria"), "model_dump") else item.get("challenge_safety_criteria"),
                })

            if any_challenge_failed_safety:
                actual_outcome = "blocked_by_safety"
                execution_trace.append(
                    AgentTraceItem(
                        step_id="generate_challenges",
                        tool="engagement_engine",
                        status="failed",
                        summary="Unsafe engagement challenge(s) detected. Blocking publication.",
                        decision="Finalize as blocked_by_safety due to Safety Gate 2 violation.",
                        next_action="write_audit",
                        metadata={
                            "challenges_count": len(challenges_outputs),
                            "safety_gate_2_passed": False,
                        },
                    )
                )
            else:
                actual_outcome = "published"
                execution_trace.append(
                    AgentTraceItem(
                        step_id="generate_challenges",
                        tool="engagement_engine",
                        status="completed",
                        summary=f"Generated {len(challenges_outputs)} challenge(s) for the passed nudges.",
                        decision="Publish all safe observations, nudges, and adaptive challenges.",
                        next_action="write_audit",
                        metadata={
                            "challenges_count": len(challenges_outputs),
                            "safety_gate_2_passed": True,
                        },
                    )
                )
        else:
            actual_outcome = "published"

        execution_trace.append(
            AgentTraceItem(
                step_id="write_audit",
                tool="audit_logger",
                status="completed",
                summary="Agent finalized the audit logging steps.",
                decision="Publish safe content or log blocks accordingly.",
                next_action="finalize",
                metadata={
                    "status": actual_outcome,
                },
            )
        )

        execution_trace.append(
            AgentTraceItem(
                step_id="finalize",
                tool="agent_core",
                status="completed",
                summary=f"Agent finalized with status: {actual_outcome}.",
                decision="Finalize agent run.",
                next_action="verify_against_persona_registry" if enable_test_verification else "end",
            )
        )

        verification = {
            "enabled": False,
            "expected_outcome": None,
            "actual_outcome": actual_outcome,
            "match": None,
        }
        if enable_test_verification:
            verification = verify_against_persona_registry(customer_key, actual_outcome)
            execution_trace.append(
                AgentTraceItem(
                    step_id="verify_against_persona_registry",
                    tool="persona_verification",
                    status="completed",
                    summary="Compared actual outcome against demo persona registry.",
                    decision=(
                        "Verification matched expected outcome."
                        if verification["match"]
                        else "Verification mismatch detected."
                    ),
                    next_action="end",
                    metadata=verification,
                )
            )

        model_used = self._model_used()
        trace_list = [asdict(item) for item in execution_trace]
        outputs_for_audit = []
        for out in challenges_outputs:
            fact_payload = out.get("fact") or {}
            fact_id = fact_payload.get("fact_id")
            if not fact_id:
                continue
            challenge = out.get("challenge") or {}
            outputs_for_audit.append({
                "fact_id": fact_id,
                "candidate_id": fact_id,
                "observation": {"text": out.get("observation")},
                "nudge": {"text": out.get("nudge")},
                "observation_safety": {"passed": True, "violations": []},
                "nudge_safety": {"passed": True, "violations": []},
                "challenge": {
                    "title": challenge.get("title"),
                    "description": challenge.get("description"),
                    "criteria": challenge.get("criteria"),
                    "passed_safety_check": challenge.get("passed_safety_check"),
                } if challenge else None,
                "challenge_safety_title": out.get("challenge_safety_title"),
                "challenge_safety_desc": out.get("challenge_safety_desc"),
                "challenge_safety_criteria": out.get("challenge_safety_criteria"),
            })
        for out in safety_failed_outputs:
            fact_payload = out.get("fact") or {}
            fact_id = fact_payload.get("fact_id")
            if not fact_id:
                continue
            outputs_for_audit.append({
                "fact_id": fact_id,
                "candidate_id": fact_id,
                "observation": {"text": out.get("observation")},
                "nudge": {"text": out.get("nudge")},
                "observation_safety": {"passed": False, "violations": out.get("safety_violations", [])},
                "nudge_safety": {"passed": False, "violations": out.get("safety_violations", [])},
                "challenge": None,
            })
        persistence_info = self._persist_run(
            customer_key=customer_key,
            loaded_customer=loaded_customer,
            actual_outcome=actual_outcome,
            model_used=model_used,
            execution_trace=execution_trace,
            llm_decisions=llm_decisions,
            facts=facts,
            policy_results=policy_results,
            outputs_for_audit=outputs_for_audit,
            safety_retry_attempts=safety_retry_attempts,
            verification=verification,
        )

        return AgentRunResult(
            agent_goal=goal,
            planner_mode=self.planner_mode,
            base_plan=[asdict(step) for step in base_plan],
            execution_trace=trace_list,
            llm_decisions=llm_decisions,
            model_used=model_used,
            final_status=actual_outcome,
            verification=verification,
            result={
                "loaded_customer": self._loaded_customer_result(loaded_customer),
                "data_check": data_check_result.model_dump(mode="json"),
                "facts": [
                    fact.model_dump(mode="json") if hasattr(fact, "model_dump") else fact
                    for fact in facts
                ],
                "policy": {
                    "accepted_count": accepted_count,
                    "rejected_count": rejected_count,
                    "rejection_rules": sorted(list(set(rejection_rules))),
                    "rejection_reasons": sorted(list(set(rejection_reasons))),
                    "decisions": [
                        dec.model_dump(mode="json") if hasattr(dec, "model_dump") else dec
                        for dec in policy_results
                    ],
                },
                "llm_action": {
                    "candidate_actions": candidate_actions,
                    "selected_action": selected_action,
                    "valid": is_valid_llm_action,
                    "reason": llm_reason,
                },
                "generated_outputs": generated_outputs,
                "safety_retry_attempts": safety_retry_attempts,
                "safety_passed_outputs": safety_passed_outputs,
                "safety_failed_outputs": safety_failed_outputs,
                "challenges": challenges_outputs,
                "persistence": persistence_info,
            },
        )

