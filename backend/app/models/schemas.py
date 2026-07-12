"""
Data models for Financial Mirror (P5 + P6)

Input data covers 6 groups:
- demographic profile
- transactions
- savings/balances
- borrowing
- investments
- app usage

Important compliance principle:
- Use bucketed/anonymised demographic bands only.
- Do not use exact age or exact monthly income in mock customer data.
"""

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional
# pyrefly: ignore [missing-import]
from pydantic import BaseModel, Field


# ============================================================
# Input models
# ============================================================

class DemographicProfile(BaseModel):
    """
    Bucketed/anonymised profile.

    Do NOT store exact age or exact monthly income here.
    This is intentional for PII minimization.
    """
    customer_id: str
    display_name: str

    age_band: str
    income_band: str
    life_stage: str

    region: str = "PH"
    currency: str = "PHP"
    kyc_completed: bool
    opted_out_of_education_nudges: bool = False
    account_opened_date: date


class Transaction(BaseModel):
    transaction_id: str
    customer_id: str
    date: date
    category: str  # e.g. "food", "transport", "shopping", "bills", "entertainment"
    amount: float
    type: str
    description: str


class SavingsBalance(BaseModel):
    customer_id: str
    account_type: str  # e.g. "regular_savings", "goal_savings"
    balance: float
    savings_goal: Optional[str] = None
    as_of_date: date


class Borrowing(BaseModel):
    customer_id: str
    loan_type: str  # e.g. "personal_loan", "bnpl"
    principal: float
    outstanding_balance: float
    monthly_payment: float
    next_due_date: date
    status: str


class InvestmentHolding(BaseModel):
    customer_id: str

    asset_class: str
    product_name: str

    holding_value: float
    cost_basis: float

    last_updated: date


class AppUsageEvent(BaseModel):
    customer_id: str

    event_type: str
    feature_name: Optional[str] = None

    timestamp: datetime
    session_length_seconds: Optional[int] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)


class CustomerFullProfile(BaseModel):
    """
    Unified customer view — main input for Data Checker, Fact Engine, and Pattern Engine.
    """
    profile: DemographicProfile
    transactions: List[Transaction]
    savings: List[SavingsBalance]
    borrowings: List[Borrowing]
    investments: List[InvestmentHolding]
    app_usage: List[AppUsageEvent]


# ============================================================
# Pipeline intermediate models
# ============================================================

class DataAvailabilityReport(BaseModel):
    customer_id: str

    available_data_groups: List[str]
    missing_data_groups: List[str]

    can_generate_financial_observations: bool
    can_generate_product_nudges: bool
    notes: List[str] = Field(default_factory=list)


class Fact(BaseModel):
    """
    Evidence-grounded signal produced by the rule-based Fact/Pattern Engine.

    MVP evidence strategy:
    - Use evidence_ids only when the source records have stable IDs.
    - Store calculated metrics in value.
    - Store time/category/context in scope.
    - Do not fabricate evidence IDs for source records that do not have IDs yet.
    """
    fact_id: str
    customer_id: str

    fact_type: str
    description: str

    value: Dict[str, Any] = Field(default_factory=dict)
    scope: Dict[str, Any] = Field(default_factory=dict)
    evidence_ids: List[str] = Field(default_factory=list)

    evidence_note: Optional[str] = None


class PatternCandidate(BaseModel):
    """
    A candidate pattern created by comparing or combining multiple facts.

    Example:
    - "Dining spend increased by 50% compared with the previous 3-month average."
    """
    candidate_id: str
    customer_id: str

    pattern_type: str
    description: str

    based_on_facts: List[str]

    target_product_id: Optional[str] = None
    nudge_type: Optional[str] = None

    value: Dict[str, Any] = Field(default_factory=dict)


class PolicyDecision(BaseModel):
    candidate_id: str
    customer_id: str

    decision: str
    rule_ids_triggered: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)


# ============================================================
# Output models
# ============================================================

class Observation(BaseModel):
    """
    Customer-facing observation.

    Must stay factual, objective, and evidence-grounded.
    """
    observation_id: str
    customer_id: str

    candidate_id: str
    based_on_facts: List[str]

    text: str


class Nudge(BaseModel):
    """
    Gentle educational nudge.

    Must NOT be personalized financial advice.
    """
    nudge_id: str
    customer_id: str

    observation_id: str
    related_product_id: Optional[str] = None
    related_feature: Optional[str] = None

    nudge_type: str
    text: str

    passed_safety_check: bool = False
    safety_notes: Optional[str] = None


class Challenge(BaseModel):
    """
    P6 output: safe challenge/mission generated from a passed nudge.
    """
    challenge_id: str
    customer_id: str

    based_on_nudge: str

    title: str
    description: str
    target_feature: str

    criteria: str
    reward_type: str
    difficulty_tier: str

    reward_points: Optional[int] = None

    passed_safety_check: bool = False
    safety_notes: Optional[str] = None


class SafetyResult(BaseModel):
    checked_item_id: str
    item_type: str

    passed: bool
    violations: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class AuditFactSnapshot(BaseModel):
    model_config = {"protected_namespaces": ()}

    fact_id: str
    customer_id: str
    fact_type: str
    description: str

    value: Dict[str, Any] = Field(default_factory=dict)
    scope: Dict[str, Any] = Field(default_factory=dict)
    evidence_ids: List[str] = Field(default_factory=list)
    evidence_note: Optional[str] = None


class AuditEntry(BaseModel):
    model_config = {"protected_namespaces": ()}

    trace_id: str
    customer_id: str

    candidate_id: str
    candidate_type: str
    candidate_description: str
    based_on_facts: List[str]
    facts: List[AuditFactSnapshot]

    policy_result: Literal["accepted", "rejected", "unknown"]
    policy_rule_ids_triggered: List[str] = Field(default_factory=list)
    policy_reasons: List[str] = Field(default_factory=list)

    observation_text: Optional[str] = None
    nudge_text: Optional[str] = None

    observation_safety_passed: Optional[bool] = None
    observation_safety_violations: List[str] = Field(default_factory=list)

    nudge_safety_passed: Optional[bool] = None
    nudge_safety_violations: List[str] = Field(default_factory=list)

    challenge_title: Optional[str] = None
    challenge_description: Optional[str] = None
    challenge_criteria: Optional[str] = None

    challenge_safety_passed: Optional[bool] = None
    challenge_safety_violations: List[str] = Field(default_factory=list)

    generation_mode: str = "template"
    llm_prompt_version: str = "template_v1"
    model_name: str = "none_template_generator"

    final_status: Literal[
        "published",
        "rejected_by_policy",
        "blocked_by_safety",
        "unknown",
    ]

    timestamp: datetime