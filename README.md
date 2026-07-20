# Nutripure — Cycle rémunérations (prototype)

Prototype pour le cas d'étude Builder IA & Automatisation de Nutripure.

Automatise le passage **contrat texte libre + CA mensuel → rémunération HT + montant à facturer TTC → messages prêts à envoyer** pour ~500 influenceurs gérés par 3 responsables.

## Architecture

**Stack** : Python + Streamlit.

**Parsing hybride** :
- 5 parseurs déterministes (regex) pour les 5 types de contrats identifiés (T1–T5)
- Fallback Gemini pour les contrats hors-pattern
- Le LLM est un outil de migration one-shot, pas un moteur de calcul mensuel

Une fois la migration terminée, le calcul mensuel est 100 % déterministe.

## Structure

- `nutripure_core.py` — parseurs, dataclasses `Contrat` / `Resultat`, calcul de rémunération + TVA, génération de messages
- `nutripure_prototype.py` — interface Streamlit
- `influenceurs_echantillon.csv` — 29 lignes (25 originales + 4 synthétiques pour couvrir les edge cases : hors-UE, versioning, régression T1 12k)
- `_test_core.py` — 28 tests de régression (edge cases + calculs TVA)
- `assets/` — logo et favicon Nutripure
- `.streamlit/config.toml` — palette Nutripure (#00557c / #77d2f5 / #1B1B1B)

## Run local

```bash
pip install -r requirements.txt
echo "GEMINI_API_KEY=votre_cle" > .env
streamlit run nutripure_prototype.py
```

## Tests

```bash
python -X utf8 _test_core.py
```

28/28 doivent passer.
