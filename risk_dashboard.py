# risk_dashboard.py

import os
import json
import base64
import datetime as dt

import requests
from dash import Dash, html, dcc, dash_table
from dash.dependencies import Input, Output, State
import plotly.graph_objs as go

# 🔧 Base URL de l’API RiskOps (FastAPI)
# On se base sur la variable d'environnement PORT, sinon 8000 (local)
PORT = os.getenv("PORT", "8000")
API_BASE = f"http://127.0.0.1:{PORT}"

# URL complète de l’endpoint
RISK_SERVICE_URL = "https://treloxai-riskops.onrender.com/risk/analyze"



# ============================================================
#  UTILITAIRES
# ============================================================

def build_demo_payload(
    site_id="SITE_001",
    zone_type="production",
    proximity="near_machine",
    floor_type="non_absorbent",
    prod_value_per_hour=8000,
    substance="oil",
    confidence=0.9,
    area_ratio=0.3,
):
    """
    Construit un payload compatible avec /risk/analyze
    à partir d'une détection (substance, confiance, surface)
    et d'un contexte simple.
    """
    return {
        "image_id": "img_demo",
        "detections": [
            {
                "id": "det_1",
                "label": "spill",
                "substance_pred": substance,
                "confidence": confidence,
                "area_ratio": area_ratio,
            }
        ],
        "context": {
            "site_id": site_id,
            "zone_id": "Z1",
            "zone_type": zone_type,
            "proximity_to_machines": proximity,
            "floor_type": floor_type,
            "production_value_per_hour": prod_value_per_hour,
        },
    }


def empty_history_figure():
    fig = go.Figure()
    fig.update_layout(
        title="Historique des scores (avant / après mitigation)",
        xaxis_title="Analyse",
        yaxis_title="Score de sévérité",
        template="plotly_white",
    )
    return fig


# ============================================================
#  STYLES GLOBAUX
# ============================================================

BACKGROUND = "#f3f5fb"
CARD_BG = "#ffffff"
BORDER_RADIUS = "10px"
SHADOW = "0 10px 25px rgba(15, 23, 42, 0.08)"
PRIMARY = "#2563eb"
TEXT_MUTED = "#6b7280"


def level_color(level: str) -> str:
    """
    Couleur du texte en fonction du niveau de risque.
    """
    if not level:
        return "#111827"
    lvl = level.upper()
    mapping = {
        "LOW": "#16a34a",       # vert
        "MEDIUM": "#ea580c",    # orange
        "HIGH": "#b91c1c",      # rouge
        "CRITICAL": "#7f1d1d",  # rouge très foncé
    }
    return mapping.get(lvl, "#111827")


# ============================================================
#  APP DASH
# ============================================================

app = Dash(
    __name__,
    suppress_callback_exceptions=True,
)


app.title = "TRELOXAI - RiskOps Demo"


# ----------------- Layout Détection (onglet 1) -----------------

def detection_tab_layout():
    return html.Div(
        style={
            "display": "grid",
            "gridTemplateColumns": "minmax(260px, 340px) minmax(0, 1fr)",
            "columnGap": "32px",
            "rowGap": "24px",
            "marginTop": "10px",
        },
        children=[
            # Colonne gauche : upload + paramètres modèle
            html.Div(
                children=[
                    html.Div(
                        "Détection visuelle (IA)",
                        style={"fontWeight": "600", "marginBottom": "8px", "fontSize": "16px"},
                    ),

                    html.Div(
                        "Téléverse une image d'incident (spill) pour illustrer la détection du modèle.",
                        style={"fontSize": "12px", "color": TEXT_MUTED, "marginBottom": "8px"},
                    ),

                    dcc.Upload(
                        id="upload-image",
                        children=html.Div(
                            [
                                "Glisser-déposer une image ici ou ",
                                html.Span("cliquer pour parcourir", style={"color": PRIMARY}),
                            ]
                        ),
                        style={
                            "borderWidth": "1px",
                            "borderStyle": "dashed",
                            "borderRadius": "8px",
                            "padding": "14px",
                            "textAlign": "center",
                            "backgroundColor": "#f9fafb",
                            "cursor": "pointer",
                            "marginBottom": "12px",
                        },
                        multiple=False,
                    ),

                    html.Div(
                        id="detection-image-preview",
                        style={
                            "borderRadius": "8px",
                            "overflow": "hidden",
                            "border": "1px solid #e5e7eb",
                            "backgroundColor": "#ffffff",
                            "minHeight": "150px",
                            "display": "flex",
                            "alignItems": "center",
                            "justifyContent": "center",
                            "fontSize": "12px",
                            "color": TEXT_MUTED,
                        },
                        children="Aucune image chargée pour l'instant.",
                    ),

                    html.Hr(style={"margin": "14px 0"}),

                    html.Div(
                        "Sortie modèle (mode démo)",
                        style={"fontWeight": "600", "marginBottom": "6px", "fontSize": "14px"},
                    ),

                    html.Div(
                        style={"display": "flex", "flexDirection": "column", "gap": "10px"},
                        children=[
                            html.Div(
                                children=[
                                    html.Label(
                                        "Substance détectée par le modèle",
                                        style={"fontSize": "12px", "color": TEXT_MUTED},
                                    ),
                                    dcc.Dropdown(
                                        id="det-substance",
                                        options=[
                                            {"label": "Eau", "value": "water"},
                                            {"label": "Huile", "value": "oil"},
                                            {"label": "Produit chimique", "value": "chemical"},
                                        ],
                                        value="oil",
                                        clearable=False,
                                        style={"marginTop": "3px", "fontSize": "13px"},
                                    ),
                                ]
                            ),
                            html.Div(
                                children=[
                                    html.Label(
                                        "Confiance du modèle (%)",
                                        style={"fontSize": "12px", "color": TEXT_MUTED},
                                    ),
                                    dcc.Slider(
                                        id="det-confidence",
                                        min=40,
                                        max=100,
                                        step=1,
                                        value=90,
                                        marks=None,
                                        tooltip={"always_visible": True, "placement": "top"},
                                    ),
                                ]
                            ),
                            html.Div(
                                children=[
                                    html.Label(
                                        "Surface impactée (ratio de l'image)",
                                        style={"fontSize": "12px", "color": TEXT_MUTED},
                                    ),
                                    dcc.Slider(
                                        id="det-area",
                                        min=0.05,
                                        max=0.6,
                                        step=0.05,
                                        value=0.3,
                                        marks=None,
                                        tooltip={"always_visible": True, "placement": "top"},
                                    ),
                                ]
                            ),
                        ],
                    ),

                    html.Button(
                        "Simuler la prédiction",
                        id="btn-simulate-detection",
                        n_clicks=0,
                        style={
                            "marginTop": "16px",
                            "backgroundColor": PRIMARY,
                            "color": "white",
                            "border": "none",
                            "padding": "8px 14px",
                            "cursor": "pointer",
                            "borderRadius": "999px",
                            "fontSize": "13px",
                            "fontWeight": "500",
                        },
                    ),

                    html.Div(
                        id="detection-error",
                        style={"color": "#b91c1c", "fontSize": "12px", "marginTop": "8px"},
                    ),
                ]
            ),

            # Colonne droite : heatmap + mini RiskOps
            html.Div(
                children=[
                    html.Div(
                        "Visualisation & impact RiskOps",
                        style={"fontWeight": "600", "marginBottom": "8px", "fontSize": "16px"},
                    ),

                    html.Div(
                        style={
                            "display": "grid",
                            "gridTemplateColumns": "minmax(0, 1.2fr) minmax(0, 1fr)",
                            "columnGap": "18px",
                        },
                        children=[
                            dcc.Graph(
                                id="heatmap-graph",
                                style={"height": "260px"},
                            ),
                            html.Div(
                                id="detection-risk-card",
                                style={
                                    "backgroundColor": "#f9fafb",
                                    "borderRadius": "10px",
                                    "padding": "12px 14px",
                                    "border": "1px solid #e5e7eb",
                                    "fontSize": "13px",
                                },
                                children=html.Div(
                                    "Clique sur « Simuler la prédiction » pour voir l'impact RiskOps.",
                                    style={"color": TEXT_MUTED, "fontSize": "12px"},
                                ),
                            ),
                        ],
                    ),
                ]
            ),
        ],
    )


# ----------------- Layout RiskOps (onglet 2) -----------------

def riskops_tab_layout():
    return html.Div(
        style={
            "display": "grid",
            "gridTemplateColumns": "minmax(260px, 320px) minmax(0, 1fr)",
            "columnGap": "32px",
            "rowGap": "24px",
            "marginTop": "10px",
        },
        children=[
            # Colonne gauche : contexte RiskOps
            html.Div(
                children=[
                    # Scénarios de démo
                    html.Div(
                        children=[
                            html.Label(
                                "Scénario démo rapide",
                                style={"fontSize": "13px", "color": TEXT_MUTED},
                            ),
                            dcc.Dropdown(
                                id="demo-scenario",
                                options=[
                                    {
                                        "label": "Petite fuite d'eau dans couloir",
                                        "value": "water_small",
                                    },
                                    {
                                        "label": "Fuite d'huile proche machine",
                                        "value": "oil_machine",
                                    },
                                    {
                                        "label": "Déversement chimique en salle électrique",
                                        "value": "chem_elec",
                                    },
                                ],
                                value="oil_machine",
                                clearable=False,
                                style={"marginTop": "3px", "fontSize": "13px"},
                            ),
                        ],
                        style={"marginBottom": "12px"},
                    ),

                    html.Div(
                        "Contexte site / zone",
                        style={"fontWeight": "600", "marginBottom": "12px", "fontSize": "16px"},
                    ),

                    html.Div(
                        style={"display": "flex", "flexDirection": "column", "gap": "10px"},
                        children=[
                            html.Div(
                                children=[
                                    html.Label(
                                        "Site ID",
                                        style={"fontSize": "13px", "color": TEXT_MUTED},
                                    ),
                                    dcc.Input(
                                        id="input-site-id",
                                        type="text",
                                        value="SITE_001",
                                        style={
                                            "width": "100%",
                                            "marginTop": "3px",
                                            "padding": "6px 8px",
                                            "borderRadius": "6px",
                                            "border": "1px solid #d1d5db",
                                            "fontSize": "13px",
                                        },
                                    ),
                                ]
                            ),
                            html.Div(
                                children=[
                                    html.Label(
                                        "Type de zone",
                                        style={"fontSize": "13px", "color": TEXT_MUTED},
                                    ),
                                    dcc.Dropdown(
                                        id="input-zone-type",
                                        options=[
                                            {"label": "Production", "value": "production"},
                                            {"label": "Salle électrique", "value": "electrical_room"},
                                            {"label": "Couloir", "value": "corridor"},
                                            {"label": "Stockage", "value": "storage"},
                                        ],
                                        value="production",
                                        clearable=False,
                                        style={"marginTop": "3px", "fontSize": "13px"},
                                    ),
                                ]
                            ),
                            html.Div(
                                children=[
                                    html.Label(
                                        "Substance détectée (mode démo)",
                                        style={"fontSize": "13px", "color": TEXT_MUTED},
                                    ),
                                    dcc.Dropdown(
                                        id="input-substance",
                                        options=[
                                            {"label": "Eau", "value": "water"},
                                            {"label": "Huile", "value": "oil"},
                                            {"label": "Produit chimique", "value": "chemical"},
                                        ],
                                        value="oil",
                                        clearable=False,
                                        style={"marginTop": "3px", "fontSize": "13px"},
                                    ),
                                ]
                            ),
                            html.Div(
                                children=[
                                    html.Label(
                                        "Proximité aux machines",
                                        style={"fontSize": "13px", "color": TEXT_MUTED},
                                    ),
                                    dcc.Dropdown(
                                        id="input-proximity",
                                        options=[
                                            {"label": "Loin", "value": "far"},
                                            {"label": "Proche machine", "value": "near_machine"},
                                            {"label": "Machine critique", "value": "critical_machine"},
                                        ],
                                        value="near_machine",
                                        clearable=False,
                                        style={"marginTop": "3px", "fontSize": "13px"},
                                    ),
                                ]
                            ),
                            html.Div(
                                children=[
                                    html.Label(
                                        "Type de sol",
                                        style={"fontSize": "13px", "color": TEXT_MUTED},
                                    ),
                                    dcc.Dropdown(
                                        id="input-floor-type",
                                        options=[
                                            {"label": "Absorbant", "value": "absorbent"},
                                            {"label": "Non absorbant", "value": "non_absorbent"},
                                        ],
                                        value="non_absorbent",
                                        clearable=False,
                                        style={"marginTop": "3px", "fontSize": "13px"},
                                    ),
                                ]
                            ),
                            html.Div(
                                children=[
                                    html.Label(
                                        "Valeur de production par heure (€)",
                                        style={"fontSize": "13px", "color": TEXT_MUTED},
                                    ),
                                    dcc.Input(
                                        id="input-prod-value",
                                        type="number",
                                        value=8000,
                                        style={
                                            "width": "100%",
                                            "marginTop": "3px",
                                            "padding": "6px 8px",
                                            "borderRadius": "6px",
                                            "border": "1px solid #d1d5db",
                                            "fontSize": "13px",
                                        },
                                    ),
                                ]
                            ),
                        ],
                    ),

                    html.Div(
                        style={
                            "display": "flex",
                            "justifyContent": "space-between",
                            "alignItems": "center",
                            "marginTop": "18px",
                        },
                        children=[
                            html.Button(
                                "Lancer l'analyse de risque",
                                id="btn-run",
                                n_clicks=0,
                                style={
                                    "backgroundColor": PRIMARY,
                                    "color": "white",
                                    "border": "none",
                                    "padding": "9px 16px",
                                    "cursor": "pointer",
                                    "borderRadius": "999px",
                                    "fontSize": "13px",
                                    "fontWeight": "500",
                                },
                            ),
                            html.Div(
                                id="error-message",
                                style={"color": "#b91c1c", "fontSize": "12px"},
                            ),
                        ],
                    ),
                ]
            ),

            # Colonne droite : résultats RiskOps
            html.Div(
                children=[
                    html.Div(
                        "Résultats RiskOps",
                        style={"fontWeight": "600", "marginBottom": "10px", "fontSize": "16px"},
                    ),

                    html.Div(
                        id="summary-cards",
                        style={
                            "display": "flex",
                            "gap": "16px",
                            "marginBottom": "18px",
                            "flexWrap": "wrap",
                        },
                    ),

                    html.Div(
                        style={"marginBottom": "16px"},
                        children=[
                            html.Div(
                                "Facteurs de risque",
                                style={
                                    "fontWeight": "500",
                                    "marginBottom": "8px",
                                    "fontSize": "14px",
                                },
                            ),
                            dash_table.DataTable(
                                id="factors-table",
                                columns=[
                                    {"name": "Facteur", "id": "name"},
                                    {"name": "Score", "id": "value"},
                                    {"name": "Poids", "id": "weight"},
                                    {"name": "Contribution", "id": "contribution"},
                                ],
                                data=[],
                                style_table={
                                    "maxWidth": "650px",
                                    "borderRadius": "8px",
                                    "overflow": "hidden",
                                },
                                style_header={
                                    "backgroundColor": "#f3f4f6",
                                    "fontWeight": "600",
                                    "border": "none",
                                },
                                style_cell={
                                    "textAlign": "left",
                                    "padding": "6px 8px",
                                    "fontSize": "12px",
                                    "borderBottom": "1px solid #e5e7eb",
                                },
                            ),
                        ],
                    ),

                    html.Div(
                        style={"marginBottom": "16px"},
                        children=[
                            html.Div(
                                "Explication",
                                style={
                                    "fontWeight": "500",
                                    "marginBottom": "6px",
                                    "fontSize": "14px",
                                },
                            ),
                            html.Pre(
                                id="explanation-text",
                                style={
                                    "backgroundColor": "#f9fafb",
                                    "padding": "10px 12px",
                                    "borderRadius": "8px",
                                    "fontSize": "12px",
                                    "whiteSpace": "pre-wrap",
                                },
                            ),
                        ],
                    ),

                    html.Div(
                        style={"marginBottom": "16px"},
                        children=[
                            html.Div(
                                "Recommandations",
                                style={
                                    "fontWeight": "500",
                                    "marginBottom": "6px",
                                    "fontSize": "14px",
                                },
                            ),
                            html.Ul(
                                id="recommendations-list",
                                style={"margin": 0, "paddingLeft": "18px", "fontSize": "12px"},
                            ),
                        ],
                    ),
                ],
            ),
        ],
    )


# ----------------- Layout global (header + tabs) -----------------

app.layout = html.Div(
    style={
        "backgroundColor": BACKGROUND,
        "minHeight": "100vh",
        "padding": "30px 0",
        "fontFamily": "system-ui, -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    },
    children=[
        dcc.Store(id="history-store", data=[]),

        html.Div(
            style={"maxWidth": "1200px", "margin": "0 auto", "padding": "0 20px"},
            children=[
                # HEADER avec logo + bandeau
                html.Div(
                    style={
                        "display": "flex",
                        "justifyContent": "space-between",
                        "alignItems": "center",
                        "marginBottom": "16px",
                    },
                    children=[
                        # Logo
                        html.Div(
                            children=[
                                # Place ton fichier logo dans assets/treloxai_logo.png
                                html.Img(
                                    src="/assets/treloxai_logo.png",
                                    style={"height": "40px", "marginBottom": "4px"},
                                ),
                                html.Div(
                                    "TRELOXAI - RiskOps Platform",
                                    style={
                                        "fontSize": "12px",
                                        "color": TEXT_MUTED,
                                    },
                                ),
                            ]
                        ),

                        # Titre centre
                        html.Div(
                            style={"textAlign": "center"},
                            children=[
                                html.H1(
                                    "RiskOps Demo",
                                    style={
                                        "margin": 0,
                                        "fontWeight": "700",
                                        "fontSize": "24px",
                                        "color": "#111827",
                                    },
                                ),
                                html.P(
                                    "De la détection IA à la quantification du risque et des coûts.",
                                    style={"color": TEXT_MUTED, "margin": 0, "fontSize": "12px"},
                                ),
                            ],
                        ),

                        # Bandeau Client / Site / Date
                        html.Div(
                            style={
                                "backgroundColor": CARD_BG,
                                "borderRadius": "999px",
                                "padding": "6px 12px",
                                "boxShadow": SHADOW,
                                "display": "flex",
                                "alignItems": "center",
                                "gap": "10px",
                                "fontSize": "11px",
                            },
                            children=[
                                html.Div(
                                    children=[
                                        html.Span("Client :", style={"color": TEXT_MUTED}),
                                        dcc.Input(
                                            id="banner-client",
                                            type="text",
                                            value="Client Démo",
                                            style={
                                                "border": "none",
                                                "borderBottom": "1px dotted #e5e7eb",
                                                "marginLeft": "4px",
                                                "width": "90px",
                                            },
                                        ),
                                    ]
                                ),
                                html.Div(
                                    children=[
                                        html.Span("Site :", style={"color": TEXT_MUTED}),
                                        dcc.Input(
                                            id="banner-site",
                                            type="text",
                                            value="SITE_001",
                                            style={
                                                "border": "none",
                                                "borderBottom": "1px dotted #e5e7eb",
                                                "marginLeft": "4px",
                                                "width": "80px",
                                            },
                                        ),
                                    ]
                                ),
                                html.Div(
                                    children=[
                                        html.Span("Date :", style={"color": TEXT_MUTED}),
                                        html.Span(
                                            dt.date.today().isoformat(),
                                            id="banner-date",
                                            style={"marginLeft": "4px"},
                                        ),
                                    ]
                                ),
                            ],
                        ),
                    ],
                ),

                # Carte principale avec onglets
                html.Div(
                    style={
                        "backgroundColor": CARD_BG,
                        "borderRadius": BORDER_RADIUS,
                        "boxShadow": SHADOW,
                        "padding": "16px 20px 22px 20px",
                    },
                    children=[
                        dcc.Tabs(
                            id="main-tabs",
                            value="tab-detection",
                            children=[
                                dcc.Tab(
                                    label="1. Détection visuelle",
                                    value="tab-detection",
                                ),
                                dcc.Tab(
                                    label="2. Analyse RiskOps",
                                    value="tab-riskops",
                                ),
                            ],
                        ),
                        html.Div(id="tabs-content"),
                        html.Hr(style={"margin": "18px 0"}),
                        html.Div(
                            style={
                                "display": "grid",
                                "gridTemplateColumns": "minmax(0, 2.2fr) minmax(0, 1fr)",
                                "columnGap": "24px",
                            },
                            children=[
                                html.Div(
                                    children=[
                                        html.Div(
                                            "Historique des analyses (RiskOps)",
                                            style={
                                                "fontWeight": "500",
                                                "marginBottom": "6px",
                                                "fontSize": "14px",
                                            },
                                        ),
                                        dcc.Graph(
                                            id="history-graph",
                                            style={"height": "260px"},
                                        ),
                                    ]
                                ),
                                html.Div(
                                    children=[
                                        html.Div(
                                            "Réponse brute (JSON dernière analyse)",
                                            style={
                                                "fontWeight": "500",
                                                "marginBottom": "6px",
                                                "fontSize": "14px",
                                            },
                                        ),
                                        html.Pre(
                                            id="raw-json",
                                            style={
                                                "backgroundColor": "#020617",
                                                "color": "#22c55e",
                                                "padding": "10px 12px",
                                                "borderRadius": "8px",
                                                "fontSize": "11px",
                                                "maxHeight": "260px",
                                                "overflowY": "auto",
                                            },
                                        ),
                                    ]
                                ),
                            ],
                        ),
                    ],
                ),
            ],
        ),
    ],
)


# ============================================================
#  CALLBACK TABS
# ============================================================

@app.callback(
    Output("tabs-content", "children"),
    Input("main-tabs", "value"),
)
def render_tabs(tab):
    if tab == "tab-detection":
        return detection_tab_layout()
    return riskops_tab_layout()


# ============================================================
#  CALLBACK DÉMO SCÉNARIOS (onglet 2)
# ============================================================

@app.callback(
    Output("input-zone-type", "value"),
    Output("input-substance", "value"),
    Output("input-proximity", "value"),
    Output("input-floor-type", "value"),
    Output("input-prod-value", "value"),
    Input("demo-scenario", "value"),
    prevent_initial_call=True,
)
def update_demo_scenario(scenario):
    """
    Pré-remplit les paramètres en fonction d'un scénario de démo.
    Tu cliques sur le scénario, puis sur 'Lancer l'analyse de risque'.
    """
    if scenario == "water_small":
        # Petit incident eau, faible criticité
        return "corridor", "water", "far", "absorbent", 3000
    elif scenario == "chem_elec":
        # Cas le plus critique pour la démo
        return "electrical_room", "chemical", "critical_machine", "non_absorbent", 15000
    else:  # "oil_machine" par défaut
        return "production", "oil", "near_machine", "non_absorbent", 8000


# ============================================================
#  CALLBACKS DÉTECTION (onglet 1)
# ============================================================

@app.callback(
    Output("detection-image-preview", "children"),
    Input("upload-image", "contents"),
    State("upload-image", "filename"),
)
def update_image_preview(contents, filename):
    if contents is None:
        return "Aucune image chargée pour l'instant."

    return html.Div(
        style={"width": "100%", "textAlign": "center"},
        children=[
            html.Div(filename, style={"fontSize": "11px", "marginBottom": "4px", "color": TEXT_MUTED}),
            html.Img(
                src=contents,
                style={"maxWidth": "100%", "maxHeight": "220px", "objectFit": "contain"},
            ),
        ],
    )


@app.callback(
    Output("heatmap-graph", "figure"),
    Output("detection-risk-card", "children"),
    Output("detection-error", "children"),
    Input("btn-simulate-detection", "n_clicks"),
    State("det-substance", "value"),
    State("det-confidence", "value"),
    State("det-area", "value"),
    State("banner-site", "value"),
)
def simulate_detection(n_clicks, substance, conf, area_ratio, site_id):
    if not n_clicks:
        return empty_history_figure(), html.Div(
            "Clique sur « Simuler la prédiction » pour voir l'impact RiskOps.",
            style={"color": TEXT_MUTED, "fontSize": "12px"},
        ), ""

    try:
        payload = build_demo_payload(
            site_id=site_id or "SITE_001",
            zone_type="production",
            proximity="near_machine",
            floor_type="non_absorbent",
            prod_value_per_hour=8000,
            substance=substance or "oil",
            confidence=(conf or 90) / 100.0,
            area_ratio=area_ratio or 0.3,
        )

        resp = requests.post(RISK_SERVICE_URL, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        # heatmap très simple (juste pour visuel)
        z = [
            [0.1, 0.2, 0.3],
            [0.2, 0.6, 0.4],
            [0.1, 0.3, 0.2],
        ]
        heatmap_fig = go.Figure(
            data=go.Heatmap(z=z, colorscale="YlOrRd")
        )
        heatmap_fig.update_layout(
            title="Exemple de carte de chaleur (zone d'attention IA)",
            xaxis=dict(showticklabels=False),
            yaxis=dict(showticklabels=False),
            margin=dict(l=30, r=20, t=40, b=30),
        )

        severity = data["global_severity_score"]
        level = data["global_severity_level"]
        cost = data["estimated_cost"]
        mitigated_score = data.get("mitigated_severity_score")
        mitigated_level = data.get("mitigated_severity_level")
        mitigated_cost = data.get("mitigated_cost")
        risk_reduction_pct = data.get("risk_reduction_pct")

        saved = None
        roi_pct = None
        if mitigated_cost is not None and cost is not None and mitigated_cost < cost:
            saved = cost - mitigated_cost
            if cost > 0:
                roi_pct = saved / cost * 100.0

        card_children = [
            html.Div("Impact RiskOps (direct)", style={"fontWeight": "600", "marginBottom": "6px"}),
            html.Div(
                [
                    html.Div("Niveau de risque :", style={"fontSize": "12px", "color": TEXT_MUTED}),
                    html.Div(
                        f"{level} ({severity:.1f}/100)",
                        style={
                            "fontSize": "16px",
                            "fontWeight": "700",
                            "color": level_color(level),
                        },
                    ),
                ],
                style={"marginBottom": "6px"},
            ),
            html.Div(
                [
                    html.Div("Coût estimé :", style={"fontSize": "12px", "color": TEXT_MUTED}),
                    html.Div(
                        f"{cost:,.0f} €".replace(",", " "),
                        style={"fontSize": "16px", "fontWeight": "700"},
                    ),
                ],
                style={"marginBottom": "6px"},
            ),
        ]

        if mitigated_score is not None and mitigated_cost is not None:
            card_children.append(
                html.Div(
                    [
                        html.Div("Après mitigation :", style={"fontSize": "12px", "color": TEXT_MUTED}),
                        html.Div(
                            f"{mitigated_level} ({mitigated_score:.1f}/100)",
                            style={
                                "fontSize": "14px",
                                "fontWeight": "600",
                                "color": level_color(mitigated_level),
                            },
                        ),
                        html.Div(
                            f"Coût : {mitigated_cost:,.0f} €".replace(",", " "),
                            style={"fontSize": "12px"},
                        ),
                        html.Div(
                            f"Réduction : {risk_reduction_pct:.1f}%" if risk_reduction_pct is not None else "",
                            style={"fontSize": "11px", "color": "#16a34a", "marginTop": "2px"},
                        ),
                    ],
                    style={"marginBottom": "4px"},
                )
            )

        if saved is not None:
            card_children.append(
                html.Div(
                    [
                        html.Div(
                            "Économie potentielle si plan appliqué :",
                            style={"fontSize": "12px", "color": TEXT_MUTED},
                        ),
                        html.Div(
                            f"{saved:,.0f} €".replace(",", " "),
                            style={"fontSize": "14px", "fontWeight": "600", "color": "#15803d"},
                        ),
                    ],
                    style={"marginTop": "4px"},
                )
            )

        return heatmap_fig, card_children, ""

    except Exception as e:
        return empty_history_figure(), html.Div(
            "Erreur lors de l'appel au service RiskOps.",
            style={"color": "#b91c1c", "fontSize": "12px"},
        ), f"Erreur : {str(e)}"


# ============================================================
#  CALLBACKS RISKOPS (onglet 2 + partie bas de page)
# ============================================================

@app.callback(
    Output("summary-cards", "children"),
    Output("factors-table", "data"),
    Output("explanation-text", "children"),
    Output("raw-json", "children"),
    Output("recommendations-list", "children"),
    Output("history-store", "data"),
    Output("history-graph", "figure"),
    Output("error-message", "children"),
    Input("btn-run", "n_clicks"),
    State("input-site-id", "value"),
    State("input-zone-type", "value"),
    State("input-substance", "value"),
    State("input-proximity", "value"),
    State("input-floor-type", "value"),
    State("input-prod-value", "value"),
    State("history-store", "data"),
)
def run_risk_analysis(
    n_clicks,
    site_id,
    zone_type,
    substance,
    proximity,
    floor_type,
    prod_value_per_hour,
    history_data,
):
    if not n_clicks:
        return [], [], "", "", [], [], empty_history_figure(), ""

    try:
        payload = build_demo_payload(
            site_id=site_id or "SITE_001",
            zone_type=zone_type or "production",
            proximity=proximity or "near_machine",
            floor_type=floor_type or "non_absorbent",
            prod_value_per_hour=prod_value_per_hour or 8000,
            substance=substance or "oil",
        )

        resp = requests.post(RISK_SERVICE_URL, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        severity = data["global_severity_score"]
        level = data["global_severity_level"]
        cost = data["estimated_cost"]

        mitigated_score = data.get("mitigated_severity_score")
        mitigated_level = data.get("mitigated_severity_level")
        mitigated_cost = data.get("mitigated_cost")
        risk_reduction_pct = data.get("risk_reduction_pct")

        # Cartes résumé
        summary_cards = []

        summary_cards.append(
            html.Div(
                style={
                    "background": "linear-gradient(135deg, #eef2ff, #e0ecff)",
                    "padding": "10px 14px",
                    "borderRadius": BORDER_RADIUS,
                    "minWidth": "190px",
                },
                children=[
                    html.Div("Niveau de risque (avant)", style={"fontSize": "11px", "color": TEXT_MUTED}),
                    html.Div(
                        level,
                        style={
                            "fontSize": "20px",
                            "fontWeight": "700",
                            "marginTop": "2px",
                            "color": level_color(level),
                        },
                    ),
                    html.Div(f"Score : {severity:.1f}/100", style={"fontSize": "11px", "marginTop": "2px"}),
                ],
            )
        )

        summary_cards.append(
            html.Div(
                style={
                    "background": "linear-gradient(135deg, #fff7ed, #fffbeb)",
                    "padding": "10px 14px",
                    "borderRadius": BORDER_RADIUS,
                    "minWidth": "190px",
                },
                children=[
                    html.Div("Coût estimé (avant)", style={"fontSize": "11px", "color": TEXT_MUTED}),
                    html.Div(
                        f"{cost:,.0f} €".replace(",", " "),
                        style={"fontSize": "20px", "fontWeight": "700", "marginTop": "2px"},
                    ),
                ],
            )
        )

        saved = None
        roi_pct = None
        if mitigated_score is not None and mitigated_cost is not None:
            summary_cards.append(
                html.Div(
                    style={
                        "background": "linear-gradient(135deg, #ecfdf5, #dcfce7)",
                        "padding": "10px 14px",
                        "borderRadius": BORDER_RADIUS,
                        "minWidth": "210px",
                    },
                    children=[
                        html.Div("Après mitigation", style={"fontSize": "11px", "color": TEXT_MUTED}),
                        html.Div(
                            f"{mitigated_level} ({mitigated_score:.1f}/100)",
                            style={
                                "fontSize": "18px",
                                "fontWeight": "700",
                                "marginTop": "2px",
                                "color": level_color(mitigated_level),
                            },
                        ),
                        html.Div(
                            f"Coût : {mitigated_cost:,.0f} €".replace(",", " "),
                            style={"fontSize": "11px", "marginTop": "2px"},
                        ),
                        html.Div(
                            f"Réduction : {risk_reduction_pct:.1f}%" if risk_reduction_pct is not None else "",
                            style={"fontSize": "11px", "marginTop": "2px", "color": "#15803d"},
                        ),
                    ],
                )
            )

            if mitigated_cost is not None and cost is not None and mitigated_cost < cost:
                saved = cost - mitigated_cost
                if cost > 0:
                    roi_pct = saved / cost * 100.0

        if saved is not None:
            summary_cards.append(
                html.Div(
                    style={
                        "background": "linear-gradient(135deg, #ecfdf3, #dcfce7)",
                        "padding": "10px 14px",
                        "borderRadius": BORDER_RADIUS,
                        "minWidth": "210px",
                    },
                    children=[
                        html.Div("Économie potentielle", style={"fontSize": "11px", "color": TEXT_MUTED}),
                        html.Div(
                            f"{saved:,.0f} €".replace(",", " "),
                            style={"fontSize": "20px", "fontWeight": "700", "marginTop": "2px"},
                        ),
                        html.Div(
                            f"Soit {roi_pct:.1f}% du coût initial" if roi_pct is not None else "",
                            style={"fontSize": "11px", "marginTop": "2px", "color": "#15803d"},
                        ),
                    ],
                )
            )

        factors = data.get("factors", [])
        explanation = data.get("explanation", "")
        raw_json = json.dumps(data, indent=2, ensure_ascii=False)

        # Recommandations
        recs = data.get("recommendations", [])
        if recs:
            rec_children = [html.Li(r) for r in recs]
        else:
            rec_children = [html.Li("Aucune recommandation disponible.")]

        # Historique
        history_data = history_data or []
        new_index = len(history_data) + 1
        history_data.append(
            {
                "index": new_index,
                "score": severity,
                "mitigated_score": mitigated_score,
            }
        )

        x_vals = [h["index"] for h in history_data]
        y_baseline = [h["score"] for h in history_data]
        y_mitigated = [h["mitigated_score"] for h in history_data]

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=x_vals,
                y=y_baseline,
                mode="lines+markers",
                name="Score avant",
            )
        )
        if any(y is not None for y in y_mitigated):
            fig.add_trace(
                go.Scatter(
                    x=x_vals,
                    y=y_mitigated,
                    mode="lines+markers",
                    name="Score après",
                )
            )

        fig.update_layout(
            title="Historique des scores (avant / après mitigation)",
            xaxis_title="Analyse",
            yaxis_title="Score de sévérité",
            template="plotly_white",
            margin=dict(l=40, r=20, t=50, b=40),
        )

        return summary_cards, factors, explanation, raw_json, rec_children, history_data, fig, ""

    except Exception as e:
        return [], [], "", "", [], history_data, empty_history_figure(), f"Erreur : {str(e)}"


# ============================================================
#  RUN
# ============================================================

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(debug=False, host="0.0.0.0", port=port)


