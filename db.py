import sqlite3
from contextlib import contextmanager
from config import Config


# ---------------------------------------------------------------------------
# Connection
# ---------------------------------------------------------------------------

def get_connection():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row   # rows behave like dicts
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@contextmanager
def get_db():
    """Context manager that auto-commits or rolls back."""
    conn = get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT    NOT NULL UNIQUE,
    email       TEXT    NOT NULL UNIQUE,
    password    TEXT    NOT NULL,
    role        TEXT    NOT NULL DEFAULT 'viewer'
                        CHECK(role IN ('viewer', 'analyst', 'admin')),
    status      TEXT    NOT NULL DEFAULT 'active'
                        CHECK(status IN ('active', 'inactive')),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS financial_records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    amount      REAL    NOT NULL CHECK(amount > 0),
    type        TEXT    NOT NULL CHECK(type IN ('income', 'expense')),
    category    TEXT    NOT NULL,
    date        TEXT    NOT NULL,
    notes       TEXT,
    created_by  INTEGER NOT NULL REFERENCES users(id),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    deleted_at  TEXT    DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_records_type     ON financial_records(type);
CREATE INDEX IF NOT EXISTS idx_records_category ON financial_records(category);
CREATE INDEX IF NOT EXISTS idx_records_date     ON financial_records(date);
CREATE INDEX IF NOT EXISTS idx_records_deleted  ON financial_records(deleted_at);
"""


def init_db():
    """Create tables and seed default admin user if database is fresh."""
    with get_db() as conn:
        conn.executescript(SCHEMA)

    _seed_if_empty()


# ---------------------------------------------------------------------------
# Seed
# ---------------------------------------------------------------------------

def _seed_if_empty():
    """Insert a default admin account and sample records on first run."""
    from auth_utils import hash_password

    with get_db() as conn:
        existing = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        if existing > 0:
            return

        users = [
            ("admin",   "admin@example.com",   hash_password("admin123"),   "admin"),
            ("analyst", "analyst@example.com", hash_password("analyst123"), "analyst"),
            ("viewer",  "viewer@example.com",  hash_password("viewer123"),  "viewer"),
        ]
        conn.executemany(
            "INSERT INTO users (username, email, password, role) VALUES (?,?,?,?)",
            users,
        )

        records = [
            (5000.00, "income",  "Salary",      "2025-01-05", "January salary",    1),
            (1200.00, "expense", "Rent",         "2025-01-10", "Monthly rent",      1),
            (80.00,   "expense", "Utilities",    "2025-01-15", "Electricity bill",  1),
            (3200.00, "income",  "Freelance",    "2025-02-03", "Web design project",1),
            (900.00,  "expense", "Groceries",    "2025-02-08", "Monthly groceries", 1),
            (5000.00, "income",  "Salary",       "2025-02-05", "February salary",   1),
            (1200.00, "expense", "Rent",         "2025-02-10", "Monthly rent",      1),
            (450.00,  "expense", "Subscriptions","2025-02-20", "Software tools",    1),
            (5000.00, "income",  "Salary",       "2025-03-05", "March salary",      1),
            (1200.00, "expense", "Rent",         "2025-03-10", "Monthly rent",      1),
            (300.00,  "expense", "Travel",       "2025-03-22", "Conference trip",   1),
            (750.00,  "income",  "Bonus",        "2025-03-28", "Q1 performance",    1),
        ]
        conn.executemany(
            """INSERT INTO financial_records
               (amount, type, category, date, notes, created_by)
               VALUES (?,?,?,?,?,?)""",
            records,
        )

        print("✓ Database seeded with default users and sample records.")


# ---------------------------------------------------------------------------
# Tiny query helpers (avoid raw SQL repetition in routes)
# ---------------------------------------------------------------------------

def row_to_dict(row):
    """Convert a sqlite3.Row to a plain dict."""
    return dict(row) if row else None


def rows_to_list(rows):
    return [dict(r) for r in rows]
