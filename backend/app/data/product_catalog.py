"""
Product Catalog — single source of truth for GoTyme products.

Roles:
- Insight/Engagement Engine MUST query this catalog to get educational_copy,
  NEVER self-generate what a product is (prevents hallucination).
- Data Checker queries required_data_fields to know what fields are needed for each product.
- Policy Engine queries eligibility_rules + blocked_conditions.
- Safety Engine queries prohibited_claims to block risky wording.

Wording adjusted according to review: avoid phrases like "grow idle cash", "diversify
beyond cash savings" (sounds like financial guidance) -> changed to purely educational,
neutral language ("learn about", "review how it works").
"""

from typing import Dict, List, Optional

PRODUCT_CATALOG = [
    {
        "product_id": "invest_gold",
        "product_name": "Gold Savings (PAXG)",
        "category": "investment",
        "allowed_nudge_types": ["dormant_feature", "idle_balance"],
        # Required field in customer data to be allowed to generate a nudge for this product
        "required_data_fields": ["app_usage", "investments"],
        "eligibility_rules": [
            "kyc_completed", "age_at_least_18", "available_in_philippines",
            "not_opted_out", "no_overdue_loan",
        ],
        "blocked_conditions": [
            "overdue_loan", "missing_product_usage", "user_opted_out",
        ],
        "educational_copy": (
            "Gold Savings is a GoTyme feature that lets users learn about saving "
            "in digital gold (PAXG). You can review how it works, including risks "
            "and product details, before deciding whether it is relevant to you."
        ),
        "prohibited_claims": [
            "guaranteed return", "risk-free", "you should invest", "move x% of your balance",
            "grow your money", "grow idle cash", "optimize return", "better use of your balance",
            "put idle money to work", "maximize earnings", "safe return", "diversify beyond cash",
            "optimize profit", "maximize return",
        ],
        # Preferred verbs for Challenge (P6) — educational only, NO financial action verbs
        "safe_challenge_verbs": ["learn about", "review", "compare information about", "complete a short tutorial on"],
        "unsafe_challenge_verbs": ["deposit into", "move money to", "activate", "invest in", "transfer to"],
    },
    {
        "product_id": "invest_crypto",
        "product_name": "Crypto Investing",
        "category": "investment",
        "allowed_nudge_types": ["dormant_feature"],
        "required_data_fields": ["app_usage", "investments"],
        "eligibility_rules": ["kyc_completed", "age_gte_18", "available_in_jurisdiction"],
        "blocked_conditions": ["user_opted_out_of_education_nudges"],
        "educational_copy": (
            "Crypto Investing is a GoTyme feature for learning about and reviewing "
            "cryptocurrency products available in the app, including risk information."
        ),
        "prohibited_claims": [
            "guaranteed return", "risk-free", "you should invest", "grow your money",
            "safe return", "maximize earnings",
        ],
        "safe_challenge_verbs": ["learn about", "review", "complete a short tutorial on"],
        "unsafe_challenge_verbs": ["deposit into", "buy", "invest in", "transfer to"],
    },
    {
        "product_id": "invest_stocks",
        "product_name": "PH Stocks Investing",
        "category": "investment",
        "allowed_nudge_types": ["dormant_feature"],
        "required_data_fields": ["app_usage", "investments"],
        "eligibility_rules": ["kyc_completed", "age_gte_18", "available_in_jurisdiction"],
        "blocked_conditions": ["user_opted_out_of_education_nudges"],
        "educational_copy": (
            "PH Stocks Investing is a GoTyme feature for learning about and reviewing "
            "Philippine stock market products available in the app."
        ),
        "prohibited_claims": [
            "guaranteed return", "risk-free", "you should invest", "grow your money", "safe return",
        ],
        "safe_challenge_verbs": ["learn about", "review", "complete a short tutorial on"],
        "unsafe_challenge_verbs": ["deposit into", "buy", "invest in"],
    },
    {
        "product_id": "goal_savings",
        "product_name": "Goal-based Savings Pocket",
        "category": "savings",
        "allowed_nudge_types": ["idle_balance"],
        "required_data_fields": ["savings"],
        "eligibility_rules": ["kyc_completed"],
        "blocked_conditions": ["user_opted_out_of_education_nudges"],
        "educational_copy": (
            "Goal-based Savings Pockets let users learn how to organize savings "
            "into separate pockets for specific goals."
        ),
        "prohibited_claims": ["you should save", "move x% of your balance", "grow your money"],
        "safe_challenge_verbs": ["learn about", "review", "explore"],
        "unsafe_challenge_verbs": ["move money to", "deposit into", "transfer to"],
    },
    {
        "product_id": "spending_breakdown",
        "product_name": "Spending Breakdown",
        "category": "financial_awareness",
        "allowed_nudge_types": ["spending_spike"],
        "required_data_fields": ["transactions"],
        "eligibility_rules": ["not_opted_out"],
        "blocked_conditions": ["missing_transactions", "user_opted_out"],
        "educational_copy": (
            "Spending Breakdown helps users review how their spending is "
            "distributed across categories."
        ),
        "prohibited_claims": [
            "you should stop spending", "bad spending habit", "financially irresponsible",
            "you should cut back",
        ],
        "safe_challenge_verbs": ["review", "check", "explore"],
        "unsafe_challenge_verbs": ["cut spending on", "stop using", "reduce"],
    },
    {
        "product_id": "bnpl",
        "product_name": "Buy Now Pay Later",
        "category": "credit",
        "allowed_nudge_types": ["upcoming_due_reminder"],
        "required_data_fields": ["borrowings"],
        "eligibility_rules": ["kyc_completed"],
        "blocked_conditions": [],
        "educational_copy": (
            "Buy Now Pay Later (BNPL) is a GoTyme credit feature. Payment schedules "
            "and due dates are shown so users can plan ahead."
        ),
        "prohibited_claims": ["you should borrow more", "you should pay early", "you should pay late"],
        "safe_challenge_verbs": ["review", "check"],
        "unsafe_challenge_verbs": ["borrow more", "pay early", "delay payment"],
    },
]


def get_product(product_id: str) -> Optional[dict]:
    for p in PRODUCT_CATALOG:
        if p["product_id"] == product_id:
            return p
    return None


def get_products_by_nudge_type(nudge_type: str) -> List[dict]:
    return [p for p in PRODUCT_CATALOG if nudge_type in p["allowed_nudge_types"]]


def get_all_prohibited_claims() -> List[str]:
    """Used for Safety Engine — aggregates all prohibited claims of all products."""
    claims = set()
    for p in PRODUCT_CATALOG:
        claims.update(c.lower() for c in p["prohibited_claims"])
    return sorted(claims)
