from __future__ import annotations

import altair as alt
import pandas as pd


COLORS = ["#0f766e", "#e89b4a", "#c94c4c", "#4e79a7", "#7b61a8"]


def trend_chart(content: pd.DataFrame) -> alt.Chart:
    trend = content.groupby("capture_date", as_index=False).agg(
        impressions=("impressions", "sum"),
        engagement_rate=("engagement_rate", "mean"),
    )
    return (
        alt.Chart(trend)
        .mark_line(color=COLORS[0], strokeWidth=2.5)
        .encode(
            x=alt.X("capture_date:T", title=None),
            y=alt.Y("impressions:Q", title="曝光量", axis=alt.Axis(format="~s")),
            tooltip=[alt.Tooltip("capture_date:T", title="日期"), alt.Tooltip("impressions:Q", title="曝光量")],
        )
        .properties(height=285)
    )


def opportunity_scatter(products: pd.DataFrame) -> alt.Chart:
    data = products.copy()
    data["margin_pct"] = data["margin_rate"] * 100
    data["risk_pct"] = data["risk_rate"] * 100
    return (
        alt.Chart(data)
        .mark_circle(size=90, opacity=0.82)
        .encode(
            x=alt.X("keyword_demand:Q", title="需求强度", scale=alt.Scale(domain=[0, 1])),
            y=alt.Y("margin_pct:Q", title="毛利率（%）"),
            color=alt.Color("recommendation:N", title="建议", scale=alt.Scale(domain=["推荐", "观察", "不建议"], range=[COLORS[0], COLORS[1], COLORS[2]])),
            size=alt.Size("sales_count:Q", title="销量", scale=alt.Scale(range=[50, 600])),
            tooltip=[
                alt.Tooltip("product_name:N", title="商品"),
                alt.Tooltip("category:N", title="品类"),
                alt.Tooltip("overall_score:Q", title="综合分", format=".1f"),
                alt.Tooltip("margin_pct:Q", title="毛利率", format=".1f"),
                alt.Tooltip("risk_pct:Q", title="风险率", format=".1f"),
            ],
        )
        .interactive()
        .properties(height=330)
    )


def product_signal_trend(orders: pd.DataFrame, reviews: pd.DataFrame, product_id: str) -> pd.DataFrame:
    """Build a daily order/review signal table for one product."""
    order_data = orders.loc[orders.get("product_id", pd.Series(dtype=str)).astype(str) == str(product_id)].copy()
    review_data = reviews.loc[reviews.get("product_id", pd.Series(dtype=str)).astype(str) == str(product_id)].copy()
    order_data["日期"] = pd.to_datetime(order_data.get("order_date"), errors="coerce").dt.normalize()
    review_data["日期"] = pd.to_datetime(review_data.get("review_date"), errors="coerce").dt.normalize()
    order_daily = (
        order_data.dropna(subset=["日期"])
        .groupby("日期", as_index=False)
        .agg(订单数=("order_id", "nunique"), 收入=("revenue", "sum"))
        if not order_data.empty
        else pd.DataFrame(columns=["日期", "订单数", "收入"])
    )
    review_daily = (
        review_data.dropna(subset=["日期"])
        .assign(负向评论=lambda frame: (frame["sentiment"] == "负向").astype(int))
        .groupby("日期", as_index=False)
        .agg(评论数=("review_id", "nunique"), 负向评论=("负向评论", "sum"))
        if not review_data.empty
        else pd.DataFrame(columns=["日期", "评论数", "负向评论"])
    )
    result = order_daily.merge(review_daily, on="日期", how="outer").fillna(0).sort_values("日期")
    if result.empty:
        return pd.DataFrame(columns=["日期", "订单数", "收入", "评论数", "负向评论", "负向率"])
    result["负向率"] = 0.0
    has_reviews = result["评论数"] > 0
    result.loc[has_reviews, "负向率"] = (
        result.loc[has_reviews, "负向评论"] / result.loc[has_reviews, "评论数"]
    )
    return result.reset_index(drop=True)
