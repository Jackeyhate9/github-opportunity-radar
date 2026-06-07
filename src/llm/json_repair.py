import re
import json


def extract_json(text: str) -> dict | None:
    text = text.strip()

    code_block = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if code_block:
        text = code_block.group(1).strip()

    brace_start = text.find("{")
    brace_end = text.rfind("}")

    if brace_start == -1 or brace_end == -1 or brace_end <= brace_start:
        return None

    json_str = text[brace_start : brace_end + 1]

    result = _try_parse(json_str)
    if result is not None:
        return result

    result = _try_parse(_fix_common(json_str))
    if result is not None:
        return result

    result = _try_parse(_fix_trailing_commas(json_str))
    if result is not None:
        return result

    result = _try_parse(_fix_single_quotes(json_str))
    if result is not None:
        return result

    return None


def _try_parse(s: str) -> dict | None:
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None


def _fix_common(s: str) -> str:
    s = re.sub(r",\s*}", "}", s)
    s = re.sub(r",\s*]", "]", s)
    s = re.sub(r"(?<!\\)\\(?![\"\\/bfnrtu])", r"\\\\", s)
    return s


def _fix_trailing_commas(s: str) -> str:
    s = re.sub(r",\s*}", "}", s)
    s = re.sub(r",\s*]", "]", s)
    return s


def _fix_single_quotes(s: str) -> str:
    s = re.sub(r"(?<!\\)'", '"', s)
    return s


def safe_parse_analysis(data: dict) -> dict | None:
    required = ["repo_full_name", "best_mvp_idea", "confidence"]
    for field in required:
        if field not in data:
            return None

    valid_mvp_types = [
        "one_click_installer", "webui", "plugin", "mcp_server",
        "chrome_extension", "deployment_template", "tutorial_pack",
        "cloud_wrapper", "enterprise_addon", "automation_connector", "other"
    ]
    mvp_type = data.get("mvp_type", "other")
    if mvp_type not in valid_mvp_types:
        data["mvp_type"] = "other"

    for valid in ["low", "medium", "high"]:
        for field in ["severity", "monetization_potential", "build_difficulty", "confidence"]:
            if data.get(field) not in ["low", "medium", "high", None]:
                pass

    return data
