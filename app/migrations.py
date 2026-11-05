"""Adds columns that newer versions need to a database that was created by an older one."""

# (table, column, definition); the same text works on SQLite, PostgreSQL and MySQL
COLUMNS = [
    ("complaint", "category", "VARCHAR(60) NOT NULL DEFAULT 'Other'"),
    ("complaint", "severity", "VARCHAR(20) NOT NULL DEFAULT 'Medium'"),
    ("complaint", "latitude", "DOUBLE PRECISION"),
    ("complaint", "longitude", "DOUBLE PRECISION"),
    ("police_station", "phone", "VARCHAR(40)"),
    ("police_station", "latitude", "DOUBLE PRECISION"),
    ("police_station", "longitude", "DOUBLE PRECISION"),
]


def _has_column(conn, table, column):
    try:
        conn.execute(f"SELECT {column} FROM {table} LIMIT 0")
        return True
    except Exception:
        conn.rollback()  # PostgreSQL leaves the transaction broken after a failed statement
        return False


def upgrade(conn):
    for table, column, definition in COLUMNS:
        if not _has_column(conn, table, column):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")
    conn.commit()
