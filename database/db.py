import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Database:
    def __init__(self, db_path: Path):
        self._path = db_path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self._path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def initialize_schema(self):
        schema_path = Path(__file__).parent / "schema.sql"
        schema = schema_path.read_text(encoding="utf-8")
        with self.transaction() as conn:
            conn.executescript(schema)
        self._migrate(schema_path)

    def _migrate(self, schema_path: Path):
        """Apply additive column migrations for existing databases."""
        migrations = [
            ("leads", "brand", "TEXT NOT NULL DEFAULT 'default'"),
            ("outreach_log", "brand", "TEXT NOT NULL DEFAULT 'default'"),
            ("daily_stats", "brand", "TEXT NOT NULL DEFAULT 'default'"),
        ]
        with self.transaction() as conn:
            for table, column, col_def in migrations:
                cur = conn.execute(f"PRAGMA table_info({table})")
                existing_cols = {row[1] for row in cur.fetchall()}
                if column not in existing_cols:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")

    @contextmanager
    def transaction(self):
        conn = self.connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
