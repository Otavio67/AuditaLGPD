"""Fábrica da aplicação AuditaLGPD."""

import os
import secrets
from pathlib import Path

from flask import Flask


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("AUDITALGPD_SECRET_KEY") or secrets.token_hex(32),
        DATABASE=str(Path(app.instance_path) / "auditorias.sqlite3"),
        MAX_CONTENT_LENGTH=16 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
    )
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    @app.get("/health")
    def health():
        return {"status": "ok", "application": "AuditaLGPD", "version": "0.1.0"}

    return app
