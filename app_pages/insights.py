import altair as alt
import streamlit as st

from utils.data import load_active_data
from utils.duckdb_store import query_review_summary
from utils.data import enrich_products
from utils.filters import combined_date_bounds, filter_products, filter_related_datasets, normalize_date_range


products, orders, content, reviews, source_label = load_active_data()
products = enrich_products(products)
selected_platforms = st.session_state.get("global_platforms", sorted(products["platform"].unique()))
selected_categories = st.session_state.get("global_categories", sorted(products["category"].unique()))
selected_countries = st.session_state.get("global_countries", sorted(products["country"].unique()))
fallback_dates = combined_date_bounds([(orders, "order_date"), (content, "capture_date"), (reviews, "review_date")])
date_range = normalize_date_range(st.session_state.get("global_date_range"), fallback_dates)
products = filter_products(products, selected_platforms, selected_categories, selected_countries)
products, orders, content, reviews = filter_related_datasets(products, orders, content, reviews, date_range)
summary = query_review_summary(reviews)

st.title("评论洞察")
st.caption("第一版采用可解释的规则分类，后续可接入本地模型做主题归因。")
st.caption(f"当前数据来源：{source_label}")
st.caption("主题聚合指标：DuckDB SQL")
filtered_reviews = reviews
summary = query_review_summary(filtered_reviews)

left, right = st.columns([1.1, 1])
with left:
    with st.container(border=True):
        st.subheader("用户反馈主题")
        chart = alt.Chart(summary).mark_bar(cornerRadiusEnd=4).encode(
            x=alt.X("review_count:Q", title="评论数"),
            y=alt.Y("theme:N", sort="-x", title=None),
            color=alt.Color("negative_rate:Q", title="负向率", scale=alt.Scale(scheme="oranges")),
            tooltip=[alt.Tooltip("theme:N", title="主题"), alt.Tooltip("review_count:Q", title="评论数"), alt.Tooltip("negative_rate:Q", title="负向率", format=".1%")],
        ).properties(height=290)
        st.altair_chart(chart, width="stretch")
with right:
    with st.container(border=True):
        st.subheader("主题结论")
        for row in summary.head(5).itertuples(index=False):
            label = "需要优先关注" if row.negative_rate >= 0.25 else "持续观察"
            st.markdown(f"**{row.theme}** · {label}")
            st.caption(f"共 {row.review_count:,} 条反馈，负向率 {row.negative_rate:.1%}")

with st.container(border=True):
    st.subheader("代表性反馈")
    display = filtered_reviews[["theme", "sentiment", "text"]].head(12).rename(columns={"theme": "主题", "sentiment": "情绪", "text": "反馈"})
    st.dataframe(display, hide_index=True, width="stretch")
    st.download_button("下载评论明细", data=filtered_reviews.to_csv(index=False).encode("utf-8-sig"), file_name="filtered_reviews.csv", mime="text/csv", icon=":material/download:")
