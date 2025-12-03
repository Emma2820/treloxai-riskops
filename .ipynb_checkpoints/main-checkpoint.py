# risk_service/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from schemas import RiskRequest, RiskResult
from risk_engine import build_risk_result

app = FastAPI(
    title="TRELOXAI RiskOps Service",
    version="0.1.0",
)

# CORS larges pour la démo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/risk/analyze", response_model=RiskResult)
def analyze_risk(payload: RiskRequest):
    """
    Reçoit la sortie du modèle + contexte,
    renvoie un JSON enrichi avec le risque.
    """
    result = build_risk_result(
        image_id=payload.image_id,
        detections=payload.detections,
        context=payload.context,
    )
    return result
