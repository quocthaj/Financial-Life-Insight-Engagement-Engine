"""
Mock customer data — 1 sample customer "Maria Santos" in Philippines.

Patterns intentionally embedded in the data for Fact Engine to detect:
1. "food_delivery" spending spike in the last 3 months (spending_spike)
2. Stable savings balance, left unused ("idle_balance")
3. Never used Gold Savings feature despite being eligible ("dormant_feature")
4. BNPL loan due soon ("upcoming_due_reminder" — neutral calendar reminder, not advice)
"""

from datetime import date

CUSTOMER_ID = "cust_00123"

demographic_profile = {
    "customer_id": CUSTOMER_ID,
    "display_name": "Maria Santos",
    "age_band": "25-34",
    "income_band": "middle_income",
    "life_stage": "young_professional",
    "region": "PH",
    "currency": "PHP",
    "kyc_completed": True,
    "opted_out_of_education_nudges": False,
    "account_opened_date": "2023-01-15",
}

# 3 transaction months — food_delivery increasing: Month 1 ~3000, Month 2 ~4500, Month 3 ~7200
transactions = [
    # Month 1
    {"transaction_id": "tx001", "customer_id": CUSTOMER_ID, "date": "2026-04-05", "category": "food_delivery", "amount": 950, "type": "debit", "description": "GrabFood order"},
    {"transaction_id": "tx002", "customer_id": CUSTOMER_ID, "date": "2026-04-12", "category": "food_delivery", "amount": 1100, "type": "debit", "description": "Foodpanda order"},
    {"transaction_id": "tx003", "customer_id": CUSTOMER_ID, "date": "2026-04-20", "category": "food_delivery", "amount": 980, "type": "debit", "description": "GrabFood order"},
    {"transaction_id": "tx004", "customer_id": CUSTOMER_ID, "date": "2026-04-01", "category": "bills", "amount": 3500, "type": "debit", "description": "Electricity bill"},
    # Month 2
    {"transaction_id": "tx005", "customer_id": CUSTOMER_ID, "date": "2026-05-04", "category": "food_delivery", "amount": 1200, "type": "debit", "description": "GrabFood order"},
    {"transaction_id": "tx006", "customer_id": CUSTOMER_ID, "date": "2026-05-11", "category": "food_delivery", "amount": 1450, "type": "debit", "description": "Foodpanda order"},
    {"transaction_id": "tx007", "customer_id": CUSTOMER_ID, "date": "2026-05-18", "category": "food_delivery", "amount": 1850, "type": "debit", "description": "GrabFood order"},
    {"transaction_id": "tx008", "customer_id": CUSTOMER_ID, "date": "2026-05-01", "category": "bills", "amount": 3500, "type": "debit", "description": "Electricity bill"},
    # Month 3 (most recent month — food_delivery spending spikes)
    {"transaction_id": "tx009", "customer_id": CUSTOMER_ID, "date": "2026-06-03", "category": "food_delivery", "amount": 2100, "type": "debit", "description": "GrabFood order"},
    {"transaction_id": "tx010", "customer_id": CUSTOMER_ID, "date": "2026-06-10", "category": "food_delivery", "amount": 2450, "type": "debit", "description": "Foodpanda order"},
    {"transaction_id": "tx011", "customer_id": CUSTOMER_ID, "date": "2026-06-17", "category": "food_delivery", "amount": 2650, "type": "debit", "description": "GrabFood order"},
    {"transaction_id": "tx012", "customer_id": CUSTOMER_ID, "date": "2026-06-01", "category": "bills", "amount": 3500, "type": "debit", "description": "Electricity bill"},
    {"transaction_id": "tx013", "customer_id": CUSTOMER_ID, "date": "2026-06-15", "category": "salary", "amount": 45000, "type": "credit", "description": "Monthly salary"},
]

savings_balances = [
    {
        "customer_id": CUSTOMER_ID,
        "account_type": "regular_savings",
        "balance": 27800,
        "savings_goal": None,
        "as_of_date": "2026-04-30",
    },
    {
        "customer_id": CUSTOMER_ID,
        "account_type": "regular_savings",
        "balance": 28100,
        "savings_goal": None,
        "as_of_date": "2026-05-31",
    },
    {
        "customer_id": CUSTOMER_ID,
        "account_type": "regular_savings",
        "balance": 28450,
        "savings_goal": None,
        "as_of_date": "2026-06-30",
    },
]
# 1 BNPL due in the next 5 days
borrowings = [
    {
        "customer_id": CUSTOMER_ID,
        "loan_type": "bnpl",
        "principal": 6000,
        "outstanding_balance": 2000,
        "monthly_payment": 2000,
        "next_due_date": "2026-07-14",
        "status": "current",
    }
]

# No investments yet -> never used Gold Savings / Crypto / PH Stocks despite being available in-app
investments = []

app_usage = [
    {
        "customer_id": CUSTOMER_ID,
        "event_type": "login",
        "feature_name": "home",
        "timestamp": "2026-06-01T09:00:00",
        "session_length_seconds": 180,
        "metadata": {},
    },
    {
        "customer_id": CUSTOMER_ID,
        "event_type": "feature_view",
        "feature_name": "savings",
        "timestamp": "2026-06-05T10:15:00",
        "session_length_seconds": 240,
        "metadata": {},
    },
    {
        "customer_id": CUSTOMER_ID,
        "event_type": "feature_view",
        "feature_name": "savings",
        "timestamp": "2026-06-12T11:20:00",
        "session_length_seconds": 210,
        "metadata": {},
    },
    {
        "customer_id": CUSTOMER_ID,
        "event_type": "feature_view",
        "feature_name": "bnpl",
        "timestamp": "2026-06-20T14:30:00",
        "session_length_seconds": 160,
        "metadata": {},
    },
    {
        "customer_id": CUSTOMER_ID,
        "event_type": "feature_view",
        "feature_name": "invest_gold",
        "timestamp": "2026-04-20T16:45:00",
        "session_length_seconds": 90,
        "metadata": {
            "drop_off_step": "gold_savings_intro",
            "completed_onboarding": False,
        },
    },
]

def get_customer_full_profile() -> dict:
    """Returns the full profile data of a customer, used as input for the Fact Engine."""
    return {
        "profile": demographic_profile,
        "transactions": transactions,
        "savings": savings_balances,
        "borrowings": borrowings,
        "investments": investments,
        "app_usage": app_usage,
    }


# List of available GoTyme features — used by Engagement Engine to identify dormant features
AVAILABLE_FEATURES = [
    {"feature_id": "invest_gold", "name": "Gold Savings (PAXG)", "category": "investment"},
    {"feature_id": "invest_crypto", "name": "Crypto Investing", "category": "investment"},
    {"feature_id": "invest_stocks", "name": "PH Stocks Investing", "category": "investment"},
    {"feature_id": "goal_savings", "name": "Goal-based Savings Pocket", "category": "savings"},
    {"feature_id": "bnpl", "name": "Buy Now Pay Later", "category": "credit"},
]
