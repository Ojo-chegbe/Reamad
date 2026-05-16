from __future__ import annotations

import subprocess
import sys
import threading
import os
import csv
import base64
import hashlib
import hmac
from io import StringIO
from pathlib import Path
from functools import wraps

from flask import Flask, Response, jsonify, request

from ui.state import (
    bootstrap_owner,
    create_account_for_user,
    create_session,
    create_user,
    delete_session,
    get_opportunity,
    get_user_by_email,
    get_user_by_session,
    get_user_context,
    init_db,
    list_audit,
    list_opportunities,
    list_playbooks,
    seed_if_empty,
    set_current_account,
    analytics as get_analytics,
    update_feedback,
    update_outcome,
    update_status,
)

app = Flask(__name__)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
SESSION_COOKIE = "gatekeeper_session"


def _hash_password(password: str, salt: bytes | None = None) -> str:
    salt = salt or os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200_000)
    return f"pbkdf2_sha256$200000${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iterations, salt_b64, digest_b64 = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iterations))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def _ensure_bootstrap_owner() -> None:
    email = os.getenv("SOLOA_ADMIN_EMAIL", "admin@soloa.local").strip().lower()
    password = os.getenv("SOLOA_ADMIN_PASSWORD", "soloa-admin")
    bootstrap_owner(email=email, password_hash=_hash_password(password))


def _session_user() -> dict | None:
    return get_user_by_session(request.cookies.get(SESSION_COOKIE))


def _current_account_id() -> str:
    user = _session_user()
    if not user:
        raise PermissionError("Authentication required")
    return str(user["current_account_id"])


def require_auth(handler):
    @wraps(handler)
    def wrapper(*args, **kwargs):
        if not _session_user():
            return jsonify({"error": "Authentication required"}), 401
        return handler(*args, **kwargs)

    return wrapper


class BotRuntime:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._procs: dict[str, subprocess.Popen[str] | None] = {"reddit": None, "twitter": None, "youtube": None}
        self._last_returncodes: dict[str, int | None] = {"reddit": None, "twitter": None, "youtube": None}
        self._account_ids: dict[str, str | None] = {"reddit": None, "twitter": None, "youtube": None}

    def _stdout_path(self, engine: str) -> Path:
        return _PROJECT_ROOT / f"run.{engine}.out.log"

    def _stderr_path(self, engine: str) -> Path:
        return _PROJECT_ROOT / f"run.{engine}.err.log"

    def _refresh_engine(self, engine: str) -> None:
        proc = self._procs[engine]
        if proc and proc.poll() is not None:
            self._last_returncodes[engine] = proc.returncode
            self._procs[engine] = None
            self._account_ids[engine] = None

    def _engine_status(self, engine: str) -> dict[str, int | bool | None]:
        self._refresh_engine(engine)
        proc = self._procs[engine]
        return {
            "running": proc is not None,
            "pid": proc.pid if proc else None,
            "last_returncode": self._last_returncodes[engine],
            "account_id": self._account_ids[engine],
        }

    def status(self) -> dict[str, object]:
        with self._lock:
            reddit = self._engine_status("reddit")
            twitter = self._engine_status("twitter")
            youtube = self._engine_status("youtube")
            return {
                "running": bool(reddit["running"] or twitter["running"] or youtube["running"]),
                "engines": {
                    "reddit": reddit,
                    "twitter": twitter,
                    "youtube": youtube,
                },
            }

    def start_engine(self, engine: str, account_id: str) -> dict[str, int | bool | None]:
        if engine not in ("reddit", "twitter", "youtube"):
            raise ValueError("engine must be reddit, twitter, or youtube")
        with self._lock:
            self._refresh_engine(engine)
            proc = self._procs[engine]
            if proc is None:
                out_path = self._stdout_path(engine)
                err_path = self._stderr_path(engine)
                out_path.write_text("")
                err_path.write_text("")
                stdout_handle = out_path.open("a", encoding="utf-8")
                stderr_handle = err_path.open("a", encoding="utf-8")
                self._procs[engine] = subprocess.Popen(
                    [sys.executable, "-u", "-m", "src.main"],
                    cwd=str(_PROJECT_ROOT),
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    env={
                        **os.environ,
                        "PYTHONUTF8": "1",
                        "PYTHONIOENCODING": "utf-8",
                        "ENGINE_MODE": engine,
                        "SOLOA_ACCOUNT_ID": account_id,
                    },
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )
                self._account_ids[engine] = account_id
                self._last_returncodes[engine] = None
            return self._engine_status(engine)

    def stop_engine(self, engine: str) -> dict[str, int | bool | None]:
        if engine not in ("reddit", "twitter", "youtube"):
            raise ValueError("engine must be reddit, twitter, or youtube")
        with self._lock:
            self._refresh_engine(engine)
            proc = self._procs[engine]
            if proc is None:
                return self._engine_status(engine)
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            self._last_returncodes[engine] = proc.returncode
            self._procs[engine] = None
            self._account_ids[engine] = None
            return self._engine_status(engine)

    def start(self, engine: str = "both", account_id: str = "soloa-ai") -> dict[str, object]:
        if engine == "both":
            self.start_engine("reddit", account_id)
            self.start_engine("twitter", account_id)
            self.start_engine("youtube", account_id)
            return self.status()
        return {"engine": engine, **self.start_engine(engine, account_id)}

    def stop(self, engine: str = "both") -> dict[str, object]:
        if engine == "both":
            self.stop_engine("reddit")
            self.stop_engine("twitter")
            self.stop_engine("youtube")
            return self.status()
        return {"engine": engine, **self.stop_engine(engine)}


runtime = BotRuntime()


@app.before_request
def _bootstrap() -> None:
    init_db()
    _ensure_bootstrap_owner()
    seed_if_empty()


@app.get("/api/auth/me")
def auth_me():
    user = _session_user()
    if not user:
        return jsonify({"authenticated": False}), 401
    context = get_user_context(user["id"]) or {}
    return jsonify({"authenticated": True, **context})


@app.post("/api/auth/login")
def auth_login():
    data = request.get_json() or {}
    email = str(data.get("email", "") or "").strip().lower()
    password = str(data.get("password", "") or "")
    user = get_user_by_email(email)
    if not user or not _verify_password(password, user["password_hash"]):
        return jsonify({"error": "Invalid email or password"}), 401
    token = create_session(user["id"])
    response = jsonify({"success": True, **(get_user_context(user["id"]) or {})})
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="Lax", max_age=60 * 60 * 24 * 30)
    return response


@app.post("/api/auth/signup")
def auth_signup():
    data = request.get_json() or {}
    email = str(data.get("email", "") or "").strip().lower()
    password = str(data.get("password", "") or "")
    account_name = str(data.get("account_name", "") or "").strip()
    display_name = str(data.get("display_name", "") or "").strip()
    if not email or "@" not in email:
        return jsonify({"error": "Valid email is required"}), 400
    if len(password) < 8:
        return jsonify({"error": "Password must be at least 8 characters"}), 400
    if get_user_by_email(email):
        return jsonify({"error": "An account already exists for this email"}), 409
    context = create_user(
        email=email,
        password_hash=_hash_password(password),
        account_name=account_name or "New account",
        display_name=display_name,
    )
    token = create_session(context["user"]["id"])
    response = jsonify({"success": True, **context})
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="Lax", max_age=60 * 60 * 24 * 30)
    return response


@app.post("/api/auth/logout")
def auth_logout():
    delete_session(request.cookies.get(SESSION_COOKIE, ""))
    response = jsonify({"success": True})
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.post("/api/accounts")
@require_auth
def create_account():
    user = _session_user()
    data = request.get_json() or {}
    name = str(data.get("name", "") or "").strip()
    if not name:
        return jsonify({"error": "Account name is required"}), 400
    return jsonify({"success": True, **create_account_for_user(user["id"], name)})


@app.post("/api/accounts/current")
@require_auth
def switch_account():
    user = _session_user()
    data = request.get_json() or {}
    account_id = str(data.get("account_id", "") or "").strip()
    if not set_current_account(user["id"], account_id):
        return jsonify({"error": "Account not found"}), 404
    return jsonify({"success": True, **(get_user_context(user["id"]) or {})})


@app.get("/api/opportunities")
@require_auth
def dashboard():
    account_id = _current_account_id()
    status = request.args.get("status") or None
    platform = (request.args.get("platform") or "reddit").strip().lower()
    all_opportunities = list_opportunities(platform=platform, account_id=account_id)
    
    summary = {
        "pending": len([o for o in all_opportunities if o["status"] in ("new", "qualified", "drafted", "pending")]),
        "approved": len([o for o in all_opportunities if o["status"] in ("approved", "posted", "replied_back", "converted")]),
        "rejected": len([o for o in all_opportunities if o["status"] == "rejected"]),
        "posted": len([o for o in all_opportunities if o["status"] in ("posted", "replied_back", "converted")]),
        "converted": len([o for o in all_opportunities if o["status"] == "converted"]),
    }
    
    if status and status != "all":
        if status == "pending":
            opportunities = [o for o in all_opportunities if o["status"] in ("new", "qualified", "drafted", "pending")]
        else:
            opportunities = [o for o in all_opportunities if o["status"] == status]
    else:
        opportunities = all_opportunities
    return jsonify({
        "opportunities": opportunities,
        "summary": summary,
        "selected_status": status or "all",
        "platform": platform,
    })


@app.get("/api/opportunity/<opportunity_id>")
@require_auth
def opportunity_detail(opportunity_id: str):
    opportunity = get_opportunity(opportunity_id, account_id=_current_account_id())
    if not opportunity:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"opportunity": opportunity})


@app.post("/api/opportunity/<opportunity_id>/approve")
@require_auth
def approve(opportunity_id: str):
    data = request.get_json() or {}
    note = data.get("note", "").strip() if request.is_json else request.form.get("note", "").strip()
    update_status(opportunity_id, "approved", "operator", note, account_id=_current_account_id())
    return jsonify({"success": True})


@app.post("/api/opportunity/<opportunity_id>/reject")
@require_auth
def reject(opportunity_id: str):
    data = request.get_json() or {}
    note = data.get("note", "").strip() if request.is_json else request.form.get("note", "").strip()
    update_status(opportunity_id, "rejected", "operator", note, account_id=_current_account_id())
    return jsonify({"success": True})


@app.post("/api/opportunity/<opportunity_id>/status")
@require_auth
def set_opportunity_status(opportunity_id: str):
    data = request.get_json() or {}
    status = str(data.get("status", "")).strip()
    note = str(data.get("note", "") or "").strip()
    try:
        update_status(opportunity_id, status, "operator", note, account_id=_current_account_id())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"success": True})


@app.post("/api/opportunity/<opportunity_id>/outcome")
@require_auth
def save_opportunity_outcome(opportunity_id: str):
    data = request.get_json() or {}
    try:
        update_outcome(
            opportunity_id=opportunity_id,
            actor="operator",
            posted_reply_url=str(data.get("posted_reply_url", "") or "").strip(),
            selected_draft_index=data.get("selected_draft_index"),
            replied_at=str(data.get("replied_at", "") or "").strip() or None,
            followup_sentiment=str(data.get("followup_sentiment", "") or "").strip(),
            clicks=int(data.get("clicks", 0) or 0),
            signups=int(data.get("signups", 0) or 0),
            conversion_value=float(data.get("conversion_value", 0) or 0),
            next_follow_up_at=str(data.get("next_follow_up_at", "") or "").strip() or None,
            operator_notes=str(data.get("operator_notes", "") or "").strip(),
            status=str(data.get("status", "") or "").strip() or None,
            account_id=_current_account_id(),
        )
    except (TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"success": True})


@app.post("/api/opportunity/<opportunity_id>/feedback")
@require_auth
def save_opportunity_feedback(opportunity_id: str):
    data = request.get_json() or {}
    label = str(data.get("label", "") or "").strip()
    note = str(data.get("note", "") or "").strip()
    if not label:
        return jsonify({"error": "label is required"}), 400
    try:
        update_feedback(opportunity_id, label, "operator", note, account_id=_current_account_id())
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"success": True})


@app.post("/api/opportunities/reject_all")
@require_auth
def reject_all():
    from ui.state import reject_all_pending
    platform = (request.args.get("platform") or "reddit").strip().lower()
    count = reject_all_pending("operator", platform=platform, account_id=_current_account_id())
    return jsonify({"success": True, "count": count})


@app.get("/api/playbooks")
@require_auth
def playbooks():
    account_id = _current_account_id()
    platform = (request.args.get("platform") or "reddit").strip().lower()
    if platform != "reddit":
        return jsonify({"playbooks": [], "platform": platform})

    from src.config import load_settings
    from src.reddit_client import make_reddit
    from src.store import Store
    from src.playbook import refresh_subreddit_rules
    from ui.state import upsert_playbook

    current = list_playbooks(account_id=account_id)
    current_subs = {p["subreddit"].lower() for p in current}
    
    settings = load_settings(account_id=account_id)
    effective_subreddits = settings.target_subreddits or settings.pain_subreddits
    missing = [s for s in effective_subreddits if s.lower() not in current_subs]
    
    if missing:
        reddit = make_reddit(settings)
        store = Store(account_id=account_id)
        refresh_subreddit_rules(reddit, store, missing)
        for sub_name in missing:
            upsert_playbook(sub_name, store.get_rules(sub_name), account_id=account_id)
        
        current = list_playbooks(account_id=account_id)

    return jsonify({"playbooks": current, "platform": platform})


@app.get("/api/audit")
@require_auth
def audit():
    platform = (request.args.get("platform") or "reddit").strip().lower()
    return jsonify({"logs": list_audit(platform=platform, account_id=_current_account_id()), "platform": platform})


@app.get("/api/audit/export")
@require_auth
def audit_export():
    platform = (request.args.get("platform") or "reddit").strip().lower()
    rows = list_audit(platform=platform, account_id=_current_account_id())
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["id", "platform", "opportunity_id", "action", "actor", "note", "created_at"])
    writer.writeheader()
    writer.writerows(rows)
    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=gatekeeper-{platform}-audit.csv"},
    )


@app.get("/api/analytics")
@require_auth
def analytics():
    platform = (request.args.get("platform") or "reddit").strip().lower()
    return jsonify({"analytics": get_analytics(platform=platform, account_id=_current_account_id()), "platform": platform})


@app.get("/api/runtime")
@require_auth
def runtime_status():
    return jsonify(runtime.status())


@app.post("/api/runtime/start")
@require_auth
def runtime_start():
    engine = (request.args.get("engine") or "both").strip().lower()
    if engine not in ("both", "reddit", "twitter", "youtube"):
        return jsonify({"error": "Invalid engine. Use both, reddit, twitter, or youtube."}), 400
    return jsonify(runtime.start(engine=engine, account_id=_current_account_id()))


@app.post("/api/runtime/stop")
@require_auth
def runtime_stop():
    engine = (request.args.get("engine") or "both").strip().lower()
    if engine not in ("both", "reddit", "twitter", "youtube"):
        return jsonify({"error": "Invalid engine. Use both, reddit, twitter, or youtube."}), 400
    return jsonify(runtime.stop(engine=engine))


@app.get("/api/profile")
@require_auth
def get_bot_profile():
    from src.soloa_profile import get_profile
    return jsonify(get_profile(account_id=_current_account_id()))


@app.post("/api/profile")
@require_auth
def update_bot_profile():
    from src.soloa_profile import save_profile
    data = request.get_json() or {}
    account_id = _current_account_id()
    save_profile(data, account_id=account_id)
    
    # Restart whichever engines are currently running to apply new configuration.
    status = runtime.status()
    engines = status.get("engines", {})
    for engine in ("reddit", "twitter", "youtube"):
        details = engines.get(engine, {})
        if isinstance(details, dict) and details.get("running"):
            runtime.stop(engine=engine)
            runtime.start(engine=engine, account_id=account_id)
            
    return jsonify({"success": True})


@app.get("/api/search_subreddits")
@require_auth
def api_search_subreddits():
    from src.config import load_settings
    from src.reddit_client import make_reddit
    
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"results": []})
        
    try:
        settings = load_settings(account_id=_current_account_id())
        reddit = make_reddit(settings)
        results = reddit.search_subreddits(query)
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/suggest_keywords")
@require_auth
def api_suggest_keywords():
    from src.config import load_settings
    from google import genai
    from src.soloa_profile import get_profile

    try:
        settings = load_settings(account_id=_current_account_id())
        if not settings.google_api_key:
            return jsonify({"error": "No Google API Key configured."}), 400

        profile = get_profile(account_id=_current_account_id())
        platform = (request.args.get("platform") or "reddit").strip().lower()
        if platform == "twitter":
            knowledge = profile.get("twitter_knowledge_block", "")
            current_keywords = profile.get("twitter_keywords", [])
            platform_label = "X/Twitter users"
            phrase_label = "reply discovery signals"
        elif platform == "youtube":
            knowledge = profile.get("youtube_knowledge_block", "")
            current_keywords = profile.get("youtube_keywords", [])
            platform_label = "YouTube commenters or video searchers"
            phrase_label = "YouTube discovery signals"
        else:
            knowledge = profile.get("reddit_knowledge_block", "")
            current_keywords = profile.get("reddit_keywords", [])
            platform_label = "Reddit users"
            phrase_label = "Reddit discovery signals"

        client = genai.Client(api_key=settings.google_api_key)
        prompt = f"""
        Based on this product knowledge:
        {knowledge}

        And these current keywords:
        {', '.join(current_keywords)}

        Suggest 5-8 short, natural {phrase_label} that {platform_label} might use when discussing problems this configured business can solve.
        Output ONLY the phrases, one per line, no bullet points, no quotes.
        """

        response = client.models.generate_content(
            model=settings.google_model,
            contents=prompt.strip(),
        )
        
        text = response.text or ""
        suggestions = [line.strip().strip('-* ') for line in text.splitlines() if line.strip()]
        # filter out any that are already in current_keywords
        suggestions = [s for s in suggestions if s and s.lower() not in [k.lower() for k in current_keywords]]
        
        return jsonify({"suggestions": suggestions})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=os.getenv("FLASK_DEBUG", "0").strip() in ("1", "true", "yes"), port=5050)
