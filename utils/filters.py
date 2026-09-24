from __future__ import annotations

from datetime import date

import pandas as pd


GLOBAL_FILTER_KEYS = (
    "global_platforms",
    "global_categories",
    "global_countries",
    "global_date_range",
)


def normalize_date_range(value: object, fallback: tuple[date, date]) -> tuple[date, date]:
    """Normalize Streamlit date_input output to an inclusive two-date tuple."""
    if isinstance(value, (tuple, list)) and len(value) == 2:
        start, end = value
    elif isinstance(value, date):
        start = end = value
    else:
        return fallback
    if start > end:
        start, end = end, start
    return start, end


def date_bounds(frame: pd.DataFrame, column: str) -> tuple[date, date]:
    """Return inclusive date bounds for a datetime column."""
    if frame.empty or column not in frame.columns:
        today = date.today()
        return today, today
    values = pd.to_datetime(frame[column], errors="coerce").dropna()
    if values.empty:
        today = date.today()
        return today, today
    return values.min().date(), values.max().date()


def filter_by_date(frame: pd.DataFrame, column: str, start: date, end: date) -> pd.DataFrame:
    """Apply an inclusive date range without mutating the input frame."""
    if frame.empty or column not in frame.columns:
        return frame.copy()
    values = pd.to_datetime(frame[column], errors="coerce")
    mask = values.dt.date.between(start, end)
    return frame.loc[mask].copy()


def combined_date_bounds(frames: list[tuple[pd.DataFrame, str]]) -> tuple[date, date]:
    """Return the inclusive union of date bounds across several datasets."""
    bounds = [date_bounds(frame, column) for frame, column in frames if column in frame.columns and not frame.empty]
    if not bounds:
        return date.today(), date.today()
    return min(start for start, _ in bounds), max(end for _, end in bounds)


def filter_products(products: pd.DataFrame, platforms: list[str], categories: list[str], countries: list[str]) -> pd.DataFrame:
    """Filter the product catalog using the shared dashboard dimensions."""
    if products.empty:
        return products.copy()
    mask = pd.Series(True, index=products.index)
    if platforms:
        mask &= products["platform"].isin(platforms)
    else:
        mask &= False
    if categories:
        mask &= products["category"].isin(categories)
    else:
        mask &= False
    if countries:
        mask &= products["country"].isin(countries)
    else:
        mask &= False
    return products.loc[mask].copy()


def filter_related_datasets(
    products: pd.DataFrame,
    orders: pd.DataFrame,
    content: pd.DataFrame,
    reviews: pd.DataFrame,
    date_range: tuple[date, date],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Apply product scope and each table's native date column consistently."""
    start, end = date_range
    product_ids = set(products.get("product_id", pd.Series(dtype=str)).astype(str))

    def scope(frame: pd.DataFrame, date_column: str) -> pd.DataFrame:
        result = filter_by_date(frame, date_column, start, end)
        if "product_id" in result.columns:
            result = result[result["product_id"].astype(str).isin(product_ids)].copy()
        return result

    return products.copy(), scope(orders, "order_date"), scope(content, "capture_date"), scope(reviews, "review_date")
