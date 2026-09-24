from __future__ import annotations

import pandas as pd


RISK_THRESHOLDS = {
    "delay_rate": 0.12,
    "return_rate": 0.10,
    "margin_rate": 0.12,
    "rating": 4.0,
}


def calculate_kpis(products: pd.DataFrame, orders: pd.DataFrame) -> dict[str, float | int]:
    if products.empty:
        return {
            "product_count": 0,
            "avg_margin": 0.0,
            "avg_return": 0.0,
            "recommended": 0,
            "order_count": int(orders["order_id"].nunique()) if "order_id" in orders else 0,
        }
    return {
        "product_count": int(products["product_id"].nunique()),
        "avg_margin": float(products["margin_rate"].mean()),
        "avg_return": float(products["return_rate"].mean()),
        "recommended": int((products["recommendation"] == "推荐").sum()),
        "order_count": int(orders["order_id"].nunique()),
    }


def carrier_summary(orders: pd.DataFrame) -> pd.DataFrame:
    if orders.empty:
        return pd.DataFrame(columns=["carrier", "delay_rate", "refund_rate", "avg_ship_days", "order_count"])
    return (
        orders.groupby("carrier", as_index=False)
        .agg(
            delay_rate=("delayed", "mean"),
            refund_rate=("refunded", "mean"),
            avg_ship_days=("ship_days", "mean"),
            order_count=("order_id", "nunique"),
        )
        .sort_values("delay_rate", ascending=False)
    )


def review_summary(reviews: pd.DataFrame) -> pd.DataFrame:
    if reviews.empty:
        return pd.DataFrame(columns=["theme", "review_count", "negative_rate"])
    summary = (
        reviews.groupby("theme", as_index=False)
        .agg(
            review_count=("review_id", "nunique"),
            negative_rate=("sentiment", lambda values: (values == "负向").mean()),
        )
        .sort_values("review_count", ascending=False)
    )
    return summary


def risk_driver_table(product: pd.Series) -> pd.DataFrame:
    """Explain the weighted risk score for one enriched product."""
    rows = [
        ("物流延误", float(product["delay_rate"]), 0.5, "延误率较高" if product["delay_rate"] >= RISK_THRESHOLDS["delay_rate"] else "延误率可控"),
        ("退款表现", float(product["return_rate"]), 0.3, "退款率较高" if product["return_rate"] >= RISK_THRESHOLDS["return_rate"] else "退款率可控"),
        ("供应商稳定性", float(1 - product["supplier_stability"]), 0.2, "供应稳定性偏弱" if product["supplier_stability"] < 0.7 else "供应稳定性较好"),
    ]
    result = pd.DataFrame(rows, columns=["风险因素", "指标值", "权重", "解释"])
    result["风险贡献"] = result["指标值"] * result["权重"]
    return result.sort_values("风险贡献", ascending=False).reset_index(drop=True)


def find_anomalous_products(products: pd.DataFrame) -> pd.DataFrame:
    """Return products with an operational warning and a human-readable reason."""
    if products.empty:
        return products.copy()
    result = products.copy()
    conditions = {
        "物流延误偏高": result["delay_rate"] >= RISK_THRESHOLDS["delay_rate"],
        "退款率偏高": result["return_rate"] >= RISK_THRESHOLDS["return_rate"],
        "毛利率偏低": result["margin_rate"] < RISK_THRESHOLDS["margin_rate"],
        "评分偏低": result["rating"] < RISK_THRESHOLDS["rating"],
    }
    result["异常原因"] = [
        "、".join(label for label, mask in conditions.items() if bool(mask.iloc[index]))
        for index in range(len(result))
    ]
    return result[result["异常原因"] != ""].sort_values(
        ["risk_rate", "return_rate"], ascending=[False, False]
    ).reset_index(drop=True)
