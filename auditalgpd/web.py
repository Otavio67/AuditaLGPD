"""Fluxo local da auditoria, com proteção de formulários e saída escapada."""

from datetime import datetime
import base64
from io import BytesIO
from pathlib import Path
import secrets
from flask import Blueprint, abort, current_app, redirect, render_template, request, send_file, session, url_for
from werkzeug.exceptions import SecurityError
from .audit import Auditoria
from .security import AuditError, UnsafeURL, normalize_url
from .storage import Repository
from .assessment import assessment
from .browser import SeleniumFetcher
from .settings import Settings
from .jobs import Jobs, BusyError

bp = Blueprint("web", __name__)
LABELS = {"presente": "Identificado", "nao_identificado": "Não identificado", "erro": "Erro na verificação", "nao_executado": "Não executado"}


def repository():
    return current_app.extensions["repository"]


@bp.app_context_processor
def helpers():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(32)
    return {"csrf_token": session["csrf"], "status_labels": LABELS,
            "local_settings": current_app.extensions["settings"].public()}


def require_csrf():
    token = request.form.get("csrf", "")
    if not token or not secrets.compare_digest(token, session.get("csrf", "")):
        abort(400)


def auditor():
    configured = current_app.extensions["auditor"]
    if configured:
        return configured
    settings = current_app.extensions["settings"]
    return Auditoria(browser_fetcher=SeleniumFetcher(Path(current_app.instance_path)/"selenium", settings.browser), ai_client=settings.client())


@bp.app_template_filter("data_br")
def data_br(value):
    return datetime.fromisoformat(value).astimezone().strftime("%d/%m/%Y às %H:%M")


@bp.get("/")
def home():
    return render_template("home.html", error=None, entered_url="")


@bp.post("/auditorias")
def create():
    require_csrf()
    entered_url = request.form.get("url", "")
    if request.form.get("authorized") != "yes":
        return render_template("home.html", error="Confirme que tem autorização para analisar o site.", entered_url=entered_url), 400
    try:
        normalize_url(entered_url)
        mode = request.form.get("mode", "static")
        use_ai = request.form.get("use_ai") == "yes"
        if mode not in {"static", "browser"}:
            raise UnsafeURL("Escolha um modo de análise válido.")
        if use_ai and not current_app.extensions["settings"].public()["configured"]:
            raise UnsafeURL("Configure a chave do Gemini antes de ativar a IA.")
        collector, repo = auditor(), repository()
        if request.headers.get("X-Audita-Async") == "1":
            def work(update):
                result = collector.executar(entered_url, mode=mode, use_ai=use_ai, progress=update)
                repo.save(result)
                return result
            job_id = current_app.extensions["jobs"].submit(work)
            return {"progress_url": url_for("web.job", job_id=job_id)}, 202
        result = current_app.extensions["jobs"].run_sync(lambda: collector.executar(entered_url, mode=mode, use_ai=use_ai))
    except BusyError:
        return {"error": "Uma análise já está em andamento. Aguarde sua conclusão."}, 409
    except AuditError as exc:
        if request.headers.get("X-Audita-Async") == "1":
            return {"error": str(exc)}, 400
        return render_template("home.html", error=str(exc), entered_url=entered_url), 400
    repository().save(result)
    return redirect(url_for("web.result", audit_id=result.id), code=303)


@bp.get("/auditorias/<audit_id>")
def result(audit_id):
    audit = repository().get(audit_id)
    if audit is None:
        abort(404)
    return render_template("result.html", audit=audit, score=audit.score or assessment(audit))


@bp.get("/tarefas/<job_id>")
def job(job_id):
    item = current_app.extensions["jobs"].get(job_id)
    if not item:
        abort(404)
    if item["state"] == "done":
        item["result_url"] = url_for("web.result", audit_id=item.pop("audit_id"))
    return item


@bp.get("/auditorias/<audit_id>/captura.png")
def screenshot(audit_id):
    audit = repository().get(audit_id)
    if not audit:
        abort(404)
    try:
        data = base64.b64decode(audit.browser.get("screenshot", ""), validate=True)
    except ValueError:
        abort(404)
    if not data.startswith(b"\x89PNG\r\n\x1a\n") or len(data) > 1_000_000:
        abort(404)
    return send_file(BytesIO(data), mimetype="image/png")


@bp.route("/configuracoes", methods=["GET", "POST"])
def settings():
    error, saved = None, False
    if request.method == "POST":
        require_csrf()
        try:
            current_app.extensions["settings"].update(request.form.get("browser", "edge"), request.form.get("model", "").strip(),
                                                       request.form.get("api_key", "").strip(), request.form.get("clear_key") == "yes")
            saved = True
        except AuditError as exc:
            error = str(exc)
    return render_template("settings.html", error=error, saved=saved), (400 if error else 200)


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
    audit = demo_result()
    return render_template("result.html", audit=audit, score=audit.score or assessment(audit))


def init_app(app):
    app.extensions["repository"] = Repository(app.config["DATABASE"])
    app.extensions["settings"] = Settings(Path(app.config["DATABASE"]).parent)
    app.extensions["jobs"] = Jobs()
    app.extensions["auditor"] = app.config.get("AUDITOR")
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
