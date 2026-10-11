"""
Создаёт подключение к StarRocks в метаданных Superset.
"""

import os
import sys

sys.path.append("/app")

from superset import create_app
from superset import db

app = create_app()

with app.app_context():
    # Импорт модели ДОЛЖЕН быть внутри app_context,
    # иначе Flask падает с "Working outside of application context"
    from superset.models.core import Database

    host = os.getenv("STARROCKS_HOST", "starrocks")
    port = os.getenv("STARROCKS_PORT", "9030")
    user = os.getenv("STARROCKS_USER", "root")
    password = os.getenv("STARROCKS_PASSWORD", "")
    catalog = os.getenv("STARROCKS_CATALOG", "default_catalog")
    schema = os.getenv("STARROCKS_SCHEMA", "analytics")

    uri = f"starrocks://{user}:{password}@{host}:{port}/{catalog}.{schema}?charset=utf8"

    existing = db.session.query(Database).filter_by(database_name="StarRocks Analytics").first()
    if existing:
        print(f"Подключение уже существует: {existing.database_name}")
    else:
        new_db = Database(
            database_name="StarRocks Analytics",
            sqlalchemy_uri=uri,
            expose_in_sqllab=True,
            allow_run_async=True,
        )
        db.session.add(new_db)
        db.session.commit()
        print(f"Создано подключение: {uri}")