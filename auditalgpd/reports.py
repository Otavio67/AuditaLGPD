"""Relatório legível, sem pontuações ou conclusões jurídicas automáticas."""

from io import BytesIO
from xml.sax.saxutils import escape
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

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
    story.append(Spacer(1, 5*mm))
    for index, check in enumerate(audit.checks, 1):
        paragraph(f"{index:02d}. {check.title}", "Heading2")
        paragraph("Estado: " + LABELS[check.status])
        paragraph(check.detail)
        for item in check.evidence:
            paragraph("Evidência: " + item)
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
