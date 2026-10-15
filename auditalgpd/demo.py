"""Dados de exemplo explícitos; nunca executam coleta de rede."""

from .audit import LIMITATIONS, analyze_page
from .domain import AuditResult, Check, Status


def demo_result():
    html = '''<html><body><div id="cookie-banner">Utilizamos cookies <button>Aceitar</button></div>
    <form><input type="email" name="email"></form><a href="/privacidade">Política de privacidade</a></body></html>'''
    result = AuditResult("https://exemplo.com.br/", final_url="https://exemplo.com.br/", demo=True,
                         checks=analyze_page(html, "https://exemplo.com.br/", True), limitations=list(LIMITATIONS))
    result.checks.append(Check("ai", "Análise com inteligência artificial", Status.NOT_RUN, "Integração com IA ainda não implementada."))
    return result
