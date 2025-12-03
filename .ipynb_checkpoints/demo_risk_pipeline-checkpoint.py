# risk_service/demo_risk_pipeline.py

import requests
from typing import Dict, Any, List

from schemas import Detection, Context, RiskRequest

RISK_SERVICE_URL = "http://localhost:8000/risk/analyze"


def build_detections_from_model_output(model_output: Dict[str, Any]) -> List[Detection]:
    """
    Adapter entre la sortie du modèle et nos objets Detection.

    👉 Ici on part sur un EXEMPLE de structure :
       model_output = {
         "spills": [
            {
              "id": "1",
              "class": "oil_spill",
              "substance": "oil",
              "confidence": 0.92,
              "area_ratio": 0.25
            },
            ...
         ]
       }

    Tu ajusteras les clés (class/substance/confidence/area_ratio)
    pour les aligner avec la vraie sortie du modèle.
    """
    detections: List[Detection] = []

    for spill in model_output.get("spills", []):
        det = Detection(
            id=str(spill.get("id", "")),
            label=spill.get("class", "spill"),
            substance_pred=spill.get("substance", "unknown"),
            confidence=float(spill.get("confidence", 0.0)),
            area_ratio=float(spill.get("area_ratio", 0.0)),
        )
        detections.append(det)

    return detections


def call_risk_service(
    image_id: str,
    model_output: Dict[str, Any],
    context_data: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Construit un RiskRequest à partir de la sortie du modèle + contexte,
    puis appelle le service RiskOps.
    """
    detections = build_detections_from_model_output(model_output)
    context = Context(**context_data)

    risk_request = RiskRequest(
        image_id=image_id,
        detections=detections,
        context=context,
    )

    payload = risk_request.model_dump()

    resp = requests.post(RISK_SERVICE_URL, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    # 🔬 1) On simule la sortie du modèle (pour l’instant)
    fake_model_output = {
        "spills": [
            {
                "id": "det_1",
                "class": "spill",
                "substance": "oil",
                "confidence": 0.93,
                "area_ratio": 0.30
            }
        ]
    }

    # 🔬 2) Contexte de risque (site, zone, etc.)
    fake_context = {
        "site_id": "SITE_001",
        "zone_id": "Z1",
        "zone_type": "production",
        "proximity_to_machines": "near_machine",
        "floor_type": "non_absorbent",
        "production_value_per_hour": 8000
    }

    # 🔬 3) Appel de ton service RiskOps
    result = call_risk_service(
        image_id="img_001",
        model_output=fake_model_output,
        context_data=fake_context,
    )

    print("=== Réponse du service RiskOps ===")
    print(result)
