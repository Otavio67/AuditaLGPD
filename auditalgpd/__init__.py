"""Fábrica da aplicação AuditaLGPD."""

import os
import secrets
from pathlib import Path

from flask import Flask


def create_app(test_config=None, *, instance_path=None):
    app = Flask(__name__, instance_relative_config=True, instance_path=instance_path)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("AUDITALGPD_SECRET_KEY") or secrets.token_hex(32),
        DATABASE=str(Path(app.instance_path) / "auditorias.sqlite3"),
        MAX_CONTENT_LENGTH=16 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Strict",
        TRUSTED_HOSTS=["localhost", "127.0.0.1"],
        # Opcionais, para demonstrações temporárias: código de acesso e limite por hora (0 = sem limite).
        ACCESS_CODE=os.environ.get("AUDITALGPD_ACCESS_CODE", "").strip(),
        MAX_ANALYSES_PER_HOUR=int(os.environ.get("AUDITALGPD_MAX_ANALYSES_PER_HOUR", "0") or 0),
        # Demonstração pública: impede que visitantes troquem a chave/modelo e deixa o Gemini marcado por padrão.
        LOCK_SETTINGS=os.environ.get("AUDITALGPD_LOCK_SETTINGS") == "1",
        AI_DEFAULT=os.environ.get("AUDITALGPD_AI_DEFAULT") == "1",
    )
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    from .web import init_app
    init_app(app)

    @app.get("/health")
    def health():
        return {"status": "ok", "application": "AuditaLGPD", "version": "0.2.0"}

    return app
