"""
Analyze README for early-stage and commercial signals.
No LLM — pure keyword/regex matching.
"""

import re

EARLY_SIGNALS = [
    (r"\balpha\b", "alpha"),
    (r"\bbeta\b", "beta"),
    (r"\bexperimental\b", "experimental"),
    (r"\bprototype\b", "prototype"),
    (r"\bwork in progress\b", "work in progress"),
    (r"\bwip\b", "wip"),
    (r"\broadmap\b", "roadmap"),
    (r"\btodo\b", "todo"),
    (r"\bnot production ready\b", "not production ready"),
    (r"\bunder development\b", "under development"),
    (r"\bcoming soon\b", "coming soon"),
    (r"\bpre-release\b", "pre-release"),
    (r"\bproof of concept\b", "proof of concept"),
    (r"\bpoc\b", "poc"),
    (r"\bhackathon\b", "hackathon"),
    (r"\bmvp\b", "mvp"),
    (r"\binitial release\b", "initial release"),
    (r"\bunstable\b", "unstable"),
    (r"\bpreview\b", "preview"),
    (r"\bearly\s+(stage|version|release|access|development)\b", "early stage"),
]

COMMERCIAL_SIGNALS = [
    (r"\bpricing\b", "pricing"),
    (r"\benterprise\b", "enterprise"),
    (r"\bsales\b", "sales"),
    (r"\bbook a demo\b", "book a demo"),
    (r"\bcontact sales\b", "contact sales"),
    (r"\bsoc2\b", "SOC2"),
    (r"\bcase studies\b", "case studies"),
    (r"\bcustomers\b", "customers"),
    (r"\bpaid plan\b", "paid plan"),
    (r"\bsubscription\b", "subscription"),
    (r"\bcloud platform\b", "cloud platform"),
    (r"\bhosted platform\b", "hosted platform"),
    (r"\bteam plan\b", "team plan"),
    (r"\bbusiness plan\b", "business plan"),
    (r"\bpro plan\b", "pro plan"),
    (r"\brequest demo\b", "request demo"),
    (r"\benterprise plan\b", "enterprise plan"),
    (r"\bmanaged hosting\b", "managed hosting"),
    (r"\bdedicated support\b", "dedicated support"),
    (r"\bsla\b", "SLA"),
    (r"\buptime guarantee\b", "uptime guarantee"),
    (r"\bcontact us for pricing\b", "contact for pricing"),
    (r"\bget a quote\b", "get a quote"),
]


def analyze_readme(readme_text: str) -> dict:
    text_lower = (readme_text or "").lower()

    early_signals = []
    for pattern, name in EARLY_SIGNALS:
        if re.search(pattern, text_lower):
            early_signals.append(name)

    commercial_signals = []
    for pattern, name in COMMERCIAL_SIGNALS:
        if re.search(pattern, text_lower):
            commercial_signals.append(name)

    # Check for pre-1.0 version
    version_match = re.search(r"v?\b(\d+)\.(\d+)", readme_text or "")
    major_version = int(version_match.group(1)) if version_match else None
    if major_version is not None and major_version == 0:
        early_signals.append("v0.x (pre-1.0)")

    early_signals = list(dict.fromkeys(early_signals))
    commercial_signals = list(dict.fromkeys(commercial_signals))

    return {
        "early_signals": early_signals,
        "commercial_signals": commercial_signals,
        "has_early_signal": len(early_signals) > 0,
        "has_commercial_signal": len(commercial_signals) > 0,
        "major_version": major_version,
        "is_pre_v1": major_version is not None and major_version < 1,
    }
