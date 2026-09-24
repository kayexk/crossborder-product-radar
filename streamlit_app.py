from datetime import date

import pandas as pd
import streamlit as st

from utils.data import dataset_status, load_active_data, load_demo_data
from utils.filters import combined_date_bounds, normalize_date_range
from utils.importer import ProductImportError, parse_dataset_csv, validate_product_references

st.set_page_config(
    page_title="跨境商品雷达",
    page_icon=":material/analytics:",
    layout="wide",
    initial_sidebar_state="expanded",
)


def render_data_source_uploader() -> None:
    """Allow each dashboard dataset to be replaced without external credentials."""
    with st.sidebar:
        st.divider()
        st.subheader("数据来源")
        st.caption("可分别上传商品、订单、内容和评论 CSV；未上传的表继续使用演示数据。")
        template_products, template_orders, template_content, template_reviews = load_demo_data()
        templates = {
            "products": ("商品", template_products, "product_catalog_template.csv"),
            "orders": ("订单", template_orders, "orders_template.csv"),
            "content": ("内容", template_content, "content_template.csv"),
            "reviews": ("评论", template_reviews, "reviews_template.csv"),
        }
        for dataset, (label, template, filename) in templates.items():
            with st.container(border=True):
                st.download_button(
                    f"下载{label}模板",
                    data=template.head(3).to_csv(index=False).encode("utf-8-sig"),
                    file_name=filename,
                    mime="text/csv",
                    icon=":material/download:",
                    key=f"{dataset}_template_download",
                    width="stretch",
                )
                uploaded_file = st.file_uploader(
                    f"{label} CSV",
                    type=["csv"],
                    key=f"{dataset}_csv_upload",
                    help=f"必须包含模板中的 {len(template.columns)} 个字段。",
                )
            if uploaded_file is None:
                st.session_state.pop(f"uploaded_{dataset}", None)
                st.session_state.pop(f"data_source_{dataset}", None)
                continue
            try:
                parsed = parse_dataset_csv(uploaded_file.getvalue(), dataset)
                if dataset != "products":
                    active_products = st.session_state.get("uploaded_products", template_products)
                    validate_product_references(active_products, parsed, dataset)
                st.session_state[f"uploaded_{dataset}"] = parsed
                st.session_state[f"data_source_{dataset}"] = uploaded_file.name
                st.success(f"{label}已载入 {len(parsed):,} 条")
            except ProductImportError as exc:
                st.session_state.pop(f"uploaded_{dataset}", None)
                st.session_state.pop(f"data_source_{dataset}", None)
                st.error(f"{label}：{exc}")
        active_products = st.session_state.get("uploaded_products", template_products)
        for dataset, label in (("orders", "订单"), ("content", "内容"), ("reviews", "评论")):
            uploaded_supporting = st.session_state.get(f"uploaded_{dataset}")
            if not isinstance(uploaded_supporting, pd.DataFrame):
                continue
            try:
                validate_product_references(active_products, uploaded_supporting, dataset)
            except ProductImportError as exc:
                st.session_state.pop(f"uploaded_{dataset}", None)
                st.session_state.pop(f"data_source_{dataset}", None)
                st.error(f"{label}：{exc}")


def render_data_status() -> None:
    demo_products, demo_orders, demo_content, demo_reviews = load_demo_data()
    products = st.session_state.get("uploaded_products", demo_products)
    orders = st.session_state.get("uploaded_orders", demo_orders)
    content = st.session_state.get("uploaded_content", demo_content)
    reviews = st.session_state.get("uploaded_reviews", demo_reviews)
    names = {key: st.session_state[f"data_source_{key}"] for key in ("products", "orders", "content", "reviews") if f"data_source_{key}" in st.session_state}
    status = dataset_status(products, orders, content, reviews, names)
    with st.sidebar:
        with st.expander("数据健康状态", expanded=True):
            st.dataframe(
                status,
                hide_index=True,
                width="stretch",
                column_config={"商品关联率": st.column_config.ProgressColumn("商品关联率", format="%.0f%%", min_value=0, max_value=1)},
            )
            if (status.loc[status["数据集"] != "商品", "商品关联率"] < 1).any():
                st.warning("部分支持数据包含未关联商品，请检查 product_id。")


def render_global_filters() -> None:
    """Render the single filter state shared by every dashboard page."""
    products, orders, content, reviews, _ = load_active_data()
    platforms = sorted(products.get("platform", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
    categories = sorted(products.get("category", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
    countries = sorted(products.get("country", pd.Series(dtype=str)).dropna().astype(str).unique().tolist())
    date_min, date_max = combined_date_bounds(
        [(orders, "order_date"), (content, "capture_date"), (reviews, "review_date")]
    )

    # Keep keyed widgets valid when a newly uploaded CSV changes its options or bounds.
    for key, options in (
        ("global_platforms", platforms),
        ("global_categories", categories),
        ("global_countries", countries),
    ):
        selected = st.session_state.get(key)
        if not isinstance(selected, list) or any(value not in options for value in selected):
            st.session_state[key] = options
    current_dates = normalize_date_range(st.session_state.get("global_date_range"), (date_min, date_max))
    if "global_date_range" not in st.session_state or current_dates[0] < date_min or current_dates[1] > date_max:
        st.session_state["global_date_range"] = (date_min, date_max)

    with st.sidebar:
        st.divider()
        st.subheader("全局筛选")
        st.caption("切换页面后仍会保留当前平台、品类、市场和日期范围。")
        st.multiselect("平台", platforms, key="global_platforms")
        st.multiselect("品类", categories, key="global_categories")
        st.multiselect("市场", countries, key="global_countries")
        st.date_input(
            "统一日期范围",
            min_value=date_min,
            max_value=date_max,
            key="global_date_range",
        )


render_data_source_uploader()
render_data_status()
render_global_filters()

pages = [
    st.Page("app_pages/overview.py", title="总览", icon=":material/dashboard:"),
    st.Page("app_pages/product_radar.py", title="商品雷达", icon=":material/search:"),
    st.Page("app_pages/fulfillment.py", title="履约分析", icon=":material/local_shipping:"),
    st.Page("app_pages/insights.py", title="评论洞察", icon=":material/insights:"),
]

st.navigation(pages).run()
