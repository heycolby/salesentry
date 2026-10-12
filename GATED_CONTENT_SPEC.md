# Gated Content Hub: Build Spec (Python + GCP)

Handoff document for building a members-only content site. It is self-contained: nothing here depends on any other codebase. Replace placeholders like `<PROJECT_ID>` and `<DOMAIN>` with real values.

## Goal

A subdomain where marketing/sales publishes digital content, with **everything behind a free, email-verified membership**.

Visitor flow:
1. Enter your email
2. Verify your address
3. Get access to the content

Decisions already made:
- **Free membership.** The gate is a verified email. No payments. (Leave room to add a paid tier later; see the end.)
- **Content types:** PDFs, Markdown and Word (`.docx`) documents, and video.
- **The head of marketing publishes the content himself**, so publishing must work through a simple admin page. No code, git or command line.
- Sender domain, subdomain name and project names are not decided yet. Keep them as configuration (environment variables), never hardcoded.

## Recommended stack

| Concern | Choice |
|---|---|
| App | **Python 3.12 + Flask**, server-rendered with Jinja templates, one Cloud Run service. No JS framework needed. |
| Hosting | **Cloud Run** (public, `<SUBDOMAIN>.<DOMAIN>` via a domain mapping or load balancer) |
| Data | **Firestore (Native mode)** |
| Content files | **Cloud Storage**, a private bucket (uniform bucket-level access, public access prevented) |
| Email | **Mailgun** HTTP API (or any provider with an HTTP API) |
| Secrets | **Secret Manager** (Mailgun key, app secret, Slack bot token). Never plaintext env vars. |
| Slack invites | A small **Cloud Function (2nd gen) with an Eventarc Firestore trigger** on `members/{email}` (see "Slack community channel") |
| Containers | Artifact Registry + Cloud Build (or `gcloud run deploy --source .`) |
| Logging/alerts | Cloud Logging, plus an uptime check on `/healthz` |
| Optional | Cloud Scheduler (cleanup jobs), Transcoder API (adaptive video, later), Terraform for everything above |

Python libraries: `flask`, `gunicorn`, `google-cloud-firestore`, `google-cloud-storage`, `requests`, `markdown-it-py` or `markdown`, `mammoth` (docx to HTML), `nh3` (HTML sanitizing), `email-validator`.

## Service accounts (least privilege)

- **`hub-runtime`** (Cloud Run identity): Firestore `datastore.user`, Storage `objectViewer` + `objectCreator` on the content bucket, Secret Manager `secretAccessor` on its secrets, and `iam.serviceAccountTokenCreator` **on itself**. That last role is required to sign GCS URLs on Cloud Run, because there is no key file (see "Signed URLs").
- No service account keys anywhere. Application Default Credentials only.

## Data model (Firestore)

`members/{normalized_email}`
- `email`, `status`: `pending` | `active` | `unsubscribed` | `bounced` | `complained`
- `role`: `member` | `admin`
- `sid`: stable random id used in unsubscribe links (never the email itself)
- `created_at`, `confirmed_at`, `last_login_at`, `confirm_sent_at`
- `source`: `{utm_source, utm_medium, utm_campaign, referrer, landing_path}` captured at signup
- `plan`: `"free"` (reserved)
- `slack_invite`: `none` | `sent` | `failed` | `removed`, plus `slack_invited_at` and `slack_error` (last failure reason)

`login_tokens/{sha256(token)}`: `email`, `purpose` (`verify` | `login`), `expires_at`, `used_at`. Raw tokens are never stored.

`sessions/{sha256(session_id)}`: `email`, `created_at`, `expires_at`. Server-side sessions so they can be revoked.

`content/{slug}`
- `title`, `summary`, `type`: `pdf` | `article` | `document` | `video`
- `gcs_path` (original file), `html` or `html_gcs_path` (rendered Markdown/docx, already sanitized)
- `published` (bool), `published_at`, `created_by`, `tags`, `thumbnail_gcs_path`

`rate_limits/{key}`: counters for signup and login throttling.

## HTTP routes

Public:
- `GET /`: landing page with the email form and a teaser of what members get
- `POST /join`: start signup
- `GET /verify?t=TOKEN`: shows a confirm button only (does **not** spend the token)
- `POST /verify`: spends the token; activates and signs in the member
- `POST /login`: returning member requests a sign-in link
- `GET /unsubscribe?sid=...`, `POST /unsubscribe`: unsubscribe, including RFC 8058 one-click
- `POST /webhooks/mailgun`: bounce/complaint/unsubscribe events (verify Mailgun's HMAC signature)
- `GET /healthz`

Members (require a valid session AND `status == "active"`, checked on every request):
- `GET /library`: list of content
- `GET /c/<slug>`: view an article/document, or a player page for video
- `GET /download/<slug>`: 302 to a short-lived signed URL
- `POST /logout`

Admin (member with `role == "admin"`):
- `GET /admin`: content list
- `POST /admin/uploads/start`: returns a signed **resumable upload URL** so the browser uploads straight to GCS
- `POST /admin/content`: create/update a content record after upload, rendering Markdown/docx
- `POST /admin/content/<slug>/publish` and `/unpublish`
- `GET /admin/members`: simple member list with counts and CSV export

## Core logic (Python sketches)

```python
# --- tokens: random, single-use, stored hashed ---
import secrets, hashlib, time

def new_token(email, purpose, ttl=900):
    raw = secrets.token_urlsafe(32)
    h = hashlib.sha256(raw.encode()).hexdigest()
    db.collection("login_tokens").document(h).set(
        {"email": email, "purpose": purpose, "expires_at": time.time() + ttl, "used_at": None})
    return raw  # goes in the email link only

@firestore.transactional
def spend_token(txn, ref):
    snap = ref.get(transaction=txn)
    d = snap.to_dict() if snap.exists else None
    if not d or d["used_at"] or d["expires_at"] < time.time():
        return None
    txn.update(ref, {"used_at": time.time()})
    return d
# POST /verify: hash the submitted token, look it up, spend it in a transaction.
# A wrong/expired/used token returns the same generic page (no oracle).

# --- sessions ---
def create_session(email, days=90):
    sid = secrets.token_urlsafe(32)
    db.collection("sessions").document(sha256(sid)).set(
        {"email": email, "created_at": now(), "expires_at": now() + days*86400})
    resp.set_cookie("__session", sid, max_age=days*86400,
                    httponly=True, secure=True, samesite="Lax")
    # Cloud Run / Firebase Hosting only forward a cookie named `__session`

def current_member():
    sid = request.cookies.get("__session")
    if not sid: return None
    s = db.collection("sessions").document(sha256(sid)).get()
    if not s.exists or s.get("expires_at") < now(): return None
    m = db.collection("members").document(s.get("email")).get()
    return m.to_dict() if m.exists and m.get("status") == "active" else None  # revoke = instant
```

`POST /join`:
1. Normalize the email (`email-validator`, lowercase, trim). Reject honeypot-filled forms silently (return the same success page).
2. Rate limit: max N signups per IP per hour (hash the IP) and a per-email resend cooldown (for example 2 minutes). Use Firestore transactions for the counters.
3. If the member is already `active`, send a normal sign-in link instead (do not reveal whether the address exists; show the same "check your email" page).
4. Else upsert `members/{email}` as `pending`, store UTM/referrer in `source`, create a `verify` token, send the email.

`POST /verify`: spend the token; if `purpose == "verify"` set `status = "active"` and `confirmed_at`; create a session; redirect to `/library`. **Verification and sign-in happen in one step.**

Why `GET /verify` must not spend the token: corporate mail scanners and link previewers fetch URLs automatically and would burn the single-use token before the person clicks. Only a `POST` from the button spends it.

### Signed URLs (important on Cloud Run)

Cloud Run has no private key file, so sign through the IAM API:

```python
import google.auth
from google.auth.transport import requests as ga_requests
creds, _ = google.auth.default()
creds.refresh(ga_requests.Request())
url = blob.generate_signed_url(
    version="v4", expiration=timedelta(minutes=15), method="GET",
    service_account_email=creds.service_account_email,
    access_token=creds.token,
    response_disposition='attachment; filename="..."')  # only for downloads
```

Signed URLs support HTTP range requests, so a plain `<video src="<signed url>" controls>` can seek. Sign a fresh URL each time a gated page renders; use a short TTL (15 minutes, longer for video, for example 2 hours, so playback is not cut off).

### Content rendering and publishing

- **Upload path:** the admin page requests a signed resumable upload URL and the browser uploads straight to GCS. Do not route large files through Cloud Run (request size limits make big videos fail).
- **Markdown:** render with a Markdown library, then **sanitize with `nh3`** (allowlist tags/attributes; strip scripts, event handlers, `javascript:` URLs). Store the sanitized HTML.
- **Word (`.docx`):** convert to HTML with `mammoth`, sanitize the same way, store the HTML, and keep the original for download.
- **PDF:** stored as is; offer an in-page viewer and a download button.
- **Video:** stored as is (MP4/H.264 recommended). Player page uses a signed URL. For adaptive streaming later, add the Transcoder API to produce HLS, still stored in the private bucket.
- Never render admin- or user-supplied HTML unsanitized; treat every upload as untrusted.

### Admin access

The same email-verification login, with an `ADMIN_EMAILS` allowlist (config or a Firestore document) granting `role = "admin"`. Admin routes check the role server-side on every request. Optionally put the `/admin` path behind Identity-Aware Proxy later.

### Email

- Send through the Mailgun HTTP API from a verified sending domain (SPF + DKIM + DMARC configured). Plain text and HTML versions.
- Every email includes `List-Unsubscribe` and `List-Unsubscribe-Post: List-Unsubscribe=One-Click` headers, plus a visible unsubscribe link and a physical postal address in the footer.
- Mailgun webhook events (`failed` permanent, `complained`, `unsubscribed`) update the member's `status`. Verify the webhook signature (HMAC of timestamp + token with the signing key) with a constant-time compare.
- Transactional emails (verify/sign-in) and later marketing emails should be easy to separate by sender.

## Slack community channel (#sales-agents)

Requirement: when someone becomes an active member, they are also **invited to the `#sales-agents` Slack channel**, in addition to getting content access.

**Use Slack Connect, not a workspace invite.** Members are outside the organization's Slack workspace. Inviting them as full workspace members would expose the member directory and every public channel to strangers, and Slack offers no general API to invite arbitrary emails into a workspace (the admin invite API is Enterprise Grid only). Slack Connect sends a channel-scoped email invite; accepting it adds the person to that one channel only and nothing else. Consequences to plan for (verify against Slack's current docs before building):
- Slack Connect invites require a **paid Slack plan** on the workspace that owns the channel. The invitee needs a Slack account/workspace of their own (they can create a free one), which adds friction, so some members will never accept.
- A shared channel has limits on how many external organizations can be connected, and everyone in it sees each other's display names. Confirm the limits fit the expected member count.
- Use a dedicated Slack app (bot token in Secret Manager) installed in the workspace that owns `#sales-agents`; the app needs Slack Connect invite and channel-read scopes (exact scope names to be confirmed in Slack's docs).

**Do it asynchronously and idempotently, never inside the verify request.** A Slack outage must not stop someone from getting their content.

```
POST /verify activates the member (status -> "active")
  -> Firestore write on members/{email} fires an Eventarc trigger
  -> Cloud Function: if status == "active" and slack_invite == "none":
       claim it in a transaction (set slack_invite = "sent" first),
       call the Slack Connect invite API for that email + the channel ID,
       on API failure set slack_invite = "failed", store slack_error, raise
       so the failure is visible in logs (and alert on it).
```

```python
@functions_framework.cloud_event
def on_member_write(event):
    email = unquote(event["subject"].split("/documents/members/", 1)[-1])
    ref = db.collection("members").document(email)
    member = claim_slack_invite(db.transaction(), ref)   # returns None if already claimed/not active
    if not member:
        return
    r = requests.post("https://slack.com/api/conversations.inviteShared",
        headers={"Authorization": f"Bearer {SLACK_TOKEN}"},
        json={"channel": SLACK_CHANNEL_ID, "emails": [email]})   # confirm exact parameters in Slack docs
    body = r.json()
    if not body.get("ok"):
        ref.update({"slack_invite": "failed", "slack_error": body.get("error")})
        raise RuntimeError(body.get("error"))
```

The claim-before-call pattern means retries and the function's own write never produce duplicate invites. An Eventarc Firestore trigger does not retry by default, so failures are surfaced via `slack_invite = "failed"` rather than silently dropped.

Admin page additions:
- A **"Resend Slack invite"** button per member (resets `slack_invite` to `none` to re-fire the trigger), because Connect invites expire and are easy to miss.
- A column showing each member's `slack_invite` state, and a filter for `failed`.

Offboarding: when a member unsubscribes or is marked `bounced`/`complained`, set `slack_invite = "removed"` and remove them from the channel on a best-effort basis (check whether the API allows removing an external member and document the limitation if not). Content access ends immediately regardless, because status is checked on every request.

Consent: the signup form must say that members will be invited to a shared Slack channel where other members can see their name. Consider an opt-in checkbox instead of inviting everyone by default; Slack Connect friction means opt-in will likely produce a more engaged channel.

## Marketing needs

- Capture UTM parameters and referrer on the first visit (store in a short-lived cookie or the form) and persist them to `members.source`.
- `/admin/members` shows signups over time and the top sources, with CSV export.
- Optional: Google Analytics 4 events (`member_signup`, `member_verified`, `content_view`). Server-side events via the Measurement Protocol if the action does not load a page.

## Security checklist (acceptance criteria)

- [ ] Gated content, HTML and file URLs are never reachable without a valid session and an `active` member (test with `curl`, no cookie, and with a cookie for an unsubscribed member).
- [ ] Tokens: 32 random bytes, stored hashed, single-use, 15-minute expiry; `GET /verify` never spends them.
- [ ] Cookie flags `HttpOnly`, `Secure`, `SameSite=Lax`; named `__session`.
- [ ] Signup/login are rate limited per IP and per email; honeypot field present; responses never reveal whether an email exists.
- [ ] CSRF protection on all state-changing `POST`s (token or `SameSite` plus an origin check).
- [ ] All HTML from uploads sanitized; Markdown/docx never rendered raw.
- [ ] Bucket has public access prevented; no object is ever public.
- [ ] Unsubscribing or a bounce/complaint cuts off access immediately (status is checked on every request).
- [ ] No secrets in code or plaintext env vars; no service account key files.
- [ ] Mailgun webhook signature verified.
- [ ] Slack invite is sent once per member, never blocks content access, and a Slack failure leaves `slack_invite = "failed"` visible in the admin page.
- [ ] `robots.txt` disallows gated paths; gated pages send `Cache-Control: private, no-store`.

## Suggested layout

```
hub/
  app.py            routes + request handling
  auth.py           tokens, sessions, rate limits
  content.py        upload start, rendering (md/docx), signed URLs
  mailer.py         Mailgun send + webhook verification
  templates/        landing, verify, library, article, video, admin
  tests/            token single-use, status revocation, sanitizer, rate limit
  Dockerfile        python:3.12-slim, gunicorn
  infra/            optional Terraform: Cloud Run, bucket, Firestore, SA + IAM, secrets
```

## Open items (not blocking the build)

- Slack: which workspace owns `#sales-agents`, and is it on a paid plan (needed for Slack Connect invites)? Free-plan workspaces cannot send them.
- Invite everyone by default, or opt-in at signup?

- Subdomain name, GCP project and billing account
- Sending domain and sender address for the verification/marketing mail
- Optional: per-member watermarking for downloads, if content is valuable. Magic links stop casual sharing but not screenshots or forwarded files.

## Future: paid tier

Add a Stripe subscription webhook that sets `members.plan` and `status`, and a `required_plan` field on `content`. The per-request status check already enforces it, so nothing in the free design has to be undone.
