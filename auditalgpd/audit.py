"""Orquestração da primeira etapa funcional da auditoria."""

import time
from .domain import AuditResult, Check, Status, public_url
from .security import AuditError, SafeFetcher, normalize_url
from .detectors import detect_banner, detect_forms, find_policy, parse_html, policy_check

LIMITATIONS = [
    "O diagnóstico é técnico e preliminar; não certifica conformidade com a LGPD.",
    "Apenas a página informada e, quando disponível, uma política vinculada da mesma origem são consultadas.",
    "JavaScript não é executado nesta versão; elementos dinâmicos podem não ser identificados.",
    "O comportamento dos cookies, o bloqueio de rastreadores e a validade do consentimento não são testados.",
    "A presença de formulários ou a ausência de um banner não determina, por si só, uma irregularidade.",
]


class Auditoria:
    def __init__(self, fetcher=None):
        self.fetcher = fetcher or SafeFetcher()

    def executar(self, url):
        target = normalize_url(url)  # Entrada inválida não gera resultado artificial.
        result = AuditResult(public_url(target.url), limitations=list(LIMITATIONS))
        start = time.monotonic()
        deadline = start + 20
        try:
            page = self.fetcher.fetch(target.url, deadline=deadline)
            result.final_url = public_url(page.url)
            result.checks = analyze_page(page.html, page.url, page.tls_verified)
            candidates = find_policy(parse_html(page.html), page.url)
            if candidates:
                self._read_policy(result, candidates, page.url, deadline)
        except AuditError as exc:
            result.checks = [Check("collection", "Acesso à página", Status.ERROR, str(exc))]
            for key, title in [("https", "Conexão HTTPS"), ("banner", "Banner de cookies"),
                               ("forms", "Formulários de dados pessoais"), ("policy", "Política de privacidade")]:
                result.checks.append(Check(key, title, Status.NOT_RUN, "A coleta falhou; não é possível concluir esta verificação."))
        result.checks.append(Check("ai", "Análise com inteligência artificial", Status.NOT_RUN,
                                   "Integração com LLM ainda não implementada. Nenhum texto foi enviado a um provedor de IA."))
        result.duration_ms = round((time.monotonic() - start) * 1000)
        return result

    def _read_policy(self, result, candidates, page_url, deadline):
        base = normalize_url(page_url)
        origin = (base.scheme, base.host, base.port)
        for candidate in candidates:
            try:
                document = self.fetcher.fetch(candidate, deadline=deadline, origin=origin)
                text = parse_html(document.html).get_text(" ", strip=True)
                result.checks.append(Check("policy_content", "Acesso ao texto da política",
                                          Status.PRESENT if text else Status.ABSENT,
                                          f"Texto recuperado com {len(text)} caracteres. O conteúdo não recebeu avaliação semântica." if text else
                                          "O documento não apresentou texto extraível.", [public_url(document.url)]))
                return
            except AuditError:
                continue
        result.checks.append(Check("policy_content", "Acesso ao texto da política", Status.ERROR,
                                   "Não foi possível recuperar o texto dentro do escopo e do tempo disponíveis. Links externos não são consultados."))


def analyze_page(html, url, tls_verified):
    soup = parse_html(html)
    secure = normalize_url(url).scheme == "https" and tls_verified
    return [
        Check("https", "Conexão HTTPS", Status.PRESENT if secure else Status.ABSENT,
              "Conexão HTTPS concluída com validação do certificado TLS." if secure else
              "A página final foi recebida por HTTP, sem proteção TLS nesta conexão."),
        detect_banner(soup), detect_forms(soup), policy_check(find_policy(soup, url)),
    ]
