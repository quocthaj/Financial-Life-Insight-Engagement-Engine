import os
os.environ["LLM_PROVIDER"] = "mock"
os.environ["ENV"] = "development"

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"message": "Welcome to Financial Mirror API", "status": "running"}

def test_list_customers():
    response = client.get("/api/customers")
    assert response.status_code == 200
    customers = response.json()
    assert len(customers) == 9
    ids = [c["customer_id"] for c in customers]
    assert "cust_00123" in ids # Maria
    assert "cust_00124" in ids # Juan
    assert "cust_00125" in ids # Alex
    assert "cust_00126" in ids # Bea
    assert "cust_00127" in ids # Carlo
    assert "cust_00128" in ids # Dana
    assert "cust_00129" in ids # Elena
    assert "cust_00130" in ids # Niko
    assert "cust_00131" in ids # Fina

def test_list_products():
    response = client.get("/api/products")
    assert response.status_code == 200
    products = response.json()
    assert len(products) > 0
    names = [p["product_id"] for p in products]
    assert "invest_gold" in names

def test_pipeline_run_maria():
    response = client.post("/api/pipeline/run", json={"customer_id": "cust_00123"})
    assert response.status_code == 200
    data = response.json()
    assert data["customer_id"] == "cust_00123"
    assert data["facts_count"] == 4
    # All 4 should be accepted
    accepted_policies = [p for p in data["policies"] if p["decision"] == "accepted"]
    assert len(accepted_policies) == 4

def test_pipeline_run_juan():
    response = client.post("/api/pipeline/run", json={"customer_id": "cust_00124"})
    assert response.status_code == 200
    data = response.json()
    assert data["customer_id"] == "cust_00124"
    assert data["facts_count"] == 2
    # All should be rejected by opt-out policy
    rejected_policies = [p for p in data["policies"] if p["decision"] == "rejected"]
    assert len(rejected_policies) == 2
    for p in rejected_policies:
        assert "global_user_opted_out" in p["rule_ids_triggered"]

def test_pipeline_run_alex():
    response = client.post("/api/pipeline/run", json={"customer_id": "cust_00125"})
    assert response.status_code == 200
    data = response.json()
    assert data["customer_id"] == "cust_00125"
    assert data["facts_count"] == 1
    # Should be rejected because Crypto is blocked in MVP release
    rejected_policies = [p for p in data["policies"] if p["decision"] == "rejected"]
    assert len(rejected_policies) == 1
    assert "reject_unapproved_investment_feature" in rejected_policies[0]["rule_ids_triggered"]

def test_pipeline_run_bea():
    response = client.post("/api/pipeline/run", json={"customer_id": "cust_00126"})
    assert response.status_code == 200
    data = response.json()
    assert data["customer_id"] == "cust_00126"
    assert data["facts_count"] == 0
    assert data["data_availability"]["can_generate_financial_observations"] is False
    assert "transactions" in data["data_availability"]["missing_data_groups"]

def test_pipeline_run_carlo():
    response = client.post("/api/pipeline/run", json={"customer_id": "cust_00127"})
    assert response.status_code == 200
    data = response.json()
    assert data["customer_id"] == "cust_00127"
    assert data["facts_count"] == 2
    rejected_policies = [p for p in data["policies"] if p["decision"] == "rejected"]
    assert len(rejected_policies) == 2
    for p in rejected_policies:
        assert "global_kyc_not_completed" in p["rule_ids_triggered"]

def test_pipeline_run_dana():
    response = client.post("/api/pipeline/run", json={"customer_id": "cust_00128"})
    assert response.status_code == 200
    data = response.json()
    assert data["customer_id"] == "cust_00128"
    assert data["facts_count"] == 1
    # Policy accepted, output created but should fail safety check because we force-injected unsafe wording
    assert len(data["outputs"]) == 1
    nudge = data["outputs"][0]["nudge"]
    assert nudge["passed_safety_check"] is False
    assert "Safety check failed" in nudge["safety_notes"]
    # Verify audit final_status is blocked_by_safety
    assert data["audit_entries"][0]["final_status"] == "blocked_by_safety"

def test_pipeline_run_elena():
    response = client.post("/api/pipeline/run", json={"customer_id": "cust_00129"})
    assert response.status_code == 200
    data = response.json()
    assert data["customer_id"] == "cust_00129"
    assert data["facts_count"] == 3
    # Verify adaptive difficulty tier
    for ch_item in data["challenges"]:
        challenge = ch_item["challenge"]
        if challenge["based_on_nudge"] == "nudge_fact_cust_00129_002":
            assert challenge["difficulty_tier"] == "power_user"
            assert challenge["reward_points"] == 200

def test_pipeline_run_niko():
    response = client.post("/api/pipeline/run", json={"customer_id": "cust_00130"})
    assert response.status_code == 200
    data = response.json()
    assert data["customer_id"] == "cust_00130"
    assert data["facts_count"] == 1
    rejected_policies = [p for p in data["policies"] if p["decision"] == "rejected"]
    assert len(rejected_policies) == 1
    assert "global_age_band_not_eligible" in rejected_policies[0]["rule_ids_triggered"]

def test_pipeline_run_fina():
    response = client.post("/api/pipeline/run", json={"customer_id": "cust_00131"})
    assert response.status_code == 200
    data = response.json()
    assert data["customer_id"] == "cust_00131"
    assert data["final_status"] == "published"
    assert len(data["result"]["safety_retry_attempts"]) == 1
    attempt = data["result"]["safety_retry_attempts"][0]
    assert attempt["status"] == "recovered"
    assert attempt["attempt"] == 1
    assert "We recommend" in attempt["original_nudge"]
    assert "You can review" in attempt["rewritten_nudge"]

def test_audit_logs():
    # Clear audit logs first
    clear_resp = client.post("/api/audit-logs/clear")
    assert clear_resp.status_code == 200
    
    # Run pipelines to generate logs
    client.post("/api/pipeline/run", json={"customer_id": "cust_00123"})
    client.post("/api/pipeline/run", json={"customer_id": "cust_00124"})
    
    # Fetch logs
    resp = client.get("/api/audit-logs")
    assert resp.status_code == 200
    logs = resp.json()
    # Maria has 4 logs, Juan has 2 logs, total = 6 logs
    assert len(logs) == 6

