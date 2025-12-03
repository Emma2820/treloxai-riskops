# demo_risk_pipeline.py

import json
from typing import Dict, Any
import requests

RISK_SERVICE_URL = "http://127.0.0.1:8000/risk/analyze"


def build_demo_payload() -> Dict[str, Any]:
    """
    Construit un payload de démo pour le service RiskOps.
    """
    payload = {
        "image_id": "img_test",
        "detections": [
            {
                "id": "det_1",
                "label": "spill",
                "substance_pred": "oil",
                "confidence": 0.85,
                "area_ratio": 0.21
            }
        ],
        "context": {
            "site_id": "SITE_001",
            "zone_id": "Z1",
            "zone_type": "production",
            "proximity_to_machines": "near_machine",
            "floor_type": "non_absorbent",
            "production_value_per_hour": 8000
        }
    }
    return payload


def call_risk_service(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Envoie le payload au service RiskOps et renvoie la réponse JSON.
    """
    resp = requests.post(RISK_SERVICE_URL, json=payload, timeout=10)
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    payload = build_demo_payload()
    print("=== Payload envoyé à RiskOps ===")
    print(json.dumps(payload, indent=2))

    result = call_risk_service(payload)

    print("\n=== Réponse du service RiskOps ===")
    print(json.dumps(result, indent=2, ensure_ascii=False))
