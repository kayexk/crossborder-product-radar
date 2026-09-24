import altair as alt
import streamlit as st

from utils.charts import opportunity_scatter, trend_chart
from utils.data import enrich_products, load_active_data
from utils.duckdb_store import query_kpis
from utils.filters import combined_date_bounds, filter_products, filter_related_datasets, normalize_date_range


products_raw, orders, content, reviews, source_label = load_active_data()
products = enrich_products(products_raw)

st.title("跨境商品雷达")
st.caption("用内容信号、利润空间和履约风险，支持小批量选品决策。")
st.caption(f"当前数据来源：{source_label}")
st.caption("核心聚合指标：DuckDB SQL；商品评分：pandas 可解释公式")

selected_platforms = st.session_state.get("global_platforms", sorted(products["platform"].unique()))
selected_categories = st.session_state.get("global_categories", sorted(products["category"].unique()))
selected_countries = st.session_state.get("global_countries", sorted(products["country"].unique()))
fallback_dates = combined_date_bounds([(orders, "order_date"), (content, "capture_date"), (reviews, "review_date")])
date_range = normalize_date_range(st.session_state.get("global_date_range"), fallback_dates)
filtered = filter_products(products, selected_platforms, selected_categories, selected_countries)
filtered, filtered_orders, filtered_content, _ = filter_related_datasets(products=filtered, orders=orders, content=content, reviews=reviews, date_range=date_range)

kpis = query_kpis(filtered, filtered_orders)
with st.container(horizontal=True):
    st.metric("监控商品数", f"{kpis['product_count']:,}", border=True)
    st.metric("平均毛利率", f"{kpis['avg_margin']:.1%}", border=True)
    st.metric("平均退款率", f"{kpis['avg_return']:.1%}", border=True)
    st.metric("推荐商品数", f"{kpis['recommended']:,}", border=True)

left, right = st.columns([1.05, 1.35])
with left:
    with st.container(border=True):
        st.subheader("内容需求趋势")
        st.altair_chart(trend_chart(filtered_content), width="stretch")
        st.caption("按日汇总内容曝光量，帮助判断需求是否持续，而不是只看单日爆发。")
with right:
    with st.container(border=True):
        st.subheader("需求与利润机会")
        st.altair_chart(opportunity_scatter(filtered), width="stretch")
        st.caption("右上区域通常更值得优先测试；颜色同时考虑履约和供应链风险。")

with st.container(border=True):
    st.subheader("优先观察商品")
    table = filtered.sort_values("overall_score", ascending=False).head(10).copy()
    table["综合评分"] = table["overall_score"].round(1)
    table["毛利率"] = (table["margin_rate"] * 100).round(1).astype(str) + "%"
    table["退款率"] = (table["return_rate"] * 100).round(1).astype(str) + "%"
    table["履约风险"] = (table["risk_rate"] * 100).round(1).astype(str) + "%"
    st.dataframe(
        table[["product_name", "category", "platform", "country", "综合评分", "毛利率", "退款率", "履约风险", "recommendation"]].rename(columns={"product_name": "商品", "category": "品类", "platform": "平台", "country": "市场", "recommendation": "建议"}),
        hide_index=True,
        width="stretch",
    )
    st.download_button(
        "下载当前商品清单",
        data=table.to_csv(index=False).encode("utf-8-sig"),
        file_name="filtered_products.csv",
        mime="text/csv",
        icon=":material/download:",
    )
