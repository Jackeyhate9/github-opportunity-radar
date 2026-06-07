"""
Classify GitHub issues into opportunity categories.
Uses keyword matching - no LLM API calls needed.
"""

import re

CATEGORY_KEYWORDS = {
    "install_deploy": [
        "install", "setup", "docker", "windows", "mac", "linux",
        "dependency", "environment", "cuda", "torch", "python version",
        "build failed", "installation", "pip", "conda", "package",
        "compile", "dependency conflict", "requirement", "path",
        "import error", "module not found", "not found",
    ],
    "performance_gpu": [
        "out of memory", "oom", "vram", "slow", "latency",
        "performance", "gpu", "cpu", "optimization", "fp8", "quantization",
        "memory leak", "high memory", "crashes", "freeze",
        "response time", "throughput", "bottleneck",
    ],
    "workflow_integration": [
        "export", "import", "sync", "integration", "webhook", "api",
        "plugin", "extension", "automation", "workflow",
        "connector", "webhook", "rest", "graphql", "sdk",
        "callback", "trigger", "event", "pipeline",
    ],
    "newbie_docs": [
        "documentation", "docs", "tutorial", "example", "confusing",
        "how to", "quickstart", "beginner", "newbie",
        "getting started", "guide", "walkthrough",
        "unclear", "missing docs", "example code",
    ],
    "feature_request": [
        "feature request", "enhancement", "support", "add",
        "roadmap", "request", "would be great", "would be nice",
        "please add", "missing feature", "proposal",
    ],
    "enterprise_team": [
        "auth", "permission", "team", "workspace", "sso",
        "private", "self-host", "deploy", "security", "audit",
        "ldap", "oauth", "rbac", "multi-tenant",
        "enterprise", "compliance",
    ],
    "compatibility_upgrade": [
        "breaking change", "version", "compatibility", "migration",
        "upgrade", "deprecated", "legacy", "backward",
        "incompatible", "transition",
    ],
    "mobile_ui": [
        "mobile", "android", "ios", "webui", "ui", "frontend",
        "dashboard", "gradio", "streamlit", "responsive",
        "touch", "mobile friendly", "tablet",
    ],
}


def classify_issue(issue: dict) -> str:
    text = f"{issue.get('title', '')} {issue.get('body', '')}"
    text_lower = text.lower()

    label_score = 0
    for label in issue.get("labels", []):
        for cat, kws in CATEGORY_KEYWORDS.items():
            if any(kw in label.lower() for kw in kws):
                label_score += 0.5

    best_cat = "feature_request"
    best_score = 0

    for cat, keywords in CATEGORY_KEYWORDS.items():
        score = 0
        for kw in keywords:
            matches = re.findall(re.escape(kw), text_lower)
            score += len(matches)
        if "enhancement" in issue.get("labels", []) or "feature request" in issue.get("labels", []):
            if cat == "feature_request":
                score += 2
        score += label_score
        if score > best_score:
            best_score = score
            best_cat = cat

    return best_cat


def classify_issues(issues: list) -> dict:
    cat_counts = {}
    cat_issues = {}

    for issue in issues:
        cat = classify_issue(issue)
        issue["category"] = cat
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
        if cat not in cat_issues:
            cat_issues[cat] = []
        cat_issues[cat].append(issue)

    sorted_cats = sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)

    return {
        "category_counts": cat_counts,
        "category_issues": cat_issues,
        "sorted_categories": sorted_cats,
        "top_categories": [c[0] for c in sorted_cats[:3]],
    }


CATEGORY_NAMES = {
    "install_deploy": "安装部署痛点",
    "performance_gpu": "显存/性能痛点",
    "workflow_integration": "工作流断点",
    "newbie_docs": "新手不会用",
    "feature_request": "功能请求",
    "enterprise_team": "企业/团队需求",
    "compatibility_upgrade": "兼容性/迁移问题",
    "mobile_ui": "移动端/前端UI机会",
}
