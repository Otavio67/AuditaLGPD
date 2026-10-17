"""Fluxo local da auditoria, com proteção de formulários e saída escapada."""

from datetime import datetime
import secrets
from flask import Blueprint, abort, current_app, redirect, render_template, request, send_file, session, url_for
from werkzeug.exceptions import SecurityError
from .audit import Auditoria
from .security import UnsafeURL
from .storage import Repository

bp = Blueprint("web", __name__)
LABELS = {"presente": "Identificado", "nao_identificado": "Não identificado", "erro": "Erro na verificação", "nao_executado": "Não executado"}


def repository():
    return current_app.extensions["repository"]


@bp.app_context_processor
def helpers():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return {"csrf_token": session["csrf"], "status_labels": LABELS}


@bp.app_template_filter("data_br")
def data_br(value):
    return datetime.fromisoformat(value).astimezone().strftime("%d/%m/%Y às %H:%M")


@bp.get("/")
def home():
    return render_template("home.html", error=None, entered_url="")


@bp.post("/auditorias")
def create():
    token = request.form.get("csrf", "")
    if not token or not secrets.compare_digest(token, session.get("csrf", "")):
        abort(400, description="A sessão do formulário expirou. Volte ao início e tente novamente.")
    entered_url = request.form.get("url", "")
    if request.form.get("authorized") != "yes":
        return render_template("home.html", error="Confirme que tem autorização para analisar o site.", entered_url=entered_url), 400
    try:
        result = current_app.extensions["auditor"].executar(entered_url)
    except UnsafeURL as exc:
        return render_template("home.html", error=str(exc), entered_url=entered_url), 400
    repository().save(result)
    return redirect(url_for("web.result", audit_id=result.id), code=303)


@bp.get("/auditorias/<audit_id>")
def result(audit_id):
    audit = repository().get(audit_id)
    if audit is None:
        abort(404)
    return render_template("result.html", audit=audit)


@bp.get("/historico")
def history():
    return render_template("history.html", audits=repository().latest())


@bp.get("/auditorias/<audit_id>/relatorio.pdf")
def pdf(audit_id):
    from .reports import generate_pdf
    audit = repository().get(audit_id)
    if audit is None:
        abort(404)
    return send_file(generate_pdf(audit), mimetype="application/pdf", as_attachment=True,
                     download_name=f"AuditaLGPD-{audit.id}.pdf")


@bp.get("/demonstracao")
def demo():
    from .demo import demo_result
    return render_template("result.html", audit=demo_result())


def init_app(app):
    app.extensions["repository"] = Repository(app.config["DATABASE"])
    app.extensions["auditor"] = app.config.get("AUDITOR") or Auditoria()
    app.register_blueprint(bp)

    @app.after_request
    def secure_headers(response):
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.errorhandler(400)
    @app.errorhandler(404)
    @app.errorhandler(413)
    def error_page(error):
        if isinstance(error, SecurityError):
            # A validação do Host falha antes da criação do adaptador de rotas.
            # A resposta não pode depender de url_for nem refletir o Host recebido.
            return "Endereço de acesso não permitido.", 400, {"Content-Type": "text/plain; charset=utf-8"}
        descriptions = {400: "Não foi possível aceitar a solicitação. Volte ao início e tente novamente.",
                        404: "Esta auditoria não foi encontrada no histórico local.",
                        413: "O formulário excedeu o tamanho permitido."}
        return render_template("error.html", code=error.code, description=descriptions[error.code]), error.code
