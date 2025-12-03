# incident_report.py

from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

from schema import RiskResult


def generate_incident_pdf(result: RiskResult) -> bytes:
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    width, height = A4
    y = height - 2 * cm

    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, y, "TRELOXAI - Rapport d'incident RiskOps")
    y -= 1.5 * cm

    c.setFont("Helvetica", 11)
    c.drawString(2 * cm, y, f"Image ID : {result.image_id}")
    y -= 0.7 * cm
    c.drawString(2 * cm, y, f"Niveau de risque : {result.global_severity_level} ({result.global_severity_score:.1f}/100)")
    y -= 0.7 * cm
    if result.mitigated_severity_score is not None:
        c.drawString(
            2 * cm,
            y,
            f"Après mitigation : {result.mitigated_severity_level} ({result.mitigated_severity_score:.1f}/100)",
        )
        y -= 0.7 * cm

    c.drawString(2 * cm, y, f"Coût estimé : {result.estimated_cost:,.0f} {result.currency}")
    y -= 0.7 * cm
    if result.mitigated_cost is not None:
        c.drawString(2 * cm, y, f"Coût estimé après mitigation : {result.mitigated_cost:,.0f} {result.currency}")
        y -= 0.7 * cm

    if result.risk_reduction_pct is not None:
        c.drawString(2 * cm, y, f"Réduction de risque estimée : {result.risk_reduction_pct:.1f} %")
        y -= 1.0 * cm

    # Facteurs
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, y, "Facteurs de risque :")
    y -= 0.8 * cm
    c.setFont("Helvetica", 10)

    for f in result.factors:
        c.drawString(
            2 * cm,
            y,
            f"- {f.name} : score {f.value:.1f}/100, poids {f.weight:.2f}, contribution {f.contribution:.1f}",
        )
        y -= 0.6 * cm
        if y < 3 * cm:
            c.showPage()
            y = height - 2 * cm
            c.setFont("Helvetica", 10)

    # Recommandations
    y -= 0.5 * cm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, y, "Recommandations :")
    y -= 0.8 * cm
    c.setFont("Helvetica", 10)

    for rec in result.recommendations:
        c.drawString(2 * cm, y, f"- {rec}")
        y -= 0.6 * cm
        if y < 3 * cm:
            c.showPage()
            y = height - 2 * cm
            c.setFont("Helvetica", 10)

    # Explication
    y -= 0.5 * cm
    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, y, "Explication détaillée :")
    y -= 0.8 * cm
    c.setFont("Helvetica", 10)

    # on coupe l'explication en lignes
    text_obj = c.beginText(2 * cm, y)
    text_obj.setLeading(14)
    for line in result.explanation.split(". "):
        text_obj.textLine(line.strip())
    c.drawText(text_obj)

    c.showPage()
    c.save()
    pdf = buffer.getvalue()
    buffer.close()
    return pdf
