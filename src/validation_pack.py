import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from src.config import OUTPUTS_DIR, settings
from src.database import get_repo_id_by_name, get_latest_score_for_repo
from src.database import get_last_two_snapshots, get_watchlist_status
from src.database import get_issues_for_snapshot
from src.repo_page_scraper import scrape_issues_direct
from src.scorer import RECOMMENDATION_MAP_CN
from src.llm.base import LLMConfig
from src.llm.provider_router import create_client
from src.llm.prompts import SYSTEM_PROMPT_EN, USER_PROMPT_TEMPLATE_EN
from src.llm.json_repair import extract_json


def _sanitize_name(name):
    return name.replace("/", "__").replace("\\", "__")


def _get_issues_text(issues, max_count=15):
    lines = []
    for i, iss in enumerate((issues or [])[:max_count], 1):
        title = iss.get("title", "")
        labels = ", ".join(iss.get("labels", [])[:3])
        comments = iss.get("comments_count", 0)
        body = (iss.get("body", "") or "")[:200].replace("\n", " ")
        lines.append(f"{i}. **{title}** (comments: {comments}, labels: {labels})")
        if body:
            lines.append(f"   {body}")
    return "\n".join(lines)


def _safe_readme_excerpt(repo_info: dict) -> str:
    text = repo_info.get("readme_text", "") or ""
    if not text:
        return "No README available."
    lines = text.split("\n")
    significant = [l for l in lines if len(l.strip()) > 20]
    return "\n".join(significant[:30])[:2000]


def generate_validation_pack(repo_full_name: str, issues: list = None,
                             llm_config: Optional[LLMConfig] = None,
                             repo_info: Optional[dict] = None):
    out_dir = OUTPUTS_DIR / "validation_packs" / _sanitize_name(repo_full_name)
    out_dir.mkdir(parents=True, exist_ok=True)

    repo_id = get_repo_id_by_name(repo_full_name)
    last_score = get_latest_score_for_repo(repo_id) if repo_id else None
    watch_status = get_watchlist_status(repo_id) if repo_id else None
    snapshots = get_last_two_snapshots(repo_id) if repo_id else []

    if issues is None:
        issues = scrape_issues_direct(repo_full_name, max_count=20)
        for iss in (issues or []):
            iss["body"] = iss.get("body", "") or ""

    stars_current = repo_info.get("stars", 0) if repo_info else (snapshots[0].get("stars", 0) if snapshots else 0)
    stars_delta_7d = repo_info.get("stars_delta_7d", "") if repo_info else ""
    open_issues = repo_info.get("open_issues_count", 0) if repo_info else len(issues)

    def _safe(val, default=""):
        return val if val else default

    llm_client = None
    if llm_config and llm_config.provider != "none":
        llm_client = create_client(llm_config)

    files_created = []

    files_created.append(_write_opportunity_brief(out_dir, repo_full_name, repo_id,
                                                   last_score, watch_status, issues,
                                                   stars_current, stars_delta_7d, open_issues,
                                                   repo_info, llm_client, llm_config))
    files_created.append(_write_landing_page_copy(out_dir, repo_full_name, last_score,
                                                   issues, llm_client, llm_config))
    files_created.append(_write_mvp_scope(out_dir, repo_full_name, last_score, issues,
                                           llm_client, llm_config))
    files_created.append(_write_issue_reply_drafts(out_dir, repo_full_name, issues))
    files_created.append(_write_user_interview_questions(out_dir, repo_full_name, issues,
                                                          llm_client, llm_config))
    files_created.append(_write_7_day_validation_plan(out_dir, repo_full_name, issues,
                                                       llm_client, llm_config))
    files_created.append(_write_launch_post_drafts(out_dir, repo_full_name, last_score,
                                                    issues, llm_client, llm_config))

    print(f"  Validation pack generated: {out_dir}")
    return str(out_dir), files_created


def _llm_enhance(system_prompt, user_prompt, llm_client, llm_config) -> Optional[str]:
    if not llm_client:
        return None
    schema = None
    if llm_config and llm_config.use_json_schema:
        from src.llm.analyzer import LLMAnalyzer
        dummy = LLMAnalyzer(llm_config)
        schema = dummy._build_openai_schema() if llm_config.use_json_schema else None
    try:
        result = llm_client.chat_json(system_prompt, user_prompt, schema)
        if result.success and result.content:
            return result.content
    except Exception:
        pass
    return None


def _write_opportunity_brief(out_dir, fn, repo_id, last_score, watch_status,
                              issues, stars_current, stars_delta_7d, open_issues,
                              repo_info, llm_client, llm_config):
    path = out_dir / "opportunity_brief.md"
    lines = []
    lines.append(f"# Opportunity Brief: {fn}")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## What Is This Opportunity")
    lines.append("")
    if last_score:
        verdict = last_score.get("opportunity_verdict", "unknown")
        rec = last_score.get("final_recommendation", "")
        rec_cn = RECOMMENDATION_MAP_CN.get(rec, rec)
        score = last_score.get("opportunity_score", 0)
        lines.append(f"**Score**: {score}/100 | **Verdict**: {verdict} | **Recommendation**: {rec_cn}")
        lines.append("")
        why_opp = last_score.get("why_opportunity", "")
        if why_opp:
            lines.append(f"**Why Opportunity**: {why_opp}")
            lines.append("")
        why_not = last_score.get("why_not_worth", "")
        if why_not:
            lines.append(f"**Why Not Worth**: {why_not}")
            lines.append("")

    lines.append(f"**Stars**: {stars_current} | **Open Issues**: {open_issues}")
    if stars_delta_7d:
        lines.append(f"**Weekly Star Growth**: +{stars_delta_7d}")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## Target Users")
    lines.append("")
    if watch_status:
        tgt = watch_status.get("target_user_guess", "")
        if tgt:
            lines.append(f"**User guess (from watchlist)**: {tgt}")
            lines.append("")

    lines.append("## Pain Evidence from Issues")
    lines.append("")
    if issues:
        lines.append(_get_issues_text(issues, max_count=10))
    else:
        lines.append("No issues available.")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## Why Now")
    lines.append("")
    why_now = last_score.get("why_opportunity", "") if last_score else ""
    if why_now:
        lines.append(why_now)
    else:
        lines.append("Market timing analysis not available. Review issue growth and star velocity.")
    lines.append("")
    lines.append("## Why Not Worth")
    if last_score:
        why_not = last_score.get("why_not_worth", "")
        if why_not:
            lines.append(why_not)
    lines.append("")
    lines.append("## Minimum Validation Approach")
    lines.append("")
    lines.append("1. Reply to 3-5 active issues to gauge interest (see issue_reply_drafts.md)")
    lines.append("2. Run 5 user interviews to confirm willingness to pay (see user_interview_questions.md)")
    lines.append("3. Build a minimal landing page to collect waitlist signups (see landing_page_copy.md)")
    lines.append("4. Follow the 7-day validation plan (see 7_day_validation_plan.md)")
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"    Created: {path.name}")
    return path


def _write_landing_page_copy(out_dir, fn, last_score, issues, llm_client, llm_config):
    path = out_dir / "landing_page_copy.md"
    lines = []
    lines.append(f"# Landing Page Copy: {fn}")
    lines.append("")
    lines.append("*Draft — do not publish without review*")
    lines.append("")
    lines.append("---")
    lines.append("")

    repo_name = fn.split("/")[-1] if "/" in fn else fn
    desc = last_score.get("why_opportunity", f"A tool built around {repo_name}") if last_score else f"A tool built around {repo_name}"
    top_pain = ""
    if last_score:
        top_pain = last_score.get("top_pain_cluster_name", "")

    lines.append("## Headline")
    lines.append("")
    lines.append(f"{repo_name}: {desc[:80]}")
    lines.append("")
    lines.append("## Subheadline")
    lines.append("")
    lines.append(f"Stop struggling with {top_pain if top_pain else 'setup and configuration'}. Get a working solution in minutes.")
    lines.append("")
    lines.append("## 3 Pain Points")
    lines.append("")
    if issues:
        pain_points = []
        for iss in issues[:5]:
            t = iss.get("title", "")
            if len(t) > 10:
                pain_points.append(t)
        for i, p in enumerate(pain_points[:3], 1):
            lines.append(f"### Pain {i}: {p}")
            lines.append("")
            lines.append("Users are facing this right now. They're searching for solutions.")
            lines.append("")
    else:
        lines.append("1. Setup and installation is time-consuming and error-prone")
        lines.append("2. Documentation is scattered or outdated")
        lines.append("3. Missing integrations with existing workflows")
        lines.append("")

    lines.append("## 3 Solution Benefits")
    lines.append("")
    lines.append("1. **One-click setup** — Get running in under 5 minutes")
    lines.append("2. **Works with your stack** — No vendor lock-in, open-source friendly")
    lines.append("3. **Built for the community** — Developed iteratively based on real user feedback")
    lines.append("")
    lines.append("## Call to Action")
    lines.append("")
    lines.append("### Primary CTA")
    lines.append("Join the waitlist for early access — free for the first 100 users.")
    lines.append("")
    lines.append("[Join Waitlist](https://example.com/waitlist)")
    lines.append("")
    lines.append("### Secondary CTA")
    lines.append("Star the project on GitHub to follow progress.")
    lines.append("")
    lines.append("## FAQ")
    lines.append("")
    lines.append("**Q: Is this free?**")
    lines.append("A: The MVP will be free. We'll introduce paid plans only for advanced features.")
    lines.append("")
    lines.append("**Q: When will it be ready?**")
    lines.append("A: We're building in public. Expected MVP in 7 days.")
    lines.append("")
    lines.append("**Q: Can I request features?**")
    lines.append("A: Yes! Open a GitHub issue or reply to our discussion thread.")
    lines.append("")
    lines.append("**Q: Is this open source?**")
    lines.append("A: The base version will be open source. Premium features may be proprietary.")
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"    Created: {path.name}")
    return path


def _write_mvp_scope(out_dir, fn, last_score, issues, llm_client, llm_config):
    path = out_dir / "mvp_scope.md"
    lines = []
    lines.append(f"# MVP Scope: {fn}")
    lines.append("")
    lines.append("*Draft scope — adjust based on validation results*")
    lines.append("")
    lines.append("---")
    lines.append("")

    mvp_type_hint = ""
    if last_score:
        mvp_type_hint = last_score.get("mvp_type", "")

    delivery_options = {
        "one_click_installer": "One-click installer script",
        "webui": "Web UI (Gradio/Streamlit)", "plugin": "Plugin",
        "mcp_server": "MCP Server", "chrome_extension": "Chrome Extension",
        "deployment_template": "Docker template / deployment script",
        "tutorial_pack": "Tutorial pack with templates",
        "cloud_wrapper": "Cloud API wrapper", "enterprise_addon": "Enterprise addon",
        "automation_connector": "Automation connector (n8n / Zapier)",
    }
    delivery_type = delivery_options.get(mvp_type_hint, "Minimal CLI script / Web UI")

    lines.append("## MVP Delivery Format")
    lines.append("")
    lines.append(f"**Recommended**: {delivery_type}")
    lines.append("")
    lines.append("## What the MVP Will Do")
    lines.append("")
    lines.append("1. Solve the single most painful issue identified in the issue tracker")
    lines.append("2. Require minimal setup (ideally one command or one click)")
    lines.append("3. Produce a visible result in under 5 minutes")
    lines.append("")
    lines.append("## What the MVP Will NOT Do")
    lines.append("")
    lines.append("1. Support every platform or configuration")
    lines.append("2. Have a polished UI")
    lines.append("3. Include authentication or multi-user support")
    lines.append("4. Handle edge cases and error recovery")
    lines.append("5. Scale beyond single-user or small team use")
    lines.append("")
    lines.append("## 7-Day Build Plan")
    lines.append("")
    lines.append("1. **Day 1**: Core functionality working end-to-end")
    lines.append("2. **Day 2**: Error handling and basic edge cases")
    lines.append("3. **Day 3**: Documentation and usage examples")
    lines.append("4. **Day 4**: Test with 3-5 real users from GitHub issues")
    lines.append("5. **Day 5**: Polish based on feedback")
    lines.append("6. **Day 6**: Create landing page and launch post drafts")
    lines.append("7. **Day 7**: Launch on GitHub Discussions / Reddit / HN / X")
    lines.append("")
    lines.append("## Tech Stack Suggestion")
    lines.append("")
    lines.append("* Python / TypeScript for core logic")
    lines.append("* CLI: Click / Typer (Python) or Commander (Node)")
    lines.append("* Web UI: Gradio / Streamlit for fast prototyping")
    lines.append("* Packaging: pip install / npm install / Docker")
    lines.append("* Distribution: GitHub Releases + PyPI / npm")
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"    Created: {path.name}")
    return path


def _write_issue_reply_drafts(out_dir, fn, issues):
    path = out_dir / "issue_reply_drafts.md"
    lines = []
    lines.append(f"# Issue Reply Drafts: {fn}")
    lines.append("")
    lines.append("*DRAFT — Do not post automatically. Review and customize before replying.*")
    lines.append("")
    lines.append("---")
    lines.append("")

    if not issues:
        lines.append("No issues available to draft replies.")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return path

    for iss in issues[:8]:
        title = iss.get("title", "")
        labels = ", ".join(iss.get("labels", [])[:3])
        url = iss.get("url", "")
        body = (iss.get("body", "") or "")[:300]
        lines.append(f"## Issue: {title}")
        lines.append("")
        if url:
            lines.append(f"Source: {url}")
        lines.append(f"Labels: {labels}")
        lines.append("")
        if body:
            lines.append("> " + body.replace("\n", "\n> "))
            lines.append("")

        lines.append("### Draft Reply")
        lines.append("")
        lines.append(f"> Hi! I'm working on a small tool to address exactly this.")
        lines.append(f"> ")
        lines.append(f"> From your experience with this issue, could you help me understand:")
        lines.append(f"> ")
        lines.append(f"> 1. How much time does this problem cost you per week?")
        lines.append(f"> 2. Have you found any workarounds?")
        lines.append(f"> 3. Would you be interested in testing an early prototype?")
        lines.append(f"> ")
        lines.append(f"> No spam, no sales — just trying to build something useful for the community.")
        lines.append("")
        lines.append("---")
        lines.append("")

    lines.append("")
    lines.append("*End of drafts*")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"    Created: {path.name}")
    return path


def _write_user_interview_questions(out_dir, fn, issues, llm_client, llm_config):
    path = out_dir / "user_interview_questions.md"
    lines = []
    lines.append(f"# User Interview Questions: {fn}")
    lines.append("")
    lines.append("*Prepare these questions before reaching out to potential users.*")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 10 Validation Questions")
    lines.append("")
    questions = [
        ("Problem Validation",
         "1. How are you currently solving this problem?\n   *Follow-up: What workaround or manual process do you use?*"),
        ("Frequency & Impact",
         "2. How often do you encounter this issue?\n   *Follow-up: How much time does it waste per week?*"),
        ("Current Solutions",
         "3. What tools or services have you tried for this?\n   *Follow-up: Why didn't they work?*"),
        ("Willingness to Pay",
         "4. If a tool solved this for $10-20/month, would you pay for it?\n   *Follow-up: What's the most you'd pay?*"),
        ("Feature Priority",
         "5. What's the one feature that would make you switch to a new tool today?"),
        ("Early Adopter",
         "6. Would you be willing to test an early version and give feedback?\n   *Follow-up: What's your preferred communication channel?*"),
        ("Alternative Behavior",
         "7. If this problem had a perfect solution, how would your workflow change?"),
        ("Social Proof",
         "8. Do you know other teams or individuals who share this problem?"),
        ("Urgency",
         "9. How urgent is this problem for you?\n   *Scale 1-10: Nice to have vs must fix now*"),
        ("Commitment",
         "10. If I build a working prototype in 7 days, will you try it and give 15 min of feedback?"),
    ]
    for topic, q in questions:
        lines.append(f"### {topic}")
        lines.append("")
        lines.append(q)
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Interview Tips")
    lines.append("")
    lines.append("* Listen more than you talk (80/20 rule)")
    lines.append("* Don't pitch your solution — understand their problem")
    lines.append("* Ask about specific past behavior, not hypotheticals")
    lines.append("* Look for emotional language (frustration, relief, excitement)")
    lines.append("* Record with permission, transcribe, and look for patterns")
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"    Created: {path.name}")
    return path


def _write_7_day_validation_plan(out_dir, fn, issues, llm_client, llm_config):
    path = out_dir / "7_day_validation_plan.md"
    lines = []
    lines.append(f"# 7-Day Validation Plan: {fn}")
    lines.append("")
    lines.append("*Adjust timeline based on your availability and user feedback velocity.*")
    lines.append("")
    lines.append("---")
    lines.append("")

    days = [
        ("Day 1: Research & Outreach List",
         [
             "Read all open issues in the repo",
             "Identify the top 3 recurring pain points",
             "Find 10-20 users who commented on relevant issues",
             "Create a list of target users for outreach",
             "Set up a simple landing page with waitlist (see landing_page_copy.md)",
         ]),
        ("Day 2: User Outreach",
         [
             "Reply to 5-8 GitHub issues with validation questions (see issue_reply_drafts.md)",
             "Send 10 cold DMs/Discord messages to potential users",
             "Set up 3-5 user interviews for Days 3-4",
             "Post in relevant communities (Reddit, Discord, GitHub Discussions)",
         ]),
        ("Day 3: User Interviews (Round 1)",
         [
             "Conduct 2-3 user interviews using the question guide",
             "Record key insights and pain point quotes",
             "Identify the single most urgent problem to solve",
             "Update MVP scope based on findings",
         ]),
        ("Day 4: User Interviews (Round 2) & MVP Start",
         [
             "Conduct remaining 2-3 user interviews",
             "Start building the core MVP feature",
             "Set up GitHub repo, basic README, and CI",
             "Share progress with interviewees to maintain engagement",
         ]),
        ("Day 5: MVP Working Prototype",
         [
             "Complete the core MVP feature",
             "Add basic error handling",
             "Write minimal documentation",
             "Share prototype with 2-3 engaged users for early feedback",
         ]),
        ("Day 6: Polish & Launch Prep",
         [
             "Incorporate early feedback",
             "Prepare launch posts (see launch_post_drafts.md)",
             "Finalize landing page",
             "Create a short demo video or GIF",
         ]),
        ("Day 7: Launch & Measure",
         [
             "Post on GitHub Discussions, Reddit, Hacker News, X/Twitter",
             "Monitor incoming traffic and signups",
             "Engage with all comments and questions",
             "Review Day 1-6 learnings and decide: iterate, pivot, or drop",
         ]),
    ]

    for day_title, tasks in days:
        lines.append(f"## {day_title}")
        lines.append("")
        for t in tasks:
            lines.append(f"- [ ] {t}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Success Criteria")
    lines.append("")
    lines.append("By end of Day 7, you should have:")
    lines.append("")
    lines.append("* 5+ user interviews completed")
    lines.append("* 20+ waitlist signups or expressions of interest")
    lines.append("* A working prototype that 2+ users have tested")
    lines.append("* Clear signal on whether to continue, pivot, or stop")
    lines.append("* Evidence of willingness to pay (qualitative)")
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"    Created: {path.name}")
    return path


def _write_launch_post_drafts(out_dir, fn, last_score, issues, llm_client, llm_config):
    path = out_dir / "launch_post_drafts.md"
    lines = []
    lines.append(f"# Launch Post Drafts: {fn}")
    lines.append("")
    lines.append("*DRAFT — Review and adapt before posting. Do not post without checking platform rules.*")
    lines.append("")
    lines.append("---")
    lines.append("")

    repo_name = fn.split("/")[-1] if "/" in fn else fn
    desc = last_score.get("why_opportunity", f"A tool for {repo_name} users")[:120] if last_score else f"A tool for {repo_name} users"
    pain = last_score.get("top_pain_cluster_name", "setup and configuration") if last_score else "setup and configuration"

    lines.append("## GitHub Discussion Post")
    lines.append("")
    lines.append("> **Title**: Building in public: solving [pain] for [repo_name] community")
    lines.append("> ")
    lines.append(f"> Hi everyone,")
    lines.append(f"> ")
    lines.append(f"> I've been following the issues in this repo and noticed a recurring theme: **{pain}**.")
    lines.append(f"> ")
    lines.append(f"> I'm building a small tool to address this. Here's what I'm thinking:")
    lines.append(f"> ")
    lines.append("> **The MVP**: A minimal tool that solves the single most painful aspect")
    lines.append("> **Timeline**: Working prototype in 7 days")
    lines.append("> **Pricing**: Free for early users")
    lines.append("> ")
    lines.append("> I'd love your feedback:")
    lines.append("> - Is this something you'd use?")
    lines.append("> - What's the #1 thing it MUST do?")
    lines.append("> - Would you be willing to test an early version?")
    lines.append("> ")
    lines.append("> Building in public, no spam, no sales.")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## Reddit Post")
    lines.append("")
    lines.append("> **Subreddit**: r/[relevant_subreddit]")
    lines.append("> **Title**: Building a free tool for {repo_name} users — what's your biggest pain?")
    lines.append("> ")
    lines.append(f"> I've noticed a lot of people struggling with **{pain}** in the {repo_name} ecosystem.")
    lines.append(f"> ")
    lines.append(f"> Before I build anything, I want to hear from real users:")
    lines.append(f"> ")
    lines.append(f"> 1. What's the most frustrating part of your current workflow?")
    lines.append("> 2. What would a \"magic fix\" look like?")
    lines.append(f"> 3. Would you use a free tool if it solved this in under 5 minutes?")
    lines.append(f"> ")
    lines.append(f"> No self-promotion, just researching before building. Thanks!")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## Hacker News (Show HN) Draft")
    lines.append("")
    lines.append("> **Title**: Show HN: I'm building [tool_name] — solving {pain} for {repo_name} users")
    lines.append("> ")
    lines.append(f"> After seeing repeated issues about **{pain}** in the {repo_name} community,")
    lines.append(f"> I decided to build a focused tool instead of waiting for a solution.")
    lines.append(f"> ")
    lines.append(f"> **What it does**: [1 sentence description]")
    lines.append(f"> **Status**: Early prototype, looking for first users")
    lines.append(f"> **Stack**: [tech stack]")
    lines.append(f"> ")
    lines.append(f"> Would love feedback from the HN community. What am I missing?")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## X/Twitter Thread")
    lines.append("")
    lines.append("1/ I've been watching [repo_name] issues and noticed a pattern.")
    lines.append("")
    lines.append(f"2/ People keep asking about **{pain}**. There's no good solution.")
    lines.append("")
    lines.append("3/ So I'm building one. In public. 7 days to MVP.")
    lines.append("")
    lines.append(f"4/ Day 1: Research. Found {len(issues) if issues else 'several'} related issues.")
    lines.append("")
    lines.append("5/ Want to follow along? Star the repo and join the discussion.")
    lines.append("")
    lines.append(f"6/ What's YOUR biggest pain with {repo_name}? Reply below ↓")
    lines.append("")
    lines.append("---")
    lines.append("")

    lines.append("## 小红书中文文案")
    lines.append("")
    lines.append("**标题**: 我在 GitHub 上发现了一个被忽略的需求")
    lines.append("")
    lines.append("最近在看某个开源项目，发现 issues 区大量用户在反馈同一个问题：")
    lines.append("")
    lines.append(f"**{pain}**")
    lines.append("")
    lines.append("市面上没有好的解决方案。")
    lines.append("")
    lines.append("所以决定自己做一个。")
    lines.append("")
    lines.append("7 天出 MVP。")
    lines.append("免费给早期用户。")
    lines.append("")
    lines.append("会在这里更新进展。")
    lines.append("")
    lines.append("如果你也有这个痛点，评论区告诉我👇")
    lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"    Created: {path.name}")
    return path
