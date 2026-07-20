# -*- coding: utf-8 -*-
"""
Nutripure — Calculateur de rémunération influenceurs.
Core : parsing hybride (déterministe + LLM Gemini), calcul TVA, génération messages.
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field, asdict
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

# ── Constantes colonnes CSV ────────────────────────────────────────────────────

COL_ID              = "influencer_id"
COL_HANDLE          = "influenceur"
COL_RESPONSABLE     = "responsable_influence"
COL_CONTRAT         = "contrat_paliers_texte_libre"
COL_CA_MOIS         = "ca_mois_courant_ht"
COL_CA_12M          = "ca_12_mois_glissant_ht"
COL_STATUT_TVA      = "statut_tva"
COL_CHANNEL         = "contact_channel"
COL_DATE_DEBUT      = "date_debut_contrat"
COL_VERSION         = "contract_version"
COL_DATE_SIGNATURE  = "date_signature_contrat"

TVA_RATES: dict[str, Optional[float]] = {
    "non_assujetti": 0.0,
    "assujetti_20":  0.20,
    "hors_ue":       None,   # Ne pas calculer — flag humain
    "inconnu":       None,
}

# ── Modèles ────────────────────────────────────────────────────────────────────

@dataclass
class Palier:
    seuil:      float
    taux:       float            # décimal : 0.06 = 6 %
    bonus_fixe: float = 0.0


@dataclass
class Contrat:
    type_detecte:   str
    base_fixe:      float
    paliers:        list[Palier]  # ordonnés seuil décroissant
    application:    str           # "seuil_taux_total" | "flat" | "table_lookup"
    seuil_strict:   bool  = False # True = ">", False = ">="
    ca_min:         Optional[float] = None
    ca_max:         Optional[float] = None
    source_parsing: str  = "regex"
    notes:          str  = ""

    def to_json(self) -> str:
        """Sérialise le contrat structuré (utilisé pour la démo migration)."""
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


@dataclass
class Resultat:
    remuneration_ht:    float
    montant_facturer:   Optional[float]   # None si TVA non calculable
    detail_calcul:      str
    alertes:            list[str] = field(default_factory=list)
    palier_applique:    Optional[Palier] = None

# ── Détection du type de contrat ──────────────────────────────────────────────

def _detecte_type(texte: str) -> str:
    t = texte.strip()
    if re.search(r"4\s*600.*fixe.*\+\s*4\s*%", t, re.DOTALL):
        return "T2"
    if re.search(r"1\s*500.*fixe.*8\s*000.*9\s*000.*10\s*000.*11\s*000.*12\s*000", t, re.DOTALL):
        return "T1"
    if re.search(r"2\s*000.*fixe.*12\s*000.*14\s*000.*16\s*000", t, re.DOTALL):
        return "T3"
    if re.search(r"100\s*€?\s*fixe\s*puis", t):
        return "T5"
    if re.search(r"^\s*1000\s*:", t):
        return "T4"
    return "INCONNU"

# ── Parsers déterministes ──────────────────────────────────────────────────────

def _parse_t1(_: str) -> Contrat:
    """1 500 € fixe + paliers NON-MARGINAUX. Palier 12k = strict (au-delà de)."""
    return Contrat(
        type_detecte="T1",
        base_fixe=1500.0,
        paliers=[
            # Le palier 12 000 utilise "au-delà de" → strict (>)
            # Les paliers 8k-11k utilisent "à partir de" → inclusif (≥)
            # On modélise avec seuil_strict=False globalement et on gère
            # le cas 12k en le plaçant avec un seuil légèrement > 12000 via
            # une vérification manuelle dans calcule_remuneration (flag T1_12K).
            Palier(seuil=12000.0, taux=0.10),
            Palier(seuil=11000.0, taux=0.09),
            Palier(seuil=10000.0, taux=0.08),
            Palier(seuil=9000.0,  taux=0.06),
            Palier(seuil=8000.0,  taux=0.04),
        ],
        application="seuil_taux_total",
        seuil_strict=False,
        source_parsing="regex",
        notes="Paliers 8k-11k inclusifs (≥). Palier 12k strict (au-delà de = >). "
              "À CA=12 000€ exact, c'est le palier 11k (9%) qui s'applique.",
    )


def _parse_t2(_: str) -> Contrat:
    """4 600 € fixe + 4 % du CA mensuel. Pas de seuil — appliqué dès 0 €.
    Hypothèse : absence de seuil = intentionnelle. À valider avec Yohan."""
    return Contrat(
        type_detecte="T2",
        base_fixe=4600.0,
        paliers=[Palier(seuil=0.0, taux=0.04)],
        application="flat",
        source_parsing="regex",
        notes="Contrat sous-spécifié : pas de seuil explicite, 'du CA' interprété "
              "comme CA mensuel (cross-inférence T3). Hypothèse : taux plat dès 0 €.",
    )


def _parse_t3(_: str) -> Contrat:
    """2 000 € fixe + paliers NON-MARGINAUX avec seuils STRICTS (si CA >)."""
    return Contrat(
        type_detecte="T3",
        base_fixe=2000.0,
        paliers=[
            Palier(seuil=16000.0, taux=0.06),
            Palier(seuil=14000.0, taux=0.05),
            Palier(seuil=12000.0, taux=0.04),
        ],
        application="seuil_taux_total",
        seuil_strict=True,   # "si CA >" = strict
        source_parsing="regex",
        notes="Seuils stricts (si CA > X). À CA = seuil exact, aucun palier déclenché.",
    )


def _parse_t4(_: str) -> Contrat:
    """Table de lookup CA→(taux% × CA + bonus). Couverture 1 000–5 000 €."""
    return Contrat(
        type_detecte="T4",
        base_fixe=0.0,
        paliers=[
            Palier(seuil=5000.0, taux=0.08, bonus_fixe=350.0),
            Palier(seuil=4000.0, taux=0.08, bonus_fixe=300.0),
            Palier(seuil=3000.0, taux=0.08, bonus_fixe=250.0),
            Palier(seuil=2000.0, taux=0.08, bonus_fixe=200.0),
            Palier(seuil=1500.0, taux=0.06, bonus_fixe=150.0),
            Palier(seuil=1000.0, taux=0.06, bonus_fixe=100.0),
        ],
        application="table_lookup",
        ca_min=1000.0,
        ca_max=5000.0,
        source_parsing="regex",
        notes="Aucune garantie contractuelle sous 1 000 €. "
              "Comportement au-delà de 5 000 € non spécifié — hypothèse : palier max.",
    )


def _parse_t5(_: str) -> Contrat:
    """100 € base fixe + table de lookup étendue. Couverture 500–5 000 €.
    AMBIGUÏTÉ : palier 500 noté '6 % + 65' (taux d'abord) vs les suivants
    '125 + 6' (fixe d'abord). Interprétation retenue : partout bonus_fixe + taux% × CA."""
    return Contrat(
        type_detecte="T5",
        base_fixe=100.0,
        paliers=[
            Palier(seuil=5000.0, taux=0.08, bonus_fixe=500.0),
            Palier(seuil=4000.0, taux=0.08, bonus_fixe=425.0),
            Palier(seuil=3000.0, taux=0.08, bonus_fixe=350.0),
            Palier(seuil=2000.0, taux=0.06, bonus_fixe=275.0),
            Palier(seuil=1500.0, taux=0.06, bonus_fixe=200.0),
            Palier(seuil=1000.0, taux=0.06, bonus_fixe=125.0),
            Palier(seuil=500.0,  taux=0.06, bonus_fixe=65.0),
        ],
        application="table_lookup",
        ca_min=500.0,
        ca_max=5000.0,
        source_parsing="regex",
        notes="AMBIGUÏTÉ notation : palier 500 écrit '6 % + 65' alors que les suivants "
              "écrivent 'fixe + taux'. Interprétation uniforme retenue : base + bonus_fixe + taux%×CA.",
    )


_PARSERS: dict[str, object] = {
    "T1": _parse_t1,
    "T2": _parse_t2,
    "T3": _parse_t3,
    "T4": _parse_t4,
    "T5": _parse_t5,
}

# ── Fallback LLM (Gemini) ──────────────────────────────────────────────────────

_LLM_CLIENT = None

def _gemini_client():
    global _LLM_CLIENT
    if _LLM_CLIENT is not None:
        return _LLM_CLIENT
    from google import genai as google_genai
    raw = os.getenv("GEMINI_API_KEY", "")
    key = raw.split(",")[0].strip().strip('"')
    if not key:
        raise RuntimeError("GEMINI_API_KEY introuvable.")
    _LLM_CLIENT = google_genai.Client(api_key=key)
    return _LLM_CLIENT


_LLM_SCHEMA = {
    "type": "object",
    "properties": {
        "base_fixe":    {"type": "number"},
        "application":  {"type": "string", "enum": ["seuil_taux_total", "flat", "table_lookup"]},
        "seuil_strict": {"type": "boolean"},
        "ca_min":       {"type": "number"},
        "ca_max":       {"type": "number"},
        "paliers": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "seuil":      {"type": "number"},
                    "taux":       {"type": "number"},
                    "bonus_fixe": {"type": "number"},
                },
                "required": ["seuil", "taux"],
            },
        },
        "confiance": {"type": "number"},
        "notes":     {"type": "string"},
    },
    "required": ["base_fixe", "application", "paliers", "confiance", "notes"],
}

_LLM_PROMPT = """\
Tu es un parseur de contrats de rémunération d'influenceurs (Nutripure).
Convertis le contrat en JSON déterministe pour calcul mensuel.

Règles :
- "à partir de X €" = seuil inclusif → seuil_strict: false
- "si CA > X €"     = seuil strict   → seuil_strict: true
- "du CA total"     = taux sur CA total (non-marginal)
- Ordonne les paliers par seuil DÉCROISSANT
- Convertis % en décimal (6 % → 0.06)
- ca_min / ca_max = 0 si non spécifié
- confiance entre 0 et 1

Contrat :
---
{texte}
---"""


def _parse_llm(texte: str) -> Contrat:
    from google.genai import types as genai_types
    client = _gemini_client()
    resp = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=_LLM_PROMPT.format(texte=texte),
        config=genai_types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=_LLM_SCHEMA,
            temperature=0.0,
        ),
    )
    data: dict = json.loads(resp.text)
    paliers = sorted(
        [Palier(seuil=p["seuil"], taux=p["taux"], bonus_fixe=p.get("bonus_fixe", 0.0))
         for p in data["paliers"]],
        key=lambda x: x.seuil,
        reverse=True,
    )
    confiance = data.get("confiance", 0.0)
    return Contrat(
        type_detecte=f"LLM ({confiance:.0%})",
        base_fixe=data["base_fixe"],
        paliers=paliers,
        application=data["application"],
        seuil_strict=data.get("seuil_strict", False),
        ca_min=data.get("ca_min") or None,
        ca_max=data.get("ca_max") or None,
        source_parsing="llm",
        notes=data.get("notes", ""),
    )

# ── Parser principal ───────────────────────────────────────────────────────────

def parse_contrat(texte: str, autoriser_llm: bool = True) -> Contrat:
    """Dispatch déterministe, puis LLM en fallback."""
    type_detecte = _detecte_type(texte)
    if type_detecte in _PARSERS:
        fn = _PARSERS[type_detecte]
        return fn(texte)  # type: ignore[operator]
    if autoriser_llm:
        try:
            return _parse_llm(texte)
        except Exception as exc:
            return Contrat(
                type_detecte="INCONNU",
                base_fixe=0.0,
                paliers=[],
                application="flat",
                source_parsing="regex",
                notes=f"Échec parsing déterministe ET LLM : {type(exc).__name__} — {str(exc)[:200]}",
            )
    return Contrat(
        type_detecte="INCONNU",
        base_fixe=0.0,
        paliers=[],
        application="flat",
        source_parsing="regex",
        notes="Type non reconnu. Fallback LLM désactivé.",
    )

# ── Calcul de rémunération ─────────────────────────────────────────────────────

def calcule_remuneration(contrat: Contrat, ca: float, statut_tva: str = "inconnu") -> Resultat:
    alertes: list[str] = []

    # ── Alertes spéciales ──────────────────────────────────────────────────────
    if contrat.type_detecte == "T2" and ca == 0.0:
        alertes.append("⚠️ CA = 0 € sur contrat T2 (base fixe garantie). Vérifier si actif.")

    # ── Gestion bornes de couverture ───────────────────────────────────────────
    if contrat.ca_min is not None and ca < contrat.ca_min:
        alertes.append(
            f"⚠️ CA {ca:.0f} € sous le minimum contractuel ({contrat.ca_min:.0f} €). "
            "Base fixe uniquement."
        )
        remu_ht = contrat.base_fixe
        detail = f"Base fixe {contrat.base_fixe:.2f} € (CA sous seuil minimum)"
        return _build_resultat(remu_ht, detail, alertes, statut_tva)

    if contrat.ca_max is not None and ca > contrat.ca_max:
        alertes.append(
            f"⚠️ CA {ca:.0f} € au-delà du plafond contractuel ({contrat.ca_max:.0f} €). "
            "Hypothèse : palier maximum appliqué."
        )

    # ── Calcul selon application ───────────────────────────────────────────────
    if contrat.application == "flat":
        p = contrat.paliers[0]
        remu_ht = contrat.base_fixe + p.taux * ca
        detail = (
            f"{contrat.base_fixe:.2f} € fixe + {p.taux*100:.0f} % × {ca:.0f} € "
            f"= {remu_ht:.2f} €"
        )
        return _build_resultat(remu_ht, detail, alertes, statut_tva, palier=p)

    # Trouver le palier applicable (seuils ordonnés décroissants)
    palier_applique: Optional[Palier] = None
    for p in contrat.paliers:
        if contrat.type_detecte == "T1" and p.seuil == 12000.0:
            # Palier 12k de T1 = "au-delà de" = STRICT (>)
            if ca > p.seuil:
                palier_applique = p
                break
            elif ca == p.seuil:
                alertes.append(
                    "ℹ️ CA = 12 000 € exact — palier 12k non déclenché "
                    "('au-delà de' = strict). Palier 11k (9 %) appliqué."
                )
                # Ne pas break — on continue au palier 11k
        else:
            condition = (ca > p.seuil) if contrat.seuil_strict else (ca >= p.seuil)
            if condition:
                # Alerte si CA exactement au seuil avec contrat strict
                if contrat.seuil_strict and ca == p.seuil:
                    alertes.append(
                        f"⚠️ CA exactement au seuil {p.seuil:.0f} € — "
                        "palier non déclenché (contrat strict : CA > seuil requis)."
                    )
                    continue
                palier_applique = p
                break

    if palier_applique is None:
        # T1 edge case : CA=12000 exact → aucun palier strict, mais palier 11k inclusif
        if contrat.type_detecte == "T1" and ca == 12000.0:
            for p in contrat.paliers:
                if p.seuil == 11000.0:
                    palier_applique = p
                    alertes.append(
                        "ℹ️ CA = 12 000 € exact — palier 12k non déclenché "
                        "('au-delà de' = strict). Palier 11k (9 %) appliqué."
                    )
                    break

    if palier_applique is None:
        remu_ht = contrat.base_fixe
        detail = f"Base fixe {contrat.base_fixe:.2f} € (aucun palier déclenché)"
        return _build_resultat(remu_ht, detail, alertes, statut_tva)

    if contrat.application == "seuil_taux_total":
        remu_ht = contrat.base_fixe + palier_applique.taux * ca
        detail = (
            f"{contrat.base_fixe:.2f} € fixe + palier {palier_applique.seuil:.0f} € atteint "
            f"→ {palier_applique.taux*100:.0f} % × {ca:.0f} € (CA total) = {remu_ht:.2f} €"
        )
    elif contrat.application == "table_lookup":
        remu_ht = contrat.base_fixe + palier_applique.bonus_fixe + palier_applique.taux * ca
        parts = []
        if contrat.base_fixe:
            parts.append(f"{contrat.base_fixe:.2f} € base")
        parts.append(f"{palier_applique.bonus_fixe:.2f} € (palier {palier_applique.seuil:.0f} €)")
        parts.append(f"{palier_applique.taux*100:.0f} % × {ca:.0f} € = {palier_applique.taux*ca:.2f} €")
        detail = " + ".join(parts) + f" = {remu_ht:.2f} €"
    else:
        remu_ht = contrat.base_fixe
        detail = f"Application '{contrat.application}' non gérée — base fixe uniquement."
        alertes.append(f"⚠️ Application inconnue : {contrat.application}")

    return _build_resultat(remu_ht, detail, alertes, statut_tva, palier=palier_applique)


def _build_resultat(
    remu_ht: float,
    detail: str,
    alertes: list[str],
    statut_tva: str,
    palier: Optional[Palier] = None,
) -> Resultat:
    tva_rate = TVA_RATES.get(statut_tva)
    if tva_rate is None:
        # hors_ue ou inconnu → montant à facturer non calculable
        montant_facturer: Optional[float] = None
        if statut_tva == "hors_ue":
            alertes.append(
                "🚨 Statut TVA hors-UE : règles intracom applicables. "
                "Montant à facturer à calculer manuellement avec la comptabilité."
            )
        elif statut_tva == "inconnu":
            alertes.append(
                "⚠️ Statut TVA inconnu. Vérifier avant envoi du message de facturation."
            )
    else:
        montant_facturer = round(remu_ht * (1 + tva_rate), 2)

    return Resultat(
        remuneration_ht=round(remu_ht, 2),
        montant_facturer=montant_facturer,
        detail_calcul=detail,
        alertes=alertes,
        palier_applique=palier,
    )

# ── Trend indicator (CA mois vs baseline 12M) ──────────────────────────────────

def calcule_tendance(ca_mois: float, ca_12m: float, date_debut: Optional[str] = None) -> str:
    """Retourne un indicateur de tendance lisible.
    Fiable uniquement si l'influenceur a au moins 12 mois d'historique.
    """
    if date_debut:
        try:
            from datetime import date
            debut = date.fromisoformat(date_debut)
            mois_actifs = (date.today() - debut).days / 30
            if mois_actifs < 11:
                return "— (< 12 mois)"
        except ValueError:
            pass

    if ca_12m <= 0:
        return "—"

    baseline = ca_12m / 12
    if baseline == 0:
        return "—"

    delta = (ca_mois - baseline) / baseline
    if delta <= -0.30:
        return f"↓ {delta:+.0%}"
    if delta >= 0.30:
        return f"↑ {delta:+.0%}"
    return f"→ {delta:+.0%}"

# ── Génération du message à l'influenceur ──────────────────────────────────────

_CHANNEL_LABELS: dict[str, str] = {
    "dm_instagram": "Instagram DM",
    "dm_tiktok":    "TikTok DM",
    "email":        "Email",
    "whatsapp":     "WhatsApp",
}


def _fmt(x: float, decimals: int = 2) -> str:
    """Format euros : espace milliers, virgule décimale."""
    s = f"{x:,.{decimals}f}"
    return s.replace(",", " ").replace(".", ",")


def genere_message(
    handle: str,
    ca: float,
    responsable: str,
    resultat: Resultat,
    contact_channel: str = "dm_instagram",
) -> str:
    channel_label = _CHANNEL_LABELS.get(contact_channel, contact_channel)

    if resultat.montant_facturer is not None:
        ligne_facture = f"Merci de nous adresser une facture de **{_fmt(resultat.montant_facturer)} €**"
        if resultat.remuneration_ht != resultat.montant_facturer:
            ligne_facture += f" TTC (soit {_fmt(resultat.remuneration_ht)} € HT + TVA)"
        ligne_facture += "."
    else:
        ligne_facture = (
            f"Le montant à facturer est à définir avec notre comptabilité "
            f"(base HT : {_fmt(resultat.remuneration_ht)} €) — "
            "ton statut TVA nécessite un traitement particulier."
        )

    return (
        f"Bonjour {handle},\n\n"
        f"Voici le récapitulatif de ta rémunération Nutripure pour le mois en cours.\n\n"
        f"• CA généré : {_fmt(ca, 0)} € HT\n"
        f"• Rémunération due : {_fmt(resultat.remuneration_ht)} € HT\n\n"
        f"Détail du calcul :\n{resultat.detail_calcul}\n\n"
        f"{ligne_facture}\n\n"
        f"Canal de contact : {channel_label}\n\n"
        f"Belle journée,\n{responsable}"
    )
