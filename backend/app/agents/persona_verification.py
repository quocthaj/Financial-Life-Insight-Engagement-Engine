from app.data.persona_registry import PERSONA_REGISTRY

def verify_against_persona_registry(customer_key: str, actual_outcome: str) -> dict:
    """
    Compares the actual outcome of the FinancialMirrorAgent run against the
    expected status/outcome from the persona registry.
    """
    persona = PERSONA_REGISTRY.get(customer_key)
    if not persona:
        return {
            "enabled": True,
            "persona_purpose": "Unknown persona",
            "expected_outcome": "unknown",
            "actual_outcome": actual_outcome,
            "match": False,
        }
    
    expected_outcome = persona.get("expected_status")
    match = expected_outcome == actual_outcome
    return {
        "enabled": True,
        "persona_purpose": persona.get("purpose", ""),
        "expected_outcome": expected_outcome,
        "actual_outcome": actual_outcome,
        "match": match,
    }
