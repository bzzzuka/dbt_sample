"""
Создаёт дашборд 'Supply Chain Overview' в Superset через REST API.

Запуск из хоста:
    docker cp superset/init/create_dashboard.py superset_app:/tmp/
    docker exec -it superset_app python /tmp/create_dashboard.py
"""

import json
import sys

import requests

SUPERSET_URL = "http://localhost:8088"
USERNAME = "admin"
PASSWORD = "admin"
DATABASE_NAME = "StarRocks Analytics"
SCHEMA = "analytics"


def login():
    s = requests.Session()
    r = s.post(
        f"{SUPERSET_URL}/api/v1/security/login",
        json={"username": USERNAME, "password": PASSWORD,
              "provider": "db", "refresh": True},
    )
    r.raise_for_status()
    s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})

    r = s.get(f"{SUPERSET_URL}/api/v1/security/csrf_token/")
    r.raise_for_status()
    s.headers.update({
        "X-CSRFToken": r.json()["result"],
        "Referer": SUPERSET_URL,
        "Content-Type": "application/json",
    })
    return s


def get_database_id(s):
    r = s.get(f"{SUPERSET_URL}/api/v1/database/")
    r.raise_for_status()
    for db in r.json()["result"]:
        if db["database_name"] == DATABASE_NAME:
            return db["id"]
    raise RuntimeError(f"БД {DATABASE_NAME} не найдена")


def get_or_create_dataset(s, db_id, table_name):
    # проверка существует ли
    q = f"(filters:!((col:table_name,opr:eq,value:'{table_name}')))"
    r = s.get(f"{SUPERSET_URL}/api/v1/dataset/?q={q}")
    r.raise_for_status()
    items = r.json()["result"]
    if items:
        print(f"  ✓ dataset {table_name} уже есть (id={items[0]['id']})")
        return items[0]["id"]

    payload = {"database": db_id, "schema": SCHEMA, "table_name": table_name}
    r = s.post(f"{SUPERSET_URL}/api/v1/dataset/", json=payload)
    if not r.ok:
        print(f"  ❌ dataset {table_name}: {r.status_code} {r.text[:200]}")
        r.raise_for_status()
    ds_id = r.json()["id"]
    print(f"  + dataset {table_name} создан (id={ds_id})")
    return ds_id


def simple_metric(column, aggregate, label=None):
    return {
        "expressionType": "SIMPLE",
        "column": {"column_name": column},
        "aggregate": aggregate,
        "label": label or f"{aggregate}({column})",
        "hasCustomLabel": bool(label),
    }


def create_chart(s, name, dataset_id, viz_type, params):
    payload = {
        "slice_name": name,
        "datasource_id": dataset_id,
        "datasource_type": "table",
        "viz_type": viz_type,
        "params": json.dumps(params, ensure_ascii=False),
    }
    r = s.post(f"{SUPERSET_URL}/api/v1/chart/", json=payload)
    if not r.ok:
        print(f"  ❌ chart '{name}': {r.status_code} {r.text[:200]}")
        return None
    chart_id = r.json()["id"]
    print(f"  + chart '{name}' создан (id={chart_id})")
    return chart_id


def create_dashboard(s, name, chart_ids):
    payload = {"dashboard_title": name, "published": True}
    r = s.post(f"{SUPERSET_URL}/api/v1/dashboard/", json=payload)
    if not r.ok:
        print(f"  ❌ dashboard: {r.status_code} {r.text[:200]}")
        r.raise_for_status()
    dash_id = r.json()["id"]
    print(f"  + dashboard '{name}' создан (id={dash_id})")

    # привязываем графики к дашборду
    for cid in chart_ids:
        if cid is None:
            continue
        r = s.post(f"{SUPERSET_URL}/api/v1/chart/{cid}", json={"dashboards": [dash_id]})
        if not r.ok:
            print(f"    ⚠ не привязан chart {cid}: {r.text[:100]}")

    return dash_id


def main():
    print("Авторизация в Superset...")
    s = login()

    print("Поиск базы StarRocks...")
    db_id = get_database_id(s)
    print(f"  ✓ database id={db_id}")

    print("\nСоздание датасетов...")
    datasets = {}
    for table in [
        "mart_supplier_performance",
        "mart_supply_by_category",
        "mart_delivery_kpi",
        "mart_warehouse_activity",
        "mart_payment_summary",
        "mart_transport_analysis",
    ]:
        datasets[table] = get_or_create_dataset(s, db_id, table)

    print("\nСоздание графиков...")
    charts = []

    # 1. Top-10 поставщиков по обороту
    charts.append(create_chart(
        s, "Top-10 поставщиков по обороту",
        datasets["mart_supplier_performance"], "echarts_timeseries_bar",
        {
            "datasource": f"{db_id}__table",
            "viz_type": "echarts_timeseries_bar",
            "granularity_sqla": None,
            "time_range": "No filter",
            "x_axis": "supplier_name",
            "metrics": [simple_metric("total_purchase_amount", "SUM", "Оборот")],
            "row_limit": 10,
            "order_desc": True,
            "orientation": "horizontal",
        },
    ))

    # 2. Оборот по категориям (pie)
    charts.append(create_chart(
        s, "Оборот по категориям",
        datasets["mart_supply_by_category"], "pie",
        {
            "datasource": f"{db_id}__table",
            "viz_type": "pie",
            "granularity_sqla": None,
            "time_range": "No filter",
            "groupby": ["category"],
            "metric": simple_metric("total_revenue", "SUM", "Оборот"),
            "row_limit": 20,
            "donut": True,
        },
    ))

    # 3. Динамика платежей по месяцам (line)
    charts.append(create_chart(
        s, "Динамика платежей по месяцам",
        datasets["mart_payment_summary"], "echarts_timeseries_line",
        {
            "datasource": f"{db_id}__table",
            "viz_type": "echarts_timeseries_line",
            "granularity_sqla": None,
            "time_range": "No filter",
            "x_axis": "month",
            "metrics": [
                simple_metric("invoices_total", "SUM", "Счета"),
                simple_metric("payments_total", "SUM", "Платежи"),
            ],
            "row_limit": 100,
        },
    ))

    # 4. KPI доставок (table)
    charts.append(create_chart(
        s, "KPI доставок",
        datasets["mart_delivery_kpi"], "table",
        {
            "datasource": f"{db_id}__table",
            "viz_type": "table",
            "granularity_sqla": None,
            "time_range": "No filter",
            "query_mode": "raw",
            "all_columns": [
                "transport_mode", "container_type", "priority",
                "shipments_count", "avg_delivery_days",
                "total_shipping_cost", "delivered_count", "returned_count",
            ],
            "row_limit": 50,
        },
    ))

    # 5. Топ-10 складов по движениям
    charts.append(create_chart(
        s, "Топ-10 складов по движениям",
        datasets["mart_warehouse_activity"], "echarts_timeseries_bar",
        {
            "datasource": f"{db_id}__table",
            "viz_type": "echarts_timeseries_bar",
            "granularity_sqla": None,
            "time_range": "No filter",
            "x_axis": "warehouse_name",
            "metrics": [simple_metric("movements_count", "SUM", "Движений")],
            "row_limit": 10,
            "order_desc": True,
        },
    ))

    # 6. Стоимость доставки по видам транспорта
    charts.append(create_chart(
        s, "Стоимость доставки по видам транспорта",
        datasets["mart_transport_analysis"], "echarts_timeseries_bar",
        {
            "datasource": f"{db_id}__table",
            "viz_type": "echarts_timeseries_bar",
            "granularity_sqla": None,
            "time_range": "No filter",
            "x_axis": "transport_mode",
            "metrics": [simple_metric("cost_per_km", "AVG", "Стоимость за км")],
            "row_limit": 20,
        },
    ))

    print("\nСоздание дашборда...")
    dash_id = create_dashboard(s, "Supply Chain Overview", charts)

    print(f"\n✅ Готово! Дашборд доступен:")
    print(f"   {SUPERSET_URL}/superset/dashboard/{dash_id}/")


if __name__ == "__main__":
    main()