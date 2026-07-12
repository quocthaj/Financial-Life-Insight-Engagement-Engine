"""
Mock customer data — Persona 3: Alex Rivera.
This customer viewed the Crypto Investing feature, which is rejected by MVP policy rules.
"""

CUSTOMER_ID = "cust_00125"

demographic_profile = {
    "customer_id": CUSTOMER_ID,
    "display_name": "Alex Rivera",
    "age_band": "18-24",
    "income_band": "low_income",
    "life_stage": "student",
    "region": "PH",
    "currency": "PHP",
    "kyc_completed": True,
    "opted_out_of_education_nudges": False,
    "account_opened_date": "2025-09-01",
}

transactions = [
    {"transaction_id": "tx201", "customer_id": CUSTOMER_ID, "date": "2026-06-02", "category": "food_delivery", "amount": 300, "type": "debit", "description": "McDonalds delivery"},
    {"transaction_id": "tx202", "customer_id": CUSTOMER_ID, "date": "2026-06-15", "category": "allowance", "amount": 5000, "type": "credit", "description": "Monthly allowance"},
]

savings_balances = [
    {
        "customer_id": CUSTOMER_ID,
        "account_type": "regular_savings",
        "balance": 2000,
        "savings_goal": None,
        "as_of_date": "2026-06-30",
    }
]

borrowings = []
investments = []

app_usage = [
    {
        "customer_id": CUSTOMER_ID,
        "event_type": "login",
        "feature_name": "home",
        "timestamp": "2026-06-25T10:00:00",
        "session_length_seconds": 120,
        "metadata": {},
    },
    {
        "customer_id": CUSTOMER_ID,
        "event_type": "feature_view",
        "feature_name": "invest_crypto",
        "timestamp": "2026-06-26T14:35:00",
        "session_length_seconds": 95,
        "metadata": {
            "drop_off_step": "crypto_risk_warning",
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


# List of available GoTyme features
AVAILABLE_FEATURES = [
    {"feature_id": "invest_gold", "name": "Gold Savings (PAXG)", "category": "investment"},
    {"feature_id": "invest_crypto", "name": "Crypto Investing", "category": "investment"},
    {"feature_id": "invest_stocks", "name": "PH Stocks Investing", "category": "investment"},
    {"feature_id": "goal_savings", "name": "Goal-based Savings Pocket", "category": "savings"},
    {"feature_id": "bnpl", "name": "Buy Now Pay Later", "category": "credit"},
]
