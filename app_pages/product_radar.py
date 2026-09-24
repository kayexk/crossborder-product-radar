import altair as alt
import pandas as pd
import streamlit as st

from utils.charts import product_signal_trend
from utils.data import enrich_products, load_active_data
from utils.duckdb_store import query_kpis, query_product_performance
from utils.filters import combined_date_bounds, filter_products, filter_related_datasets, normalize_date_range
from utils.metrics import find_anomalous_products, risk_driver_table


products_raw, orders, content, reviews, source_label = load_active_data()
products = enrich_products(products_raw)
selected_platforms = st.session_state.get("global_platforms", sorted(products["platform"].unique()))
selected_categories = st.session_state.get("global_categories", sorted(products["category"].unique()))
selected_countries = st.session_state.get("global_countries", sorted(products["country"].unique()))
fallback_dates = combined_date_bounds([(orders, "order_date"), (content, "capture_date"), (reviews, "review_date")])
date_range = normalize_date_range(st.session_state.get("global_date_range"), fallback_dates)
products = filter_products(products, selected_platforms, selected_categories, selected_countries)
products, orders, content, reviews = filter_related_datasets(products, orders, content, reviews, date_range)

st.title("商品雷达")
st.caption("查看单个商品的评分构成、成本结构和推荐理由。")
st.caption(f"当前商品数据来源：{source_label}")
catalog_kpis = query_kpis(products, orders)
st.caption(f"商品目录概览：{catalog_kpis['product_count']:,} 个商品，平均毛利率 {catalog_kpis['avg_margin']:.1%}（DuckDB SQL）")

if products.empty:
    st.info("当前全局筛选没有匹配商品，请放宽平台、品类或市场条件。")
    st.stop()

sort_options = {
    "综合评分": "overall_score",
    "毛利率": "margin_rate",
    "履约风险": "risk_rate",
    "销量": "sales_count",
}
sort_label = st.selectbox("商品排序", list(sort_options), index=0)
products = products.sort_values(
    sort_options[sort_label],
    ascending=sort_options[sort_label] == "risk_rate",
)
st.dataframe(
    products[["product_name", "category", "platform", "country", "overall_score", "margin_rate", "risk_rate", "recommendation"]]
    .head(8)
    .rename(
        columns={
            "product_name": "商品",
            "category": "品类",
            "platform": "平台",
            "country": "市场",
            "overall_score": "综合评分",
            "margin_rate": "毛利率",
            "risk_rate": "履约风险",
            "recommendation": "建议",
        }
    ),
    hide_index=True,
    width="stretch",
    column_config={
        "综合评分": st.column_config.NumberColumn(format="%.1f"),
        "毛利率": st.column_config.NumberColumn(format="%.1%"),
        "履约风险": st.column_config.NumberColumn(format="%.1%"),
    },
)

anomalies = find_anomalous_products(products)
with st.container(border=True):
    st.subheader("异常商品提醒")
    if anomalies.empty:
        st.success("当前筛选范围内没有触发异常阈值的商品。")
    else:
        anomaly_display = anomalies[
            ["product_name", "category", "risk_rate", "return_rate", "margin_rate", "rating", "异常原因"]
        ].head(10).rename(
            columns={
                "product_name": "商品",
                "category": "品类",
                "risk_rate": "履约风险",
                "return_rate": "退款率",
                "margin_rate": "毛利率",
                "rating": "评分",
            }
        )
        st.dataframe(
            anomaly_display,
            hide_index=True,
            width="stretch",
            column_config={
                "履约风险": st.column_config.NumberColumn(format="%.1%"),
                "退款率": st.column_config.NumberColumn(format="%.1%"),
                "毛利率": st.column_config.NumberColumn(format="%.1%"),
                "评分": st.column_config.NumberColumn(format="%.1f"),
            },
        )

selected_id = st.selectbox(
    "选择商品",
    products["product_id"].tolist(),
    format_func=lambda value: products.loc[products["product_id"] == value, "product_name"].iloc[0],
)
product = products.loc[products["product_id"] == selected_id].iloc[0]
performance = query_product_performance(orders, reviews)
performance_row = performance.loc[performance["product_id"] == selected_id]
performance_values = performance_row.iloc[0] if not performance_row.empty else {
    "order_count": 0, "revenue": 0.0, "delay_rate": 0.0, "refund_rate": 0.0, "review_count": 0, "negative_rate": 0.0
}

with st.container(horizontal=True):
    st.metric("综合评分", f"{product['overall_score']:.1f}", border=True)
    st.metric("毛利率", f"{product['margin_rate']:.1%}", border=True)
    st.metric("退款率", f"{product['return_rate']:.1%}", border=True)
    st.metric("履约风险", f"{product['risk_rate']:.1%}", border=True)

with st.container(horizontal=True):
    st.metric("关联订单", f"{int(performance_values['order_count']):,}", border=True)
    st.metric("订单收入", f"¥{float(performance_values['revenue']):,.2f}", border=True)
    st.metric("实际延误率", f"{float(performance_values['delay_rate']):.1%}", border=True)
    st.metric("关联评论", f"{int(performance_values['review_count']):,}", border=True)

risk_table = risk_driver_table(product)
with st.container(border=True):
    st.subheader("风险原因拆解")
    st.dataframe(
        risk_table.rename(columns={"指标值": "指标值", "权重": "权重", "风险贡献": "风险贡献"}),
        hide_index=True,
        width="stretch",
        column_config={
            "指标值": st.column_config.NumberColumn(format="%.1%"),
            "权重": st.column_config.NumberColumn(format="%.0%"),
            "风险贡献": st.column_config.NumberColumn(format="%.1%"),
        },
    )

trend = product_signal_trend(orders, reviews, selected_id)
with st.container(border=True):
    st.subheader("选中商品趋势")
    if trend.empty:
        st.info("当前日期范围没有该商品的订单或评论记录。")
    else:
        base = alt.Chart(trend).encode(x=alt.X("日期:T", title="日期"))
        orders_line = base.mark_line(color="#0f766e", strokeWidth=2.5).encode(
            y=alt.Y("订单数:Q", title="订单数"),
            tooltip=[alt.Tooltip("日期:T", title="日期"), alt.Tooltip("订单数:Q", title="订单数"), alt.Tooltip("收入:Q", title="收入", format=".2f")],
        )
        reviews_line = base.mark_line(color="#c94c4c", strokeWidth=2.5).encode(
            y=alt.Y("评论数:Q", title="评论数"),
            tooltip=[alt.Tooltip("日期:T", title="日期"), alt.Tooltip("评论数:Q", title="评论数"), alt.Tooltip("负向率:Q", title="负向率", format=".1%")],
        )
        st.altair_chart(orders_line + reviews_line, width="stretch")

left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.subheader("评分构成")
        score_data = pd.DataFrame(
            {
                "维度": ["需求强度", "利润空间", "内容传播", "供应链稳定", "风险控制"],
                "得分": [
                product["keyword_demand"] * 100,
                max(0, min(100, (product["margin_rate"] - 0.08) / 0.45 * 100)),
                product["content_score"] * 100,
                product["supplier_stability"] * 100,
                max(0, min(100, (1 - product["risk_rate"] / 0.22) * 100)),
                ],
            }
        )
        score_chart = alt.Chart(score_data).mark_bar(color="#0f766e", cornerRadiusEnd=4).encode(
            x=alt.X("得分:Q", scale=alt.Scale(domain=[0, 100]), title="分数"),
            y=alt.Y("维度:N", sort="-x", title=None),
            tooltip=[alt.Tooltip("得分:Q", format=".1f")],
        ).properties(height=260)
        st.altair_chart(score_chart, width="stretch")
with right:
    with st.container(border=True):
        st.subheader("成本结构")
        cost_data = pd.DataFrame(
            {
                "项目": ["采购成本", "平台佣金", "物流成本", "广告成本", "预估利润"],
                "金额": [
                product["cost_price"],
                product["commission_cost"],
                product["logistics_cost"],
                product["ad_cost"],
                product["gross_profit"],
                ],
            }
        )
        cost_chart = alt.Chart(cost_data).mark_bar().encode(
            x=alt.X("金额:Q", title="金额（元）"),
            y=alt.Y("项目:N", sort="-x", title=None),
            color=alt.Color("项目:N", legend=None, scale=alt.Scale(range=["#4e79a7", "#7b61a8", "#e89b4a", "#c94c4c", "#0f766e"])),
            tooltip=[alt.Tooltip("金额:Q", format=".2f")],
        ).properties(height=260)
        st.altair_chart(cost_chart, width="stretch")

recommendation = product["recommendation"]
if recommendation == "推荐":
    st.success(f"建议：{recommendation}。需求强度、利润空间和风险控制的综合结果较好，可进入小批量测试。")
elif recommendation == "观察":
    st.warning(f"建议：{recommendation}。先补充供应链和履约验证，再决定是否放量。")
else:
    st.error(f"建议：{recommendation}。当前综合评分不足，暂不建议投入较多广告预算。")

st.caption(
    f"关联证据：订单退款率 {float(performance_values['refund_rate']):.1%}，评论负向率 {float(performance_values['negative_rate']):.1%}。"
    "以上数据由订单和评论表按 product_id 联合聚合。"
)
