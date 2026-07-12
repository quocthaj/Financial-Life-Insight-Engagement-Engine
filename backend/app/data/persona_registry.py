"""
Persona Registry — Metadata and expected outcome mapping for the 8 demonstration and stress test cases.
Provides structured data for the compliance dashboard UI to explain testing goals and actual outcomes.
"""

PERSONA_REGISTRY = {
    "maria": {
        "customer_id": "cust_00123",
        "label": "Maria Santos",
        "purpose": "Happy path - published nudges/challenges",
        "expected_status": "published",
    },
    "juan": {
        "customer_id": "cust_00124",
        "label": "Juan Dela Cruz",
        "purpose": "User opt-out - rejected by global policy gate",
        "expected_status": "rejected_by_policy",
    },
    "alex": {
        "customer_id": "cust_00125",
        "label": "Alex Rivera",
        "purpose": "Crypto out-of-scope - rejected by product policy gate",
        "expected_status": "rejected_by_policy",
    },
    "bea": {
        "customer_id": "cust_00126",
        "label": "Bea Alcaraz",
        "purpose": "Missing data - reports missing groups, no facts generated",
        "expected_status": "no_facts",
    },
    "carlo": {
        "customer_id": "cust_00127",
        "label": "Carlo Reyes",
        "purpose": "KYC incomplete - rejected by KYC policy gate",
        "expected_status": "rejected_by_policy",
    },
    "dana": {
        "customer_id": "cust_00128",
        "label": "Dana Lopez",
        "purpose": "Forced unsafe wording - blocked by safety engine",
        "expected_status": "blocked_by_safety",
    },
    "elena": {
        "customer_id": "cust_00129",
        "label": "Elena Rostova",
        "purpose": "Power user - published with power_user difficulty adaptive rewards",
        "expected_status": "published",
    },
    "niko": {
        "customer_id": "cust_00130",
        "label": "Niko Santos",
        "purpose": "Under 18 - rejected by age policy gate",
        "expected_status": "rejected_by_policy",
    },
    "fina": {
        "customer_id": "cust_00131",
        "label": "Fina",
        "purpose": "Safety retry recovery - unsafe wording rewritten successfully",
        "expected_status": "published",
    },
}
