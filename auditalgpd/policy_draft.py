"""Rascunho de política de privacidade montado com o que a análise observou no site.

Não consulta a internet nem envia dados a terceiros: usa só o resultado já salvo
(formulários, cookies sem valores, domínios conectados e critérios não identificados).
O texto é um ponto de partida e exige revisão humana e jurídica.
"""

from datetime import datetime
import re
from urllib.parse import urlsplit

LIMIT = 60  # o rascunho só é oferecido quando a nota fica abaixo disto

# Prefixos/nomes de cookies conhecidos -> (categoria, descrição). Classificação por nome, sem inferir finalidade real.
COOKIE_RULES = [
    (r"^(_ga|_gid|_gat|_gac_)", "Estatística", "Google Analytics"),
    (r"^(_clck|_clsk|clid|sm|muid|anonymousid)$", "Estatística", "Microsoft Clarity / Bing"),
    (r"^_hj", "Estatística", "Hotjar"),
    (r"^(_gcl_|ide|anid|test_cookie|dsid)", "Publicidade", "Google Ads / DoubleClick"),
    (r"^(_fbp|_fbc|fr)$", "Publicidade", "Meta (Facebook/Instagram)"),
    (r"^(_ttp|_tt_)", "Publicidade", "TikTok"),
    (r"^(phpsessid|wordpress_|wp-settings|wp_|cookieyes|cky|cookielawinfo|viewed_cookie_policy|__cf_bm|cf_clearance|csrf|session|_csrf)", "Necessário", "funcionamento do site e registro da sua escolha de cookies"),
]

# Domínios conhecidos -> descrição para a lista de terceiros.
DOMAIN_RULES = [
    (r"(google-analytics|analytics\.google|googletagmanager)\.", "Google (análise de audiência / gerenciador de tags)"),
    (r"(doubleclick|googleadservices|googlesyndication)\.", "Google Ads (publicidade)"),
    (r"(googleapis|gstatic)\.com$", "Google (fontes, bibliotecas e recursos)"),
    (r"(youtube|ytimg|youtube-nocookie)\.", "YouTube (vídeos incorporados)"),
    (r"clarity\.ms$", "Microsoft Clarity (análise de uso)"),
    (r"(facebook|fbcdn|instagram)\.", "Meta (Facebook/Instagram)"),
    (r"hotjar\.", "Hotjar (análise de uso)"),
    (r"(cloudflare|cloudflareinsights)\.", "Cloudflare (desempenho e segurança)"),
    (r"(wp\.com|wordpress\.com|gravatar\.com)$", "WordPress / Automattic"),
    (r"(whatsapp|wa\.me)", "WhatsApp (contato)"),
    (r"(linkedin|licdn)\.", "LinkedIn"),
]

# Onde o rascunho responde a cada critério da rubrica que não foi identificado.
CRITERIA_MAP = {
    "policy": "Checklist no fim deste arquivo: publique o texto em uma página pública e coloque o link no rodapé de todas as páginas.",
    "policy_content": "Publique este texto em uma página acessível sem login.",
    "purposes": "Seção 3 (finalidades).",
    "data_types": "Seção 2 (dados que coletamos).",
    "sharing": "Seção 5 (compartilhamento).",
    "retention": "Seção 6 (prazos de guarda).",
    "rights": "Seção 7 (direitos do titular).",
    "controller": "Seções 1 e 10 (controlador e canal de contato).",
    "legal_basis": "Seção 3 (bases legais de cada finalidade).",
    "cookie_choices": "Seção 4 (cookies): descreva e ofereça aceitar, rejeitar e configurar no aviso do site.",
    "form_notice": "Texto curto para colocar ao lado do formulário, no fim deste arquivo.",
}


def eligible(score):
    """Só para nota baixa; sem nota (nada avaliado) também não há base para personalizar."""
    return score.get("value") is not None and score["value"] < LIMIT


def host_of(audit):
    host = (urlsplit(audit.final_url or audit.url).hostname or "site").lower()
    return host[4:] if host.startswith("www.") else host


def filename(audit):
    return "politica-de-privacidade-" + re.sub(r"[^a-z0-9.-]", "-", host_of(audit)) + ".txt"


def classify_cookie(name):
    lowered = name.lower()
    for pattern, category, source in COOKIE_RULES:
        if re.search(pattern, lowered):
            return category, source
    return "Não classificado", "finalidade a confirmar com quem administra o site"


def describe_domain(domain):
    for pattern, label in DOMAIN_RULES:
        if re.search(pattern, domain):
            return label
    return None


def form_fields(audit):
    labels = {"email": "e-mail", "tel": "telefone", "password": "senha de acesso", "identificação/contato": "nome e dados de contato"}
    found = []
    for check in audit.checks:
        if check.key == "forms":
            for line in check.evidence:
                for raw, label in labels.items():
                    if raw in line and label not in found:
                        found.append(label)
    return found


def build_policy_draft(audit, score):
    host = host_of(audit)
    cookies = (audit.browser or {}).get("cookies", [])
    domains = (audit.browser or {}).get("domains", [])
    fields = form_fields(audit)
    date = datetime.fromisoformat(audit.created_at).astimezone().strftime("%d/%m/%Y")
    missing = [i for i in score.get("items", []) if i["status"] == "nao_identificado"]
    out = []
    add = out.append

    add(f"RASCUNHO DE POLÍTICA DE PRIVACIDADE - {host}")
    add(f"Gerado pelo AuditaLGPD em {date}, a partir da análise de https://{host}/.")
    add("")
    add("AVISO IMPORTANTE")
    add("Este texto é um ponto de partida montado com o que a análise observou neste site. Ele não é consultoria jurídica")
    add("e pode não refletir tudo o que a empresa faz com dados pessoais. Troque os trechos entre [COLCHETES] pelos dados reais,")
    add("apague o que não se aplica, inclua o que falta e peça a revisão de um profissional antes de publicar.")
    add("")
    if missing:
        add("O QUE A ANÁLISE APONTOU E ONDE ESTE RASCUNHO RESPONDE")
        for item in missing:
            add(f"- {item['title']}: {CRITERIA_MAP.get(item['key'], 'Ver seções deste rascunho.')}")
        add("")
    add("=" * 72)
    add("")
    add("1. QUEM SOMOS (CONTROLADOR DOS DADOS)")
    add(f"O site {host} é administrado por [NOME EMPRESARIAL], inscrita no CNPJ/CPF [NÚMERO], com sede em [ENDEREÇO COMPLETO].")
    add("Essa organização é a controladora dos dados pessoais tratados por meio deste site, nos termos da Lei Geral de Proteção de Dados (Lei nº 13.709/2018, a LGPD).")
    add("")
    add("2. DADOS PESSOAIS QUE COLETAMOS")
    add("a) Dados de navegação: endereço IP, tipo de navegador e dispositivo, páginas acessadas, data e hora do acesso. São registrados automaticamente quando você visita o site.")
    if fields:
        add(f"b) Dados que você informa em formulários: {', '.join(fields)}. Coletamos apenas o necessário para responder à sua solicitação.")
    else:
        add("b) Dados que você informa: o site não apresentou formulário de coleta na página analisada. Se houver outros canais (e-mail, WhatsApp, cadastro, compras), liste aqui os dados recebidos: [DADOS].")
    if cookies:
        add("c) Dados coletados por cookies e tecnologias semelhantes, descritos na seção 4.")
    add("Não pedimos dados pessoais sensíveis. [Se pedir, informe quais e a base legal específica.]")
    add("")
    add("3. PARA QUE USAMOS SEUS DADOS (FINALIDADES) E EM QUE BASE LEGAL")
    add("Cada finalidade abaixo precisa ter uma base legal (art. 7º da LGPD). As sugeridas são as mais comuns; confirme a adequada para o seu caso.")
    add("- Fazer o site funcionar e mantê-lo seguro (dados de navegação). Base sugerida: legítimo interesse (art. 7º, IX).")
    if fields:
        add("- Responder a contatos e pedidos feitos pelo formulário. Base sugerida: procedimentos preliminares a contrato, se o contato for sobre contratar (art. 7º, V), ou legítimo interesse (art. 7º, IX).")
    categories = {classify_cookie(c["name"])[0] for c in cookies}
    if "Estatística" in categories:
        add("- Entender como o site é usado e melhorá-lo (cookies estatísticos). Base sugerida: consentimento (art. 7º, I), pedido no aviso de cookies antes de ativar.")
    if "Publicidade" in categories:
        add("- Medir e personalizar anúncios (cookies de publicidade). Base sugerida: consentimento (art. 7º, I), pedido no aviso de cookies antes de ativar.")
    add("- Cumprir obrigações legais ou regulatórias, quando houver. Base: obrigação legal (art. 7º, II).")
    add("[Inclua aqui outras finalidades reais: envio de newsletter, cadastro de clientes, vendas, suporte etc.]")
    add("O consentimento não é a única base legal: use-o apenas quando for a base adequada, e permita que você o retire quando quiser.")
    add("")
    add("4. COOKIES E TECNOLOGIAS SEMELHANTES")
    if cookies:
        add(f"Na análise feita em {date}, antes de qualquer interação com o aviso, foram observados {len(cookies)} cookie(s). A classificação abaixo é pelo nome e deve ser confirmada:")
        for cookie in cookies[:40]:
            category, source = classify_cookie(cookie["name"])
            add(f"- {cookie['name']} ({cookie['domain']}): {category} - {source}.")
        if len(cookies) > 40:
            add(f"- ... e mais {len(cookies) - 40} cookie(s).")
        add("Cookies estatísticos e de publicidade só devem ser ativados depois da sua escolha no aviso de cookies.")
    else:
        add("A análise não observou cookies nesta página. Se o site usar cookies ou ferramentas de terceiros em outras páginas, liste-os aqui por categoria (necessários, estatísticos, publicidade).")
    add("Você pode aceitar, rejeitar ou configurar os cookies no aviso exibido no site e alterar sua escolha depois pelo link [LINK/BOTÃO DE PREFERÊNCIAS DE COOKIES]. Também pode apagar cookies nas configurações do navegador; algumas funções do site podem deixar de funcionar.")
    add("")
    add("5. COMPARTILHAMENTO DE DADOS")
    known = []
    unknown = []
    for domain in domains:
        label = describe_domain(domain)
        if label and label not in known:
            known.append(label)
        elif not label and domain != host and not domain.endswith("." + host):
            unknown.append(domain)
    if known or unknown:
        add("Ao carregar o site, seu navegador se conecta a serviços de terceiros que podem receber dados técnicos, como o endereço IP:")
        for label in known:
            add(f"- {label}.")
        if unknown:
            add(f"- Outros domínios observados (identifique o responsável por cada um antes de publicar): {', '.join(sorted(unknown)[:15])}.")
    else:
        add("Não observamos conexões com serviços de terceiros na análise. Se o site usar hospedagem, e-mail, CRM, pagamentos ou outras ferramentas, liste-as aqui: [OPERADORES].")
    add("Não vendemos seus dados pessoais. Compartilhamos apenas quando necessário para as finalidades acima, com empresas que nos prestam serviços (operadores) ou por exigência legal. [Confirme que isso é verdadeiro para a sua empresa.]")
    add("Se algum serviço estiver em outro país, informe: [TRANSFERÊNCIA INTERNACIONAL E GARANTIAS].")
    add("")
    add("6. POR QUANTO TEMPO GUARDAMOS SEUS DADOS")
    add("- Dados de navegação (registros de acesso): [PRAZO, por exemplo 6 meses]. Obs.: o Marco Civil da Internet exige guarda mínima de registros de acesso para provedores de aplicações; confirme se se aplica.")
    if fields:
        add("- Dados enviados em formulários: pelo tempo necessário para atender sua solicitação e por [PRAZO] depois, para eventual defesa em processos.")
    if cookies:
        add("- Cookies: conforme o prazo de cada cookie, informado na tabela da seção 4 quando disponível: [PRAZOS].")
    add("Depois desses prazos, os dados são eliminados ou anonimizados, salvo se a lei exigir a guarda por mais tempo.")
    add("")
    add("7. SEUS DIREITOS")
    add("Pela LGPD (art. 18), você pode pedir, a qualquer momento: confirmação de que tratamos seus dados; acesso; correção de dados incompletos ou desatualizados;")
    add("anonimização, bloqueio ou eliminação de dados desnecessários ou tratados fora da lei; portabilidade; eliminação dos dados tratados com consentimento;")
    add("informação sobre com quem compartilhamos seus dados; informação sobre a possibilidade de não consentir e suas consequências; e a revogação do consentimento.")
    add("Para exercer esses direitos, escreva para [E-MAIL DE PRIVACIDADE]. Responderemos em até [PRAZO, por exemplo 15 dias]. Você também pode reclamar à Autoridade Nacional de Proteção de Dados (ANPD).")
    add("")
    add("8. SEGURANÇA")
    if audit.checks and any(c.key == "https" and c.status == "presente" for c in audit.checks):
        add("O site usa conexão criptografada (HTTPS) com certificado válido, o que protege os dados em trânsito.")
    else:
        add("[Atenção: a análise não confirmou HTTPS com certificado válido. Ative HTTPS antes de publicar esta política.]")
    add("Adotamos medidas técnicas e administrativas para proteger seus dados contra acesso não autorizado, perda e alteração: [DESCREVA, por exemplo controle de acessos, backups, atualizações]. Em caso de incidente que possa causar risco relevante a você, comunicaremos você e a ANPD, conforme a lei.")
    add("")
    add("9. CRIANÇAS E ADOLESCENTES")
    add("Este site [não é direcionado a menores de 18 anos / é direcionado a ... e trata seus dados com o consentimento de um responsável legal]. Escolha a frase que vale para o seu caso.")
    add("")
    add("10. CONTATO E ENCARREGADO PELA PROTEÇÃO DE DADOS")
    add("Para dúvidas sobre esta política ou sobre seus dados, fale com [NOME DO ENCARREGADO OU RESPONSÁVEL] pelo e-mail [E-MAIL DE PRIVACIDADE]. [Se a empresa for dispensada de indicar encarregado, informe apenas o canal de atendimento.]")
    add("")
    add("11. ALTERAÇÕES")
    add("Podemos atualizar esta política. A data da última atualização aparece no fim desta página e mudanças relevantes serão informadas no site.")
    add("")
    add("Última atualização: [DATA]")
    add("")
    add("=" * 72)
    if fields:
        add("")
        add("TEXTO CURTO PARA COLOCAR AO LADO DO FORMULÁRIO")
        add(f"\"Usaremos {', '.join(fields)} apenas para responder à sua solicitação. Saiba mais na nossa Política de Privacidade [LINK].\"")
    add("")
    add("CHECKLIST ANTES DE PUBLICAR")
    add("[ ] Substituí todos os [COLCHETES] e apaguei o que não se aplica.")
    add("[ ] Conferi se cada cookie e serviço listado realmente é usado, e incluí os que faltam.")
    add("[ ] Publiquei em uma página pública (por exemplo /politica-de-privacidade/) e coloquei o link no rodapé de todas as páginas.")
    add("[ ] O aviso de cookies tem aceitar, rejeitar e configurar, e cookies não essenciais só rodam depois da escolha.")
    add("[ ] Um profissional revisou o texto.")
    return "\n".join(out) + "\n"
