import csv
import json
import copy
from datetime import datetime, timezone
from src.config import OUTPUTS_DIR
from src.scorer import RECOMMENDATION_MAP_CN


def _timestamp():
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def export_csv(results):
    ts = _timestamp()
    path = OUTPUTS_DIR / f"report_{ts}.csv"
    fields = [
        "rank", "full_name", "url", "description", "language",
        "stars", "stars_delta_7d", "forks", "open_issues_count",
        "data_quality", "data_quality_score", "data_quality_label",
        "opportunity_verdict", "final_recommendation",
        "hot_score", "issue_score", "early_score",
        "commercial_gap_score", "mvp_feasibility_score", "opportunity_score",
        "readme_early_signals", "readme_commercial_signals",
        "top_pain_categories", "top_pain_cluster", "top_pain_cluster_name",
        "recommended_mvp_idea", "mvp_type",
        "llm_summary", "llm_mvp_idea", "llm_target_customer",
        "llm_monetization_angle", "llm_build_difficulty", "llm_confidence",
        "llm_status",
        "ranking_flags", "ranking_warning", "suggested_next_action",
    ]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for i, r in enumerate(results, 1):
            row = copy.deepcopy(r)
            row["rank"] = i
            for k in ["readme_early_signals", "readme_commercial_signals",
                       "top_pain_categories", "ranking_flags"]:
                if isinstance(row.get(k), (list, dict)):
                    row[k] = json.dumps(row[k], ensure_ascii=False)
            w.writerow(row)
    print(f"  CSV report saved: {path}")
    return path


def export_json(results):
    ts = _timestamp()
    path = OUTPUTS_DIR / f"report_{ts}.json"
    clean = []
    for i, r in enumerate(results, 1):
        entry = {
            "rank": i,
            "full_name": r.get("full_name", ""),
            "url": r.get("url", ""),
            "description": r.get("description", ""),
            "language": r.get("language", ""),
            "stars": r.get("stars", 0),
            "stars_delta_7d": r.get("stars_delta_7d"),
            "forks": r.get("forks", 0),
            "open_issues_count": r.get("open_issues_count", 0),
            "data_quality_score": r.get("data_quality_score", 0),
            "data_quality_label": r.get("data_quality_label", ""),
            "opportunity_verdict": r.get("opportunity_verdict", ""),
            "final_recommendation": r.get("final_recommendation", ""),
            "scores": {
                "hot": r.get("hot_score", 0),
                "issue": r.get("issue_score", 0),
                "early": r.get("early_score", 0),
                "commercial_gap": r.get("commercial_gap_score", 0),
                "mvp_feasibility": r.get("mvp_feasibility_score", 0),
                "total": r.get("opportunity_score", 0),
            },
            "top_pain_cluster": r.get("top_pain_cluster_name", ""),
            "readme_early_signals": r.get("readme_early_signals", []),
            "readme_commercial_signals": r.get("readme_commercial_signals", []),
            "top_pain_categories": r.get("top_pain_categories", {}),
            "recommended_mvp_idea": r.get("recommended_mvp_idea", ""),
            "mvp_type": r.get("mvp_type", ""),
            "all_ideas": r.get("all_ideas", []),
            "topics": r.get("topics", []),
            "license": r.get("license_name", ""),
            "ranking_flags": json.loads(r["ranking_flags"]) if isinstance(r.get("ranking_flags"), str) else r.get("ranking_flags", []),
            "ranking_warning": r.get("ranking_warning", ""),
            "suggested_next_action": r.get("suggested_next_action", ""),
        }
        if r.get("llm_summary"):
            entry["llm_analysis"] = {
                "summary": r.get("llm_summary", ""),
                "mvp_idea": r.get("llm_mvp_idea", ""),
                "target_customer": r.get("llm_target_customer", ""),
                "monetization_angle": r.get("llm_monetization_angle", ""),
                "build_difficulty": r.get("llm_build_difficulty", ""),
                "confidence": r.get("llm_confidence", ""),
                "status": r.get("llm_status", ""),
                "user_pain_summary": r.get("llm_user_pain_summary", ""),
                "why_now": r.get("llm_why_now", ""),
            }
        clean.append(entry)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2)
    print(f"  JSON report saved: {path}")
    return path


def _write_common_meta(lines, title, results, report_type="latest_scan"):
    lines.append(f"# {title}")
    lines.append("")
    lines.append(f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    lines.append(f"Type: {report_type}")
    if report_type == "latest_scan":
        lines.append(f"Total repos: {len(results)}")
        rec_counts = {}
        for r in results:
            rec = r.get("final_recommendation", "")
            rec_counts[rec] = rec_counts.get(rec, 0) + 1
        if rec_counts:
            rec_label = {k: RECOMMENDATION_MAP_CN.get(k, k) for k in rec_counts}
            parts = [f"{rec_label[k]}: {v}" for k, v in rec_counts.items()]
            lines.append("Recommendation distribution: " + " | ".join(parts))
    lines.append("")
    lines.append("---")
    lines.append("")


def _write_repo_section(lines, r):
    verdict = r.get("opportunity_verdict", "")
    rec_key = r.get("final_recommendation", "")
    rec_cn = RECOMMENDATION_MAP_CN.get(rec_key, rec_key)
    lines.append(f"**Score**: {r.get('opportunity_score', 0)}/100 | "
                 f"**DQ**: {r.get('data_quality_score', 0)} ({r.get('data_quality_label', '')}) | "
                 f"**Verdict**: {verdict} | "
                 f"**Recommendation**: {rec_cn}")
    lines.append(f"Stars: {r.get('stars', 0)} | "
                 f"+/7d: {r.get('stars_delta_7d', 'N/A')} | "
                 f"Issues: {r.get('open_issues_count', 0)} | "
                 f"Language: {r.get('language', 'N/A')}")
    lines.append(f"Description: {r.get('description', '')[:200]}")
    lines.append("")
    lines.append("| Dimension | Score | Max |")
    lines.append("|---|---|---|")
    lines.append(f"| Hot | {r.get('hot_score', 0)} | 25 |")
    lines.append(f"| Issue Demand | {r.get('issue_score', 0)} | 25 |")
    lines.append(f"| Early Stage | {r.get('early_score', 0)} | 20 |")
    lines.append(f"| Commercial Gap | {r.get('commercial_gap_score', 0)} | 20 |")
    lines.append(f"| MVP Feasibility | {r.get('mvp_feasibility_score', 0)} | 10 |")
    lines.append("")
    top_cluster = r.get("top_pain_cluster_name", "")
    evid = r.get("pain_cluster_evidence", [])
    if top_cluster:
        lines.append(f"**Top Pain Cluster**: {top_cluster} ({r.get('top_pain_cluster_count', 0)} issues)")
        if evid:
            lines.append("Evidence:")
            for e in evid[:3]:
                lines.append(f"- {e}")
        lines.append("")
    lines.append(f"**MVP Idea**: {r.get('recommended_mvp_idea', 'N/A')}")
    lines.append(f"**Why Opportunity**: {r.get('why_opportunity', '')[:300]}")
    lines.append(f"**Why Not Worth**: {r.get('why_not_worth', '')[:300]}")
    lines.append("")
    flags = r.get("ranking_flags", [])
    if isinstance(flags, str):
        import json as _json
        try:
            flags = _json.loads(flags)
        except Exception:
            flags = [flags]
    if isinstance(flags, list) and flags:
        lines.append(f"**Flags**: {', '.join(flags)}")
        warn = r.get("ranking_warning", "")
        if warn:
            lines.append(f"**Warning**: {warn}")
        next_action = r.get("suggested_next_action", "")
        if next_action:
            lines.append(f"**Suggestion**: {next_action}")
        lines.append("")

    llm_summary = r.get("llm_summary", "")
    llm_status = r.get("llm_status", "")
    if llm_summary and llm_status == "success":
        lines.append("### LLM Enhanced Analysis")
        lines.append(f"**Summary**: {llm_summary}")
        lines.append(f"**Target Customer**: {r.get('llm_target_customer', '')}")
        lines.append(f"**Monetization**: {r.get('llm_monetization_angle', '')}")
        lines.append(f"**Build Difficulty**: {r.get('llm_build_difficulty', '')}")
        lines.append(f"**Confidence**: {r.get('llm_confidence', '')}")
        plan = r.get("llm_build_plan", None)
        if isinstance(plan, list) and plan:
            lines.append("**7 Day Build Plan**:")
            for step in plan:
                lines.append(f"- {step}")
        risks = r.get("llm_risks", None)
        if isinstance(risks, list) and risks:
            lines.append("**Risks**: " + "; ".join(risks[:3]))
        lines.append("")


def export_markdown(results, report_type="latest_scan"):
    ts = _timestamp()
    path = OUTPUTS_DIR / f"report_{ts}.md"
    lines = []
    _write_common_meta(lines, "GitHub Opportunity Radar - Scan Report", results, report_type)

    for i, r in enumerate(results, 1):
        lines.append(f"## {i}. [{r.get('full_name', '')}]({r.get('url', '')})")
        lines.append("")
        _write_repo_section(lines, r)
        lines.append("---")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  Markdown report saved: {path}")
    return path


def export_watchlist_report(watchlist_data):
    ts = _timestamp()
    path = OUTPUTS_DIR / f"watchlist_{ts}.md"
    lines = []
    _write_common_meta(lines, "Watchlist Opportunity Report", watchlist_data, "watchlist_report")

    for i, w in enumerate(watchlist_data, 1):
        fn = w.get("full_name", "")
        lines.append(f"## {i}. {fn}")
        lines.append("")
        lines.append(f"**Score**: {w.get('opportunity_score', 'N/A')}/100 | "
                     f"**DQ**: {w.get('data_quality_score', 'N/A')} | "
                     f"**Verdict**: {w.get('opportunity_verdict', 'N/A')} | "
                     f"**Recommendation**: {RECOMMENDATION_MAP_CN.get(w.get('final_recommendation', ''), w.get('final_recommendation', 'N/A'))}")
        lines.append(f"Stars: {w.get('stars', 'N/A')} | "
                     f"+/7d: {w.get('stars_delta_7d', 'N/A')} | "
                     f"Stars since first seen: {w.get('stars_delta_since_first_seen', 'N/A')}")
        lines.append(f"Status: {w.get('status', '')} | User Rating: {w.get('user_rating', 0)}/5")
        lines.append("")

        needs_review = w.get("needs_review", 0)
        if needs_review:
            lines.append(f"**⚠ Needs Review**: {w.get('review_reason', '')}")
            lines.append("")

        hyp = w.get("user_hypothesis", "")
        if hyp:
            lines.append(f"**My Hypothesis**: {hyp}")
        tgt = w.get("target_user_guess", "")
        if tgt:
            lines.append(f"**Target User**: {tgt}")
        mon = w.get("monetization_guess", "")
        if mon:
            lines.append(f"**Monetization Guess**: {mon}")
        val_next = w.get("validation_next_step", "")
        if val_next:
            lines.append(f"**Validation Next Step**: {val_next}")
        val_res = w.get("validation_result", "")
        if val_res:
            lines.append(f"**Validation Result**: {val_res}")
        lines.append("")
        lines.append("---")
        lines.append("")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"  Watchlist report saved: {path}")
    return path
