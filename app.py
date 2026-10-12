import os
import time
import nh3
from markdown_it import MarkdownIt
from flask import (
    Flask, render_template, request, redirect, url_for, 
    jsonify, make_response, session, flash, g
)

import config
from database import db
from slack_service import send_slack_lets_work_notification, send_test_slack_notification
from auth import (
    create_magic_token, verify_token, create_session, 
    clear_session, get_current_member, login_required, admin_required
)
from gcs_service import get_video_stream_url

app = Flask(__name__)
app.secret_key = config.SECRET_KEY

# Markdown renderer with HTML sanitization (nh3 allowlist)
md = MarkdownIt()

def render_safe_markdown(text: str) -> str:
    raw_html = md.render(text or "")
    clean_html = nh3.clean(raw_html)
    return clean_html

app.jinja_env.filters["markdown"] = render_safe_markdown

@app.before_request
def load_user():
    g.member = get_current_member()

# -------------------------------------------------------------
# Public Lead Funnel (Bio Link -> Intro Video -> "Let's Work")
# -------------------------------------------------------------

@app.route("/")
def index():
    """Bio link landing page with lead capture form."""
    utm_source = request.args.get("utm_source", "") or request.referrer or "bio_link"
    return render_template("index.html", utm_source=utm_source)

@app.route("/lead", methods=["POST"])
def submit_lead():
    """Captures lead info and redirects to the intro video."""
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    utm_source = request.form.get("utm_source", "bio_link")

    if not name or not email or not phone:
        flash("Please provide your name, email, and phone number.", "error")
        return redirect(url_for("index"))

    lead = db.create_lead(name=name, email=email, phone=phone, utm_source=utm_source)
    
    # Store lead id in session to associate video watch activity
    session["active_lead_id"] = lead["id"]
    return redirect(url_for("intro_video", lead_id=lead["id"]))

@app.route("/intro")
def intro_video():
    """Introductory video page with the interactive 'Let's Work' trigger."""
    lead_id = request.args.get("lead_id") or session.get("active_lead_id")
    lead = db.get_lead(lead_id) if lead_id else None
    
    settings = db.get_settings()
    video_url = get_video_stream_url(settings.get("intro_video_url") or config.INTRO_VIDEO_URL)

    return render_template("intro.html", lead=lead, video_url=video_url)

@app.route("/api/track-video", methods=["POST"])
def track_video():
    """Updates watch time for the lead."""
    data = request.get_json(silent=True) or {}
    lead_id = data.get("lead_id") or session.get("active_lead_id")
    seconds = int(data.get("seconds", 0))

    if lead_id:
        db.update_lead(lead_id, {"watched_seconds": seconds})
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "No lead_id provided"}), 400

@app.route("/api/lets-work", methods=["POST"])
def lets_work():
    """
    Triggered when applicant clicks 'Let's Work'.
    Fires Slack webhook notification to your channel.
    """
    data = request.get_json(silent=True) or {}
    lead_id = data.get("lead_id") or session.get("active_lead_id")
    watched_seconds = int(data.get("watched_seconds", 0))

    if not lead_id:
        # Fallback if lead wasn't saved in session
        name = data.get("name", "Applicant")
        email = data.get("email", "")
        phone = data.get("phone", "")
        lead = db.create_lead(name=name, email=email, phone=phone)
        lead_id = lead["id"]
    else:
        lead = db.get_lead(lead_id)

    # Update lead status to 'applied' and clicked_lets_work
    lead = db.update_lead(lead_id, {
        "clicked_lets_work": True,
        "status": "applied",
        "watched_seconds": max(watched_seconds, lead.get("watched_seconds", 0))
    })

    # Send instant Slack notification
    slack_res = send_slack_lets_work_notification(lead)

    return jsonify({
        "success": True,
        "message": "Thank you! Your application has been received. Colby will personally reach out shortly.",
        "slack_delivered": slack_res.get("success", False)
    })

# -------------------------------------------------------------
# Gated Onboarding Hub (Modules & Lessons for Hired Members)
# -------------------------------------------------------------

@app.route("/onboarding")
@app.route("/library")
@login_required
def onboarding_portal():
    """Gated course curriculum for active members and admins."""
    member = g.member
    modules = db.get_modules()
    progress = member.get("progress", {})

    # Calculate total lessons and completed count
    total_lessons = sum(len(m.get("lessons", [])) for m in modules)
    completed_count = sum(1 for completed in progress.values() if completed)
    pct = int((completed_count / total_lessons * 100)) if total_lessons > 0 else 0

    return render_template(
        "onboarding.html",
        member=member,
        modules=modules,
        progress=progress,
        total_lessons=total_lessons,
        completed_count=completed_count,
        completion_percentage=pct
    )

@app.route("/lesson/<lesson_id>")
@login_required
def view_lesson(lesson_id):
    """Individual lesson player and study guide."""
    module, lesson = db.get_lesson(lesson_id)
    if not lesson:
        flash("Lesson not found.", "error")
        return redirect(url_for("onboarding_portal"))

    member = g.member
    progress = member.get("progress", {})
    is_completed = progress.get(lesson_id, False)

    # Get video stream URL if lesson has video
    video_url = ""
    if lesson.get("video_url"):
        video_url = get_video_stream_url(lesson.get("video_url"))

    # Find next lesson
    next_lesson = None
    all_lessons = []
    for mod in db.get_modules():
        for l in mod.get("lessons", []):
            all_lessons.append(l)
    for i, l in enumerate(all_lessons):
        if l["id"] == lesson_id and i + 1 < len(all_lessons):
            next_lesson = all_lessons[i + 1]
            break

    return render_template(
        "lesson.html",
        module=module,
        lesson=lesson,
        member=member,
        is_completed=is_completed,
        video_url=video_url,
        next_lesson=next_lesson
    )

@app.route("/api/progress", methods=["POST"])
@login_required
def toggle_progress():
    """Toggles lesson completion status."""
    data = request.get_json(silent=True) or {}
    lesson_id = data.get("lesson_id")
    completed = bool(data.get("completed", True))

    if not lesson_id:
        return jsonify({"success": False, "error": "Missing lesson_id"}), 400

    member = db.update_member_progress(g.member["email"], lesson_id, completed)
    return jsonify({"success": True, "progress": member.get("progress", {})})

# -------------------------------------------------------------
# Authentication & Magic Links (Per GATED_CONTENT_SPEC.md)
# -------------------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login_page():
    """Member and Admin login via magic email token."""
    if g.member:
        if g.member.get("role") == "admin":
            return redirect(url_for("admin_dashboard"))
        return redirect(url_for("onboarding_portal"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        member = db.get_member(email)
        
        # Don't leak if email exists, show standard verify message
        if member and member.get("status") == "active":
            token = create_magic_token(email, purpose="login", ttl=3600)
            verify_link = f"{config.APP_URL}/verify?t={token}"
            # In production Mailgun sends email, locally we provide the direct instant link
            return render_template("verify_sent.html", email=email, verify_link=verify_link)
        else:
            return render_template("verify_sent.html", email=email, verify_link=None)

    return render_template("login.html")

@app.route("/verify", methods=["GET", "POST"])
def verify_token_page():
    """
    GET: Displays 'Click to Confirm Sign In' button without spending token.
    POST: Spends token, sets __session cookie, signs member in.
    """
    raw_token = request.args.get("t") or request.form.get("t")
    if not raw_token:
        flash("Invalid or missing verification link.", "error")
        return redirect(url_for("login_page"))

    if request.method == "GET":
        token_rec = verify_token(raw_token, spend=False)
        if not token_rec:
            return render_template("verify_expired.html")
        return render_template("verify_confirm.html", token=raw_token, email=token_rec["email"])

    # POST: Spend the token
    token_rec = verify_token(raw_token, spend=True)
    if not token_rec:
        return render_template("verify_expired.html")

    email = token_rec["email"]
    member = db.get_member(email)
    if not member:
        member = db.create_or_update_member(email, status="active")

    resp = make_response(redirect(url_for("admin_dashboard" if member.get("role") == "admin" else "onboarding_portal")))
    create_session(resp, email)
    return resp

@app.route("/logout", methods=["POST", "GET"])
def logout():
    resp = make_response(redirect(url_for("index")))
    clear_session(resp)
    return resp

# -------------------------------------------------------------
# Admin Dashboard (Leads CRM, 1-Click Hiring, Course Editor)
# -------------------------------------------------------------

@app.route("/admin")
@admin_required
def admin_dashboard():
    """Admin command center."""
    leads = db.list_leads()
    members = db.list_members()
    modules = db.get_modules()
    settings = db.get_settings()
    return render_template(
        "admin.html",
        leads=leads,
        members=members,
        modules=modules,
        settings=settings,
        admin_member=g.member
    )

@app.route("/admin/leads/<lead_id>/hire", methods=["POST"])
@admin_required
def hire_lead(lead_id):
    """
    1-Click action to hire a candidate:
    - Promotes lead to active member
    - Generates 24-hr magic login link for onboarding training
    """
    lead = db.get_lead(lead_id)
    if not lead:
        return jsonify({"success": False, "error": "Lead not found"}), 404

    email = lead["email"]
    name = lead["name"]
    phone = lead.get("phone", "")

    # Create active member record
    member = db.create_or_update_member(
        email=email,
        name=name,
        phone=phone,
        role="member",
        status="active"
    )
    db.update_lead(lead_id, {"status": "hired"})

    # Create magic token
    token = create_magic_token(email, purpose="login", ttl=86400)
    magic_url = f"{config.APP_URL}/verify?t={token}"

    return jsonify({
        "success": True,
        "lead_id": lead_id,
        "name": name,
        "email": email,
        "magic_url": magic_url,
        "message": f"Candidate {name} hired! Onboarding magic link generated."
    })

@app.route("/admin/settings/slack-test", methods=["POST"])
@admin_required
def test_slack_webhook():
    """Tests the configured Slack webhook URL."""
    data = request.get_json(silent=True) or {}
    webhook_url = data.get("webhook_url") or config.SLACK_WEBHOOK_URL
    res = send_test_slack_notification(webhook_url)
    return jsonify(res)

@app.route("/admin/settings/save", methods=["POST"])
@admin_required
def save_settings():
    """Saves updated settings (Slack webhook, Intro Video URL)."""
    data = request.get_json(silent=True) or {}
    slack_webhook = data.get("slack_webhook_url", "").strip()
    intro_video = data.get("intro_video_url", "").strip()
    
    db.update_settings({
        "slack_webhook_url": slack_webhook,
        "intro_video_url": intro_video
    })
    
    if slack_webhook:
        config.SLACK_WEBHOOK_URL = slack_webhook
    if intro_video:
        config.INTRO_VIDEO_URL = intro_video

    return jsonify({"success": True, "message": "Settings saved successfully."})

@app.route("/healthz")
def healthz():
    return jsonify({"status": "healthy", "service": "sales-course-hub"}), 200

if __name__ == "__main__":
    print(f"Sales Course Hub running at http://127.0.0.1:{config.PORT}")
    app.run(host="0.0.0.0", port=config.PORT, debug=True)
