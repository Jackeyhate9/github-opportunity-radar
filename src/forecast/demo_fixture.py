import math
from datetime import datetime, timedelta, timezone
from src.forecast.models import SeriesBatch
from src.forecast.service import ForecastService


def generate_demo_data(svc: ForecastService | None = None):
    now = datetime.now(timezone.utc)
    demos = []

    # 1. Star rapidly growing, issues also exploding
    ts1 = [(now - timedelta(days=89 - i)).isoformat() for i in range(90)]
    stars1 = [200 + int(20 * math.sin(i * 0.2) + i * 1.5 + random_noise()) for i in range(90)]
    issues1 = [5 + int(2 * math.sin(i * 0.1) + i * 0.3 + random_noise()) for i in range(90)]
    demos.append(("快速爆红 + Issue 激增", [
        SeriesBatch("repo", "hotstar/demo1", "stars_count", ts1, stars1),
        SeriesBatch("repo", "hotstar/demo1", "open_issues_count", ts1, issues1),
    ]))

    # 2. Stable growth, issues closing well
    ts2 = [(now - timedelta(days=89 - i)).isoformat() for i in range(90)]
    stars2 = [1000 + int(5 * i + 20 * math.sin(i * 0.05) + random_noise()) for i in range(90)]
    issues2 = [10 + int(math.sin(i * 0.3)) for i in range(90)]
    closed2 = [3 + int(0.5 * i + math.sin(i * 0.2)) for i in range(90)]
    demos.append(("稳定增长 + Issue 关闭良好", [
        SeriesBatch("repo", "stable/demo2", "stars_count", ts2, stars2),
        SeriesBatch("repo", "stable/demo2", "open_issues_count", ts2, issues2),
        SeriesBatch("repo", "stable/demo2", "closed_issues_count", ts2, closed2),
    ]))

    # 3. Sudden spike then fade
    ts3 = [(now - timedelta(days=89 - i)).isoformat() for i in range(90)]
    stars3 = []
    for i in range(90):
        if 60 <= i <= 70:
            stars3.append(500 + int(50 * (i - 60) + random_noise()))
        elif i > 70:
            stars3.append(max(200, stars3[-1] - 30 + int(random_noise())))
        else:
            stars3.append(100 + int(i * 0.5 + random_noise()))
    demos.append(("突然爆红后快速回落", [
        SeriesBatch("repo", "fading/demo3", "stars_count", ts3, stars3),
    ]))

    # 4. Insufficient data
    ts4 = [(now - timedelta(days=4 - i)).isoformat() for i in range(5)]
    stars4 = [100 + int(random_noise()) for _ in range(5)]
    demos.append(("数据不足 (仅5天)", [
        SeriesBatch("repo", "newbie/demo4", "stars_count", ts4, stars4),
    ]))

    if svc:
        for label, batches in demos:
            for b in batches:
                svc.store_metrics(b.entity_type, b.entity_id,
                                   b.metric_name, b.timestamps, b.values,
                                   source="demo_fixture")

    return demos


def random_noise():
    import random
    return random.randint(-5, 5)
