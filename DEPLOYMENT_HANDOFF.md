# Developer Hand-Off Guide — C30 Digital Sales Hub & Gated LMS

This document is for the developer deploying the **C30 Digital Sales Hub & Gated Onboarding LMS** to production on **Google Cloud Run**.

The repository is built strictly to the specifications in `GATED_CONTENT_SPEC.md` and the `C30 Digital Brand Guide`.

---

## 🚀 What Has Already Been Built & Tested

1. **Public Lead Funnel (`/`)**:
   - Capture form: Legal Full Name, Direct Mobile, Primary Email, UTM tracking.
   - Redirects to `/intro` with session-tracked `lead_id`.
2. **Orientation Video & "Let's Work" Dispatch (`/intro`)**:
   - Streams from Google Cloud Storage (`INTRO_VIDEO_URL`).
   - Real-time video watch-time telemetry (`/api/track-video`).
   - "LET'S WORK" action button triggers immediate Slack webhook payload with candidate details.
3. **Slack Webhook Dispatch (`slack_service.py`)**:
   - Formatted Slack block alert posted directly into your private channel (already tested and verified).
4. **Security & Session Architecture (`auth.py`)**:
   - 32-byte single-use cryptographic tokens (stored only as SHA-256 hashes).
   - `GET /verify?t=TOKEN` does **not** spend token (prevents corporate bot link-burners).
   - `POST /verify` spends token, provisions session, sets `__session` cookie (`HttpOnly`, `SameSite=Lax`).
   - Per-request session + `active` status validation.
5. **Gated Onboarding Curriculum (`/onboarding` & `/lesson/<id>`)**:
   - Restricted to `status == "active"` members.
   - Modules, lessons, sanitized Markdown/HTML rendering (`nh3`), and progress telemetry.
6. **Admin Command Center (`/admin`)**:
   - Real-time lead CRM pipeline.
   - 1-Click candidate hiring (`POST /admin/leads/<id>/hire`) generating 24-hr single-use onboarding magic links.
7. **Production Containerization**:
   - `Dockerfile` using `python:3.12-slim` + `gunicorn` with Cloud Run `$PORT` support.
   - `.dockerignore` configured.
   - `requirements.txt` generated.

---

## 🛠️ Step-by-Step Production Deployment (Google Cloud Run)

### 1. Prerequisites for Developer
- Access to the target GCP Project:
  ```bash
  gcloud config set project <PROJECT_ID>
  ```
- APIs enabled:
  ```bash
  gcloud services enable run.googleapis.com \
                         firestore.googleapis.com \
                         storage.googleapis.com \
                         secretmanager.googleapis.com \
                         cloudbuild.googleapis.com
  ```

---

### 2. Service Account Setup (Least Privilege per Spec)

Create the Cloud Run runtime service account:
```bash
gcloud iam service-accounts create c30-hub-runtime \
    --display-name="C30 Hub Runtime Service Account"

# Firestore access
gcloud projects add-iam-policy-binding <PROJECT_ID> \
    --member="serviceAccount:c30-hub-runtime@<PROJECT_ID>.iam.gserviceaccount.com" \
    --role="roles/datastore.user"

# GCS Private Content Bucket access
gcloud storage buckets add-iam-policy-binding gs://<CONTENT_BUCKET> \
    --member="serviceAccount:c30-hub-runtime@<PROJECT_ID>.iam.gserviceaccount.com" \
    --role="roles/storage.objectViewer"

# Token Creator on ITSELF (Required for Cloud Run to sign GCS URLs without service account keys)
gcloud iam service-accounts add-iam-policy-binding \
    c30-hub-runtime@<PROJECT_ID>.iam.gserviceaccount.com \
    --member="serviceAccount:c30-hub-runtime@<PROJECT_ID>.iam.gserviceaccount.com" \
    --role="roles/iam.serviceAccountTokenCreator"
```

---

### 3. Environment Variables & Secrets

Configure the following environment variables on Cloud Run:

| Variable | Description | Example |
|---|---|---|
| `SECRET_KEY` | Flask cryptographic session key | Secure random string (or Secret Manager) |
| `APP_URL` | Production public URL | `https://apply.c30.digital` |
| `SLACK_WEBHOOK_URL` | Slack incoming webhook | Current verified URL is in `.env` |
| `GCP_PROJECT_ID` | GCP Project ID | `<YOUR_GCP_PROJECT>` |
| `GCS_BUCKET` | Cloud Storage bucket for video & content | `<YOUR_BUCKET>` |
| `INTRO_VIDEO_URL` | Cloud Storage path or signed URL | `https://storage.googleapis.com/<BUCKET>/intro.mp4` |
| `ADMIN_EMAILS` | Comma-separated admin emails | `colby@c30.digital,admin@c30.digital` |
| `USE_FIRESTORE` | Set to `true` to persist to Firestore Native | `true` |

---

### 4. Deploy Command

Deploy directly from the root directory:
```bash
gcloud run deploy c30-sales-hub \
    --source . \
    --region us-central1 \
    --service-account c30-hub-runtime@<PROJECT_ID>.iam.gserviceaccount.com \
    --allow-unauthenticated \
    --set-env-vars USE_FIRESTORE=true,GCP_PROJECT_ID=<PROJECT_ID>,APP_URL=https://<YOUR_DOMAIN>
```

---

### 5. Custom Domain Mapping

Map your subdomain (e.g. `join.c30.digital` or `apply.c30.digital`):
```bash
gcloud beta run domain-mappings create \
    --service c30-sales-hub \
    --domain apply.c30.digital \
    --region us-central1
```
Add the generated DNS CNAME/A records in your DNS provider (Cloudflare, Google Domains, etc.).

---

## 📁 Repository Structure

```
├── app.py                # Main Flask application & routes
├── auth.py               # Token crypto, sessions, __session cookie, decorators
├── database.py           # Dual-mode data layer (local store & Firestore Native)
├── slack_service.py      # Rich Slack block notification dispatcher
├── gcs_service.py        # GCS signed URL generator (IAM-based)
├── config.py             # Environment configurations
├── Dockerfile            # Production Docker image (Python 3.12-slim + gunicorn)
├── .dockerignore         # Build exclusions
├── requirements.txt      # Frozen pip dependencies
├── static/
│   ├── css/style.css     # C30 Digital Design System (0px radius, terminal aesthetic)
│   └── images/           # Transparent C30 Digital logos
└── templates/            # Jinja2 templates (index, intro, onboarding, lesson, admin, login)
```

---

## 🔍 Developer Support
- Health check route: `GET /healthz` returns `{"status": "healthy"}`.
- Local testing runner: `run.bat` (Windows) or `gunicorn app:app`.
