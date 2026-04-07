"""Automated insights generation using pandas. No LLM involved in calculations."""

import logging

import pandas as pd

from config import ANOMALY_THRESHOLD, BENCHMARK_STD_THRESHOLD, CORRELATION_MIN_ABS, TREND_MIN_WEEKS

WEEK_COLS = ["L8W_ROLL", "L7W_ROLL", "L6W_ROLL", "L5W_ROLL",
             "L4W_ROLL", "L3W_ROLL", "L2W_ROLL", "L1W_ROLL", "L0W_ROLL"]

# Metrics where a lower value is better — direction logic is flipped for these
LOWER_BETTER = {"Restaurants Markdowns / GMV"}

logger = logging.getLogger(__name__)


def detect_anomalies(df: pd.DataFrame, threshold: float = ANOMALY_THRESHOLD) -> pd.DataFrame:
    """Return zones with >threshold week-over-week change between L1W_ROLL and L0W_ROLL."""
    mask = df["L0W_ROLL"].notna() & df["L1W_ROLL"].notna() & (df["L1W_ROLL"] != 0)
    work = df[mask].copy()

    work["change_pct"] = (work["L0W_ROLL"] - work["L1W_ROLL"]) / work["L1W_ROLL"].abs() * 100
    work = work[work["change_pct"].abs() > threshold * 100].copy()

    def _direction(row: pd.Series) -> str:
        improving = row["change_pct"] > 0
        if row["METRIC"] in LOWER_BETTER:
            improving = not improving
        return "improvement" if improving else "deterioration"

    work["direction"] = work.apply(_direction, axis=1)

    return (
        work[["COUNTRY", "CITY", "ZONE", "ZONE_TYPE", "METRIC",
              "L1W_ROLL", "L0W_ROLL", "change_pct", "direction"]]
        .rename(columns={"L1W_ROLL": "prev_value", "L0W_ROLL": "current_value"})
        .sort_values("change_pct", key=abs, ascending=False)
        .reset_index(drop=True)
    )


def detect_concerning_trends(df: pd.DataFrame, min_weeks: int = TREND_MIN_WEEKS) -> pd.DataFrame:
    """Return zones where a metric declined for min_weeks consecutive weeks ending at L0W_ROLL."""
    records = []

    for _, row in df.iterrows():
        metric = row["METRIC"]
        is_lower_better = metric in LOWER_BETTER
        values = [row[col] for col in WEEK_COLS]  # oldest → newest

        # Walk backwards from L0W_ROLL counting consecutive deterioration steps
        streak = 0
        for i in range(len(values) - 1, 0, -1):
            curr, prev = values[i], values[i - 1]
            if pd.isna(curr) or pd.isna(prev):
                break
            deteriorating = (curr < prev) if not is_lower_better else (curr > prev)
            if deteriorating:
                streak += 1
            else:
                break

        if streak >= min_weeks:
            start_idx = len(values) - 1 - streak
            records.append({
                "COUNTRY": row["COUNTRY"],
                "CITY": row["CITY"],
                "ZONE": row["ZONE"],
                "ZONE_TYPE": row["ZONE_TYPE"],
                "METRIC": metric,
                "streak_weeks": streak,
                "start_value": values[start_idx],
                "current_value": values[-1],
            })

    if not records:
        return pd.DataFrame(columns=["COUNTRY", "CITY", "ZONE", "ZONE_TYPE",
                                     "METRIC", "streak_weeks", "start_value", "current_value"])
    return (
        pd.DataFrame(records)
        .sort_values("streak_weeks", ascending=False)
        .reset_index(drop=True)
    )


def benchmark_zones(df: pd.DataFrame) -> pd.DataFrame:
    """Return zones performing >BENCHMARK_STD_THRESHOLD std devs below their COUNTRY+ZONE_TYPE peer group."""
    work = df[df["L0W_ROLL"].notna()].copy()
    records = []

    for (country, zone_type, metric), group in work.groupby(["COUNTRY", "ZONE_TYPE", "METRIC"]):
        if len(group) < 3:  # too few peers for meaningful stats
            continue
        values = group["L0W_ROLL"]
        mean, std = values.mean(), values.std()
        if std == 0 or pd.isna(std):
            continue

        is_lower_better = metric in LOWER_BETTER

        for _, row in group.iterrows():
            z = (row["L0W_ROLL"] - mean) / std
            if abs(z) < BENCHMARK_STD_THRESHOLD:
                continue
            underperforming = (z < 0) if not is_lower_better else (z > 0)
            records.append({
                "COUNTRY": country,
                "CITY": row["CITY"],
                "ZONE": row["ZONE"],
                "ZONE_TYPE": zone_type,
                "METRIC": metric,
                "value": round(row["L0W_ROLL"], 6),
                "group_mean": round(mean, 6),
                "z_score": round(z, 3),
                "status": "underperforming" if underperforming else "outperforming",
            })

    if not records:
        return pd.DataFrame(columns=["COUNTRY", "CITY", "ZONE", "ZONE_TYPE",
                                     "METRIC", "value", "group_mean", "z_score", "status"])
    return (
        pd.DataFrame(records)
        .sort_values("z_score")
        .reset_index(drop=True)
    )


def compute_correlations(df: pd.DataFrame) -> pd.DataFrame:
    """Return metric pairs with abs(correlation) > CORRELATION_MIN_ABS on L0W_ROLL values."""
    pivot = df.pivot_table(
        index=["COUNTRY", "CITY", "ZONE"],
        columns="METRIC",
        values="L0W_ROLL",
        aggfunc="first",
    )

    # Drop metrics with <50% zone coverage, then drop any zone still missing a value
    pivot = pivot.dropna(axis=1, thresh=int(len(pivot) * 0.5))
    pivot = pivot.dropna(how="any")

    if pivot.shape[1] < 2 or pivot.shape[0] < 5:
        return pd.DataFrame(columns=["metric_1", "metric_2", "correlation", "type", "strength"])

    corr = pivot.corr()
    metrics = corr.columns.tolist()
    records = []

    for i, m1 in enumerate(metrics):
        for j in range(i + 1, len(metrics)):
            m2 = metrics[j]
            val = corr.loc[m1, m2]
            if pd.isna(val) or abs(val) < CORRELATION_MIN_ABS:
                continue
            records.append({
                "metric_1": m1,
                "metric_2": m2,
                "correlation": round(val, 4),
                "type": "positive" if val > 0 else "negative",
                "strength": "strong" if abs(val) >= 0.7 else "moderate",
            })

    if not records:
        return pd.DataFrame(columns=["metric_1", "metric_2", "correlation", "type", "strength"])
    return (
        pd.DataFrame(records)
        .sort_values("correlation", key=abs, ascending=False)
        .reset_index(drop=True)
    )


def generate_report(df_metrics: pd.DataFrame, df_orders: pd.DataFrame) -> str:
    """Run all four insight functions and return a structured Markdown data summary."""
    df_anomalies = detect_anomalies(df_metrics)
    df_trends = detect_concerning_trends(df_metrics)
    df_benchmarks = benchmark_zones(df_metrics)
    df_correlations = compute_correlations(df_metrics)

    lines: list[str] = []

    # ── Anomalies ──────────────────────────────────────────────────────────
    lines.append("## Anomalies (>10% week-over-week change)")
    if df_anomalies.empty:
        lines.append("No anomalies detected.")
    else:
        lines.append(f"Total flagged: {len(df_anomalies)}\n")
        for _, r in df_anomalies.head(20).iterrows():
            lines.append(
                f"- [{r['direction'].upper()}] {r['COUNTRY']} / {r['ZONE']} — {r['METRIC']}: "
                f"{r['prev_value']:.2%} → {r['current_value']:.2%} ({r['change_pct']:+.1f}%)"
            )

    # ── Trends ─────────────────────────────────────────────────────────────
    lines.append("\n## Concerning Trends (3+ consecutive weeks declining)")
    if df_trends.empty:
        lines.append("No concerning trends detected.")
    else:
        lines.append(f"Total flagged: {len(df_trends)}\n")
        for _, r in df_trends.head(20).iterrows():
            lines.append(
                f"- {r['COUNTRY']} / {r['ZONE']} — {r['METRIC']}: "
                f"{r['streak_weeks']} weeks declining "
                f"({r['start_value']:.2%} → {r['current_value']:.2%})"
            )

    # ── Benchmarking ───────────────────────────────────────────────────────
    lines.append("\n## Benchmarking (zones vs COUNTRY+ZONE_TYPE peer group)")
    if df_benchmarks.empty:
        lines.append("No significant outliers detected.")
    else:
        under = df_benchmarks[df_benchmarks["status"] == "underperforming"]
        over = df_benchmarks[df_benchmarks["status"] == "outperforming"]
        lines.append(f"Underperforming: {len(under)} | Outperforming: {len(over)}\n")
        for _, r in under.head(15).iterrows():
            lines.append(
                f"- UNDER {r['COUNTRY']} / {r['ZONE']} ({r['ZONE_TYPE']}) — {r['METRIC']}: "
                f"{r['value']:.2%} vs group mean {r['group_mean']:.2%} (z={r['z_score']:.2f})"
            )

    # ── Correlations ───────────────────────────────────────────────────────
    lines.append("\n## Correlations (|r| ≥ 0.3)")
    if df_correlations.empty:
        lines.append("No significant correlations found.")
    else:
        lines.append(f"Total significant pairs: {len(df_correlations)}\n")
        for _, r in df_correlations.head(10).iterrows():
            lines.append(
                f"- {r['metric_1']} ↔ {r['metric_2']}: "
                f"r={r['correlation']:.3f} ({r['strength']} {r['type']})"
            )

    return "\n".join(lines)
