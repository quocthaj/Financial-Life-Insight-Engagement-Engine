from typing import Any, Dict, List

from app.models.schemas import PolicyDecision
from app.data.product_catalog import get_product


def _get(obj: Any, key: str):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key)


def _is_age_band_adult(age_band: str) -> bool:
    return age_band not in ["under_18"]


def evaluate_policy_for_fact(fact: Dict[str, Any], customer: Any) -> PolicyDecision:
    """
    MVP Policy Engine.

    This engine does NOT decide whether the customer should use a product.
    It only decides whether the system is allowed to show a nudge/reminder
    derived from this fact.
    """
    profile = _get(customer, "profile")
    fact_id = fact["fact_id"]
    customer_id = fact["customer_id"]
    fact_type = fact["fact_type"]

    triggered: List[str] = []
    reasons: List[str] = []

    # Global rule: user consent / opt-out
    if _get(profile, "opted_out_of_education_nudges"):
        triggered.append("global_user_opted_out")
        reasons.append("Customer opted out of education nudges.")
        return PolicyDecision(
            candidate_id=fact_id,
            customer_id=customer_id,
            decision="rejected",
            rule_ids_triggered=triggered,
            reasons=reasons,
        )

    # Global rule: KYC
    if not _get(profile, "kyc_completed"):
        triggered.append("global_kyc_not_completed")
        reasons.append("Customer has not completed KYC.")
        return PolicyDecision(
            candidate_id=fact_id,
            customer_id=customer_id,
            decision="rejected",
            rule_ids_triggered=triggered,
            reasons=reasons,
        )

    # Global rule: adult age band
    if not _is_age_band_adult(_get(profile, "age_band")):
        triggered.append("global_age_band_not_eligible")
        reasons.append("Customer age band is not eligible for product nudges.")
        return PolicyDecision(
            candidate_id=fact_id,
            customer_id=customer_id,
            decision="rejected",
            rule_ids_triggered=triggered,
            reasons=reasons,
        )

    # Spending awareness is generally safe because it only points to review tools.
    if fact_type == "spending_spike":
        triggered.append("allow_spending_awareness")
        reasons.append("Spending pattern can be shown as an educational observation.")
        return PolicyDecision(
            candidate_id=fact_id,
            customer_id=customer_id,
            decision="accepted",
            rule_ids_triggered=triggered,
            reasons=reasons,
        )

    # Due reminder is allowed if it is neutral and does not shame or advise.
    if fact_type == "upcoming_due_reminder":
        triggered.append("allow_neutral_due_reminder")
        reasons.append("Upcoming due reminder is factual and time-based.")
        return PolicyDecision(
            candidate_id=fact_id,
            customer_id=customer_id,
            decision="accepted",
            rule_ids_triggered=triggered,
            reasons=reasons,
        )

    # Dormant feature is only allowed when the fact has app-usage evidence.
    if fact_type == "dormant_feature":
        scope = fact.get("scope", {})
        feature_id = scope.get("feature_id")
        has_app_usage_evidence = "last_feature_view_timestamp" in scope

        # Single source of truth lookup
        product = get_product(feature_id) if feature_id else None

        if not has_app_usage_evidence:
            triggered.append("reject_missing_app_usage_evidence")
            reasons.append("Dormant feature nudge requires explicit app-usage evidence.")
            decision = "rejected"
        elif product is None:
            triggered.append("reject_unknown_product")
            reasons.append(f"Product '{feature_id}' is not in the product catalog.")
            decision = "rejected"
        elif feature_id == "invest_gold":
            # NOTE: For MVP compliance, we explicitly approve Gold Savings education.
            # Other dormant features (like invest_crypto, invest_stocks) are available in catalog
            # but rejected by policy rules in this MVP release to keep the focus tight.
            triggered.append("allow_gold_savings_education")
            reasons.append(f"{product['product_name']} education nudge allowed because customer viewed the feature and did not opt out.")
            decision = "accepted"
        else:
            triggered.append("reject_unapproved_investment_feature")
            reasons.append(f"Product '{product['product_name']}' is in catalog but currently blocked by policy rules for this MVP release.")
            decision = "rejected"

        return PolicyDecision(
            candidate_id=fact_id,
            customer_id=customer_id,
            decision=decision,
            rule_ids_triggered=triggered,
            reasons=reasons,
        )

    # Idle balance is risky if mapped directly to investment/savings product.
    # For MVP, accept only as observation, not as product recommendation.
    if fact_type == "idle_balance":
        triggered.append("allow_idle_balance_observation_only")
        reasons.append("Idle balance may be shown as factual observation only, without product recommendation.")
        return PolicyDecision(
            candidate_id=fact_id,
            customer_id=customer_id,
            decision="accepted",
            rule_ids_triggered=triggered,
            reasons=reasons,
        )

    triggered.append("reject_unknown_fact_type")
    reasons.append(f"No policy rule exists for fact_type={fact_type}.")

    return PolicyDecision(
        candidate_id=fact_id,
        customer_id=customer_id,
        decision="rejected",
        rule_ids_triggered=triggered,
        reasons=reasons,
    )


def evaluate_policies(facts: List[Dict[str, Any]], customer: Any) -> List[PolicyDecision]:
    return [evaluate_policy_for_fact(fact, customer) for fact in facts]
