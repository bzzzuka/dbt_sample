"""
Идемпотентно создаёт дашборды Superset:
  - Supply Chain Overview
  - Retail Overview

Запуск внутри сети Docker Compose:
    SUPERSET_URL=http://superset:8088 python /app/init/create_all_dashboards.py
"""

import json
import os
import sys

import requests

BASE_URL = os.getenv("SUPERSET_URL", "http://localhost:8088").rstrip("/")
USERNAME = os.getenv("SUPERSET_USERNAME", "admin")
PASSWORD = os.getenv("SUPERSET_PASSWORD", "admin")
DATABASE_NAME = "StarRocks Analytics"
SCHEMA = "analytics"


def login():
    session = requests.Session()
    r = session.post(
        f"{BASE_URL}/api/v1/security/login",
        json={"username": USERNAME, "password": PASSWORD,
              "provider": "db", "refresh": True},
        timeout=30,
    )
    r.raise_for_status()
    session.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})

    r = session.get(f"{BASE_URL}/api/v1/security/csrf_token/", timeout=30)
    r.raise_for_status()
    session.headers.update({
        "X-CSRFToken": r.json()["result"],
        "Referer": BASE_URL,
        "Content-Type": "application/json",
    })
    return session


def api_get(session, path):
    r = session.get(f"{BASE_URL}{path}", timeout=30)
    r.raise_for_status()
    return r.json()


def api_post(session, path, payload):
    r = session.post(f"{BASE_URL}{path}", json=payload, timeout=60)
    if not r.ok:
        raise RuntimeError(f"POST {path}: {r.status_code} {r.text[:500]}")
    return r.json()


def api_put(session, path, payload):
    r = session.put(f"{BASE_URL}{path}", json=payload, timeout=60)
    if not r.ok:
        raise RuntimeError(f"PUT {path}: {r.status_code} {r.text[:500]}")
    return r.json()


def get_database_id(session):
    result = api_get(session, "/api/v1/database/")["result"]
    for db in result:
        if db["database_name"] == DATABASE_NAME:
            return db["id"]
    raise RuntimeError(f"База {DATABASE_NAME} не найдена")


def find_or_create_dataset(session, db_id, table_name):
    result = api_get(session, "/api/v1/dataset/")["result"]
    for ds in result:
        if ds.get("table_name") == table_name and ds.get("schema") == SCHEMA:
            print(f"  = dataset {table_name} (id={ds['id']})")
            return ds["id"]

    payload = {"database": db_id, "schema": SCHEMA, "table_name": table_name}
    data = api_post(session, "/api/v1/dataset/", payload)
    ds_id = data.get("id") or data.get("result", {}).get("id")
    print(f"  + dataset {table_name} (id={ds_id})")
    return ds_id


def simple_metric(column, aggregate, label=None):
    return {
        "expressionType": "SIMPLE",
        "column": {"column_name": column},
        "aggregate": aggregate,
        "label": label or f"{aggregate}({column})",
        "hasCustomLabel": bool(label),
    }


def chart_specs(db_id):
    ds = f"{db_id}__table"
    return [
        # ---------------- Supply Chain ----------------
        {
            "name": "SC: Total Purchase Amount",
            "dataset": "mart_supplier_performance",
            "viz_type": "big_number_total",
            "params": {
                "datasource": ds, "viz_type": "big_number_total",
                "metric": simple_metric("total_purchase_amount", "SUM", "Total purchase"),
                "subheader": "Supply chain revenue", "time_range": "No filter",
            },
        },
        {
            "name": "SC: Total Orders",
            "dataset": "mart_supplier_performance",
            "viz_type": "big_number_total",
            "params": {
                "datasource": ds, "viz_type": "big_number_total",
                "metric": simple_metric("orders_count", "SUM", "Total orders"),
                "subheader": "Supply chain orders", "time_range": "No filter",
            },
        },
        {
            "name": "SC: Top-10 Suppliers by Turnover",
            "dataset": "mart_supplier_performance",
            "viz_type": "echarts_timeseries_bar",
            "params": {
                "datasource": ds, "viz_type": "echarts_timeseries_bar",
                "granularity_sqla": None, "time_range": "No filter",
                "x_axis": "supplier_name",
                "metrics": [simple_metric("total_purchase_amount", "SUM", "Turnover")],
                "row_limit": 10, "order_desc": True, "orientation": "horizontal",
            },
        },
        {
            "name": "SC: Revenue by Category",
            "dataset": "mart_supply_by_category",
            "viz_type": "pie",
            "params": {
                "datasource": ds, "viz_type": "pie",
                "granularity_sqla": None, "time_range": "No filter",
                "groupby": ["category"],
                "metric": simple_metric("total_revenue", "SUM", "Revenue"),
                "row_limit": 20, "donut": True,
            },
        },
        {
            "name": "SC: Payments vs Invoices by Month",
            "dataset": "mart_payment_summary",
            "viz_type": "echarts_timeseries_line",
            "params": {
                "datasource": ds, "viz_type": "echarts_timeseries_line",
                "granularity_sqla": None, "time_range": "No filter",
                "x_axis": "month",
                "metrics": [
                    simple_metric("invoices_total", "SUM", "Invoices"),
                    simple_metric("payments_total", "SUM", "Payments"),
                ],
                "row_limit": 100,
            },
        },
        {
            "name": "SC: Delivery KPI",
            "dataset": "mart_delivery_kpi",
            "viz_type": "table",
            "params": {
                "datasource": ds, "viz_type": "table",
                "granularity_sqla": None, "time_range": "No filter",
                "query_mode": "raw",
                "all_columns": [
                    "transport_mode", "container_type", "priority",
                    "shipments_count", "avg_delivery_days",
                    "total_shipping_cost", "delivered_count", "returned_count",
                ],
                "row_limit": 50,
            },
        },
        {
            "name": "SC: Top-10 Warehouses by Movements",
            "dataset": "mart_warehouse_activity",
            "viz_type": "echarts_timeseries_bar",
            "params": {
                "datasource": ds, "viz_type": "echarts_timeseries_bar",
                "granularity_sqla": None, "time_range": "No filter",
                "x_axis": "warehouse_name",
                "metrics": [simple_metric("movements_count", "SUM", "Movements")],
                "row_limit": 10, "order_desc": True,
            },
        },
        {
            "name": "SC: Delivery Cost by Transport Mode",
            "dataset": "mart_transport_analysis",
            "viz_type": "echarts_timeseries_bar",
            "params": {
                "datasource": ds, "viz_type": "echarts_timeseries_bar",
                "granularity_sqla": None, "time_range": "No filter",
                "x_axis": "transport_mode",
                "metrics": [simple_metric("cost_per_km", "AVG", "Cost per km")],
                "row_limit": 20,
            },
        },
        # ---------------- Retail ----------------
        {
            "name": "RT: Total Revenue",
            "dataset": "mart_retail__sales_by_month",
            "viz_type": "big_number_total",
            "params": {
                "datasource": ds, "viz_type": "big_number_total",
                "metric": simple_metric("net_revenue", "SUM", "Revenue"),
                "subheader": "Retail revenue", "time_range": "No filter",
            },
        },
        {
            "name": "RT: Total Orders",
            "dataset": "mart_retail__sales_by_month",
            "viz_type": "big_number_total",
            "params": {
                "datasource": ds, "viz_type": "big_number_total",
                "metric": simple_metric("orders_count", "SUM", "Orders"),
                "subheader": "Retail orders", "time_range": "No filter",
            },
        },
        {
            "name": "RT: Avg Order Value",
            "dataset": "mart_retail__customer_ltv",
            "viz_type": "big_number_total",
            "params": {
                "datasource": ds, "viz_type": "big_number_total",
                "metric": simple_metric("avg_order_value", "AVG", "AOV"),
                "subheader": "Average order value", "time_range": "No filter",
            },
        },
        {
            "name": "RT: Revenue by Month",
            "dataset": "mart_retail__sales_by_month",
            "viz_type": "echarts_timeseries_line",
            "params": {
                "datasource": ds, "viz_type": "echarts_timeseries_line",
                "granularity_sqla": None, "time_range": "No filter",
                "x_axis": "month",
                "metrics": [
                    simple_metric("net_revenue", "SUM", "Net revenue"),
                    simple_metric("gross_revenue", "SUM", "Gross revenue"),
                ],
                "row_limit": 100,
            },
        },
        {
            "name": "RT: Top Products by Revenue",
            "dataset": "mart_retail__top_products",
            "viz_type": "echarts_timeseries_bar",
            "params": {
                "datasource": ds, "viz_type": "echarts_timeseries_bar",
                "granularity_sqla": None, "time_range": "No filter",
                "x_axis": "product_name",
                "metrics": [simple_metric("revenue", "SUM", "Revenue")],
                "row_limit": 10, "order_desc": True, "orientation": "horizontal",
            },
        },
        {
            "name": "RT: Revenue by Category",
            "dataset": "mart_retail__sales_by_category",
            "viz_type": "pie",
            "params": {
                "datasource": ds, "viz_type": "pie",
                "granularity_sqla": None, "time_range": "No filter",
                "groupby": ["category_name"],
                "metric": simple_metric("revenue", "SUM", "Revenue"),
                "row_limit": 20, "donut": True,
            },
        },
        {
            "name": "RT: Top Customers by LTV",
            "dataset": "mart_retail__customer_ltv",
            "viz_type": "table",
            "params": {
                "datasource": ds, "viz_type": "table",
                "granularity_sqla": None, "time_range": "No filter",
                "query_mode": "raw",
                "all_columns": [
                    "customer_name", "segment", "loyalty_tier",
                    "orders_count", "total_spent", "avg_order_value",
                ],
                "row_limit": 20,
            },
        },
        {
            "name": "RT: Returns Rate by Month",
            "dataset": "mart_retail__returns_rate",
            "viz_type": "echarts_timeseries_line",
            "params": {
                "datasource": ds, "viz_type": "echarts_timeseries_line",
                "granularity_sqla": None, "time_range": "No filter",
                "x_axis": "month",
                "metrics": [simple_metric("return_rate_pct", "AVG", "Return rate %")],
                "row_limit": 100,
            },
        },
    ]


def find_or_create_chart(session, spec, db_id, dataset_ids):
    dataset_id = dataset_ids[spec["dataset"]]
    existing = api_get(session, "/api/v1/chart/")["result"]
    by_name = {c["slice_name"]: c for c in existing}

    payload = {
        "slice_name": spec["name"],
        "datasource_id": dataset_id,
        "datasource_type": "table",
        "viz_type": spec["viz_type"],
        "params": json.dumps(spec["params"], ensure_ascii=False),
    }

    if spec["name"] in by_name:
        chart_id = by_name[spec["name"]]["id"]
        api_put(session, f"/api/v1/chart/{chart_id}", payload)
        print(f"  = chart {spec['name']} (id={chart_id})")
        return chart_id

    data = api_post(session, "/api/v1/chart/", payload)
    chart_id = data.get("id") or data.get("result", {}).get("id")
    print(f"  + chart {spec['name']} (id={chart_id})")
    return chart_id


def attach_chart(session, chart_id, dashboard_id):
    try:
        chart = api_get(session, f"/api/v1/chart/{chart_id}")["result"]
        current = chart.get("dashboards") or []
        if current and isinstance(current[0], dict):
            current_ids = [d.get("id") for d in current]
        else:
            current_ids = list(current)
        if dashboard_id in current_ids:
            return
        payload = {"dashboards": current_ids + [dashboard_id]}
        try:
            api_put(session, f"/api/v1/chart/{chart_id}", payload)
        except RuntimeError:
            api_post(session, f"/api/v1/chart/{chart_id}", payload)
    except Exception as exc:
        print(f"    ⚠ не удалось привязать chart {chart_id}: {exc}")


def build_position(charts, title):
    position = {
        "DASHBOARD_VERSION_KEY": "v2",
        "ROOT_ID": {"type": "ROOT", "id": "ROOT_ID", "children": ["GRID_ID"], "parents": []},
        "GRID_ID": {"type": "GRID", "id": "GRID_ID", "children": [], "parents": ["ROOT_ID"]},
        "HEADER_ID": {"type": "HEADER", "id": "HEADER_ID", "meta": {"text": title}},
    }
    for row_idx, start in enumerate(range(0, len(charts), 2), start=1):
        row_id = f"ROW-{row_idx}"
        row_children = []
        for chart in charts[start:start + 2]:
            chart_key = f"CHART-{chart['id']}"
            row_children.append(chart_key)
            position[chart_key] = {
                "type": "CHART",
                "id": chart_key,
                "children": [],
                "parents": ["ROOT_ID", "GRID_ID", row_id],
                "meta": {"chartId": chart["id"], "width": 6, "height": 50,
                         "sliceName": chart["name"]},
            }
        position[row_id] = {
            "type": "ROW",
            "id": row_id,
            "children": row_children,
            "parents": ["ROOT_ID", "GRID_ID"],
            "meta": {"background": "BACKGROUND_TRANSPARENT"},
        }
        position["GRID_ID"]["children"].append(row_id)
    return json.dumps(position, ensure_ascii=False)


def dashboard_metadata():
    return json.dumps({
        "chart_configuration": {},
        "global_chart_configuration": {
            "scope": {"rootPath": ["ROOT_ID"], "excluded": []},
            "globalChartConfigList": [],
        },
        "timed_refresh_immune_slices": [],
        "expanded_slices": {},
        "refresh_frequency": 0,
        "default_filters": "{}",
        "color_scheme": "supersetColors",
        "label_colors": {},
        "shared_label_colors": {},
        "native_filter_configuration": [],
        "cross_filters_enabled": False,
    }, ensure_ascii=False)


def find_or_create_dashboard(session, title):
    existing = api_get(session, "/api/v1/dashboard/")["result"]
    by_title = {d["dashboard_title"]: d for d in existing}
    if title in by_title:
        dash_id = by_title[title]["id"]
        print(f"  = dashboard {title} (id={dash_id})")
        return dash_id
    data = api_post(session, "/api/v1/dashboard/", {"dashboard_title": title, "published": True})
    dash_id = data.get("id") or data.get("result", {}).get("id")
    print(f"  + dashboard {title} (id={dash_id})")
    return dash_id


def update_dashboard(session, dash_id, title, charts):
    payload = {
        "dashboard_title": title,
        "published": True,
        "position_json": build_position(charts, title),
        "json_metadata": dashboard_metadata(),
    }
    api_put(session, f"/api/v1/dashboard/{dash_id}", payload)


def verify_superset_sql(session, db_id, tables):
    print("\nПроверка SQL Lab (Superset -> StarRocks):")
    for table in tables:
        sql = f"SELECT COUNT(*) AS cnt FROM {SCHEMA}.{table}"
        payload = {
            "database_id": db_id,
            "sql": sql,
            "schema": SCHEMA,
            "runAsync": False,
            "json": True,
        }
        try:
            r = session.post(f"{BASE_URL}/api/v1/sqllab/execute/", json=payload, timeout=60)
            if not r.ok:
                print(f"  ⚠ {table}: HTTP {r.status_code} {r.text[:200]}")
                continue
            data = r.json()
            print(f"  ✓ {table}: {json.dumps(data, ensure_ascii=False)[:300]}")
        except Exception as exc:
            print(f"  ⚠ {table}: {exc}")


def main():
    print("=" * 60)
    print("  Superset dashboards: Supply Chain + Retail")
    print("=" * 60)

    session = login()
    db_id = get_database_id(session)
    print(f"  ✓ database id={db_id}\n")

    specs = chart_specs(db_id)
    dataset_tables = sorted({s["dataset"] for s in specs})
    dataset_ids = {}
    print("Datasets:")
    for table in dataset_tables:
        dataset_ids[table] = find_or_create_dataset(session, db_id, table)
    print()

    for spec in specs:
        spec["params"]["datasource"] = f"{dataset_ids[spec['dataset']]}__table"

    dashboards = [
        ("Supply Chain Overview", [s for s in specs if s["name"].startswith("SC:")]),
        ("Retail Overview", [s for s in specs if s["name"].startswith("RT:")]),
    ]

    all_charts = []
    for title, charts in dashboards:
        print(f"Dashboard: {title}")
        dash_id = find_or_create_dashboard(session, title)
        chart_refs = []
        for spec in charts:
            chart_id = find_or_create_chart(session, spec, db_id, dataset_ids)
            attach_chart(session, chart_id, dash_id)
            chart_refs.append({"id": chart_id, "name": spec["name"]})
        update_dashboard(session, dash_id, title, chart_refs)
        print(f"  ✓ {title}: {len(chart_refs)} чартов\n")
        all_charts.append((title, chart_refs, dash_id))

    verify_superset_sql(session, db_id, [
        "mart_supplier_performance",
        "mart_retail__sales_by_month",
        "mart_retail__top_products",
        "mart_retail__customer_ltv",
        "mart_retail__returns_rate",
        "mart_retail__sales_by_category",
    ])

    print("\n✅ Готово.")
    for title, charts, dash_id in all_charts:
        print(f"  {title}: dashboard_id={dash_id}, charts={len(charts)}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\n❌ Ошибка: {exc}", file=sys.stderr)
        sys.exit(1)
