import hashlib
import secrets
import time
from functools import wraps
from flask import request, redirect, url_for, g
import config
from database import db

def hash_string(raw: str) -> str:
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def create_magic_token(email: str, purpose: str = "login", ttl: int = 86400) -> str:
    """
    Generates a secure, 32-byte single use raw token.
    Stores only the SHA256 hash in database.
    Default TTL is 24 hours for hiring invites.
    """
    raw_token = secrets.token_urlsafe(32)
    token_hash = hash_string(raw_token)
    expires_at = time.time() + ttl
    db.save_token(token_hash, email, purpose, expires_at)
    return raw_token

def verify_token(raw_token: str, spend: bool = False) -> dict:
    """
    Checks token validity.
    GET /verify displays confirmation without spending.
    POST /verify marks it used and spends it.
    """
    if not raw_token:
        return None
    token_hash = hash_string(raw_token)
    token_record = db.get_token(token_hash)
    if not token_record:
        return None
    
    if token_record.get("used_at"):
        return None
    
    if token_record.get("expires_at") < time.time():
        return None

    if spend:
        db.mark_token_used(token_hash)

    return token_record

def create_session(response, email: str, days: int = 90) -> str:
    """
    Creates a server-side session and sets the HttpOnly __session cookie.
    """
    raw_sid = secrets.token_urlsafe(32)
    sid_hash = hash_string(raw_sid)
    expires_at = time.time() + (days * 86400)
    db.save_session(sid_hash, email, expires_at)
    
    # Cookie name __session as required by Cloud Run / Firebase Hosting specs
    response.set_cookie(
        "__session",
        raw_sid,
        max_age=days * 86400,
        httponly=True,
        samesite="Lax",
        secure=False  # Allow local HTTP testing, becomes secure on HTTPS
    )
    return raw_sid

def clear_session(response):
    sid = request.cookies.get("__session")
    if sid:
        sid_hash = hash_string(sid)
        db.delete_session(sid_hash)
    response.set_cookie("__session", "", expires=0)

def get_current_member() -> dict:
    """
    Returns the currently authenticated member if session is valid
    AND member status is 'active'.
    """
    sid = request.cookies.get("__session")
    if not sid:
        return None
    
    sid_hash = hash_string(sid)
    session_rec = db.get_session(sid_hash)
    if not session_rec or session_rec.get("expires_at") < time.time():
        return None
    
    email = session_rec.get("email")
    member = db.get_member(email)
    if not member or member.get("status") != "active":
        return None

    return member

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        member = get_current_member()
        if not member:
            return redirect(url_for("login_page", next=request.path))
        g.member = member
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        member = get_current_member()
        if not member or member.get("role") != "admin":
            return redirect(url_for("login_page", next=request.path, admin="1"))
        g.member = member
        return f(*args, **kwargs)
    return decorated_function
