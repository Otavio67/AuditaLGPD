"""PDF vetorial com identidade visual, evidências e paginação consistente."""

from datetime import datetime
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
import reportlab
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    BaseDocTemplate, Flowable, Frame, KeepTogether, LongTable, PageBreak,
    PageTemplate, Paragraph, Spacer, Table, TableStyle,
)
from .assessment import assessment
from .presentation import display_check, plain_language


INK = colors.HexColor("#152b4b")
BLUE = colors.HexColor("#2365db")
MUTED = colors.HexColor("#5b6c82")
LINE = colors.HexColor("#dce5f0")
PALE = colors.HexColor("#f2f6fc")
WHITE = colors.white
GREEN = colors.HexColor("#13733b")
RED = colors.HexColor("#b52238")
STATE = {
    "presente": ("Identificado", GREEN, colors.HexColor("#e4f6eb")),
    "nao_identificado": ("Não identificado", RED, colors.HexColor("#ffedf0")),
    "erro": ("Erro na verificação", colors.HexColor("#885000"), colors.HexColor("#fff3db")),
    "nao_executado": ("Não executado", MUTED, colors.HexColor("#edf1f6")),
}

# Fontes livres incluídas pelo ReportLab; incorporadas no PDF para manter
# acentos e métricas iguais em Windows, Linux e leitores diferentes.
FONT_DIR = Path(reportlab.__file__).parent / "fonts"
for name, filename in [("AuditSans", "Vera.ttf"), ("AuditSans-Bold", "VeraBd.ttf"), ("AuditSans-Italic", "VeraIt.ttf")]:
    pdfmetrics.registerFont(TTFont(name, str(FONT_DIR/filename)))
pdfmetrics.registerFontFamily("AuditSans", normal="AuditSans", bold="AuditSans-Bold", italic="AuditSans-Italic", boldItalic="AuditSans-Bold")


def styles():
    body = ParagraphStyle("Body", fontName="AuditSans", fontSize=8.4, leading=13, textColor=INK, spaceAfter=6,
                          splitLongWords=True, allowWidows=0, allowOrphans=0)
    return {
        "body": body,
        "small": ParagraphStyle("Small", parent=body, fontSize=7.2, leading=10.5, textColor=MUTED, spaceAfter=4),
        "tiny": ParagraphStyle("Tiny", parent=body, fontSize=6.5, leading=9, textColor=MUTED, spaceAfter=0),
        "kicker": ParagraphStyle("Kicker", parent=body, fontName="AuditSans-Bold", fontSize=7, leading=11, textColor=BLUE, spaceAfter=8, keepWithNext=True),
        "title": ParagraphStyle("Title", parent=body, fontName="AuditSans-Bold", fontSize=25, leading=31, spaceAfter=8, keepWithNext=True),
        "section": ParagraphStyle("Section", parent=body, fontName="AuditSans-Bold", fontSize=14, leading=19, spaceBefore=14, spaceAfter=10, keepWithNext=True),
        "subhead": ParagraphStyle("Subhead", parent=body, fontName="AuditSans-Bold", fontSize=10, leading=14, spaceAfter=6, keepWithNext=True),
        "url": ParagraphStyle("URL", parent=body, fontSize=10, leading=15, textColor=BLUE, spaceAfter=12),
        "evidence": ParagraphStyle("Evidence", parent=body, fontSize=7.7, leading=11.8, textColor=MUTED, leftIndent=11, borderColor=LINE, borderWidth=1, borderPadding=7, spaceBefore=3, spaceAfter=8),
        "table": ParagraphStyle("TableCell", parent=body, fontSize=7.1, leading=10.2, spaceAfter=0),
        "table_head": ParagraphStyle("TableHead", parent=body, fontName="AuditSans-Bold", fontSize=6.5, leading=9, textColor=MUTED, spaceAfter=0),
        "status": ParagraphStyle("Status", parent=body, fontName="AuditSans-Bold", fontSize=6.7, leading=9.5, alignment=TA_CENTER, spaceAfter=0),
        "check_title": ParagraphStyle("CheckTitle", parent=body, fontName="AuditSans-Bold", fontSize=9, leading=13, spaceAfter=0),
        "index": ParagraphStyle("Index", parent=body, fontName="AuditSans-Bold", fontSize=9, leading=13, textColor=BLUE, spaceAfter=0),
    }


class ScorePanel(Flowable):
    def __init__(self, width, score):
        super().__init__()
        self.width, self.height, self.score = width, 108, score

    def draw(self):
        c, score, w, h = self.canv, self.score, self.width, self.height
        c.setFillColor(PALE)
        c.roundRect(0, 0, w, h, 9, fill=1, stroke=0)
        c.setFillColor(INK)
        c.roundRect(0, 0, 166, h, 9, fill=1, stroke=0)
        c.rect(156, 0, 10, h, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#c6d8f4"))
        c.setFont("AuditSans-Bold", 6.5)
        c.drawString(16, h-21, "SINAIS OBSERVÁVEIS")
        if score["value"] is None:
            c.setFont("AuditSans-Bold", 21)
            c.setFillColor(WHITE)
            c.drawString(16, 47, "Sem nota")
            c.setFont("AuditSans", 7)
            c.setFillColor(colors.HexColor("#c6d8f4"))
            c.drawString(16, 28, "Cobertura insuficiente")
        else:
            c.setFillColor(colors.HexColor("#9ee2b4") if score["value"] >= 75 else colors.HexColor("#ffd08b") if score["value"] >= 40 else colors.HexColor("#ffb2b9"))
            c.setFont("AuditSans-Bold", 40)
            c.drawString(15, 34, score["grade"])
            c.setFont("AuditSans-Bold", 22)
            c.drawString(61, 47, str(score["value"]))
            c.setFont("AuditSans", 9)
            c.drawString(61, 30, "de 100 pontos")
        c.setFont("AuditSans", 6)
        c.setFillColor(colors.HexColor("#c6d8f4"))
        c.drawString(16, 12, "Avaliação técnica preliminar")
        column = (w-166)/3
        metrics = [("COBERTURA", f"{score['coverage']}%", "dos pesos avaliados", BLUE),
                   ("IDENTIFICADOS", str(score["identified"]), "de 12 critérios", GREEN),
                   ("PARA REVISAR", str(len(score["missing"])), f"{len(score['pending'])} sem conclusão", RED)]
        for i, (label, value, caption, color) in enumerate(metrics):
            x = 166 + i*column + 14
            if i:
                c.setStrokeColor(LINE)
                c.line(x-14, 17, x-14, h-17)
            c.setFillColor(MUTED)
            c.setFont("AuditSans-Bold", 6.1)
            c.drawString(x, h-22, label)
            c.setFillColor(color)
            c.setFont("AuditSans-Bold", 27)
            c.drawString(x, 38, value)
            c.setFillColor(MUTED)
            c.setFont("AuditSans", 6.1)
            c.drawString(x, 20, caption)


class CategoryPanel(Flowable):
    def __init__(self, width, categories):
        super().__init__()
        self.width, self.height, self.categories = width, 94, categories

    def draw(self):
        c, gap = self.canv, 8
        width = (self.width-gap*(len(self.categories)-1))/max(1, len(self.categories))
        for i, group in enumerate(self.categories):
            x = i*(width+gap)
            c.setStrokeColor(LINE)
            c.setFillColor(WHITE)
            c.roundRect(x, 0, width, self.height, 6, stroke=1, fill=1)
            c.setFont("AuditSans-Bold", 6.6)
            c.setFillColor(MUTED)
            lines = ["Direitos e", "contato"] if group["name"] == "Direitos e contato" else [group["name"]]
            for line_index, line in enumerate(lines):
                c.drawString(x+10, self.height-17-9*line_index, line)
            c.setFont("AuditSans-Bold", 17)
            c.setFillColor(INK)
            c.drawString(x+10, 36, f"{group['percent']}%" if group["percent"] is not None else "-")
            c.setFillColor(PALE)
            c.roundRect(x+10, 24, width-20, 4, 2, stroke=0, fill=1)
            if group["percent"]:
                c.setFillColor(BLUE)
                c.roundRect(x+10, 24, (width-20)*group["percent"]/100, 4, 2, stroke=0, fill=1)
            c.setFillColor(MUTED)
            c.setFont("AuditSans", 5.9)
            caption = f"{group['earned']}/{group['assessed']} pontos" if group["assessed"] else "Sem avaliação"
            c.drawString(x+10, 11, caption)


def generate_pdf(audit):
    stream, s = BytesIO(), styles()
    left, bottom, top = 18*mm, 21*mm, 33*mm
    width = A4[0]-2*left
    doc = BaseDocTemplate(stream, pagesize=A4, leftMargin=left, rightMargin=left, topMargin=top, bottomMargin=bottom,
                          title="AuditaLGPD - Relatório de privacidade", author="AuditaLGPD")
    score = audit.score or assessment(audit)
    url = audit.final_url or audit.url
    date = datetime.fromisoformat(audit.created_at).astimezone().strftime("%d/%m/%Y às %H:%M")
    mode = "Análise avançada" if audit.mode == "browser" else "Análise simples"
    story = []

    def p(text, style="body"):
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), s[style])

    def section(number, title):
        story.append(p(f"{number:02d}  /  {title}", "section"))

    def notice(text, background=PALE):
        table = Table([[p(text, "small")]], colWidths=[width])
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), background),
                                   ("BOX", (0, 0), (-1, -1), .5, LINE),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 12), ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                                   ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
        return table

    def table(headers, rows, widths, compact=False):
        data = [[p(h, "table_head") for h in headers]] + [[p(c, "table") for c in row] for row in rows]
        result = LongTable(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
        result.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("BACKGROUND", (0, 0), (-1, 0), PALE),
                                   ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, colors.HexColor("#fafbfd")]),
                                   ("LINEBELOW", (0, 0), (-1, 0), .7, LINE), ("LINEBELOW", (0, 1), (-1, -1), .4, LINE),
                                   ("LEFTPADDING", (0, 0), (-1, -1), 9), ("RIGHTPADDING", (0, 0), (-1, -1), 9),
                                   ("TOPPADDING", (0, 0), (-1, -1), 4.5 if compact else 8),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 4.5 if compact else 8)]))
        return result

    def check_block(index, check):
        label, color, background = STATE.get(check.status, STATE["nao_executado"])
        badge_style = ParagraphStyle("Badge", parent=s["status"], textColor=color)
        head = Table([[p(f"{index:02d}", "index"), p(check.title, "check_title"), Paragraph(escape(label), badge_style)]],
                     colWidths=[36, width-153, 117])
        head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("BACKGROUND", (0, 0), (-1, -1), PALE),
                                 ("BACKGROUND", (2, 0), (2, 0), background), ("LINEBELOW", (0, 0), (-1, -1), .5, LINE),
                                 ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                                 ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
        beginning = [head, Spacer(1, 7), p(check.detail)]
        if check.evidence:
            beginning += [p("EVIDÊNCIA", "kicker"), p(check.evidence[0], "evidence")]
        story.append(KeepTogether(beginning))
        for evidence in check.evidence[1:]:
            story.append(p(evidence, "evidence"))
        story.append(Spacer(1, 9))

    def on_page(canvas, document):
        canvas.saveState()
        canvas.setFillColor(BLUE)
        canvas.roundRect(left, A4[1]-23*mm, 21, 23, 5, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("AuditSans-Bold", 13)
        canvas.drawCentredString(left+10.5, A4[1]-23*mm+6, "A")
        canvas.setFillColor(INK)
        canvas.setFont("AuditSans-Bold", 12)
        canvas.drawString(left+29, A4[1]-23*mm+7, "AuditaLGPD")
        canvas.setFillColor(MUTED)
        canvas.setFont("AuditSans", 6.7)
        canvas.drawRightString(A4[0]-left, A4[1]-23*mm+13, "RELATÓRIO DE PRIVACIDADE")
        canvas.drawRightString(A4[0]-left, A4[1]-23*mm+3, "ANÁLISE LOCAL  /  PROJETO ACADÊMICO")
        canvas.setStrokeColor(LINE)
        canvas.line(left, A4[1]-28*mm, A4[0]-left, A4[1]-28*mm)
        canvas.line(left, 16*mm, A4[0]-left, 16*mm)
        canvas.setFont("AuditSans", 6)
        canvas.drawString(left, 11*mm, "Diagnóstico preliminar. Não certifica conformidade com a LGPD.")
        canvas.setFont("AuditSans-Bold", 6.8)
        canvas.drawRightString(A4[0]-left, 11*mm, f"PÁGINA {document.page:02d}")
        canvas.restoreState()

    frame = Frame(left, bottom, width, A4[1]-top-bottom, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates(PageTemplate(id="report", frames=[frame], onPage=on_page))
    story += [p("DIAGNÓSTICO TÉCNICO PRELIMINAR", "kicker"), p("Relatório de privacidade", "title"),
              p("Uma visão dos sinais encontrados, dos pontos para revisar e dos limites desta análise.", "body"), p(url, "url")]
    meta = Table([[p("DATA DA ANÁLISE", "tiny"), p("MODALIDADE", "tiny"), p("TEMPO DE ANÁLISE", "tiny")],
                  [p(date, "small"), p("Demonstração" if audit.demo else mode, "small"), p(f"{audit.duration_ms/1000:.1f} segundos", "small")]],
                 colWidths=[width*.43, width*.32, width*.25])
    meta.setStyle(TableStyle([("LEFTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0),
                              ("BOTTOMPADDING", (0, 0), (-1, -1), 3), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story += [meta, Spacer(1, 13)]
    if audit.demo:
        story += [notice("DEMONSTRAÇÃO - dados fictícios para apresentar o relatório. Nenhum site foi consultado.", colors.HexColor("#fff6e2")), Spacer(1, 10)]
    story += [ScorePanel(width, score), Spacer(1, 12),
              notice("A nota resume apenas os critérios que puderam ser avaliados. Não representa aprovação jurídica do site. Itens sem conclusão não entram no cálculo; cobertura abaixo de 60% não gera nota."),
              p("Indicadores por assunto", "section"), CategoryPanel(width, score["categories"]), Spacer(1, 15)]
    if score["missing"]:
        summary = f"Comece pela revisão de {len(score['missing'])} critério(s) não identificado(s). As orientações e evidências estão nas próximas páginas."
    else:
        summary = "Não houve ausência nos critérios avaliados. Confira a cobertura e os itens ainda sem conclusão antes de interpretar o resultado."
    story += [p("COMO USAR ESTE RELATÓRIO", "kicker"), p(summary),
              p("Identificado = sinal encontrado. Não identificado = a busca não encontrou o sinal. Erro ou não executado = não há conclusão. Essas observações exigem conferência no contexto.", "small"),
              p(f"Registro: {audit.id}  |  Metodologia: {score['version']}", "tiny"), PageBreak()]

    section(1, "O que revisar e melhorar")
    if not score["missing"]:
        story.append(notice("Nenhuma ausência nos critérios avaliados. Isso não elimina a necessidade de revisão humana e de análise dos itens pendentes."))
    for index, item in enumerate(score["missing"], 1):
        story.append(KeepTogether([p(f"{index:02d}. {item['title']}", "subhead"), p(item["recommendation"]),
                                  p("Não identificado pela busca. Confirme a situação antes de alterar o site.", "small"), Spacer(1, 5)]))
    if score["pending"]:
        story.append(p("Itens que ainda precisam de avaliação", "subhead"))
        story.append(table(["CRITÉRIO", "ESTADO"], [(item["title"], STATE[item["status"]][0]) for item in score["pending"]], [width*.70, width*.30]))
    section(2, "Verificações e evidências")
    story.append(p("Os estados abaixo descrevem o que foi observado nesta coleta. Presença de cookies ou formulários não determina aprovação ou infração.", "small"))
    for index, saved_check in enumerate(audit.checks, 1):
        check_block(index, display_check(saved_check))

    next_section = 3
    if audit.browser:
        section(next_section, "Cookies e domínios observados")
        next_section += 1
        story.append(p("Observação antes de qualquer interação com o aviso. Valores dos cookies não são armazenados.", "small"))
        cookies = audit.browser.get("cookies", [])
        if cookies:
            story.append(table(["NOME / DOMÍNIO", "SECURE", "HTTPONLY", "SAMESITE"],
                               [(f"{c['name']}\n{c['domain']}", "Sim" if c.get("secure") else "Não", "Sim" if c.get("httpOnly") else "Não", c.get("sameSite", "Não informado")) for c in cookies],
                               [width*.49, width*.14, width*.16, width*.21]))
        else:
            story.append(p("Nenhum cookie observado nesta janela de coleta. Isso não comprova ausência em outras condições."))
        domains = audit.browser.get("domains", [])
        if domains:
            story += [p("Domínios conectados", "subhead"), p(" · ".join(domains), "evidence")]
        story.append(p("Não foram testadas as escolhas, o bloqueio ou a revogação. Uma conexão com outro domínio não comprova rastreamento.", "small"))
    if audit.ai:
        section(next_section, "Leitura assistida com Gemini")
        next_section += 1
        story += [notice(audit.ai.get("notice", "Interpretação complementar, sujeita a revisão humana.")),
                  p(f"Modelo: {audit.ai.get('model', '-')}  |  Caracteres enviados: {audit.ai.get('characters_sent', 0)}", "small")]
        if audit.ai.get("truncated"):
            story.append(p("O texto excedeu o limite; apenas um trecho da política foi enviado ao provedor.", "small"))
        ai_labels = {"identificado": "Trecho identificado", "nao_localizado": "Não localizado no trecho", "incerto": "Interpretação incerta"}
        for item in audit.ai.get("items", []):
            block = [p(item["title"], "subhead"), p(ai_labels.get(item["status"], "Revisão necessária"), "small"), p(item["explanation"])]
            if item.get("quote"):
                block.append(p(item["quote"], "evidence"))
            story += [KeepTogether(block), Spacer(1, 7)]

    story.append(PageBreak())
    section(next_section, "Metodologia e interpretação")
    story += [p(f"Rubrica {score['version']} - {score['earned']} pontos identificados de {score['assessed']} efetivamente avaliados. Os pesos completos somam 100 pontos."),
              p("Nota = 100 × pontos identificados / pesos avaliados. Erros e itens não executados ficam fora do denominador. Cobertura mínima: 60%. Escala: A de 90 a 100; B de 75 a 89; C de 60 a 74; D de 40 a 59; E abaixo de 40.", "small"),
              p("Pesos e faixas são decisões acadêmicas do projeto; não constituem uma escala oficial da ANPD. Termos isolados podem gerar falsos positivos, e outras redações podem gerar falsos negativos. A IA não altera a nota.", "small")]
    if not audit.score:
        story.append(notice("Registro anterior à rubrica: os indicadores foram calculados nesta exportação, sem alterar o histórico original."))
    story.append(table(["CRITÉRIO", "PESO", "RESULTADO"], [(item["title"], str(item["weight"]), STATE[item["status"]][0]) for item in score["items"]], [width*.56, width*.12, width*.32], compact=True))
    story += [Spacer(1, 8), p("O que depende de revisão humana", "subhead")]
    for index, item in enumerate(score["manual"], 1):
        story.append(p(f"{index:02d}. {item}", "small"))
    story += [Spacer(1, 8), p("Limites desta análise", "subhead")]
    for item in audit.limitations:
        story.append(p(plain_language(item), "small"))
    story += [p("REFERÊNCIAS PARA A AVALIAÇÃO HUMANA", "kicker"),
              p("LGPD - Lei nº 13.709/2018, texto oficial no Portal Planalto. Guia orientativo Cookies e proteção de dados pessoais, da ANPD. A rubrica é própria do AuditaLGPD.", "small")]
    doc.build(story)
    stream.seek(0)
    return stream
