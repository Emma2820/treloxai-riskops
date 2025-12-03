# main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.middleware.wsgi import WSGIMiddleware
import io

from schema import RiskRequest, RiskResult
from risk_engine import build_risk_result
from incident_report import generate_incident_pdf

# ⬅️ on importe le Dash déjà défini dans risk_dashboard.py
from risk_dashboard import dash_app

app = FastAPI(
    title="TRELOXAI RiskOps Service",
    version="0.2.0",
)

# CORS (pour pouvoir appeler l'API depuis le Dash, un front web, etc.)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # à restreindre en prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 🔗 On monte le dashboard Dash sur /dashboard
#    => http://127.0.0.1:8000/dashboard en local
app.mount("/dashboard", WSGIMiddleware(dash_app.server))


@app.get("/health")
def health():
    """Petit endpoint de santé pour vérifier que le service tourne."""
    return {"status": "ok"}


@app.post("/risk/analyze", response_model=RiskResult)
def analyze_risk(payload: RiskRequest) -> RiskResult:
    """
    Endpoint principal : analyse de risque à partir :
    - des détections du modèle (detections)
    - du contexte (site, zone, machines, valeur de prod, etc.)
    """
    result = build_risk_result(
        image_id=payload.image_id,
        detections=payload.detections,
        context=payload.context,
    )
    return result


@app.post("/risk/report")
def risk_report(payload: RiskRequest):
    """
    Génère un rapport PDF d'incident à partir des mêmes données
    que /risk/analyze (Before/After mitigation, coût, recommandations).
    """
    result = build_risk_result(
        image_id=payload.image_id,
        detections=payload.detections,
        context=payload.context,
    )

    pdf_bytes = generate_incident_pdf(result)

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="incident_report.pdf"'
        },
    )
