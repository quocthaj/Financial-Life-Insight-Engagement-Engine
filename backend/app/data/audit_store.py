import json
import os
from typing import List, Dict, Any

DB_PATH = os.path.join(os.path.dirname(__file__), "audit_db.json")

def load_audit_logs() -> List[Dict[str, Any]]:
    if not os.path.exists(DB_PATH):
        return []
    try:
        with open(DB_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("load_audit_logs exception:", str(e))
        return []

def save_audit_logs(logs: List[Dict[str, Any]]):
    try:
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print("save_audit_logs exception:", str(e))
        pass

def add_audit_entries(entries: List[Dict[str, Any]]):
    current = load_audit_logs()
    # Filter out duplicates to avoid duplicate logs in DB when re-running
    existing_ids = {e.get("trace_id") for e in current}
    new_entries = [e for e in entries if e.get("trace_id") not in existing_ids]
    
    # Prepend new entries so that the latest logs appear first
    current = new_entries + current
    save_audit_logs(current)

def clear_audit_logs():
    save_audit_logs([])
