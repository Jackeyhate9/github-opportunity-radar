import math
from datetime import datetime, timezone
from typing import Optional

CATEGORY_NAMES_CN = {
    "install_deploy": "安装部署痛点",
    "performance_gpu": "显存/性能痛点",
    "workflow_integration": "工作流断点",
    "newbie_docs": "新手不会用",
    "feature_request": "功能请求",
    "enterprise_team": "企业/团队需求",
    "compatibility_upgrade": "兼容性/迁移问题",
    "mobile_ui": "移动端/前端UI机会",
}


def calculate_hot_score(stars, created_at, pushed_at,
                        stars_delta_1d=None, stars_delta_7d=None,
                        stars_delta_30d=None):
    score = 0.0

    if stars_delta_7d is not None and stars_delta_7d > 0:
        growth_rate = stars_delta_7d / max(stars, 1)
        score += min(growth_rate * 10, 15)
        if stars_delta_7d > 100:
            score += 5
        elif stars_delta_7d > 50:
            score += 3
        elif stars_delta_7d > 10:
            score += 1

    if stars_delta_1d is not None and stars_delta_1d > 0:
        if stars_delta_1d < 10:
            score += 1
        elif stars_delta_1d < 50:
            score += 2
        else:
            score += 3

    if stars > 0:
        stars_norm = min(stars / 1000, 20)
        stars_score = math.log(stars_norm + 1) * 4
        score += min(stars_score, 12)

    if created_at:
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - created).days
            if age_days < 30:
                score += 8
            elif age_days < 90:
                score += 6
            elif age_days < 180:
                score += 4
            elif age_days < 365:
                score += 2
        except ValueError:
            pass

    if pushed_at:
        try:
            pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
            hours_since = (datetime.now(timezone.utc) - pushed).total_seconds() / 3600
            if hours_since < 24:
                score += 5
            elif hours_since < 72:
                score += 4
            elif hours_since < 168:
                score += 3
            elif hours_since < 720:
                score += 1
        except ValueError:
            pass

    return min(score, 25)


def calculate_issue_score(open_issues_count, issues):
    score = 0.0

    if open_issues_count >= 50:
        score += 10
    elif open_issues_count >= 30:
        score += 8
    elif open_issues_count >= 20:
        score += 6
    elif open_issues_count >= 10:
        score += 4
    elif open_issues_count >= 5:
        score += 2

    recent_count = len(issues) if issues else 0
    if recent_count >= 20:
        score += 5
    elif recent_count >= 10:
        score += 4
    elif recent_count >= 5:
        score += 3
    elif recent_count >= 3:
        score += 1

    if issues:
        total_comments = sum(i.get("comments_count", 0) for i in issues)
        if total_comments > 20:
            score += 5
        elif total_comments > 10:
            score += 3
        elif total_comments > 5:
            score += 1

    if issues:
        helpful_labels = ["enhancement", "feature request", "help wanted",
                          "good first issue", "bug"]
        label_count = sum(
            1 for i in issues
            for lb in i.get("labels", [])
            if lb.lower() in helpful_labels
        )
        if label_count > 5:
            score += 2

    return min(score, 25)


def calculate_early_score(created_at, readme_early_signals,
                          has_releases=False, major_version=None):
    score = 0.0

    if created_at:
        try:
            created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
            age_days = (datetime.now(timezone.utc) - created).days
            if age_days < 30:
                score += 8
            elif age_days < 90:
                score += 6
            elif age_days < 180:
                score += 4
            elif age_days < 365:
                score += 2
        except ValueError:
            pass

    signal_count = len(readme_early_signals) if readme_early_signals else 0
    if signal_count >= 5:
        score += 6
    elif signal_count >= 3:
        score += 5
    elif signal_count >= 1:
        score += 3

    if readme_early_signals:
        signal_text = " ".join(readme_early_signals).lower()
        if "alpha" in signal_text or "beta" in signal_text:
            score += 2
        if "experimental" in signal_text:
            score += 2
        if "roadmap" in signal_text or "todo" in signal_text:
            score += 1
        if "wip" in signal_text or "work in progress" in signal_text:
            score += 1

    if not has_releases:
        score += 2
    if major_version is not None and major_version < 1:
        score += 2
    elif major_version is None:
        score += 1

    return min(score, 20)


def calculate_commercial_gap_score(readme_commercial_signals):
    signal_count = len(readme_commercial_signals) if readme_commercial_signals else 0
    if signal_count == 0:
        return 20.0
    elif signal_count == 1:
        return 15.0
    elif signal_count == 2:
        return 10.0
    elif signal_count <= 4:
        return 5.0
    else:
        return 0.0


def calculate_mvp_feasibility_score(top_categories, issues,
                                     readme_data_quality="medium"):
    score = 5.0

    easy_mvp_cats = {
        "install_deploy": 2.0,
        "mobile_ui": 2.0,
        "newbie_docs": 1.5,
        "workflow_integration": 1.5,
        "feature_request": 0.5,
    }
    hard_mvp_cats = {
        "performance_gpu": -0.5,
        "enterprise_team": 1.0,
    }

    for cat in top_categories:
        score += easy_mvp_cats.get(cat, 0)
        score += hard_mvp_cats.get(cat, 0)

    if len(issues) > 15:
        score += 1
    elif len(issues) > 8:
        score += 0.5

    if issues:
        install_count = sum(
            1 for i in issues
            if i.get("category") == "install_deploy"
        )
        if install_count > 3:
            score += 1

    if readme_data_quality == "low":
        score -= 1

    return max(0, min(score, 10))


def calculate_data_quality_score(repo: dict, issues: list,
                                 classification: dict,
                                 llm_status: str = "") -> dict:
    score = 0
    reasons = []

    # 1. Basic repo info completeness: 20pt
    basic_checks = {
        "full_name": repo.get("full_name"),
        "url": repo.get("url"),
        "description": repo.get("description"),
        "stars": repo.get("stars", 0) > 0,
        "language": repo.get("language"),
    }
    basic_score = sum(4 for k, v in basic_checks.items() if v)
    score += basic_score
    if basic_score >= 20:
        reasons.append("基础信息完整")
    elif basic_score >= 12:
        reasons.append(f"基础信息部分缺失 ({basic_score}/20)")
    else:
        reasons.append(f"基础信息严重缺失 ({basic_score}/20)")

    # 2. README fetch success: 20pt
    readme_text = repo.get("readme_text", "") or ""
    readme_len = len(readme_text)
    if readme_len > 500:
        readme_score = 20
        reasons.append("README 抓取成功且完整")
    elif readme_len > 200:
        readme_score = 12
        reasons.append("README 内容较短")
    elif readme_len > 50:
        readme_score = 6
        reasons.append("README 非常简短")
    else:
        readme_score = 0
        reasons.append("README 缺失")
    score += readme_score

    # 3. Issues fetch quality: 30pt
    issue_count = len(issues) if issues else 0
    if issue_count >= 20:
        issue_score_val = 30
        reasons.append(f"Issue 数据充足 ({issue_count} 条)")
    elif issue_count >= 10:
        issue_score_val = 20
        reasons.append(f"Issue 数据中等 ({issue_count} 条)")
    elif issue_count >= 1:
        issue_score_val = 10
        reasons.append(f"Issue 数据较少 ({issue_count} 条)")
    else:
        issue_score_val = 0
        reasons.append("未抓到 Issue 数据")
    score += issue_score_val

    # 4. Issue classification quality: 15pt
    cat_counts = classification.get("category_counts", {})
    active_cats = sum(1 for v in cat_counts.values() if v > 0)
    if active_cats >= 3:
        class_score = 15
        reasons.append(f"Issue 分类丰富 ({active_cats} 类)")
    elif active_cats >= 1:
        class_score = 8
        reasons.append(f"Issue 分类较少 ({active_cats} 类)")
    else:
        class_score = 0
        reasons.append("无 Issue 分类")
    score += class_score

    # 5. LLM analysis status: 15pt
    if llm_status == "success":
        llm_score = 15
    elif llm_status == "failed":
        llm_score = 5
    elif llm_status == "unavailable":
        llm_score = 5
    else:
        llm_score = 0
    score += llm_score

    if llm_status == "success":
        reasons.append("LLM 分析成功")
    elif llm_status and llm_score > 0:
        reasons.append("LLM 分析不可用，使用规则")
    else:
        reasons.append("LLM 未启用")

    score = min(score, 100)

    if score >= 75:
        label = "high"
    elif score >= 45:
        label = "medium"
    else:
        label = "low"

    return {
        "data_quality_score": score,
        "data_quality_label": label,
        "data_quality_reasons": reasons,
    }


def calculate_opportunity_verdict(repo: dict, data_quality_score: int,
                                  llm_status: str = "") -> dict:
    opp_score = repo.get("opportunity_score", 0)
    hot_score = repo.get("hot_score", 0)
    issue_score = repo.get("issue_score", 0)
    early_score = repo.get("early_score", 0)
    commercial_gap = repo.get("commercial_gap_score", 0)
    commercial_signals = repo.get("readme_commercial_signals", [])
    cat_counts = repo.get("top_pain_categories", {})
    mvp_type = repo.get("mvp_type", "")

    has_commercial_prod = any(
        s.lower() in ("pricing", "enterprise", "contact sales", "subscription",
                       "paid", "license key", "saas")
        for s in (commercial_signals or [])
    )

    verdict = "weak_candidate"
    reason = ""

    if data_quality_score < 35:
        verdict = "avoid"
        reason = "数据质量过低，不足以做出可靠判断"
    elif has_commercial_prod and commercial_gap < 5:
        verdict = "avoid"
        reason = "已有成熟商业化方案，竞争激烈"
    elif opp_score >= 75 and data_quality_score >= 70:
        verdict = "strong_candidate"
        reason = "机会评分高、数据质量高，适合重点研究"
    elif opp_score >= 60:
        verdict = "niche_candidate"
        reason = "有机会，但方向较窄，需进一步验证"
    elif opp_score < 50:
        verdict = "weak_candidate"
        reason = "暂不值得做，需求不够明确"
    elif commercial_gap < 5 and early_score < 10:
        verdict = "avoid"
        reason = "项目已成熟，商业化程度高，早期机会有限"

    workflow_ratio = cat_counts.get("workflow_integration", 0) / max(sum(cat_counts.values()), 1)
    install_ratio = cat_counts.get("install_deploy", 0) / max(sum(cat_counts.values()), 1)
    newbie_ratio = cat_counts.get("newbie_docs", 0) / max(sum(cat_counts.values()), 1)
    enterprise_ratio = cat_counts.get("enterprise_team", 0) / max(sum(cat_counts.values()), 1)

    if verdict == "weak_candidate" and install_ratio > 0.15:
        verdict = "service_opportunity"
        reason = "安装部署痛点集中，适合做部署服务或教程"
    elif verdict == "weak_candidate" and newbie_ratio > 0.15:
        verdict = "service_opportunity"
        reason = "新手教程需求明显，适合做教程或模板包"
    elif workflow_ratio > 0.2 or mvp_type in ("plugin", "mcp_server"):
        if verdict in ("strong_candidate", "niche_candidate", "weak_candidate"):
            verdict = "plugin_opportunity"
            reason = "工作流/API 集成需求集中，适合做插件或 MCP Server"
    elif install_ratio > 0.15:
        if verdict in ("weak_candidate", "niche_candidate"):
            verdict = "service_opportunity"
            reason = "安装部署/文档痛点集中，适合做部署服务或教程"

    if verdict == "niche_candidate" and enterprise_ratio > 0.1:
        verdict = "service_opportunity"
        reason = "企业需求明显，适合做私有化部署服务"

    return {
        "opportunity_verdict": verdict,
        "verdict_reason": reason,
    }


def generate_pain_cluster_summary(issues: list, classification: dict) -> dict:
    cat_counts = classification.get("category_counts", {})
    sorted_cats = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)

    top_cat = sorted_cats[0][0] if sorted_cats else ""
    top_count = sorted_cats[0][1] if sorted_cats else 0

    cat_name = CATEGORY_NAMES_CN.get(top_cat, top_cat)
    evidence = []
    if issues:
        for iss in issues:
            if iss.get("category") == top_cat and len(evidence) < 5:
                title = iss.get("title", "")
                if title:
                    evidence.append(title)

    monetization_hints = {
        "install_deploy": "适合做一键安装器、Docker 模板、Windows 启动器或付费部署服务",
        "performance_gpu": "适合做显存配置推荐器、量化工具、云 GPU 启动器",
        "workflow_integration": "适合做 API 连接器、MCP Server、Chrome 扩展、n8n 节点",
        "newbie_docs": "适合做中文教程包、WebUI 封装、模板市场或付费部署文档",
        "feature_request": "适合做功能投票平台、插件市场或定制开发服务",
        "enterprise_team": "适合做私有化部署脚手架、SSO 集成、权限管理",
        "compatibility_upgrade": "适合做迁移工具、兼容层或升级辅助工具",
        "mobile_ui": "适合做移动端 WebApp、PWA 封装或移动端监控面板",
    }
    hint = monetization_hints.get(top_cat, "需进一步分析需求")
    if not top_cat:
        hint = "暂无明确的痛点聚类"

    return {
        "top_pain_cluster": top_cat,
        "top_pain_cluster_name": cat_name,
        "top_pain_cluster_count": top_count,
        "pain_cluster_evidence": evidence,
        "pain_cluster_monetization_hint": hint,
        "all_category_counts": cat_counts,
    }


def generate_why_opportunity(repo: dict, classification: dict,
                             pain_cluster: dict, llm_analysis: Optional[dict] = None) -> str:
    parts = []
    cat_counts = classification.get("category_counts", {})
    total_issues = sum(cat_counts.values())

    if total_issues > 0:
        pain_cats = [CATEGORY_NAMES_CN.get(k, k) for k, v in cat_counts.items() if v > 0]
        parts.append(f"Issues 反映了明确用户需求，涉及 {len(pain_cats)} 个痛点分类：{' / '.join(pain_cats[:4])}")

    early_signals = repo.get("readme_early_signals", [])
    if early_signals:
        signals_str = " / ".join(early_signals[:4])
        parts.append(f"README 显示项目仍处早期阶段（{signals_str}），尚未成熟商业化")

    commercial_signals = repo.get("readme_commercial_signals", [])
    if not commercial_signals:
        parts.append("README 中无商业化信号（pricing / enterprise / sales），说明存在商业空白可填补")
    else:
        lack_sig = [s for s in commercial_signals
                     if s.lower() not in ("pricing", "enterprise", "contact sales")]
        if not lack_sig and len(commercial_signals) <= 2:
            parts.append("商业化痕迹较轻，仍有独立工具/插件的生存空间")

    top_cluster = pain_cluster.get("top_pain_cluster", "")
    if top_cluster:
        hint = pain_cluster.get("pain_cluster_monetization_hint", "")
        if hint:
            parts.append(hint)

    if llm_analysis and llm_analysis.get("why_now"):
        parts.append(f"LLM 补充分析：{llm_analysis['why_now']}")

    if not parts:
        parts.append("暂无充足数据判断，建议手动验证")

    return "\n\n".join(parts)


def generate_why_not_worth(repo: dict, classification: dict,
                            pain_cluster: dict, data_quality_score: int,
                            llm_analysis: Optional[dict] = None) -> str:
    parts = []

    opp_score = repo.get("opportunity_score", 0)
    commercial_signals = repo.get("readme_commercial_signals", [])
    cat_counts = classification.get("category_counts", {})
    total_issues = sum(cat_counts.values())

    if opp_score < 50:
        parts.append(f"机会评分较低（{opp_score}/100），需求不够明确或项目吸引力不足")

    has_commercial = any(
        s.lower() in ("pricing", "enterprise", "subscription", "contact sales")
        for s in (commercial_signals or [])
    )
    if has_commercial:
        parts.append("项目已有商业化信号，可能存在成熟竞品")

    stars = repo.get("stars", 0)
    if stars > 10000 and total_issues < 10:
        parts.append("Stars 虽多但 Issue 需求不足，说明用户可能是旁观者而非使用者")

    if total_issues < 5:
        parts.append("抓取到的 Issue 数量太少，需求不够明确")

    top_cat = pain_cluster.get("top_pain_cluster", "")
    if top_cat == "performance_gpu":
        parts.append("显存/性能问题通常底层且复杂，个人开发者难以有效解决")

    if data_quality_score < 45:
        parts.append(f"数据质量不足（{data_quality_score}/100），结论可信度低")

    if not parts:
        parts.append("暂无明显挡拆因素，建议进一步验证")

    if llm_analysis and llm_analysis.get("risks"):
        risk_list = llm_analysis.get("risks", [])
        if isinstance(risk_list, list) and risk_list:
            parts.append(f"LLM 风险提示：{' / '.join(risk_list[:3])}")

    return "\n\n".join(parts)


def generate_7day_mvp_plan(repo: dict, classification: dict) -> list:
    cat_counts = classification.get("category_counts", {})
    sorted_cats = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)
    top_cat = sorted_cats[0][0] if sorted_cats else ""
    mvp_type = repo.get("mvp_type", "")

    day_specific = ""
    if mvp_type == "installer" or top_cat == "install_deploy":
        day_specific = "做一键安装器 demo（Shell / Docker Compose / Windows 安装包）"
    elif mvp_type == "config_tool" or top_cat == "performance_gpu":
        day_specific = "做配置推荐器 demo（显存检测 + 自动推荐参数）"
    elif mvp_type == "plugin" or top_cat == "workflow_integration":
        day_specific = "做 connector / MCP Server / Chrome 扩展 demo"
    elif mvp_type == "mobile" or top_cat == "mobile_ui":
        day_specific = "做移动端 WebApp demo"
    elif mvp_type == "tutorial" or top_cat == "newbie_docs":
        day_specific = "做教程包 / 模板包 demo"
    elif mvp_type == "enterprise" or mvp_type == "saas" or top_cat == "enterprise_team":
        day_specific = "做私有部署脚手架说明 / 权限设计架构图"
    elif mvp_type == "feature_platform" or top_cat == "feature_request":
        day_specific = "做功能投票 UI 原型"
    else:
        day_specific = "做最小可用原型"

    plan = [
        f"Day 1：验证 issue 是否集中，整理 10 条代表性痛点。",
        f"Day 2：做 landing page 或 README demo，描述解决方案。",
        f"Day 3：{day_specific}。",
        "Day 4：在相关 issue / discussion / Reddit / Discord 找真实用户反馈。",
        "Day 5：完善 demo，录制 1 分钟视频。",
        "Day 6：发到 GitHub、X、Reddit、Hacker News、相关社区。",
        "Day 7：根据反馈判断是否继续。",
    ]
    return plan


RECOMMENDATION_MAP_CN = {
    "build_prototype_now": "立即构建原型验证",
    "research_manually_first": "先人工调研确认",
    "good_for_service_business": "适合做服务/教程",
    "good_for_plugin_business": "适合做插件/MCP",
    "add_to_watchlist": "加入观察列表",
    "skip": "跳过",
}

FINAL_RECOMMENDATION_KEYS = list(RECOMMENDATION_MAP_CN.keys())


def generate_final_recommendation(verdict: str, opp_score: float,
                                   data_quality_score: int,
                                   hot_score: float = 0,
                                   issue_score: float = 0,
                                   ) -> str:
    if verdict == "strong_candidate" and data_quality_score >= 75 and issue_score >= 15:
        return "build_prototype_now"

    if verdict == "service_opportunity":
        return "good_for_service_business"

    if verdict == "plugin_opportunity":
        return "good_for_plugin_business"

    if verdict == "niche_candidate":
        return "research_manually_first"

    if data_quality_score < 40:
        if verdict in ("weak_candidate", "avoid"):
            return "skip"
        return "research_manually_first"

    if hot_score >= 20 and issue_score < 10:
        return "add_to_watchlist"

    if verdict == "weak_candidate":
        if opp_score < 45:
            return "skip"
        return "add_to_watchlist"

    if verdict == "avoid":
        return "skip"

    if opp_score < 50:
        return "add_to_watchlist"

    if data_quality_score < 60:
        return "research_manually_first"

    return "research_manually_first"


def calculate_opportunity_score(repo, issues, classification, data_quality="medium",
                                 llm_status="", llm_analysis=None):
    hot_score = calculate_hot_score(
        stars=repo.get("stars", 0),
        created_at=repo.get("created_at", ""),
        pushed_at=repo.get("pushed_at", ""),
        stars_delta_1d=repo.get("stars_delta_1d"),
        stars_delta_7d=repo.get("stars_delta_7d"),
        stars_delta_30d=repo.get("stars_delta_30d"),
    )

    issue_score = calculate_issue_score(
        open_issues_count=repo.get("open_issues_count", 0),
        issues=issues,
    )

    early_signals = repo.get("readme_early_signals", [])
    major_version = repo.get("readme_major_version")
    early_score = calculate_early_score(
        created_at=repo.get("created_at", ""),
        readme_early_signals=early_signals,
        has_releases=repo.get("has_releases", False),
        major_version=major_version,
    )

    commercial_signals = repo.get("readme_commercial_signals", [])
    commercial_gap_score = calculate_commercial_gap_score(commercial_signals)

    top_cats = classification.get("top_categories", [])
    mvp_feasibility_score = calculate_mvp_feasibility_score(
        top_cats, issues, data_quality
    )

    total = round(
        hot_score + issue_score + early_score
        + commercial_gap_score + mvp_feasibility_score,
        1
    )

    dq_result = calculate_data_quality_score(repo, issues, classification, llm_status)
    pain_cluster = generate_pain_cluster_summary(issues, classification)

    result = {
        "hot_score": round(hot_score, 1),
        "issue_score": round(issue_score, 1),
        "early_score": round(early_score, 1),
        "commercial_gap_score": round(commercial_gap_score, 1),
        "mvp_feasibility_score": round(mvp_feasibility_score, 1),
        "opportunity_score": min(total, 100),
        "top_pain_categories": classification.get("category_counts", {}),
        "top_categories": top_cats,
        **dq_result,
        **pain_cluster,
    }

    verdict_result = calculate_opportunity_verdict(result, dq_result["data_quality_score"], llm_status)
    result.update(verdict_result)

    result["why_opportunity"] = generate_why_opportunity(
        repo, classification, pain_cluster, llm_analysis
    )
    result["why_not_worth"] = generate_why_not_worth(
        repo, classification, pain_cluster, dq_result["data_quality_score"], llm_analysis
    )
    result["seven_day_mvp_plan"] = generate_7day_mvp_plan(result, classification)
    rec = generate_final_recommendation(
        verdict_result["opportunity_verdict"],
        min(total, 100),
        dq_result["data_quality_score"],
        hot_score=hot_score,
        issue_score=issue_score,
    )
    result["final_recommendation"] = rec

    from src.ranking_diagnostics import analyze_ranking_quality
    ranking = analyze_ranking_quality(result, classification)
    result.update(ranking)

    return result
