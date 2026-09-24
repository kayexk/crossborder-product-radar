from __future__ import annotations

from datetime import date, timedelta

import numpy as np
import pandas as pd
import streamlit as st

from utils.filters import date_bounds


CATEGORIES = ["家居收纳", "宠物用品", "旅行用品", "办公整理", "户外小件"]
PLATFORMS = ["独立站", "Amazon", "TikTok Shop"]
COUNTRIES = ["美国", "英国", "德国", "日本", "澳大利亚"]
CARRIERS = ["Carrier A", "Carrier B", "Carrier C"]
THEMES = ["质量", "物流", "效果", "尺寸", "售后"]


@st.cache_data(ttl="1h")
def load_demo_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Create stable synthetic data for the portfolio demo."""
    rng = np.random.default_rng(42)

    product_rows = []
    names = [
        "折叠收纳箱", "旅行压缩袋", "宠物饮水器", "桌面理线器", "防水旅行收纳包",
        "猫砂垫", "车载收纳袋", "便携洗漱包", "桌面文件架", "宠物外出背包",
    ]
    for index in range(1, 61):
        category = CATEGORIES[(index - 1) % len(CATEGORIES)]
        price = round(float(rng.uniform(18, 86)), 2)
        cost = round(price * float(rng.uniform(0.27, 0.52)), 2)
        product_rows.append(
            {
                "product_id": f"P{index:03d}",
                "product_name": f"{names[(index - 1) % len(names)]} {index:02d}",
                "category": category,
                "platform": PLATFORMS[(index - 1) % len(PLATFORMS)],
                "country": COUNTRIES[(index - 1) % len(COUNTRIES)],
                "keyword_demand": round(float(rng.uniform(0.35, 0.98)), 3),
                "content_score": round(float(rng.uniform(0.25, 0.95)), 3),
                "avg_price": price,
                "cost_price": cost,
                "commission_rate": round(float(rng.uniform(0.06, 0.15)), 3),
                "logistics_cost": round(float(rng.uniform(3.2, 12.5)), 2),
                "ad_cost": round(float(rng.uniform(1.8, 9.5)), 2),
                "return_rate": round(float(rng.uniform(0.015, 0.14)), 3),
                "delay_rate": round(float(rng.uniform(0.025, 0.19)), 3),
                "supplier_stability": round(float(rng.uniform(0.55, 0.98)), 3),
                "competition_index": round(float(rng.uniform(0.2, 0.94)), 3),
                "sales_count": int(rng.integers(180, 6800)),
                "rating": round(float(rng.uniform(3.6, 4.9)), 1),
            }
        )
    products = pd.DataFrame(product_rows)

    order_rows = []
    start = date(2026, 5, 1)
    for index in range(1, 1501):
        product = products.iloc[(index - 1) % len(products)]
        ship_days = int(rng.integers(4, 18))
        delayed = ship_days >= 13 or rng.random() < 0.07
        refunded = bool(rng.random() < (0.035 + (0.04 if delayed else 0)))
        order_rows.append(
            {
                "order_id": f"O{index:05d}",
                "product_id": product["product_id"],
                "order_date": start + timedelta(days=int(rng.integers(0, 120))),
                "country": product["country"],
                "carrier": CARRIERS[(index - 1) % len(CARRIERS)],
                "revenue": round(float(product["avg_price"] * rng.uniform(0.9, 1.05)), 2),
                "ship_days": ship_days,
                "delayed": delayed,
                "refunded": refunded,
            }
        )
    orders = pd.DataFrame(order_rows)
    orders["order_date"] = pd.to_datetime(orders["order_date"])

    content_rows = []
    for day in range(120):
        capture_date = start + timedelta(days=day)
        for product in products.iloc[::3].itertuples(index=False):
            impressions = int(rng.integers(500, 25000) * (1 + day / 300))
            likes = int(impressions * rng.uniform(0.015, 0.09))
            saves = int(impressions * rng.uniform(0.006, 0.045))
            comments = int(impressions * rng.uniform(0.002, 0.018))
            content_rows.append(
                {
                    "product_id": product.product_id,
                    "capture_date": capture_date,
                    "platform": product.platform,
                    "impressions": impressions,
                    "likes": likes,
                    "saves": saves,
                    "comments": comments,
                    "engagement_rate": round((likes + saves + comments) / impressions, 4),
                }
            )
    content = pd.DataFrame(content_rows)

    review_rows = []
    review_text = {
        "质量": "材质比预期结实，使用一段时间后仍然稳定",
        "物流": "配送比预计慢了几天，包装没有破损",
        "效果": "收纳效果不错，实际使用比较方便",
        "尺寸": "尺寸和页面描述一致，适合小户型",
        "售后": "客服响应较快，换货流程比较清楚",
    }
    for index in range(1, 901):
        theme = THEMES[(index - 1) % len(THEMES)]
        sentiment = "正向" if rng.random() > 0.22 else "负向"
        review_rows.append(
            {
                "review_id": f"R{index:05d}",
                "product_id": products.iloc[(index * 7) % len(products)]["product_id"],
                "review_date": start + timedelta(days=int(rng.integers(0, 120))),
                "theme": theme,
                "sentiment": sentiment,
                "text": review_text[theme],
            }
        )
    reviews = pd.DataFrame(review_rows)
    reviews["review_date"] = pd.to_datetime(reviews["review_date"])
    return products, orders, content, reviews


def load_active_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, str]:
    """Return uploaded datasets when present, falling back per dataset to demo data."""
    products, orders, content, reviews = load_demo_data()
    labels = []
    dataset_labels = {"products": "商品", "orders": "订单", "content": "内容", "reviews": "评论"}
    for name in ("products", "orders", "content", "reviews"):
        uploaded = st.session_state.get(f"uploaded_{name}")
        if isinstance(uploaded, pd.DataFrame):
            if name == "products":
                products = uploaded.copy()
            elif name == "orders":
                orders = uploaded.copy()
            elif name == "content":
                content = uploaded.copy()
            else:
                reviews = uploaded.copy()
            filename = st.session_state.get(f"data_source_{name}", name)
            labels.append(f"{dataset_labels[name]}：{filename}")
    source_label = "演示数据" if not labels else "、".join(labels)
    return products, orders, content, reviews, source_label


def dataset_status(products: pd.DataFrame, orders: pd.DataFrame, content: pd.DataFrame, reviews: pd.DataFrame, uploaded_names: dict[str, str] | None = None) -> pd.DataFrame:
    """Build a compact data health table for the sidebar status panel."""
    uploaded_names = uploaded_names or {}
    product_ids = set(products["product_id"].astype(str)) if "product_id" in products else set()
    rows = []
    for key, label, frame, date_column in (
        ("products", "商品", products, None),
        ("orders", "订单", orders, "order_date"),
        ("content", "内容", content, "capture_date"),
        ("reviews", "评论", reviews, "review_date"),
    ):
        source = uploaded_names.get(key, "演示数据")
        start, end = date_bounds(frame, date_column) if date_column else (None, None)
        coverage = 1.0
        if key != "products" and not frame.empty and "product_id" in frame and product_ids:
            coverage = float(frame["product_id"].astype(str).isin(product_ids).mean())
        rows.append({
            "数据集": label,
            "来源": source,
            "记录数": int(len(frame)),
            "日期范围": f"{start} 至 {end}" if start and end else "不适用",
            "商品关联率": coverage,
        })
    return pd.DataFrame(rows)


@st.cache_data
def enrich_products(products: pd.DataFrame) -> pd.DataFrame:
    """Add business metrics used by every page (cached: pure function of the input frame)."""
    enriched = products.copy()
    enriched["commission_cost"] = enriched["avg_price"] * enriched["commission_rate"]
    enriched["gross_profit"] = (
        enriched["avg_price"]
        - enriched["cost_price"]
        - enriched["commission_cost"]
        - enriched["logistics_cost"]
        - enriched["ad_cost"]
    )
    enriched["margin_rate"] = enriched["gross_profit"] / enriched["avg_price"]
    enriched["risk_rate"] = (
        enriched["delay_rate"] * 0.5
        + enriched["return_rate"] * 0.3
        + (1 - enriched["supplier_stability"]) * 0.2
    )
    margin_score = ((enriched["margin_rate"] - 0.08) / 0.45).clip(0, 1)
    risk_score = (1 - enriched["risk_rate"] / 0.22).clip(0, 1)
    demand_score = enriched["keyword_demand"]
    enriched["overall_score"] = (
        demand_score * 0.30
        + margin_score * 0.25
        + enriched["content_score"] * 0.15
        + enriched["supplier_stability"] * 0.15
        + risk_score * 0.15
    ) * 100
    enriched["recommendation"] = pd.cut(
        enriched["overall_score"],
        bins=[-np.inf, 55, 72, np.inf],
        labels=["不建议", "观察", "推荐"],
    ).astype(str)
    return enriched
