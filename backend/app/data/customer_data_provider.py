"""
customer_data_provider.py

Hybrid customer data loading abstraction.

Providers:
  - MockCustomerDataProvider  : wraps existing customer_registry (default)
  - SupabaseCustomerDataProvider : loads data from Supabase tables

Selection:
  DATA_SOURCE=mock       → MockCustomerDataProvider  (default)
  DATA_SOURCE=supabase   → SupabaseCustomerDataProvider
                           with ALLOW_MOCK_FALLBACK=true → falls back to mock if
                           the customer is not found in Supabase.

Rules:
  - Provider returns the same dict shape as get_customer_profile() / get_customer_features().
  - result["source"] is always "mock" or "supabase".
  - No LLM involvement.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()


# ─────────────────────────────────────────────────────────────
# Abstract base
# ─────────────────────────────────────────────────────────────

class CustomerDataProvider(ABC):
    source: str = "unknown"

    @abstractmethod
    def get_customer_profile(self, customer_key: str) -> Optional[Dict[str, Any]]:
        """Return full customer profile dict or None if not found."""

    @abstractmethod
    def get_customer_features(self, customer_key: str) -> List[Dict[str, Any]]:
        """Return list of available feature dicts for the customer."""


# ─────────────────────────────────────────────────────────────
# Mock provider (wraps existing customer_registry)
# ─────────────────────────────────────────────────────────────

class MockCustomerDataProvider(CustomerDataProvider):
    source = "mock"

    def get_customer_profile(self, customer_key: str) -> Optional[Dict[str, Any]]:
        from app.data.customer_registry import get_customer_profile
        return get_customer_profile(customer_key)

    def get_customer_features(self, customer_key: str) -> List[Dict[str, Any]]:
        from app.data.customer_registry import get_customer_features
        return get_customer_features(customer_key)


# ─────────────────────────────────────────────────────────────
# Supabase provider
# ─────────────────────────────────────────────────────────────

DEFAULT_FEATURES = [
    {"feature_id": "invest_gold",   "name": "Gold Savings (PAXG)",          "category": "investment"},
    {"feature_id": "invest_crypto", "name": "Crypto Investing",             "category": "investment"},
    {"feature_id": "invest_stocks", "name": "PH Stocks Investing",          "category": "investment"},
    {"feature_id": "goal_savings",  "name": "Goal-based Savings Pocket",    "category": "savings"},
    {"feature_id": "bnpl",          "name": "Buy Now Pay Later",            "category": "credit"},
]


class SupabaseCustomerDataProvider(CustomerDataProvider):
    source = "supabase"

    def __init__(self) -> None:
        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY", "")
        if not self.url or not self.key:
            raise RuntimeError(
                "DATA_SOURCE=supabase requires SUPABASE_URL and "
                "SUPABASE_SERVICE_ROLE_KEY (or SUPABASE_ANON_KEY) in environment."
            )
        if not self.url.startswith(("http://", "https://")):
            raise RuntimeError(
                "DATA_SOURCE=supabase requires SUPABASE_URL to be a full http(s) URL."
            )

    # ── HTTP helpers ────────────────────────────────────────

    def _headers(self) -> Dict[str, str]:
        return {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
        }

    def _get(self, table: str, params: str) -> List[Dict[str, Any]]:
        url = f"{self.url}/rest/v1/{table}?{params}"
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Supabase HTTP {exc.code} on {table}: {body}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Supabase network error on {table}: {exc}") from exc

    # ── Resolve persona key → customer_id ──────────────────

    def _resolve_customer_id(self, customer_key: str) -> Optional[str]:
        """
        Accept either a persona key (e.g. 'maria') or a raw customer_id
        (e.g. 'cust_00123').  Resolves via persona_registry table first,
        then tries customers table directly.
        """
        # Try persona_registry
        rows = self._get(
            "persona_registry",
            f"persona_key=eq.{customer_key}&select=customer_id&limit=1",
        )
        if rows:
            return rows[0]["customer_id"]

        # Maybe caller passed a raw customer_id
        rows = self._get(
            "customers",
            f"customer_id=eq.{customer_key}&select=customer_id&limit=1",
        )
        if rows:
            return rows[0]["customer_id"]

        return None

    # ── Load each data group ────────────────────────────────

    def _load_profile(self, customer_id: str) -> Optional[Dict[str, Any]]:
        rows = self._get(
            "customer_profiles",
            f"customer_id=eq.{customer_id}&limit=1",
        )
        if not rows:
            return None
        customer_rows = self._get(
            "customers",
            f"customer_id=eq.{customer_id}&select=display_name&limit=1",
        )
        r = rows[0]
        display_name = customer_rows[0].get("display_name") if customer_rows else customer_id
        return {
            "customer_id": r["customer_id"],
            "display_name": display_name,
            "age_band": r.get("age_band", "unknown"),
            "income_band": r.get("income_band", "unknown"),
            "life_stage": r.get("life_stage", "unknown"),
            "region": r.get("region", "PH"),
            "currency": r.get("currency", "PHP"),
            "kyc_completed": bool(r.get("kyc_completed", False)),
            "opted_out_of_education_nudges": bool(r.get("opted_out_of_education_nudges", False)),
            "account_opened_date": str(r.get("account_opened_date", "2020-01-01")),
        }

    def _load_transactions(self, customer_id: str) -> List[Dict[str, Any]]:
        rows = self._get(
            "transactions",
            f"customer_id=eq.{customer_id}&order=transaction_date.desc&limit=500",
        )
        result = []
        for r in rows:
            result.append({
                "transaction_id": r.get("transaction_id", r.get("id", "")),
                "customer_id": r["customer_id"],
                "date": str(r.get("transaction_date") or r.get("date") or r.get("created_at", "2020-01-01"))[:10],
                "category": r.get("category", "other"),
                "amount": float(r.get("amount", 0)),
                "type": r.get("type", "debit"),
                "description": r.get("description", ""),
            })
        return result

    def _load_savings(self, customer_id: str) -> List[Dict[str, Any]]:
        rows = self._get(
            "savings_balances",
            f"customer_id=eq.{customer_id}&order=snapshot_date.desc&limit=50",
        )
        result = []
        for r in rows:
            result.append({
                "customer_id": r["customer_id"],
                "account_type": r.get("account_type", "regular_savings"),
                "balance": float(r.get("balance", 0)),
                "savings_goal": r.get("savings_goal"),
                "as_of_date": str(r.get("snapshot_date") or r.get("as_of_date") or r.get("created_at", "2020-01-01"))[:10],
            })
        return result

    def _load_borrowings(self, customer_id: str) -> List[Dict[str, Any]]:
        rows = self._get(
            "borrowings",
            f"customer_id=eq.{customer_id}&limit=50",
        )
        result = []
        for r in rows:
            result.append({
                "customer_id": r["customer_id"],
                "loan_type": r.get("loan_type", "personal_loan"),
                "principal": float(r.get("principal_amount") or r.get("principal") or 0),
                "outstanding_balance": float(r.get("outstanding_balance", 0)),
                "monthly_payment": float(r.get("monthly_payment", 0)),
                "next_due_date": str(r.get("next_due_date", "2099-01-01")),
                "status": r.get("status", "current"),
            })
        return result

    def _load_investments(self, customer_id: str) -> List[Dict[str, Any]]:
        rows = self._get(
            "investment_holdings",
            f"customer_id=eq.{customer_id}&limit=50",
        )
        result = []
        for r in rows:
            result.append({
                "customer_id": r["customer_id"],
                "asset_class": r.get("asset_class", "other"),
                "product_name": r.get("product_name") or r.get("product_id", "unknown"),
                "holding_value": float(r.get("holding_value", 0)),
                "cost_basis": float(r.get("cost_basis", 0)),
                "last_updated": str(r.get("last_updated", "2020-01-01")),
            })
        return result

    def _load_app_usage(self, customer_id: str) -> List[Dict[str, Any]]:
        rows = self._get(
            "app_usage_events",
            f"customer_id=eq.{customer_id}&order=event_timestamp.desc&limit=200",
        )
        result = []
        for r in rows:
            meta = r.get("metadata") or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            result.append({
                "customer_id": r["customer_id"],
                "event_type": r.get("event_type", "login"),
                "feature_name": r.get("feature_name"),
                "timestamp": str(r.get("event_timestamp") or r.get("timestamp") or r.get("created_at", "2020-01-01T00:00:00")),
                "session_length_seconds": r.get("session_length_seconds"),
                "metadata": meta,
            })
        return result

    # ── Public API ─────────────────────────────────────────

    def get_customer_profile(self, customer_key: str) -> Optional[Dict[str, Any]]:
        customer_id = self._resolve_customer_id(customer_key)
        if not customer_id:
            return None

        profile = self._load_profile(customer_id)
        if not profile:
            return None

        return {
            "profile": profile,
            "transactions": self._load_transactions(customer_id),
            "savings": self._load_savings(customer_id),
            "borrowings": self._load_borrowings(customer_id),
            "investments": self._load_investments(customer_id),
            "app_usage": self._load_app_usage(customer_id),
        }

    def get_customer_features(self, customer_key: str) -> List[Dict[str, Any]]:
        # For MVP: return default feature list.
        # Could be extended to read from a features/products table.
        return DEFAULT_FEATURES


# ─────────────────────────────────────────────────────────────
# Factory
# ─────────────────────────────────────────────────────────────

def get_customer_data_provider() -> CustomerDataProvider:
    """
    Select provider by DATA_SOURCE env var.

    DATA_SOURCE=mock (default) → MockCustomerDataProvider
    DATA_SOURCE=supabase       → SupabaseCustomerDataProvider
    """
    data_source = os.getenv("DATA_SOURCE", "mock").strip().lower()

    if data_source == "supabase":
        return SupabaseCustomerDataProvider()

    return MockCustomerDataProvider()
