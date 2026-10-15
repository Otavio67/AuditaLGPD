"""Resultados observáveis, sem notas de conformidade jurídica."""

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from urllib.parse import urlsplit, urlunsplit
import secrets


class Status(StrEnum):
    PRESENT = "presente"
    ABSENT = "nao_identificado"
    ERROR = "erro"
    NOT_RUN = "nao_executado"


def public_url(url: str) -> str:
    """Não persistir parâmetros, fragmentos ou credenciais da URL."""
    parsed = urlsplit(url)
    hostname = parsed.hostname or ""
    if ":" in hostname:
        hostname = f"[{hostname}]"
    return urlunsplit((parsed.scheme, hostname, parsed.path or "/", "", ""))


@dataclass
class Check:
    key: str
    title: str
    status: str
    detail: str
    evidence: list[str] = field(default_factory=list)


@dataclass
class AuditResult:
    url: str
    id: str = field(default_factory=lambda: secrets.token_urlsafe(18))
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    final_url: str = ""
    checks: list[Check] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    duration_ms: int = 0
    demo: bool = False

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        data = dict(data)
        data["checks"] = [Check(**item) for item in data["checks"]]
        return cls(**data)
