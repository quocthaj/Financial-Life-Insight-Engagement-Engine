"""
Fact Engine — Step 1 in the pipeline.

Role: scan raw data (transactions, savings, borrowings, investments, app_usage)
and generate "Facts" — evidence-grounded truths, NO interpretation, NO advice.

Each Fact has "evidence" (raw source data) to ensure auditability —
this is a key pitch point: "every fact is traceable back to evidence".

This is a pure logic (rule-based) function, NO LLM used — because "identifying numeric
patterns" should be 100% accurate, and should not be delegated to an LLM (avoiding hallucination).
The LLM is only used in the next step (Insight Engine) to translate the Facts into human-readable text.
"""

from collections import defaultdict
from datetime import date
from typing import Any, Dict, List, Optional


def _month_key(value) -> str:
    if isinstance(value, date):
        return value.strftime("%Y-%m")
    return str(value)[:7]


def _get(obj: Any, key: str):
    """
    Allows the engine to read both dicts and Pydantic objects.

    dict:
        tx["amount"]

    Pydantic object:
        tx.amount
    """
    if isinstance(obj, dict):
        return obj.get(key)
    return getattr(obj, key)


def detect_spending_spike(transactions: List[Any], category: str = "food_delivery", threshold_pct: float = 30.0) -> Optional[dict]:
    """
    Compares spending in the most recent month vs the average of previous months, for a specific category.
    Returns a Fact if it increases beyond threshold_pct (%).
    """
    monthly_totals: Dict[str, float] = defaultdict(float)
    evidence_tx_ids: Dict[str, List[str]] = defaultdict(list)

    for tx in transactions:
        if _get(tx, "category") == category and _get(tx, "type") == "debit":
            m = _month_key(_get(tx, "date"))
            monthly_totals[m] += _get(tx, "amount")
            evidence_tx_ids[m].append(_get(tx, "transaction_id"))

    months_sorted = sorted(monthly_totals.keys())
    if len(months_sorted) < 2:
        return None  # insufficient data to compare

    latest_month = months_sorted[-1]
    previous_months = months_sorted[:-1]
    avg_previous = sum(monthly_totals[m] for m in previous_months) / len(previous_months)
    latest_amount = monthly_totals[latest_month]

    if avg_previous == 0:
        return None

    pct_change = ((latest_amount - avg_previous) / avg_previous) * 100

    if pct_change >= threshold_pct:
        return {
            "fact_type": "spending_spike",
            "description": (
                f"Spending on category '{category}' in {latest_month} is {latest_amount:,.0f} PHP, "
                f"an increase of {pct_change:.0f}% compared with the average of the previous {len(previous_months)} months "
                f"({avg_previous:,.0f} PHP)."
            ),
            "value": {
                "latest_amount": latest_amount,
                "avg_previous_months": round(avg_previous, 2),
                "pct_change": round(pct_change, 1),
            },
            "scope": {
                "category": category,
                "latest_month": latest_month,
                "comparison_month_count": len(previous_months),
                "currency": "PHP",
            },
            "evidence_ids": evidence_tx_ids[latest_month],
            "evidence_note": None,
        }
    return None


def detect_idle_balance(savings: List[Any], min_balance: float = 10000.0, max_fluctuation_pct: float = 5.0) -> Optional[dict]:
    """
    Detects stable (low fluctuation) and sufficiently large savings balances over multiple consecutive periods
    -> suggests this is an "idle balance", not advice, just an observation.
    """
    if len(savings) < 2:
        return None

    balances_sorted = sorted(savings, key=lambda s: _get(s, "as_of_date"))
    balances = [_get(s, "balance") for s in balances_sorted]

    if min(balances) < min_balance:
        return None

    fluctuation_pct = ((max(balances) - min(balances)) / min(balances)) * 100

    if fluctuation_pct <= max_fluctuation_pct:
        return {
            "fact_type": "idle_balance",
            "description": (
                f"Savings balance remained stable around {balances[-1]:,.0f} PHP over the last "
                f"{len(balances)} consecutive periods, with a fluctuation of only {fluctuation_pct:.1f}%."
            ),
            "value": {
                "latest_balance": balances[-1],
                "fluctuation_pct": round(fluctuation_pct, 1),
            },
            "scope": {
                "account_type": _get(balances_sorted[0], "account_type"),
                "balance_snapshots": [
                    {
                        "date": str(_get(s, "as_of_date")),
                        "balance": _get(s, "balance"),
                        "savings_goal": _get(s, "savings_goal"),
                    }
                    for s in balances_sorted
                ],
                "currency": "PHP",
            },
            "evidence_ids": [],
            "evidence_note": "SavingsBalance records do not have stable balance_id in MVP; balance snapshots are stored in scope.",
        }
    return None


def detect_dormant_feature(app_usage: List[Any], investments: List[Any], available_features: List[dict]) -> List[dict]:
    """
    Detects investment features that the customer has NOT used yet (no corresponding holding record),
    but shows evidence of viewing/abandoning onboarding in app_usage metadata.

    Note:
    - Does not conclude "never invested in their lifetime".
    - Only states "no holding record in existing investment data".
    """
    facts = []

    used_asset_classes = {_get(inv, "asset_class") for inv in investments}

    feature_to_asset_class = {
        "invest_gold": "paxg_gold",
        "invest_crypto": "crypto",
        "invest_stocks": "ph_stock",
    }

    viewed_features = {}

    for event in app_usage:
        feature_name = _get(event, "feature_name")
        event_type = _get(event, "event_type")
        metadata = _get(event, "metadata") or {}

        if event_type == "feature_view" and feature_name:
            viewed_features[feature_name] = {
                "timestamp": str(_get(event, "timestamp")),
                "metadata": metadata,
            }

    for feature in available_features:
        fid = feature["feature_id"]
        asset_class = feature_to_asset_class.get(fid)

        if not asset_class:
            continue

        if asset_class not in used_asset_classes:
            # For MVP safety, only create a dormant_feature fact when there is
            # explicit app-usage evidence that the customer viewed the feature.
            if fid not in viewed_features:
                continue

            note = f"viewed feature '{feature['name']}'"
            completed_onboarding = viewed_features[fid]["metadata"].get("completed_onboarding") == True

            if viewed_features[fid]["metadata"].get("completed_onboarding") is False:
                note = (
                    f"viewed feature '{feature['name']}' but metadata shows "
                    "onboarding was not completed"
                )

            facts.append({
                "fact_type": "dormant_feature",
                "description": f"Customer {note}.",
                "value": {
                    "investment_holding_record_found": False,
                    "completed_onboarding": completed_onboarding,
                },
                "scope": {
                    "feature_id": fid,
                    "feature_name": feature["name"],
                    "last_feature_view_timestamp": viewed_features[fid]["timestamp"],
                    "drop_off_step": viewed_features[fid]["metadata"].get("drop_off_step"),
                },
                "evidence_ids": [],
                "evidence_note": "AppUsageEvent records do not have stable event_id in MVP; app usage metadata is stored in scope.",
            })

    return facts


def detect_upcoming_due(borrowings: List[Any], days_ahead: int = 7) -> List[dict]:
    """
    Detects loans that are due within the next N days.
    This is a neutral calendar reminder fact, NOT a judgmental warning.
    """
    facts = []
    for loan in borrowings:
        if _get(loan, "status") != "current":
            continue

        raw_due = _get(loan, "next_due_date")
        due = raw_due if isinstance(raw_due, date) else date.fromisoformat(raw_due)
        # Assume "today" is the latest transaction date in the demo system (2026-07-09)
        today = date(2026, 7, 9)
        days_left = (due - today).days
        if 0 <= days_left <= days_ahead:
            facts.append({
                "fact_type": "upcoming_due_reminder",
                "description": (
                    f"The {_get(loan, 'loan_type').upper()} loan has an outstanding balance of {_get(loan, 'outstanding_balance'):,.0f} PHP "
                    f"and a monthly payment of {_get(loan, 'monthly_payment'):,.0f} PHP due on {_get(loan, 'next_due_date')} "
                    f"({days_left} days remaining)."
                ),
                "value": {
                    "outstanding_balance": float(_get(loan, "outstanding_balance")),
                    "monthly_payment": float(_get(loan, "monthly_payment")),
                    "days_left": days_left,
                },
                "scope": {
                    "loan_type": _get(loan, "loan_type"),
                    "next_due_date": str(_get(loan, "next_due_date")),
                    "currency": "PHP",
                },
                "evidence_ids": [],
                "evidence_note": "Borrowing records do not have stable loan_id in MVP; due-date details are stored in scope.",
            })
    return facts


def generate_facts(customer_data: Any, available_features: List[dict]) -> List[dict]:
    """
    Aggregation function: runs all detectors, returns a complete list of Facts
    (with customer_id and fact_id attached).
    """
    profile = _get(customer_data, "profile")
    customer_id = _get(profile, "customer_id")
    raw_facts = []

    spike = detect_spending_spike(_get(customer_data, "transactions"))
    if spike:
        raw_facts.append(spike)

    idle = detect_idle_balance(_get(customer_data, "savings"))
    if idle:
        raw_facts.append(idle)

    raw_facts.extend(
        detect_dormant_feature(
            _get(customer_data, "app_usage"),
            _get(customer_data, "investments"),
            available_features,
        )
    )

    raw_facts.extend(detect_upcoming_due(_get(customer_data, "borrowings")))

    facts = []
    for i, f in enumerate(raw_facts):
        facts.append({
            "fact_id": f"fact_{customer_id}_{i+1:03d}",
            "customer_id": customer_id,
            **f,
        })
    return facts
