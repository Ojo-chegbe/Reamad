from __future__ import annotations

import subprocess
import sys
import threading
from pathlib import Path

from flask import Flask, jsonify, request

from ui.state import (
    get_opportunity,
    init_db,
    list_audit,
    list_opportunities,
    list_playbooks,
    seed_if_empty,
    update_status,
)

app = Flask(__name__)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent


class BotRuntime:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._proc: subprocess.Popen[str] | None = None
        self._last_returncode: int | None = None
        self._stdout_path = _PROJECT_ROOT / "run.out.log"
        self._stderr_path = _PROJECT_ROOT / "run.err.log"

    def _refresh(self) -> None:
        if self._proc and self._proc.poll() is not None:
            self._last_returncode = self._proc.returncode
            self._proc = None

    def status(self) -> dict[str, int | bool | None]:
        with self._lock:
            self._refresh()
            return {
                "running": self._proc is not None,
                "pid": self._proc.pid if self._proc else None,
                "last_returncode": self._last_returncode,
            }

    def start(self) -> dict[str, int | bool | None]:
        with self._lock:
            self._refresh()
            if self._proc is None:
                self._stdout_path.write_text("")
                self._stderr_path.write_text("")
                stdout_handle = self._stdout_path.open("a", encoding="utf-8")
                stderr_handle = self._stderr_path.open("a", encoding="utf-8")
                self._proc = subprocess.Popen(
                    [sys.executable, "-m", "src.main"],
                    cwd=str(_PROJECT_ROOT),
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )
                self._last_returncode = None
            return {
                "running": True,
                "pid": self._proc.pid,
                "last_returncode": self._last_returncode,
            }

    def stop(self) -> dict[str, int | bool | None]:
        with self._lock:
            self._refresh()
            if self._proc is None:
                return {
                    "running": False,
                    "pid": None,
                    "last_returncode": self._last_returncode,
                }

            proc = self._proc
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
            self._last_returncode = proc.returncode
            self._proc = None
            return {
                "running": False,
                "pid": None,
                "last_returncode": self._last_returncode,
            }


runtime = BotRuntime()


@app.before_request
def _bootstrap() -> None:
    init_db()
    seed_if_empty()


@app.get("/api/opportunities")
def dashboard():
    status = request.args.get("status") or None
    all_opportunities = list_opportunities()
    
    summary = {
        "pending": len([o for o in all_opportunities if o["status"] == "pending"]),
        "approved": len([o for o in all_opportunities if o["status"] == "approved"]),
        "rejected": len([o for o in all_opportunities if o["status"] == "rejected"]),
    }
    
    if status and status != "all":
        opportunities = [o for o in all_opportunities if o["status"] == status]
    else:
        opportunities = all_opportunities
    return jsonify({
        "opportunities": opportunities,
        "summary": summary,
        "selected_status": status or "all",
    })


@app.get("/api/opportunity/<opportunity_id>")
def opportunity_detail(opportunity_id: str):
    opportunity = get_opportunity(opportunity_id)
    if not opportunity:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"opportunity": opportunity})


@app.post("/api/opportunity/<opportunity_id>/approve")
def approve(opportunity_id: str):
    data = request.get_json() or {}
    note = data.get("note", "").strip() if request.is_json else request.form.get("note", "").strip()
    update_status(opportunity_id, "approved", "operator", note)
    return jsonify({"success": True})


@app.post("/api/opportunity/<opportunity_id>/reject")
def reject(opportunity_id: str):
    data = request.get_json() or {}
    note = data.get("note", "").strip() if request.is_json else request.form.get("note", "").strip()
    update_status(opportunity_id, "rejected", "operator", note)
    return jsonify({"success": True})


@app.post("/api/opportunities/reject_all")
def reject_all():
    from ui.state import reject_all_pending
    count = reject_all_pending("operator")
    return jsonify({"success": True, "count": count})


@app.get("/api/playbooks")
def playbooks():
    from src.config import load_settings
    from src.reddit_client import make_reddit
    from src.store import Store
    from src.playbook import refresh_subreddit_rules
    from ui.state import upsert_playbook

    current = list_playbooks()
    current_subs = {p["subreddit"].lower() for p in current}
    
    settings = load_settings()
    effective_subreddits = settings.target_subreddits or settings.pain_subreddits
    missing = [s for s in effective_subreddits if s.lower() not in current_subs]
    
    if missing:
        reddit = make_reddit(settings)
        store = Store()
        refresh_subreddit_rules(reddit, store, missing)
        for sub_name in missing:
            upsert_playbook(sub_name, store.get_rules(sub_name))
        
        current = list_playbooks()

    return jsonify({"playbooks": current})


@app.get("/api/audit")
def audit():
    return jsonify({"logs": list_audit()})


@app.get("/api/runtime")
def runtime_status():
    return jsonify(runtime.status())


@app.post("/api/runtime/start")
def runtime_start():
    return jsonify(runtime.start())


@app.post("/api/runtime/stop")
def runtime_stop():
    return jsonify(runtime.stop())


@app.get("/api/profile")
def get_bot_profile():
    from src.soloa_profile import get_profile
    return jsonify(get_profile())


@app.post("/api/profile")
def update_bot_profile():
    from src.soloa_profile import save_profile
    data = request.get_json() or {}
    save_profile(data)
    
    # Restart the bot to apply new configuration
    with runtime._lock:
        if runtime._proc:
            runtime._proc.terminate()
            try:
                runtime._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                runtime._proc.kill()
                runtime._proc.wait(timeout=5)
            runtime._proc = None
            runtime._last_returncode = None
            
            # Start again
            runtime._stdout_path.write_text("")
            runtime._stderr_path.write_text("")
            stdout_handle = runtime._stdout_path.open("a", encoding="utf-8")
            stderr_handle = runtime._stderr_path.open("a", encoding="utf-8")
            runtime._proc = subprocess.Popen(
                [sys.executable, "-m", "src.main"],
                cwd=str(_PROJECT_ROOT),
                stdout=stdout_handle,
                stderr=stderr_handle,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            
    return jsonify({"success": True})


@app.get("/api/search_subreddits")
def api_search_subreddits():
    from src.config import load_settings
    from src.reddit_client import make_reddit
    
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify({"results": []})
        
    try:
        settings = load_settings()
        reddit = make_reddit(settings)
        results = reddit.search_subreddits(query)
        return jsonify({"results": results})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.post("/api/suggest_keywords")
def api_suggest_keywords():
    from src.config import load_settings
    from google import genai
    from src.soloa_profile import get_profile

    try:
        settings = load_settings()
        if not settings.google_api_key:
            return jsonify({"error": "No Google API Key configured."}), 400

        profile = get_profile()
        knowledge = profile.get("knowledge_block", "")
        current_keywords = profile.get("keywords", [])

        client = genai.Client(api_key=settings.google_api_key)
        prompt = f"""
        Based on this product knowledge:
        {knowledge}

        And these current keywords:
        {', '.join(current_keywords)}

        Suggest 5-8 new short, natural "pain keywords" or "frustration phrases" that Reddit users might use when struggling with problems this product solves.
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
    app.run(debug=True, port=5050)
