import pandas as pd
import pytest

from utils.importer import ProductImportError, parse_dataset_csv, parse_product_csv, validate_product_frame, validate_product_references


def valid_product_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "product_id": ["P001"],
            "product_name": ["测试商品"],
            "category": ["家居收纳"],
            "platform": ["独立站"],
            "country": ["美国"],
            "keyword_demand": [0.8],
            "content_score": [0.7],
            "avg_price": [49.9],
            "cost_price": [20.0],
            "commission_rate": [0.1],
            "logistics_cost": [5.0],
            "ad_cost": [4.0],
            "return_rate": [0.04],
            "delay_rate": [0.06],
            "supplier_stability": [0.9],
            "competition_index": [0.4],
            "sales_count": [1000],
            "rating": [4.6],
        }
    )


def test_parse_product_csv_accepts_required_schema():
    result = parse_product_csv(valid_product_frame().to_csv(index=False).encode("utf-8"))
    assert list(result.columns) == [
        "product_id", "product_name", "category", "platform", "country",
        "keyword_demand", "content_score", "avg_price", "cost_price",
        "commission_rate", "logistics_cost", "ad_cost", "return_rate",
        "delay_rate", "supplier_stability", "competition_index", "sales_count", "rating",
    ]
    assert result.loc[0, "avg_price"] == 49.9


def test_validate_product_frame_rejects_missing_columns():
    frame = valid_product_frame().drop(columns=["rating"])
    with pytest.raises(ProductImportError, match="缺少必填字段.*rating"):
        validate_product_frame(frame)


def test_validate_product_frame_rejects_out_of_range_values():
    frame = valid_product_frame()
    frame.loc[0, "return_rate"] = 1.2
    with pytest.raises(ProductImportError, match="return_rate"):
        validate_product_frame(frame)


def test_validate_product_frame_rejects_duplicate_ids():
    frame = pd.concat([valid_product_frame(), valid_product_frame()], ignore_index=True)
    with pytest.raises(ProductImportError, match="product_id 必须唯一"):
        validate_product_frame(frame)


def test_parse_orders_csv_normalizes_dates_and_booleans():
    frame = pd.DataFrame(
        {
            "order_id": ["O1"], "product_id": ["P001"], "order_date": ["2026-06-01"],
            "country": ["美国"], "carrier": ["Carrier A"], "revenue": [49.9],
            "ship_days": [8], "delayed": ["false"], "refunded": ["否"],
        }
    )
    result = parse_dataset_csv(frame.to_csv(index=False).encode("utf-8"), "orders")
    assert pd.api.types.is_datetime64_any_dtype(result["order_date"])
    assert bool(result.loc[0, "delayed"]) is False
    assert bool(result.loc[0, "refunded"]) is False


def test_parse_content_csv_rejects_invalid_engagement_rate():
    frame = pd.DataFrame(
        {
            "product_id": ["P001"], "capture_date": ["2026-06-01"], "platform": ["独立站"],
            "impressions": [100], "likes": [4], "saves": [2], "comments": [1],
            "engagement_rate": [1.2],
        }
    )
    with pytest.raises(ProductImportError, match="engagement_rate"):
        parse_dataset_csv(frame.to_csv(index=False).encode("utf-8"), "content")


def test_parse_reviews_csv_rejects_unknown_sentiment():
    frame = pd.DataFrame(
        {
            "review_id": ["R1"], "product_id": ["P001"], "review_date": ["2026-06-01"],
            "theme": ["质量"], "sentiment": ["中性"], "text": ["测试反馈"],
        }
    )
    with pytest.raises(ProductImportError, match="sentiment"):
        parse_dataset_csv(frame.to_csv(index=False).encode("utf-8"), "reviews")


def test_validate_product_references_rejects_unknown_product_id():
    products = pd.DataFrame({"product_id": ["P001"]})
    orders = pd.DataFrame({"product_id": ["P999"]})
    with pytest.raises(ProductImportError, match="不存在的 product_id"):
        validate_product_references(products, orders, "orders")
