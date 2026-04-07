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

# Metrics that are NOT simple 0-1 ratios — displayed as raw numbers, not percentages.
# Gross Profit UE is margin per order (e.g. 0.05 means $0.05, not 5%).
NON_RATIO_METRICS = {"Gross Profit UE"}

OPPORTUNITY_ORDER_GROWTH_THRESHOLD_PCT = 10.0

logger = logging.getLogger(__name__)


def detect_anomalies(df: pd.DataFrame, threshold: float = ANOMALY_THRESHOLD) -> pd.DataFrame:
    """Return zones with >threshold week-over-week change between L1W_ROLL and L0W_ROLL.

    Uses absolute difference when the previous value is near zero (|prev| < 0.01) to avoid
    explosive percentage changes from near-zero denominators (e.g. Gross Profit UE crossing zero).
    """
    mask = df["L0W_ROLL"].notna() & df["L1W_ROLL"].notna() & (df["L1W_ROLL"] != 0)
    work = df[mask].copy()

    # Use absolute delta for near-zero denominators to avoid meaningless -100000% figures
    near_zero = work["L1W_ROLL"].abs() < 0.01
    work["change_pct"] = (work["L0W_ROLL"] - work["L1W_ROLL"]) / work["L1W_ROLL"].abs() * 100
    work.loc[near_zero, "change_pct"] = (work.loc[near_zero, "L0W_ROLL"] - work.loc[near_zero, "L1W_ROLL"]) * 100

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


def _fmt_val(val: float, metric: str = "") -> str:
    """Format a metric value appropriately based on its type.

    Non-ratio metrics (e.g. Gross Profit UE) are shown as raw numbers.
    All other metrics are ratios and shown as percentages.
    """
    if metric in NON_RATIO_METRICS:
        return f"{val:.4f}"
    return f"{val * 100:.1f}%"


def _fmt_delta(prev: float, curr: float, metric: str = "") -> str:
    """Describe an absolute change between two metric values in plain language."""
    if metric in NON_RATIO_METRICS:
        delta = curr - prev
        sign = "+" if delta >= 0 else ""
        return f"{sign}{delta:.4f}"
    delta = (curr - prev) * 100
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.1f} percentage points"


def _executive_summary(
    df_anomalies: pd.DataFrame,
    df_trends: pd.DataFrame,
    df_benchmarks: pd.DataFrame,
    df_correlations: pd.DataFrame,
    df_opportunities: pd.DataFrame,
) -> list[str]:
    """Build top 3-5 critical findings in plain executive language.

    Each finding is drawn from a different analysis category to ensure
    diversity across zones and countries.
    """
    points: list[str] = []

    if not df_anomalies.empty:
        det = df_anomalies[df_anomalies["direction"] == "deterioration"]
        row = (det.head(1) if not det.empty else df_anomalies.head(1)).iloc[0]
        metric = row["METRIC"]
        delta = _fmt_delta(row["prev_value"], row["current_value"], metric)
        points.append(
            f"{row['COUNTRY']} / {row['ZONE']}: {metric} dropped {delta} week-over-week "
            f"({_fmt_val(row['prev_value'], metric)} → {_fmt_val(row['current_value'], metric)}). "
            f"Immediate attention required."
        )

    if not df_trends.empty:
        # Pick the worst trend from a different country than the anomaly finding, if possible.
        seen_countries = {p.split(" / ")[0] for p in points}
        candidates = df_trends[~df_trends["COUNTRY"].isin(seen_countries)]
        row = (candidates.iloc[0] if not candidates.empty else df_trends.iloc[0])
        metric = row["METRIC"]
        points.append(
            f"{row['COUNTRY']} / {row['ZONE']}: {metric} has been declining for "
            f"{int(row['streak_weeks'])} consecutive weeks "
            f"({_fmt_val(row['start_value'], metric)} → {_fmt_val(row['current_value'], metric)}). "
            f"Structural issue — will not self-correct without intervention."
        )

    if not df_opportunities.empty:
        seen_countries = {p.split(" / ")[0] for p in points}
        candidates = df_opportunities[~df_opportunities["COUNTRY"].isin(seen_countries)]
        row = (candidates.iloc[0] if not candidates.empty else df_opportunities.iloc[0])
        metric = row["METRIC"]
        points.append(
            f"{row['COUNTRY']} / {row['ZONE']}: demand is up {row['orders_growth_pct']:.0f}% over 5 weeks "
            f"but {metric} is {row['peer_gap_pct']:.0f} points below similar zones. "
            f"Growth is at risk if operations do not catch up."
        )

    if not df_benchmarks.empty:
        under = df_benchmarks[df_benchmarks["status"] == "underperforming"]
        if not under.empty:
            seen_countries = {p.split(" / ")[0] for p in points}
            candidates = under[~under["COUNTRY"].isin(seen_countries)]
            row = (candidates.iloc[0] if not candidates.empty else under.iloc[0])
            metric = row["METRIC"]
            points.append(
                f"{row['COUNTRY']} / {row['ZONE']} ({row['ZONE_TYPE']}): {metric} at "
                f"{_fmt_val(row['value'], metric)}, vs {_fmt_val(row['group_mean'], metric)} peer average. "
                f"Significant gap vs similar zones in the same country."
            )

    if not df_correlations.empty:
        row = df_correlations.iloc[0]
        points.append(
            f"Zones with higher {row['metric_1']} also tend to have higher {row['metric_2']} "
            f"(r={row['correlation']:.2f}). "
            f"Improving one is likely to drive the other — consider joint interventions."
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
        metric = row["METRIC"]
        score = 100 + float(row["streak_weeks"]) * 10
        scored.append((
            score,
            f"**{row['COUNTRY']} / {row['ZONE']} — {metric}:** {int(row['streak_weeks'])} weeks of consecutive decline. "
            f"Assign an owner and define a recovery target for next week.",
        ))

    if not df_anomalies.empty:
        det = df_anomalies[df_anomalies["direction"] == "deterioration"]
        row = (det.head(1) if not det.empty else df_anomalies.head(1)).iloc[0]
        metric = row["METRIC"]
        score = 90 + abs(float(row["change_pct"]))
        scored.append((
            score,
            f"**{row['COUNTRY']} / {row['ZONE']} — {metric}:** "
            f"dropped {_fmt_delta(row['prev_value'], row['current_value'], metric)} this week. "
            f"Investigate root cause within 48 hours and define containment actions.",
        ))

    if not df_opportunities.empty:
        row = df_opportunities.iloc[0]
        metric = row["METRIC"]
        score = 85 + float(row["orders_growth_pct"]) + abs(float(row["z_score"])) * 10
        scored.append((
            score,
            f"**{row['COUNTRY']} / {row['ZONE']} — {metric}:** orders up {row['orders_growth_pct']:.0f}% "
            f"but metric is {row['peer_gap_pct']:.0f} points below peers. "
            f"Close the gap before demand stabilizes.",
        ))

    if not df_benchmarks.empty:
        under = df_benchmarks[df_benchmarks["status"] == "underperforming"]
        if not under.empty:
            row = under.iloc[0]
            metric = row["METRIC"]
            score = 70 + abs(float(row["z_score"])) * 10
            scored.append((
                score,
                f"**{row['COUNTRY']} / {row['ZONE']} ({row['ZONE_TYPE']}) — {metric}:** "
                f"at {_fmt_val(row['value'], metric)}, well below the {_fmt_val(row['group_mean'], metric)} peer average. "
                f"Review operations against top-performing zones in the same segment.",
            ))

    if not df_correlations.empty:
        row = df_correlations.iloc[0]
        score = 60 + abs(float(row["correlation"])) * 20
        scored.append((
            score,
            f"**Leverage point — {row['metric_1']} and {row['metric_2']}:** "
            f"these two metrics move together (r={row['correlation']:.2f}). "
            f"Interventions targeting {row['metric_1']} are likely to improve {row['metric_2']} as well.",
        ))

    if not scored:
        return ["No high-priority actions identified due to limited valid signals in the current cut."]

    scored.sort(key=lambda x: x[0], reverse=True)
    seen: set[str] = set()
    unique_actions: list[str] = []
    for _, action in scored:
        if action not in seen:
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


def _high_priority_zones(df_metrics: pd.DataFrame) -> list[str]:
    """Return a sorted list of 'Country / Zone' strings flagged as High Priority."""
    if "ZONE_PRIORITIZATION" not in df_metrics.columns:
        return []
    hp = df_metrics[df_metrics["ZONE_PRIORITIZATION"] == "High Priority"]
    if hp.empty:
        return []
    return sorted(
        {f"{r['COUNTRY']} / {r['ZONE']}" for _, r in hp[["COUNTRY", "ZONE"]].drop_duplicates().iterrows()}
    )


def generate_report(df_metrics: pd.DataFrame, df_orders: pd.DataFrame) -> str:
    """Run all insight functions and return a compact executive Markdown report."""
    df_anomalies = _dedup(detect_anomalies(df_metrics), "change_pct", ascending=False)
    df_trends = detect_concerning_trends(df_metrics).drop_duplicates(subset=["ZONE", "METRIC"]).reset_index(drop=True)
    df_benchmarks = _dedup(benchmark_zones(df_metrics), "z_score", ascending=False)
    df_correlations = compute_correlations(df_metrics)
    df_opportunities = detect_opportunities(df_metrics, df_orders)
    high_priority_zones = _high_priority_zones(df_metrics)

    TOP_N = 5
    lines: list[str] = []

    # --- High Priority Zone Watchlist ---
    if high_priority_zones:
        lines.append("## High Priority Zone Watchlist")
        lines.append(
            "The following zones are flagged as **High Priority** in the operational plan. "
            "All findings below should be reviewed with these zones in mind first."
        )
        for zone_label in high_priority_zones[:10]:
            lines.append(f"- {zone_label}")

    # --- Executive Summary ---
    lines.append("\n## Executive Summary" if high_priority_zones else "## Executive Summary")
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
    lines.append(
        "These zones are growing in order volume but have an operational gap vs similar zones in the same country. "
        "They represent the highest-ROI targets: demand is already there, execution needs to catch up."
    )
    if df_opportunities.empty:
        lines.append("\nNo high-confidence opportunities found this week.")
    else:
        for _, r in df_opportunities.head(TOP_N).iterrows():
            metric = r["METRIC"]
            lines.append(f"\n**{r['COUNTRY']} / {r['ZONE']}** ({r['ZONE_TYPE']})")
            lines.append(
                f"- Metric lagging: **{metric}** — currently {_fmt_val(r['value'], metric)}, "
                f"peers average {_fmt_val(r['group_mean'], metric)} (gap: {r['peer_gap_pct']:.0f} points below)"
            )
            lines.append(
                f"- Order growth: {r['orders_prev_5w']:.0f} orders 5 weeks ago → {r['orders_current']:.0f} today "
                f"({r['orders_growth_pct']:+.0f}%)"
            )
            lines.append(
                f"- Action: Address {metric} in this zone within the next 2 weeks to avoid losing the demand spike."
            )

    # --- Anomalies ---
    lines.append("\n## Anomalies")
    lines.append(
        "Zones where a metric changed significantly compared to last week (more than 10%). "
        "Deteriorations need an owner assigned immediately. Improvements should be documented and replicated."
    )
    if df_anomalies.empty:
        lines.append("\nNo anomalies detected.")
    else:
        det = df_anomalies[df_anomalies["direction"] == "deterioration"].head(TOP_N)
        imp = df_anomalies[df_anomalies["direction"] == "improvement"].head(2)
        if not det.empty:
            lines.append("\n**Deteriorations — assign an owner this week**")
            for _, r in det.iterrows():
                metric = r["METRIC"]
                lines.append(
                    f"- **{r['COUNTRY']} / {r['ZONE']}** — {metric}: "
                    f"{_fmt_val(r['prev_value'], metric)} → {_fmt_val(r['current_value'], metric)} "
                    f"({_fmt_delta(r['prev_value'], r['current_value'], metric)})"
                )
        if not imp.empty:
            lines.append("\n**Improvements — replicate the playbook**")
            for _, r in imp.iterrows():
                metric = r["METRIC"]
                lines.append(
                    f"- **{r['COUNTRY']} / {r['ZONE']}** — {metric}: "
                    f"{_fmt_val(r['prev_value'], metric)} → {_fmt_val(r['current_value'], metric)} "
                    f"({_fmt_delta(r['prev_value'], r['current_value'], metric)})"
                )

    # --- Concerning Trends ---
    lines.append("\n## Concerning Trends")
    lines.append(
        "Metrics that have been declining every single week for 3 or more consecutive weeks. "
        "Unlike anomalies, these are not one-off events — they signal a structural problem that will not self-correct."
    )
    if df_trends.empty:
        lines.append("\nNo concerning trends detected.")
    else:
        for _, r in df_trends.head(TOP_N).iterrows():
            metric = r["METRIC"]
            lines.append(
                f"- **{r['COUNTRY']} / {r['ZONE']}** — {metric}: "
                f"declining for {int(r['streak_weeks'])} weeks in a row "
                f"({_fmt_val(r['start_value'], metric)} → {_fmt_val(r['current_value'], metric)}). "
                f"Trigger a recovery sprint with weekly check-ins."
            )

    # --- Benchmarking ---
    lines.append("\n## Benchmarking")
    lines.append(
        "Zones compared against others in the same country and zone type (Wealthy / Non Wealthy). "
        "Underperformers have a statistically significant gap — not just slightly below average."
    )
    if df_benchmarks.empty:
        lines.append("\nNo significant outliers detected.")
    else:
        under = df_benchmarks[df_benchmarks["status"] == "underperforming"].head(TOP_N)
        over = df_benchmarks[df_benchmarks["status"] == "outperforming"].head(2)
        if not under.empty:
            lines.append("\n**Underperforming zones** (review operations vs top peers)")
            for _, r in under.iterrows():
                metric = r["METRIC"]
                lines.append(
                    f"- **{r['COUNTRY']} / {r['ZONE']}** ({r['ZONE_TYPE']}) — {metric}: "
                    f"{_fmt_val(r['value'], metric)} vs {_fmt_val(r['group_mean'], metric)} peer average"
                )
        if not over.empty:
            lines.append("\n**Outperforming zones** (use these as benchmarks for the rest)")
            for _, r in over.iterrows():
                metric = r["METRIC"]
                lines.append(
                    f"- **{r['COUNTRY']} / {r['ZONE']}** ({r['ZONE_TYPE']}) — {metric}: "
                    f"{_fmt_val(r['value'], metric)} vs {_fmt_val(r['group_mean'], metric)} peer average"
                )

    # --- Correlations ---
    lines.append("\n## Key Metric Relationships")
    lines.append(
        "Pairs of metrics that tend to move together across zones. "
        "When one is low, the other tends to be low too. These are leverage points: fixing one is likely to improve the other."
    )
    if df_correlations.empty:
        lines.append("\nNo significant correlations found.")
    else:
        for _, r in df_correlations.head(TOP_N).iterrows():
            direction_note = "tend to move together" if r["type"] == "positive" else "tend to move in opposite directions"
            lines.append(
                f"- **{r['metric_1']}** and **{r['metric_2']}** {direction_note} (r={r['correlation']:.2f}). "
                f"Zones that improve one typically see gains in the other as well."
            )

    return "\n".join(lines)
