def analyze_ranking_quality(repo: dict, classification: dict) -> dict:
    flags = []
    warnings = []

    opp_score = repo.get("opportunity_score", 0)
    dq_score = repo.get("data_quality_score", 0)
    hot_score = repo.get("hot_score", 0)
    issue_score = repo.get("issue_score", 0)
    early_score = repo.get("early_score", 0)
    commercial_gap = repo.get("commercial_gap_score", 0)
    commercial_signals = repo.get("readme_commercial_signals", [])
    open_issues_count = repo.get("open_issues_count", 0)
    cat_counts = classification.get("category_counts", {})
    total_issues = sum(cat_counts.values())

    install_ratio = cat_counts.get("install_deploy", 0) / max(total_issues, 1)
    newbie_ratio = cat_counts.get("newbie_docs", 0) / max(total_issues, 1)
    workflow_ratio = cat_counts.get("workflow_integration", 0) / max(total_issues, 1)
    api_ratio = cat_counts.get("api_integration", 0) / max(total_issues, 1)
    plugin_terms = [k for k in cat_counts if any(t in k.lower() for t in ("plugin", "mcp", "connector", "extension", "integration"))]
    plugin_ratio = sum(cat_counts.get(k, 0) for k in plugin_terms) / max(total_issues, 1)

    # 1. High score but low data quality
    if opp_score >= 70 and dq_score < 50:
        flags.append("score_may_be_unreliable")
        warnings.append("分数高但数据质量低，排名可能不可靠")

    # 2. High score but strong commercial signals
    if opp_score >= 70 and len(commercial_signals) >= 3:
        flags.append("commercial_risk")
        warnings.append("分数高但商业化信号强，可能存在成熟竞品")

    # 3. Few issues but high score
    if open_issues_count < 5 and opp_score >= 65:
        flags.append("weak_issue_evidence")
        warnings.append("Issue 数量少但分数高，需求证据不足")

    # 4. High heat but no pain evidence
    if hot_score >= 20 and issue_score < 10:
        flags.append("hype_without_pain")
        warnings.append("热度高但 Issue 需求弱，可能只是围观而非真实需求")

    # 5. Strong pain but low heat
    if issue_score >= 20 and hot_score < 10:
        flags.append("niche_but_painful")
        warnings.append("痛点明确但热度低，适合小团队深耕")

    # 6. Service-first pattern
    if install_ratio > 0.15 or newbie_ratio > 0.15:
        flags.append("service_first")
        warnings.append("安装/文档/新手类痛点占比高，适合先做服务而非产品")

    # 7. Plugin-first pattern
    if workflow_ratio > 0.15 or api_ratio > 0.15 or plugin_ratio > 0.15:
        flags.append("plugin_first")
        warnings.append("工作流/API/集成类痛点占比高，适合先做插件或连接器")

    # Build suggestion
    if "hype_without_pain" in flags and "score_may_be_unreliable" in flags:
        suggestion = "先不要做产品，手动验证 Issue 是否真实代表付费需求"
    elif "commercial_risk" in flags:
        suggestion = "存在成熟竞品，建议做差异化定位"
    elif "service_first" in flags and "plugin_first" in flags:
        suggestion = "痛点混合，建议先发布服务/教程，再考虑产品化"
    elif "service_first" in flags:
        suggestion = "考虑做部署服务、教程模板、咨询，而非 SaaS 产品"
    elif "plugin_first" in flags:
        suggestion = "考虑做插件、MCP Server、Chrome 扩展、n8n 节点"
    elif "niche_but_painful" in flags:
        suggestion = "适合小团队深耕细分领域，不要急于扩展"
    elif "weak_issue_evidence" in flags:
        suggestion = "Issue 数据不足，建议手动调研 Reddit/Discord 确认需求"
    elif not flags:
        suggestion = "排名信号正常，按最终建议推进"
    else:
        suggestion = "综合信号混合，建议人工研判"

    return {
        "ranking_flags": flags,
        "ranking_warning": "; ".join(warnings) if warnings else "",
        "suggested_next_action": suggestion,
    }
