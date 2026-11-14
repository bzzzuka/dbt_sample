"""Создаёт подключение к Trino в метаданных Superset."""

import os
import sys

sys.path.append("/app")

from superset import create_app
from superset import db

app = create_app()

with app.app_context():
    from superset.models.core import Database

    host = os.getenv("TRINO_HOST", "trino")
    port = os.getenv("TRINO_PORT", "8080")
    user = os.getenv("TRINO_USER", "trino")
    catalog = os.getenv("TRINO_CATALOG", "iceberg")
    schema = os.getenv("TRINO_SCHEMA", "analytics")

    uri = f"trino://{user}@{host}:{port}/{catalog}/{schema}"

    existing = db.session.query(Database).filter_by(database_name="Trino Iceberg").first()
    if existing:
        print(f"Подключение уже существует: {existing.database_name}")
    else:
        new_db = Database(
            database_name="Trino Iceberg",
            sqlalchemy_uri=uri,
            expose_in_sqllab=True,
            allow_run_async=True,
        )
        db.session.add(new_db)
        db.session.commit()
        print(f"Создано подключение: {uri}")
