import json
from datetime import datetime, timezone
from src.config import settings
from src.database import get_all_watchlist_repos, save_daily_scan_run, get_or_create_repo
from src.database import save_snapshot, save_issues, save_score, finish_scan_run
from src.database import get_last_two_snapshots, get_latest_score_for_repo
from src.database import set_watchlist_needs_review
from src.repo_page_scraper import scrape_repo_page, scrape_issues_direct
from src.readme_analyzer import analyze_readme
from src.issue_classifier import classify_issues
from src.scorer import calculate_opportunity_score
from src.mvp_recommender import recommend_mvp

TRIGGER_KEYWORDS = [
    "pricing", "enterprise", "self-host", "deploy", "api",
    "integration", "windows", "cuda", "oom", "feature request",
    "plugin", "mcp", "workflow",
]


def compute_deltas(repo_id, repo, new_scores):
    deltas = {
        "stars_delta_since_last_scan": 0,
        "stars_delta_since_first_seen": 0,
        "issues_delta_since_last_scan": 0,
        "opportunity_score_delta": 0,
        "data_quality_score_delta": 0,
        "recommendation_changed": False,
        "needs_review": False,
        "review_reason": "",
    }

    snapshots = get_last_two_snapshots(repo_id)
    last_score = get_latest_score_for_repo(repo_id)

    if len(snapshots) >= 2:
        prev = snapshots[1]
        deltas["stars_delta_since_last_scan"] = repo.get("stars", 0) - (prev.get("stars", 0) or 0)
        deltas["issues_delta_since_last_scan"] = repo.get("open_issues_count", 0) - (prev.get("open_issues", 0) or 0)
    elif snapshots:
        prev = snapshots[0]
        deltas["stars_delta_since_first_seen"] = repo.get("stars", 0) - (prev.get("stars", 0) or 0)

    if len(snapshots) >= 1:
        first = snapshots[-1]
        deltas["stars_delta_since_first_seen"] = repo.get("stars", 0) - (first.get("stars", 0) or 0)

    if last_score:
        deltas["opportunity_score_delta"] = new_scores.get("opportunity_score", 0) - (last_score.get("opportunity_score", 0) or 0)
        deltas["data_quality_score_delta"] = new_scores.get("data_quality_score", 0) - (last_score.get("data_quality_score", 0) or 0)
        old_rec = last_score.get("final_recommendation", "")
        new_rec = new_scores.get("final_recommendation", "")
        if old_rec and new_rec and old_rec != new_rec:
            deltas["recommendation_changed"] = True

    reasons = []
    if deltas["stars_delta_since_last_scan"] >= 100:
        reasons.append(f"Star growth: +{deltas['stars_delta_since_last_scan']}")
    if deltas["issues_delta_since_last_scan"] >= 5:
        reasons.append(f"New issues: +{deltas['issues_delta_since_last_scan']}")
    if deltas["opportunity_score_delta"] >= 10:
        reasons.append(f"Score increase: +{deltas['opportunity_score_delta']}")
    if deltas["recommendation_changed"]:
        reasons.append(f"Recommendation changed: {old_rec} → {new_rec}")

    if reasons:
        deltas["needs_review"] = True
        deltas["review_reason"] = "; ".join(reasons)

    return deltas


def check_issue_keywords(issues, existing_reasons):
    new_reasons = []
    for iss in (issues or []):
        title = iss.get("title", "").lower()
        body = (iss.get("body", "") or "").lower()
        text = title + " " + body
        for kw in TRIGGER_KEYWORDS:
            if kw in text:
                new_reasons.append(f"Keyword '{kw}' in issue: {iss.get('title', '')[:80]}")
                break
    return new_reasons


def run_daily_scan():
    print("=" * 68)
    print("  Daily Watchlist Scan")
    print("=" * 68)

    watchlist_repos = get_all_watchlist_repos()
    if not watchlist_repos:
        print("\n  Watchlist is empty. Add repos from WebUI or latest scan first.")
        print("  Use: python app.py scan --enable-llm ... to scan and add to watchlist")
        return []

    print(f"  Watchlist repos: {len(watchlist_repos)}")
    print()

    scan_run_id = save_daily_scan_run()
    print(f"  Daily scan run #{scan_run_id}")

    updated = []
    needs_review_count = 0
    for idx, wl in enumerate(watchlist_repos):
        fn = wl.get("full_name", "")
        repo_id = wl.get("repo_id") or wl.get("rid")
        print(f"  [{idx+1}/{len(watchlist_repos)}] {fn}")

        repo = scrape_repo_page(fn)
        if not repo:
            print(f"    SKIP: could not fetch repo page")
            continue

        repo_id_db = get_or_create_repo(repo)
        snapshot_id, data_quality = save_snapshot(scan_run_id, repo_id_db, repo)

        readme_text = repo.get("readme_text", "")
        readme_analysis = analyze_readme(readme_text)
        repo["readme_early_signals"] = readme_analysis["early_signals"]
        repo["readme_commercial_signals"] = readme_analysis["commercial_signals"]
        repo["readme_major_version"] = readme_analysis["major_version"]

        max_issues = settings.default_max_issues_per_repo
        issues = scrape_issues_direct(fn, max_count=max_issues)
        classification = classify_issues(issues)
        save_issues(snapshot_id, issues)

        scores = calculate_opportunity_score(repo, issues, classification, data_quality,
                                              llm_status="", llm_analysis=None)
        repo.update(scores)
        repo["data_quality"] = data_quality

        mvp = recommend_mvp(repo, issues, classification)
        repo.update(mvp)

        save_score(scan_run_id, snapshot_id, repo, mvp, classification)

        deltas = compute_deltas(repo_id_db or repo_id, repo, scores)
        keyword_reasons = check_issue_keywords(issues, deltas.get("review_reason", ""))
        if keyword_reasons:
            deltas["needs_review"] = True
            existing = deltas.get("review_reason", "")
            if existing:
                deltas["review_reason"] = existing + "; " + "; ".join(keyword_reasons[:3])
            else:
                deltas["review_reason"] = "; ".join(keyword_reasons[:3])

        if deltas["needs_review"]:
            needs_review_count += 1
            set_watchlist_needs_review(repo_id_db or repo_id, True, deltas["review_reason"])

        repo["_deltas"] = deltas
        updated.append(repo)

        delta_str = ""
        if deltas["stars_delta_since_last_scan"]:
            delta_str = f" stars: {deltas['stars_delta_since_last_scan']:+d}"
        issues_delta = deltas.get("issues_delta_since_last_scan", 0)
        score_delta = deltas.get("opportunity_score_delta", 0)
        print(f"    Score: {scores.get('opportunity_score', 0)}/100{delta_str}")
        if issues_delta:
            print(f"    Issues delta: {issues_delta:+d}")
        if score_delta:
            print(f"    Score delta: {score_delta:+d}")
        if deltas["needs_review"]:
            print(f"    [!] Needs review: {deltas['review_reason'][:100]}")

    finish_scan_run(scan_run_id, "completed")

    print(f"\n  Daily scan complete. Updated: {len(updated)}, Needs review: {needs_review_count}")
    return updated, scan_run_id
