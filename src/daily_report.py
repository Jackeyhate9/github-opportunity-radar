from datetime import datetime, timezone
from src.config import OUTPUTS_DIR
from src.database import get_all_watchlist_repos, get_last_two_snapshots
from src.database import get_latest_score_for_repo
from src.scorer import RECOMMENDATION_MAP_CN


def _timestamp():
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _get_repo_scores(full_name, r):
    repo_id = r.get("repo_id") or r.get("rid") or r.get("id")
    last_score = get_latest_score_for_repo(repo_id)
    snapshots = get_last_two_snapshots(repo_id)
    stars_delta = 0
    issues_delta = 0
    if len(snapshots) >= 2:
        prev = snapshots[1]
        stars_delta = r.get("stars", 0) - (prev.get("stars", 0) or 0)
        issues_delta = r.get("open_issues_count", 0) - (prev.get("open_issues", 0) or 0)
    score_val = last_score.get("opportunity_score", 0) if last_score else 0
    old_score_val = score_val
    last_score_val = last_score.get("opportunity_score", 0) if last_score else 0
    if last_score:
        old_score_val = 0
        if len(snapshots) >= 2:
            prev_score = get_latest_score_for_repo(repo_id)
            if prev_score:
                old_score_val = prev_score.get("opportunity_score", 0)
        score_delta = last_score_val - old_score_val
    else:
        score_delta = 0

    needs_review = r.get("needs_review", False)
    review_reason = r.get("review_reason", "")
    rec_key = last_score.get("final_recommendation", "") if last_score else ""
    suggested = last_score.get("suggested_next_action", "") if last_score else ""
    return {
        "stars_delta_since_last_scan": stars_delta,
        "issues_delta_since_last_scan": issues_delta,
        "opportunity_score_delta": score_delta,
        "needs_review": needs_review,
        "review_reason": review_reason,
        "opportunity_score": last_score_val,
        "final_recommendation": rec_key,
        "suggested_next_action": suggested,
    }


def generate_daily_report(updated_repos=None):
    path = OUTPUTS_DIR / f"daily_watchlist_report.md"
    lines = []

    lines.append("# Daily Watchlist Report")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append("")

    watchlist = get_all_watchlist_repos()
    if not watchlist:
        lines.append("Watchlist is empty. Add repos from WebUI or latest scan first.")
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"  Daily report saved: {path}")
        return path

    repos_to_process = updated_repos or watchlist

    needs_review_list = []
    no_change_list = []
    star_gainers = []
    issue_gainers = []
    rec_changes = []

    for r in repos_to_process:
        fn = r.get("full_name", "")
        if updated_repos:
            deltas = r.get("_deltas", {})
            if not deltas:
                continue
            stars_delta = deltas.get("stars_delta_since_last_scan", 0)
            issues_delta = deltas.get("issues_delta_since_last_scan", 0)
            score_delta = deltas.get("opportunity_score_delta", 0)
            needs_review = deltas.get("needs_review", False)
            review_reason = deltas.get("review_reason", "")
            rec_key = r.get("final_recommendation", "")
            suggested = r.get("suggested_next_action", "")
            score_val = r.get("opportunity_score", 0)
            rec_changed = deltas.get("recommendation_changed", False)
        else:
            info = _get_repo_scores(fn, r)
            stars_delta = info["stars_delta_since_last_scan"]
            issues_delta = info["issues_delta_since_last_scan"]
            score_delta = info["opportunity_score_delta"]
            needs_review = info["needs_review"]
            review_reason = info["review_reason"]
            rec_key = info["final_recommendation"]
            suggested = info["suggested_next_action"]
            score_val = info["opportunity_score"]
            rec_changed = False

        rec_cn = RECOMMENDATION_MAP_CN.get(rec_key, rec_key)

        if stars_delta and stars_delta > 0:
            star_gainers.append((fn, stars_delta))
        if issues_delta and issues_delta > 0:
            issue_gainers.append((fn, issues_delta))
        if rec_changed:
            rec_changes.append(fn)
        if needs_review:
            needs_review_list.append({
                "fn": fn, "url": r.get("url", ""),
                "old_score": score_val - score_delta,
                "new_score": score_val,
                "stars_delta": stars_delta,
                "issues_delta": issues_delta,
                "rec_cn": rec_cn,
                "review_reason": review_reason,
                "suggested": suggested,
            })
        elif not stars_delta and not issues_delta and not score_delta:
            no_change_list.append(fn)

    lines.append("## Summary")
    lines.append("")
    lines.append(f"* Watchlist repo count: {len(watchlist)}")
    lines.append(f"* Repos updated: {len(repos_to_process)}")
    lines.append(f"* Repos needing review: {len(needs_review_list)}")
    star_gainers.sort(key=lambda x: -x[1])
    if star_gainers:
        lines.append(f"* Biggest star gainer: {star_gainers[0][0]} (+{star_gainers[0][1]})")
    issue_gainers.sort(key=lambda x: -x[1])
    if issue_gainers:
        lines.append(f"* Biggest issue gainer: {issue_gainers[0][0]} (+{issue_gainers[0][1]})")
    if rec_changes:
        lines.append(f"* Recommendation changes: {len(rec_changes)}")
    lines.append("")
    lines.append("---")
    lines.append("")

    if needs_review_list:
        lines.append("## Needs Review")
        lines.append("")
        for item in needs_review_list:
            lines.append(f"### [{item['fn']}]({item['url']})")
            lines.append("")
            lines.append(f"* **Old Score**: {item['old_score']} → **New Score**: {item['new_score']}")
            lines.append(f"* **Stars Delta**: {item['stars_delta']:+d}")
            lines.append(f"* **Issues Delta**: {item['issues_delta']:+d}")
            lines.append(f"* **Final Recommendation**: {item['rec_cn']}")
            lines.append(f"* **Review Reason**: {item['review_reason']}")
            lines.append(f"* **Suggested Action**: {item['suggested']}")
            lines.append("")
        lines.append("---")
        lines.append("")

    if no_change_list:
        lines.append("## No Major Change")
        lines.append("")
        for fn in no_change_list:
            lines.append(f"* {fn}")
        lines.append("")
        lines.append("---")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  Daily watchlist report saved: {path}")
    return path
