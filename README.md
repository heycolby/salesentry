# 🚀 Sales Course & Gated Onboarding Hub

A full-stack, mobile-optimized funnel and members-only training portal built according to [`GATED_CONTENT_SPEC.md`](../GATED_CONTENT_SPEC.md).

---

## 🌟 How the Funnel Works

### 1. The Bio Link Funnel (Lead Generation)
1. **Bio Link Landing Page (`/`)**: 
   - Put this link in your Instagram, TikTok, Twitter/X bio.
   - High-converting, mobile-first design.
   - Captures: **Full Name**, **Email Address**, and **Phone Number**.
2. **Intro Video Page (`/intro`)**:
   - Applicant lands on your introductory/VSL video.
   - The video is streamed from your Google Cloud Storage bucket or MP4 URL.
   - Watch time is tracked automatically.
3. **Interactive "Let's Work" Action (`POST /api/lets-work`)**:
   - A pulsing, animated **"Let's Work"** button unlocks.
   - When the applicant clicks it, an **instant Slack notification** fires to your Slack channel with their name, clickable phone number, and video watch duration!
   - You can immediately call or text them from your phone.

---

### 2. Gated Onboarding & Course LMS (Hired Members)
1. **1-Click Hiring in Admin Portal (`/admin`)**:
   - In your Admin Hub, you see all applicants in real time.
   - When you decide to hire someone, click **"Hire & Give Training Link"**.
   - The system instantly promotes them to an `active` member and generates a secure, 24-hour single-use magic login link (`/verify?t=...`).
   - Copy and send it to them via SMS, WhatsApp, or email.
2. **Onboarding Portal (`/onboarding`)**:
   - Only accessible to verified active members and admins.
   - Structured into **Modules** and **Lessons** (video lessons, commission guides, objection scripts).
   - Tracks each agent's completion progress percentage.

---

## ⚡ Quick Start

### Option A: Double-Click Runner
Double-click `run.bat` located inside your Desktop folder `sales course`.

### Option B: Terminal Command
```bash
cd "C:\Users\Colbty\Desktop\sales course"
.\venv\Scripts\python.exe app.py
```
Open **`http://127.0.0.1:5000`** in your browser.

---

## ⚙️ Configuration (`.env`)

Edit `.env` (or configure live in `/admin` under Settings):

- **Slack Notifications**:
  ```env
  SLACK_WEBHOOK_URL=https://hooks.slack.com/services/T00/B00/XXXXX
  ```
  *(To create one: Go to api.slack.com/apps -> Create App -> Incoming Webhooks -> Activate and add to your channel)*.

- **Google Cloud Video**:
  ```env
  INTRO_VIDEO_URL=https://storage.googleapis.com/YOUR_BUCKET/intro.mp4
  # Or bucket name:
  GCS_BUCKET=your-bucket-name
  ```

- **Admin Login**:
  - The default admin email is `admin@example.com`.
  - To log into Admin, go to `/login`, enter `admin@example.com`, and click the sign-in link.
