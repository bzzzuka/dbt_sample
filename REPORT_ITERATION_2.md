# REPORT_ITERATION_2.md — вторая итерация

**Дата:** 2026-11-08  
**Статус:** в работе (диагностика Задачи 1 завершена)

---

## Задача 1. Airflow: вход admin/admin

### 1.1. Диагностика (до правок)

На старте итерации контейнеры проекта отсутствовали (`docker compose ps` пуст),
хотя образы и volumes сохранились. Стек был поднят командой `docker compose up -d`
без удаления volumes.

Фактическое состояние после подъёма:

| Проверка | Результат |
|---|---|
| `docker compose ps` | `airflow_webserver` — Up (healthy), scheduler/worker/triggerer — Up, worker healthy |
| `curl http://localhost:8080/health` | `200`, scheduler/metastore/triggerer healthy |
| `GET http://localhost:8080/login/` | `200`, форма логина отдаётся, cookie `session` ставится |
| `POST /login/` без CSRF | `400 BAD REQUEST`, тело: `The CSRF token is missing.` — ожидаемое поведение CSRF |
| `POST /login/` с валидным CSRF-токеном | **`500 INTERNAL SERVER ERROR`** |
| `airflow users list` | пользователь `admin` существует, роль `Admin`, email `airflowadmin@example.com` |
| `airflow db check` | `Connection successful` |
| `airflow config get-value core fernet_key` | `8mX2rT9pLqK5vB1wYhN7jF3dC6sA0eU4xZbGqRkMnPc=` (валидный, из `.env`) |
| `airflow config get-value webserver secret_key` | `8IESbYgG39cEa9tHBMAGYQ==` — **сгенерирован Airflow**, не значение из `.env` |
| `airflow config get-value webserver base_url` | `http://localhost:8080` — корректно |
| Werkzeug в контейнере | `2.2.3` |

### 1.2. Traceback (фактическая причина 500)

Из `docker compose logs airflow-webserver`:

```
File "/home/airflow/.local/lib/python3.11/site-packages/airflow/providers/fab/auth_manager/security_manager/override.py", line 2217, in auth_user_db
    elif check_password_hash(user.password, password):
File "/home/airflow/.local/lib/python3.11/site-packages/werkzeug/security.py", line 107, in check_password_hash
    return hmac.compare_digest(_hash_internal(method, salt, password)[0], hashval)
...
ValueError: unsupported hash type scrypt:32768:8:1
```

Проверка хеша в БД:

```sql
SELECT username, substr(password,1,30) AS password_prefix, active FROM ab_user;
-- admin | scrypt:32768:8:1$iBt20wzo9eO9B | t
```

**Диагноз:** пароль `admin` был сохранён в формате `scrypt` (Werkzeug 3.x),
а текущий образ Airflow 2.10.5 использует Werkzeug 2.2.3, который не умеет
проверять `scrypt`. Поэтому любой корректный POST логина падает с 500.
`Bad Request` без CSRF-токена — отдельное ожидаемое поведение, не причина
основной ошибки.

### 1.3. Дополнительная проблема

`AIRFLOW__WEBSERVER__SECRET_KEY` задан в `.env`, но **не передаётся в контейнеры
Airflow** в `docker-compose.yml` (нет `env_file` и нет соответствующей переменной
в `environment`). Airflow генерирует ключ сам и пишет его в `/opt/airflow/airflow.cfg`.
При пересоздании контейнера ключ меняется → все сессии/CSRF-токены инвалидируются.
Это не причина текущего 500, но причина нестабильного поведения и «непонятных
ошибок» после рестартов.

### 1.4. План правок Задачи 1

1. Сбросить пароль `admin` командой
   `airflow users reset-password --username admin --password admin`,
   чтобы хеш был создан текущим Werkzeug 2.2.3.
2. Прокинуть `AIRFLOW__WEBSERVER__SECRET_KEY=${AIRFLOW__WEBSERVER__SECRET_KEY}`
   во все Airflow-сервисы (`airflow-init`, webserver, scheduler, worker, triggerer).
3. Убрать дубли `AIRFLOW_FERNET_KEY` / `AIRFLOW__WEBSERVER__SECRET_KEY` из `.env`.
4. Пересоздать Airflow-контейнеры (без `docker compose down`, без удаления volumes).
5. Проверить:
   - `airflow users list`;
   - логин с CSRF-токеном через `curl` → ожидаем 200/302, не 400/500;
   - вход в UI и доступ к `/home`;
   - `airflow dags list` без import errors.
6. CSRF **не отключать**.

---

## Задача 2. Retail / e-commerce данные

_Диагностика и реализация — после завершения Задачи 1._

---

## Задача 3. Superset dashboards

_Диагностика и реализация — после завершения Задач 1–2._

---

## Сервисы и доступы

_Будет заполнено на финальном состоянии проекта._
