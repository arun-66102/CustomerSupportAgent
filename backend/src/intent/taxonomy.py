"""
Intent taxonomy for AppleSupport brand.
Each intent has a label, description, keywords, and risk level.
Risk levels: LOW, MEDIUM, HIGH
"""

INTENT_TAXONOMY = {
    "ios_update_issue": {
        "label": "iOS Update Issue",
        "description": "Customer reports problems after installing an iOS update — slowdowns, bugs, crashes, UI issues.",
        "keywords": ["update", "ios", "upgrade", "new version", "after update", "updated", "11", "12", "15", "16", "17"],
        "risk": "LOW",
        "examples": [
            "My phone is so slow after the iOS update",
            "The new update broke my apps",
            "Everything lags since I updated to iOS 17"
        ]
    },
    "battery_drain": {
        "label": "Battery Drain",
        "description": "Customer reports excessive or abnormal battery consumption.",
        "keywords": ["battery", "drain", "draining", "percent", "charge", "charging", "power"],
        "risk": "LOW",
        "examples": [
            "Battery drains so fast after update",
            "Used my phone for 2 minutes and it dropped 10%",
            "Battery life is terrible since iOS update"
        ]
    },
    "app_crash": {
        "label": "App Crash / Not Working",
        "description": "Customer reports that a specific app or apps are crashing or not functioning correctly.",
        "keywords": ["crash", "crashes", "crashing", "app", "broken", "not working", "stops", "closes", "force close"],
        "risk": "LOW",
        "examples": [
            "WhatsApp keeps crashing on my iPhone",
            "My apps stop working without warning",
            "App closes randomly"
        ]
    },
    "wifi_connectivity": {
        "label": "WiFi / Network Connectivity",
        "description": "Customer has issues with WiFi disconnection, internet speed, or network connection.",
        "keywords": ["wifi", "wi-fi", "internet", "connection", "connect", "network", "disconnects", "signal"],
        "risk": "LOW",
        "examples": [
            "WiFi keeps disconnecting after update",
            "Can't connect to the internet",
            "My iPhone drops WiFi randomly"
        ]
    },
    "device_performance": {
        "label": "Device Performance",
        "description": "Customer reports general slowness, freezing, or poor performance of the device.",
        "keywords": ["slow", "sluggish", "lag", "freeze", "frozen", "hang", "performance", "speed", "lags"],
        "risk": "LOW",
        "examples": [
            "My phone freezes every five minutes",
            "iPhone is super slow",
            "Everything takes ages to load"
        ]
    },
    "account_access": {
        "label": "Account Access / Login",
        "description": "Customer cannot log in, forgot password, or is locked out of their Apple ID or iCloud account.",
        "keywords": ["login", "log in", "sign in", "password", "locked out", "apple id", "icloud", "access", "forgot"],
        "risk": "MEDIUM",
        "examples": [
            "I can't log into my Apple ID",
            "Forgot my iCloud password",
            "Locked out of my account"
        ]
    },
    "account_security": {
        "label": "Account Security / Unauthorized Access",
        "description": "Customer reports unauthorized access, hacking, suspicious activity, or potential account compromise.",
        "keywords": ["hacked", "hack", "unauthorized", "suspicious", "someone else", "stolen", "compromise", "security", "breach"],
        "risk": "HIGH",
        "examples": [
            "Someone hacked my Apple ID",
            "Suspicious activity on my account",
            "Someone is using my iCloud without permission"
        ]
    },
    "billing_payment": {
        "label": "Billing / Payment Issue",
        "description": "Customer reports incorrect charges, failed payments, unwanted subscriptions, or refund requests.",
        "keywords": ["charge", "charged", "payment", "refund", "subscription", "billing", "money", "purchase", "price", "fee"],
        "risk": "HIGH",
        "examples": [
            "I was charged for an app I didn't buy",
            "Cancel my subscription and refund me",
            "Unknown charge on my account"
        ]
    },
    "hardware_issue": {
        "label": "Hardware Issue",
        "description": "Customer reports physical problems with device such as screen damage, buttons not working, camera issues.",
        "keywords": ["screen", "broken", "camera", "button", "speaker", "microphone", "physical", "cracked", "display"],
        "risk": "MEDIUM",
        "examples": [
            "My iPhone screen is cracked",
            "The camera on my phone is blurry",
            "Home button not working"
        ]
    },
    "general_question": {
        "label": "General Question / Feature Inquiry",
        "description": "Customer asks a general question about Apple products, features, or services.",
        "keywords": ["how", "what", "where", "when", "can i", "does", "feature", "support", "hours", "help"],
        "risk": "LOW",
        "examples": [
            "How do I enable dark mode?",
            "What are your support hours?",
            "Does iPhone support wireless charging?"
        ]
    }
}

# High-risk intents that always trigger escalation
HIGH_RISK_INTENTS = {k for k, v in INTENT_TAXONOMY.items() if v["risk"] == "HIGH"}
MEDIUM_RISK_INTENTS = {k for k, v in INTENT_TAXONOMY.items() if v["risk"] == "MEDIUM"}
LOW_RISK_INTENTS = {k for k, v in INTENT_TAXONOMY.items() if v["risk"] == "LOW"}

INTENT_LABELS = list(INTENT_TAXONOMY.keys())


def get_intent_risk(intent: str) -> str:
    """Return risk level for a given intent."""
    return INTENT_TAXONOMY.get(intent, {}).get("risk", "MEDIUM")


def get_intent_description(intent: str) -> str:
    """Return description for a given intent."""
    return INTENT_TAXONOMY.get(intent, {}).get("description", "Unknown intent")


def get_taxonomy_prompt_section() -> str:
    """Return a formatted string describing the taxonomy for LLM prompts."""
    lines = ["Available intents (name: description):"]
    for k, v in INTENT_TAXONOMY.items():
        lines.append(f"  - {k}: {v['description']}")
    return "\n".join(lines)
