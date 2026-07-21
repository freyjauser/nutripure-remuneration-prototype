# -*- coding: utf-8 -*-
"""
Nutripure — Prototype calculateur de rémunération influenceurs.
Palette officielle Nutripure (#00557c / #77d2f5 / #1B1B1B / #ffffff).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

_LOGO_SVG = Path("assets/nutripure_logo.svg").read_text(encoding="utf-8")

from nutripure_core import (
    COL_CA_12M, COL_CA_MOIS, COL_CHANNEL, COL_CONTRAT, COL_DATE_DEBUT,
    COL_DATE_SIGNATURE, COL_HANDLE, COL_ID, COL_RESPONSABLE,
    COL_STATUT_TVA, COL_VERSION,
    Resultat,
    calcule_remuneration, calcule_tendance, genere_message, parse_contrat,
    _fmt,
)

CSV_PATH = "influenceurs_echantillon.csv"

st.set_page_config(
    page_title="Nutripure — Cycle rémunérations",
    layout="wide",
    page_icon="assets/nutripure_favicon.ico",
    initial_sidebar_state="expanded",
)

# ── CSS moderne ────────────────────────────────────────────────────────────────

st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">

<style>
    /* Base typography */
    html, body, [class*="css"], .stApp, .stMarkdown, div[data-testid="stText"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        color: #1B1B1B;
    }
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Inter', -apple-system, sans-serif;
        letter-spacing: -0.02em;
        color: #0f172a;
    }

    /* Hide default Streamlit chrome */
    #MainMenu, header[data-testid="stHeader"], footer, .stDeployButton {
        display: none !important;
    }
    [data-testid="stToolbar"] {
        display: none !important;
    }
    /* Reduce Streamlit default padding */
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 3rem;
        max-width: 1600px;
    }

    /* Nutripure header */
    .nutripure-header {
        display: flex;
        align-items: center;
        gap: 18px;
        padding-bottom: 24px;
        margin-bottom: 24px;
        border-bottom: 1px solid #e2e8f0;
    }
    .nutripure-header svg {
        height: 34px;
        width: auto;
        display: block;
    }
    .brand-separator {
        color: #cbd5e1;
        font-size: 24px;
        font-weight: 300;
    }
    .tool-name {
        color: #475569;
        font-size: 15px;
        font-weight: 600;
        letter-spacing: -0.01em;
    }
    .tool-tag {
        margin-left: auto;
        background: #dbeafe;
        color: #1e40af;
        font-size: 11px;
        font-weight: 700;
        padding: 5px 12px;
        border-radius: 20px;
        letter-spacing: 0.05em;
    }

    /* Metric cards — bordered containers */
    div[data-testid="stVerticalBlockBorderWrapper"] {
        background: #ffffff;
        border-radius: 12px !important;
        border: 1px solid #e2e8f0 !important;
        box-shadow: 0 1px 2px rgba(0, 0, 0, 0.03);
        transition: box-shadow 0.15s, transform 0.15s;
    }
    div[data-testid="stVerticalBlockBorderWrapper"]:hover {
        box-shadow: 0 4px 14px rgba(0, 85, 124, 0.08);
    }
    [data-testid="stMetricLabel"] p {
        font-size: 12px !important;
        font-weight: 600 !important;
        color: #64748b !important;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    [data-testid="stMetricValue"] {
        color: #00557c !important;
        font-weight: 700 !important;
        font-size: 30px !important;
        line-height: 1.1 !important;
    }
    [data-testid="stMetricValue"] > div {
        color: #00557c !important;
        font-weight: 700 !important;
    }

    /* Buttons */
    .stButton > button, .stDownloadButton > button {
        border-radius: 10px;
        font-weight: 600;
        border: 1px solid #e2e8f0;
        transition: all 0.15s;
    }
    .stDownloadButton > button {
        background: #00557c;
        color: white;
        border-color: #00557c;
    }
    .stDownloadButton > button:hover {
        background: #003d5c;
        border-color: #003d5c;
        color: white;
    }

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        border-bottom: 1px solid #e2e8f0;
    }
    .stTabs [data-baseweb="tab"] {
        font-weight: 600;
        color: #64748b;
        padding: 10px 4px;
    }
    .stTabs [aria-selected="true"] {
        color: #00557c !important;
    }

    /* Expanders */
    .streamlit-expanderHeader, [data-testid="stExpander"] summary {
        font-weight: 600 !important;
        color: #0f172a !important;
    }

    /* Sidebar */
    [data-testid="stSidebar"] {
        background: #f8fafc;
        border-right: 1px solid #e2e8f0;
    }
    [data-testid="stSidebar"] h2 {
        font-size: 16px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: #64748b;
        font-weight: 700;
    }

    /* Legend chips */
    .legend-row {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 6px 0;
        font-size: 13px;
        color: #334155;
    }
    .legend-chip {
        width: 14px;
        height: 14px;
        border-radius: 4px;
        flex-shrink: 0;
    }

    /* Section titles */
    .section-title {
        font-size: 20px;
        font-weight: 700;
        color: #0f172a;
        margin: 32px 0 16px 0;
        letter-spacing: -0.02em;
    }
    .section-subtitle {
        font-size: 14px;
        color: #64748b;
        margin-bottom: 20px;
        font-weight: 500;
    }

    /* Copy hint */
    .copy-hint {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        color: #64748b;
        font-size: 12px;
        margin-bottom: 8px;
    }

    /* Dataframe */
    [data-testid="stDataFrame"] {
        border-radius: 12px;
        overflow: hidden;
        border: 1px solid #e2e8f0;
    }

    /* Reduce heading margins */
    h1 { font-size: 26px !important; margin-bottom: 4px !important; }
    h2 { font-size: 20px !important; }
    h3 { font-size: 16px !important; }

    /* Pipeline diagram */
    .pipeline-grid {
        display: grid;
        grid-template-columns: 1fr 24px 1fr 24px 1fr 24px 1fr;
        gap: 0;
        align-items: stretch;
        margin: 8px 0 8px 0;
    }
    .pipeline-card {
        background: #ffffff;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 16px 16px 14px 16px;
        display: flex;
        flex-direction: column;
        gap: 6px;
        box-shadow: 0 1px 2px rgba(0,0,0,0.03);
        position: relative;
        overflow: hidden;
        min-height: 150px;
    }
    .pipeline-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #00557c 0%, #77d2f5 100%);
    }
    .pipeline-step {
        display: flex;
        align-items: center;
        gap: 8px;
        margin: 4px 0 2px 0;
    }
    .pipeline-num {
        background: #eff6ff;
        color: #00557c;
        font-weight: 800;
        font-size: 10px;
        padding: 3px 7px;
        border-radius: 5px;
        letter-spacing: 0.08em;
    }
    .pipeline-title {
        font-weight: 700;
        color: #0f172a;
        font-size: 14px;
        letter-spacing: -0.01em;
        text-transform: uppercase;
    }
    .pipeline-items {
        list-style: none;
        padding: 0;
        margin: 2px 0 8px 0;
        font-size: 12.5px;
        color: #475569;
        line-height: 1.5;
    }
    .pipeline-items li {
        padding: 1px 0;
    }
    .pipeline-badge {
        margin-top: auto;
        display: inline-block;
        background: #f1f5f9;
        color: #475569;
        font-size: 10.5px;
        font-weight: 600;
        padding: 3px 9px;
        border-radius: 20px;
        width: fit-content;
        letter-spacing: 0.02em;
        text-transform: uppercase;
    }
    .pipeline-badge.warn {
        background: #fef3c7;
        color: #92400e;
    }
    .pipeline-badge.ok {
        background: #d1fae5;
        color: #065f46;
    }
    .pipeline-arrow {
        display: flex;
        align-items: center;
        justify-content: center;
        color: #94a3b8;
        font-size: 18px;
        font-weight: 300;
    }

    /* Version chip */
    .version-strip {
        display: flex;
        align-items: center;
        gap: 10px;
        background: #f8fafc;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        padding: 10px 14px;
        margin: 4px 0 12px 0;
    }
    .version-chip {
        background: #00557c;
        color: white;
        font-weight: 700;
        font-size: 12px;
        padding: 4px 10px;
        border-radius: 6px;
        letter-spacing: 0.03em;
    }
    .version-meta {
        font-size: 13px;
        color: #475569;
    }
    .version-meta strong {
        color: #0f172a;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────

_LOGO_INLINE = " ".join(_LOGO_SVG.split())
st.markdown(
    "<div class='nutripure-header'>"
    f"{_LOGO_INLINE}"
    "<div class='brand-separator'>|</div>"
    "<div class='tool-name'>Cycle rémunérations</div>"
    "<div class='tool-tag'>PROTOTYPE</div>"
    "</div>",
    unsafe_allow_html=True,
)

st.markdown(
    "<div class='section-subtitle'>Parsing hybride (regex déterministe + LLM Gemini fallback) → calcul TVA → messages prêts à envoyer.</div>",
    unsafe_allow_html=True,
)


# ── Chargement + traitement ────────────────────────────────────────────────────

@st.cache_data(show_spinner="Parsing des contrats…")
def process_all(csv_path: str, autoriser_llm: bool) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    rows = []
    for _, row in df.iterrows():
        texte    = str(row[COL_CONTRAT])
        ca       = float(row[COL_CA_MOIS])
        ca_12m   = float(row.get(COL_CA_12M, 0) or 0)
        statut   = str(row.get(COL_STATUT_TVA, "inconnu") or "inconnu")
        channel  = str(row.get(COL_CHANNEL, "dm_instagram") or "dm_instagram")
        date_deb = str(row.get(COL_DATE_DEBUT, "") or "")
        version  = int(row.get(COL_VERSION, 1) or 1)
        date_sig = str(row.get(COL_DATE_SIGNATURE, "") or "")

        contrat  = parse_contrat(texte, autoriser_llm=autoriser_llm)
        resultat = calcule_remuneration(contrat, ca, statut_tva=statut)
        tendance = calcule_tendance(ca, ca_12m, date_debut=date_deb)

        rows.append({
            "ID":                        str(row.get(COL_ID, "")),
            "Influenceur":               row[COL_HANDLE],
            "Responsable":               row[COL_RESPONSABLE],
            "CA mois (€ HT)":            ca,
            "CA 12M (€ HT)":             ca_12m,
            "Tendance":                  tendance,
            "Type contrat":              contrat.type_detecte,
            "Version":                   f"v{version} · {date_sig}",
            "Source parsing":            contrat.source_parsing,
            "Statut TVA":                statut,
            "Rémunération HT (€)":       resultat.remuneration_ht,
            "Montant à facturer":        resultat.montant_facturer,
            "Détail calcul":             resultat.detail_calcul,
            "Canal":                     channel,
            "Alertes":                   " | ".join(resultat.alertes),
            "Notes parser":              contrat.notes,
            "_contrat_texte":            texte,
            "_contrat_json":             contrat.to_json(),
        })
    return pd.DataFrame(rows)

# ── Sidebar ────────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## Contrôles")
    autoriser_llm = st.toggle(
        "Fallback LLM (Gemini)",
        value=True,
        help="Active Gemini pour parser les contrats hors des 5 types déterministes.",
    )
    if st.button("Recharger / recalculer", use_container_width=True):
        st.cache_data.clear()
        st.session_state["_reload_toast"] = True
        st.rerun()

    st.markdown("---")
    st.markdown("## Légende")
    st.markdown("""
        <div class='legend-row'>
            <div class='legend-chip' style='background:#10b981'></div>
            <div>Parser déterministe (regex)</div>
        </div>
        <div class='legend-row'>
            <div class='legend-chip' style='background:#3b82f6'></div>
            <div>Parsé par LLM Gemini</div>
        </div>
        <div class='legend-row'>
            <div class='legend-chip' style='background:#f59e0b'></div>
            <div>Alerte ou ambiguïté</div>
        </div>
        <div class='legend-row'>
            <div class='legend-chip' style='background:#ef4444'></div>
            <div>Type inconnu / erreur</div>
        </div>
    """, unsafe_allow_html=True)

df = process_all(CSV_PATH, autoriser_llm)

if st.session_state.pop("_reload_toast", False):
    st.toast(f"✓ Pipeline relancé — {len(df)} contrats reparsés", icon="🔄")

# ── Filtres ────────────────────────────────────────────────────────────────────

st.markdown("<div class='section-title'>Portefeuille influenceurs</div>", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
with c1:
    choix_resp = ["Tous"] + sorted(df["Responsable"].unique().tolist())
    sel_resp = st.selectbox("Responsable", choix_resp)
with c2:
    choix_source = ["Toutes"] + sorted(df["Source parsing"].unique().tolist())
    sel_source = st.selectbox("Source parsing", choix_source)
with c3:
    choix_tva = ["Tous"] + sorted(df["Statut TVA"].unique().tolist())
    sel_tva = st.selectbox("Statut TVA", choix_tva)
with c4:
    only_alertes = st.checkbox("Alertes uniquement", value=False)

df_f = df.copy()
if sel_resp   != "Tous":    df_f = df_f[df_f["Responsable"]    == sel_resp]
if sel_source != "Toutes":  df_f = df_f[df_f["Source parsing"] == sel_source]
if sel_tva    != "Tous":    df_f = df_f[df_f["Statut TVA"]     == sel_tva]
if only_alertes:             df_f = df_f[df_f["Alertes"]        != ""]

# ── KPIs ───────────────────────────────────────────────────────────────────────

total_ht  = df_f["Rémunération HT (€)"].sum()
total_ttc = df_f["Montant à facturer"].dropna().sum()
nb_alert  = (df_f["Alertes"] != "").sum()
nb_llm    = (df_f["Source parsing"] == "llm").sum()
nb_manual = df_f["Montant à facturer"].isna().sum()

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    with st.container(border=True):
        st.metric("Influenceurs", len(df_f))
with k2:
    with st.container(border=True):
        st.metric("Total HT", f"{_fmt(total_ht, 0)} €")
with k3:
    with st.container(border=True):
        st.metric("Total TTC provisonné", f"{_fmt(total_ttc, 0)} €")
with k4:
    with st.container(border=True):
        st.metric("Alertes", nb_alert)
with k5:
    with st.container(border=True):
        st.metric("Manuels (TVA)", nb_manual)

# ── Référentiel des types de contrats ────────────────────────────────────────

with st.expander("📖 Référentiel des types de contrats — comprendre T1 à T5"):
    st.markdown(
        "Chaque contrat identifié dans le portefeuille est classé selon l'un des 5 types "
        "ci-dessous. Les contrats qui ne matchent aucun de ces types passent par le parseur "
        "LLM (Gemini) et sont taggés `LLM (X %)`."
    )
    ref_types = pd.DataFrame([
        {
            "Type": "T1",
            "Base fixe": "1 500 €",
            "Formule": "+ 4→10 % du CA total selon palier",
            "Notation": "R = 1 500 + t · CA  |  t ∈ {4, 6, 8, 9, 10}%",
            "Seuils": "8k / 9k / 10k / 11k / 12k €",
            "Notes": "Paliers 8k-11k inclusifs (≥). Palier 12k strict (au-delà de = >). Bug T1 12k identifié et corrigé.",
        },
        {
            "Type": "T2",
            "Base fixe": "4 600 €",
            "Formule": "+ 4 % du CA (flat, dès 0 €)",
            "Notation": "R = 4 600 + 0,04 · CA",
            "Seuils": "Aucun explicite",
            "Notes": "Contrat sous-spécifié dans Notion. Question ouverte à Yohan : le contrat papier a-t-il un seuil d'activation ?",
        },
        {
            "Type": "T3",
            "Base fixe": "2 000 €",
            "Formule": "+ 4→6 % du CA total selon palier",
            "Notation": "R = 2 000 + t · CA  |  t ∈ {4, 5, 6}%",
            "Seuils": "12k / 14k / 16k € (stricts)",
            "Notes": "Seuils écrits 'si CA >' (strict). Probable erreur de saisie — question ouverte à Yohan (voir @yanis.calisthenics à CA=12 000 exact).",
        },
        {
            "Type": "T4",
            "Base fixe": "0 €",
            "Formule": "Table de lookup (bonus fixe + taux %)",
            "Notation": "R = b + t · CA  |  (b, t) = lookup(palier)",
            "Seuils": "Couverture 1 000 - 5 000 €",
            "Notes": "Pas de base fixe. CA < 1 000 € = 0 € + alerte critique. CA > 5 000 € = palier max + alerte.",
        },
        {
            "Type": "T5",
            "Base fixe": "100 €",
            "Formule": "Base + table de lookup étendue",
            "Notation": "R = 100 + b + t · CA  |  (b, t) = lookup(palier)",
            "Seuils": "Couverture 500 - 5 000 €",
            "Notes": "Notation inversée sur palier 500 ('6 % + 65' vs '125 + 6' pour les autres). Interprétation uniforme : base + bonus_fixe + taux% × CA.",
        },
    ])
    st.dataframe(
        ref_types,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Type":      st.column_config.TextColumn(width="small"),
            "Base fixe": st.column_config.TextColumn(width="small"),
            "Formule":   st.column_config.TextColumn(width="medium"),
            "Notation":  st.column_config.TextColumn("Notation math",
                                width="medium",
                                help="R = rémunération HT. t = taux appliqué au palier atteint. b = bonus fixe du palier."),
            "Seuils":    st.column_config.TextColumn(width="medium"),
            "Notes":     st.column_config.TextColumn(width="large"),
        },
    )
    st.caption(
        "💡 Ce référentiel est aujourd'hui hardcodé dans le code — post-migration, il serait "
        "auto-généré depuis les métadonnées des types dans Notion (formulaire structuré à la signature)."
    )

# ── Tableau principal ──────────────────────────────────────────────────────────

st.markdown("<div class='section-title'>Détail par influenceur</div>", unsafe_allow_html=True)

df_display = df_f.copy()
df_display["Alerte"] = df_display["Alertes"].apply(
    lambda v: "" if not v else ("● " + str(len(v.split(" | "))))
)
df_display["v"] = df_display["Version"].str.split(" · ").str[0]

COLS_DISPLAY = [
    "Influenceur", "Responsable", "CA mois (€ HT)", "Tendance",
    "Type contrat", "v", "Source parsing",
    "Statut TVA", "Rémunération HT (€)", "Montant à facturer",
    "Canal", "Alerte",
]


def _style_source(val: str) -> str:
    if val == "regex":  return "background-color: #d1fae5; color: #065f46; font-weight: 600"
    if val == "llm":    return "background-color: #dbeafe; color: #1e40af; font-weight: 600"
    return "background-color: #fee2e2; color: #991b1b; font-weight: 600"


def _style_alerte(val: str) -> str:
    return "background-color: #fef3c7; color: #92400e; font-weight: 700; text-align: center" if val else ""


def _style_version(val: str) -> str:
    if val == "v2":
        return "background-color: #e0e7ff; color: #3730a3; font-weight: 700; text-align: center"
    return "color: #64748b; text-align: center"


def _style_tva(val: str) -> str:
    if val == "hors_ue": return "background-color: #fee2e2; color: #991b1b; font-weight: 700"
    if val == "inconnu":  return "background-color: #fef3c7; color: #92400e"
    return ""


styled = (
    df_display[COLS_DISPLAY]
    .style
    .map(_style_source,  subset=["Source parsing"])
    .map(_style_alerte,  subset=["Alerte"])
    .map(_style_tva,     subset=["Statut TVA"])
    .map(_style_version, subset=["v"])
    .format({
        "CA mois (€ HT)":       "{:,.0f} €",
        "Rémunération HT (€)":  "{:,.2f} €",
        "Montant à facturer":   lambda x: f"{x:,.2f} €" if pd.notna(x) else "Manuel",
    })
)

st.dataframe(
    styled,
    hide_index=True,
    use_container_width=True,
    height=min(500, 55 + 35 * len(df_f)),
    column_config={
        "Influenceur":           st.column_config.TextColumn(width="medium"),
        "Responsable":           st.column_config.TextColumn(width="small"),
        "CA mois (€ HT)":        st.column_config.TextColumn("CA mois (€ HT)", width="small"),
        "Tendance":              st.column_config.TextColumn(width="small"),
        "Type contrat":          st.column_config.TextColumn("Type", width="small"),
        "v":                     st.column_config.TextColumn("v", width="small",
                                     help="Version active du contrat. Détail complet dans le message généré."),
        "Source parsing":        st.column_config.TextColumn("Parser", width="small"),
        "Statut TVA":            st.column_config.TextColumn("TVA", width="small"),
        "Rémunération HT (€)":   st.column_config.TextColumn("Rému HT", width="medium"),
        "Montant à facturer":    st.column_config.TextColumn("À facturer", width="medium"),
        "Canal":                 st.column_config.TextColumn(width="small"),
        "Alerte":                st.column_config.TextColumn("⚠", width="small",
                                     help="Nombre d'alertes. Détail dans l'expander ci-dessous."),
    },
)

# ── Alertes détaillées ─────────────────────────────────────────────────────────

df_alertes = df_f[df_f["Alertes"] != ""]
if len(df_alertes):
    with st.expander(f"⚠ {len(df_alertes)} alerte(s) — détail", expanded=False):
        for _, r in df_alertes.iterrows():
            for alerte in r["Alertes"].split(" | "):
                if "🚨" in alerte:
                    st.error(f"**{r['Influenceur']}** — {alerte}")
                else:
                    st.warning(f"**{r['Influenceur']}** — {alerte}")

# ── LLM : transparence + démo migration ───────────────────────────────────────

df_llm = df_f[df_f["Source parsing"] == "llm"]
if len(df_llm):
    with st.expander(f"🤖 {len(df_llm)} contrat(s) parsé(s) par LLM — à valider", expanded=True):
        for _, r in df_llm.iterrows():
            st.markdown(f"**{r['Influenceur']}** — {r['Type contrat']}")
            col_a, col_b = st.columns(2)
            with col_a:
                st.markdown("**Contrat brut (texte libre)**")
                st.code(r["_contrat_texte"], language=None)
            with col_b:
                st.markdown("**Contrat structuré (JSON post-migration)**")
                st.code(r["_contrat_json"], language="json")
            if r["Notes parser"]:
                st.info(f"Notes LLM : {r['Notes parser']}")
            st.markdown(f"Calcul : {r['Détail calcul']}")
            st.divider()

# ── Démo migration : tous les contrats ────────────────────────────────────────

with st.expander("Vue migration — texte libre → JSON structuré (tous les contrats)"):
    if len(df_f) == 0:
        st.info("Aucun influenceur ne correspond aux filtres actuels.")
    else:
        choices = df_f["Influenceur"].tolist()
        # Reset si valeur persistée invalide (changement de filtre)
        if st.session_state.get("migr_sel") not in choices:
            st.session_state["migr_sel"] = choices[0]
        sel_migr = st.selectbox("Influenceur", choices, key="migr_sel")
        matches = df_f[df_f["Influenceur"] == sel_migr]
        if len(matches):
            row_m = matches.iloc[0]
            col_m1, col_m2 = st.columns(2)
            with col_m1:
                st.markdown("**Avant — texte libre Notion**")
                st.code(row_m["_contrat_texte"], language=None)
            with col_m2:
                st.markdown("**Après — champs structurés**")
                st.code(row_m["_contrat_json"], language="json")

st.divider()

# ── Livrables ──────────────────────────────────────────────────────────────────

st.markdown("<div class='section-title'>Livrables du cycle mensuel</div>", unsafe_allow_html=True)

tab_export, tab_messages = st.tabs(["Export comptabilité", "Messages influenceurs"])

with tab_export:
    df_compta = df_f[[
        "Influenceur", "Responsable", "CA mois (€ HT)",
        "Rémunération HT (€)", "Montant à facturer",
        "Statut TVA", "Canal", "Type contrat", "Version", "Alertes",
    ]].copy()
    csv_bytes = df_compta.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        "Télécharger le récap compta (CSV)",
        data=csv_bytes,
        file_name="nutripure_remuneration_mensuelle.csv",
        mime="text/csv",
        use_container_width=True,
    )
    st.caption("Aperçu des 10 premières lignes du fichier téléchargé ci-dessus.")
    st.dataframe(
        df_compta.head(10),
        use_container_width=True,
        hide_index=True,
        column_config={
            "Influenceur":         st.column_config.TextColumn(width="medium"),
            "Responsable":         st.column_config.TextColumn(width="small"),
            "CA mois (€ HT)":      st.column_config.NumberColumn(format="%.0f €", width="small"),
            "Rémunération HT (€)": st.column_config.NumberColumn("Rému HT", format="%.2f €", width="small"),
            "Montant à facturer":  st.column_config.NumberColumn("À facturer", format="%.2f €", width="small"),
            "Statut TVA":          st.column_config.TextColumn("TVA", width="small"),
            "Canal":               st.column_config.TextColumn(width="small"),
            "Type contrat":        st.column_config.TextColumn("Type", width="small"),
            "Version":             st.column_config.TextColumn(width="small"),
            "Alertes":             st.column_config.TextColumn(width="large"),
        },
    )

with tab_messages:
    if len(df_f) == 0:
        st.info("Aucun influenceur ne correspond aux filtres actuels.")
    else:
        handles = df_f["Influenceur"].tolist()
        if st.session_state.get("msg_sel") not in handles:
            st.session_state["msg_sel"] = handles[0]
        sel_h = st.selectbox("Influenceur", handles, key="msg_sel")
        matches = df_f[df_f["Influenceur"] == sel_h]
        if len(matches):
            r = matches.iloc[0]
            res = Resultat(
                remuneration_ht=r["Rémunération HT (€)"],
                montant_facturer=r["Montant à facturer"] if pd.notna(r["Montant à facturer"]) else None,
                detail_calcul=r["Détail calcul"],
            )
            msg = genere_message(
                handle=r["Influenceur"],
                ca=r["CA mois (€ HT)"],
                responsable=r["Responsable"],
                resultat=res,
                contact_channel=r["Canal"],
            )
            canal_label = r["Canal"].replace("dm_", "").capitalize()
            version_label = r["Version"]
            st.markdown(
                f"<div class='version-strip'>"
                f"<div class='version-chip'>{version_label.split(' · ')[0].upper()}</div>"
                f"<div class='version-meta'>Contrat signé le <strong>{version_label.split(' · ')[1]}</strong> · "
                f"Type <strong>{r['Type contrat']}</strong> · Canal <strong>{canal_label}</strong></div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            st.markdown("<div class='copy-hint'>📋 Clique sur l'icône en haut à droite du bloc pour copier.</div>", unsafe_allow_html=True)
            st.code(msg, language="markdown", wrap_lines=True)

st.divider()

# ── Répartition par type de contrat ───────────────────────────────────────────

st.markdown("<div class='section-title'>Répartition par type de contrat</div>", unsafe_allow_html=True)
recap = (
    df_f.groupby("Type contrat")
    .agg(Nb=("Influenceur", "count"), Total_HT=("Rémunération HT (€)", "sum"))
    .reset_index()
    .rename(columns={"Total_HT": "Total HT (€)"})
)
recap["Total HT (€)"] = recap["Total HT (€)"].map(lambda x: f"{_fmt(x, 2)} €")
st.dataframe(recap, use_container_width=True, hide_index=True)
