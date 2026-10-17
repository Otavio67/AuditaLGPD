"""Coleta pública limitada, com DNS validado e conexão ao IP verificado."""

from dataclasses import dataclass, field
import http.client
import ipaddress
import re
import socket
import ssl
import time
from urllib.parse import quote, urljoin, urlsplit, urlunsplit


class AuditError(Exception):
    """Erro de entrada ou coleta que pode ser mostrado ao usuário."""


class UnsafeURL(AuditError):
    pass


@dataclass(frozen=True)
class Target:
    url: str
    scheme: str
    host: str
    port: int
    path: str


def normalize_url(value: str) -> Target:
    value = value.strip()
    if not value or len(value) > 2048 or any(ord(c) < 32 for c in value) or "\\" in value:
        raise UnsafeURL("Informe uma URL pública válida, com até 2048 caracteres.")
    if "://" not in value:
        value = "https://" + value
    try:
        parsed = urlsplit(value)
        host = (parsed.hostname or "").encode("idna").decode("ascii").lower().rstrip(".")
        if parsed.scheme not in {"http", "https"} or parsed.username is not None or parsed.password is not None:
            raise ValueError
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        if port != (443 if parsed.scheme == "https" else 80):
            raise ValueError
        if not host or "%" in host or not re.fullmatch(r"[a-z0-9.:-]+", host):
            raise ValueError
        if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
            raise ValueError
        try:
            address = ipaddress.ip_address(host)
            if not is_public(address):
                raise ValueError
        except ValueError:
            # Endereços numéricos inválidos não podem virar nomes DNS alternativos.
            if ":" in host or re.fullmatch(r"[\d.]+", host):
                raise UnsafeURL("Endereços locais, privados ou reservados não são permitidos.")
            if "." not in host or any(not part or len(part) > 63 or part.startswith("-") or part.endswith("-") for part in host.split(".")):
                raise ValueError
        authority = f"[{host}]" if ":" in host else host
        path = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
        query = quote(parsed.query, safe="%=&?/:@!$'()*+,;~-._")
        url = urlunsplit((parsed.scheme, authority, path, query, ""))
        return Target(url, parsed.scheme, host, port, path + ("?" + query if query else ""))
    except (ValueError, UnicodeError) as exc:
        raise UnsafeURL("Use uma URL pública HTTP ou HTTPS, sem credenciais e com porta padrão.") from exc


def is_public(address):
    return address.is_global and not (
        address.is_multicast or address.is_reserved or address.is_unspecified
        or address.is_loopback or address.is_link_local
    ) and (not getattr(address, "ipv4_mapped", None) or is_public(address.ipv4_mapped))


def resolve_public(host, port):
    try:
        records = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
        addresses = list(dict.fromkeys(record[4][0] for record in records))
    except socket.gaierror as exc:
        raise AuditError("Não foi possível localizar o domínio informado.") from exc
    if not addresses or any(not is_public(ipaddress.ip_address(ip)) for ip in addresses):
        raise UnsafeURL("O domínio aponta para endereço local, privado ou reservado.")
    return addresses


class PinnedHTTP(http.client.HTTPConnection):
    def __init__(self, target, address, timeout):
        super().__init__(target.host, target.port, timeout=timeout)
        self.address = address

    def connect(self):
        self.sock = socket.create_connection((self.address, self.port), self.timeout)


class PinnedHTTPS(http.client.HTTPSConnection):
    def __init__(self, target, address, timeout):
        super().__init__(target.host, target.port, timeout=timeout, context=ssl.create_default_context())
        self.address = address

    def connect(self):
        raw = socket.create_connection((self.address, self.port), self.timeout)
        try:
            self.sock = self._context.wrap_socket(raw, server_hostname=self.host)
        except Exception:
            raw.close()
            raise


@dataclass
class Page:
    url: str
    html: str
    tls_verified: bool
    browser: dict = field(default_factory=dict)


class SafeFetcher:
    """Não utiliza proxies de ambiente, cookies, autenticação ou JavaScript."""

    def __init__(self, max_bytes=2_000_000, timeout=6, max_redirects=3, resolver=resolve_public, connector=None):
        self.max_bytes = max_bytes
        self.timeout = timeout
        self.max_redirects = max_redirects
        self.resolver = resolver
        self.connector = connector

    def fetch(self, url, deadline=None, origin=None):
        deadline = deadline or (time.monotonic() + 15)
        target = normalize_url(url)
        for _ in range(self.max_redirects + 1):
            if origin and (target.scheme, target.host, target.port) != origin:
                raise UnsafeURL("A política foi redirecionada para outra origem; não foi consultada.")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise AuditError("O tempo limite da auditoria foi atingido.")
            addresses = self.resolver(target.host, target.port)
            connection = (self.connector(target, addresses[0], min(self.timeout, remaining)) if self.connector else
                          (PinnedHTTPS if target.scheme == "https" else PinnedHTTP)(target, addresses[0], min(self.timeout, remaining)))
            try:
                connection.request("GET", target.path, headers={
                    "User-Agent": "AuditaLGPD/0.1 (diagnostico academico preliminar)",
                    "Accept": "text/html, application/xhtml+xml",
                    "Accept-Encoding": "identity",
                    "Connection": "close",
                })
                response = connection.getresponse()
                if response.status in {301, 302, 303, 307, 308}:
                    location = response.getheader("Location")
                    if not location:
                        raise AuditError("O site retornou um redirecionamento sem destino.")
                    target = normalize_url(urljoin(target.url, location))
                    continue
                if not 200 <= response.status < 300:
                    raise AuditError(f"O site respondeu com HTTP {response.status}; o HTML não foi analisado.")
                content_type = response.getheader("Content-Type", "").lower()
                if content_type.split(";", 1)[0].strip() not in {"text/html", "application/xhtml+xml"}:
                    raise AuditError("O endereço não retornou uma página HTML.")
                if response.getheader("Content-Encoding", "identity").lower() not in {"", "identity"}:
                    raise AuditError("O servidor retornou conteúdo comprimido não suportado nesta etapa.")
                chunks, size = [], 0
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise AuditError("O tempo limite da auditoria foi atingido.")
                    if getattr(connection, "sock", None):
                        connection.sock.settimeout(min(self.timeout, remaining))
                    chunk = response.read1(min(65536, self.max_bytes - size + 1))
                    if not chunk:
                        break
                    size += len(chunk)
                    if size > self.max_bytes:
                        raise AuditError("A página ultrapassa o limite de 2 MB de HTML.")
                    chunks.append(chunk)
                charset = response.headers.get_content_charset() or "utf-8"
                try:
                    text = b"".join(chunks).decode(charset, errors="replace")
                except LookupError:
                    text = b"".join(chunks).decode("utf-8", errors="replace")
                return Page(target.url, text, target.scheme == "https")
            except ssl.SSLCertVerificationError as exc:
                raise AuditError("O certificado TLS não pôde ser validado. A análise foi interrompida.") from exc
            except (OSError, http.client.HTTPException) as exc:
                raise AuditError("Não foi possível concluir a conexão com o site no prazo disponível.") from exc
            finally:
                connection.close()
        raise AuditError("O site ultrapassou o limite de redirecionamentos.")
