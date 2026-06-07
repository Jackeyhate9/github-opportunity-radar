"""
Generate MVP recommendations based on issue category analysis.
No LLM API calls - rule-based generation.
"""

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


def recommend_mvp(repo: dict, issues: list,
                   classification: dict) -> dict:
    cat_counts = classification.get("category_counts", {})
    sorted_cats = classification.get("sorted_categories", [])

    if not sorted_cats:
        return {
            "recommended_mvp_idea": "暂无明确方向，建议关注项目动态",
            "mvp_type": "observation",
        }

    top_cat = sorted_cats[0][0] if sorted_cats else None
    top_count = sorted_cats[0][1] if sorted_cats else 0
    total_issues = len(issues) or 1

    # Weight by category percentage
    cat_ratios = {
        cat: count / total_issues
        for cat, count in cat_counts.items()
    }

    recommendations = []
    mvp_types = []

    # Check install/deploy
    if cat_ratios.get("install_deploy", 0) > 0.1:
        recs = [
            "一键安装器 - 自动检测系统环境，一键部署项目",
            "Windows/Mac 桌面启动器 - 图形化界面启动和管理",
            "Docker Compose 模板 - 预配置的容器化部署方案",
            "云端部署服务 - 一键部署到云服务器",
            "环境检测工具 - 自动检测并安装缺失的依赖",
        ]
        recommendations.extend(recs)
        mvp_types.append("installer")

    # Check performance
    if cat_ratios.get("performance_gpu", 0) > 0.1:
        recs = [
            "显存配置推荐器 - 根据 GPU 自动推荐最佳参数",
            "低显存启动模板 - 优化配置降低显存占用",
            "FP8/量化配置封装 - 模型量化的一键配置工具",
            "云 GPU 启动器 - 自动连接到云端 GPU 资源",
            "性能调参面板 - 可视化调整推理参数",
        ]
        recommendations.extend(recs)
        mvp_types.append("config_tool")

    # Check workflow
    if cat_ratios.get("workflow_integration", 0) > 0.1:
        recs = [
            "API 连接器 - 提供简单易用的 REST API 封装",
            "MCP Server - 实现 Model Context Protocol 服务器",
            "n8n/Zapier 节点 - 低代码工作流集成节点",
            "Chrome 扩展 - 浏览器插件快速调用",
            "自动化脚本集 - 常用工作流的脚本集合",
        ]
        recommendations.extend(recs)
        mvp_types.append("plugin")

    # Check newbie
    if cat_ratios.get("newbie_docs", 0) > 0.1:
        recs = [
            "中文教程包 - 详细的中文入门教程和示例",
            "可视化 WebUI - 图形界面替代命令行操作",
            "模板市场 - 预配置的用例模板集合",
            "示例项目生成器 - 交互式生成示例代码",
            "付费部署文档 - 详细的私有化部署文档服务",
        ]
        recommendations.extend(recs)
        mvp_types.append("tutorial")

    # Check enterprise
    if cat_ratios.get("enterprise_team", 0) > 0.1:
        recs = [
            "私有化部署脚手架 - 一键私有化部署方案",
            "权限管理插件 - 完善的用户权限系统",
            "团队协作面板 - 多用户协作工作台",
            "SSO/Auth 集成 - 对接企业身份认证系统",
            "审计日志插件 - 操作审计和合规报告",
        ]
        recommendations.extend(recs)
        mvp_types.append("enterprise")

    # Check mobile/UI
    if cat_ratios.get("mobile_ui", 0) > 0.05:
        recs = [
            "移动端 WebApp - 响应式移动端界面",
            "移动端监控面板 - 手机端实时状态监控",
            "PWA 封装 - 将 WebUI 封装为可安装应用",
            "移动端推送服务 - 重要事件实时通知",
        ]
        recommendations.extend(recs)
        mvp_types.append("mobile")

    # Check feature request in general
    if cat_ratios.get("feature_request", 0) > 0.2:
        recs = [
            "插件市场 - 社区贡献的扩展插件平台",
            "功能投票面板 - 用户投票决定下一个功能",
        ]
        recommendations.extend(recs)
        if "feature_platform" not in mvp_types:
            mvp_types.append("feature_platform")

    # Determine primary persona
    if "installer" in mvp_types:
        final_type = "installer"
        best_for = "个人开发者 / 小团队"
    elif "plugin" in mvp_types:
        final_type = "plugin"
        best_for = "个人开发者"
    elif "tutorial" in mvp_types:
        final_type = "tutorial"
        best_for = "个人开发者 / 咨询服务"
    elif "enterprise" in mvp_types:
        final_type = "saas"
        best_for = "小团队 / SaaS"
    elif "mobile" in mvp_types:
        final_type = "mobile"
        best_for = "个人开发者 / 小团队"
    elif "config_tool" in mvp_types:
        final_type = "config_tool"
        best_for = "个人开发者"
    else:
        # Default based on project type
        lang = (repo.get("language") or "").lower()
        desc = (repo.get("description") or "").lower()
        if "python" in lang:
            final_type = "webui"
            best_for = "个人开发者"
            recommendations = [
                "Gradio/Streamlit 前端封装 - 为项目提供美观界面",
                "Web API 服务 - 封装为 REST API",
                "Docker 镜像 - 提供开箱即用的容器",
            ]
        else:
            final_type = "plugin"
            best_for = "个人开发者"
            recommendations = [
                "CLI 工具增强 - 提供更好的命令行体验",
                "IDE 插件 - VS Code / JetBrains 插件",
                "文档站点 - 完善的中文文档和示例",
            ]

    recommendation = recommendations[0]
    alt_recommendations = recommendations[1:4] if len(recommendations) > 1 else []

    return {
        "recommended_mvp_idea": recommendation,
        "alternative_ideas": alt_recommendations,
        "mvp_type": final_type,
        "best_for": best_for,
        "all_ideas": recommendations,
    }
