import re
from bs4 import BeautifulSoup
from urllib.parse import quote
from src.scraper import fetch, parse_count


def scrape_repo_page(full_name):
    url = f"https://github.com/{full_name}"
    html = fetch(url, max_age_hours=6)
    if not html:
        return {"data_quality": "failed", "full_name": full_name}

    soup = BeautifulSoup(html, "lxml")
    data = {"full_name": full_name, "readme_fetch_status": "pending"}

    desc_el = soup.select_one("p.f4")
    if desc_el:
        data["description"] = desc_el.get_text(strip=True)

    star_el = soup.select_one("#repo-stars-counter-star")
    if star_el:
        data["stars"] = parse_count(star_el.get_text(strip=True))
    if not data.get("stars"):
        star_link = soup.select_one("a[href*='/stargazers']")
        if star_link:
            text = star_link.get_text(strip=True)
            m = re.search(r"([\d,]+[kKmM]?)", text)
            if m:
                data["stars"] = parse_count(m.group(1))

    fork_link = soup.select_one("a[href*='/forks']")
    if fork_link:
        text = fork_link.get_text(strip=True)
        m = re.search(r"([\d,]+)", text)
        if m:
            data["forks"] = parse_count(m.group(1))

    issues_link = soup.select_one(f"a[href='/{full_name}/issues']")
    if not issues_link:
        issues_link = soup.select_one("a[href*='/issues']")
    while issues_link and ("features" in issues_link.get("href", "")):
        next_links = soup.select("a[href*='/issues']")
        issues_link = next_links[1] if len(next_links) > 1 else None
    if issues_link:
        text = issues_link.get_text(strip=True)
        m = re.search(r"([\d,]+[kKmM]?)", text)
        if m:
            data["open_issues_count"] = parse_count(m.group(1))

    lang_els = soup.select("[data-ga-click*='language']")
    for el in lang_els:
        text = el.get_text(strip=True)
        lang = re.sub(r"\d+[\.\d]*%", "", text).strip()
        if lang:
            data["language"] = lang
            break

    topics = []
    for el in soup.select("a.topic-tag, [data-ga-click*='topic']"):
        text = el.get_text(strip=True)
        if text and text not in topics:
            topics.append(text)
    if topics:
        data["topics"] = topics

    lic_el = soup.select_one("a[href*='/license/']")
    if not lic_el:
        for a in soup.select("a[href]"):
            h = a.get("href", "")
            if "/license" in h and "features" not in h:
                lic_el = a
                break
    if lic_el:
        data["license_name"] = lic_el.get_text(strip=True)

    for a in soup.select("a[rel~='nofollow']"):
        h = a.get("href", "")
        if h and h != f"https://github.com/{full_name}" and "login" not in h:
            data["homepage"] = h
            break

    release_el = soup.select_one("a[href*='/releases']")
    if release_el:
        text = release_el.get_text(strip=True)
        m = re.search(r"(\d+)", text)
        if m and int(m.group(1)) > 0:
            data["has_releases"] = True

    readme_text = _extract_readme(soup, full_name)
    if readme_text:
        data["readme_text"] = readme_text
        data["readme_fetch_status"] = "success"
    else:
        data["readme_fetch_status"] = "failed"

    data["data_quality"] = "medium"
    return data


def _extract_readme(soup, full_name):
    article = soup.select_one("article.markdown-body")
    if article:
        text = article.get_text(strip=True)
        if len(text) > 100:
            return text

    for branch in ("main", "master"):
        url = f"https://raw.githubusercontent.com/{full_name}/{branch}/README.md"
        content = fetch(url, max_age_hours=24)
        if content and len(content) > 50:
            return content

    return ""


def scrape_issues_direct(full_name, max_count=20):
    """Scrape /issues page directly (not search endpoint)."""
    issues = []
    for page_num in range(1, 3):
        url = f"https://github.com/{full_name}/issues?page={page_num}&q=is%3Aissue+is%3Aopen"
        html = fetch(url, max_age_hours=6)
        if not html:
            break

        soup = BeautifulSoup(html, "lxml")

        found = False
        for selector in [
            "div[aria-label='Issues'] > div",
            ".js-navigation-container > div",
            "[data-testid='list-view-item']",
            ".js-issue-row",
            "div[role='group'] > div",
        ]:
            items = soup.select(selector)
            if items and len(items) > 1:
                found = True
                break

        if not found:
            items = []
            for div in soup.find_all("div", class_=lambda c: c and "issue" in c.lower()):
                if div.find("a", href=re.compile(rf"/{re.escape(full_name)}/issues/\d+")):
                    items.append(div)
                    if len(items) >= max_count:
                        break
            if not items:
                break

        for item in items:
            try:
                issue = _parse_issue_row(item, full_name)
                if issue:
                    issues.append(issue)
            except Exception:
                continue

        if len(issues) >= max_count:
            break

    return issues[:max_count]


def _parse_issue_row(el, full_name):
    a = el.select_one(f"a[href*='/{full_name}/issues/']")
    if not a:
        for a_tag in el.find_all("a", href=re.compile(r"/issues/\d+")):
            a = a_tag
            break
    if not a:
        return None

    href = a.get("href", "")
    m = re.search(r"issues/(\d+)", href)
    issue_id = m.group(1) if m else ""
    title = a.get_text(strip=True)

    labels = []
    for lab in el.select("[class*='IssueLabel'], [data-testid='issue-tag'], .lh-condensed a"):
        text = lab.get_text(strip=True)
        if text and len(text) < 50 and not text.startswith("http"):
            labels.append(text)

    comments = 0
    cm = re.search(r"(\d+)\s*comment", el.get_text())
    if cm:
        comments = int(cm.group(1))

    snippet = el.get_text(strip=True)[:300]

    return {
        "title": title,
        "url": f"https://github.com/{full_name}/issues/{issue_id}",
        "labels": list(set(labels)),
        "comments_count": comments,
        "snippet": snippet,
        "updated_at": "",
    }
