"""Cache local das respostas já validadas do Gemini.

A chave é o hash do conteúdo enviado (sem a chave da API). O mesmo conteúdo reaproveita a resposta por até 24 horas,
sem gastar cota. Falhas de disco nunca interrompem a análise: o cache simplesmente deixa de ser usado.
"""

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import time


class AiCache:
    def __init__(self, path, ttl=24 * 3600):
        self.path, self.ttl = Path(path), ttl

    def _connect(self):
        db = sqlite3.connect(self.path, timeout=5)
        db.execute("CREATE TABLE IF NOT EXISTS ai_cache (key TEXT PRIMARY KEY, created REAL NOT NULL, payload TEXT NOT NULL)")
        return db

    def get(self, key):
        try:
            with closing(self._connect()) as db:
                row = db.execute("SELECT created, payload FROM ai_cache WHERE key = ?", (key,)).fetchone()
                if not row:
                    return None
                if time.time() - row[0] > self.ttl:
                    db.execute("DELETE FROM ai_cache WHERE key = ?", (key,))
                    db.commit()
                    return None
                return json.loads(row[1])
        except (sqlite3.Error, OSError, ValueError):
            return None

    def set(self, key, value):
        try:
            with closing(self._connect()) as db:
                db.execute("DELETE FROM ai_cache WHERE created < ?", (time.time() - self.ttl,))
                db.execute("INSERT OR REPLACE INTO ai_cache VALUES (?, ?, ?)", (key, time.time(), json.dumps(value, ensure_ascii=False)))
                db.commit()
        except (sqlite3.Error, OSError, TypeError, ValueError):
            pass
