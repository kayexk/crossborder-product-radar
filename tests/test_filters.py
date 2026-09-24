from datetime import date

import pandas as pd
import pytest

from utils.filters import combined_date_bounds, date_bounds, filter_by_date, filter_products, filter_related_datasets
from utils.charts import product_signal_trend


def test_filter_by_date_is_inclusive_and_does_not_mutate():
    frame = pd.DataFrame({"event_date": pd.to_datetime(["2026-06-01", "2026-06-15", "2026-07-01"]), "value": [1, 2, 3]})
    result = filter_by_date(frame, "event_date", date(2026, 6, 1), date(2026, 6, 15))
    assert result["value"].tolist() == [1, 2]
    assert len(frame) == 3


def test_date_bounds_returns_minimum_and_maximum_dates():
    frame = pd.DataFrame({"event_date": pd.to_datetime(["2026-06-01", "2026-07-01"])})
    assert date_bounds(frame, "event_date") == (date(2026, 6, 1), date(2026, 7, 1))


def test_combined_date_bounds_uses_union_across_tables():
    orders = pd.DataFrame({"order_date": pd.to_datetime(["2026-06-10", "2026-06-20"])})
    reviews = pd.DataFrame({"review_date": pd.to_datetime(["2026-05-28", "2026-07-02"])})
    assert combined_date_bounds([(orders, "order_date"), (reviews, "review_date")]) == (
        date(2026, 5, 28),
        date(2026, 7, 2),
    )


def test_global_product_scope_and_related_tables_share_product_and_date_filters():
    products = pd.DataFrame(
        {
            "product_id": ["P1", "P2"],
            "platform": ["Amazon", "TikTok Shop"],
            "category": ["家居收纳", "宠物用品"],
            "country": ["美国", "英国"],
        }
    )
    orders = pd.DataFrame(
        {
            "product_id": ["P1", "P2"],
            "order_date": pd.to_datetime(["2026-06-10", "2026-06-20"]),
        }
    )
    content = pd.DataFrame(
        {
            "product_id": ["P1", "P2"],
            "capture_date": pd.to_datetime(["2026-06-11", "2026-06-21"]),
        }
    )
    reviews = pd.DataFrame(
        {
            "product_id": ["P1", "P2"],
            "review_date": pd.to_datetime(["2026-06-12", "2026-06-22"]),
        }
    )
    scoped = filter_products(products, ["Amazon"], ["家居收纳"], ["美国"])
    _, scoped_orders, scoped_content, scoped_reviews = filter_related_datasets(
        scoped,
        orders,
        content,
        reviews,
        (date(2026, 6, 1), date(2026, 6, 15)),
    )
    assert scoped["product_id"].tolist() == ["P1"]
    assert scoped_orders["product_id"].tolist() == ["P1"]
    assert scoped_content["product_id"].tolist() == ["P1"]
    assert scoped_reviews["product_id"].tolist() == ["P1"]


def test_empty_global_product_scope_returns_empty_related_tables():
    products = pd.DataFrame({"product_id": ["P1"], "platform": ["Amazon"], "category": ["家居收纳"], "country": ["美国"]})
    orders = pd.DataFrame({"product_id": ["P1"], "order_date": pd.to_datetime(["2026-06-10"])})
    scoped = filter_products(products, [], ["家居收纳"], ["美国"])
    _, scoped_orders, _, _ = filter_related_datasets(scoped, orders, pd.DataFrame(), pd.DataFrame(), (date(2026, 6, 1), date(2026, 6, 15)))
    assert scoped.empty
    assert scoped_orders.empty


def test_product_signal_trend_merges_orders_and_reviews_by_day():
    orders = pd.DataFrame(
        {
            "order_id": ["O1", "O2"],
            "product_id": ["P1", "P1"],
            "order_date": pd.to_datetime(["2026-06-01", "2026-06-01"]),
            "revenue": [10.0, 15.0],
        }
    )
    reviews = pd.DataFrame(
        {
            "review_id": ["R1", "R2"],
            "product_id": ["P1", "P1"],
            "review_date": pd.to_datetime(["2026-06-01", "2026-06-02"]),
            "sentiment": ["负向", "正向"],
        }
    )
    result = product_signal_trend(orders, reviews, "P1")
    assert result["订单数"].tolist() == [2, 0]
    assert result["收入"].tolist() == [25.0, 0.0]
    assert result["评论数"].tolist() == [1, 1]
    assert result["负向率"].tolist() == pytest.approx([1.0, 0.0])
