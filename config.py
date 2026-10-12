import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Server Settings
SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-sales-course-2026-super-secure")
PORT = int(os.getenv("PORT", 5000))
APP_URL = os.getenv("APP_URL", f"http://127.0.0.1:{PORT}")

# Slack Integration
# Paste your incoming webhook URL here (e.g., https://hooks.slack.com/services/...)
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_CHANNEL_ID = os.getenv("SLACK_CHANNEL_ID", "#sales-agents")

# Google Cloud Platform Settings
GCP_PROJECT_ID = os.getenv("GCP_PROJECT_ID", "")
GCS_BUCKET = os.getenv("GCS_BUCKET", "")
# Default or initial video URL (can be a direct GCS URL, signed URL, or MP4)
INTRO_VIDEO_URL = os.getenv("INTRO_VIDEO_URL", "")

# Admin Security
ADMIN_EMAILS = [
    email.strip().lower() 
    for email in os.getenv("ADMIN_EMAILS", "admin@example.com").split(",") 
    if email.strip()
]

# Database Mode (automatically uses Firestore if GCP_PROJECT_ID and credentials are set, otherwise local JSON store)
USE_FIRESTORE = bool(os.getenv("USE_FIRESTORE", "false").lower() == "true" and GCP_PROJECT_ID)
