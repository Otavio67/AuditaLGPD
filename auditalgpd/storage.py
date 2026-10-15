"""Histórico local; o HTML e valores de formulários não são armazenados."""

import json
import sqlite3
from contextlib import contextmanager
from .domain import AuditResult


class Repository:
    def __init__(self, path):
        self.path = path
        with self.connect() as db:
            db.execute("CREATE TABLE IF NOT EXISTS audits (id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL)")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def save(self, result):
        with self.connect() as db:
            db.execute("INSERT INTO audits VALUES (?, ?, ?)",
                       (result.id, result.created_at, json.dumps(result.to_dict(), ensure_ascii=False)))

    def get(self, audit_id):
        with self.connect() as db:
            row = db.execute("SELECT payload FROM audits WHERE id = ?", (audit_id,)).fetchone()
        return AuditResult.from_dict(json.loads(row[0])) if row else None

    def latest(self, limit=30):
        with self.connect() as db:
            rows = db.execute("SELECT payload FROM audits ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [AuditResult.from_dict(json.loads(row[0])) for row in rows]
