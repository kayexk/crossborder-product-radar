import pandas as pd

from utils.data import enrich_products
from utils.metrics import carrier_summary, calculate_kpis, find_anomalous_products, risk_driver_table


def test_enrich_products_calculates_margin_and_recommendation():
    raw = pd.DataFrame(
        [
            {
                "product_id": "P001",
                "product_name": "测试商品",
                "category": "家居收纳",
                "platform": "独立站",
                "country": "美国",
                "keyword_demand": 0.9,
                "content_score": 0.9,
                "avg_price": 100.0,
                "cost_price": 20.0,
                "commission_rate": 0.1,
                "logistics_cost": 5.0,
                "ad_cost": 5.0,
                "return_rate": 0.02,
                "delay_rate": 0.03,
                "supplier_stability": 0.95,
                "competition_index": 0.3,
                "sales_count": 1000,
                "rating": 4.8,
            }
        ]
    )
    result = enrich_products(raw).iloc[0]
    assert result["gross_profit"] == 60.0
    assert result["margin_rate"] == 0.6
    assert result["recommendation"] == "推荐"


def test_kpis_count_filtered_products_and_recommendations():
    products = pd.DataFrame(
        {
            "product_id": ["P001", "P002"],
            "margin_rate": [0.3, 0.4],
            "return_rate": [0.04, 0.06],
            "recommendation": ["推荐", "观察"],
        }
    )
    orders = pd.DataFrame({"order_id": ["O1", "O2"]})
    result = calculate_kpis(products, orders)
    assert result["product_count"] == 2
    assert result["recommended"] == 1
    assert result["order_count"] == 2


def test_carrier_summary_orders_by_delay_rate():
    orders = pd.DataFrame(
        {
            "order_id": ["O1", "O2", "O3"],
            "carrier": ["A", "A", "B"],
            "delayed": [True, False, True],
            "refunded": [False, False, True],
            "ship_days": [14, 7, 15],
        }
    )
    result = carrier_summary(orders)
    assert result.iloc[0]["carrier"] == "B"
    assert result.iloc[0]["delay_rate"] == 1.0


def test_risk_driver_table_explains_weighted_contributions():
    product = pd.Series(
        {
            "delay_rate": 0.20,
            "return_rate": 0.12,
            "supplier_stability": 0.60,
        }
    )
    result = risk_driver_table(product)
    assert result.iloc[0]["风险因素"] == "物流延误"
    assert result["风险贡献"].sum() == 0.20 * 0.5 + 0.12 * 0.3 + 0.40 * 0.2
    assert "延误率较高" in result.loc[result["风险因素"] == "物流延误", "解释"].iloc[0]


def test_find_anomalous_products_returns_reasons_and_keeps_normal_rows_out():
    products = pd.DataFrame(
        {
            "product_id": ["P1", "P2"],
            "product_name": ["异常品", "正常品"],
            "category": ["家居收纳", "家居收纳"],
            "delay_rate": [0.18, 0.04],
            "return_rate": [0.12, 0.03],
            "margin_rate": [0.20, 0.30],
            "rating": [4.5, 4.8],
            "risk_rate": [0.14, 0.04],
        }
    )
    result = find_anomalous_products(products)
    assert result["product_id"].tolist() == ["P1"]
    assert result.iloc[0]["异常原因"] == "物流延误偏高、退款率偏高"
