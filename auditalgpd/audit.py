"""Orquestra coleta, evidências, rubrica e interpretação opcional por IA."""

import time
from .domain import AuditResult, Check, Status, public_url
from .security import AuditError, SafeFetcher, normalize_url
from .detectors import detect_banner, detect_forms, find_policy, parse_html, policy_check
from .assessment import assessment, contextual_checks, policy_topics

LIMITATIONS = [
    "O diagnóstico é técnico e preliminar; a nota mede sinais observáveis pela rubrica acadêmica, não certifica conformidade com a LGPD.",
    "São consultadas a página informada e uma política vinculada da mesma origem. Não há varredura de todas as páginas do domínio.",
    "A heurística textual pode gerar falsos positivos e negativos. Presença de termos não comprova clareza, suficiência ou veracidade das declarações.",
    "Cookies são observados antes de qualquer interação. Bloqueio, escolhas, revogação e finalidade real exigem validação adicional.",
    "Formulários não são preenchidos nem enviados pela ferramenta. Sua presença e a ausência de um banner não determinam irregularidade.",
]


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
        policy_text, policy_source = "", ""
        notify("Carregando a página no navegador" if mode == "browser" else "Consultando o HTML da página")
        try:
            collector = self.browser_fetcher if mode == "browser" else self.fetcher
            if collector is None:
                raise AuditError("A análise avançada não está disponível nesta instalação.")
            page = collector.fetch(target.url, deadline=deadline)
            result.final_url = public_url(page.url)
            result.browser = page.browser
            notify("Verificando privacidade, formulários e cookies")
            result.checks = analyze_page(page.html, page.url, page.tls_verified)
            soup = parse_html(page.html)
            result.checks.extend(contextual_checks(soup, browser=mode == "browser"))
            if mode == "static":
                result.limitations.append("O modo rápido não executa JavaScript. Conteúdos dinâmicos podem não ser identificados.")
            else:
                result.checks.append(Check("selenium", "Página com conteúdo dinâmico", Status.PRESENT,
                                           "Coleta concluída em navegador local com perfil temporário, antes de qualquer escolha de cookies."))
                cookies = result.browser.get("cookies", [])
                result.checks.append(Check("cookies", "Cookies observados no navegador", Status.PRESENT if cookies else Status.ABSENT,
                                          f"{len(cookies)} cookie(s) observado(s) nesta sessão. Valores não são armazenados. A finalidade não é inferida automaticamente.",
                                          [f"{c['name']} · {c['domain']}" for c in cookies[:30]]))
            candidates = find_policy(soup, page.url)
            if candidates:
                notify("Lendo a política de privacidade")
                policy_text, policy_source = self._read_policy(result, candidates, page.url, deadline, collector)
            result.checks.extend(policy_topics(policy_text))
        except AuditError as exc:
            result.checks = [Check("collection", "Acesso à página", Status.ERROR, str(exc))]
            for key, title in [("https", "Conexão HTTPS"), ("banner", "Banner de cookies"),
                               ("forms", "Formulários de dados pessoais"), ("policy", "Política de privacidade")]:
                result.checks.append(Check(key, title, Status.NOT_RUN, "A coleta falhou; não é possível concluir esta verificação."))
        if use_ai and policy_text and self.ai_client:
            notify("Interpretando a política com o Gemini")
            try:
                result.ai = self.ai_client.analyze(policy_text, policy_source)
                result.checks.append(Check("ai", "Interpretação com Gemini", Status.PRESENT,
                                           "Interpretação recebida. Apenas trechos presentes no texto enviado são aceitos como evidência; a IA não altera a nota."))
            except AuditError as exc:
                result.checks.append(Check("ai", "Interpretação com Gemini", Status.ERROR, str(exc)))
        else:
            detail = ("Não há texto de política disponível para enviar ao Gemini." if use_ai and not policy_text else
                      "Configure sua chave do Gemini nas configurações locais." if use_ai else
                      "IA desativada para esta análise. Nenhum texto foi enviado ao Gemini.")
            result.checks.append(Check("ai", "Interpretação com Gemini", Status.NOT_RUN, detail))
        notify("Calculando os indicadores e salvando o relatório")
        result.score = assessment(result)
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
