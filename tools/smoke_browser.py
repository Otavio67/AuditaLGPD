"""Teste manual opt-in do navegador real; não faz parte da suíte offline.

O proxy de teste encaminha SOMENTE fixture.example a um servidor efêmero
de fixture. Esse transporte injetado não existe na configuração da aplicação.
"""

from contextlib import contextmanager
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os
import socket
import tempfile
import threading
from unittest.mock import patch
from auditalgpd.browser_proxy import PublicProxy
from auditalgpd.browser_worker import collect
from auditalgpd.detectors import detect_banner, parse_html
from auditalgpd.assessment import contextual_checks
from auditalgpd.security import AuditError


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--portable", type=Path, help="Testar navegador/driver incluídos no pacote")
    args = parser.parse_args()
    if args.portable:
        from auditalgpd.portable import configure_bundle
        configure_bundle(args.portable.resolve())
    root = Path(__file__).resolve().parents[1]
    body = (root/"tests/fixtures/dynamic.html").read_bytes()
    class Fixture(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(("127.0.0.1", 0), Fixture)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    @contextmanager
    def fixture_proxy(lifetime):
        def resolver(host, port):
            if host != "fixture.example" or port != 80:
                raise AuditError("Fora do escopo da fixture.")
            return ["93.184.216.34"]
        proxy = PublicProxy(resolver=resolver, connector=lambda *_args, **_kw: socket.create_connection(("127.0.0.1", server.server_port), timeout=5), lifetime=lifetime)
        threading.Thread(target=proxy.serve_forever, daemon=True).start()
        try:
            yield proxy
        finally:
            proxy.shutdown()
            proxy.finish_connections()
            proxy.server_close()
    os.environ["SE_CACHE_PATH"] = str(root/"instance/selenium")
    os.environ["SE_AVOID_STATS"] = "true"
    try:
        with tempfile.TemporaryDirectory(prefix="audit-fixture-") as temp, patch("auditalgpd.browser_worker.public_proxy", fixture_proxy):
            result = collect({"url":"http://fixture.example/", "browser":"chrome" if args.portable else "edge", "profile":str(Path(temp)/"profile"), "timeout":50})
        assert 'id="cookie-banner"' in result["html"], "O JavaScript não inseriu o aviso."
        assert "VALUE_MUST_NOT_BE_COLLECTED" not in result["html"]
        assert "COOKIE_VALUE_MUST_NOT_BE_SAVED" not in str(result["browser"])
        assert any(c["name"] == "audit_fixture" for c in result["browser"]["cookies"])
        assert result["browser"]["domains"] == ["fixture.example"]
        assert detect_banner(parse_html(result["html"])).status == "presente"
        assert contextual_checks(parse_html(result["html"]), browser=True)[1].status == "presente"
        print("OK: JavaScript real, aviso dinâmico, controles de cookies, captura e remoção de valores; tráfego de inicialização não atribuído à página.")
    finally:
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
