"""Rubrica acadêmica explícita; não é uma escala publicada pela ANPD."""

import re
import unicodedata
from .domain import Check, Status
from .detectors import visible, detect_banner


def fold(text):
    return "".join(c for c in unicodedata.normalize("NFD", text.lower()) if unicodedata.category(c) != "Mn")


# key, título, categoria, peso, orientação. A soma dos pesos é 100.
RULES = [
    ("https", "Conexão HTTPS", "Segurança", 10, "Disponibilize a página em HTTPS com certificado válido e redirecione os acessos HTTP."),
    ("policy", "Link de política", "Transparência", 10, "Disponibilize um link visível e descritivo para a política de privacidade."),
    ("policy_content", "Política acessível", "Transparência", 5, "Verifique se o link permite acessar o texto da política sem autenticação."),
    ("purposes", "Finalidades do tratamento", "Transparência", 10, "Explique para quais finalidades cada atividade utiliza dados pessoais."),
    ("data_types", "Categorias de dados", "Transparência", 5, "Informe quais dados são coletados e como são obtidos."),
    ("sharing", "Compartilhamento de dados", "Transparência", 10, "Explique o compartilhamento com terceiros e suas finalidades, ou declare sua ausência quando isso for verdadeiro."),
    ("retention", "Retenção e eliminação", "Transparência", 5, "Informe os prazos ou critérios de retenção e as condições de eliminação dos dados."),
    ("rights", "Direitos dos titulares", "Direitos e contato", 10, "Explique os direitos dos titulares e o procedimento para exercê-los."),
    ("controller", "Responsável e canal de contato", "Direitos e contato", 10, "Identifique o controlador e disponibilize um canal de atendimento de privacidade, considerando as regras aplicáveis ao encarregado."),
    ("legal_basis", "Explicação das bases legais", "Transparência", 5, "Associe as operações de tratamento às bases legais aplicáveis. Consentimento não é a única base legal."),
    ("cookie_choices", "Escolhas no aviso de cookies", "Cookies", 10, "Quando aplicável, ofereça escolhas claras para aceitar, rejeitar e configurar cookies. Confirme manualmente se elas funcionam."),
    ("form_notice", "Informação próxima ao formulário", "Formulários", 10, "Explique o uso dos dados junto ao formulário e ofereça acesso à política de privacidade. Não imponha consentimento como base para toda coleta."),
]

PATTERNS = {
    "purposes": r"finalidade|para que utilizamos|como utilizamos|usamos seus dados|purpose",
    "data_types": r"dados (?:pessoais )?(?:coletados|que coletamos)|coletamos.{0,90}(?:nome|email|e-mail|telefone|endereco|ip)|information we collect",
    "sharing": r"compartilh|sharing|share.{0,50}(?:data|information)|nao.{0,30}vendemos",
    "retention": r"retencao|armazenad[oa]s? por|periodo de (?:armazenamento|conservacao)|eliminacao.{0,70}dados|retention",
    "rights": r"direitos (?:dos? |do titular|de voce)|direito.{0,70}(?:acesso|correcao|exclusao|portabilidade)|your rights",
    "legal_basis": r"bas(?:e|es) lega(?:l|is)|legitimo interesse|execucao de contrato|obrigacao legal|legal bas(?:is|es)",
}

MANUAL_REVIEW = [
    "Confirmar a necessidade dos dados e a base legal de cada operação; verificar tratamentos de dados sensíveis e de crianças/adolescentes quando existentes.",
    "Verificar se as declarações da política correspondem à prática, inclusive compartilhamento, operadores e transferências internacionais.",
    "Testar aceitar, rejeitar, configurar e revogar cookies; classificar suas finalidades e verificar bloqueio antes da escolha, quando aplicável.",
    "Testar o atendimento aos direitos dos titulares e verificar as obrigações aplicáveis ao encarregado e eventuais dispensas.",
    "Avaliar controles internos de segurança, acessos, retenção, eliminação, contratos e resposta a incidentes.",
    "Verificar registros de tratamento, responsabilização e relatórios de impacto quando cabíveis.",
]


def policy_topics(text, unavailable=Status.NOT_RUN):
    """Sinais lexicais com trecho literal; não valida a suficiência jurídica."""
    flat = re.sub(r"\s+", " ", text).strip()
    normalized = fold(flat)
    checks = []
    for key, title, _, _, _ in RULES:
        if key not in {*PATTERNS, "controller"}:
            continue
        match = re.search(PATTERNS.get(key, r"controlador|responsavel pelo tratamento|data controller"), normalized)
        if key == "controller":
            contact = re.search(r"encarregado|\bdpo\b|[\w.+-]+@[\w.-]+\.[a-z]{2,}|canal.{0,40}(?:contato|atendimento)", normalized)
            match = match if match and contact else None
        status = (Status.PRESENT if match else Status.ABSENT) if flat else unavailable
        excerpt = flat[max(0, match.start()-55):match.end()+135] if match else ""
        detail = ("Foram encontrados termos relacionados a este tema. O trecho precisa ser conferido no contexto." if match else
                  "Não foram encontrados os termos previstos pela heurística neste texto. Outra redação pode gerar falso negativo.") if flat else "O texto da política não pôde ser avaliado; este item não entra no cálculo."
        checks.append(Check(key, title, status, detail, [excerpt] if excerpt else []))
    return checks


def contextual_checks(soup, browser=False):
    forms = [f for f in soup.find_all("form") if visible(f)]
    def personal(form):
        return any(c.get("type", "text").lower() not in {"hidden", "search", "submit", "button", "checkbox", "radio"} and
                   (c.get("type", "text").lower() in {"email", "tel", "password"} or
                    re.search(r"nome|name|cpf|email|telefone|phone|birth|endereco|address", " ".join(str(c.get(a, "")) for a in ["name", "id", "autocomplete"]), re.I))
                   for c in form.find_all("input") if visible(c))
    personal_forms = [f for f in forms if personal(f)]
    notices = [f for f in personal_forms if re.search(r"privacidade|privacy|dados pessoais", f.get_text(" ", strip=True), re.I)]
    form_status = Status.PRESENT if len(notices) == len(personal_forms) else Status.ABSENT
    if not personal_forms:
        form_status = Status.NOT_RUN
    form_check = Check("form_notice", "Informação próxima ao formulário", form_status,
                       f"Há referência à privacidade em {len(notices)}/{len(personal_forms)} formulário(s) de dados pessoais identificado(s). Avalie clareza e finalidade." if form_status == Status.PRESENT else
                       f"Referência à privacidade localizada em {len(notices)}/{len(personal_forms)} formulário(s) com indícios de coleta." if personal_forms else
                       "Não foi identificado formulário de dados pessoais; aplicabilidade pendente de revisão.")
    banners = []
    for el in soup.find_all(["div", "aside", "section", "dialog"]):
        identity = str(el.get("id", "")) + " " + " ".join(el.get("class", []))
        if visible(el) and re.search(r"cookie|consent", identity, re.I):
            banners.append(el)
    controls = " ".join(fold(b.get_text(" ", strip=True)) for banner in banners for b in banner.find_all(["button", "a", "input"]) if visible(b))
    kinds = [("aceitar", r"aceit|accept|permitir todos"), ("rejeitar", r"rejeit|recus|reject|necessarios|deny"),
             ("configurar", r"configur|preferenc|personaliz|settings|manage")]
    found = [label for label, pattern in kinds if re.search(pattern, controls)]
    choices = len(found) == len(kinds)
    # A ausência do banner não permite inferir sua obrigatoriedade.
    status = (Status.PRESENT if choices else Status.ABSENT) if banners and browser and detect_banner(soup).status == Status.PRESENT else Status.NOT_RUN
    cookie_check = Check("cookie_choices", "Escolhas no aviso de cookies", status,
                         "Foram localizados controles de aceitar, rejeitar e configurar. Não houve clique nem teste de bloqueio/revogação." if status == Status.PRESENT else
                         "Não foram localizados os três tipos de controle no aviso observado. Verifique sua aplicabilidade e funcionamento." if status == Status.ABSENT else
                         "Exige um aviso observado no navegador e análise de aplicabilidade. A ausência de banner não implica irregularidade.",
                         found if status == Status.ABSENT else [])
    return [form_check, cookie_check]


def assessment(audit):
    indexed = {c.key: c for c in audit.checks}
    categories = {}
    items, earned, assessed = [], 0, 0
    for key, title, category, weight, recommendation in RULES:
        check = indexed.get(key)
        status = check.status if check else Status.NOT_RUN
        observed = status in {Status.PRESENT, Status.ABSENT}
        passed = status == Status.PRESENT
        # Crédito parcial: 1/3 do peso por controle de cookie encontrado (aceitar, rejeitar, configurar).
        partial = round(weight * len(check.evidence) / 3) if key == "cookie_choices" and status == Status.ABSENT and check else 0
        row = {"key": key, "title": title, "category": category, "weight": weight, "status": status,
               "recommendation": recommendation, "detail": check.detail if check else "Item não avaliado nesta coleta.",
               "evidence": check.evidence if check else [], "partial": partial}
        items.append(row)
        group = categories.setdefault(category, {"name": category, "earned": 0, "assessed": 0, "total": 0})
        group["total"] += weight
        if observed:
            assessed += weight
            group["assessed"] += weight
        if passed:
            earned += weight
            group["earned"] += weight
        elif partial:
            earned += partial
            group["earned"] += partial
    # Com cobertura suficiente, a nota é a média dos pesos avaliados. Com cobertura baixa,
    # os pontos não avaliados contam como zero: a nota vira um piso, sem parecer completa.
    if not assessed:
        value = None
    elif assessed >= 60:
        value = round(100 * earned / assessed)
    else:
        value = round(earned)
    limited = 0 < assessed < 60
    for group in categories.values():
        group["percent"] = round(100 * group["earned"] / group["assessed"]) if group["assessed"] else None
    # Melhorias ordenadas pelo ganho de pontos: o peso do critério menos o crédito parcial já obtido.
    improvements = sorted(
        [{"key": i["key"], "title": i["title"], "category": i["category"], "weight": i["weight"],
          "gain": i["weight"] - i["partial"], "severity": "alta" if i["weight"] - i["partial"] >= 10 else "media",
          "recommendation": i["recommendation"], "detail": i["detail"], "evidence": i["evidence"]}
         for i in items if i["status"] == Status.ABSENT],
        key=lambda item: (-item["gain"], item["title"]))
    potential_earned = earned + sum(item["gain"] for item in improvements)
    potential_value = None if not assessed else (round(100 * potential_earned / assessed) if assessed >= 60 else round(potential_earned))
    return {"value": value, "grade": grade_for(value), "earned": earned, "assessed": assessed, "total": 100,
            "coverage": assessed, "limited": limited, "categories": list(categories.values()), "items": items,
            "missing": [i for i in items if i["status"] == Status.ABSENT],
            "pending": [i for i in items if i["status"] not in {Status.PRESENT, Status.ABSENT}],
            "improvements": improvements,
            "potential": {"value": potential_value, "grade": grade_for(potential_value), "gain": potential_earned - earned},
            "identified": sum(i["status"] == Status.PRESENT for i in items), "manual": MANUAL_REVIEW,
            "version": "observaveis-1.0"}


def grade_for(value):
    return next((letter for floor, letter in [(90, "A"), (75, "B"), (60, "C"), (40, "D"), (0, "E")] if value is not None and value >= floor), "—")
