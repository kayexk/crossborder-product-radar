import altair as alt
import streamlit as st

from utils.data import enrich_products, load_active_data
from utils.duckdb_store import query_carrier_summary
from utils.filters import combined_date_bounds, filter_products, filter_related_datasets, normalize_date_range


products_raw, orders, content, reviews, source_label = load_active_data()
products = enrich_products(products_raw)
selected_platforms = st.session_state.get("global_platforms", sorted(products["platform"].unique()))
selected_categories = st.session_state.get("global_categories", sorted(products["category"].unique()))
selected_countries = st.session_state.get("global_countries", sorted(products["country"].unique()))
fallback_dates = combined_date_bounds([(orders, "order_date"), (content, "capture_date"), (reviews, "review_date")])
date_range = normalize_date_range(st.session_state.get("global_date_range"), fallback_dates)
products = filter_products(products, selected_platforms, selected_categories, selected_countries)
products, orders, content, reviews = filter_related_datasets(products, orders, content, reviews, date_range)

st.title("履约分析")
st.caption("把物流延误、退款和承运商表现放到同一条履约链路上观察。")
st.caption(f"当前数据来源：{source_label}")
st.caption("承运商聚合指标：DuckDB SQL")

filtered_orders = orders
carrier = query_carrier_summary(filtered_orders)
delay_rate = float(filtered_orders["delayed"].mean()) if not filtered_orders.empty else 0.0
refund_rate = float(filtered_orders["refunded"].mean()) if not filtered_orders.empty else 0.0
avg_days = float(filtered_orders["ship_days"].mean()) if not filtered_orders.empty else 0.0

with st.container(horizontal=True):
    st.metric("整体延误率", f"{delay_rate:.1%}", border=True)
    st.metric("整体退款率", f"{refund_rate:.1%}", border=True)
    st.metric("平均运输天数", f"{avg_days:.1f} 天", border=True)
    st.metric("订单数", f"{len(filtered_orders):,}", border=True)

left, right = st.columns(2)
with left:
    with st.container(border=True):
        st.subheader("承运商延误率")
        chart = alt.Chart(carrier).mark_bar(cornerRadiusEnd=4).encode(
            x=alt.X("delay_rate:Q", title="延误率", axis=alt.Axis(format=".0%")),
            y=alt.Y("carrier:N", sort="-x", title=None),
            color=alt.condition(alt.datum.delay_rate > delay_rate, alt.value("#c94c4c"), alt.value("#0f766e")),
            tooltip=[alt.Tooltip("carrier:N", title="承运商"), alt.Tooltip("delay_rate:Q", title="延误率", format=".1%"), alt.Tooltip("avg_ship_days:Q", title="平均天数", format=".1f")],
        ).properties(height=260)
        st.altair_chart(chart, width="stretch")
with right:
    with st.container(border=True):
        st.subheader("运输时长与退款")
        orders_plot = filtered_orders.copy()
        orders_plot["ship_day_group"] = orders_plot["ship_days"].clip(upper=18)
        grouped = orders_plot.groupby("ship_day_group", as_index=False).agg(refund_rate=("refunded", "mean"), order_count=("order_id", "nunique"))
        chart = alt.Chart(grouped).mark_line(point=True, color="#e89b4a", strokeWidth=2.5).encode(
            x=alt.X("ship_day_group:Q", title="运输天数"),
            y=alt.Y("refund_rate:Q", title="退款率", axis=alt.Axis(format=".0%")),
            tooltip=[alt.Tooltip("ship_day_group:Q", title="运输天数"), alt.Tooltip("refund_rate:Q", title="退款率", format=".1%"), alt.Tooltip("order_count:Q", title="订单数")],
        ).properties(height=260)
        st.altair_chart(chart, width="stretch")

with st.container(border=True):
    st.subheader("履约动作建议")
    if carrier.empty:
        st.info("当前日期范围没有订单数据。")
    else:
        worst = carrier.iloc[0]
        st.markdown(
            f"- **优先核查 {worst['carrier']}**：当前延误率为 **{worst['delay_rate']:.1%}**，高于全部订单平均值 **{delay_rate:.1%}**。\n"
            "- 对高延误线路设置备选承运商，先以小批量订单验证时效。\n"
            "- 将延误订单的退款和差评单独追踪，避免只看平均物流时长。"
        )
    st.download_button("下载履约汇总", data=carrier.to_csv(index=False).encode("utf-8-sig"), file_name="fulfillment_summary.csv", mime="text/csv", icon=":material/download:")
