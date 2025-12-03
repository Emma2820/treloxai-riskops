# risk_engine.py

from typing import List, Dict, Tuple
from schema import Detection, Context, RiskResult


# ---------------------------------------------------------
# Helpers de scoring
# ---------------------------------------------------------


def _area_factor(area_ratio: float) -> float:
    """
    Ajuste le score en fonction de la surface impactée.
    ~0.1 → petit incident, ~0.3 → moyen, ~0.6 → large.
    """
    if area_ratio <= 0.15:
        return 0.6
    elif area_ratio <= 0.35:
        return 1.0
    else:
        return 1.3


def _physical_score(detection: Detection, context: Context) -> float:
    """
    Score de sévérité physique : toxicité / inflammabilité / surface.
    Calibré pour que :
      - eau  -> faible
      - huile -> moyen
      - chimique -> fort
    """
    substance = (detection.substance_pred or "unknown").lower()
    area_ratio = detection.area_ratio or 0.0
    floor_type = (context.floor_type or "").lower()

    # Base par substance (sur 100)
    if substance == "water":
        base = 20
    elif substance == "oil":
        base = 40
    elif substance == "chemical":
        base = 70
    else:
        base = 30

    af = _area_factor(area_ratio)

    # Sol absorbant réduit légèrement le risque, non absorbant l'augmente
    if "absorbent" in floor_type:
        floor_factor = 0.8
    else:
        floor_factor = 1.1

    score = base * af * floor_factor
    return max(0.0, min(score, 100.0))


def _electrical_score(detection: Detection, context: Context) -> float:
    """
    Score électrique : risque de court-circuit, arc, incendie,
    particulièrement en salle électrique ou proche d'équipements.
    """
    substance = (detection.substance_pred or "unknown").lower()
    zone_type = (context.zone_type or "").lower()
    proximity = (context.proximity_to_machines or "").lower()
    area_ratio = detection.area_ratio or 0.0

    base = 0.0

    if zone_type == "electrical_room":
        # Cas le plus sévère (chimique, eau conductrice…)
        if substance == "chemical":
            base = 80
        elif substance == "water":
            base = 60
        elif substance == "oil":
            base = 40
    elif zone_type in ("production", "storage"):
        # Risque électrique plus modéré mais réel si proche machine
        if proximity in ("near_machine", "critical_machine"):
            if substance == "chemical":
                base = 50
            elif substance == "oil":
                base = 40
            elif substance == "water":
                base = 25

    af = _area_factor(area_ratio)
    score = base * af
    return max(0.0, min(score, 100.0))


def _human_safety_score(detection: Detection, context: Context) -> float:
    """
    Score de risque humain : glissade, brûlure, intoxication.
    Combine substance, surface et proximité aux machines.
    """
    substance = (detection.substance_pred or "unknown").lower()
    proximity = (context.proximity_to_machines or "").lower()
    area_ratio = detection.area_ratio or 0.0

    # Base "glissade + toxicité"
    if substance == "water":
        base = 20
    elif substance == "oil":
        base = 40
    elif substance == "chemical":
        base = 70  # glissade + toxicité
    else:
        base = 30

    af = _area_factor(area_ratio)

    if proximity == "far":
        pf = 0.7
    elif proximity == "near_machine":
        pf = 1.0
    elif proximity == "critical_machine":
        pf = 1.2
    else:
        pf = 1.0

    score = base * af * pf
    return max(0.0, min(score, 100.0))


def _business_score(detection: Detection, context: Context) -> float:
    """
    Impact business : coût d'arrêt de production / logistique.
    Dépend surtout de la valeur de production par heure.
    """
    zone_type = (context.zone_type or "").lower()
    area_ratio = detection.area_ratio or 0.0
    prod_value = context.production_value_per_hour or 0

    # Valeur économique de la zone
    if zone_type == "production":
        zone_mult = 1.0
    elif zone_type == "electrical_room":
        zone_mult = 0.8
    elif zone_type == "storage":
        zone_mult = 0.7
    else:  # corridor, bureaux...
        zone_mult = 0.5

    # Transforme la valeur de prod en score ~ [0,100]
    base = min(prod_value / 500.0, 100.0)
    af = _area_factor(area_ratio)

    score = base * af * zone_mult
    return max(0.0, min(score, 100.0))


def _model_confidence_score(detection: Detection) -> float:
    """
    Score reflétant la confiance du modèle.
    Utilisé comme facteur de pondération global.
    """
    conf = detection.confidence or 0.0
    return max(0.0, min(conf * 100.0, 100.0))


def _severity_level(score: float) -> str:
    """
    Mapping score -> niveau :
      < 25   => LOW
      < 50   => MEDIUM
      < 75   => HIGH
      else   => CRITICAL
    """
    if score < 25:
        return "LOW"
    elif score < 50:
        return "MEDIUM"
    elif score < 75:
        return "HIGH"
    else:
        return "CRITICAL"


def _estimate_cost(
    global_score: float,
    detection: Detection,
    context: Context,
) -> float:
    """
    Estimation grossière du coût (en €) combinant :
      - valeur de production par heure
      - surface impactée
      - type de substance
      - sévérité globale
    On vise ici un ordre de grandeur pour la démo.
    """
    prod_value = context.production_value_per_hour or 0
    area_ratio = detection.area_ratio or 0.0
    substance = (detection.substance_pred or "unknown").lower()

    # Heures d'arrêt proportionnelles à la surface (max 4h)
    hours_lost = min(4.0 * area_ratio, 4.0)

    # Facteur substance
    if substance == "water":
        dmg_factor = 0.6
    elif substance == "oil":
        dmg_factor = 1.0
    elif substance == "chemical":
        dmg_factor = 2.0
    else:
        dmg_factor = 0.8

    base_loss = prod_value * hours_lost * dmg_factor

    # Amplifie selon le score global
    severity_factor = 0.5 + (global_score / 100.0)  # entre ~0.5 et 1.5

    cost = base_loss * severity_factor
    return max(0.0, float(cost))


def _build_recommendations(
    level: str,
    detection: Detection,
    context: Context,
) -> List[str]:
    """
    Génère une liste de recommandations simples,
    adaptées à la substance, la zone et le niveau.
    """
    recs: List[str] = []

    # Recommandations génériques
    recs.append("Isoler la zone et baliser l'accès (cones, rubalise).")

    substance = (detection.substance_pred or "unknown").lower()
    zone_type = (context.zone_type or "").lower()

    if substance == "oil":
        recs.append("Nettoyage urgent avec kit absorbant adapté à l'huile.")
    elif substance == "water":
        recs.append("Sécher / nettoyer la zone pour éviter les chutes.")
    elif substance == "chemical":
        recs.append("Déclencher la procédure de déversement chimique (EPI, SDS, ventilation).")

    if zone_type == "electrical_room":
        recs.append("Couper l'alimentation électrique de la zone si possible et sécurisé.")

    if level in ("HIGH", "CRITICAL"):
        recs.append("Informer immédiatement le responsable HSE / sécurité du site.")
        recs.append("Documenter l'incident dans le registre HSE et analyser les causes racines.")
    else:
        recs.append("Documenter l'incident dans le registre HSE.")

    return recs


def _build_explanation(
    level: str,
    score: float,
    detection: Detection,
    context: Context,
) -> str:
    """
    Texte explicatif lisible pour l'utilisateur.
    """
    substance = detection.substance_pred or "unknown"
    zone = context.zone_type or "unknown"
    proximity = context.proximity_to_machines or "unknown"

    return (
        f"Incident classé {level} (score {score:.1f}/100). "
        f"Substance détectée : {substance}. "
        f"Zone : {zone}, proximité aux équipements : {proximity}. "
        f"Les scores détaillés (physique, électrique, humain, business, confiance modèle) "
        f"contribuent chacun au score global en fonction de leur poids."
    )


# ---------------------------------------------------------
# Mitigation : calcul “after” pour la démo
# ---------------------------------------------------------


def _apply_mitigation(
    physical: float,
    electrical: float,
    human: float,
    business: float,
    model_conf: float,
) -> Tuple[float, float, float, float, float]:
    """
    Applique des coefficients de réduction simulant
    l'effet de la mitigation (balisage, nettoyage,
    coupure électrique, etc.).
    """
    physical_after = physical * 0.5
    electrical_after = electrical * 0.5
    human_after = human * 0.6
    business_after = business * 0.7
    model_conf_after = model_conf  # la confiance modèle ne change pas

    return (
        physical_after,
        electrical_after,
        human_after,
        business_after,
        model_conf_after,
    )


# ---------------------------------------------------------
# Fonction principale appelée par l'API
# ---------------------------------------------------------


def build_risk_result(
    image_id: str,
    detections: List[Detection],
    context: Context,
) -> RiskResult:
    """
    Point d'entrée principal du moteur RiskOps.
    Utilise UNIQUEMENT la première détection pour la démo.
    """
    if not detections:
        # Cas dégradé : pas de détection -> tout à zéro
        factors = []
        return RiskResult(
            image_id=image_id,
            global_severity_score=0.0,
            global_severity_level="LOW",
            estimated_cost=0.0,
            currency="EUR",
            factors=factors,
            explanation="Aucune détection fournie. Score de risque nul.",
            recommendations=[],
            mitigated_severity_score=0.0,
            mitigated_severity_level="LOW",
            mitigated_cost=0.0,
            risk_reduction_pct=0.0,
        )

    det = detections[0]

    # 1) Scores par facteur (0-100)
    physical = _physical_score(det, context)
    electrical = _electrical_score(det, context)
    human = _human_safety_score(det, context)
    business = _business_score(det, context)
    model_conf = _model_confidence_score(det)

    # 2) Poids : calibrés pour ta démo
    w_physical = 0.35
    w_electrical = 0.20
    w_human = 0.20
    w_business = 0.15
    w_model_conf = 0.10

    # 3) Contribution de chaque facteur
    factors: List[Dict] = []
    factors.append(
        {
            "name": "physical",
            "value": round(physical, 2),
            "weight": w_physical,
            "contribution": round(physical * w_physical, 3),
        }
    )
    factors.append(
        {
            "name": "electrical",
            "value": round(electrical, 2),
            "weight": w_electrical,
            "contribution": round(electrical * w_electrical, 3),
        }
    )
    factors.append(
        {
            "name": "human_safety",
            "value": round(human, 2),
            "weight": w_human,
            "contribution": round(human * w_human, 3),
        }
    )
    factors.append(
        {
            "name": "business",
            "value": round(business, 2),
            "weight": w_business,
            "contribution": round(business * w_business, 3),
        }
    )
    factors.append(
        {
            "name": "model_confidence",
            "value": round(model_conf, 2),
            "weight": w_model_conf,
            "contribution": round(model_conf * w_model_conf, 3),
        }
    )

    # 4) Score global (somme des contributions)
    global_score = sum(f["contribution"] for f in factors)
    global_level = _severity_level(global_score)

    # 5) Estimation du coût
    estimated_cost = _estimate_cost(global_score, det, context)

    # 6) Explication + recommandations
    explanation = _build_explanation(global_level, global_score, det, context)
    recommendations = _build_recommendations(global_level, det, context)

    # 7) Simulation "After mitigation"
    (
        physical_after,
        electrical_after,
        human_after,
        business_after,
        model_conf_after,
    ) = _apply_mitigation(physical, electrical, human, business, model_conf)

    # Score après mitigation
    factors_after = [
        physical_after * w_physical,
        electrical_after * w_electrical,
        human_after * w_human,
        business_after * w_business,
        model_conf_after * w_model_conf,
    ]
    mitigated_score = sum(factors_after)
    mitigated_level = _severity_level(mitigated_score)

    # Coût après mitigation : réduction proportionnelle au score
    if global_score > 0:
        mitigated_cost = estimated_cost * (mitigated_score / global_score)
    else:
        mitigated_cost = 0.0

    # Réduction en %
    if global_score > 0:
        risk_reduction_pct = (global_score - mitigated_score) / global_score * 100.0
    else:
        risk_reduction_pct = 0.0

    # 8) Construction de l'objet de réponse
    return RiskResult(
        image_id=image_id,
        global_severity_score=round(global_score, 2),
        global_severity_level=global_level,
        estimated_cost=round(estimated_cost, 2),
        currency="EUR",
        factors=factors,
        explanation=explanation,
        recommendations=recommendations,
        mitigated_severity_score=round(mitigated_score, 2),
        mitigated_severity_level=mitigated_level,
        mitigated_cost=round(mitigated_cost, 2),
        risk_reduction_pct=round(risk_reduction_pct, 1),
    )
