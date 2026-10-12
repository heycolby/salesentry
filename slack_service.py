import json
import logging
import requests
import config

logger = logging.getLogger(__name__)

def send_slack_lets_work_notification(lead: dict) -> dict:
    """
    Sends a rich Slack notification when an applicant finishes the intro video
    and clicks 'Let's Work'.
    """
    webhook_url = config.SLACK_WEBHOOK_URL
    name = lead.get("name", "Unknown Applicant")
    email = lead.get("email", "Not provided")
    phone = lead.get("phone", "Not provided")
    watched_time = lead.get("watched_seconds", 0)
    lead_id = lead.get("id", "")

    # Format phone link
    phone_clean = "".join(ch for ch in phone if ch.isdigit() or ch == "+")
    phone_display = f"<{f'tel:{phone_clean}' if phone_clean else '#'}|{phone}>" if phone else "Not provided"

    payload = {
        "text": f"🔥 New 'Let's Work' Lead: {name} ({phone})",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🔥 New Applicant Ready To Work!",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{name}* just completed the intro video and hit *'Let's Work'*. Reach out to them personally below:"
                }
            },
            {
                "type": "section",
                "fields": [
                    {
                        "type": "mrkdwn",
                        "text": f"*👤 Name:*\n{name}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*📞 Phone:*\n{phone_display}"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*✉️ Email:*\n<{f'mailto:{email}'}|{email}>"
                    },
                    {
                        "type": "mrkdwn",
                        "text": f"*⏱️ Video Watched:*\n{watched_time} seconds"
                    }
                ]
            },
            {
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {
                            "type": "plain_text",
                            "text": "Open Admin Dashboard",
                            "emoji": True
                        },
                        "url": f"{config.APP_URL}/admin",
                        "style": "primary"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"Lead ID: `{lead_id}` • Sales Course Lead Funnel"
                    }
                ]
            }
        ]
    }

    if not webhook_url:
        logger.warning("SLACK_WEBHOOK_URL is not set in .env. Notification logged locally.")
        return {
            "success": False, 
            "error": "No SLACK_WEBHOOK_URL configured yet. Go to /admin or edit .env to add your webhook."
        }

    try:
        response = requests.post(
            webhook_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        if response.status_code == 200:
            return {"success": True}
        else:
            logger.error(f"Slack webhook failed: {response.status_code} - {response.text}")
            return {"success": False, "error": f"Slack error: {response.status_code} {response.text}"}
    except Exception as e:
        logger.exception("Failed to send Slack notification")
        return {"success": False, "error": str(e)}

def send_test_slack_notification(webhook_url: str = None) -> dict:
    """Sends a test ping to Slack to verify incoming webhook."""
    target_url = webhook_url or config.SLACK_WEBHOOK_URL
    if not target_url:
        return {"success": False, "error": "No webhook URL provided."}

    payload = {
        "text": "✅ Sales Course Funnel Slack Integration Connected Successfully!",
        "blocks": [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "✅ Slack Webhook Verified!",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "Your Sales Course funnel is now connected. Whenever a candidate watches the video and clicks *'Let's Work'*, an instant alert will post right here."
                }
            }
        ]
    }

    try:
        res = requests.post(
            target_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=8
        )
        if res.status_code == 200:
            return {"success": True}
        return {"success": False, "error": f"Slack returned {res.status_code}: {res.text}"}
    except Exception as e:
        return {"success": False, "error": str(e)}
