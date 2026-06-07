from pydantic import BaseModel, Field
from typing import Optional


class PainCluster(BaseModel):
    name: str = Field(description="Pain cluster name")
    evidence_issue_titles: list[str] = Field(description="Issue titles that support this cluster")
    severity: str = Field(description="low / medium / high")
    monetization_potential: str = Field(description="low / medium / high")


class LLMRepoAnalysis(BaseModel):
    repo_full_name: str = Field(description="Full repo name owner/repo")
    one_sentence_summary: str = Field(description="One sentence summary of the repo")
    user_pain_summary: str = Field(description="Summary of user pain points from issues")
    pain_clusters: list[PainCluster] = Field(description="Clustered pain points")
    best_mvp_idea: str = Field(description="Recommended MVP idea")
    mvp_type: str = Field(
        description="MVP type",
        pattern=r"^(one_click_installer|webui|plugin|mcp_server|chrome_extension|deployment_template|tutorial_pack|cloud_wrapper|enterprise_addon|automation_connector|other)$"
    )
    target_customer: str = Field(description="Target customer description")
    why_now: str = Field(description="Why this opportunity exists now")
    monetization_angle: str = Field(description="How to monetize the MVP")
    build_difficulty: str = Field(description="low / medium / high")
    first_7_day_build_plan: list[str] = Field(description="7 day MVP build plan steps")
    risks: list[str] = Field(description="Risk factors")
    confidence: str = Field(description="low / medium / high")
    llm_notes: str = Field(description="Additional LLM notes or caveats")
