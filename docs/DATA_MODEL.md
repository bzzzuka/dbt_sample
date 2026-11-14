# Модель данных (Trino + Iceberg)

**Актуально на:** 2026-11-13

Все таблицы живут в Iceberg, доступ — через Trino catalog `iceberg`,
schema `analytics`. StarRocks удалён.

---

## 1. Слои

| Слой | Имя | Где | Материализация |
|---|---|---|---|
| Raw supply | `raw_{table}` | Iceberg | Spark write |
| Raw retail | `raw_retail_{table}` | Iceberg | Spark write |
| Staging | `stg_*`, `stg_retail__*` | Trino | view |
| Marts | `mart_*`, `mart_retail__*` | Iceberg | dbt table |

---

## 2. Raw supply chain (15)

```
suppliers
supply_contracts
supply_orders
supply_items
shipments
warehouses
deliveries
invoices
payments
quality_checks
returns
inventory_movements
transport_routes
customs_declarations
supplier_ratings
```

Связи:

```
suppliers
  ├── supply_contracts
  ├── supply_orders
  │     ├── supply_items
  │     └── invoices
  ├── supplier_ratings
  └── warehouses
shipments -> deliveries, customs_declarations
transport_routes — справочник маршрутов
```

---

## 3. Raw retail (11)

```
categories
products
customers
stores
promotions
orders
order_items
payments
shipments
returns
reviews
```

Связи:

- `products.category_id → categories`
- `orders.customer_id → customers`, `orders.store_id → stores`,
  `orders.promotion_id → promotions`
- `order_items.order_id → orders`, `order_items.product_id → products`
- `payments.order_id → orders`
- `shipments.order_id → orders`
- `returns.order_id → orders`
- `reviews.product_id/customer_id/order_id`

---

## 4. Staging (26)

15 supply `stg_*` + 11 retail `stg_retail__*` — views в Trino.

Не редактируйте 15 supply `stg_*.sql` вручную: их перегенерирует
`generate_and_upload.py` при `data-init`.

---

## 5. Marts (11)

### Supply chain

| Mart | Grain | Метрики |
|---|---|---|
| `mart_supplier_performance` | supplier_id | orders, purchase amount, rating |
| `mart_supply_by_category` | category | orders, quantity, revenue |
| `mart_delivery_kpi` | transport_mode + container_type + priority | delivery days, cost, statuses |
| `mart_warehouse_activity` | warehouse_id | inbound/outbound, movements |
| `mart_payment_summary` | month + currency | invoices, payments |
| `mart_transport_analysis` | transport_mode | routes, distance, cost per km |

### Retail

| Mart | Grain | Метрики |
|---|---|---|
| `mart_retail__sales_by_month` | month | orders, revenue, AOV |
| `mart_retail__top_products` | product_id | units, revenue |
| `mart_retail__customer_ltv` | customer_id | orders, total spent, AOV |
| `mart_retail__returns_rate` | month | returns count, rate |
| `mart_retail__sales_by_category` | category_id | units, revenue, share |

---

## 6. Проверка структуры

```sql
SHOW TABLES FROM iceberg.analytics;

DESCRIBE iceberg.analytics.mart_supplier_performance;
DESCRIBE iceberg.analytics.mart_retail__sales_by_month;
DESCRIBE iceberg.analytics.raw_retail_orders;
```

Примеры:

```sql
SELECT month, orders_count, net_revenue
FROM iceberg.analytics.mart_retail__sales_by_month
ORDER BY month;

SELECT supplier_id, total_purchase_amount
FROM iceberg.analytics.mart_supplier_performance
ORDER BY total_purchase_amount DESC
LIMIT 10;
```

---

## 7. Iceberg

Физически данные — Parquet в `s3://dbt-bucket/warehouse/`.
Metadata — в Iceberg REST catalog (`iceberg_catalog_data`).

---

## 8. Связанные документы

- [`modules/03-dbt.md`](modules/03-dbt.md)
- [`modules/05-trino.md`](modules/05-trino.md)
- [`modules/06-spark-iceberg.md`](modules/06-spark-iceberg.md)
