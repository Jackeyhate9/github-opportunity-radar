import re
from bs4 import BeautifulSoup
from urllib.parse import quote
from src.scraper import fetch, parse_count


def search_github(keyword, sort="stars", order="desc", per_page=25):
    encoded = quote(keyword)
    url = (
        f"https://github.com/search?q={encoded}"
        f"&type=repositories&s={sort}&o={order}"
        f"&per_page={per_page}"
    )

    html = fetch(url, max_age_hours=2)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    repos = []

    results = soup.select("[data-testid='results-list'] > div")
    if not results:
        results = soup.select(".repo-list-item, .f4 a")
        if results:
            return _legacy_parse(results)

    for result in results:
        try:
            repo = _parse_result(result)
            if repo:
                repos.append(repo)
        except Exception:
            continue

    return repos


def _parse_result(el):
    a = el.select_one("a[href]")
    if not a:
        return None
    href = a.get("href", "")
    if href.count("/") != 2 or not href.startswith("/"):
        return None
    parts = href.strip("/").split("/")
    if len(parts) < 2:
        return None
    owner, name = parts[0], parts[1]
    full_name = f"{owner}/{name}"

    if not _looks_like_repo(full_name):
        return None

    desc_el = el.select_one('[class*="Content"]')
    description = desc_el.get_text(strip=True)[:300] if desc_el else ""

    topics = []
    for te in el.select('[class*="TokenList"] a, a[href*="/topics/"]'):
        t = te.get_text(strip=True)
        if t and t not in topics:
            topics.append(t)

    all_text = el.get_text()
    numbers = re.findall(r"(\d[\d,]*\.?\d*[kKmMbB]?)", all_text)
    stars = 0
    for n in numbers:
        val = parse_count(n)
        if 20 < val < 10_000_000 and val > stars:
            stars = val

    language = ""
    lis = el.select("li")
    for li in lis:
        circle = li.select_one('[class*="LanguageCircle"], [class*="language"]')
        if circle:
            lang_text = li.get_text(strip=True)[:30]
            for child in li.find_all(["div", "span"]):
                child_text = child.get_text(strip=True)
                if child_text:
                    lang_text = lang_text.replace(child_text, "", 1)
            lang_text = lang_text.strip()
            if lang_text and not any(x in lang_text.lower() for x in ["star", "fork", "ago", "updated"]):
                language = lang_text
                break

    return {
        "full_name": full_name,
        "owner": owner,
        "name": name,
        "url": f"https://github.com/{full_name}",
        "description": description,
        "stars": stars,
        "language": language,
        "topics": topics,
        "source": "search",
    }


def _looks_like_repo(full_name):
    parts = full_name.split("/")
    return len(parts) == 2 and len(parts[0]) > 0 and len(parts[1]) > 0


def _legacy_parse(items):
    repos = []
    for item in items:
        try:
            a = item if item.name == "a" else item.select_one("a")
            if not a:
                continue
            href = a.get("href", "")
            if href.count("/") != 2:
                continue
            parts = href.strip("/").split("/")
            owner, name = parts[0], parts[1]
            repos.append({
                "full_name": f"{owner}/{name}",
                "owner": owner, "name": name,
                "url": f"https://github.com/{owner}/{name}",
                "description": "", "stars": 0,
                "language": "", "topics": [],
                "source": "search",
            })
        except Exception:
            continue
    return repos
