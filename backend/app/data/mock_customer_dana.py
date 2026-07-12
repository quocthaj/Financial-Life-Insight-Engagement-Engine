"""
Mock customer data — Persona 6: Dana Lopez.
This customer triggers a dormant Gold Savings feature fact.
During generation, the output is deliberately intercepted to force unsafe wording.
Used to verify the Safety Gate block in the full pipeline.
"""

CUSTOMER_ID = "cust_00128"

demographic_profile = {
    "customer_id": CUSTOMER_ID,
    "display_name": "Dana Lopez",
    "age_band": "25-34",
    "income_band": "middle_income",
    "life_stage": "young_professional",
    "region": "PH",
    "currency": "PHP",
    "kyc_completed": True,
    "opted_out_of_education_nudges": False,
    "account_opened_date": "2023-11-12",
}

transactions = [
    {"transaction_id": "tx401", "customer_id": CUSTOMER_ID, "date": "2026-06-01", "category": "groceries", "amount": 3500, "type": "debit", "description": "Supermarket purchase"},
    {"transaction_id": "tx402", "customer_id": CUSTOMER_ID, "date": "2026-06-15", "category": "salary", "amount": 30000, "type": "credit", "description": "Salary payout"},
]

savings_balances = [
    {
        "customer_id": CUSTOMER_ID,
        "account_type": "regular_savings",
        "balance": 25000,
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
        "timestamp": "2026-06-25T18:00:00",
        "session_length_seconds": 60,
        "metadata": {},
    },
    {
        "customer_id": CUSTOMER_ID,
        "event_type": "feature_view",
        "feature_name": "invest_gold",
        "timestamp": "2026-06-26T14:35:00",
        "session_length_seconds": 95,
        "metadata": {
            "drop_off_step": "gold_savings_intro",
            "completed_onboarding": False,
        },
    }
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
