---
title: T-006 DuckDB 查询层
aliases:
  - DuckDB 查询层
tags:
  - 项目
  - 任务
  - DuckDB
status: 已验收
---

# T-006 DuckDB 查询层

## 任务目标

在不引入独立数据库服务和持久化迁移的前提下，把看板中的核心聚合改为 SQL 查询，并证明 SQL 结果与原有 pandas 基线一致。

## 范围

- 使用 DuckDB `:memory:` 连接，不写入本地数据库文件。
- 通过 `register()` 注册当前会话中的商品、订单和评论 DataFrame。
- 提供 KPI、承运商履约、评论主题三个查询接口。
- 商品综合评分继续使用 `enrich_products()`，评分权重保持透明。
- 上传 CSV 仍只替换商品目录，订单、内容和评论仍为演示数据。

## 接口与 SQL 口径

| 接口 | SQL 聚合 | 页面使用 |
| --- | --- | --- |
| `query_kpis(products, orders)` | 商品数、平均毛利率、平均退款率、推荐数、订单数 | 总览、商品雷达 |
| `query_carrier_summary(orders)` | 承运商延误率、退款率、平均运输天数、订单数 | 履约分析 |
| `query_review_summary(reviews)` | 评论主题数、负向率 | 评论洞察 |

布尔字段按 `True=1、False=0` 计算平均值；数量字段使用去重后的业务 ID。空 DataFrame 返回零值或带固定字段的空表，避免页面因无筛选结果崩溃。

## 验收记录

- 实现：`utils/duckdb_store.py`
- 页面接入：`app_pages/overview.py`、`app_pages/product_radar.py`、`app_pages/fulfillment.py`、`app_pages/insights.py`
- 对照测试：`tests/test_duckdb_store.py`
- 命令：`python -m pytest -q`
- 结果：13 passed

## 面试讲解

商品目录通过 CSV 进入系统后，先用 pandas 做字段校验和商品评分，再将 DataFrame 注册到 DuckDB 内存关系中。总览、履约和评论页面的核心聚合由 SQL 返回；测试同时调用 pandas 基线比较结果，保证换查询引擎后指标口径没有变化。当前数据规模和部署形态不需要持久化数据库，因此保留 `:memory:` 设计。
