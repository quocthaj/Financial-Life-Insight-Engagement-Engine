from typing import Any, Dict, List, Optional
from app.models.schemas import Challenge, Nudge
from app.engines.safety_engine import validate_challenge


def _get(obj: Any, key: str):
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key)


def compute_difficulty_tier_and_reward(
    customer: Optional[Any],
    base_difficulty: str,
) -> tuple[str, int]:
    """
    Adapts challenge difficulty and rewards dynamically based on individual customer behavior.
    """
    if not customer:
        # Default fallback if customer profile is not passed
        default_rewards = {"beginner": 50, "intermediate": 100, "power_user": 200}
        return base_difficulty, default_rewards.get(base_difficulty, 50)

    # 1. Behavior assessment
    app_usage_events = getattr(customer, "app_usage", [])
    if not app_usage_events:
        app_usage_events = getattr(customer, "app_usage_events", [])
    
    savings_balances = getattr(customer, "savings", [])
    if not savings_balances:
        savings_balances = getattr(customer, "savings_balances", [])
        
    borrowings = getattr(customer, "borrowings", [])
    
    investment_holdings = getattr(customer, "investments", [])
    if not investment_holdings:
        investment_holdings = getattr(customer, "investment_holdings", [])

    # 2. Compute behavior-only score
    score = 0

    # App activity
    score += min(len(app_usage_events) * 10, 40)

    # Feature usage diversity
    if len(savings_balances) > 0:
        score += 15
    if len(borrowings) > 0:
        score += 15
    if len(investment_holdings) > 0:
        score += 15

    # Product navigation / onboarding evidence
    feature_views = [
        event for event in app_usage_events
        if _get(event, "event_type") in ["feature_view", "feature_use"]
    ]
    score += min(len(feature_views) * 5, 20)

    # Map score to target difficulty
    if score < 40:
        target_difficulty = "beginner"
    elif score < 75:
        target_difficulty = "intermediate"
    else:
        target_difficulty = "power_user"

    # 3. Dynamic adjustment mapping based on base challenge tier
    if base_difficulty == "beginner":
        if target_difficulty == "beginner":
            return "beginner", 50
        elif target_difficulty == "intermediate":
            return "intermediate", 100
        else:
            return "power_user", 200

    elif base_difficulty == "intermediate":
        if target_difficulty == "beginner":
            return "beginner", 75
        elif target_difficulty == "intermediate":
            return "intermediate", 125
        else:
            return "power_user", 250

    else:  # power_user
        if target_difficulty == "beginner":
            return "beginner", 100
        elif target_difficulty == "intermediate":
            return "intermediate", 200
        else:
            return "power_user", 350


def generate_challenge_for_nudge(
    nudge: Nudge,
    customer: Optional[Any] = None,
) -> Optional[Challenge]:
    """
    Generate a single Challenge from a safe Nudge (behavior-adaptive).
    """
    if not nudge.passed_safety_check:
        return None

    customer_id = nudge.customer_id
    nudge_id = nudge.nudge_id
    nudge_type = nudge.nudge_type
    related_feature = nudge.related_feature or "App Features"
    related_product_id = nudge.related_product_id

    challenge_id = f"chal_{nudge_id}"

    title = ""
    description = ""
    target_feature = related_feature
    criteria = ""
    base_difficulty = "beginner"

    if nudge_type == "spending_awareness":
        title = "Explore Spending Patterns"
        description = "Review your Spending Breakdown to compare information about your categories over time."
        criteria = "Open the Spending Breakdown feature"
        base_difficulty = "beginner"
    elif nudge_type == "observation_only":
        title = "Review Savings History"
        description = "Review your savings history to understand how your balance changed across recent snapshots."
        target_feature = "Savings History"
        criteria = "Open savings history view"
        base_difficulty = "beginner"
    elif nudge_type == "educational_exploration":
        title = f"Learn about {related_feature}"
        description = f"Complete a tutorial on {related_feature} to understand product features and risks."
        criteria = f"Complete the introductory guide for {related_feature}"
        base_difficulty = "intermediate"
    elif nudge_type == "neutral_due_reminder":
        title = "Check Repayment Date"
        description = "Review your repayment details on the BNPL dashboard to see the due date and payment information."
        criteria = "Open your BNPL repayment schedule"
        base_difficulty = "beginner"
    else:
        # Default fallback
        title = f"Learn about {related_feature}"
        description = f"Learn about the {related_feature} feature in your app."
        criteria = f"Open the {related_feature} page"
        base_difficulty = "beginner"

    # Adapt difficulty and rewards dynamically based on customer behavior
    difficulty_tier, reward_points = compute_difficulty_tier_and_reward(customer, base_difficulty)

    challenge = Challenge(
        challenge_id=challenge_id,
        customer_id=customer_id,
        based_on_nudge=nudge_id,
        title=title,
        description=description,
        target_feature=target_feature,
        criteria=criteria,
        reward_type="points",
        difficulty_tier=difficulty_tier,
        reward_points=reward_points,
        passed_safety_check=False,
    )

    return challenge


def generate_challenges(
    outputs: List[Dict[str, Any]],
    customer: Optional[Any] = None,
) -> List[Dict[str, Any]]:
    """
    Generate Challenge for each output pair and run Safety Engine Gate 2.
    """
    results = []

    for output in outputs:
        nudge = output.get("nudge")
        if not nudge:
            continue

        challenge = generate_challenge_for_nudge(nudge, customer)
        if challenge:
            # Safety Gate 2
            # Validate challenge title, description, and criteria
            safety_title = validate_challenge(challenge.challenge_id, challenge.title)
            safety_desc = validate_challenge(challenge.challenge_id, challenge.description)
            safety_criteria = validate_challenge(challenge.challenge_id, challenge.criteria)

            challenge.passed_safety_check = (
                safety_title.passed
                and safety_desc.passed
                and safety_criteria.passed
            )
            violations = (
                safety_title.violations
                + safety_desc.violations
                + safety_criteria.violations
            )

            if not challenge.passed_safety_check:
                challenge.safety_notes = f"Safety check failed. Violations: {'; '.join(violations)}"
            else:
                challenge.safety_notes = "Passed safety check."

            # Store the updated output dict with challenge details
            output_with_challenge = dict(output)
            output_with_challenge["challenge"] = challenge
            output_with_challenge["challenge_safety_title"] = safety_title
            output_with_challenge["challenge_safety_desc"] = safety_desc
            output_with_challenge["challenge_safety_criteria"] = safety_criteria
            results.append(output_with_challenge)
        else:
            # Nudge failed safety check or could not generate challenge.
            # Append output with None challenge so that audit logs record the safety block.
            output_no_challenge = dict(output)
            output_no_challenge["challenge"] = None
            results.append(output_no_challenge)

    return results
