import sys
from src.forecast.service import ForecastService
from src.forecast.demo_fixture import generate_demo_data
from src.forecast.features import compute_forecast_features, compute_forecast_signal
from src.forecast.database import init_forecast_tables, get_historical_metrics
from src.config import settings


def run_forecast_demo(horizon: int = 30):
    print("=" * 60)
    print("  Forecast Demo — 趋势预测演示")
    print("=" * 60)
    print(f"  Horizon: {horizon} 天")
    print()

    import sqlite3
    conn = sqlite3.connect(str(settings.db_path))
    conn.row_factory = sqlite3.Row
    init_forecast_tables(conn)

    svc = ForecastService()
    demos = generate_demo_data(svc)

    for label, series_batch in demos:
        print(f"\n--- {label} ---")
        for batch in series_batch:
            print(f"  {batch.metric_name}: {len(batch.values)} data points, "
                  f"last={batch.values[-1] if batch.values else 'N/A'}")

        results = svc.forecast_series(series_batch, horizon=horizon)
        for r in results:
            print(f"  预测 {r.metric_name} ({r.horizon_days}d): "
                  f"dir={r.trend_direction.value}, "
                  f"conf={r.trend_confidence}, "
                  f"adapter={r.adapter_name}"
                  f"{' (fallback)' if r.was_fallback else ''}"
                  f"{' [数据不足]' if r.insufficient_history else ''}")
            if r.point_forecast:
                fc = [round(v, 0) for v in r.point_forecast[:7]]
                print(f"  前7天预测: {fc}...")

        features = compute_forecast_features(series_batch, results)
        signal = compute_forecast_signal(features)
        print(f"  → trend_label={features.trend_label.value}, "
              f"signal_score={signal.forecast_signal_score}")
        print(f"  → {features.explanation}")
        print(f"  → {signal.score_delta_reason}")

    conn.close()
    print()
    print("Demo complete.")


def run_forecast_for_entity(entity_type: str, entity_id: str,
                             metric: str, horizon: int):
    svc = ForecastService()
    conn = svc.conn
    init_forecast_tables(conn)

    timestamps, values = get_historical_metrics(
        conn, entity_type, entity_id, metric, limit=90
    )
    if not timestamps:
        print(f"未找到 {entity_type}/{entity_id}/{metric} 的历史数据")
        print("提示: 先用 --demo 跑演示数据")
        return

    import sqlite3
    from src.forecast.models import SeriesBatch
    batch = SeriesBatch(
        entity_type=entity_type,
        entity_id=entity_id,
        metric_name=metric,
        timestamps=timestamps,
        values=values,
        frequency="daily",
    )
    results = svc.forecast_series([batch], horizon=horizon)
    for r in results:
        print(f"预测 {r.metric_name} ({r.horizon_days}d):")
        print(f"  趋势: {r.trend_direction.value}")
        print(f"  置信度: {r.trend_confidence}")
        print(f"  Adapter: {r.adapter_name}{' (fallback)' if r.was_fallback else ''}")
        print(f"  点预测: {[round(v,1) for v in r.point_forecast[:7]]}...")
        print(f"  异常: {r.anomaly_flags}")
        print(f"  解释: {r.explanation}")
