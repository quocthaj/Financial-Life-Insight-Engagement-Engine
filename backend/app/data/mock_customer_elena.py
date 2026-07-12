"""
Mock customer data — Persona 7: Elena Rostova.
This customer is a power user with high app usage events and multiple financial products.
Used to verify the behavior-adaptive engagement difficulty and rewards.
"""

CUSTOMER_ID = "cust_00129"

demographic_profile = {
    "customer_id": CUSTOMER_ID,
    "display_name": "Elena Rostova",
    "age_band": "25-34",
    "income_band": "high_income",
    "life_stage": "young_professional",
    "region": "PH",
    "currency": "PHP",
    "kyc_completed": True,
    "opted_out_of_education_nudges": False,
    "account_opened_date": "2023-05-15",
}

transactions = [
    {"transaction_id": "tx501", "customer_id": CUSTOMER_ID, "date": "2026-06-01", "category": "groceries", "amount": 5000, "type": "debit", "description": "Supermarket"},
    {"transaction_id": "tx502", "customer_id": CUSTOMER_ID, "date": "2026-06-15", "category": "salary", "amount": 90000, "type": "credit", "description": "Salary payout"},
    {"transaction_id": "tx503", "customer_id": CUSTOMER_ID, "date": "2026-04-05", "category": "food_delivery", "amount": 2000, "type": "debit", "description": "GrabFood"},
    {"transaction_id": "tx504", "customer_id": CUSTOMER_ID, "date": "2026-05-05", "category": "food_delivery", "amount": 3500, "type": "debit", "description": "GrabFood"},
    {"transaction_id": "tx505", "customer_id": CUSTOMER_ID, "date": "2026-06-05", "category": "food_delivery", "amount": 7000, "type": "debit", "description": "GrabFood"},
]

savings_balances = [
    {
        "customer_id": CUSTOMER_ID,
        "account_type": "regular_savings",
        "balance": 80000,
        "savings_goal": None,
        "as_of_date": "2026-04-30",
    },
    {
        "customer_id": CUSTOMER_ID,
        "account_type": "regular_savings",
        "balance": 81000,
        "savings_goal": None,
        "as_of_date": "2026-05-31",
    },
    {
        "customer_id": CUSTOMER_ID,
        "account_type": "regular_savings",
        "balance": 82000,
        "savings_goal": None,
        "as_of_date": "2026-06-30",
    }
]

borrowings = []

investments = [
    {
        "customer_id": CUSTOMER_ID,
        "asset_class": "ph_stock",
        "product_name": "PH Stocks Investing",
        "holding_value": 15000,
        "cost_basis": 14500,
        "last_updated": "2026-06-30",
    }
]

app_usage = [
    {"customer_id": CUSTOMER_ID, "event_type": "login", "feature_name": "home", "timestamp": "2026-06-01T09:00:00", "session_length_seconds": 180, "metadata": {}},
    {"customer_id": CUSTOMER_ID, "event_type": "login", "feature_name": "home", "timestamp": "2026-06-02T10:00:00", "session_length_seconds": 150, "metadata": {}},
    {"customer_id": CUSTOMER_ID, "event_type": "login", "feature_name": "home", "timestamp": "2026-06-03T11:00:00", "session_length_seconds": 200, "metadata": {}},
    {"customer_id": CUSTOMER_ID, "event_type": "login", "feature_name": "home", "timestamp": "2026-06-04T12:00:00", "session_length_seconds": 220, "metadata": {}},
    {"customer_id": CUSTOMER_ID, "event_type": "feature_view", "feature_name": "savings", "timestamp": "2026-06-05T10:15:00", "session_length_seconds": 240, "metadata": {}},
    {"customer_id": CUSTOMER_ID, "event_type": "feature_view", "feature_name": "invest_stocks", "timestamp": "2026-06-12T11:20:00", "session_length_seconds": 210, "metadata": {}},
    {"customer_id": CUSTOMER_ID, "event_type": "feature_use", "feature_name": "invest_stocks", "timestamp": "2026-06-20T14:30:00", "session_length_seconds": 160, "metadata": {}},
    {"customer_id": CUSTOMER_ID, "event_type": "feature_view", "feature_name": "invest_gold", "timestamp": "2026-06-25T16:45:00", "session_length_seconds": 90, "metadata": {"drop_off_step": "gold_savings_intro", "completed_onboarding": False}},
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
