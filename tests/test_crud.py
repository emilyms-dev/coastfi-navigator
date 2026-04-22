"""CRUD tests — Phase 3.

Integration tests for app/db/crud.py using a test database.
Uses SQLite in-memory for speed; tradeoff documented: SQLite does not support
all PostgreSQL features (e.g. UUID columns require adaptation), but covers
CRUD correctness adequately for the MVP feature set.
"""
