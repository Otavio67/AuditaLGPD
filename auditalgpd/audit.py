"""Orquestra coleta, evidências, rubrica e interpretação opcional por IA."""

import time
from urllib.parse import urlsplit, urlunsplit
from .domain import AuditResult, Check, Status, public_url
from .security import AuditError, SafeFetcher, normalize_url
from .detectors import detect_banner, detect_forms, find_policy, parse_html, policy_check
from .assessment import assessment, contextual_checks, policy_topics
from .gemini import redact
from .policy_draft import classify_cookie, describe_domain, form_fields, host_of

LIMITATIONS = [
    "O diagnóstico é técnico e preliminar; a nota mede sinais observáveis pela rubrica acadêmica, não certifica conformidade com a LGPD.",
    "São consultadas a página informada e uma política vinculada da mesma origem. Não há varredura de todas as páginas do domínio.",
    "A heurística textual pode gerar falsos positivos e negativos. Presença de termos não comprova clareza, suficiência ou veracidade das declarações.",
    "Cookies são observados antes de qualquer interação. Bloqueio, escolhas, revogação e finalidade real exigem validação adicional.",
    "Formulários não são preenchidos nem enviados pela ferramenta. Sua presença e a ausência de um banner não determinam irregularidade.",
]


TOPIC_KEYS = {"purposes", "data_types", "sharing", "retention", "rights", "controller", "legal_basis"}


def advice_facts(result, policy_how="nenhuma", policy_chars=0):
    """Contexto enviado ao Gemini: nomes de cookies (sem valores), tipos de campos, serviços de terceiros, controles do aviso de cookies
    e o que a leitura da política encontrou (com trechos curtos e remoção básica de e-mail, CPF e telefone)."""
    browser = result.browser or {}
    cookies = browser.get("cookies", [])
    categories = {}
    for cookie in cookies:
        category = classify_cookie(cookie["name"])[0]
        categories[category] = categories.get(category, 0) + 1
    third_parties = sorted({label for domain in browser.get("domains", []) if (label := describe_domain(domain))})
    facts = {"modo_de_analise": "avançada" if result.mode == "browser" else "simples",
             "campos_de_formulario": form_fields(result), "cookies_por_categoria": categories,
             "cookies_observados": [{"nome": c["name"], "categoria": classify_cookie(c["name"])[0], "dominio": c.get("domain", "")} for c in cookies[:30]],
             "servicos_de_terceiros": third_parties}
    cookie_check = next((c for c in result.checks if c.key == "cookie_choices"), None)
    if cookie_check and cookie_check.evidence:
        facts["controles_encontrados_no_aviso_de_cookies"] = cookie_check.evidence
    topics = [{"tema": c.title, "estado": str(c.status), "trecho": redact(c.evidence[0])[:220] if c.evidence else ""}
              for c in result.checks if c.key in TOPIC_KEYS]
    facts["politica"] = {"encontrada_por": policy_how, "caracteres_lidos": policy_chars, "temas_buscados_por_heuristica": topics}
    return facts


COMMON_POLICY_PATHS = ["/politica-de-privacidade/", "/privacidade/"]


def common_policy_urls(page_url):
    """Caminhos comuns no mesmo host e porta; não segue links externos."""
    parts = urlsplit(page_url)
    return [urlunsplit((parts.scheme, parts.netloc, path, "", "")) for path in COMMON_POLICY_PATHS]


class Auditoria:
    def __init__(self, fetcher=None, browser_fetcher=None, ai_client=None):
        self.fetcher = fetcher or SafeFetcher()
        self.browser_fetcher = browser_fetcher
        self.ai_client = ai_client

    def executar(self, url, mode="static", use_ai=False, progress=None):
        target = normalize_url(url)
        if mode not in {"static", "browser"}:
            raise AuditError("Modo de coleta inválido.")
        result = AuditResult(public_url(target.url), mode=mode, limitations=list(LIMITATIONS))
        start = time.monotonic()
        deadline = start + (130 if mode == "browser" else 20)
        notify = progress or (lambda *_: None)
        policy_text, policy_source, policy_how = "", "", "nenhuma"
        notify("Validando o endereço informado", 3)
        notify("Carregando a página no navegador" if mode == "browser" else "Consultando o HTML da página", 8, 36 if mode == "browser" else 30)
        try:
            collector = self.browser_fetcher if mode == "browser" else self.fetcher
            if collector is None:
                raise AuditError("A análise avançada não está disponível nesta instalação.")
            page = collector.fetch(target.url, deadline=deadline)
            result.final_url = public_url(page.url)
            result.browser = page.browser
            notify("Conferindo HTTPS, aviso de cookies e formulários", 40)
            result.checks = analyze_page(page.html, page.url, page.tls_verified)
            soup = parse_html(page.html)
            notify("Analisando as escolhas do aviso de cookies", 46)
            result.checks.extend(contextual_checks(soup, browser=mode == "browser"))
            if mode == "static":
                result.limitations.append("O modo rápido não executa JavaScript. Conteúdos dinâmicos podem não ser identificados.")
            else:
                result.checks.append(Check("selenium", "Página com conteúdo dinâmico", Status.PRESENT,
                                           "Coleta concluída em navegador local com perfil temporário, antes de qualquer escolha de cookies."))
                notify("Analisando os cookies e domínios observados", 52)
                cookies = result.browser.get("cookies", [])
                result.checks.append(Check("cookies", "Cookies observados no navegador", Status.PRESENT if cookies else Status.ABSENT,
                                          f"{len(cookies)} cookie(s) observado(s) nesta sessão. Valores não são armazenados. A finalidade não é inferida automaticamente.",
                                          [f"{c['name']} · {c['domain']}" for c in cookies[:30]]))
            notify("Procurando o link da política de privacidade", 58)
            candidates = find_policy(soup, page.url)
            policy_how = "link na página" if candidates else "nenhuma"
            if not candidates:
                # Muitos sites não linkam a política na página inicial (ou só no aviso de cookies).
                candidates = common_policy_urls(page.url)
                if candidates:
                    policy_how = "caminho comum do mesmo domínio"
                    result.limitations.append("Nenhum link de política foi visível na página; o texto foi buscado em caminhos comuns do mesmo domínio.")
            if candidates:
                notify("Lendo a página da política de privacidade", 64, 74)
                policy_text, policy_source = self._read_policy(result, candidates, page.url, deadline, collector)
            notify("Analisando os temas da política: finalidades, retenção e direitos", 76)
            result.checks.extend(policy_topics(policy_text))
        except AuditError as exc:
            result.checks = [Check("collection", "Acesso à página", Status.ERROR, str(exc))]
            for key, title in [("https", "Conexão HTTPS"), ("banner", "Banner de cookies"),
                               ("forms", "Formulários de dados pessoais"), ("policy", "Política de privacidade")]:
                result.checks.append(Check(key, title, Status.NOT_RUN, "A coleta falhou; não é possível concluir esta verificação."))
        notify("Calculando a nota pela rubrica", 80)
        result.score = assessment(result)
        # A nota é calculada antes da IA e nunca depende dela. Uma única chamada serve à leitura da política e às dicas.
        low = result.score["value"] is not None and result.score["value"] < 60
        wants_policy = bool(use_ai and self.ai_client and policy_text)
        wants_advice = bool(use_ai and self.ai_client and low and result.score["improvements"])
        review = {"analysis": None, "advice": None, "errors": {}}
        if wants_policy or wants_advice:
            notify("Gemini analisando a política e preparando as dicas de melhoria" if wants_policy and wants_advice else
                   "Gemini interpretando o texto da política" if wants_policy else "Gemini preparando as dicas de melhoria", 84, 96)
            try:
                review = self.ai_client.review(policy_text if wants_policy else "", policy_source, host_of(result),
                                               result.score if wants_advice else None,
                                               advice_facts(result, policy_how, len(policy_text)) if wants_advice else None)
            except AuditError as exc:
                review = {"analysis": None, "advice": None, "errors": {"ai": str(exc), "advice": str(exc)}}
        if wants_policy:
            if review["analysis"]:
                result.ai = review["analysis"]
                result.checks.append(Check("ai", "Interpretação com Gemini", Status.PRESENT,
                                           "Interpretação recebida. Apenas trechos presentes no texto enviado são aceitos como evidência; a IA não altera a nota."))
            else:
                result.checks.append(Check("ai", "Interpretação com Gemini", Status.ERROR,
                                           review["errors"].get("ai", "O Gemini não retornou a interpretação da política.")))
        else:
            detail = ("Não há texto de política disponível para enviar ao Gemini." if use_ai and not policy_text else
                      "Configure sua chave do Gemini nas configurações locais." if use_ai else
                      "IA desativada para esta análise. Nenhum texto foi enviado ao Gemini.")
            result.checks.append(Check("ai", "Interpretação com Gemini", Status.NOT_RUN, detail))
        if wants_advice:
            result.advice = review["advice"] or {"error": review["errors"].get("advice", "O Gemini não retornou as dicas de melhoria.")}
        notify("Montando o relatório", 98)
        result.duration_ms = round((time.monotonic() - start) * 1000)
        return result

    def _read_policy(self, result, candidates, page_url, deadline, collector):
        base = normalize_url(page_url)
        origin = (base.scheme, base.host, base.port)
        for candidate in candidates:
            try:
                document = collector.fetch(candidate, deadline=deadline, origin=origin)
                soup = parse_html(document.html)
                for tag in soup(["nav", "header", "footer", "form"]):
                    tag.decompose()
                text = soup.get_text(" ", strip=True)[:60_000]
                result.checks.append(Check("policy_content", "Acesso ao texto da política", Status.PRESENT if text else Status.ABSENT,
                                          f"Texto recuperado: {len(text)} caracteres, limitado a 60.000. Os temas são buscados por heurísticas textuais." if text else
                                          "O documento não apresentou texto extraível.", [public_url(document.url)]))
                return text, public_url(document.url)
            except AuditError:
                continue
        result.checks.append(Check("policy_content", "Acesso ao texto da política", Status.ERROR,
                                   "Não foi possível recuperar o texto dentro do escopo e tempo disponíveis. Links externos não são consultados."))
        return "", ""


def analyze_page(html, url, tls_verified):
    soup = parse_html(html)
    secure = normalize_url(url).scheme == "https" and tls_verified
    return [Check("https", "Conexão HTTPS", Status.PRESENT if secure else Status.ABSENT,
                  "Conexão HTTPS concluída com validação do certificado TLS." if secure else
                  "A página final foi recebida por HTTP, sem proteção TLS nesta conexão."),
            detect_banner(soup), detect_forms(soup), policy_check(find_policy(soup, url))]
