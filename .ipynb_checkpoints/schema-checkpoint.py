# risk_service/schemas.py
from typing import List, Optional
from pydantic import BaseModel


class Detection(BaseModel):
    """
    Une détection renvoyée par le modèle (adaptée à ton usage).
    Tu pourras mapper ici les champs de la sortie réelle du modèle.
    """
    id: str
    label: str                 # ex: "spill", "water_spill", "oil_spill"
    substance_pred: str        # ex: "water", "oil", "chemical"
    confidence: float          # 0–1
    area_ratio: Optional[float] = None  # surface du spill / surface image (0–1)


class Context(BaseModel):
    """
    Contexte métier minimal pour calculer le risque.
    Tu peux en ajouter ou en enlever selon ta démo.
    """
    site_id: str
    zone_id: Optional[str] = None
    zone_type: Optional[str] = None           # ex: "production", "electrical_room"
    proximity_to_machines: Optional[str] = None  # "near_machine", "far"
    floor_type: Optional[str] = None          # "absorbent", "non_absorbent"
    production_value_per_hour: Optional[float] = None  # en euros/h


class RiskRequest(BaseModel):
    """
    Ce que ton cofondateur enverra à ton API Risk.
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
    """
    Réponse de ton service Risk.
    """
    image_id: str
    global_severity_score: float        # 0–100
    global_severity_level: str          # "LOW" / "MEDIUM" / "HIGH" / "CRITICAL"
    estimated_cost: float               # en euros
    currency: str = "EUR"
    factors: List[RiskFactor]
    explanation: str
