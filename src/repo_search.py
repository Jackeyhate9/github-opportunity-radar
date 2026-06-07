from src.trending_scraper import scrape_all_trending
from src.github_search_scraper import search_github
from src.scraper import clear_cache as clear_scraper_cache
from src.config import settings


def _keyword_match(repo, keyword):
    kw = keyword.lower().replace("-", " ")
    fields = [
        (repo.get("description") or "").lower(),
        (repo.get("name") or "").lower(),
        (repo.get("full_name") or "").lower(),
    ]
    topics = [t.lower() for t in (repo.get("topics") or [])]
    fields.extend(topics)
    return any(kw in f for f in fields)


def search_repos(keywords, target_count=15, min_stars=100, max_stars=50000,
                 min_open_issues=5, time_range_days=30, trending_period="weekly"):
    all_repos = {}
    seen = set()

    print("\n[Phase 1] GitHub Trending (multi-source)...")
    trending = scrape_all_trending(
        target_count=target_count,
        languages=settings.trending_languages,
    )
    for repo in trending:
        fn = repo["full_name"]
        if fn not in seen:
            repo["source"] = "trending"
            if keywords:
                if not any(_keyword_match(repo, kw) for kw in keywords):
                    continue
            all_repos[fn] = repo
            seen.add(fn)

    print(f"  {len(all_repos)} repos after trending + keyword filter\n")

    if settings.enable_github_search_fallback and len(all_repos) < target_count:
        print("[Phase 2] GitHub Search fallback...")
        search_kws = keywords or settings.search_fallback_keywords
        for kw in search_kws:
            if len(all_repos) >= target_count:
                break
            try:
                results = search_github(kw, sort="stars", order="desc", per_page=20)
            except Exception as e:
                print(f"  Search error '{kw}': {e}")
                continue
            for repo in results:
                fn = repo["full_name"]
                if fn in seen:
                    continue
                stars = repo.get("stars", 0)
                if stars < min_stars or stars > max_stars:
                    continue
                all_repos[fn] = repo
                seen.add(fn)
                if len(all_repos) >= target_count:
                    break

        print(f"  {len(all_repos)} repos after search fallback\n")

    repos = list(all_repos.values())[:target_count]

    print(f"[Phase 3] Enriching {len(repos)} repos with detail data...")
    from src.repo_page_scraper import scrape_repo_page

    enriched = []
    for idx, repo in enumerate(repos):
        fn = repo["full_name"]
        print(f"  [{idx+1}/{len(repos)}] {fn} ({repo.get('stars', '?')} stars)")

        detail = scrape_repo_page(fn)
        repo.update(detail)

        repo["owner"] = repo.get("owner") or fn.split("/")[0]
        repo["name"] = repo.get("name") or fn.split("/")[1]
        repo["url"] = repo.get("url") or f"https://github.com/{fn}"
        repo["topics"] = repo.get("topics") or []
        repo["license_name"] = repo.get("license_name") or ""
        repo["homepage"] = repo.get("homepage") or ""

        stars = repo.get("stars", 0) or 0
        if stars < min_stars or stars > max_stars:
            print(f"    Filtered: stars {stars} outside range")
            continue

        enriched.append(repo)

    print(f"\n  {len(enriched)} repos passed all filters\n")
    return enriched


def clear_cache():
    clear_scraper_cache()
    print("  Cache cleared.")
