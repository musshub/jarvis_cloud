from typing import Dict, Any, List
from datetime import datetime

DEFAULT_MEMORY: Dict[str, Any] = {
    "rules": [
        {"id": "backup_before_edit", "text": "Always create a backup before editing any project file.", "mandatory": True},
        {"id": "prefer_full_files", "text": "When giving code updates, prefer complete full files instead of tiny patches.", "mandatory": True},
        {"id": "avoid_firestore_indexes", "text": "Avoid Firestore composite indexes unless absolutely necessary.", "mandatory": True},
        {"id": "confirm_sensitive_actions", "text": "Ask confirmation before sending WhatsApp messages, deleting data, deploying, installing APK, or changing system settings.", "mandatory": True},
    ],
    "projects": {},
    "personal_profile": {"name": "Shubham", "main_project": "Nirmansutra ERP", "style": "Talkative, practical, Hindi-English mixed, direct guidance."},
}

def now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"

def ensure_user_memory(memory_store: Dict[str, Dict[str, Any]], user_id: str) -> Dict[str, Any]:
    if user_id not in memory_store:
        memory_store[user_id] = {
            "rules": list(DEFAULT_MEMORY["rules"]),
            "projects": {},
            "personal_profile": dict(DEFAULT_MEMORY["personal_profile"]),
            "saved_facts": [],
            "updated_at": now_iso(),
        }
    memory_store[user_id].setdefault("rules", list(DEFAULT_MEMORY["rules"]))
    memory_store[user_id].setdefault("projects", {})
    memory_store[user_id].setdefault("personal_profile", dict(DEFAULT_MEMORY["personal_profile"]))
    memory_store[user_id].setdefault("saved_facts", [])
    return memory_store[user_id]

def add_memory_rule(memory_store: Dict[str, Dict[str, Any]], user_id: str, rule_text: str) -> Dict[str, Any]:
    memory = ensure_user_memory(memory_store, user_id)
    existing = [r for r in memory.get("rules", []) if r.get("text", "").lower().strip() == rule_text.lower().strip()]
    if existing:
        return {"ok": True, "already_exists": True, "rule": existing[0]}
    rule = {"id": "rule_" + str(abs(hash(rule_text)))[:10], "text": rule_text.strip(), "mandatory": True, "created_at": now_iso()}
    memory["rules"].append(rule)
    memory["updated_at"] = now_iso()
    return {"ok": True, "already_exists": False, "rule": rule}

def memory_to_prompt(memory: Dict[str, Any]) -> str:
    lines: List[str] = []
    lines.append("USER PROFILE:")
    for k, v in memory.get("personal_profile", {}).items():
        lines.append(f"- {k}: {v}")
    lines.append("\nMANDATORY RULES:")
    for rule in memory.get("rules", []):
        lines.append(f"- {rule.get('text')}")
    lines.append("\nKNOWN PROJECTS:")
    projects = memory.get("projects", {})
    if not projects:
        lines.append("- No saved project paths yet.")
    for project_id, data in projects.items():
        lines.append(f"- {project_id}: {data.get('root_path')} ({data.get('project_type', 'unknown')})")
    return "\n".join(lines)
