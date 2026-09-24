from __future__ import annotations

from io import BytesIO

import pandas as pd


REQUIRED_PRODUCT_COLUMNS = (
    "product_id",
    "product_name",
    "category",
    "platform",
    "country",
    "keyword_demand",
    "content_score",
    "avg_price",
    "cost_price",
    "commission_rate",
    "logistics_cost",
    "ad_cost",
    "return_rate",
    "delay_rate",
    "supplier_stability",
    "competition_index",
    "sales_count",
    "rating",
)

NUMERIC_PRODUCT_COLUMNS = (
    "keyword_demand",
    "content_score",
    "avg_price",
    "cost_price",
    "commission_rate",
    "logistics_cost",
    "ad_cost",
    "return_rate",
    "delay_rate",
    "supplier_stability",
    "competition_index",
    "sales_count",
    "rating",
)


REQUIRED_ORDER_COLUMNS = ("order_id", "product_id", "order_date", "country", "carrier", "revenue", "ship_days", "delayed", "refunded")
REQUIRED_CONTENT_COLUMNS = ("product_id", "capture_date", "platform", "impressions", "likes", "saves", "comments", "engagement_rate")
REQUIRED_REVIEW_COLUMNS = ("review_id", "product_id", "review_date", "theme", "sentiment", "text")

DATASET_COLUMNS = {
    "products": REQUIRED_PRODUCT_COLUMNS,
    "orders": REQUIRED_ORDER_COLUMNS,
    "content": REQUIRED_CONTENT_COLUMNS,
    "reviews": REQUIRED_REVIEW_COLUMNS,
}


class ProductImportError(ValueError):
    """A user-correctable product CSV validation error."""


def _require_columns(frame: pd.DataFrame, columns: tuple[str, ...], dataset_name: str) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ProductImportError(f"{dataset_name} 缺少必填字段：{', '.join(missing)}")


def _normalize_text(frame: pd.DataFrame, columns: tuple[str, ...], dataset_name: str) -> pd.DataFrame:
    normalized = frame.copy()
    for column in columns:
        normalized[column] = normalized[column].astype("string").str.strip()
        if normalized[column].isna().any() or normalized[column].eq("").any():
            raise ProductImportError(f"{dataset_name} 字段 {column} 不能为空")
    return normalized


def _parse_boolean_column(values: pd.Series, column: str, dataset_name: str) -> pd.Series:
    mapping = {"true": True, "false": False, "1": True, "0": False, "yes": True, "no": False, "是": True, "否": False}
    normalized = values.astype("string").str.strip().str.lower().map(mapping)
    if normalized.isna().any():
        raise ProductImportError(f"{dataset_name} 字段 {column} 必须是 true/false、1/0 或 是/否")
    return normalized.astype(bool)


def validate_product_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Validate and normalize a product catalog for the scoring pipeline."""
    missing = [column for column in REQUIRED_PRODUCT_COLUMNS if column not in frame.columns]
    if missing:
        raise ProductImportError(f"缺少必填字段：{', '.join(missing)}")

    normalized = frame.loc[:, list(REQUIRED_PRODUCT_COLUMNS)].copy()
    if normalized.empty:
        raise ProductImportError("CSV 中没有商品记录")
    if normalized["product_id"].isna().any() or normalized["product_id"].astype(str).str.strip().eq("").any():
        raise ProductImportError("product_id 不能为空")
    if normalized["product_id"].duplicated().any():
        raise ProductImportError("product_id 必须唯一")

    for column in NUMERIC_PRODUCT_COLUMNS:
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        if normalized[column].isna().any():
            raise ProductImportError(f"字段 {column} 包含无法识别的数字")

    bounded_fields = {
        "keyword_demand": (0, 1),
        "content_score": (0, 1),
        "commission_rate": (0, 1),
        "return_rate": (0, 1),
        "delay_rate": (0, 1),
        "supplier_stability": (0, 1),
        "competition_index": (0, 1),
        "rating": (0, 5),
    }
    for column, (minimum, maximum) in bounded_fields.items():
        if not normalized[column].between(minimum, maximum).all():
            raise ProductImportError(f"字段 {column} 必须在 {minimum} 到 {maximum} 之间")
    for column in ("avg_price", "cost_price", "logistics_cost", "ad_cost", "sales_count"):
        if (normalized[column] < 0).any():
            raise ProductImportError(f"字段 {column} 不能为负数")

    normalized["product_id"] = normalized["product_id"].astype(str).str.strip()
    normalized["product_name"] = normalized["product_name"].astype(str).str.strip()
    if normalized["product_name"].eq("").any():
        raise ProductImportError("product_name 不能为空")
    return normalized


def parse_product_csv(raw_bytes: bytes) -> pd.DataFrame:
    """Parse UTF-8/UTF-8-BOM CSV bytes and validate the product catalog."""
    if not raw_bytes:
        raise ProductImportError("上传文件为空")
    try:
        frame = pd.read_csv(BytesIO(raw_bytes), encoding="utf-8-sig")
    except (UnicodeDecodeError, pd.errors.ParserError) as exc:
        raise ProductImportError("无法读取 CSV，请保存为 UTF-8 编码并检查逗号分隔格式") from exc
    return validate_product_frame(frame)


def _parse_csv_frame(raw_bytes: bytes) -> pd.DataFrame:
    if not raw_bytes:
        raise ProductImportError("上传文件为空")
    try:
        return pd.read_csv(BytesIO(raw_bytes), encoding="utf-8-sig")
    except (UnicodeDecodeError, pd.errors.ParserError) as exc:
        raise ProductImportError("无法读取 CSV，请保存为 UTF-8 编码并检查逗号分隔格式") from exc


def _validate_orders(frame: pd.DataFrame) -> pd.DataFrame:
    _require_columns(frame, REQUIRED_ORDER_COLUMNS, "订单 CSV")
    normalized = _normalize_text(frame.loc[:, list(REQUIRED_ORDER_COLUMNS)], ("order_id", "product_id", "country", "carrier"), "订单 CSV")
    if normalized["order_id"].duplicated().any():
        raise ProductImportError("订单 CSV 的 order_id 必须唯一")
    normalized["order_date"] = pd.to_datetime(normalized["order_date"], errors="coerce")
    if normalized["order_date"].isna().any():
        raise ProductImportError("订单 CSV 的 order_date 包含无法识别的日期")
    for column in ("revenue", "ship_days"):
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        if normalized[column].isna().any():
            raise ProductImportError(f"订单 CSV 字段 {column} 包含无法识别的数字")
        if (normalized[column] < 0).any():
            raise ProductImportError(f"订单 CSV 字段 {column} 不能为负数")
    normalized["delayed"] = _parse_boolean_column(normalized["delayed"], "delayed", "订单 CSV")
    normalized["refunded"] = _parse_boolean_column(normalized["refunded"], "refunded", "订单 CSV")
    return normalized


def _validate_content(frame: pd.DataFrame) -> pd.DataFrame:
    _require_columns(frame, REQUIRED_CONTENT_COLUMNS, "内容 CSV")
    normalized = _normalize_text(frame.loc[:, list(REQUIRED_CONTENT_COLUMNS)], ("product_id", "platform"), "内容 CSV")
    normalized["capture_date"] = pd.to_datetime(normalized["capture_date"], errors="coerce")
    if normalized["capture_date"].isna().any():
        raise ProductImportError("内容 CSV 的 capture_date 包含无法识别的日期")
    for column in ("impressions", "likes", "saves", "comments", "engagement_rate"):
        normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        if normalized[column].isna().any():
            raise ProductImportError(f"内容 CSV 字段 {column} 包含无法识别的数字")
        if (normalized[column] < 0).any():
            raise ProductImportError(f"内容 CSV 字段 {column} 不能为负数")
    if not normalized["engagement_rate"].between(0, 1).all():
        raise ProductImportError("内容 CSV 字段 engagement_rate 必须在 0 到 1 之间")
    return normalized


def _validate_reviews(frame: pd.DataFrame) -> pd.DataFrame:
    _require_columns(frame, REQUIRED_REVIEW_COLUMNS, "评论 CSV")
    normalized = _normalize_text(frame.loc[:, list(REQUIRED_REVIEW_COLUMNS)], ("review_id", "product_id", "theme", "sentiment", "text"), "评论 CSV")
    if normalized["review_id"].duplicated().any():
        raise ProductImportError("评论 CSV 的 review_id 必须唯一")
    normalized["review_date"] = pd.to_datetime(normalized["review_date"], errors="coerce")
    if normalized["review_date"].isna().any():
        raise ProductImportError("评论 CSV 的 review_date 包含无法识别的日期")
    if not normalized["sentiment"].isin(["正向", "负向"]).all():
        raise ProductImportError("评论 CSV 的 sentiment 只能是 正向 或 负向")
    return normalized


def parse_dataset_csv(raw_bytes: bytes, dataset: str) -> pd.DataFrame:
    """Parse and validate one of the four supported dashboard datasets."""
    if dataset == "products":
        return parse_product_csv(raw_bytes)
    frame = _parse_csv_frame(raw_bytes)
    validators = {"orders": _validate_orders, "content": _validate_content, "reviews": _validate_reviews}
    if dataset not in validators:
        raise ProductImportError(f"不支持的数据类型：{dataset}")
    result = validators[dataset](frame)
    if result.empty:
        raise ProductImportError("CSV 中没有数据记录")
    return result


def validate_product_references(products: pd.DataFrame, frame: pd.DataFrame, dataset: str) -> None:
    """Ensure supporting datasets only reference known product IDs."""
    if frame.empty or products.empty:
        return
    known_ids = set(products["product_id"].astype(str))
    referenced_ids = set(frame["product_id"].astype(str))
    unknown = sorted(referenced_ids - known_ids)
    if unknown:
        preview = ", ".join(unknown[:5])
        suffix = " 等" if len(unknown) > 5 else ""
        label = {"orders": "订单", "content": "内容", "reviews": "评论"}.get(dataset, dataset)
        raise ProductImportError(f"{label} CSV 引用了不存在的 product_id：{preview}{suffix}")
