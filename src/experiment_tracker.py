from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from src.config import OUTPUTS_DIR
from src.database import get_experiment, get_experiments, get_latest_score_for_repo
from src.database import get_repo_id_by_name


def compute_system_suggestion(exp: dict) -> tuple:
    outreach = exp.get("outreach_count", 0) or 0
    replies = exp.get("reply_count", 0) or 0
    interested = exp.get("interested_count", 0) or 0
    waitlist = exp.get("waitlist_count", 0) or 0
    paid = exp.get("paid_count", 0) or 0
    status = exp.get("status", "planned")
    demo_url = exp.get("demo_url", "") or ""
    validation_channel = exp.get("validation_channel", "") or ""
    decision = exp.get("decision", "unknown")
    updated_at = exp.get("updated_at", "")
    created_at = exp.get("created_at", "")

    if decision and decision != "unknown" and exp.get("system_suggestion"):
        return exp["system_suggestion"], exp.get("system_suggestion_reason", "")

    reasons = []

    if paid >= 1:
        suggestion = "ship"
        reasons.append(f"Paid users detected ({paid}): strong validation signal.")
        return suggestion, " | ".join(reasons)

    if waitlist >= 5:
        suggestion = "continue"
        reasons.append(f"Waitlist >= 5 ({waitlist}): clear demand signal.")
        return suggestion, " | ".join(reasons)

    if interested >= 3:
        suggestion = "continue"
        reasons.append(f"Interested users >= 3 ({interested}): sufficient validation.")
        return suggestion, " | ".join(reasons)

    if outreach >= 20 and replies == 0:
        suggestion = "kill"
        reasons.append("Outreach >= 20 with zero replies: no market signal.")
        return suggestion, " | ".join(reasons)

    if outreach >= 10 and interested == 0 and replies == 0:
        suggestion = "pause"
        reasons.append("Outreach >= 10 with no interest: weak signal.")
        return suggestion, " | ".join(reasons)

    if status == "building":
        try:
            created = datetime.fromisoformat(created_at)
            now = datetime.now(timezone.utc)
            days_since = (now - created).days
            if days_since > 7 and not demo_url:
                suggestion = "pause"
                reasons.append(f"Building for {days_since} days without demo: reduce scope.")
                return suggestion, " | ".join(reasons)
        except (ValueError, TypeError):
            pass

    if status == "demo_ready" and not validation_channel:
        suggestion = "continue"
        reasons.append("Demo ready but no validation channel: start outreach.")
        return suggestion, " | ".join(reasons)

    if outreach >= 5 and interested >= 1:
        suggestion = "continue"
        reasons.append(f"Early signal: {interested} interested out of {outreach} outreach.")
        return suggestion, " | ".join(reasons)

    suggestion = "continue"
    reasons.append("Insufficient data for automated suggestion.")
    return suggestion, " | ".join(reasons)


def generate_experiment_report(experiment_id: int) -> Path:
    exp = get_experiment(experiment_id)
    if not exp:
        raise ValueError(f"Experiment #{experiment_id} not found")

    out_dir = OUTPUTS_DIR / "experiments"
    out_dir.mkdir(parents=True, exist_ok=True)

    system_suggestion, suggestion_reason = compute_system_suggestion(exp)

    lines = [
        f"# Experiment Report: {exp.get('experiment_name', 'N/A')}",
        "",
        f"> Generated {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Source Repo",
        "",
        f"- **Full Name**: {exp.get('repo_full_name', 'N/A')}",
        f"- **Opportunity Score**: {exp.get('opportunity_score', 'N/A')}",
        f"- **Data Quality Score**: {exp.get('data_quality_score', 'N/A')}",
        f"- **Final Recommendation**: {exp.get('final_recommendation', 'N/A')}",
        "",
        "## Experiment Status",
        "",
        f"- **Status**: {exp.get('status', 'N/A')}",
        f"- **Priority**: {exp.get('priority', 'N/A')}",
        f"- **MVP Type**: {exp.get('mvp_type', 'N/A')}",
        f"- **Decision**: {exp.get('decision', 'N/A')}",
        "",
        "## Linked Assets",
        "",
        f"- **Validation Pack**: {exp.get('validation_pack_path', 'Not generated')}",
        f"- **MVP Brief**: {exp.get('mvp_brief_path', 'Not generated')}",
        f"- **Codex Prompt**: {exp.get('codex_prompt_path', 'Not generated')}",
        f"- **External Project**: {exp.get('external_project_path', 'N/A')}",
        f"- **Demo URL**: {exp.get('demo_url', 'N/A')}",
        f"- **GitHub Repo**: {exp.get('github_repo_url', 'N/A')}",
        f"- **Landing Page**: {exp.get('landing_page_url', 'N/A')}",
        "",
        "## Validation Data",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Outreach Count | {exp.get('outreach_count', 0)} |",
        f"| Reply Count | {exp.get('reply_count', 0)} |",
        f"| Interested Count | {exp.get('interested_count', 0)} |",
        f"| Waitlist Count | {exp.get('waitlist_count', 0)} |",
        f"| Paid Count | {exp.get('paid_count', 0)} |",
        f"| Revenue Estimate | {exp.get('revenue_estimate', 0)} |",
        "",
        "## Target & Hypothesis",
        "",
        f"- **Target User**: {exp.get('target_user', 'N/A')}",
        f"- **Hypothesis**: {exp.get('hypothesis', 'N/A')}",
        f"- **Monetization Hypothesis**: {exp.get('monetization_hypothesis', 'N/A')}",
        f"- **Success Criteria**: {exp.get('success_criteria', 'N/A')}",
        f"- **Validation Channel**: {exp.get('validation_channel', 'N/A')}",
        "",
        "## Notes",
        "",
        f"{exp.get('notes', 'No notes.')}",
        "",
        "## System Suggestion",
        "",
        f"- **Suggestion**: **{system_suggestion.upper()}**",
        f"- **Reason**: {suggestion_reason}",
        "",
        "## Next Steps",
        "",
    ]
    if system_suggestion == "kill":
        lines.append("- Document what was learned.")
        lines.append("- Move to the next opportunity.")
        lines.append("- Archive this experiment.")
    elif system_suggestion == "pause":
        lines.append("- Reduce scope if building.")
        lines.append("- Start outreach if demo is ready.")
        lines.append("- Re-evaluate in 2 weeks.")
    elif system_suggestion == "continue":
        lines.append("- Proceed with current plan.")
        lines.append("- Collect more validation data.")
        lines.append("- Set a clear kill criterion.")
    elif system_suggestion == "ship":
        lines.append("- Polish the MVP.")
        lines.append("- Set up payment processing.")
        lines.append("- Prepare launch materials.")

    path = out_dir / f"experiment_{experiment_id}_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def generate_experiment_dashboard() -> Path:
    exps = get_experiments(limit=200)
    out_dir = OUTPUTS_DIR / "experiments"
    out_dir.mkdir(parents=True, exist_ok=True)

    total = len(exps)
    building = sum(1 for e in exps if e.get("status") == "building")
    validating = sum(1 for e in exps if e.get("status") == "validating")
    killed = sum(1 for e in exps if e.get("status") == "killed")
    shipped = sum(1 for e in exps if e.get("status") == "shipped")
    planned = sum(1 for e in exps if e.get("status") == "planned")
    paused = sum(1 for e in exps if e.get("status") == "paused")

    total_outreach = sum(e.get("outreach_count", 0) or 0 for e in exps)
    total_interested = sum(e.get("interested_count", 0) or 0 for e in exps)
    total_paid = sum(e.get("paid_count", 0) or 0 for e in exps)

    by_suggestion = {}
    for e in exps:
        sug, _ = compute_system_suggestion(e)
        by_suggestion[sug] = by_suggestion.get(sug, 0) + 1

    high_priority = [e for e in exps if e.get("priority") == "high" and e.get("status") not in ("killed", "shipped")]
    needs_followup = [e for e in exps if e.get("status") in ("building", "validating", "demo_ready")]
    suggest_kill = [e for e in exps if compute_system_suggestion(e)[0] == "kill" and e.get("status") != "killed"]

    lines = [
        f"# Experiment Dashboard",
        "",
        f"> Generated {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Overview",
        "",
        f"| Metric | Value |",
        f"|--------|-------|",
        f"| Total Experiments | {total} |",
        f"| Planned | {planned} |",
        f"| Building | {building} |",
        f"| Validating | {validating} |",
        f"| Killed | {killed} |",
        f"| Shipped | {shipped} |",
        f"| Paused | {paused} |",
        "",
        "## Cumulative Metrics",
        "",
        f"| Metric | Total |",
        f"|--------|-------|",
        f"| Total Outreach | {total_outreach} |",
        f"| Total Interested | {total_interested} |",
        f"| Total Paid | {total_paid} |",
        "",
        "## System Suggestions Distribution",
        "",
    ]
    for sug, count in sorted(by_suggestion.items(), key=lambda x: -x[1]):
        lines.append(f"- **{sug.upper()}**: {count}")
    lines.append("")

    if high_priority:
        lines.append("## High Priority Experiments")
        lines.append("")
        lines.append("| ID | Name | Status | Decision |")
        lines.append("|----|------|--------|----------|")
        for e in high_priority[:10]:
            lines.append(f"| {e['id']} | {e.get('experiment_name', 'N/A')} | {e.get('status', 'N/A')} | {e.get('decision', 'N/A')} |")
        lines.append("")

    if needs_followup:
        lines.append("## Needs Follow-up")
        lines.append("")
        for e in needs_followup[:10]:
            sug, _ = compute_system_suggestion(e)
            lines.append(f"- #{e['id']} **{e.get('experiment_name', 'N/A')}** ({e.get('status', 'N/A')}) → suggest: {sug}")
        lines.append("")

    if suggest_kill:
        lines.append("## Suggested to Kill")
        lines.append("")
        for e in suggest_kill[:10]:
            lines.append(f"- #{e['id']} **{e.get('experiment_name', 'N/A')}** ({e.get('repo_full_name', 'N/A')})")
        lines.append("")

    path = out_dir / "dashboard.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def generate_codex_task(experiment_id: int) -> Path:
    exp = get_experiment(experiment_id)
    if not exp:
        raise ValueError(f"Experiment #{experiment_id} not found")

    brief_path = exp.get("mvp_brief_path", "") or ""
    codex_path = exp.get("codex_prompt_path", "") or ""

    out_dir = OUTPUTS_DIR / "experiments"
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = [
        f"# Codex Task: {exp.get('experiment_name', 'N/A')}",
        "",
        f"> Generated {datetime.now(timezone.utc).isoformat()}",
        f"> Experiment #{experiment_id}",
        "",
        "## Opportunity Source",
        "",
        f"- **Repo**: {exp.get('repo_full_name', 'N/A')}",
        f"- **MVP Type**: {exp.get('mvp_type', 'N/A')}",
        f"- **Target User**: {exp.get('target_user', 'N/A')}",
        f"- **Hypothesis**: {exp.get('hypothesis', 'N/A')}",
        "",
        "## Target MVP",
        "",
        f"Build a {exp.get('mvp_type', 'N/A')} for {exp.get('repo_full_name', 'N/A')}.",
        "",
    ]

    if brief_path:
        lines.append("## Required Reading (Files)")
        lines.append("")
        lines.append("The following files contain detailed requirements and architecture:")
        lines.append("")
        base = Path(brief_path).parent if brief_path else out_dir
        for fname in ["product_brief.md", "mvp_requirements.md", "technical_architecture.md", "codex_prompt.md"]:
            fpath = base / fname
            if fpath.exists():
                lines.append(f"- [ ] Read [{fname}]({fpath})")
        lines.append("")
    elif codex_path:
        cp = Path(codex_path)
        if cp.exists():
            lines.append(f"### codex_prompt.md")
            lines.append("")
            lines.append(cp.read_text(encoding="utf-8")[:3000])
            lines.append("")
            lines.append(f"Full file: {cp}")
            lines.append("")

    lines.append("## Execution Requirements")
    lines.append("")
    lines.append("1. **Create a standalone project** — do NOT modify github-opportunity-radar")
    lines.append("2. **First version must be runnable** — no placeholder code")
    lines.append("3. **Must have README** with install and run instructions")
    lines.append("4. **Must have smoke-test** (`smoke_test.py`) that verifies core features")
    lines.append("5. **Must include demo data or fixtures** — never fake real API responses")
    lines.append("6. **Must provide run commands** in the README")
    lines.append("7. **Write tests** for all core features")
    lines.append("8. **Use requirements.txt / package.json** for dependencies")
    lines.append("9. **Use .env.example** for configuration")
    lines.append("")

    lines.append("## Acceptance Criteria")
    lines.append("")
    if exp.get("mvp_type") == "one_click_installer":
        lines.append("- [ ] Installs on macOS, Linux, Windows")
        lines.append("- [ ] Dependencies auto-detected")
        lines.append("- [ ] Clear success/failure feedback")
        lines.append("- [ ] Clean uninstall")
    elif exp.get("mvp_type") == "webui":
        lines.append("- [ ] Server starts with one command")
        lines.append("- [ ] User can upload config and see results")
        lines.append("- [ ] Export produces valid files")
        lines.append("- [ ] Non-technical user can complete flow")
    elif exp.get("mvp_type") == "mcp_server":
        lines.append("- [ ] Server starts and connects to MCP client")
        lines.append("- [ ] All tool definitions have valid JSON Schema")
        lines.append("- [ ] Each tool executes and returns results")
        lines.append("- [ ] Error responses are informative")
    else:
        lines.append("- [ ] MVP is functional and can be demonstrated")
        lines.append("- [ ] README is complete and accurate")
        lines.append("- [ ] smoke_test.py passes")
    lines.append("")

    lines.append("## Prohibited")
    lines.append("")
    lines.append("- Do NOT modify files in github-opportunity-radar")
    lines.append("- Do NOT add auth systems")
    lines.append("- Do NOT add analytics/telemetry")
    lines.append("- Do NOT over-engineer (readable code > abstractions)")
    lines.append("- Do NOT assume network access for core features")
    lines.append("- Do NOT generate fake API responses")

    path = out_dir / f"experiment_{experiment_id}_codex_task.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
