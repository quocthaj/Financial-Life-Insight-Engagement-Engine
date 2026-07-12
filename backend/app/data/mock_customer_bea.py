"""
Mock customer data — Persona 4: Bea Alcaraz.
This customer has missing data across multiple categories (transactions, savings, app usage, etc.).
Used to test Data Checker's ability to identify missing data groups and prevent engine crash.
"""

CUSTOMER_ID = "cust_00126"

demographic_profile = {
    "customer_id": CUSTOMER_ID,
    "display_name": "Bea Alcaraz",
    "age_band": "35-44",
    "income_band": "middle_income",
    "life_stage": "family",
    "region": "PH",
    "currency": "PHP",
    "kyc_completed": True,
    "opted_out_of_education_nudges": False,
    "account_opened_date": "2024-03-12",
}

transactions = []
savings_balances = []
borrowings = []
investments = []
app_usage = []

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
