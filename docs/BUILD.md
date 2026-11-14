# BUILD — сборка на Windows, Linux и macOS (Trino)

**Актуально на:** 2026-11-13

---

## 1. Требования

| Требование | Минимум |
|---|---|
| Docker Desktop (Win/Mac) или Docker Engine + Compose plugin (Linux) | 4.30+ |
| Docker Compose | v2 |
| ОЗУ для Docker | 8 ГБ (лучше 16 ГБ) |
| Диск | 40+ ГБ |
| Интернет | первая сборка и Maven-зависимости Spark |

Порты: 8081 (Trino), 8080 (Airflow), 8088 (Superset), 9000/9001 (MinIO),
8181 (Iceberg REST), 4040 (Spark UI).

---

## 2. Запуск

Windows:

```powershell
docker compose config
docker compose up -d --build
docker compose ps -a
```

> Первый запуск — **20–30 минут**: `data-init` (100k supply + 200k retail),
> затем `spark-etl` (Iceberg) и dbt.

Linux/macOS:

```bash
chmod +x scripts/linux/*.sh
./scripts/linux/start-all.sh
```

---

## 3. Trino и Iceberg

Добавлены:

- `trino` — `trinodb/trino:484`, порт **8081 → 8080**;
- `trino/etc/catalog/iceberg.properties` — Iceberg REST + MinIO/S3;
- volume `iceberg_catalog_data:/tmp` у `iceberg-rest` — metadata не
  теряются при пересоздании;
- `spark-etl` — one-shot CSV → Iceberg;
- dbt-trino 1.6.2 в dbt- и Airflow-образах.

`trinodb/trino:484` имеет `linux/amd64` и `linux/arm64` — работает на
Windows, Linux и Apple Silicon без Rosetta.

StarRocks удалён: нет портов 8030/9030/8040, нет `dbt-starrocks`.

---

## 4. Проверка

```bash
docker compose ps -a
curl -fsS http://localhost:8081/v1/info
docker exec trino trino --execute "SHOW TABLES FROM iceberg.analytics"
docker compose logs dbt --tail 50
docker compose logs spark-etl --tail 50
```

Ожидаемо:

- Trino `ACTIVE`, 37 dbt-моделей, 19 тестов;
- Trino видит 26 raw-таблиц, 26 staging views, 11 marts;
- `dbt` — `PASS=37`, `PASS=19`.

---

## 5. DBeaver

```text
Driver:   Trino
Host:     localhost
Port:     8081
User:     trino
Password: (пусто)
Catalog:  iceberg
Schema:   analytics
JDBC:     jdbc:trino://localhost:8081/iceberg/analytics
```

---

## 6. Скрытые условия

- **Интернет:** Docker Hub, PyPI, Maven для Spark.
- **Память:** Trino JVM 2 ГБ, Spark 4 ГБ, Superset/Airflow — 8+ ГБ всего.
- **Iceberg REST fixture:** metadata в `/tmp`; в проекте том
  `iceberg_catalog_data`; для production — JDBC/Nessie.
- **Airflow + Spark:** в Airflow-образ ставится `pyspark` + Java 17;
  Spark запускается в `local[2]`.
- **CRLF:** `.sh` только LF.
- **Порт 8081:** Trino, потому что 8080 занят Airflow.

---

## 7. Troubleshooting

| Симптом | Решение |
|---|---|
| Trino пуст | `docker compose run --rm --no-deps spark-etl` |
| Trino unhealthy | `docker compose logs trino` |
| dbt dialect error | заменить StarRocks-функции на Trino |
| Airflow Spark task failed | пересобрать Airflow образ с `pyspark`/Java |
| Superset connection error | пересобрать Superset с `trino[sqlalchemy]` |
| Порт занят | освободить 8080/8081/8088 |

---

## 8. Связанные документы

- [`RUNBOOK.md`](RUNBOOK.md)
- [`ARCHITECTURE.md`](ARCHITECTURE.md)
- [`modules/05-trino.md`](modules/05-trino.md)
