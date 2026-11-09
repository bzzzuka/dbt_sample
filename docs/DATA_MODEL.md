# Модель данных

**Актуально на:** 2026-11-09

Справочник по таблицам, связям и витринам. Используйте его, когда нужно
понять, откуда берётся колонка или куда добавить новую.

---

## 1. Слои и имена

| Слой | Префикс | Где | Материализация |
|---|---|---|---|
| Raw supply chain | `raw_` | StarRocks `analytics` | table |
| Raw retail | `raw_retail_` | StarRocks `analytics` | table |
| Staging supply chain | `stg_` | StarRocks `analytics` | view |
| Staging retail | `stg_retail__` | StarRocks `analytics` | view |
| Marts supply chain | `mart_` | StarRocks `analytics` | table |
| Marts retail | `mart_retail__` | StarRocks `analytics` | table |
| Iceberg | `lakehouse.` | MinIO | Iceberg |

---

## 2. Supply chain: таблицы и связи

Источник: `dbt/scripts/generate_and_upload.py`, список `TABLES`.

```
suppliers
  ├── supply_contracts (supplier_id)
  ├── supply_orders (supplier_id, supply_contract_id)
  │     ├── supply_items (supply_order_id)
  │     │     ├── quality_checks (supply_item_id)
  │     │     └── returns (supply_item_id)
  │     ├── shipments (supply_order_id)
  │     │     ├── deliveries (shipment_id, warehouse_id)
  │     │     └── customs_declarations (shipment_id)
  │     └── invoices (supply_order_id)
  │           └── payments (invoice_id)
  ├── supplier_ratings (supplier_id)
  └── warehouses
        ├── deliveries (warehouse_id)
        └── inventory_movements (warehouse_id)

transport_routes — справочник маршрутов
```

### 2.1. Ключевые таблицы

| Таблица | Ключевые поля | Смысл |
|---|---|---|
| `suppliers` | supplier_id, supplier_name, country, city, rating | Поставщики |
| `supply_contracts` | contract_id, supplier_id, contract_number, total_price | Контракты |
| `supply_orders` | supply_order_id, supplier_id, order_date, total_price, status | Заказы |
| `supply_items` | supply_item_id, supply_order_id, product_name, quantity, unit_price | Позиции заказов |
| `shipments` | shipment_id, supply_order_id, transport_mode, shipping_cost | Отгрузки |
| `warehouses` | warehouse_id, warehouse_name, city, capacity_m3 | Склады |
| `deliveries` | delivery_id, shipment_id, warehouse_id, status | Доставки |
| `invoices` | invoice_id, supply_order_id, total_price, payment_status | Инвойсы |
| `payments` | payment_id, invoice_id, total_price, payment_status | Платежи |
| `quality_checks` | check_id, supply_item_id, quality_grade, quality_passed | Проверки качества |
| `returns` | return_id, supply_item_id, quantity, status | Возвраты |
| `inventory_movements` | movement_id, warehouse_id, direction, quantity | Движения склада |
| `transport_routes` | route_code, city_from, city_to, distance_km | Маршруты |
| `customs_declarations` | declaration_id, shipment_id, customs_duty | Таможня |
| `supplier_ratings` | rating_id, supplier_id, rating, quality_grade | Оценки |

> Полный набор колонок динамический: `generate_and_upload.py` добавляет
> колонки из `COLUMN_POOL` до `COLUMNS_PER_TABLE`. Поэтому «120 колонок» —
> это верхняя граница, а не фиксированная схема. Для точного списка смотрите
> `/tmp/_schema.json` после `data-init`.

---

## 3. Retail: таблицы и связи

Источник: `dbt/scripts/generate_retail.py`, словарь `SCHEMAS`.

```
categories
  └── products (category_id)
        ├── order_items (product_id)
        └── reviews (product_id)

customers
  ├── orders (customer_id)
  └── reviews (customer_id)

stores
  └── orders (store_id)

promotions
  └── orders (promotion_id, 0 = без промо)

orders
  ├── order_items (order_id)
  ├── payments (order_id)
  ├── shipments (order_id)
  ├── returns (order_id)
  └── reviews (order_id)
```

### 3.1. Ключевые поля

| Таблица | Ключевые поля |
|---|---|
| `categories` | category_id, category_name, department, is_active |
| `products` | product_id, product_name, category_id, brand, unit_price, cost, launch_date |
| `customers` | customer_id, first_name, last_name, email, city, country, signup_date, segment, loyalty_tier |
| `stores` | store_id, store_name, city, country, store_type, opened_date |
| `promotions` | promotion_id, promotion_name, promo_type, discount_pct, start_date, end_date, channel |
| `orders` | order_id, customer_id, store_id, promotion_id, order_date, status, channel, currency, subtotal, discount_amount, shipping_cost, tax_amount, total_amount |
| `order_items` | order_item_id, order_id, product_id, quantity, unit_price, discount_pct, line_total |
| `payments` | payment_id, order_id, payment_date, payment_method, amount, status, transaction_ref |
| `shipments` | shipment_id, order_id, carrier, shipping_method, shipped_date, promised_date, delivered_date, status |
| `returns` | return_id, order_id, return_date, reason, status, refund_amount |
| `reviews` | review_id, product_id, customer_id, order_id, rating, review_date, review_text, helpful_votes |

### 3.2. Бизнес-правила генерации

- `orders.promotion_id = 0` означает «без промоции»;
- `order_items.line_total = unit_price * quantity * (1 - discount_pct/100)`;
- `orders.subtotal` — сумма до скидки;
- `orders.discount_amount` — сумма скидок;
- `orders.tax_amount` — 8% от net;
- `orders.total_amount = net + shipping + tax`;
- `payments.status` зависит от `orders.status`;
- `shipments` создаются только для `completed/delivered/shipped`;
- `returns` — около 8% доставленных заказов.

---

## 4. Marts supply chain

| Модель | Grain | Основные метрики |
|---|---|---|
| `mart_supplier_performance` | supplier_id | orders_count, total_purchase_amount, avg_order_amount, contracts_count, avg_quality_rating |
| `mart_supply_by_category` | category | orders_count, items_count, total_quantity, total_revenue, avg_unit_price |
| `mart_delivery_kpi` | transport_mode + container_type + priority | shipments_count, avg_delivery_days, total_shipping_cost, delivered/returned_count |
| `mart_warehouse_activity` | warehouse_id | movements_count, total_quantity_moved, inbound/outbound, deliveries_count |
| `mart_payment_summary` | month + currency | invoices_total, payments_total, payment_ratio_pct |
| `mart_transport_analysis` | transport_mode | routes_count, total_distance_km, shipments_count, total_shipping_cost, cost_per_km |

---

## 5. Marts retail

| Модель | Grain | Основные метрики |
|---|---|---|
| `mart_retail__sales_by_month` | month | orders_count, items_count, units_sold, gross_revenue, discount_amount, net_revenue, avg_order_value |
| `mart_retail__top_products` | product_id | orders_count, units_sold, revenue, avg_unit_price |
| `mart_retail__customer_ltv` | customer_id | orders_count, total_spent, avg_order_value, first/last_order_date |
| `mart_retail__returns_rate` | month | orders_count, returns_count, refund_amount, return_rate_pct |
| `mart_retail__sales_by_category` | category_id | orders_count, units_sold, revenue, revenue_share_pct |

---

## 6. MOEX (опционально)

| Модель | Grain | Смысл |
|---|---|---|
| `stg_moex_prices` | ticker + tradedate | Цены MOEX |
| `mart_moex_daily_returns` | ticker + tradedate | Дневные доходности |

MOEX не входит в основной DAG. В чистом окружении `raw_moex_prices` пустая,
и витрина будет пустой, но dbt не упадёт.

---

## 7. Iceberg

| Объект | Где | Смысл |
|---|---|---|
| `lakehouse.supply_chain.suppliers` | MinIO `warehouse/` | Iceberg-копия suppliers |
| `iceberg_lakehouse.supply_chain.suppliers` | StarRocks external catalog | Чтение Iceberg |

Обратите внимание: Iceberg-таблица — **отдельная копия**, а не та же
таблица, что `analytics.raw_suppliers`. Spark перезаписывает её из CSV.

---

## 8. Lineage

```
generate_and_upload.py
  -> s3://dbt-bucket/stg/{table}/...
  -> load_s3_to_starrocks.py
  -> analytics.raw_{table}
  -> dbt stg_{table}
  -> dbt mart_*

generate_retail.py
  -> s3://dbt-bucket/retail/stg/{table}/...
  -> load_retail_to_starrocks.py
  -> analytics.raw_retail_{table}
  -> dbt stg_retail__{table}
  -> dbt mart_retail__*

etl_supply_chain.py
  -> s3a://dbt-bucket/stg/suppliers/...
  -> lakehouse.supply_chain.suppliers
  -> StarRocks iceberg_lakehouse
```

---

## 9. Где смотреть точную схему

- Supply chain: `/tmp/_schema.json` после `data-init` (в контейнере).
- Retail: `/tmp/_retail_schema.json` после `data-init`.
- StarRocks:

```sql
USE analytics;
DESC raw_suppliers;
DESC raw_retail_orders;
DESC mart_retail__sales_by_month;
```

- dbt:

```powershell
docker compose run --rm --no-deps --entrypoint dbt dbt `
  --profiles-dir /dbt/profiles ls
```

---

## 10. Связанные документы

- [`modules/04-data-generation.md`](modules/04-data-generation.md)
- [`modules/03-dbt.md`](modules/03-dbt.md)
- [`modules/05-starrocks.md`](modules/05-starrocks.md)
- [`modules/06-spark-iceberg.md`](modules/06-spark-iceberg.md)
