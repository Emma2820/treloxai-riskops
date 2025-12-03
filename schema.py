# schema.py
from typing import List, Optional
from pydantic import BaseModel


class Detection(BaseModel):
    """
    Détection renvoyée par le modèle / ou simulée.
    """
    id: str
    label: str                 # ex: "spill"
    substance_pred: str        # ex: "water", "oil", "chemical"
    confidence: float          # 0–1
    area_ratio: Optional[float] = None  # proportion de l'image


class Context(BaseModel):
    """
    Contexte métier pour le calcul de risque.
    """
    site_id: str
    zone_id: Optional[str] = None
    zone_type: Optional[str] = None            # ex: "production", "electrical_room"
    proximity_to_machines: Optional[str] = None  # ex: "near_machine"
    floor_type: Optional[str] = None           # ex: "non_absorbent"
    production_value_per_hour: Optional[float] = None  # € / heure


class RiskRequest(BaseModel):
    """
    Payload de la requête /risk/analyze.
    """
    image_id: str
    detections: List[Detection]
    context: Context


class RiskFactor(BaseModel):
    name: str
    value: float
    weight: float
    contribution: float



class RiskResult(BaseModel):
    image_id: str

    # Score & coût AVANT mitigation
    global_severity_score: float
    global_severity_level: str
    estimated_cost: float

    currency: str = "EUR"
    factors: List[RiskFactor]
    explanation: str

    # --- NOUVEAUX CHAMPS : AFTER MITIGATION ---
    mitigated_severity_score: Optional[float] = None
    mitigated_severity_level: Optional[str] = None
    mitigated_cost: Optional[float] = None
    risk_reduction_pct: Optional[float] = None

    # Recommandations textuelles
    recommendations: List[str] = []