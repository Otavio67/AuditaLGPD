"""Proxy efêmero de saída: valida DNS e conecta ao IP público aprovado.

O navegador usa o proxy inclusive para loopback. Não há interceptação TLS.
Isto reduz acesso acidental à rede privada; não substitui isolamento de SO.
"""

from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import select
import socket
import threading
import time
from .security import AuditError, normalize_url, resolve_public


def proxy_target(authority, connect=False):
    target = normalize_url(("https://" + authority) if connect else authority)
    if connect and target.port != 443:
        raise AuditError("Túnel permitido apenas para HTTPS padrão.")
    if not connect and target.scheme != "http":
        raise AuditError("Use CONNECT para HTTPS.")
    return target


class PublicProxy(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def __init__(self, resolver=resolve_public, connector=socket.create_connection, lifetime=55):
        self.resolver, self.connector = resolver, connector
        self.deadline = time.monotonic() + lifetime
        self.lock = threading.Lock()
        self.sockets = set()
        self.domains = set()
        self.connections = 0
        self.bytes = 0
        self.blocked = 0
        super().__init__(("127.0.0.1", 0), Handler)

    def open_public(self, target):
        with self.lock:
            self.connections += 1
            if self.connections > 180 or time.monotonic() > self.deadline:
                raise AuditError("Limite de conexões do navegador atingido.")
        addresses = self.resolver(target.host, target.port)
        remote = self.connector((addresses[0], target.port), timeout=5)
        with self.lock:
            self.sockets.add(remote)
            self.domains.add(target.host)
        return remote

    def relay(self, client, remote):
        client.settimeout(8)
        remote.settimeout(8)
        while time.monotonic() < self.deadline:
            ready, _, _ = select.select([client, remote], [], [], 1)
            if not ready:
                continue
            for source in ready:
                chunk = source.recv(65536)
                if not chunk:
                    return
                with self.lock:
                    self.bytes += len(chunk)
                    if self.bytes > 20_000_000:
                        return
                (remote if source is client else client).sendall(chunk)

    def finish_connections(self):
        with self.lock:
            sockets = list(self.sockets)
        for sock in sockets:
            try:
                sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            sock.close()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *_):
        pass  # URLs e cabeçalhos não devem ir para logs.

    def do_CONNECT(self):
        self.forward(True)

    def do_GET(self):
        self.forward(False)

    def do_HEAD(self):
        self.forward(False)

    def forward(self, connect):
        remote, started = None, False
        try:
            target = proxy_target(self.path, connect=connect)
            remote = self.server.open_public(target)
            if connect:
                self.send_response(200, "Connection established")
                self.end_headers()
            else:
                headers = {k: v for k, v in self.headers.items() if k.lower() not in {
                    "host", "connection", "proxy-connection", "proxy-authorization", "transfer-encoding", "content-length"}}
                headers["Host"] = target.host
                headers["Connection"] = "close"
                head = f"{self.command} {target.path} HTTP/1.1\r\n" + "".join(f"{k}: {v}\r\n" for k, v in headers.items()) + "\r\n"
                remote.sendall(head.encode("iso-8859-1"))
            started = True
            self.server.relay(self.connection, remote)
        except (AuditError, OSError, ValueError):
            with self.server.lock:
                self.server.blocked += 1
            if not started:
                try:
                    self.send_error(403, "Destino indisponivel ou nao permitido")
                except OSError:
                    pass
        finally:
            self.close_connection = True
            if remote:
                with self.server.lock:
                    self.server.sockets.discard(remote)
                remote.close()


@contextmanager
def public_proxy(lifetime=55):
    server = PublicProxy(lifetime=lifetime)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.finish_connections()
        server.server_close()
        thread.join(timeout=2)
