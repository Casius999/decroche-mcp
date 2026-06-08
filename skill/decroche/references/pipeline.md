# Pipeline 360° — rechercher & postuler au MAXIMUM (P2-P5)

Ce playbook étend le skill au-delà du CV : trouver le plus d'offres pertinentes, postuler à la source
(gated), suivre, préparer l'entretien, négocier. Mêmes bornes d'intégrité que le CV (honesty-guardrails.md).

## Outils (namespaces montés)
`source_*` (sourcing) · `match_*` (score/keyword_gap/dedupe/success_probability/company_intel) ·
`recruiter_*` / `network_*` · `apply_*` (resolve/prefill/cover_letter/answer_screening/queue/send/followup) ·
`analytics_*` (CRM/funnel) · `interview_*` · `negotiate_*` · plus les `cv_*`/`ats_*`/`market_*` du cœur.

---

## A. Sourcing LARGE (P2) — entrée principale
1. **Cadre** : rôle(s) cible, région/marché, mots-clés, séniorité (depuis `cv_parse` + l'utilisateur).
2. **`source_search_market(query, region, use_keyed=True)`** = fan-out de TOUS les providers en une requête :
   - keyed (si clés env présentes) : **JSearch** (LinkedIn/Indeed/Glassdoor licite), **France Travail** (tout FR), **Adzuna** (multi-pays) ;
   - keyless via `data/known_boards.yaml` : Greenhouse/Lever/Ashby/Recruitee (par entreprise) ;
   - dédup automatique (`match_dedupe`), tri par récence. Les providers sans clé sont **ignorés silencieusement** (warning).
3. **Compléments ciblés** : `source_labonneboite` (marché caché FR), `source_careerjet`, `source_remotive`/`source_remoteok` (remote), ou un board précis `source_greenhouse(token)`.
4. **Veille** : `monitor_snapshot` puis `monitor_diff` pour capter les nouvelles offres d'un board.
> Breadth MAX = fournir les clés env : `JSEARCH_RAPIDAPI_KEY`, `FRANCE_TRAVAIL_ID/SECRET`, `ADZUNA_APP_ID/KEY` (+ `USAJOBS_*`, `REED_KEY`, `JOOBLE_KEY`). Sans clés → seulement les boards par-entreprise.

## B. Priorisation (postuler malin ET en volume)
Pour chaque offre : `match_score(cv, offre)` + `match_success_probability` (+ `match_company_intel`). Trie.
Seuil : prépare une candidature si fit ≥ ~50/100 et `missing_must` raisonnable ; sinon écarte ou signale les compétences à acquérir (jamais mentir).

## C. Tailoring CV par offre (réutilise le cœur P1)
Pour chaque offre retenue : `ats_parse_sim` + `ats_redflag_scan` + `match_keyword_gap` + `ats_screener_brief` (joue le screener) → réécriture XYZ honnête → `cv_render` ATS-safe (prouvé par round-trip). Garde un JSON Resume maître + variantes par offre.

## D. Intel recruteur + réseau (P3) — fort levier (référence ≈ 4×)
`recruiter_identify`/`recruiter_qualify`/`recruiter_find_contact` (sur données **collées** par l'utilisateur, jamais de scraping) + `recruiter_draft_message` (opt-out RGPD). `network_find_warm_path` → `network_draft_intro_request` pour une intro chaude.

## E. Candidature GATED (P4) — apply-at-source, file + validation en lot
1. `apply_resolve_source(job)` → URL **ATS employeur** (jamais l'Easy Apply LinkedIn).
2. Prépare : `apply_prefill(cv, job)` + `apply_cover_letter(cv, job, lang)` + `apply_answer_screening(question, cv)` pour chaque question custom.
3. `apply_queue_add` chaque candidature prête.
4. `apply_queue_review` → **l'humain revoit la file**.
5. `apply_queue_approve(ids)` → validation **en lot**.
6. `apply_send_approved(queue, confirm_send=True)` → envoie les **approuvées** via l'ATS source.
   **Garde-fous durs (inviolables)** : jamais de mot de passe/CB, **stop avant paiement**, **stop si login requis**, jamais un item non-approuvé. Champs sensibles refusés. (Pré-requis : `uv sync --extra browser` + `playwright install chromium` + Chrome lancé `--remote-debugging-port=9222`, `CHROME_CDP_URL`.)
7. `apply_followup` → relances polies (gated).

## F. Suivi (CRM + analytics)
`analytics_track` à chaque candidature → stage ; `analytics_update_stage` à chaque évènement ; `analytics_funnel` + `analytics_channel_roi` + `analytics_bottleneck` → **diagnostique le goulot** : pas de réponse = ciblage/CV à revoir ; entretiens sans offre = prep entretien.

## G. Entretien & négociation (P5) — convertir
- `interview_company_brief` (5 sections) · `interview_story_bank` (STAR+E) · `interview_question_bank(role_family, kind)` · `interview_mock_evaluate(answer)` (Claude joue le recruteur) · `interview_thank_you`.
- `negotiate_benchmark_range(role_family, seniority, region)` (dataset sourcé) · `negotiate_counter_offer_template` · `negotiate_total_comp`.

---

## Boucle « max offres » (résumé exécutable)
```
search_market(query, region) → dedup → pour chaque offre:
  match_score + success_probability → si fit≥seuil:
    tailor CV (cœur P1) → apply_prefill + cover_letter + answer_screening → apply_queue_add
apply_queue_review → (humain) apply_queue_approve(lot) → apply_send_approved(confirm_send=True)
→ analytics_track chacune. Répète par requête/marché. monitor_diff pour le flux. funnel pour le goulot.
```

## Garde-fous (rappel, mêmes que le cœur)
Honnêteté : ne jamais inventer (CV, lettre = preuves CV réelles, screening éligibilité/visa/salaire = `needs_human`).
Conformité : apply-at-source, **zéro scraping/auto-apply LinkedIn**, RGPD (opt-out + rétention 3 ans), secrets via env (jamais dans les erreurs).
