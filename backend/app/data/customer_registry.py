from app.data import (
    mock_customer_maria,
    mock_customer_juan,
    mock_customer_alex,
    mock_customer_bea,
    mock_customer_carlo,
    mock_customer_dana,
    mock_customer_elena,
    mock_customer_niko,
    mock_customer_fina,
)
from app.data.persona_registry import PERSONA_REGISTRY

CUSTOMERS = {
    "cust_00123": {
        "id": "cust_00123",
        "name": "Maria Santos",
        "module": mock_customer_maria,
        "key": "maria",
    },
    "cust_00124": {
        "id": "cust_00124",
        "name": "Juan Dela Cruz",
        "module": mock_customer_juan,
        "key": "juan",
    },
    "cust_00125": {
        "id": "cust_00125",
        "name": "Alex Rivera",
        "module": mock_customer_alex,
        "key": "alex",
    },
    "cust_00126": {
        "id": "cust_00126",
        "name": "Bea Alcaraz",
        "module": mock_customer_bea,
        "key": "bea",
    },
    "cust_00127": {
        "id": "cust_00127",
        "name": "Carlo Reyes",
        "module": mock_customer_carlo,
        "key": "carlo",
    },
    "cust_00128": {
        "id": "cust_00128",
        "name": "Dana Lopez",
        "module": mock_customer_dana,
        "key": "dana",
    },
    "cust_00129": {
        "id": "cust_00129",
        "name": "Elena Rostova",
        "module": mock_customer_elena,
        "key": "elena",
    },
    "cust_00130": {
        "id": "cust_00130",
        "name": "Niko Santos",
        "module": mock_customer_niko,
        "key": "niko",
    },
    "cust_00131": {
        "id": "cust_00131",
        "name": "Fina",
        "module": mock_customer_fina,
        "key": "fina",
    },
}

def get_all_customers() -> list:
    results = []
    for cid, info in CUSTOMERS.items():
        profile = info["module"].get_customer_full_profile()["profile"]
        key = info["key"]
        reg_meta = PERSONA_REGISTRY.get(key, {})
        results.append({
            "customer_id": cid,
            "display_name": profile["display_name"],
            "age_band": profile["age_band"],
            "income_band": profile["income_band"],
            "life_stage": profile["life_stage"],
            "opted_out_of_education_nudges": profile["opted_out_of_education_nudges"],
            "kyc_completed": profile["kyc_completed"],
            "key": key,
            "purpose": reg_meta.get("purpose", ""),
            "expected_status": reg_meta.get("expected_status", ""),
        })
    return results

def get_customer_profile(customer_id: str) -> dict:
    if customer_id in CUSTOMERS:
        return CUSTOMERS[customer_id]["module"].get_customer_full_profile()
    # Search by key
    for cid, info in CUSTOMERS.items():
        if info["key"] == customer_id.lower():
            return info["module"].get_customer_full_profile()
    return None

def get_customer_features(customer_id: str) -> list:
    if customer_id in CUSTOMERS:
        return CUSTOMERS[customer_id]["module"].AVAILABLE_FEATURES
    for cid, info in CUSTOMERS.items():
        if info["key"] == customer_id.lower():
            return info["module"].AVAILABLE_FEATURES
    return []
