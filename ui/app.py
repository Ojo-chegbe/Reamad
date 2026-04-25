from __future__ import annotations

from flask import Flask, redirect, render_template, request, url_for

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


@app.before_request
def _bootstrap() -> None:
    init_db()
    seed_if_empty()


@app.get("/")
def dashboard():
    status = request.args.get("status") or None
    opportunities = list_opportunities(status=status)
    summary = {
        "pending": len([o for o in opportunities if o["status"] == "pending"]),
        "approved": len([o for o in opportunities if o["status"] == "approved"]),
        "rejected": len([o for o in opportunities if o["status"] == "rejected"]),
    }
    return render_template(
        "dashboard.html",
        opportunities=opportunities,
        summary=summary,
        selected_status=status or "all",
    )


@app.get("/opportunity/<opportunity_id>")
def opportunity_detail(opportunity_id: str):
    opportunity = get_opportunity(opportunity_id)
    if not opportunity:
        return render_template("not_found.html"), 404
    return render_template("opportunity_detail.html", opportunity=opportunity)


@app.post("/opportunity/<opportunity_id>/approve")
def approve(opportunity_id: str):
    note = request.form.get("note", "").strip()
    update_status(opportunity_id, "approved", "operator", note)
    return redirect(url_for("opportunity_detail", opportunity_id=opportunity_id))


@app.post("/opportunity/<opportunity_id>/reject")
def reject(opportunity_id: str):
    note = request.form.get("note", "").strip()
    update_status(opportunity_id, "rejected", "operator", note)
    return redirect(url_for("opportunity_detail", opportunity_id=opportunity_id))


@app.get("/playbooks")
def playbooks():
    return render_template("playbooks.html", playbooks=list_playbooks())


@app.get("/audit")
def audit():
    return render_template("audit.html", logs=list_audit())


if __name__ == "__main__":
    app.run(debug=True, port=5050)

