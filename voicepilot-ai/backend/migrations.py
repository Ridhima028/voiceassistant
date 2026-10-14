"""
Minimal additive schema migration run at startup.

SQLAlchemy's `Base.metadata.create_all()` creates tables that don't exist,
but it will NOT add new columns to a table that already exists. Since this
project gained several columns after the `lectures` table was first created
(duration_seconds, flashcards, key_concepts, mindmap, chapters, ...), a
existing database would silently be missing them and every query would fail.

This walks the model definitions and issues `ALTER TABLE ... ADD COLUMN` for
anything missing. It's additive only — it never drops or alters existing
columns, so it cannot destroy data.

For a production project this would be Alembic. For a project at this stage,
this keeps `docker compose up` working without a migration workflow.
"""

import logging

from sqlalchemy import inspect, text

from database import Base, engine

logger = logging.getLogger(__name__)


def run_additive_migrations() -> None:
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue  # create_all() will handle brand-new tables

            existing_cols = {c["name"] for c in inspector.get_columns(table.name)}

            for column in table.columns:
                if column.name in existing_cols:
                    continue

                col_type = column.type.compile(dialect=engine.dialect)

                # New columns must be nullable — an existing row has no value
                # to put in a NOT NULL column.
                ddl = f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {col_type}'

                try:
                    conn.execute(text(ddl))
                    logger.info("Migration: added %s.%s", table.name, column.name)
                except Exception as e:
                    logger.warning(
                        "Migration: could not add %s.%s — %s", table.name, column.name, e
                    )
