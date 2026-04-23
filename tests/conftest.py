import os

# Must run before any app module is imported during pytest collection.
# app/db/session.py calls get_engine() at module level; without a DATABASE_URL
# that connectivity check raises SystemExit(1). SQLite satisfies the import-time
# check instantly. Individual tests that need DB access patch crud_module.Session
# with their own per-test session.
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
