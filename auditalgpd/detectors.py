"""Heurísticas de HTML estático; presença não equivale à adequação legal."""

import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .domain import Check, Status, public_url


def parse_html(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "template"]):
        tag.decompose()
    return soup


def visible(tag):
    for item in [tag, *tag.parents]:
        if not getattr(item, "attrs", None):
            continue
        if item.has_attr("hidden") or str(item.get("aria-hidden", "")).lower() == "true":
            return False
        if re.search(r"(?:display\s*:\s*none|visibility\s*:\s*hidden)", item.get("style", ""), re.I):
            return False
    return True


def detect_banner(soup):
    for tag in soup.find_all(["div", "aside", "section", "dialog"]):
        identity = str(tag.get("id", "")) + " " + " ".join(tag.get("class", []))
        if not visible(tag) or not re.search(r"cookie|consent", identity, re.I):
            continue
        text = tag.get_text(" ", strip=True)
        if re.search(r"cookie|consentimento|consent", text, re.I) and (tag.find(["button", "input"]) or tag.get("role") == "dialog" or tag.name == "dialog"):
            return Check("banner", "Banner de cookies", Status.PRESENT,
                         "Há indícios de um mecanismo de cookies no HTML recebido. Seu comportamento não foi validado.",
                         ["Elemento identificado por atributo de cookies/consentimento e controle de interação."])
    return Check("banner", "Banner de cookies", Status.ABSENT,
                 "Não identificado no HTML recebido. Um banner pode depender de JavaScript ou das condições de acesso.")


def detect_forms(soup):
    found = []
    for form in soup.find_all("form"):
        if not visible(form):
            continue
        types = set()
        for control in form.find_all(["input", "textarea"]):
            kind = str(control.get("type", "text")).lower()
            name = str(control.get("name", "")) + " " + str(control.get("id", "")) + " " + str(control.get("autocomplete", ""))
            if kind in {"hidden", "search", "submit", "button", "checkbox", "radio"} or not visible(control):
                continue
            if kind in {"email", "tel", "password"}:
                types.add(kind)
            elif re.search(r"email|e-mail|telefone|phone|cpf|cnpj|nascimento|birth|address|endereco|endereço|(?:^|[-_ ])(?:nome|name)(?:$|[-_ ])", name, re.I):
                types.add("identificação/contato")
        if types:
            found.append("Campos com indícios de dados pessoais: " + ", ".join(sorted(types)) + ".")
    return Check("forms", "Formulários de dados pessoais", Status.PRESENT if found else Status.ABSENT,
                 f"{len(found)} formulário(s) com indícios de coleta. Nenhum campo foi preenchido ou enviado." if found else
                 "Não foram identificados campos típicos de dados pessoais no HTML recebido.", found[:5])


def find_policy(soup, base_url):
    candidates = []
    for link in soup.find_all("a", href=True):
        if visible(link) and re.search(r"privacidade|privacy\s*policy|proteção de dados|protecao de dados", link.get_text(" ", strip=True), re.I):
            value = urljoin(base_url, link["href"])
            if value not in candidates:
                candidates.append(value)
    return candidates[:3]


def policy_check(candidates):
    return Check("policy", "Link de política de privacidade", Status.PRESENT if candidates else Status.ABSENT,
                 "Foi identificado um link com indicação de política. A presença do link não comprova adequação do conteúdo." if candidates else
                 "Não foi identificado um link de política pelos critérios textuais utilizados.",
                 [public_url(url) for url in candidates])
