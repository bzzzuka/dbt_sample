# dbt-trino

Образ: `python:3.11-slim` + `dbt-core==1.6.2` + `dbt-trino==1.6.2`.

Профиль: `dbt/profiles/profiles.yml`, host `trino`, port `8080`,
catalog `iceberg`, schema `analytics`.

```powershell
docker compose run --rm --no-deps --entrypoint dbt dbt run `
  --profiles-dir /dbt/profiles --project-dir /dbt/project

docker compose run --rm --no-deps --entrypoint dbt dbt test `
  --profiles-dir /dbt/profiles --project-dir /dbt/project
```

Результат: **PASS=37**, тесты **PASS=19**.

StarRocks-адаптер и загрузчики удалены.
