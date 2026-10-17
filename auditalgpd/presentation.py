"""Linguagem da interface, inclusive para relatórios históricos."""

from dataclasses import replace
import re


def plain_language(text):
    return re.sub(r"\bselenium\b", "análise avançada", str(text), flags=re.I)


def display_check(check):
    return replace(check,
                   title="Página com conteúdo dinâmico" if check.key == "selenium" else plain_language(check.title),
                   detail=plain_language(check.detail))
