"""Relatório com rubrica, evidências e interpretação opcional separada."""

from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from .assessment import assessment

LABELS = {"presente": "Identificado", "nao_identificado": "Não identificado", "erro": "Erro na verificação", "nao_executado": "Não executado"}


def generate_pdf(audit):
    stream = BytesIO()
    styles = getSampleStyleSheet()
    styles["Heading2"].keepWithNext = True
    styles.add(ParagraphStyle(name="BodyPT", fontName="Helvetica", fontSize=10, leading=15, spaceAfter=9, textColor=colors.HexColor("#29443b"), splitLongWords=True))
    doc = SimpleDocTemplate(stream, pagesize=A4, rightMargin=22*mm, leftMargin=22*mm, topMargin=22*mm, bottomMargin=22*mm,
                            title="AuditaLGPD - Diagnóstico técnico preliminar", author="AuditaLGPD")
    story = []

    def paragraph(text, style="BodyPT"):
        story.append(Paragraph(escape(str(text)), styles[style]))

    paragraph("AuditaLGPD", "Title")
    paragraph("Diagnóstico técnico preliminar", "Heading2")
    paragraph("URL: " + (audit.final_url or audit.url))
    paragraph("Registro: " + audit.id)
    paragraph("Data (ISO 8601): " + audit.created_at)
    paragraph(f"Duração: {audit.duration_ms / 1000:.2f} segundos")
    if audit.demo:
        paragraph("DEMONSTRAÇÃO: dados de exemplo; nenhuma consulta real foi realizada.")
    score = audit.score or assessment(audit)
    paragraph("Indicadores de sinais observáveis", "Heading2")
    paragraph(f"Nota: {str(score['value']) + '/100' if score['value'] is not None else 'não atribuída (cobertura insuficiente)'} · Letra: {score['grade']}")
    paragraph(f"Cobertura: {score['coverage']}% · Pontos identificados: {score['earned']}/{score['assessed']} avaliados · Rubrica: {score['version']}")
    paragraph("A nota não representa conformidade jurídica. Itens sem avaliação não entram no denominador. É necessário pelo menos 60% de cobertura para atribuir nota. Escala acadêmica: A >= 90; B >= 75; C >= 60; D >= 40; E < 40.")
    if not audit.score:
        paragraph("Registro anterior à rubrica: cálculo realizado para esta exportação, sem alterar o registro histórico.")
    paragraph("O que revisar e melhorar", "Heading2")
    for item in score["missing"]:
        paragraph(item["title"] + ": " + item["recommendation"])
    if not score["missing"]:
        paragraph("Nenhuma ausência nos itens avaliados. Confira cobertura, pendências e revisão humana.")
    story.append(Spacer(1, 5*mm))
    for index, check in enumerate(audit.checks, 1):
        paragraph(f"{index:02d}. {check.title}", "Heading2")
        paragraph("Estado: " + LABELS[check.status])
        story[-1].keepWithNext = True
        paragraph(check.detail)
        story[-1].keepWithNext = bool(check.evidence)
        for item in check.evidence:
            paragraph("Evidência: " + item)
    if audit.browser:
        paragraph("Cookies observados antes de interação", "Heading2")
        for cookie in audit.browser.get("cookies", []):
            paragraph(f"{cookie['name']} · {cookie['domain']} · Secure: {cookie['secure']} · HttpOnly: {cookie['httpOnly']} · SameSite: {cookie['sameSite']}")
        paragraph("Valores não são armazenados. Não foram testadas escolhas, bloqueio ou revogação. Domínios conectados não são automaticamente classificados como rastreadores.")
    if audit.ai:
        paragraph("Interpretação opcional com Gemini", "Heading2")
        paragraph(audit.ai["notice"])
        paragraph(f"Modelo: {audit.ai['model']} · Caracteres enviados: {audit.ai['characters_sent']}")
        for item in audit.ai["items"]:
            paragraph(f"{item['title']} - {item['status']}")
            paragraph(item["explanation"])
            if item["quote"]:
                paragraph("Citação conferida: " + item["quote"])
    paragraph("Rubrica e revisão humana", "Heading2")
    for item in score["items"]:
        paragraph(f"{item['title']}: peso {item['weight']} · {LABELS[item['status']]}")
    for item in score["manual"]:
        paragraph(item)
    paragraph("Limites e interpretação", "Heading2")
    for item in audit.limitations:
        paragraph("• " + item)

    def footer(canvas, document):
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#566c65"))
        canvas.drawString(22*mm, 13*mm, "Projeto acadêmico • Não certifica conformidade com a LGPD")
        canvas.drawRightString(A4[0]-22*mm, 13*mm, str(document.page))

    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    stream.seek(0)
    return stream
