# ROADMAP — новые цели проекта

**Актуально на:** 2026-11-09

Этот файл — про **что развивать**. Как именно реализовывать — в
[`DEVELOPMENT_GUIDE.md`](DEVELOPMENT_GUIDE.md).

---

## 1. Текущая базовая линия

Уже работает:

- supply chain: 15 таблиц, ~120 колонок, 5000 строк;
- retail: 11 таблиц, 5000 заказов;
- dbt: 39 моделей, 19 тестов;
- Airflow DAG: 6 задач;
- Spark ETL → Iceberg `suppliers`;
- StarRocks external catalog `iceberg_lakehouse`;
- Superset: 2 дашборда, 16 чартов;
- Redis results backend для Superset;
- full stack в Docker Compose.

---

## 2. Как выбрать новую цель

Хорошая цель:

- имеет понятную бизнес-ценность;
- не ломает существующие слои;
- проверяема (есть SQL/API/UI-критерий);
- укладывается в локальные ресурсы (RAM/диск);
- может быть выполнена аддитивно.

Плохая цель:

- «переписать всё на другой стек» без причины;
- «добавить миллион строк» без проверки памяти;
- «сразу production» без тестов и мониторинга;
- изменение версий dbt/StarRocks без плана отката.

---

## 3. Приоритетный backlog

### P0 — укрепить текущее

| Цель | Зачем | Критерий готовности |
|---|---|---|
| `spark_etl_dag` | автоматизировать Spark | DAG виден, запускает ETL, task success |
| Incremental ETL | не перезаписывать всё | `MERGE INTO`/append, повторный запуск идемпотентен |
| Больше dbt-тестов | качество данных | tests для retail/supply key-полей |
| Persist Iceberg REST metadata | не терять каталог | volume/внешний Postgres для REST |
| Secrets в env/connections | безопасность | нет паролей в DAG, `.env.example` |

### P1 — расширить аналитику

| Цель | Зачем | Критерий готовности |
|---|---|---|
| Новое направление (finance/marketing) | показать масштабируемость | генератор + loader + stg + mart + dashboard |
| Iceberg для всех 15 supply-chain таблиц | полный lakehouse | таблицы в `lakehouse.supply_chain`, проверка Spark |
| dbt поверх Iceberg | единый источник | source на `iceberg_lakehouse`, модели собираются |
| Superset: больше чартов | глубина анализа | 6+ чартов на новый дашборд, данные не пустые |
| Data quality dashboard | контроль | таблица/график с тестами/аномалиями |

### P2 — эксплуатация

| Цель | Зачем | Критерий готовности |
|---|---|---|
| Prometheus + Grafana | мониторинг | метрики контейнеров/БД |
| Алерты Airflow → Telegram/Slack | реакция на падения | on_failure_callback |
| CI/CD GitHub Actions | качество | lint + dbt + compose config на PR |
| Terraform | IaC | воспроизводимая инфраструктура |
| Backup/restore | сохранность | скрипт backup MinIO/StarRocks/Postgres |

---

## 4. Шаблон новой цели

Скопируйте в issue/PR:

```markdown
## Цель
<одно предложение>

## Бизнес-ценность
<зачем это нужно>

## Данные
- источник:
- таблицы:
- объём:
- seed:

## Слои
- S3 prefix:
- raw:
- staging:
- marts:
- BI:

## Изменения
- [ ] генератор
- [ ] загрузчик
- [ ] dbt source
- [ ] staging models
- [ ] marts
- [ ] tests
- [ ] Airflow task/DAG
- [ ] Superset dataset/chart/dashboard
- [ ] docs

## Критерии готовности
- [ ] dbt run PASS
- [ ] dbt test PASS
- [ ] Airflow DAG success
- [ ] SQL COUNT > 0
- [ ] dashboard открывается
- [ ] нет регрессий supply chain
```

---

## 5. Definition of Done для новой фичи

- [ ] Изменения аддитивны, старые модели не сломаны.
- [ ] Есть seed и воспроизводимая генерация.
- [ ] Есть FK/согласованность данных.
- [ ] Есть dbt-модели и тесты.
- [ ] Есть проверка `COUNT(*)`/SQL.
- [ ] DAG (если нужно) импортируется и проходит run.
- [ ] Дашборд (если нужно) открывается и отдаёт данные.
- [ ] Обновлены `docs/` (архитектура, модуль, runbook).
- [ ] `git status` не содержит логов/`target`/`__pycache__`.

---

## 6. Идеи для учебных задач

1. Добавить таблицу `marketing_campaigns` и витрину ROI.
2. Построить `mart_retail__cohort_retention`.
3. Добавить `mart_supply_chain__late_delivery_rate`.
4. Сделать Iceberg-партиционирование по месяцу.
5. Реализовать `MERGE INTO` для suppliers.
6. Добавить dbt source на Iceberg.
7. Сделать Superset-дашборд `Data Quality`.
8. Настроить алерт при падении DAG.
9. Добавить GitHub Actions: `docker compose config` + dbt compile.
10. Сделать backup/restore скрипт.

---

## 7. Чего избегать

- Не запускайте `setup_starrocks.py` и `make_dag.py` — они перезапишут
  актуальную архитектуру.
- Не коммитьте логи, `target`, `__pycache__`.
- Не храните реальные секреты в git.
- Не обновляйте dbt-starrocks/StarRocks без тестового прогона.
- Не добавляйте миллионы строк без проверки RAM и времени.

---

## 8. Связанные документы

- [`DEVELOPMENT_GUIDE.md`](DEVELOPMENT_GUIDE.md) — как реализовывать.
- [`ARCHITECTURE.md`](ARCHITECTURE.md) — как всё связано.
- [`RUNBOOK.md`](RUNBOOK.md) — как проверять.
