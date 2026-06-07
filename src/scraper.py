"""
Shared HTTP scraper with polite headers, rate limiting, and caching.
Scrapes public GitHub pages only — no API, no tokens, no auth.
"""

import time
import re
import hashlib
import requests
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from src.config import CACHE_DIR, settings

_session = None
_last_request_time = 0


def get_session():
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://github.com/",
            "DNT": "1",
        })
    return _session


def rate_limit():
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    min_gap = settings.request_delay_seconds
    if elapsed < min_gap:
        time.sleep(min_gap - elapsed)
    _last_request_time = time.time()


def cache_key(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()


def get_cached(url: str, max_age_hours: int = 1):
    key = cache_key(url)
    cache_file = CACHE_DIR / key
    if cache_file.exists():
        age = time.time() - cache_file.stat().st_mtime
        if age < max_age_hours * 3600:
            return cache_file.read_text(encoding="utf-8")
    return None


def set_cache(url: str, text: str):
    key = cache_key(url)
    cache_file = CACHE_DIR / key
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_file.write_text(text, encoding="utf-8")


def clear_cache():
    import shutil
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)


def fetch(url: str, max_age_hours: int = 1, force: bool = False) -> Optional[str]:
    if not force:
        cached = get_cached(url, max_age_hours)
        if cached is not None:
            return cached

    rate_limit()
    session = get_session()

    for attempt in range(3):
        try:
            resp = session.get(url, timeout=30)
            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "60"))
                print(f"  [429] Rate limited. Waiting {retry_after}s...")
                time.sleep(retry_after)
                continue
            if resp.status_code == 200:
                set_cache(url, resp.text)
                return resp.text
            elif resp.status_code == 404:
                return None
            else:
                print(f"  [HTTP {resp.status_code}] {url[:80]}")
                return None
        except requests.RequestException as e:
            if attempt < 2:
                wait = (attempt + 1) * 5
                print(f"  [retry {attempt+1}/3] {url[:50]} — waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"  [network] {url[:50]} — {e}")
                return None
    return None


def parse_count(text: str) -> int:
    text = text.strip()
    multipliers = {"k": 1_000, "m": 1_000_000}
    if text[-1].lower() in multipliers:
        try:
            return int(float(text[:-1]) * multipliers[text[-1].lower()])
        except ValueError:
            pass
    try:
        return int(text.replace(",", ""))
    except ValueError:
        return 0


def parse_relative_date(text: str) -> str:
    now = datetime.now(timezone.utc)
    text = text.strip().lower()
    match = re.search(r"(\d+)\s*(minute|hour|day|month|year)", text)
    if not match:
        return now.isoformat()
    num = int(match.group(1))
    unit = match.group(2)
    if "minute" in unit:
        dt = now - __import__("datetime").timedelta(minutes=num)
    elif "hour" in unit:
        dt = now - __import__("datetime").timedelta(hours=num)
    elif "day" in unit:
        dt = now - __import__("datetime").timedelta(days=num)
    elif "month" in unit:
        dt = now - __import__("datetime").timedelta(days=num * 30)
    elif "year" in unit:
        dt = now - __import__("datetime").timedelta(days=num * 365)
    else:
        dt = now
    return dt.isoformat()
