from typing import Any, Dict, List, Optional, Tuple

from app.models.schemas import Observation, Nudge, PolicyDecision
from app.engines.safety_engine import validate_observation, validate_nudge


def _get(obj: Any, key: str):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key)


def _find_policy_decision(
    fact_id: str,
    policy_decisions: List[PolicyDecision],
) -> Optional[PolicyDecision]:
    for decision in policy_decisions:
        if decision.candidate_id == fact_id:
            return decision
    return None


def generate_observation_and_nudge(
    fact: Dict[str, Any],
    policy_decision: PolicyDecision,
) -> Tuple[Optional[Observation], Optional[Nudge]]:
    """
    Template-based output generator.

    Đây là bản MVP chưa dùng LLM.
    Chỉ generate output khi Policy Engine đã accepted.

    Lưu ý:
    - Observation: mô tả khách quan
    - Nudge: gợi ý nhẹ, giáo dục, không advice
    """
    fact_id = fact["fact_id"]
    customer_id = fact["customer_id"]
    fact_type = fact["fact_type"]
    value = fact.get("value", {})
    scope = fact.get("scope", {})

    if policy_decision.decision != "accepted":
        return None, None

    observation_id = f"obs_{fact_id}"
    nudge_id = f"nudge_{fact_id}"

    # 1. Spending spike
    if fact_type == "spending_spike":
        category = scope.get("category", "this category")
        latest_month = scope.get("latest_month")
        latest_amount = value.get("latest_amount")
        avg_previous = value.get("avg_previous_months")
        pct_change = value.get("pct_change")

        observation = Observation(
            observation_id=observation_id,
            customer_id=customer_id,
            candidate_id=fact_id,
            based_on_facts=[fact_id],
            text=(
                f"Your {category} spending in {latest_month} was "
                f"{latest_amount:,.0f} PHP, which was {pct_change:.0f}% higher "
                f"than the average of the previous months ({avg_previous:,.0f} PHP)."
            ),
        )

        nudge = Nudge(
            nudge_id=nudge_id,
            customer_id=customer_id,
            observation_id=observation_id,
            related_product_id="spending_breakdown",
            related_feature="Spending Breakdown",
            nudge_type="spending_awareness",
            text=(
                "You can review Spending Breakdown to better understand which "
                "categories changed over time."
            ),
            passed_safety_check=False,
        )

        return observation, nudge

    # 2. Idle balance — observation only, no product recommendation
    if fact_type == "idle_balance":
        latest_balance = value.get("latest_balance")
        fluctuation_pct = value.get("fluctuation_pct")

        balance_text = (
            f"{latest_balance:,.0f} PHP"
            if latest_balance is not None
            else "your recent savings balance"
        )

        observation = Observation(
            observation_id=observation_id,
            customer_id=customer_id,
            candidate_id=fact_id,
            based_on_facts=[fact_id],
            text=(
                f"Your regular savings balance stayed around {balance_text} "
                f"across the recent balance snapshots, with about "
                f"{fluctuation_pct}% fluctuation."
            ),
        )

        nudge = Nudge(
            nudge_id=nudge_id,
            customer_id=customer_id,
            observation_id=observation_id,
            related_product_id=None,
            related_feature=None,
            nudge_type="observation_only",
            text=(
                "You can review your savings history to understand how your "
                "balance has changed over time."
            ),
            passed_safety_check=False,
        )

        return observation, nudge

    # 3. Dormant feature — Gold Savings education only
    if fact_type == "dormant_feature":
        feature_id = scope.get("feature_id")
        feature_name = scope.get("feature_name", "this feature")

        observation = Observation(
            observation_id=observation_id,
            customer_id=customer_id,
            candidate_id=fact_id,
            based_on_facts=[fact_id],
            text=(
                f"You viewed {feature_name}, and the available app-usage metadata "
                f"shows the onboarding was not completed."
            ),
        )

        nudge_text = (
            f"You can revisit the {feature_name} introduction to learn how it "
            f"works, including product details and risks, before deciding "
            f"whether it is relevant to you."
        )
        if customer_id == "cust_00128":  # Dana Lopez - Unsafe forced wording demo
            nudge_text = "You should move 5% of your balance into Gold Savings to maximize return."

        nudge = Nudge(
            nudge_id=nudge_id,
            customer_id=customer_id,
            observation_id=observation_id,
            related_product_id=feature_id,
            related_feature=feature_name,
            nudge_type="educational_exploration",
            text=nudge_text,
            passed_safety_check=False,
        )

        return observation, nudge

    # 4. Upcoming due reminder
    if fact_type == "upcoming_due_reminder":
        loan_type = scope.get("loan_type", "loan")
        next_due_date = scope.get("next_due_date")
        monthly_payment = value.get("monthly_payment")
        days_left = value.get("days_left")

        observation = Observation(
            observation_id=observation_id,
            customer_id=customer_id,
            candidate_id=fact_id,
            based_on_facts=[fact_id],
            text=(
                f"Your {loan_type.upper()} payment of {monthly_payment:,.0f} PHP "
                f"is due on {next_due_date}, which is in {days_left} days."
            ),
        )

        nudge = Nudge(
            nudge_id=nudge_id,
            customer_id=customer_id,
            observation_id=observation_id,
            related_product_id="bnpl",
            related_feature="BNPL",
            nudge_type="neutral_due_reminder",
            text=(
                "You can open the repayment schedule to review the due date "
                "and payment details."
            ),
            passed_safety_check=False,
        )

        return observation, nudge

    return None, None


def generate_outputs(
    facts: List[Dict[str, Any]],
    policy_decisions: List[PolicyDecision],
) -> List[Dict[str, Any]]:
    """
    Generate Observation + Nudge pairs for accepted policy decisions,
    running them through Safety Engine (Gate 1).
    """
    outputs = []

    for fact in facts:
        fact_id = fact["fact_id"]
        decision = _find_policy_decision(fact_id, policy_decisions)

        if decision is None:
            continue

        observation, nudge = generate_observation_and_nudge(fact, decision)

        if observation and nudge:
            # Safety Engine Gate 1
            obs_safety = validate_observation(observation.observation_id, observation.text)
            nudge_safety = validate_nudge(nudge.nudge_id, nudge.text)

            nudge.passed_safety_check = obs_safety.passed and nudge_safety.passed
            
            violations = obs_safety.violations + nudge_safety.violations
            if not nudge.passed_safety_check:
                nudge.safety_notes = f"Safety check failed. Violations: {'; '.join(violations)}"
            else:
                nudge.safety_notes = "Passed safety check."

            outputs.append({
                "fact_id": fact_id,
                "policy_decision": decision,
                "observation": observation,
                "nudge": nudge,
                "observation_safety": obs_safety,
                "nudge_safety": nudge_safety,
            })

    return outputs
