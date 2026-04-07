"""Automated insights generation using pandas. No LLM involved in calculations."""

import logging

import pandas as pd

from config import ANOMALY_THRESHOLD, BENCHMARK_STD_THRESHOLD, CORRELATION_MIN_ABS, TREND_MIN_WEEKS

WEEK_COLS = [
    "L8W_ROLL",
    "L7W_ROLL",
    "L6W_ROLL",
    "L5W_ROLL",
    "L4W_ROLL",
    "L3W_ROLL",
    "L2W_ROLL",
    "L1W_ROLL",
    "L0W_ROLL",
]

# Metrics where a lower value is better; direction logic is flipped for these.
LOWER_BETTER = {"Restaurants Markdowns / GMV"}

OPPORTUNITY_ORDER_GROWTH_THRESHOLD_PCT = 10.0

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
        work[
            [
                "COUNTRY",
                "CITY",
                "ZONE",
                "ZONE_TYPE",
                "METRIC",
                "L1W_ROLL",
                "L0W_ROLL",
                "change_pct",
                "direction",
            ]
        ]
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
        values = [row[col] for col in WEEK_COLS]

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
            records.append(
                {
                    "COUNTRY": row["COUNTRY"],
                    "CITY": row["CITY"],
                    "ZONE": row["ZONE"],
                    "ZONE_TYPE": row["ZONE_TYPE"],
                    "METRIC": metric,
                    "streak_weeks": streak,
                    "start_value": values[start_idx],
                    "current_value": values[-1],
                }
            )

    if not records:
        return pd.DataFrame(
            columns=[
                "COUNTRY",
                "CITY",
                "ZONE",
                "ZONE_TYPE",
                "METRIC",
                "streak_weeks",
                "start_value",
                "current_value",
            ]
        )
    return pd.DataFrame(records).sort_values("streak_weeks", ascending=False).reset_index(drop=True)


def benchmark_zones(df: pd.DataFrame) -> pd.DataFrame:
    """Return zones performing >BENCHMARK_STD_THRESHOLD std devs from their COUNTRY+ZONE_TYPE peer group."""
    work = df[df["L0W_ROLL"].notna()].copy()
    records = []

    for (country, zone_type, metric), group in work.groupby(["COUNTRY", "ZONE_TYPE", "METRIC"]):
        if len(group) < 3:
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
            records.append(
                {
                    "COUNTRY": country,
                    "CITY": row["CITY"],
                    "ZONE": row["ZONE"],
                    "ZONE_TYPE": zone_type,
                    "METRIC": metric,
                    "value": round(row["L0W_ROLL"], 6),
                    "group_mean": round(mean, 6),
                    "z_score": round(z, 3),
                    "status": "underperforming" if underperforming else "outperforming",
                }
            )

    if not records:
        return pd.DataFrame(
            columns=[
                "COUNTRY",
                "CITY",
                "ZONE",
                "ZONE_TYPE",
                "METRIC",
                "value",
                "group_mean",
                "z_score",
                "status",
            ]
        )
    return pd.DataFrame(records).sort_values("z_score").reset_index(drop=True)


def compute_correlations(df: pd.DataFrame) -> pd.DataFrame:
    """Return metric pairs with abs(correlation) > CORRELATION_MIN_ABS on L0W_ROLL values."""
    pivot = df.pivot_table(
        index=["COUNTRY", "CITY", "ZONE"],
        columns="METRIC",
        values="L0W_ROLL",
        aggfunc="first",
    )

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
            records.append(
                {
                    "metric_1": m1,
                    "metric_2": m2,
                    "correlation": round(val, 4),
                    "type": "positive" if val > 0 else "negative",
                    "strength": "strong" if abs(val) >= 0.7 else "moderate",
                }
            )

    if not records:
        return pd.DataFrame(columns=["metric_1", "metric_2", "correlation", "type", "strength"])
    return pd.DataFrame(records).sort_values("correlation", key=abs, ascending=False).reset_index(drop=True)


def detect_opportunities(
    df_metrics: pd.DataFrame,
    df_orders: pd.DataFrame,
    min_growth_pct: float = OPPORTUNITY_ORDER_GROWTH_THRESHOLD_PCT,
) -> pd.DataFrame:
    """Return zones with strong order growth and operational metric gaps vs peers."""
    required_orders = {"COUNTRY", "CITY", "ZONE", "L5W", "L0W"}
    if not required_orders.issubset(df_orders.columns):
        return pd.DataFrame(
            columns=[
                "COUNTRY",
                "CITY",
                "ZONE",
                "ZONE_TYPE",
                "METRIC",
                "orders_prev_5w",
                "orders_current",
                "orders_growth_pct",
                "value",
                "group_mean",
                "z_score",
                "peer_gap_pct",
                "opportunity_type",
                "recommendation",
            ]
        )

    orders_work = df_orders[["COUNTRY", "CITY", "ZONE", "L5W", "L0W"]].copy()
    orders_work = orders_work[
        orders_work["L5W"].notna() & orders_work["L0W"].notna() & (orders_work["L5W"] > 0)
    ].copy()
    if orders_work.empty:
        return pd.DataFrame(
            columns=[
                "COUNTRY",
                "CITY",
                "ZONE",
                "ZONE_TYPE",
                "METRIC",
                "orders_prev_5w",
                "orders_current",
                "orders_growth_pct",
                "value",
                "group_mean",
                "z_score",
                "peer_gap_pct",
                "opportunity_type",
                "recommendation",
            ]
        )

    orders_work["orders_growth_pct"] = (orders_work["L0W"] - orders_work["L5W"]) / orders_work["L5W"] * 100
    high_growth = orders_work[orders_work["orders_growth_pct"] >= min_growth_pct].copy()
    if high_growth.empty:
        return pd.DataFrame(
            columns=[
                "COUNTRY",
                "CITY",
                "ZONE",
                "ZONE_TYPE",
                "METRIC",
                "orders_prev_5w",
                "orders_current",
                "orders_growth_pct",
                "value",
                "group_mean",
                "z_score",
                "peer_gap_pct",
                "opportunity_type",
                "recommendation",
            ]
        )

    benchmarks = benchmark_zones(df_metrics)
    underperformers = benchmarks[benchmarks["status"] == "underperforming"].copy()
    if underperformers.empty:
        return pd.DataFrame(
            columns=[
                "COUNTRY",
                "CITY",
                "ZONE",
                "ZONE_TYPE",
                "METRIC",
                "orders_prev_5w",
                "orders_current",
                "orders_growth_pct",
                "value",
                "group_mean",
                "z_score",
                "peer_gap_pct",
                "opportunity_type",
                "recommendation",
            ]
        )

    merged = high_growth.merge(
        underperformers,
        on=["COUNTRY", "CITY", "ZONE"],
        how="inner",
        suffixes=("_orders", ""),
    )
    if merged.empty:
        return pd.DataFrame(
            columns=[
                "COUNTRY",
                "CITY",
                "ZONE",
                "ZONE_TYPE",
                "METRIC",
                "orders_prev_5w",
                "orders_current",
                "orders_growth_pct",
                "value",
                "group_mean",
                "z_score",
                "peer_gap_pct",
                "opportunity_type",
                "recommendation",
            ]
        )

    merged["peer_gap_pct"] = (
        (merged["group_mean"] - merged["value"]).abs() / merged["group_mean"].abs().clip(lower=1e-9) * 100
    )
    merged["opportunity_type"] = "growth_with_metric_gap"
    merged["recommendation"] = merged.apply(
        lambda r: (
            f"Orders are growing {r['orders_growth_pct']:.1f}% in this zone. "
            f"Prioritize closing the {r['METRIC']} gap vs peers in the next 2 weeks."
        ),
        axis=1,
    )

    merged = merged.sort_values(["COUNTRY", "CITY", "ZONE", "z_score", "orders_growth_pct"], ascending=[True, True, True, True, False])
    merged = merged.drop_duplicates(subset=["COUNTRY", "CITY", "ZONE"], keep="first")

    return (
        merged[
            [
                "COUNTRY",
                "CITY",
                "ZONE",
                "ZONE_TYPE",
                "METRIC",
                "L5W",
                "L0W",
                "orders_growth_pct",
                "value",
                "group_mean",
                "z_score",
                "peer_gap_pct",
                "opportunity_type",
                "recommendation",
            ]
        ]
        .rename(columns={"L5W": "orders_prev_5w", "L0W": "orders_current"})
        .sort_values("orders_growth_pct", ascending=False)
        .reset_index(drop=True)
    )


def _executive_summary(
    df_anomalies: pd.DataFrame,
    df_trends: pd.DataFrame,
    df_benchmarks: pd.DataFrame,
    df_correlations: pd.DataFrame,
    df_opportunities: pd.DataFrame,
) -> list[str]:
    """Build top 3-5 critical findings in deterministic business language."""
    points: list[str] = []

    if not df_anomalies.empty:
        det = df_anomalies[df_anomalies["direction"] == "deterioration"]
        top_anomaly = det.head(1) if not det.empty else df_anomalies.head(1)
        row = top_anomaly.iloc[0]
        points.append(
            f"Most critical week-over-week change: {row['COUNTRY']} / {row['ZONE']} in {row['METRIC']} "
            f"moved {row['change_pct']:+.1f}% ({row['prev_value']:.2%} to {row['current_value']:.2%})."
        )

    if not df_trends.empty:
        row = df_trends.iloc[0]
        points.append(
            f"Persistent deterioration detected in {row['COUNTRY']} / {row['ZONE']} for {row['METRIC']} "
            f"({int(row['streak_weeks'])} consecutive weeks)."
        )

    if not df_opportunities.empty:
        row = df_opportunities.iloc[0]
        points.append(
            f"Top upside opportunity: {row['COUNTRY']} / {row['ZONE']} orders grew {row['orders_growth_pct']:.1f}% "
            f"while {row['METRIC']} remains below peers (z={row['z_score']:.2f})."
        )

    under = df_benchmarks[df_benchmarks["status"] == "underperforming"] if not df_benchmarks.empty else df_benchmarks
    if not under.empty:
        row = under.iloc[0]
        points.append(
            f"Benchmark gap remains material in {row['COUNTRY']} / {row['ZONE']} ({row['ZONE_TYPE']}): "
            f"{row['METRIC']} at {row['value']:.2%} vs {row['group_mean']:.2%} peer mean."
        )

    if not df_correlations.empty:
        row = df_correlations.iloc[0]
        points.append(
            f"Strong {row['type']} relationship observed between {row['metric_1']} and {row['metric_2']} "
            f"(r={row['correlation']:.3f}), useful for leverage-based interventions."
        )

    if len(points) < 3:
        points.append(
            f"Coverage snapshot: {len(df_anomalies)} anomalies, {len(df_trends)} trends, "
            f"{len(df_opportunities)} opportunities, {len(df_correlations)} significant correlations."
        )

    return points[:5]


def _prioritized_actions(
    df_anomalies: pd.DataFrame,
    df_trends: pd.DataFrame,
    df_benchmarks: pd.DataFrame,
    df_correlations: pd.DataFrame,
    df_opportunities: pd.DataFrame,
) -> list[str]:
    """Build top 3 prioritized actions ranked by impact and urgency proxies."""
    scored: list[tuple[float, str]] = []

    if not df_trends.empty:
        row = df_trends.iloc[0]
        score = 100 + float(row["streak_weeks"]) * 10
        scored.append(
            (
                score,
                f"Launch a 2-week recovery plan in {row['COUNTRY']} / {row['ZONE']} for {row['METRIC']} "
                f"with daily tracking and a weekly target reset.",
            )
        )

    if not df_anomalies.empty:
        det = df_anomalies[df_anomalies["direction"] == "deterioration"]
        top_anomaly = det.head(1) if not det.empty else df_anomalies.head(1)
        row = top_anomaly.iloc[0]
        score = 90 + abs(float(row["change_pct"]))
        scored.append(
            (
                score,
                f"Run root-cause analysis for {row['COUNTRY']} / {row['ZONE']} on {row['METRIC']} "
                f"within 48 hours and define containment actions.",
            )
        )

    if not df_opportunities.empty:
        row = df_opportunities.iloc[0]
        score = 85 + float(row["orders_growth_pct"]) + abs(float(row["z_score"])) * 10
        scored.append(
            (
                score,
                f"Capture demand in {row['COUNTRY']} / {row['ZONE']}: orders are up {row['orders_growth_pct']:.1f}%, "
                f"so prioritize closing {row['METRIC']} gap to improve conversion and service quality.",
            )
        )

    under = df_benchmarks[df_benchmarks["status"] == "underperforming"] if not df_benchmarks.empty else df_benchmarks
    if not under.empty:
        row = under.iloc[0]
        score = 70 + abs(float(row["z_score"])) * 10
        scored.append(
            (
                score,
                f"Run peer benchmarking playbook for {row['COUNTRY']} / {row['ZONE']} ({row['ZONE_TYPE']}) on {row['METRIC']} "
                f"using top zones in the same segment as references.",
            )
        )

    if not df_correlations.empty:
        row = df_correlations.iloc[0]
        score = 60 + abs(float(row["correlation"])) * 20
        scored.append(
            (
                score,
                f"Test a focused intervention on {row['metric_1']} to validate downstream impact on {row['metric_2']} "
                f"based on r={row['correlation']:.3f}.",
            )
        )

    if not scored:
        return ["No high-priority actions identified due to limited valid signals in the current cut."]

    scored.sort(key=lambda x: x[0], reverse=True)
    unique_actions: list[str] = []
    seen = set()
    for _, action in scored:
        if action in seen:
            continue
        seen.add(action)
        unique_actions.append(action)
        if len(unique_actions) == 3:
            break
    return unique_actions


def _dedup(df: pd.DataFrame, sort_col: str, ascending: bool = False) -> pd.DataFrame:
    """Drop duplicate ZONE+METRIC rows, keeping the row with the most extreme sort_col value."""
    if df.empty:
        return df
    return (
        df.sort_values(sort_col, key=abs, ascending=ascending)
        .drop_duplicates(subset=["ZONE", "METRIC"], keep="first")
        .reset_index(drop=True)
    )


def generate_report(df_metrics: pd.DataFrame, df_orders: pd.DataFrame) -> str:
    """Run all insight functions and return a compact executive Markdown report."""
    df_anomalies = _dedup(detect_anomalies(df_metrics), "change_pct", ascending=False)
    df_trends = detect_concerning_trends(df_metrics).drop_duplicates(subset=["ZONE", "METRIC"]).reset_index(drop=True)
    df_benchmarks = _dedup(benchmark_zones(df_metrics), "z_score", ascending=False)
    df_correlations = compute_correlations(df_metrics)
    df_opportunities = detect_opportunities(df_metrics, df_orders)

    TOP_N = 5
    lines: list[str] = []

    # --- Executive Summary ---
    lines.append("## Executive Summary")
    for point in _executive_summary(
        df_anomalies=df_anomalies,
        df_trends=df_trends,
        df_benchmarks=df_benchmarks,
        df_correlations=df_correlations,
        df_opportunities=df_opportunities,
    ):
        lines.append(f"- {point}")

    # --- Recommended Actions (top of report, after summary) ---
    lines.append("\n## Recommended Actions")
    actions = _prioritized_actions(
        df_anomalies=df_anomalies,
        df_trends=df_trends,
        df_benchmarks=df_benchmarks,
        df_correlations=df_correlations,
        df_opportunities=df_opportunities,
    )
    for idx, action in enumerate(actions, start=1):
        lines.append(f"{idx}. {action}")

    # --- Opportunities ---
    lines.append("\n## Opportunities")
    lines.append("Zones with strong demand growth and operational gaps vs peers.")
    if df_opportunities.empty:
        lines.append("\nNo high-confidence opportunities found this week.")
    else:
        for _, r in df_opportunities.head(TOP_N).iterrows():
            lines.append(
                f"\n**{r['COUNTRY']} / {r['ZONE']}** ({r['ZONE_TYPE']}) — {r['METRIC']}  \n"
                f"Orders: {r['orders_prev_5w']:.0f} -> {r['orders_current']:.0f} ({r['orders_growth_pct']:+.1f}%) | "
                f"Peer gap: {r['peer_gap_pct']:.1f}pp (z={r['z_score']:.2f})  \n"
                f"Action: Close the {r['METRIC']} gap in the next 2 weeks to convert demand into sustainable performance."
            )

    # --- Anomalies ---
    lines.append("\n## Anomalies")
    lines.append("Zones with >10% week-over-week change. Deteriorations require an assigned owner.")
    if df_anomalies.empty:
        lines.append("\nNo anomalies detected.")
    else:
        det = df_anomalies[df_anomalies["direction"] == "deterioration"].head(TOP_N)
        imp = df_anomalies[df_anomalies["direction"] == "improvement"].head(2)
        if not det.empty:
            lines.append("\n**Deteriorations**")
            for _, r in det.iterrows():
                lines.append(
                    f"- {r['COUNTRY']} / {r['ZONE']} — {r['METRIC']}: "
                    f"{r['prev_value']:.2%} -> {r['current_value']:.2%} ({r['change_pct']:+.1f}%)"
                )
        if not imp.empty:
            lines.append("\n**Improvements** (replicate playbook)")
            for _, r in imp.iterrows():
                lines.append(
                    f"- {r['COUNTRY']} / {r['ZONE']} — {r['METRIC']}: "
                    f"{r['prev_value']:.2%} -> {r['current_value']:.2%} ({r['change_pct']:+.1f}%)"
                )

    # --- Concerning Trends ---
    lines.append("\n## Concerning Trends")
    lines.append("Metrics in consistent decline for 3 or more consecutive weeks.")
    if df_trends.empty:
        lines.append("\nNo concerning trends detected.")
    else:
        for _, r in df_trends.head(TOP_N).iterrows():
            lines.append(
                f"- {r['COUNTRY']} / {r['ZONE']} — {r['METRIC']}: "
                f"{int(r['streak_weeks'])} weeks declining "
                f"({r['start_value']:.2%} -> {r['current_value']:.2%})"
            )

    # --- Benchmarking ---
    lines.append("\n## Benchmarking")
    lines.append("Zones performing >1 std dev from their country + zone-type peer group.")
    if df_benchmarks.empty:
        lines.append("\nNo significant outliers detected.")
    else:
        under = df_benchmarks[df_benchmarks["status"] == "underperforming"].head(TOP_N)
        over = df_benchmarks[df_benchmarks["status"] == "outperforming"].head(2)
        if not under.empty:
            lines.append("\n**Underperforming**")
            for _, r in under.iterrows():
                lines.append(
                    f"- {r['COUNTRY']} / {r['ZONE']} ({r['ZONE_TYPE']}) — {r['METRIC']}: "
                    f"{r['value']:.2%} vs peer mean {r['group_mean']:.2%} (z={r['z_score']:.2f})"
                )
        if not over.empty:
            lines.append("\n**Outperforming** (use as reference)")
            for _, r in over.iterrows():
                lines.append(
                    f"- {r['COUNTRY']} / {r['ZONE']} ({r['ZONE_TYPE']}) — {r['METRIC']}: "
                    f"{r['value']:.2%} vs peer mean {r['group_mean']:.2%} (z={r['z_score']:+.2f})"
                )

    # --- Correlations ---
    lines.append("\n## Key Metric Relationships")
    lines.append("Significant correlations across zones — useful for identifying leverage points.")
    if df_correlations.empty:
        lines.append("\nNo significant correlations found.")
    else:
        for _, r in df_correlations.head(TOP_N).iterrows():
            direction_note = "move together" if r["type"] == "positive" else "move in opposite directions"
            lines.append(
                f"- **{r['metric_1']}** and **{r['metric_2']}**: r={r['correlation']:.3f} — "
                f"these metrics tend to {direction_note}. "
                f"Intervening on one is likely to affect the other."
            )

    return "\n".join(lines)
