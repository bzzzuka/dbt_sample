# Superset (Trino)

Подключение: `trino://trino@trino:8080/iceberg/analytics`
(имя `Trino Iceberg`).

Requirements: `trino[sqlalchemy]==0.340.0`.

`superset-init` создаёт connection, `superset-dashboards` — 11 datasets,
16 charts, 2 dashboards.

UI: http://localhost:8088, admin/admin.

StarRocks-драйвер удалён.
