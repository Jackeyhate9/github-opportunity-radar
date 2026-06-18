import math
from src.forecast.models import (
    TrendLabel, ForecastFeatures, ForecastSignal,
    SeriesBatch, ForecastResult,
)


def compute_forecast_features(
    metrics: list[SeriesBatch],
    forecasts: list[ForecastResult],
) -> ForecastFeatures:
    if not metrics or not forecasts:
        return ForecastFeatures(
            explanation="无预测数据",
        )

    star_forecasts = [f for f in forecasts if f.metric_name == "stars_count"]
    if not star_forecasts:
        star_forecasts = forecasts

    f = star_forecasts[-1]
    pf = f.point_forecast if f.point_forecast else []

    forecast_growth_7d = _calc_growth(pf, 7)
    forecast_growth_14d = _calc_growth(pf, 14)
    forecast_growth_30d = _calc_growth(pf, 30)

    forecast_acceleration = _calc_acceleration(pf)
    forecast_volatility = _calc_volatility(pf)
    forecast_confidence = f.trend_confidence
    anomaly_score = _calc_anomaly_score(f.anomaly_flags)

    trend_label = _decide_trend_label(
        f, forecast_growth_7d, forecast_growth_14d,
        forecast_volatility, anomaly_score, f.insufficient_history,
    )

    explanation = _build_explanation(trend_label, f, pf)

    return ForecastFeatures(
        forecast_growth_7d=round(forecast_growth_7d, 1),
        forecast_growth_14d=round(forecast_growth_14d, 1),
        forecast_growth_30d=round(forecast_growth_30d, 1),
        forecast_acceleration=round(forecast_acceleration, 2),
        forecast_volatility=round(forecast_volatility, 2),
        forecast_confidence=round(forecast_confidence, 2),
        anomaly_score=round(anomaly_score, 1),
        trend_label=trend_label,
        explanation=explanation,
    )


def compute_forecast_signal(features: ForecastFeatures) -> ForecastSignal:
    score = 50.0
    reasons = []

    if features.trend_label == TrendLabel.insufficient_data:
        return ForecastSignal(forecast_signal_score=50, score_delta_reason="数据不足，维持原分")

    if features.forecast_growth_30d > 0.1:
        score += 15
        reasons.append("30天增长为正")
    elif features.forecast_growth_30d < -0.1:
        score -= 10
        reasons.append("30天增长为负")

    if features.forecast_acceleration > 0:
        score += 10
        reasons.append("增速加快")
    elif features.forecast_acceleration < 0:
        score -= 5
        reasons.append("增速放缓")

    if features.forecast_volatility > 0.5:
        score -= 10
        reasons.append("波动过大降低置信度")
    elif features.forecast_volatility < 0.1:
        score += 5
        reasons.append("波动低趋势稳定")

    if features.anomaly_score > 0:
        score -= 5 * features.anomaly_score
        reasons.append("存在异常尖峰")

    if features.forecast_confidence < 0.3:
        score -= 10
        reasons.append("预测置信度较低")

    score = max(0, min(100, score))
    return ForecastSignal(
        forecast_signal_score=score,
        score_delta_reason="; ".join(reasons) if reasons else "无明显信号",
    )


def _calc_growth(pf, days):
    if len(pf) < days + 1:
        days = len(pf) - 1
    if days < 1:
        return 0.0
    first = pf[0]
    if first == 0:
        return 0.0
    return (pf[min(days, len(pf)-1)] - first) / first


def _calc_acceleration(pf):
    if len(pf) < 6:
        return 0.0
    half = len(pf) // 2
    first_half_avg = sum(pf[:half]) / max(half, 1)
    second_half_avg = sum(pf[half:]) / max(len(pf) - half, 1)
    if first_half_avg == 0:
        return 0.0
    return (second_half_avg - first_half_avg) / abs(first_half_avg)


def _calc_volatility(pf):
    if len(pf) < 2:
        return 0.0
    import statistics
    mean_val = statistics.mean(pf)
    if mean_val == 0:
        return 0.0
    variance = sum((v - mean_val) ** 2 for v in pf) / len(pf)
    return math.sqrt(variance) / abs(mean_val)


def _calc_anomaly_score(flags):
    if not flags:
        return 0.0
    score_map = {"spike": 0.5, "sudden_surge": 1.0, "sudden_drop": 0.8}
    return sum(score_map.get(f, 0.3) for f in flags) / len(flags)


def _decide_trend_label(f, g7, g14, vol, anomaly, insufficient):
    if insufficient:
        return TrendLabel.insufficient_data
    if vol > 0.5 or anomaly > 0.5:
        return TrendLabel.noisy
    if g14 > 0.05 and g7 > 0.02:
        return TrendLabel.heating_up
    if g14 < -0.05 and g7 < -0.02:
        return TrendLabel.cooling_down
    return TrendLabel.stable


def _build_explanation(label, f, pf):
    cn = {
        TrendLabel.heating_up: "项目热度未来30天预计继续上升",
        TrendLabel.cooling_down: "项目热度预计未来30天有所下降",
        TrendLabel.stable: "项目热度预计未来30天保持稳定",
        TrendLabel.noisy: "项目近期波动异常，建议观察后再判断",
        TrendLabel.insufficient_data: "历史数据不足，无法做出可靠预测",
    }
    base = cn.get(label, "")
    if f.anomaly_flags:
        base += "，存在异常信号"
    if not f.insufficient_history:
        metric = f.metric_name.replace("_count", "").replace("_daily", "").replace("_", " ")
        peak = max(pf) if pf else 0
        base += f"。{metric}峰值预计达{peak:.0f}"
    return base
