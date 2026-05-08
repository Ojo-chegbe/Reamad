from __future__ import annotations

import subprocess
import sys
import threading
import os
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
        self._procs: dict[str, subprocess.Popen[str] | None] = {"reddit": None, "twitter": None}
        self._last_returncodes: dict[str, int | None] = {"reddit": None, "twitter": None}

    def _stdout_path(self, engine: str) -> Path:
        return _PROJECT_ROOT / f"run.{engine}.out.log"

    def _stderr_path(self, engine: str) -> Path:
        return _PROJECT_ROOT / f"run.{engine}.err.log"

    def _refresh_engine(self, engine: str) -> None:
        proc = self._procs[engine]
        if proc and proc.poll() is not None:
            self._last_returncodes[engine] = proc.returncode
            self._procs[engine] = None

    def _engine_status(self, engine: str) -> dict[str, int | bool | None]:
        self._refresh_engine(engine)
        proc = self._procs[engine]
        return {
            "running": proc is not None,
            "pid": proc.pid if proc else None,
            "last_returncode": self._last_returncodes[engine],
        }

    def status(self) -> dict[str, object]:
        with self._lock:
            reddit = self._engine_status("reddit")
            twitter = self._engine_status("twitter")
            return {
                "running": bool(reddit["running"] or twitter["running"]),
                "engines": {
                    "reddit": reddit,
                    "twitter": twitter,
                },
            }

    def start_engine(self, engine: str) -> dict[str, int | bool | None]:
        if engine not in ("reddit", "twitter"):
            raise ValueError("engine must be reddit or twitter")
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
                    },
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                )
                self._last_returncodes[engine] = None
            return self._engine_status(engine)

    def stop_engine(self, engine: str) -> dict[str, int | bool | None]:
        if engine not in ("reddit", "twitter"):
            raise ValueError("engine must be reddit or twitter")
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
            return self._engine_status(engine)

    def start(self, engine: str = "both") -> dict[str, object]:
        if engine == "both":
            self.start_engine("reddit")
            self.start_engine("twitter")
            return self.status()
        return {"engine": engine, **self.start_engine(engine)}

    def stop(self, engine: str = "both") -> dict[str, object]:
        if engine == "both":
            self.stop_engine("reddit")
            self.stop_engine("twitter")
            return self.status()
        return {"engine": engine, **self.stop_engine(engine)}


runtime = BotRuntime()


@app.before_request
def _bootstrap() -> None:
    init_db()
    seed_if_empty()


@app.get("/api/opportunities")
def dashboard():
    status = request.args.get("status") or None
    platform = (request.args.get("platform") or "reddit").strip().lower()
    all_opportunities = list_opportunities(platform=platform)
    
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
        "platform": platform,
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
    platform = (request.args.get("platform") or "reddit").strip().lower()
    count = reject_all_pending("operator", platform=platform)
    return jsonify({"success": True, "count": count})


@app.get("/api/playbooks")
def playbooks():
    platform = (request.args.get("platform") or "reddit").strip().lower()
    if platform != "reddit":
        return jsonify({"playbooks": [], "platform": platform})

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

    return jsonify({"playbooks": current, "platform": platform})


@app.get("/api/audit")
def audit():
    platform = (request.args.get("platform") or "reddit").strip().lower()
    return jsonify({"logs": list_audit(platform=platform), "platform": platform})


@app.get("/api/runtime")
def runtime_status():
    return jsonify(runtime.status())


@app.post("/api/runtime/start")
def runtime_start():
    engine = (request.args.get("engine") or "both").strip().lower()
    if engine not in ("both", "reddit", "twitter"):
        return jsonify({"error": "Invalid engine. Use both, reddit, or twitter."}), 400
    return jsonify(runtime.start(engine=engine))


@app.post("/api/runtime/stop")
def runtime_stop():
    engine = (request.args.get("engine") or "both").strip().lower()
    if engine not in ("both", "reddit", "twitter"):
        return jsonify({"error": "Invalid engine. Use both, reddit, or twitter."}), 400
    return jsonify(runtime.stop(engine=engine))


@app.get("/api/profile")
def get_bot_profile():
    from src.soloa_profile import get_profile
    return jsonify(get_profile())


@app.post("/api/profile")
def update_bot_profile():
    from src.soloa_profile import save_profile
    data = request.get_json() or {}
    save_profile(data)
    
    # Restart whichever engines are currently running to apply new configuration.
    status = runtime.status()
    engines = status.get("engines", {})
    for engine in ("reddit", "twitter"):
        details = engines.get(engine, {})
        if isinstance(details, dict) and details.get("running"):
            runtime.stop(engine=engine)
            runtime.start(engine=engine)
            
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
        platform = (request.args.get("platform") or "reddit").strip().lower()
        if platform == "twitter":
            knowledge = profile.get("twitter_knowledge_block", "")
            current_keywords = profile.get("twitter_keywords", [])
        else:
            knowledge = profile.get("reddit_knowledge_block", "")
            current_keywords = profile.get("reddit_keywords", [])

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
