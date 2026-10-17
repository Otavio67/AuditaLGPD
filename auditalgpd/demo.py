"""Dados de exemplo explícitos; nunca executam coleta de rede."""

from .audit import LIMITATIONS, analyze_page
from .domain import AuditResult, Check, Status
from .assessment import assessment, policy_topics, contextual_checks
from .detectors import parse_html


def demo_result():
    html = '''<html><body><div id="cookie-banner">Utilizamos cookies <button>Aceitar</button></div>
    <form><input type="email" name="email"></form><a href="/privacidade">Política de privacidade</a></body></html>'''
    result = AuditResult("https://exemplo.com.br/", final_url="https://exemplo.com.br/", demo=True,
                         checks=analyze_page(html, "https://exemplo.com.br/", True), limitations=list(LIMITATIONS))
    result.checks.extend(contextual_checks(parse_html(html), browser=True))
    result.checks.append(Check("policy_content", "Acesso ao texto da política", Status.PRESENT, "Texto fictício para demonstração."))
    result.checks.extend(policy_topics("A finalidade é prestar serviços. Coletamos nome e e-mail. Compartilhamos dados com prestadores. Os direitos do titular incluem acesso, correção e exclusão. O controlador é Exemplo Ltda. Contato: privacidade@exemplo.com.br. As bases legais incluem execução de contrato."))
    result.checks.append(Check("ai", "Interpretação com Gemini", Status.NOT_RUN, "A demonstração não faz chamadas ao Google."))
    result.score = assessment(result)
    return result
