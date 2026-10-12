import json
import os
import time
import uuid
import config

DATA_DIR = os.path.join(config.BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
STORE_FILE = os.path.join(DATA_DIR, "store.json")

# C30 Digital Onboarding Curriculum - Diagnostic & Architectural Protocol
DEFAULT_MODULES = [
    {
        "id": "module-1",
        "title": "PROTOCOL 01: System Architecture & Consultative Framework",
        "description": "Operational principles, compensation models, and high-ticket pipeline execution.",
        "order": 1,
        "lessons": [
            {
                "id": "lesson-1-1",
                "title": "01.1 Operational Command & Daily Execution Standards",
                "duration": "8 min",
                "type": "video",
                "video_url": "",
                "content_markdown": """# Operational Protocol: Daily Standards

C30 Digital operates as systems architects. Consultative sales agents execute systematic diagnoses of client operational bottlenecks rather than standard transactional pitches.

### Daily Execution Standard:
1. **08:30 Pipeline Triage**: Review inbound intake routing and qualify organizational fit.
2. **Consultative Touchpoints**: Multi-channel diagnostic touches within 12 hours of dispatch.
3. **Telemetry & Call Logs**: Systematically record operational diagnoses into internal CRM records immediately following each call.

> **Operational Standard**: Consistency in diagnostic qualification determines client retention and deal execution margin.
"""
            },
            {
                "id": "lesson-1-2",
                "title": "01.2 Compensation Architecture & Margin Acceleration",
                "duration": "12 min",
                "type": "article",
                "video_url": "",
                "content_markdown": """# Compensation Architecture

Compensation tiers reflect direct closed revenue contribution and gross deal margin.

- **Baseline Tier**: 15% net commission on closed enterprise contracts.
- **Volume Accelerator**: Closing 5+ qualified deployments within a calendar cycle elevates all transactions that month to 20% margin.
- **Disbursement Schedule**: Bi-weekly automated wire or direct deposit following contract execution.
"""
            }
        ]
    },
    {
        "id": "module-2",
        "title": "PROTOCOL 02: The Diagnostic Discovery Framework",
        "description": "Systematic evaluation of legacy software friction, manual admin leaks, and architecture gaps.",
        "order": 2,
        "lessons": [
            {
                "id": "lesson-2-1",
                "title": "02.1 The 5-Stage Diagnostic Framework",
                "duration": "15 min",
                "type": "video",
                "video_url": "",
                "content_markdown": """# The Diagnostic Discovery Framework

We never pitch before diagnosing. Inefficient organizations do not need generic persuasion; they need infrastructure.

### The 5 Diagnostic Stages:
1. **System Framing**: Establish agenda, operational focus, and mutual diagnostic criteria.
2. **Current Architecture**: Map existing legacy workflow and manual touchpoints.
3. **Structural Bottleneck**: Isolate where labor or margins leak (handoff delays, dispatch lag, redundant data entry).
4. **Economic Cost of Inaction**: Calculate monthly operational overhead caused by the current bottleneck.
5. **Prescription**: Prescribe targeted automation architecture or command center deployment.
"""
            },
            {
                "id": "lesson-2-2",
                "title": "02.2 Resolving Structural Objections",
                "duration": "18 min",
                "type": "video",
                "video_url": "",
                "content_markdown": """# Resolving Structural Objections

### Pattern 1: "We already have software for this."
*Diagnosis:* "Most organizations run multiple point solutions that fail to communicate. Where in your current workflow are staff manually copying data between systems?"

### Pattern 2: "We need to delay this until next quarter."
*Diagnosis:* "Delaying simply compounds the monthly margin leakage you identified in dispatch handoffs. If this maps to what you are observing in your operations, we can review the internal architecture now."
"""
            }
        ]
    },
    {
        "id": "module-3",
        "title": "PROTOCOL 03: Field Certification & Dispatch Activation",
        "description": "Verification of diagnostic mastery prior to active lead routing.",
        "order": 3,
        "lessons": [
            {
                "id": "lesson-3-1",
                "title": "03.1 Roleplay Evaluation & Account Provisioning",
                "duration": "5 min",
                "type": "article",
                "video_url": "",
                "content_markdown": """# Deployment Certification

To be activated for live candidate routing:
1. Review the diagnostic frameworks in Protocol 02.
2. Complete your 20-minute operational roleplay review with Colby.
3. Upon certification, CRM credentials and live pipeline access are provisioned.
"""
            }
        ]
    }
]

class LocalStore:
    def __init__(self):
        self._load()

    def _ensure_fresh(self):
        if os.path.exists(STORE_FILE):
            try:
                mtime = os.path.getmtime(STORE_FILE)
                if getattr(self, "_last_mtime", 0) != mtime:
                    with open(STORE_FILE, "r", encoding="utf-8") as f:
                        self.data = json.load(f)
                    self._last_mtime = mtime
            except Exception:
                pass

    def _load(self):
        if not os.path.exists(STORE_FILE):
            self.data = {
                "leads": {},
                "members": {},
                "login_tokens": {},
                "sessions": {},
                "modules": DEFAULT_MODULES,
                "settings": {
                    "slack_webhook_url": config.SLACK_WEBHOOK_URL,
                    "intro_video_url": config.INTRO_VIDEO_URL
                }
            }
            for admin_email in config.ADMIN_EMAILS:
                self.data["members"][admin_email] = {
                    "email": admin_email,
                    "name": "System Administrator",
                    "role": "admin",
                    "status": "active",
                    "created_at": time.time(),
                    "confirmed_at": time.time(),
                    "progress": {}
                }
            self._save()
        else:
            try:
                with open(STORE_FILE, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
                self._last_mtime = os.path.getmtime(STORE_FILE)
                # Ensure modules adhere to updated protocol
                self.data["modules"] = DEFAULT_MODULES
                self._save()
            except Exception:
                self.data = {"leads": {}, "members": {}, "login_tokens": {}, "sessions": {}, "modules": DEFAULT_MODULES, "settings": {}}
                self._save()

    def _save(self):
        with open(STORE_FILE, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2)
        if os.path.exists(STORE_FILE):
            self._last_mtime = os.path.getmtime(STORE_FILE)

    def create_lead(self, name: str, email: str, phone: str, utm_source: str = "") -> dict:
        self._ensure_fresh()
        lead_id = str(uuid.uuid4())
        normalized_email = email.strip().lower()
        lead = {
            "id": lead_id,
            "name": name.strip(),
            "email": normalized_email,
            "phone": phone.strip(),
            "utm_source": utm_source,
            "watched_seconds": 0,
            "clicked_lets_work": False,
            "status": "watching_intro",
            "created_at": time.time(),
            "updated_at": time.time()
        }
        self.data["leads"][lead_id] = lead
        self._save()
        return lead

    def get_lead(self, lead_id: str) -> dict:
        self._ensure_fresh()
        return self.data["leads"].get(lead_id)

    def get_lead_by_email(self, email: str) -> dict:
        self._ensure_fresh()
        normalized_email = email.strip().lower()
        for lead in self.data["leads"].values():
            if lead.get("email") == normalized_email:
                return lead
        return None

    def update_lead(self, lead_id: str, updates: dict) -> dict:
        self._ensure_fresh()
        if lead_id in self.data["leads"]:
            self.data["leads"][lead_id].update(updates)
            self.data["leads"][lead_id]["updated_at"] = time.time()
            self._save()
            return self.data["leads"][lead_id]
        return None

    def list_leads(self) -> list:
        self._ensure_fresh()
        leads = list(self.data["leads"].values())
        leads.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return leads

    def get_member(self, email: str) -> dict:
        self._ensure_fresh()
        return self.data["members"].get(email.strip().lower())

    def create_or_update_member(self, email: str, name: str = "", role: str = "member", status: str = "active", phone: str = "") -> dict:
        self._ensure_fresh()
        norm_email = email.strip().lower()
        now = time.time()
        member = self.data["members"].get(norm_email)
        if not member:
            member = {
                "email": norm_email,
                "name": name or "Member",
                "phone": phone,
                "role": role,
                "status": status,
                "created_at": now,
                "confirmed_at": now if status == "active" else None,
                "last_login_at": None,
                "progress": {}
            }
        else:
            if name: member["name"] = name
            if phone: member["phone"] = phone
            if role: member["role"] = role
            if status: member["status"] = status
            if status == "active" and not member.get("confirmed_at"):
                member["confirmed_at"] = now
        self.data["members"][norm_email] = member
        self._save()
        return member

    def list_members(self) -> list:
        self._ensure_fresh()
        members = list(self.data["members"].values())
        members.sort(key=lambda x: x.get("created_at", 0), reverse=True)
        return members

    def update_member_progress(self, email: str, lesson_id: str, completed: bool = True) -> dict:
        self._ensure_fresh()
        member = self.get_member(email)
        if member:
            if "progress" not in member:
                member["progress"] = {}
            member["progress"][lesson_id] = completed
            self.data["members"][email.strip().lower()] = member
            self._save()
            return member
        return None

    def save_token(self, token_hash: str, email: str, purpose: str, expires_at: float):
        self._ensure_fresh()
        self.data["login_tokens"][token_hash] = {
            "email": email.strip().lower(),
            "purpose": purpose,
            "expires_at": expires_at,
            "used_at": None
        }
        self._save()

    def get_token(self, token_hash: str) -> dict:
        self._ensure_fresh()
        return self.data["login_tokens"].get(token_hash)

    def mark_token_used(self, token_hash: str):
        self._ensure_fresh()
        if token_hash in self.data["login_tokens"]:
            self.data["login_tokens"][token_hash]["used_at"] = time.time()
            self._save()

    def save_session(self, session_hash: str, email: str, expires_at: float):
        self._ensure_fresh()
        self.data["sessions"][session_hash] = {
            "email": email.strip().lower(),
            "created_at": time.time(),
            "expires_at": expires_at
        }
        self._save()

    def get_session(self, session_hash: str) -> dict:
        self._ensure_fresh()
        return self.data["sessions"].get(session_hash)

    def delete_session(self, session_hash: str):
        self._ensure_fresh()
        if session_hash in self.data["sessions"]:
            del self.data["sessions"][session_hash]
            self._save()

    def get_modules(self) -> list:
        self._ensure_fresh()
        return self.data.get("modules", DEFAULT_MODULES)

    def save_modules(self, modules: list):
        self.data["modules"] = modules
        self._save()

    def get_lesson(self, lesson_id: str) -> tuple:
        self._ensure_fresh()
        for mod in self.get_modules():
            for les in mod.get("lessons", []):
                if les.get("id") == lesson_id:
                    return mod, les
        return None, None

    def get_settings(self) -> dict:
        self._ensure_fresh()
        return self.data.get("settings", {})

    def update_settings(self, updates: dict):
        self._ensure_fresh()
        if "settings" not in self.data:
            self.data["settings"] = {}
        self.data["settings"].update(updates)
        self._save()

db = LocalStore()
