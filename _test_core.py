# -*- coding: utf-8 -*-
"""Tests clés pour nutripure_core — edge cases + régressions."""
from nutripure_core import parse_contrat, calcule_remuneration

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"

def check(label, actual, expected, tol=0.01):
    ok = abs(actual - expected) < tol if isinstance(expected, float) else actual == expected
    status = PASS if ok else FAIL
    print(f"{status}  {label}")
    if not ok:
        print(f"       attendu={expected!r}  obtenu={actual!r}")

def check_none(label, actual):
    ok = actual is None
    status = PASS if ok else FAIL
    print(f"{status}  {label}")
    if not ok:
        print(f"       attendu=None  obtenu={actual!r}")

def check_in(label, haystack, needle):
    ok = needle in haystack
    status = PASS if ok else FAIL
    print(f"{status}  {label}")
    if not ok:
        print(f"       '{needle}' introuvable dans {haystack!r}")


print("=" * 60)
print("TESTS NUTRIPURE CORE")
print("=" * 60)

# ── T1 : palier 12k strict ─────────────────────────────────────────────────────
print("\n── T1 paliers ──")
T1_TEXTE = "1 500 € HT fixe. À partir de 8 000 € : +4 % du CA total. À partir de 9 000 € : +6 %. À partir de 10 000 € : +8 %. À partir de 11 000 € : +9 %. Au-delà de 12 000 € : +10 %."
c = parse_contrat(T1_TEXTE, autoriser_llm=False)
check("T1 détecté",           c.type_detecte, "T1")
check("T1 base fixe",         c.base_fixe, 1500.0)

# CA=12000 exact → palier 11k (9%), NOT 10%
r = calcule_remuneration(c, 12000.0, "non_assujetti")
check("T1 CA=12000 → remu_ht=2580€ (11k palier, pas 12k)", r.remuneration_ht, 2580.0)
check("T1 CA=12000 → montant_facturer=2580€ (non_assujetti)", r.montant_facturer, 2580.0)
check_in("T1 CA=12000 → alerte palier strict", r.alertes, "ℹ️ CA = 12 000 € exact — palier 12k non déclenché ('au-delà de' = strict). Palier 11k (9 %) appliqué.")

# CA>12000 → palier 10%
r2 = calcule_remuneration(c, 12001.0, "non_assujetti")
check("T1 CA=12001 → palier 10% appliqué (12001*0.10+1500=2700.1)", r2.remuneration_ht, 2700.10)

# CA=7950 (lea.fitfuel) → aucun palier
r3 = calcule_remuneration(c, 7950.0, "non_assujetti")
check("T1 CA=7950 → base fixe seule (1500€)", r3.remuneration_ht, 1500.0)

# CA=8000 → palier 4% (à partir de = inclusif)
r4 = calcule_remuneration(c, 8000.0, "non_assujetti")
check("T1 CA=8000 → palier 4% inclusif (1500+0.04*8000=1820)", r4.remuneration_ht, 1820.0)

# ── T2 : flat ──────────────────────────────────────────────────────────────────
print("\n── T2 flat ──")
T2_TEXTE = "4 600 € HT fixe + 4 % du CA."
c2 = parse_contrat(T2_TEXTE, autoriser_llm=False)
check("T2 détecté",           c2.type_detecte, "T2")

# @maya.nutrition CA=11400, assujetti_20 → (4600 + 4%*11400) * 1.20 = 6105.60€
r5 = calcule_remuneration(c2, 11400.0, "assujetti_20")
check("T2 CA=11400 → remu_ht=5056€ (4600+4%×11400)", r5.remuneration_ht, 5056.0)
check("T2 CA=11400 assujetti_20 → montant_facturer=6067.20€", r5.montant_facturer, 6067.20)

# @paulperformance CA=0 → alerte T2
r6 = calcule_remuneration(c2, 0.0, "non_assujetti")
check("T2 CA=0 → base fixe 4600€",     r6.remuneration_ht, 4600.0)
check_in("T2 CA=0 → alerte", r6.alertes, "⚠️ CA = 0 € sur contrat T2 (base fixe garantie). Vérifier si actif.")

# ── T3 : strict ────────────────────────────────────────────────────────────────
print("\n── T3 stricts ──")
T3_TEXTE = "2 000 € HT fixe + variable : si CA > 12 000 € : +4 % du CA total du mois ; si CA > 14 000 € : +5 % ; si CA > 16 000 € : +6 %."
c3 = parse_contrat(T3_TEXTE, autoriser_llm=False)
check("T3 détecté",           c3.type_detecte, "T3")
check("T3 seuil_strict=True", c3.seuil_strict, True)

# @yanis.calisthenics CA=12000 → aucun palier (strict, =12000 ne déclenche pas)
r7 = calcule_remuneration(c3, 12000.0, "non_assujetti")
check("T3 CA=12000 → base fixe seule 2000€", r7.remuneration_ht, 2000.0)

# CA=12001 → palier 12k (4%)
r8 = calcule_remuneration(c3, 12001.0, "non_assujetti")
check("T3 CA=12001 → 4% (2000+0.04*12001=2480.04)", r8.remuneration_ht, 2480.04)

# ── T4 : table_lookup ─────────────────────────────────────────────────────────
print("\n── T4 table_lookup ──")
T4_TEXTE = "1000 : 6 + 100 / 1500 : 6 + 150 / 2000 : 8 + 200 / 3000 : 8 + 250 / 4000 : 8 + 300 / 5000 : 8 + 350"
c4 = parse_contrat(T4_TEXTE, autoriser_llm=False)
check("T4 détecté",           c4.type_detecte, "T4")
check("T4 base_fixe=0",       c4.base_fixe, 0.0)

# @ines.yoga.flow CA=950 < ca_min=1000 → base seule (0€) + alerte
r9 = calcule_remuneration(c4, 950.0, "non_assujetti")
check("T4 CA=950 < 1000 → remu_ht=0€", r9.remuneration_ht, 0.0)
check_in("T4 CA=950 → alerte minimum", r9.alertes, "⚠️ CA 950 € sous le minimum contractuel (1000 €). Base fixe uniquement.")

# @nadia.crossfit CA=2600 → palier 2000 (0.08*2600+200=408)
r10 = calcule_remuneration(c4, 2600.0, "non_assujetti")
check("T4 CA=2600 → palier 2000 (0+200+0.08*2600=408)", r10.remuneration_ht, 408.0)

# ── T5 : table étendue ─────────────────────────────────────────────────────────
print("\n── T5 table étendue ──")
T5_TEXTE = "100 € fixe puis 500 : 6 % + 65 / 1000 : 125 + 6 / 1500 : 200 + 6 / 2000 : 275 + 6 / 3000 : 350 + 8 / 4000 : 425 + 8 / 5000 : 500 + 8"
c5 = parse_contrat(T5_TEXTE, autoriser_llm=False)
check("T5 détecté",           c5.type_detecte, "T5")
check("T5 base_fixe=100",     c5.base_fixe, 100.0)

# @sofiane_mma CA=480 < ca_min=500 → base 100€ + alerte
r11 = calcule_remuneration(c5, 480.0, "non_assujetti")
check("T5 CA=480 < 500 → remu_ht=100€", r11.remuneration_ht, 100.0)
check_in("T5 CA=480 → alerte minimum", r11.alertes, "⚠️ CA 480 € sous le minimum contractuel (500 €). Base fixe uniquement.")

# @camille.marathon CA=500 → palier 500 (100+65+0.06*500=195)
r12 = calcule_remuneration(c5, 500.0, "non_assujetti")
check("T5 CA=500 → palier 500 (100+65+0.06*500=195)", r12.remuneration_ht, 195.0)

# @raph.gym CA=1750 → palier 1500 (100+200+0.06*1750=405)
r13 = calcule_remuneration(c5, 1750.0, "non_assujetti")
check("T5 CA=1750 → palier 1500 (100+200+0.06*1750=405)", r13.remuneration_ht, 405.0)

# ── TVA ────────────────────────────────────────────────────────────────────────
print("\n── TVA / statut ──")
T1_C = parse_contrat(T1_TEXTE, autoriser_llm=False)

# hors_ue → montant_facturer=None + 🚨 alerte
r14 = calcule_remuneration(T1_C, 9200.0, "hors_ue")
check_none("T1 CA=9200 hors_ue → montant_facturer=None", r14.montant_facturer)
check_in("T1 hors_ue → alerte 🚨", r14.alertes, "🚨 Statut TVA hors-UE : règles intracom applicables. Montant à facturer à calculer manuellement avec la comptabilité.")

# inconnu → montant_facturer=None + ⚠️ alerte
r15 = calcule_remuneration(T1_C, 9200.0, "inconnu")
check_none("T1 CA=9200 inconnu → montant_facturer=None", r15.montant_facturer)
check_in("T1 inconnu → alerte ⚠️", r15.alertes, "⚠️ Statut TVA inconnu. Vérifier avant envoi du message de facturation.")

# assujetti_20 → TTC = HT * 1.20
r16 = calcule_remuneration(T1_C, 10450.0, "assujetti_20")   # juliette.wellness
check("T1 CA=10450 assujetti_20 → remu_ht=2336€", r16.remuneration_ht, 2336.0)
check("T1 CA=10450 assujetti_20 → montant_facturer=2803.20€", r16.montant_facturer, 2803.20)

print("\n" + "=" * 60)
print("Tous les tests terminés.")
