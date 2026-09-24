"""DuckDB query layer for repeatable dashboard aggregations.

The MVP keeps data in memory. DataFrames are registered as temporary DuckDB
relations for each query, so the SQL layer does not introduce persistence or a
second source of truth for the scoring formula.
"""

from __future__ import annotations

import duckdb
import pandas as pd


KPI_COLUMNS = ["product_count", "avg_margin", "avg_return", "recommended", "order_count"]
CARRIER_COLUMNS = ["carrier", "delay_rate", "refund_rate", "avg_ship_days", "order_count"]
REVIEW_COLUMNS = ["theme", "review_count", "negative_rate"]
PRODUCT_PERFORMANCE_COLUMNS = ["product_id", "order_count", "revenue", "delay_rate", "refund_rate", "review_count", "negative_rate"]


def _empty_result(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def query_kpis(products: pd.DataFrame, orders: pd.DataFrame) -> dict[str, float | int]:
    """Return the dashboard KPI aggregate through DuckDB SQL."""
    if products.empty:
        order_count = int(orders["order_id"].nunique()) if "order_id" in orders else 0
        return {
            "product_count": 0,
            "avg_margin": 0.0,
            "avg_return": 0.0,
            "recommended": 0,
            "order_count": order_count,
        }

    with duckdb.connect(database=":memory:") as connection:
        connection.register("products_df", products)
        connection.register("orders_df", orders)
        row = connection.execute(
            """
            SELECT
              COUNT(DISTINCT product_id)::BIGINT AS product_count,
              COALESCE(AVG(margin_rate), 0)::DOUBLE AS avg_margin,
              COALESCE(AVG(return_rate), 0)::DOUBLE AS avg_return,
              SUM(CASE WHEN recommendation = '推荐' THEN 1 ELSE 0 END)::BIGINT AS recommended
            FROM products_df
            """
        ).fetchone()
        order_count = connection.execute(
            "SELECT COUNT(DISTINCT order_id)::BIGINT FROM orders_df"
        ).fetchone()[0]

    return {
        "product_count": int(row[0]),
        "avg_margin": float(row[1]),
        "avg_return": float(row[2]),
        "recommended": int(row[3]),
        "order_count": int(order_count),
    }


def query_carrier_summary(orders: pd.DataFrame) -> pd.DataFrame:
    """Aggregate delivery performance by carrier through DuckDB SQL."""
    if orders.empty:
        return _empty_result(CARRIER_COLUMNS)

    with duckdb.connect(database=":memory:") as connection:
        connection.register("orders_df", orders)
        result = connection.execute(
            """
            SELECT
              carrier,
              AVG(CASE WHEN delayed THEN 1.0 ELSE 0.0 END)::DOUBLE AS delay_rate,
              AVG(CASE WHEN refunded THEN 1.0 ELSE 0.0 END)::DOUBLE AS refund_rate,
              AVG(ship_days)::DOUBLE AS avg_ship_days,
              COUNT(DISTINCT order_id)::BIGINT AS order_count
            FROM orders_df
            GROUP BY carrier
            ORDER BY delay_rate DESC
            """
        ).fetchdf()
    return result.loc[:, CARRIER_COLUMNS]


def query_review_summary(reviews: pd.DataFrame) -> pd.DataFrame:
    """Aggregate review themes and negative sentiment through DuckDB SQL."""
    if reviews.empty:
        return _empty_result(REVIEW_COLUMNS)

    with duckdb.connect(database=":memory:") as connection:
        connection.register("reviews_df", reviews)
        result = connection.execute(
            """
            SELECT
              theme,
              COUNT(DISTINCT review_id)::BIGINT AS review_count,
              AVG(CASE WHEN sentiment = '负向' THEN 1.0 ELSE 0.0 END)::DOUBLE AS negative_rate
            FROM reviews_df
            GROUP BY theme
            ORDER BY review_count DESC
            """
        ).fetchdf()
    return result.loc[:, REVIEW_COLUMNS]


def query_product_performance(orders: pd.DataFrame, reviews: pd.DataFrame) -> pd.DataFrame:
    """Join order and review signals into one product-level performance table."""
    if orders.empty and reviews.empty:
        return _empty_result(PRODUCT_PERFORMANCE_COLUMNS)

    order_frame = orders if not orders.empty else pd.DataFrame(columns=["product_id", "order_id", "revenue", "delayed", "refunded"])
    review_frame = reviews if not reviews.empty else pd.DataFrame(columns=["product_id", "review_id", "sentiment"])
    with duckdb.connect(database=":memory:") as connection:
        connection.register("orders_df", order_frame)
        connection.register("reviews_df", review_frame)
        result = connection.execute(
            """
            WITH order_metrics AS (
              SELECT product_id,
                     COUNT(DISTINCT order_id)::BIGINT AS order_count,
                     COALESCE(SUM(revenue), 0)::DOUBLE AS revenue,
                     AVG(CASE WHEN delayed THEN 1.0 ELSE 0.0 END)::DOUBLE AS delay_rate,
                     AVG(CASE WHEN refunded THEN 1.0 ELSE 0.0 END)::DOUBLE AS refund_rate
              FROM orders_df
              GROUP BY product_id
            ), review_metrics AS (
              SELECT product_id,
                     COUNT(DISTINCT review_id)::BIGINT AS review_count,
                     AVG(CASE WHEN sentiment = '负向' THEN 1.0 ELSE 0.0 END)::DOUBLE AS negative_rate
              FROM reviews_df
              GROUP BY product_id
            ), ids AS (
              SELECT product_id FROM order_metrics
              UNION
              SELECT product_id FROM review_metrics
            )
            SELECT ids.product_id,
                   COALESCE(order_metrics.order_count, 0)::BIGINT AS order_count,
                   COALESCE(order_metrics.revenue, 0)::DOUBLE AS revenue,
                   COALESCE(order_metrics.delay_rate, 0)::DOUBLE AS delay_rate,
                   COALESCE(order_metrics.refund_rate, 0)::DOUBLE AS refund_rate,
                   COALESCE(review_metrics.review_count, 0)::BIGINT AS review_count,
                   COALESCE(review_metrics.negative_rate, 0)::DOUBLE AS negative_rate
            FROM ids
            LEFT JOIN order_metrics USING (product_id)
            LEFT JOIN review_metrics USING (product_id)
            ORDER BY order_count DESC, review_count DESC
            """
        ).fetchdf()
    return result.loc[:, PRODUCT_PERFORMANCE_COLUMNS]
