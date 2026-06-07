import re
from bs4 import BeautifulSoup
from src.scraper import fetch, parse_count


_PAGE_CACHE = {}


def scrape_trending(since="weekly", language=""):
    url = "https://github.com/trending"
    if language:
        url += f"/{language}"
    url += f"?since={since}"

    label = f"trending/{language or 'all'}/{since}"
    if label in _PAGE_CACHE:
        return _PAGE_CACHE[label]

    print(f"  [trending] Fetching github.com/trending ({language or 'all'} / {since})...")
    html = fetch(url, max_age_hours=2)
    if not html:
        print(f"  [trending] Page fetch failed: {url}")
        return []

    soup = BeautifulSoup(html, "lxml")
    articles = soup.select("article.Box-row")
    if not articles:
        print(f"  [trending] No article.Box-row found on {url}")
        return []

    repos = []
    for art in articles:
        try:
            repo = _parse_article(art, since)
            if repo:
                repos.append(repo)
        except Exception as e:
            print(f"  [trending] Parse error: {e}")
            continue

    _PAGE_CACHE[label] = repos
    print(f"  [trending] {len(repos)} repos from {label}")
    return repos


def scrape_all_trending(target_count=15, languages=None):
    """Multi-source trending scraping to hit target_count repos."""
    languages = languages or []
    all_seen = {}
    results = []

    periods = ["daily", "weekly", "monthly"]

    for period in periods:
        repos = scrape_trending(since=period)
        for r in repos:
            fn = r["full_name"]
            if fn not in all_seen:
                r["trending_source"] = period
                r["stars_delta_source"] = period
                if period == "daily":
                    r["stars_delta_1d"] = r.get("stars_delta_7d")
                elif period == "weekly":
                    r["stars_delta_7d"] = r.get("stars_delta_7d")
                elif period == "monthly":
                    r["stars_delta_30d"] = r.get("stars_delta_7d")
                all_seen[fn] = r
                results.append(r)
        if len(results) >= target_count:
            break

    if len(results) < target_count:
        for lang in languages:
            for period in ["daily", "weekly"]:
                repos = scrape_trending(since=period, language=lang)
                for r in repos:
                    fn = r["full_name"]
                    if fn not in all_seen:
                        r["trending_source"] = f"{lang}/{period}"
                        r["stars_delta_source"] = period
                        all_seen[fn] = r
                        results.append(r)
                if len(results) >= target_count:
                    break
            if len(results) >= target_count:
                break

    return results[:target_count]


def _parse_article(art, since="weekly"):
    h2 = art.select_one("h2")
    if not h2:
        return None
    a = h2.select_one("a")
    if not a:
        return None
    href = a.get("href", "").strip("/")
    parts = href.split("/")
    if len(parts) < 2:
        return None
    owner, name = parts[0], parts[1]
    full_name = f"{owner}/{name}"

    desc_el = art.select_one("p")
    description = desc_el.get_text(strip=True) if desc_el else ""

    f6 = art.select_one(".f6")
    language = ""
    stars_total = 0
    forks_total = 0
    stars_delta = 0

    if f6:
        for span in f6.select("span.d-inline-block"):
            text = span.get_text(strip=True)
            if text and text != "Built by" and "float-sm-right" not in span.get("class", []):
                language = text
                break

        star_anchor = f6.select_one("a[href*='stargazers']")
        if star_anchor:
            stars_total = parse_count(star_anchor.get_text(strip=True))

        fork_anchor = f6.select_one("a[href*='/forks']")
        if fork_anchor:
            forks_total = parse_count(fork_anchor.get_text(strip=True))

        delta_span = f6.select_one("span.float-sm-right")
        if delta_span:
            delta_text = delta_span.get_text(strip=True)
            m = re.search(r"([\d,]+[kKmM]?)\s*stars?", delta_text)
            if m:
                stars_delta = parse_count(m.group(1))

    return {
        "full_name": full_name,
        "owner": owner,
        "name": name,
        "url": f"https://github.com/{full_name}",
        "description": description,
        "stars": stars_total,
        "stars_delta_7d": stars_delta if since in ("weekly", "daily") else None,
        "forks": forks_total,
        "language": language,
        "source": "trending",
    }
