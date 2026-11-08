# Livraison Phase 4 T1 — pour l’assembleur

## À prendre

```text
phase_4_t1_evaluation/evaluation/
phase_4_t1_evaluation/tests/evaluation/
phase_4_t1_evaluation/data/          # questions.json
phase_4_t1_evaluation/docs/
phase_4_t1_evaluation/README.md
phase_4_t1_evaluation/requirements.txt
phase_4_t1_evaluation/.env.example
phase_4_t1_evaluation/pytest.ini
```

## À ne pas faire

- Ne pas remplacer le pipeline Phase 2 de `main`
- Ne pas remplacer `phase_3/`
- Ne pas écraser `requirements.txt` de `main` (httpx suffit souvent déjà)

## Dépendance runtime

- Endpoint **`POST /ask`** de la Phase 3 (contrat officiel à brancher)
- Ou `EVAL_ASK_MODE=mock` pour développement / CI sans serveur
- Variables : `EVAL_API_BASE_URL`, `EVAL_ASK_PATH`, `EVAL_HTTP_TIMEOUT_SECONDS`, `EVAL_ASK_MODE`

## Rapport produit

- `eval_report_{run_id}.json` / `eval_report_{run_id}.csv`
- Contrat métriques Phase 4 (voir `docs/ETAPE_0_CADRE.md` et `docs/phase4_t1_evaluation.md`)

## Vérification Ubuntu

```bash
cd phase_4_t1_evaluation
source ../.venv/bin/activate
python -m pytest tests/evaluation -v
EVAL_ASK_MODE=mock python -m evaluation.cli --run-id livraison_check
```

## Checklist assembleur

- [ ] `evaluation/` copié (sans écraser main)
- [ ] `tests/evaluation/` + `data/questions.json` copiés
- [ ] `EVAL_*` documentées côté déploiement
- [ ] Brancher `EVAL_ASK_MODE=http` dès que `POST /ask` est livré
- [ ] Contrat provisoire `/ask` remplacé par le contrat officiel (parseur seul)
