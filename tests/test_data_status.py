import pandas as pd

from utils.data import dataset_status


def test_dataset_status_reports_counts_dates_and_reference_coverage():
    products = pd.DataFrame({"product_id": ["P1", "P2"]})
    orders = pd.DataFrame({"product_id": ["P1", "P9"], "order_date": pd.to_datetime(["2026-06-01", "2026-06-02"])})
    content = pd.DataFrame({"product_id": ["P1"], "capture_date": pd.to_datetime(["2026-06-03"])})
    reviews = pd.DataFrame({"product_id": ["P2"], "review_date": pd.to_datetime(["2026-06-04"])})
    result = dataset_status(products, orders, content, reviews, {"orders": "orders.csv"})
    assert result.loc[result["数据集"] == "订单", "记录数"].item() == 2
    assert result.loc[result["数据集"] == "订单", "商品关联率"].item() == 0.5
    assert result.loc[result["数据集"] == "订单", "来源"].item() == "orders.csv"
