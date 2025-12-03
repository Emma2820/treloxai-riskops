# risk_service/adapter_example.py

import requests
from typing import List, Dict, Any

from schemas import Detection, Context, RiskRequest
from risk_engine import RiskResult  # seulement pour le type (optionnel)


RISK_SERVICE_URL = "http://localhost:8000/risk/analyze"


def build_detections_from_model_output(model_output: Dict[str, Any]) -> List[Detection]:
    """
    Adapter entre la sortie du modèle et nos objets Detection.
    ICI tu feras le mapping exact selon la vraie structure de model_output.

    Exemple fictif:
      model_output = {
         "spills": [
            {"id": "1", "class": "oil_spill", "substance": "oil",
             "confidence": 0.92, "area_ratio": 0.25},
            ...
         ]
      }
    """
    detections = []

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

    # Conversion en dict / json pour l’API
    payload = risk_request.model_dump()

    response = requests.post(RISK_SERVICE_URL, json=payload, timeout=10)
    response.raise_for_status()

    return response.json()


if __name__ == "__main__":
    # 🔬 Exemple de test local (MVP)
    fake_model_output = {
        "spills": [
            {
                "id": "det_1",
                "class": "spill",
                "substance": "oil",
                "confidence": 0.93,
                "area_ratio": 0.30,
            }
        ]
    }

    fake_context = {
        "site_id": "SITE_001",
        "zone_id": "Z1",
        "zone_type": "production",
        "proximity_to_machines": "near_machine",
        "floor_type": "non_absorbent",
        "production_value_per_hour": 8000,
    }

    result = call_risk_service(
        image_id="img_001",
        model_output=fake_model_output,
        context_data=fake_context,
    )

    print("Réponse RiskOps :")
    print(result)
