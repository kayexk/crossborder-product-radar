import pandas as pd
import pytest

from utils.duckdb_store import query_carrier_summary, query_kpis, query_product_performance, query_review_summary
from utils.metrics import calculate_kpis, carrier_summary, review_summary


def test_duckdb_kpis_match_pandas_baseline():
    products = pd.DataFrame(
        {
            "product_id": ["P001", "P002", "P002"],
            "margin_rate": [0.3, 0.4, 0.4],
            "return_rate": [0.04, 0.06, 0.06],
            "recommendation": ["推荐", "观察", "观察"],
        }
    )
    orders = pd.DataFrame({"order_id": ["O1", "O2", "O2"]})

    assert query_kpis(products, orders) == calculate_kpis(products, orders)


def test_duckdb_carrier_summary_matches_pandas_baseline():
    orders = pd.DataFrame(
        {
            "order_id": ["O1", "O2", "O3", "O4"],
            "carrier": ["A", "A", "B", "B"],
            "delayed": [True, False, True, True],
            "refunded": [False, False, True, False],
            "ship_days": [14, 7, 15, 16],
        }
    )

    expected = carrier_summary(orders).sort_values("carrier").reset_index(drop=True)
    actual = query_carrier_summary(orders).sort_values("carrier").reset_index(drop=True)
    pd.testing.assert_frame_equal(actual, expected, check_dtype=False, check_like=True)
    assert actual["delay_rate"].tolist() == pytest.approx(expected["delay_rate"].tolist())


def test_duckdb_review_summary_matches_pandas_baseline():
    reviews = pd.DataFrame(
        {
            "review_id": ["R1", "R2", "R3", "R4"],
            "theme": ["质量", "质量", "物流", "物流"],
            "sentiment": ["正向", "负向", "负向", "正向"],
        }
    )

    expected = review_summary(reviews).sort_values("theme").reset_index(drop=True)
    actual = query_review_summary(reviews).sort_values("theme").reset_index(drop=True)
    pd.testing.assert_frame_equal(actual, expected, check_dtype=False, check_like=True)
    assert actual["negative_rate"].tolist() == pytest.approx(expected["negative_rate"].tolist())


def test_duckdb_empty_inputs_return_stable_results():
    products = pd.DataFrame(columns=["product_id", "margin_rate", "return_rate", "recommendation"])
    orders = pd.DataFrame(columns=["order_id", "carrier", "delayed", "refunded", "ship_days"])
    reviews = pd.DataFrame(columns=["review_id", "theme", "sentiment"])

    assert query_kpis(products, orders) == calculate_kpis(products, orders)
    assert list(query_carrier_summary(orders).columns) == list(carrier_summary(orders).columns)
    assert list(query_review_summary(reviews).columns) == list(review_summary(reviews).columns)


def test_duckdb_product_performance_joins_orders_and_reviews():
    orders = pd.DataFrame({
        "order_id": ["O1", "O2", "O3"], "product_id": ["P1", "P1", "P2"],
        "revenue": [10.0, 20.0, 15.0], "delayed": [True, False, True], "refunded": [False, True, False],
    })
    reviews = pd.DataFrame({
        "review_id": ["R1", "R2", "R3"], "product_id": ["P1", "P1", "P3"],
        "sentiment": ["正向", "负向", "负向"],
    })
    result = query_product_performance(orders, reviews).set_index("product_id")
    assert result.loc["P1", "order_count"] == 2
    assert result.loc["P1", "revenue"] == 30.0
    assert result.loc["P1", "delay_rate"] == pytest.approx(0.5)
    assert result.loc["P1", "negative_rate"] == pytest.approx(0.5)
    assert result.loc["P3", "order_count"] == 0
