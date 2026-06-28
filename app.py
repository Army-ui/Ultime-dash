# -*- coding: utf-8 -*-
"""
Dashboard de déduplication de fichiers — version modernisée.

Au lancement :
  - Le pipeline complet (scan -> nettoyage -> détection -> enrichissement)
    s'exécute automatiquement en arrière-plan.
  - Un écran de chargement animé affiche la progression en temps réel.
  - Une fois terminé, le dashboard de visualisation s'affiche automatiquement.

Fonctionnalités :
  - Thème clair / sombre (bascule instantanée, sans rechargement).
  - Multilingue FR / EN, détecté automatiquement depuis le navigateur,
    avec bascule manuelle possible.
  - Suppression et archivage réels des fichiers (avec confirmation).
  - Export PDF des doublons filtrés.
"""

import os
import io
import flask
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dash import (
    Dash, html, dcc, dash_table, Output, Input, State,
    ctx, no_update, ALL,
)
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from pipeline.runner import start_pipeline_async, get_state, CLEANED_CSV
from i18n import t, detect_lang_from_header
from file_actions import delete_file, archive_file

# =========================
# CONFIG
# =========================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, CLEANED_CSV)

# Dossier scanné par le pipeline. Modifiable via variable d'environnement
# pour pouvoir cibler un autre répertoire sans toucher au code.
SCAN_TARGET = os.environ.get("DEDUP_SCAN_DIR") or os.path.expanduser("~")
NB_THREADS = int(os.environ.get("DEDUP_THREADS", "4"))

PIPELINE_STEPS = ["scan", "clean", "detect", "enrich"]

server = flask.Flask(__name__)
app = Dash(__name__, server=server, suppress_callback_exceptions=True)
app.title = "Dedup Scanner"


def empty_df():
    """DataFrame vide avec les colonnes attendues, utilisé avant que le
    pipeline n'ait produit le CSV final (évite tout crash de l'UI)."""
    return pd.DataFrame(columns=[
        "nom_fichier", "chemin", "chemin_dossier", "profondeur_dossier",
        "taille_octets", "taille_lisible", "categorie_taille_fichier",
        "extension", "hash_md5", "date_creation", "date_modification",
        "age_fichier", "jours_depuis_modification", "nb_occurrences",
        "est_doublon_exact", "rang_dans_groupe", "id_groupe_doublon",
        "statut_doublon", "type_duplication", "id_groupe", "depot",
        "unite_metier", "proprietaire",
    ])


def load_dataframe():
    """Charge le CSV final produit par le pipeline, si disponible."""
    if os.path.exists(CSV_PATH):
        try:
            df = pd.read_csv(CSV_PATH)
            # Colonne dérivée utilisée par l'UI pour le marquage de suppression
            if "a_supprimer" not in df.columns:
                df["a_supprimer"] = False
            return df
        except Exception:
            return empty_df()
    return empty_df()


def empty_figure(theme="dark", message="—"):
    """Figure Plotly vide et thémée, affichée tant qu'il n'y a pas de données."""
    fig = go.Figure()
    fig.update_layout(**plotly_layout_theme(theme))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.add_annotation(
        text=message,
        xref="paper", yref="paper",
        x=0.5, y=0.5,
        showarrow=False,
        font=dict(size=13, color="#5C6472" if theme == "dark" else "#9C9586"),
    )
    return fig


def plotly_layout_theme(theme):
    """Renvoie les kwargs de layout Plotly adaptés au thème courant."""
    if theme == "light":
        paper = "#FFFFFF"
        plot = "#FFFFFF"
        font_color = "#211D17"
        grid = "#ECE9E2"
    else:
        paper = "#11151D"
        plot = "#11151D"
        font_color = "#EDEEF0"
        grid = "#232A37"

    return dict(
        paper_bgcolor=paper,
        plot_bgcolor=plot,
        font=dict(color=font_color, family="Space Grotesk, sans-serif", size=12),
        margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(gridcolor=grid, zerolinecolor=grid),
        yaxis=dict(gridcolor=grid, zerolinecolor=grid),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        colorway=["#C77D34", "#3D9E92", "#C9594C", "#8E96A3", "#E0A05C", "#277A70"],
    )


def style_figure(fig, theme):
    fig.update_layout(**plotly_layout_theme(theme))
    return fig


# =========================
# LAYOUT — STORES & ROOT
# =========================

def kpi_card(label, kpi_id, color_var):
    return html.Div(
        [
            html.Div(label, className="kpi-label", id=f"{kpi_id}-label"),
            html.Div("0", className="kpi-value", id=kpi_id),
        ],
        className="kpi-card",
        style={"--kpi-accent": color_var},
    )


def build_scan_screen(lang="fr"):
    return html.Div(
        className="scan-screen",
        id="scan-screen",
        children=[
            # Le SVG radar est injecté côté client (voir assets/radar.js)
            # car dash.html ne propose pas de wrappers pour les balises SVG.
            html.Div(className="scan-radar", id="radar-svg-mount"),

            html.Div(t(lang, "scanning_title"), className="scan-title", id="scan-title"),
            html.Div(t(lang, "scanning_subtitle"), className="scan-subtitle", id="scan-subtitle"),

            html.Div(className="scan-steps", id="scan-steps", children=_build_steps(0, lang)),

            html.Div(className="scan-progress-track", children=[
                html.Div(className="scan-progress-fill", id="scan-progress-fill", style={"width": "0%"})
            ]),

            html.Div(className="scan-console", id="scan-console"),

            dcc.Interval(id="scan-poll-interval", interval=600, n_intervals=0),
        ],
    )


def _build_steps(active_step, lang="fr"):
    labels = [t(lang, f"step_{s}") for s in PIPELINE_STEPS]
    children = []
    for idx, label in enumerate(labels, start=1):
        state = "is-done" if idx < active_step else ("is-active" if idx == active_step else "")
        children.append(
            html.Div(className=f"scan-step {state}".strip(), children=[
                html.Div(className=f"scan-step-led {state}".strip()),
                html.Div(label, className="scan-step-label"),
            ])
        )
        if idx < len(labels):
            connector_state = "is-done" if idx < active_step else ""
            children.append(html.Div(className=f"scan-connector {connector_state}".strip()))
    return children


def build_dashboard(lang="fr", theme="dark"):
    return html.Div(
        className="main-content",
        id="dashboard-content",
        children=[

            html.Div(className="kpi-row", children=[
                kpi_card(t(lang, "kpi_total"), "kpi-files", "var(--accent-copper)"),
                kpi_card(t(lang, "kpi_exact"), "kpi-duplicates", "var(--accent-coral)"),
                kpi_card(t(lang, "kpi_groups"), "kpi-groups", "var(--accent-teal)"),
                kpi_card(t(lang, "kpi_space"), "kpi-space", "var(--accent-copper)"),
            ]),

            html.Div(className="filter-panel", children=[
                html.Div(className="filter-field", children=[
                    html.Label(t(lang, "filter_depot"), className="filter-label", id="label-filter-depot"),
                    dcc.Dropdown(id="depot_filter", multi=True, placeholder="—"),
                ]),
                html.Div(className="filter-field", children=[
                    html.Label(t(lang, "filter_extension"), className="filter-label", id="label-filter-extension"),
                    dcc.Dropdown(id="extension_filter", multi=True, placeholder="—"),
                ]),
            ]),

            html.Div(className="chart-grid-2", children=[
                html.Div(className="chart-card", children=[
                    html.Div(t(lang, "chart_top_ext"), className="section-title", id="title-chart-ext"),
                    dcc.Graph(id="graph-extension", config={"displayModeBar": False}),
                ]),
                html.Div(className="chart-card", children=[
                    html.Div(t(lang, "chart_status"), className="section-title", id="title-chart-status"),
                    dcc.Graph(id="graph-dup", config={"displayModeBar": False}),
                ]),
            ]),

            html.Div(className="chart-grid-2", children=[
                html.Div(className="chart-card", children=[
                    html.Div(t(lang, "chart_top_depot"), className="section-title", id="title-chart-depot"),
                    dcc.Graph(id="graph-depot", config={"displayModeBar": False}),
                ]),
                html.Div(className="chart-card", children=[
                    html.Div(t(lang, "chart_top_group"), className="section-title", id="title-chart-group"),
                    dcc.Graph(id="graph-group", config={"displayModeBar": False}),
                ]),
            ]),

            html.Div(className="toolbar-row", children=[
                html.Button([" 📥 ", html.Span(t(lang, "btn_export"), id="label-btn-export")],
                            id="btn-export", className="control-pill-btn"),
                html.Button([" 📦 ", html.Span(t(lang, "btn_archive_selected"), id="label-btn-archive")],
                            id="btn-archive-selected", className="control-pill-btn secondary"),
                html.Button([" 🗑️ ", html.Span(t(lang, "btn_delete_selected"), id="label-btn-delete")],
                            id="btn-delete-selected", className="control-pill-btn secondary"),
                html.Div(id="selection-counter", className="selection-counter"),
            ]),

            dcc.Download(id="download-pdf"),

            html.Div(className="table-card", children=[
                html.Div(t(lang, "table_title"), className="section-title", id="title-table"),
                dash_table.DataTable(
                    id="table",
                    columns=_table_columns(lang),
                    page_size=10,
                    row_selectable="multi",
                    selected_rows=[],
                    style_table={"overflowX": "auto"},
                    style_header={"backgroundColor": "var(--bg-subtle)", "fontWeight": "600"},
                    style_cell={"padding": "12px", "backgroundColor": "var(--bg-card)", "border": "none"},
                    style_data_conditional=[
                        {
                            "if": {"filter_query": "{a_supprimer} = True"},
                            "backgroundColor": "var(--accent-coral-soft)",
                            "color": "var(--accent-coral)",
                            "fontWeight": "600",
                        }
                    ],
                ),
            ]),

            # Modale de confirmation (delete / archive)
            html.Div(id="confirm-modal-mount"),

            # Pile de notifications toast
            html.Div(id="toast-stack", className="toast-stack"),

            # Stores internes
            dcc.Store(id="pending-action-store"),  # {"type": "delete"|"archive", "paths": [...]}
            dcc.Store(id="refresh-trigger-store", data=0),
        ],
    )


def _table_columns(lang):
    return [
        {"name": t(lang, "col_name"), "id": "nom_fichier"},
        {"name": t(lang, "col_path"), "id": "chemin"},
        {"name": t(lang, "col_size"), "id": "taille_lisible"},
        {"name": t(lang, "col_status"), "id": "statut_doublon"},
        {"name": t(lang, "col_delete"), "id": "delete", "presentation": "markdown"},
        {"name": t(lang, "col_archive"), "id": "archive", "presentation": "markdown"},
    ]


# =========================
# ROOT LAYOUT
# =========================

app.layout = html.Div(id="theme-root", children=[

    dcc.Store(id="lang-store", data="fr"),
    dcc.Store(id="theme-store", data="dark"),
    dcc.Store(id="lang-initialized", data=False),

    html.Div(className="app-shell", id="app-shell", children=[

        html.Div(className="topbar", children=[
            html.Div(className="brand-block", children=[
                html.Div("◎", className="brand-mark"),
                html.Div([
                    html.Div(t("fr", "app_title"), className="brand-text-title", id="brand-title"),
                    html.Div(t("fr", "app_subtitle"), className="brand-text-subtitle", id="brand-subtitle"),
                ])
            ]),
            html.Div(className="topbar-controls", children=[
                html.Button("FR / EN", id="btn-lang-toggle", className="icon-toggle-btn"),
                html.Button("🌙 Sombre", id="btn-theme-toggle", className="icon-toggle-btn"),
            ]),
        ]),

        html.Div(id="page-body", children=[
            build_scan_screen("fr"),
        ]),
    ]),
])


# =========================
# CALLBACK : DÉMARRAGE AUTOMATIQUE DU PIPELINE
# =========================
# Lancé une seule fois au tout premier rendu du serveur (pas par session,
# car le pipeline scanne le disque serveur, pas le navigateur du client).

_PIPELINE_LAUNCHED = {"started": False}
_launch_lock = __import__("threading").Lock()


@server.before_request
def _maybe_launch_pipeline():
    with _launch_lock:
        if not _PIPELINE_LAUNCHED["started"]:
            _PIPELINE_LAUNCHED["started"] = True
            start_pipeline_async(dossier_cible=SCAN_TARGET, nb_threads=NB_THREADS)


# =========================
# CALLBACK : DÉTECTION DE LA LANGUE NAVIGATEUR (au premier chargement)
# =========================

@app.callback(
    Output("lang-store", "data"),
    Output("lang-initialized", "data"),
    Input("lang-initialized", "data"),
    prevent_initial_call=False,
)
def detect_browser_language(already_init):
    if already_init:
        return no_update, no_update
    accept_language = flask.request.headers.get("Accept-Language", "")
    lang = detect_lang_from_header(accept_language)
    return lang, True


# =========================
# CALLBACK : BASCULE LANGUE / THÈME (boutons topbar)
# =========================

@app.callback(
    Output("lang-store", "data", allow_duplicate=True),
    Input("btn-lang-toggle", "n_clicks"),
    State("lang-store", "data"),
    prevent_initial_call=True,
)
def toggle_lang(n_clicks, current_lang):
    return "en" if current_lang == "fr" else "fr"


@app.callback(
    Output("theme-store", "data"),
    Input("btn-theme-toggle", "n_clicks"),
    State("theme-store", "data"),
    prevent_initial_call=True,
)
def toggle_theme(n_clicks, current_theme):
    return "light" if current_theme == "dark" else "dark"


# Applique l'attribut data-theme sur la racine HTML (clientside, instantané)
app.clientside_callback(
    """
    function(theme) {
        document.documentElement.setAttribute('data-theme', theme || 'dark');
        return window.dash_clientside.no_update;
    }
    """,
    Output("theme-root", "title"),
    Input("theme-store", "data"),
)


@app.callback(
    Output("btn-theme-toggle", "children"),
    Output("btn-lang-toggle", "children"),
    Input("theme-store", "data"),
    Input("lang-store", "data"),
)
def update_toggle_labels(theme, lang):
    theme_label = ("🌙 " + t(lang, "theme_dark")) if theme == "dark" else ("☀️ " + t(lang, "theme_light"))
    lang_label = "FR 🇫🇷" if lang == "fr" else "EN 🇬🇧"
    return theme_label, lang_label


@app.callback(
    Output("brand-title", "children"),
    Output("brand-subtitle", "children"),
    Input("lang-store", "data"),
)
def update_brand_text(lang):
    return t(lang, "app_title"), t(lang, "app_subtitle")


# =========================
# CALLBACK : POLLING DE L'ÉTAT DU PIPELINE
# =========================

@app.callback(
    Output("page-body", "children"),
    Output("scan-title", "children"),
    Output("scan-subtitle", "children"),
    Output("scan-steps", "children"),
    Output("scan-progress-fill", "style"),
    Output("scan-console", "children"),
    Input("scan-poll-interval", "n_intervals"),
    State("lang-store", "data"),
    State("theme-store", "data"),
    prevent_initial_call=False,
)
def poll_pipeline(n_intervals, lang, theme):
    lang = lang or "fr"
    state = get_state()
    status = state["status"]
    step = state["step"]
    progress = state["progress"]
    logs = state["logs"][-12:]

    console_children = [
        html.Div(line, className=f"scan-console-line{' is-latest' if i == len(logs) - 1 else ''}")
        for i, line in enumerate(logs)
    ] or [html.Div("…", className="scan-console-line")]

    steps_children = _build_steps(step, lang)
    fill_style = {"width": f"{progress}%"}

    if status == "done":
        return (
            build_dashboard(lang, theme),
            no_update, no_update, no_update, no_update, no_update,
        )

    if status == "error":
        subtitle = f"❌ {state.get('error', 'Erreur inconnue')}"
        return (
            no_update,
            t(lang, "scanning_title"),
            subtitle,
            steps_children,
            fill_style,
            console_children,
        )

    return (
        no_update,
        t(lang, "scanning_title"),
        t(lang, "scanning_subtitle"),
        steps_children,
        fill_style,
        console_children,
    )


# =========================
# CALLBACK : INITIALISATION DES OPTIONS DE FILTRES
# =========================

@app.callback(
    Output("depot_filter", "options"),
    Output("extension_filter", "options"),
    Input("dashboard-content", "id"),  # se déclenche dès que le dashboard est monté
    prevent_initial_call=False,
)
def init_filter_options(_):
    df = load_dataframe()
    if df.empty or "depot" not in df.columns:
        return [], []
    depot_opts = [{"label": d, "value": d} for d in sorted(df["depot"].dropna().unique())]
    ext_opts = [{"label": e, "value": e} for e in sorted(df["extension"].dropna().unique())]
    return depot_opts, ext_opts


# =========================
# CALLBACK PRINCIPAL : KPI + GRAPHIQUES + TABLE
# =========================

@app.callback(
    Output("table", "data"),
    Output("table", "columns"),
    Output("kpi-files", "children"),
    Output("kpi-duplicates", "children"),
    Output("kpi-groups", "children"),
    Output("kpi-space", "children"),
    Output("graph-extension", "figure"),
    Output("graph-dup", "figure"),
    Output("graph-depot", "figure"),
    Output("graph-group", "figure"),
    Input("depot_filter", "value"),
    Input("extension_filter", "value"),
    Input("lang-store", "data"),
    Input("theme-store", "data"),
    Input("refresh-trigger-store", "data"),
)
def update_dashboard(depot, extension, lang, theme, _refresh):
    lang = lang or "fr"
    theme = theme or "dark"
    df = load_dataframe()

    if df.empty or "est_doublon_exact" not in df.columns:
        empty_fig = empty_figure(theme, t(lang, "no_duplicates"))
        return (
            [], _table_columns(lang),
            "0", "0", "0", "0 MB",
            empty_fig, empty_fig, empty_fig, empty_fig,
        )

    dff = df.copy()

    if depot:
        dff = dff[dff["depot"].isin(depot)]
    if extension:
        dff = dff[dff["extension"].isin(extension)]

    # ✅ FILTRE UNIQUEMENT DOUBLONS
    df_dup = dff[dff["est_doublon_exact"] == True].copy()

    # KPI
    total = len(df_dup)
    duplicates = total
    groups = df_dup["id_groupe"].nunique() if len(df_dup) else 0

    # Espace récupérable = somme des tailles des copies en trop par groupe
    # (on garde 1 exemplaire "Original" par groupe, le reste est récupérable).
    if len(df_dup):
        espace_recuperable_octets = df_dup.loc[
            df_dup["statut_doublon"] != "Original", "taille_octets"
        ].sum()
    else:
        espace_recuperable_octets = 0
    space = espace_recuperable_octets / (1024 * 1024)

    total_fmt = f"{total:,}".replace(",", " ")
    duplicates_fmt = f"{duplicates:,}".replace(",", " ")
    groups_fmt = f"{groups:,}".replace(",", " ")
    space_fmt = f"{space:,.2f} MB".replace(",", " ")

    # Boutons visuels d'action sur chaque ligne
    df_dup["delete"] = "🗑️"
    df_dup["archive"] = "📦"

    # GRAPHIQUES (basés sur doublons)
    if len(df_dup):
        fig_ext = px.bar(df_dup["extension"].value_counts().head(10),
                          color_discrete_sequence=["#C77D34"])

        # Pour le pie de statut, on regroupe par motif générique
        # ("Original" vs "Doublon") plutôt que par numéro exact de doublon,
        # sinon un grand nombre de groupes fait exploser le nombre de
        # tranches (Doublon #1, #2, #3... #150) et rend le graphique illisible.
        statut_generique = df_dup["statut_doublon"].apply(
            lambda s: "Original" if s == "Original" else "Doublon"
        )
        fig_dup = px.pie(
            names=statut_generique,
            hole=0.55,
            color=statut_generique,
            color_discrete_map={"Original": "#C77D34", "Doublon": "#3D9E92"},
        )

        fig_depot = px.bar(df_dup["depot"].value_counts().head(10),
                            color_discrete_sequence=["#3D9E92"])
        fig_group = px.bar(df_dup["id_groupe"].value_counts().head(10),
                            color_discrete_sequence=["#C9594C"])
    else:
        fig_ext = fig_dup = fig_depot = fig_group = empty_figure(theme, t(lang, "no_duplicates"))

    fig_ext = style_figure(fig_ext, theme)
    fig_dup = style_figure(fig_dup, theme)
    fig_depot = style_figure(fig_depot, theme)
    fig_group = style_figure(fig_group, theme)

    for fig in (fig_ext, fig_depot, fig_group):
        fig.update_traces(marker_line_width=0)
        fig.update_layout(showlegend=False, bargap=0.35, yaxis_title=None, xaxis_title=None)

    return (
        df_dup.to_dict("records"),
        _table_columns(lang),
        total_fmt,
        duplicates_fmt,
        groups_fmt,
        space_fmt,
        fig_ext,
        fig_dup,
        fig_depot,
        fig_group,
    )


# =========================
# CALLBACK : LABELS DYNAMIQUES (filtres, charts, table) SELON LA LANGUE
# =========================

@app.callback(
    Output("label-filter-depot", "children"),
    Output("label-filter-extension", "children"),
    Output("title-chart-ext", "children"),
    Output("title-chart-status", "children"),
    Output("title-chart-depot", "children"),
    Output("title-chart-group", "children"),
    Output("title-table", "children"),
    Output("label-btn-export", "children"),
    Output("label-btn-archive", "children"),
    Output("label-btn-delete", "children"),
    Output("kpi-files-label", "children"),
    Output("kpi-duplicates-label", "children"),
    Output("kpi-groups-label", "children"),
    Output("kpi-space-label", "children"),
    Input("lang-store", "data"),
)
def update_dashboard_labels(lang):
    lang = lang or "fr"
    return (
        t(lang, "filter_depot"),
        t(lang, "filter_extension"),
        t(lang, "chart_top_ext"),
        t(lang, "chart_status"),
        t(lang, "chart_top_depot"),
        t(lang, "chart_top_group"),
        t(lang, "table_title"),
        t(lang, "btn_export"),
        t(lang, "btn_archive_selected"),
        t(lang, "btn_delete_selected"),
        t(lang, "kpi_total"),
        t(lang, "kpi_exact"),
        t(lang, "kpi_groups"),
        t(lang, "kpi_space"),
    )


# =========================
# CALLBACK : COMPTEUR DE SÉLECTION
# =========================

@app.callback(
    Output("selection-counter", "children"),
    Input("table", "selected_rows"),
    State("lang-store", "data"),
)
def update_selection_counter(selected_rows, lang):
    lang = lang or "fr"
    n = len(selected_rows) if selected_rows else 0
    if n == 0:
        return ""
    return html.Span([html.Strong(str(n)), f" {t(lang, 'selected_count')}"])


# =========================
# CALLBACK : CLIC SUR UNE CELLULE D'ACTION -> OUVRE LA MODALE
# =========================

@app.callback(
    Output("pending-action-store", "data"),
    Output("confirm-modal-mount", "children"),
    Input("table", "active_cell"),
    Input("btn-archive-selected", "n_clicks"),
    Input("btn-delete-selected", "n_clicks"),
    State("table", "data"),
    State("table", "selected_rows"),
    State("lang-store", "data"),
    prevent_initial_call=True,
)
def open_confirm_modal(active_cell, n_archive_sel, n_delete_sel, data, selected_rows, lang):
    lang = lang or "fr"
    triggered = ctx.triggered_id

    if triggered == "table" and active_cell:
        row = active_cell["row"]
        col = active_cell["column_id"]
        if col not in ("delete", "archive") or row >= len(data):
            return no_update, no_update
        path = data[row]["chemin"]
        action_type = "delete" if col == "delete" else "archive"
        paths = [path]

    elif triggered == "btn-archive-selected":
        if not selected_rows:
            return no_update, no_update
        action_type = "archive"
        paths = [data[i]["chemin"] for i in selected_rows if i < len(data)]

    elif triggered == "btn-delete-selected":
        if not selected_rows:
            return no_update, no_update
        action_type = "delete"
        paths = [data[i]["chemin"] for i in selected_rows if i < len(data)]

    else:
        return no_update, no_update

    if not paths:
        return no_update, no_update

    modal = _build_confirm_modal(action_type, paths, lang)
    return {"type": action_type, "paths": paths}, modal


def _build_confirm_modal(action_type, paths, lang):
    is_delete = action_type == "delete"
    title = t(lang, "modal_delete_title") if is_delete else t(lang, "modal_archive_title")
    body_label = t(lang, "modal_delete_body") if is_delete else t(lang, "modal_archive_body")

    preview_paths = paths[:5]
    extra = len(paths) - len(preview_paths)
    body_lines = [html.Div(p) for p in preview_paths]
    if extra > 0:
        body_lines.append(html.Div(f"… +{extra}"))

    return html.Div(className="modal-overlay", id="confirm-modal-overlay", children=[
        html.Div(className="modal-box", children=[
            html.Div(title, className="modal-title"),
            html.Div([html.Div(body_label, style={
                "fontFamily": "var(--font-display)", "color": "var(--text-primary)",
                "marginBottom": "10px", "fontSize": "13.5px"
            })] + body_lines, className="modal-body"),
            html.Div(className="modal-actions", children=[
                html.Button(t(lang, "modal_cancel"), id="btn-modal-cancel",
                             className="control-pill-btn secondary"),
                html.Button(t(lang, "modal_confirm"), id="btn-modal-confirm",
                             className="control-pill-btn",
                             style={"background": "var(--accent-coral)"} if is_delete else None),
            ]),
        ]),
    ])


# =========================
# CALLBACK : ANNULER LA MODALE
# =========================

@app.callback(
    Output("confirm-modal-mount", "children", allow_duplicate=True),
    Output("pending-action-store", "data", allow_duplicate=True),
    Input("btn-modal-cancel", "n_clicks"),
    prevent_initial_call=True,
)
def cancel_modal(n_clicks):
    if not n_clicks:
        return no_update, no_update
    return None, None


# =========================
# CALLBACK : CONFIRMER L'ACTION (suppression / archivage réels)
# =========================

@app.callback(
    Output("confirm-modal-mount", "children", allow_duplicate=True),
    Output("pending-action-store", "data", allow_duplicate=True),
    Output("toast-stack", "children"),
    Output("refresh-trigger-store", "data"),
    Input("btn-modal-confirm", "n_clicks"),
    State("pending-action-store", "data"),
    State("toast-stack", "children"),
    State("lang-store", "data"),
    State("refresh-trigger-store", "data"),
    prevent_initial_call=True,
)
def confirm_action(n_clicks, pending, existing_toasts, lang, refresh_count):
    lang = lang or "fr"
    if not n_clicks or not pending:
        return no_update, no_update, no_update, no_update

    action_type = pending["type"]
    paths = pending["paths"]

    success_count = 0
    fail_count = 0

    for path in paths:
        if action_type == "delete":
            ok, _msg = delete_file(path)
        else:
            ok, _msg, _dest = archive_file(path)
        if ok:
            success_count += 1
        else:
            fail_count += 1

    # Met à jour le CSV source pour retirer/marquer les fichiers traités
    _sync_csv_after_action(paths, action_type)

    toasts = list(existing_toasts or [])
    if success_count:
        label = t(lang, "toast_deleted") if action_type == "delete" else t(lang, "toast_archived")
        css_class = "toast toast-danger" if action_type == "delete" else "toast"
        toasts.append(html.Div(f"✅ {label} ({success_count})", className=css_class,
                                key=f"toast-ok-{n_clicks}"))
    if fail_count:
        toasts.append(html.Div(f"⚠️ {t(lang, 'toast_error')} ({fail_count})",
                                className="toast toast-warn", key=f"toast-fail-{n_clicks}"))

    # Garde uniquement les 4 derniers toasts affichés
    toasts = toasts[-4:]

    return None, None, toasts, (refresh_count or 0) + 1


def _sync_csv_after_action(paths, action_type):
    """Retire du CSV final les fichiers supprimés/archivés, pour que le
    dashboard reflète l'état réel du disque sans relancer tout le pipeline."""
    if not os.path.exists(CSV_PATH):
        return
    try:
        df = pd.read_csv(CSV_PATH)
        df = df[~df["chemin"].isin(paths)]
        df.to_csv(CSV_PATH, index=False)
    except Exception:
        pass


# =========================
# CALLBACK : EXPORT PDF
# =========================

@app.callback(
    Output("download-pdf", "data"),
    Input("btn-export", "n_clicks"),
    State("depot_filter", "value"),
    State("extension_filter", "value"),
    prevent_initial_call=True,
)
def export_pdf(n_clicks, depot, extension):
    df = load_dataframe()
    if df.empty or "est_doublon_exact" not in df.columns:
        return no_update

    dff = df.copy()

    if depot:
        dff = dff[dff["depot"].isin(depot)]
    if extension:
        dff = dff[dff["extension"].isin(extension)]

    df_dup = dff[dff["est_doublon_exact"] == True]

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=letter)

    width, height = letter
    y = height - 40

    pdf.drawString(30, y, "Export doublons")
    y -= 20

    cols = ["nom_fichier", "chemin", "taille_lisible"]

    for _, row in df_dup.head(100).iterrows():
        line = " | ".join([str(row[c])[:30] for c in cols])
        pdf.drawString(30, y, line)
        y -= 15

        if y < 40:
            pdf.showPage()
            y = height - 40

    pdf.save()
    buffer.seek(0)

    return dcc.send_bytes(buffer.read(), "doublons.pdf")


# =========================
# RUN
# =========================
if __name__ == "__main__":
    debug_mode = os.environ.get("DEDUP_DEBUG", "0") == "1"
    app.run(debug=debug_mode, host="0.0.0.0", port=8050, use_reloader=False)